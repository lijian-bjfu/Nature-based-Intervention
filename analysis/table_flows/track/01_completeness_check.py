"""track 01：埋点完整性检查入口。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 01_completeness_check.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
输入（只读）：data/<数据集>/raw/track/sub-P###/ 下的记录文件夹（不进入下划线开头的文件夹）
输出：data/<数据集>/processed/track/preview/check/
    track_completeness.csv、track_completeness_subjects.csv、track_completeness_report.txt
实现在 analysis/tools/track_completeness.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from track_completeness import run

# ================= 设置区 =================
# 实验条件（Interactive、Passive）记录的最短时长，单位分钟。
# 时长 = session 表的 t_device_end − t_device_start。短于此值的记录标为过短（flag=yes）。
MIN_INTERACTIVE_MIN = 10
# ==========================================


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_track_completeness").PARAMETERS
    cfg = {"MIN_INTERACTIVE_MIN": MIN_INTERACTIVE_MIN}
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"), cfg)
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
