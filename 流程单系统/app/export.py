"""
从各被试的 state.json 重新生成三张表（CSV）：问卷总表、问卷总表列名对照、实验记录表。
对应交接文档第八节的"问卷总表"“实验记录表"；列名对照是额外加的，不看代码也能看懂
总表里每一列是什么（参照 analysis/README.md 里 track 制表"列名对照"的做法）。

设计原则：state.json 是唯一权威数据源（它已经是原子写入，不怕中途崩溃）；这三张表
只是从它派生出来的视图，每次都整表重新生成，不做增量追加——不管重新导出多少次、
什么时候导出，结果都只取决于当时各被试的 state.json 内容。

触发时机：被试跑到第 17 页"完成实验"、进入结束页（第 18 页）时，由 server.py 自动
调用 export_all()，不需要实验员另外点导出按钮。

这里导出的只是"流程单系统自己的原始记录"，不是项目根目录 README 里说的正式
数据规范（global_settings.py 的 METRICS["psycho"]）——那是经过研究讨论确认后
登记的事，不属于这个系统的工作范围。字段/计分口径的草稿登记在
analysis/table_flows/psycho/psycho_schema_draft.py，确认后再合并进 global_settings.py。
"""
import csv
import datetime
import os

import flow
import judging
import questionnaire
import state as state_mod

# 问卷总表收 A、T0-T3 的全部题目。T3 在流程里拆成 T3a、T3b 两份问卷，列名仍用 T3_ 前缀。
QUESTIONNAIRE_IDS = ["A", "T0", "T1", "T2", "T3a", "T3b"]
# 合并各人作答时读取的 state.json 记录名：额外带上合并的 "T3"（新版由系统自动维护，
# 旧版被试只有这一份），题目键名相同，合并结果一致。
ANSWER_RECORD_IDS = ["A", "T0", "T1", "T2", "T3", "T3a", "T3b"]

# 原始作答的编码方式，写进 questionnaires_codebook.csv，供看表的人核对每一列的含义。
# 重要：matrix/numeric 题存的是"选项下标"（0 起），不是量表原始的 1-4、1-7 这种分数；
# 下标到分数的换算（含反向计分题）由 scales.py 里的 value_start/reverse 决定，这里不转换——
# APP 只记录被试选了第几个选项，计分、分类等派生指标留给下游的 analysis/table_flows/psycho
# 去做（和 track 流程"APP 仅记录原始量，指标离线计算"的原则一致）。


def _questionnaire_schema():
    """返回 (列名列表, 对应的取值函数列表, 对应的编码说明行)。
    取值函数签名 extract(merged_answers) -> str。"""
    columns, extractors, codebook_rows = [], [], []
    for instrument_id in QUESTIONNAIRE_IDS:
        # codebook 的 instrument 列：T3a、T3b 仍写 T3，与列名前缀、下游分析工具一致。
        instrument_label = questionnaire.QUESTIONNAIRES[instrument_id].get("codebook_instrument", instrument_id)
        for page in questionnaire.QUESTIONNAIRES[instrument_id]["pages"]:
            for block in page["blocks"]:
                t = block["type"]
                if t == "matrix":
                    value_note = "选项下标（0 起）：" + "; ".join(
                        "%d=%s" % (i, opt) for i, opt in enumerate(block["options"])
                    )
                    for key, text in block["items"]:
                        columns.append(key)
                        extractors.append(lambda a, k=key: a.get(k, ""))
                        codebook_rows.append([key, instrument_label, text, value_note])
                elif t == "numeric":
                    labels = "; ".join(
                        "%d=%s" % (v, l) for v, l in sorted(block["scale_labels"].items())
                    )
                    value_note = "%d-%d（数字越大越符合；%s）" % (block["scale_min"], block["scale_max"], labels)
                    for key, text in block["items"]:
                        columns.append(key)
                        extractors.append(lambda a, k=key: a.get(k, ""))
                        codebook_rows.append([key, instrument_label, text, value_note])
                elif t == "slider":
                    key = block["key"]
                    spec = block["spec"]
                    columns.append(key)
                    extractors.append(lambda a, k=key: a.get(k, ""))
                    codebook_rows.append([key, instrument_label, spec["prompt"], "%s-%s（%s → %s）" % (
                        spec["min"], spec["max"], spec.get("left_label", ""), spec.get("right_label", ""),
                    )])
                elif t == "multi":
                    key = block["key"]
                    spec = block["spec"]
                    for i, opt in enumerate(spec["options"]):
                        col = "%s_%d" % (key, i + 1)
                        columns.append(col)
                        extractors.append(lambda a, k=key, idx=i: (
                            "" if k not in a else ("1" if str(idx) in a[k] else "0")
                        ))
                        codebook_rows.append([col, instrument_label, opt, "1=勾选, 0=未勾选, 空=未作答该题"])
                elif t == "basic_info":
                    columns.append("A_age")
                    extractors.append(lambda a: a.get("A_age", ""))
                    codebook_rows.append(["A_age", instrument_label, "年龄", "数字（岁）"])
                    columns.append("A_gender")
                    extractors.append(lambda a: a.get("A_gender", ""))
                    codebook_rows.append(["A_gender", instrument_label, "性别", "0=男, 1=女"])
    return columns, extractors, codebook_rows


def _iter_participants(data_root):
    """按被试编号排序，依次产出 (participant_id, state_dict)；读不出来的目录直接跳过
    （比如正好在被另一个进程写入、或者是半成品目录），不让一个坏文件拖垮整次导出。"""
    root = state_mod.mode_root(data_root)
    if not os.path.isdir(root):
        return
    for name in sorted(os.listdir(root)):
        state_file = os.path.join(root, name, "state.json")
        if not os.path.isfile(state_file):
            continue
        try:
            yield name, state_mod.load_state(data_root, name)
        except (OSError, ValueError):
            continue


def _fmt_ts(ts):
    if not ts:
        return ""
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _atomic_write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    # utf-8-sig：带 BOM，Windows 上 Excel 直接双击打开中文表头不会乱码。
    with open(tmp_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    os.replace(tmp_path, path)


def export_questionnaires_csv(data_root):
    columns, extractors, _codebook_rows = _questionnaire_schema()
    rows = []
    for participant_id, st in _iter_participants(data_root):
        answers = {}
        for instrument_id in ANSWER_RECORD_IDS:
            answers.update(st.get("questionnaires", {}).get(instrument_id, {}).get("answers", {}))
        rows.append([participant_id, st.get("group") or ""] + [ex(answers) for ex in extractors])
    path = state_mod.questionnaire_csv_path(data_root)
    _atomic_write_csv(path, ["participant_id", "group"] + columns, rows)
    return path


def export_questionnaire_codebook_csv(data_root):
    """问卷总表的列名对照（每列对应哪份问卷、哪道题、怎么编码），和 questionnaires.csv
    放在一起——不看代码也能看懂表里每一列是什么。每次导出都和总表一起重新生成。"""
    _columns, _extractors, codebook_rows = _questionnaire_schema()
    path = state_mod.questionnaire_codebook_path(data_root)
    _atomic_write_csv(path, ["column", "instrument", "item_text", "value_meaning"], codebook_rows)
    return path


def export_log_csv(data_root):
    """实验员写的实验记录文字不放这张表里（另存成每人一份的 notes.txt，见
    export_notes_txt），避免长文字、换行、逗号把 CSV 弄乱。"""
    page_ids = [p for p in flow.PAGE_ORDER if p != "end"]
    header = [
        "participant_id", "verdict", "stait_total", "stait_classification",
        "group", "group_code", "group_method", "ended", "end_reason",
    ] + page_ids
    rows = []
    for participant_id, st in _iter_participants(data_root):
        t0_answers = st.get("questionnaires", {}).get("T0", {}).get("answers", {})
        total = judging.stait_total_score(t0_answers)
        classification = judging.stait_classification(total)
        pages = st.get("pages", {})
        row = [
            participant_id, st.get("verdict") or "",
            total if total is not None else "", classification or "",
            st.get("group") or "", st.get("group_code") or "", st.get("group_method") or "",
            st.get("ended"), st.get("end_reason") or "",
        ]
        for page_id in page_ids:
            rec = pages.get(page_id)
            row.append("%s ~ %s" % (_fmt_ts(rec.get("started_at")), _fmt_ts(rec.get("completed_at"))) if rec else "")
        rows.append(row)
    path = state_mod.log_csv_path(data_root)
    _atomic_write_csv(path, header, rows)
    return path


def _page_notes(st):
    """这个被试每一页的 (页面标签, 备注文字)，按流程顺序；没写备注的页直接跳过。"""
    pages = st.get("pages", {})
    rows = []
    for page_id in flow.PAGE_ORDER:
        if page_id == "end":
            continue
        rec = pages.get(page_id)
        if not rec or not rec.get("notes"):
            continue
        page_def = flow.PAGES.get(page_id, {})
        number = page_def.get("number")
        title = page_def.get("title", page_id)
        label = "第 %s 页 · %s" % (number, title) if number else title
        rows.append((label, rec["notes"]))
    return rows


def export_notes_txt(data_root):
    """给每个被试生成一份单独的实验记录 txt（data/<mode>/<被试编号>/notes.txt），
    按页面顺序列出写了什么；没写备注的页直接跳过，不占位。"""
    paths = []
    for participant_id, st in _iter_participants(data_root):
        rows = _page_notes(st)
        lines = ["被试编号：%s" % participant_id, ""]
        if rows:
            for label, text in rows:
                lines.append(label)
                lines.append(text)
                lines.append("")
        else:
            lines.append("（本场没有记录任何实验记录文字）")
        path = state_mod.notes_txt_path(data_root, participant_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip("\n") + "\n")
        os.replace(tmp_path, path)
        paths.append(path)
    return paths


def export_all(data_root):
    """重新生成三张表和每位被试的实验记录 txt，返回 (问卷总表路径, 列名对照路径,
    实验记录表路径)。"""
    export_notes_txt(data_root)
    return export_questionnaires_csv(data_root), export_questionnaire_codebook_csv(data_root), export_log_csv(data_root)
