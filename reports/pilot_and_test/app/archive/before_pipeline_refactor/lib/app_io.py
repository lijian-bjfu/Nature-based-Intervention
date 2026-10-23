"""读取 APP 实验数据（规范见 研究思路/实验记录-埋点.md 附A）。

所有读取 APP 数据的脚本都用这里的函数，不直接 pd.read_csv：
pandas 默认把 "None"、"NA" 等字符串当成缺失值。APP 数据只以空格作为缺失，
其余取值一律按原样读入（早期数据里仍有取值 None，规范已改为 NoHit / NotBlocked）。
"""
from pathlib import Path
import pandas as pd

from .paths import raw

TABLES = ("session", "spacetime", "tap", "backstep", "look", "world_event", "tech_glitch")


def read_table(session_dir: Path, name: str) -> pd.DataFrame:
    f = Path(session_dir) / f"{name}.csv"
    if not f.exists():
        return pd.DataFrame()
    return pd.read_csv(f, keep_default_na=False, na_values=[""])


def read_session(session_dir: Path) -> dict:
    """读一个会话文件夹里的全部表，返回 {表名: DataFrame}。"""
    return {n: read_table(session_dir, n) for n in TABLES}


def session_dirs(phase: str, module: str = None):
    """列出某阶段的全部会话文件夹，可按模块（Practice / Interactive / Passive）筛选。"""
    for d in sorted(raw(phase, "app").glob("sub-*")):
        if module is None or f"_mod-{module}_" in d.name:
            yield d
