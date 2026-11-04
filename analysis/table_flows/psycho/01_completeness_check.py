"""psycho 01：问卷完整性检查（未提交、缺答、全同选项、作答过快）。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 01_completeness_check.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
输入（只读）：data/<数据集>/raw/psycho/sub-P###/questionnaires.csv、state.json（不进入下划线开头的文件夹）
输出：data/<数据集>/processed/psycho/preview/check/
    completeness.csv（所有被试合表）、completeness_report.txt
实现在 analysis/tools/psycho_check.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from psycho_check import run

# ================= 设置区 =================
# 每题平均用时（秒）：用时（submitted_at − started_at）÷ 该问卷 answers 的条数。
# 低于此值记为作答过快（too_fast=yes）。
MIN_SEC_PER_ITEM = 1.0
# 量表块的题数不少于此数时，才检查是否全选同一选项（straightline）。
STRAIGHTLINE_MIN_ITEMS = 5
# ==========================================


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_psycho").PARAMETERS
    cfg = {
        "MIN_SEC_PER_ITEM": MIN_SEC_PER_ITEM,
        "STRAIGHTLINE_MIN_ITEMS": STRAIGHTLINE_MIN_ITEMS,
    }
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"), cfg)
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
