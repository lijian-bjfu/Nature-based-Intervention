"""03 套用人工更正表并体检事件。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 03_events_edit.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
输入（只读）：data/<数据集>/processed/physio/sub-P###/merged/markers.csv
    data/<数据集>/corrections/physio_events.csv（人工更正表，只读；不存在视为没有更正）
输出：data/<数据集>/processed/physio/sub-P###/events/markers.csv、report.txt、windows.csv
    （windows.csv 为窗口表：按阶段顺序每阶段一行，含起止时刻、时长、valid、issue 与 note；每次覆盖。
     valid=0 只表示窗口无法确定（缺失、重复、顺序冲突）；时长偏差写在 note，只是提示，不影响 07 计算）
    更正表套用出错时：该被试已有的 events/ 经 safe_io.retire_dir 移到 _to_delete/，并在 events_check.csv 记 error
    data/<数据集>/processed/physio/events_check.csv（每人一行，重跑只替换本次被试的行）
实现在 analysis/tools/physio_events.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from physio_events import run

# ================= 设置区 =================
DURATION_TOL_S = 30   # 阶段时长与标准时长相差超过多少秒时给出提示；只提示人核对，不判窗口无效、不丢数据
# ==========================================


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_physio").PARAMETERS
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"), {"DURATION_TOL_S": DURATION_TOL_S})
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
