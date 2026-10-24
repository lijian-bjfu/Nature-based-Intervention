"""data_lab/track/description/path_viewer：把一份实验记录叠加在地理空间标注上，生成可交互的路径浏览页。"""

# ════════════════════════════════════════════════════════════════════
# ▼▼▼ 研究者只需要改这一段 PARAMETERS，改完保存，点右上角 Run ▼▼▼
# ════════════════════════════════════════════════════════════════════
# selection：选哪份数据（一次只看一份记录；用了哪份，在 log.md 里记下）。
#   dataset：test=开发测试，pilot=预实验，formal=正式实验。
#   subject：被试编号，如 "P000"。
#   run：同一被试有多份记录时才需要填，如 "004"；只有一份时填 None。
# stay：浏览页上"停留"图层的画法（暂定口径，见 description/behavior 的讨论，尚未写入规范）。
#   still_step_m：相邻两个采样之间水平位置变化不超过多少米，算这一步没动。
#   min_seconds：连续没动至少多久，才画成一次停留。
# dwell：浏览页打开时"逗留"的识别参数。None = 用 global_settings.METRICS 中登记的逗留阈值（推荐）；
#   想临时试别的值，可写成 {"min_seconds": 10.0, "radius_m": 2.0}。页面上也可以随时拖动调整。
PARAMETERS = {
    "selection": {
        "dataset": "test",
        "subject": "P000",
        "run": "004",
    },
    "stay": {
        "still_step_m": 0.03,
        "min_seconds": 2.0,
    },
    "dwell": None,
}

# ════════════════════════════════════════════════════════════════════
# ▲▲▲ 以上是参数。以下是程序本身，日常使用不需要修改 ▲▲▲
# ════════════════════════════════════════════════════════════════════

from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT/"analysis"), str(PROJECT/"analysis/tools")]

import importlib.metadata
import json
import re
import shutil

import numpy as np
import pandas as pd

import global_settings as settings
from data_access import find, load, load_geo
from artifacts import sha256, write_json, settings_snapshot
from options import positive
from paths import ROOT, ANALYSIS, DATASETS, GEO_ANNOTATION
from run_records import now, run_id, git_state, record_sources, script_history

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "viewer_template.html"
OUTPUT_NAME = "path_viewer.html"


def check(parameters):
    sel = parameters["selection"]
    if sel["dataset"] not in DATASETS:
        raise ValueError(f"selection.dataset 应为 {tuple(DATASETS)} 之一")
    if not re.fullmatch(r"P\d+", str(sel["subject"])):
        raise ValueError("selection.subject 应是一名被试的编号，如 P000")
    run = sel.get("run")
    stay = parameters["stay"]
    step = float(stay["still_step_m"])
    if not 0 <= step < 1:
        raise ValueError("stay.still_step_m 应在 0 到 1 米之间")
    return {"dataset": sel["dataset"], "subject": str(sel["subject"]),
            "run": None if run in (None, "") else str(run),
            "still_step": step, "min_stay": positive(stay["min_seconds"], "stay.min_seconds"),
            **dwell_params(parameters.get("dwell"))}


def dwell_params(override):
    """逗留阈值：默认取 global_settings.METRICS 中登记的值，PARAMETERS.dwell 可临时覆盖。"""
    reg = settings.METRICS["track"]["dwell"]["parameters"]
    o = override or {}
    return {"dwell_t": positive(o.get("min_seconds", reg["min_seconds"]), "dwell.min_seconds"),
            "dwell_r": positive(o.get("radius_m", reg["radius_m"]), "dwell.radius_m"),
            "dwell_step": float(reg["still_step_m"]), "dwell_registered": not override}


def col(tables, table, field, dtype=float):
    return tables[table][settings.column(table, field)].to_numpy(dtype=dtype, na_value=np.nan)


def txt(tables, table, field):
    return tables[table][settings.column(table, field)].astype("string").fillna("").tolist()


def r(v, n):
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), n)


def stays(t, x, z, step_m, min_s, tap_t, touched_t):
    """相邻采样水平位移 ≤ step_m 算没动；连续没动、持续 ≥ min_s 的一段画成一次停留。"""
    step = np.hypot(np.diff(x), np.diff(z))
    still = step <= step_m
    out, s = [], None
    for i in range(len(still) + 1):
        if i < len(still) and still[i]:
            if s is None: s = i
            continue
        if s is not None:
            a, b = t[s], t[i]
            if b - a >= min_s:
                out.append({"t0": r(a, 2), "t1": r(b, 2), "dur": r(b - a, 2),
                            "x": r(x[s:i + 1].mean(), 2), "z": r(z[s:i + 1].mean(), 2),
                            "taps": int(((tap_t >= a) & (tap_t <= b)).sum()),
                            "touched": int(((touched_t >= a) & (touched_t <= b)).sum())})
            s = None
    return out


def build(cfg):
    settings.validate()
    folder = find(cfg["dataset"], "track", [cfg["subject"]], run=cfg["run"])[cfg["subject"]]
    tb = load(cfg["dataset"], "track", cfg["subject"], run=cfg["run"], formatted=True)
    geo = load_geo()

    t, x, z, yaw = (col(tb, "spacetime", f) for f in ("t_session", "cam_x", "cam_z", "view_yaw"))
    if (np.diff(t) <= 0).any():
        raise ValueError("spacetime.t_session 不是严格递增")
    sess = tb["session"]
    end = sess[settings.column("session", "t_device_end")].iloc[0]
    start = sess[settings.column("session", "t_device_start")].iloc[0]
    duration = float(end - start) if pd.notna(end) else float(t[-1])

    taps = []
    tap_t = np.array([]); touched_t = np.array([])
    if tb["tap"].attrs["present"] and len(tb["tap"]):
        tt = col(tb, "tap", "t_session"); tap_t = tt
        touched = tb["tap"][settings.column("tap", "is_touched")].eq(True).fillna(False).to_numpy()
        touched_t = tt[touched]
        cols = {f: col(tb, "tap", f) for f in ("touch_id", "cam_x", "cam_z", "hit_x", "hit_z")}
        intent, layer, btype, reason = (txt(tb, "tap", f) for f in ("intent", "hit_layer", "block_type", "block_reason"))
        for i in range(len(tt)):
            taps.append({"id": int(cols["touch_id"][i]), "t": r(tt[i], 3), "x": r(cols["cam_x"][i], 2), "z": r(cols["cam_z"][i], 2),
                         "hx": r(cols["hit_x"][i], 2), "hz": r(cols["hit_z"][i], 2), "intent": intent[i], "layer": layer[i],
                         "touched": bool(touched[i]), "block": btype[i], "reason": reason[i]})
    looks = []
    if tb["look"].attrs["present"] and len(tb["look"]):
        lt0, lt1, ye, yp, yd, pp = (col(tb, "look", f) for f in ("t_session_start", "t_session_end", "yaw_end", "yaw_path", "yaw_delta", "pitch_path"))
        lty = txt(tb, "look", "look_type")
        looks = [{"t0": r(lt0[i], 2), "t1": r(lt1[i], 2), "yaw_end": r(ye[i], 1), "yaw_path": r(yp[i], 1),
                  "yaw_delta": r(yd[i], 1), "pitch_path": r(pp[i], 1), "type": lty[i]} for i in range(len(lt0))]
    backsteps = []
    if tb["backstep"].attrs["present"] and len(tb["backstep"]):
        bt, bx, bz, bd = (col(tb, "backstep", f) for f in ("t_session", "cam_x", "cam_z", "back_dist"))
        bb = txt(tb, "backstep", "block_type")
        backsteps = [{"t": r(bt[i], 2), "x": r(bx[i], 2), "z": r(bz[i], 2), "dist": r(bd[i], 2), "block": bb[i]} for i in range(len(bt))]
    events = []
    if tb["world_event"].attrs["present"] and len(tb["world_event"]):
        et, ex, ez = (col(tb, "world_event", f) for f in ("t_session", "cam_x", "cam_z"))
        en, ea, ed = (txt(tb, "world_event", f) for f in ("event_name", "action", "detail"))
        events = [{"t": r(et[i], 2), "x": r(ex[i], 2), "z": r(ez[i], 2), "name": en[i], "action": ea[i], "detail": ed[i]} for i in range(len(et))]
    glitches = []
    if tb["tech_glitch"].attrs["present"] and len(tb["tech_glitch"]):
        gt, gd = (col(tb, "tech_glitch", f) for f in ("t_session", "duration"))
        gs = txt(tb, "tech_glitch", "status")
        glitches = [{"t": r(gt[i], 2), "dur": r(gd[i], 2), "status": gs[i]} for i in range(len(gt))]

    stay_list = stays(t, x, z, cfg["still_step"], cfg["min_stay"], tap_t, touched_t)
    notes = [
        f"停留图层：相邻采样水平位移 ≤ {cfg['still_step']:g} m 算没动，连续没动 ≥ {cfg['min_stay']:g} s 画成一次停留。暂定口径，尚未写入规范。",
        f"逗留：把相邻的停顿（不动片段，长短不限）串起来，从第一次停顿到最后一次停顿，所有采样到平均位置的距离不超过 R、持续不少于 T，记为一次；中间的小移动算在内，走进来、走出去的路不算。默认 T = {cfg['dwell_t']:g} s、R = {cfg['dwell_r']:g} m（{'global_settings 登记值，见《实验记录-埋点》10.2' if cfg['dwell_registered'] else '本次临时覆盖，非登记值'}），可在页面上调整。阈值暂定，待预实验数据重新评估。",
        "点击默认画在点击时被试所在的位置，可切换为命中位置；「点击 → 命中连线」连接两者。",
        "环视线段从环视开始时的位置出发，指向停稳后的朝向，长 1.6 m，只表示方向。",
        "空间结构来自 Unity 地理空间标注导出，" + f"导出于 {geo.get('exported_at')}（Unity 提交 {str(geo.get('unity_commit'))[:8]}）。",
        "区域、桥内停留时间按轨迹采样落在多边形内的时间累加（单步间隔超过 1 s 的按 1 s 计）。",
        "滚轮缩放，拖动平移，双击范围聚焦；颜色与图层开关保存在本机浏览器。",
    ]
    data = {
        "meta": {"dataset": cfg["dataset"], "record": folder.name, "duration": r(duration, 2), "generated": now()[:16].replace("T", " "),
                 "notes": notes},
        "params": {"still_step_m": cfg["still_step"], "min_stay_s": cfg["min_stay"],
                   "dwell_min_s": cfg["dwell_t"], "dwell_radius_m": cfg["dwell_r"], "dwell_still_step_m": cfg["dwell_step"]},
        "geo": {"polygons": geo["polygons"], "air_walls": geo["air_walls"], "bounds": geo["bounds"]},
        "path": {"t": [r(v, 2) for v in t], "x": [r(v, 2) for v in x], "z": [r(v, 2) for v in z], "yaw": [r(v, 1) for v in yaw]},
        "stays": stay_list, "taps": taps, "looks": looks, "backsteps": backsteps, "events": events, "glitches": glitches,
    }
    return folder, data


def main():
    cfg = check(PARAMETERS)
    folder, data = build(cfg)
    dest = HERE / "results"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    assert html.count("/*__DATA__*/null") == 1
    (dest / OUTPUT_NAME).write_text(html.replace("/*__DATA__*/null", payload), encoding="utf-8")

    provenance = dest / "_provenance"
    files = [ROOT / "global_settings.py"] + sorted((ANALYSIS / "tools").glob("*.py")) + [Path(__file__).resolve(), TEMPLATE]
    hashes, copied = record_sources(ROOT, files, provenance / "uncommitted_sources")
    raw_hashes = {str(p.relative_to(ROOT)): sha256(p) for name in settings.TRACK_TABLES
                  if (p := folder / settings.TRACK_FILES[name]).is_file()}
    write_json(provenance / "manifest.json", {
        "experiment": "track/description/path_viewer", "run_id": run_id(), "run_at": now(),
        "selection": {k: cfg[k] for k in ("dataset", "subject", "run")}, "record": folder.name,
        "geo_annotation": {"path": str(GEO_ANNOTATION), "sha256": sha256(GEO_ANNOTATION)},
        "git": git_state(ROOT, files), "uncommitted_copied": copied,
        "script_sha256": hashes, "source_sha256": raw_hashes,
        "script_history": script_history(Path(__file__).resolve()),
        "python_version": sys.version,
        "package_versions": {n: importlib.metadata.version(n) for n in ("numpy", "pandas")}})
    write_json(provenance / "parameters_snapshot.json", PARAMETERS)
    write_json(provenance / "global_settings_snapshot.json", settings_snapshot())
    print(f"数据：{cfg['dataset']}／{folder.name}")
    print(f"在浏览器中打开：{dest / OUTPUT_NAME}")


# 脚本的修改记录（供 analysis/tools/lab_history.py 按时间检索），日常使用不必看。
SCRIPT_HISTORY = [
    {"at": "2026-10-24T21:17:11+08:00", "action": "created",
     "summary": "路径浏览页：一份实验记录叠加在地理空间标注（区域、桥、景点、空气墙）上，生成单文件交互页面；支持图层开关、颜色与透明度调整、时间窗筛选与播放、范围聚焦。"},
    {"at": "2026-10-24T22:23:42+08:00", "action": "modified",
     "summary": "增加逗留图层：页面内按时长 T、半径 R 识别逗留，参数可在页面上实时调整，默认值由 PARAMETERS.dwell 给出。"},
    {"at": "2026-10-24T22:35:56+08:00", "action": "modified",
     "summary": "逗留定义已登记到 global_settings.METRICS；页面默认阈值与停顿口径改为读取登记值，PARAMETERS.dwell 仅作临时覆盖。"},
    {"at": "2026-10-24T23:21:55+08:00", "action": "modified",
     "summary": "技术故障改用红色感叹三角（红叉只表示起步受阻）；增加点击筛选：全部 / 只看受阻 / 只看摸到。"},
]

if __name__ == "__main__":
    main()
