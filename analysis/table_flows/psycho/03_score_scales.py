"""psycho 03：量表计分（反向计分、分量表合计/均分、STAI-T 分类），并与组别拼合。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 03_score_scales.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
输入（只读）：data/<数据集>/processed/psycho/items_wide.csv（工具 02 的输出）、
    data/<数据集>/raw/session_notes/sub-P###/log.csv（只取 group_code、group、stait_total）
    计分参数来自 table_flows/psycho/psycho_schema_draft.py 的 PSYCHO_METRICS。
输出：data/<数据集>/processed/psycho/
    scores_wide.csv（每位被试一行）、scores_long.csv（每位被试 × T1/T2/T3 一行）、
    scores_report.txt（中文报告，含 STAI-T 校验结果）
实现在 analysis/tools/psycho_score.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from psycho_score import run

# ================= 设置区 =================
# 矩阵题的选项数（存的是选项下标，0 起）。与 table_flows/psycho/psycho_schema_draft.py 定义一致；
# 运行时会与 PSYCHO_SCHEMA 的 levels 逐项核对，不一致就报错退出。
OPTION_COUNTS = {
    "stait_total": 4,   # STAI-T（20 题）：4 个选项
    "stai6_total": 4,   # STAI-6（6 题）：4 个选项
    "cns_total": 5,     # CNS 自然联结（14 题）：5 个选项
    "msbs8_total": 7,   # MSBS-8 状态无聊（8 题）：7 个选项
}
# ==========================================


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_psycho").PARAMETERS
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"), OPTION_COUNTS)
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
