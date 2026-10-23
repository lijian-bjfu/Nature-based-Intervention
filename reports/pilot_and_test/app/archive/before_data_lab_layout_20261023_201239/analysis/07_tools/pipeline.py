"""两种入口共用的调度器：任务选择、依赖、参数校验、数据与报告输出。"""
from dataclasses import asdict
from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import importlib.util
import importlib.metadata
import re
import sys
from importlib import import_module
settings = import_module("00_settings")
from configuration import RunConfig, RunContext, load_config, choice_help
from artifacts import write_json, sha256, settings_snapshot
from paths import raw, report_root, processed_root, final_root

def discover(config):
    base = raw(config.dataset, "app")
    matches = []
    for folder in sorted(base.glob(settings.APP_SESSION_GLOB)):
        match = re.fullmatch(settings.APP_SESSION_REGEX, folder.name)
        if not folder.is_dir() or not match:
            continue
        if not any(fnmatchcase(folder.name, pattern) for pattern in config.sessions):
            continue
        if match["module"] not in config.modules:
            continue
        matches.append(folder)
    if not matches:
        raise FileNotFoundError(f"没有匹配的埋点数据：{base}\n请检查 parameters.RUN 的 dataset、sessions、modules。")
    return matches

def resolve_steps(requested):
    required, visiting = set(), set()
    def add(step):
        if step not in settings.APP_PIPELINE:
            raise ValueError(f"{step} 尚未实现；当前可执行 {tuple(settings.APP_PIPELINE)}")
        if step in visiting:
            raise ValueError(f"任务依赖形成循环：{step}")
        if step in required:
            return
        visiting.add(step)
        for parent in settings.APP_PIPELINE[step]["requires"]:
            add(parent)
        visiting.remove(step)
        required.add(step)
    for step in requested:
        add(step)
    return [step for step in settings.STEP_ORDER if step in required]

def resolve_tasks(tasks):
    return resolve_steps([settings.TASKS[task]["stage"] for task in tasks])

def execute(config: RunConfig):
    settings.validate()
    steps = resolve_tasks(config.tasks)
    sessions = discover(config)
    stamp = datetime.now(ZoneInfo(settings.PROJECT_TIMEZONE)).strftime("%Y%m%d_%H%M%S_%f")
    group = settings.DATASETS[config.dataset]["report_group"]
    output = report_root(group, "app") / settings.RUNS_FOLDER / stamp
    processed_output = processed_root(config.dataset, "app") / stamp
    final_output = final_root(config.dataset) / stamp
    processed_output.mkdir(parents=True, exist_ok=False)
    has_analysis = "06_analysis" in steps
    if has_analysis:
        output.mkdir(parents=True, exist_ok=False)
    context = RunContext(config, sessions, output, processed_output, final_output)
    source_hashes = {str(path): sha256(path) for folder in sessions
                     for name in settings.APP_TABLES
                     if (path := folder/settings.APP_FILES[name]).is_file()}
    scripts = [settings.ROOT/name for name in ("02_run.py","00_settings.py","01_parameters.py")]
    scripts += sorted(settings.ANALYSIS_DIR.rglob("*.py"))
    manifest = {
        "schema_version": settings.SCHEMA_VERSION, "config_version": settings.CONFIG_VERSION,
        "status": "running", "run_id": stamp, "timezone": settings.PROJECT_TIMEZONE,
        "selection": {"tasks": config.tasks,"dataset":config.dataset,"sessions":config.sessions,
                      "modules":config.modules},
        "resolved_steps": steps, "language": config.language,
        "processed_output": processed_output, "final_output": None,
        "report_output": output if has_analysis else None,
        "sessions": [p.name for p in sessions], "source_sha256": source_hashes,
        "script_sha256": {str(p.relative_to(settings.ROOT)): sha256(p) for p in scripts},
        "python_executable": sys.executable, "python_version": sys.version,
        "package_versions": {name: importlib.metadata.version(name) for name in ("numpy","pandas","matplotlib")},
    }
    effective = asdict(config)
    effective.pop("configured_parameters")
    effective.pop("overrides")
    parameters_snapshot = {"configured":config.configured_parameters,
                           "effective":effective,"command_line_overrides":config.overrides}
    metadata_roots = [processed_output] + ([output] if has_analysis else [])
    for folder in metadata_roots:
        write_json(folder/"settings_snapshot.json", settings_snapshot())
        write_json(folder/"parameters_snapshot.json", parameters_snapshot)
        write_json(folder/"manifest.json", manifest)
    print(f"任务：{', '.join(config.tasks)}；数据集：{config.dataset}；会话：{len(sessions)} 场",flush=True)
    try:
        for step in steps:
            script = settings.ANALYSIS_DIR / settings.APP_PIPELINE[step]["script"]
            spec = importlib.util.spec_from_file_location("nbi_"+step, script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print(f"[{step}] {script.name}", flush=True)
            module.run(context)
        changed = [path for path,digest in source_hashes.items() if sha256(path) != digest]
        if changed:
            raise RuntimeError(f"输入文件发生变化：{changed}")
        manifest.update(status="complete",raw_files_unchanged=True)
    except Exception as error:
        manifest.update(status="failed",error=str(error))
        raise
    finally:
        for folder in metadata_roots:
            write_json(folder/"manifest.json",manifest)
    print(f"处理数据：{processed_output}",flush=True)
    if has_analysis:
        print(f"打开报告：{output/'index.md'}",flush=True)
    return output if has_analysis else processed_output

def cli(default_tasks=None, argv=None):
    """无命令行选项时完整采用 01_parameters.py；CLI 仅覆盖明确提供的键。"""
    parser = argparse.ArgumentParser(description="修改 01_parameters.py 后直接点 Run，或使用命令行临时覆盖。")
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--tasks",nargs="+",help="工作任务，例如 app_describe、app_clean")
    select.add_argument("--steps",nargs="+",help="兼容旧用法：01_import、02_clean、03_format、06_analysis")
    parser.add_argument("--dataset",choices=tuple(settings.DATASETS),default=None)
    parser.add_argument("--sessions",nargs="+",default=None)
    parser.add_argument("--modules",nargs="+",default=None)
    parser.add_argument("--language",choices=("auto","zh","en"),default=None)
    parser.add_argument("--time-bin-seconds",type=float,default=None)
    parser.add_argument("--figure-dpi",type=int,default=None)
    parser.add_argument("--figure-formats",nargs="+",default=None)
    parser.add_argument("--list",action="store_true",help="显示可用任务，不执行处理")
    args = parser.parse_args(argv)
    if args.list:
        print("工作任务：" + choice_help("tasks"))
        print("输入数据范围：" + choice_help("dataset"))
        print("APP 模块：" + choice_help("modules"))
        print("日常编辑：01_parameters.py；直接运行：02_run.py")
        return
    overrides = {key:value for key,value in vars(args).items() if key not in ("steps","list") and value is not None}
    try:
        if args.steps:
            inverse = {task["stage"]: name for name,task in settings.TASKS.items()}
            unknown = set(args.steps)-set(inverse)
            if unknown:
                raise ValueError(f"所选阶段尚未实现：{sorted(unknown)}")
            overrides["tasks"] = [inverse[step] for step in args.steps]
        config = load_config(overrides,default_tasks)
    except (ValueError, KeyError, TypeError) as error:
        print(f"参数错误：{error}\n请修改根目录 01_parameters.py，或更正本次命令行选项。",file=sys.stderr)
        raise SystemExit(2) from None
    try:
        return execute(config)
    except FileNotFoundError as error:
        print(str(error),file=sys.stderr)
        raise SystemExit(2) from None
