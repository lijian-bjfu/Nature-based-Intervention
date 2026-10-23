"""跨来源共用的结果序列化、校验值和 Markdown 表格。"""
from pathlib import Path
from dataclasses import asdict, is_dataclass
import hashlib
import json
import math
import numpy as np
import pandas as pd
import settings

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def json_ready(value):
    if is_dataclass(value):
        return json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if value is pd.NA:
        return None
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_ready(value), ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def records(frame):
    return [{k: json_ready(v) for k,v in row.items()} for row in frame.to_dict("records")]

def markdown_table(frame):
    def show(value):
        if value is pd.NA or value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.3f}" if math.isfinite(value) else "—"
        return str(value).replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(str, frame.columns)) + " |",
                       "| " + " | ".join(["---"]*len(frame.columns)) + " |"] +
                      ["| " + " | ".join(show(x) for x in row) + " |"
                       for row in frame.itertuples(index=False, name=None)])

def settings_snapshot():
    return {name: json_ready(getattr(settings, name))
            for name in dir(settings) if name.isupper() and not name.startswith("_")}
