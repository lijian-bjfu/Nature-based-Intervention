"""
psycho（问卷）原始表的字段规范草稿。

对应 global_settings.py 里 TRACK_SCHEMA / METRICS["track"] 的写法和颗粒度，
但还没有经过研究确认，不是正式规范，也没有登记进 global_settings.py。

来源：流程单系统（研究思路/交接提示-流程单系统.md 及其代码 app/scales.py、
app/questionnaire.py）导出的 data/<dataset>/raw/psycho/questionnaires.csv、
questionnaires_codebook.csv。两边字段定义如果以后不一致，以流程单系统代码为准，
这份草稿需要跟着更新。

怎么用这份草稿：
  - PSYCHO_SCHEMA：每一列的类型、取值范围，对应 TRACK_SCHEMA。
  - SCALE_LABELS：量表选项的文字含义（矩阵题存的是选项下标，不是文字本身，要靠这个查）。
  - PSYCHO_METRICS：每个量表的计分口径——反向计分题、分值范围、合计方式、分类界值，
    对应 METRICS["track"]。这是这份草稿里最需要研究确认的部分。
  - 确认后，把 PSYCHO_SCHEMA 合并进 global_settings.py 的 SCHEMAS，PSYCHO_METRICS 的
    内容登记进 METRICS["psycho"]，格式照抄即可（用的是同一个 Field 类）；完成后这份
    草稿文件可以删掉或转成 deprecated。

2026-10-31 已确定的问题：
  - 多选题的勾选状态，流程单系统导出成字符串 "1"/"0"/""（空＝未作答），不跟 track 那边
    TRACK_TRUE="TRUE"/TRACK_FALSE="FALSE" 的布尔惯例对齐——研究者认为 1/0 更符合直觉、
    也更方便后续分析，就按这个来，不用再改。

2026-10-31 还没解决、合并前需要研究确认的问题：
  1. STAI-T 41 分界值、GAD-2 的 3 分界值，来源都还没核对原始文献（交接文档第十节）。
  2. log.csv（判定结果、分组、各页起止时间）、notes.txt（实验记录文字，每个被试一份，
     按页列出）算 raw/psycho 还是 raw/session_notes 还是 supplementary，还没讨论过，
     这份草稿先不收它们。

2026-11-01、2026-11-02 的问卷改动已同步进本草稿：
  - T3 干预后新增"注意题"（E5，4 题，第 2 题反向），意义题（E6）由 1-9 点改为 1-7 点，
    和注意题共用同一组选项。
  - 原 IMI 兴趣/愉悦 5 题（旧 E5）已整体替换为"迷恋与远离"（新 E7，改编自 Hartig et al.
    1997 PRS，迷恋 5 题 + 远离 2 题，全部正向），IMI 感知选择改到 E8、和迷恋/远离共用
    同一句指导语；FMS 顺位到 E9。T3 题数 37 → 41 → 43。
  - 原"IMI 两个子量表题序随机混排未实现"的问题随 IMI 兴趣/愉悦被替换而不再适用；新的
    迷恋/远离/感知选择三组题，问卷草稿里没有要求随机混排，流程单系统按固定顺序呈现。
"""
from global_settings import Field  # 草稿阶段直接复用同一个 Field 类；合并进
                                     # global_settings.py 时删掉这行，字段原样搬过去。


# ------------------------------------------------------------------
# 量表选项的文字含义：矩阵题（matrix）存的是选项下标（0 起），不是文字本身，
# 查这里才知道每个下标代表什么。数字量表（numeric，注意题/意义题/迷恋远离/IMI 感知选择）
# 存的就是数字本身，不用查下标，只在端点和中点有文字提示。
# ------------------------------------------------------------------
SCALE_LABELS = {
    "STAI_T": ("几乎从不", "有时", "经常", "几乎总是"),  # STAI-T 状态-特质焦虑量表·特质分量表
    "CNS": ("非常不同意", "不同意", "中立", "同意", "非常同意"),  # CNS 自然联结量表
    "GAD2": ("完全不会", "好几天", "一半以上的日子", "几乎每天"),  # GAD-2 广泛性焦虑量表筛查版
    "STAI_6": ("完全没有", "有些", "中等程度", "非常明显"),  # STAI-6 状态焦虑简版
    "PANAS": ("几乎没有", "有一点", "中等程度", "比较多", "非常多"),  # PANAS 正负性情绪量表
    "MSBS8": ("非常不同意", "不同意", "有点不同意", "中立", "有点同意", "同意", "非常同意"),  # MSBS-8 无聊状态量表
}

# 数字量表（1-7，只标端点和中点文字，存的是数字本身不是下标）。
# 2026-11-02：MEANING 由 1-9 改成 1-7；ATTENTION 是新加的注意题；FASCINATION/BEING_AWAY
# 替换了原来的 IMI 兴趣/愉悦；IMI_CHOICE（感知选择）内容没变，和 FASCINATION 共用同一组选项。
NUMERIC_SCALE_LABELS = {
    "ATTENTION": {"range": (1, 7), "labels": {1: "完全没有", 4: "有些", 7: "非常"}},
    "MEANING": {"range": (1, 7), "labels": {1: "完全没有", 4: "有些", 7: "非常"}},
    "FASCINATION": {"range": (1, 7), "labels": {1: "完全不符合", 4: "有些符合", 7: "非常符合"}},
    "BEING_AWAY": {"range": (1, 7), "labels": {1: "完全不符合", 4: "有些符合", 7: "非常符合"}},
    "IMI_CHOICE": {"range": (1, 7), "labels": {1: "完全不符合", 4: "有些符合", 7: "非常符合"}},
}

# ------------------------------------------------------------------
# 每一列的类型、取值范围。按问卷（A/T0/T1/T2/T3）分组，和流程单系统 app/questionnaire.py
# 里 QUESTIONNAIRES 的呈现顺序一致。
# ------------------------------------------------------------------
PSYCHO_SCHEMA = {
    "A": {
        "A_age": Field("A_age", "Int64", unit="years"),
        "A_gender": Field("A_gender", "Int64", levels=(0, 1)),  # 0=男, 1=女
        "A_screen_1": Field("A_screen_1", "boolean", levels=(0, 1)),  # 第 1 项：曾被诊断患有精神或心理方面的疾病（如抑郁症、焦虑症等）
        "A_screen_2": Field("A_screen_2", "boolean", levels=(0, 1)),  # 第 2 项：目前正在接受心理咨询、心理治疗或精神科治疗
        "A_screen_3": Field("A_screen_3", "boolean", levels=(0, 1)),  # 第 3 项：患有心脏或血管方面的疾病（如心脏病、高血压）
        "A_screen_4": Field("A_screen_4", "boolean", levels=(0, 1)),  # 第 4 项：有癫痫病史，或观看闪烁画面时出现过明显不适
        "A_screen_5": Field("A_screen_5", "boolean", levels=(0, 1)),  # 第 5 项：目前在服用可能影响心率或情绪的药物（如抗抑郁药、抗焦虑药、降压药）
        "A_screen_6": Field("A_screen_6", "boolean", levels=(0, 1)),  # 第 6 项：看手机或平板上的视频、玩第一人称三维游戏时，经常感到头晕或恶心
        "A_screen_7": Field("A_screen_7", "boolean", levels=(0, 1)),  # 第 7 项：参加过本项目的预实验或测试
        "A_screen_8": Field("A_screen_8", "boolean", levels=(0, 1)),  # 第 8 项：以上都没有
        "A_gad2_1": Field("A_gad2_1", "Int64", levels=(0, 1, 2, 3)),  # GAD2 · 感觉紧张、焦虑或急切
        "A_gad2_2": Field("A_gad2_2", "Int64", levels=(0, 1, 2, 3)),  # GAD2 · 不能够停止或控制担忧
    },
    "T0": {
        "T0_stait_1": Field("T0_stait_1", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我感到愉快
        "T0_stait_2": Field("T0_stait_2", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我感到紧张不安
        "T0_stait_3": Field("T0_stait_3", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我对自己感到满意
        "T0_stait_4": Field("T0_stait_4", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我希望我可以像其他人一样快乐
        "T0_stait_5": Field("T0_stait_5", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我觉得自己是个失败者
        "T0_stait_6": Field("T0_stait_6", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我感觉精力充沛
        "T0_stait_7": Field("T0_stait_7", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我"平静、冷静、沉着"
        "T0_stait_8": Field("T0_stait_8", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我觉得困难堆积如山，并且我无法克服它们
        "T0_stait_9": Field("T0_stait_9", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我为一些实际上无关紧要的事情担心太多
        "T0_stait_10": Field("T0_stait_10", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我感到高兴
        "T0_stait_11": Field("T0_stait_11", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我有令人不安的想法
        "T0_stait_12": Field("T0_stait_12", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我缺乏自信
        "T0_stait_13": Field("T0_stait_13", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我感到安全
        "T0_stait_14": Field("T0_stait_14", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我很容易做出决定
        "T0_stait_15": Field("T0_stait_15", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我觉得力不从心
        "T0_stait_16": Field("T0_stait_16", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我感到满足
        "T0_stait_17": Field("T0_stait_17", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 一些不重要的想法在我的脑海中回荡，并困扰着我
        "T0_stait_18": Field("T0_stait_18", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我把失望看得很重，以至于总是放不下
        "T0_stait_19": Field("T0_stait_19", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 我是一个踏实稳重的人
        "T0_stait_20": Field("T0_stait_20", "Int64", levels=(0, 1, 2, 3)),  # STAI_T · 当我思考我最近关注的问题和感兴趣的事物时，我就会陷入紧张不安的状态
        "T0_cns_1": Field("T0_cns_1", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我常感到与我周围的自然世界融为一体
        "T0_cns_2": Field("T0_cns_2", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我认为自然界是我所属的一个群体
        "T0_cns_3": Field("T0_cns_3", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我承认并欣赏其他生物的智慧
        "T0_cns_4": Field("T0_cns_4", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我常感到与大自然之间没有联系
        "T0_cns_5": Field("T0_cns_5", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 当我想到我的人生时，我想象自己是更大生命循环的一部分
        "T0_cns_6": Field("T0_cns_6", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我常感到与动植物有一种亲近感
        "T0_cns_7": Field("T0_cns_7", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我感到我是属于大自然的，大自然也同样属于我
        "T0_cns_8": Field("T0_cns_8", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我深刻地理解我的行为如何影响大自然
        "T0_cns_9": Field("T0_cns_9", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我常感到自己是生命网络的一部分
        "T0_cns_10": Field("T0_cns_10", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我感到所有栖息在地球上的人类和其他生物都分享着同一份生命力量
        "T0_cns_11": Field("T0_cns_11", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 就像一棵树可以成为森林的一部分，我感觉自己融入了更广阔的自然世界
        "T0_cns_12": Field("T0_cns_12", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 当我考虑自己在地球的位置时，我认为自己是大自然阶梯顶层的一员
        "T0_cns_13": Field("T0_cns_13", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我经常觉得我只是周围自然世界的一小部分，我并不比地上的草或树上的鸟更重要
        "T0_cns_14": Field("T0_cns_14", "Int64", levels=(0, 1, 2, 3, 4)),  # CNS · 我个人的福祉与大自然的福祉互不相关
    },
    "T1": {
        "T1_stai6_1": Field("T1_stai6_1", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心情平静
        "T1_stai6_2": Field("T1_stai6_2", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我是紧张的
        "T1_stai6_3": Field("T1_stai6_3", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心烦意乱
        "T1_stai6_4": Field("T1_stai6_4", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到轻松
        "T1_stai6_5": Field("T1_stai6_5", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心满意足
        "T1_stai6_6": Field("T1_stai6_6", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到担忧
        "T1_vas": Field("T1_vas", "Int64", levels=tuple(range(0, 101))),  # 请拖动滑块，标出你此刻感到焦虑的程度。（完全不焦虑 → 极度焦虑）
        "T1_panas_1": Field("T1_panas_1", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 心烦的
        "T1_panas_2": Field("T1_panas_2", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 有敌意的
        "T1_panas_3": Field("T1_panas_3", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 警觉的
        "T1_panas_4": Field("T1_panas_4", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 羞愧的
        "T1_panas_5": Field("T1_panas_5", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 受鼓舞的
        "T1_panas_6": Field("T1_panas_6", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 紧张的
        "T1_panas_7": Field("T1_panas_7", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 坚定的
        "T1_panas_8": Field("T1_panas_8", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 专注的
        "T1_panas_9": Field("T1_panas_9", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 害怕的
        "T1_panas_10": Field("T1_panas_10", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 活跃的
    },
    "T2": {
        "T2_stai6_1": Field("T2_stai6_1", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心情平静
        "T2_stai6_2": Field("T2_stai6_2", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我是紧张的
        "T2_stai6_3": Field("T2_stai6_3", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心烦意乱
        "T2_stai6_4": Field("T2_stai6_4", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到轻松
        "T2_stai6_5": Field("T2_stai6_5", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心满意足
        "T2_stai6_6": Field("T2_stai6_6", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到担忧
        "T2_vas": Field("T2_vas", "Int64", levels=tuple(range(0, 101))),  # 请拖动滑块，标出你此刻感到焦虑的程度。（完全不焦虑 → 极度焦虑）
        "T2_panas_1": Field("T2_panas_1", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 心烦的
        "T2_panas_2": Field("T2_panas_2", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 有敌意的
        "T2_panas_3": Field("T2_panas_3", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 警觉的
        "T2_panas_4": Field("T2_panas_4", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 羞愧的
        "T2_panas_5": Field("T2_panas_5", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 受鼓舞的
        "T2_panas_6": Field("T2_panas_6", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 紧张的
        "T2_panas_7": Field("T2_panas_7", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 坚定的
        "T2_panas_8": Field("T2_panas_8", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 专注的
        "T2_panas_9": Field("T2_panas_9", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 害怕的
        "T2_panas_10": Field("T2_panas_10", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 活跃的
    },
    "T3": {
        "T3_stai6_1": Field("T3_stai6_1", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心情平静
        "T3_stai6_2": Field("T3_stai6_2", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我是紧张的
        "T3_stai6_3": Field("T3_stai6_3", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心烦意乱
        "T3_stai6_4": Field("T3_stai6_4", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到轻松
        "T3_stai6_5": Field("T3_stai6_5", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到心满意足
        "T3_stai6_6": Field("T3_stai6_6", "Int64", levels=(0, 1, 2, 3)),  # STAI_6 · 我感到担忧
        "T3_vas": Field("T3_vas", "Int64", levels=tuple(range(0, 101))),  # 请拖动滑块，标出你此刻感到焦虑的程度。（完全不焦虑 → 极度焦虑）
        "T3_panas_1": Field("T3_panas_1", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 心烦的
        "T3_panas_2": Field("T3_panas_2", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 有敌意的
        "T3_panas_3": Field("T3_panas_3", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 警觉的
        "T3_panas_4": Field("T3_panas_4", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 羞愧的
        "T3_panas_5": Field("T3_panas_5", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 受鼓舞的
        "T3_panas_6": Field("T3_panas_6", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 紧张的
        "T3_panas_7": Field("T3_panas_7", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 坚定的
        "T3_panas_8": Field("T3_panas_8", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 专注的
        "T3_panas_9": Field("T3_panas_9", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 害怕的
        "T3_panas_10": Field("T3_panas_10", "Int64", levels=(0, 1, 2, 3, 4)),  # PANAS · 活跃的
        "T3_msbs_1": Field("T3_msbs_1", "Int64", levels=(0, 1, 2, 3, 4, 5, 6)),  # MSBS8 · 时间过得比平时慢
        "T3_msbs_2": Field("T3_msbs_2", "Int64", levels=(0, 1, 2, 3, 4, 5, 6)),  # MSBS8 · 容易分心
        "T3_msbs_3": Field("T3_msbs_3", "Int64", levels=(0, 1, 2, 3, 4, 5, 6)),  # MSBS8 · 我不得不做一些对我毫无价值的事情
        "T3_msbs_4": Field("T3_msbs_4", "Int64", levels=(0, 1, 2, 3, 4, 5, 6)),  # MSBS8 · 我觉得无聊
        "T3_msbs_5": Field("T3_msbs_5", "Int64", levels=(0, 1, 2, 3, 4, 5, 6)),  # MSBS8 · 我正在浪费时间，如果把这些时间花在别的事情上会更好
        "T3_msbs_6": Field("T3_msbs_6", "Int64", levels=(0, 1, 2, 3, 4, 5, 6)),  # MSBS8 · 我在走神
        "T3_msbs_7": Field("T3_msbs_7", "Int64", levels=(0, 1, 2, 3, 4, 5, 6)),  # MSBS8 · 我希望某件事情发生，但我不确定那是什么事
        "T3_msbs_8": Field("T3_msbs_8", "Int64", levels=(0, 1, 2, 3, 4, 5, 6)),  # MSBS8 · 我觉得我正在坐等某些事情的发生
        "T3_attention_1": Field("T3_attention_1", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # ATTENTION · 在刚才这段体验中，你觉得集中注意有多困难？
        "T3_attention_2": Field("T3_attention_2", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # ATTENTION · 在刚才这段体验中，你的注意在多大程度上成功地集中在了眼前的内容上？
        "T3_attention_3": Field("T3_attention_3", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # ATTENTION · 在刚才这段体验中，你在多大程度上需要强迫自己去集中注意？
        "T3_attention_4": Field("T3_attention_4", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # ATTENTION · 在刚才这段体验中，你在多大程度上会走神，想到与眼前无关的事情？
        "T3_meaning_1": Field("T3_meaning_1", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # MEANING · 刚才这段体验对你个人来说有多有意义？
        "T3_meaning_2": Field("T3_meaning_2", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # MEANING · 在刚才这段时间里，你在多大程度上觉得自己在做一件值得的事？
        "T3_meaning_3": Field("T3_meaning_3", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # MEANING · 刚才这段体验在多大程度上符合你那时想要的？
        "T3_fascination_1": Field("T3_fascination_1", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # FASCINATION · 刚才的虚拟自然有令人着迷的地方
        "T3_fascination_2": Field("T3_fascination_2", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # FASCINATION · 在刚才的虚拟自然中，有许多东西吸引了我的注意
        "T3_fascination_3": Field("T3_fascination_3", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # FASCINATION · 我想更多地了解刚才的虚拟自然
        "T3_fascination_4": Field("T3_fascination_4", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # FASCINATION · 刚才的虚拟自然中有很多可以探索和发现的东西
        "T3_fascination_5": Field("T3_fascination_5", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # FASCINATION · 我想再多花些时间看看刚才的虚拟自然
        "T3_away_1": Field("T3_away_1", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # BEING_AWAY · 刚才的体验像是一次短暂的逃离
        "T3_away_2": Field("T3_away_2", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # BEING_AWAY · 在刚才的虚拟自然中待一会儿，让我从日常事务中好好歇了一下
        "T3_imi_choice_1": Field("T3_imi_choice_1", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # IMI_CHOICE · 在刚才的体验中，去哪里、看什么，是按我自己的意愿决定的
        "T3_imi_choice_2": Field("T3_imi_choice_2", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # IMI_CHOICE · 在刚才的体验中，在哪里停留、停留多久，是我自己做的决定
        "T3_imi_choice_3": Field("T3_imi_choice_3", "Int64", levels=(1, 2, 3, 4, 5, 6, 7)),  # IMI_CHOICE · 在刚才的体验中，看什么都是被安排好的，由不得我
        "T3_fms": Field("T3_fms", "Int64", levels=tuple(range(0, 21))),  # 在刚才的体验中，你最不舒服的时候，头晕、恶心或胃部不适的程度是多少？（0 完全没有不适 → 20 明显的晕动或恶心）
    },
}

# ------------------------------------------------------------------
# 各量表的计分口径：反向计分题、分值换算、合计方式、分类界值。对应 METRICS["track"]
# 的写法——登记名称、定义、输入字段、参数、输出、确认状态、规范出处；计算函数不放
# 在这里，以后实现到 analysis/table_flows/psycho/ 的制表逻辑里。
#
# 重要：PSYCHO_SCHEMA 里矩阵题存的是"选项下标"（0 起），下面的计分口径里写的
# "换算成 1-4 分"等，是指下标 + value_start 之后的分数，不是下标本身；数字量表
# （注意题、意义题、迷恋/远离、IMI 感知选择）存的本来就是分数，不用换算。
# ------------------------------------------------------------------
PSYCHO_METRICS = {
    "stait_total": {
        "name": "STAI-T 特质焦虑总分",
        "definition": "20 题每题选项下标 + 1 转换为 1-4 分；反向计分题（第 1、3、6、7、10、13、"
                      "14、16、19 题）取 5 − 原始分；20 题相加，总分 20-80。总分 ≥ cutoff 为"
                      "“高焦虑”层，< cutoff 为“低焦虑”层。",
        "inputs": tuple("PSYCHO_SCHEMA.T0.T0_stait_%d" % i for i in range(1, 21)),
        "parameters": {
            "reverse_items": (1, 3, 6, 7, 10, 13, 14, 16, 19),
            "value_start": 1, "cutoff": 41,
        },
        "output": "总分（20-80）；分类（高焦虑/低焦虑）",
        "status": "界值 41 分是根据 Han et al. (2020) 的表格换算推断出来的，研究者尚未核对原文，"
                  "需要研究确认（交接文档第十节）。流程单系统第 11 页“揭晓组别”已有同款计分实现"
                  "（app/judging.py 的 stait_total_score/stait_classification），是实验现场"
                  "用来实时分组的即时计算，不是这份规范的权威来源，确认后以这里登记的为准。",
        "source": "研究思路/实验记录-问卷草稿.md B1",
    },
    "cns_total": {
        "name": "CNS 自然联结量表总分",
        "definition": "14 题每题选项下标 + 1 转换为 1-5 分；反向计分题（第 4、12、14 题）取 "
                      "6 − 原始分；14 题相加或取均分。",
        "inputs": tuple("PSYCHO_SCHEMA.T0.T0_cns_%d" % i for i in range(1, 15)),
        "parameters": {"reverse_items": (4, 12, 14), "value_start": 1},
        "output": "总分（14-70）或均分（1-5），用哪个未定",
        "status": "未确认：报总分还是均分、是否沿用这组反向计分题，都需要研究确认",
        "source": "研究思路/实验记录-问卷草稿.md B2",
    },
    "gad2_total": {
        "name": "GAD-2 广泛性焦虑筛查总分",
        "definition": "2 题每题选项下标直接计分（0-3，value_start=0，不用转换）相加，0-6 分。"
                      "总分 ≥ cutoff 时文档里建议提示“不适合”。",
        "inputs": ("PSYCHO_SCHEMA.A.A_gad2_1", "PSYCHO_SCHEMA.A.A_gad2_2"),
        "parameters": {"value_start": 0, "cutoff": 3},
        "output": "总分（0-6）",
        "status": "流程单系统第 3 页目前只接入了 A2 筛查题（第 1-4 项）的纳入建议，GAD-2 这条"
                  "“≥3 分建议不适合”的规则还没有在系统里实现，需要研究确认是否要补上",
        "source": "研究思路/实验记录-问卷草稿.md A3",
    },
    "stai6_total": {
        "name": "STAI-6 状态焦虑简版总分",
        "definition": "6 题每题选项下标 + 1 转换为 1-4 分；反向计分题（第 1、4、5 题）取 "
                      "5 − 原始分；6 题相加。是否需要再按 STAI-6 常见公式（总分 / 6 × 20）"
                      "换算成与 20 题版可比的分数，未确认。",
        "inputs": tuple("PSYCHO_SCHEMA.<T1/T2/T3>.<前缀>_stai6_%d" % i for i in range(1, 7)),
        "parameters": {"reverse_items": (1, 4, 5), "value_start": 1},
        "output": "原始合计（6-24）；换算分（如需要）",
        "status": "是否换算成 20 题等效分未确认",
        "source": "研究思路/实验记录-问卷草稿.md C1",
    },
    "anxiety_vas": {
        "name": "焦虑 VAS",
        "definition": "直接读取 0-100 滑块值，数值越大越焦虑，不用转换。",
        "inputs": ("PSYCHO_SCHEMA.<T1/T2/T3>.<前缀>_vas",),
        "parameters": {},
        "output": "0-100",
        "status": "已定",
        "source": "研究思路/实验记录-问卷草稿.md C2",
    },
    "panas": {
        "name": "I-PANAS-SF 积极/消极情绪分",
        "definition": "10 题每题选项下标 + 1 转换为 1-5 分，无反向计分题；positive_items 五题"
                      "相加为积极情绪分，negative_items 五题相加为消极情绪分。",
        "inputs": tuple("PSYCHO_SCHEMA.<T1/T2/T3>.<前缀>_panas_%d" % i for i in range(1, 11)),
        "parameters": {
            "value_start": 1,
            "positive_items": (3, 5, 7, 8, 10), "negative_items": (1, 2, 4, 6, 9),
        },
        "output": "积极情绪分（5-25）；消极情绪分（5-25）",
        "status": "已定",
        "source": "研究思路/实验记录-问卷草稿.md C3",
    },
    "msbs8_total": {
        "name": "MSBS-8 状态无聊量表总分",
        "definition": "8 题每题选项下标 + 1 转换为 1-7 分，无反向计分题；8 题相加或取均分。",
        "inputs": tuple("PSYCHO_SCHEMA.T3.T3_msbs_%d" % i for i in range(1, 9)),
        "parameters": {"value_start": 1},
        "output": "总分（8-56）或均分（1-7），用哪个未定",
        "status": "未确认报总分还是均分",
        "source": "研究思路/实验记录-问卷草稿.md E4",
    },
    "attention": {
        "name": "注意困难指数",
        "definition": "4 题，1-7 数字量表存的就是选择的数字本身（不是下标）；第 2 题反向计分，"
                      "取 8 − 原始分（min+max=1+7=8）；4 题求均分，分数越高表示注意越不顺。",
        "inputs": tuple("PSYCHO_SCHEMA.T3.T3_attention_%d" % i for i in range(1, 5)),
        "parameters": {"reverse_items": (2,), "scale_min": 1, "scale_max": 7},
        "output": "均分（1-7）",
        "status": "改编自 Westgate & Wilson (2018) Study 2 的注意操纵检验，原文无逐字题目，"
                  "中文措辞按题意改编；第 1 题与 MSBS-8“容易分心”、第 4 题与“我在走神”内容"
                  "相近，分析“注意 → 无聊”时需说明这一重叠会抬高两者的相关。",
        "source": "研究思路/实验记录-问卷草稿.md E5",
    },
    "fascination": {
        "name": "迷恋分量表",
        "definition": "5 题，1-7 数字量表存的就是选择的数字本身，全部正向，无反向计分题；"
                      "5 题求均分。",
        "inputs": tuple("PSYCHO_SCHEMA.T3.T3_fascination_%d" % i for i in range(1, 6)),
        "parameters": {"scale_min": 1, "scale_max": 7},
        "output": "均分（1-7）",
        "status": "2026-11-02 新增，替换原 IMI 兴趣/愉悦 5 题。改编自 Hartig et al. (1997) PRS"
                  "迷恋分量表（Study 2 版题项），中文为本研究自译，需找人回译。",
        "source": "研究思路/实验记录-问卷草稿.md E7",
    },
    "being_away": {
        "name": "远离分量表",
        "definition": "2 题，1-7 数字量表存的就是选择的数字本身，全部正向，无反向计分题；"
                      "2 题求均分。",
        "inputs": tuple("PSYCHO_SCHEMA.T3.T3_away_%d" % i for i in range(1, 3)),
        "parameters": {"scale_min": 1, "scale_max": 7},
        "output": "均分（1-7）",
        "status": "2026-11-02 新增，和迷恋分量表同页、共用同一句指导语。改编自 Hartig et al. "
                  "(1997) PRS 远离分量表，中文为本研究自译，需找人回译。",
        "source": "研究思路/实验记录-问卷草稿.md E7",
    },
    "imi_choice": {
        "name": "IMI 感知选择分量表",
        "definition": "3 题，1-7 数字量表存的就是选择的数字本身；第 3 题反向计分，取 "
                      "8 − 原始分；3 题相加或取均分。",
        "inputs": tuple("PSYCHO_SCHEMA.T3.T3_imi_choice_%d" % i for i in range(1, 4)),
        "parameters": {"reverse_items": (3,), "scale_min": 1, "scale_max": 7},
        "output": "总分（3-21）或均分（1-7），用哪个未定",
        "status": "未确认报总分还是均分。2026-11-02 起和迷恋/远离同页、共用同一句指导语",
        "source": "研究思路/实验记录-问卷草稿.md E8",
    },
    "meaning": {
        "name": "意义题",
        "definition": "3 题，1-7 数字量表存的就是选择的数字本身，无反向计分题；3 题相加或"
                      "取均分。",
        "inputs": tuple("PSYCHO_SCHEMA.T3.T3_meaning_%d" % i for i in range(1, 4)),
        "parameters": {"scale_min": 1, "scale_max": 7},
        "output": "总分（3-21）或均分（1-7），用哪个未定",
        "status": "未确认报总分还是均分。2026-11-01 点数由 1-9 改为 1-7，和注意题共用同一组选项",
        "source": "研究思路/实验记录-问卷草稿.md E6",
    },
    "fms": {
        "name": "FMS 晕动量表",
        "definition": "单题，0-20 滑块，直接读取，数值越大越不适，不用转换。",
        "inputs": ("PSYCHO_SCHEMA.T3.T3_fms",),
        "parameters": {},
        "output": "0-20",
        "status": "已定",
        "source": "研究思路/实验记录-问卷草稿.md E9",
    },
    "a2_screening": {
        "name": "A2 筛查多选·纳入建议",
        "definition": "8 个布尔列（A_screen_1…A_screen_8）。第 1-4 项（精神/心理疾病史、正在"
                      "接受心理或精神科治疗、心脏或血管疾病、癫痫或闪烁画面不适史）命中任一项，"
                      "建议谨慎判断是否纳入；第 5-7 项（服药、屏幕/游戏头晕恶心、参加过预实验）"
                      "仅供参考，不直接建议排除；第 8 项“以上都没有”与其余互斥。",
        "inputs": tuple("PSYCHO_SCHEMA.A.A_screen_%d" % i for i in range(1, 9)),
        "parameters": {"hard_exclusion_items": (1, 2, 3, 4), "soft_reference_items": (5, 6, 7)},
        "output": "命中的项目列表；纳入建议文字",
        "status": "流程单系统第 3 页“判定结果确认”已有同款提示（app/judging.py 的"
                  "a_screening_summary），是实验现场辅助实验员判断的即时计算，不是这份规范的"
                  "权威来源，确认后以这里登记的为准",
        "source": "研究思路/实验记录-问卷草稿.md A2",
    },
}
