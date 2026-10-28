"""data_lab/track/processing/device_debug_20261027：把 10-27 真机测试的旧版调试日志，近似还原成规范的七张埋点表，
再用路径浏览页与正式指标计算（track_metrics）处理，看能还原多少。

背景：10-27 iPad 上装的是 10-17 导出的旧版本，没有正式埋点，只有调试日志（点击日志、声音日志、剧本事件日志）。
还原方法与每张表的可信程度见同目录 README.md。还原出的表是近似数据，只用于检验与观察，不进入任何正式分析。
"""

# ════════════════════════════════════════════════════════════════════
# ▼▼▼ 研究者只需要改这一段 PARAMETERS，改完保存，点右上角 Run ▼▼▼
# ════════════════════════════════════════════════════════════════════
# walk_speed_mps：重建轨迹时假定的行走速度（米/秒）。两个位置样本之间有位移时，假定被试从前一样本起以这个速度走过去、
#                 到了就停。0.78 来自研究者 run-004 的实测中位速度。
PARAMETERS = {
    "source": "data/pilot_and_test/test/raw/device_debug_20261027",
    "tap_log": "TapLogs/tap_20261027_182843.csv",
    "sound_log": "SoundLogs/sound_20261027_182843.tsv",
    "event_log": "EventLogs/event_20261027_182843.tsv",
    "session_start_local": "2026-10-27T18:28:43+08:00",   # 日志文件名上的开始时刻，作为 t_device 的近似零点
    "walk_speed_mps": 0.78,
    "freeze_threshold_s": 0.5,                            # 规范 tech_glitch：卡住超过 0.5 s 记 Freeze
}

# ════════════════════════════════════════════════════════════════════
# ▲▲▲ 以上是参数。以下是程序本身，日常使用不需要修改 ▲▲▲
# ════════════════════════════════════════════════════════════════════
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT/"analysis"), str(PROJECT/"analysis/tools"),
                str(PROJECT/"analysis/data_lab/track/description/behavior/path_viewer")]

import csv, json, shutil, importlib.metadata
from datetime import datetime
import numpy as np
import pandas as pd

import global_settings as settings
from track_io import write_table, read_session
from track_metrics import compute_record, SceneGeometry, SUMMARY_COLUMNS
from data_access import load_geo
from paths import ROOT, ANALYSIS, GEO_ANNOTATION
from artifacts import write_json, sha256
from run_records import now, run_id, git_state, record_sources, script_history
import path_viewer as pv

HERE = Path(__file__).resolve().parent
RECORD = "sub-P000_ses-S001_mod-Interactive_run-001"   # 还原记录的文件夹名（被试编号未知，记 0）
OUT_DATA = ROOT / "data/pilot_and_test/test/processed/track/data_lab/device_debug_20261027" / RECORD


def read_taplog(path):
    rows = [r for r in csv.reader(open(path, encoding="utf-8-sig")) if r and not r[0].startswith("#")]
    head = rows[0]
    d = pd.DataFrame([r[:len(head)] for r in rows[1:]], columns=head)
    for c in ["时刻", "上击后位移m", "相机X", "相机Y", "相机Z", "偏航", "俯仰", "命中X", "命中Y", "命中Z", "实走m"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def reconstruct(p):
    src = ROOT / p["source"]
    tap = read_taplog(src / p["tap_log"])
    snd = pd.read_csv(src / p["sound_log"], sep="\t", encoding="utf-8-sig")
    evt = pd.read_csv(src / p["event_log"], sep="\t", encoding="utf-8-sig")
    t0 = float(snd.loc[snd.event == "start", "time"].iloc[0])                 # 场景加载完成
    nf = evt[(evt.action == "not-fired") & (evt.camX != 0)]
    t1 = float(nf.time.iloc[0])                                               # 离开场景时补写 not-fired 的时刻
    snd = snd[(snd.time >= t0) & (snd.time <= t1)].copy()
    evt = evt[(evt.time >= t0) & (evt.time <= t1)].copy()
    dur = t1 - t0
    dev0 = datetime.fromisoformat(p["session_start_local"]).timestamp()
    tap["t"] = tap["时刻"] - t0; snd["t"] = snd.time - t0; evt["t"] = evt.time - t0

    # ── 点击日志逐行归类 ──
    # 旧版 StopOnLook 下，每次拖屏一开始就调 StopNow("look")，在点击日志里写一行"停下来"（在走）或"停下来·空停"（站着）。
    # 这些行是拖动，不是点击。"补发出手"是需走近/下蹲后才伸手的那次触摸，回填到原点击。"后退"是长按后退。
    tap["touched"] = tap["触碰"].str.contains("触碰", na=False)
    for i in tap.index[tap["意图"] == "补发出手"]:
        j = i - 1
        while tap.loc[j, "意图"] == "补发出手":
            j -= 1
        tap.loc[j, "touched"] = True
    tap = tap[tap["意图"] != "补发出手"].reset_index(drop=True)
    tap["touch_id"] = np.arange(1, len(tap) + 1)
    kind = np.select([tap["意图"].isin(["停下来", "停下来·空停"]), tap["意图"] == "后退"], ["drag", "back"], "tap")
    tap["kind"] = kind
    T, Bk, Dg = tap[kind == "tap"], tap[kind == "back"], tap[kind == "drag"]

    def block(df):
        b = df["路径受阻"] == "是"
        btype = np.where(~b, "NotBlocked", np.where(df["实走m"] <= 1e-3, "NoStart", "CutShort"))
        rs = df["受阻原因"].fillna("")
        reason = np.select([~b, rs.str.startswith("阻挡层"), rs.str.startswith("太陡"), rs.str.contains("迈不上"),
                            rs.str.contains("落差"), rs.str.contains("无地面")],
                           ["NotBlocked", "BarrierUnlabeled", "TooSteep", "StepUp", "DropTooHigh", "NoGround"], "NoGround")
        return btype, reason

    tb, tr = block(T)
    hit = T["命中"] == "是"
    tap_tbl = pd.DataFrame({
        "touch_id": T.touch_id, "t_session": T.t.round(3), "t_device": (dev0 + T.t).round(3),
        "cam_x": T["相机X"], "cam_y": T["相机Y"], "cam_z": T["相机Z"],
        "intent": np.where(~hit, "NoHit", T["意图"].map({"走过去": "WalkTo", "我想看": "LookAt"}).fillna("NoHit")),
        "hit_layer": np.where(hit, T["命中层"], "NoHit"),
        "hit_x": T["命中X"].where(hit), "hit_y": T["命中Y"].where(hit), "hit_z": T["命中Z"].where(hit),
        "is_touched": T.touched, "block_type": tb, "block_reason": tr})
    bb, br = block(Bk)
    back_tbl = pd.DataFrame({"touch_id": Bk.touch_id, "t_session": Bk.t.round(3), "t_device": (dev0 + Bk.t).round(3),
                             "cam_x": Bk["相机X"], "cam_y": Bk["相机Y"], "cam_z": Bk["相机Z"], "back_dist": Bk["实走m"],
                             "block_type": bb, "block_reason": br})

    # ── 位置与朝向样本：点击日志每行 + 声音日志每行（每条声音都记了当时的相机位置与左右朝向） ──
    S = pd.concat([tap[["t", "相机X", "相机Y", "相机Z", "偏航"]].set_axis(["t", "x", "y", "z", "yaw"], axis=1),
                   snd[["t", "camX", "camY", "camZ", "camYaw"]].set_axis(["t", "x", "y", "z", "yaw"], axis=1)])
    S = S.apply(pd.to_numeric, errors="coerce").dropna()
    S = S[(S.x != 0) | (S.z != 0)].sort_values("t").drop_duplicates("t").reset_index(drop=True)
    ts, xs, ys, zs, yws = (S[c].to_numpy() for c in ("t", "x", "y", "z", "yaw"))

    # 0.1 s 时空表：两样本间有位移时，从前一样本起以 walk_speed 走到后一样本、到了就停；朝向取最近的前一个样本
    tt = np.round(np.arange(0, dur, 0.1), 3)
    X = np.empty_like(tt); Z = np.empty_like(tt); Y = np.empty_like(tt); YW = np.empty_like(tt)
    k = 0; v = p["walk_speed_mps"]
    for i, ti in enumerate(tt):
        while k + 1 < len(ts) and ts[k + 1] <= ti:
            k += 1
        if ti < ts[0] or k + 1 >= len(ts):
            X[i], Y[i], Z[i] = xs[k], ys[k], zs[k]
        else:
            d = np.hypot(xs[k + 1] - xs[k], zs[k + 1] - zs[k])
            f = 0.0 if d <= 0.03 else min(1.0, (ti - ts[k]) / min(d / v, ts[k + 1] - ts[k]))
            X[i] = xs[k] + (xs[k + 1] - xs[k]) * f; Z[i] = zs[k] + (zs[k + 1] - zs[k]) * f; Y[i] = ys[k] + (ys[k + 1] - ys[k]) * f
        YW[i] = yws[k]
    st_tbl = pd.DataFrame({"t_session": tt, "t_device": (dev0 + tt).round(3), "cam_x": X.round(2), "cam_y": Y.round(2),
                           "cam_z": Z.round(2), "ground_y": np.nan, "view_yaw": YW.round(1), "view_pitch": np.nan})

    # ── 环视表：只能还原拖拽式。起点＝拖动开始那一行；终点取下一次触屏之前的最后一个朝向样本 ──
    starts = tap.t.to_numpy()
    look_rows = []
    for _, g in Dg.iterrows():
        nxt = starts[starts > g.t]; end = nxt[0] if len(nxt) else dur
        seg = S[(S.t >= g.t) & (S.t <= end)]
        yw = np.r_[g["偏航"], seg.yaw.to_numpy()]
        dy = (np.diff(yw) + 180) % 360 - 180
        te = float(seg.t.iloc[-1]) if len(seg) else float(g.t)
        look_rows.append({"touch_id": g.touch_id, "t_session_start": round(g.t, 3), "t_device_start": round(dev0 + g.t, 3),
                          "t_session_end": round(te, 3), "t_device_end": round(dev0 + te, 3),
                          "yaw_start": g["偏航"], "pitch_start": -g["俯仰"], "yaw_end": yw[-1], "pitch_end": np.nan,
                          "yaw_delta": round(float(dy.sum()), 1), "pitch_delta": np.nan,
                          "yaw_path": round(float(np.abs(dy).sum()), 1), "pitch_path": np.nan, "look_type": "Drag"})
    look_tbl = pd.DataFrame(look_rows)

    # ── 世界事件：只有剧本事件的 fired / not-fired；手惊飞常驻生物旧版不记 ──
    we = evt[evt.action.isin(["fired", "not-fired"])]
    we_tbl = pd.DataFrame({"t_session": we.t.round(3), "t_device": (dev0 + we.t).round(3), "event_name": we.event,
                           "action": we.action.map({"fired": "Fired", "not-fired": "NotFired"}),
                           "cam_x": we.camX, "cam_y": we.camY, "cam_z": we.camZ,
                           "detail": np.where(we.action == "not-fired", we.detail, "")})

    # ── 技术故障：声音日志的 hitch 行（volume 列为卡顿毫秒数）；加载那一下（t=0）不算 ──
    h = snd[(snd.event == "hitch") & (snd.t > 0)]
    h = h[h.volume / 1000 >= p["freeze_threshold_s"]]
    gl_tbl = pd.DataFrame({"t_session": h.t.round(3), "t_device": (dev0 + h.t).round(3), "status": "Freeze",
                           "duration": (h.volume / 1000).round(3)})

    sess = pd.DataFrame([{"subject": 0, "session": 1, "group": 1, "module": "Interactive",
                          "t_device_start": round(dev0, 3), "t_device_end": round(dev0 + dur, 3),
                          "app_commit": "reconstructed-from-debug-logs_build-20261017"}])
    tables = {"session": sess, "spacetime": st_tbl, "tap": tap_tbl, "backstep": back_tbl, "look": look_tbl,
              "world_event": we_tbl, "tech_glitch": gl_tbl}
    info = {"t0_game": t0, "t1_game": t1, "duration_s": dur, "position_samples": len(S),
            "sample_gap_median_s": float(np.median(np.diff(ts))), "sample_gap_max_s": float(np.diff(ts).max()),
            "drag_rows": len(Dg), "drag_while_walking": int((Dg["意图"] == "停下来").sum()),
            "all_hitches_ms": snd.loc[snd.event == "hitch", ["t", "volume"]].round(3).values.tolist()}
    return tables, info


def main():
    p = PARAMETERS
    tables, info = reconstruct(p)
    if OUT_DATA.exists():
        shutil.rmtree(OUT_DATA)
    for name in settings.TRACK_TABLES:
        write_table(OUT_DATA, name, tables[name])
    tb = read_session(OUT_DATA, formatted=True)          # 按规范读回：同时检查列名与取值都合规

    scene = SceneGeometry(load_geo())
    res = compute_record(tb, scene)

    dest = HERE / "results"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    pd.DataFrame([{"column": k, "label": SUMMARY_COLUMNS[k], "value": res.summary[k]} for k in SUMMARY_COLUMNS]) \
        .to_csv(dest / "metrics.csv", index=False, encoding="utf-8-sig")
    for name in ("dwells", "ap", "areas", "per_minute"):
        getattr(res, name).to_csv(dest / f"{name}.csv", index=False, encoding="utf-8-sig")

    # 路径浏览页：沿用 path_viewer 的页面与数据整理，只把取数换成这份还原记录
    pv.find = lambda *a, **k: {"P000": OUT_DATA}
    pv.load = lambda *a, **k: read_session(OUT_DATA, formatted=True)
    cfg = pv.check({**pv.PARAMETERS, "selection": {"dataset": "test", "subject": "P000", "run": None}})
    _, data = pv.build(cfg)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = pv.TEMPLATE.read_text(encoding="utf-8")
    (dest / "path_viewer.html").write_text(html.replace("/*__DATA__*/null", payload), encoding="utf-8")

    prov = dest / "_provenance"
    files = [ROOT / "global_settings.py"] + sorted((ANALYSIS / "tools").glob("*.py")) + [Path(__file__).resolve(), Path(pv.__file__), pv.TEMPLATE]
    hashes, copied = record_sources(ROOT, files, prov / "uncommitted_sources")
    write_json(prov / "manifest.json", {"experiment": "track/processing/device_debug_20261027", "run_id": run_id(), "run_at": now(),
                                        "parameters": p, "reconstructed_record": str(OUT_DATA.relative_to(ROOT)), "info": info,
                                        "geo_annotation": {"path": str(GEO_ANNOTATION), "sha256": sha256(GEO_ANNOTATION)},
                                        "git": git_state(ROOT, files), "script_sha256": hashes, "uncommitted_copied": copied,
                                        "script_history": script_history(Path(__file__).resolve()), "python_version": sys.version})
    print(json.dumps(info, ensure_ascii=False))
    for k in SUMMARY_COLUMNS:
        v = res.summary[k]
        print(f"{SUMMARY_COLUMNS[k]}：{round(v, 3) if isinstance(v, float) else v}")
    print(f"在浏览器中打开：{dest / 'path_viewer.html'}")


SCRIPT_HISTORY = [
    {"at": "2026-10-28T22:00:00+08:00", "action": "created",
     "summary": "把 10-27 真机测试的旧版调试日志（点击、声音、剧本事件）近似还原为规范七表，生成路径浏览页并按 track_metrics 计算第十节指标。"},
]

if __name__ == "__main__":
    main()
