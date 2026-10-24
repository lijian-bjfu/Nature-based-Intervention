"""统一的数据调取：按 dataset / pipeline / subject（以及 layer）找到并载入数据。

命名规范见 paths.py。制表（table_flows）与数据实验（data_lab）一律通过这里取数据，不在脚本里拼路径、
不各自写一套"找文件"的逻辑。

    from data_access import subjects, find, load
    subjects("test", "track")                    # 这个数据集里有哪些被试：['P000', 'P999']
    find("test", "track", ["P999"], run="002")   # {'P999': Path(.../sub-P999_ses-S001_mod-Interactive_run-002)}
    load("test", "track", "P999", run="002")     # 载入这名被试的七张埋点表

subjects 参数可以是一个编号、一组编号，或通配符（"*" 全部，"P0*" 等）。

各 pipeline 的"一名被试对应什么"：
    track   被试在实验条件中的那一份记录（实验组 Interactive，对照组 Passive）。练习场（Practice）的记录不用于分析，
            这里不会返回。同一被试有多份记录时（例如测试中重跑），必须用 run 指明要哪一份，否则报错并列出可选项。
    psycho  尚未接入：问卷原始格式确定后实现。
    physio  尚未接入：生理数据原始格式确定后实现。

目前只实现 layer="raw" 的查找；processed、final 的组织方式随 table_flows 实现时确定。
"""
from fnmatch import fnmatchcase
from pathlib import Path
import re

import global_settings as settings
from paths import layer_dir, PIPELINES

TRACK_ANALYSED_MODULES = ("Interactive", "Passive")   # 不含 Practice


def subject_of(record_name):
    """sub-P040_ses-S001_mod-Interactive_run-001 → P040"""
    match = re.fullmatch(settings.TRACK_SESSION_REGEX, record_name)
    return f"P{match['subject']}" if match else None


def _track_records(dataset):
    base = layer_dir(dataset, "raw", "track")
    out = []
    for folder in sorted(base.glob(settings.TRACK_SESSION_GLOB)):
        match = re.fullmatch(settings.TRACK_SESSION_REGEX, folder.name) if folder.is_dir() else None
        if match and match["module"] in TRACK_ANALYSED_MODULES:
            out.append((f"P{match['subject']}", match["run"], folder))
    return out


def _not_yet(pipeline):
    raise NotImplementedError(f"{pipeline} 的数据调取尚未接入：原始格式确定后在 data_access.py 中实现。")


def subjects(dataset, pipeline, layer="raw"):
    """这个数据集、这个 pipeline 下有哪些被试。"""
    _check(pipeline, layer)
    if pipeline == "track":
        return sorted({s for s, _, _ in _track_records(dataset)})
    _not_yet(pipeline)


def find(dataset, pipeline, subjects="*", layer="raw", run=None):
    """返回 {被试编号: 记录位置}。subjects 可为编号、编号列表或通配符。"""
    _check(pipeline, layer)
    patterns = [subjects] if isinstance(subjects, str) else list(subjects)
    if pipeline != "track":
        _not_yet(pipeline)
    records = _track_records(dataset)
    chosen = {}
    for subject in sorted({s for s, _, _ in records if any(fnmatchcase(s, p) for p in patterns)}):
        mine = [(r, f) for s, r, f in records if s == subject]
        if run is not None:
            mine = [(r, f) for r, f in mine if r == str(run).zfill(3)]
        if len(mine) == 1:
            chosen[subject] = mine[0][1]
        elif not mine:
            raise FileNotFoundError(f"{dataset}/{pipeline}：被试 {subject} 没有 run={run} 的记录")
        else:
            raise ValueError(f"{dataset}/{pipeline}：被试 {subject} 有多份记录 "
                             f"{[f.name for _, f in mine]}，请用 run 指明要哪一份")
    if not chosen:
        available = ", ".join(sorted({s for s, _, _ in records})) or "（无）"
        raise FileNotFoundError(f"{dataset}/{pipeline} 中没有匹配 {patterns} 的被试。现有被试：{available}")
    return chosen


def load(dataset, pipeline, subject, layer="raw", run=None, formatted=False):
    """载入一名被试的数据。track 返回 {表名: DataFrame}。"""
    path = find(dataset, pipeline, [subject], layer=layer, run=run)[subject]
    if pipeline == "track":
        from track_io import read_session
        return read_session(path, formatted=formatted)
    _not_yet(pipeline)


def load_geo():
    """载入地理空间标注（区域、桥、景点多边形与空气墙折线），并按 global_settings.GEO_ANNOTATION_SPEC 核对。"""
    import json
    from paths import GEO_ANNOTATION
    spec = settings.GEO_ANNOTATION_SPEC
    if not GEO_ANNOTATION.is_file():
        raise FileNotFoundError(f"找不到地理空间标注：{GEO_ANNOTATION}。在 Unity 里用 Tools ▸ NBI ▸ 地理空间标注 导出。")
    geo = json.loads(GEO_ANNOTATION.read_text(encoding="utf-8"))
    if geo.get("format") != spec["format"] or geo.get("format_version") != spec["format_version"]:
        raise ValueError(f"地理空间标注格式为 {geo.get('format')} v{geo.get('format_version')}，"
                         f"规范要求 {spec['format']} v{spec['format_version']}；导出于 Unity 提交 {geo.get('unity_commit')}")
    for poly in geo["polygons"]:
        if poly["kind"] not in spec["kinds"] or not re.fullmatch(spec["id_regex"][poly["kind"]], poly["id"]):
            raise ValueError(f"地理空间标注中有不合规的范围：{poly['kind']} {poly['id']}")
    return geo


def _check(pipeline, layer):
    if pipeline not in PIPELINES:
        raise ValueError(f"未知 pipeline：{pipeline}；可选 {PIPELINES}")
    if layer != "raw":
        raise NotImplementedError("目前只实现 raw 层的调取；processed、final 随 table_flows 实现时确定。")
