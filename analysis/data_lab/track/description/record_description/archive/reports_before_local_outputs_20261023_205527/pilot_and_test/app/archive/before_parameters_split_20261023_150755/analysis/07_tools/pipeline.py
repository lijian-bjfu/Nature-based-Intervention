"""共用调度入口：依赖、配置快照、运行清单与输入校验。"""
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
import settings
from artifacts import write_json, sha256, settings_snapshot
from paths import raw, report_root, processed_root, final_root

def discover(config):
    base = raw(config.dataset, "app")
    matches = []
    for folder in sorted(base.glob(settings.APP_SESSION_GLOB)):
        match = re.fullmatch(settings.APP_SESSION_REGEX, folder.name)
        if not folder.is_dir() or not match:
            continue
        if not any(fnmatchcase(folder.name, pat) for pat in config.sessions):
            continue
        if config.modules and match["module"] not in config.modules:
            continue
        matches.append(folder)
    if not matches:
        raise FileNotFoundError(f"没有匹配的 APP 会话：{base}；sessions={config.sessions}；modules={config.modules}")
    return matches

def resolve_steps(requested):
    required = set()
    def add(step):
        if step not in settings.APP_PIPELINE:
            raise ValueError(f"{step} 尚未实现；当前可执行 {tuple(settings.APP_PIPELINE)}")
        if step in required:
            return
        required.add(step)
        for parent in settings.APP_PIPELINE[step]["requires"]:
            add(parent)
    for step in requested:
        add(step)
    return [step for step in settings.STEP_ORDER if step in required]

def execute(config):
    settings.validate()
    if config.dataset not in settings.DATASETS:
        raise ValueError(f"未登记的数据集 {config.dataset}")
    steps = resolve_steps(config.steps)
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
    language = config.language or settings.DATASETS[config.dataset]["language"]
    if language not in ("zh", "en"):
        raise ValueError("报告语言只支持 zh/en")
    context = {"config": config, "sessions": sessions, "output": output, "language": language,
               "processed_output": processed_output, "final_output": final_output}
    source_hashes = {str(p): sha256(p) for folder in sessions
                     for name in settings.APP_TABLES
                     if (p := folder/settings.APP_FILES[name]).is_file()}
    scripts = [settings.ROOT/"run.py", settings.ROOT/"settings.py"] + sorted(settings.ANALYSIS_DIR.rglob("*.py"))
    manifest = {"schema_version": settings.SCHEMA_VERSION, "status": "running",
        "run_id": stamp, "timezone": settings.PROJECT_TIMEZONE, "selection": asdict(config),
        "resolved_steps": steps, "language": language,
        "processed_output": processed_output, "final_output": None,
        "report_output": output if has_analysis else None,
        "sessions": [p.name for p in sessions], "source_sha256": source_hashes,
        "script_sha256": {str(p.relative_to(settings.ROOT)): sha256(p) for p in scripts},
        "python_executable": sys.executable, "python_version": sys.version,
        "package_versions": {name: importlib.metadata.version(name) for name in ("numpy","pandas","matplotlib")}}
    metadata_roots = [processed_output] + ([output] if has_analysis else [])
    for folder in metadata_roots:
        write_json(folder/"settings_snapshot.json", settings_snapshot())
        write_json(folder/"manifest.json", manifest)
    try:
        for step in steps:
            script = settings.ANALYSIS_DIR / settings.APP_PIPELINE[step]["script"]
            spec = importlib.util.spec_from_file_location("nbi_"+step, script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print(f"[{step}] {script.name}", flush=True)
            module.run(context)
        changed = [p for p, digest in source_hashes.items() if sha256(p) != digest]
        if changed:
            raise RuntimeError(f"输入文件发生变化：{changed}")
        manifest.update(status="complete", raw_files_unchanged=True)
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        for folder in metadata_roots:
            write_json(folder/"manifest.json", manifest)
    print(f"处理数据：{processed_output}", flush=True)
    if has_analysis:
        print(f"报告结果：{output}", flush=True)
    return output if has_analysis else processed_output

def cli(default_steps=None):
    parser = argparse.ArgumentParser(description="NBI 可复用分析流程；无参数时读取根目录 settings.py。")
    parser.add_argument("--dataset", choices=tuple(settings.DATASETS), default=settings.RUN_DATASET)
    parser.add_argument("--sessions", nargs="+", default=settings.RUN_SESSIONS)
    parser.add_argument("--modules", nargs="+", default=settings.RUN_MODULES)
    parser.add_argument("--steps", nargs="+", default=default_steps or settings.RUN_STEPS)
    parser.add_argument("--language", choices=("zh","en"), default=None)
    parser.add_argument("--list", action="store_true", help="显示已实现步骤，不读取或改写数据")
    args = parser.parse_args()
    if args.list:
        for step in settings.STEP_ORDER:
            print(step, settings.APP_PIPELINE.get(step, {}).get("script", "尚未实现"))
        return
    config = settings.RunConfig(dataset=args.dataset, sessions=tuple(args.sessions),
        modules=tuple(args.modules), steps=tuple(args.steps), language=args.language)
    execute(config)
