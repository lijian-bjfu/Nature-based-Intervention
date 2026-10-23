"""路径只来自根目录 settings。数据按数据集/性质组织，报告按工作内容组织。"""
import settings

ROOT = settings.ROOT
DATA = settings.DATA_DIR
ANALYSIS = settings.ANALYSIS_DIR
REPORTS = settings.REPORTS_DIR

def dataset(name):
    if name not in settings.DATASETS:
        raise ValueError(f"未知数据集 {name}；可选 {tuple(settings.DATASETS)}")
    return settings.DATASETS[name]["root"]

def raw(name, source):
    if source not in settings.SOURCES:
        raise ValueError(f"未知来源 {source}")
    return dataset(name) / settings.DATA_FOLDERS["raw"] / source

def processed_root(name, source):
    if source not in settings.SOURCES:
        raise ValueError(f"未知来源 {source}")
    return dataset(name) / settings.DATA_FOLDERS["processed"] / source

def final_root(name):
    return dataset(name) / settings.DATA_FOLDERS["final"]

def supplementary(name):
    return dataset(name) / settings.DATA_FOLDERS["supplementary"]

def report_root(group, topic="app"):
    if group not in settings.REPORT_GROUPS:
        raise ValueError(f"未知报告类别 {group}")
    if topic not in settings.REPORT_TOPICS:
        raise ValueError(f"未知工作内容 {topic}")
    return settings.REPORT_GROUPS[group] / settings.REPORT_TOPICS[topic]

def stage_dir(context, step, session=None):
    destination = settings.DATA_STAGE_DESTINATIONS[step]
    if destination == "processed":
        path = context["processed_output"] / step
    elif destination == "final":
        path = context["final_output"]
    elif destination == "report":
        path = context["output"]
    else:
        raise ValueError(f"未实现的输出类型 {destination}")
    return path / session if session else path
