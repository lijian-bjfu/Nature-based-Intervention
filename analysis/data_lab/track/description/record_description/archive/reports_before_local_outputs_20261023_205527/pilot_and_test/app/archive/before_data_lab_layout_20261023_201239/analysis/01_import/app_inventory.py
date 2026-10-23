"""01：核对已拷入 raw/app 的文件；不会重新写入或修改原始数据。"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "00_settings.py").is_file())
sys.path.insert(0, str(PROJECT))
from importlib import import_module
settings = import_module("00_settings")
sys.path.insert(0, str(settings.TOOLS_DIR))

from artifacts import write_json, sha256
from paths import stage_dir

def run(context):
    entries = []
    for source in context.sessions:
        tables = {}
        for table in settings.APP_TABLES:
            path = source/settings.APP_FILES[table]
            tables[table] = {"present": path.is_file(), "sha256": sha256(path) if path.is_file() else None}
        entries.append({"session_dir": source.name, "tables": tables})
    write_json(stage_dir(context,"01_import")/"inventory.json", entries)
    context.inventory = entries

if __name__ == "__main__":
    from pipeline import cli
    cli(("app_inventory",))
