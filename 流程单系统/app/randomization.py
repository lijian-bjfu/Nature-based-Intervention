"""
分层区组随机分组。

方法：按 STAI-T 总分分高/低两层；每层一张独立的随机序列，由区组拼成（每区组
config.RANDOMIZATION_BLOCK_SIZE 个位置，实验组与对照组各占一半，区组内顺序随机）。
序列不存文件，每次由 config.RANDOMIZATION_SEED 确定性地重新生成。

"位置"从 1 开始计，按层独立编号。已取号但被试中途退出的位置作废，不回收。
本模块的 build_sequences / assign_for 同时供服务和 tests/simulate_randomization.py 使用。
"""
import json
import os
import random

import config
import state as state_mod

STRATA = ("high", "low")
CONDITIONS = ("实验组", "对照组")
CONDITION_CODE = {"实验组": "1", "对照组": "2"}
STRATUM_LABEL = {"high": "高焦虑", "low": "低焦虑"}


class RandomizationError(Exception):
    """取号失败（例如某层位置已用尽）。"""


def build_sequences():
    """返回 {"high": [...], "low": [...]}，元素为 "实验组"/"对照组"。
    每层用独立的 random.Random(f"{seed}-{stratum}")（字符串种子，跨平台、跨次运行一致）。"""
    size = config.RANDOMIZATION_BLOCK_SIZE
    length = config.RANDOMIZATION_LENGTH_PER_STRATUM
    if size % 2 or length % size:
        raise ValueError("区组大小必须为偶数，且每层位置数必须是区组大小的整数倍")
    sequences = {}
    for stratum in STRATA:
        rng = random.Random("%s-%s" % (config.RANDOMIZATION_SEED, stratum))
        seq = []
        for _ in range(length // size):
            block = ["实验组"] * (size // 2) + ["对照组"] * (size // 2)
            rng.shuffle(block)
            seq.extend(block)
        sequences[stratum] = seq
    return sequences


def next_position(used_positions):
    """已用位置的最大值 + 1；没有已用位置时为 1。中途退出者占用的位置不回收。"""
    used = list(used_positions)
    return (max(used) + 1) if used else 1


def assign_for(stratum, used_positions, sequences):
    """纯函数：返回 (位置, 组别)。位置超出序列长度时抛 RandomizationError。"""
    if stratum not in sequences:
        raise RandomizationError("未知的层：%r" % (stratum,))
    position = next_position(used_positions)
    seq = sequences[stratum]
    if position > len(seq):
        raise RandomizationError(
            "%s层的随机序列已用尽（共 %d 个位置，已用到第 %d 位），无法再分组。请联系研究者。"
            % (STRATUM_LABEL.get(stratum, stratum), len(seq), position - 1))
    return position, seq[position - 1]


def stratum_of(total):
    """STAI-T 总分 → "high"/"low"（界值 config.STAI_T_CUTOFF）。"""
    return "high" if total >= config.STAI_T_CUTOFF else "low"


def used_position_map(data_root, stratum):
    """{位置: 被试编号}：实验模式数据集 raw/psycho/ 下 sub-P### 与 _break_sub-P### 文件夹的
    state.json 里 state["randomization"] 属于该层的位置。其他文件夹、调整模式的数据不算。
    读不出的 state.json 跳过并在控制台打印警告。"""
    root = state_mod.psycho_root(data_root, "experiment")
    result = {}
    if not os.path.isdir(root):
        return result
    prefix = config.PARTICIPANT_PREFIX["experiment"]
    for name in sorted(os.listdir(root)):
        base = name[len(config.BREAK_PREFIX):] if name.startswith(config.BREAK_PREFIX) else name
        if not (base.startswith("sub-" + prefix) and base[len("sub-" + prefix):].isdigit()):
            continue
        path = os.path.join(root, name, "state.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                st = json.load(f)
            rec = st.get("randomization")
            if rec and rec.get("stratum") == stratum:
                result[int(rec["position"])] = st.get("participant_id") or base[len("sub-"):]
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            print("[警告] 随机分组：读不出 %s（%s），已跳过，该被试占用的位置可能未被计入。" % (path, e))
    return result


def used_positions(data_root, stratum):
    return sorted(used_position_map(data_root, stratum))
