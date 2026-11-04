"""psycho 工具 03 的全部计分函数：量表计分（反向计分、合计、均分、分类），拼合组别。

输入（只读）：
    data/<数据集>/processed/psycho/items_wide.csv：工具 02 的输出，每位被试一行，值为原始存储值
        （矩阵题存的是选项下标，0 起；数字题存的是所选数字；空＝未作答）。
    data/<数据集>/raw/session_notes/sub-P###/log.csv：只取 group_code、group、stait_total 三列
        （stait_total 只用于校验，不参与计分）。下划线开头的文件夹不读。
    analysis/table_flows/psycho/psycho_schema_draft.py：计分参数全部从其中的 PSYCHO_METRICS 的
        parameters 读取（反向题号、起始值、cutoff、量程），选项数核对用 PSYCHO_SCHEMA 的 levels。
        本文件不重写反向题号，也不修改 psycho_schema_draft.py。
输出：data/<数据集>/processed/psycho/
    scores_wide.csv：每位被试一行（列名 = 问卷_量表_统计量）。
    scores_long.csv：每位被试 × 时间点（T1、T2、T3）一行，重复测量的量表。
    scores_report.txt：中文报告（处理的被试、STAI-T 校验、各量表用到的题与反向题号、得分为空的原因）。

计分规则：
    矩阵题（stait、stai6、cns、msbs）：存的是选项下标，先加 value_start 得原始分；
        反向题取 (lo + hi) − 原始分，lo、hi 为该量表原始分的最小、最大值
        （lo = value_start，hi = value_start + 选项数 − 1；即 (选项数 + 1) − 原始分）。
    数字题（attention、fascination、away、imi_choice、meaning）：存的就是所选数字；
        反向题取 (scale_min + scale_max) − 原值，即 8 − 原值。
    gad2：下标直接计分（value_start=0），不 +1。
    vas、fms：原值，不转换。
    任一题缺答（或取值异常）→ 该量表得分记为空，不做插补。

安全：所有写入都先经过 check_inside()，目标不在 processed/psycho/ 之内就报错，不写任何文件。
    读取不改 raw/，不删除任何文件。
"""
import csv
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paths import layer_dir

if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from global_settings import VALUE_LABELS

PROJECT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT / "analysis" / "table_flows" / "psycho" / "psycho_schema_draft.py"

# 三个输出文件名
WIDE_NAME = "scores_wide.csv"
LONG_NAME = "scores_long.csv"
REPORT_NAME = "scores_report.txt"
# 重复测量的时间点
TIMES = ("T1", "T2", "T3")
# 北京时间 UTC+8（固定偏移，不依赖时区数据库），与工具 01、02 一致
TZ_BEIJING = timezone(timedelta(hours=8))

# 量表（与 PSYCHO_METRICS 的 key 相同）→ 列名模板。列名 = 模板 + "_" + 题号；
# 模板里的 {T} 代表 T1 / T2 / T3 之一（STAI-6、MSBS-8、VAS 三个时间点都测）。
SCALE_TEMPLATE = {
    "stait_total": "T0_stait",
    "cns_total": "T0_cns",
    "gad2_total": "A_gad2",
    "stai6_total": "{T}_stai6",
    "msbs8_total": "{T}_msbs",
    "anxiety_vas": "{T}_vas",
    "fms": "T3_fms",
    "attention": "T3_attention",
    "fascination": "T3_fascination",
    "being_away": "T3_away",
    "imi_choice": "T3_imi_choice",
    "meaning": "T3_meaning",
}
# 单题直接读取的量表（不分题、没有题号后缀）
DIRECT_SCALES = ("anxiety_vas", "fms")
# 量表的中文名，用于报告
SCALE_NAMES = {
    "stait_total": "STAI-T 特质焦虑",
    "cns_total": "CNS 自然联结",
    "gad2_total": "GAD-2 广泛性焦虑筛查",
    "stai6_total": "STAI-6 状态焦虑",
    "msbs8_total": "MSBS-8 状态无聊",
    "anxiety_vas": "焦虑 VAS",
    "fms": "FMS 晕动",
    "attention": "注意困难",
    "fascination": "迷恋",
    "being_away": "远离",
    "imi_choice": "IMI 感知选择",
    "meaning": "意义",
}

# 输出列（列名 = 问卷_量表_统计量）。顺序即 scores_wide.csv 的列顺序。
WIDE_COLUMNS = (
    ["subject", "group", "A_age", "A_gender",
     "A_gad2_sum", "A_screen_hard",
     "T0_stait_sum", "T0_stait_level", "T0_cns_sum", "T0_cns_mean"]
    + [col for t in TIMES for col in (f"{t}_stai6_sum", f"{t}_stai6_x20", f"{t}_vas",
                                      f"{t}_msbs_sum", f"{t}_msbs_mean")]
    + ["T3_attention_mean", "T3_fascination_mean", "T3_away_mean",
       "T3_imi_choice_sum", "T3_imi_choice_mean", "T3_meaning_sum", "T3_meaning_mean",
       "T3_fms"]
)
# 长表列
LONG_COLUMNS = ["subject", "group", "time",
                "stai6_sum", "stai6_x20", "vas", "msbs_sum", "msbs_mean"]


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
    """写 scores_report.txt。写前先检查路径。"""
    target = check_inside(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# ---------- 参数（从 psycho_schema_draft.py 读取） ----------

def normalize_subject(text):
    """接受 'P001' 或 'sub-P001'，统一成 'P001'。"""
    text = str(text).strip()
    return text[4:] if text.startswith("sub-") else text


def load_schema():
    """只读导入 psycho_schema_draft.py（不修改它）。该文件 import global_settings.Field，
    所以先把项目根目录放进 sys.path。"""
    if str(PROJECT) not in sys.path:
        sys.path.insert(0, str(PROJECT))
    spec = importlib.util.spec_from_file_location("psycho_schema_draft_for_score", SCHEMA_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_field(schema, column):
    """在 PSYCHO_SCHEMA 的各问卷里查找列名对应的 Field；找不到返回 None。"""
    for questionnaire in schema.PSYCHO_SCHEMA.values():
        if column in questionnaire:
            return questionnaire[column]
    return None


def item_columns(template, count, time):
    """列名：count 为题数（None 表示单题直接读取，列名就是模板本身）。"""
    base = template.format(T=time)
    if count is None:
        return [base]
    return [f"{base}_{i}" for i in range(1, count + 1)]


def build_specs(schema, option_counts):
    """每个量表的计分规格：题数、列名、反向题号、原始分范围、换算偏移、cutoff。
    全部从 PSYCHO_METRICS 的 parameters 读取；矩阵题选项数优先用 option_counts（设置区），
    并与 PSYCHO_SCHEMA 的 levels 核对，不一致就报错。"""
    metrics = schema.PSYCHO_METRICS
    specs = {}
    for scale, template in SCALE_TEMPLATE.items():
        metric = metrics[scale]
        params = metric["parameters"]
        direct = scale in DIRECT_SCALES
        count = None if direct else len(metric["inputs"])
        first = item_columns(template, count, "T1")[0]
        field = schema_field(schema, first)
        if field is None or field.levels is None:
            raise ValueError(f"PSYCHO_SCHEMA 里找不到 {first} 的取值范围，无法计分")
        levels = tuple(field.levels)
        reverse = tuple(params.get("reverse_items", ()))
        spec = {
            "scale": scale,
            "name": SCALE_NAMES[scale],
            "template": template,
            "timed": "{T}" in template,
            "count": count,
            "reverse": reverse,
            "cutoff": params.get("cutoff"),
            "first_column": first,
            "check": "",
        }
        if direct:
            spec.update(kind="直接读取", offset=0, lo=min(levels), hi=max(levels),
                        store_lo=min(levels), store_hi=max(levels))
        elif "scale_min" in params:
            lo, hi = params["scale_min"], params["scale_max"]
            if (min(levels), max(levels)) != (lo, hi):
                raise ValueError(f"{scale} 的量程 {lo}-{hi} 与 PSYCHO_SCHEMA 的 {first} "
                                 f"取值 {min(levels)}-{max(levels)} 不一致")
            spec.update(kind="数字题", offset=0, lo=lo, hi=hi, store_lo=lo, store_hi=hi)
            spec["check"] = f"量程 {lo}-{hi} 与 PSYCHO_SCHEMA 一致"
        else:
            start = params["value_start"]
            if levels != tuple(range(0, len(levels))):
                raise ValueError(f"{scale} 的 {first} 不是下标取值（0 起），无法按矩阵题计分")
            n = option_counts.get(scale, len(levels))
            if n != len(levels):
                raise ValueError(f"{scale} 的选项数设置为 {n}，与 PSYCHO_SCHEMA 的 {first} "
                                 f"选项数 {len(levels)} 不一致，请修改 03 脚本的设置区")
            spec.update(kind="下标直接计分" if start == 0 else "矩阵题", offset=start,
                        lo=start, hi=start + n - 1, store_lo=0, store_hi=n - 1)
            spec["check"] = (f"选项数 {n} 与 PSYCHO_SCHEMA 一致" if scale in option_counts
                             else f"选项数 {n} 取自 PSYCHO_SCHEMA")
        specs[scale] = spec
    return specs


# ---------- 单元格读取与计分 ----------

def read_cell(row, column):
    """读一个单元格：返回 (整数或 None, 状态)；状态为 "ok"、"blank"（空＝未作答）、"bad"（不是整数）。"""
    text = (row.get(column) or "").strip()
    if text == "":
        return None, "blank"
    try:
        number = float(text)
    except ValueError:
        return None, "bad"
    if not number.is_integer():
        return None, "bad"
    return int(number), "ok"


def score_one(row, spec, time):
    """计算一个量表（某个时间点）的得分。缺答或取值异常时 sum、mean 留空，不插补。
    返回 dict：columns（用到的列）、items（每题计分后的值）、missing、invalid、sum、mean。"""
    columns = item_columns(spec["template"], spec["count"], time)
    values, missing, invalid = [], [], []
    for position, column in enumerate(columns, start=1):
        stored, status = read_cell(row, column)
        if status == "blank":
            missing.append(column)
            continue
        if status == "bad":
            invalid.append(f"{column}={(row.get(column) or '').strip()}（不是整数）")
            continue
        raw = stored + spec["offset"]
        if not spec["lo"] <= raw <= spec["hi"]:
            invalid.append(f"{column}={stored}（超出 {spec['store_lo']}-{spec['store_hi']}）")
            continue
        if position in spec["reverse"]:
            raw = spec["lo"] + spec["hi"] - raw
        values.append(raw)
    result = {"columns": columns, "items": values, "missing": missing, "invalid": invalid,
              "sum": None, "mean": None}
    if not missing and not invalid and values:
        total = sum(values)
        result["sum"] = total
        result["mean"] = total / len(values)
    return result


def score_subject(row, specs):
    """一位被试的全部量表得分。键为 (量表, 时间点)；非重复测量的量表时间点为 None。"""
    results = {}
    for scale, spec in specs.items():
        times = TIMES if spec["timed"] else (None,)
        for time in times:
            results[(scale, time)] = score_one(row, spec, time)
    return results


def screen_hard(row, items):
    """A_screen 第 1–4 项中为 1 的项号，分号连接；无则留空。任一项缺答则整体留空并说明原因。"""
    hits, gaps = [], []
    for item in items:
        stored, status = read_cell(row, f"A_screen_{item}")
        if status != "ok":
            gaps.append(f"A_screen_{item}")
        elif stored == 1:
            hits.append(str(item))
    if gaps:
        return "", "缺答或取值异常：" + "、".join(gaps)
    return ";".join(hits), ""


def stait_level(total, cutoff):
    """≥ cutoff 为 1，否则 0（含义见 VALUE_LABELS["T0_stait_level"]）；得分为空则留空。"""
    if total is None:
        return ""
    return "1" if total >= cutoff else "0"


# ---------- 格式 ----------

def fmt_int(value):
    return "" if value is None else str(int(value))


def fmt_mean(value):
    return "" if value is None else f"{value:.3f}"


# ---------- 组别（log.csv） ----------

def read_log(dataset, subject):
    """读 raw/session_notes/sub-P###/log.csv 的 group_code、group、stait_total。
    返回 (dict 或 None, 说明文字)。"""
    path = layer_dir(dataset, "raw") / "session_notes" / f"sub-{subject}" / "log.csv"
    if not path.is_file():
        return None, f"缺少 {path}"
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        return None, f"log.csv 有 {len(rows)} 行数据（应为 1 行）"
    row = rows[0]
    return {
        "group_code": (row.get("group_code") or "").strip(),
        "group": (row.get("group") or "").strip(),
        "stait_total": (row.get("stait_total") or "").strip(),
    }, ""


def group_value(log):
    """组别整数编码（取自 log.csv 的 group_code）；必须是 VALUE_LABELS["group"] 里的编码，否则留空。"""
    text = log["group_code"] if log else ""
    try:
        code = int(float(text))
    except ValueError:
        return ""
    return str(code) if code in VALUE_LABELS["group"] else ""


def check_stait(subject, computed, log):
    """STAI-T 校验：计算出的 T0_stait_sum 与 log.csv 的 stait_total 逐人比较。"""
    logged = log["stait_total"] if log else ""
    if computed is None:
        status = "无法校验（计分为空）"
    elif logged == "":
        status = "无法校验（log.csv 无 stait_total）"
    else:
        try:
            status = "一致" if int(float(logged)) == computed else "不一致"
        except ValueError:
            status = f"无法校验（log.csv 的 stait_total 不是数字：{logged}）"
    return {"subject": subject, "computed": fmt_int(computed) or "空",
            "logged": logged or "空", "status": status}


# ---------- 组装 ----------

def build_wide(subject, row, results, specs, log, hard_items):
    """一位被试的一行（scores_wide.csv）。返回 (dict, 空缺说明列表, 校验结果)。"""
    out = {col: "" for col in WIDE_COLUMNS}
    out["subject"] = subject
    out["group"] = group_value(log)
    out["A_age"] = (row.get("A_age") or "").strip()
    out["A_gender"] = (row.get("A_gender") or "").strip()

    gad = results[("gad2_total", None)]
    out["A_gad2_sum"] = fmt_int(gad["sum"])
    out["A_screen_hard"], _ = screen_hard(row, hard_items)

    stait = results[("stait_total", None)]
    out["T0_stait_sum"] = fmt_int(stait["sum"])
    out["T0_stait_level"] = stait_level(stait["sum"], specs["stait_total"]["cutoff"])
    cns = results[("cns_total", None)]
    out["T0_cns_sum"] = fmt_int(cns["sum"])
    out["T0_cns_mean"] = fmt_mean(cns["mean"])

    for t in TIMES:
        stai6 = results[("stai6_total", t)]
        n6 = len(stai6["columns"])
        out[f"{t}_stai6_sum"] = fmt_int(stai6["sum"])
        out[f"{t}_stai6_x20"] = "" if stai6["sum"] is None else fmt_mean(stai6["sum"] / n6 * 20)
        out[f"{t}_vas"] = fmt_int(results[("anxiety_vas", t)]["sum"])
        msbs = results[("msbs8_total", t)]
        out[f"{t}_msbs_sum"] = fmt_int(msbs["sum"])
        out[f"{t}_msbs_mean"] = fmt_mean(msbs["mean"])

    out["T3_attention_mean"] = fmt_mean(results[("attention", None)]["mean"])
    out["T3_fascination_mean"] = fmt_mean(results[("fascination", None)]["mean"])
    out["T3_away_mean"] = fmt_mean(results[("being_away", None)]["mean"])
    imi = results[("imi_choice", None)]
    out["T3_imi_choice_sum"] = fmt_int(imi["sum"])
    out["T3_imi_choice_mean"] = fmt_mean(imi["mean"])
    meaning = results[("meaning", None)]
    out["T3_meaning_sum"] = fmt_int(meaning["sum"])
    out["T3_meaning_mean"] = fmt_mean(meaning["mean"])
    out["T3_fms"] = fmt_int(results[("fms", None)]["sum"])
    return out


def build_long(wide):
    """一位被试 × 时间点一行（scores_long.csv），数值直接取自宽表，保证两表一致。"""
    rows = []
    for t in TIMES:
        rows.append({
            "subject": wide["subject"], "group": wide["group"],
            "time": t,
            "stai6_sum": wide[f"{t}_stai6_sum"], "stai6_x20": wide[f"{t}_stai6_x20"],
            "vas": wide[f"{t}_vas"], "msbs_sum": wide[f"{t}_msbs_sum"],
            "msbs_mean": wide[f"{t}_msbs_mean"],
        })
    return rows


# ---------- 报告 ----------

def describe_gap(result):
    parts = []
    if result["missing"]:
        parts.append("缺答：" + "、".join(result["missing"]))
    if result["invalid"]:
        parts.append("取值异常（按缺答处理）：" + "；".join(result["invalid"]))
    return "；".join(parts)


def describe_spec(spec):
    """报告里“用到的题、反向题号、取值范围”一行。"""
    if spec["count"] is None:
        cols = spec["first_column"]
        reverse = "无"
    else:
        head = spec["template"].replace("{T}", "T1/T2/T3") if spec["timed"] else spec["template"]
        cols = f"{head}_1 至 {head}_{spec['count']}（共 {spec['count']} 题）"
        reverse = "、".join(str(i) for i in spec["reverse"]) if spec["reverse"] else "无"
    if spec["kind"] == "直接读取":
        value = f"存储值 {spec['store_lo']}–{spec['store_hi']}，直接读取，不转换"
        total = "单题，原值"
    else:
        value = (f"存储值 {spec['store_lo']}–{spec['store_hi']}"
                 f"（{spec['kind']}），计分用原始分 {spec['lo']}–{spec['hi']}")
        if spec["kind"] == "矩阵题":
            value += f"（存储下标 + {spec['offset']}）"
        total = (f"合计 {spec['count'] * spec['lo']}–{spec['count'] * spec['hi']}，"
                 f"均分 {spec['lo']}–{spec['hi']}")
    cutoff = f"；分类界值 cutoff={spec['cutoff']}" if spec["cutoff"] is not None else ""
    check = f"；{spec['check']}" if spec["check"] else ""
    return (f"  {spec['name']}（{spec['scale']}）\n"
            f"    题：{cols}\n"
            f"    反向题号：{reverse}\n"
            f"    取值：{value}\n"
            f"    汇总：{total}{cutoff}{check}")


def build_report(dataset, chosen, specs, checks, empty_lines, screen_notes, log_notes, extra_notes):
    now = datetime.now(TZ_BEIJING).isoformat(timespec="seconds")
    lines = [
        "psycho 工具 03 量表计分报告",
        f"数据集：{dataset}；本次处理被试：{', '.join(chosen)}（共 {len(chosen)} 位）",
        f"生成时间：{now}（北京时间）",
        "",
        "[一] STAI-T 总分校验（计算值 与 log.csv 的 stait_total 逐人比较）",
    ]
    mismatches = [c for c in checks if c["status"] == "不一致"]
    unverified = [c for c in checks if c["status"].startswith("无法校验")]
    if mismatches:
        lines.append(f"  ★★★ 校验发现 {len(mismatches)} 位被试不一致（不影响输出，请核对）："
                     + "；".join(f"{c['subject']}（计算 {c['computed']}，log {c['logged']}）"
                                 for c in mismatches))
    elif not unverified:
        lines.append(f"  ★ 校验通过：{len(checks)} 位被试的计算 STAI-T 总分与 log.csv 一致。")
    if unverified:
        lines.append("  ⚠ 以下被试无法校验：" + "；".join(
            f"{c['subject']}（{c['status']}）" for c in unverified))
    for c in checks:
        lines.append(f"    {c['subject']}：计算 {c['computed']}，log.csv {c['logged']}，{c['status']}")
    lines.append("")

    lines.append("[二] 各量表用到的题、反向题号、取值范围（选项数核对见各条“检查”）")
    for spec in specs.values():
        lines.append(describe_spec(spec))
    lines.append("")

    lines.append("[三] 得分为空的量表及原因（不插补）")
    if empty_lines or screen_notes:
        lines.extend(f"  {line}" for line in empty_lines + screen_notes)
    else:
        lines.append("  无")
    lines.append("")

    lines.append("[四] 组别与其他说明")
    lines.extend(f"  {line}" for line in (log_notes + extra_notes) or ["无"])
    lines.append("")

    lines.append("[五] 编码说明（取自 global_settings.VALUE_LABELS；数据表里只存整数）")
    for variable, mapping in VALUE_LABELS.items():
        lines.append(f"  {variable}：" + "；".join(f"{k} = {v}" for k, v in mapping.items()))
    return "\n".join(lines) + "\n"


# ---------- 主流程 ----------

def run(dataset, subjects, option_counts):
    """计算数据集中被试的量表得分，写三个输出文件。返回 (wide_rows, long_rows, checks)。"""
    processed = layer_dir(dataset, "processed", "psycho")
    wide_in = processed / "items_wide.csv"
    if not wide_in.is_file():
        raise FileNotFoundError(f"找不到 {wide_in}；请先运行工具 02（02_merge_questionnaires.py）")

    schema = load_schema()
    specs = build_specs(schema, option_counts)
    hard_items = tuple(schema.PSYCHO_METRICS["a2_screening"]["parameters"]["hard_exclusion_items"])

    with wide_in.open(newline="", encoding="utf-8-sig") as f:
        by_subject = {normalize_subject(r["subject"]): r for r in csv.DictReader(f)}
    if subjects == "*":
        chosen = list(by_subject)
    else:
        wanted = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        absent = [s for s in wanted if s not in by_subject]
        if absent:
            raise ValueError(f"items_wide.csv 中没有这些被试：{absent}；请先运行工具 02")
        chosen = wanted
    if not chosen:
        raise ValueError("没有可处理的被试")
    print(f"数据集 {dataset}：共 {len(chosen)} 位被试")

    wide_rows, long_rows, checks = [], [], []
    empty_lines, screen_notes, log_notes = [], [], []
    for subject in chosen:
        print(f"[开始] sub-{subject}")
        row = by_subject[subject]
        log, log_error = read_log(dataset, subject)
        if log_error:
            log_notes.append(f"{subject}：{log_error}（组别留空）")
        results = score_subject(row, specs)
        wide = build_wide(subject, row, results, specs, log, hard_items)
        _, screen_gap = screen_hard(row, hard_items)
        if screen_gap:
            screen_notes.append(f"{subject} A_screen_hard：{screen_gap}")
        for (scale, time), result in results.items():
            if result["sum"] is None:
                label = SCALE_NAMES[scale] + (f"（{time}）" if time else "")
                empty_lines.append(f"{subject} {label}：{describe_gap(result)}")
        checks.append(check_stait(subject, results[("stait_total", None)]["sum"], log))
        wide_rows.append(wide)
        long_rows.extend(build_long(wide))
        print(f"[完成] sub-{subject}")

    mismatches = [c for c in checks if c["status"] == "不一致"]
    for c in mismatches:
        print(f"!! STAI-T 校验不一致：{c['subject']} 计算 {c['computed']}，log.csv {c['logged']}")

    wide_path = write_csv(processed / WIDE_NAME, WIDE_COLUMNS,
                          [[r[c] for c in WIDE_COLUMNS] for r in wide_rows], processed)
    long_path = write_csv(processed / LONG_NAME, LONG_COLUMNS,
                          [[r[c] for c in LONG_COLUMNS] for r in long_rows], processed)
    report_text = build_report(dataset, chosen, specs, checks, empty_lines, screen_notes,
                               log_notes, [])
    report_path = write_text(processed / REPORT_NAME, report_text, processed)
    print(f"已写入：{wide_path}")
    print(f"已写入：{long_path}")
    print(f"已写入：{report_path}")
    return wide_rows, long_rows, checks
