"""psycho 工具 02 的全部处理函数：各被试问卷合并为长宽表。

输入（只读）：data/<数据集>/raw/psycho/sub-P###/questionnaires.csv（正好 1 行）、
    questionnaires_codebook.csv（只看 raw/psycho/ 下的 sub-P### 文件夹；
    下划线开头的文件夹跳过）
输出：data/<数据集>/processed/psycho/
    items_wide.csv：每位被试一行，subject 列 + 题目列（顺序同 codebook）
    items_long.csv：每位被试 × 每道题一行
    items_codebook.csv：codebook 原样拷贝一份
    items_report.txt：中文报告

问卷 = 列名第一个下划线前的部分（A、T0、T1、T2、T3）。
量表块 = 列名去掉末尾 "_数字" 后的部分，如 T1_stai6_3 → T1_stai6。
量表 = 量表块去掉问卷前缀，如 T1_stai6 → stai6。
题号 = 列名末尾的数字，没有就留空。

检查：每位被试的 questionnaires.csv 必须正好 1 行数据，且 participant_id 必须等于
    所在文件夹的编号；各被试的 codebook（表头、列、每列内容）必须完全一致，不一致
    说明问卷版本不同，报错退出并列出不一致的被试和列名，不写任何文件。

安全：所有写入都先经过 check_inside()，目标不在 processed/psycho/ 之内就报错，不写
    任何文件。subjects 只决定读哪些被试；输出总是用这些被试重新生成完整的四个文件
    （覆盖旧文件），不与旧文件合并。读取不改 raw/。
"""
import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paths import layer_dir

# 四个输出文件名
WIDE_NAME = "items_wide.csv"
LONG_NAME = "items_long.csv"
CODEBOOK_NAME = "items_codebook.csv"
REPORT_NAME = "items_report.txt"
LONG_COLUMNS = ["subject", "instrument", "block", "scale", "item_no", "column", "value"]
# 北京时间 UTC+8（固定偏移，不依赖时区数据库），与工具 01 一致
TZ_BEIJING = timezone(timedelta(hours=8))
# 列名末尾 "_数字" 的正则：用于算量表块名、题号
TRAILING_NUMBER = re.compile(r"_(\d+)$")


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
    """写 items_report.txt。写前先检查路径。"""
    target = check_inside(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# ---------- 被试选择 ----------

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


# ---------- 列名拆解 ----------

def instrument_of(column):
    """问卷代号：列名第一个下划线前的部分。"""
    return column.split("_", 1)[0]


def block_name(column):
    """量表块名：去掉列名末尾的 '_数字'。没有这种后缀的列，块名就是列名本身。"""
    return TRAILING_NUMBER.sub("", column)


def item_no(column):
    """题号：列名末尾的数字；没有就返回空串。"""
    m = TRAILING_NUMBER.search(column)
    return m.group(1) if m else ""


def scale_of(block, instrument):
    """量表名：量表块去掉问卷前缀（'<问卷>_'）；没有这个前缀就原样返回。"""
    prefix = instrument + "_"
    return block[len(prefix):] if block.startswith(prefix) else block


# ---------- 读取与校验：单个被试 ----------

def read_subject_csv(path, subject):
    """读 questionnaires.csv，校验正好 1 行、第一列是 participant_id 且等于 subject。

    返回 (表头, 该行字典)。
    """
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if len(rows) != 1:
        raise ValueError(f"{path}：questionnaires.csv 应为 1 行数据，实际 {len(rows)} 行")
    if not header or header[0] != "participant_id":
        raise ValueError(f"{path}：第一列应为 participant_id，实际是 {header[0] if header else '（无列）'}")
    row = rows[0]
    pid = (row.get("participant_id") or "").strip()
    if pid != subject:
        raise ValueError(f"{path}：participant_id 应等于所在文件夹编号 {subject}，实际是 {pid!r}")
    return header, row


def read_codebook(path):
    """读 questionnaires_codebook.csv，返回 (表头, 行字典列表)。"""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    return header, rows


# ---------- 校验：各被试 codebook 一致 ----------

def codebook_map(rows):
    """{column: (instrument, item_text, value_meaning)}，用于逐列比较内容。"""
    return {r.get("column"): (r.get("instrument", ""), r.get("item_text", ""), r.get("value_meaning", ""))
            for r in rows}


def validate_codebooks(codebooks):
    """各被试 codebook 必须完全一致；不一致就报错，列出不一致的被试和列名。

    codebooks：{subject: (表头, 行字典列表)}。
    返回参照被试（取 codebooks 中第一个）的 (表头, 行字典列表, column 顺序列表)。
    """
    subjects = list(codebooks)
    ref_subject = subjects[0]
    ref_header, ref_rows = codebooks[ref_subject]
    ref_columns = [r.get("column") for r in ref_rows]
    ref_map = codebook_map(ref_rows)

    problems = []
    for subject in subjects[1:]:
        header, rows = codebooks[subject]
        if header != ref_header:
            problems.append(f"{subject}：表头不同（{header} vs {ref_subject} 的 {ref_header}）")
            continue
        columns = [r.get("column") for r in rows]
        if columns != ref_columns:
            missing = [c for c in ref_columns if c not in columns]
            extra = [c for c in columns if c not in ref_columns]
            detail = []
            if missing:
                detail.append(f"缺少列 {missing}")
            if extra:
                detail.append(f"多出列 {extra}")
            if not detail:
                detail.append("列顺序与参照被试不同")
            problems.append(f"{subject}：{'；'.join(detail)}")
            continue
        this_map = codebook_map(rows)
        diff_columns = [c for c in ref_columns if this_map.get(c) != ref_map.get(c)]
        if diff_columns:
            problems.append(f"{subject}：以下列的内容与参照被试（{ref_subject}）不一致：{', '.join(diff_columns)}")

    if problems:
        raise ValueError(
            "各被试 questionnaires_codebook.csv 不一致（可能是问卷版本不同，需要人工决定）：\n"
            + "\n".join(f"  {p}" for p in problems)
        )
    return ref_header, ref_rows, ref_columns


# ---------- 宽表、长表 ----------

def build_wide_row(subject, row, columns):
    """一位被试的宽表行：subject + 各题目列原值（原样保留，缺省为空）。"""
    out = {"subject": subject}
    for col in columns:
        out[col] = row.get(col) or ""
    return out


def build_long_rows(subject, row, columns):
    """一位被试的长表行：每道题一行。"""
    rows = []
    for col in columns:
        instrument = instrument_of(col)
        block = block_name(col)
        rows.append({
            "subject": subject,
            "instrument": instrument,
            "block": block,
            "scale": scale_of(block, instrument),
            "item_no": item_no(col),
            "column": col,
            "value": row.get(col) or "",
        })
    return rows


# ---------- 报告 ----------

def instrument_block_counts(columns):
    """按出现顺序，问卷 → 量表块（含量表名、题数）的分组统计。"""
    order = []
    by_instrument = {}
    block_info = {}
    for col in columns:
        instrument = instrument_of(col)
        block = block_name(col)
        if instrument not in by_instrument:
            by_instrument[instrument] = []
            order.append(instrument)
        if block not in block_info:
            block_info[block] = {"scale": scale_of(block, instrument), "count": 0}
            by_instrument[instrument].append(block)
        block_info[block]["count"] += 1
    return order, by_instrument, block_info


def build_report(dataset, chosen, columns, wide_rows, long_rows):
    """生成中文报告：处理的被试、表格规模、每份问卷/每个量表块的题数。"""
    lines = []
    add = lines.append
    add("psycho 工具 02 问卷合并报告")
    add(f"数据集：{dataset}；本次处理被试：{', '.join(chosen)}（共 {len(chosen)} 位）")
    add(f"生成时间：{datetime.now(TZ_BEIJING).isoformat(timespec='seconds')}（北京时间）")
    add("")

    add("[一] 表格规模")
    add(f"  items_wide.csv：{len(wide_rows)} 行 × {1 + len(columns)} 列（subject + {len(columns)} 个题目列）")
    add(f"  items_long.csv：{len(long_rows)} 行（{len(chosen)} 位被试 × {len(columns)} 道题）")
    add("")

    add("[二] 各问卷、各量表块题数")
    order, by_instrument, block_info = instrument_block_counts(columns)
    for instrument in order:
        blocks = by_instrument[instrument]
        total = sum(block_info[b]["count"] for b in blocks)
        add(f"  {instrument}（共 {total} 题）")
        for block in blocks:
            info = block_info[block]
            add(f"    {info['scale']}：{info['count']} 题")
    return "\n".join(lines) + "\n"


# ---------- 入口 ----------

def run(dataset, subjects):
    """合并数据集中被试的问卷为长宽表，写四个输出文件。返回 (wide_rows, long_rows, report_text)。"""
    raw_psycho = layer_dir(dataset, "raw", "psycho")
    processed = layer_dir(dataset, "processed", "psycho")
    if not raw_psycho.is_dir():
        raise FileNotFoundError(f"找不到原始问卷文件夹：{raw_psycho}")
    chosen = select_subjects(raw_psycho, subjects)
    print(f"数据集 {dataset}：共 {len(chosen)} 位被试")

    subject_rows = {}
    codebooks = {}
    for subject in chosen:
        print(f"[开始] sub-{subject}")
        subject_dir = raw_psycho / f"sub-{subject}"
        csv_path = subject_dir / "questionnaires.csv"
        codebook_path = subject_dir / "questionnaires_codebook.csv"
        if not csv_path.is_file():
            raise FileNotFoundError(f"缺少文件：{csv_path}")
        if not codebook_path.is_file():
            raise FileNotFoundError(f"缺少文件：{codebook_path}")
        subject_rows[subject] = read_subject_csv(csv_path, subject)
        codebooks[subject] = read_codebook(codebook_path)
        print(f"[完成] sub-{subject}")

    ref_header, ref_rows, columns = validate_codebooks(codebooks)

    wide_rows = [build_wide_row(subject, subject_rows[subject][1], columns) for subject in chosen]
    long_rows = []
    for subject in chosen:
        long_rows += build_long_rows(subject, subject_rows[subject][1], columns)

    wide_header = ["subject"] + columns
    wide_path = write_csv(processed / WIDE_NAME, wide_header,
                           [[r[c] for c in wide_header] for r in wide_rows], processed)
    long_path = write_csv(processed / LONG_NAME, LONG_COLUMNS,
                           [[r[c] for c in LONG_COLUMNS] for r in long_rows], processed)
    codebook_out_path = write_csv(processed / CODEBOOK_NAME, ref_header,
                                   [[r.get(c, "") for c in ref_header] for r in ref_rows], processed)

    report_text = build_report(dataset, chosen, columns, wide_rows, long_rows)
    report_path = write_text(processed / REPORT_NAME, report_text, processed)

    print(f"       输出：{wide_path}")
    print(f"       输出：{long_path}")
    print(f"       输出：{codebook_out_path}")
    print(f"       输出：{report_path}")
    return wide_rows, long_rows, report_text
