"""
从被试的 state.json 重新生成该被试的导出文件，写进项目 data/ 的规范位置：
  <数据集>/raw/psycho/<被试文件夹>/questionnaires.csv        该被试 1 行问卷表
  <数据集>/raw/psycho/<被试文件夹>/questionnaires_codebook.csv  该被试的列名对照（导出时的快照）
  <数据集>/raw/session_notes/<被试文件夹>/log.csv         该被试 1 行实验记录表
  <数据集>/raw/session_notes/<被试文件夹>/notes.txt       实验记录文字

设计原则：state.json 是唯一权威数据源（原子写入，不怕中途崩溃）；这些文件只是它派生出来的
视图，每次都整份重新生成，不做增量追加。只处理当前这一位被试，不扫描其他被试。

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
import time

import config
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


def export_questionnaires_csv(st):
    columns, extractors, _codebook_rows = _questionnaire_schema()
    answers = {}
    for instrument_id in ANSWER_RECORD_IDS:
        answers.update(st.get("questionnaires", {}).get(instrument_id, {}).get("answers", {}))
    row = [st["participant_id"], st.get("group") or ""] + [ex(answers) for ex in extractors]
    path = state_mod.questionnaire_csv_path(st["data_root"], st["participant_id"], st["mode"], st.get("broken", False))
    _atomic_write_csv(path, ["participant_id", "group"] + columns, [row])
    return path


def export_questionnaire_codebook_csv(st):
    """问卷表的列名对照（每列对应哪份问卷、哪道题、怎么编码），写进该被试自己的文件夹，
    与 questionnaires.csv 同处；每次导出都重新生成，作为该被试导出那一刻的快照。"""
    _columns, _extractors, codebook_rows = _questionnaire_schema()
    path = state_mod.questionnaire_codebook_path(st["data_root"], st["participant_id"], st["mode"], st.get("broken", False))
    _atomic_write_csv(path, ["column", "instrument", "item_text", "value_meaning"], codebook_rows)
    return path


def export_log_csv(st):
    """实验员写的实验记录文字不放这张表里（另存成 notes.txt，见 export_notes_txt），
    避免长文字、换行、逗号把 CSV 弄乱。"""
    page_ids = [p for p in flow.PAGE_ORDER if p != "end"]
    header = [
        "participant_id", "verdict", "stait_total", "stait_classification",
        "stratum", "stratum_position", "group", "group_code", "group_method", "ended", "end_reason",
    ] + page_ids
    t0_answers = st.get("questionnaires", {}).get("T0", {}).get("answers", {})
    total = judging.stait_total_score(t0_answers)
    classification = judging.stait_classification(total)
    pages = st.get("pages", {})
    rand = st.get("randomization") or {}  # 调整模式没有这条记录，两列为空
    row = [
        st["participant_id"], st.get("verdict") or "",
        total if total is not None else "", classification or "",
        rand.get("stratum", ""), rand.get("position", ""),
        st.get("group") or "", st.get("group_code") or "", st.get("group_method") or "",
        st.get("ended"), st.get("end_reason") or "",
    ]
    for page_id in page_ids:
        rec = pages.get(page_id)
        row.append("%s ~ %s" % (_fmt_ts(rec.get("started_at")), _fmt_ts(rec.get("completed_at"))) if rec else "")
    path = state_mod.log_csv_path(st["data_root"], st["participant_id"], st["mode"], st.get("broken", False))
    _atomic_write_csv(path, header, [row])
    return path


def _page_notes(st):
    """这个被试每一页的 (页面标签, 备注文字)，按流程顺序；没写备注的页直接跳过。"""
    pages = st.get("pages", {})
    drafts = st.get("drafts", {})
    rows = []
    for page_id in flow.PAGE_ORDER:
        if page_id == "end":
            continue
        rec = pages.get(page_id)
        # 已完成的页以"完成该阶段"时提交的文字为准；还没完成的页（比如中断时停在的那页）用实时保存的草稿。
        text = rec.get("notes") if rec else drafts.get(page_id, "")
        if not text:
            continue
        page_def = flow.PAGES.get(page_id, {})
        number = page_def.get("number")
        title = page_def.get("title", page_id)
        label = "第 %s 页 · %s" % (number, title) if number else title
        rows.append((label, text))
    return rows


def export_notes_txt(st):
    """该被试的实验记录 txt，按页面顺序列出写了什么；没写备注的页直接跳过，不占位。"""
    participant_id = st["participant_id"]
    rows = _page_notes(st)
    lines = ["被试编号：%s" % participant_id, ""]
    if rows:
        for label, text in rows:
            lines.append(label)
            lines.append(text)
            lines.append("")
    else:
        lines.append("（本场没有记录任何实验记录文字）")
    path = state_mod.notes_txt_path(st["data_root"], participant_id, st["mode"], st.get("broken", False))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip("\n") + "\n")
    os.replace(tmp_path, path)
    return path


_BJ = datetime.timezone(datetime.timedelta(hours=8))


def _fmt_bj(ts):
    return datetime.datetime.fromtimestamp(ts, _BJ).strftime("%Y-%m-%d %H:%M:%S")


def _page_label(page_id):
    if page_id == "end":
        return "结束页"
    page_def = flow.PAGES.get(page_id, {})
    number = page_def.get("number")
    title = page_def.get("title", page_id)
    return "第 %s 页 · %s" % (number, title) if number else title


def interrupt_note_text(st, now=None):
    """中断说明.txt 的内容（每行一项）。"""
    now = now or time.time()
    current = _page_label(st["current_page"])
    page_def = flow.PAGES.get(st["current_page"], {})
    if page_def.get("kind") == "questionnaire":
        q = st.get("questionnaires", {}).get(page_def["instrument"])
        if q and not q.get("submitted"):
            total = len(questionnaire.QUESTIONNAIRES[page_def["instrument"]]["pages"])
            current += "（问卷第 %d/%d 屏）" % (q.get("current_subpage", 0) + 1, total)
    done = [_page_label(p) for p in flow.PAGE_ORDER if p in st.get("pages", {})]
    submitted = [i for i in QUESTIONNAIRE_IDS
                 if st.get("questionnaires", {}).get(i, {}).get("submitted")]
    lines = [
        "被试编号：%s" % st["participant_id"],
        "运行模式：%s" % config.MODE_LABEL.get(st["mode"], st["mode"]),
        "开始时间：%s" % _fmt_bj(st["created_at"]),
        "最后更新时间：%s（北京时间）" % _fmt_bj(now),
        "当前停在：%s" % current,
        "已完成的页：%s" % ("、".join(done) if done else "（无）"),
        "已提交的问卷：%s" % ("、".join(submitted) if submitted else "（无）"),
        "此文件夹名以 _break_ 开头，表示本场实验没有正常结束。正常结束时程序会自动改名并删除本说明。",
    ]
    return "\n".join(lines) + "\n"


def write_interrupt_notes(st):
    text = interrupt_note_text(st)
    for path in state_mod.interrupt_note_paths(st["data_root"], st["participant_id"], st["mode"]):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)


def save_all(st):
    """统一保存：state.json + 重新导出问卷表/列名对照/实验记录表/记录文字 + 更新中断说明.txt。
    所有修改状态的地方改完后都调用它，保证任何时刻中断，磁盘上都是最新的。"""
    state_mod.save_state(st)
    export_all(st)
    if st.get("broken"):
        write_interrupt_notes(st)


def finalize(st):
    """正常结束：先把 _break_ 文件夹改回正式名；改名成功后才删除正式文件夹里自己生成的
    中断说明.txt，最后按正式名重新保存导出。改名失败（抛 FileExistsError/OSError）时不删除任何东西。"""
    if st.get("broken"):
        state_mod.rename_to_final(st)  # 失败会直接抛出，下面的删除不会执行
        for path in state_mod.interrupt_note_paths(st["data_root"], st["participant_id"], st["mode"], broken=False):
            if os.path.exists(path):
                os.remove(path)  # 程序运行时删除它自己生成的说明文件（唯一允许的删除）
    save_all(st)


def export_all(st):
    """只导出这一位被试（st 为其 state 字典）的文件，包括该被试自己的列名对照。
    返回 (问卷表路径, 列名对照路径, 实验记录表路径, 实验记录文字路径)。"""
    notes = export_notes_txt(st)
    return (export_questionnaires_csv(st), export_questionnaire_codebook_csv(st),
            export_log_csv(st), notes)
