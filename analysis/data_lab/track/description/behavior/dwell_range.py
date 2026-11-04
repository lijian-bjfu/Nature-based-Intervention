"""data_lab/track/description/behavior：驻留的概念定义探索——时间窗内的活动范围，其分布与可能的切分阈值。"""

# ════════════════════════════════════════════════════════════════════
# ▼▼▼ 研究者只需要改这一段 PARAMETERS，改完保存，点右上角 Run ▼▼▼
# ════════════════════════════════════════════════════════════════════
# selection：选哪份数据（一次只分析一份记录；用了哪份，在 log.md 里记下）。
#   dataset：test=开发测试，pilot=预实验，formal=正式实验。
#   subject：被试编号，如 "P000"。
#   run：同一被试有多份记录时才需要填，如 "004"；只有一份时填 None。
# dwell：
#   window_seconds：候选时间窗长度（秒），每个长度各算一遍，用来看结论是否随窗长漂移。
#   reference_window_seconds：画时间曲线、列驻留段落时用哪个窗长，必须是上面列表中的一个。
#   floor_m：活动半径的下限（米）。位置记录精度为 0.01 米，半径低于它的都按"完全没动"处理，
#            取对数时也以它为下限。
#   candidate_radius_m：候选"原地"半径（米）。None 表示只看分布、不切分；
#            填了数值，就按它列出驻留段落（table_dwell_segments.csv），供对照观察者系统回放。
#   min_dwell_seconds：段落至少持续多久才列出（只在填了 candidate_radius_m 时起作用）。
#   still_step_m：相邻两个采样之间位置变化不超过多少米，算"这一步没动"。0 表示位置完全不变。
#            用来把全程切成"不动片段"和"走动片段"（table_episodes.csv），不依赖时间窗。
PARAMETERS = {
    "selection": {
        "dataset": "test",
        "subject": "P000",
        "run": "004",
    },
    "dwell": {
        "window_seconds": [2.0, 3.0, 5.0, 8.0, 12.0],
        "reference_window_seconds": 5.0,
        "floor_m": 0.01,
        "candidate_radius_m": None,
        "min_dwell_seconds": 2.0,
        "still_step_m": 0.0,
    },
    "figure": {
        "dpi": 160,             # 正整数
        "formats": ["png"],     # png / svg / pdf，可多选
        "font": "Arial Unicode MS",
        "font_size": 10,
    },
}

# ════════════════════════════════════════════════════════════════════
# ▲▲▲ 以上是参数。以下是程序本身，日常使用不需要修改 ▲▲▲
# ════════════════════════════════════════════════════════════════════

from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT/"analysis"), str(PROJECT/"analysis/tools")]

import importlib.metadata
import re
import shutil

import numpy as np
import pandas as pd

import global_settings as settings
from safe_io import retire_dir  # 旧目录移到 _to_delete，不直接删除
from data_access import find, load
from artifacts import sha256, write_json, markdown_table, settings_snapshot
from options import figure_options, positive
from paths import ROOT, ANALYSIS, DATASETS
from plotting import pyplot, save_figure
from run_records import now, run_id, git_state, record_sources, script_history

HERE = Path(__file__).resolve().parent
FIGURES = {"distribution": "fig1_radius_distribution", "time": "fig2_radius_time",
           "speed": "fig3_radius_vs_speed", "episodes": "fig4_episode_durations"}


# ── 参数检查 ────────────────────────────────────────────────────────
def check(parameters):
    sel = parameters["selection"]
    if sel["dataset"] not in DATASETS:
        raise ValueError(f"selection.dataset 应为 {tuple(DATASETS)} 之一")
    if not re.fullmatch(r"P\d+", str(sel["subject"])):
        raise ValueError("selection.subject 应是一名被试的编号，如 P000")
    run = sel.get("run")
    run = None if run in (None, "") else str(run)
    d = parameters["dwell"]
    widths = [positive(w, "dwell.window_seconds") for w in d["window_seconds"]]
    if not widths or len(set(widths)) != len(widths):
        raise ValueError("dwell.window_seconds 应是不重复的非空数值列表")
    reference = positive(d["reference_window_seconds"], "dwell.reference_window_seconds")
    if reference not in widths:
        raise ValueError("dwell.reference_window_seconds 必须是 window_seconds 中的一个")
    candidate = d["candidate_radius_m"]
    return {
        "dataset": sel["dataset"], "subject": str(sel["subject"]), "run": run,
        "widths": widths, "reference": reference,
        "floor": positive(d["floor_m"], "dwell.floor_m"),
        "candidate": None if candidate is None else positive(candidate, "dwell.candidate_radius_m"),
        "min_dwell": positive(d["min_dwell_seconds"], "dwell.min_dwell_seconds"),
        "still_step": float(d["still_step_m"]),
        "figure": figure_options(parameters["figure"]),
    }


# ── 读表 ────────────────────────────────────────────────────────────
def column(tables, table, field, dtype=float):
    return tables[table][settings.column(table, field)].to_numpy(dtype=dtype, na_value=np.nan)


def read_pose(tables):
    t, x, z = (column(tables, "spacetime", f) for f in ("t_session", "cam_x", "cam_z"))
    if len(t) < 2 or not np.isfinite(np.r_[t, x, z]).all():
        raise ValueError("spacetime 缺少可用的时间或位置")
    if (np.diff(t) <= 0).any():
        raise ValueError("spacetime.t_session 不是严格递增，不能计算时间窗")
    return t, x, z


# ── 核心：时间窗内的活动范围 ─────────────────────────────────────────
def window_measures(t, x, z, width):
    """对每个采样时刻，取以它为中心、长 width 秒的窗口，返回两个量：
        radius  窗内各点到窗内平均位置的最大水平距离（米）——"这段时间活动范围多大"
        speed   窗内水平路程 / 窗内时长（米/秒）——"这段时间平均走多快"，仅作对照
    窗口超出记录开头或结尾的时刻不计算（NaN），不拿残缺的窗口凑数。"""
    cumulative = np.r_[0.0, np.cumsum(np.hypot(np.diff(x), np.diff(z)))]
    half = width / 2
    first = np.searchsorted(t, t - half, side="left")
    last = np.searchsorted(t, t + half, side="right")        # 不含
    complete = (t - half >= t[0]) & (t + half <= t[-1])
    radius = np.full(len(t), np.nan)
    speed = np.full(len(t), np.nan)
    for i in np.flatnonzero(complete):
        a, b = first[i], last[i]
        if b - a < 2:
            continue
        px, pz = x[a:b], z[a:b]
        radius[i] = np.hypot(px - px.mean(), pz - pz.mean()).max()
        span = t[b - 1] - t[a]
        speed[i] = (cumulative[b - 1] - cumulative[a]) / span if span > 0 else np.nan
    return radius, speed


def glitch_overlap(t, glitches, width):
    """窗口与技术卡顿（含前后各一个卡顿时长）有重叠的时刻。只标记，不排除。"""
    mask = np.zeros(len(t), dtype=bool)
    for when, duration in glitches:
        mask |= (t + width / 2 >= when - duration) & (t - width / 2 <= when + duration)
    return mask


# ── 分布：是否存在可以切分的阈值 ─────────────────────────────────────
def otsu(v, bins=64):
    """在对数半径上做二分类，使两类之间的方差占比最大。返回 (分界, 可分性 η)；
    η 是两类间方差占总方差的比例，越接近 1 越像清晰分开的两堆。"""
    hist, edges = np.histogram(v, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    p = hist / hist.sum()
    w0 = np.cumsum(p)
    m = np.cumsum(p * centers)
    mean_all = m[-1]
    total = float((p * (centers - mean_all) ** 2).sum())
    if total <= 0:
        return None, None
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (mean_all * w0 - m) ** 2 / (w0 * (1 - w0))
    k = int(np.nanargmax(between[:-1]))
    return float(10 ** edges[k + 1]), float(between[k] / total)


def valley(v, bins=40, min_gap=4):
    """平滑后的直方图里，两个最高峰之间的最低谷。返回 (谷处半径, 谷深比, 两个峰处半径)；
    谷深比 = 谷高 / 较低那座峰的高，越小说明谷越深。找不到两座分开的峰则返回 None。"""
    hist, edges = np.histogram(v, bins=bins)
    smooth = np.convolve(hist, np.ones(3) / 3, mode="same")
    padded = np.r_[0.0, smooth, 0.0]
    peaks = [i for i in range(bins) if padded[i + 1] >= padded[i] and padded[i + 1] > padded[i + 2]]
    peaks.sort(key=lambda i: -smooth[i])
    if not peaks:
        return None
    first = peaks[0]
    second = next((i for i in peaks[1:] if abs(i - first) >= min_gap), None)
    if second is None:
        return None
    lo, hi = sorted((first, second))
    bottom = lo + int(np.argmin(smooth[lo:hi + 1]))
    centers = (edges[:-1] + edges[1:]) / 2
    low_peak = min(smooth[first], smooth[second])
    return (float(10 ** centers[bottom]), float(smooth[bottom] / low_peak) if low_peak else None,
            (float(10 ** centers[lo]), float(10 ** centers[hi])))


def bimodality(v):
    """双峰系数 BC=(偏度²+1)/(超额峰度+3(n-1)²/((n-2)(n-3)))；常用经验界 0.555，超过提示可能双峰。
    相邻采样高度相关，n 实际偏大，只作旁证。"""
    n = len(v)
    sd = v.std()
    if n < 4 or sd == 0:
        return None
    z = (v - v.mean()) / sd
    return float((np.mean(z ** 3) ** 2 + 1) / (np.mean(z ** 4) - 3 + 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))))


def distribution_row(width, radius, floor, session_seconds):
    valid = radius[np.isfinite(radius)]
    v = np.log10(np.maximum(valid, floor))
    cut, eta = otsu(v)
    low = valley(v)
    q = {f"q{int(p * 100):02d}": float(np.quantile(valid, p)) for p in (.05, .25, .5, .75, .95)}
    return {"window_s": width, "valid_n": int(len(valid)), "valid_share": float(len(valid) / len(radius)),
            "at_floor_share": float((valid <= floor).mean()), **q, "max": float(valid.max()),
            "otsu_radius_m": cut, "otsu_separability": eta,
            "valley_radius_m": None if low is None else low[0],
            "valley_depth": None if low is None else low[1],
            "peak_low_m": None if low is None else low[2][0],
            "peak_high_m": None if low is None else low[2][1],
            "bimodality_coef": bimodality(v)}


# ── 不依赖时间窗：相邻采样之间动没动 ─────────────────────────────────
def step_episodes(t, x, z, still_step, tap_t, touched_t):
    """相邻两个采样之间位置变化 ≤ still_step 算"没动"。连续的"没动"合并为一个不动片段，
    连续的"动了"合并为一个走动片段。返回 (片段表, 每一步的速度, 每一步是否没动)。"""
    step = np.hypot(np.diff(x), np.diff(z))
    speed = step / np.diff(t)
    still = step <= still_step
    rows, s = [], 0
    for i in range(1, len(still) + 1):
        if i == len(still) or still[i] != still[s]:
            a, b = float(t[s]), float(t[i])
            rows.append({"kind": "still" if still[s] else "moving", "start_s": a, "end_s": b,
                         "duration_s": b - a, "path_m": float(step[s:i].sum()),
                         "tap_n": int(((tap_t >= a) & (tap_t < b)).sum()),
                         "touched_n": int(((touched_t >= a) & (touched_t < b)).sum())})
            s = i
    return pd.DataFrame(rows), speed, still


def episode_summary(episodes, speed, still, total_seconds):
    moving_speed = speed[~still]
    out = {"still_step_share": float(still.mean()),
           "moving_speed_q": {f"q{int(p * 100):02d}": float(np.quantile(moving_speed, p)) for p in (.05, .5, .95)}
           if len(moving_speed) else None,
           "slow_step_share": float(((~still) & (speed < 0.3)).mean())}
    for kind in ("still", "moving"):
        d = episodes.loc[episodes.kind == kind, "duration_s"].to_numpy()
        out[kind] = {"n": int(len(d)), "total_s": float(d.sum()), "share_of_time": float(d.sum() / total_seconds),
                     "q10": float(np.quantile(d, .1)) if len(d) else None, "q50": float(np.median(d)) if len(d) else None,
                     "q90": float(np.quantile(d, .9)) if len(d) else None}
    d = episodes.loc[episodes.kind == "still", "duration_s"].to_numpy()
    out["still_bins"] = {label: int(((d >= lo) & (d < hi)).sum())
                         for label, lo, hi in (("<1 s", 0, 1), ("1–2 s", 1, 2), ("2–5 s", 2, 5),
                                               ("5–10 s", 5, 10), ("≥10 s", 10, np.inf))}
    return out


# ── 候选驻留段落（只在给了 candidate_radius_m 时） ───────────────────
def dwell_segments(t, x, z, radius, threshold, min_dwell, tap_t, touched_t):
    inside = np.isfinite(radius) & (radius <= threshold)
    rows, start = [], None
    for i in range(len(t)):
        if inside[i] and start is None:
            start = i
        if start is not None and (not inside[i] or i == len(t) - 1):
            end = i if inside[i] else i - 1
            if t[end] - t[start] >= min_dwell:
                path = float(np.hypot(np.diff(x[start:end + 1]), np.diff(z[start:end + 1])).sum())
                rows.append({"start_s": float(t[start]), "end_s": float(t[end]),
                             "duration_s": float(t[end] - t[start]),
                             "center_x": float(x[start:end + 1].mean()), "center_z": float(z[start:end + 1].mean()),
                             "path_m": path,
                             "tap_n": int(((tap_t >= t[start]) & (tap_t <= t[end])).sum()),
                             "touched_n": int(((touched_t >= t[start]) & (touched_t <= t[end])).sum())})
            start = None
    return pd.DataFrame(rows, columns=["start_s", "end_s", "duration_s", "center_x", "center_z",
                                       "path_m", "tap_n", "touched_n"])


# ── 图 ──────────────────────────────────────────────────────────────
def radius_ticks(ax, floor):
    marks = [m for m in (0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30) if m >= floor / 1.01]
    ax.set_xticks([np.log10(m) for m in marks], [f"{m:g}" for m in marks])


def plots(cfg, series, rows, t, glitch_times, tap_t, touched_t, segments, episodes, summary, dest):
    plt = pyplot(cfg["figure"])
    floor, ref = cfg["floor"], cfg["reference"]
    images = []

    widths = cfg["widths"]
    fig, axes = plt.subplots(len(widths), 1, figsize=(9, 2.1 * len(widths) + .8), sharex=True, layout="constrained")
    axes = np.atleast_1d(axes)
    for ax, width, row in zip(axes, widths, rows):
        radius = series[width]["radius"]
        v = np.log10(np.maximum(radius[np.isfinite(radius)], floor))
        ax.hist(v, bins=60, color="#7FA39A")
        if row["otsu_radius_m"]:
            ax.axvline(np.log10(row["otsu_radius_m"]), color="#C44545", lw=1.5, label=f"Otsu {row['otsu_radius_m']:.2f} m")
        if row["valley_radius_m"]:
            ax.axvline(np.log10(row["valley_radius_m"]), color="#555555", lw=1.2, ls="--", label=f"valley {row['valley_radius_m']:.2f} m")
        if cfg["candidate"]:
            ax.axvline(np.log10(cfg["candidate"]), color="#4169A2", lw=1.5, ls=":", label=f"candidate {cfg['candidate']:g} m")
        ax.set_ylabel("samples")
        ax.set_title(f"window {width:g} s", loc="left", fontsize=10)
        ax.legend(fontsize=8, loc="upper right")
    axes[-1].set_xlabel("activity radius in window (m, log scale)")
    radius_ticks(axes[-1], floor)
    fig.suptitle(summary["record"], fontsize=11)
    images += save_figure(fig, dest, FIGURES["distribution"], cfg["figure"]); plt.close(fig)

    radius = series[ref]["radius"]
    fig, ax = plt.subplots(figsize=(13, 4.5), layout="constrained")
    ax.plot(t / 60, np.maximum(radius, floor), lw=.9, color="#3F6F63")
    ax.set_yscale("log")
    ax.set(xlabel="t_session (min)", ylabel="activity radius (m)", xlim=(0, t[-1] / 60),
           title=f"Activity radius over time (window {ref:g} s)")
    low_edge = ax.get_ylim()[0]
    ax.plot(tap_t / 60, np.full(len(tap_t), low_edge), "|", color="#4169A2", ms=8, label="tap")
    ax.plot(touched_t / 60, np.full(len(touched_t), low_edge), "*", color="#22866B", ms=9, label="is_touched=TRUE")
    for k, when in enumerate(glitch_times):
        ax.axvline(when / 60, color="#C44545", lw=.8, alpha=.6, label="tech_glitch" if k == 0 else None)
    ref_row = rows[widths.index(ref)]
    if ref_row["otsu_radius_m"]:
        ax.axhline(ref_row["otsu_radius_m"], color="#C44545", ls="-", lw=1, label=f"Otsu {ref_row['otsu_radius_m']:.2f} m")
    if cfg["candidate"]:
        ax.axhline(cfg["candidate"], color="#4169A2", ls=":", lw=1.4, label=f"candidate {cfg['candidate']:g} m")
        for _, seg in segments.iterrows():
            ax.axvspan(seg.start_s / 60, seg.end_s / 60, color="#4169A2", alpha=.12)
    ax.legend(fontsize=8, ncol=5, loc="upper right")
    ax.grid(alpha=.15)
    fig.suptitle(summary["record"], fontsize=11)
    images += save_figure(fig, dest, FIGURES["time"], cfg["figure"]); plt.close(fig)

    speed = series[ref]["speed"]
    ok = np.isfinite(radius) & np.isfinite(speed)
    fig, ax = plt.subplots(figsize=(6.5, 5.5), layout="constrained")
    ax.scatter(np.maximum(radius[ok], floor), np.maximum(speed[ok], 1e-3), s=6, alpha=.35, color="#3F6F63")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set(xlabel="activity radius in window (m)", ylabel="mean speed in window (m/s, floor 0.001)",
           title=f"Radius vs. mean speed (window {ref:g} s)")
    ax.grid(alpha=.15)
    fig.suptitle(summary["record"], fontsize=11)
    images += save_figure(fig, dest, FIGURES["speed"], cfg["figure"]); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", sharey=True)
    bins = np.logspace(-1, np.log10(max(episodes.duration_s.max(), 1.0) * 1.05), 30)
    for ax, kind, color in zip(axes, ("still", "moving"), ("#4169A2", "#D69325")):
        d = episodes.loc[episodes.kind == kind, "duration_s"]
        ax.hist(d, bins=bins, color=color)
        ax.set_xscale("log")
        ax.set(xlabel="episode duration (s, log scale)", title=f"{kind} episodes (n={len(d)})")
    axes[0].set_ylabel("episodes")
    fig.suptitle(summary["record"], fontsize=11)
    images += save_figure(fig, dest, FIGURES["episodes"], cfg["figure"]); plt.close(fig)
    return images


# ── 报告 ────────────────────────────────────────────────────────────
def shape_sentence(row):
    eta, depth, bc = row["otsu_separability"], row["valley_depth"], row["bimodality_coef"]
    if eta is None:
        return "半径几乎没有变化，无法判断形状。"
    clean = eta >= .75 and depth is not None and depth <= .5
    return (f"{'较明显地分成了两堆' if clean else '没有看到清晰的两堆'}"
            f"（Otsu 可分性 η={eta:.2f}；"
            f"{'两峰之间谷深比 ' + format(depth, '.2f') if depth is not None else '找不到两座分开的峰'}；"
            f"双峰系数 {'—' if bc is None else format(bc, '.2f')}）。")


def build_report(cfg, rows, summary, segments, episodes_info, speed_corr, glitch_share, images, dest):
    ref_row = rows[cfg["widths"].index(cfg["reference"])]
    frame = pd.DataFrame(rows)
    cuts = frame.otsu_radius_m.dropna()
    stable = (f"各窗长的 Otsu 分界在 {cuts.min():.2f}–{cuts.max():.2f} m 之间，最大最小相差 {cuts.max() / cuts.min():.1f} 倍；"
              f"{'较稳定（≤1.5 倍）' if cuts.max() / cuts.min() <= 1.5 else '随窗长漂移明显（>1.5 倍），说明这个分界本身不太可靠'}。"
              if len(cuts) >= 2 else "有效分界不足两个，无法比较窗长稳定性。")
    lines = [f"# 驻留：时间窗内活动范围的分布", "",
             f"数据：{cfg['dataset']}／{summary['record']}（时长 {summary['duration_s']:.1f} s）　运行于 {summary['run_at']}", "",
             "## 一、看到了什么", "",
             f"- 位姿记录 {summary['pose_rows']} 行，采样间隔中位 {summary['interval_median_s']:.3f} s、最长 {summary['interval_max_s']:.3f} s"
             f"（规范为 {settings.TRACK_RECORDING['spacetime_interval_seconds']} s）。",
             f"- 以 {cfg['reference']:g} s 窗为参照：有效时刻 {ref_row['valid_n']} 个（占 {ref_row['valid_share']:.0%}，开头结尾不足半窗的不算）；"
             f"其中 {ref_row['at_floor_share']:.0%} 完全没动（半径 ≤ {cfg['floor']:g} m）。半径中位数 {ref_row['q50']:.2f} m，"
             f"25%–75% 分位 {ref_row['q25']:.2f}–{ref_row['q75']:.2f} m，95% 分位 {ref_row['q95']:.2f} m。",
             f"- 分布形状：{shape_sentence(ref_row)}"
             + (f"Otsu 候选分界 {ref_row['otsu_radius_m']:.2f} m。" if ref_row["otsu_radius_m"] else ""),
             f"- 两座峰的位置：低的一座在地板（完全没动）；高的一座随窗长移动，"
             + "、".join(f"{r['window_s']:g} s 窗 {r['peak_high_m']:.2f} m" for r in rows if r["peak_high_m"])
             + "，大致随窗长成比例——走动时窗内半径主要由走动速度和窗长决定，并不是一个独立于速度的量。",
             f"- 窗长稳定性：{stable}",
             f"- 与速度的关系：半径与窗内平均速度的 Spearman 相关 ρ={speed_corr:.2f}。"
             if speed_corr is not None else "- 与速度的关系：样本不足，未计算。",
             f"- 技术卡顿 {summary['glitch_n']} 次；{glitch_share:.1%} 的有效时刻其窗口与卡顿重叠（只标记，未排除）。",
             f"- 不依赖时间窗，只看相邻采样（{'位置完全不变' if cfg['still_step'] == 0 else '步长 ≤ ' + format(cfg['still_step'], 'g') + ' m'}算没动）：{episodes_info['still_step_share']:.0%} 的步没动；"
             + (f"动了的步，速度中位 {episodes_info['moving_speed_q']['q50']:.2f} m/s（5%–95% 为 "
                f"{episodes_info['moving_speed_q']['q05']:.2f}–{episodes_info['moving_speed_q']['q95']:.2f} m/s），"
                if episodes_info["moving_speed_q"] else "")
             + f"速度低于 0.3 m/s 的慢步占 {episodes_info['slow_step_share']:.1%}。",
             f"- 不动片段 {episodes_info['still']['n']} 段，合计 {episodes_info['still']['total_s']:.0f} s"
             f"（占全程 {episodes_info['still']['share_of_time']:.0%}），时长中位 {episodes_info['still']['q50']:.1f} s"
             f"（10%–90% 分位 {episodes_info['still']['q10']:.1f}–{episodes_info['still']['q90']:.1f} s）；"
             f"按时长分：" + "、".join(f"{k} {v} 段" for k, v in episodes_info["still_bins"].items()) + "。"
             f"走动片段 {episodes_info['moving']['n']} 段，合计 {episodes_info['moving']['total_s']:.0f} s，时长中位 {episodes_info['moving']['q50']:.1f} s。", "",
             "判据说明：\"清晰的两堆\"取 η≥0.75 且谷深比≤0.5，是本脚本的粗略工作规则，不是统计检验；"
             "最终是否存在可切分的阈值，要结合观察者回放判断。", ""]
    if cfg["candidate"]:
        lines += [f"## 二、候选驻留段落（半径 ≤ {cfg['candidate']:g} m，窗 {cfg['reference']:g} s，持续 ≥ {cfg['min_dwell']:g} s）", "",
                  f"共 {len(segments)} 段，合计 {segments.duration_s.sum():.1f} s（占全程 {segments.duration_s.sum() / summary['duration_s']:.0%}）。"
                  "起止时刻是窗口中心的会话时间（秒），可在观察者回放里跳到这些时刻核对；每段实际观察范围向两侧各延伸半个窗长。", "",
                  markdown_table(segments), ""]
    else:
        lines += ["## 二、候选驻留段落", "", "尚未设置 candidate_radius_m，本次只看分布。", ""]
    lines += ["## 三、各窗长的分布表", "", markdown_table(frame.round(3)), "", "## 四、图", ""]
    lines += [f"![{name}]({name})" for name in images]
    (dest / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── 运行 ────────────────────────────────────────────────────────────
def main():
    cfg = check(PARAMETERS)
    settings.validate()
    folder = find(cfg["dataset"], "track", [cfg["subject"]], run=cfg["run"])[cfg["subject"]]
    tables = load(cfg["dataset"], "track", cfg["subject"], run=cfg["run"], formatted=True)
    t, x, z = read_pose(tables)

    dest = HERE / "results" / "dwell_range"   # 只清空这个子文件夹，不动 results/ 下其他工具的输出（如 path_viewer/）
    if dest.exists():
        retire_dir(dest)
    dest.mkdir(parents=True)
    provenance = dest / "_provenance"

    session = tables["session"]
    duration = float(session[settings.column("session", "t_device_end")].iloc[0]
                     - session[settings.column("session", "t_device_start")].iloc[0])
    glitches = []
    if tables["tech_glitch"].attrs["present"]:
        glitches = list(zip(column(tables, "tech_glitch", "t_session"), column(tables, "tech_glitch", "duration")))
    tap_t = column(tables, "tap", "t_session") if tables["tap"].attrs["present"] else np.array([])
    touched = tables["tap"][settings.column("tap", "is_touched")].eq(True).fillna(False).to_numpy() \
        if tables["tap"].attrs["present"] else np.array([], dtype=bool)
    touched_t = tap_t[touched]

    series, rows = {}, []
    for width in cfg["widths"]:
        radius, speed = window_measures(t, x, z, width)
        series[width] = {"radius": radius, "speed": speed}
        rows.append(distribution_row(width, radius, cfg["floor"], duration))

    ref = cfg["reference"]
    radius, speed = series[ref]["radius"], series[ref]["speed"]
    ok = np.isfinite(radius) & np.isfinite(speed)
    corr = float(pd.Series(radius[ok]).corr(pd.Series(speed[ok]), method="spearman")) if ok.sum() > 10 else None
    near = glitch_overlap(t, glitches, ref)
    glitch_share = float(near[np.isfinite(radius)].mean()) if np.isfinite(radius).any() else 0.0

    episodes, step_speed, step_still = step_episodes(t, x, z, cfg["still_step"], tap_t, touched_t)
    episodes_info = episode_summary(episodes, step_speed, step_still, float(t[-1] - t[0]))
    segments = (dwell_segments(t, x, z, radius, cfg["candidate"], cfg["min_dwell"], tap_t, touched_t)
                if cfg["candidate"] else pd.DataFrame())
    intervals = np.diff(t)
    summary = {"record": folder.name, "duration_s": duration, "pose_rows": int(len(t)),
               "interval_median_s": float(np.median(intervals)), "interval_max_s": float(intervals.max()),
               "glitch_n": len(glitches), "run_at": now()[:19]}

    pd.DataFrame(rows).to_csv(dest / "table_distribution.csv", index=False, na_rep="")
    wide = {"t_session": t, "near_glitch_ref": near}
    for width in cfg["widths"]:
        wide[f"radius_{width:g}s"] = series[width]["radius"]
        wide[f"speed_{width:g}s"] = series[width]["speed"]
    pd.DataFrame(wide).to_csv(dest / "table_window_series.csv", index=False, na_rep="")
    episodes.to_csv(dest / "table_episodes.csv", index=False, na_rep="")
    if cfg["candidate"]:
        segments.to_csv(dest / "table_dwell_segments.csv", index=False, na_rep="")
    images = plots(cfg, series, rows, t, [g for g, _ in glitches], tap_t, touched_t, segments, episodes, summary, dest)
    build_report(cfg, rows, summary, segments, episodes_info, corr, glitch_share, images, dest)

    # 追溯信息：参数、Git 提交号、源码与原始文件校验值
    files = [ROOT / "global_settings.py"] + sorted((ANALYSIS / "tools").glob("*.py")) + [Path(__file__).resolve()]
    hashes, copied = record_sources(ROOT, files, provenance / "uncommitted_sources")
    raw_hashes = {str(p.relative_to(ROOT)): sha256(p) for name in settings.TRACK_TABLES
                  if (p := folder / settings.TRACK_FILES[name]).is_file()}
    write_json(provenance / "manifest.json", {
        "experiment": "track/description/behavior/dwell_range", "run_id": run_id(), "run_at": now(),
        "selection": {k: cfg[k] for k in ("dataset", "subject", "run")}, "record": folder.name,
        "git": git_state(ROOT, files), "uncommitted_copied": copied,
        "script_sha256": hashes, "source_sha256": raw_hashes,
        "script_history": script_history(Path(__file__).resolve()),
        "python_version": sys.version,
        "package_versions": {n: importlib.metadata.version(n) for n in ("numpy", "pandas", "matplotlib")}})
    write_json(provenance / "parameters_snapshot.json", PARAMETERS)
    write_json(provenance / "global_settings_snapshot.json", settings_snapshot())
    print(f"数据：{cfg['dataset']}／{folder.name}")
    print(f"打开报告：{dest / 'report.md'}")


# 脚本的修改记录（供 analysis/tools/lab_history.py 按时间检索），日常使用不必看。
SCRIPT_HISTORY = [
    {"at": "2026-10-24T16:56:30+08:00", "action": "created",
     "summary": "驻留的概念定义探索：对每个时刻取前后时间窗，计算水平活动半径，看其分布是否存在可切分的阈值（Otsu、谷深、双峰系数），并比较不同窗长；可按候选半径列出驻留段落供回放核对。"},
    {"at": "2026-10-24T16:57:47+08:00", "action": "modified",
     "summary": "增加不依赖时间窗的分析：按相邻采样是否移动，把全程切成不动片段和走动片段（table_episodes.csv、fig4），报告其时长分布。"},
    {"at": "2026-10-24T17:28:32+08:00", "action": "moved", "summary": "工作性质是描述（观察数据、识别行为的分类方式），不是统计分析：从 track/analysis/ 移到 track/description/behavior/。", "previous_path": "analysis/data_lab/track/analysis/dwell_range.py"}
]

if __name__ == "__main__":
    main()
