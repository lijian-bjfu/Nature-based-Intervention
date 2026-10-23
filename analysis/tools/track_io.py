"""埋点唯一读写接口：字段、类别、文件名、缺失规则均来自 settings。"""
from pathlib import Path
import pandas as pd
from importlib import import_module
settings = import_module("00_settings")

TABLES = settings.APP_TABLES

def read_table(session_dir, name, *, formatted=False):
    path = Path(session_dir) / settings.APP_FILES[name]
    cols = list(settings.table_columns(name))
    if not path.is_file():
        frame = pd.DataFrame(columns=cols)
        frame.attrs["present"] = False
        return frame
    frame = pd.read_csv(path, dtype="string", **settings.APP_CSV)
    missing = set(cols)-set(frame.columns)
    if missing:
        raise ValueError(f"{path}: 缺少配置要求的字段 {sorted(missing)}")
    frame.attrs["present"] = True
    if formatted:
        frame = convert_types(frame, name)
    return frame

def read_session(session_dir, *, formatted=False):
    return {name: read_table(session_dir, name, formatted=formatted) for name in TABLES}

def convert_types(frame, table):
    out = frame.copy()
    for field, name in settings.APP_COLUMNS[table].items():
        dtype = settings.APP_TYPES[field]
        if dtype == "boolean":
            known = {settings.APP_TRUE: True, settings.APP_FALSE: False}
            bad = out[name].dropna()[~out[name].dropna().isin(known)]
            if not bad.empty:
                raise ValueError(f"{table}.{name}: 非法布尔值 {bad.unique().tolist()}")
            out[name] = out[name].map(known).astype("boolean")
        elif dtype in ("Float64", "Int64"):
            out[name] = pd.to_numeric(out[name], errors="raise").astype(dtype)
        else:
            out[name] = out[name].astype("string")
    out.attrs.update(frame.attrs)
    return out

def write_table(folder, table, frame):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    for field, name in settings.APP_COLUMNS[table].items():
        if field == "is_touched" and pd.api.types.is_bool_dtype(out[name].dtype):
            out[name] = out[name].map({True: settings.APP_TRUE, False: settings.APP_FALSE})
    out.to_csv(folder / settings.APP_FILES[table], index=False, encoding="utf-8", na_rep="")
