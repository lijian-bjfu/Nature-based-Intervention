"""工程路径与数据命名规范（项目规范，制表与数据实验都按此调用数据）。

数据由四个名字定位：

    dataset   哪一套数据：formal（正式实验）、pilot（预实验）、test（开发测试）
              formal 与另外两者绝对隔离：formal 在 data/formal/，pilot 与 test 在 data/pilot_and_test/ 下。
    layer     加工程度：raw（原始，只读）、processed（处理中间结果）、final（最终分析表）
              另有 supplementary：分组、被试信息、访谈编码等补充信息，不属于某个 pipeline。
    pipeline  数据类型，与 table_flows 的流程对应：track（虚拟自然行为）、psycho（问卷）、physio（生理）
    subject   被试编号，如 P040。不含组别（组别记在被试表里，由程序按编号查）。

磁盘上的位置：data/<dataset 所在目录>/<layer>/<pipeline>/sub-P###/<该被试的记录文件>
例：data/pilot_and_test/test/raw/track/sub-P999/sub-P999_mod-Interactive_run-002/
不用于分析的文件放在被试文件夹下的 _excluded/，读取时跳过。

调取数据请用 data_access.py，不要在脚本里拼路径。数据规范（表、字段、取值、单位）在 global_settings.py；
本文件只管"数据在哪"，不管"数据是什么"。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ANALYSIS = ROOT / "analysis"
DATA_LAB = ANALYSIS / "data_lab"
TABLE_FLOWS = ANALYSIS / "table_flows"
CACHE = ROOT / ".cache"

DATASETS = {
    "formal": {"root": DATA / "formal", "kind": "formal", "label": "正式实验数据"},
    "pilot":  {"root": DATA / "pilot_and_test" / "pilot", "kind": "pilot_and_test", "label": "预实验数据"},
    "test":   {"root": DATA / "pilot_and_test" / "test", "kind": "pilot_and_test", "label": "开发测试数据"},
}
# 地理空间标注（区域、桥、景点、空气墙）由虚拟自然工程导出，不属于任何 dataset：它描述场景，
# 对所有被试相同。导出位置固定在 Unity 工程内，随 Unity 代码库留版本；格式规范见 global_settings.GEO_ANNOTATION_SPEC。
GEO_ANNOTATION = Path("/Users/lijian/Working Projects/NBI proj/nature/Assets/_Project/Interaction/GeoAnnotation~/geo_annotation.json")
LAYERS = ("raw", "processed", "final")
PIPELINES = ("track", "psycho", "physio")
# raw 下除三个 pipeline 外，还有不属于任何 pipeline 的原始材料
RAW_EXTRAS = ("interview", "session_notes")


def dataset(name):
    if name not in DATASETS:
        raise ValueError(f"未知 dataset：{name}；可选 {tuple(DATASETS)}")
    return DATASETS[name]["root"]


def layer_dir(name, layer, pipeline=None):
    """data/<dataset>/<layer>/[<pipeline>]"""
    if layer not in LAYERS + ("supplementary",):
        raise ValueError(f"未知 layer：{layer}；可选 {LAYERS + ('supplementary',)}")
    path = dataset(name) / layer
    if pipeline is None:
        return path
    if pipeline not in PIPELINES + (RAW_EXTRAS if layer == "raw" else ()):
        raise ValueError(f"未知 pipeline：{pipeline}；可选 {PIPELINES}")
    return path / pipeline


# 以下为常用简写，与 layer_dir 等价
def raw(name, pipeline):
    return layer_dir(name, "raw", pipeline)

def processed_root(name, pipeline):
    return layer_dir(name, "processed", pipeline)

def final_root(name):
    return layer_dir(name, "final")

def supplementary(name):
    return layer_dir(name, "supplementary")


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
