"""本次 Track 记录描述实验的配置解析与执行；参数由入口脚本传入。"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT/"analysis"), str(PROJECT/"analysis/tools")]

SCRIPT_HISTORY = [
    {"at": "2026-10-23T20:48:27+08:00", "action": "created", "summary": "建立局部实验调度，解除根目录参数和运行入口依赖；为每步记录时间、Git 信息及源码快照。"},
    {"at": "2026-10-24T12:55:00+08:00", "action": "modified", "summary": "源码记录改为提交号加 SHA-256，只复制未提交的源码（uncommitted_sources），不再整份快照。"},
    {"at": "2026-10-24T15:00:00+08:00", "action": "moved", "summary": "按\"一个文件夹一个研究问题\"整理：本问题用到的脚本都放在 track/description/。 结果改为只保留最近一次（results/，每次覆盖），追溯信息放 results/_provenance/。", "previous_path": "analysis/data_lab/track/description/record_description/experiment.py"},
    {"at": "2026-10-24T16:10:00+08:00", "action": "modified", "summary": "参数 sessions/modules 改为单一的 session（完整文件夹名）；找不到时列出可选记录。"},
    {"at": "2026-10-24T17:30:00+08:00", "action": "modified", "summary": "改用 tools/data_access.py 统一调取数据（dataset / pipeline / subject），不再自行查找文件夹。"},
]

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from fnmatch import fnmatchcase
import argparse
import shutil
import importlib.metadata
import math
import numbers
import re

import global_settings as settings
from artifacts import sha256, write_json, settings_snapshot
from options import FigureOptions, figure_options, positive, string_list, valid_colors
from paths import ROOT, ANALYSIS, DATASETS, processed_root, final_root
from run_records import now, run_id, git_state, record_sources, script_history
from workflow import resolve_steps as resolve_dependencies, script_path, load_script
from data_access import find

EXPERIMENT_DIR = Path(__file__).resolve().parent
EXPERIMENT_NAME = "description"
DESCRIPTION_METHOD = "adjacent_xz"
FIGURES = {"space": "fig1_space", "time": "fig2_time", "actions": "fig3_actions"}
STAGE_TABLE_FOLDER = "tables"
STEP_ORDER = ("01_import", "02_clean", "03_format", "06_analysis")
STAGES = {
    "01_import": {"script": "data_lab/track/description/track_inventory.py", "requires": ()},
    "02_clean": {"script": "data_lab/track/description/track_clean.py", "requires": ("01_import",)},
    "03_format": {"script": "data_lab/track/description/track_format.py", "requires": ("02_clean",)},
    "06_analysis": {"script": "data_lab/track/description/track_describe.py", "requires": ("03_format",)},
}
TASKS = {
    "track_inventory": {"stage": "01_import", "label": "核对埋点文件"},
    "track_clean": {"stage": "02_clean", "label": "清理埋点历史取值"},
    "track_format": {"stage": "03_format", "label": "生成埋点标准输入表"},
    "track_describe": {"stage": "06_analysis", "label": "埋点记录描述、绘图与报告"},
}
STAGE_DESTINATIONS = {"01_import": "processed", "02_clean": "processed",
                      "03_format": "processed", "06_analysis": "report"}

@dataclass(frozen=True)
class TrackDescribeOptions:
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
    description: TrackDescribeOptions
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
    table_folder: str = "tables"
    stage_destinations: dict = field(default_factory=lambda: dict(STAGE_DESTINATIONS))

    @property
    def language(self):
        return self.config.language

def choice_help(kind):
    entries = {"tasks": {k:v["label"] for k,v in TASKS.items()},
               "dataset": {k:v["label"] for k,v in DATASETS.items()},
               "modules": settings.MODULE_LABELS}[kind]
    return "；".join(f"{key}（{label}）" for key,label in entries.items())

def load_config(parameters, overrides=None, default_tasks=None):
    overrides = {k:v for k,v in (overrides or {}).items() if v is not None}
    configured = deepcopy(parameters)
    select = configured["selection"]
    tasks = string_list(overrides.get("tasks", default_tasks or select["tasks"]), "selection.tasks")
    if set(tasks)-set(TASKS):
        raise ValueError(f"selection.tasks 存在未实现任务；可选 {choice_help('tasks')}")
    dataset = overrides.get("dataset", select["dataset"])
    if dataset not in DATASETS:
        raise ValueError(f"selection.dataset 应为 {choice_help('dataset')}")
    subject = overrides.get("subject", select["subject"])
    if not isinstance(subject, str) or not re.fullmatch(r"P\d+", subject.strip()):
        raise ValueError("selection.subject 应是一名被试的编号，如 P040（一次只分析一名被试，不用通配符）")
    run = overrides.get("run", select.get("run"))
    sessions = [subject.strip(), None if run in (None, "") else str(run)]
    modules = list(settings.TRACK_LEVELS["session"]["module"])
    language = overrides.get("language", configured["report_language"])
    if language == "auto":
        language = "en" if DATASETS[dataset]["kind"] == "formal" else "zh"
    if language not in ("zh", "en"):
        raise ValueError("report_language 应为 auto、zh 或 en")
    options = configured["description"]
    width = positive(overrides.get("time_bin_seconds", options["time_bin_seconds"]), "description.time_bin_seconds")
    quantiles = options["interval_quantiles"]
    if not isinstance(quantiles, (list,tuple)) or not quantiles or any(
        isinstance(q,bool) or not isinstance(q,numbers.Real) or not math.isfinite(q) or not 0<=q<=1 for q in quantiles):
        raise ValueError("description.interval_quantiles 应是 0–1 的数值列表")
    if len(set(quantiles)) != len(quantiles):
        raise ValueError("description.interval_quantiles 不能重复")
    required = set(settings.TRACK_LEVELS["tap"]["block_type"]) | set(settings.TRACK_LEVELS["look"]["look_type"]) | {"event"}
    return RunConfig(tasks, dataset, sessions, modules, language,
                     figure_options(configured["figure"], overrides),
                     TrackDescribeOptions(width,tuple(float(q) for q in quantiles),
                                          valid_colors(options["colors"],required)),
                     configured,deepcopy(overrides))

def discover(config):
    """按项目统一的数据调取方法（tools/data_access.py）找到这名被试的记录。"""
    subject, run = config.sessions
    return list(find(config.dataset, "track", [subject], run=run).values())

def resolve_tasks(tasks):
    return resolve_dependencies(STAGES, [TASKS[task]["stage"] for task in tasks], STEP_ORDER)

def source_files():
    paths = [ROOT/"global_settings.py", ROOT/"requirements.txt"]
    paths += sorted((ANALYSIS/"tools").glob("*.py"))
    paths += sorted((ANALYSIS/"data_lab/track").rglob("*.py"))
    return [path for path in paths if not set(path.relative_to(ROOT).parts)&{"archive","outputs","deprecated","__pycache__"}]

def execute(config):
    settings.validate()
    steps = resolve_tasks(config.tasks)
    scripts = {step:script_path(ANALYSIS, STAGES[step]["script"]) for step in steps}
    sessions = discover(config)
    stamp = run_id()
    # 结果只保留最近一次：每次运行先清空 results/ 和对应的处理数据目录，不按时间戳堆文件夹。
    # 想保留的结果由研究者手动复制到 save/，按含义命名。追溯信息放在 _provenance/，平时不用打开。
    output = EXPERIMENT_DIR / "results"
    processed = processed_root(config.dataset,"track") / "data_lab" / EXPERIMENT_NAME
    has_report = "06_analysis" in steps
    for folder in [processed] + ([output] if has_report else []):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
    context = RunContext(config,sessions,output,processed,final_root(config.dataset)/("data_lab_"+EXPERIMENT_NAME))
    metadata_roots = [processed/"_provenance"] + ([output/"_provenance"] if has_report else [])
    primary = metadata_roots[-1]
    files = source_files()
    sources, copied = record_sources(ROOT,files,primary/"uncommitted_sources")
    raw_hashes = {str(path.relative_to(ROOT)):sha256(path) for folder in sessions
                  for name in settings.TRACK_TABLES if (path:=folder/settings.TRACK_FILES[name]).is_file()}
    effective = asdict(config)
    effective.pop("configured_parameters")
    effective.pop("overrides")
    manifest = {
        "schema_version":settings.SCHEMA_VERSION, "experiment":EXPERIMENT_NAME, "run_id":stamp,
        "status":"running", "timezone":"Asia/Shanghai", "started_at":now(), "finished_at":None,
        "selection":effective, "resolved_steps":steps,
        "processed_output":str(processed), "final_output":None,
        "report_output":str(output) if has_report else None,
        "uncommitted_sources":str(primary/"uncommitted_sources"), "uncommitted_copied":copied,
        "script_sha256":sources,
        "source_sha256":raw_hashes, "git":git_state(ROOT,files),
        "script_history":{str(p.relative_to(ROOT)):script_history(p) for p in files
                          if p.is_relative_to(ANALYSIS/"data_lab")},
        "sessions":[p.name for p in sessions], "steps":[],
        "python_executable":sys.executable, "python_version":sys.version,
        "package_versions":{name:importlib.metadata.version(name) for name in ("numpy","pandas","matplotlib")},
    }
    for folder in metadata_roots:
        write_json(folder/"global_settings_snapshot.json",settings_snapshot())
        write_json(folder/"parameters_snapshot.json",{"configured":config.configured_parameters,
                   "effective":effective,"command_line_overrides":config.overrides})
        write_json(folder/"manifest.json",manifest)
    print(f"实验：{EXPERIMENT_NAME}；数据：{config.dataset}／{sessions[0].name}",flush=True)
    try:
        for step in steps:
            record = {"step":step,"script":str(scripts[step].relative_to(ROOT)),
                      "started_at":now(),"finished_at":None,"status":"running"}
            manifest["steps"].append(record)
            try:
                module = load_script(scripts[step],"nbi_"+step+"_"+stamp)
                print(f"[{step}] {scripts[step].name}",flush=True)
                module.run(context)
                record["status"]="complete"
            except Exception as error:
                record.update(status="failed",error=str(error))
                raise
            finally:
                record["finished_at"]=now()
                for folder in metadata_roots:
                    write_json(folder/"manifest.json",manifest)
        manifest["raw_files_unchanged"]=all((ROOT/path).is_file() and sha256(ROOT/path)==digest
                                            for path,digest in raw_hashes.items())
        manifest["source_files_unchanged"]=all((ROOT/path).is_file() and sha256(ROOT/path)==digest
                                               for path,digest in sources.items())
        if not manifest["raw_files_unchanged"] or not manifest["source_files_unchanged"]:
            raise RuntimeError("运行期间输入数据或源码发生变化，请核对本次快照")
        manifest["status"]="complete"
    except Exception as error:
        manifest.update(status="failed",error=str(error))
        raise
    finally:
        manifest["finished_at"]=now()
        for folder in metadata_roots:
            write_json(folder/"manifest.json",manifest)
    print(f"处理数据：{processed}",flush=True)
    if has_report:
        print(f"打开报告：{output/'report.md'}",flush=True)
    return output if has_report else processed

def cli(parameters, default_tasks=None, argv=None):
    parser = argparse.ArgumentParser(description="修改当前实验脚本的 PARAMETERS 后点 Run，或使用命令行临时覆盖。")
    parser.add_argument("--tasks",nargs="+")
    parser.add_argument("--dataset",choices=tuple(DATASETS))
    parser.add_argument("--subject")
    parser.add_argument("--run")
    parser.add_argument("--language",choices=("auto","zh","en"))
    parser.add_argument("--time-bin-seconds",type=float)
    parser.add_argument("--figure-dpi",type=int)
    parser.add_argument("--figure-formats",nargs="+")
    parser.add_argument("--list",action="store_true")
    args = vars(parser.parse_args(argv))
    if args.pop("list"):
        for kind in ("tasks","dataset"):
            print(kind+": "+choice_help(kind))
        print("局部参数：当前 track_describe.py 的 PARAMETERS；不读取 table_flows 参数。")
        return
    try:
        config=load_config(parameters,args,default_tasks)
        return execute(config)
    except (ValueError,KeyError,TypeError,FileNotFoundError) as error:
        parser.error(str(error))
