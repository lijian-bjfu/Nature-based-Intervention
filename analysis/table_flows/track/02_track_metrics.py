"""track 制表入口：读取同目录 parameters.py，支持 VS Code Run 与命令行。

流程：载入（data_access）→ 清理（历史取值）→ 确定分析窗口 → 指标（tools/track_metrics.py）→ 制表。
分析窗口（2026-11-10 研究者确认，global_settings.TRACK_ANALYSIS_WINDOW）：埋点指标只算干预窗口——生理 03 更正后的
intervention_start 到 intervention_end，按 t_device 与 t_session 之差的中位数换算为会话时间；没有生理事件（或标签不全）时，
从 App 记录起点切 750 s（12 分 30 秒）。窗口之外的埋点行一律不参与计算；duration_s 是窗口长度（记录没覆盖整个窗口时取
实际覆盖部分，并在 note 列注明）。结果表带 window_source（events / fallback）、window_start_s、window_end_s（会话时间）。
第一次触摸时间与每分钟表都从窗口起点算起；逗留明细（track_dwells）里的时刻仍是会话时间。
输出到 data/<dataset>/final/track/：
  track_metrics.csv        每名被试一行，第十节全部指标（宽表）
  track_dwells.csv         每次逗留一行
  track_ap.csv             被试 × 景点：逗留次数、逗留时长、触摸次数（分景点明细，用于评估景点设计）
  track_areas.csv          被试 × 区域/桥：在内时间、逗留时间、行动范围面积（用于评估区域设计）
  track_per_minute.csv     被试 × 分钟：点击、无位移点击、approach、触摸、环视、停留时间、路程（时间变化的报告）
  track_columns.csv        宽表各列的中文说明
  _provenance/             所用数据、参数、规范与代码版本
组别等被试信息不在这里加入，由 integration 按被试表合并。
"""
SCRIPT_HISTORY = [
    {"at": "2026-10-25T00:55:39+08:00", "action": "created",
     "summary": "实现 track 制表：按 global_settings.METRICS 计算第十节全部指标，输出宽表与明细表。"},
    {"at": "2026-11-10T00:00:00+08:00", "action": "modified",
     "summary": "指标只算干预窗口（global_settings.TRACK_ANALYSIS_WINDOW）；结果表增加 window_source、window_start_s、window_end_s 与 note。"},
]

from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT/"analysis"), str(PROJECT/"analysis/tools")]

import argparse
import importlib.metadata
import shutil

import pandas as pd

import global_settings as settings
from safe_io import retire_dir  # 旧目录移到 _to_delete，不直接删除
from workflow import load_script
from paths import ROOT, ANALYSIS, DATASETS, GEO_ANNOTATION, final_root
from data_access import subjects as list_subjects, find, load, load_geo
from track_metrics import compute_record, analysis_window, clean_legacy, SceneGeometry, SUMMARY_COLUMNS
from artifacts import sha256, write_json, settings_snapshot
from run_records import now, run_id, git_state, record_sources


def choose(dataset, subjects, runs):
    pool = list_subjects(dataset, "track")
    if subjects == "*":
        chosen = pool
    else:
        chosen = [subjects] if isinstance(subjects, str) else list(subjects)
        missing = sorted(set(chosen) - set(pool))
        if missing:
            raise ValueError(f"{dataset} 中没有这些被试：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"{dataset} 中还没有 track 数据（data/.../raw/track/ 为空）")
    return {s: find(dataset, "track", [s], run=runs.get(s))[s] for s in chosen}


def run(parameters=None):
    if parameters is None:
        parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_track").PARAMETERS
    dataset = parameters["dataset"]
    if dataset not in DATASETS:
        raise ValueError(f"dataset 应为 {tuple(DATASETS)}")
    settings.validate()
    records = choose(dataset, parameters.get("subjects", "*"), parameters.get("runs", {}) or {})
    geo = load_geo()
    scene = SceneGeometry(geo)
    rows, dwells, aps, areas, per_min = [], [], [], [], []
    for subject, folder in records.items():
        tables = load(dataset, "track", subject, run=parameters.get("runs", {}).get(subject), formatted=True)
        res = compute_record(tables, scene, analysis_window(dataset, subject, clean_legacy(tables)))
        key = {"subject": subject, "record": folder.name}
        commit = tables["session"][settings.column("session", "app_commit")].iloc[0]
        rows.append({**key, "app_commit": None if pd.isna(commit) else str(commit), **res.summary})
        for frame, sink in ((res.dwells, dwells), (res.ap, aps), (res.areas, areas), (res.per_minute, per_min)):
            sink.append(frame.assign(**key)[list(key) + list(frame.columns)])
        print(f"  {subject}  {folder.name}  逗留 {res.summary['dwell_n']} 次  点击 {res.summary['tap_n']}  触摸 {res.summary['touch_n']}", flush=True)

    dest = final_root(dataset) / "track"
    if dest.exists():
        retire_dir(dest)
    dest.mkdir(parents=True)
    wide = pd.DataFrame(rows)[["subject", "record", "app_commit"] + list(SUMMARY_COLUMNS)]
    wide.to_csv(dest / "track_metrics.csv", index=False, encoding="utf-8-sig")
    for name, parts in (("track_dwells", dwells), ("track_ap", aps), ("track_areas", areas), ("track_per_minute", per_min)):
        pd.concat(parts, ignore_index=True).to_csv(dest / f"{name}.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"column": k, "label": v} for k, v in SUMMARY_COLUMNS.items()]).to_csv(dest / "track_columns.csv", index=False, encoding="utf-8-sig")

    prov = dest / "_provenance"
    files = [ROOT / "global_settings.py"] + sorted((ANALYSIS / "tools").glob("*.py")) + [Path(__file__).resolve(), Path(__file__).with_name("parameters.py")]
    hashes, copied = record_sources(ROOT, files, prov / "uncommitted_sources")
    write_json(prov / "manifest.json", {
        "flow": "table_flows/track", "run_id": run_id(), "run_at": now(), "parameters": parameters,
        "records": {s: f.name for s, f in records.items()},
        "raw_sha256": {str(p.relative_to(ROOT)): sha256(p) for f in records.values() for n in settings.TRACK_TABLES
                       if (p := f / settings.TRACK_FILES[n]).is_file()},
        "geo_annotation": {"path": str(GEO_ANNOTATION), "sha256": sha256(GEO_ANNOTATION),
                           "exported_at": geo.get("exported_at"), "unity_commit": geo.get("unity_commit")},
        "scene_walkable_m2": scene.walkable_m2, "metrics": settings.METRICS["track"],
        "git": git_state(ROOT, files), "script_sha256": hashes, "uncommitted_copied": copied,
        "python_version": sys.version,
        "package_versions": {n: importlib.metadata.version(n) for n in ("numpy", "pandas", "matplotlib")}})
    write_json(prov / "global_settings_snapshot.json", settings_snapshot())
    print(f"共 {len(rows)} 名被试；输出：{dest}")
    return dest


def cli(argv=None):
    parser = argparse.ArgumentParser(description="track 制表：第十节全部指标")
    parser.add_argument("--dataset", choices=tuple(DATASETS))
    parser.add_argument("--subjects", nargs="+")
    parser.add_argument("--list", action="store_true", help="列出这个数据集里的被试，不执行")
    args = parser.parse_args(argv)
    parameters = dict(load_script(Path(__file__).with_name("parameters.py"), "parameters_track").PARAMETERS)
    if args.dataset:
        parameters["dataset"] = args.dataset
    if args.subjects:
        parameters["subjects"] = args.subjects if len(args.subjects) > 1 else args.subjects[0]
    if args.list:
        print(f"{parameters['dataset']}：{list_subjects(parameters['dataset'], 'track')}")
        return 0
    try:
        run(parameters)
        return 0
    except (ValueError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
