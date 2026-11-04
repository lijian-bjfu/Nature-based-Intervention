"""psycho 工具 01 的全部处理函数：问卷完整性检查（未提交、缺答、全同选项、作答过快）。

输入（只读）：data/<数据集>/raw/psycho/sub-P###/questionnaires.csv、state.json
    只看 raw/psycho/ 下的 sub-P### 文件夹；下划线开头的文件夹（_excluded/、_archive_* 等）跳过。
输出：data/<数据集>/processed/psycho/preview/check/
    completeness.csv：每位被试 × 每份问卷一行，所有被试合表
    completeness_report.txt：中文报告

问卷 = 列名第一个下划线前的部分（A、T0、T1、T2、T3）。
量表块 = 列名去掉末尾 "_数字" 后的部分，如 T1_stai6_3 → T1_stai6。
用时 = state.json 中 submitted_at − started_at；每题用时 = 用时 ÷ answers 的条数。

安全：所有写入都先经过 check_inside()，目标不在 processed/psycho/ 之内就报错，不写任何文件。
重跑只替换本次处理的被试的行，其他被试的行保留。读取不改 raw/。
"""
import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paths import layer_dir

# 问卷代号（列名第一个下划线之前的部分）。列名前缀不在此表中的列（如 participant_id、group）不计入问卷。
QUESTIONNAIRES = ("A", "T0", "T1", "T2", "T3")
# 合表的列，顺序即输出顺序
COLUMNS = ["subject", "instrument", "submitted", "n_items", "n_missing", "missing_items",
           "duration_s", "sec_per_item", "too_fast", "straightline_blocks", "flag", "note"]
# 被试文件夹没有完整文件时，用此代号占一行
ALL_INSTRUMENTS = "ALL"
PREVIEW_SUBDIR = ("preview", "check")
TABLE_NAME = "completeness.csv"
REPORT_NAME = "completeness_report.txt"
# 北京时间 UTC+8，与工具 02 一致（固定偏移，不依赖时区数据库）
TZ_BEIJING = timezone(timedelta(hours=8))


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
    """写 completeness_report.txt。写前先检查路径。"""
    target = check_inside(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# ---------- 被试与文件选择 ----------

def normalize_subject(text):
    """接受 'P001' 或 'sub-P001'，统一成 'P001'。"""
    text = str(text).strip()
    return text[4:] if text.startswith("sub-") else text


def list_subjects(raw_psycho):
    """raw/psycho/ 下所有 sub-P### 文件夹的被试编号；下划线开头的文件夹不算。"""
    return sorted(p.name[4:] for p in raw_psycho.iterdir()
                  if p.is_dir() and p.name.startswith("sub-") and not p.name.startswith("_"))


def select_subjects(raw_psycho, subjects):
    """subjects 为 '*'（全部）或编号列表；列表里有不存在的被试则报错。"""
    pool = list_subjects(raw_psycho)
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"raw/psycho 中没有这些被试：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"raw/psycho 中没有任何 sub-P### 文件夹：{raw_psycho}")
    return chosen


# ---------- 读取与小工具 ----------

def read_questionnaire_csv(path):
    """读 questionnaires.csv，返回 (列名列表, 行字典列表)。utf-8-sig 去掉 Excel 写入的 BOM。"""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    return header, rows


def to_float(value):
    """转成浮点数；无法转换（None、空串、非数字）时返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def yn(flag):
    """布尔值写成 yes / no。"""
    return "yes" if flag else "no"


def fmt(value, digits):
    """数值保留指定位数写成文本；None 写成空串。"""
    return "" if value is None else f"{value:.{digits}f}"


def block_name(column):
    """量表块名：去掉列名末尾的 '_数字'。没有这种后缀的列，块名就是列名本身。"""
    return re.sub(r"_\d+$", "", column)


def instrument_columns(header, instrument):
    """表头中属于某份问卷的列（列名第一个下划线前的部分等于问卷代号）。"""
    return [c for c in header if c.split("_", 1)[0] == instrument]


def straightline_blocks(columns, values, min_items):
    """题数不少于 min_items 且所有题都已作答、选项下标完全相同的量表块名（按出现顺序）。

    有任何一题缺答时，该块不判为全同（无法确定）。
    """
    blocks = {}
    for c in columns:
        blocks.setdefault(block_name(c), []).append(c)
    found = []
    for name, members in blocks.items():
        if len(members) < min_items:
            continue
        answers = [values[c] for c in members]
        if all(a != "" for a in answers) and len(set(answers)) == 1:
            found.append(name)
    return found


# ---------- 单份问卷的检查 ----------

def check_instrument(subject, instrument, header, row, state_q, cfg):
    """检查一个被试的一份问卷，返回一行字典（键即 COLUMNS）。"""
    columns = instrument_columns(header, instrument)
    values = {c: (row.get(c) or "").strip() for c in columns}
    missing = [c for c in columns if values[c] == ""]
    notes = []

    if state_q is None:
        submitted, started, ended, answers = False, None, None, {}
        notes.append("state.json 中无该问卷记录")
    else:
        submitted = state_q.get("submitted") is True
        started = to_float(state_q.get("started_at"))
        ended = to_float(state_q.get("submitted_at"))
        answers = state_q.get("answers") or {}
    if not columns:
        notes.append("questionnaires.csv 中无该问卷的列")

    duration = None
    if started is not None and ended is not None:
        duration = ended - started
    elif state_q is not None:
        notes.append("时间戳缺失，无法计算用时")

    n_answers = len(answers) if isinstance(answers, dict) else 0
    sec_per_item = None
    if duration is not None:
        if n_answers > 0:
            sec_per_item = duration / n_answers
        else:
            notes.append("answers 为空，无法计算每题用时")
    too_fast = sec_per_item is not None and sec_per_item < cfg["MIN_SEC_PER_ITEM"]

    straight = straightline_blocks(columns, values, cfg["STRAIGHTLINE_MIN_ITEMS"])

    flag = (not submitted) or len(missing) > 0 or too_fast or len(straight) > 0
    return {
        "subject": subject,
        "instrument": instrument,
        "submitted": yn(submitted),
        "n_items": len(columns),
        "n_missing": len(missing),
        "missing_items": ";".join(missing),
        "duration_s": fmt(duration, 3),
        "sec_per_item": fmt(sec_per_item, 2),
        "too_fast": "" if sec_per_item is None else yn(too_fast),
        "straightline_blocks": ";".join(straight),
        "flag": yn(flag),
        "note": "；".join(notes),
    }


def missing_file_row(subject, reason):
    """被试文件不完整时的占位行：instrument=ALL，flag=yes，note 写明缺什么。"""
    row = {c: "" for c in COLUMNS}
    row.update({"subject": subject, "instrument": ALL_INSTRUMENTS, "flag": "yes", "note": reason})
    return row


# ---------- 单个被试 ----------

def check_subject(subject, subject_dir, cfg):
    """检查一个被试的全部问卷，返回若干行（每份问卷一行；文件不全则一行 ALL）。"""
    csv_path = subject_dir / "questionnaires.csv"
    state_path = subject_dir / "state.json"
    absent = []
    if not csv_path.is_file():
        absent.append("缺 questionnaires.csv")
    if not state_path.is_file():
        absent.append("缺 state.json")
    if absent:
        return [missing_file_row(subject, "；".join(absent))]

    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        return [missing_file_row(subject, f"state.json 无法读取：{error}")]

    header, rows = read_questionnaire_csv(csv_path)
    if len(rows) != 1:
        return [missing_file_row(subject, f"questionnaires.csv 应为 1 行数据，实际 {len(rows)} 行")]

    questionnaires = state.get("questionnaires") or {}
    return [check_instrument(subject, q, header, rows[0], questionnaires.get(q), cfg)
            for q in QUESTIONNAIRES]


# ---------- 合表 ----------

INSTRUMENT_ORDER = {ALL_INSTRUMENTS: 0, **{q: i + 1 for i, q in enumerate(QUESTIONNAIRES)}}


def merge_table(path, new_rows, chosen, root):
    """把本次处理的被试的行替换进 completeness.csv，其他被试的行保留。返回合并后的全部行。"""
    kept = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8-sig") as f:
            for old in csv.DictReader(f):
                if old.get("subject") not in chosen:
                    kept.append({c: old.get(c, "") for c in COLUMNS})
    rows = kept + new_rows
    rows.sort(key=lambda r: (r["subject"], INSTRUMENT_ORDER.get(r["instrument"], 99)))
    write_csv(path, COLUMNS, [[r[c] for c in COLUMNS] for r in rows], root)
    return rows


# ---------- 报告 ----------

def problem_text(row, min_sec):
    """一行 flag=yes 的问题说明（中文）。"""
    if row["instrument"] == ALL_INSTRUMENTS:
        return f"问卷文件缺失或不完整：{row['note']}"
    parts = []
    if row["submitted"] == "no":
        parts.append("未提交")
    if int(row["n_missing"]) > 0:
        parts.append(f"缺答 {row['n_missing']} 题（{row['missing_items'].replace(';', '、')}）")
    if row["too_fast"] == "yes":
        parts.append(f"作答过快：每题平均 {row['sec_per_item']} 秒，低于阈值 {min_sec} 秒")
    if row["straightline_blocks"]:
        parts.append(f"全选同一选项的量表块：{row['straightline_blocks'].replace(';', '、')}")
    text = "；".join(parts) or "（无具体原因）"
    if row["note"]:
        text += f"；备注：{row['note']}"
    return text


def duration_text(seconds_text):
    """'123.456' → '123.5 秒（2 分 3.5 秒）'；空串 → '—'。"""
    if seconds_text == "":
        return "—"
    seconds = float(seconds_text)
    minutes, rest = divmod(seconds, 60)
    return f"{seconds:.1f} 秒（{int(minutes)} 分 {rest:.1f} 秒）"


def build_report(rows, dataset, chosen, cfg):
    """生成中文报告：先列 flag=yes 的行及问题，再列每位被试每份问卷的用时。"""
    lines = []
    add = lines.append
    subjects = sorted({r["subject"] for r in rows})
    flagged = [r for r in rows if r["flag"] == "yes"]
    add("psycho 工具 01 问卷完整性检查报告")
    add(f"数据集：{dataset}；本次处理被试：{', '.join(chosen)}")
    add(f"生成时间：{datetime.now(TZ_BEIJING).isoformat(timespec='seconds')}（北京时间）")
    add(f"completeness.csv 共 {len(rows)} 行，涉及被试 {len(subjects)} 位：{', '.join(subjects)}")
    add(f"判定阈值：每题平均用时低于 {cfg['MIN_SEC_PER_ITEM']} 秒记为作答过快；"
        f"题数不少于 {cfg['STRAIGHTLINE_MIN_ITEMS']} 的量表块若全选同一选项记为全同。")
    add("flag=yes 表示：未提交、有缺答、作答过快、存在全同选项的量表块，或问卷文件缺失之一。")
    add("")

    add(f"[一] flag=yes 的行（共 {len(flagged)} 行）")
    if not flagged:
        add("  无。")
    for r in flagged:
        add(f"  {r['subject']}  {r['instrument']}")
        add(f"    问题：{problem_text(r, cfg['MIN_SEC_PER_ITEM'])}")
    add("")

    add("[二] 每位被试每份问卷的用时")
    if not rows:
        add("  （无）")
    for r in rows:
        if r["instrument"] == ALL_INSTRUMENTS:
            add(f"  {r['subject']}  ALL  无法给出用时：{r['note']}")
            continue
        submitted = "是" if r["submitted"] == "yes" else "否"
        per_item = r["sec_per_item"] + " 秒" if r["sec_per_item"] else "—"
        add(f"  {r['subject']}  {r['instrument']:<3}  提交：{submitted}  "
            f"用时：{duration_text(r['duration_s'])}  每题平均：{per_item}")
    return "\n".join(lines) + "\n"


# ---------- 入口 ----------

def check_settings(cfg):
    """检查设置区的常量是否合理，不合理就报错，不往下跑。"""
    if not isinstance(cfg["MIN_SEC_PER_ITEM"], (int, float)) or cfg["MIN_SEC_PER_ITEM"] <= 0:
        raise ValueError(f"MIN_SEC_PER_ITEM 必须为大于 0 的数：{cfg['MIN_SEC_PER_ITEM']}")
    if not isinstance(cfg["STRAIGHTLINE_MIN_ITEMS"], int) or cfg["STRAIGHTLINE_MIN_ITEMS"] < 2:
        raise ValueError(f"STRAIGHTLINE_MIN_ITEMS 必须为不小于 2 的整数：{cfg['STRAIGHTLINE_MIN_ITEMS']}")


def run(dataset, subjects, cfg):
    """对数据集中的被试做问卷完整性检查，写 completeness.csv 与 completeness_report.txt。返回合并后的全部行。"""
    check_settings(cfg)
    raw_psycho = layer_dir(dataset, "raw", "psycho")
    processed = layer_dir(dataset, "processed", "psycho")
    if not raw_psycho.is_dir():
        raise FileNotFoundError(f"找不到原始问卷文件夹：{raw_psycho}")
    chosen = select_subjects(raw_psycho, subjects)

    out_dir = check_inside(processed / PREVIEW_SUBDIR[0] / PREVIEW_SUBDIR[1], processed)
    print(f"数据集 {dataset}：共 {len(chosen)} 位被试")
    new_rows = []
    for subject in chosen:
        print(f"[开始] sub-{subject}")
        rows = check_subject(subject, raw_psycho / f"sub-{subject}", cfg)
        flagged = sum(r["flag"] == "yes" for r in rows)
        print(f"[完成] sub-{subject}：{len(rows)} 行，flag=yes {flagged} 行")
        new_rows += rows

    table_path = out_dir / TABLE_NAME
    all_rows = merge_table(table_path, new_rows, chosen, processed)
    report_path = write_text(out_dir / REPORT_NAME, build_report(all_rows, dataset, chosen, cfg), processed)
    print(f"       输出：{table_path}")
    print(f"       输出：{report_path}")
    return all_rows
