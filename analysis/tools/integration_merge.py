"""integration 工具 03 的全部处理逻辑：把问卷得分与生理窗口指标合成宽表、长表和数据字典。只合并，不计算。

输入（只读）：data/<数据集>/ 下
    raw/session_notes/sub-P###/log.csv：被试名单（文件夹名，下划线开头跳过）与组别（group_code）
    processed/psycho/scores_wide.csv、scores_long.csv
    final/physio/window_metrics_long.csv（只用长表；宽表由本工具从长表展开）
输出：data/<数据集>/final/integration/（每次整表重写）
    wide.csv             一人一行：subject、group、问卷得分（原顺序）、生理 <窗口>_<列名>
    long.csv             每人五阶段：配对T1–T3问卷、生理指标和个人字段；对应关系读global_settings
    psycho_long.csv      每人 × T1–T3 一行：subject、group、time、time_code、scores_long 其余列、协变量
    physio_long.csv      每人 × 五个窗口一行：subject、group、window、window_code、window_metrics_long 其余列、协变量
    data_dictionary.csv  四张表出现的每一列一行（只引用登记，不自行编写含义）
    merge_report.txt     中文报告
规则：被试号写 P###；流程单名单里有、某类数据没有的被试，该类列留空，不删人；组别取 log.csv 的 group_code；
    所有数值照抄上游文本，不重新格式化、不重新计算。
安全：写入前检查目标路径在 final/integration/ 之内；不读写 raw 以外的其他位置，不删除任何文件。
"""
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paths import layer_dir

PROJECT = Path(__file__).resolve().parents[2]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
from global_settings import (INTEGRATION_AUX_FILES, INTEGRATION_COVARIATES, INTEGRATION_PHASE_TIMEPOINTS,
                             INTEGRATION_TABLES, METRICS, PHYSIO_PHASES, PSYCHO_TIMEPOINTS,
                             TRANSFORM_METHODS, VALUE_LABELS, validate)
from psycho_score import SCALE_NAMES, SCALE_TEMPLATE, TIMES, load_schema

WIDE_NAME = INTEGRATION_TABLES["wide"]["filename"]
LONG_NAME = INTEGRATION_TABLES["long"]["filename"]
PSYCHO_LONG_NAME = INTEGRATION_TABLES["psycho_long"]["filename"]
PHYSIO_LONG_NAME = INTEGRATION_TABLES["physio_long"]["filename"]
DICT_NAME = INTEGRATION_AUX_FILES["dictionary"]
REPORT_NAME = INTEGRATION_AUX_FILES["report"]
TABLE_ORDER = tuple(t["filename"] for t in INTEGRATION_TABLES.values())
TZ_BEIJING = timezone(timedelta(hours=8))

# 每人一个值的协变量（并入两张长表）；另加 scores_wide 中以 T0_/A_ 开头、以 _c/_z/_ln 结尾的转换列
COVARIATES = INTEGRATION_COVARIATES
# 统计量后缀 → 中文
STAT_NAMES = {"sum": "总分", "mean": "均分", "x20": "×20/6 换算分", "level": "分类"}
# physio_metrics.py 文件头的说明（只抄文件里有的）；其余质量列没有说明，登记为 registered=0
QUALITY_DOC = {
    "window_valid": "窗口是否可确定（window_valid=0：缺失、重复、顺序冲突，此时不计算）",
    "note": "提示文字（窗口时长偏离标准时长等偏差只抄进 note 作提示）",
}
QUALITY_COLUMNS = ("hr_coverage", "hrv_coverage", "hr_ok", "hrv_ok")
SOURCE_ORDER = {"session_notes": 0, "psycho": 1, "physio": 2, "integration": 3}


# ---------- 读写 ----------

def check_inside(path, root):
    """写入前检查：path 必须位于 root 之内，否则报错，不写任何文件。"""
    target = Path(path).resolve()
    base = Path(root).resolve()
    if base not in target.parents:
        raise RuntimeError(f"拒绝写入：{target} 不在允许的输出目录 {base} 之内")
    return target


def write_csv(path, header, rows, root):
    target = check_inside(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return target


def write_text(path, text, root):
    target = check_inside(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def read_table(path):
    """返回 (表头, 行字典列表)；值保持文本原样。"""
    if not path.is_file():
        raise FileNotFoundError(f"找不到 {path}；请先运行上游工具")
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def norm_subject(text):
    text = str(text).strip()
    return (text[4:] if text.lower().startswith("sub-") else text).upper()


def read_roster(raw_notes):
    """流程单名单与组别：{被试: (group 文本或 "", 说明)}，按文件夹名排序。"""
    if not raw_notes.is_dir():
        raise FileNotFoundError(f"找不到 {raw_notes}")
    roster = {}
    for folder in sorted(raw_notes.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_") or not folder.name.startswith("sub-"):
            continue
        subject = norm_subject(folder.name)
        log = folder / "log.csv"
        if not log.is_file():
            roster[subject] = ("", "缺少 log.csv")
            continue
        with log.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 1:
            roster[subject] = ("", f"log.csv 有 {len(rows)} 行数据（应为 1 行）")
            continue
        text = (rows[0].get("group_code") or "").strip()
        try:
            code = int(float(text))
        except ValueError:
            roster[subject] = ("", f"group_code 不是整数：{text!r}")
            continue
        if code not in VALUE_LABELS["group"]:
            roster[subject] = ("", f"group_code {code} 不在 VALUE_LABELS['group'] 中")
            continue
        roster[subject] = (str(code), "")
    if not roster:
        raise ValueError(f"{raw_notes} 下没有 sub-P### 文件夹")
    return roster


def index_rows(rows, key_fields, name):
    """按 key_fields 建索引；键重复就报错。被试号统一为 P###。"""
    index = {}
    for row in rows:
        row["subject"] = norm_subject(row["subject"])
        key = tuple(row[k] for k in key_fields)
        if key in index:
            raise ValueError(f"{name} 中 {key} 出现多行")
        index[key] = row
    return index


# ---------- 数据字典 ----------

def coding_text(name, prefixes):
    """列名（或去掉时间/窗口前缀后的名字）在 VALUE_LABELS 中时写成 '0=…; 1=…'。"""
    names = [name] + [name[len(p) + 1:] for p in prefixes if name.startswith(p + "_")]
    for candidate in names:
        if candidate in VALUE_LABELS:
            return "; ".join(f"{k}={v}" for k, v in VALUE_LABELS[candidate].items())
    return ""


def split_transform(name):
    for info in TRANSFORM_METHODS.values():
        if name.endswith(info["suffix"]):
            return name[:-len(info["suffix"])], info
    return name, None


def psycho_entry(name, schema):
    """问卷列 → (label_zh, unit_or_range)；拼不出来返回 None。"""
    base, transform = split_transform(name)
    metrics = schema.PSYCHO_METRICS
    found = None
    for scale, template in SCALE_TEMPLATE.items():
        candidates = []
        if "{T}" in template:
            candidates += [(template.replace("{T}", t), t) for t in TIMES]
            candidates.append((template.replace("{T}_", ""), None))   # 长表中去掉了时点前缀
        else:
            candidates.append((template, template.split("_")[0]))
        for stem, time in candidates:
            if base == stem:
                found = (scale, time, "")
            elif base.startswith(stem + "_") and base[len(stem) + 1:] in STAT_NAMES:
                found = (scale, time, base[len(stem) + 1:])
            if found:
                break
        if found:
            break
    if found is None and base == "A_screen_hard":
        found = ("a2_screening", "A", "")
    if found is None and not base.startswith(tuple(t + "_" for t in PSYCHO_TIMEPOINTS)):
        # 合并长表去前缀的T3单次体验指标，仍复用原指标含义。
        return psycho_entry("T3_" + name, schema)
    if found is None:
        return None
    scale, time, stat = found
    when = PSYCHO_TIMEPOINTS[time] if time else "各时点（T1–T3，见 time 列）"
    scale_name = SCALE_NAMES.get(scale) or metrics[scale]["name"]
    label = f"{when}：{scale_name}" + (f" {STAT_NAMES[stat]}" if stat else "")
    if transform:
        label += f"（{transform['name']}）"
        return label, transform["definition"]
    return label, metrics[scale]["output"]


def physio_entry(name):
    """生理列（宽表带窗口前缀、长表不带）→ (label_zh, unit_or_range)；没有登记返回 ("", "")。"""
    window = None
    metric = name
    for phase in sorted(PHYSIO_PHASES, key=len, reverse=True):
        if name.startswith(phase + "_"):
            window, metric = phase, name[len(phase) + 1:]
            break
    prefix = f"{PHYSIO_PHASES[window]}：" if window else ""
    metrics = METRICS["physio"]
    if metric in QUALITY_COLUMNS:
        return f"{prefix}{metrics['window_quality']['name']} {metric}", ""
    if metric in metrics and metric != "window_quality":
        return f"{prefix}{metrics[metric]['name']}", metrics[metric]["output"]
    if metric in QUALITY_DOC:
        return f"{prefix}{QUALITY_DOC[metric]}", ""
    return "", ""


def build_dictionary(tables, provenance, schema):
    """tables: {表名: 表头}；provenance: {列: 来源}。返回字典行列表。"""
    order, where = [], {}
    for table in TABLE_ORDER:
        for col in tables[table]:
            if col not in where:
                order.append(col)
                where[col] = []
            where[col].append(table)
    prefixes = list(PSYCHO_TIMEPOINTS) + list(PHYSIO_PHASES)
    integration = {
        "subject": "被试编号（P###）",
        "group": "组别（log.csv 的 group_code）",
        "time": "配对问卷时点（T1、T2、T3；合并长表训练及干预后静息无对应问卷时留空）",
        "time_code": "测量时点编码",
        "window": "生理窗口（PHYSIO_PHASES 的英文标识）",
        "window_code": "生理窗口编码（按 PHYSIO_PHASES 顺序）",
    }
    rows = []
    for col in order:
        source = provenance[col]
        label, unit = "", ""
        if col in integration:
            label = integration[col]
            if col == "time":
                unit = "; ".join(TIMES)
            elif col == "window":
                unit = "; ".join(PHYSIO_PHASES)
        elif source == "psycho":
            entry = psycho_entry(col, schema)
            if entry:
                label, unit = entry
        elif source == "physio":
            label, unit = physio_entry(col)
        rows.append([col, ";".join(where[col]), source, label, unit, coding_text(col, prefixes), 1 if label else 0])
    return rows


def build_combined_long(subjects, roster, wide, win, score_cols, metric_cols, time_codes, window_codes):
    """按阶段展开时点列；仅规范指定前缀的个人列重复进长表；只复制文本。"""
    time_fields = {t: {} for t in TIMES}
    point_cols, person_cols = [], []
    for col in score_cols:
        matched = next((t for t in TIMES if col.startswith(t + "_")), None)
        if matched is None:
            if col.startswith(INTEGRATION_TABLES["long"]["person_column_prefixes"]):
                person_cols.append(col)
        else:
            field = col[len(matched) + 1:]
            time_fields[matched][field] = col
            if field not in point_cols:
                point_cols.append(field)
    header = list(INTEGRATION_TABLES["long"]["id_columns"]) + point_cols + person_cols + metric_cols
    if len(header) != len(set(header)):
        raise ValueError("合并长表问卷、生理或标识字段重名，请核对字段规范")
    rows = []
    for subject in subjects:
        scores = wide.get(subject, {})
        for phase in PHYSIO_PHASES:
            time = INTEGRATION_PHASE_TIMEPOINTS[phase]
            ids = {"subject": subject, "group": roster[subject][0], "window": phase,
                   "window_code": window_codes[phase], "time": time or "",
                   "time_code": time_codes[time] if time else ""}
            fields = time_fields[time] if time else {}
            measures = [scores.get(fields[c], "") if c in fields else "" for c in point_cols]
            rows.append([ids[c] for c in INTEGRATION_TABLES["long"]["id_columns"]] + measures
                        + [scores.get(c, "") for c in person_cols]
                        + [win.get((subject, phase), {}).get(c, "") for c in metric_cols])
    return header, rows, point_cols, person_cols


def archive_legacy_wide(out_dir):
    """旧宽表改名后留档，不让merged_wide.csv继续冒充当前输出，不删除文件。"""
    legacy = check_inside(out_dir / "merged_wide.csv", out_dir)
    if not legacy.is_file():
        return
    stamp = datetime.now(TZ_BEIJING).strftime("%Y%m%d-%H%M%S")
    archive = check_inside(out_dir / "_to_delete" / f"merged_wide_{stamp}.csv", out_dir)
    n = 2
    while archive.exists():
        archive = archive.with_name(f"merged_wide_{stamp}_{n}.csv")
        n += 1
    archive.parent.mkdir(parents=True, exist_ok=True)
    legacy.rename(archive)
    print(f"旧宽表已留档：{archive}")


# ---------- 主流程 ----------

def run(dataset):
    validate()
    base = layer_dir(dataset, "raw") / "session_notes"
    scores_wide_path = layer_dir(dataset, "processed", "psycho") / "scores_wide.csv"
    scores_long_path = layer_dir(dataset, "processed", "psycho") / "scores_long.csv"
    window_path = layer_dir(dataset, "final", "physio") / "window_metrics_long.csv"
    out_dir = layer_dir(dataset, "final") / "integration"
    started = datetime.now(TZ_BEIJING)

    roster = read_roster(base)
    subjects = list(roster)
    wide_cols, wide_list = read_table(scores_wide_path)
    long_cols, long_list = read_table(scores_long_path)
    win_cols, win_list = read_table(window_path)
    for need, cols, name in (("subject", wide_cols, "scores_wide.csv"), ("group", wide_cols, "scores_wide.csv"),
                             ("subject", long_cols, "scores_long.csv"), ("time", long_cols, "scores_long.csv"),
                             ("subject", win_cols, "window_metrics_long.csv"), ("window", win_cols, "window_metrics_long.csv")):
        if need not in cols:
            raise ValueError(f"{name} 缺少 {need} 列")
    unknown = {r["window"] for r in win_list} - set(PHYSIO_PHASES)
    if unknown:
        raise ValueError(f"window_metrics_long.csv 含未登记的窗口：{sorted(unknown)}")
    wide = {k[0]: v for k, v in index_rows(wide_list, ("subject",), "scores_wide.csv").items()}
    long = index_rows(long_list, ("subject", "time"), "scores_long.csv")
    win = index_rows(win_list, ("subject", "window"), "window_metrics_long.csv")
    time_codes = {t: i for i, t in enumerate(TIMES)}
    if list(VALUE_LABELS["time_code"]) != list(time_codes.values()):
        raise ValueError("VALUE_LABELS['time_code'] 与 T1–T3 的编号不一致")
    window_codes = {w: i for i, w in enumerate(PHYSIO_PHASES)}
    if list(VALUE_LABELS["window_code"]) != list(window_codes.values()):
        raise ValueError("VALUE_LABELS['window_code'] 与 PHYSIO_PHASES 的编号不一致")

    score_cols = [c for c in wide_cols if c not in ("subject", "group")]
    metric_cols = [c for c in win_cols if c not in ("subject", "window")]
    psycho_value_cols = [c for c in long_cols if c not in ("subject", "group", "time")]
    for col in COVARIATES:
        if col not in wide_cols:
            raise ValueError(f"scores_wide.csv 缺少协变量列 {col}")
    covariates = list(COVARIATES)
    for col in wide_cols:
        if col.startswith(("T0_", "A_")) and col.endswith(tuple(m["suffix"] for m in TRANSFORM_METHODS.values())):
            if col not in covariates:
                covariates.append(col)
    long_extra = [c for c in covariates if c not in psycho_value_cols]
    physio_extra = [c for c in covariates if c not in metric_cols]
    phases = list(PHYSIO_PHASES)

    def pull(row, cols):
        return [row.get(c, "") if row else "" for c in cols]

    # a) 宽表
    wide_header = list(INTEGRATION_TABLES["wide"]["id_columns"]) + score_cols + [f"{p}_{c}" for p in phases for c in metric_cols]
    wide_rows = []
    for s in subjects:
        row = pull(wide.get(s), score_cols)
        for p in phases:
            row += pull(win.get((s, p)), metric_cols)
        wide_rows.append([s, roster[s][0]] + row)
    # b) 问卷长表
    psycho_header = list(INTEGRATION_TABLES["psycho_long"]["id_columns"]) + psycho_value_cols + long_extra
    psycho_rows = []
    for s in subjects:
        for t in TIMES:
            psycho_rows.append([s, roster[s][0], t, time_codes[t]] + pull(long.get((s, t)), psycho_value_cols)
                               + pull(wide.get(s), long_extra))
    # c) 生理长表
    physio_header = list(INTEGRATION_TABLES["physio_long"]["id_columns"]) + metric_cols + physio_extra
    physio_rows = []
    for s in subjects:
        for p in phases:
            physio_rows.append([s, roster[s][0], p, window_codes[p]] + pull(win.get((s, p)), metric_cols)
                               + pull(wide.get(s), physio_extra))

    combined_header, combined_rows, point_cols, person_cols = build_combined_long(
        subjects, roster, wide, win, score_cols, metric_cols, time_codes, window_codes)

    # d) 数据字典
    provenance = {"subject": "session_notes", "group": "session_notes",
                  "time": "integration", "time_code": "integration",
                  "window": "integration", "window_code": "integration"}
    for c in score_cols + psycho_value_cols + covariates + point_cols + person_cols:
        provenance.setdefault(c, "psycho")
    for c in metric_cols:
        provenance.setdefault(c, "physio")
    for p in phases:
        for c in metric_cols:
            provenance[f"{p}_{c}"] = "physio"
    tables = {WIDE_NAME: wide_header, LONG_NAME: combined_header,
              PSYCHO_LONG_NAME: psycho_header, PHYSIO_LONG_NAME: physio_header}
    dict_rows = build_dictionary(tables, provenance, load_schema())
    dict_header = ["column", "tables", "source", "label_zh", "unit_or_range", "coding", "registered"]

    # e) 报告
    present = lambda s: s in wide
    physio_n = {s: sum((s, p) in win for p in phases) for s in subjects}
    lines = [f"integration 03 合表报告（数据集 {dataset}）",
             f"运行时间：{started:%Y-%m-%d %H:%M:%S}（北京时间）", "",
             f"一、被试名单（raw/session_notes，共 {len(subjects)} 人）：{'、'.join(subjects)}", "",
             "二、完整性（每人：问卷 / 生理窗口数）"]
    for s in subjects:
        rows_long = sum((s, t) in long for t in TIMES)
        lines.append(f"  {s}：问卷 {'有' if present(s) else '无'}（长表 {rows_long}/{len(TIMES)} 个时点）；"
                     f"生理 {'有' if physio_n[s] else '无'}（{physio_n[s]}/{len(phases)} 个窗口）")
    gaps = [f"{s} 缺问卷" for s in subjects if not present(s)] + [f"{s} 缺生理" for s in subjects if not physio_n[s]]
    lines.append("  流程单有、某类数据表里没有的被试：" + ("；".join(gaps) if gaps else "无"))
    lines += ["", "三、组别核对（log.csv 的 group_code 与 scores_wide.csv 的 group）"]
    bad = []
    for s in subjects:
        if roster[s][1]:
            bad.append(f"  {s}：log.csv 无法取得组别（{roster[s][1]}），group 留空")
        elif present(s) and wide[s].get("group", "").strip() != roster[s][0]:
            bad.append(f"  {s}：log.csv={roster[s][0]}，scores_wide.csv={wide[s].get('group', '').strip() or '空'}")
    lines += bad or ["  一致"]
    extra = sorted(({s for s in wide} | {k[0] for k in long} | {k[0] for k in win}) - set(subjects))
    lines += ["", "四、数据表里有、流程单没有的被试（不并入）：" + ("、".join(extra) if extra else "无"), "",
              f"五、各变量有效（非空）人数（{WIDE_NAME}，共 {len(subjects)} 人）"]
    for i, col in enumerate(wide_header):
        n = sum(1 for r in wide_rows if r[i] != "")
        lines.append(f"  {col}：{n}")
    unreg = [r[0] for r in dict_rows if r[6] == 0]
    lines += ["", f"六、data_dictionary 中 registered=0 的列（{len(unreg)} 个）：" + ("、".join(unreg) if unreg else "无"), ""]
    lines += ["七、合并长表的问卷—生理对应（阶段后问卷，不代表同时采集）"]
    lines += [f"  {phase} → {time or '无问卷时点，时点测量列留空'}" for phase, time in INTEGRATION_PHASE_TIMEPOINTS.items()]
    lines += [f"  {LONG_NAME} 每人五行；个人字段重复，T3单次体验字段仅在intervention行保留。",
              "  所有数值照抄上游，不筛除质量不合格测量，不自动执行研究者的统计排除决定。", ""]
    person_prefixes = INTEGRATION_TABLES["long"]["person_column_prefixes"]
    wide_only = [c for c in score_cols if c not in person_cols
                 and not any(c.startswith(t + "_") for t in TIMES)]
    lines += ["八、合并长表的问卷列纳入规则：",
              "  T1/T2/T3列按对应时点展开；个人字段仅纳入前缀：" + "、".join(person_prefixes),
              "  仅保留在宽表、未带入合并长表的问卷列：" + ("、".join(wide_only) if wide_only else "无"), ""]

    write_csv(out_dir / WIDE_NAME, wide_header, wide_rows, out_dir)
    write_csv(out_dir / LONG_NAME, combined_header, combined_rows, out_dir)
    write_csv(out_dir / PSYCHO_LONG_NAME, psycho_header, psycho_rows, out_dir)
    write_csv(out_dir / PHYSIO_LONG_NAME, physio_header, physio_rows, out_dir)
    write_csv(out_dir / DICT_NAME, dict_header, dict_rows, out_dir)
    write_text(out_dir / REPORT_NAME, "\n".join(lines), out_dir)
    archive_legacy_wide(out_dir)
    print(f"数据集 {dataset}：{len(subjects)} 位被试，已写入 {out_dir}")
    print(f"  {WIDE_NAME} {len(wide_rows)} 行 × {len(wide_header)} 列；{LONG_NAME} {len(combined_rows)} 行 × {len(combined_header)} 列；"
          f"{PSYCHO_LONG_NAME} {len(psycho_rows)} 行；"
          f"{PHYSIO_LONG_NAME} {len(physio_rows)} 行；{DICT_NAME} {len(dict_rows)} 行")
    return out_dir
