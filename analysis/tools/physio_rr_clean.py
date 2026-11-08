"""physio 工具 04 的全部处理逻辑：H10 RR 伪迹清理（只输出数据，不画图）。

方法：丢包只标记、不填补；每个无空洞片段内由 RR 累加重建峰时刻，
用 neurokit2.signal_fixpeaks(method="kubios")（Lipponen & Tarvainen, 2019）识别并校正漏检、多检、异位搏、长短拍。
校正前后的峰集合逐一比对，判定每个输出 RR 的 handling：
    0 原样保留  1 漏检补拍  2 多检合并  3 异位搏或长短拍校正  4 待人工（仍异常，未修改）
（含义登记在 global_settings.VALUE_LABELS["rr_handling"]）

输入（只读）：data/<数据集>/processed/physio/sub-P###/merged/rr.csv
输出：data/<数据集>/processed/physio/sub-P###/clean/rr.csv、holes.csv、report.txt（覆盖同名文件）
      data/<数据集>/processed/physio/rr_clean_summary.csv（每人一行，重跑只替换本次被试的行）
写入前检查路径在 processed/physio/ 之内。
"""
import numpy as np
import pandas as pd

import neurokit2 as nk

from paths import layer_dir
from physio_xdf import check_inside, list_subjects, normalize_subject

SUMMARY_COLUMNS = ["subject", "n_raw", "n_clean", "n_handling_0", "n_handling_1", "n_handling_2",
                   "n_handling_3", "n_handling_4", "n_holes", "holes_total_s", "n_segments",
                   "n_short_segments", "sum_check_ok", "n_prepass_split", "n_prepass_inserted", "n_prepass_merged", "n_kubios_reverted", "n_unresolved_reverted"]
HANDLING_NAMES = {0: "原样保留", 1: "漏检补拍", 2: "多检合并", 3: "异位搏或长短拍校正", 4: "待人工（仍异常，未修改）"}
SUM_TOL_MS = 2.0
FS = 1000


# ---------- 切段 ----------

def split_segments(rr, cfg):
    """按 t_unix 排序、剔除无效行、在空洞或 part 变化处切段。返回 (清洗后表, 片段索引列表, 空洞表, 剔除行数)。"""
    rr = rr.sort_values("t_unix", kind="stable").reset_index(drop=True)
    ms = pd.to_numeric(rr["ms"], errors="coerce")
    bad = ~np.isfinite(ms) | (ms <= 0)
    n_dropped = int(bad.sum())
    rr = rr.loc[~bad].reset_index(drop=True)
    t = rr["t_unix"].to_numpy(float)
    ms = rr["ms"].to_numpy(float)
    part = rr["part"].astype(str).to_numpy()
    n = len(rr)

    excess = np.zeros(n)
    excess[1:] = (t[1:] - t[:-1]) * 1000.0 - ms[1:]
    is_hole = np.zeros(n, bool)
    is_hole[1:] = excess[1:] > cfg["GAP_EXCESS_MS"]
    part_change = np.zeros(n, bool)
    part_change[1:] = part[1:] != part[:-1]
    brk = is_hole | part_change

    holes = []
    for i in np.flatnonzero(is_hole):
        around = np.r_[ms[max(0, i - 5):i], ms[i:i + 5]]
        med = float(np.median(around))
        holes.append({"part": part[i], "t_start": t[i - 1], "t_end": t[i], "dur_s": excess[i] / 1000.0,
                      "est_missing_beats": int(round(excess[i] / med))})
    holes = pd.DataFrame(holes, columns=["part", "t_start", "t_end", "dur_s", "est_missing_beats"])

    starts = np.r_[0, np.flatnonzero(brk)] if n else np.array([], int)
    ends = np.r_[starts[1:], n]
    segs = [np.arange(a, b) for a, b in zip(starts, ends)]
    return rr, segs, holes, n_dropped


# ---------- 整数倍切分预处理 ----------

def prepass_reference(t, ms, window_s):
    """每拍的参考 RR：该拍前后各 window_s 秒内全部原始 RR 的中位数（跨片段取）。"""
    lo = np.searchsorted(t, t - window_s, side="left")
    hi = np.searchsorted(t, t + window_s, side="right")
    return np.array([np.median(ms[a:b]) for a, b in zip(lo, hi)])


def prepass_split(ms, t, ref, cfg):
    """预处理（对一个片段）：先"多检合并"，再"整数倍切分"。

    多检合并：从前往后扫描相邻两拍 a、b，若 a、b 都 < 0.75×参考 且 |(a+b)/参考 − 1| < MULTI_TOL，
    合并为一拍（a+b），handling 记 2，跳过 b 继续扫描。参考取后一拍 b 的参考值。
    整数倍切分：k = round(ms/参考)，2 ≤ k ≤ MULTI_MAX_K 且 |ms/(k×参考) − 1| < MULTI_TOL，则等分为 k 个，handling 记 1。
    返回 (新 ms, 新 t_unix 终点, 新 handling, 终点是否新插入峰, 合并次数, 切分的原始 RR 个数, 新增拍数)。"""
    n = len(ms)
    m_ms, m_t, m_ref, m_h = [], [], [], []
    n_merged = 0
    i = 0
    while i < n:
        if i + 1 < n:
            r = ref[i + 1]
            a, b = ms[i], ms[i + 1]
            if a < 0.75 * r and b < 0.75 * r and abs((a + b) / r - 1) < cfg["MULTI_TOL"]:
                m_ms.append(a + b); m_t.append(t[i + 1]); m_ref.append(r); m_h.append(2)
                n_merged += 1
                i += 2
                continue
        m_ms.append(ms[i]); m_t.append(t[i]); m_ref.append(ref[i]); m_h.append(0)
        i += 1

    out_ms, out_t, out_h, out_ins = [], [], [], []
    n_split = n_ins = 0
    for m, tt, r, h in zip(m_ms, m_t, m_ref, m_h):
        k = int(round(m / r))
        if h == 0 and 2 <= k <= cfg["MULTI_MAX_K"] and abs(m / (k * r) - 1) < cfg["MULTI_TOL"]:
            start = tt - m / 1000.0
            for j in range(1, k + 1):
                out_ms.append(m / k)
                out_t.append(start + j * m / k / 1000.0)
                out_h.append(1)
                out_ins.append(j < k)
            n_split += 1
            n_ins += k - 1
        else:
            out_ms.append(m)
            out_t.append(tt)
            out_h.append(h)
            out_ins.append(False)
    return (np.array(out_ms), np.array(out_t), np.array(out_h, int), np.array(out_ins, bool),
            n_merged, n_split, n_ins)


# ---------- 校正 ----------

def classify(orig, fixed, rr_orig_med, prepass_peaks=frozenset()):
    """比较原始峰与校正后峰，返回校正后每个 RR（len(fixed)-1）的 handling。

    原始峰不在校正集中、校正集中新增的峰：先按位置就近一一配对（距离不超过 0.5 个局部 RR）视为"移动"；
    配对不上的新增峰视为"补拍"，配对不上的被删峰视为"合并"。
    """
    orig_set = set(orig.tolist())
    fixed_set = set(fixed.tolist())
    removed = np.array(sorted(orig_set - fixed_set), float)
    added = np.array(sorted(fixed_set - orig_set), float)
    tol = 0.5 * rr_orig_med
    moved_added, inserted, merged_removed = set(), set(), []
    used = np.zeros(len(removed), bool)
    for a in added:
        if len(removed):
            d = np.abs(removed - a)
            d[used] = np.inf
            j = int(np.argmin(d))
            if d[j] <= tol:
                used[j] = True
                moved_added.add(int(a))
                continue
        inserted.add(int(a))
    merged_removed = removed[~used]

    h = np.zeros(len(fixed) - 1, int)
    # 优先级：移动(3) > 补拍(1) > 合并(2)
    for k in range(len(fixed) - 1):
        a, b = int(fixed[k]), int(fixed[k + 1])
        label = 0
        if len(merged_removed) and np.any((merged_removed > a) & (merged_removed < b)):
            label = 2
        if a in inserted or b in inserted or a in prepass_peaks or b in prepass_peaks:
            label = 1
        if a in moved_added or b in moved_added:
            label = 3
        h[k] = label
    return h


def revert_regions(P, K, ins_peaks, kept_peaks, merged_pairs):
    """Kubios 不得推翻预处理：找出 K 与 P 不同的每个连续区域（边界取两侧最近的、在 P 与 K 中位置相同的峰），
    区域内含预处理插入的峰或合并保留下来的峰（合并后一拍的起止峰；区域边界恰好就是某次合并的起止峰时也算），
    则该区域整体退回 P 的峰位置。返回 (最终峰, 退回区域数)。"""
    common = np.intersect1d(P, K)
    bounds = np.r_[-np.inf, common.astype(float), np.inf]
    special = ins_peaks | kept_peaks
    keep = [common]
    n_rev = 0
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        pin = P[(P > lo) & (P < hi)]
        kin = K[(K > lo) & (K < hi)]
        if len(pin) == 0 and len(kin) == 0:
            continue
        revert = any(int(x) in special for x in pin) or (lo, hi) in merged_pairs
        if revert:
            keep.append(pin)
            n_rev += 1
        else:
            keep.append(kin)
    return np.unique(np.concatenate(keep)).astype(np.int64), n_rev


def correct_segment(ms, t0, h0, ins_end, orig_sum, cfg):
    """校正一个片段（ms 为预处理后的 RR，h0 为其预处理标记，ins_end 标出终点为预处理新插入峰的 RR，
    t0 为片段起点的绝对时间，orig_sum 为预处理前 RR 之和）。
    返回 dict：ms、t_unix、handling、info 计数、n_reverted。"""
    P = np.round(np.r_[0.0, np.cumsum(ms)]).astype(np.int64)  # n+1 个峰，毫秒整数位置
    ins_peaks = {int(P[i + 1]) for i in np.flatnonzero(ins_end)}
    merged_idx = np.flatnonzero(h0 == 2)
    kept_peaks = {int(P[i]) for i in merged_idx} | {int(P[i + 1]) for i in merged_idx}
    merged_pairs = {(float(P[i]), float(P[i + 1])) for i in merged_idx}
    out = {"orig_sum": float(orig_sum)}
    info, K = nk.signal_fixpeaks(P, sampling_rate=FS, iterative=True, method="kubios", show=False)
    K = np.asarray(K, np.int64)
    out["info"] = {k: len(info.get(k, [])) for k in ("ectopic", "missed", "extra", "longshort")}
    fixed, n_rev = revert_regions(P, K, ins_peaks, kept_peaks, merged_pairs)
    med = float(np.median(ms))
    h = classify(P, fixed, med, ins_peaks)
    # 与 P 中相邻两峰完全对应的 RR：沿用预处理结果
    pos = {int(v): i for i, v in enumerate(P)}
    for k in range(len(fixed) - 1):
        ia, ib = pos.get(int(fixed[k])), pos.get(int(fixed[k + 1]))
        if ia is not None and ib is not None and ib == ia + 1:
            h[k] = h0[ia]
    out.update(ms=np.diff(fixed).astype(float), t_unix=t0 + fixed[1:] / 1000.0, handling=h,
               fixed_sum=float(fixed[-1] - fixed[0]), orig_span=float(orig_sum), n_reverted=n_rev,
               P=P, fixed=fixed, t0=t0)
    return out


def unresolved_revert(res, handling, win, rel):
    """复查之后：对 Kubios 改动过的每个连续区域（与"退回预处理"同一划分方式：P 与最终峰集合不同的区域，
    边界取两侧最近的、在两者中位置相同的峰），若区域内有任何一拍 handling=4，该区域整体恢复为预处理前后未被
    Kubios 改动的峰（区域内部即原始 RR，数值与时间都用原始值），区域内全部拍 handling 记 4。
    返回 (ms, t_unix, handling, 退回区域数, 校正后 RR 之和)。"""
    P, F, t0 = res["P"], res["fixed"], res["t0"]
    common = np.intersect1d(P, F)
    bounds = np.r_[-np.inf, common.astype(float), np.inf]
    old_h = {(int(F[k]), int(F[k + 1])): handling[k] for k in range(len(F) - 1)}
    keep, regions, n_rev = [common], [], 0
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        pin = P[(P > lo) & (P < hi)]
        fin = F[(F > lo) & (F < hi)]
        if len(pin) == 0 and len(fin) == 0:
            continue
        if np.array_equal(pin, fin):
            keep.append(fin)
            continue
        idx = [k for k in range(len(F) - 1) if F[k] >= lo and F[k + 1] <= hi]
        if any(handling[k] == 4 for k in idx):
            keep.append(pin)
            regions.append((lo, hi))
            n_rev += 1
        else:
            keep.append(fin)
    if n_rev == 0:
        return np.diff(F).astype(float), t0 + F[1:] / 1000.0, handling, 0, float(F[-1] - F[0])
    F2 = np.unique(np.concatenate(keep)).astype(np.int64)
    h2 = np.zeros(len(F2) - 1, int)
    for k in range(len(F2) - 1):
        a, b = int(F2[k]), int(F2[k + 1])
        if any(a >= lo and b <= hi for lo, hi in regions):
            h2[k] = 4
        else:
            h2[k] = old_h.get((a, b), 0)
    return np.diff(F2).astype(float), t0 + F2[1:] / 1000.0, h2, n_rev, float(F2[-1] - F2[0])


def residual_flag(ms, handling, win, rel):
    """片段内滚动中位数（中心对齐）复查；偏离超过 rel 的拍 handling 改 4。返回 (handling, 局部中位数)。"""
    med = pd.Series(ms).rolling(win, center=True, min_periods=1).median().to_numpy()
    handling = handling.copy()
    handling[np.abs(ms - med) / med > rel] = 4
    return handling, med


# ---------- 单个被试 ----------

def clean_subject(dataset, pid, processed, cfg):
    subject_dir = processed / f"sub-{pid}"
    src = subject_dir / "merged" / "rr.csv"
    if not src.is_file():
        raise ValueError(f"sub-{pid} 没有 merged/rr.csv（先运行工具 02）")
    raw = pd.read_csv(src, dtype={"part": str})
    n_raw = len(raw)
    rr, segs, holes, n_dropped = split_segments(raw, cfg)

    frames, short_segs, failed, sum_bad, info_tot = [], [], [], [], {"ectopic": 0, "missed": 0, "extra": 0, "longshort": 0}
    t_all = rr["t_unix"].to_numpy(float)
    ms_all = rr["ms"].to_numpy(float)
    ref_all = prepass_reference(t_all, ms_all, cfg["MULTI_REF_WINDOW_S"])
    n_split_tot = n_ins_tot = n_merged_tot = n_rev_tot = n_unres_tot = 0
    part_all = rr["part"].astype(str).to_numpy()
    for si, idx in enumerate(segs, start=1):
        ms0, t = ms_all[idx], t_all[idx]
        t0 = t[0] - ms0[0] / 1000.0
        ms, t, h0, ins_end, n_merged, n_split, n_ins = prepass_split(ms0, t, ref_all[idx], cfg)
        n_merged_tot += n_merged
        n_split_tot += n_split
        n_ins_tot += n_ins
        res = None
        if len(idx) >= cfg["MIN_SEG_BEATS"]:
            try:
                res = correct_segment(ms, t0, h0, ins_end, ms0.sum(), cfg)
            except Exception as error:  # noqa: BLE001  校正失败：原样输出并在报告列出
                failed.append((si, f"{type(error).__name__}: {error}"))
        else:
            short_segs.append(si)
        if res is None:
            seg_ms, seg_t, seg_h = ms.copy(), t.copy(), h0.copy()
            seg_h, _ = residual_flag(seg_ms, seg_h, cfg["RESIDUAL_WIN"], cfg["RESIDUAL_REL"])
        else:
            n_rev_tot += res["n_reverted"]
            for k, v in res["info"].items():
                info_tot[k] += v
            seg_h, _ = residual_flag(res["ms"], res["handling"], cfg["RESIDUAL_WIN"], cfg["RESIDUAL_REL"])
            seg_ms, seg_t, seg_h, n_unres, fixed_sum = unresolved_revert(
                res, seg_h, cfg["RESIDUAL_WIN"], cfg["RESIDUAL_REL"])
            n_unres_tot += n_unres
            diff = fixed_sum - res["orig_span"]
            if abs(diff) > SUM_TOL_MS:
                sum_bad.append((si, diff))
        gap = np.zeros(len(seg_ms), int)
        gap[0] = 1
        frames.append(pd.DataFrame({"t_unix": seg_t, "part": part_all[idx[0]], "segment": si,
                                    "ms": np.round(seg_ms, 1), "gap_before": gap, "handling": seg_h}))
    clean = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["t_unix", "part", "segment", "ms", "gap_before", "handling"])
    if len(clean):
        clean.loc[0, "gap_before"] = 0

    # 清理后仍 > 1.7 倍局部中位数的 RR 个数（同 RESIDUAL_WIN，按片段）
    n_big = 0
    for _, g in clean.groupby("segment"):
        med = g["ms"].rolling(cfg["RESIDUAL_WIN"], center=True, min_periods=1).median()
        n_big += int((g["ms"] > 1.7 * med).sum())

    out_dir = subject_dir / "clean"
    check_inside(out_dir, processed)
    out_dir.mkdir(parents=True, exist_ok=True)
    clean.to_csv(check_inside(out_dir / "rr.csv", processed), index=False, float_format="%.6f")
    holes.to_csv(check_inside(out_dir / "holes.csv", processed), index=False, float_format="%.6f")

    counts = {k: int((clean["handling"] == k).sum()) for k in range(5)}
    summary = {"subject": f"sub-{pid}", "n_raw": n_raw, "n_clean": len(clean),
               **{f"n_handling_{k}": counts[k] for k in range(5)},
               "n_holes": len(holes), "holes_total_s": round(float(holes["dur_s"].sum()), 3),
               "n_segments": len(segs), "n_short_segments": len(short_segs),
               "sum_check_ok": int(not sum_bad and not failed),
               "n_prepass_split": n_split_tot, "n_prepass_inserted": n_ins_tot,
               "n_prepass_merged": n_merged_tot, "n_kubios_reverted": n_rev_tot,
               "n_unresolved_reverted": n_unres_tot}

    lines = [f"RR 伪迹清理报告 sub-{pid}（数据集 {dataset}）", "",
             f"原始拍数：{n_raw}",
             f"剔除行数（ms 非有限或 ≤0）：{n_dropped}",
             f"片段数：{len(segs)}；其中未校正短片段（< {cfg['MIN_SEG_BEATS']} 拍）：{len(short_segs)}"
             + (f"（片段号 {short_segs}）" if short_segs else ""),
             f"预处理：多检合并 {n_merged_tot} 次；整数倍切分的原始 RR 个数 {n_split_tot}，因此新增拍数 {n_ins_tot}",
             f"Kubios 结果退回预处理（区域个数）：{n_rev_tot}",
             f"Kubios 未解决而退回原始 RR 的区域个数（n_unresolved_reverted）：{n_unres_tot}",
             f"清理后拍数：{len(clean)}", "", "各处理类别拍数与占比："]
    for k in range(5):
        pct = 100.0 * counts[k] / len(clean) if len(clean) else 0.0
        lines.append(f"  {k} {HANDLING_NAMES[k]}：{counts[k]}（{pct:.2f}%）")
    lines += ["", f"空洞个数：{len(holes)}；总时长：{holes['dur_s'].sum():.1f} s；估计丢失拍数合计：{int(holes['est_missing_beats'].sum())}",
              f"清理后仍 > 1.7 倍局部中位数的 RR：{n_big}",
              f"neurokit2 返回的索引条数合计（仅供参考）：{info_tot}", "", "自检（每个片段校正后 RR 之和与原始之差 ≤ "
              f"{SUM_TOL_MS:g} ms）："]
    if not sum_bad and not failed:
        lines.append("  全部通过")
    for si, d in sum_bad:
        lines.append(f"  未通过：片段 {si}，差 {d:+.1f} ms")
    for si, msg in failed:
        lines.append(f"  校正失败（该片段原样输出，handling=0）：片段 {si}，{msg}")
    lines += ["", f"neurokit2 版本：{nk.__version__}",
              "方法：signal_fixpeaks(sampling_rate=1000, iterative=True, method=\"kubios\")",
              "设置区参数：" + "；".join(f"{k}={v}" for k, v in cfg.items())]
    check_inside(out_dir / "report.txt", processed).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary, n_big


def merge_summary(summary, path, root):
    """只替换本次被试的行。"""
    target = check_inside(path, root)
    if target.is_file():
        old = pd.read_csv(target, dtype={"subject": str})
        old = old[old["subject"] != summary["subject"]]
        df = pd.concat([old, pd.DataFrame([summary])], ignore_index=True)
    else:
        df = pd.DataFrame([summary])
    df = df.sort_values("subject")[SUMMARY_COLUMNS]
    df[SUMMARY_COLUMNS[1:]] = df[SUMMARY_COLUMNS[1:]].fillna(0).astype({c: int for c in SUMMARY_COLUMNS[1:] if c != "holes_total_s"})
    df.to_csv(target, index=False)


# ---------- 入口 ----------

def run(dataset, subjects, cfg):
    processed = layer_dir(dataset, "processed", "physio")
    pool = [p for p in list_subjects(processed) if (processed / f"sub-{p}" / "merged" / "rr.csv").is_file()]
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"这些被试没有 merged/rr.csv：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"processed/physio 中没有含 merged/rr.csv 的被试：{processed}（先运行工具 02）")
    print(f"数据集 {dataset}：共 {len(chosen)} 位被试；neurokit2 {nk.__version__}")
    results = []
    for pid in chosen:
        print(f"[开始] {pid}")
        summary, n_big = clean_subject(dataset, pid, processed, cfg)
        merge_summary(summary, processed / "rr_clean_summary.csv", processed)
        print(f"[完成] {pid}：{summary['n_raw']} → {summary['n_clean']} 拍；空洞 {summary['n_holes']}；"
              f"自检 {'通过' if summary['sum_check_ok'] else '未通过'}；clean/ 与 rr_clean_summary.csv 已更新")
        results.append((summary, n_big))
    return results
