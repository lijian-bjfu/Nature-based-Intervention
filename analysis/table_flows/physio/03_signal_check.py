"""03 RR、HR、ECG 绘图检查与质量报告。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 03_signal_check.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
输入（只读）：data/<数据集>/processed/physio/sub-P###/merged/
输出：data/<数据集>/processed/physio/preview/signal/
    P###_overview_raw.png、P###_rr_raw.png、P###_report_raw.txt、quality.csv（所有被试合表）
    RR_PAGES=True 时另有 P###_rr_raw_page_01.png …
实现在 analysis/tools/physio_check.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from physio_check import run

# ================= 设置区 =================
# RR 图纵轴显示的百分位范围（下限, 上限）。(0, 100) 表示显示全部数据（默认，用于看原始数据录成了什么样）；
# 改成如 (0.5, 99.5) 可以放大主体数据，但超出范围的点会落在图外看不见。
# 上下限按此百分位计算，上下各留 5% 余量。所选范围不是 (0, 100) 时，图标题末尾会注明 y-axis 范围。
RR_YAXIS_PERCENTILE = (0, 100)
# RR 低于此值（毫秒）记为超出范围。300 ms 对应心率 200 bpm。
RR_MIN_MS = 300
# RR 高于此值（毫秒）记为超出范围。2000 ms 对应心率 30 bpm。
RR_MAX_MS = 2000
# 相邻 RR 变化超过前一个 RR 的这个比例，记为可疑跳变（0.20 即 20%）。
RR_JUMP = 0.20
# ECG 采样率（Hz），用于计算每段期望的 ECG 样本数。
ECG_FS = 130
# RR 分页图每页的时长（分钟）。
RR_PAGE_MIN = 10
# 是否额外输出 RR 分页图（P001_rr_page_01.png 等）。False 时只输出全程 RR 图 P001_rr.png，不生成分页图。
RR_PAGES = False
# ==========================================


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_physio").PARAMETERS
    cfg = {
        "RR_MIN_MS": RR_MIN_MS,
        "RR_MAX_MS": RR_MAX_MS,
        "RR_JUMP": RR_JUMP,
        "ECG_FS": ECG_FS,
        "RR_PAGE_MIN": RR_PAGE_MIN,
        "RR_PAGES": RR_PAGES,
        "RR_YAXIS_PERCENTILE": RR_YAXIS_PERCENTILE,
    }
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"), cfg)
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
