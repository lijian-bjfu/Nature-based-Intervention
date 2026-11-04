"""埋点唯一读写接口：字段、类别、文件名、缺失规则均来自 settings。"""
from pathlib import Path
import pandas as pd
import global_settings as settings

TABLES = settings.TRACK_TABLES

def app_commit(session_dir):
    """报错时附上产生这份数据的 APP 代码版本，便于定位是哪个版本的代码产生了不符合规范的数据。"""
    path = Path(session_dir) / settings.TRACK_FILES["session"]
    try:
        value = pd.read_csv(path, dtype="string", **settings.TRACK_CSV).get("app_commit")
        commit = value.iloc[0] if value is not None and len(value) and pd.notna(value.iloc[0]) else None
    except Exception:
        commit = None
    return f"APP 代码版本 app_commit={commit}" if commit else "APP 代码版本未知（加入 app_commit 之前录制的数据）"

def read_table(session_dir, name, *, formatted=False):
    path = Path(session_dir) / settings.TRACK_FILES[name]
    cols = list(settings.table_columns(name))
    if not path.is_file():
        frame = pd.DataFrame(columns=cols)
        frame.attrs["present"] = False
        return frame
    frame = pd.read_csv(path, dtype="string", **settings.TRACK_CSV)
    for legacy in settings.TRACK_LEGACY_MISSING.get(name, ()):
        if legacy not in frame.columns:
            frame[legacy] = pd.NA
    frame = frame.drop(columns=[c for c in settings.TRACK_LEGACY_EXTRA.get(name, ()) if c in frame.columns])
    missing = set(cols)-set(frame.columns)
    if missing:
        raise ValueError(f"{path}: 缺少配置要求的字段 {sorted(missing)}；{app_commit(session_dir)}")
    extra = set(frame.columns)-set(cols)
    if extra:
        raise ValueError(f"{path}: 出现规范外的字段 {sorted(extra)}；{app_commit(session_dir)}")
    frame.attrs["present"] = True
    frame.attrs["session_dir"] = str(session_dir)
    if formatted:
        frame = convert_types(frame, name)
    return frame

def read_session(session_dir, *, formatted=False):
    return {name: read_table(session_dir, name, formatted=formatted) for name in TABLES}

def convert_types(frame, table):
    out = frame.copy()
    for field, name in settings.TRACK_COLUMNS[table].items():
        dtype = settings.TRACK_TYPES[field]
        if dtype == "boolean":
            known = {settings.TRACK_TRUE: True, settings.TRACK_FALSE: False}
            bad = out[name].dropna()[~out[name].dropna().isin(known)]
            if not bad.empty:
                raise ValueError(f"{table}.{name}: 非法布尔值 {bad.unique().tolist()}；"
                                 f"{app_commit(frame.attrs['session_dir']) if 'session_dir' in frame.attrs else ''}")
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
    for field, name in settings.TRACK_COLUMNS[table].items():
        if field == "is_touched" and pd.api.types.is_bool_dtype(out[name].dtype):
            out[name] = out[name].map({True: settings.TRACK_TRUE, False: settings.TRACK_FALSE})
    out.to_csv(folder / settings.TRACK_FILES[table], index=False, encoding="utf-8", na_rep="")
