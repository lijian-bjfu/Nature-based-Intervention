"""integration 04：按 global_settings.INTEGRATION_SHORT_TABLES 从 03 的整表排除固定字段及训练阶段，生成简表。不计算。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 04_short_tables.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"]；本流程总是处理全部被试。
输入（只读）：data/<数据集>/final/integration/ 下 03 生成的 wide.csv、long.csv
输出：data/<数据集>/final/integration/
    wide_short.csv、long_short.csv、short_report.txt（每次整表重写）
固定排除字段与排除窗口登记在 global_settings.INTEGRATION_SHORT_TABLES；改取舍只改那里，不另维护映射文件。
未登记的新列（包括计算列）默认保留，列序沿用来源表。
宽表保留全部被试，长表仅去掉训练行；不改数值、不按 ok 筛数据、不生成诊断简表。
生理纳入以人工审查为准；本工具不执行人工判断，完整版及上游文件只读。
实现在 analysis/tools/short_tables.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from short_tables import run


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
