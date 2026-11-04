"""psycho 02：各被试问卷合并为长宽表。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 02_merge_questionnaires.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
输入（只读）：data/<数据集>/raw/psycho/sub-P###/questionnaires.csv、
    questionnaires_codebook.csv（不进入下划线开头的文件夹）
输出：data/<数据集>/processed/psycho/
    items_wide.csv、items_long.csv、items_codebook.csv、items_report.txt
实现在 analysis/tools/psycho_merge.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from psycho_merge import run


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_psycho").PARAMETERS
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"))
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
