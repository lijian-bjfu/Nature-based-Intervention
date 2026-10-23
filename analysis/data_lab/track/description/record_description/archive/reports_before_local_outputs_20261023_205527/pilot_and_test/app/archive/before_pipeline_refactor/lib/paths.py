"""统一的路径配置。所有分析脚本都从这里取路径，不在脚本里写死。

数据集（三者绝对隔离）：
    "main"          正式实验              data/main/
    "pilot"         预实验                data/pilot_and_test/pilot/
    "logging_test"  埋点开发测试          data/pilot_and_test/logging_test/

用法：
    from lib.paths import raw, derived
    raw("logging_test", "app")        # data/pilot_and_test/logging_test/raw/app
    derived("main", "04_features")    # data/main/derived/04_features
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # 项目主目录（analysis/lib/ 向上两级）
DATA = ROOT / "data"
ANALYSIS = ROOT / "analysis"

DATASETS = {
    "main":         DATA / "main",
    "pilot":        DATA / "pilot_and_test" / "pilot",
    "logging_test": DATA / "pilot_and_test" / "logging_test",
}
SOURCES = ("app", "physio", "questionnaire", "interview", "session_notes")


def dataset(name: str) -> Path:
    assert name in DATASETS, f"未知数据集 {name}，可选：{list(DATASETS)}"
    return DATASETS[name]


def raw(name: str, source: str) -> Path:
    """原始数据目录（只读）。"""
    assert source in SOURCES, source
    return dataset(name) / "raw" / source


def derived(name: str, step: str) -> Path:
    """派生数据目录（脚本生成，可删可重建）；不存在时自动创建。"""
    p = dataset(name) / "derived" / step
    p.mkdir(parents=True, exist_ok=True)
    return p


def participants(name: str) -> Path:
    """被试表（只有 main 与 pilot 有）：被试编号、场次、组别、日期等个人与分组信息。"""
    return dataset(name) / "participants.csv"
