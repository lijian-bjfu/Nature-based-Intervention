"""02：保留空值与历史字符串的区别；仅在输出副本中应用已定的取值映射。"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "settings.py").is_file())
sys.path.insert(0, str(PROJECT))
import settings
sys.path.insert(0, str(settings.TOOLS_DIR))

from app_io import read_session, write_table
from artifacts import write_json
from paths import stage_dir

def run(context):
    changes = []
    for source in context["sessions"]:
        tables = read_session(source)
        dest = stage_dir(context,"02_clean",source.name)/settings.STAGE_TABLE_FOLDER
        for table, frame in tables.items():
            if not frame.attrs["present"]:
                continue
            for field, mapping in settings.APP_LEGACY_VALUES.get(table,{}).items():
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
    from pipeline import cli
    cli(("02_clean",))
