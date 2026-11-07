"""
17 页流程（加结束页共 18 页）的内容定义：指导语原文、操作清单、计时器。

指导语原文取自《实验记录-实验流程骨架.md》第四节，页码与该文档第三节标题括号里的
流程单页码一致。诱导后、干预后各有一段专给 HRV 用的静息（post_writing_rest /
post_intervention_rest），指导语与静息基线相同。

两处"问卷在前、静息在后"的顺序，原理是：此刻状态的题目随时间消退，先静息会让问卷
测到已部分恢复的状态；所以问卷紧接事件，HRV 静息放在问卷之后。
  诱导后：书写 → 问卷 T2 → 诱导后静息
  干预后：干预 → 问卷 T3a（此刻状态）→ 干预后静息 → 问卷 T3b（回顾干预体验）
"""
import config


def timer_lead_sec(page_def):
    """计时页的念指导语加时（秒），来自 config.INSTRUCTION_LEAD_SEC，按 timer_key 查。
    没有计时器或没有加时项的页面返回 0。"""
    timer_key = page_def.get("timer_key")
    if not timer_key:
        return 0
    return config.INSTRUCTION_LEAD_SEC.get(timer_key, 0)


def warn(text, title=None):
    """警示清单项：红色块、大字、行首带 ⚠。title 是警示区块标题，显示在同一组警示项的第一项上方。"""
    item = {"text": text, "warning": True}
    if title:
        item["title"] = title
    return item


def normalize_item(item, fmt=None):
    """清单项统一成 {"text", "warning", "title"}。item 可以是普通字符串，也可以是 warn() 返回的 dict。
    fmt 不为空时，对文字做 str.format（目前只有第 4 页用到，填 xdf_name）。"""
    if isinstance(item, str):
        item = {"text": item}
    text = item["text"]
    if fmt:
        text = text.format(**fmt)
    return {"text": text, "warning": bool(item.get("warning")), "title": item.get("title")}


def normalize_list(items, fmt=None):
    return [normalize_item(i, fmt) for i in (items or [])]


def sections_of(page_def):
    """页面的内容段落列表：{"say": 提示语} 或 {"checklist": [...]}。
    没有写 sections 的页面，整页就是一个 checklist 段，行为与原来一致。"""
    if "sections" in page_def:
        return page_def["sections"]
    return [{"checklist": page_def.get("checklist", [])}]


def flat_checklist(page_def, fmt=None):
    """把页面所有清单段按顺序拍平成一个列表（勾选框的序号就是这里的下标）。"""
    items = []
    for sec in sections_of(page_def):
        items.extend(normalize_list(sec.get("checklist", []), fmt))
    return items
# ------------------------------------------------------------------
# 每一页的内容。
#   kind: "task"（标准任务页）/ "placeholder"（问卷模式占位）/ "end"（结束页）
#   instruction: 要大字念给被试的原话（None 表示这页没有要念的话）
#   note: 给实验员看的说明文字，不是念给被试的（用于标注"下一轮再做"等）
#   checklist: 操作清单；每项是字符串，或 warn(文字, title=...) 得到的警示项
#   sections: 可选。按顺序排列的段落 {"say": 提示语} / {"checklist": [...]}，有它时忽略 instruction 和 checklist
#   timer_key: 对应 durations_sec 里的键名，没有计时器就是 None
#   timeup_message: 到时间后的提示语，不填则用通用的"已到预定时间"
#   midpoint: (duration_key, message) 中途提示，目前只有担忧书写页用到
# ------------------------------------------------------------------
PAGES = {
    "consent": {
        "number": 1,
        "title": "知情同意",
        "kind": "task",
        "instruction": "您好，请坐。欢迎参加我们的实验。本实验是测试一款 iPad 应用的设计质量。"
                        "实验过程中，您如果有任何不适，可以随时退出实验。这是一份知情同意书，"
                        "请您先阅读；如果同意参加，请签上名字和日期。",
        "note": None,
        "checklist": ["已签字", "已填写日期", "介绍中没有透露研究目的"],
        "timer_key": None,
    },
    "q_a": {
        "number": 2,
        "title": "问卷 A",
        "kind": "questionnaire",
        "instrument": "A",
        "timer_key": None,
    },
    "verify_h10": {
        "number": 3,
        "title": "判定结果确认、佩戴 H10",
        "kind": "verdict",
        "instruction": None,
        "note": "下面是问卷 A 筛查多选题的结果和建议，供判断是否纳入时参考；最终由实验员手动选择结果。",
        "checklist": [],
        "timer_key": None,
    },
    "check_signal": {
        "number": 4,
        "title": "检查信号并开始录制",
        "kind": "task",
        "instruction": "请您稍等一下。",
        "note": "LabRecorder 从这一步开始录制，一直录到第 17 页停止——中途（第 12 页"
                "“揭晓组别”）才会知道分组，所以文件名里不含分组信息，分组对照见"
                "导出的 log.csv。路径、文件名模板怎么设，见准备检查页。",
        "checklist": [
            "PolarBridge 已打开",
            "SensorBridge 已连接 H10 并开始录制",
            "LabRecorder 文件名已设为 {xdf_name}（不含 session/分组，BIDS 已关闭）",
            "心率数据连续、数值合理",
            warn("LabRecorder 已点 Start：确认状态显示正在录制，文件大小在增长", title="数据录制确认"),
        ],
        "timer_key": None,
    },
    "q_t0": {
        "number": 5,
        "title": "问卷 T0",
        "kind": "questionnaire",
        "instrument": "T0",
        "timer_key": None,
    },
    "practice": {
        "number": 6,
        "title": "练习场",
        "kind": "task",
        "instruction": "下面请您熟悉一下我们的应用，这部分是让您熟悉实验环境。",
        "note": "下方五部分按顺序讲，要点不能漏，说法可以自己组织。",
        "checklist": [
            "已在 SensorBridge 点“训练开始”（下方列表）",
            "已在 SensorBridge 点“训练结束”（下方列表）",
            {"text": "已退出练习场回到菜单：三根手指在屏幕边角处长按，不要在屏幕中间按"
                     "（退回菜单时手指会正好落在“实验条件”等按钮上，造成误触）",
             "warning": True, "title": "退出练习场"},
        ],
        "timer_key": "practice",
    },
    "rest": {
        "number": 7,
        "title": "静息基线",
        "kind": "task",
        "instruction": "接下来，请您用自己觉得舒服的姿势坐在椅子上，上身稍微向后靠，避免传感器移位；"
                        "轻轻闭上眼睛，尽可能放松。时间大约 5 分钟，到时间我会提醒您。",
        "note": None,
        "checklist": ["已在 SensorBridge 点“基线开始”（上方按钮）", "已在 SensorBridge 点“基线结束”（下方列表）"],
        "timer_key": "rest",
    },
    "q_t1": {
        "number": 8,
        "title": "问卷 T1",
        "kind": "questionnaire",
        "instrument": "T1",
        "timer_key": None,
    },
    "writing": {
        "number": 9,
        "title": "焦虑诱导：担忧书写",
        "kind": "task",
        "instruction": "接下来请您做一个书写任务。请想一想，您目前生活中最担心的一件事。"
                        "这件事现在还没有结果，您担心它会朝不好的方向发展。它可以是任何方面的事，"
                        "请选一件对您来说真正重要、让您放心不下的事。如果一时想不到，也可以想想"
                        "考试、毕业或找工作这类事情。选好以后，请把它写下来：这是一件什么事，"
                        "您担心会发生什么，如果事情朝坏的方向发展，可能会变成什么样，以及您想到"
                        "这些时的感受。想到什么就写什么，不用在意字迹、语句和错别字。您写的内容"
                        "不会有任何人看，结束后由您自己处理。时间大约 6 分钟，请一直写到我提醒您"
                        "结束。现在请开始。",
        "note": None,
        "checklist": [
            "已在 SensorBridge 点“诱导开始”（上方按钮）",
            "已在 SensorBridge 点“诱导结束”（上方按钮）",
            "未查看书写内容",
        ],
        "timer_key": "writing",
        "timeup_message": "时间到了，请停笔，把纸翻过来放在一边。",
        "midpoint": ("writing_midpoint", "请继续写。想一想，如果这件事真的往坏的方向发展，接下来还可能发生什么。"),
    },
    "q_t2": {
        # 书写结束后立即填，问卷在前、静息在后（原理见本文件开头）。
        "number": 10,
        "title": "问卷 T2",
        "kind": "questionnaire",
        "instrument": "T2",
        "timer_key": None,
    },
    "post_writing_rest": {
        # 专给 HRV 用的静息，5 分钟；分析时去掉第 1 分钟，用后 4 分钟算 RMSSD。
        # 指导语与静息基线一致（4.10b）。
        "number": 11,
        "title": "诱导后静息",
        "kind": "task",
        "instruction": "接下来，请您用自己觉得舒服的姿势坐在椅子上，上身稍微向后靠，避免传感器移位；"
                        "轻轻闭上眼睛，尽可能放松。时间大约 5 分钟，到时间我会提醒您。",
        "note": None,
        "checklist": [
            "已在 SensorBridge 点“诱导后静息开始”（下方列表）",
            "已在 SensorBridge 点“诱导后静息结束”（下方列表）",
            "静息姿势与基线相同（上身靠在椅背上、闭眼），开始计时前已确认",
        ],
        "timer_key": "post_writing_rest",
    },
    "reveal_group": {
        "number": 12,
        "title": "揭晓组别",
        "kind": "group",
        "instruction": None,
        "note": "分组依据见下方；确认无误后再去 VN 中选择对应条件。",
        "checklist": ["已在 VN 中选择对应条件", "已确认 iPad 屏幕亮度 90%、音量 80%"],
        "timer_key": None,
    },
    "intervention": {
        "number": 13,
        "title": "干预",
        "kind": "task",
        "instruction": None,
        "note": "实验期间不与被试交流（除非被试求助、出现不适，或要求停止）。",
        "checklist": ["已在 SensorBridge 点“干预开始”（上方按钮）", "已在 SensorBridge 点“干预结束”（上方按钮）"],
        "timer_key": "intervention",
    },
    "q_t3a": {
        # 干预结束后立即填的此刻状态块（与 T1、T2 完全相同的 15 题）。
        "number": 14,
        "title": "问卷 T3a",
        "kind": "questionnaire",
        "instrument": "T3a",
        "timer_key": None,
    },
    "post_intervention_rest": {
        # 专给 HRV 用的静息，理由和用法同"诱导后静息"（4.12b）。
        "number": 15,
        "title": "干预后静息",
        "kind": "task",
        "instruction": "接下来，请您用自己觉得舒服的姿势坐在椅子上，上身稍微向后靠，避免传感器移位；"
                        "轻轻闭上眼睛，尽可能放松。时间大约 5 分钟，到时间我会提醒您。",
        "note": None,
        "checklist": [
            "已在 SensorBridge 点“干预后静息开始”（下方列表）",
            "已在 SensorBridge 点“干预后静息结束”（下方列表）",
            "静息姿势与基线相同（上身靠在椅背上、闭眼），开始计时前已确认",
        ],
        "timer_key": "post_intervention_rest",
    },
    "q_t3b": {
        "number": 16,
        "title": "问卷 T3b",
        "kind": "questionnaire",
        "instrument": "T3b",
        "timer_key": None,
    },
    "wrapup": {
        "number": 17,
        "title": "停止录制、事后说明、支付报酬",
        "kind": "task",
        "complete_label": "完成实验",
        "instruction": None,
        "note": None,
        # 按顺序排列的段落：提示语（念给被试）/ 警示清单 / 普通清单。
        "sections": [
            {"say": "我们的实验结束了。您现在有没有什么不适？"},
            {"checklist": [
                warn("1. LabRecorder 已点击 End，停止录制", title="停止录制（按顺序，一项一行）"),
                warn("2. PolarBridge 已按 ESC 停止", title="停止录制（按顺序，一项一行）"),
                warn("3. SensorBridge 已点击“录制结束”", title="停止录制（按顺序，一项一行）"),
            ]},
            {"say": "请您摘下心电记录仪。实验的具体内容，请先不要和其他同学讨论，谢谢。"
                    "这是给您的报酬，请您签字确认收款。这是心理咨询中心的联系卡，之后如果您有任何"
                    "情绪上的不适，欢迎随时咨询。再见。"},
            {"checklist": [
                "已取下 H10",
                "书写稿已交由被试处理（自行带走或密封回收）",
                "已支付报酬并签字",
                "H10 已清洁",
            ]},
        ],
        "timer_key": None,
    },
    "end": {
        "number": 18,
        "title": "结束页",
        "kind": "end",
        "instruction": None,
        "note": None,
        "checklist": [],
        "timer_key": None,
    },
}

# 线性顺序（第 3 页“判定结果确认”的去向由 verdict 决定，在 server.py 里单独处理）。
NEXT_PAGE = {
    "consent": "q_a",
    "q_a": "verify_h10",
    "check_signal": "q_t0",
    "q_t0": "practice",
    "practice": "rest",
    "rest": "q_t1",
    "q_t1": "writing",
    "writing": "q_t2",
    "q_t2": "post_writing_rest",
    "post_writing_rest": "reveal_group",
    "reveal_group": "intervention",
    "intervention": "q_t3a",
    "q_t3a": "post_intervention_rest",
    "post_intervention_rest": "q_t3b",
    "q_t3b": "wrapup",
    "wrapup": "end",
}

# 第 3 页三种判定结果各自的指导语、清单、去向。
VERDICT_OPTIONS = {
    "continue": {
        "label": "继续",
        "instruction": "请您佩戴这个心电记录仪。它只记录与心跳相关的一些指标，不会对身体造成"
                        "任何伤害。记录仪需要贴身佩戴：把传感器放在双乳下缘之间，在背后把带子"
                        "扣上即可。",
        "checklist": ["H10 佩戴正确（位置、松紧合适）"],
        "next": "check_signal",
    },
    "unfit": {
        "label": "不适合",
        "instruction": "谢谢您的支持，本实验不适合您，下次再合作。",
        "checklist": ["已照付报酬、发放说明卡"],
        "next": "end",
    },
    "reschedule": {
        "label": "改期",
        "instruction": "谢谢您。今天的情况可能会影响测量结果，我们另约一个时间再来，可以吗？",
        "checklist": ["已说明原因、另约时间"],
        "next": "end",
    },
}

# 第 12 页"揭晓组别"确定条件后，按条件念给被试的指导语（原文取自《实验流程骨架》4.11）。
GROUP_INSTRUCTIONS = {
    "实验组": "下面请您使用和体验正式产品。这是一个虚拟自然环境，您可以在其中自由探索，"
             "交互方式与您刚才练习过的一致。使用期间，您完全按照自己的想法与虚拟环境互动，"
             "我不会与您交流；在这期间腰背稍微挺直，避免加压传感器。如果感到不适，可以随时"
             "示意我。使用时长大约 12 分钟，到时间我会提醒您。那请开始吧。",
    "对照组": "下面请您观看正式产品的演示视频。这是一个虚拟自然环境。观看期间您只需要看，"
             "不需要操作，我不会与您交流；在这期间腰背稍微挺直，避免加压传感器。如果感到不适，"
             "可以随时示意我。观看时长大约 12 分钟，到时间我会提醒您。那请开始吧。",
}

PAGE_ORDER = [
    "consent", "q_a", "verify_h10", "check_signal", "q_t0", "practice", "rest",
    "q_t1", "writing", "q_t2", "post_writing_rest", "reveal_group", "intervention",
    "q_t3a", "post_intervention_rest", "q_t3b", "wrapup", "end",
]
