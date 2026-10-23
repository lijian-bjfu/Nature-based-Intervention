"""03：应用集中配置的字段类型，输出标准表；非法数值/布尔值明确报错。"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "00_settings.py").is_file())
sys.path.insert(0, str(PROJECT))
from importlib import import_module
settings = import_module("00_settings")
sys.path.insert(0, str(settings.TOOLS_DIR))

import pandas as pd
from track_io import read_session, convert_types, write_table
from artifacts import write_json
from paths import stage_dir

def run(context):
    notes = []
    for source in context.sessions:
        incoming = stage_dir(context,"02_clean",source.name)/settings.STAGE_TABLE_FOLDER
        tables = read_session(incoming)
        dest = stage_dir(context,"03_format",source.name)/settings.STAGE_TABLE_FOLDER
        for table,frame in tables.items():
            if not frame.attrs["present"]:
                continue
            frame = convert_types(frame,table)
            for field,levels in settings.APP_LEVELS.get(table,{}).items():
                name = settings.column(table,field)
                extra = frame[name].dropna()[~frame[name].dropna().isin(levels)].unique().tolist()
                if extra:
                    notes.append({"session_dir":source.name,"field":f"{table}.{name}","unknown_values":extra})
            write_table(dest,table,frame)
    write_json(stage_dir(context,"03_format")/"format_notes.json",notes)

if __name__ == "__main__":
    from pipeline import cli
    cli(("track_format",))
