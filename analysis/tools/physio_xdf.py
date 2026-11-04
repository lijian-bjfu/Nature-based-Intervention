"""physio 工具 01 的全部处理函数：把 xdf 拆成 csv，并做结构体检。

只借用 PhysicoBridge（src/tools/xdf_to_csv.py、check_xdf.py）的读取与导出思路；
弹窗、RECORDER_DATA_DIR 路径逻辑、设备后缀命名均已去掉。

输入：data/<数据集>/raw/physio/sub-P###/*.xdf（只看该文件夹直接子项，_excluded/ 自动跳过）
输出：data/<数据集>/processed/physio/sub-P###/<xdf 文件名去掉 .xdf>/
    ecg.csv、acc.csv、hr.csv、rr.csv、markers.csv、gaps.csv、udp_clock.csv、header.json、report.txt
    某条流不存在时不生成对应 csv，并在 report.txt 中写"缺失"，不中断处理。

安全：所有写入都先经过 check_inside()，目标不在 processed/physio/ 之内就报错，不写任何文件。
重跑只覆盖本工具固定的同名文件，不清空目录。
"""
import csv
import json
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

from paths import layer_dir

# 期望的流类型（报告中逐条检查）
EXPECTED_TYPES = ["ECG", "ACC", "HR", "RR", "Markers", "udp_text"]
# 以此前缀开头的 Markers 标记属于断流记录，进 gaps.csv
GAP_PREFIX = "gap_"
# PB_UDP 中只导出这三类包
UDP_KEEP = ("rr", "hr", "marker")

# 每个输出文件的列：(列名, 含义)。表头与报告都从这里取，保证两者一致。
OUTPUTS = {
    "ecg.csv": [
        ("time_lsl", "LSL 时间（秒，xdf 时间戳）"),
        ("uV", "心电电压（微伏）"),
    ],
    "acc.csv": [
        ("time_lsl", "LSL 时间（秒，xdf 时间戳）"),
        ("x_mG", "X 轴加速度（毫 g）"),
        ("y_mG", "Y 轴加速度（毫 g）"),
        ("z_mG", "Z 轴加速度（毫 g）"),
    ],
    "hr.csv": [
        ("time_lsl", "LSL 时间（秒，xdf 时间戳）"),
        ("bpm", "瞬时心率（次/分）"),
    ],
    "rr.csv": [
        ("time_lsl", "LSL 时间（秒，xdf 时间戳）"),
        ("ms", "RR 间期（毫秒；只取第 1 通道，第 2 通道 te 精度不足，未导出）"),
    ],
    "markers.csv": [
        ("time_lsl", "LSL 时间（秒，xdf 时间戳）"),
        ("label", "事件标签（不以 gap_ 开头的标记）"),
    ],
    "gaps.csv": [
        ("time_lsl", "LSL 时间（秒，xdf 时间戳）"),
        ("label", "断流记录（以 gap_ 开头，原样保存）"),
    ],
    "udp_clock.csv": [
        ("time_lsl", "LSL 时间（秒，xdf 时间戳）"),
        ("type", "包类型：rr / hr / marker"),
        ("seq", "包序号（marker 包没有此字段，留空）"),
        ("t_device", "设备端时间戳（JSON 中的 t_device，原样保留全部小数位）"),
        ("te", "beat 事件时间（JSON 中的 te，仅 rr 包有，其余留空）"),
    ],
}

# 数值流 → 输出文件 → 取前几个通道
NUMERIC = [
    ("ECG", "ecg.csv", 1),
    ("ACC", "acc.csv", 3),
    ("HR", "hr.csv", 1),
    ("RR", "rr.csv", 1),
]


# ---------- 路径与写入保护 ----------

def check_inside(path, root):
    """写入前检查：path 必须位于 root 之内，否则报错，不写任何文件。"""
    target = Path(path).resolve()
    base = Path(root).resolve()
    if base not in target.parents:
        raise RuntimeError(f"拒绝写入：{target} 不在允许的输出目录 {base} 之内")
    return target


def write_csv(path, header, rows, root):
    """按固定表头写 csv（utf-8）。写前先检查路径。"""
    target = check_inside(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return target


def write_text(path, text, root):
    """写普通文本（header.json、report.txt）。写前先检查路径。"""
    target = check_inside(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# ---------- 流的读取辅助 ----------

def flat(value):
    """把一个样本（数组、列表或字符串）拍平成一维 Python 列表。"""
    return np.asarray(value).ravel().tolist()


def info(stream, key):
    """xdf 流信息字段（pyxdf 中都是字符串列表），取第一个值。"""
    values = stream.get("info", {}).get(key) or [""]
    return values[0]


def stream_name(stream):
    return str(info(stream, "name"))


def stream_type(stream):
    return str(info(stream, "type"))


def to_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def to_int(text):
    value = to_float(text)
    return None if value is None else int(value)


def find_streams(streams, stype):
    """按流类型（不区分大小写）找出所有匹配的流，保持文件中的顺序。"""
    return [s for s in streams if stream_type(s).lower() == stype.lower()]


def span(stream):
    """流的首尾 time_lsl；没有样本时返回 (None, None)。"""
    ts = stream["time_stamps"]
    if len(ts) == 0:
        return None, None
    return float(ts[0]), float(ts[-1])


# ---------- 各类流的导出 ----------

def numeric_rows(stream, ncols):
    """数值流：每行 time_lsl + 前 ncols 个通道；缺通道的位置留空。"""
    rows = []
    for t, sample in zip(stream["time_stamps"], stream["time_series"]):
        values = [float(v) for v in flat(sample)[:ncols]]
        values += [""] * (ncols - len(values))
        rows.append([float(t)] + values)
    return rows


def split_markers(stream):
    """Markers 流：标签以 gap_ 开头的进断流表，其余进标记表。标签原样保存。"""
    markers, gaps = [], []
    for t, sample in zip(stream["time_stamps"], stream["time_series"]):
        items = flat(sample)
        label = str(items[0]) if items else ""
        (gaps if label.startswith(GAP_PREFIX) else markers).append([float(t), label])
    return markers, gaps


def udp_rows(stream):
    """PB_UDP 文本流：每个样本是一段 JSON 文本，只保留 rr、hr、marker 包。

    返回 (行, 各类型导出计数, 各类型未导出计数, 无法解析的样本数)。
    """
    rows, kept, dropped, bad = [], Counter(), Counter(), 0
    for t, sample in zip(stream["time_stamps"], stream["time_series"]):
        items = flat(sample)
        try:
            # parse_float=str：小数按 JSON 原文保存，不经过浮点转换，保留全部小数位
            packet = json.loads(items[0], parse_float=str) if items else None
        except (TypeError, ValueError):
            packet = None
        if not isinstance(packet, dict):
            bad += 1
            continue
        ptype = packet.get("type")
        if ptype not in UDP_KEEP:
            dropped[str(ptype)] += 1
            continue
        # 字段缺失时留空；t_device、te 保持 JSON 中的原始数值（csv 写入时保留全部小数位）
        rows.append([float(t), ptype, packet.get("seq", ""), packet.get("t_device", ""), packet.get("te", "")])
        kept[ptype] += 1
    return rows, kept, dropped, bad


# ---------- 报告 ----------

def build_report(xdf_name, dt, streams, written, missing, udp, marker_counts, marker_items):
    """生成中文结构体检报告文本。"""
    lines = []
    add = lines.append
    add("physio 结构体检报告（xdf → csv）")
    add(f"源文件：{xdf_name}")
    add(f"xdf 文件头录制时间：{dt or '（无）'}")
    add(f"生成时间：{datetime.now().isoformat(timespec='seconds')}")
    add(f"xdf 内流的数量：{len(streams)}")
    add("")

    add("[一] 期望流结构（有/缺失与样本数）")
    for stype in EXPECTED_TYPES:
        matches = find_streams(streams, stype)
        if not matches:
            add(f"  {stype:<9} 缺失（本文件没有 {stype} 流）")
            continue
        s = matches[0]
        detail = f"流名 {stream_name(s)}，样本数 {len(s['time_stamps'])}"
        if stype == "Markers" and marker_counts is not None:
            detail += f"（gap_ 开头 {marker_counts[1]} 条，其它 {marker_counts[0]} 条）"
        elif stype == "udp_text":
            detail += "（样本数即 JSON 包数）"
        else:
            rate = to_float(info(s, "nominal_srate"))
            rate_text = "不规则（事件流）" if rate == 0 else ("未知" if rate is None else f"{rate:g} Hz")
            detail += f"，通道 {to_int(info(s, 'channel_count'))}，标称采样率 {rate_text}"
        add(f"  {stype:<9} 有  {detail}")
        if len(matches) > 1:
            add(f"            注意：该类型有 {len(matches)} 条流，只取第一条，其余未导出")

    expected_lower = {t.lower() for t in EXPECTED_TYPES}
    others = [s for s in streams if stream_type(s).lower() not in expected_lower]
    if others:
        add("  其它流（不在期望清单内，未导出）：")
        for s in others:
            add(f"    - 流名 {stream_name(s)}，类型 {stream_type(s)}，样本数 {len(s['time_stamps'])}")
    else:
        add("  其它流：无")
    add("")

    add("[二] PB_UDP 包统计")
    if udp is None:
        add("  本文件没有 udp_text 流，未生成 udp_clock.csv")
    else:
        kept, dropped, bad = udp
        add("  导出：" + ("、".join(f"{k} {kept[k]} 包" for k in UDP_KEEP) or "无"))
        add("  未导出（非 rr/hr/marker）：" + ("、".join(f"{k} {n} 包" for k, n in dropped.most_common()) or "无"))
        add(f"  无法解析的样本：{bad}")
    add("")

    add("[三] 输出文件（行数与各列含义）")
    for filename in OUTPUTS:
        if filename in written:
            add(f"  {filename}  {written[filename]} 行")
            add("      列：" + "；".join(f"{c}＝{m}" for c, m in OUTPUTS[filename]))
    add("  header.json  xdf 头的录制时间，以及每条流的 name、type、channel_count、nominal_srate、样本数、首尾 time_lsl")
    add("  report.txt   本报告")
    if missing:
        add("  未生成（缺失）：")
        for filename, reason in missing:
            add(f"    - {filename}：{reason}")
    add("")

    add(f"[四] markers.csv 全部标记（共 {len(marker_items)} 条，不含 gap_ 断流记录）")
    if marker_items:
        add("  time_lsl（秒）          label")
        for t, label in marker_items:
            add(f"  {t:<22.4f}  {label}")
    else:
        add("  （无）")
    return "\n".join(lines) + "\n"


# ---------- 单个 xdf 的处理 ----------

def process_xdf(pyxdf, xdf_path, out_dir, guard_root):
    """处理一个 xdf：导出 csv、header.json、report.txt。返回摘要 dict。"""
    # pyxdf 内部的 numpy 无害提示，屏蔽以免刷屏
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*'where' used without 'out'.*")
        streams, header = pyxdf.load_xdf(str(xdf_path))

    written, missing = {}, []

    def emit(filename, rows):
        write_csv(out_dir / filename, [c for c, _ in OUTPUTS[filename]], rows, guard_root)
        written[filename] = len(rows)

    # 数值流（ECG、ACC、HR、RR）
    for stype, filename, ncols in NUMERIC:
        matches = find_streams(streams, stype)
        if matches:
            emit(filename, numeric_rows(matches[0], ncols))
        else:
            missing.append((filename, f"本文件没有 {stype} 流"))

    # Markers 流：拆成标记表与断流表
    marker_items, marker_counts = [], None
    matches = find_streams(streams, "Markers")
    if matches:
        markers, gaps = split_markers(matches[0])
        emit("markers.csv", markers)
        emit("gaps.csv", gaps)
        marker_items = markers
        marker_counts = (len(markers), len(gaps))
    else:
        missing.append(("markers.csv", "本文件没有 Markers 流"))
        missing.append(("gaps.csv", "本文件没有 Markers 流"))

    # PB_UDP 文本流：只导出 rr、hr、marker 包
    udp = None
    matches = find_streams(streams, "udp_text")
    if matches:
        rows, kept, dropped, bad = udp_rows(matches[0])
        emit("udp_clock.csv", rows)
        udp = (kept, dropped, bad)
    else:
        missing.append(("udp_clock.csv", "本文件没有 udp_text 流（PB_UDP）"))

    # header.json：录制时间 + 每条流的概要
    stream_summaries = []
    for s in streams:
        first, last = span(s)
        stream_summaries.append({
            "name": stream_name(s),
            "type": stream_type(s),
            "channel_count": to_int(info(s, "channel_count")),
            "nominal_srate": to_float(info(s, "nominal_srate")),
            "samples": len(s["time_stamps"]),
            "first_time_lsl": first,
            "last_time_lsl": last,
        })
    dt = str(header.get("info", {}).get("datetime", [""])[0]) if header else ""
    write_text(out_dir / "header.json",
               json.dumps({"datetime": dt, "streams": stream_summaries}, ensure_ascii=False, indent=2),
               guard_root)

    # report.txt
    report = build_report(xdf_path.name, dt, streams, written, missing, udp, marker_counts, marker_items)
    write_text(out_dir / "report.txt", report, guard_root)

    return {"xdf": xdf_path.name, "out_dir": out_dir, "written": written, "missing": missing}


# ---------- 被试与文件选择 ----------

def normalize_subject(text):
    """接受 'P001' 或 'sub-P001'，统一成 'P001'。"""
    text = str(text).strip()
    return text[4:] if text.startswith("sub-") else text


def list_subjects(raw_physio):
    """raw/physio/ 下所有 sub-P### 文件夹的被试编号。"""
    return sorted(p.name[4:] for p in raw_physio.iterdir() if p.is_dir() and p.name.startswith("sub-"))


def select_subjects(raw_physio, subjects):
    """subjects 为 '*'（全部）或编号列表；列表里有不存在的被试则报错。"""
    pool = list_subjects(raw_physio)
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"raw/physio 中没有这些被试：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"raw/physio 中没有任何 sub-P### 文件夹：{raw_physio}")
    return chosen


def xdf_files(raw_physio, subject):
    """被试文件夹直接子项中的 .xdf（不递归，因此 _excluded/ 中的文件不会被读取）。"""
    folder = raw_physio / f"sub-{subject}"
    return sorted(p for p in folder.glob("*.xdf") if p.is_file())


# ---------- 入口函数 ----------

def run(dataset, subjects="*"):
    """处理一个数据集中的被试。返回每个 xdf 的处理摘要列表。"""
    try:
        import pyxdf
    except ImportError as error:
        raise RuntimeError("缺少依赖 pyxdf，请先自行安装后再运行（本工具不自动安装）") from error

    raw_physio = layer_dir(dataset, "raw", "physio")
    processed = layer_dir(dataset, "processed", "physio")

    jobs = []
    for subject in select_subjects(raw_physio, subjects):
        files = xdf_files(raw_physio, subject)
        if not files:
            print(f"[跳过] sub-{subject}：没有 .xdf 文件")
        jobs += [(subject, f) for f in files]
    if not jobs:
        raise ValueError(f"没有可处理的 .xdf 文件（数据集 {dataset}）")

    print(f"数据集 {dataset}：共 {len(jobs)} 个 xdf")
    summaries = []
    for subject, xdf in jobs:
        out_dir = processed / f"sub-{subject}" / xdf.stem
        check_inside(out_dir, processed)  # 先确认输出位置合法
        print(f"[开始] sub-{subject}/{xdf.name}")
        summary = process_xdf(pyxdf, xdf, out_dir, processed)
        missing = "、".join(f for f, _ in summary["missing"]) or "无"
        print(f"[完成] {xdf.name}：写出 {len(summary['written'])} 个 csv，缺失 {missing}")
        print(f"       输出：{out_dir}")
        summaries.append(summary)
    return summaries
