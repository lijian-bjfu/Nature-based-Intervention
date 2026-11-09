"""physio 工具 07 的全部处理逻辑：窗口质量与 HRV 指标（平均心率、RMSSD、lnRMSSD、SDNN）。

口径与阈值全部来自 global_settings.METRICS["physio"]，本文件不写死。
valid_beat：handling 为 0–3 的拍（4 待人工一律排除），用于平均心率与 hr_coverage。
real_beat：handling 为 0 或 2 的拍（真实间期）；handling 1、3 是推算值，在 HRV 中按空洞处理。RMSSD、SDNN、HF 只用 real_beat。
拍的归属：t_unix 落在 [t_start, t_end) 的拍属于该窗口。

输入（只读）：data/<数据集>/processed/physio/sub-P###/events/windows.csv（工具 03）、clean/rr.csv（工具 05）
输出：data/<数据集>/final/physio/window_metrics_long.csv、window_metrics_wide.csv、window_metrics_report.txt（整表重算并覆盖）
写入前检查路径在 final/physio/ 之内。
"""
import csv
import math
from datetime import datetime

import numpy as np
from scipy.signal import lombscargle

from global_settings import METRICS, PHYSIO_PHASES
from paths import layer_dir
from physio_xdf import check_inside, list_subjects, normalize_subject

LONG_COLUMNS = ["subject", "window", "window_valid", "duration_s", "n_beats_valid", "n_real", "n_estimated",
                "n_review", "hr_coverage", "hrv_coverage", "hr_ok", "hrv_ok",
                "hr_mean", "rmssd", "ln_rmssd", "sdnn", "hf", "ln_hf", "note"]
WIDE_METRICS = ("hr_mean", "rmssd", "ln_rmssd", "sdnn", "hf", "ln_hf", "hr_ok", "hrv_ok")
DIGITS = {"hr_coverage": 4, "hrv_coverage": 4, "ln_rmssd": 4, "duration_s": 2,
          "hr_mean": 2, "rmssd": 2, "sdnn": 2, "hf": 2, "ln_hf": 4}


def fmt(key, value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ""
    return f"{value:.{DIGITS[key]}f}" if key in DIGITS else str(value)


def pct(x):
    return f"{x * 100:.1f}%"


def pct_limit(x):
    return f"{x * 100:g}%"


def read_windows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_rr(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: float(r["t_unix"]))
    return (np.array([float(r["t_unix"]) for r in rows]), np.array([float(r["ms"]) for r in rows]),
            np.array([int(float(r["gap_before"])) for r in rows]), np.array([int(float(r["handling"])) for r in rows]))


def to_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def hf_power(t, x, band_hz, step_hz):
    """HF 功率（ms²）：Lomb-Scargle 周期图，不插补。t 为拍时刻（s），x 为 RR（ms）。

    先减均值；scipy.lombscargle 的频率参数是角频率（rad/s）。未归一化周期图 P_raw 在偶采样下约等于 |X|²/N，
    故单边功率谱密度 = 2·(T/N)·P_raw（ms²/Hz），T 为首尾拍时间跨度，N 为拍数；在频带内梯形积分得 ms²。
    """
    t, x = np.asarray(t, float), np.asarray(x, float)
    if len(t) < 3 or t[-1] <= t[0]:
        return None
    freqs = np.arange(band_hz[0], band_hz[1] + step_hz / 2, step_hz)
    raw = lombscargle(t - t[0], x - x.mean(), 2 * np.pi * freqs, precenter=False, normalize=False)
    psd = 2.0 * (t[-1] - t[0]) / len(t) * raw
    return float(np.trapezoid(psd, freqs))


def window_row(pid, win, rr, params, hf_params=None):
    t, ms, gap, handling = rr
    row = {k: None for k in LONG_COLUMNS}
    row.update(subject=pid, window=win["window"], window_valid=int(win["valid"]), note="")
    t0, t1, dur = to_float(win["t_start"]), to_float(win["t_end"]), to_float(win["duration_s"])
    row["duration_s"] = dur
    if row["window_valid"] == 0 or t0 is None or t1 is None or not dur:
        row["note"] = "窗口无效：" + (win.get("issue") or "")
        return row
    lo, hi = np.searchsorted(t, t0, side="left"), np.searchsorted(t, t1, side="left")
    ms_w, h_w, g_w, t_w = ms[lo:hi], handling[lo:hi], gap[lo:hi], t[lo:hi]
    valid = h_w <= 3
    real = (h_w == 0) | (h_w == 2)
    row["n_beats_valid"] = int(valid.sum())
    row["n_real"] = int(real.sum())
    row["n_estimated"] = int(((h_w == 1) | (h_w == 3)).sum())
    row["n_review"] = int((h_w == 4).sum())
    real_s = float(ms_w[real].sum()) / 1000.0
    row["hr_coverage"] = float(ms_w[valid].sum()) / 1000.0 / dur
    row["hrv_coverage"] = real_s / dur
    notes = []
    hr_ok = row["hr_coverage"] >= params["hr_min_coverage"]
    hrv_ok = row["hrv_coverage"] >= params["hrv_min_coverage"]
    row["hr_ok"], row["hrv_ok"] = int(hr_ok), int(hrv_ok)
    if not hr_ok:
        notes.append(f"心率覆盖率 {pct(row['hr_coverage'])} < {pct_limit(params['hr_min_coverage'])}")
    if not hrv_ok:
        notes.append(f"HRV 覆盖率 {pct(row['hrv_coverage'])} < {pct_limit(params['hrv_min_coverage'])}")
    if row["n_beats_valid"] > 0:
        row["hr_mean"] = 60000.0 / float(ms_w[valid].mean())
    else:
        notes.append("窗口内没有有效拍，平均心率留空")
    if real_s < params["min_real_seconds"] or row["n_real"] < 2:
        notes.append(f"真实间期 RR 之和 {real_s:.1f} s < {params['min_real_seconds']:g} s，HRV 指标留空")
    else:
        pair = real[1:] & real[:-1] & (g_w[1:] == 0)
        d = (ms_w[1:] - ms_w[:-1])[pair]
        if len(d):
            row["rmssd"] = float(np.sqrt(np.mean(d ** 2)))
            row["ln_rmssd"] = math.log(row["rmssd"]) if row["rmssd"] > 0 else None
        else:
            notes.append("没有可用的相邻拍对，RMSSD 无法计算")
        row["sdnn"] = float(np.std(ms_w[real], ddof=1))
        if hf_params:
            row["hf"] = hf_power(t_w[real], ms_w[real], hf_params["band_hz"], hf_params["freq_step_hz"])
            row["ln_hf"] = math.log(row["hf"]) if row["hf"] and row["hf"] > 0 else None
    row["note"] = "；".join(notes)
    return row


def write_outputs(rows, subjects, skipped, params, hf_params, out_dir, final):
    long_path = check_inside(out_dir / "window_metrics_long.csv", final)
    wide_path = check_inside(out_dir / "window_metrics_wide.csv", final)
    report_path = check_inside(out_dir / "window_metrics_report.txt", final)
    out_dir.mkdir(parents=True, exist_ok=True)
    with long_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(LONG_COLUMNS)
        for r in rows:
            w.writerow([fmt(k, r[k]) for k in LONG_COLUMNS])
    wide_cols = ["subject"] + [f"{p}_{m}" for p in PHYSIO_PHASES for m in WIDE_METRICS]
    with wide_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(wide_cols)
        for pid in subjects:
            by = {r["window"]: r for r in rows if r["subject"] == pid}
            w.writerow([pid] + [fmt(m, by[p][m]) if p in by else "" for p in PHYSIO_PHASES for m in WIDE_METRICS])

    lines = ["physio 工具 07 窗口指标报告",
             f"生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}", "",
             "[一] 口径与参数（来自 global_settings.METRICS['physio']）",
             "  valid_beat：handling 为 0–3 的拍（4 待人工一律排除）；real_beat：handling 为 0 或 2 的拍；handling 1、3 是推算值，在 HRV 中按空洞处理",
             "  拍属于 [t_start, t_end) 的窗口。hr_coverage = valid_beat 的 RR 之和 / 窗口时长；hrv_coverage = real_beat 的 RR 之和 / 窗口时长",
             f"  hr_ok：hr_coverage ≥ {pct_limit(params['hr_min_coverage'])}；hrv_ok：hrv_coverage ≥ {pct_limit(params['hrv_min_coverage'])}；不合格时数值照常输出，note 写明原因",
             f"  real_beat 的 RR 之和不足 {params['min_real_seconds']:g} s 时 HRV 指标留空",
             "  平均心率 = 60000 / valid_beat 的 RR 均值；RMSSD 只用前后相邻、两拍均为 real_beat 且后一拍无丢包的相邻对；SDNN 只用 real_beat（ddof=1）",
             f"  HF 功率：Lomb-Scargle 周期图（只用 real_beat，不插补，其余拍缺席；先减均值），PSD 单位 ms²/Hz，"
             f"在 {hf_params['band_hz'][0]}–{hf_params['band_hz'][1]} Hz 积分（频率步长 {hf_params['freq_step_hz']} Hz）；lnHF 为其自然对数", "",
             f"[二] 处理被试（{len(subjects)} 位）"]
    lines += [f"  跳过 {pid}：{why}" for pid, why in skipped] or ["  无跳过"]
    lines += ["", "[三] 每人每窗口摘要"]
    for r in rows:
        if not r["window_valid"]:
            body = "窗口无效"
        else:
            body = (f"有效拍 {r['n_beats_valid']}（真实 {r['n_real']}，推算 {r['n_estimated']}），待人工 {r['n_review']}，"
                    f"hr_coverage {fmt('hr_coverage', r['hr_coverage'])}，hrv_coverage {fmt('hrv_coverage', r['hrv_coverage'])}，"
                    f"hr_ok={r['hr_ok']} hrv_ok={r['hrv_ok']}，HR {fmt('hr_mean', r['hr_mean']) or '—'} bpm，"
                    f"RMSSD {fmt('rmssd', r['rmssd']) or '—'} ms，lnRMSSD {fmt('ln_rmssd', r['ln_rmssd']) or '—'}，"
                    f"SDNN {fmt('sdnn', r['sdnn']) or '—'} ms，"
                    f"HF {fmt('hf', r['hf']) or '—'} ms²，lnHF {fmt('ln_hf', r['ln_hf']) or '—'}")
        lines.append(f"  {r['subject']} {r['window']:<24} {body}" + (f"  〔{r['note']}〕" if r["note"] else ""))
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(dataset, subjects="*"):
    params = METRICS["physio"]["window_quality"]["parameters"]
    hf_params = METRICS["physio"]["hf"]["parameters"]
    processed = layer_dir(dataset, "processed", "physio")
    final = layer_dir(dataset, "final", "physio")
    pool = list_subjects(processed)
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"processed/physio 中没有这些被试：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"processed/physio 中没有任何 sub-P### 文件夹：{processed}")
    rows, done, skipped = [], [], []
    for pid in chosen:
        base = processed / f"sub-{pid}"
        if not (base / "events" / "windows.csv").is_file():
            skipped.append((pid, "请先运行 03（缺 events/windows.csv）"))
            continue
        if not (base / "clean" / "rr.csv").is_file():
            skipped.append((pid, "请先运行 05（缺 clean/rr.csv）"))
            continue
        rr = read_rr(base / "clean" / "rr.csv")
        wins = {w["window"]: w for w in read_windows(base / "events" / "windows.csv")}
        for phase in PHYSIO_PHASES:
            if phase in wins:
                rows.append(window_row(pid, wins[phase], rr, params, hf_params))
        done.append(pid)
        print(f"[完成] {pid}")
    for pid, why in skipped:
        print(f"[跳过] {pid}：{why}")
    write_outputs(rows, done, skipped, params, hf_params, final, final)
    print(f"已写入 {final}")
    print("-" * 60)
    root = final.resolve()
    print(f"全体汇总：{root}/window_metrics_long.csv、window_metrics_wide.csv、window_metrics_report.txt")
    print("看什么：指标为空的格子，看 note 列写的原因。")
    return rows
