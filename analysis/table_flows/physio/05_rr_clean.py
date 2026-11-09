"""05 H10 RR 伪迹清理（只出数据，图由 06 画）

在 VS Code 中打开本文件点 Run，或在终端运行：python3 05_rr_clean.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
来源：新写；识别与校正采用 Lipponen & Tarvainen (2019)（neurokit2.signal_fixpeaks, method="kubios"）
输入（只读）：data/<数据集>/processed/physio/sub-P###/merged/rr.csv
输出：data/<数据集>/processed/physio/sub-P###/clean/rr.csv、holes.csv、changes.csv（对原始数据的修改清单）、report.txt
      data/<数据集>/processed/physio/rr_clean_summary.csv（每人一行）
handling 编码：0 原样保留、1 漏检补拍、2 多检合并、3 异位搏或长短拍校正、4 待人工（仍异常，未修改）
实现在 analysis/tools/physio_rr_clean.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from physio_rr_clean import run

# ================= 设置区 =================
# 丢包判定（毫秒）：相邻两拍的时间差比这一拍的 RR 多出超过此值，视为中间丢了拍（记为空洞，只标记不填补）。
# 调大：更少的缺口被认定为丢包，缺口留在片段内由校正当作漏检处理；调小：更敏感，片段被切得更碎。
GAP_EXCESS_MS = 250
# 两个空洞之间少于此拍数的片段不做校正（原样输出）。
# 调大：更多短片段被放弃校正；调小：短片段也交给校正，但统计依据不足，容易误判。
MIN_SEG_BEATS = 30
# 校正后复查用的滚动中位数窗口（拍，中心对齐）。
# 调大：局部中位数更平滑，对短时心率变化更敏感；调小：更贴近局部，但容易被相邻异常拍拉偏。
RESIDUAL_WIN = 11
# 校正后 RR 偏离局部中位数超过此比例，记为待人工（handling=4，数值不改）。
# 调大：待人工的拍更少；调小：更严格，待人工的拍更多。
RESIDUAL_REL = 0.30
# 整数倍切分预处理（在 Kubios 之前，对全部原始 RR 含短片段逐拍判断；识别"漏了几拍合成一个 RR"）：
# 参考 RR = 该拍前后各这么多秒内原始 RR 的中位数（跨片段取，不受空洞切段影响）。
# 调大：参考更平稳，但心率变化快时参考滞后；调小：参考更贴近局部，但窗内拍数少时不稳。
MULTI_REF_WINDOW_S = 30
# 最多认为漏了几拍合成一个 RR（k 的上限）。调大：能切分更长的漏拍，但误切风险增大；调小：只处理短漏拍。
MULTI_MAX_K = 5
# |RR / (k × 参考) − 1| 小于此值才切分。调大：更多 RR 被切分，误切风险增大；调小：只切分非常接近整数倍的 RR。
MULTI_TOL = 0.15
# ==========================================


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_physio").PARAMETERS
    cfg = {"GAP_EXCESS_MS": GAP_EXCESS_MS, "MIN_SEG_BEATS": MIN_SEG_BEATS,
           "RESIDUAL_WIN": RESIDUAL_WIN, "RESIDUAL_REL": RESIDUAL_REL,
           "MULTI_REF_WINDOW_S": MULTI_REF_WINDOW_S, "MULTI_MAX_K": MULTI_MAX_K, "MULTI_TOL": MULTI_TOL}
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"), cfg)
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
