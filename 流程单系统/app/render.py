"""HTML 渲染：所有页面共用的外壳、计时器脚本，以及各类页面的拼装。"""
import html
import json

import config
import flow
import judging
import practice_script
import randomization
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
.topbar .timer-plan { font-size: 15px; font-weight: normal; opacity: 0.85; margin-right: 14px; }
.wrap { max-width: 900px; margin: 0 auto; padding: 24px; }
.stage-heading { font-size: 20px; color: #555; margin: 0 0 16px; font-weight: 600; }
.section-label { font-size: 15px; color: #666; margin: 0 0 6px; font-weight: 600; }
.instruction {
    font-size: 26px; line-height: 1.6; background: #fff; border-radius: 10px;
    padding: 24px; margin-bottom: 16px; border-left: 6px solid #3a6b4c;
}
.note { font-size: 14px; color: #888; margin-bottom: 16px; }
.iv-group { font-size: 20px; font-weight: 700; margin: 20px 0 8px; }
.iv-q { background: #fff; border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; }
.iv-title { font-size: 15px; color: #888; margin-bottom: 6px; }
.iv-text { font-size: 20px; line-height: 1.6; }
.iv-follow { font-size: 17px; color: #555; margin-top: 6px; padding-left: 1.5em; }
.midpoint-banner, .timeup-banner {
    display: none; font-size: 20px; font-weight: bold; padding: 14px 20px;
    border-radius: 8px; margin-bottom: 16px;
}
.midpoint-banner { background: #fff3cd; color: #8a6d00; }
.timeup-banner { background: #ffe1e1; color: #a30000; }
.checklist { background: #fff; border-radius: 10px; padding: 16px 24px; margin-bottom: 16px; }
.checklist label { display: block; font-size: 17px; margin: 8px 0; }
/* 警示清单项：每项独占一行，浅红底 + 左侧深红竖条，深红加粗大字；上方可有警示区块标题 */
.checklist .warn-title { font-size: 24px; font-weight: 700; color: #8b0000; margin: 18px 0 6px; }
.checklist label.warn-item {
    display: block; font-size: 22px; font-weight: 700; color: #8b0000; line-height: 1.5;
    background: #ffe5e5; border-left: 8px solid #8b0000; border-radius: 6px;
    padding: 12px 16px; margin: 10px 0;
}
.checklist input.big-check { width: 24px; height: 24px; margin-right: 10px; vertical-align: middle; }
/* 结束页顶部的大号警示块 */
.end-warning {
    background: #ffe5e5; border-left: 8px solid #8b0000; border-radius: 8px;
    padding: 18px 22px; margin-bottom: 20px;
}
.end-warning .big { font-size: 28px; font-weight: 700; color: #8b0000; line-height: 1.5; }
.end-warning .small { font-size: 18px; color: #8b0000; margin-top: 8px; line-height: 1.6; }
button.end-finish-btn {
    font-size: 24px; font-weight: 700; padding: 18px 40px; background: #8b0000; color: #fff;
}
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
.resume-box {
    background: #fff3cd; border: 1px solid #ffe08a; border-radius: 10px;
    padding: 16px 20px; margin-bottom: 20px;
}
.resume-box p { margin: 0 0 10px; font-size: 15px; }
.resume-box .resume-note { font-size: 13px; color: #8a6d00; margin-top: 10px; margin-bottom: 0; }
.resume-box .btn {
    display: inline-block; background: #3a6b4c; color: #fff; text-decoration: none;
    padding: 10px 22px; border-radius: 8px; font-size: 16px;
}
.mode-flag { font-size: 12px; opacity: 0.8; }
.debug-bar {
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
    background: #c62828; color: #fff; padding: 8px 24px; font-size: 16px;
}
.debug-bar .debug-tag { font-weight: 800; font-size: 20px; letter-spacing: 2px; }
.debug-bar form { margin: 0; }
.debug-bar select { font-size: 15px; padding: 4px 8px; }
.debug-only-note { font-size: 13px; color: #999; margin-left: 12px; }
.debug-box {
    background: #fff; border-radius: 10px; padding: 16px 22px; margin: 16px 0;
    border-left: 6px solid #c62828;
}
.debug-box input[type=text] { font-size: 18px; padding: 8px; width: 120px; }
.radio-row label { display: block; font-size: 18px; margin: 8px 0; cursor: pointer; }
.judging-box {
    background: #fff; border-radius: 10px; padding: 16px 22px; margin-bottom: 16px;
    border-left: 6px solid #8a6d00; font-size: 15px; line-height: 1.7;
}
.judging-box .suggestion { display: block; font-weight: 700; color: #8a6d00; margin-top: 8px; }

/* 练习场：总原则 + 五部分要点卡片，全部直接展开，不折叠，纵向排列，靠拖动屏幕查看 */
.guide-wrap { margin-bottom: 16px; }
.guide-principles { background: #fff; border-radius: 10px; padding: 14px 20px; margin: 0 0 14px; font-size: 16px; color: #555; line-height: 1.7; list-style: disc; }
.guide-grid { display: flex; flex-direction: column; gap: 14px; }
.guide-card { background: #fff; border-radius: 10px; padding: 18px 22px; }
.guide-card h4 { margin: 0 0 10px; font-size: 20px; font-weight: 700; color: #333; }
.guide-points { margin: 0 0 10px; padding-left: 22px; font-size: 17px; color: #333; line-height: 1.6; }
.guide-points li { margin: 4px 0; }
.guide-script { font-size: 15px; color: #777; line-height: 1.6; }

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
.qinstruction {
    font-size: 19px; font-weight: 700; color: #222; line-height: 1.5;
    margin: 20px 0 12px; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "SimHei", sans-serif;
}
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


def timer_plan_text(stage_sec, lead_sec):
    """计时器旁的预定说明，例如 "预定 05:20（含念指导语 00:20）"。没有加时项时返回空串，行为与原来一致。"""
    if not lead_sec:
        return ""
    return "预定 %s（含念指导语 %s）" % (fmt_mmss(stage_sec + lead_sec), fmt_mmss(lead_sec))


def fmt_mmss(sec):
    sec = max(0, int(round(sec)))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return ("%02d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))


def top_bar(state, page_number, total=17):
    started_at = state.get("page_started_at")
    duration_sec = None
    page_id = state["current_page"]
    page_def = flow.PAGES.get(page_id, {})
    timer_key = page_def.get("timer_key")
    plan_html = ""
    if timer_key:
        duration_sec = state["durations_sec"].get(timer_key)
        if duration_sec:
            plan = timer_plan_text(duration_sec, flow.timer_lead_sec(page_def))
            if plan:
                plan_html = '<span class="timer-plan">%s</span>' % esc(plan)
    timer_html = ('<div>%s<span class="timer" id="timer-display"></span></div>' % plan_html) if duration_sec else ""
    page_label = ("%s / %s" % (page_number, total)) if page_number else "结束页"
    return """<div class="topbar">
<div>被试编号：%s</div>
<div>%s</div>
%s
</div>""" % (esc(state["participant_id"]), esc(page_label), timer_html)


def is_debug(state):
    return state.get("mode") == "debug"


def debug_bar(state):
    """调整模式专用：红色"调整模式"标识 + "跳到第 N 页"下拉菜单。实验模式不出现。"""
    current = state["current_page"]
    options = ""
    for pid in flow.PAGE_ORDER:
        pdef = flow.PAGES[pid]
        options += '<option value="%s"%s>第 %s 页 · %s</option>' % (
            esc(pid), " selected" if pid == current else "", esc(pdef["number"]), esc(pdef["title"]),
        )
    return """<div class="debug-bar"><span class="debug-tag">调整模式</span>
<form method="post" action="/jump"><label>跳到第 N 页：
<select name="page_id" onchange="this.form.submit()">%s</select></label></form></div>""" % options


def with_debug_bar(html_text, state):
    """给任意整页 HTML（含问卷页、空白页）在 <body> 后插入调整模式条；实验模式原样返回。"""
    if not is_debug(state):
        return html_text
    return html_text.replace("<body>", "<body>" + debug_bar(state), 1)


def back_button(state):
    """"上一步"按钮：只在调整模式下出现。"""
    if is_debug(state) and len(state["history"]) > 1:
        return '<button type="submit" formaction="/back" class="secondary" formnovalidate>上一步</button>'
    return ""


def gate_script(state):
    """实验模式：清单没勾完"完成该阶段"按钮灰掉；调整模式不拦。"""
    return "" if is_debug(state) else COMPLETE_GATE_SCRIPT


def instruction_block(text):
    if not text:
        return ""
    return '<h3 class="section-label">提示语</h3><div class="instruction">%s</div>' % esc(text)


_GROUP_DISPLAY = {"实验组": "交互组", "对照组": "观看组"}


def interview_block(state):
    """第 16 页访谈问题：只显示本被试组别的版本；没有组别时（调整模式未设定）两组都显示。"""
    group = state.get("group")
    groups = [group] if group in _GROUP_DISPLAY else ["实验组", "对照组"]
    html = '<h3 class="section-label">访谈问题</h3>'
    for g in groups:
        if len(groups) > 1:
            html += '<div class="iv-group">%s</div>' % esc(_GROUP_DISPLAY[g])
        for item in flow.INTERVIEW_QUESTIONS:
            question, followups = item[g]
            html += '<div class="iv-q"><div class="iv-title">%s</div><div class="iv-text">%s</div>' % (
                esc(item["title"]), esc(question))
            for f in followups:
                html += '<div class="iv-follow">追问：%s</div>' % esc(f)
            html += "</div>"
    return html


def checklist_block(items, name="checked", start=0):
    """清单渲染。items 可以是字符串或 flow.warn() 的 dict；start 是这一段第一项在整页里的序号。"""
    items = flow.normalize_list(items)
    if not items:
        return ""
    parts = []
    last_title = None
    for offset, item in enumerate(items):
        i = start + offset
        if item["warning"]:
            if item["title"] and item["title"] != last_title:
                parts.append('<div class="warn-title">⚠ %s</div>' % esc(item["title"]))
            last_title = item["title"]
            parts.append('<label class="warn-item"><input type="checkbox" class="big-check" name="%s" value="%d"> ⚠ %s</label>'
                         % (name, i, esc(item["text"])))
        else:
            last_title = None
            parts.append('<label><input type="checkbox" name="%s" value="%d"> %s</label>'
                         % (name, i, esc(item["text"])))
    # 整段都是警示项时，警示区块标题已经代替了"任务确认单"的标题。
    heading = ""
    if any(not item["warning"] for item in items):
        heading = '<h3 class="section-label">任务确认单</h3>'
    return heading + '<div class="checklist">%s</div>' % "".join(parts)


def sections_block(page_def, fmt=None):
    """按 flow.sections_of 的顺序渲染：提示语段念给被试，清单段出勾选框（序号接着往下数）。"""
    parts = []
    idx = 0
    for sec in flow.sections_of(page_def):
        if "say" in sec:
            parts.append(instruction_block(sec["say"]))
        else:
            items = flow.normalize_list(sec.get("checklist", []), fmt)
            parts.append(checklist_block(items, start=idx))
            idx += len(items)
    return "".join(parts)


NOTES_AUTOSAVE_SCRIPT = """<script>
(function () {
    var ta = document.getElementById("notes");
    if (!ta) return;
    var pageId = ta.dataset.pageId, timer = null, last = ta.value;
    function send() {
        timer = null;
        if (ta.value === last) return;
        last = ta.value;
        var body = new URLSearchParams({page_id: pageId, notes: ta.value});
        fetch("/autosave_notes", {method: "POST", body: body, keepalive: true}).catch(function () { last = null; });
    }
    ta.addEventListener("input", function () {
        if (timer) clearTimeout(timer);
        timer = setTimeout(send, 1000);   // 停止输入约 1 秒后保存
    });
    ta.addEventListener("blur", send);
})();
</script>"""


def notes_block(state):
    """实验记录文字框，预填该页已实时保存的草稿（刷新、续接后文字还在）；停止输入约 1 秒自动保存。"""
    page_id = state["current_page"]
    draft = state.get("drafts", {}).get(page_id, "")
    return """<h3 class="section-label">实验记录</h3><div class="notes-box">
<textarea id="notes" name="notes" data-page-id="%s" placeholder="异常情况、被试反应等">%s</textarea>
</div>%s""" % (esc(page_id), esc(draft), NOTES_AUTOSAVE_SCRIPT)


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


def _render_guide_card(section):
    points_html = "".join("<li>%s</li>" % esc(p) for p in section["points"])
    return """<div class="guide-card">
<h4>%s</h4>
<ul class="guide-points">%s</ul>
<div class="guide-script">参考说法：%s</div>
</div>""" % (esc(section["title"]), points_html, esc(section["script"]))


def practice_guide_block():
    """练习场（第 6 页）指导语：总原则 + 五部分要点卡片，全部直接展开、纵向排列，不折叠，
    靠拖动屏幕查看，不追求一页堆满。"""
    principles_html = "".join("<li>%s</li>" % esc(p) for p in practice_script.PRINCIPLES)
    cards_html = "".join(_render_guide_card(s) for s in practice_script.SECTIONS)
    return """<div class="guide-wrap">
<ul class="guide-principles">%s</ul>
<div class="guide-grid">%s</div>
</div>""" % (principles_html, cards_html)


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


PREP_CSS = """
.prep-card { background: #fff; border-radius: 12px; padding: 22px 28px; margin-bottom: 20px; }
.prep-card h2 { font-size: 22px; font-weight: 700; margin: 0 0 14px; color: #222; }
.prep-card label.prep-item { display: block; font-size: 18px; line-height: 1.6; margin: 14px 0 6px; }
.prep-card label.prep-item input { width: 20px; height: 20px; margin-right: 10px; vertical-align: -3px; }
.prep-card details { margin: 0 0 12px 32px; }
.prep-card details > summary { font-size: 14px; color: #888; cursor: pointer; }
.prep-card details > .prep-body { font-size: 16px; line-height: 1.7; color: #333; margin-top: 8px; }
.prep-card .prep-body p { margin: 8px 0; }
.prep-card .prep-body .path { font-family: Menlo, Consolas, monospace; font-size: 15px; word-break: break-all; }
.prep-card table { border-collapse: collapse; margin: 10px 0; font-size: 16px; }
.prep-card th, .prep-card td { border: 1px solid #ddd; padding: 6px 14px; text-align: left; }
.prep-card th { background: #f4f4f4; }
"""


def _prep_item(text, fold_summary=None, fold_body=""):
    html = '<label class="prep-item"><input type="checkbox" name="checked" value="%d"> %s</label>' % (
        _prep_item.n, esc(text))
    _prep_item.n += 1
    if fold_summary:
        html += '<details><summary>%s</summary><div class="prep-body">%s</div></details>' % (
            esc(fold_summary), fold_body)
    return html


def _prep_card(title, inner):
    return '<div class="prep-card"><h2>%s</h2>%s</div>' % (esc(title), inner)


def render_prep_page():
    """设置页之前的"设备准备检查"：不是某个被试的页面，不计入 flow.PAGES 编号。
    每次开始新的一天/新开软件至少确认一次（本次服务进程运行期间只需要一次，不是
    每个被试都来一遍），确认过才放行到设置页。2026-11-04 加，起因是真机测试时
    防火墙/VPN 把网络卡死、实验中途被迫重启电脑。2026-11-07 改成 5 张卡片，
    每个确认项一行，提示折叠在对应项下面。"""
    _prep_item.n = 0
    modes = ("experiment", "debug")
    dirs_html = "".join(
        '<p>%s：<span class="path">%s</span></p>'
        % (esc(config.MODE_LABEL[m]), esc(state_mod.physio_data_dir(m))) for m in modes)
    tpl_html = "".join(
        '<p>%s：<span class="path">%s</span></p>'
        % (esc(config.MODE_LABEL[m]), esc(config.LABRECORDER_FILENAME_TEMPLATE[m])) for m in modes)

    cards = []
    cards.append(_prep_card("网络检查", _prep_item(
        "电脑已关闭所有防火墙和 VPN（包括但不限于 LuLu、Surfshark）",
        "为什么必须关",
        "<p>先关再连热点。上次预实验就是这类软件在连热点时把网络卡死，实验中途被迫重启电脑。</p>")))

    cards.append(_prep_card("设备连接",
        _prep_item("手机热点已开启")
        + _prep_item("电脑和 SensorBridge / PolarBridge 所在设备都连上了同一个热点")
        + _prep_item(
            "SensorBridge 的 UDP 已设置",
            "自动连不上时：查本机 IP，填进 SensorBridge 的 UDP 设置",
            "<p><b>Windows</b>：按 Win+R，输入 cmd 回车打开命令提示符，输入 ipconfig 回车。找正在用的那个"
            "网络（连的是热点，一般是“无线局域网适配器”）下面的“IPv4 地址”那一行，形如 192.168.x.x，"
            "把这个填进 SensorBridge 的 UDP 设置里。</p>"
            "<p><b>Mac</b>：“系统设置 → 网络”，点当前连接的 Wi-Fi（热点），右边会直接显示 IP 地址；"
            "或者打开“终端”，输入 ipconfig getifaddr en0 回车（Wi-Fi 一般是 en0，没反应就换成 en1 再试一次）。</p>")))

    cards.append(_prep_card("iPad 设置",
        _prep_item("iPad 屏幕亮度已设为 90%")
        + _prep_item("iPad 音量已设为 80%")))

    cards.append(_prep_card("LabRecorder 数据保存",
        _prep_item("LabRecorder 的保存路径（Study Root）已设置", "保存到哪里", dirs_html)
        + _prep_item("BIDS 选项已关闭")
        + _prep_item(
            "文件名模板已设置", "模板怎么写",
            tpl_html
            + "<p>斜杠表示子文件夹，文件应落在 physio 目录下的 sub-P###/ 文件夹里；模板里不含 session"
              "（每人只来一次）和分组（录制开始时还不知道分组，分组看 log.csv 的 group 列）。</p>")))

    marker_table = (
        "<table><tr><th>阶段</th><th>开始</th><th>结束</th></tr>"
        "<tr><td>练习场</td><td>训练开始（下方列表）</td><td>训练结束（下方列表）</td></tr>"
        "<tr><td>静息基线</td><td>基线开始（上方按钮）</td><td>基线结束（下方列表）</td></tr>"
        "<tr><td>担忧书写</td><td>诱导开始（上方按钮）</td><td>诱导结束（上方按钮）</td></tr>"
        "<tr><td>干预</td><td>干预开始（上方按钮）</td><td>干预结束（上方按钮）</td></tr>"
        "<tr><td>干预后静息</td><td>干预后静息开始（下方列表）</td><td>干预后静息结束（下方列表）</td></tr>"
        "</table>")
    cards.append(_prep_card("事件标记", _prep_item(
        "SensorBridge 已添加 5 个自定义事件：训练开始、训练结束、基线结束、干预后静息开始、干预后静息结束",
        "10 个标记在哪里点",
        "<p>SensorBridge 上方有 5 个自带按钮（基线开始、诱导开始、诱导结束、干预开始、干预结束），"
        "其余 5 个在下方自定义事件列表里（列表里如果还有以前加的“诱导后静息开始/结束”，已不再使用，可以删掉）。打标记时要在上方按钮和下方列表之间来回点，不是按屏幕顺序连续点。</p>"
        + marker_table
        + "<p>每个标记在对应阶段真正开始或结束的那一刻点，点完看一眼确认记录的是哪个。"
          "预实验中曾把静息基线误点成“诱导开始”。</p>")))

    cards.append(_prep_card("编号设置", _prep_item(
        "已知悉：VN 里被试编号从 1 开始、LabRecorder 从 0 开始，两者差 1；后续处理数据时按 "
        "LabRecorder 的编号 + 1 对齐")))

    body = "<style>%s</style>" % PREP_CSS
    body += '<div class="wrap">'
    body += "<h1>流程单系统 · 准备检查</h1>"
    body += ('<div class="note">每次开始新的一天、或者重新打开这个软件，先把下面这些都弄好、'
             '勾完，才能进入设置页开始被试。已经在跑的被试不会再弹这个页面，不用每个被试都'
             '重新确认一遍。</div>')
    body += "".join(cards)
    body += '<form method="post" action="/prep_confirm">'
    body += '<div class="actions"><button type="submit" id="complete-btn">都准备好了，进入设置页</button></div>'
    body += '</form></div>'
    body += COMPLETE_GATE_SCRIPT
    return shell("准备检查", body)


def render_task_page(state, page_id, page_def):
    number = page_def.get("number")
    body = top_bar(state, number)
    body += '<div class="wrap">'
    body += stage_heading(number, page_def["title"])
    if page_def.get("note"):
        body += '<div class="note">%s</div>' % esc(page_def["note"])
    if "sections" not in page_def:
        body += instruction_block(page_def.get("instruction"))
    if page_id == "practice":
        body += practice_guide_block()
    if page_id == "post_interview":
        body += interview_block(state)

    duration_sec = None
    timer_key = page_def.get("timer_key")
    midpoint_sec = midpoint_message = None
    if timer_key:
        duration_sec = state["durations_sec"].get(timer_key)
        if duration_sec is not None:
            # 判定点 = 阶段时长 + 念指导语加时；中途提示点 = 中途时间 + 同一页的加时。
            lead_sec = flow.timer_lead_sec(page_def)
            duration_sec = duration_sec + lead_sec
        midpoint = page_def.get("midpoint")
        if midpoint:
            midpoint_key, midpoint_message = midpoint
            midpoint_sec = state["durations_sec"].get(midpoint_key)
            if midpoint_sec is not None:
                midpoint_sec = midpoint_sec + flow.timer_lead_sec(page_def)
    timer_html, timer_script = timer_block(
        state["page_started_at"], duration_sec, midpoint_sec, midpoint_message,
        page_def.get("timeup_message"),
    )
    body += timer_html

    fmt = None
    if page_id == "check_signal":
        fmt = {"xdf_name": state_mod.xdf_filename(state["participant_id"], state["mode"])}

    body += '<form method="post" action="/complete">'
    if "sections" in page_def:
        body += sections_block(page_def, fmt)
    else:
        body += checklist_block(flow.flat_checklist(page_def, fmt))
    body += notes_block(state)
    back_btn = back_button(state)
    complete_label = page_def.get("complete_label", "完成该阶段")
    body += '<div class="actions"><button type="submit" id="complete-btn">%s</button>%s</div>' % (
        esc(complete_label), back_btn,
    )
    body += "</form></div>"
    body += timer_script
    body += gate_script(state)
    return shell(page_def["title"], body)


def render_placeholder_page(state, page_id, page_def):
    number = page_def.get("number")
    body = top_bar(state, number)
    body += '<div class="wrap">'
    body += stage_heading(number, page_def["title"])
    body += '<div class="note">%s</div>' % esc(page_def["note"])
    body += '<form method="post" action="/complete">'
    body += notes_block(state)
    back_btn = back_button(state)
    body += '<div class="actions"><button type="submit" id="complete-btn">完成该阶段</button>%s</div>' % back_btn
    body += "</form></div>"
    body += gate_script(state)
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
    body += notes_block(state)
    back_btn = back_button(state)
    body += '<div class="actions"><button type="submit" id="complete-btn">完成该阶段</button>%s</div>' % back_btn
    body += "</form></div>"
    body += gate_script(state)
    return shell(page_def["title"], body)


def _randomization_preview_html(state, total):
    """调整模式专用：随机分组预览（只显示，不写入）+ 默认折叠的两张随机序列。"""
    data_root = state["data_root"]
    sequences = randomization.build_sequences()
    size = config.RANDOMIZATION_BLOCK_SIZE
    used = {st_: randomization.used_position_map(data_root, st_) for st_ in randomization.STRATA}
    out = '<p><strong>随机分组预览</strong>（只显示，不写入，不占用位置）：'
    if total is None:
        out += "T0 未提交，无法预览。</p>"
    else:
        stratum = randomization.stratum_of(total)
        label = randomization.STRATUM_LABEL[stratum]
        try:
            pos, cond = randomization.assign_for(stratum, list(used[stratum]), sequences)
            out += "若在实验模式下，本被试将取 %s层第 %d 位 → %s（STAI-T 总分 %s）。</p>" % (
                esc(label), pos, esc(cond), esc(total))
        except randomization.RandomizationError as e:
            out += "若在实验模式下，本被试将无法取号：%s</p>" % esc(e)
    out += "<details><summary>两张随机序列（调试用）</summary>"
    for stratum in randomization.STRATA:
        out += "<p><strong>%s层</strong></p>" % esc(randomization.STRATUM_LABEL[stratum])
        out += '<table border="1" cellpadding="4" style="border-collapse:collapse;font-size:14px">' \
               "<tr><th>位置</th><th>区组号</th><th>组别</th><th>已被使用（被试）</th></tr>"
        for i, cond in enumerate(sequences[stratum], start=1):
            out += "<tr><td>%d</td><td>%d</td><td>%s</td><td>%s</td></tr>" % (
                i, (i - 1) // size + 1, esc(cond), esc(used[stratum].get(i, "")))
        out += "</table>"
    out += "</details>"
    return out


def render_group_page(state):
    """第 11 页"揭晓组别"：先展示 T0 STAI-T 分类，再揭晓 T0 提交时已锁定的分层区组随机组别；调整模式另有手动设定与随机预览。"""
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
    debug = is_debug(state)
    rec = state.get("randomization")
    if not debug and not rec:
        # 实验模式但 T0 提交时没有取到号（位置用尽等）：不能揭晓、不能推进。
        reason = "本被试没有随机分组记录（T0 提交时未能取号）。"
        if total is not None:
            try:
                randomization.assign_for(
                    randomization.stratum_of(total),
                    randomization.used_positions(state["data_root"], randomization.stratum_of(total)),
                    randomization.build_sequences())
            except randomization.RandomizationError as e:
                reason = str(e)
        body += '<div style="font-size:32px;font-weight:bold;color:#c00;line-height:1.5;margin:16px 0">' \
                '无法分组：%s<br>请不要继续，联系研究者。</div>' % esc(reason)
        body += "</div>"
        return shell(page_def["title"], body)
    if not debug and rec:
        body += '<div class="judging-box"><strong>所在层：</strong>%s（STAI-T 总分 %s）%s</div>' % (
            esc(randomization.STRATUM_LABEL[rec["stratum"]]), esc(rec["stait_total"]),
            ('　<strong>组别：%s</strong>' % esc(group)) if group else "")
    if not group or debug:
        # 实验模式：只有"揭晓组别"按钮，揭晓后不能更改。调整模式：上半部分界面与实验模式相同
        # （按钮点了不执行），下面另有调整模式专用区。
        body += """<form method="post" action="/group_random">
<div class="actions"><button type="submit">揭晓组别</button>%s</div></form>""" % (
            '<span class="debug-only-note">调整模式下不执行</span>' if debug else "")
    if debug:
        body += '<div class="debug-box"><strong>调整模式专用 · 手动设定组别</strong>'
        body += '<p>当前组别：%s</p>' % (esc(group) if group else "（尚未设定）")
        body += """<form method="post" action="/group_set">
<label>输入 1 或 2（1 = 实验组，2 = 对照组）：<input type="text" name="group_value" maxlength="1" autocomplete="off"></label>
<button type="submit">设定组别</button></form>"""
        body += _randomization_preview_html(state, total)
        body += "</div>"
    if not group:
        if debug and len(state["history"]) > 1:
            body += '<form method="post">%s</form>' % back_button(state)
        body += "</div>"
        return shell(page_def["title"], body)

    method = state.get("group_method")
    if method == "debug_manual":
        basis = "分组方式：调整模式下手动设定（1 = 实验组，2 = 对照组）。"
    else:
        basis = "分层区组随机（按 STAI-T 分层，每层每 %d 人 %d:%d），组别已在 T0 提交时锁定。" % (
            config.RANDOMIZATION_BLOCK_SIZE, config.RANDOMIZATION_BLOCK_SIZE // 2,
            config.RANDOMIZATION_BLOCK_SIZE // 2)
    body += '<div class="note">%s</div>' % esc(basis)
    body += instruction_block(flow.GROUP_INSTRUCTIONS.get(group))

    body += '<form method="post" action="/complete">'
    body += checklist_block(page_def.get("checklist", []))
    body += notes_block(state)
    back_btn = back_button(state)
    body += '<div class="actions"><button type="submit" id="complete-btn">完成该阶段</button>%s</div>' % back_btn
    body += "</form></div>"
    body += gate_script(state)
    return shell(page_def["title"], body)


def render_end_page(state):
    page_def = flow.PAGES["end"]
    number = page_def.get("number")
    body = top_bar(state, number)
    body += '<div class="wrap">'
    body += stage_heading(number, page_def["title"])
    body += ('<div class="end-warning"><div class="big">⚠ 最后一步：务必点击下方「结束本场，返回设置页」按钮</div>'
             '<div class="small">不点击，这场实验不会被标记为结束，下一位被试开始时会出现续接提示。</div></div>')
    body += '<div class="instruction">本场流程已跑完，数据已保存。</div>'

    data_root = state["data_root"]
    mode = state["mode"]
    pid = state["participant_id"]
    participant_path = state_mod.state_path(data_root, pid, mode)
    q_csv_path = state_mod.questionnaire_csv_path(data_root, pid, mode)
    codebook_path = state_mod.questionnaire_codebook_path(data_root, pid, mode)
    log_csv_path = state_mod.log_csv_path(data_root, pid, mode)
    notes_path = state_mod.notes_txt_path(data_root, pid, mode)
    body += """<div class="note">
本场原始记录（state.json）：%s<br>
本场问卷表（A/T0/T1/T2/T3 全部题目；T3 含 T3a、T3b 两份）：%s<br>
本场问卷表列名对照（每列对应哪道题，与问卷表同一文件夹）：%s<br>
本场实验记录表：%s<br>
本场实验记录文字（按页列出）：%s
</div>""" % (esc(participant_path), esc(q_csv_path), esc(codebook_path), esc(log_csv_path), esc(notes_path))

    body += """<div class="checklist">
<p>被试编号：%s</p>
<p>判定结果：%s</p>
<p>组别：%s</p>
</div>""" % (
        esc(state["participant_id"]), esc(state.get("verdict") or "（未记录）"),
        esc(state.get("group") or "（未记录）"),
    )
    body += """<form method="post" action="/finish">
<div class="actions"><button type="submit" class="end-finish-btn">结束本场，返回设置页</button></div>
</form></div>"""
    return shell("结束页", body)


def render_finish_error_page(break_dirs, conflict_dirs, detail=""):
    """结束时 _break_ 文件夹改名失败：不重定向，直接显示错误，数据仍在 _break_ 文件夹里。"""
    li = lambda paths: "".join('<li><span style="font-family:Menlo,Consolas,monospace;word-break:break-all;">%s</span></li>' % esc(p) for p in paths) or "<li>（无）</li>"
    body = '<div class="wrap">'
    body += ('<h1 style="color:#c00;font-size:40px;">正式文件夹已存在，本场数据保留在 _break_ 文件夹中，'
             '未改名</h1>')
    body += '<div class="error-box"><p><b>_break_ 文件夹（本场数据在这里）：</b></p><ul>%s</ul>' % li(break_dirs)
    body += '<p><b>冲突的正式文件夹（已存在）：</b></p><ul>%s</ul>' % li(conflict_dirs)
    if detail:
        body += '<p>系统提示：%s</p>' % esc(detail)
    body += '</div>'
    body += '<p style="font-size:22px;font-weight:bold;">请联系研究者手动处理。</p>'
    body += '<p><a class="btn" href="/">返回设置页</a></p></div>'
    return shell("结束出错", body)


def render_settings_page(data_root_default, suggested_ids, durations_default, error=None, resume_info=None,
                         selected_mode=None, participant_id_value=None, data_root_missing=False,
                         saved_folder=None):
    """suggested_ids: {mode: 建议编号}，两种模式各一个；选了模式后由页面 JS 填入编号框。
    selected_mode / participant_id_value 用于校验失败后重新显示时保留用户已填的内容。"""
    body = '<div class="wrap">'
    body += "<h1>流程单系统 · 设置页</h1>"
    if saved_folder:
        body += ('<div style="background:#e3f6e3;color:#1b6e1b;padding:12px 16px;border-radius:8px;'
                 'margin-bottom:16px;font-size:18px;font-weight:bold;">上一场 %s 的数据已正式保存。</div>'
                 % esc(saved_folder))
    if resume_info:
        body += """<div class="resume-box">
<p>有一场还没结束的实验：被试编号 <b>%s</b>，停在<b>%s</b>。</p>
<a class="btn" href="/page">继续这场实验</a>
<p class="resume-note">不继续也没关系——下面照常填表单开始新的被试，这场的数据不会丢，
只是以后要接回来得找技术帮忙手动恢复。</p>
</div>""" % (esc(resume_info["participant_id"]), esc(resume_info["page_label"]))
    if data_root_missing:
        body += ('<div class="error-box" style="font-size:32px;font-weight:bold;color:#c00;">%s</div>'
                 % esc("找不到项目 data 文件夹，请手动填写路径"))
    if error and not (data_root_missing and error.startswith("找不到项目 data")):
        body += '<div class="error-box">%s</div>' % esc(error)
    mode_radios = "".join(
        '<label><input type="radio" name="mode" value="%s"%s> %s</label>' % (
            esc(m), " checked" if selected_mode == m else "", esc(config.MODE_LABEL[m]),
        )
        for m in ("experiment", "debug")
    )
    pid_value = participant_id_value if participant_id_value is not None else (
        suggested_ids.get(selected_mode, "") if selected_mode else "")
    body += """<form class="settings-form" method="post" action="/start" id="start-form">
<label>运行模式（必须选择）</label>
<div class="radio-row">%s</div>

<label>数据存放路径（项目 data 文件夹，含 formal/、pilot_and_test/）</label>
<input type="text" name="data_root" value="%s">

<label>被试编号</label>
<input type="text" name="participant_id" id="participant-id" value="%s">

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

<label>干预后静息时长（分钟）</label>
<input type="number" step="0.5" name="post_intervention_rest_min" value="%s">

<div class="actions"><button type="submit" id="start-btn"%s>开始实验</button></div>
</form></div>
<script>
(function () {
    var SUGGESTED = __SUGGESTED__;
    var radios = document.querySelectorAll('input[name="mode"]');
    var pid = document.getElementById("participant-id");
    var btn = document.getElementById("start-btn");
    function selected() {
        for (var i = 0; i < radios.length; i++) if (radios[i].checked) return radios[i].value;
        return null;
    }
    function update() { btn.disabled = selected() === null; }
    radios.forEach(function (r) {
        r.addEventListener("change", function () {
            pid.value = SUGGESTED[r.value] || "";
            update();
        });
    });
    update();
})();
</script>""" % (
        mode_radios, esc(data_root_default), esc(pid_value),
        durations_default["practice"] / 60, durations_default["rest"] / 60,
        durations_default["writing"] / 60, durations_default["writing_midpoint"] / 60,
        durations_default["intervention"] / 60,
        durations_default["post_intervention_rest"] / 60,
        "" if selected_mode else " disabled",
    )
    body = body.replace("__SUGGESTED__", json.dumps(suggested_ids, ensure_ascii=False))
    return shell("设置页", body)
