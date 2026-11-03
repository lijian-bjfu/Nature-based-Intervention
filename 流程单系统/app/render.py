"""HTML 渲染：所有页面共用的外壳、计时器脚本，以及各类页面的拼装。"""
import html
import json

import config
import flow
import judging
import practice_script
import state as state_mod

CSS = """
* { box-sizing: border-box; }
body {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    margin: 0; padding: 0; background: #f4f4f2; color: #222;
}
.topbar {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 24px; background: #2b2d32; color: #fff; font-size: 16px;
}
.topbar .timer { font-size: 22px; font-weight: bold; font-variant-numeric: tabular-nums; }
.topbar .timer.overtime { color: #ff6b6b; }
.wrap { max-width: 900px; margin: 0 auto; padding: 24px; }
.stage-heading { font-size: 20px; color: #555; margin: 0 0 16px; font-weight: 600; }
.section-label { font-size: 15px; color: #666; margin: 0 0 6px; font-weight: 600; }
.instruction {
    font-size: 26px; line-height: 1.6; background: #fff; border-radius: 10px;
    padding: 24px; margin-bottom: 16px; border-left: 6px solid #3a6b4c;
}
.note { font-size: 14px; color: #888; margin-bottom: 16px; }
.midpoint-banner, .timeup-banner {
    display: none; font-size: 20px; font-weight: bold; padding: 14px 20px;
    border-radius: 8px; margin-bottom: 16px;
}
.midpoint-banner { background: #fff3cd; color: #8a6d00; }
.timeup-banner { background: #ffe1e1; color: #a30000; }
.checklist { background: #fff; border-radius: 10px; padding: 16px 24px; margin-bottom: 16px; }
.checklist label { display: block; font-size: 17px; margin: 8px 0; }
.notes-box textarea {
    width: 100%; min-height: 90px; font-size: 15px; padding: 10px; border-radius: 8px;
    border: 1px solid #ccc; font-family: inherit;
}
.actions { margin-top: 20px; display: flex; gap: 12px; }
button, .btn {
    font-size: 18px; padding: 12px 28px; border-radius: 8px; border: none;
    cursor: pointer; background: #3a6b4c; color: #fff;
}
button.secondary, .btn.secondary { background: #999; }
button.danger { background: #a33; }
button:disabled { background: #ccc; color: #888; cursor: not-allowed; }
form.inline { display: inline; }
.verdict-choices { display: flex; gap: 12px; margin: 16px 0; }
.verdict-choices button { background: #566; }
.settings-form label { display: block; margin: 14px 0 4px; font-size: 15px; }
.settings-form input { font-size: 16px; padding: 8px; width: 260px; }
.error-box { background: #ffe1e1; color: #a30000; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; }
.mode-flag { font-size: 12px; opacity: 0.8; }
.judging-box {
    background: #fff; border-radius: 10px; padding: 16px 22px; margin-bottom: 16px;
    border-left: 6px solid #8a6d00; font-size: 15px; line-height: 1.7;
}
.judging-box .suggestion { display: block; font-weight: 700; color: #8a6d00; margin-top: 8px; }

/* 练习场：按情境展开的指导语（原生 <details>，默认全收起） */
.guide-wrap { margin-bottom: 16px; }
.guide-principles { background: #fff; border-radius: 10px; padding: 14px 20px 14px 36px; margin: 0 0 12px; font-size: 14px; color: #555; line-height: 1.7; }
.guide-section { background: #fff; border-radius: 10px; padding: 4px 20px; margin-bottom: 10px; }
.guide-section summary { cursor: pointer; padding: 12px 0; font-size: 16px; font-weight: 600; color: #333; }
.guide-section[open] summary { border-bottom: 1px solid #eee; margin-bottom: 10px; }
.guide-note { font-size: 13px; color: #888; margin: 4px 0 12px; }
.guide-item { padding: 10px 0; border-top: 1px solid #f0f0f0; }
.guide-item:first-of-type { border-top: none; }
.guide-item-head { font-size: 14px; color: #666; margin-bottom: 4px; }
.guide-task { font-size: 14px; color: #555; margin-bottom: 6px; }
.guide-script { font-size: 15px; color: #222; line-height: 1.6; }
.guide-script-label { font-weight: 600; color: #3a6b4c; }
.guide-conditions { margin-top: 14px; padding-top: 10px; border-top: 1px dashed #ddd; }
.guide-conditions h4 { font-size: 14px; color: #a66; margin: 0 0 8px; }

/* 问卷模式：页面加宽到 1100px，给最多选项的量表（MSBS-8，7 个选项）留出一排摆下的空间。 */
.qpage { max-width: 1100px; margin: 0 auto; padding: 32px 24px 80px; }
.qintro { font-size: 17px; color: #444; background: #fff; border-radius: 10px; padding: 18px 22px; margin-bottom: 20px; }
.qbanner-error {
    background: #ffe1e1; color: #a30000; font-size: 16px; font-weight: 600;
    padding: 12px 18px; border-radius: 8px; margin-bottom: 16px; position: sticky; top: 8px;
}
.qblock { margin-bottom: 28px; }
.qitem {
    background: #fff; border-radius: 10px; padding: 16px 20px; margin-bottom: 10px;
    border: 2px solid transparent;
}
.qitem.unanswered-flag { border-color: #e05555; background: #fff6f6; }
.qinstruction { font-size: 16px; color: #666; margin: 18px 0 10px; }
.qrow-text { font-size: 20px; font-weight: 700; color: #111; line-height: 1.4; margin-bottom: 12px; }
.qoptions { display: flex; flex-wrap: nowrap; gap: 10px 26px; overflow-x: auto; }
.qoptions label { font-size: 18px; display: flex; align-items: center; gap: 6px; cursor: pointer; white-space: nowrap; }
.qmulti { flex-direction: column; overflow-x: visible; gap: 8px; }
.numeric-scale { gap: 14px; }
.num-cell { flex-direction: column; font-size: 14px; width: 92px; text-align: center; }
.num-n { font-size: 21px; font-weight: 700; }
.num-label { font-size: 14px; color: #666; white-space: nowrap; }
.qnumber { font-size: 18px; padding: 8px; width: 120px; }
.slider-wrap { padding: 6px 4px; }
.qslider { width: 100%; }
.slider-value { text-align: center; font-size: 18px; font-weight: bold; margin-top: 4px; }
.slider-labels { display: flex; justify-content: space-between; font-size: 13px; color: #777; margin-top: 2px; }
.qnav { display: flex; gap: 12px; margin-top: 24px; justify-content: flex-end; }
"""


def esc(s):
    return html.escape("" if s is None else str(s))


def shell(title, body_html):
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>%s</style>
</head><body>%s</body></html>""" % (esc(title), CSS, body_html)


def timer_block(started_at, duration_sec, midpoint_sec=None, midpoint_message=None, timeup_message=None):
    """返回 (计时器显示区 HTML, 配套 <script>)。duration_sec 为 None 时不显示计时器。"""
    if duration_sec is None:
        return "", ""
    timer_cfg = {
        "startedAt": started_at * 1000,
        "durationSec": duration_sec,
        "midpointSec": midpoint_sec,
        "midpointMessage": midpoint_message,
        "timeupMessage": timeup_message or "已到预定时间",
    }
    html_part = (
        '<div class="midpoint-banner" id="midpoint-banner"></div>'
        '<div class="timeup-banner" id="timeup-banner"></div>'
    )
    script_part = """<script>
const TIMER = __TIMER_CFG__;
function pad(n) { return String(n).padStart(2, "0"); }
function fmt(sec) {
    sec = Math.max(0, Math.round(sec));
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return h > 0 ? (pad(h) + ":" + pad(m) + ":" + pad(s)) : (pad(m) + ":" + pad(s));
}
function tick() {
    const elapsedSec = (Date.now() - TIMER.startedAt) / 1000;
    const timerEl = document.getElementById("timer-display");
    if (timerEl) {
        timerEl.textContent = "已用时 " + fmt(elapsedSec);
        timerEl.classList.toggle("overtime", elapsedSec >= TIMER.durationSec);
    }
    const mid = document.getElementById("midpoint-banner");
    if (mid && TIMER.midpointSec != null) {
        if (elapsedSec >= TIMER.midpointSec && elapsedSec < TIMER.durationSec) {
            mid.style.display = "block";
            mid.textContent = TIMER.midpointMessage;
        } else {
            mid.style.display = "none";
        }
    }
    const up = document.getElementById("timeup-banner");
    if (up) {
        if (elapsedSec >= TIMER.durationSec) {
            up.style.display = "block";
            const over = elapsedSec - TIMER.durationSec;
            up.textContent = TIMER.timeupMessage + "（已超出 " + fmt(over) + "）";
        } else {
            up.style.display = "none";
        }
    }
}
setInterval(tick, 1000);
tick();
</script>""".replace("__TIMER_CFG__", json.dumps(timer_cfg, ensure_ascii=False))
    return html_part, script_part


def top_bar(state, page_number, total=15):
    started_at = state.get("page_started_at")
    duration_sec = None
    page_id = state["current_page"]
    page_def = flow.PAGES.get(page_id, {})
    timer_key = page_def.get("timer_key")
    if timer_key:
        duration_sec = state["durations_sec"].get(timer_key)
    timer_html = '<span class="timer" id="timer-display"></span>' if duration_sec else ""
    page_label = ("%s / %s" % (page_number, total)) if page_number else "结束页"
    mode_flag = (" · 测试模式" if config.MODE == "test" else " · 预实验模式" if config.MODE == "pilot" else "")
    return """<div class="topbar">
<div>被试编号：%s<span class="mode-flag">%s</span></div>
<div>%s</div>
%s
</div>""" % (esc(state["participant_id"]), esc(mode_flag), esc(page_label), timer_html)


def instruction_block(text):
    if not text:
        return ""
    return '<h3 class="section-label">提示语</h3><div class="instruction">%s</div>' % esc(text)


def checklist_block(items, name="checked"):
    if not items:
        return ""
    rows = "".join(
        '<label><input type="checkbox" name="%s" value="%d"> %s</label>' % (name, i, esc(item))
        for i, item in enumerate(items)
    )
    return '<h3 class="section-label">任务确认单</h3><div class="checklist">%s</div>' % rows


def notes_block():
    return """<h3 class="section-label">实验记录</h3><div class="notes-box">
<textarea id="notes" name="notes" placeholder="异常情况、被试反应等"></textarea>
</div>"""


def screening_summary_block(answers):
    """问卷 A 筛查多选题的结果 + 给实验员的建议，用于第 3 页判定结果确认。"""
    lines, suggestion = judging.a_screening_summary(answers)
    lines_html = "<br>".join(esc(l) for l in lines)
    return '<div class="judging-box"><strong>问卷 A 筛查结果</strong><br>%s' \
           '<span class="suggestion">%s</span></div>' % (lines_html, esc(suggestion))


def stait_summary_block(total, classification):
    """T0 的 STAI-T 总分与焦虑分类，用于第 11 页揭晓组别。"""
    if total is None:
        return '<div class="judging-box">T0 的 STAI-T 尚未完整作答，无法计算总分。</div>'
    return '<div class="judging-box"><strong>T0 · STAI-T 焦虑特质总分</strong><br>' \
           '总分 %s 分（以 %s 分为界，&gt;= 为高焦虑）<span class="suggestion">分类：%s</span></div>' % (
               esc(total), esc(config.STAI_T_CUTOFF), esc(classification),
           )


def _render_guide_item(item):
    head = "<b>%s</b> " % esc(item["code"]) if item.get("code") else ""
    parts = ['<div class="guide-item"><div class="guide-item-head">%s%s</div>' % (head, esc(item["when"]))]
    parts.append('<div class="guide-task">%s</div>' % esc(item["task"]))
    if "script" in item:
        parts.append('<div class="guide-script">%s</div>' % esc(item["script"]))
    else:
        parts.append('<div class="guide-script"><span class="guide-script-label">尝试前：</span>%s</div>'
                      % esc(item["before_script"]))
        parts.append('<div class="guide-script"><span class="guide-script-label">结果出现后：</span>%s</div>'
                      % esc(item["after_script"]))
    parts.append("</div>")
    return "".join(parts)


def _render_guide_section(section):
    items_html = "".join(_render_guide_item(i) for i in section["items"])
    note_html = '<p class="guide-note">%s</p>' % esc(section["note"]) if section.get("note") else ""
    conditions_html = ""
    if section.get("conditions"):
        cond_items = "".join(
            '<div class="guide-item"><div class="guide-item-head">触发：%s</div>'
            '<div class="guide-task">%s</div><div class="guide-script">%s</div></div>' % (
                esc(c["trigger"]), esc(c["task"]), esc(c["script"]),
            )
            for c in section["conditions"]
        )
        conditions_html = '<div class="guide-conditions"><h4>条件提示（仅在对应情况出现时使用）</h4>%s</div>' % cond_items
    closing_html = '<p class="guide-note">%s</p>' % esc(section["closing_note"]) if section.get("closing_note") else ""
    return """<details class="guide-section">
<summary>%s、%s</summary>
%s%s%s%s
</details>""" % (esc(section["code"]), esc(section["title"]), note_html, items_html, conditions_html, closing_html)


def practice_guide_block():
    """练习场（第 6 页）用的"按情境展开"指导语：原生 <details> 折叠，默认全部收起，
    实验员走到哪个环节再点开哪个，不用提前通读整份文档。"""
    principles_html = "".join("<li>%s</li>" % esc(p) for p in practice_script.USAGE_PRINCIPLES)
    sections_html = "".join(_render_guide_section(s) for s in practice_script.SECTIONS)
    return """<div class="guide-wrap">
<h3 class="section-label">情境指导语（按需展开，不用提前通读）</h3>
<ul class="guide-principles">%s</ul>
%s
<div class="note">%s</div>
</div>""" % (principles_html, sections_html, esc(practice_script.TIMING_NOTE))


def stage_heading(number, title):
    """页面正文顶部的大字当前阶段标注，和浏览器标签页标题分开，确保一看就知道在第几步。"""
    text = ("第 %s 页 · %s" % (number, title)) if number else title
    return '<h2 class="stage-heading">%s</h2>' % esc(text)


# 清单里只要有一项没勾，"完成该阶段"按钮就不能点；没有清单的页面（比如问卷占位页）
# 按钮始终可点。所有带 complete-btn 的页面都插这一段。
COMPLETE_GATE_SCRIPT = """<script>
(function () {
    var boxes = document.querySelectorAll('input[name="checked"]');
    var btn = document.getElementById("complete-btn");
    if (!btn) return;
    function update() {
        var allChecked = true;
        boxes.forEach(function (cb) { if (!cb.checked) allChecked = false; });
        btn.disabled = !allChecked;
    }
    boxes.forEach(function (cb) { cb.addEventListener("change", update); });
    update();
})();
</script>"""


def render_task_page(state, page_id, page_def):
    number = page_def.get("number")
    body = top_bar(state, number)
    body += '<div class="wrap">'
    body += stage_heading(number, page_def["title"])
    if page_def.get("note"):
        body += '<div class="note">%s</div>' % esc(page_def["note"])
    body += instruction_block(page_def.get("instruction"))
    if page_id == "practice":
        body += practice_guide_block()

    duration_sec = None
    timer_key = page_def.get("timer_key")
    midpoint_sec = midpoint_message = None
    if timer_key:
        duration_sec = state["durations_sec"].get(timer_key)
        midpoint = page_def.get("midpoint")
        if midpoint:
            midpoint_key, midpoint_message = midpoint
            midpoint_sec = state["durations_sec"].get(midpoint_key)
    timer_html, timer_script = timer_block(
        state["page_started_at"], duration_sec, midpoint_sec, midpoint_message,
        page_def.get("timeup_message"),
    )
    body += timer_html

    body += '<form method="post" action="/complete">'
    body += checklist_block(page_def.get("checklist", []))
    body += notes_block()
    back_btn = '<button type="submit" formaction="/back" class="secondary" formnovalidate>上一步</button>' \
        if config.MODE == "test" and len(state["history"]) > 1 else ""
    complete_label = page_def.get("complete_label", "完成该阶段")
    body += '<div class="actions"><button type="submit" id="complete-btn">%s</button>%s</div>' % (
        esc(complete_label), back_btn,
    )
    body += "</form></div>"
    body += timer_script
    body += COMPLETE_GATE_SCRIPT
    return shell(page_def["title"], body)


def render_placeholder_page(state, page_id, page_def):
    number = page_def.get("number")
    body = top_bar(state, number)
    body += '<div class="wrap">'
    body += stage_heading(number, page_def["title"])
    body += '<div class="note">%s</div>' % esc(page_def["note"])
    body += '<form method="post" action="/complete">'
    body += notes_block()
    back_btn = '<button type="submit" formaction="/back" class="secondary" formnovalidate>上一步</button>' \
        if config.MODE == "test" and len(state["history"]) > 1 else ""
    body += '<div class="actions"><button type="submit" id="complete-btn">完成该阶段</button>%s</div>' % back_btn
    body += "</form></div>"
    body += COMPLETE_GATE_SCRIPT
    return shell(page_def["title"], body)


def render_verdict_page(state, page_def):
    number = page_def.get("number")
    body = top_bar(state, number)
    body += '<div class="wrap">'
    body += stage_heading(number, page_def["title"])
    body += '<div class="note">%s</div>' % esc(page_def["note"])
    a_answers = state.get("questionnaires", {}).get("A", {}).get("answers", {})
    body += screening_summary_block(a_answers)
    verdict = state.get("verdict")

    if verdict is None:
        body += '<div class="verdict-choices">'
        for key, opt in flow.VERDICT_OPTIONS.items():
            body += """<form class="inline" method="post" action="/verdict">
<input type="hidden" name="verdict" value="%s">
<button type="submit">%s</button></form>""" % (esc(key), esc(opt["label"]))
        body += "</div></div>"
        return shell(page_def["title"], body)

    opt = flow.VERDICT_OPTIONS[verdict]
    body += """<form class="inline" method="post" action="/verdict_reset">
<button type="submit" class="secondary" formnovalidate>重新选择（当前：%s）</button></form>""" % esc(opt["label"])
    body += instruction_block(opt["instruction"])
    body += '<form method="post" action="/complete">'
    body += checklist_block(opt.get("checklist", []))
    body += notes_block()
    back_btn = '<button type="submit" formaction="/back" class="secondary" formnovalidate>上一步</button>' \
        if config.MODE == "test" and len(state["history"]) > 1 else ""
    body += '<div class="actions"><button type="submit" id="complete-btn">完成该阶段</button>%s</div>' % back_btn
    body += "</form></div>"
    body += COMPLETE_GATE_SCRIPT
    return shell(page_def["title"], body)


def render_group_page(state):
    """第 11 页"揭晓组别"：先展示 T0 STAI-T 分类，再展示/完成分组（随机抽取或预实验手动选择）。"""
    page_def = flow.PAGES["reveal_group"]
    number = page_def.get("number")
    body = top_bar(state, number)
    body += '<div class="wrap">'
    body += stage_heading(number, page_def["title"])
    if page_def.get("note"):
        body += '<div class="note">%s</div>' % esc(page_def["note"])

    t0_answers = state.get("questionnaires", {}).get("T0", {}).get("answers", {})
    total = judging.stait_total_score(t0_answers)
    classification = judging.stait_classification(total)
    body += stait_summary_block(total, classification)

    group = state.get("group")
    if not group:
        if config.MODE == "pilot":
            body += '<div class="verdict-choices">'
            for cond in ("实验组", "对照组"):
                body += """<form class="inline" method="post" action="/group_manual">
<input type="hidden" name="condition" value="%s">
<button type="submit">%s</button></form>""" % (esc(cond), esc(cond))
            body += "</div></div>"
        else:
            body += '<div class="note">当前为简单随机分配（候选组号 1-4，各组号对应的条件见 config.py 的' \
                    ' GROUP_CONDITIONS）；未来正式版计划改为按 STAI-T 分层、一次性生成的随机分配表。</div>'
            body += """<form method="post" action="/group_random">
<div class="actions"><button type="submit">为本次被试随机分配组别</button></div></form></div>"""
        return shell(page_def["title"], body)

    body += """<form class="inline" method="post" action="/group_reset">
<button type="submit" class="secondary" formnovalidate>重新分配（当前：%s）</button></form>""" % esc(group)

    if state.get("group_method") == "manual":
        basis = "分组方式：预实验模式下由实验员手动选择。"
    else:
        basis = "分组方式：简单随机分配，候选组号 1-4 中本次抽到第 %s 号 → %s。" % (
            esc(state.get("group_code", "")), esc(group),
        )
    body += '<div class="note">%s</div>' % basis
    body += instruction_block(flow.GROUP_INSTRUCTIONS.get(group))

    body += '<form method="post" action="/complete">'
    body += checklist_block(page_def.get("checklist", []))
    body += notes_block()
    back_btn = '<button type="submit" formaction="/back" class="secondary" formnovalidate>上一步</button>' \
        if config.MODE == "test" and len(state["history"]) > 1 else ""
    body += '<div class="actions"><button type="submit" id="complete-btn">完成该阶段</button>%s</div>' % back_btn
    body += "</form></div>"
    body += COMPLETE_GATE_SCRIPT
    return shell(page_def["title"], body)


def render_end_page(state):
    page_def = flow.PAGES["end"]
    number = page_def.get("number")
    body = top_bar(state, number)
    body += '<div class="wrap">'
    body += stage_heading(number, page_def["title"])
    body += '<div class="instruction">本场流程已跑完，数据已保存。</div>'

    data_root = state["data_root"]
    participant_path = state_mod.state_path(data_root, state["participant_id"])
    q_csv_path = state_mod.questionnaire_csv_path(data_root)
    codebook_path = state_mod.questionnaire_codebook_path(data_root)
    log_csv_path = state_mod.log_csv_path(data_root)
    notes_path = state_mod.notes_txt_path(data_root, state["participant_id"])
    body += """<div class="note">
本场原始记录：%s<br>
本场实验记录文字（按页列出）：%s<br>
问卷总表（已自动更新，A/T0/T1/T2/T3 全部题目）：%s<br>
问卷总表列名对照（每列对应哪道题）：%s<br>
实验记录表（已自动更新）：%s
</div>""" % (esc(participant_path), esc(notes_path), esc(q_csv_path), esc(codebook_path), esc(log_csv_path))

    body += """<div class="checklist">
<p>被试编号：%s</p>
<p>判定结果：%s</p>
<p>组别：%s</p>
</div>""" % (
        esc(state["participant_id"]), esc(state.get("verdict") or "（未记录）"),
        esc(state.get("group") or "（未记录）"),
    )
    body += """<form method="post" action="/finish">
<div class="actions"><button type="submit">结束本场，返回设置页</button></div>
</form></div>"""
    return shell("结束页", body)


def render_settings_page(data_root_default, participant_id_default, durations_default, error=None):
    mode_label = {"formal": "正式", "test": "测试", "pilot": "预实验"}[config.MODE]
    body = '<div class="wrap">'
    body += "<h1>流程单系统 · 设置页</h1>"
    body += '<p class="mode-flag">当前运行模式：%s（在 config.py 里改 MODE 切换）</p>' % esc(mode_label)
    if error:
        body += '<div class="error-box">%s</div>' % esc(error)
    body += """<form class="settings-form" method="post" action="/start">
<label>数据存放路径</label>
<input type="text" name="data_root" value="%s">

<label>被试编号</label>
<input type="text" name="participant_id" value="%s">

<label>练习场时长（分钟）</label>
<input type="number" step="0.5" name="practice_min" value="%s">

<label>静息时长（分钟）</label>
<input type="number" step="0.5" name="rest_min" value="%s">

<label>担忧书写时长（分钟）</label>
<input type="number" step="0.5" name="writing_min" value="%s">

<label>担忧书写中途提示时间（分钟）</label>
<input type="number" step="0.5" name="writing_midpoint_min" value="%s">

<label>干预时长（分钟）</label>
<input type="number" step="0.5" name="intervention_min" value="%s">

<div class="actions"><button type="submit">开始实验</button></div>
</form></div>""" % (
        esc(data_root_default), esc(participant_id_default),
        durations_default["practice"] / 60, durations_default["rest"] / 60,
        durations_default["writing"] / 60, durations_default["writing_midpoint"] / 60,
        durations_default["intervention"] / 60,
    )
    return shell("设置页", body)
