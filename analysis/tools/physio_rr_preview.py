"""physio 工具 06 的全部处理与绘图逻辑：清理后 RR 预览图（只画图，不改任何数据）。

输入（只读）：data/<数据集>/processed/physio/sub-P###/
    clean/rr.csv、clean/holes.csv、merged/rr.csv、events/markers.csv（没有则退回 merged/markers.csv）、merged/segments.csv
    没有 clean/rr.csv 的被试跳过，并提示先运行 05。
输出：data/<数据集>/processed/physio/preview/signal/P###_rr_clean.png（每人一张，覆盖旧图）
图的版式（尺寸、北京时间横轴、字体、底色）与 04 的 P###_rr_raw.png 一致，复用 physio_check 的常量与函数。
写入前检查路径在 processed/physio/ 之内。
"""
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

from global_settings import PHYSIO_PHASES  # noqa: E402
from paths import layer_dir  # noqa: E402
from physio_check import (load_event_markers, COLOR_BLE, COLOR_NORMAL, COLOR_SEG, SIGNAL_SUBDIR, hhmm,  # noqa: E402
                          save_figure, segment_gap_spans)
from physio_merge import TZ_BEIJING  # noqa: E402
from physio_xdf import check_inside, list_subjects, normalize_subject  # noqa: E402

# handling → (图例英文, 颜色, 点大小, zorder)
HANDLING_STYLE = {
    0: ("0 kept", COLOR_NORMAL, 3, 3),
    1: ("1 missed beat split", "#1f77b4", 6, 4),
    2: ("2 extra beat merged", "#9467bd", 6, 4),
    3: ("3 ectopic / long-short corrected", "#ff8c00", 6, 4),
    4: ("4 needs review", "#d62728", 12, 6),
}
PHASE_COLORS = {
    "training": "#cfe3f5",
    "baseline": "#d9f0d3",
    "induction": "#fde3c4",
    "intervention": "#e6d9f2",
    "post_intervention_rest": "#fbd9e4",
}
PHASE_NAMES = {
    "training": "Training", "baseline": "Baseline", "induction": "Induction",
    "intervention": "Intervention", "post_intervention_rest": "Post-intervention rest",
}


def clock(t):
    return datetime.fromtimestamp(float(t), TZ_BEIJING).strftime("%H:%M:%S")


def phase_intervals(markers):
    """每个阶段：成对的 start/end → (start, end)；缺一个不推算，记入 missing 与 lone。
    返回 (完整区间 {phase: (a, b)}, 孤立标记 [(t, label)], 缺失标签列表)。"""
    full, lone, missing = {}, [], []
    m = markers.sort_values("t_unix")
    for phase in PHASE_COLORS:
        s = m.loc[m["label"] == f"{phase}_start", "t_unix"].to_numpy(float)
        e = m.loc[m["label"] == f"{phase}_end", "t_unix"].to_numpy(float)
        if len(s) and len(e) and (e >= s[0]).any():
            full[phase] = (float(s[0]), float(e[e >= s[0]][0]))
            continue
        if len(s):
            lone.append((float(s[0]), f"{phase}_start"))
        if len(e):
            lone.append((float(e[0]), f"{phase}_end"))
        if not len(s):
            missing.append(f"{phase}_start")
        if not len(e) or (len(s) and not (e >= s[0]).any()):
            missing.append(f"{phase}_end")
    return full, lone, missing


def y_range(clean, mode, t_train=None):
    """clip：只用 training_start 之后、handling≠4 的拍（没有 training_start 则用全部 handling≠4 的拍）。"""
    ms = clean["ms"].to_numpy(float)
    t = clean["t_unix"].to_numpy(float)
    keep = clean["handling"].to_numpy() != 4
    if mode == "clip":
        base = ms[keep & (t >= t_train)] if t_train is not None else ms[keep]
    else:
        base = ms
    if len(base) == 0:
        base = ms[keep] if keep.any() else ms
    lo, hi = float(base.min()), float(base.max())
    pad = max(0.05 * (hi - lo), 1.0)
    return lo - pad, hi + pad


def plot_subject(pid, clean, holes, raw, markers, segments, mode, out_dir, root, marker_note=""):
    assert set(PHASE_COLORS) == set(PHYSIO_PHASES), "阶段表与 global_settings.PHYSIO_PHASES 不一致"
    t = clean["t_unix"].to_numpy(float)
    ms = clean["ms"].to_numpy(float)
    h = clean["handling"].to_numpy(int)
    fig, ax = plt.subplots(figsize=(24, 6))

    # 阶段背景带
    mk = markers[markers["label"].isin([f"{p}_{b}" for p in PHASE_COLORS for b in ("start", "end")])]
    full, lone, missing = phase_intervals(mk)
    ts = mk.loc[mk["label"] == "training_start", "t_unix"]
    t_train = float(ts.min()) if len(ts) else None
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    for phase, (a, b) in full.items():
        ax.axvspan(a, b, color=PHASE_COLORS[phase], alpha=0.55, zorder=0.2, lw=0)
        ax.text((a + b) / 2, 0.985, PHASE_NAMES[phase], transform=trans, ha="center", va="top",
                fontsize=9, color="0.25", zorder=7)
    for tt, lab in lone:
        ax.axvline(tt, color="k", ls="--", lw=0.8, alpha=0.8, zorder=1)
        ax.text(tt, 0.985, " " + lab, transform=trans, ha="left", va="top", fontsize=7, color="0.25", zorder=7)

    # 空档与丢包底色
    segs = segment_gap_spans(segments)
    for a, b in segs:
        ax.axvspan(a, b, color=COLOR_SEG, zorder=0.5)
    for _, r in holes.iterrows():
        ax.axvspan(r["t_start"], r["t_end"], color=COLOR_BLE, alpha=0.6, zorder=0.6)

    handles = []
    if len(raw):
        handles.append(ax.scatter(raw["t_unix"], raw["ms"], s=2, color="0.8", label="raw RR", zorder=1.5))

    ymin, ymax = y_range(clean, mode, t_train) if len(clean) else (0, 1)
    above = ms > ymax
    below = ms < ymin
    beyond = int((above | below).sum()) if mode == "clip" else 0
    inside = ~(above | below)
    span = ymax - ymin
    yc = np.clip(ms, ymin + 0.01 * span, ymax - 0.01 * span)
    for k, (label, color, size, z) in HANDLING_STYLE.items():
        sel = h == k
        if not sel.any():
            continue
        handles.append(ax.scatter(t[sel & inside], ms[sel & inside], s=size, color=color, label=label, zorder=z))
        up, dn = sel & above, sel & below
        if up.any():
            ax.scatter(t[up], yc[up], s=size * 4, color=color, marker="^", zorder=z)
        if dn.any():
            ax.scatter(t[dn], yc[dn], s=size * 4, color=color, marker="v", zorder=z)

    # 阶段内待人工标注
    review = np.flatnonzero(h == 4)
    in_phase = []
    for n, i in enumerate(review):
        for phase, (a, b) in full.items():
            if a <= t[i] <= b:
                in_phase.append((float(t[i]), phase))
                ax.annotate(clock(t[i]), (t[i], yc[i]), xytext=(4, (-18 - 10 * (n % 3)) if above[i] else (8 + 10 * (n % 3))),
                            textcoords="offset points", fontsize=7, color="#d62728", zorder=8)
                break

    if segs:
        handles.append(Patch(facecolor=COLOR_SEG, label="recording gap"))
    if len(holes):
        handles.append(Patch(facecolor=COLOR_BLE, alpha=0.6, label="data-loss gap"))

    ax.set_xlim(*(min(t.min(), raw["t_unix"].min() if len(raw) else t.min()),
                  max(t.max(), raw["t_unix"].max() if len(raw) else t.max())))
    ax.set_ylim(ymin, ymax)
    ax.xaxis.set_major_formatter(FuncFormatter(hhmm))
    ax.grid(alpha=0.2)
    ax.set_ylabel("RR (ms)")

    title = (f"{pid} RR after cleaning: {len(clean)} beats | needs review {len(review)} "
             f"(in phases {len(in_phase)}) | holes {len(holes)}, {holes['dur_s'].sum():.1f} s")
    if beyond:
        title += f" | {beyond} points beyond axis"
    if missing:
        title += f" | missing markers: {', '.join(missing)}"
    if marker_note:
        title += f" | {marker_note}"
    fig.suptitle(title, fontsize=11, y=0.985)
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.945),
               ncol=len(handles), frameon=False, fontsize=9)
    fig.subplots_adjust(top=0.87, bottom=0.10, left=0.07, right=0.98)
    ax.set_xlabel("Time (HH:MM)")
    path = save_figure(fig, f"{pid}_rr_clean.png", out_dir, root)
    return {"path": path, "review_total": len(review), "in_phase": in_phase, "beyond": beyond, "ylim": (ymin, ymax),
            "missing": missing, "t_review": [(float(t[i]), int(i)) for i in review]}


def run(dataset, subjects, cfg):
    mode = cfg.get("YAXIS_MODE", "clip")
    if mode not in ("clip", "full"):
        raise ValueError(f'YAXIS_MODE 应为 "clip" 或 "full"，当前为 {mode!r}')
    processed = layer_dir(dataset, "processed", "physio")
    out_dir = processed.joinpath(*SIGNAL_SUBDIR)
    check_inside(out_dir, processed)
    pool = list_subjects(processed)
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"processed/physio 中没有这些被试：{missing}；现有：{pool}")
    print(f"数据集 {dataset}：共 {len(chosen)} 位被试；输出目录：{out_dir}")
    results = {}
    for pid in chosen:
        sub = processed / f"sub-{pid}"
        if not (sub / "clean" / "rr.csv").is_file():
            print(f"[跳过] {pid}：没有 clean/rr.csv，请先运行 05")
            continue
        clean = pd.read_csv(sub / "clean" / "rr.csv", dtype={"part": str})
        holes_path = sub / "clean" / "holes.csv"
        holes = pd.read_csv(holes_path) if holes_path.is_file() else pd.DataFrame(columns=["t_start", "t_end", "dur_s"])
        raw = pd.read_csv(sub / "merged" / "rr.csv", dtype={"part": str})
        markers, marker_path, marker_note = load_event_markers(sub)
        print(f"       事件文件：{marker_path}" + (f"（{marker_note}）" if marker_note else ""))
        res_note = "events not corrected by 03" if marker_note else ""
        segments = pd.read_csv(sub / "merged" / "segments.csv", dtype={"part": str})
        res = plot_subject(pid, clean, holes, raw, markers, segments, mode, out_dir, processed, res_note)
        res["clean"] = clean
        res["marker_path"] = marker_path
        results[pid] = res
        print(f"[完成] {pid}：{res['path'].name}")
    print("-" * 60)
    root = out_dir.resolve()
    print(f"每人一份：{root}/P###_rr_clean.png")
    print("看什么：只看阶段色带里标了时刻的红点（需要人工判断的心跳）；没有红点标注就不用管。")
    return results
