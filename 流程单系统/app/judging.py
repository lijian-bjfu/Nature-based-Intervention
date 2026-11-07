"""
从已填的问卷作答里算出"判定依据"：问卷 A 的筛查结果、T0 的 STAI-T 总分与分类。
只做计算，不涉及渲染和状态落盘（落盘由 server.py 负责）。
"""
import config
import scales


def a_screening_summary(answers):
    """读问卷 A 的筛查多选（A_screen）作答，返回 (说明文字行列表, 给实验员的建议文字)。

    页面上第 1-4 项（精神心理疾病史/正在接受心理或精神科治疗/心脑血管疾病/癫痫或闪烁画面
    不适史）是医学/精神科方面的排除性筛查项；命中任意一项，建议实验员谨慎判断是否纳入。
    第 5-7 项（服药、看屏幕/玩游戏时头晕恶心、参加过本项目预实验）仅供参考，不直接建议排除。
    """
    options = scales.A2_SCREENING["options"]
    exclusive_idx = scales.A2_SCREENING["exclusive_option"]
    hard_idx = {0, 1, 2, 3}  # 页面上显示的第 1-4 项（0 起下标）

    selected = sorted(int(v) for v in (answers.get("A_screen") or []))

    if not selected or selected == [exclusive_idx]:
        return (["筛查结果：未勾选任何情况（“以上都没有”）。"], "建议：未命中排除性情况，可以纳入。")

    hit_hard = [i for i in selected if i in hard_idx]
    hit_soft = [i for i in selected if i not in hard_idx and i != exclusive_idx]

    lines = []
    if hit_hard:
        lines.append("命中第 1-4 项（医学/精神科排除性筛查项）：")
        lines.extend("　第 %d 项：%s" % (i + 1, options[i]) for i in hit_hard)
        suggestion = "建议：存在医学/精神科排除性情况，请谨慎判断是否适合纳入，必要时选择“不适合”。"
    else:
        suggestion = "建议：未命中第 1-4 项排除性情况，可以考虑纳入。"

    if hit_soft:
        lines.append("另外还勾选了（仅供参考，不直接建议排除）：")
        lines.extend("　第 %d 项：%s" % (i + 1, options[i]) for i in hit_soft)

    return lines, suggestion


def stait_total_score(t0_answers):
    """从 T0 答卷里算 STAI-T 总分（反向题已转换）。答得不全时返回 None。"""
    scale = scales.STAI_T
    lo = scale["value_start"]
    hi = lo + len(scale["options"]) - 1
    total = 0
    for i in range(1, len(scale["items"]) + 1):
        raw = t0_answers.get("T0_stait_%d" % i)
        if raw is None:
            return None
        score = int(raw) + lo
        if i in scale["reverse"]:
            score = (lo + hi) - score
        total += score
    return total


def stait_classification(total):
    """以 config.STAI_T_CUTOFF 为界，返回“高焦虑”/“低焦虑”；total 为 None 时返回 None。"""
    if total is None:
        return None
    return "高焦虑" if total >= config.STAI_T_CUTOFF else "低焦虑"

