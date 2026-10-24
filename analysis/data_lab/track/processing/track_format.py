"""03：应用集中配置的字段类型，输出标准表；非法数值/布尔值明确报错。"""
SCRIPT_HISTORY = [
    {"at": "2026-10-23T20:36:13+08:00", "action": "first_versioned",
     "summary": "已有工具首次纳入 Git；原始创建时间未知。", "commit": "38cdd46dd4da3d1f614d5f558a10f886d96cbafb"},
    {"at": "2026-10-23T20:48:27+08:00", "action": "refactor",
     "summary": "改用 global_settings 原始数据规范与调用方上下文，移除根入口和固定参数依赖；处理规则不变。"},
    {"at": "2026-10-24T14:00:00+08:00", "action": "modified", "summary": "规范外取值的记录附上 app_commit，定位产生数据的 APP 代码版本。"},
]

from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT),str(PROJECT/"analysis"),str(PROJECT/"analysis/tools")]
import global_settings as settings

import pandas as pd
from track_io import read_session, convert_types, write_table, app_commit
from artifacts import write_json
from paths import stage_dir

def run(context):
    notes = []
    for source in context.sessions:
        incoming = stage_dir(context,"02_clean",source.name)/context.table_folder
        tables = read_session(incoming)
        dest = stage_dir(context,"03_format",source.name)/context.table_folder
        for table,frame in tables.items():
            if not frame.attrs["present"]:
                continue
            frame = convert_types(frame,table)
            for field,levels in settings.TRACK_LEVELS.get(table,{}).items():
                name = settings.column(table,field)
                extra = frame[name].dropna()[~frame[name].dropna().isin(levels)].unique().tolist()
                if extra:
                    notes.append({"session_dir":source.name,"field":f"{table}.{name}","unknown_values":extra,
                                  "app_commit":app_commit(incoming)})
            write_table(dest,table,frame)
    write_json(stage_dir(context,"03_format")/"format_notes.json",notes)

if __name__ == "__main__":
    print("这是实验工具。请运行 data_lab/track/description/record_description/track_describe.py；选择相应 tasks 可单独检查本环节。")
