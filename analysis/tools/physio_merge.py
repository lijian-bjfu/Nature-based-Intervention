"""physio 工具 02 的全部处理函数：同一被试的多段录制按绝对时间拼接。

输入：data/<数据集>/processed/physio/sub-P###/<段文件夹>/（工具 01 的输出；跳过名为 merged 的文件夹）
输出：data/<数据集>/processed/physio/sub-P###/merged/
    ecg.csv、acc.csv、hr.csv、rr.csv、markers.csv、gaps.csv
        列顺序：t_unix, time_lsl, part, 其后是原有数据列（markers.csv 末尾另有 t_local）
    segments.csv：每段一行
    report.txt：中文报告

时钟对齐（每段单独做）：
    取该段 udp_clock.csv 中 type 为 hr 或 rr 的行，offset = t_device − time_lsl，
    取中位数作为该段的 offset；差值的四分位距（IQR）一并记录。
    t_unix = time_lsl + offset。
    某段没有可用的 hr/rr 包时无法对齐，该段不拼入，并在 segments.csv 与报告中写明。

安全：所有写入都先经过 check_inside()，目标不在 processed/physio/ 之内就报错，不写任何文件。
重跑只覆盖本工具生成的同名文件，不清空目录。读取只针对工具 01 的输出，不读 raw/。
"""
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from paths import layer_dir
from physio_xdf import check_inside, write_csv, list_subjects, normalize_subject

# 拼接的表（工具 01 的输出中与时间有关的表；udp_clock.csv 不拼接）
TABLES = ["ecg.csv", "acc.csv", "hr.csv", "rr.csv", "markers.csv", "gaps.csv"]
MERGED_DIR = "merged"
# 北京时间 UTC+8。中国大陆自 1991 年起不再使用夏令时，固定偏移即可，不依赖时区数据库。
TZ_BEIJING = timezone(timedelta(hours=8))
SEGMENT_COLUMNS = ["part", "start_unix", "end_unix", "start_local", "end_local",
                   "offset", "offset_iqr", "n_clock_rows", "tables"]


# ---------- 时间格式 ----------

def t_local(t_unix):
    """Unix 秒 → 北京时间 'YYYY-MM-DD HH:MM:SS.fff'（毫秒部分截断）。没有时间时返回空串。"""
    if t_unix is None or t_unix == "":
        return ""
    dt = datetime.fromtimestamp(float(t_unix), TZ_BEIJING)
    return dt.strftime("%Y-%m-%d %H:%M:%S") + f".{dt.microsecond // 1000:03d}"


def hms(seconds):
    """秒 → 'hh:mm:ss.fff'（负值前加负号，用于重叠的情况）。"""
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{sign}{h:02d}:{m:02d}:{s:06.3f}"


# ---------- 读取 ----------

def read_table(path):
    """读 csv，返回 (表头, 行列表)。行保持为文本，不做数值转换，以免改变原始写法。"""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        rows = [r for r in reader if r]
    return header, rows


def list_segments(subject_dir):
    """被试文件夹下的各段（工具 01 生成的子文件夹），跳过 merged/。"""
    return sorted(p for p in subject_dir.iterdir() if p.is_dir() and p.name != MERGED_DIR)


def load_tables(seg_dir):
    """读入该段存在的拼接表。缺某张表就跳过，不报错。"""
    tables = {}
    for name in TABLES:
        path = seg_dir / name
        if path.is_file():
            header, rows = read_table(path)
            if header:
                tables[name] = (header, rows)
    return tables


# ---------- 时钟对齐 ----------

def estimate_offset(seg_dir):
    """用 udp_clock.csv 中 hr/rr 包估计该段 offset = t_device − time_lsl。

    返回 {"offset": 中位数, "iqr": 四分位距, "n": 参与估计的行数}；无可用行时返回 None。
    """
    path = seg_dir / "udp_clock.csv"
    if not path.is_file():
        return None
    header, rows = read_table(path)
    i_lsl = header.index("time_lsl")
    i_type = header.index("type")
    i_dev = header.index("t_device")
    diffs = []
    for r in rows:
        if r[i_type] in ("hr", "rr") and r[i_dev] != "":
            diffs.append(float(r[i_dev]) - float(r[i_lsl]))
    if not diffs:
        return None
    d = np.asarray(diffs)
    q1, q3 = np.percentile(d, [25, 75])
    return {"offset": float(np.median(d)), "iqr": float(q3 - q1), "n": len(diffs)}


def time_range(seg, tables_only=None):
    """段内时间范围（t_unix）。tables_only 为 None 时取所有表，否则只取指定的表。"""
    lo, hi = None, None
    for name, (header, rows) in seg["tables"].items():
        if tables_only is not None and name != tables_only:
            continue
        ti = header.index("time_lsl")
        for r in rows:
            t = float(r[ti]) + seg["offset"]
            lo = t if lo is None or t < lo else lo
            hi = t if hi is None or t > hi else hi
    return lo, hi


# ---------- 拼接 ----------

def merged_table(name, usable):
    """把所有可对齐段的同一张表上下拼接，按 t_unix 排序。

    返回 (输出表头, 输出行列表)；所有段都没有这张表时返回 (None, [])。
    """
    header_ref, items = None, []
    for seg in usable:
        if name not in seg["tables"]:
            continue
        header, rows = seg["tables"][name]
        if header_ref is None:
            header_ref = header
        elif header != header_ref:
            raise RuntimeError(f"{seg['part']} 的 {name} 列与其它段不一致：{header} ≠ {header_ref}")
        ti = header.index("time_lsl")
        for r in rows:
            t = float(r[ti]) + seg["offset"]
            data = [v for j, v in enumerate(r) if j != ti]
            items.append((t, [t, r[ti], seg["part"]] + data))
    if header_ref is None:
        return None, []
    items.sort(key=lambda x: x[0])  # 稳定排序：同一时刻保持段的先后
    out_header = ["t_unix", "time_lsl", "part"] + [c for c in header_ref if c != "time_lsl"]
    rows_out = [row for _, row in items]
    if name == "markers.csv":
        out_header.append("t_local")
        rows_out = [row + [t_local(row[0])] for row in rows_out]
    return out_header, rows_out


# ---------- 报告 ----------

def build_report(dataset, subject, usable, excluded, merged_counts, marker_rows):
    """生成中文拼接报告。"""
    lines = []
    add = lines.append
    add("physio 工具 02 拼接报告（同一被试多段录制按绝对时间拼接）")
    add(f"数据集：{dataset}；被试：sub-{subject}")
    add(f"生成时间：{datetime.now(TZ_BEIJING).isoformat(timespec='seconds')}（北京时间）")
    add("时钟对齐：每段用自己 udp_clock.csv 中 hr/rr 包估计 offset = t_device − time_lsl（取中位数），")
    add("          t_unix = time_lsl + offset；IQR 为这些差值的四分位距。")
    add(f"段数：{len(usable) + len(excluded)}；参与拼接 {len(usable)}；未能对齐（未拼入）{len(excluded)}")
    add("")

    add("[一] 各段（时间为北京时间）")
    for seg in usable + excluded:
        add(f"  {seg['part']}")
        if seg["offset"] is None:
            add("    未能对齐：没有可用的 hr/rr 包或无 udp_clock.csv，本段未拼入")
            add(f"    包含表：{', '.join(n[:-4] for n in seg['tables']) or '无'}")
            continue
        s, e = seg["ecg_span"]
        if s is None:
            add("    起止：本段没有 ecg.csv，无法给出起止时间")
        else:
            add(f"    起：{t_local(s)}")
            add(f"    止：{t_local(e)}")
            add(f"    时长：{e - s:.3f} 秒（{hms(e - s)}）")
        add(f"    offset：{seg['offset']:.6f} 秒；IQR：{seg['iqr']:.6f} 秒；参与估计的 hr/rr 包数：{seg['n']}")
        present = [n[:-4] for n in seg["tables"]]
        add(f"    包含表：{', '.join(present) or '无'}")
        missing = [n[:-4] for n in TABLES if n not in seg["tables"]]
        add(f"    缺表（拼接时跳过）：{', '.join(missing) or '无'}")
    add("")

    add("[二] 段间空档（相邻两段：前段止 → 后段起）")
    if len(usable) < 2:
        add("  只有一段，没有段间空档")
    for prev, nxt in zip(usable, usable[1:]):
        p_end = prev["ecg_span"][1]
        n_start = nxt["ecg_span"][0]
        if p_end is None or n_start is None:
            add(f"  {prev['part']} → {nxt['part']}：缺 ecg.csv，无法计算空档")
            continue
        gap = n_start - p_end
        tag = "（重叠，负值）" if gap < 0 else ""
        add(f"  {prev['part']} 止 {t_local(p_end)} → {nxt['part']} 起 {t_local(n_start)}")
        add(f"    空档：{gap:.3f} 秒（{hms(gap)}）{tag}")
    add("")

    add("[三] 拼接后各表行数")
    for name in TABLES:
        if name in merged_counts:
            add(f"  {name}  {merged_counts[name]} 行")
        else:
            add(f"  {name}  未输出（所有段都没有这张表）")
    add("")

    add(f"[四] 拼接后全部标记（共 {len(marker_rows)} 条，不含 gap_ 断流记录；多余标记未删除）")
    if marker_rows:
        add("  t_local                   label")
        for t_text, label in marker_rows:
            add(f"  {t_text}  {label}")
    else:
        add("  （无）")
    return "\n".join(lines) + "\n"


# ---------- 单个被试 ----------

def merge_subject(dataset, subject, subject_dir, processed):
    """拼接一个被试的各段，写入 merged/。返回摘要 dict。"""
    segs = []
    for seg_dir in list_segments(subject_dir):
        seg = {"part": seg_dir.name, "tables": load_tables(seg_dir)}
        est = estimate_offset(seg_dir)
        seg["offset"] = est["offset"] if est else None
        seg["iqr"] = est["iqr"] if est else None
        seg["n"] = est["n"] if est else 0
        seg["ecg_span"] = (None, None)
        seg["all_span"] = (None, None)
        if seg["offset"] is not None:
            seg["ecg_span"] = time_range(seg, tables_only="ecg.csv")
            seg["all_span"] = time_range(seg)
        segs.append(seg)
    if not segs:
        raise ValueError(f"sub-{subject} 下没有段文件夹（先运行工具 01）")

    # 能对齐且有数据的段按最早 t_unix 排序；其余不拼入
    usable = [s for s in segs if s["offset"] is not None and s["all_span"][0] is not None]
    usable.sort(key=lambda s: s["all_span"][0])
    usable_ids = {id(s) for s in usable}
    excluded = [s for s in segs if id(s) not in usable_ids]

    merged_dir = processed / f"sub-{subject}" / MERGED_DIR
    check_inside(merged_dir, processed)

    merged_counts, merged_markers = {}, []
    for name in TABLES:
        header, rows = merged_table(name, usable)
        if header is None:
            continue
        write_csv(merged_dir / name, header, rows, processed)
        merged_counts[name] = len(rows)
        if name == "markers.csv":
            ci = header.index("label")
            merged_markers = [(row[-1], row[ci]) for row in rows]

    # segments.csv：每段一行（起止取该段 ecg.csv 的首尾 t_unix）
    seg_rows = []
    for seg in usable + excluded:
        s, e = seg["ecg_span"]
        seg_rows.append([
            seg["part"],
            "" if s is None else s,
            "" if e is None else e,
            t_local(s),
            t_local(e),
            "" if seg["offset"] is None else seg["offset"],
            "" if seg["iqr"] is None else seg["iqr"],
            seg["n"],
            ";".join(n[:-4] for n in seg["tables"]),
        ])
    write_csv(merged_dir / "segments.csv", SEGMENT_COLUMNS, seg_rows, processed)

    # 报告：各段、段间空档、拼接后行数与标记
    report = build_report(dataset, subject, usable, excluded, merged_counts, merged_markers)
    write_text_report(merged_dir / "report.txt", report, processed)
    return {"subject": subject, "merged_dir": merged_dir, "usable": [s["part"] for s in usable],
            "excluded": [s["part"] for s in excluded], "counts": merged_counts, "markers": merged_markers}


def write_text_report(path, text, root):
    """写 report.txt（写前检查路径）。"""
    target = check_inside(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# ---------- 入口 ----------

def run(dataset, subjects="*"):
    """对数据集中的被试做段拼接。返回每位被试的摘要列表。"""
    processed = layer_dir(dataset, "processed", "physio")
    pool = list_subjects(processed)
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"processed/physio 中没有这些被试：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"processed/physio 中没有任何 sub-P### 文件夹：{processed}（先运行工具 01）")

    print(f"数据集 {dataset}：共 {len(chosen)} 位被试")
    summaries = []
    for subject in chosen:
        subject_dir = processed / f"sub-{subject}"
        print(f"[开始] sub-{subject}")
        summary = merge_subject(dataset, subject, subject_dir, processed)
        print(f"[完成] sub-{subject}：拼入 {', '.join(summary['usable']) or '无'}"
              f"；未拼入 {', '.join(summary['excluded']) or '无'}")
        print(f"       输出：{summary['merged_dir']}")
        summaries.append(summary)
    return summaries
