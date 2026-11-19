"""integration 工具 04 的全部处理逻辑：按 global_settings.INTEGRATION_SHORT_TABLES 从整表排除固定字段，生成简表。

输入（只读）：data/<数据集>/final/integration/ 下 03 生成的整表（本工具不读 raw、不重算）
输出：同目录（每次整表重写）
    wide_short.csv          一人一行：背景与特质、T1–T3 核心结果、T3 体验指标、差值列、四窗口分析口径生理指标
    long_short.csv          每人四阶段：焦虑分层、中心化协变量、配对问卷、体验与安全、五项生理指标
    short_report.txt        中文报告：规模、逐列非空人数、来源表中未入选的列
规则：取舍只登记在 global_settings.INTEGRATION_SHORT_TABLES，本模块不维护第二份清单；
    只选列并排除登记窗口（训练），不改列名、不重算、不改值，不按 ok 筛选。
    不执行或推断人工审查结论，不生成诊断简表；标识列缺失时报错；固定排除列在源表不存在时列入报告，不阻止运行。
    未登记的新列默认保留，计算列不按后缀或构念筛选，列序沿用来源表。
安全：写入前检查目标路径在 final/integration/ 之内；不删除任何文件。
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paths import layer_dir

PROJECT = Path(__file__).resolve().parents[2]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
from global_settings import (INTEGRATION_AUX_FILES, INTEGRATION_SHORT_TABLES, INTEGRATION_TABLES, validate)
from integration_merge import check_inside, read_table, write_csv, write_text

REPORT_NAME = INTEGRATION_AUX_FILES["short_report"]
TZ_BEIJING = timezone(timedelta(hours=8))
WRAP = 8   # 报告里每行最多列出的列名个数


def source_path(out_dir, source):
    """来源整表的文件名与路径；整表规范读 INTEGRATION_TABLES。"""
    return out_dir / INTEGRATION_TABLES[source]["filename"]


def build_short(spec, header, rows):
    """排除固定字段/结构，未知新列自动保留；不改源行序及数值文本。"""
    required = list(spec["id_columns"])
    excluded_windows = set(spec.get("exclude_windows", ()))
    if excluded_windows and "window" not in required:
        required.append("window")
    missing = [c for c in required if c not in header]
    if missing:
        raise ValueError(f"来源表缺少简表 {spec['filename']} 需要的标识列：{'、'.join(missing)}；请先重跑 03")
    if len(header) != len(set(header)):
        raise ValueError(f"来源表含重复列名：{spec['filename']}")
    excluded = set(spec.get("exclude_columns", ()))
    prefixes = tuple(spec.get("exclude_column_prefixes", ()))
    keep = [c for c in header if c not in excluded and not (prefixes and c.startswith(prefixes))]
    if any(c not in keep for c in required):
        raise ValueError(f"简表 {spec['filename']} 的排除规则误排除了标识列")
    return keep, [[row[c] for c in keep] for row in rows
                  if not excluded_windows or row["window"] not in excluded_windows]


def wrap_columns(names, width=WRAP):
    """把列名按每行若干个折行，便于在报告里核对。"""
    if not names:
        return ["  （无）"]
    return ["  " + "、".join(names[i:i + width]) for i in range(0, len(names), width)]


def run(dataset):
    validate()
    out_dir = layer_dir(dataset, "final") / "integration"
    if not out_dir.is_dir():
        raise FileNotFoundError(f"找不到 {out_dir}；请先运行 03_merge_tables.py")
    started = datetime.now(TZ_BEIJING)
    cache, written = {}, []
    check_inside(out_dir / REPORT_NAME, out_dir)

    for spec in INTEGRATION_SHORT_TABLES.values():
        name = spec["filename"]
        path = source_path(out_dir, spec["source"])
        check_inside(out_dir / name, out_dir)
        if path not in cache:
            cache[path] = read_table(path)
        header, rows = cache[path]
        keep, short_rows = build_short(spec, header, rows)
        previous_path = out_dir / name
        previous = read_table(previous_path)[0] if previous_path.is_file() else None
        # 仅比较表头，报告新增列；不依赖旧数据决定本次输出。
        additions = [c for c in keep if previous is not None and c not in previous]
        spec = dict(spec, previous_exists=previous is not None, added_columns=additions)
        written.append((name, keep, short_rows, header, spec, len(rows)))

    lines = [f"integration 04 简表报告（数据集 {dataset}）",
             f"运行时间：{started:%Y-%m-%d %H:%M:%S}（北京时间）", "",
             "说明：按 global_settings.INTEGRATION_SHORT_TABLES 排除固定字段与登记窗口；",
             "      未登记的新列默认保留，中心化、差值等计算列随来源表自动带入，列序沿用源表。",
             "      保持源行顺序、原始编码、数值文本和空值，不重算，不按 ok 筛选或清空指标。",
             "      除登记的窗口外不筛行；不执行或推断人工审查结论；生理纳入以人工审查为准。",
             "      不生成诊断简表；历史诊断文件不属于当前输出。", "",
             "一、规模"]
    for name, keep, short_rows, src_header, spec, source_n in written:
        src_name = INTEGRATION_TABLES[spec["source"]]["filename"]
        excluded = spec.get("exclude_windows", ())
        lines.append(f"  {name}：{len(short_rows)} 行 × {len(keep)} 列"
                     f"（来源 {src_name} {source_n} 行 × {len(src_header)} 列；未入选 {len(src_header) - len(keep)} 列）")
        lines.append(f"    排除窗口：{'、'.join(excluded) if excluded else '无'}；排除 {source_n - len(short_rows)} 行；"
                     f"保留 {len({r[keep.index('subject')] for r in short_rows})} 位被试")

    lines += ["", "二、各简表逐列非空被试数与非空行数"]
    for name, keep, short_rows, src_header, spec, _ in written:
        lines.append(f"  {name}")
        for i, col in enumerate(keep):
            n = sum(1 for r in short_rows if r[i] != "")
            subjects = {r[keep.index("subject")] for r in short_rows if r[i] != ""}
            lines.append(f"    {col}：{len(subjects)} 人 / {n} 行")

    lines += ["", "三、来源表中未进简表的列（不含标识列，供核对；需要时回整表取）"]
    for name, keep, _, src_header, spec, _ in written:
        unused = [c for c in src_header if c not in keep]
        lines.append(f"  {INTEGRATION_TABLES[spec['source']]['filename']} → {name}（{len(unused)} 列）")
        lines += wrap_columns(unused)

    lines += ["", "四、排除清单核对与新增保留列"]
    for name, keep, _, src_header, spec, _ in written:
        absent = [c for c in spec.get("exclude_columns", ()) if c not in src_header]
        lines.append(f"  {name}：")
        lines.append("    源表不存在的固定排除列（未命中，非错误）：" + ("、".join(absent) if absent else "无"))
        lines.append("    相比上次新增保留列：" +
                     ("首次生成，无旧表头可比较" if not spec["previous_exists"] else
                      "、".join(spec["added_columns"]) or "无"))

    empty = [f"{name} 的 {col}" for name, keep, rows_, _, _, _ in written
             for i, col in enumerate(keep) if all(r[i] == "" for r in rows_)]
    lines += ["", "五、提示",
              "  保留列全为空：" + ("、".join(empty) if empty else "无"),
              "  全空列仍保留，不将缺失替换为 0；被试不会因缺少问卷或生理值而被删除。",
              "  本次未应用人工审查排除；请按人工审查记录确定用于分析的指标。", ""]

    for name, keep, short_rows, _, _, _ in written:
        write_csv(out_dir / name, keep, short_rows, out_dir)
    write_text(out_dir / REPORT_NAME, "\n".join(lines), out_dir)
    print(f"数据集 {dataset}：已写入 {out_dir}")
    for name, keep, short_rows, _, _, _ in written:
        print(f"  {name} {len(short_rows)} 行 × {len(keep)} 列")
    print(f"  {REPORT_NAME}")
    return out_dir
