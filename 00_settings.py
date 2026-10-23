"""固定规范，日常运行不要修改；日常选项请改 01_parameters.py。

字段、单位、分类、命名、目录结构和任务依赖来自已同意的规范。
研究或工程规范正式调整后才维护本文件，不把它当作运行参数面板。
"""
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
ANALYSIS_DIR = ROOT / "analysis"
REPORTS_DIR = ROOT / "reports"
TOOLS_DIR = ANALYSIS_DIR / "tools"
TABLE_FLOWS_DIR = ANALYSIS_DIR / "table_flows"
DATA_LAB_DIR = ANALYSIS_DIR / "data_lab"
LAB_OBJECTS = ("track", "psycho", "physico")
TABLE_FLOW_OBJECTS = (*LAB_OBJECTS, "integration")
LAB_STAGES = ("processing", "description", "analysis", "report")
DEPRECATED_FOLDER = "deprecated"
CACHE_DIR = REPORTS_DIR / "_runtime_cache"
PROJECT_TIMEZONE = "Asia/Shanghai"

# 原始、处理、最终与补充数据都属于 data；报告按工作内容分类。
DATASETS = {
    "formal": {"root": DATA_DIR / "formal", "report_group": "formal", "label": "正式实验数据"},
    "pilot": {"root": DATA_DIR / "pilot_and_test" / "pilot",
              "report_group": "pilot_and_test", "label": "被试预实验数据"},
    "logging_test": {"root": DATA_DIR / "pilot_and_test" / "logging_test",
                     "report_group": "pilot_and_test", "label": "开发埋点测试数据"},
}
DATA_FOLDERS = {"raw": "raw", "processed": "processed", "final": "final",
                "supplementary": "supplementary"}
REPORT_GROUPS = {"formal": REPORTS_DIR / "formal",
                 "pilot_and_test": REPORTS_DIR / "pilot_and_test"}
# 新报告按工作内容分类；既有数据目录通过映射保留，以免破坏历史路径。
REPORT_TOPICS = {"track": "track", "psycho": "psycho", "physico": "physico"}
DATA_SOURCE_FOLDERS = {"track": "app", "psycho": "questionnaire", "physico": "physio",
                       "interview": "interview", "session_notes": "session_notes"}
SOURCES = tuple(DATA_SOURCE_FOLDERS)
RAW_FOLDER = DATA_FOLDERS["raw"]
RUNS_FOLDER = "runs"
# 处理数据先按性质/来源分，再按运行与处理阶段分；各来源可有不同的阶段集合。
DATA_STAGE_DESTINATIONS = {
    "01_import": "processed", "02_clean": "processed", "03_format": "processed",
    "04_features": "processed", "05_integrate": "final", "06_analysis": "report",
}
# 目录名用于识别会话，session.csv 是实际模块信息的依据；P000 是编辑器直接 Play 的测试编号。
APP_SESSION_GLOB = "sub-*"
APP_SESSION_REGEX = (
    r"^sub-P(?P<subject>\d+)_ses-S(?P<session>\d+)_mod-"
    r"(?P<module>Practice|Interactive|Passive)_run-(?P<run>\d+)$"
)

STEP_ORDER = ("01_import", "02_clean", "03_format", "06_analysis")
# 编号沿用现有 Track 步骤标识，不再对应 analysis 下的目录。
# table_flows 尚未实现；以下依赖只属于 data_lab/track 的记录描述。
APP_PIPELINE = {
    "01_import": {"script": "data_lab/track/processing/track_inventory.py", "requires": ()},
    "02_clean": {"script": "data_lab/track/processing/track_clean.py", "requires": ("01_import",)},
    "03_format": {"script": "data_lab/track/processing/track_format.py", "requires": ("02_clean",)},
    "06_analysis": {"script": "data_lab/track/description/track_describe.py", "requires": ("03_format",)},
}

# 用户按工作任务选择；依赖和脚本位置由工程固定登记。
TASKS = {
    "track_inventory": {"source": "track", "stage": "01_import", "label": "核对埋点文件"},
    "track_clean": {"source": "track", "stage": "02_clean", "label": "清理埋点历史取值"},
    "track_format": {"source": "track", "stage": "03_format", "label": "生成埋点标准表"},
    "track_describe": {"source": "track", "stage": "06_analysis", "label": "埋点描述、绘图与报告"},
}
MODULE_LABELS = {
    "Interactive": "自由交互体验",
    "Practice": "练习场（只有会话信息）",
    "Passive": "被动观看视频（当前只有会话信息）",
}
FIGURE_FORMATS = ("png", "svg", "pdf")
APP_DESCRIPTION_METHOD = "adjacent_xz"  # 已实现的描述方法；不是用户方法选择器。
APP_RECORDING = {"spacetime_interval_seconds": 0.1, "yaw_zero": "+Z", "pitch_positive": "up"}

@dataclass(frozen=True)
class Field:
    column: str
    dtype: str
    unit: str | None = None
    levels: tuple | None = None

# 每行依次写明：实际列名、类型、单位、分类取值；没有按名字猜测类型的规则。
APP_SCHEMA = {
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
APP_TABLES = tuple(APP_SCHEMA)
APP_FILES = {name: name + ".csv" for name in APP_TABLES}
APP_COLUMNS = {table: {key: field.column for key,field in fields.items()}
               for table,fields in APP_SCHEMA.items()}
APP_TYPES = {key: field.dtype for fields in APP_SCHEMA.values() for key,field in fields.items()}
APP_UNITS = {key: field.unit for fields in APP_SCHEMA.values() for key,field in fields.items()
             if field.unit is not None}
APP_LEVELS = {table: {key: field.levels for key,field in fields.items() if field.levels is not None}
              for table,fields in APP_SCHEMA.items() if any(f.levels is not None for f in fields.values())}
PRECISION = {"s": 3, "m": 2, "degree": 1}
APP_LEGACY_VALUES = {
    "tap": {"intent": {"None": "NoHit"}, "hit_layer": {"None": "NoHit"},
            "block_type": {"None": "NotBlocked"}, "block_reason": {"None": "NotBlocked"}},
    "backstep": {"block_type": {"None": "NotBlocked"}, "block_reason": {"None": "NotBlocked"}},
}
APP_TRUE = "TRUE"
APP_FALSE = "FALSE"
APP_CSV = {"encoding": "utf-8-sig", "keep_default_na": False, "na_values": [""]}
APP_REQUIRED_TABLES = {
    "Interactive": APP_TABLES, "Practice": ("session",), "Passive": ("session",),
}
APP_FIGURES = {"space": "fig1_space", "time": "fig2_time", "actions": "fig3_actions"}
STAGE_TABLE_FOLDER = "tables"
SCHEMA_VERSION = "1.1"
CONFIG_VERSION = "3.0"

def column(table, field):
    return APP_COLUMNS[table][field]

def table_columns(table):
    return tuple(APP_COLUMNS[table].values())

def validate():
    for table,cols in APP_COLUMNS.items():
        if len(set(cols.values())) != len(cols):
            raise ValueError(f"settings.APP_COLUMNS: {table} 的实际列名重复")
    for step, entry in APP_PIPELINE.items():
        path = Path(entry["script"])
        if path.is_absolute() or ".." in path.parts or DEPRECATED_FOLDER in path.parts:
            raise ValueError(f"任务不得调用废弃工具或外部路径：{step}: {path}")
        if path.parts[:2] != ("data_lab", "track") or path.parts[2] not in LAB_STAGES:
            raise ValueError(f"任务不在已实现的对象与分析环节内：{path}")
        if not (ANALYSIS_DIR/path).is_file():
            raise ValueError(f"找不到任务脚本：{path}")
