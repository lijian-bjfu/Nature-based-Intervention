"""
16 页流程（加结束页共 17 页）的内容定义：指导语原文、操作清单、计时器。

指导语原文取自《实验记录-实验流程骨架.md》第四节。2026-11-04 在诱导（担忧书写）、
干预后各加了一段静息（post_writing_rest / post_intervention_rest），专给 HRV 用，
原文档没有这两页，页码、指导语是照着"静息基线"页的写法续的，不是文档原文。
"""
import config

# ------------------------------------------------------------------
# 每一页的内容。
#   kind: "task"（标准任务页）/ "placeholder"（问卷模式占位）/ "end"（结束页）
#   instruction: 要大字念给被试的原话（None 表示这页没有要念的话）
#   note: 给实验员看的说明文字，不是念给被试的（用于标注"下一轮再做"等）
#   checklist: 操作清单文字列表
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
        "note": "LabRecorder 从这一步开始录制，一直录到第 16 页停止——中途（第 12 页"
                "“揭晓组别”）才会知道分组，所以文件名里不含分组信息，分组对照见"
                "导出的 log.csv。路径、文件名模板怎么设，见准备检查页。",
        "checklist": [
            "PolarBridge 已打开",
            "SensorBridge 已连接 H10 并开始录制",
            "LabRecorder 文件名已设为 sub-{participant_id}.xdf（不含 session/分组，BIDS 已关闭）",
            "心率数据连续、数值合理",
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
        "note": "下方“情境指导语”按环节折叠，走到哪个环节再点开对应的部分查看，不用提前通读。",
        "checklist": [
            "已在 SensorBridge 打“训练开始”标记",
            "已完成行走练习", "已完成触摸练习", "已完成情境练习", "已完成自由探索",
            "已在 SensorBridge 打“训练结束”标记",
        ],
        "timer_key": "practice",
    },
    "rest": {
        "number": 7,
        "title": "静息基线",
        "kind": "task",
        "instruction": "接下来，请您用自己觉得舒服的姿势坐在椅子上，上身稍微向后靠，避免传感器移位；"
                        "轻轻闭上眼睛，尽可能放松。时间大约 6 分钟，到时间我会提醒您。",
        "note": None,
        "checklist": ["已在 SensorBridge 打“基线开始”标记", "已在 SensorBridge 打“基线结束”标记"],
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
            "已在 SensorBridge 打“诱导开始”标记",
            "已在 SensorBridge 打“诱导结束”标记",
            "未查看书写内容",
        ],
        "timer_key": "writing",
        "timeup_message": "时间到了，请停笔，把纸翻过来放在一边。",
        "midpoint": ("writing_midpoint", "请继续写。想一想，如果这件事真的往坏的方向发展，接下来还可能发生什么。"),
    },
    "post_writing_rest": {
        # 2026-11-04 加：诱导后至少静息 6 分钟，给 HRV 用（分析时取中间 5 分钟窗口算
        # RMSSD），指导语和静息基线那页一样。
        "number": 10,
        "title": "诱导后静息",
        "kind": "task",
        "instruction": "请您把笔放下。接下来请您用自己觉得舒服的姿势坐在椅子上，上身稍微向后靠，"
                        "避免传感器移位；轻轻闭上眼睛，尽可能放松。时间大约 6 分钟，到时间我会"
                        "提醒您。",
        "note": None,
        "checklist": ["已在 SensorBridge 打“诱导后静息开始”标记", "已在 SensorBridge 打“诱导后静息结束”标记"],
        "timer_key": "post_writing_rest",
    },
    "q_t2": {
        "number": 11,
        "title": "问卷 T2",
        "kind": "questionnaire",
        "instrument": "T2",
        "timer_key": None,
    },
    "reveal_group": {
        "number": 12,
        "title": "揭晓组别",
        "kind": "group",
        "instruction": None,
        "note": "预实验模式下由实验员手动选择组别；其余模式下由系统随机分配（见下方分组依据）。"
                if config.MODE == "pilot" else "分组依据见下方；确认无误后再去 VN 中选择对应条件。",
        "checklist": ["已在 VN 中选择对应条件"],
        "timer_key": None,
    },
    "intervention": {
        "number": 13,
        "title": "干预",
        "kind": "task",
        "instruction": None,
        "note": "实验期间不与被试交流（除非被试求助、出现不适，或要求停止）。",
        "checklist": ["已打“干预开始”标记", "已打“干预结束”标记"],
        "timer_key": "intervention",
    },
    "post_intervention_rest": {
        # 2026-11-04 加：干预后至少静息 6 分钟，给 HRV 用，理由和用法同"诱导后静息"。
        "number": 14,
        "title": "干预后静息",
        "kind": "task",
        "instruction": "接下来请您用自己觉得舒服的姿势坐在椅子上，上身稍微向后靠，避免传感器移位；"
                        "轻轻闭上眼睛，尽可能放松。时间大约 6 分钟，到时间我会提醒您。",
        "note": None,
        "checklist": ["已在 SensorBridge 打“干预后静息开始”标记", "已在 SensorBridge 打“干预后静息结束”标记"],
        "timer_key": "post_intervention_rest",
    },
    "q_t3": {
        "number": 15,
        "title": "问卷 T3",
        "kind": "questionnaire",
        "instrument": "T3",
        "timer_key": None,
    },
    "wrapup": {
        "number": 16,
        "title": "停止录制、事后说明、支付报酬",
        "kind": "task",
        "complete_label": "完成实验",
        "instruction": "我们的实验结束了。您现在有没有什么不适？"
                        "（停止录制后）请您摘下心电记录仪。"
                        "实验的具体内容，请先不要和其他同学讨论，谢谢。这是给您的报酬，"
                        "请您签字确认收款。这是心理咨询中心的联系卡，之后如果您有任何情绪上的"
                        "不适，欢迎随时咨询。再见。",
        "note": None,
        "checklist": [
            "已在 SensorBridge 打“录制结束”标记",
            "LabRecorder、SensorBridge 已停止",
            "已取下 H10",
            "书写稿已交由被试处理（自行带走或密封回收）",
            "已支付报酬并签字",
            "H10 已清洁",
        ],
        "timer_key": None,
    },
    "end": {
        "number": 17,
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
    "writing": "post_writing_rest",
    "post_writing_rest": "q_t2",
    "q_t2": "reveal_group",
    "reveal_group": "intervention",
    "intervention": "post_intervention_rest",
    "post_intervention_rest": "q_t3",
    "q_t3": "wrapup",
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
        "next": "wrapup",
    },
    "reschedule": {
        "label": "改期",
        "instruction": "谢谢您。今天的情况可能会影响测量结果，我们另约一个时间再来，可以吗？",
        "checklist": ["已说明原因、另约时间"],
        "next": "end",
    },
}

# 第 12 页"揭晓组别"确定条件后，按条件念给被试的指导语（原文取自《实验流程骨架》4.11）。
# 注意：原文里写的时长是"大约 15 分钟"，与 INTERVENTION_DURATION_SEC 当前的 10 分钟占位
# 不一致，这里先保留原文，时长定下来后记得一并改这里的文字。
GROUP_INSTRUCTIONS = {
    "实验组": "下面请您使用和体验正式产品。这是一个虚拟自然环境，您可以在其中自由探索，"
             "交互方式与您刚才练习过的一致。使用期间，您完全按照自己的想法与虚拟环境互动，"
             "我不会与您交流；在这期间腰背稍微挺直，避免加压传感器。如果感到不适，可以随时"
             "示意我。使用时长大约 15 分钟，到时间我会提醒您。那请开始吧。",
    "对照组": "下面请您观看正式产品的演示视频。这是一个虚拟自然环境。观看期间您只需要看，"
             "不需要操作，我不会与您交流；在这期间腰背稍微挺直，避免加压传感器。如果感到不适，"
             "可以随时示意我。观看时长大约 15 分钟，到时间我会提醒您。那请开始吧。",
}

PAGE_ORDER = [
    "consent", "q_a", "verify_h10", "check_signal", "q_t0", "practice", "rest",
    "q_t1", "writing", "post_writing_rest", "q_t2", "reveal_group", "intervention",
    "post_intervention_rest", "q_t3", "wrapup", "end",
]
