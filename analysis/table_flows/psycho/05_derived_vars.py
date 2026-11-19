"""psycho 05：变量转换（中心化、标准化、取对数）与跨时间点差值。

功能：按登记做变量转换，新列直接补进 scores_wide.csv / scores_long.csv，并写 derived_report.txt。
来源：新写
KANO：基本型
确证性转换登记在 global_settings.TRANSFORMS，每次都算；设置区只用于探索时追加。
03 计分后会自动做确证性转换，改了设置区才需要单独跑 05；均值始终用全体被试（忽略 parameters.py 的 subjects）。
差值仅进宽表；03 重跑后需再运行 05 恢复设置区追加的转换与差值。
输入：data/<数据集>/processed/psycho/scores_wide.csv、scores_long.csv（03 的输出）
输出：同目录 scores_wide.csv、scores_long.csv（覆盖）、derived_report.txt
实现在 analysis/tools/psycho_derive.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from psycho_derive import apply_transforms

# ================= 设置区 =================
# 探索用的追加转换。source 须是 03 的基础列；method 代号：
#   "center"：总均值中心化（后缀 _c），减去全体被试的均值
#   "z"：标准化（后缀 _z），减去全体被试的均值后除以标准差（ddof = 1）
#   "ln"：自然对数（后缀 _ln），≤ 0 的值留空
EXTRA_TRANSFORMS = [
    # 探索用的追加转换，例：{"source": "T3_msbs_mean", "method": "z"},
]
# 跨时间点差值：name = minuend（被减数）- subtrahend（减数）。
# 源列须为 03 的数值基础列；任一缺失则留空，仅进宽表，保留 3 位小数。
# STAI 使用 20–80 折算分；正值分别表示诱导后提升、干预后恢复，负值照实保留。
EXTRA_DIFFERENCES = [
    {"name": "stai_t2t1_dif", "minuend": "T2_stai6_x20", "subtrahend": "T1_stai6_x20"},
    {"name": "vas_t2t1_dif", "minuend": "T2_vas", "subtrahend": "T1_vas"},
    {"name": "stai_t2t3_diff", "minuend": "T2_stai6_x20", "subtrahend": "T3_stai6_x20"},
    {"name": "vas_t2t3_diff", "minuend": "T2_vas", "subtrahend": "T3_vas"},
    {"name": "msbs_t3t1_diff", "minuend": "T3_msbs_mean", "subtrahend": "T1_msbs_mean",},
]
# ==========================================


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_psycho").PARAMETERS
    try:
        apply_transforms(parameters["dataset"], EXTRA_TRANSFORMS, EXTRA_DIFFERENCES)
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
