"""integration 03：合并问卷与生理，生成wide.csv、long.csv，并保留两张分类型长表和数据字典。只合并，不计算。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 03_merge_tables.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"]；本流程总是处理全部被试（以流程单 raw/session_notes 的名单为准）。
输入（只读）：data/<数据集>/raw/session_notes/sub-P###/log.csv（名单与组别）、
    data/<数据集>/processed/psycho/scores_wide.csv、scores_long.csv、
    data/<数据集>/final/physio/window_metrics_long.csv
输出：data/<数据集>/final/integration/
    wide.csv、long.csv、psycho_long.csv、physio_long.csv、data_dictionary.csv、merge_report.txt（每次整表重写）
    文件名与结构读取global_settings.INTEGRATION_TABLES；long.csv每人五个阶段，问卷对应关系读取INTEGRATION_PHASE_TIMEPOINTS。
    合并长表：T1/T2/T3列按时点展开，仅long.person_column_prefixes指定的个人字段重复；
    其他宽表派生列（含跨时点差值）不自动带入，未带入列在merge_report.txt列出。
实现在 analysis/tools/integration_merge.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from integration_merge import run


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_integration").PARAMETERS
    try:
        run(parameters["dataset"])
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
