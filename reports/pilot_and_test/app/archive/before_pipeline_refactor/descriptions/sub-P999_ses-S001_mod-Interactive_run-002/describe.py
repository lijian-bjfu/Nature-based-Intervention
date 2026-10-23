"""对一个 APP 会话的原始数据做基本描述：数字摘要 + 三张图。
输出（summary.json、fig1–3）写在本脚本所在文件夹。
用法：python3 describe.py            # 默认描述本文件夹同名的会话（logging_test 数据集）
      python3 describe.py <数据集> <会话文件夹名>
"""
import os, sys, json, math
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))          # analysis/
from lib.paths import raw
from lib.app_io import read_session

PHASE = sys.argv[1] if len(sys.argv) > 2 else "logging_test"
SES = sys.argv[2] if len(sys.argv) > 2 else HERE.name
T = read_session(raw(PHASE, "app") / SES)
ses, st, tap, back, look, we, gl = [T[n] for n in
    ["session", "spacetime", "tap", "backstep", "look", "world_event", "tech_glitch"]]
HERE = str(HERE)

out = {}
dur = ses.t_device_end[0] - ses.t_device_start[0]
out["session_min"] = round(dur / 60, 2)

# ── 时空 ──
st["dt"] = st.t_session.diff()
st["step"] = np.hypot(st.cam_x.diff(), st.cam_z.diff())
st["speed"] = st.step / st.dt
moving = st.speed > 0.2          # 仅用于描述：> 0.2 m/s 视为在移动
out["spacetime"] = dict(
    rows=len(st), mean_dt=round(st.dt.mean(), 3), max_dt=round(st.dt.max(), 3),
    path_m=round(st.step.sum(), 1),
    moving_share=round(moving.mean(), 3),
    x_range=[round(st.cam_x.min(), 1), round(st.cam_x.max(), 1)],
    z_range=[round(st.cam_z.min(), 1), round(st.cam_z.max(), 1)],
    ground_range=[round(st.ground_y.min(), 1), round(st.ground_y.max(), 1)],
    eye_minus_ground=[round((st.cam_y - st.ground_y).min(), 2), round((st.cam_y - st.ground_y).max(), 2)],
    pitch_pct=[round(x, 1) for x in st.view_pitch.quantile([.05, .5, .95])])

# ── 点击 ──
out["tap"] = dict(
    n=len(tap), per_min=round(len(tap) / (dur / 60), 2),
    intent=tap.intent.value_counts().to_dict(),
    hit_layer=tap.hit_layer.value_counts().to_dict(),
    touched=int((tap.is_touched == True).sum()),
    touched_layers=tap[tap.is_touched == True].hit_layer.value_counts().to_dict(),
    block_type=tap.block_type.value_counts().to_dict(),
    block_reason=tap.block_reason.value_counts().to_dict())
out["backstep"] = back.to_dict("records")

# ── 环视 ──
look["dur"] = look.t_session_end - look.t_session_start
look["wobble"] = look.yaw_delta.abs() / look.yaw_path.replace(0, np.nan)
seg = look[look.look_type == "Drag"].groupby("touch_id").size()
out["look"] = {
    t: dict(n=int((look.look_type == t).sum()),
            dur_median=round(look[look.look_type == t].dur.median(), 2),
            yaw_path_median=round(look[look.look_type == t].yaw_path.median(), 1),
            yaw_path_max=round(look[look.look_type == t].yaw_path.max(), 1),
            pitch_path_median=round(look[look.look_type == t].pitch_path.median(), 1))
    for t in ["Drag", "Tap"]}
out["look"]["drags"] = int(len(seg))
out["look"]["drag_segments_dist"] = seg.value_counts().sort_index().to_dict()
out["look"]["drag_wobbly(|net|/path<0.5, path>5deg)"] = int(((look.look_type == "Drag") & (look.yaw_path > 5) & (look.wobble < .5)).sum())
out["look"]["look_time_share"] = round(look.dur.sum() / dur, 3)

out["world_event"] = we.to_dict("records")
out["tech_glitch"] = gl.to_dict("records")
json.dump(out, open(os.path.join(HERE, "summary.json"), "w"), ensure_ascii=False, indent=1, default=str)

# ── 图 1：平面图 ──
fig, ax = plt.subplots(figsize=(9, 9), dpi=90)
sc = ax.scatter(st.cam_x, st.cam_z, c=st.t_session / 60, s=2, cmap="viridis")
plt.colorbar(sc, ax=ax, fraction=.04, label="minute")
ok = tap[tap.block_type == "None"]
ax.scatter(ok.hit_x, ok.hit_z, marker="x", s=18, c="0.4", label="tap target (not blocked)")
colors = {"BarrierDenseSlope": "tab:green", "BarrierWater": "tab:blue", "TooSteep": "tab:orange",
          "StepUp": "tab:red", "DropTooHigh": "tab:purple", "NoGround": "k", "BarrierUnlabeled": "m"}
for r, g in tap[tap.block_type != "None"].groupby("block_reason"):
    ax.scatter(g.cam_x, g.cam_z, s=30, facecolors="none", edgecolors=colors.get(r, "r"), label="blocked: " + r)
t = tap[tap.is_touched == True]
ax.scatter(t.hit_x, t.hit_z, marker="*", s=160, c="gold", edgecolors="k", label="touched")
for _, e in we.iterrows():
    ax.annotate(e.action, (e.cam_x, e.cam_z), fontsize=8, color="crimson")
ax.set_aspect("equal"); ax.set_xlabel("x (m)"); ax.set_ylabel("z (m)")
ax.set_title(SES + " — trajectory (color = time)")
ax.legend(fontsize=7, loc="best")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "fig1_map.png")); plt.close(fig)

# ── 图 2：时间线（每分钟） ──
bins = np.arange(0, math.ceil(dur / 60) + 1)
mm = lambda s: np.histogram(s / 60, bins)[0]
dist_min = st.groupby((st.t_session // 60).astype(int)).step.sum().reindex(bins[:-1], fill_value=0)
fig, axs = plt.subplots(4, 1, figsize=(10, 9), dpi=90, sharex=True)
axs[0].bar(bins[:-1], dist_min.values, width=.8, color="tab:gray"); axs[0].set_ylabel("walked m")
axs[1].bar(bins[:-1], mm(tap.t_session), width=.8, label="taps")
axs[1].bar(bins[:-1], mm(tap[tap.block_type != "None"].t_session), width=.5, color="tab:red", label="blocked taps")
axs[1].legend(fontsize=8); axs[1].set_ylabel("taps")
axs[2].bar(bins[:-1] - .2, mm(look[look.look_type == "Drag"].t_session_start), width=.4, label="Drag segments")
axs[2].bar(bins[:-1] + .2, mm(look[look.look_type == "Tap"].t_session_start), width=.4, label="Tap turns")
axs[2].legend(fontsize=8); axs[2].set_ylabel("look")
yawsum = look.groupby((look.t_session_start // 60).astype(int)).yaw_path.sum().reindex(bins[:-1], fill_value=0)
axs[3].bar(bins[:-1], yawsum.values, width=.8, color="tab:olive"); axs[3].set_ylabel("yaw turned (deg)")
for _, e in we.iterrows():
    for a in axs: a.axvline(e.t_session / 60, color="crimson", lw=.8, ls="--")
axs[-1].set_xlabel("minute (bars start at the minute; red dashed = world events)")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "fig2_timeline.png")); plt.close(fig)

# ── 图 3：分布 ──
fig, axs = plt.subplots(1, 3, figsize=(13, 3.8), dpi=90)
axs[0].hist(st.speed.clip(0, 3).dropna(), bins=60); axs[0].set_title("speed (m/s, 0.1 s samples)")
for tname in ["Drag", "Tap"]:
    axs[1].hist(look[look.look_type == tname].dur, bins=30, alpha=.6, label=tname)
    axs[2].hist(look[look.look_type == tname].yaw_path, bins=30, alpha=.6, label=tname)
axs[1].set_title("look segment duration (s)"); axs[2].set_title("look segment yaw path (deg)")
axs[1].legend(); axs[2].legend()
fig.tight_layout(); fig.savefig(os.path.join(HERE, "fig3_distributions.png")); plt.close(fig)
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
