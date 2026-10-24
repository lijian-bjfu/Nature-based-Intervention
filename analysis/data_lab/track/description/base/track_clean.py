"""02：保留空值与历史字符串的区别；仅在输出副本中应用已定的取值映射。"""
SCRIPT_HISTORY = [
    {"at": "2026-10-23T20:36:13+08:00", "action": "first_versioned",
     "summary": "已有工具首次纳入 Git；原始创建时间未知。", "commit": "38cdd46dd4da3d1f614d5f558a10f886d96cbafb"},
    {"at": "2026-10-23T20:48:27+08:00", "action": "refactor",
     "summary": "改用 global_settings 原始数据规范与调用方上下文，移除根入口和固定参数依赖；处理规则不变。"},
    {"at": "2026-10-24T15:00:00+08:00", "action": "moved", "summary": "按\"一个文件夹一个研究问题\"整理：本问题用到的脚本都放在 track/description/。", "previous_path": "analysis/data_lab/track/processing/track_clean.py"},
    {"at": "2026-10-24T17:28:32+08:00", "action": "moved", "summary": "data_lab 按 pipeline／环节／研究问题三级组织：本问题（埋点原始记录的基本描述）移入 track/description/base/。", "previous_path": "analysis/data_lab/track/description/track_clean.py"}
]

from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT),str(PROJECT/"analysis"),str(PROJECT/"analysis/tools")]
import global_settings as settings

from track_io import read_session, write_table
from artifacts import write_json
from paths import stage_dir

def run(context):
    changes = []
    for source in context.sessions:
        tables = read_session(source)
        dest = stage_dir(context,"02_clean",source.name)/context.table_folder
        for table, frame in tables.items():
            if not frame.attrs["present"]:
                continue
            for field, mapping in settings.TRACK_LEGACY_VALUES.get(table,{}).items():
                name = settings.column(table,field)
                for old,new in mapping.items():
                    count = int(frame[name].eq(old).fillna(False).sum())
                    frame[name] = frame[name].replace({old:new})
                    if count:
                        changes.append({"session_dir":source.name,"table":table,
                                        "field":name,"old":old,"new":new,"rows":count})
            write_table(dest,table,frame)
    write_json(stage_dir(context,"02_clean")/"cleaning_log.json",changes)

if __name__ == "__main__":
    print("这是实验工具。请运行 data_lab/track/description/base/track_describe.py；选择相应 tasks 可单独检查本环节。")
