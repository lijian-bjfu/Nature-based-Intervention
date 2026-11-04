"""track 01：埋点完整性检查的全部处理函数。

只读 raw，不改任何数据，不计算任何指标。

输入（只读）：data/<数据集>/raw/track/sub-P###/ 下的记录文件夹
    记录文件夹名符合 global_settings.TRACK_SESSION_REGEX（sub-P###_mod-<模块>_run-###），
    模块含 Practice、Interactive、Passive。不进入下划线开头的文件夹（_excluded/ 等）。
    七张表（session、spacetime、tap、look、backstep、world_event、tech_glitch）用 track_io.read_table 读取，
    旧版数据多出或缺少的列由 track_io 处理。

输出：data/<数据集>/processed/track/preview/check/
    track_completeness.csv          每个记录一行
    track_completeness_subjects.csv 每位被试一行（被试层判定）
    track_completeness_report.txt   中文报告

判定规则：
    各模块要求的表直接读取 global_settings.TRACK_REQUIRED_TABLES（Practice、Passive 只要求 session，Interactive 要求全部）。
    实验条件（Interactive、Passive）时长 < MIN_INTERACTIVE_MIN 分钟记为过短。
    缺表、读取失败、时长缺失，或实验条件过短，flag=yes，note 写明原因。
被试层：实验条件记录 = Interactive 与 Passive 合计的合格记录数。
    0 份：flag=yes；1 份：正常；多于 1 份：flag=no，但在 note 与报告中提示需要处理。

安全：所有写入都先经过 check_inside()，目标不在 processed/track/ 之内就报错，不写任何文件。
"""
import re
from pathlib import Path

import pandas as pd

import global_settings as settings
from paths import layer_dir
from track_io import read_table

# 七张表（列顺序即输出顺序）
TABLES = settings.TRACK_TABLES
# 模块顺序，用于排序输出
MODULE_ORDER = {"Practice": 0, "Interactive": 1, "Passive": 2}
# 实验条件模块
EXPERIMENT_MODULES = ("Interactive", "Passive")
PRESENT, MISSING = "有", "缺"
FLAG_YES, FLAG_NO = "yes", "no"
PREVIEW_SUBDIR = ("preview", "check")
RECORD_TABLE = "track_completeness.csv"
SUBJECT_TABLE = "track_completeness_subjects.csv"
REPORT_NAME = "track_completeness_report.txt"
RECORD_COLUMNS = (["subject", "module", "run", "record"] + list(TABLES)
                  + [f"rows_{t}" for t in TABLES] + ["duration_min", "app_commit", "flag", "note"])
SUBJECT_COLUMNS = ["subject", "n_practice", "n_interactive", "n_interactive_ok",
                   "n_passive", "n_passive_ok", "flag", "note"]


# ---------- 路径与写入保护 ----------

def check_inside(path, root):
    """写入前检查：path 必须位于 root 之内，否则报错，不写任何文件。"""
    target = Path(path).resolve()
    base = Path(root).resolve()
    if base not in target.parents:
        raise RuntimeError(f"拒绝写入：{target} 不在允许的输出目录 {base} 之内")
    return target


# ---------- 被试与记录选择 ----------

def list_subjects(raw_track):
    """raw/track/ 下所有 sub-P### 文件夹的被试编号（如 P001）；下划线开头的文件夹不算。"""
    out = []
    for folder in sorted(raw_track.glob(settings.SUBJECT_DIR_GLOB)):
        match = re.fullmatch(settings.SUBJECT_DIR_REGEX, folder.name) if folder.is_dir() else None
        if match:
            out.append(f"P{match['subject']}")
    return out


def normalize_subject(text):
    """接受 'P001' 或 'sub-P001'，统一成 'P001'。"""
    text = str(text).strip()
    return text[4:] if text.startswith("sub-") else text


def select_subjects(raw_track, subjects):
    """subjects 为 '*'（全部）或编号列表；列表里有不存在的被试则报错。"""
    pool = list_subjects(raw_track)
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"raw/track 中没有这些被试：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"raw/track 中没有任何 sub-P### 文件夹：{raw_track}")
    return chosen


def list_records(subject, subject_dir):
    """被试文件夹下的记录文件夹，返回 [(文件夹, 模块, 运行编号)]。下划线开头的文件夹（_excluded/ 等）跳过。"""
    out = []
    for folder in sorted(subject_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        match = re.fullmatch(settings.TRACK_SESSION_REGEX, folder.name)
        if not match:
            continue
        if f"P{match['subject']}" != subject:
            raise ValueError(f"{folder}: 记录名中的被试编号与所在被试文件夹 {subject_dir.name} 不一致")
        out.append((folder, match["module"], match["run"]))
    return sorted(out, key=lambda r: (MODULE_ORDER[r[1]], r[2]))


# ---------- 读取与单条记录判定 ----------

def read_record(folder):
    """读取一个记录文件夹的七张表。返回 (表名 -> DataFrame 或 None, 表名 -> 错误信息)。读取失败不中断，只记录。"""
    frames, errors = {}, {}
    for name in TABLES:
        try:
            frames[name] = read_table(folder, name, formatted=True)
        except Exception as error:   # 列名或取值不符合规范：记下原因，继续检查其他表
            frames[name] = None
            errors[name] = str(error)
    return frames, errors


def duration_minutes(session):
    """session 表的 t_device_end − t_device_start，单位分钟；取不到时返回 None。"""
    if session is None or session.empty:
        return None
    start = session[settings.column("session", "t_device_start")].iloc[0]
    end = session[settings.column("session", "t_device_end")].iloc[0]
    if pd.isna(start) or pd.isna(end):
        return None
    return (float(end) - float(start)) / 60


def app_commit_of(session):
    """产生这份数据的 APP 代码版本；没有则返回空字符串（加入 app_commit 之前录制的数据）。"""
    if session is None or session.empty:
        return ""
    value = session[settings.column("session", "app_commit")].dropna()
    return str(value.iloc[0]) if len(value) else ""


def check_record(subject, folder, module, run, cfg):
    """判定一个记录文件夹，返回一行（字典）。"""
    frames, errors = read_record(folder)
    row = {"subject": subject, "module": module, "run": run, "record": folder.name}
    missing, notes = [], []

    for name in TABLES:
        exists = (folder / settings.TRACK_FILES[name]).is_file()
        row[name] = PRESENT if exists else MISSING
        row[f"rows_{name}"] = "" if frames[name] is None or not exists else len(frames[name])
        if not exists:
            missing.append(name)

    session = frames["session"]
    minutes = duration_minutes(session)
    row["duration_min"] = "" if minutes is None else f"{minutes:.1f}"
    row["app_commit"] = app_commit_of(session)

    required = settings.TRACK_REQUIRED_TABLES[module]
    missing_required = [n for n in required if n in missing]
    if missing_required:
        notes.append(f"缺表：{'、'.join(missing_required)}")
    for name, message in errors.items():
        notes.append(f"读取失败 {name}：{message}")

    too_short = False
    if module in EXPERIMENT_MODULES and session is not None:
        if minutes is None:
            notes.append("session 表缺少时长（t_device_start 或 t_device_end 为空）")
        elif minutes < cfg["MIN_INTERACTIVE_MIN"]:
            too_short = True
            notes.append(f"实验条件时长 {minutes:.1f} 分钟，短于 {cfg['MIN_INTERACTIVE_MIN']} 分钟（过短）")

    flagged = bool(missing_required or errors or too_short
                   or (module in EXPERIMENT_MODULES and minutes is None and session is not None))
    row["flag"] = FLAG_YES if flagged else FLAG_NO
    row["note"] = "；".join(notes)
    return row


def record_ok(row):
    """记录是否合格：未被标记。"""
    return row["flag"] == FLAG_NO


# ---------- 被试层判定 ----------

def check_subject(subject, records):
    """被试层：实验条件记录 = Interactive 与 Passive 合计的合格记录数。"""
    def count(*modules):
        return sum(r["module"] in modules for r in records)

    def ok(*modules):
        return sum(r["module"] in modules and record_ok(r) for r in records)

    qualified = ok(*EXPERIMENT_MODULES)
    notes = []
    if qualified == 0:
        flag = FLAG_YES
        notes.append("没有合格的实验条件记录")
    else:
        flag = FLAG_NO
        if qualified > 1:
            notes.append(f"有 {qualified} 份实验条件记录，需把多余的移入 _excluded/ 或在 parameters.py 的 runs 里指定")
    return {
        "subject": subject,
        "n_practice": count("Practice"),
        "n_interactive": count("Interactive"),
        "n_interactive_ok": ok("Interactive"),
        "n_passive": count("Passive"),
        "n_passive_ok": ok("Passive"),
        "flag": flag,
        "note": "；".join(notes),
    }


# ---------- 主流程与输出 ----------

def build_report(records, subjects_rows, dataset, chosen, cfg):
    """中文报告：各模块记录数、被标记记录、被试层判定。"""
    lines = [f"埋点完整性检查报告", f"数据集：{dataset}",
             f"被试数：{len(chosen)}；记录数：{len(records)}",
             f"实验条件过短阈值：{cfg['MIN_INTERACTIVE_MIN']} 分钟", ""]
    lines.append("【记录层】被标记记录（flag=yes）：")
    flagged = [r for r in records if r["flag"] == FLAG_YES]
    if not flagged:
        lines.append("  无")
    for r in flagged:
        lines.append(f"  {r['subject']} {r['module']} {r['run']}  {r['record']}：{r['note']}")
    lines.append("")
    lines.append("【被试层】被标记被试（flag=yes）：")
    bad_subjects = [s for s in subjects_rows if s["flag"] == FLAG_YES]
    if not bad_subjects:
        lines.append("  无")
    for s in bad_subjects:
        lines.append(f"  {s['subject']}：{s['note']}")
    lines.append("")
    lines.append("【提示】（非错误，需人工确认）")
    hints = [s for s in subjects_rows if s["note"] and s["flag"] == FLAG_NO]
    if not hints:
        lines.append("  无")
    for s in hints:
        lines.append(f"  {s['subject']}：{s['note']}")
    return "\n".join(lines) + "\n"


def run(dataset, subjects, cfg):
    """对数据集中的被试做埋点完整性检查，写两张表与一份报告。返回 (记录行, 被试行)。"""
    if cfg["MIN_INTERACTIVE_MIN"] <= 0:
        raise ValueError("MIN_INTERACTIVE_MIN 应为正数")
    raw_track = layer_dir(dataset, "raw", "track")
    processed = layer_dir(dataset, "processed", "track")
    if not raw_track.is_dir():
        raise FileNotFoundError(f"找不到原始埋点文件夹：{raw_track}")
    chosen = select_subjects(raw_track, subjects)

    out_dir = check_inside(processed / PREVIEW_SUBDIR[0] / PREVIEW_SUBDIR[1], processed)
    print(f"数据集 {dataset}：共 {len(chosen)} 位被试")
    records, subjects_rows = [], []
    for subject in chosen:
        print(f"[开始] sub-{subject}")
        subject_dir = raw_track / f"sub-{subject}"
        rows = [check_record(subject, folder, module, run, cfg)
                for folder, module, run in list_records(subject, subject_dir)]
        records += rows
        subjects_rows.append(check_subject(subject, rows))
        print(f"[完成] sub-{subject}：{len(rows)} 条记录")

    record_df = pd.DataFrame(records, columns=RECORD_COLUMNS)
    subject_df = pd.DataFrame(subjects_rows, columns=SUBJECT_COLUMNS)
    record_path = check_inside(out_dir / RECORD_TABLE, processed)
    subject_path = check_inside(out_dir / SUBJECT_TABLE, processed)
    report_path = check_inside(out_dir / REPORT_NAME, processed)
    out_dir.mkdir(parents=True, exist_ok=True)
    record_df.to_csv(record_path, index=False, encoding="utf-8-sig")
    subject_df.to_csv(subject_path, index=False, encoding="utf-8-sig")
    report_path.write_text(build_report(records, subjects_rows, dataset, chosen, cfg), encoding="utf-8")
    print(f"       输出：{record_path}")
    print(f"       输出：{subject_path}")
    print(f"       输出：{report_path}")
    return records, subjects_rows
