#!/usr/bin/env python3
"""独立描述单次日志；仅读原始七表，不读取同目录其他描述。"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
analysis_dir = next(p for p in HERE.parents if (p / "lib" / "paths.py").is_file())
sys.path.insert(0, str(analysis_dir))
from lib.paths import ANALYSIS, raw
from lib.app_io import TABLES, read_session
import numpy as np
import pandas as pd

SESSION = "sub-P999_ses-S001_mod-Interactive_run-002"
LAYERS = ["Terrain", "Road", "Rock", "DeadWood", "Flower", "Creature",
          "TouchFoliage", "SweepFoliage", "TouchRigid", "WaterTouchSurface", "NoHit"]
BLOCKS = ["NotBlocked", "CutShort", "NoStart"]
REASONS = ["NotBlocked", "BarrierDenseSlope", "BarrierWater", "BarrierUnlabeled",
           "StepUp", "DropTooHigh", "TooSteep", "NoGround"]


def records(df):
    return json.loads(df.to_json(orient="records", force_ascii=False, double_precision=12))


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(name, value):
    (HERE / name).write_text(
        json.dumps(clean_json(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(s, levels=None):
    vc = s.value_counts(dropna=False)
    if levels is not None:
        return {level: int(vc.get(level, 0)) for level in levels}
    return {str(k): int(v) for k, v in vc.items()}


def md_table(df):
    def cell(v):
        if isinstance(v, (float, np.floating)):
            return f"{v:.3f}"
        return str(v).replace("|", "/").replace("\n", " ")
    return "\n".join(
        ["| " + " | ".join(map(str, df.columns)) + " |",
         "| " + " | ".join(["---"] * len(df.columns)) + " |"] +
        ["| " + " | ".join(cell(v) for v in row) + " |"
         for row in df.itertuples(index=False, name=None)])


def load_data():
    source = raw("logging_test", "app") / SESSION
    expected_out = ANALYSIS / "06_analysis" / "describe" / "app" / SESSION / "describe_v2"
    assert HERE == expected_out.resolve()
    for name in TABLES:
        if not (source / f"{name}.csv").is_file():
            raise FileNotFoundError(source / f"{name}.csv")
    original = read_session(source)
    d = {k: v.copy(deep=True) for k, v in original.items()}
    mapping = []
    for table, field, replacement in [
        ("tap", "intent", "NoHit"), ("tap", "hit_layer", "NoHit"),
        ("tap", "block_type", "NotBlocked"), ("tap", "block_reason", "NotBlocked"),
        ("backstep", "block_type", "NotBlocked"), ("backstep", "block_reason", "NotBlocked")
    ]:
        mask = d[table][field].eq("None")
        mapping.append({"table": table, "field": field, "from": "None",
                        "to": replacement, "n": int(mask.sum())})
        d[table].loc[mask, field] = replacement
    # app_io 本次推断为 bool；明确验证，防止未来字符串 FALSE 被 bool("FALSE") 误读。
    assert set(d["tap"].is_touched.unique()).issubset({True, False})
    return source, original, d, mapping


def calculate(d, original, mapping):
    session, sp, tap, back, look, world, glitch = (d[n] for n in TABLES)
    assert len(session) == 1
    meta = session.iloc[0]
    duration = float(meta.t_device_end - meta.t_device_start)
    assert duration > 0
    t = sp.t_session.to_numpy(float)
    dt = np.diff(t)
    ds = np.hypot(np.diff(sp.cam_x), np.diff(sp.cam_z))
    overlap = np.zeros(len(ds), dtype=bool)
    for g in glitch.itertuples():
        overlap |= (t[:-1] < g.t_session + g.duration) & (t[1:] > g.t_session)
    sorted_checks, clock_offsets = {}, {}
    for name, df in d.items():
        if name == "session" or df.empty:
            continue
        tc = "t_session_start" if name == "look" else "t_session"
        dc = "t_device_start" if name == "look" else "t_device"
        assert df[tc].is_monotonic_increasing, name
        assert df[tc].ge(0).all() and df[tc].le(duration + .002).all(), name
        sorted_checks[name] = True
        delta = df[dc] - df[tc] - meta.t_device_start
        clock_offsets[name] = {"min_s": delta.min(), "max_s": delta.max()}
    assert np.all(dt > 0)
    look = look.assign(duration_s=look.t_session_end - look.t_session_start)
    assert look.duration_s.ge(0).all()
    assert look.t_session_end.le(duration + .002).all()
    assert ((look.yaw_path + .11 >= look.yaw_delta.abs()) &
            (look.pitch_path + .11 >= look.pitch_delta.abs())).all()
    assert not tap.touch_id.duplicated().any()
    lt = look[look.look_type.eq("Tap")]
    assert lt.touch_id.isin(tap.touch_id).all()

    layers = pd.crosstab(tap.hit_layer, tap.is_touched).reindex(
        index=LAYERS, columns=[False, True], fill_value=0)
    layers.columns = ["is_touched_FALSE", "is_touched_TRUE"]
    layers["tap_n"] = layers.sum(axis=1)
    layers = layers.reset_index()
    reason_type = pd.crosstab(tap.block_reason, tap.block_type).reindex(
        index=REASONS, columns=BLOCKS, fill_value=0).reset_index()
    intent_type = pd.crosstab(tap.intent, tap.block_type).reindex(
        index=["NoHit", "WalkTo", "LookAt"], columns=BLOCKS, fill_value=0).reset_index()
    look_rows = []
    for kind, z in look.groupby("look_type", sort=True):
        look_rows.append({"look_type": kind, "segments_n": len(z),
            "distinct_touch_ids_n": z.touch_id.nunique(),
            "duration_sum_s": z.duration_s.sum(), "duration_median_s": z.duration_s.median(),
            "duration_min_s": z.duration_s.min(), "duration_max_s": z.duration_s.max(),
            "yaw_path_sum_deg": z.yaw_path.sum(), "pitch_path_sum_deg": z.pitch_path.sum()})
    look_stats = pd.DataFrame(look_rows)
    edges = np.r_[np.arange(0, duration, 60), duration]
    bin_rows = []
    for i, (start, end) in enumerate(zip(edges[:-1], edges[1:]), 1):
        z = tap[tap.t_session.ge(start) & tap.t_session.lt(end)]
        bin_rows.append({"bin": i, "start_s": start, "end_s": end,
            "observed_s": end-start, "tap_n": len(z),
            "is_touched_TRUE_n": int(z.is_touched.sum()),
            "NotBlocked_n": int(z.block_type.eq("NotBlocked").sum()),
            "CutShort_n": int(z.block_type.eq("CutShort").sum()),
            "NoStart_n": int(z.block_type.eq("NoStart").sum())})
    bins = pd.DataFrame(bin_rows)
    touched = tap[tap.is_touched].copy()
    touched.insert(0, "touch_label", [f"T{i}" for i in range(1, len(touched)+1)])

    ids_tap, ids_back = set(tap.touch_id), set(back.touch_id)
    ids_drag = set(look.loc[look.look_type.eq("Drag"), "touch_id"])
    ids_all = ids_tap | ids_back | set(look.touch_id)
    sampled_end_gap = duration-t[-1]
    endpoint_errors = {}
    for kind, z in look.groupby("look_type"):
        recorded = (z.yaw_delta + 180) % 360 - 180
        endpoint = (z.yaw_end-z.yaw_start+180) % 360 - 180
        error_yaw = ((recorded-endpoint+180) % 360-180).abs()
        error_pitch = (z.pitch_delta-(z.pitch_end-z.pitch_start)).abs()
        endpoint_errors[kind] = {"max_abs_yaw_difference_deg": error_yaw.max(),
                                "max_abs_pitch_difference_deg": error_pitch.max()}
    summary = {
        "scope": "single researcher/editor logging test; descriptive only; no prior descriptions read",
        "session": records(session)[0], "duration_s": duration, "duration_min": duration/60,
        "rows": {n: len(z) for n, z in d.items()},
        "legacy_value_mapping": mapping,
        "quality": {
            "missing_cells_by_field": {n: {c: int(v) for c,v in z.isna().sum().items() if v}
                                       for n,z in original.items()},
            "monotonic_time": sorted_checks,
            "spacetime_first_s": t[0], "spacetime_last_s": t[-1],
            "spacetime_first_gap_s": t[0], "spacetime_end_gap_s": sampled_end_gap,
            "spacetime_interval_s": {"min": dt.min(), "median": np.median(dt),
                "p95": np.quantile(dt,.95), "p99": np.quantile(dt,.99), "max": dt.max()},
            "clock_offset_device_minus_session_minus_device_start_s": clock_offsets,
            "touch_ids_observed_n": len(ids_all), "touch_id_max": max(ids_all),
            "touch_ids_missing_within_observed_range": sorted(set(range(1,max(ids_all)+1))-ids_all),
            "tap_backstep_shared_ids": sorted(ids_tap & ids_back),
            "tap_drag_shared_ids": sorted(ids_tap & ids_drag),
            "backstep_drag_shared_ids": sorted(ids_back & ids_drag),
            "Tap_look_without_tap_n": int((~lt.touch_id.isin(tap.touch_id)).sum()),
            "look_overlapping_segments_n": int((look.t_session_start.iloc[1:].to_numpy() <
                                                look.t_session_end.iloc[:-1].to_numpy()-.0011).sum()),
            "look_endpoint_vs_logged_delta": endpoint_errors,
            "technical_events": records(glitch)
        },
        "space": {
            "sampled_horizontal_path_m": ds.sum(),
            "horizontal_path_excluding_segments_overlapping_tech_glitch_m": ds[~overlap].sum(),
            "segments_overlapping_tech_glitch_n": int(overlap.sum()),
            "start_end_horizontal_displacement_m": float(np.hypot(
                sp.cam_x.iloc[-1]-sp.cam_x.iloc[0],sp.cam_z.iloc[-1]-sp.cam_z.iloc[0])),
            "start_position_xz": [sp.cam_x.iloc[0], sp.cam_z.iloc[0]],
            "end_position_xz": [sp.cam_x.iloc[-1], sp.cam_z.iloc[-1]],
            "ranges": {c: {"min": sp[c].min(), "max": sp[c].max()}
                       for c in ["cam_x","cam_z","ground_y","view_pitch"]},
            "method": "sum adjacent recorded horizontal positions, including same-position intervals as zero; no smoothing, interpolation, region assignment or coverage score"
        },
        "tap": {"intent": counts(tap.intent,["NoHit","WalkTo","LookAt"]),
            "hit_layer": counts(tap.hit_layer,LAYERS),
            "block_type": counts(tap.block_type,BLOCKS),
            "block_reason": counts(tap.block_reason,REASONS),
            "blocked_n": int(tap.block_type.ne("NotBlocked").sum()),
            "blocked_fraction_of_all_taps": float(tap.block_type.ne("NotBlocked").mean()),
            "is_touched_TRUE_n": int(tap.is_touched.sum()),
            "is_touched_TRUE_by_hit_layer": counts(touched.hit_layer,LAYERS),
            "touch_records": records(touched),
            "layers_x_touch": records(layers), "intent_x_block": records(intent_type),
            "reason_x_block": records(reason_type)},
        "look": records(look_stats),
        "backstep": records(back),
        "world_event": records(world), "time_bins": records(bins)
    }
    return summary, layers, reason_type, intent_type, look_stats, bins, touched, look


def debug_verification(root, d):
    if root is None:
        return {"used": False}
    # 仅指定的三个调试文件；CSV 有注释前导行、TSV 有不同分隔符，不能用固定 CSV 接口读取。
    paths = [root/"Tap"/"tap_20261023_104904.csv",
             root/"Event"/"event_20261023_104904.tsv",
             root/"Sound"/"sound_20261023_104904.tsv"]
    hashes = {str(p): sha(p) for p in paths}
    with paths[0].open(encoding="utf-8-sig", newline="") as f:
        debug_taps = list(csv.DictReader(line for line in f if not line.startswith("#")))
    with paths[1].open(encoding="utf-8-sig", newline="") as f:
        events = list(csv.DictReader(f, delimiter="\t"))
    with paths[2].open(encoding="utf-8-sig", newline="") as f:
        sounds = list(csv.DictReader(f, delimiter="\t"))
    resolved = [r for r in debug_taps if r["意图"] in ["走过去","我想看"]]
    assert len(resolved) == len(d["tap"])
    delta = []
    for dr, ar in zip(resolved, d["tap"].itertuples()):
        assert dr["命中层"] == ar.hit_layer
        for dk, ak in [("相机X","cam_x"),("相机Y","cam_y"),("相机Z","cam_z"),
                       ("命中X","hit_x"),("命中Y","hit_y"),("命中Z","hit_z")]:
            assert abs(float(dr[dk])-getattr(ar,ak)) < .011
        delta.append(float(dr["时刻"])-ar.t_session)
    touch_debug = [r for r in debug_taps if r["触碰"] == "★触碰"]
    touched = d["tap"][d["tap"].is_touched]
    assert len(touch_debug) == len(touched)
    touch_matches = []
    # 依据命中层及命中三维位置逐次对应；不能使用调试序号充当 touch_id。
    for dr, ar in zip(touch_debug, touched.itertuples()):
        assert dr["命中层"] == ar.hit_layer
        assert all(abs(float(dr[dk])-getattr(ar,ak)) < .011
                   for dk,ak in [("命中X","hit_x"),("命中Y","hit_y"),("命中Z","hit_z")])
        touch_matches.append({"touch_id": ar.touch_id, "debug_row_id": dr["序号"],
            "tap_t_session": ar.t_session, "debug_time": float(dr["时刻"]),
            "debug_intent": dr["意图"], "hit_layer": dr["命中层"]})
    event_matches = []
    for ar in d["world_event"].itertuples():
        target = "fired" if ar.action=="Fired" else "not-fired"
        matches = [r for r in events if r["event"]==ar.event_name and r["action"]==target]
        assert len(matches)==1
        dr=matches[0]
        assert abs(float(dr["camX"])-ar.cam_x)<.011 and abs(float(dr["camZ"])-ar.cam_z)<.011
        event_matches.append({"event_name":ar.event_name,"action":ar.action,
            "t_session":ar.t_session,"debug_time":float(dr["time"]),
            "debug_minus_session_s":float(dr["time"])-ar.t_session,
            "debug_detail":dr["detail"],"debug_source":dr["source"]})
    from collections import Counter
    return {"used": True, "source_sha256": hashes,
        "debug_tap_rows_n":len(debug_taps),"matched_resolved_taps_n":len(resolved),
        "resolved_tap_positions_and_layers_match":True,
        "debug_time_minus_t_session_min_max_s":[min(delta),max(delta)],
        "touch_matches":touch_matches,"world_event_matches":event_matches,
        "debug_event_action_counts":dict(Counter(r["action"] for r in events)),
        "bird_path_end_details":[r for r in events if r["action"]=="path-end"],
        "sound_technical_rows":[r for r in sounds if r["event"] in ["hitch","focus-lost","focus-back"]],
        "note":"Debug time uses old game-clock values; not directly t_session. No absolute alignment to a fixed offset assumed. Debug row id is not touch_id."}


def figures(d, layers, reason_type, bins, touched, look, duration):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize
    from matplotlib.font_manager import fontManager, FontProperties
    font = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
    if font.is_file():
        fontManager.addfont(str(font))
        plt.rcParams["font.family"] = FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({"font.size":10,"axes.unicode_minus":False,
        "axes.spines.top":False,"axes.spines.right":False,"savefig.dpi":180,
        "axes.titleweight":"bold"})
    sp,tap,world,glitch=d["spacetime"],d["tap"],d["world_event"],d["tech_glitch"]
    green,amber,red,blue="#22866B","#D69325","#C44545","#4169A2"
    fig,axs=plt.subplots(1,2,figsize=(15,8.8),layout="constrained")
    p=sp[["cam_x","cam_z"]].to_numpy()
    lc=LineCollection(np.stack([p[:-1],p[1:]],axis=1),cmap="viridis",
                      norm=Normalize(0,duration/60),linewidth=1.8)
    lc.set_array(sp.t_session.to_numpy()[:-1]/60)
    axs[0].add_collection(lc)
    fig.colorbar(lc,ax=axs[0],label="spacetime.t_session（分钟）",shrink=.75)
    for kind,col,mark in [("CutShort",amber,"o"),("NoStart",red,"x")]:
        z=tap[tap.block_type.eq(kind)]
        axs[0].scatter(z.cam_x,z.cam_z,c=col,marker=mark,s=34,alpha=.8,
                       label=f"tap.block_type={kind}（{len(z)}）",zorder=4)
    axs[0].scatter(p[0,0],p[0,1],marker="^",s=100,c="black",label="起点",zorder=6)
    axs[0].scatter(p[-1,0],p[-1,1],marker="s",s=65,c="white",edgecolors="black",label="终点",zorder=6)
    fired=world[world.action.eq("Fired")]
    for i,r in enumerate(fired.itertuples(),1):
        axs[0].scatter(r.cam_x,r.cam_z,marker="D",s=70,c="#B04CB8",zorder=5)
        axs[0].annotate(f"E{i}",(r.cam_x,r.cam_z),xytext=(6,7),textcoords="offset points")
    axs[0].set_title("A 轨迹与受阻时相机位置；E1/E2 为事件发生时的位置",loc="left",fontsize=11)
    axs[0].legend(loc="upper left",fontsize=8,framealpha=.9)
    colors=plt.get_cmap("tab10")
    axs[1].plot(p[:,0],p[:,1],color="#D5D9D8",lw=1.2,label="相机轨迹")
    observed=[k for k in LAYERS if tap.hit_layer.eq(k).any()]
    for i,k in enumerate(observed):
        z=tap[tap.hit_layer.eq(k)]
        axs[1].scatter(z.hit_x,z.hit_z,color=colors(i),s=28,alpha=.72,
                       label=f"{k}（{len(z)}）")
    for i,r in enumerate(touched.itertuples(),1):
        axs[1].plot([r.cam_x,r.hit_x],[r.cam_z,r.hit_z],color="black",lw=.8)
        axs[1].scatter(r.hit_x,r.hit_z,marker="*",s=160,c="white",edgecolors="black",zorder=7)
        offsets={1:(7,-12),2:(-29,14),3:(9,-17),4:(8,7),5:(8,-14),6:(8,8)}
        axs[1].annotate(f"T{i}",(r.hit_x,r.hit_z),xytext=offsets[i],
                       textcoords="offset points",fontsize=9,zorder=8,
                       arrowprops={"arrowstyle":"-","lw":.5})
    axs[1].set_title("B 点击命中点；星号 T1–T6 为最终摸到的点击",loc="left",fontsize=11)
    axs[1].legend(loc="upper left",fontsize=8,framealpha=.9)
    xmin=min(sp.cam_x.min(),tap.hit_x.min())-4
    xmax=max(sp.cam_x.max(),tap.hit_x.max())+4
    zmin=min(sp.cam_z.min(),tap.hit_z.min())-4
    zmax=max(sp.cam_z.max(),tap.hit_z.max())+4
    for ax in axs:
        ax.set(xlabel="世界 X（米）",ylabel="世界 Z（米）",xlim=(xmin,xmax),ylim=(zmin,zmax))
        ax.set_aspect("equal",adjustable="box"); ax.grid(alpha=.16)
    fig.suptitle("单次自由探索：空间分布",fontsize=17)
    fig.get_layout_engine().set(rect=(0,.05,1,.95))
    fig.text(.5,.012,"无场景底图或区域标注。命中点不代表到达点；相同位置的标记可能重叠。T 标号对应 touch_records.csv。",ha="center",fontsize=9)
    fig.savefig(HERE/"fig1_space.png"); plt.close(fig)

    fig,axs=plt.subplots(5,1,figsize=(15,13.8),sharex=True,
                        gridspec_kw={"height_ratios":[1.3,1.3,1.2,.8,1.3]},layout="constrained")
    time=sp.t_session.to_numpy()/60
    axs[0].plot(time,sp.cam_x,label="spacetime.cam_x",color=green,lw=1.2)
    axs[0].plot(time,sp.cam_z,label="spacetime.cam_z",color=blue,lw=1.2)
    axs[0].set(ylabel="位置（米）",title="A 相机水平位置"); axs[0].legend(loc="upper right",ncol=2,fontsize=9)
    # 不把 yaw 的 360°/0° 包络跳变画成一次真实转头。
    yaw=sp.view_yaw.to_numpy().copy()
    jumps=np.r_[False,np.abs(np.diff(yaw))>180]
    yaw[jumps]=np.nan
    axs[1].plot(time,yaw,color=blue,lw=.9,label="view_yaw")
    axs[1].plot(time,sp.view_pitch,color=green,lw=.9,label="view_pitch")
    axs[1].set(ylabel="朝向（度）",title="B 画面实际朝向；偏航跨 0° 处断线"); axs[1].legend(loc="upper right",ncol=2,fontsize=9)
    for y,kind,col in [(2,"NotBlocked",green),(1,"CutShort",amber),(0,"NoStart",red)]:
        z=tap[tap.block_type.eq(kind)]
        axs[2].scatter(z.t_session/60,np.full(len(z),y),s=20,c=col,marker="|")
    axs[2].scatter(touched.t_session/60,np.full(len(touched),3),s=90,c=green,marker="*")
    axs[2].set_yticks([0,1,2,3],["NoStart","CutShort","NotBlocked","is_touched=TRUE"])
    axs[2].set_ylim(-.5,3.6);axs[2].set_title("C 点击判定与最终触摸结果；星号时间仍是原点击时刻")
    for y,kind,col in [(1,"Drag",green),(0,"Tap",blue)]:
        z=look[look.look_type.eq(kind)]
        axs[3].broken_barh(list(zip(z.t_session_start/60,z.duration_s/60)),(y-.22,.44),facecolors=col)
    axs[3].set_yticks([0,1],["Tap 系统转向","Drag 拖动转向"])
    axs[3].set_ylim(-.5,1.5);axs[3].set_title("D look 记录的转动段；不等同于手指持续接触时间")
    width=bins.observed_s.to_numpy()/60
    left=bins.start_s.to_numpy()/60
    bottom=np.zeros(len(bins))
    for c,col in [("NotBlocked_n",green),("CutShort_n",amber),("NoStart_n",red)]:
        axs[4].bar(left,bins[c],width=width*.92,bottom=bottom,align="edge",color=col,label=c.removesuffix("_n"))
        bottom+=bins[c].to_numpy()
    axs[4].set(ylabel="点击次数",xlabel="t_session（分钟）",
               title=f"E 每 60 秒点击计数；最后一箱仅 {bins.observed_s.iloc[-1]:.3f} 秒")
    axs[4].legend(loc="upper right",ncol=3,fontsize=9)
    for ax in axs:
        for i,r in enumerate(fired.itertuples(),1):
            ax.axvline(r.t_session/60,color="#B04CB8",lw=.9,ls="--",alpha=.7)
        for g in glitch.itertuples():
            ax.axvspan(g.t_session/60,(g.t_session+g.duration)/60,color="gray",alpha=.35)
        ax.set_xlim(0,duration/60);ax.grid(axis="x",alpha=.15)
    for i,r in enumerate(fired.itertuples(),1):
        axs[0].annotate(f"E{i}",(r.t_session/60,axs[0].get_ylim()[1]),xytext=(3,-15),textcoords="offset points",color="#A043A6")
    axs[4].set_xticks(np.arange(0,15))
    fig.suptitle("单次自由探索：行为时间线",fontsize=17)
    fig.get_layout_engine().set(rect=(0,.035,1,.96))
    fig.text(.5,.008,"E1：鸟群 383.341 秒；E2：蝴蝶 572.511 秒。末尾后台记录 0.250 秒，未删除原始数据。",ha="center",fontsize=9)
    fig.savefig(HERE/"fig2_time.png");plt.close(fig)

    fig,axs=plt.subplots(2,2,figsize=(15,11),layout="constrained")
    ax=axs[0,0]; y=np.arange(len(layers))
    ax.barh(y,layers.is_touched_FALSE,color="#B5C5C0",label="is_touched=FALSE")
    ax.barh(y,layers.is_touched_TRUE,left=layers.is_touched_FALSE,color=green,label="is_touched=TRUE")
    for i,n in enumerate(layers.tap_n):
        ax.text(n+.6,i,str(n),va="center",fontsize=9)
    ax.set_yticks(y,layers.hit_layer);ax.invert_yaxis();ax.set_xlim(0,layers.tap_n.max()*1.15)
    ax.set(xlabel="tap 行数",title="A 命中层与最终触摸结果（包括零计数类别）")
    ax.legend(fontsize=8,loc="lower right")
    ax=axs[0,1]; r=reason_type[reason_type[BLOCKS].sum(axis=1).gt(0)]
    y=np.arange(len(r));left=np.zeros(len(r))
    for kind,col in zip(BLOCKS,[green,amber,red]):
        ax.barh(y,r[kind],left=left,color=col,label=kind)
        for yi,n,le in zip(y,r[kind],left):
            if n:ax.text(le+n/2,yi,str(n),ha="center",va="center",color="white",fontsize=9)
        left+=r[kind].to_numpy()
    ax.set_yticks(y,r.block_reason);ax.invert_yaxis()
    ax.set(xlabel="tap 行数",title="B 路径受阻原因与类型");ax.legend(fontsize=8,loc="lower right")
    ax=axs[1,0]; x=np.arange(2);w=.35
    for off,col,title,color in [(-w/2,"yaw_path","偏航累计",blue),(w/2,"pitch_path","俯仰累计",green)]:
        vals=[look.loc[look.look_type.eq(k),col].sum() for k in ["Drag","Tap"]]
        bars=ax.bar(x+off,vals,w,color=color,label=title)
        ax.bar_label(bars,fmt="%.1f",padding=4,fontsize=9)
    ax.set_xticks(x,["Drag（130 段）","Tap（114 段）"])
    ax.set(ylabel="累计转动量（度）",title="C look.yaw_path / pitch_path 按来源求和")
    ax.margins(y=.18);ax.legend(fontsize=9)
    ax=axs[1,1]
    for k,col in [("Drag",green),("Tap",blue)]:
        vals=np.sort(look.loc[look.look_type.eq(k),"duration_s"].to_numpy())
        ax.step(vals,np.arange(1,len(vals)+1)/len(vals),where="post",color=col,
                label=f"{k}，中位 {np.median(vals):.3f} 秒")
    ax.set(xlabel="一段转动的持续时间（秒）",ylabel="累计比例",title="D 转动段时长的经验累积分布",ylim=(0,1.05))
    ax.legend(fontsize=9);ax.grid(alpha=.15)
    fig.suptitle("单次自由探索：操作类别与转动描述",fontsize=17)
    fig.get_layout_engine().set(rect=(0,.04,1,.96))
    fig.text(.5,.01,"FALSE 不等于操作失败；LookAt 不等于触摸意图。转动累计角路程不解释为注意、投入或操作负担。",ha="center",fontsize=9)
    fig.savefig(HERE/"fig3_actions.png");plt.close(fig)


def report(s, layers, reason_type, intent_type, look_stats, bins, touched, debug):
    q=s["quality"];sp=s["space"];a=s["tap"]
    table_rows=pd.DataFrame([{"table":k,"rows":v} for k,v in s["rows"].items()])
    touch_cols=["touch_label","touch_id","t_session","hit_layer","cam_x","cam_z","hit_x","hit_z"]
    world=pd.DataFrame(s["world_event"])[["t_session","event_name","action","detail"]].fillna("")
    last=bins.iloc[-1]
    report=f"""# 单次自由探索的独立描述

本报告描述研究者在编辑器中的开发测试，不能代表正式被试或两组效果。数据为 {SESSION}。第一段未读取既有 describe.py、summary.json 或三张旧图；也未开展第二段对照。描述依据先写在 description_plan.md。

## 记录范围与可用性

session.t_device_end − session.t_device_start = **{s['duration_s']:.3f} 秒（{s['duration_min']:.3f} 分钟）**，有正常结束时间。spacetime.t_session 覆盖 {q['spacetime_first_s']:.3f}–{q['spacetime_last_s']:.3f} 秒，首尾分别与会话边界相差 {q['spacetime_first_gap_s']:.3f}、{q['spacetime_end_gap_s']:.3f} 秒。

{md_table(table_rows)}

spacetime 相邻采样间隔中位数 {q['spacetime_interval_s']['median']:.3f} 秒，95% 分位 {q['spacetime_interval_s']['p95']:.3f} 秒，最大 {q['spacetime_interval_s']['max']:.3f} 秒。各表记录时间递增；look 的开始不晚于结束，转动段之间没有重叠。除 Fired 行不适用的 world_event.detail 两个空值外，本次七表没有空单元格。

tech_glitch 只有末尾一行：t_session=817.419、status=Background、duration=0.250 秒；未记录 Freeze。这不代表编辑器全过程绝对没有卡顿，只表示正式实验表在其记录时段内没有 Freeze 行。保留原始记录，不据此整体排除会话。

历史字符串 None 在分析副本中映射为 NoHit 或 NotBlocked，原始文件未修改。本次 tap.intent、tap.hit_layer 没有 None/NoHit；tap.block_type 和 tap.block_reason 各有 77 个 None，backstep 两列各有 1 个。此映射不是缺失值填补。

三张操作表合并观察到 touch_id 1–252，没有缺号。tap 有 155 个不同序号；Drag 的 130 段对应 97 个序号；backstep 的序号 139 同时关联 Drag。因此表的行数不能直接相加当触屏次数，look 的段数也不是拖动次数。所有 Tap 类型转动都能找到对应 tap.touch_id。

spacetime 和 tap 的 t_device − t_session − session.t_device_start 大致在 −0.001 至 0.022 秒内；其余事件表按会话起点换算，为零。此处只核对本文件内的时钟一致性，没有手机/LSL 数据，不能检验跨设备同步。

## 实际接触了什么

155 次点击中，tap.intent 为 WalkTo 72 次、LookAt 83 次；均有命中，没有 NoHit。LookAt 是系统判定类别，不能逐次解读为被试明确想触摸。命中 Terrain/Road 共 104 次；其他层共 51 次。命中与最终触摸结果如下：

{md_table(layers)}

**tap.is_touched=TRUE 共 6 次：WaterTouchSurface 4 次、SweepFoliage 1 次、Creature 1 次。** TouchFoliage 命中 4 次，均未记录最终摸到；TouchRigid 没有命中。149 次 FALSE 包含大量导航、走近观察等点击，不能当成 149 次触摸失败，也不将 6/155 称作触摸成功率。

{md_table(touched[touch_cols])}

表中 t_session 是原点击判定时刻，非补发出手时间。第一次最终摸到的关联点击为 18.702 秒；之后依次为 334.958、349.095、480.293、544.283、571.075 秒。这些记录证明系统执行了触摸，不证明注意或喜爱程度。

world_event 记录两个 Fired 和两个 NotFired：

{md_table(world)}

383.341 秒鸟群事件发生，572.511 秒手触发蝴蝶事件发生。另一只蝴蝶的触发者未进入范围（NeverEntered）；另一组鸟虽进入过触发范围，但视线条件未满足（NoSight）。这些是系统触发结论；NoSight 不等于“被试从未看见鸟所在方向”。HandStartle 行为零，但这不能解释为没有惊飞蝴蝶：手触发的剧本蝴蝶在本次记作 Fired，HandStartle 对应的是常驻停落生物。

## 接触发生在怎样的操作过程中

tap.block_type 有 NotBlocked 77 次、CutShort 46 次、NoStart 32 次。受路径限制的点击共 **78/155（{100*a['blocked_fraction_of_all_taps']:.1f}%）**。CutShort 表示有一部分路径获准，不能与 NoStart 混为“完全失败”；按设计停在目标前方也不算路径受阻。

{md_table(reason_type.loc[reason_type[BLOCKS].sum(axis=1).gt(0)])}

三类实际出现的受阻原因是 BarrierWater 31 次、BarrierDenseSlope 24 次、TooSteep 23 次。WalkTo 与 LookAt 都出现受阻：

{md_table(intent_type)}

受阻并非只在开头出现：0–60 秒为 13/20 次，360–420 秒为 11/16 次，720–780 秒为 14/20 次。这里只描述这些时间窗的记录，不据此认定是在学习、找路或挫败。图 1A 显示的是受阻点击发生时的相机位置，不是墙体或路径阻断点。

look 记录了 Drag 130 段和 Tap 114 段，前者包含拖动后的惯性，后者包含点击驱动的身体转向、俯仰跟随等。它们应分开描述：

{md_table(look_stats)}

持续时间按 look.t_session_end − look.t_session_start 求和；角路程直接累计 look.yaw_path/pitch_path。累计角路程不能当作净转圈数或努力程度。记录器的分段和停稳机制使“起止朝向相减”与已记录净量可有小差异；本次偏航最大 0.3°、俯仰最大 0.4°，未擅自用端点覆盖原列，也未将这些差值等同于新的行为。

backstep 仅一条：touch_id=139，t_session=438.854 秒，back_dist=1.00 米，未受阻。距离是 backstep.back_dist 的原始值，不用轨迹重建后冒充该字段。

## 时间与空间分布

相邻 spacetime.cam_x/cam_z 采样点连接的水平折线长约 **{sp['sampled_horizontal_path_m']:.2f} 米**，不包含相机俯仰或蹲起造成的竖直变化，不代表体力消耗或精确步行里程。与技术异常重叠的采样段为 {sp['segments_overlapping_tech_glitch_n']} 段，剔除这些段后的水平折线长仍为 {sp['horizontal_path_excluding_segments_overlapping_tech_glitch_m']:.2f} 米。

图 1 与图 2 显示，前段向较小 X/Z 的方向推进，中段沿较低 Z 的位置向较大 X 返回，后段又走到较大 Z 的位置，最后回到起点附近。这是对路线形状的描述，不是对探索意图的判断。

轨迹起点为 X/Z=56.23/67.75 米，终点为 55.27/65.62 米，二者相距 {sp['start_end_horizontal_displacement_m']:.2f} 米。cam_x 范围 22.01–65.73 米，cam_z 为 28.17–82.97 米，ground_y 为 0.75–4.85 米。图中保留空间关系；这些范围不用于计算场地覆盖率。没有区域多边形或景点圆，未推定访问了哪些区域、景点，也未把返回附近解释为迷路。

固定 60 秒分箱仅用于展示原始事件分布。最后一箱为 780–{s['duration_s']:.3f} 秒，只有 {last.observed_s:.3f} 秒，不能把其 4 次点击当作完整一分钟的次数作直接比较。

{md_table(bins)}

![空间分布](fig1_space.png)

![行为时间线](fig2_time.png)

![操作类别与转动](fig3_actions.png)

## 调试日志核对与解释边界

指定 Tap 调试日志有 258 行，其中 155 行为走过去/我想看，命中层、相机位置和命中位置逐行与 tap 表吻合；六条实际触碰也按命中层和三维命中位置对应一致。五条触碰在调试表中另写为补发出手，因此不能把调试行号直接当作 touch_id，或只看原点击调试行判断是否触碰。

四条世界事件的事件名、发生/未发生结论和相机位置均与 Event 调试表对应。Event 的 source 表明 bird_r3-r2 由 Observer 触发、R1-2_butterfly 由 Hand 触发。鸟群 path-end 的调试 detail 另记画面内可见 13.2 秒；这是调试可见性估计，不在 world_event 中，不能写成已测得“注意了 13.2 秒”，也不纳入本次正式表摘要。

Sound 在启动附近有两条 hitch，在退出附近有一条 focus-lost；tech_glitch 在末尾记 Background。调试表使用旧游戏时钟，时间值约比 t_session 大 100.2 秒，且并非严格固定偏移，不能直接按同名时间或固定常数强行连接，也不能将启动调试 hitch 搬成正式会话里的 Freeze。

本次最清楚的事实是：接近 13.6 分钟内有较长的空间移动和多段主动拖动转向，最终触摸只有六次，两个剧本事件发生；路径限制在多个时段出现。行为不能单独解释兴趣、无聊、注意、迷路或挫败，也不能证明某种场景设计优劣。研究者自由测试的目的与正式被试不同，本报告不做总体推断，不设计指标。

## 复现与文件

describe.py 通过 lib.paths 定位、lib.app_io 读取七张实验表。summary.json 保存完整数字、映射、检查和原始文件 SHA-256；debug_verification.json 保存核对口径。table_layers.csv、table_block_reasons.csv、table_intent_blocks.csv、table_look.csv、table_time_bins.csv、touch_records.csv、world_events.csv 是本次描述的辅助明细。所有原始文件在运行前后核对 SHA-256，不修改规范、共用读取库或旧描述。

运行：在本目录执行 python3 describe.py --debug-log-root <Unity 的 Interaction/Logs~ 目录>。脚本要求同时核对指定调试日志。脚本只生成本目录列出的描述文件，不读取父目录其他描述。运行环境详见 summary.json。
"""
    (HERE/"report.md").write_text(report,encoding="utf-8")


def independent_check(d, summary):
    """以逐行循环、Counter、Decimal、math.fsum 复核关键汇总，不重复向量化分组。"""
    from collections import Counter
    from decimal import Decimal
    row = d["session"].iloc[0]
    exact_duration = Decimal(str(row.t_device_end)) - Decimal(str(row.t_device_start))
    taps = list(d["tap"].itertuples(index=False))
    block = Counter(r.block_type for r in taps)
    touched = Counter(r.hit_layer for r in taps if r.is_touched)
    reasons = Counter(r.block_reason for r in taps)
    assert sum(block.values()) == summary["rows"]["tap"]
    assert sum(v for k, v in block.items() if k != "NotBlocked") == summary["tap"]["blocked_n"]
    assert sum(touched.values()) == summary["tap"]["is_touched_TRUE_n"]
    assert {k: touched.get(k, 0) for k in LAYERS} == summary["tap"]["is_touched_TRUE_by_hit_layer"]
    assert dict(reasons) == {k:v for k,v in summary["tap"]["block_reason"].items() if v}
    assert abs(float(exact_duration) - summary["duration_s"]) < 0.000001
    coords = list(d["spacetime"][["cam_x", "cam_z"]].itertuples(index=False, name=None))
    distance = math.fsum(math.dist(a, b) for a,b in zip(coords[:-1], coords[1:]))
    assert abs(distance-summary["space"]["sampled_horizontal_path_m"]) < 1e-9
    for bin_row in summary["time_bins"]:
        members = [r for r in taps if bin_row["start_s"] <= r.t_session < bin_row["end_s"]]
        assert len(members) == bin_row["tap_n"]
        assert sum(r.is_touched for r in members) == bin_row["is_touched_TRUE_n"]
    for group in summary["look"]:
        rows = [r for r in d["look"].itertuples(index=False) if r.look_type == group["look_type"]]
        seconds = math.fsum(r.t_session_end-r.t_session_start for r in rows)
        assert abs(seconds-group["duration_sum_s"]) < 1e-9
    return {"passed": True, "exact_session_duration_s": str(exact_duration),
        "horizontal_path_m": distance, "tap_block_counts": dict(block),
        "touched_by_layer": dict(touched),
        "checks": ["Decimal session duration", "row-wise tap and touched counts",
                   "math.fsum/math.dist horizontal path", "row-wise time bins",
                   "math.fsum look duration by source"]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug-log-root",type=Path,required=True)
    args=parser.parse_args()
    source,original,d,mapping=load_data()
    raw_hash={str(source/f"{n}.csv"):sha(source/f"{n}.csv") for n in TABLES}
    s,layers,reason_type,intent_type,look_stats,bins,touched,look=calculate(d,original,mapping)
    debug=debug_verification(args.debug_log_root,d)
    s["provenance"]={"raw_directory":str(source),"raw_sha256":raw_hash,
        "script_sha256":sha(Path(__file__)), "python_executable":sys.executable,
        "python_version":sys.version, "packages":{m:importlib.metadata.version(m) for m in ["numpy","pandas","matplotlib"]},
        "debug_used":debug["used"]}
    figures(d,layers,reason_type,bins,touched,look,s["duration_s"])
    for name,df in [("table_layers",layers),("table_block_reasons",reason_type),
        ("table_intent_blocks",intent_type),("table_look",look_stats),
        ("table_time_bins",bins),("touch_records",touched),("world_events",d["world_event"])]:
        df.to_csv(HERE/f"{name}.csv",index=False,float_format="%.6f")
    assert all(sha(Path(p))==h for p,h in raw_hash.items())
    if debug["used"]:
        assert all(sha(Path(p))==h for p,h in debug["source_sha256"].items())
    s["independent_verification"] = independent_check(d, s)
    s["provenance"]["raw_files_unchanged_after_run"]=True
    write_json("summary.json",s)
    write_json("debug_verification.json",debug)
    report(s,layers,reason_type,intent_type,look_stats,bins,touched,debug)
    print(json.dumps({"duration_s":s["duration_s"],"rows":s["rows"],"touched_n":s["tap"]["is_touched_TRUE_n"],
                      "blocked_n":s["tap"]["blocked_n"],"path_xz_m":s["space"]["sampled_horizontal_path_m"],
                      "output":str(HERE)},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
