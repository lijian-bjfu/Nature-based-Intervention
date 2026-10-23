"""项目唯一配置入口。调整数据、字段、方法、参数和路径先改这里；不在各脚本复制配置。"""
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
ANALYSIS_DIR = ROOT / "analysis"
REPORTS_DIR = ROOT / "reports"
TOOLS_DIR = ANALYSIS_DIR / "07_tools"
CACHE_DIR = REPORTS_DIR / "_runtime_cache"
PROJECT_TIMEZONE = "Asia/Shanghai"

# 原始、处理、最终与补充数据都属于 data；报告按工作内容分类。
DATASETS = {
    "formal": {"root": DATA_DIR / "formal", "report_group": "formal", "language": "en"},
    "pilot": {"root": DATA_DIR / "pilot_and_test" / "pilot",
              "report_group": "pilot_and_test", "language": "zh"},
    "logging_test": {"root": DATA_DIR / "pilot_and_test" / "logging_test",
                     "report_group": "pilot_and_test", "language": "zh"},
}
DATA_FOLDERS = {"raw": "raw", "processed": "processed", "final": "final",
                "supplementary": "supplementary"}
REPORT_GROUPS = {"formal": REPORTS_DIR / "formal",
                 "pilot_and_test": REPORTS_DIR / "pilot_and_test"}
# 工作内容，不是数据集；pilot 和 logging_test 的埋点结果都进入同一个 app 分类。
REPORT_TOPICS = {"app": "app", "questionnaire": "questionnaire", "physio": "physio"}
SOURCES = ("app", "questionnaire", "physio", "interview", "session_notes")
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

# VS Code 打开根目录 run.py 后直接运行，使用以下默认值。
RUN_DATASET = "logging_test"
RUN_SESSIONS = ("*",)             # 支持多个目录名或通配符，不在脚本里写死某次会话。
RUN_MODULES = ("Interactive",)
RUN_STEPS = ("01_import", "02_clean", "03_format", "06_analysis")
STEP_ORDER = ("01_import", "02_clean", "03_format", "04_features", "05_integrate", "06_analysis")
# 04、05 暂未实现，不假装执行；选择 06 时自动补齐目前已实现的前置步骤。
APP_PIPELINE = {
    "01_import": {"script": "01_import/app_inventory.py", "requires": ()},
    "02_clean": {"script": "02_clean/app_clean.py", "requires": ("01_import",)},
    "03_format": {"script": "03_format/app_format.py", "requires": ("02_clean",)},
    "06_analysis": {"script": "06_analysis/describe/app_describe.py", "requires": ("03_format",)},
}

APP_TABLES = ("session", "spacetime", "tap", "backstep", "look", "world_event", "tech_glitch")
APP_FILES = {name: name + ".csv" for name in APP_TABLES}
# columns 表：左侧是程序语义，右侧是文件中的实际列名。更换外部列名，只修改右侧。
APP_COLUMNS = {
    "session": {k: k for k in ("subject", "session", "group", "module", "t_device_start", "t_device_end")},
    "spacetime": {k: k for k in ("t_session", "t_device", "cam_x", "cam_y", "cam_z",
                                "ground_y", "view_yaw", "view_pitch")},
    "tap": {k: k for k in ("touch_id", "t_session", "t_device", "cam_x", "cam_y", "cam_z",
                          "intent", "hit_layer", "hit_x", "hit_y", "hit_z", "is_touched",
                          "block_type", "block_reason")},
    "backstep": {k: k for k in ("touch_id", "t_session", "t_device", "cam_x", "cam_y", "cam_z",
                               "back_dist", "block_type", "block_reason")},
    "look": {k: k for k in ("touch_id", "t_session_start", "t_device_start", "t_session_end",
                           "t_device_end", "yaw_start", "pitch_start", "yaw_end", "pitch_end",
                           "yaw_delta", "pitch_delta", "yaw_path", "pitch_path", "look_type")},
    "world_event": {k: k for k in ("t_session", "t_device", "event_name", "action",
                                  "cam_x", "cam_y", "cam_z", "detail")},
    "tech_glitch": {k: k for k in ("t_session", "t_device", "status", "duration")},
}
_FLOAT_FIELDS = (
    "t_session", "t_device", "t_device_start", "t_device_end", "t_session_start", "t_session_end",
    "cam_x", "cam_y", "cam_z", "ground_y", "hit_x", "hit_y", "hit_z", "back_dist",
    "view_yaw", "view_pitch", "yaw_start", "pitch_start", "yaw_end", "pitch_end",
    "yaw_delta", "pitch_delta", "yaw_path", "pitch_path", "duration",
)
APP_TYPES = {
    field: ("Float64" if field in _FLOAT_FIELDS else
            "Int64" if field in ("subject", "session", "group", "touch_id") else
            "boolean" if field == "is_touched" else "string")
    for columns in APP_COLUMNS.values() for field in columns
}
APP_UNITS = {
    field: ("s" if field.startswith("t_") or field == "duration" else
            "m" if field in ("cam_x", "cam_y", "cam_z", "ground_y", "hit_x", "hit_y",
                             "hit_z", "back_dist") else "degree")
    for field in _FLOAT_FIELDS
}
PRECISION = {"s": 3, "m": 2, "degree": 1}
APP_LEVELS = {
    "session": {"group": (1, 2), "module": ("Practice", "Interactive", "Passive")},
    "tap": {
        "intent": ("NoHit", "WalkTo", "LookAt"),
        "hit_layer": ("Terrain", "Road", "Rock", "DeadWood", "Flower", "Creature",
                      "TouchFoliage", "SweepFoliage", "TouchRigid", "WaterTouchSurface", "NoHit"),
        "is_touched": (True, False),
        "block_type": ("NotBlocked", "CutShort", "NoStart"),
        "block_reason": ("NotBlocked", "BarrierDenseSlope", "BarrierWater", "BarrierUnlabeled",
                         "StepUp", "DropTooHigh", "TooSteep", "NoGround"),
    },
    "look": {"look_type": ("Drag", "Tap")},
    "world_event": {"action": ("Fired", "NotFired", "HandStartle")},
    "tech_glitch": {"status": ("Background", "Freeze")},
}
APP_LEVELS["backstep"] = {k: APP_LEVELS["tap"][k] for k in ("block_type", "block_reason")}
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
# 这里只配置本次已有的描述做法，不定义投入、停留、找路、覆盖率等研究指标。
APP_DESCRIBE = {
    "time_bin_seconds": 60.0,
    "trajectory_method": "adjacent_xz",   # 不平滑；按相邻相机水平坐标连线近似。
    "interval_quantiles": (0.5, 0.95, 0.99),
}
PLOT = {
    "dpi": 160, "formats": ("png",), "font": "Arial Unicode MS",
    "colors": {"NotBlocked": "#22866B", "CutShort": "#D69325", "NoStart": "#C44545",
               "Drag": "#22866B", "Tap": "#4169A2", "event": "#A34EAA"},
}
APP_FIGURES = {"space": "fig1_space", "time": "fig2_time", "actions": "fig3_actions"}
STAGE_TABLE_FOLDER = "tables"
SCHEMA_VERSION = "1.1"

@dataclass(frozen=True)
class RunConfig:
    dataset: str = RUN_DATASET
    sessions: tuple = RUN_SESSIONS
    modules: tuple = RUN_MODULES
    steps: tuple = RUN_STEPS
    language: str | None = None

def column(table, field):
    return APP_COLUMNS[table][field]

def table_columns(table):
    return tuple(APP_COLUMNS[table].values())

def validate():
    if RUN_DATASET not in DATASETS:
        raise ValueError("RUN_DATASET 未在 DATASETS 登记")
    if APP_DESCRIBE["time_bin_seconds"] <= 0:
        raise ValueError("time_bin_seconds 必须大于零")
    if APP_DESCRIBE["trajectory_method"] != "adjacent_xz":
        raise ValueError("尚不支持该 trajectory_method，不会静默改用其他方法")
    for table, cols in APP_COLUMNS.items():
        if len(set(cols.values())) != len(cols):
            raise ValueError(f"{table} 的实际列名重复")
