"""psycho 变量转换：按 global_settings.TRANSFORMS 登记（加上 05 的追加项）给问卷得分做中心化、标准化、取对数。

输入：data/<数据集>/processed/psycho/scores_wide.csv、scores_long.csv（03 的输出）。
输出（覆盖）：同目录 scores_wide.csv、scores_long.csv（在 03 的基础列之后追加转换列）、derived_report.txt。
每次先把两张表还原成 03 的基础列再追加转换列，所以重复运行结果相同。
均值、标准差用宽表全部被试（空值不参与），不受 parameters.py 的 subjects 影响。
05 可追加差值清单（输出名、被减数、减数）；逐人相减，任一源值缺失则留空，仅进宽表。
03 默认不传差值，重跑后需再运行 05 恢复追加项。
安全：写入前经 psycho_score.check_inside，目标不在 processed/psycho/ 之内就报错；不删除任何文件。
"""
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

from paths import layer_dir

if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import global_settings
from global_settings import TRANSFORM_METHODS
import psycho_score
from psycho_score import WIDE_COLUMNS, LONG_COLUMNS, WIDE_NAME, LONG_NAME, TZ_BEIJING

REPORT_NAME = "derived_report.txt"
PER_SUBJECT_PREFIXES = ("T0_", "A_")   # 每人一个值，可补进长表
WIDE_ONLY_PREFIXES = ("T1_", "T2_", "T3_")


def fmt(value):
    return "" if value is None else f"{value:.3f}"


def read_table(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def build_plan(extra_transforms):
    """合并确证性清单与追加清单；返回 [(item, kind)] 与跳过说明。"""
    plan, notes, seen = [], [], set()
    for item in global_settings.TRANSFORMS["psycho"]:
        key = (item["source"], item["method"])
        if key not in seen:
            seen.add(key)
            plan.append((dict(item), "确证性"))
    for item in extra_transforms:
        key = (item["source"], item["method"])
        if key in seen:
            notes.append(f"追加转换 {item['source']} / {item['method']} 与已有转换重复，已跳过")
            continue
        seen.add(key)
        plan.append((dict(item), "追加"))
    return plan, notes


def apply_transforms(dataset, extra_transforms, extra_differences=None):
    processed = layer_dir(dataset, "processed", "psycho")
    wide_path, long_path = processed / WIDE_NAME, processed / LONG_NAME
    for p in (wide_path, long_path):
        if not p.is_file():
            raise FileNotFoundError(f"找不到 {p}；请先运行 03_score_scales.py")
    wide_source_header, wide_rows = read_table(wide_path)
    _, long_rows = read_table(long_path)

    plan, notes = build_plan(extra_transforms)
    differences = list(extra_differences or [])

    # ---- 全部校验通过后才写文件 ----
    for item, _ in plan:
        if item["method"] not in TRANSFORM_METHODS:
            raise ValueError(f"未知转换方式：{item['method']}（可选 {list(TRANSFORM_METHODS)}）")
        if item["source"] not in WIDE_COLUMNS:
            raise ValueError(f"源列 {item['source']} 不在 03 的基础列（WIDE_COLUMNS）中")
    names = set(WIDE_COLUMNS) | {item["source"] + TRANSFORM_METHODS[item["method"]]["suffix"]
                                 for item, _ in plan}
    numeric_columns = set(WIDE_COLUMNS) - {"subject", "group"}
    for item in differences:
        if not isinstance(item, dict) or set(item) != {"name", "minuend", "subtrahend"}:
            raise ValueError("差值项须且仅须包含 name、minuend、subtrahend")
        name = item["name"]
        if not isinstance(name, str) or not name.isidentifier() or name in names:
            raise ValueError(f"差值输出名非法、重复或与已有列冲突：{name!r}")
        names.add(name)
        for key in ("minuend", "subtrahend"):
            src = item[key]
            if src not in numeric_columns:
                raise ValueError(f"差值源列 {src!r} 不是 03 的数值基础列")
            if src not in wide_source_header:
                raise ValueError(f"宽表缺少差值源列：{src}")
    values = {}
    sources = [item["source"] for item, _ in plan]
    sources += [item[key] for item in differences for key in ("minuend", "subtrahend")]
    for src in sources:
        if src in values:
            continue
        col = []
        for r in wide_rows:
            text = (r.get(src) or "").strip()
            if text == "":
                col.append(None)
                continue
            try:
                value = float(text)
                if not math.isfinite(value):
                    raise ValueError
                col.append(value)
            except ValueError:
                raise ValueError(f"源列 {src} 中有非有限数字值：{text!r}（被试 {r.get('subject')}）")
        values[src] = col

    new_cols, new_by_subject, report_lines, flags = [], {}, [], []
    for item, kind in plan:
        src, method = item["source"], item["method"]
        info = TRANSFORM_METHODS[method]
        name = src + info["suffix"]
        col = values[src]
        valid = [v for v in col if v is not None]
        n = len(valid)
        mean = sum(valid) / n if n else None
        sd = None
        if n >= 2:
            sd = math.sqrt(sum((v - mean) ** 2 for v in valid) / (n - 1))
        out, ln_blank = [], 0
        for v in col:
            if v is None:
                out.append(None)
            elif method == "center":
                out.append(v - mean)
            elif method == "z":
                out.append(None if (sd is None or sd == 0) else (v - mean) / sd)
            else:
                if v <= 0:
                    out.append(None)
                    ln_blank += 1
                else:
                    out.append(math.log(v))
        if method == "z" and (sd is None or sd == 0):
            flags.append(f"{name}：标准差为 {'无法计算（n<2）' if sd is None else '0'}，整列留空")
        if method == "ln" and ln_blank:
            flags.append(f"{name}：{ln_blank} 个 ≤ 0 的值留空")
        in_long = src.startswith(PER_SUBJECT_PREFIXES)
        if not in_long:
            if not src.startswith(WIDE_ONLY_PREFIXES):
                raise ValueError(f"源列 {src} 的前缀不是 T0_/A_/T1_/T2_/T3_，无法判断是否进长表")
            flags.append(f"{name}：源列为 {src[:2]} 时间点变量，只进宽表，不进长表")
        new_cols.append((name, in_long))
        for r, v in zip(wide_rows, out):
            new_by_subject.setdefault(r["subject"], {})[name] = fmt(v)
        report_lines.append(
            f"{name}｜源列 {src}｜{info['name']}｜{kind}｜n={n}｜空值 {len(col) - n}｜"
            f"均值 {'无' if mean is None else f'{mean:.4f}'}｜标准差 {'无' if sd is None else f'{sd:.4f}'}｜"
            f"{'已补进长表' if in_long else '只进宽表'}")

    difference_lines = []
    for item in differences:
        name, left, right = item["name"], item["minuend"], item["subtrahend"]
        out = [None if a is None or b is None else a - b
               for a, b in zip(values[left], values[right])]
        new_cols.append((name, False))
        for row, value in zip(wide_rows, out):
            new_by_subject.setdefault(row["subject"], {})[name] = fmt(value)
        n = sum(value is not None for value in out)
        difference_lines.append(f"{name} = {left} - {right}｜追加｜n={n}｜空值 {len(out) - n}｜只进宽表")

    wide_header = list(WIDE_COLUMNS) + [c for c, _ in new_cols]
    long_cols = [c for c, in_long in new_cols if in_long]
    long_header = list(LONG_COLUMNS) + long_cols
    wide_out = [[r[c] if c in WIDE_COLUMNS else new_by_subject[r["subject"]][c] for c in wide_header]
                for r in wide_rows]
    long_out = [[r[c] for c in LONG_COLUMNS] + [new_by_subject.get(r["subject"], {}).get(c, "") for c in long_cols]
                for r in long_rows]

    psycho_score.write_csv(wide_path, wide_header, wide_out, processed)
    psycho_score.write_csv(long_path, long_header, long_out, processed)

    now = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    text = [f"变量转换报告（数据集 {dataset}）", f"运行时间：{now}（北京时间）",
            f"被试数（宽表）：{len(wide_rows)}；均值与标准差用全部被试，空值不参与",
            "", "转换（新列｜源列｜方式｜类别｜参与人数｜空值数｜均值｜标准差｜长表）："] + report_lines
    text += ["", "差值（任一源值缺失则留空；负值照实保留）："] + (difference_lines or ["- 无"])
    text += ["", "跳过与留空情况："] + ([f"- {x}" for x in notes + flags] or ["- 无"])
    psycho_score.write_text(processed / REPORT_NAME, "\n".join(text) + "\n", processed)
    print(f"已写入：{wide_path}\n已写入：{long_path}\n已写入：{processed / REPORT_NAME}")
