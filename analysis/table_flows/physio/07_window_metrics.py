"""07 窗口指标：按 03 的窗口表取 05 清理后的 RR，每人每窗口算质量与 HRV 指标，输出长表与宽表

在 VS Code 中打开本文件点 Run，或在终端运行：python3 07_window_metrics.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
来源：新写；口径见 global_settings.METRICS["physio"]（研究思路/分析工具迁移与整合工作计划.md 窗口指标口径）
输入（只读）：data/<数据集>/processed/physio/sub-P###/events/windows.csv（工具 03）、clean/rr.csv（工具 05）
输出：data/<数据集>/final/physio/window_metrics_long.csv、window_metrics_wide.csv、window_metrics_report.txt（整表重算并覆盖）
实现在 analysis/tools/physio_metrics.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from physio_metrics import run


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_physio").PARAMETERS
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"))
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
