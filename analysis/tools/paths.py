"""工程路径工具：数据位置集中映射，结果由各项工作的目录决定。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ANALYSIS = ROOT / "analysis"
DATA_LAB = ANALYSIS / "data_lab"
TABLE_FLOWS = ANALYSIS / "table_flows"
CACHE = ROOT / ".cache"
DATASETS = {
    "formal": {"root": DATA / "formal", "kind": "formal", "label": "正式实验数据"},
    "pilot": {"root": DATA / "pilot_and_test" / "pilot",
              "kind": "pilot_and_test", "label": "被试预实验数据"},
    "logging_test": {"root": DATA / "pilot_and_test" / "logging_test",
                     "kind": "pilot_and_test", "label": "开发埋点测试数据"},
}
# 保留已经采集的数据及历史处理结果的物理目录，不为改名移动原始记录。
DATA_SOURCE_FOLDERS = {"track": "app", "psycho": "questionnaire", "physico": "physio",
                       "interview": "interview", "session_notes": "session_notes"}

def dataset(name):
    if name not in DATASETS:
        raise ValueError(f"未知数据集 {name}；可选 {tuple(DATASETS)}")
    return DATASETS[name]["root"]

def source_folder(source):
    if source not in DATA_SOURCE_FOLDERS:
        raise ValueError(f"未知数据对象 {source}")
    return DATA_SOURCE_FOLDERS[source]

def raw(name, source):
    return dataset(name) / "raw" / source_folder(source)

def processed_root(name, source):
    return dataset(name) / "processed" / source_folder(source)

def final_root(name):
    return dataset(name) / "final"

def supplementary(name):
    return dataset(name) / "supplementary"

def lab_output_root(experiment_dir, name):
    experiment_dir = Path(experiment_dir).resolve()
    if not experiment_dir.is_relative_to(DATA_LAB) or "deprecated" in experiment_dir.relative_to(DATA_LAB).parts:
        raise ValueError("数据实验结果必须位于有效实验自己的目录内")
    return experiment_dir / "outputs" / DATASETS[name]["kind"]

def stage_dir(context, step, session=None):
    destination = context.stage_destinations[step]
    if destination == "processed":
        path = context.processed_output / step
    elif destination == "final":
        path = context.final_output
    elif destination == "report":
        path = context.output
    else:
        raise ValueError(f"未实现的输出类型 {destination}")
    return path / session if session else path
