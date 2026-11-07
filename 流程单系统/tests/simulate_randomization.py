"""
分层区组随机分组 · 平衡性模拟（VS Code 里直接点 Run 即可）。

调用 app/randomization.py 里真实的 build_sequences / assign_for，不另写分配逻辑。
对照基线为"简单随机"（每人 50% 掷硬币）。输出 tests/randomization_report.md 并在控制台打印摘要。
报告只写统计结果和表的检查结论，不写出两张序列的具体内容。
"""
import itertools
import os
import random
import sys
import time

_P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_P, _P + "/app"]

import config  # noqa: E402
import randomization as rz  # noqa: E402

SIM_SEED = 20261107_01   # 模拟用的固定种子：报告可重复生成
REPS = 10000
N_LIST = (40, 80, 90)
P_LIST = (0.2, 0.35, 0.5, 0.65)
D_LIST = (0.0, 0.1)
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "randomization_report.md")


def check_tables():
    """表本身检查，返回 (是否全部通过, 结论行列表)。"""
    seqs = rz.build_sequences()
    size, length = config.RANDOMIZATION_BLOCK_SIZE, config.RANDOMIZATION_LENGTH_PER_STRATUM
    lines, ok = [], True

    def record(passed, text):
        nonlocal ok
        ok = ok and passed
        lines.append("- %s：%s" % ("通过" if passed else "**未通过**", text))

    record(all(len(seqs[s]) == length for s in rz.STRATA), "两层各 %d 个位置" % length)
    block_ok = True
    for s in rz.STRATA:
        for i in range(0, length, size):
            blk = seqs[s][i:i + size]
            if blk.count("实验组") != size // 2 or blk.count("对照组") != size // 2:
                block_ok = False
    record(block_ok, "逐个区组（每 %d 位）恰为 %d 实验组 + %d 对照组（共 %d 个区组 × 2 层）" % (
        size, size // 2, size // 2, length // size))
    record(seqs["high"] != seqs["low"], "高、低两层序列不相同")
    record(rz.build_sequences() == seqs, "连续两次调用 build_sequences 结果完全一致")
    return ok, lines


def simulate_once(rng, n, p, d, sequences, method):
    """返回最终样本里 (高实验, 高对照, 低实验, 低对照)。每次从空的已用位置开始。"""
    used = {"high": [], "low": []}
    cnt = {("high", "实验组"): 0, ("high", "对照组"): 0, ("low", "实验组"): 0, ("low", "对照组"): 0}
    for _ in range(n):
        stratum = "high" if rng.random() < p else "low"
        if method == "block":
            pos, cond = rz.assign_for(stratum, used[stratum], sequences)
            used[stratum].append(pos)   # 退出者也占用位置
        else:
            cond = "实验组" if rng.random() < 0.5 else "对照组"
        if rng.random() < d:             # T0 后退出：不计入最终样本
            continue
        cnt[(stratum, cond)] += 1
    return cnt[("high", "实验组")], cnt[("high", "对照组")], cnt[("low", "实验组")], cnt[("low", "对照组")]


def summarize_diffs(vals):
    return (sum(vals) / len(vals), max(vals), sum(1 for v in vals if v <= 2) / len(vals))


def run_case(n, p, d, sequences, method):
    rng = random.Random("sim-%s-%s-%s-%s-%s" % (SIM_SEED, n, p, d, method))
    tot, hi, lo, prop = [], [], [], []
    for _ in range(REPS):
        he, hc, le, lc = simulate_once(rng, n, p, d, sequences, method)
        e, c = he + le, hc + lc
        tot.append(abs(e - c))
        hi.append(abs(he - hc))
        lo.append(abs(le - lc))
        if e and c:
            prop.append(abs(he / e - hc / c))
    prop.sort()
    return {
        "tot": summarize_diffs(tot), "hi": summarize_diffs(hi), "lo": summarize_diffs(lo),
        "prop": (sum(prop) / len(prop), prop[int(0.95 * (len(prop) - 1))]),
    }


def fmt_row(key, res, method_name):
    n, p, d = key
    return n, p, d, method_name, res


def main():
    t0 = time.time()
    ok, check_lines = check_tables()
    sequences = rz.build_sequences()
    results = []
    for n, p, d in itertools.product(N_LIST, P_LIST, D_LIST):
        for method, name in (("block", "分层区组"), ("coin", "简单随机")):
            results.append(((n, p, d), name, run_case(n, p, d, sequences, method)))
        print("完成 N=%d p=%.2f d=%.1f（%.0f 秒）" % (n, p, d, time.time() - t0), flush=True)

    def table(title, field, kind):
        out = ["### " + title, ""]
        if kind == "diff":
            out += ["| N | 高焦虑比例 p | 退出率 d | 方法 | 差值均值 | 差值最大值 | 差≤2 的比例 |",
                    "|---|---|---|---|---|---|---|"]
            for (n, p, d), name, r in results:
                m, mx, le2 = r[field]
                out.append("| %d | %.2f | %.1f | %s | %.2f | %d | %.1f%% |" % (n, p, d, name, m, mx, le2 * 100))
        else:
            out += ["| N | 高焦虑比例 p | 退出率 d | 方法 | 均值 | 95% 分位数 |", "|---|---|---|---|---|---|"]
            for (n, p, d), name, r in results:
                m, q = r[field]
                out.append("| %d | %.2f | %.1f | %s | %.3f | %.3f |" % (n, p, d, name, m, q))
        out.append("")
        return out

    md = ["# 分层区组随机分组 · 平衡性模拟报告", "",
          "本报告由 `tests/simulate_randomization.py` 生成（模拟种子 %s，每种情形重复 %d 次，可重复生成）。" % (SIM_SEED, REPS), "",
          "## 一、随机序列表检查", ""] + check_lines + [
          "", "总体结论：%s" % ("全部通过。" if ok else "**存在未通过项，请检查。**"), "",
          "## 二、模拟设定", "",
          "- 每次模拟从空的已用位置开始；被试按顺序到达，每人独立以概率 p 属高焦虑层，其余为低焦虑层。",
          "- 分层区组：调用真实的 `build_sequences` / `assign_for` 取号；简单随机：每人 50% 掷硬币（基线）。",
          "- 完成 T0 的人数 N；退出率 d：T0 后退出者仍占用位置（不回收），但不计入最终样本。",
          "- 差值均为绝对值（实验组人数与对照组人数之差）；“高焦虑者占比之差”＝|实验组中高焦虑者占比 − 对照组中高焦虑者占比|。", "",
          "## 三、结果", ""]
    md += table("1. 最终样本：实验组与对照组人数差（|实验 − 对照|）", "tot", "diff")
    md += table("2. 高焦虑层内两组人数差", "hi", "diff")
    md += table("3. 低焦虑层内两组人数差", "lo", "diff")
    md += table("4. 两组中高焦虑者所占比例之差的绝对值", "prop", "prop")
    text = "\n".join(md) + "\n"
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(text)

    print("\n===== 摘要 =====")
    print("表检查：" + ("全部通过" if ok else "存在未通过项"))
    for l in check_lines:
        print(l)
    print("\n[总人数差 / 高层内差 / 低层内差：均值、最大、≤2 比例；高焦虑占比差：均值、P95]")
    for (n, p, d), name, r in results:
        print("N=%d p=%.2f d=%.1f %s | 总 %.2f/%d/%.0f%% | 高 %.2f/%d/%.0f%% | 低 %.2f/%d/%.0f%% | 占比差 %.3f/%.3f" % (
            n, p, d, name, r["tot"][0], r["tot"][1], r["tot"][2] * 100,
            r["hi"][0], r["hi"][1], r["hi"][2] * 100, r["lo"][0], r["lo"][1], r["lo"][2] * 100,
            r["prop"][0], r["prop"][1]))
    print("\n报告已写入 %s（用时 %.0f 秒）" % (REPORT, time.time() - t0))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
