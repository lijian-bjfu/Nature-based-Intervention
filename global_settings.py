"""共享数据规范：原始结构、标签、单位及已经确认的指标定义。

table_flows 与 data_lab 共用本文件。运行选择、试验参数、任务依赖和输出路径不在这里。
埋点规范的依据是《研究思路/实验记录-埋点.md》；修改科学口径须先讨论并更新规范。
"""
from dataclasses import dataclass

SCHEMA_VERSION = "1.8"
DATA_OBJECTS = ("track", "psycho", "physio")   # 即 pipeline，命名规范见 analysis/tools/paths.py
MODULE_LABELS = {
    "Interactive": "自由交互体验",
    "Practice": "练习场（只有会话信息）",
    "Passive": "被动观看视频（当前只有会话信息）",
}

# 分类变量编码表：数据表里一律只存整数，含义以这里为准（2026-11-04 起）。
# 约定：是/否性质的二分变量用 0/1；组别是实验条件的名义因子，沿用 VN、流程单、LabRecorder 已在用的 1/2。
VALUE_LABELS = {
    "group": {1: "实验组（交互）", 2: "对照组"},
    "A_gender": {0: "男", 1: "女"},
    "T0_stait_level": {0: "低焦虑", 1: "高焦虑"},
    "time_code": {0: "T1 基线静息后", 1: "T2 诱导后", 2: "T3 干预后"},
    "rr_handling": {0: "原样保留", 1: "漏检补拍", 2: "多检合并", 3: "异位搏或长短拍校正", 4: "待人工（仍异常，未修改）"},
}

# 05 修改清单（clean/changes.csv）的类别与原因模板，2026-11-10 研究者确认。
# 键 "hole" 对应丢包空洞；整数键对应 rr_handling 编码（0 不是修改，不在清单中）。
RR_CHANGE_TYPES = {
    "hole": {"category": "切除", "reason": "数据丢失（丢包），未插补"},
    1: {"category": "补插", "reason": "漏检：RR 约为参考 RR 的整数倍，等分为多拍"},
    2: {"category": "编辑", "reason": "多检：两个相邻短间期合并为一拍"},
    3: {"category": "编辑", "reason": "异位搏或长短拍：Kubios 插值校正"},
    4: {"category": "切除", "reason": "规则无法还原：数值保留在 rr.csv，不参与计算"},
}

# 生理阶段事件（2026-11-08 定）：五个阶段各一对 start/end，共 10 个标签。
# 依据《研究思路/实验记录-实验流程骨架.md》及研究者确认；干预后静息不称为基线。
# 这是事件标识符，不是 VALUE_LABELS 中的整数分类变量；不包含诱导后静息。
PHYSIO_PHASES = {
    "training": "训练",
    "baseline": "基线",
    "induction": "诱导",
    "intervention": "干预",
    "post_intervention_rest": "干预后静息",
}
# 合表（integration 03）长表的窗口编号：按 PHYSIO_PHASES 的顺序编号 0–4（training=0 … post_intervention_rest=4）。
VALUE_LABELS["window_code"] = {i: name for i, name in enumerate(PHYSIO_PHASES.values())}
# 问卷列名前缀 → 测量时点。来源：研究思路/实验注册（2026-11-11 版）流程；2026-11-14 研究者确认
PSYCHO_TIMEPOINTS = {
    "A": "参加条件问卷（到场后，确认是否适合参加）",
    "T0": "分组前（佩戴 H10 后，STAI-T 与 CNS）",
    "T1": "基线静息后",
    "T2": "诱导（担忧书写）后",
    "T3": "干预后",
}
# 各阶段标准时长（秒）：结束减开始应等于此值。来源：2026-11-09 研究者确认；训练不检查（None）。
# 只用于 03 的时长提示和更正时的推算，不是取舍标准：实际时长偏离它的窗口照常计算指标（2026-11-11 研究者定）。
PHYSIO_PHASE_DURATION_S = {"training": None, "baseline": 300, "induction": 480, "intervention": 720, "post_intervention_rest": 300}
PHYSIO_EVENT_BOUNDARIES = {"start": "开始", "end": "结束"}
PHYSIO_MARKER_LABELS = tuple(
    f"{phase}_{boundary}"
    for phase in PHYSIO_PHASES for boundary in PHYSIO_EVENT_BOUNDARIES
)
# 采集端中文、自带英文按钮 → 统一英文标签。标准英文自身也可直接输入。
PHYSIO_MARKER_ALIASES = {
    f"{name}{suffix}": f"{phase}_{boundary}"
    for phase, name in PHYSIO_PHASES.items()
    for boundary, suffix in PHYSIO_EVENT_BOUNDARIES.items()
}
PHYSIO_MARKER_ALIASES.update({
    "stim_start": "induction_start",
    "stim_end": "induction_end",
    # 兼容先前短暂使用的名称；它们不是标准标签。
    "干预后基线开始": "post_intervention_rest_start",
    "干预后基线结束": "post_intervention_rest_end",
    "post_intervention_baseline_start": "post_intervention_rest_start",
    "post_intervention_baseline_end": "post_intervention_rest_end",
})
# markers.csv：label 存规范名称，label_raw 原样保留采集标签；未知标签原样保留并在报告提示。
# gap_* 是质量记录，单独进入 gaps.csv，不做阶段映射。stop 等旧标签不猜测其阶段含义。
# 仅规范名称，不补配对、不改顺序或时间；误打/漏打留给人工更正流程。

# raw 目录结构（2026-11-04 起，三个 pipeline 与 session_notes 相同）：
#   data/<dataset>/raw/<pipeline>/sub-P001/<该被试的记录文件>
# 每名被试一个 sub-P### 文件夹；不用于分析的文件放在被试文件夹下的 _excluded/，读取时跳过。
# 每个被试只来一次，命名中不再含 session（ses-S###）。
SUBJECT_DIR_GLOB = "sub-P*"
SUBJECT_DIR_REGEX = r"^sub-P(?P<subject>\d+)$"
EXCLUDED_DIR = "_excluded"
# track：被试文件夹内每份 VN 记录一个文件夹，名字由 APP 生成，例 sub-P001_mod-Interactive_run-001
TRACK_SESSION_GLOB = "sub-P*_mod-*"
TRACK_SESSION_REGEX = (
    r"^sub-P(?P<subject>\d+)_mod-"
    r"(?P<module>Practice|Interactive|Passive)_run-(?P<run>\d+)$"
)
TRACK_RECORDING = {"spacetime_interval_seconds": 0.1, "yaw_zero": "+Z", "pitch_positive": "up"}

@dataclass(frozen=True)
class Field:
    column: str
    dtype: str
    unit: str | None = None
    levels: tuple | None = None

# H10 ACC 原始导出字段；02 拼接后另有 t_unix（Unix秒）与 part（录制段）。
# 单位 mG 是千分之一重力加速度；不代表质量单位 mg。
PHYSIO_ACC_SCHEMA = {
    "time_lsl": Field("time_lsl", "Float64", unit="s"),
    **{f"{axis}_mG": Field(f"{axis}_mG", "Float64", unit="mG") for axis in "xyz"},
}
PHYSIO_ACC_LABELS = {"time_lsl": "LSL 时间（秒，xdf 时间戳）",
                     **{f"{axis}_mG": f"{axis.upper()} 轴加速度（毫 g）" for axis in "xyz"}}

# 每行依次写明：实际列名、类型、单位、分类取值；没有按名字猜测类型的规则。
TRACK_SCHEMA = {
    'session': {
        'subject': Field('subject', 'Int64'),
        'group': Field('group', 'Int64', levels=(1, 2)),
        'module': Field('module', 'string', levels=('Practice', 'Interactive', 'Passive')),
        't_device_start': Field('t_device_start', 'Float64', unit='s'),
        't_device_end': Field('t_device_end', 'Float64', unit='s'),
        # 产生这份数据的虚拟自然 APP 代码版本（Git 提交号，可带 -dirty）。两项目间的约定机制，
        # 见虚拟自然工程 Assets/_Project/Interaction/README.md 第十五节。
        'app_commit': Field('app_commit', 'string'),
    },
    'spacetime': {
        't_session': Field('t_session', 'Float64', unit='s'),
        't_device': Field('t_device', 'Float64', unit='s'),
        'cam_x': Field('cam_x', 'Float64', unit='m'),
        'cam_y': Field('cam_y', 'Float64', unit='m'),
        'cam_z': Field('cam_z', 'Float64', unit='m'),
        'ground_y': Field('ground_y', 'Float64', unit='m'),
        'view_yaw': Field('view_yaw', 'Float64', unit='degree'),
        'view_pitch': Field('view_pitch', 'Float64', unit='degree'),
    },
    'tap': {
        'touch_id': Field('touch_id', 'Int64'),
        't_session': Field('t_session', 'Float64', unit='s'),
        't_device': Field('t_device', 'Float64', unit='s'),
        'cam_x': Field('cam_x', 'Float64', unit='m'),
        'cam_y': Field('cam_y', 'Float64', unit='m'),
        'cam_z': Field('cam_z', 'Float64', unit='m'),
        'intent': Field('intent', 'string', levels=('NoHit', 'WalkTo', 'LookAt')),
        'hit_layer': Field('hit_layer', 'string', levels=('Terrain', 'Road', 'Rock', 'DeadWood', 'Flower', 'Creature', 'TouchFoliage', 'SweepFoliage', 'TouchRigid', 'WaterTouchSurface', 'NoHit')),
        'hit_x': Field('hit_x', 'Float64', unit='m'),
        'hit_y': Field('hit_y', 'Float64', unit='m'),
        'hit_z': Field('hit_z', 'Float64', unit='m'),
        'is_touched': Field('is_touched', 'boolean', levels=(True, False)),
        'block_type': Field('block_type', 'string', levels=('NotBlocked', 'CutShort', 'NoStart')),
        'block_reason': Field('block_reason', 'string', levels=('NotBlocked', 'BarrierDenseSlope', 'BarrierWater', 'BarrierUnlabeled', 'StepUp', 'DropTooHigh', 'TooSteep', 'NoGround')),
        # 触摸进行中（下蹲或伸手开始到手收回）APP 不响应，这期间的点击照记并标 TRUE（2026-10-28 加列）
        'touch_locked': Field('touch_locked', 'boolean', levels=(True, False)),
    },
    'backstep': {
        'touch_id': Field('touch_id', 'Int64'),
        't_session': Field('t_session', 'Float64', unit='s'),
        't_device': Field('t_device', 'Float64', unit='s'),
        'cam_x': Field('cam_x', 'Float64', unit='m'),
        'cam_y': Field('cam_y', 'Float64', unit='m'),
        'cam_z': Field('cam_z', 'Float64', unit='m'),
        'back_dist': Field('back_dist', 'Float64', unit='m'),
        'block_type': Field('block_type', 'string', levels=('NotBlocked', 'CutShort', 'NoStart')),
        'block_reason': Field('block_reason', 'string', levels=('NotBlocked', 'BarrierDenseSlope', 'BarrierWater', 'BarrierUnlabeled', 'StepUp', 'DropTooHigh', 'TooSteep', 'NoGround')),
    },
    'look': {
        'touch_id': Field('touch_id', 'Int64'),
        't_session_start': Field('t_session_start', 'Float64', unit='s'),
        't_device_start': Field('t_device_start', 'Float64', unit='s'),
        't_session_end': Field('t_session_end', 'Float64', unit='s'),
        't_device_end': Field('t_device_end', 'Float64', unit='s'),
        'yaw_start': Field('yaw_start', 'Float64', unit='degree'),
        'pitch_start': Field('pitch_start', 'Float64', unit='degree'),
        'yaw_end': Field('yaw_end', 'Float64', unit='degree'),
        'pitch_end': Field('pitch_end', 'Float64', unit='degree'),
        'yaw_delta': Field('yaw_delta', 'Float64', unit='degree'),
        'pitch_delta': Field('pitch_delta', 'Float64', unit='degree'),
        'yaw_path': Field('yaw_path', 'Float64', unit='degree'),
        'pitch_path': Field('pitch_path', 'Float64', unit='degree'),
        'look_type': Field('look_type', 'string', levels=('Drag', 'Tap')),
    },
    'world_event': {
        't_session': Field('t_session', 'Float64', unit='s'),
        't_device': Field('t_device', 'Float64', unit='s'),
        'event_name': Field('event_name', 'string'),
        'action': Field('action', 'string', levels=('Fired', 'NotFired', 'HandStartle')),
        'cam_x': Field('cam_x', 'Float64', unit='m'),
        'cam_y': Field('cam_y', 'Float64', unit='m'),
        'cam_z': Field('cam_z', 'Float64', unit='m'),
        'detail': Field('detail', 'string'),
    },
    'tech_glitch': {
        't_session': Field('t_session', 'Float64', unit='s'),
        't_device': Field('t_device', 'Float64', unit='s'),
        'status': Field('status', 'string', levels=('Background', 'Freeze')),
        'duration': Field('duration', 'Float64', unit='s'),
    },
}

# 下列索引仅从上面的单一 schema 生成，供脚本使用；不手工维护第二份 columns。
TRACK_TABLES = tuple(TRACK_SCHEMA)
TRACK_FILES = {name: name + ".csv" for name in TRACK_TABLES}
TRACK_COLUMNS = {table: {key: field.column for key,field in fields.items()}
               for table,fields in TRACK_SCHEMA.items()}
TRACK_TYPES = {key: field.dtype for fields in TRACK_SCHEMA.values() for key,field in fields.items()}
TRACK_UNITS = {key: field.unit for fields in TRACK_SCHEMA.values() for key,field in fields.items()
             if field.unit is not None}
TRACK_LEVELS = {table: {key: field.levels for key,field in fields.items() if field.levels is not None}
              for table,fields in TRACK_SCHEMA.items() if any(f.levels is not None for f in fields.values())}
PRECISION = {"s": 3, "m": 2, "degree": 1}
TRACK_LEGACY_VALUES = {
    "tap": {"intent": {"None": "NoHit"}, "hit_layer": {"None": "NoHit"},
            "block_type": {"None": "NotBlocked"}, "block_reason": {"None": "NotBlocked"}},
    "backstep": {"block_type": {"None": "NotBlocked"}, "block_reason": {"None": "NotBlocked"}},
}
# 早期数据缺少的列（加列之前录制的数据）：读取时补为空，不报错。
TRACK_LEGACY_MISSING = {"session": ("app_commit",), "tap": ("touch_locked",)}
# 早期数据多出、现已取消的列：读取时丢弃，不报错（2026-11-04 起 APP 不再写 session 列）。
TRACK_LEGACY_EXTRA = {"session": ("session",)}
TRACK_TRUE = "TRUE"
TRACK_FALSE = "FALSE"
TRACK_CSV = {"encoding": "utf-8-sig", "keep_default_na": False, "na_values": [""]}
TRACK_REQUIRED_TABLES = {
    "Interactive": TRACK_TABLES, "Practice": ("session",), "Passive": ("session",),
}

# 地理空间标注：叠加在 Unity 世界坐标上的空间结构（区域、桥、景点、空气墙），由虚拟自然工程
# Tools ▸ NBI ▸ 地理空间标注 导出为一个 JSON 文件；文件位置见 analysis/tools/paths.py 的 GEO_ANNOTATION。
# 区域与桥互不重叠、合起来覆盖能走到的地方；景点与区域相互独立，可越出区域边界；
# 编号由研究者手动指定，代表空间设计意图。空气墙只有折线位置，不区分阻挡类型。
GEO_ANNOTATION_SPEC = {
    "format": "nbi_geo_annotation",
    "format_version": 3,
    "kinds": {"region": "区域", "bridge": "桥", "attractive_point": "景点"},
    "id_regex": {"region": r"^R[1-9]\d*$", "bridge": r"^B[1-9]\d*$", "attractive_point": r"^AP[1-9]\d*$"},
    "coordinates": "Unity 世界坐标，米；points 为水平坐标 [x, z]",
}

# 埋点分析窗口（2026-11-10 研究者确认）：埋点指标一律只算干预窗口，不按 App 整段记录算。
#   events：窗口起止事件的标签，取自生理 03 更正后的事件（events/markers.csv），各须恰好一条；
#           事件时间经 t_device 与 t_session 之差的中位数换算为会话时间，不加余量。
#   fallback_duration_s：没有生理数据、或两个事件标签不全时的退路：从 App 记录起点切这么长（750 s = 12 分 30 秒）。
TRACK_ANALYSIS_WINDOW = {
    "events": ("intervention_start", "intervention_end"),   # 取自生理 03 更正后的事件
    "fallback_duration_s": 750,                              # 无事件标记时：从 App 记录起点切 12 分 30 秒
}

# 指标须经过研究讨论后逐项登记；候选指标及其试验阈值留在具体实验中。
# 登记应包含名称、定义、输入字段、输出单位、计算口径和规范出处；计算函数不放在这里。
METRICS = {
    "track": {
        "stay_walk": {
            "name": "停留与行走",
            "definition": "相邻采样水平位移不超过 still_step_m（且单步间隔不超过 max_gap_s）算没动，连续没动为一次停顿；"
                          "持续不少于 min_stay_seconds 的停顿为停留，其余时间为行走。二者切分全程",
            "inputs": ("spacetime.t_session", "spacetime.cam_x", "spacetime.cam_z"),
            "parameters": {"still_step_m": 0.03, "min_stay_seconds": 2.0, "max_gap_s": 1.0},
            "output": "停留：次数、总时长（s）、占比；行走：总时长（s）、占比、行走路程（m）",
            "status": "已定；2 秒为概念决定，数据中无自然断档",
            "source": "研究思路/实验记录-埋点.md 10.1",
        },
        "dwell": {
            "name": "逗留",
            "definition": "把相邻的停顿串起来，从第一次停顿到最后一次停顿，所有位置到其平均位置的水平距离不超过 radius_m，"
                          "且持续不少于 min_seconds，记为一次逗留；中间的小移动算在内，进出的路不算。",
            "pause_definition": "相邻采样水平位移不超过 still_step_m 算没动，连续没动为一次停顿，长短不限",
            "inputs": ("spacetime.t_session", "spacetime.cam_x", "spacetime.cam_z"),
            "parameters": {"min_seconds": 15.0, "radius_m": 3.0, "still_step_m": 0.03},
            "output": "逗留段：起止 t_session（s）、中心 [x, z]（m）、活动半径（m）",
            "status": "暂定：由研究者人工判断校准（一名熟练操作者的一次记录），须用预实验数据重新评估",
            "source": "研究思路/实验记录-埋点.md 10.2（停顿见 10.1）",
        },
        "footprint": {
            "name": "行动范围",
            "definition": "沿行走路径以 brush_radius_m 为半径涂抹，涂到的水平面积；可按区域、桥分别统计，可按时间累计",
            "inputs": ("spacetime.t_session", "spacetime.cam_x", "spacetime.cam_z", "geo_annotation.polygons"),
            "parameters": {"brush_radius_m": 0.7},
            "brush_radius_source": "场景手部水平可达距离 reach radius（IndicatorHand.reachRadius）",
            "denominator": "场景可达范围：从各桥中心出发，不穿过空气墙、不越出区域与桥的多边形能到达的范围；整个场景只算一次，所有被试共用",
            "output": "行动范围（m²），各区域/桥覆盖面积（m²），占场景可达范围比例，累计曲线",
            "status": "已定；可达范围在部分靠地形阻挡的边缘偏大，区域间比较前需收紧这些区域边界",
            "source": "研究思路/实验记录-埋点.md 10.3",
        },
        "tap_count": {
            "name": "点击量",
            "definition": "点击表的行数；除以干预时长为点击频率（次/分钟），可按分钟统计",
            "inputs": ("tap.t_session", "session.t_device_start", "session.t_device_end"),
            "parameters": {},
            "output": "次；次/分钟",
            "status": "已定",
            "source": "研究思路/实验记录-埋点.md 10.4",
        },
        "no_move_tap": {
            "name": "无位移点击",
            "definition": "起步受阻（block_type = NoStart）；或命中地面/路面、未判受阻、点击后到下一次点击前（最多 window_seconds）水平位移不足 min_move_m；或没打中（intent = NoHit）。触摸锁定中的点击（touch_locked = TRUE）不计",
            "inputs": ("tap.t_session", "tap.intent", "tap.hit_layer", "tap.block_type", "tap.touch_locked", "spacetime.t_session", "spacetime.cam_x", "spacetime.cam_z"),
            "parameters": {"min_move_m": 0.3, "window_seconds": 8.0, "ground_layers": ("Terrain", "Road")},
            "output": "次；占全部点击的比例",
            "status": "已定；不含半路被截（CutShort），与日志字段 block_type 不同",
            "source": "研究思路/实验记录-埋点.md 10.5",
        },
        "ap_visit": {
            "name": "景点到访",
            "definition": "一次逗留期间任一位置到某景点多边形的水平距离不超过 reach_m（多边形内为 0），记为在该景点逗留一次；"
                          "到访景点数＝逗留过的不同景点个数，景点逗留次数＝（逗留, 景点）组合数",
            "inputs": ("METRICS.track.dwell", "spacetime.cam_x", "spacetime.cam_z", "geo_annotation.polygons[attractive_point]"),
            "parameters": {"reach_m": 0.7},
            "output": "到访景点数（个），景点逗留次数（次）；分景点明细仅用于评估景点设计",
            "status": "已定",
            "source": "研究思路/实验记录-埋点.md 10.6",
        },
        "approach": {
            "name": "Approach",
            "definition": "命中可触摸层（approach_layers）、但最终没有摸到（is_touched = FALSE）的点击；触摸锁定中的点击不计",
            "inputs": ("tap.hit_layer", "tap.is_touched", "tap.touch_locked", "tap.t_session"),
            "parameters": {"approach_layers": ("TouchFoliage", "SweepFoliage", "TouchRigid", "DeadWood", "WaterTouchSurface", "Creature")},
            "parameters_source": "与虚拟自然 APP TapMoveCamera_V5.TouchableMask（四张触摸表的并集）同源（2026-10-28 预制体中的取值）；APP 改动触摸表时需同步。"
                                 "2026-10-28 起一击即摸，此前数据是旧规则（远处点一下只走过去）下的结果",
            "output": "次；次/分钟",
            "status": "已定；系统事件，用于评估设计策略，不作为被试意图的证据",
            "source": "研究思路/实验记录-埋点.md 10.7",
        },
        "touch": {
            "name": "触摸",
            "definition": "is_touched = TRUE 的点击",
            "inputs": ("tap.is_touched", "tap.t_session"),
            "parameters": {},
            "output": "次；次/分钟",
            "status": "已定",
            "source": "研究思路/实验记录-埋点.md 10.8",
        },
        "first_touch_time": {
            "name": "首次触摸时间",
            "definition": "第一次触摸（METRICS.track.touch）的 t_session；整场无触摸记为缺失，另报无触摸人数",
            "inputs": ("tap.is_touched", "tap.t_session"),
            "parameters": {},
            "output": "s",
            "status": "已定",
            "source": "研究思路/实验记录-埋点.md 10.9",
        },
        "touched_ap_count": {
            "name": "触摸过的景点数",
            "definition": "触摸命中位置到景点多边形的水平距离不超过 reach_m（多边形内为 0）即摸过该景点；摸过的不同景点个数",
            "inputs": ("tap.is_touched", "tap.hit_x", "tap.hit_z", "geo_annotation.polygons[attractive_point]"),
            "parameters": {"reach_m": 0.7},
            "output": "个",
            "status": "已定",
            "source": "研究思路/实验记录-埋点.md 10.10",
        },
        "backstep_count": {
            "name": "长按后退次数",
            "definition": "后退表的行数；可附后退总距离与受阻情况",
            "inputs": ("backstep.t_session", "backstep.back_dist", "backstep.block_type"),
            "parameters": {},
            "output": "次",
            "status": "已定",
            "source": "研究思路/实验记录-埋点.md 10.11",
        },
        "look": {
            "name": "环视",
            "definition": "拖动开始前 walking_window_s 秒内没有移动（相邻采样位移不超过 still_step_m）的手动拖动（look_type = Drag），"
                          "按 touch_id 合并为一次；角度、速度不限",
            "inputs": ("look.touch_id", "look.look_type", "look.t_session_start", "look.yaw_path", "look.pitch_path",
                       "spacetime.t_session", "spacetime.cam_x", "spacetime.cam_z"),
            "parameters": {"walking_window_s": 0.3, "still_step_m": 0.03},
            "output": "环视次数（次）；环视量：左右累计（°）、上下累计（°），分开报告",
            "status": "已定；受阻后环视、混乱旋转待有更多数据再观察",
            "source": "研究思路/实验记录-埋点.md 10.12",
        },
    },
    "psycho": {},
    "physio": {
        "acc_enmo_mean": {
            "name": "基线校正的平均加速度活动量",
            "definition": "vm=sqrt(x_mG²+y_mG²+z_mG²)；同一被试有效baseline窗口内全部有效样本的vm中位数为g0，"
                          "各阶段共用；指标为窗口内max(vm-g0,0)的样本算术均值。时间与三轴均须为有限数字；"
                          "样本按[t_start,t_end)取窗，不插补、不填充丢包；按实际观测样本平均，不作时间加权。"
                          "ACC缺失、基线无法确定或无有效样本、目标窗口无法确定或无有效样本时留空并报告；"
                          "不逐窗口另估g0，不依赖HRV合格标记。属于基线校正ENMO变体，不等于标准传感器校准，也不是物理动量",
            "inputs": ("merged/acc.csv:t_unix,x_mG,y_mG,z_mG", "events/windows.csv"),
            "parameters": {"reference_window": "baseline", "reference_estimator": "median"},
            "output": "mG",
            "status": "2026-11-18研究者确认；用于HRV协变量候选，不自动改变确证性模型",
            "source": "研究者确认；参考PhysicoAnalysis/scripts/features/hrv_acc.py的ENMO思路，改为基线全部有效样本的中位数",
        },
        "window_quality": {
            "name": "窗口质量",
            "definition": "valid_beat：handling 为 0–3 的拍（4 为待人工，一律排除）；real_beat：handling 为 0 或 2 的拍（原样保留、多检合并），"
                          "handling 1、3 是推算值，在 HRV 中按空洞处理。"
                          "hr_coverage = 窗口内 valid_beat 的 RR 之和 / 窗口时长；hrv_coverage = 窗口内 real_beat 的 RR 之和 / 窗口时长。"
                          "hr_ok = hr_coverage ≥ hr_min_coverage；hrv_ok = hrv_coverage ≥ hrv_min_coverage；不合格时数值照常输出，只标记。"
                          "real_beat 的 RR 之和不足 min_real_seconds 时 HRV 指标留空。"
                          "窗口按 03 给出的实际起止时刻计算；窗口时长偏离标准时长不影响计算，只在 note 中提示。"
                          "只有窗口无法确定（缺失、重复、顺序冲突）时才不计算",
            "inputs": ("windows.duration_s", "clean_rr.t_unix", "clean_rr.ms", "clean_rr.handling"),
            "parameters": {"hrv_min_coverage": 0.90, "hr_min_coverage": 0.80, "min_real_seconds": 60},
            "output": "hr_coverage、hrv_coverage；hr_ok、hrv_ok",
            "status": "已定 2026-11-09（修订）；2026-11-11 明确窗口时长偏差不丢数据",
            "source": "研究思路/分析工具迁移与整合工作计划.md 窗口指标口径",
        },
        "hr_mean": {
            "name": "平均心率",
            "definition": "60000 / 窗口内 valid_beat 的 RR 均值（ms）",
            "inputs": ("clean_rr.ms", "clean_rr.handling"),
            "parameters": {},
            "output": "bpm",
            "status": "已定 2026-11-09（修订）",
            "source": "研究思路/分析工具迁移与整合工作计划.md 窗口指标口径",
        },
        "rmssd": {
            "name": "RMSSD",
            "definition": "相邻两拍之差的均方根。只用 clean/rr.csv 中前后相邻、两拍都是 real_beat 且后一拍 gap_before = 0 的相邻对"
                          "（不跨丢包空洞，也不跨推算或被排除的拍）；只用 real_beat",
            "inputs": ("clean_rr.ms", "clean_rr.handling", "clean_rr.gap_before"),
            "parameters": {},
            "output": "ms",
            "status": "已定 2026-11-09（修订）",
            "source": "研究思路/分析工具迁移与整合工作计划.md 窗口指标口径",
        },
        "ln_rmssd": {
            "name": "lnRMSSD",
            "definition": "rmssd 的自然对数",
            "inputs": ("METRICS.physio.rmssd",),
            "parameters": {},
            "output": "ln(ms)",
            "status": "已定 2026-11-09（修订）",
            "source": "研究思路/分析工具迁移与整合工作计划.md 窗口指标口径",
        },
        "sdnn": {
            "name": "SDNN",
            "definition": "窗口内 real_beat 的 RR 标准差（ddof = 1）；只用 real_beat",
            "inputs": ("clean_rr.ms", "clean_rr.handling"),
            "parameters": {},
            "output": "ms",
            "status": "已定 2026-11-09（修订）",
            "source": "研究思路/分析工具迁移与整合工作计划.md 窗口指标口径",
        },
        "hf": {
            "name": "HF 功率",
            "definition": "Lomb-Scargle 周期图：采样点为窗口内 real_beat（只用 real_beat），时刻取 t_unix（s），数值取 ms 并减去均值；"
                          "不插补，空洞和被排除的拍直接缺席。功率谱密度（ms²/Hz）在 band_hz 内积分。有效条件同 rmssd（real_beat 的 RR 之和不足 min_real_seconds 时留空）",
            "inputs": ("clean_rr.t_unix", "clean_rr.ms", "clean_rr.handling"),
            "parameters": {"band_hz": [0.15, 0.40], "freq_step_hz": 0.001},
            "output": "ms²",
            "status": "已定 2026-11-09（修订）",
            "source": "研究思路/分析工具迁移与整合工作计划.md 窗口指标口径",
        },
        "ln_hf": {
            "name": "lnHF",
            "definition": "hf 的自然对数",
            "inputs": ("METRICS.physio.hf",),
            "parameters": {},
            "output": "ln(ms²)",
            "status": "已定 2026-11-09（修订）",
            "source": "研究思路/分析工具迁移与整合工作计划.md 窗口指标口径",
        },
    },
}

TRANSFORM_METHODS = {
    "center": {"suffix": "_c",  "name": "总均值中心化", "definition": "减去全体被试的均值"},
    "z":      {"suffix": "_z",  "name": "标准化", "definition": "减去全体被试的均值后除以标准差（ddof = 1）"},
    "ln":     {"suffix": "_ln", "name": "自然对数", "definition": "取自然对数；≤ 0 的值留空"},
}
# 来源：研究思路/实验注册（2026-11-11 版）分析方法："STAI-T 与 CNS 做总均值中心化"；
# CNS 报总分还是均分未定，两者都出；2026-11-14 研究者确认。
TRANSFORMS = {
    "psycho": [   # 确证性转换：每次都算，不受任何参数影响
        {"source": "T0_stait_sum", "method": "center"},
        {"source": "T0_cns_sum",   "method": "center"},
        {"source": "T0_cns_mean",  "method": "center"},
    ],
}
# 最终合表规范（2026-11-15研究者确认）：文件名与字段组织属于共享数据规范；输出路径仍由 paths.py 管理。
INTEGRATION_TABLES = {
    "wide": {
        "filename": "wide.csv", "id_columns": ("subject", "group"), "row_key": ("subject",),
        "contents": "一人一行；问卷宽表全部得分与转换列，随后按PHYSIO_PHASES展开全部生理指标、质量列及note，列名为<window>_<列名>",
    },
    "long": {
        "filename": "long.csv", "id_columns": ("subject", "group", "window", "window_code", "time", "time_code"),
        "row_key": ("subject", "window"),
        # 2026-11-18：只有这些前缀的个人字段（含转换列）重复进长表。
        # 其他非T1/T2/T3列（例如跨时点差值）仅留宽表，不按差值后缀猜测。
        "person_column_prefixes": ("A_", "T0_"),
        "contents": "每人五个生理阶段；T1/T2/T3问卷列去时点前缀后放对应阶段，同一时点单次测量也保留；仅person_column_prefixes指定的个人字段及转换列重复五行，其他宽表派生列不自动进入长表；生理指标、质量列及note全部保留；无对应问卷时点的测量列留空",
    },
    "psycho_long": {
        "filename": "psycho_long.csv", "id_columns": ("subject", "group", "time", "time_code"),
        "row_key": ("subject", "time"), "contents": "保留既有问卷长表，每人T1–T3三行，补充个人协变量及转换列",
    },
    "physio_long": {
        "filename": "physio_long.csv", "id_columns": ("subject", "group", "window", "window_code"),
        "row_key": ("subject", "window"), "contents": "保留既有生理长表，每人五行，补充个人协变量及转换列",
    },
}
INTEGRATION_AUX_FILES = {"dictionary": "data_dictionary.csv", "report": "merge_report.txt",
                         "short_report": "short_report.txt"}
INTEGRATION_COVARIATES = ("A_age", "A_gender", "T0_stait_sum", "T0_stait_level", "T0_cns_sum", "T0_cns_mean")
# 阶段与阶段后问卷的配对，不表示两者同时采集；不能按time_code与window_code数字直接合并。
INTEGRATION_PHASE_TIMEPOINTS = {
    "training": None, "baseline": "T1", "induction": "T2", "intervention": "T3", "post_intervention_rest": None,
}
# 短表排除规范（2026-11-18 研究者确认）：默认保留完整版字段，仅排除固定基础字段。
# 中心化、标准化、差值等计算列不在此登记或按后缀筛选；在哪张完整版出现就随该表进入短表。
# 训练属于结构排除：宽表排除 training_ 列，长表排除训练行；编码保持不变。
# 原始得分的重复口径、筛查字段及生理诊断字段按确切名称排除，避免连带排除其转换列。
# 生理纳入由人工审查决定，04 不按 ok 筛行或清空数值，不改上游或 OSF 注册正文。
INTEGRATION_SHORT_EXCLUDED_PHYSIO = (
    "window_valid", "duration_s", "n_beats_valid", "n_real", "n_estimated", "n_review",
    "hr_coverage", "hrv_coverage", "hr_ok", "hrv_ok", "note", "hf",
)
INTEGRATION_SHORT_TABLES = {
    "wide_short": {
        "filename": "wide_short.csv", "source": "wide",
        "id_columns": ("subject", "group"),
        "exclude_columns": (
            "A_gad2_sum", "A_screen_hard", "T0_stait_sum", "T0_cns_sum", "T0_cns_mean",
            "T1_stai6_sum", "T1_msbs_sum", "T2_stai6_sum", "T2_msbs_sum",
            "T3_stai6_sum", "T3_msbs_sum", "T3_imi_choice_sum", "T3_meaning_sum",
        ) + tuple(f"{window}_{column}" for window in PHYSIO_PHASES
                  for column in INTEGRATION_SHORT_EXCLUDED_PHYSIO),
        "exclude_column_prefixes": ("training_",),
        "contents": "一人一行；按源列序保留全部非排除字段，计算列自动带入；无训练及固定诊断列",
    },
    "long_short": {
        "filename": "long_short.csv", "source": "long",
        "id_columns": ("subject", "group", "window", "window_code", "time", "time_code"),
        "exclude_windows": ("training",),
        "exclude_columns": (
            "A_age", "A_gender", "A_gad2_sum", "A_screen_hard",
            "T0_stait_sum", "T0_cns_sum", "T0_cns_mean",
            "stai6_sum", "msbs_sum", "imi_choice_sum", "meaning_sum",
        ) + INTEGRATION_SHORT_EXCLUDED_PHYSIO,
        "contents": "每人四阶段；按源列序保留非排除字段，包括源表已有的全部计算列；无训练行及固定诊断列",
    },
}
SCHEMAS = {"track": TRACK_SCHEMA}

def column(table, field, source="track"):
    return SCHEMAS[source][table][field].column if source != "track" else TRACK_COLUMNS[table][field]

def table_columns(table, source="track"):
    return tuple(column(table, field, source) for field in SCHEMAS[source][table])

def validate():
    person_prefixes = INTEGRATION_TABLES["long"]["person_column_prefixes"]
    if (not isinstance(person_prefixes, tuple) or not person_prefixes
            or any(not isinstance(p, str) or not p or not p.endswith("_") for p in person_prefixes)):
        raise ValueError("integration: long.person_column_prefixes 须为非空前缀元组，各项以 _ 结尾")
    if set(INTEGRATION_PHASE_TIMEPOINTS) != set(PHYSIO_PHASES):
        raise ValueError("integration: 长表对应关系必须覆盖全部生理阶段")
    if any(t is not None and t not in ("T1", "T2", "T3") for t in INTEGRATION_PHASE_TIMEPOINTS.values()):
        raise ValueError("integration: 阶段对应问卷时点只能是T1、T2、T3或空")
    filenames = [t["filename"] for t in INTEGRATION_TABLES.values()] + list(INTEGRATION_AUX_FILES.values())
    if len(filenames) != len(set(filenames)):
        raise ValueError("integration: 输出文件名不得重复")
    short_names = [t["filename"] for t in INTEGRATION_SHORT_TABLES.values()]
    if len(short_names) != len(set(short_names)) or set(short_names) & set(filenames):
        raise ValueError("integration: 简表输出文件名不得重复，也不得与整表或附件重名")
    for key, short in INTEGRATION_SHORT_TABLES.items():
        if short["source"] not in INTEGRATION_TABLES:
            raise ValueError(f"integration: 简表 {key} 的来源必须是 INTEGRATION_TABLES 中的整表")
        if "columns" in short:
            raise ValueError(f"integration: 简表 {key} 已改为排除式登记，不得再设置保留列 columns")
        for field in ("exclude_columns", "exclude_column_prefixes"):
            values = short.get(field, ())
            if not isinstance(values, (tuple, list)) or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"integration: 简表 {key} 的 {field} 必须为非空字符串清单")
            if len(set(values)) != len(values):
                raise ValueError(f"integration: 简表 {key} 的 {field} 不得重复")
        if any(c in short.get("exclude_columns", ()) or
               any(c.startswith(p) for p in short.get("exclude_column_prefixes", ()))
               for c in short["id_columns"]):
            raise ValueError(f"integration: 简表 {key} 的标识列不能被排除")
        if len(set(short["id_columns"])) != len(short["id_columns"]):
            raise ValueError(f"integration: 简表 {key} 的标识列不得重复")
        excluded = short.get("exclude_windows", ())
        if excluded and ("window" not in short["id_columns"] or
                         len(set(excluded)) != len(excluded) or
                         not set(excluded) <= set(PHYSIO_PHASES)):
            raise ValueError(f"integration: 简表 {key} 的排除窗口必须唯一、已登记，且来源及输出须包含 window")
        parent = set(INTEGRATION_TABLES[short["source"]]["id_columns"])
        if not set(short["id_columns"]) <= parent:
            raise ValueError(f"integration: 简表 {key} 的标识列必须来自来源整表的标识列")
    expected_markers = {
        f"{phase}_{boundary}"
        for phase in PHYSIO_PHASES for boundary in PHYSIO_EVENT_BOUNDARIES
    }
    if len(PHYSIO_MARKER_LABELS) != len(expected_markers) or set(PHYSIO_MARKER_LABELS) != expected_markers:
        raise ValueError("physio: 标准事件标签必须由全局阶段及开始/结束边界生成，且不得重复")
    for alias, target in PHYSIO_MARKER_ALIASES.items():
        if target not in expected_markers:
            raise ValueError(f"physio: 标签别名 {alias!r} 指向非标准标签 {target!r}")
        if alias in expected_markers and alias != target:
            raise ValueError(f"physio: 标签别名不得重新解释标准标签 {alias!r}")
    for source, tables in SCHEMAS.items():
        for table in tables:
            columns = table_columns(table, source)
            if len(set(columns)) != len(columns):
                raise ValueError(f"{source}.{table}: 实际列名重复")
