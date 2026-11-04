"""
问卷模式：页面版式（基于 scales.py 的内容拼成每份问卷的分页）+ 渲染 + 翻页前的
漏答校验。和任务页用的渲染器（render.py）是分开的，因为问卷页面要："只显示问卷"
（不带被试编号、模式标记这些实验员信息），而且校验粒度是"每一道题"而不是"一张
清单"。

存答案的字段名约定：
  矩阵量表（STAI-T/CNS/GAD-2/STAI-6/MSBS-8）每道题一个 key，
      形如 "<量表前缀>_<题号>"，值是选项下标（0 开始的字符串）。
  数字量表（注意题/意义题/迷恋与远离/IMI 感知选择）同样每题一个 key，值是用户选的数字（字符串）。
  滑块（VAS/FMS）一个 key，值是 0-100 / 0-20 的数字字符串；没拖动过就没有这个 key。
  多选（A2 筛查）一个 key，值是选中的选项下标列表。
  基本信息："A_age"、"A_gender"。
这套 key 就是以后导出问卷总表时的列名。
"""
import json

import scales
from render import esc, shell


def _items(prefix, scale):
    return [("%s_%d" % (prefix, i + 1), text) for i, text in enumerate(scale["items"])]


def _matrix_block(prefix, scale, instruction=None):
    return {
        "type": "matrix",
        "instruction": instruction if instruction is not None else scale["instruction"],
        "options": scale["options"],
        "items": _items(prefix, scale),
    }


def _numeric_block(prefix, scale, instruction=None):
    return {
        "type": "numeric",
        "instruction": instruction if instruction is not None else scale["instruction"],
        "scale_min": scale["scale_min"],
        "scale_max": scale["scale_max"],
        "scale_labels": scale["scale_labels"],
        "items": _items(prefix, scale),
    }


def _slider_block(key, spec, prompt=None):
    if prompt is not None:
        spec = {**spec, "prompt": prompt}
    return {"type": "slider", "key": key, "spec": spec}


def _multi_block(key, spec):
    return {"type": "multi", "key": key, "spec": spec}


def _basic_info_block():
    return {"type": "basic_info"}


def _fascination_combined_block():
    # 迷恋（5 题）+ 远离（2 题）放同一页，共用一句卷首指导语，题项不混排、先迷恋后远离。
    items = _items("T3_fascination", scales.FASCINATION) + _items("T3_away", scales.BEING_AWAY)
    return {
        "type": "numeric",
        "instruction": scales.FASCINATION["instruction"],
        "scale_min": scales.FASCINATION["scale_min"],
        "scale_max": scales.FASCINATION["scale_max"],
        "scale_labels": scales.FASCINATION["scale_labels"],
        "items": items,
    }


QUESTIONNAIRES = {
    "A": {
        "title": "问卷 A",
        "pages": [
            {
                "intro": "为了确保你能安全、舒适地参加本实验，请如实回答以下问题。你的回答只用于"
                         "确认今天是否适合参加，会严格保密。",
                "blocks": [
                    _basic_info_block(),
                    _multi_block("A_screen", scales.A2_SCREENING),
                    _matrix_block("A_gad2", scales.GAD2),
                ],
            },
        ],
    },
    "T0": {
        "title": "问卷 T0",
        "pages": [
            {"intro": None, "blocks": [_matrix_block("T0_stait", scales.STAI_T)]},
            {"intro": None, "blocks": [_matrix_block("T0_cns", scales.CNS)]},
        ],
    },
    "T1": {
        "title": "问卷 T1",
        "pages": [
            {
                "intro": None,
                "blocks": [
                    _matrix_block("T1_stai6", scales.STAI_6),
                    _slider_block("T1_vas", scales.ANXIETY_VAS),
                    _matrix_block("T1_msbs", scales.MSBS8),
                ],
            },
        ],
    },
    "T2": {
        # T1、T2、T3a 是完全相同的 15 题此刻状态块，指导语都用 scales.py 里的默认"此时此刻"。
        # T2 紧接书写、在诱导后静息之前填：此刻状态的题目随时间消退，先静息会让 T2 测到
        # 已部分恢复的焦虑。
        "title": "问卷 T2",
        "pages": [
            {
                "intro": None,
                "blocks": [
                    _matrix_block("T2_stai6", scales.STAI_6),
                    _slider_block("T2_vas", scales.ANXIETY_VAS),
                    _matrix_block("T2_msbs", scales.MSBS8),
                ],
            },
        ],
    },
    # T3 在流程里拆成 T3a、T3b 两份，中间夹干预后静息；题目键名仍用 T3_ 前缀，
    # 导出的 questionnaires.csv 与 codebook 里仍属于 T3（codebook_instrument）。
    "T3a": {
        # 干预结束后立即填的此刻状态块：与 T1、T2 完全相同的 15 题（STAI-6、焦虑 VAS、MSBS-8）。
        "title": "问卷 T3a",
        "codebook_instrument": "T3",
        "pages": [
            {
                "intro": None,
                "blocks": [
                    _matrix_block("T3_stai6", scales.STAI_6),
                    _slider_block("T3_vas", scales.ANXIETY_VAS),
                    _matrix_block("T3_msbs", scales.MSBS8),
                ],
            },
        ],
    },
    "T3b": {
        # 干预后静息之后填的回顾块，问的是刚才在虚拟自然中的那段体验。
        # 各量表自己的指导语（"请回想刚才这段体验……"等）见 scales.py。
        "title": "问卷 T3b",
        "codebook_instrument": "T3",
        "pages": [
            {
                "intro": "接下来的问题问的是你刚才在虚拟自然中的那段体验，请回想那段时间的感受来填答。"
                         "问卷没有正确或错误之分，按照你的真实感受填写即可。",
                "blocks": [
                    _numeric_block("T3_attention", scales.ATTENTION),
                    _numeric_block("T3_meaning", scales.MEANING),
                    _fascination_combined_block(),
                    _numeric_block("T3_imi_choice", scales.IMI_CHOICE),
                    _slider_block("T3_fms", scales.FMS),
                ],
            },
        ],
    },
}

# --------------------------------------------------------------------------
# 作答合并 / 漏答校验（服务端兜底；正常情况下前端 JS 已经挡住了未答完的提交）
# --------------------------------------------------------------------------

def merge_answers(page, form, answers):
    """把这一页提交的表单数据合并进 answers（只在答了的题上覆盖，不清空已有答案）。"""
    for block in page["blocks"]:
        t = block["type"]
        if t == "multi":
            values = form.get(block["key"])
            if values:
                answers[block["key"]] = values
        elif t == "slider":
            values = form.get(block["key"])
            if values and values[0] != "":
                answers[block["key"]] = values[0]
        elif t == "basic_info":
            for key in ("A_age", "A_gender"):
                values = form.get(key)
                if values and values[0] != "":
                    answers[key] = values[0]
        else:  # matrix / numeric
            for key, _text in block["items"]:
                values = form.get(key)
                if values and values[0] != "":
                    answers[key] = values[0]
    return answers


def missing_items(page, answers):
    missing = []
    for block in page["blocks"]:
        t = block["type"]
        if t == "multi":
            if not answers.get(block["key"]):
                missing.append(block["key"])
        elif t == "slider":
            if block["key"] not in answers:
                missing.append(block["key"])
        elif t == "basic_info":
            for key in ("A_age", "A_gender"):
                if key not in answers:
                    missing.append(key)
        else:
            for key, _text in block["items"]:
                if key not in answers:
                    missing.append(key)
    return missing


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------

def _render_matrix(block, existing):
    rows = []
    for key, text in block["items"]:
        existing_val = existing.get(key)
        opts_html = "".join(
            '<label><input type="radio" name="%s" value="%d"%s> %s</label>' % (
                esc(key), i, " checked" if existing_val == str(i) else "", esc(opt),
            )
            for i, opt in enumerate(block["options"])
        )
        rows.append(
            '<div class="qitem" data-item="%s"><div class="qrow-text">%s</div>'
            '<div class="qoptions">%s</div></div>' % (esc(key), esc(text), opts_html)
        )
    instruction_html = ('<div class="qinstruction">%s</div>' % esc(block["instruction"])) if block.get("instruction") else ""
    return instruction_html + '<div class="qblock">%s</div>' % "".join(rows)


def _render_numeric(block, existing):
    lo, hi = block["scale_min"], block["scale_max"]
    rows = []
    for key, text in block["items"]:
        existing_val = existing.get(key)
        cells = []
        for v in range(lo, hi + 1):
            label = block["scale_labels"].get(v, "")
            checked = " checked" if existing_val == str(v) else ""
            label_html = ('<span class="num-label">%s</span>' % esc(label)) if label else ""
            cells.append(
                '<label class="num-cell"><input type="radio" name="%s" value="%d"%s>'
                '<span class="num-n">%d</span>%s</label>' % (esc(key), v, checked, v, label_html)
            )
        rows.append(
            '<div class="qitem" data-item="%s"><div class="qrow-text">%s</div>'
            '<div class="qoptions numeric-scale">%s</div></div>' % (esc(key), esc(text), "".join(cells))
        )
    instruction_html = ('<div class="qinstruction">%s</div>' % esc(block["instruction"])) if block.get("instruction") else ""
    return instruction_html + '<div class="qblock">%s</div>' % "".join(rows)


def _render_slider(block, existing):
    key = block["key"]
    spec = block["spec"]
    existing_val = existing.get(key)
    initial = existing_val if existing_val is not None else str((spec["min"] + spec["max"]) // 2)
    hidden_value_attr = ' value="%s"' % esc(existing_val) if existing_val is not None else ""
    display_style = "" if existing_val is not None else ' style="visibility:hidden"'
    return """<div class="qitem" data-item="%s">
<div class="qrow-text">%s</div>
<div class="slider-wrap">
<input type="range" min="%d" max="%d" value="%s" class="qslider" data-key="%s">
<div class="slider-value"%s id="val-%s">%s</div>
<div class="slider-labels"><span>%s</span><span>%s</span></div>
</div>
<input type="hidden" name="%s"%s>
</div>""" % (
        esc(key), esc(spec["prompt"]), spec["min"], spec["max"], initial, esc(key),
        display_style, esc(key), esc(initial),
        esc(spec.get("left_label", "")), esc(spec.get("right_label", "")),
        esc(key), hidden_value_attr,
    )


def _render_multi(block, existing):
    key = block["key"]
    spec = block["spec"]
    existing_list = existing.get(key) or []
    exclusive_idx = spec.get("exclusive_option")
    boxes = []
    for i, opt in enumerate(spec["options"]):
        checked = " checked" if str(i) in existing_list else ""
        excl_attr = ' data-exclusive="1"' if i == exclusive_idx else ""
        boxes.append(
            '<label><input type="checkbox" name="%s" value="%d"%s%s> %s</label>' % (
                esc(key), i, checked, excl_attr, esc(opt),
            )
        )
    return '<div class="qitem" data-item="%s"><div class="qrow-text">%s</div>' \
           '<div class="qoptions qmulti">%s</div></div>' % (esc(key), esc(spec["prompt"]), "".join(boxes))


def _render_basic_info(existing):
    age_val = existing.get("A_age", "")
    gender_val = existing.get("A_gender")
    gender_opts = "".join(
        '<label><input type="radio" name="A_gender" value="%d"%s> %s</label>' % (
            i, " checked" if gender_val == str(i) else "", esc(opt),
        )
        for i, opt in enumerate(["男", "女"])
    )
    return """<div class="qitem" data-item="A_age"><div class="qrow-text">年龄</div>
<input type="number" name="A_age" value="%s" class="qnumber" min="0" max="120"></div>
<div class="qitem" data-item="A_gender"><div class="qrow-text">性别</div>
<div class="qoptions">%s</div></div>""" % (esc(age_val), gender_opts)


def _render_block(block, existing):
    t = block["type"]
    if t == "matrix":
        return _render_matrix(block, existing)
    if t == "numeric":
        return _render_numeric(block, existing)
    if t == "slider":
        return _render_slider(block, existing)
    if t == "multi":
        return _render_multi(block, existing)
    if t == "basic_info":
        return _render_basic_info(existing)
    raise ValueError("未知的题目类型：%s" % t)


QUESTION_GATE_SCRIPT = """<script>
function itemAnswered(item) {
    var radios = item.querySelectorAll('input[type="radio"]');
    if (radios.length) return Array.prototype.some.call(radios, function (r) { return r.checked; });
    var checks = item.querySelectorAll('input[type="checkbox"]');
    if (checks.length) return Array.prototype.some.call(checks, function (c) { return c.checked; });
    var hiddenTouched = item.querySelector('input[type="hidden"]');
    if (item.querySelector('input[type="range"]')) return hiddenTouched && hiddenTouched.value !== "";
    var texts = item.querySelectorAll('input[type="number"], input[type="text"]');
    if (texts.length) return Array.prototype.every.call(texts, function (t) { return t.value.trim() !== ""; });
    return true;
}
document.querySelectorAll('.qslider').forEach(function (sl) {
    sl.addEventListener('input', function () {
        var key = sl.dataset.key;
        var hidden = document.querySelector('input[type="hidden"][name="' + key + '"]');
        if (hidden) hidden.value = sl.value;
        var disp = document.getElementById('val-' + key);
        if (disp) { disp.style.visibility = 'visible'; disp.textContent = sl.value; }
    });
});
document.querySelectorAll('.qmulti').forEach(function (group) {
    var boxes = group.querySelectorAll('input[type="checkbox"]');
    boxes.forEach(function (cb) {
        cb.addEventListener('change', function () {
            if (cb.checked && cb.dataset.exclusive === "1") {
                boxes.forEach(function (o) { if (o !== cb) o.checked = false; });
            } else if (cb.checked) {
                boxes.forEach(function (o) { if (o.dataset.exclusive === "1") o.checked = false; });
            }
        });
    });
});
function qSubmit(direction) {
    document.getElementById("qdirection").value = direction;
    if (direction === "prev") { document.getElementById("qform").submit(); return; }
    var missing = [];
    document.querySelectorAll(".qitem").forEach(function (item) {
        item.classList.remove("unanswered-flag");
        if (!itemAnswered(item)) missing.push(item);
    });
    var banner = document.getElementById("qerror");
    if (missing.length) {
        missing.forEach(function (it) { it.classList.add("unanswered-flag"); });
        banner.style.display = "block";
        banner.textContent = "还有 " + missing.length + " 题未作答，已用红色标出。";
        missing[0].scrollIntoView({ behavior: "smooth", block: "center" });
        return;
    }
    banner.style.display = "none";
    document.getElementById("qform").submit();
}
</script>"""


def render_questionnaire_page(instrument_id, page_index, existing_answers):
    instrument = QUESTIONNAIRES[instrument_id]
    page = instrument["pages"][page_index]
    total_pages = len(instrument["pages"])
    title = instrument["title"]
    heading = ("%s（%d/%d）" % (title, page_index + 1, total_pages)) if total_pages > 1 else title

    body = '<div class="qpage">'
    body += '<h2 class="stage-heading">%s</h2>' % esc(heading)
    if page.get("intro"):
        body += '<div class="qintro">%s</div>' % esc(page["intro"])
    body += '<div id="qerror" class="qbanner-error" style="display:none"></div>'
    body += '<form method="post" action="/qanswer" id="qform">'
    for block in page["blocks"]:
        body += _render_block(block, existing_answers)
    body += '<input type="hidden" name="direction" id="qdirection" value="next">'

    is_last = page_index == total_pages - 1
    body += '<div class="qnav">'
    if page_index > 0:
        body += '<button type="button" class="secondary" onclick="qSubmit(\'prev\')">上一页</button>'
    body += '<button type="button" id="q-submit-btn" onclick="qSubmit(\'next\')">%s</button>' % ("提交" if is_last else "下一页")
    body += "</div></form></div>"
    body += QUESTION_GATE_SCRIPT
    return shell(title, body)


def render_blank_page():
    body = """<div class="qpage" style="text-align:center; margin-top:18vh;">
<p style="font-size:24px;">请您把电脑交还实验员，不要点击下面的按钮</p>
<form method="post" action="/complete">
<div class="qnav" style="justify-content:center;"><button type="submit">进入下一阶段</button></div>
</form></div>"""
    return shell("请交还设备", body)
