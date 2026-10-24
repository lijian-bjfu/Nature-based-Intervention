"""按明确登记时间检索 Lab 脚本的先后顺序；不使用文件修改时间猜测历史。

VS Code 可修改下方 PARAMETERS 后点 Run；命令行支持 --since、--until、--object。
只解析 SCRIPT_HISTORY，不导入实验脚本，不扫描 outputs、archive 中的历史副本。
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT),str(PROJECT/"analysis/tools")]
from datetime import datetime, time
from zoneinfo import ZoneInfo
import argparse
import csv

from paths import DATA_LAB
from run_records import script_history, TIMEZONE

PARAMETERS = {"since": None, "until": None, "object": None, "write_csv": True}
# since / until：None 表示不限；可填 "2026-10-23" 或带时区的 ISO 时间。
# object：None 表示全部，也可填 "track" / "psycho" / "physio"。
# 日期的 until 包含当天；精确时间按给定时刻截止。

def boundary(value, end=False):
    if value is None:
        return None
    if len(value)==10:
        return datetime.combine(datetime.fromisoformat(value).date(),
                                time.max if end else time.min,tzinfo=ZoneInfo(TIMEZONE))
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("精确时间须带时区，例如 2026-10-23T20:00:00+08:00")
    return parsed

def collect(since=None, until=None, object_name=None):
    lower, upper = boundary(since), boundary(until,True)
    if lower and upper and lower>upper:
        raise ValueError("since 不得晚于 until")
    rows = []
    for path in sorted(DATA_LAB.rglob("*.py")):
        relative = path.relative_to(DATA_LAB)
        if set(relative.parts)&{"outputs","archive","source_snapshot","uncommitted_sources","__pycache__"}:
            continue
        if object_name and relative.parts[0]!=object_name:
            continue
        for event in script_history(path):
            at = datetime.fromisoformat(event["at"])
            if at.tzinfo is None:
                raise ValueError(f"{path}: SCRIPT_HISTORY 时间缺少时区")
            if (lower and at<lower) or (upper and at>upper):
                continue
            rows.append({"at":event["at"],"object":relative.parts[0],
                         "stage":relative.parts[1] if len(relative.parts)>2 else "",
                         "script":str(path.relative_to(PROJECT)),
                         "action":event["action"],"summary":event["summary"],
                         "commit":event.get("commit",""),
                         "previous_path":event.get("previous_path",""),
                         "deprecated":"deprecated" in relative.parts})
    return sorted(rows,key=lambda row:(datetime.fromisoformat(row["at"]),row["script"]))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since",default=PARAMETERS["since"])
    parser.add_argument("--until",default=PARAMETERS["until"])
    parser.add_argument("--object",choices=("track","psycho","physio"),default=PARAMETERS["object"])
    parser.add_argument("--no-write",action="store_true")
    args=parser.parse_args(argv)
    try:
        rows=collect(args.since,args.until,args.object)
    except ValueError as error:
        parser.error(str(error))
    for row in rows:
        print(f"{row['at']} | {row['action']} | {row['script']} | {row['summary']}")
    if PARAMETERS["write_csv"] and not args.no_write:
        destination=DATA_LAB/"history_index.csv"
        keys=("at","object","stage","script","action","summary","commit","previous_path","deprecated")
        with destination.open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
        print("时间索引："+str(destination))
    return rows

if __name__=="__main__":
    main()
