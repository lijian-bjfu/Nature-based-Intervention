"""physio 01：把 xdf 拆成 csv，并做结构体检。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 01_xdf_to_csv.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
输入：data/<数据集>/raw/physio/sub-P###/*.xdf（不进入 _excluded/）
输出：data/<数据集>/processed/physio/sub-P###/<xdf 文件名去掉 .xdf>/
    ecg.csv、acc.csv、hr.csv、rr.csv、markers.csv、gaps.csv、udp_clock.csv、header.json、report.txt
实现在 analysis/tools/physio_xdf.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from physio_xdf import run


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
