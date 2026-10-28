"""共享数据规范：原始结构、标签、单位及已经确认的指标定义。

table_flows 与 data_lab 共用本文件。运行选择、试验参数、任务依赖和输出路径不在这里。
埋点规范的依据是《研究思路/实验记录-埋点.md》；修改科学口径须先讨论并更新规范。
"""
from dataclasses import dataclass

SCHEMA_VERSION = "1.2"
DATA_OBJECTS = ("track", "psycho", "physio")   # 即 pipeline，命名规范见 analysis/tools/paths.py
MODULE_LABELS = {
    "Interactive": "自由交互体验",
    "Practice": "练习场（只有会话信息）",
    "Passive": "被动观看视频（当前只有会话信息）",
}
TRACK_SESSION_GLOB = "sub-*"
TRACK_SESSION_REGEX = (
    r"^sub-P(?P<subject>\d+)_ses-S(?P<session>\d+)_mod-"
    r"(?P<module>Practice|Interactive|Passive)_run-(?P<run>\d+)$"
)
TRACK_RECORDING = {"spacetime_interval_seconds": 0.1, "yaw_zero": "+Z", "pitch_positive": "up"}

@dataclass(frozen=True)
class Field:
    column: str
    dtype: str
    unit: str | None = None
    levels: tuple | None = None

# 每行依次写明：实际列名、类型、单位、分类取值；没有按名字猜测类型的规则。
TRACK_SCHEMA = {
    'session': {
        'subject': Field('subject', 'Int64'),
        'session': Field('session', 'Int64'),
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
    "psycho": {}, "physio": {},
}
SCHEMAS = {"track": TRACK_SCHEMA}

def column(table, field, source="track"):
    return SCHEMAS[source][table][field].column if source != "track" else TRACK_COLUMNS[table][field]

def table_columns(table, source="track"):
    return tuple(column(table, field, source) for field in SCHEMAS[source][table])

def validate():
    for source, tables in SCHEMAS.items():
        for table in tables:
            columns = table_columns(table, source)
            if len(set(columns)) != len(columns):
                raise ValueError(f"{source}.{table}: 实际列名重复")
