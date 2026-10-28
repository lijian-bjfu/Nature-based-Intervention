"""埋点指标的正式计算：口径与参数全部来自 global_settings.METRICS["track"]，定义见《研究思路/实验记录-埋点.md》第十节。

table_flows/track 与 data_lab（如路径浏览页）都从这里取计算结果，不各写一套。改口径先改规范与 METRICS，再改这里。

输入是一名被试的七张埋点表（data_access.load(..., formatted=True) 的结果，经 clean_legacy 处理）和地理空间标注
（data_access.load_geo()）。只用到水平坐标 x、z。

    from track_metrics import compute_record, SceneGeometry
    scene = SceneGeometry(load_geo())          # 场景只算一次，所有被试共用
    result = compute_record(tables, scene)     # result.summary：一行指标；result.dwells 等：明细表
"""
from dataclasses import dataclass, field
from collections import deque

import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath

import global_settings as settings

M = settings.METRICS["track"]
RASTER_M = 0.1            # 行动范围与可达范围的栅格边长（米）；只影响面积计算的精度
WALL_HALF_WIDTH_M = 0.2   # 计算可达范围时空气墙折线的半宽（米）；只用于挡住"灌水"，不改变墙的位置


# ───────────────────────── 基础 ─────────────────────────
def clean_legacy(tables):
    """把早期数据中的历史取值换成现行取值（如 None → NoHit / NotBlocked），规则来自 TRACK_LEGACY_VALUES。原表不改。"""
    out = {}
    for name, frame in tables.items():
        f = frame.copy()
        f.attrs.update(frame.attrs)
        for fld, mapping in settings.TRACK_LEGACY_VALUES.get(name, {}).items():
            col = settings.column(name, fld)
            if col in f:
                f[col] = f[col].replace(mapping)
        out[name] = f
    return out


def _col(tables, table, fld, dtype=float):
    return tables[table][settings.column(table, fld)].to_numpy(dtype=dtype, na_value=np.nan)


def _txt(tables, table, fld):
    return tables[table][settings.column(table, fld)].astype("string").fillna("").to_numpy()


def _present(tables, table):
    return bool(tables[table].attrs.get("present", True)) and len(tables[table]) > 0


@dataclass
class Pose:
    t: np.ndarray
    x: np.ndarray
    z: np.ndarray
    step: np.ndarray      # 相邻采样水平位移，长度 n-1
    cum: np.ndarray       # 累计水平路程，长度 n

    @classmethod
    def from_tables(cls, tables):
        t, x, z = (_col(tables, "spacetime", f) for f in ("t_session", "cam_x", "cam_z"))
        ok = np.isfinite(t) & np.isfinite(x) & np.isfinite(z)
        t, x, z = t[ok], x[ok], z[ok]
        if len(t) < 2 or (np.diff(t) <= 0).any():
            raise ValueError("spacetime 缺少可用的时间与位置，或 t_session 不是严格递增")
        step = np.hypot(np.diff(x), np.diff(z))
        return cls(t, x, z, step, np.r_[0.0, np.cumsum(step)])

    def path_between(self, a, b):
        return np.interp(b, self.t, self.cum) - np.interp(a, self.t, self.cum)

    def moving_before(self, a, window, eps):
        tm = self.t[1:]
        return bool((self.step[(tm > a - window) & (tm <= a + 0.05)] > eps).any())


def _dist_to_polygon(px, pz, poly):
    """一组点到多边形的水平距离；在多边形内为 0。"""
    px, pz = np.asarray(px, float), np.asarray(pz, float)
    P = np.asarray(poly, float); A = P; B = np.roll(P, -1, axis=0)
    d = np.full(px.shape, np.inf)
    for (x0, z0), (x1, z1) in zip(A, B):
        dx, dz = x1 - x0, z1 - z0
        L2 = dx * dx + dz * dz
        u = np.clip(((px - x0) * dx + (pz - z0) * dz) / L2, 0, 1) if L2 > 0 else np.zeros_like(px)
        d = np.minimum(d, np.hypot(px - (x0 + u * dx), pz - (z0 + u * dz)))
    inside = MplPath(P).contains_points(np.c_[px, pz]) if len(px) else np.zeros(0, bool)
    return np.where(inside, 0.0, d)


# ───────────────────────── 场景几何（只算一次） ─────────────────────────
class SceneGeometry:
    """区域、桥、景点多边形与空气墙；场景可达范围（行动范围占比的分母，10.3）。"""

    def __init__(self, geo, spawn_xz=None):
        self.geo = geo
        self.polygons = geo["polygons"]
        self.areas = [p for p in self.polygons if p["kind"] in ("region", "bridge")]
        self.aps = [p for p in self.polygons if p["kind"] == "attractive_point"]
        b = geo["bounds"]
        self.gx = np.arange(b["x_min"] - 1, b["x_max"] + 1, RASTER_M)
        self.gz = np.arange(b["z_min"] - 1, b["z_max"] + 1, RASTER_M)
        GX, GZ = np.meshgrid(self.gx, self.gz)
        self.GX, self.GZ = GX, GZ
        pts = np.c_[GX.ravel(), GZ.ravel()]
        self.area_masks = {p["id"]: MplPath(p["points"]).contains_points(pts).reshape(GX.shape) for p in self.areas}
        self.spawn_xz = spawn_xz
        self.walkable = self._walkable()

    def _cell(self, x, z):
        return int(round((z - self.gz[0]) / RASTER_M)), int(round((x - self.gx[0]) / RASTER_M))

    def _walkable(self):
        """从各桥中心（以及给定的出生点）出发，不穿过空气墙、不越出区域与桥的多边形能到达的栅格。"""
        inside = np.zeros(self.GX.shape, bool)
        for m in self.area_masks.values():
            inside |= m
        wall = np.zeros(self.GX.shape, bool); r = int(np.ceil(WALL_HALF_WIDTH_M / RASTER_M))
        for w in self.geo["air_walls"]:
            P = np.asarray(w["points"] + ([w["points"][0]] if w["closed"] else []), float)
            for (x0, z0), (x1, z1) in zip(P[:-1], P[1:]):
                for s in np.linspace(0, 1, max(2, int(np.hypot(x1 - x0, z1 - z0) / (RASTER_M / 2)))):
                    j, i = self._cell(x0 + (x1 - x0) * s, z0 + (z1 - z0) * s)
                    wall[max(0, j - r):j + r + 1, max(0, i - r):i + r + 1] = True
        free = inside & ~wall
        seeds = [np.mean(p["points"], axis=0) for p in self.areas if p["kind"] == "bridge"]
        if self.spawn_xz is not None:
            seeds.append(self.spawn_xz)
        seen = np.zeros(free.shape, bool); q = deque()
        for sx, sz in seeds:
            j, i = self._cell(sx, sz)
            if 0 <= j < free.shape[0] and 0 <= i < free.shape[1] and free[j, i]:
                seen[j, i] = True; q.append((j, i))
        H, W = free.shape
        while q:
            j, i = q.popleft()
            for a, c in ((j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)):
                if 0 <= a < H and 0 <= c < W and free[a, c] and not seen[a, c]:
                    seen[a, c] = True; q.append((a, c))
        return seen

    @property
    def walkable_m2(self):
        return float(self.walkable.sum() * RASTER_M ** 2)

    def brush(self, x, z, radius):
        """沿一串位置以 radius 涂抹，返回栅格掩码。"""
        m = np.zeros(self.GX.shape, bool)
        for px, pz in zip(x, z):
            i0 = np.searchsorted(self.gx, px - radius); i1 = np.searchsorted(self.gx, px + radius)
            j0 = np.searchsorted(self.gz, pz - radius); j1 = np.searchsorted(self.gz, pz + radius)
            if i1 <= i0 or j1 <= j0:
                continue
            m[j0:j1, i0:i1] |= (self.GX[j0:j1, i0:i1] - px) ** 2 + (self.GZ[j0:j1, i0:i1] - pz) ** 2 <= radius * radius
        return m


# ───────────────────────── 10.1 停留与行走 ─────────────────────────
def pauses(pose, p=None):
    """停顿：相邻采样位移 ≤ still_step_m 且单步间隔 ≤ max_gap_s 的连续一段。返回 [(起始采样, 结束采样)]。"""
    p = p or M["stay_walk"]["parameters"]
    still = (pose.step <= p["still_step_m"]) & (np.diff(pose.t) <= p["max_gap_s"])
    out, s = [], None
    for k in range(1, len(pose.t)):
        if still[k - 1]:
            if s is None:
                s = k - 1
        elif s is not None:
            out.append((s, k - 1)); s = None
    if s is not None:
        out.append((s, len(pose.t) - 1))
    return out


def stay_walk(pose):
    p = M["stay_walk"]["parameters"]
    stays = [(a, e) for a, e in pauses(pose, p) if pose.t[e] - pose.t[a] >= p["min_stay_seconds"]]
    in_stay = np.zeros(len(pose.step), bool)
    for a, e in stays:
        in_stay[a:e] = True
    dt = np.diff(pose.t)
    return stays, {"stay_n": len(stays), "stay_s": float(dt[in_stay].sum()), "walk_s": float(dt[~in_stay].sum()),
                   "walk_path_m": float(pose.step[~in_stay].sum())}


# ───────────────────────── 10.2 逗留 ─────────────────────────
def dwells(pose):
    """把相邻停顿串起来；从第一次停顿到最后一次停顿都在半径 R 内、持续 ≥ T 记一次逗留。与路径浏览页算法一致。"""
    p = M["dwell"]["parameters"]
    segs = pauses(pose, {"still_step_m": p["still_step_m"], "max_gap_s": M["stay_walk"]["parameters"]["max_gap_s"]})
    def extent(a, e):
        cx, cz = pose.x[a:e + 1].mean(), pose.z[a:e + 1].mean()
        return cx, cz, float(np.hypot(pose.x[a:e + 1] - cx, pose.z[a:e + 1] - cz).max())
    out, g = [], 0
    while g < len(segs):
        h = g
        while h + 1 < len(segs) and extent(segs[g][0], segs[h + 1][1])[2] <= p["radius_m"]:
            h += 1
        a, e = segs[g][0], segs[h][1]
        if pose.t[e] - pose.t[a] >= p["min_seconds"]:
            cx, cz, r = extent(a, e)
            out.append({"i0": a, "i1": e, "t0": float(pose.t[a]), "t1": float(pose.t[e]), "duration_s": float(pose.t[e] - pose.t[a]),
                        "x": float(cx), "z": float(cz), "radius_m": r, "pauses": h - g + 1})
        g = h + 1
    return out


# ───────────────────────── 点击类 ─────────────────────────
def classify_taps(tables, pose):
    """每次点击：点后移动距离、是否无位移点击（10.5）、是否 approach（10.7）、是否触摸（10.8）。"""
    if not _present(tables, "tap"):
        return pd.DataFrame(columns=["touch_id", "t", "moved_m", "no_move", "approach", "touched"])
    nm = M["no_move_tap"]["parameters"]; al = set(M["approach"]["parameters"]["approach_layers"])
    t = _col(tables, "tap", "t_session")
    intent, layer, btype = (_txt(tables, "tap", f) for f in ("intent", "hit_layer", "block_type"))
    touched = tables["tap"][settings.column("tap", "is_touched")].eq(True).fillna(False).to_numpy()
    lock_col = settings.column("tap", "touch_locked")
    locked = (tables["tap"][lock_col].eq(True).fillna(False).to_numpy() if lock_col in tables["tap"].columns
              else np.zeros(len(t), dtype=bool))   # 触摸锁定中的点击：APP 按规则不响应，不计无位移、不计 approach
    nxt = np.r_[t[1:], pose.t[-1]]
    moved = pose.path_between(t, np.minimum(nxt, t + nm["window_seconds"]))
    no_move = ((btype == "NoStart") | (intent == "NoHit") | (
        (btype == "NotBlocked") & np.isin(layer, list(nm["ground_layers"])) & (moved < nm["min_move_m"]))) & ~locked
    approach = np.isin(layer, list(al)) & ~touched & ~locked
    return pd.DataFrame({"touch_id": _col(tables, "tap", "touch_id"), "t": t, "intent": intent, "hit_layer": layer,
                         "block_type": btype, "hit_x": _col(tables, "tap", "hit_x"), "hit_z": _col(tables, "tap", "hit_z"),
                         "moved_m": moved, "no_move": no_move, "approach": approach, "touched": touched, "locked": locked})


# ───────────────────────── 10.12 环视 ─────────────────────────
def classify_drags(tables, pose, taps):
    """每次手动拖动（按 touch_id 合并）：是否环视（开始时没在移动）；附 after_no_move 供观察（不影响计数）。"""
    cols = ["touch_id", "t0", "t1", "yaw_deg", "pitch_deg", "yaw_end", "x", "z", "is_look", "after_no_move"]
    if not _present(tables, "look"):
        return pd.DataFrame(columns=cols)
    p = M["look"]["parameters"]
    lk = pd.DataFrame({"touch_id": _col(tables, "look", "touch_id"), "type": _txt(tables, "look", "look_type"),
                       "t0": _col(tables, "look", "t_session_start"), "t1": _col(tables, "look", "t_session_end"),
                       "yaw": _col(tables, "look", "yaw_path"), "pitch": _col(tables, "look", "pitch_path"),
                       "yaw_end": _col(tables, "look", "yaw_end")})
    lk = lk[(lk.type == "Drag") & np.isfinite(lk.touch_id)]
    rows = []
    tap_t = taps["t"].to_numpy() if len(taps) else np.array([])
    for tid, g in lk.groupby("touch_id", sort=True):
        a, b = float(g.t0.min()), float(g.t1.max())
        walking = pose.moving_before(a, p["walking_window_s"], p["still_step_m"])
        after = False
        if not walking and len(tap_t):
            prev = np.flatnonzero(tap_t < a)
            if len(prev):
                i = prev[-1]
                after = bool(taps["no_move"].iloc[i]) and pose.path_between(tap_t[i], a) < 0.3
        k = min(int(np.searchsorted(pose.t, a)), len(pose.t) - 1)
        rows.append({"touch_id": int(tid), "t0": a, "t1": b, "yaw_deg": float(g.yaw.sum()), "pitch_deg": float(g.pitch.sum()),
                     "yaw_end": float(g.sort_values("t1").yaw_end.iloc[-1]), "x": float(pose.x[k]), "z": float(pose.z[k]),
                     "is_look": not walking, "after_no_move": after})
    return pd.DataFrame(rows, columns=cols)


# ───────────────────────── 汇总 ─────────────────────────
@dataclass
class RecordResult:
    summary: dict
    dwells: pd.DataFrame
    taps: pd.DataFrame
    drags: pd.DataFrame
    ap: pd.DataFrame
    areas: pd.DataFrame
    per_minute: pd.DataFrame
    stays: list = field(default_factory=list)


def compute_record(tables, scene: SceneGeometry):
    tables = clean_legacy(tables)
    pose = Pose.from_tables(tables)
    sess = tables["session"]
    start = sess[settings.column("session", "t_device_start")].iloc[0]
    end = sess[settings.column("session", "t_device_end")].iloc[0]
    complete = pd.notna(end)
    duration = float(end - start) if complete else float(pose.t[-1])
    minutes = duration / 60.0

    stays, sw = stay_walk(pose)
    dw = dwells(pose)
    taps = classify_taps(tables, pose)
    drags = classify_drags(tables, pose, taps)

    # 10.3 行动范围
    fr = M["footprint"]["parameters"]["brush_radius_m"]
    foot = scene.brush(pose.x[::2], pose.z[::2], fr)
    foot_m2 = float(foot.sum() * RASTER_M ** 2)
    foot_walk_m2 = float((foot & scene.walkable).sum() * RASTER_M ** 2)

    # 10.6 景点到访、10.10 触摸过的景点
    reach = M["ap_visit"]["parameters"]["reach_m"]
    ap_rows = []
    touched = taps[taps.touched] if len(taps) else taps
    for ap in scene.aps:
        hits = [d for d in dw if (_dist_to_polygon(pose.x[d["i0"]:d["i1"] + 1], pose.z[d["i0"]:d["i1"] + 1], ap["points"]) <= reach).any()]
        tch = int((_dist_to_polygon(touched.hit_x.to_numpy(), touched.hit_z.to_numpy(), ap["points"])
                   <= M["touched_ap_count"]["parameters"]["reach_m"]).sum()) if len(touched) else 0
        ap_rows.append({"ap": ap["id"], "dwell_n": len(hits), "dwell_s": float(sum(d["duration_s"] for d in hits)), "touch_n": tch})
    ap_df = pd.DataFrame(ap_rows, columns=["ap", "dwell_n", "dwell_s", "touch_n"])

    # 区域与桥：在内的时间、逗留时间、行动范围面积（报告，不是指标）
    dt = np.diff(pose.t); mid_x = (pose.x[1:] + pose.x[:-1]) / 2; mid_z = (pose.z[1:] + pose.z[:-1]) / 2
    in_dwell = np.zeros(len(dt), bool)
    for d in dw:
        in_dwell[d["i0"]:d["i1"]] = True
    area_rows = []
    for a in scene.areas:
        inside = MplPath(a["points"]).contains_points(np.c_[mid_x, mid_z])
        area_rows.append({"area": a["id"], "kind": a["kind"], "time_s": float(dt[inside].sum()), "dwell_s": float(dt[inside & in_dwell].sum()),
                          "footprint_m2": float((foot & scene.area_masks[a["id"]]).sum() * RASTER_M ** 2),
                          "walkable_m2": float((scene.walkable & scene.area_masks[a["id"]]).sum() * RASTER_M ** 2)})
    area_df = pd.DataFrame(area_rows)

    # 每分钟（报告）
    nmin = int(np.ceil(duration / 60.0))
    edges = np.arange(nmin + 1) * 60.0
    cnt = lambda v: np.histogram(v, bins=edges)[0] if len(v) else np.zeros(nmin, int)
    in_stay = np.zeros(len(dt), bool)
    for a_, e_ in stays:
        in_stay[a_:e_] = True
    stay_s = np.histogram(pose.t[1:], bins=edges, weights=dt * in_stay)[0]
    looks = drags[drags.is_look] if len(drags) else drags
    per_min = pd.DataFrame({"minute": np.arange(1, nmin + 1), "taps": cnt(taps.t), "no_move_taps": cnt(taps.t[taps.no_move]) if len(taps) else 0,
                            "approach": cnt(taps.t[taps.approach]) if len(taps) else 0, "touch": cnt(taps.t[taps.touched]) if len(taps) else 0,
                            "looks": cnt(looks.t0) if len(looks) else 0, "stay_s": stay_s,
                            "path_m": np.histogram(pose.t[1:], bins=edges, weights=pose.step)[0]})

    bs = tables["backstep"]
    gl_status = _txt(tables, "tech_glitch", "status") if _present(tables, "tech_glitch") else np.array([])
    gl_dur = _col(tables, "tech_glitch", "duration") if _present(tables, "tech_glitch") else np.array([])
    s = {
        "duration_s": duration, "complete": bool(complete),
        "stay_n": sw["stay_n"], "stay_s": sw["stay_s"], "stay_share": sw["stay_s"] / duration,
        "walk_s": sw["walk_s"], "walk_share": sw["walk_s"] / duration, "walk_path_m": sw["walk_path_m"],
        "dwell_n": len(dw), "dwell_s": float(sum(d["duration_s"] for d in dw)),
        "footprint_m2": foot_m2, "footprint_walkable_m2": foot_walk_m2, "scene_walkable_m2": scene.walkable_m2,
        "footprint_share": foot_walk_m2 / scene.walkable_m2,
        "ap_visited_n": int((ap_df.dwell_n > 0).sum()), "ap_dwell_n": int(ap_df.dwell_n.sum()),
        "tap_n": int(len(taps)), "tap_per_min": len(taps) / minutes,
        "no_move_tap_n": int(taps.no_move.sum()) if len(taps) else 0,
        "approach_n": int(taps.approach.sum()) if len(taps) else 0,
        "touch_n": int(taps.touched.sum()) if len(taps) else 0,
        "first_touch_s": float(taps.t[taps.touched].min()) if len(taps) and taps.touched.any() else np.nan,
        "touched_ap_n": int((ap_df.touch_n > 0).sum()),
        "backstep_n": int(len(bs)) if _present(tables, "backstep") else 0,
        "look_n": int(len(looks)), "look_yaw_deg": float(looks.yaw_deg.sum()) if len(looks) else 0.0,
        "look_pitch_deg": float(looks.pitch_deg.sum()) if len(looks) else 0.0,
        "glitch_freeze_n": int((gl_status == "Freeze").sum()), "glitch_background_n": int((gl_status == "Background").sum()),
        "glitch_s": float(np.nansum(gl_dur)) if len(gl_dur) else 0.0,
    }
    s["dwell_share"] = s["dwell_s"] / duration
    s["no_move_tap_share"] = s["no_move_tap_n"] / s["tap_n"] if s["tap_n"] else np.nan
    for k in ("approach", "touch"):
        s[f"{k}_per_min"] = s[f"{k}_n"] / minutes
    dw_df = pd.DataFrame([{k: v for k, v in d.items() if k not in ("i0", "i1")} for d in dw],
                         columns=["t0", "t1", "duration_s", "x", "z", "radius_m", "pauses"])
    return RecordResult(s, dw_df, taps, drags, ap_df, area_df, per_min, stays)


# 宽表列的顺序与中文说明（供制表与报告使用）
SUMMARY_COLUMNS = {
    "duration_s": "会话时长（s）", "complete": "会话正常结束（有 t_device_end）",
    "stay_n": "停留次数", "stay_s": "停留总时长（s）", "stay_share": "停留占比",
    "walk_s": "行走总时长（s）", "walk_share": "行走占比", "walk_path_m": "行走路程（m）",
    "dwell_n": "逗留次数", "dwell_s": "逗留总时长（s）", "dwell_share": "逗留时间占比",
    "footprint_m2": "行动范围（m²）", "footprint_walkable_m2": "行动范围与场景可达范围的重叠（m²）",
    "scene_walkable_m2": "场景可达范围（m²，所有被试相同）", "footprint_share": "行动范围占场景可达范围比例",
    "ap_visited_n": "到访景点数", "ap_dwell_n": "景点逗留次数",
    "tap_n": "点击量", "tap_per_min": "点击频率（次/分钟）",
    "no_move_tap_n": "无位移点击次数", "no_move_tap_share": "无位移点击占比",
    "approach_n": "approach 次数", "approach_per_min": "approach 频率（次/分钟）",
    "touch_n": "触摸次数", "touch_per_min": "触摸频率（次/分钟）", "first_touch_s": "首次触摸时间（s，无触摸为空）",
    "touched_ap_n": "触摸过的景点数", "backstep_n": "长按后退次数",
    "look_n": "环视次数", "look_yaw_deg": "环视量·左右（°）", "look_pitch_deg": "环视量·上下（°）",
    "glitch_freeze_n": "画面卡住次数", "glitch_background_n": "切后台次数", "glitch_s": "技术故障总时长（s）",
}
