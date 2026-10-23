"""读取并验证用户参数，生成明确的运行信息；不修改固定规范或参数文件。"""
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import math
import numbers
from importlib import import_module
settings = import_module("00_settings")
parameters = import_module("01_parameters")

@dataclass(frozen=True)
class FigureOptions:
    dpi: int
    formats: tuple
    font: str
    font_size: float

@dataclass(frozen=True)
class AppDescribeOptions:
    time_bin_seconds: float
    interval_quantiles: tuple
    colors: dict

@dataclass(frozen=True)
class RunConfig:
    tasks: tuple
    dataset: str
    sessions: tuple
    modules: tuple
    language: str
    figure: FigureOptions
    app_describe: AppDescribeOptions
    configured_parameters: dict = field(repr=False)
    overrides: dict = field(repr=False)

@dataclass
class RunContext:
    config: RunConfig
    sessions: list
    output: Path
    processed_output: Path
    final_output: Path
    inventory: list = field(default_factory=list)

    @property
    def language(self):
        return self.config.language

def choice_help(kind):
    if kind == "tasks":
        entries = {key:value["label"] for key,value in settings.TASKS.items()}
    elif kind == "dataset":
        entries = {key:value["label"] for key,value in settings.DATASETS.items()}
    elif kind == "modules":
        entries = settings.MODULE_LABELS
    else:
        raise ValueError(kind)
    return "；".join(f"{key}（{label}）" for key,label in entries.items())

def string_list(value, key):
    if not isinstance(value, (list, tuple)) or not value or any(
            not isinstance(item, str) or not item for item in value):
        raise ValueError(f"01_parameters.py: {key} 必须是非空文字列表，例如 ['*']")
    return tuple(value)

def positive(value, key):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"01_parameters.py: {key} 必须是大于 0 的有限数值，当前为 {value!r}")
    return float(value)

def load_config(overrides=None, default_tasks=None):
    overrides = {k:v for k,v in (overrides or {}).items() if v is not None}
    configured = deepcopy({"RUN":parameters.RUN, "COMMON":parameters.COMMON, "APP":parameters.APP})
    run, common, app = (configured[k] for k in ("RUN","COMMON","APP"))
    tasks = string_list(overrides.get("tasks", default_tasks or run["tasks"]), "RUN['tasks']")
    unknown = set(tasks)-set(settings.TASKS)
    if unknown:
        raise ValueError(f"01_parameters.py: RUN['tasks'] 中有未实现任务 {sorted(unknown)}；可选 {choice_help('tasks')}")
    dataset = overrides.get("dataset", run["dataset"])
    if dataset not in settings.DATASETS:
        raise ValueError(f"01_parameters.py: RUN['dataset'] 应为 {choice_help('dataset')}，当前为 {dataset!r}")
    sessions = string_list(overrides.get("sessions", run["sessions"]), "RUN['sessions']")
    modules = string_list(overrides.get("modules", run["modules"]), "RUN['modules']")
    allowed = settings.APP_LEVELS["session"]["module"]
    if set(modules)-set(allowed):
        raise ValueError(f"01_parameters.py: RUN['modules'] 只支持 {choice_help('modules')}")
    language = overrides.get("language", common["report_language"])
    if language == "auto":
        language = common["language_by_group"][settings.DATASETS[dataset]["report_group"]]
    if language not in ("zh","en"):
        raise ValueError("01_parameters.py: COMMON['report_language'] 应为 auto、zh 或 en")
    fig = common["figure"]
    dpi_value = overrides.get("figure_dpi", fig["dpi"])
    dpi = positive(dpi_value, "COMMON['figure']['dpi']")
    if not dpi.is_integer():
        raise ValueError("01_parameters.py: COMMON['figure']['dpi'] 必须是正整数")
    formats = string_list(overrides.get("figure_formats", fig["formats"]), "COMMON['figure']['formats']")
    if len(set(formats)) != len(formats) or set(formats)-set(settings.FIGURE_FORMATS):
        raise ValueError(f"图格式不能重复，只支持 {settings.FIGURE_FORMATS}")
    if not isinstance(fig["font"], str) or not fig["font"].strip():
        raise ValueError("01_parameters.py: COMMON['figure']['font'] 不能为空")
    options = app["describe"]
    width = positive(overrides.get("time_bin_seconds", options["time_bin_seconds"]),
                     "APP['describe']['time_bin_seconds']")
    quantiles = options["interval_quantiles"]
    if not isinstance(quantiles,(list,tuple)) or not quantiles or any(
        isinstance(q,bool) or not isinstance(q,numbers.Real) or not math.isfinite(q) or not 0<=q<=1
        for q in quantiles):
        raise ValueError("01_parameters.py: APP['describe']['interval_quantiles'] 应是 0–1 的数值列表")
    if len(set(quantiles)) != len(quantiles):
        raise ValueError("01_parameters.py: APP['describe']['interval_quantiles'] 不能重复")
    colors = options["colors"]
    needed = set(settings.APP_LEVELS["tap"]["block_type"]) | set(settings.APP_LEVELS["look"]["look_type"]) | {"event"}
    if not isinstance(colors,dict) or not needed.issubset(colors):
        raise ValueError(f"01_parameters.py: APP['describe']['colors'] 必须包含 {sorted(needed)}")
    from matplotlib.colors import is_color_like
    if any(not is_color_like(colors[key]) for key in needed):
        raise ValueError("01_parameters.py: APP['describe']['colors'] 包含无效颜色")
    return RunConfig(tasks, dataset, sessions, modules, language,
        FigureOptions(int(dpi),formats,fig["font"],positive(fig["font_size"],"COMMON['figure']['font_size']")),
        AppDescribeOptions(width,tuple(float(q) for q in quantiles),deepcopy(colors)),
        configured,deepcopy(overrides))
