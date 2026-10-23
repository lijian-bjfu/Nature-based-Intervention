"""共享数据规范：原始结构、标签、单位及已经确认的指标定义。

table_flows 与 data_lab 共用本文件。运行选择、试验参数、任务依赖和输出路径不在这里。
埋点规范的依据是《研究思路/实验记录-埋点.md》；修改科学口径须先讨论并更新规范。
"""
from dataclasses import dataclass

SCHEMA_VERSION = "1.1"
DATA_OBJECTS = ("track", "psycho", "physico")
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
TRACK_TRUE = "TRUE"
TRACK_FALSE = "FALSE"
TRACK_CSV = {"encoding": "utf-8-sig", "keep_default_na": False, "na_values": [""]}
TRACK_REQUIRED_TABLES = {
    "Interactive": TRACK_TABLES, "Practice": ("session",), "Passive": ("session",),
}

# 指标须经过研究讨论后逐项登记；候选指标及其试验阈值留在具体实验中。
# 登记应包含名称、定义、输入字段、输出单位、计算口径和规范出处；计算函数不放在这里。
METRICS = {"track": {}, "psycho": {}, "physico": {}}
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
