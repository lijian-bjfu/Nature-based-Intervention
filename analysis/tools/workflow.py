"""通用依赖解析与脚本加载；任务和顺序由具体工作登记。"""
import importlib.util
import sys
from pathlib import Path

def resolve_steps(registry, requested, order):
    required, visiting = set(), set()
    def add(step):
        if step not in registry:
            raise ValueError(f"{step} 尚未实现；可选 {tuple(registry)}")
        if step in visiting:
            raise ValueError(f"任务依赖形成循环：{step}")
        if step in required:
            return
        visiting.add(step)
        for parent in registry[step]["requires"]:
            add(parent)
        visiting.remove(step)
        required.add(step)
    for step in requested:
        add(step)
    if required-set(order):
        raise ValueError("执行顺序缺少已登记步骤")
    return [step for step in order if step in required]

def script_path(analysis_root, relative):
    root = Path(analysis_root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or set(path.relative_to(root).parts)&{"deprecated","archive","outputs"}:
        raise ValueError(f"不可调度废弃工具、历史副本或外部路径：{relative}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path

def load_script(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module
