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
        "dataset": "pilot",
        "subject": "P002",
        "run": "001",
    },
    "stay": {
        "still_step_m": 0.03,
        "min_seconds": 2.0,
    },
    "dwell": None,
    # look：环视的判定窗口。None = 用 global_settings 登记值（拖动开始前 0.3 s 内有移动算"行进中拖动"，不计入环视）。
    "look": None,
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
from safe_io import retire_dir  # 旧目录移到 _to_delete，不直接删除
from data_access import find, load, load_geo
from track_metrics import clean_legacy, Pose, classify_taps, classify_drags, pauses
from artifacts import sha256, write_json, settings_snapshot
from options import positive
from paths import ROOT, ANALYSIS, DATASETS, GEO_ANNOTATION, layer_dir
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
            "look_window": positive((parameters.get("look") or settings.METRICS["track"]["look"]["parameters"])["walking_window_s"], "look.walking_window_s"),
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


# 被试信息卡上的问卷结果对照表（只用于显示，不参与任何分析）。
# 来源：data/<数据集>/processed/psycho/scores_wide.csv（psycho 工具 03 的输出，一名被试一行）。
# 每一项：(显示名, 来源列, 除数, 满分, 小数位)。显示的数值 = 来源列 ÷ 除数，格式"均值 / 满分"。
#   特质焦虑 T0_stait_sum 是 20 题之和，÷ 20 还原成 1–4 的均值；状态焦虑 stai6_sum 是 6 题之和，÷ 6 还原成均值；
#   其余来源列已经是均值（_mean）或单题得分（vas 0–100、fms 0–20），除数为 1。
QUESTIONNAIRE_CARD = [
    ("T0", [("特质焦虑", "T0_stait_sum", 20, 4, 1), ("自然联结", "T0_cns_mean", 1, 5, 1)]),
    *[(t, [("状态焦虑", f"{t}_stai6_sum", 6, 4, 1), ("压力 VAS", f"{t}_vas", 1, 100, 0), ("无聊", f"{t}_msbs_mean", 1, 7, 1)])
      for t in ("T1", "T2")],
    ("T3", [("状态焦虑", "T3_stai6_sum", 6, 4, 1), ("压力 VAS", "T3_vas", 1, 100, 0), ("无聊", "T3_msbs_mean", 1, 7, 1),
            ("注意困难", "T3_attention_mean", 1, 7, 1), ("迷恋", "T3_fascination_mean", 1, 7, 1), ("远离", "T3_away_mean", 1, 7, 1),
            ("意义", "T3_meaning_mean", 1, 7, 1), ("感知选择", "T3_imi_choice_mean", 1, 7, 1), ("晕动", "T3_fms", 1, 20, 0)]),
]


def load_card(cfg):
    """被试信息卡：组别、性别、年龄与各时间点问卷结果。读不到文件或被试时返回 has=False，不报错。只读。"""
    path = layer_dir(cfg["dataset"], "processed", "psycho") / "scores_wide.csv"
    empty = {"has": False, "who": "", "rows": []}
    if not path.is_file():
        return empty
    df = pd.read_csv(path)
    hit = df[df["subject"].astype(str) == cfg["subject"]] if "subject" in df.columns else df.iloc[0:0]
    if hit.empty:
        return empty
    row = hit.iloc[0]

    def num(c):
        v = row.get(c)
        return float(v) if c in row.index and pd.notna(v) else None

    def label(var, c):
        v = num(c)
        return None if v is None else settings.VALUE_LABELS.get(var, {}).get(int(v))
    age = num("A_age")
    who = " · ".join(x for x in (label("group", "group"), label("A_gender", "A_gender"), None if age is None else f"{age:.0f} 岁") if x)
    rows = []
    for tp, items in QUESTIONNAIRE_CARD:
        cells = []
        for name, c, div, top, nd in items:
            v = num(c)
            cells.append({"name": name, "text": "—" if v is None else f"{v / div:.{nd}f} / {top}"})
        rows.append({"tp": tp, "items": cells})
    return {"has": True, "who": who, "rows": rows}


def load_physio(cfg, tb, t_end):
    """同一被试的生理数据（processed/physio/sub-P###/merged/）换算到会话时间。读不到时返回"无生理数据"，不报错。
    会话时间 = t_unix − offset，offset = median(spacetime.t_device − spacetime.t_session)；只保留 [0, t_end] 内的部分。
    跳变不在这里算，由页面按当前阈值计算。只读。"""
    empty = {"has": False, "offset": None, "n_hr": 0, "n_rr": 0, "n_markers": 0,
             "hr": {"t": [], "bpm": []}, "rr": {"t": [], "ms": [], "seg": []}, "markers": {"t": [], "label": []}}
    folder = layer_dir(cfg["dataset"], "processed", "physio") / f"sub-{cfg['subject']}" / "merged"
    if not (folder / "hr.csv").is_file() and not (folder / "rr.csv").is_file():
        return empty
    st = tb["spacetime"]
    td = st[settings.column("spacetime", "t_device")].to_numpy(dtype=float, na_value=np.nan)
    ts = st[settings.column("spacetime", "t_session")].to_numpy(dtype=float, na_value=np.nan)
    diff = (td - ts)[np.isfinite(td - ts)]
    if not len(diff):
        return empty
    offset = float(np.median(diff))

    def read(name, value_col):
        p = folder / name
        if not p.is_file():
            return np.array([]), np.array([]), np.array([], dtype=int)
        df = pd.read_csv(p)
        if "t_unix" not in df.columns or value_col not in df.columns:
            return np.array([]), np.array([]), np.array([], dtype=int)
        tt = df["t_unix"].to_numpy(dtype=float) - offset
        vv = df[value_col].to_numpy(dtype=float)
        # 记录段号（part 列）：页面判定 RR 跳变时只与同一段内的前一个比较，与生理工具 03 一致
        sg = pd.factorize(df["part"])[0] if "part" in df.columns else np.zeros(len(df), dtype=int)
        keep = np.isfinite(tt) & np.isfinite(vv) & (tt >= 0) & (tt <= t_end)
        return tt[keep], vv[keep], sg[keep]
    ht, hv, _ = read("hr.csv", "bpm")
    rt, rv, rs = read("rr.csv", "ms")
    mt, ml = np.array([]), []
    mp = folder / "markers.csv"
    if mp.is_file():
        df = pd.read_csv(mp)
        if {"t_unix", "label"} <= set(df.columns):
            tt = df["t_unix"].to_numpy(dtype=float) - offset
            keep = np.isfinite(tt) & (tt >= 0) & (tt <= t_end)
            mt, ml = tt[keep], df["label"].astype(str).to_numpy()[keep].tolist()
    return {"has": bool(len(ht) or len(rt)), "offset": r(offset, 3), "n_hr": int(len(ht)), "n_rr": int(len(rt)), "n_markers": int(len(mt)),
            "hr": {"t": [r(v, 2) for v in ht], "bpm": [r(v, 1) for v in hv]},
            "rr": {"t": [r(v, 2) for v in rt], "ms": [r(v, 1) for v in rv], "seg": [int(v) for v in rs]},
            "markers": {"t": [r(v, 2) for v in mt], "label": ml}}


def build(cfg):
    settings.validate()
    folder = find(cfg["dataset"], "track", [cfg["subject"]], run=cfg["run"])[cfg["subject"]]
    tb = clean_legacy(load(cfg["dataset"], "track", cfg["subject"], run=cfg["run"], formatted=True))
    pose = Pose.from_tables(tb)
    tap_c = classify_taps(tb, pose)                 # 无位移点击等：与制表同一套计算
    drag_c = classify_drags(tb, pose, tap_c)        # 环视：与制表同一套计算
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
            taps.append({"no_move": bool(tap_c.no_move.iloc[i]), "moved": r(tap_c.moved_m.iloc[i], 2), "id": int(cols["touch_id"][i]), "t": r(tt[i], 3), "x": r(cols["cam_x"][i], 2), "z": r(cols["cam_z"][i], 2),
                         "hx": r(cols["hit_x"][i], 2), "hz": r(cols["hit_z"][i], 2), "intent": intent[i], "layer": layer[i],
                         "touched": bool(touched[i]), "block": btype[i], "reason": reason[i]})
    looks = []
    if tb["look"].attrs["present"] and len(tb["look"]):
        lt0, lt1, ye, yp, yd, pp = (col(tb, "look", f) for f in ("t_session_start", "t_session_end", "yaw_end", "yaw_path", "yaw_delta", "pitch_path"))
        lty = txt(tb, "look", "look_type")
        looks = [{"t0": r(lt0[i], 2), "t1": r(lt1[i], 2), "yaw_end": r(ye[i], 1), "yaw_path": r(yp[i], 1),
                  "yaw_delta": r(yd[i], 1), "pitch_path": r(pp[i], 1), "type": lty[i]} for i in range(len(lt0))]
    drags = [{"id": int(d.touch_id), "t0": r(d.t0, 2), "t1": r(d.t1, 2), "x": r(d.x, 2), "z": r(d.z, 2), "yaw_end": r(d.yaw_end, 1),
              "yaw": r(d.yaw_deg, 1), "pitch": r(d.pitch_deg, 1), "speed": r(d.yaw_deg / (d.t1 - d.t0) if d.t1 > d.t0 else 0.0, 1),
              "kind": "look" if d.is_look else "walking", "after_no_move": bool(d.after_no_move)} for d in drag_c.itertuples()]
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

    sp = {**settings.METRICS["track"]["stay_walk"]["parameters"], "still_step_m": cfg["still_step"], "min_stay_seconds": cfg["min_stay"]}
    stay_list = []
    for a, e in pauses(pose, sp):                   # 停留：与制表同一套计算
        t0, t1 = pose.t[a], pose.t[e]
        if t1 - t0 < cfg["min_stay"]:
            continue
        stay_list.append({"t0": r(t0, 2), "t1": r(t1, 2), "dur": r(t1 - t0, 1),
                          "x": r(pose.x[a:e + 1].mean(), 2), "z": r(pose.z[a:e + 1].mean(), 2),
                          "taps": int(((tap_t >= t0) & (tap_t <= t1)).sum()),
                          "touched": int(((touched_t >= t0) & (touched_t <= t1)).sum())})
    physio = load_physio(cfg, tb, duration)
    card = load_card(cfg)
    notes = [
        f"停留图层：相邻采样水平位移 ≤ {cfg['still_step']:g} m 算没动，连续没动 ≥ {cfg['min_stay']:g} s 画成一次停留，见《实验记录-埋点》10.1。",
        f"逗留：把相邻的停顿（不动片段，长短不限）串起来，从第一次停顿到最后一次停顿，所有采样到平均位置的距离不超过 R、持续不少于 T，记为一次；中间的小移动算在内，走进来、走出去的路不算。默认 T = {cfg['dwell_t']:g} s、R = {cfg['dwell_r']:g} m（{'global_settings 登记值，见《实验记录-埋点》10.2' if cfg['dwell_registered'] else '本次临时覆盖，非登记值'}），可在页面上调整。阈值暂定，待预实验数据重新评估。",
        "环视：拖动开始时没在移动的手动拖动（拖动开始前 0.3 s 内有移动的算行进中拖动，不计入），角度、速度不限，见《实验记录-埋点》10.12。悬停提示中标出受阻后环视（无位移点击之后、一直没走动），仅供观察。",
        "点击默认画在点击时被试所在的位置，可切换为命中位置；「点击 → 命中连线」连接两者。",
        "环视线段从环视开始时的位置出发，指向停稳后的朝向，长 1.6 m，只表示方向。",
        "空间结构来自 Unity 地理空间标注导出，" + f"导出于 {geo.get('exported_at')}（Unity 提交 {str(geo.get('unity_commit'))[:8]}）。",
        "区域、桥内停留时间按轨迹采样落在多边形内的时间累加（单步间隔超过 1 s 的按 1 s 计）。",
        "滚轮缩放，拖动平移，双击范围聚焦；颜色与图层开关保存在本机浏览器。",
        "生理数据（心率 HR、RR 间期）来自 processed/physio 的 merged/，按 iPad 与手机系统时间对齐：会话时间 = 生理时间戳 − offset，offset 取埋点中设备时间与会话时间之差的中位数。跳变按页面上的阈值实时判定，仅供观察。",
    ]
    data = {
        "meta": {"dataset": cfg["dataset"], "record": folder.name, "duration": r(duration, 2), "generated": now()[:16].replace("T", " "), "subject": cfg["subject"],
                 "notes": notes},
        "params": {"still_step_m": cfg["still_step"], "min_stay_s": cfg["min_stay"],
                   "dwell_min_s": cfg["dwell_t"], "dwell_radius_m": cfg["dwell_r"], "dwell_still_step_m": cfg["dwell_step"]},
        "geo": {"polygons": geo["polygons"], "air_walls": geo["air_walls"], "bounds": geo["bounds"]},
        "path": {"t": [r(v, 2) for v in t], "x": [r(v, 2) for v in x], "z": [r(v, 2) for v in z], "yaw": [r(v, 1) for v in yaw]},
        "card": card,
        "hr": physio["hr"], "rr": physio["rr"], "physio_markers": physio["markers"],
        "physio": {k: physio[k] for k in ("has", "offset", "n_hr", "n_rr", "n_markers")},
        "stays": stay_list, "taps": taps, "looks": looks, "drags": drags, "backsteps": backsteps, "events": events, "glitches": glitches,
    }
    return folder, data


def main():
    cfg = check(PARAMETERS)
    folder, data = build(cfg)
    dest = HERE.parent / "results" / "path_viewer"   # behavior/results/path_viewer/；只清空这个子文件夹，不动同级其他结果
    if dest.exists():
        retire_dir(dest)
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
    ph = data["physio"]
    print("问卷：" + (" ｜ ".join(f"{r['tp']}：" + " · ".join(f"{c['name']} {c['text']}" for c in r["items"]) for r in data["card"]["rows"]) if data["card"]["has"] else "无（需先运行 table_flows/psycho 的 01–03）"))
    print(f"数据：{cfg['dataset']}／{folder.name}")
    print(f"生理数据：" + (f"HR {ph['n_hr']} 条，RR {ph['n_rr']} 条，标记 {ph['n_markers']} 个，offset {ph['offset']} s" if ph["has"] else "无（需先运行 table_flows/physio 的 01、02）"))
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
    {"at": "2026-10-24T23:27:14+08:00", "action": "modified",
     "summary": "点击提示改为列出鼠标附近所有叠在一起的点击（原地连点时只显示最上面一次的问题），并显示目标距离与受阻原因。"},
    {"at": "2026-10-24T23:41:19+08:00", "action": "modified",
     "summary": "按 global_settings 登记的无位移点击口径给每次点击打标；红叉改为表示无位移点击，筛选「只看受阻」改为「只看无位移点击」。"},
    {"at": "2026-10-25T00:12:11+08:00", "action": "modified", "summary": "无位移点击口径加入没打中（intent = NoHit）。"},
    {"at": "2026-10-25T00:32:52+08:00", "action": "modified", "summary": "按候选的环视定义把每次拖动分为环视 / 行进中拖动 / 受阻后拖动，分层显示，供研究者对照检验。"},
    {"at": "2026-10-25T00:51:21+08:00", "action": "modified", "summary": "环视定义确定：受阻后拖动并入环视（提示中标出，仅供观察）；判定窗口改读 global_settings 登记值。"},
    {"at": "2026-11-04T18:00:00+08:00", "action": "modified",
     "summary": "加入生理面板：读取同一被试 processed/physio 的 merged/（hr、rr、markers），按 t_device 与 t_session 的 offset 换算为会话时间并嵌入页面；跳变由页面按阈值计算。"},
    {"at": "2026-11-04T20:00:00+08:00", "action": "modified",
     "summary": "左上角改为被试信息卡：组别、性别、年龄与各时间点问卷结果（读 processed/psycho/scores_wide.csv，对照表 QUESTIONNAIRE_CARD 只用于显示）。"},
]

if __name__ == "__main__":
    main()
