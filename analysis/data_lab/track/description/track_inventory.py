"""01：核对已拷入 raw/track 的文件；不会重新写入或修改原始数据。"""
SCRIPT_HISTORY = [
    {"at": "2026-10-23T20:36:13+08:00", "action": "first_versioned",
     "summary": "已有工具首次纳入 Git；原始创建时间未知。", "commit": "38cdd46dd4da3d1f614d5f558a10f886d96cbafb"},
    {"at": "2026-10-23T20:48:27+08:00", "action": "refactor",
     "summary": "改用 global_settings 原始数据规范与调用方上下文，移除根入口和固定参数依赖；处理规则不变。"},
    {"at": "2026-10-24T15:00:00+08:00", "action": "moved", "summary": "按\"一个文件夹一个研究问题\"整理：本问题用到的脚本都放在 track/description/。", "previous_path": "analysis/data_lab/track/processing/track_inventory.py"},
]

from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT),str(PROJECT/"analysis"),str(PROJECT/"analysis/tools")]
import global_settings as settings

from artifacts import write_json, sha256
from paths import stage_dir

def run(context):
    entries = []
    for source in context.sessions:
        tables = {}
        for table in settings.TRACK_TABLES:
            path = source/settings.TRACK_FILES[table]
            tables[table] = {"present": path.is_file(), "sha256": sha256(path) if path.is_file() else None}
        entries.append({"session_dir": source.name, "tables": tables})
    write_json(stage_dir(context,"01_import")/"inventory.json", entries)
    context.inventory = entries

if __name__ == "__main__":
    print("这是实验工具。请运行 data_lab/track/description/track_describe.py；选择相应 tasks 可单独检查本环节。")
