"""physio 工具 03 的全部处理函数：套用人工更正表并体检事件。

输入（只读）：
    data/<数据集>/processed/physio/sub-P###/merged/markers.csv
    data/<数据集>/corrections/physio_events.csv（utf-8-sig，可能不存在；不存在视为没有更正）
输出：data/<数据集>/processed/physio/
    sub-P###/events/markers.csv   列：t_unix、time_lsl、part、label、label_raw、t_local、source
    sub-P###/events/report.txt    中文报告
    sub-P###/events/windows.csv   窗口表：每个阶段一行；列 window、t_start、t_end、t_start_local、t_end_local、duration_s、valid、issue
    events_check.csv              每人一行（subject、status、n_corrections_applied、issues）；重跑只替换本次被试的行
subject 列写 sub-P### 或 P### 都视为同一人。

更正表按文件先后逐行套用到事件集合上，每行的依据是套用前的事件状态。
任何一行出错：该被试不写 events/；若已有旧的 events/，用 safe_io.retire_dir 移走；在 events_check.csv 记 error。
体检只报告，不修改。写盘前检查路径在 processed/physio/ 之内。
"""
import csv
from datetime import datetime

from global_settings import PHYSIO_MARKER_LABELS, PHYSIO_PHASE_DURATION_S, PHYSIO_PHASES
from paths import layer_dir
from safe_io import retire_dir
from physio_merge import TZ_BEIJING, t_local
from physio_xdf import check_inside, list_subjects, normalize_subject

MATCH_TOL_S = 1.0
ACTIONS = ("delete", "move", "add", "relabel")
OUT_COLUMNS = ["t_unix", "time_lsl", "part", "label", "label_raw", "t_local", "source"]
WINDOW_COLUMNS = ["window", "t_start", "t_end", "t_start_local", "t_end_local", "duration_s", "valid", "issue"]
CHECK_COLUMNS = ["subject", "status", "n_corrections_applied", "issues"]
SOURCE_RANK = {"raw": 0, "relabeled": 1, "moved": 2, "added": 3}


class CorrectionError(Exception):
    """更正表某一行无法套用。row 为表格行号（含表头，第 2 行是第一条数据）。"""

    def __init__(self, row, column, message):
        super().__init__(f"更正表第 {row} 行，{column} 列：{message}")
        self.row, self.column, self.message = row, column, message


# ---------- 读取 ----------

def read_markers(path):
    events = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            events.append({
                "t_unix": float(r["t_unix"]), "time_lsl": float(r["time_lsl"]),
                "part": r["part"], "label": r["label"], "label_raw": r.get("label_raw", "") or "",
                "source": "raw",
            })
    return events


def read_corrections(path, pid):
    """返回 [(表格行号, 行字典)]，只含当前被试的行，保持文件顺序。"""
    if not path.is_file():
        return []
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            if normalize_subject((r.get("subject") or "").strip()) == pid:
                rows.append((i, {k: (v or "").strip() for k, v in r.items() if k is not None}))
    return rows


# ---------- 套用 ----------

def hms(t):
    return t_local(t)[11:]


def part_offsets(events):
    """同一 part 内 time_lsl 与 t_unix 的固定差值（取中位数）。"""
    by = {}
    for e in events:
        by.setdefault(e["part"], []).append(e["time_lsl"] - e["t_unix"])
    return {p: sorted(v)[len(v) // 2] for p, v in by.items()}


def parse_clock(text, row, column):
    try:
        h, m, s = text.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except ValueError:
        raise CorrectionError(row, column, f"时刻“{text}”不是 HH:MM:SS.fff 格式")


def parse_datetime(text, row, column):
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=TZ_BEIJING).timestamp()
    except ValueError:
        raise CorrectionError(row, column, f"时间“{text}”不是 YYYY-MM-DD HH:MM:SS.fff 格式")


def locate(events, r, row):
    label, time_text = r.get("match_label", ""), r.get("match_time", "")
    if not label:
        raise CorrectionError(row, "match_label", "该动作需要填写 match_label")
    if not time_text:
        raise CorrectionError(row, "match_time", "该动作需要填写 match_time")
    target = parse_clock(time_text, row, "match_time")
    hits = []
    for e in events:
        if e["label"] != label:
            continue
        sod = datetime.fromtimestamp(e["t_unix"], TZ_BEIJING)
        sod = sod.hour * 3600 + sod.minute * 60 + sod.second + sod.microsecond / 1e6
        d = abs(sod - target)
        if min(d, 86400 - d) <= MATCH_TOL_S:
            hits.append(e)
    if not hits:
        raise CorrectionError(row, "match_label/match_time", f"找不到 {label} 在 {time_text} 附近（±1 秒）的事件")
    if len(hits) > 1:
        raise CorrectionError(row, "match_label/match_time", f"{label} 在 {time_text} 附近有 {len(hits)} 条事件，不唯一")
    return hits[0]


def new_time_of(events, r, row):
    new_time, anchor, offset = r.get("new_time", ""), r.get("anchor", ""), r.get("offset_s", "")
    has_abs, has_rel = bool(new_time), bool(anchor or offset)
    if has_abs and has_rel:
        raise CorrectionError(row, "new_time/anchor/offset_s", "new_time 与 anchor+offset_s 只能填一种，现在两种都填了")
    if not has_abs and not has_rel:
        raise CorrectionError(row, "new_time/anchor/offset_s", "新时刻必须填 new_time 或 anchor+offset_s，现在都没填")
    if has_abs:
        return parse_datetime(new_time, row, "new_time"), None
    if not anchor:
        raise CorrectionError(row, "anchor", "填了 offset_s 但没有 anchor")
    if not offset:
        raise CorrectionError(row, "offset_s", "填了 anchor 但没有 offset_s")
    try:
        off = float(offset)
    except ValueError:
        raise CorrectionError(row, "offset_s", f"“{offset}”不是数字")
    hits = [e for e in events if e["label"] == anchor]
    if not hits:
        raise CorrectionError(row, "anchor", f"当前事件中没有 {anchor}")
    if len(hits) > 1:
        raise CorrectionError(row, "anchor", f"当前事件中 {anchor} 有 {len(hits)} 条，不唯一")
    return hits[0]["t_unix"] + off, hits[0]


def bump(event, source):
    if SOURCE_RANK[source] > SOURCE_RANK[event["source"]]:
        event["source"] = source


def apply_corrections(events, corrections):
    """逐行套用；返回 (新事件列表, 套用记录)。出错抛 CorrectionError。"""
    offsets = part_offsets(events)
    events = [dict(e) for e in events]
    log = []
    for row, r in corrections:
        action = r.get("action", "")
        if action not in ACTIONS:
            raise CorrectionError(row, "action", f"“{action}”不是 delete/move/add/relabel 之一")
        label = r.get("label", "")
        if action == "delete":
            e = locate(events, r, row)
            events.remove(e)
            log.append((row, "delete", f"{e['label']} {hms(e['t_unix'])} → 删除"))
        elif action == "relabel":
            e = locate(events, r, row)
            if not label:
                raise CorrectionError(row, "label", "relabel 需要填写新的 label")
            old = e["label"]
            e["label"] = label
            bump(e, "relabeled")
            log.append((row, "relabel", f"{old} {hms(e['t_unix'])} → {label}（时刻不变）"))
        elif action == "move":
            e = locate(events, r, row)
            t_new, _ = new_time_of(events, r, row)
            old_t, old_label = e["t_unix"], e["label"]
            e["t_unix"] = t_new
            e["time_lsl"] = t_new + offsets[e["part"]]
            if label:
                e["label"] = label
            bump(e, "moved")
            log.append((row, "move", f"{old_label} {hms(old_t)} → {e['label']} {hms(t_new)}"))
        else:  # add
            if not label:
                raise CorrectionError(row, "label", "add 需要填写 label")
            t_new, anchor_event = new_time_of(events, r, row)
            if anchor_event is not None:
                part = anchor_event["part"]
            else:
                part = min(events, key=lambda x: abs(x["t_unix"] - t_new))["part"] if events else None
            if part is None or part not in offsets:
                raise CorrectionError(row, "label", "没有可用的事件来确定新增事件所属的 part")
            events.append({"t_unix": t_new, "time_lsl": t_new + offsets[part], "part": part,
                           "label": label, "label_raw": "", "source": "added"})
            log.append((row, "add", f"无 → {label} {hms(t_new)}"))
    events.sort(key=lambda x: x["t_unix"])
    return events, log


# ---------- 体检 ----------

def check_events(events, tol):
    """返回 (问题列表（中文短句）, 有效区间 spans, 各阶段问题 by_phase)。只报告，不修改。"""
    issues = []
    spans = {}
    by_phase = {phase: [] for phase in PHYSIO_PHASES}
    times = {phase: {} for phase in PHYSIO_PHASES}
    for phase in PHYSIO_PHASES:
        pts = {}
        for boundary in ("start", "end"):
            name = f"{phase}_{boundary}"
            hits = [e for e in events if e["label"] == name]
            if not hits:
                msg = f"缺少 {name}"
            elif len(hits) > 1:
                at = "、".join(hms(e["t_unix"]) for e in hits)
                msg = f"{name} 重复 {len(hits)} 条（{at}）"
            else:
                pts[boundary] = times[phase][boundary] = hits[0]["t_unix"]
                continue
            issues.append(msg)
            by_phase[phase].append(msg)
        if len(pts) == 2:
            if pts["start"] >= pts["end"]:
                msg = f"{phase} 的 start（{hms(pts['start'])}）不早于 end（{hms(pts['end'])}）"
                issues.append(msg)
                by_phase[phase].append(msg)
            else:
                spans[phase] = (pts["start"], pts["end"])
                std = PHYSIO_PHASE_DURATION_S.get(phase)
                dur = pts["end"] - pts["start"]
                if std is not None and abs(dur - std) > tol:
                    msg = f"{phase} 时长 {dur:.1f} 秒，与标准 {std} 秒相差 {dur - std:+.1f} 秒，超出 ±{tol:g} 秒"
                    issues.append(msg)
                    by_phase[phase].append(msg)
    order = [p for p in PHYSIO_PHASES if p in spans]
    for a, b in zip(order, order[1:]):
        if spans[a][1] > spans[b][0]:
            msg = f"阶段顺序有误：{a} 的结束（{hms(spans[a][1])}）晚于 {b} 的开始（{hms(spans[b][0])}）"
            issues.append(msg)
            by_phase[a].append(msg)
            by_phase[b].append(msg)
    return issues, spans, by_phase, times


# ---------- 输出 ----------

def phase_of(label):
    for phase in PHYSIO_PHASES:
        if label in (f"{phase}_start", f"{phase}_end"):
            return phase
    return None


def write_events(events, out_dir, processed):
    path = check_inside(out_dir / "markers.csv", processed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(OUT_COLUMNS)
        for e in events:
            w.writerow([repr(e["t_unix"]), repr(e["time_lsl"]), e["part"], e["label"],
                        e["label_raw"], t_local(e["t_unix"]), e["source"]])


def write_windows(pid, by_phase, times, out_dir, processed):
    """每个阶段一行；缺 start/end（或重复无法确定）的时刻留空；valid=1 当且仅当该阶段没有任何问题。"""
    path = check_inside(out_dir / "windows.csv", processed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(WINDOW_COLUMNS)
        for phase in PHYSIO_PHASES:
            t0, t1 = times[phase].get("start"), times[phase].get("end")
            dur = f"{t1 - t0:.3f}" if t0 is not None and t1 is not None else ""
            issue = "；".join(by_phase[phase])
            w.writerow([phase, repr(t0) if t0 is not None else "", repr(t1) if t1 is not None else "",
                        t_local(t0), t_local(t1), dur, 0 if issue else 1, issue])


def write_report(pid, events, log, issues, spans, n_rows, out_dir, processed):
    lines = [f"physio 工具 03 事件更正与体检报告：sub-{pid}",
             f"生成时间：{datetime.now(TZ_BEIJING).isoformat(timespec='seconds')}（北京时间）", "",
             f"[一] 套用的人工更正（共 {len(log)} 行；行号为更正表行号，含表头）"]
    lines += [f"  第 {row} 行  {action}：{text}" for row, action, text in log] or ["  无"]
    lines += ["", "[二] 体检（套用更正后）"]
    lines += [f"  - {x}" for x in issues] or ["  通过"]
    lines += ["", "[三] 最终事件表", "  t_local                  label                         source     该阶段时长"]
    for e in events:
        phase = phase_of(e["label"])
        dur = f"{spans[phase][1] - spans[phase][0]:.1f} 秒" if phase in spans else ""
        lines.append(f"  {t_local(e['t_unix'])}  {e['label']:<28}  {e['source']:<9}  {dur}")
    path = check_inside(out_dir / "report.txt", processed)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_check_csv(processed, row):
    path = check_inside(processed / "events_check.csv", processed)
    rows = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = [{k: r.get(k, "") for k in CHECK_COLUMNS} for r in csv.DictReader(f) if r["subject"] != row["subject"]]
    rows.append({k: str(v) for k, v in row.items()})
    rows.sort(key=lambda r: r["subject"])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CHECK_COLUMNS)
        w.writeheader()
        w.writerows(rows)


# ---------- 入口 ----------

def process_subject(dataset, pid, processed, corrections_path, cfg):
    out_dir = processed / f"sub-{pid}" / "events"
    check_inside(out_dir, processed)
    markers_path = processed / f"sub-{pid}" / "merged" / "markers.csv"
    row = {"subject": pid, "status": "error", "n_corrections_applied": 0, "issues": ""}
    try:
        if not markers_path.is_file():
            raise CorrectionError("-", "-", f"找不到 {markers_path}（先运行工具 01、02）")
        events = read_markers(markers_path)
        corrections = read_corrections(corrections_path, pid)
        events, log = apply_corrections(events, corrections)
    except CorrectionError as error:
        row["issues"] = str(error)
        if out_dir.exists():
            retire_dir(out_dir)
        update_check_csv(processed, row)
        print(f"[更正表出错] {pid}：{error}（未写 events/）")
        return row
    issues, spans, by_phase, times = check_events(events, cfg["DURATION_TOL_S"])
    write_events(events, out_dir, processed)
    write_windows(pid, by_phase, times, out_dir, processed)
    write_report(pid, events, log, issues, spans, len(corrections), out_dir, processed)
    row.update(status="issues" if issues else "ok", n_corrections_applied=len(log), issues="；".join(issues))
    update_check_csv(processed, row)
    if issues:
        print(f"[需要人工判断] {pid}：{row['issues']}")
    else:
        print(f"[规则检查通过] {pid}：应用 {len(log)} 行更正")
    return row


def print_summary(processed, rows):
    """全部被试处理完后的终端总结；只读 rows，不改任何文件。"""
    check_path = (processed / "events_check.csv").resolve()
    report_dir = processed.resolve()
    bad = [r for r in rows if r["status"] != "ok"]
    print("-" * 60)
    if bad:
        pids = "、".join(r["subject"] for r in bad)
        print(f"有 {len(bad)} 位被试需要人工判断：{pids}")
    print(f"事件检查结果：{check_path}")
    print(f"各被试的事件时刻与各阶段时长：{report_dir}/sub-P###/events/report.txt 第 [三] 部分")
    print("请对照实验现场情况和流程单记录（raw/session_notes/sub-P###/log.csv），逐个核对每位被试的事件是否需要调整。")
    print("不论 status 是否为 ok，都要核对：规则检查发现不了“时长正常但整体点偏”这类错误。")
    print("需要调整的，把情况发给研究者，由研究者写入更正表 corrections/physio_events.csv 后重跑 03。")
    print("不要编辑 events_check.csv 和 events/ 下的文件：它们每次运行都会被覆盖。")


def run(dataset, subjects, cfg):
    processed = layer_dir(dataset, "processed", "physio")
    corrections_path = layer_dir(dataset, "processed").parent / "corrections" / "physio_events.csv"
    pool = list_subjects(processed)
    if subjects == "*":
        chosen = pool
    else:
        chosen = [normalize_subject(s) for s in ([subjects] if isinstance(subjects, str) else subjects)]
        missing = [s for s in chosen if s not in pool]
        if missing:
            raise ValueError(f"processed/physio 中没有这些被试：{missing}；现有：{pool}")
    if not chosen:
        raise ValueError(f"processed/physio 中没有任何 sub-P### 文件夹：{processed}")
    print(f"数据集 {dataset}：共 {len(chosen)} 位被试；更正表：{corrections_path if corrections_path.is_file() else '（不存在，视为没有更正）'}")
    rows = [process_subject(dataset, pid, processed, corrections_path, cfg) for pid in chosen]
    print_summary(processed, rows)
    return rows
