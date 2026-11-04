"""physio 工具 03 的全部处理与绘图函数：RR、HR、ECG 绘图检查与质量报告。

输入（只读）：data/<数据集>/processed/physio/sub-P###/merged/
    ecg.csv、acc.csv（可能没有）、hr.csv、rr.csv、markers.csv、gaps.csv、segments.csv
输出：data/<数据集>/processed/physio/preview/signal/（所有被试平铺在同一文件夹，文件名以被试编号开头）
    P001_overview_raw.png     全程总览（ECG 包络、HR、RR、ACC）
    P001_rr_raw.png           全程 RR 散点图（宽图）
    P001_rr_raw_page_01.png…  仅当 RR_PAGES=True 时输出：只画 RR，每页 RR_PAGE_MIN 分钟
    P001_report_raw.txt       中文报告
    quality.csv           所有被试合在一张表（第一列 subject）；重跑时只替换本次被试的行

时间一律用 t_unix；图的横轴显示北京时间 HH:MM；图上文字用英文。
只读 merged/，不修改任何数据文件；写入前检查路径在 processed/physio/ 之内。
"""
import math
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # 无界面环境也能出图
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

from paths import layer_dir  # noqa: E402
from physio_merge import TZ_BEIJING, t_local  # noqa: E402
from physio_xdf import check_inside, list_subjects, normalize_subject  # noqa: E402

SIGNAL_SUBDIR = ("preview", "signal")  # 相对 processed/physio/
MERGED_DIR = "merged"
TABLE_FILES = ["ecg.csv", "acc.csv", "hr.csv", "rr.csv", "markers.csv", "gaps.csv", "segments.csv"]
QUALITY_COLUMNS = ["part", "duration_s", "ecg_samples", "ecg_expected", "ecg_completeness_pct",
                   "rr_n", "rr_out_of_range_n", "rr_jump_n", "hr_vs_rr_mae_bpm", "ble_gap_n"]

# 颜色
COLOR_NORMAL = "#7a9e7e"  # 灰绿：正常 RR
COLOR_OUT = "#ff8c00"     # 橙：超出 RR_MIN_MS–RR_MAX_MS
COLOR_JUMP = "#d62728"    # 红：与前一个 RR 相比变化超过 RR_JUMP（疑似跳变，待工具 04 判断）
COLOR_SEG = "0.85"        # 灰底：段间空档（recording gap）
COLOR_BLE = "#f4b6b6"     # 浅红底：gap_start 到 gap_end（BLE gap）


# ---------- 读取 ----------

def load_merged(merged):
    """读入 merged/ 下的表。缺的表给空表（列名保留），缺 acc.csv 时 ACC 相关图留空。"""
    empty_cols = {
        "ecg.csv": ["t_unix", "time_lsl", "part", "uV"],
        "acc.csv": ["t_unix", "time_lsl", "part", "x_mG", "y_mG", "z_mG"],
        "hr.csv": ["t_unix", "time_lsl", "part", "bpm"],
        "rr.csv": ["t_unix", "time_lsl", "part", "ms"],
        "markers.csv": ["t_unix", "time_lsl", "part", "label", "t_local"],
        "gaps.csv": ["t_unix", "time_lsl", "part", "label"],
        "segments.csv": ["part", "start_unix", "end_unix", "start_local", "end_local",
                         "offset", "offset_iqr", "n_clock_rows", "tables"],
    }
    data = {}
    for name in TABLE_FILES:
        path = merged / name
        if path.is_file():
            df = pd.read_csv(path, dtype={"part": str, "label": str})
        else:
            df = pd.DataFrame(columns=empty_cols[name])
        data[name[:-4]] = df
    data["has_acc"] = (merged / "acc.csv").is_file()
    return data


# ---------- 标记与异常点 ----------

def flag_rr(rr, cfg):
    """给每个 RR 点加两个标记（在同一段内判断）。

    out_of_range：RR 不在 [RR_MIN_MS, RR_MAX_MS]
    jump：与同段前一个 RR 相比，变化超过前一个的 RR_JUMP（比例）
    """
    rr = rr.sort_values("t_unix").reset_index(drop=True).copy()
    ms = rr["ms"].astype(float)
    rr["out_of_range"] = (ms < cfg["RR_MIN_MS"]) | (ms > cfg["RR_MAX_MS"])
    prev = ms.groupby(rr["part"]).shift(1)
    rr["jump"] = ((ms - prev).abs() / prev > cfg["RR_JUMP"]).fillna(False).astype(bool)
    return rr


def gap_spans(gaps, t_end):
    """每条 gap_start 到其后第一条 gap_end 之间的区间；找不到 gap_end 的延伸到 t_end。"""
    g = gaps.sort_values("t_unix")
    starts = g.loc[g["label"].str.startswith("gap_start"), "t_unix"].to_numpy()
    ends = np.sort(g.loc[g["label"].str.startswith("gap_end"), "t_unix"].to_numpy())
    spans = []
    for s in starts:
        i = np.searchsorted(ends, s)
        spans.append((s, ends[i] if i < len(ends) else t_end))
    return spans


def segment_gap_spans(segments):
    """相邻两段之间的空档（前段止 → 后段起）。"""
    seg = segments.dropna(subset=["start_unix", "end_unix"]).sort_values("start_unix")
    spans = []
    for (_, prev), (_, nxt) in zip(seg.iterrows(), seg.iloc[1:].iterrows()):
        if nxt["start_unix"] > prev["end_unix"]:
            spans.append((prev["end_unix"], nxt["start_unix"]))
    return spans


# ---------- 绘图 ----------

def hhmm(x, _pos=None):
    """Unix 秒 → 北京时间 HH:MM（横轴刻度用）。"""
    return datetime.fromtimestamp(x, TZ_BEIJING).strftime("%H:%M")


def decorate(ax, ctx):
    """统一画底色、标记竖线和横轴。标记文字不画在图上，统一放在图底部（见 finish_figure）。"""
    for a, b in ctx["seg_spans"]:
        ax.axvspan(a, b, color=COLOR_SEG, zorder=0)
    for a, b in ctx["gap_spans"]:
        ax.axvspan(a, b, color=COLOR_BLE, alpha=0.6, zorder=0)
    for t, _label in ctx["markers"]:
        ax.axvline(t, color="k", ls="--", lw=0.7, alpha=0.7, zorder=1)
    ax.set_xlim(ctx["t0"], ctx["t1"])
    ax.xaxis.set_major_formatter(FuncFormatter(hhmm))
    ax.grid(alpha=0.2)


def gap_handles(ctx):
    """底色图例项：只列出本图实际存在的底色。"""
    handles = []
    if ctx["seg_spans"]:
        handles.append(Patch(facecolor=COLOR_SEG, label="recording gap"))
    if ctx["gap_spans"]:
        handles.append(Patch(facecolor=COLOR_BLE, alpha=0.6, label="BLE gap"))
    return handles


MARKER_LABEL_ROWS = 3  # 相邻的 marker 标签最多上下错开的行数


def place_marker_labels(ax, ctx, fig_width_in):
    """在图的上边标注 marker 名称：只写 label，横排，细字。
    两个 marker 距离太近时，标签自动放到下一行（最多 MARKER_LABEL_ROWS 行）。"""
    span = ctx["t1"] - ctx["t0"]
    if span <= 0 or not ctx["markers"]:
        return
    axis_px = fig_width_in * 110 * 0.91  # 与 save_figure 的 dpi、subplots_adjust 的左右边距一致
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    row_end = [-np.inf] * MARKER_LABEL_ROWS
    for t, label in sorted(ctx["markers"]):
        width_s = (len(label) * 5.5 + 8) / axis_px * span  # 估计标签占用的时间宽度
        free = [r for r in range(MARKER_LABEL_ROWS) if t >= row_end[r]]
        row = free[0] if free else int(np.argmin(row_end))
        row_end[row] = t + width_s
        ax.text(t, 0.98 - 0.075 * row, " " + label, transform=trans, fontsize=6.5, color="0.2",
                ha="left", va="top", zorder=4,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.5))


def finish_figure(fig, title, handles, ctx):
    """统一版式：标题、图注（一行，放在标题下方），底部 x 轴标注 Time (HH:MM)。"""
    fig.suptitle(title, fontsize=11, y=0.985)
    if handles:
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.945),
                   ncol=len(handles), frameon=False, fontsize=9)
    fig.subplots_adjust(top=0.87, bottom=0.10, left=0.07, right=0.98, hspace=0.3)
    fig.axes[-1].set_xlabel("Time (HH:MM)")


def save_figure(fig, name, out_dir, root, dpi=110):
    target = check_inside(out_dir / name, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=dpi)
    plt.close(fig)
    return target


def split_at_gaps(t, y, max_step=5.0):
    """相邻两点时间差超过 max_step 秒时，在中间插入 NaN，使折线在无数据处断开。"""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(t) < 2:
        return t, y
    brk = np.where(np.diff(t) > max_step)[0]
    if len(brk) == 0:
        return t, y
    idx = brk + 1
    return np.insert(t, idx, (t[brk] + t[brk + 1]) / 2), np.insert(y, idx, np.nan)


def rr_categories(rr):
    """三类布尔掩码：超出范围（橙）、跳变（红，且不属于超出范围）、正常（灰绿）。"""
    out = rr["out_of_range"].to_numpy(dtype=bool)
    jump = rr["jump"].to_numpy(dtype=bool) & ~out
    normal = ~out & ~jump
    return normal, out, jump


def rr_limits(rr, percentile=(0, 100)):
    """RR 纵轴范围：按 percentile（如 (0, 100) 为全部数据，(0.5, 99.5) 为主体数据）取上下限，
    上下各留 5% 余量；没有数据时返回 None。"""
    lo_p, hi_p = percentile
    if not (0 <= lo_p < hi_p <= 100):
        raise ValueError(f"RR_YAXIS_PERCENTILE 应满足 0 <= 下限 < 上限 <= 100，当前为 {percentile}")
    ms = rr["ms"].to_numpy(dtype=float)
    if len(ms) == 0:
        return None
    lo, hi = np.percentile(ms, [lo_p, hi_p])
    pad = max(0.05 * (hi - lo), 1.0)
    return float(lo - pad), float(hi + pad)


def yaxis_note(cfg):
    """所选百分位不是 (0, 100) 时，返回标题末尾的说明；否则返回空串。"""
    lo_p, hi_p = cfg["RR_YAXIS_PERCENTILE"]
    if (lo_p, hi_p) == (0, 100):
        return ""
    return f", y-axis: P{lo_p:g}-P{hi_p:g}"


def draw_rr(ax, rr, cfg, ylim):
    """画 RR 散点。数据正常时不做任何提示：只有存在对应的点才画该类并返回它的图例项；
    只有存在超出范围的点时才画两条阈值虚线。纵轴按数据缩放（ylim），不额外标注范围。"""
    t = rr["t_unix"].to_numpy(dtype=float)
    ms = rr["ms"].to_numpy(dtype=float)
    normal, out, jump = rr_categories(rr)
    handles = []
    if normal.any():
        handles.append(ax.scatter(t[normal], ms[normal], s=3, color=COLOR_NORMAL, label="normal", zorder=2))
    if out.any():
        handles.append(ax.scatter(t[out], ms[out], s=10, color=COLOR_OUT,
                                  label=f"out of range ({cfg['RR_MIN_MS']}-{cfg['RR_MAX_MS']} ms)", zorder=3))
        ax.axhline(cfg["RR_MIN_MS"], ls=":", color="k", lw=0.8)
        ax.axhline(cfg["RR_MAX_MS"], ls=":", color="k", lw=0.8)
    if jump.any():
        handles.append(ax.scatter(t[jump], ms[jump], s=10, color=COLOR_JUMP,
                                  label=f"jump >{cfg['RR_JUMP']:.0%} vs previous (suspect)", zorder=3))
    if ylim is not None:
        ax.set_ylim(*ylim)  # 放在最后，避免被阈值线或自动缩放覆盖
    ax.set_ylabel("RR (ms)")
    return handles


def plot_overview(d, cfg, ctx, pid, out_dir, root):
    fig, (a1, a2, a3, a4) = plt.subplots(4, 1, figsize=(16, 14), sharex=True,
                                         gridspec_kw={"hspace": 0.3})
    t0 = ctx["t0"]

    ecg = d["ecg"]
    if len(ecg):
        sec = np.floor(ecg["t_unix"] - t0)
        g = ecg.assign(sec=sec).groupby("sec")["uV"].agg(["min", "max"])
        # 按整秒铺满，没有数据的秒保持空，包络带在断开处断开
        full = np.arange(g.index.min(), g.index.max() + 1)
        g = g.reindex(full)
        lo, hi = g["min"].to_numpy(), g["max"].to_numpy()
        x = t0 + full + 0.5
        a1.fill_between(x, lo, hi, where=np.isfinite(lo) & np.isfinite(hi), lw=0, color="C0", alpha=0.85)
    a1.set_ylabel("ECG (uV)")
    a1.set_title("ECG: 1-second min/max envelope")

    hr = d["hr"]
    if len(hr):
        a2.plot(*split_at_gaps(hr["t_unix"], hr["bpm"]), lw=0.6, color="C1")
    a2.set_ylabel("HR (bpm)")
    a2.set_title("HR (bpm)")

    rr_handles = draw_rr(a3, d["rr_flag"], cfg, ctx["rr_ylim"]) if len(d["rr_flag"]) else []
    a3.set_title("RR (ms)")

    acc = d["acc"]
    if len(acc):
        mag = np.sqrt(acc["x_mG"] ** 2 + acc["y_mG"] ** 2 + acc["z_mG"] ** 2)
        g = pd.DataFrame({"t": acc["t_unix"], "mag": mag}).assign(sec=lambda x: np.floor(x["t"] - t0))
        m = g.groupby("sec")["mag"].mean()
        a4.plot(*split_at_gaps(t0 + m.index.to_numpy() + 0.5, m.to_numpy()), lw=0.6, color="C4")
    else:
        a4.text(0.5, 0.5, "no acc.csv for these segments (left blank)", transform=a4.transAxes,
                ha="center", va="center", color="0.4")
    a4.set_title("ACC: 1-second mean of sqrt(x^2+y^2+z^2) (mG)")
    a4.set_ylabel("ACC (mG)")

    for ax in (a1, a2, a3, a4):
        decorate(ax, ctx)
    place_marker_labels(a1, ctx, 16)
    finish_figure(fig, f"{pid} physio overview{yaxis_note(cfg)}", rr_handles + gap_handles(ctx), ctx)
    return save_figure(fig, f"{pid}_overview_raw.png", out_dir, root)


def plot_rr_full(d, cfg, ctx, pid, out_dir, root):
    """全程 RR 散点图（宽图，24×6 英寸）。"""
    rr = d["rr_flag"]
    fig, ax = plt.subplots(figsize=(24, 6))
    handles = draw_rr(ax, rr, cfg, ctx["rr_ylim"]) if len(rr) else []
    _, out, jump = rr_categories(rr)
    decorate(ax, ctx)
    place_marker_labels(ax, ctx, 24)
    finish_figure(fig, f"{pid} RR over the whole session: {len(rr)} beats, "
                       f"{int(out.sum())} out of range, {int(jump.sum())} jump (suspect)"
                       f"{yaxis_note(cfg)}",
                  handles + gap_handles(ctx), ctx)
    return save_figure(fig, f"{pid}_rr_raw.png", out_dir, root)


def plot_rr_pages(d, cfg, ctx, pid, out_dir, root):
    """RR 分页：每页 RR_PAGE_MIN 分钟，覆盖全程。仅 RR_PAGES=True 时调用。"""
    rr = d["rr_flag"]
    page_len = cfg["RR_PAGE_MIN"] * 60.0
    n_pages = max(1, math.ceil((ctx["t1"] - ctx["t0"]) / page_len))
    written = []
    for i in range(n_pages):
        a = ctx["t0"] + i * page_len
        b = a + page_len
        page_rr = rr[(rr["t_unix"] >= a) & (rr["t_unix"] < b)]
        page_markers = [(t, lab) for t, lab in ctx["markers"] if a <= t < b]
        page_ctx = dict(ctx, t0=a, t1=b, markers=page_markers)
        fig, ax = plt.subplots(figsize=(16, 5))
        handles = draw_rr(ax, page_rr, cfg, ctx["rr_ylim"]) if len(page_rr) else []
        flagged = int((page_rr["out_of_range"] | page_rr["jump"]).sum()) if len(page_rr) else 0
        decorate(ax, page_ctx)
        place_marker_labels(ax, page_ctx, 16)
        finish_figure(fig, f"{pid} RR page {i + 1}/{n_pages}: {hhmm(a)}-{hhmm(b)}; "
                           f"{len(page_rr)} beats, {flagged} out of range or jump{yaxis_note(cfg)}",
                      handles + gap_handles(page_ctx), page_ctx)
        written.append(save_figure(fig, f"{pid}_rr_raw_page_{i + 1:02d}.png", out_dir, root))
    return written


# ---------- 质量指标 ----------

def hr_rr_mae(hr_part, rr_ok, seg_start):
    """按分钟：HR 均值 与 60000/RR 均值 之差的平均绝对值（只用在范围内的 RR）。"""
    if seg_start is None or pd.isna(seg_start) or len(hr_part) == 0 or len(rr_ok) == 0:
        return np.nan
    m_hr = pd.Series(hr_part["bpm"].to_numpy(), index=((hr_part["t_unix"] - seg_start) // 60).to_numpy())
    m_hr = m_hr.groupby(level=0).mean()
    m_rr = pd.Series(60000.0 / rr_ok["ms"].to_numpy(), index=((rr_ok["t_unix"] - seg_start) // 60).to_numpy())
    m_rr = m_rr.groupby(level=0).mean()
    joined = pd.concat([m_hr, m_rr], axis=1, keys=["hr", "rr"]).dropna()
    if joined.empty:
        return np.nan
    return float((joined["hr"] - joined["rr"]).abs().mean())


def quality_table(d, cfg):
    rows = []
    for _, s in d["segments"].iterrows():
        part = str(s["part"])
        start, end = s["start_unix"], s["end_unix"]
        has_span = not (pd.isna(start) or pd.isna(end))
        duration = float(end - start) if has_span else np.nan
        ecg_n = int((d["ecg"]["part"] == part).sum())
        expected = cfg["ECG_FS"] * duration if has_span else np.nan
        completeness = 100.0 * ecg_n / expected if has_span and expected > 0 else np.nan
        rr_p = d["rr_flag"][d["rr_flag"]["part"] == part]
        hr_p = d["hr"][d["hr"]["part"] == part]
        mae = hr_rr_mae(hr_p, rr_p[~rr_p["out_of_range"]], start if has_span else None)
        gaps_p = d["gaps"][d["gaps"]["part"] == part]
        gap_n = int(gaps_p["label"].str.startswith("gap_start").sum())
        rows.append({
            "part": part,
            "duration_s": round(duration, 3) if has_span else np.nan,
            "ecg_samples": ecg_n,
            "ecg_expected": round(expected, 1) if has_span else np.nan,
            "ecg_completeness_pct": round(completeness, 2) if has_span else np.nan,
            "rr_n": len(rr_p),
            "rr_out_of_range_n": int(rr_p["out_of_range"].sum()),
            "rr_jump_n": int(rr_p["jump"].sum()),
            "hr_vs_rr_mae_bpm": round(mae, 3) if not np.isnan(mae) else np.nan,
            "ble_gap_n": gap_n,
        })
    return pd.DataFrame(rows, columns=QUALITY_COLUMNS)


def merge_quality(quality, pid, path, root):
    """quality.csv 合并表：先去掉本次被试的旧行，再加入新行，其它被试的行保留。"""
    new = quality.copy()
    new.insert(0, "subject", pid)
    target = check_inside(path, root)
    if target.is_file():
        old = pd.read_csv(target, dtype={"subject": str, "part": str})
        old = old[old["subject"] != pid]
        combined = pd.concat([old, new], ignore_index=True)
    else:
        combined = new
    combined = combined.sort_values(["subject", "part"], kind="stable").reset_index(drop=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(target, index=False)
    return target


# ---------- 报告 ----------

def build_report(pid, dataset, d, cfg, ctx, quality, figures):
    lines = []
    add = lines.append
    add("physio 工具 03 绘图检查与质量报告（RR、HR、ECG）")
    add(f"数据集：{dataset}；被试：{pid}")
    add(f"生成时间：{datetime.now(TZ_BEIJING).isoformat(timespec='seconds')}（北京时间）")
    add(f"阈值：RR_MIN_MS={cfg['RR_MIN_MS']}，RR_MAX_MS={cfg['RR_MAX_MS']}，RR_JUMP={cfg['RR_JUMP']}，"
        f"ECG_FS={cfg['ECG_FS']}，RR_PAGE_MIN={cfg['RR_PAGE_MIN']}，RR_PAGES={cfg['RR_PAGES']}")
    add("RR 颜色：灰绿=正常；橙=超出范围；红=与前一个相比变化超过 RR_JUMP（疑似跳变，待工具 04 判断）")
    add("")

    add("[一] 逐段质量（对应 quality.csv 中本被试的行）")
    for _, q in quality.iterrows():
        add(f"  段 {q['part']}")
        if pd.isna(q["duration_s"]):
            add("    本段没有起止时间（缺 ecg.csv 或未能对齐），时长与完整度无法计算")
        else:
            add(f"    时长：{q['duration_s']:.3f} 秒")
            add(f"    ECG：实际样本 {int(q['ecg_samples'])}，期望 {q['ecg_expected']:.1f}"
                f"（{cfg['ECG_FS']} Hz × 时长），完整度 {q['ecg_completeness_pct']:.2f}%")
            if q["ecg_completeness_pct"] < 99.0:
                add("      注意：完整度低于 99%，ECG 可能有缺失")
        add(f"    RR：共 {int(q['rr_n'])} 个；超出 [{cfg['RR_MIN_MS']}, {cfg['RR_MAX_MS']}] ms 的 "
            f"{int(q['rr_out_of_range_n'])} 个；相邻变化超过 {cfg['RR_JUMP']:.0%} 的跳变 {int(q['rr_jump_n'])} 个")
        mae = q["hr_vs_rr_mae_bpm"]
        add("    HR 与 RR 一致性：" + ("无可比较的分钟" if pd.isna(mae)
                                   else f"逐分钟 |HR 均值 − 60000/RR 均值| 的平均为 {mae:.3f} bpm"
                                        "（只用范围内的 RR）"))
        add(f"    gap_start 条数（断流开始）：{int(q['ble_gap_n'])}")
    add("")

    add("[二] 全部标记（北京时间；markers.csv，不含 gap 记录）")
    if len(d["markers"]):
        add("  t_local                   label")
        for t, label in ctx["markers"]:
            add(f"  {t_local(t)}  {label}")
    else:
        add("  （无）")
    add("")

    add("[三] 超出范围的 RR（北京时间，单位 ms）")
    out = d["rr_flag"][d["rr_flag"]["out_of_range"]]
    if len(out):
        add("  t_local                   ms        段")
        for _, r in out.iterrows():
            add(f"  {t_local(r['t_unix'])}  {r['ms']:<9g} {r['part']}")
    else:
        add("  （无）")
    add("")

    add("[四] 本次输出（preview/signal/）")
    for f in figures:
        add(f"  {f.name}")
    add(f"  quality.csv（所有被试合表，本被试的行已更新）")
    add(f"  {pid}_report_raw.txt")
    return "\n".join(lines) + "\n"


# ---------- 单个被试 ----------

def check_subject(dataset, pid, subject_dir, processed, cfg, signal_dir):
    merged = subject_dir / MERGED_DIR
    if not (merged / "segments.csv").is_file():
        raise ValueError(f"sub-{pid} 没有 merged/segments.csv（先运行工具 02）")

    raw = load_merged(merged)
    d = dict(raw)
    d["rr_flag"] = flag_rr(raw["rr"], cfg)

    # 时间范围与底色、标记
    spans = [raw[k]["t_unix"] for k in ("ecg", "hr", "rr", "acc", "markers") if len(raw[k])]
    t0 = float(min(s.min() for s in spans))
    t1 = float(max(s.max() for s in spans))
    markers = [(float(t), str(lab)) for t, lab in zip(raw["markers"]["t_unix"], raw["markers"]["label"])]
    ctx = {
        "t0": t0, "t1": t1, "markers": markers,
        "seg_spans": segment_gap_spans(raw["segments"]),
        "gap_spans": gap_spans(raw["gaps"], t1),
        "rr_ylim": rr_limits(d["rr_flag"], cfg["RR_YAXIS_PERCENTILE"]),
    }

    quality = quality_table(d, cfg)
    figures = [plot_overview(d, cfg, ctx, pid, signal_dir, processed),
               plot_rr_full(d, cfg, ctx, pid, signal_dir, processed)]
    if cfg["RR_PAGES"]:
        figures += plot_rr_pages(d, cfg, ctx, pid, signal_dir, processed)
    quality_path = merge_quality(quality, pid, signal_dir / "quality.csv", processed)
    report = build_report(pid, dataset, d, cfg, ctx, quality, figures)
    target = check_inside(signal_dir / f"{pid}_report_raw.txt", processed)
    target.write_text(report, encoding="utf-8")
    return {"subject": pid, "figures": figures, "quality": quality,
            "quality_path": quality_path, "report": target}


# ---------- 入口 ----------

def run(dataset, subjects, cfg):
    processed = layer_dir(dataset, "processed", "physio")
    signal_dir = processed.joinpath(*SIGNAL_SUBDIR)
    check_inside(signal_dir, processed)

    pool = list_subjects(processed)
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"processed/physio 中没有这些被试：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"processed/physio 中没有任何 sub-P### 文件夹：{processed}（先运行工具 01、02）")

    print(f"数据集 {dataset}：共 {len(chosen)} 位被试；输出目录：{signal_dir}")
    summaries = []
    for pid in chosen:
        print(f"[开始] {pid}")
        summary = check_subject(dataset, pid, processed / f"sub-{pid}", processed, cfg, signal_dir)
        names = ", ".join(f.name for f in summary["figures"])
        print(f"[完成] {pid}：{names}；{pid}_report_raw.txt；quality.csv 已更新")
        summaries.append(summary)
    return summaries
