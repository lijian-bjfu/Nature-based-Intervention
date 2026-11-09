"""06 清理后 RR 预览图：只画图，不改任何数据。

在 VS Code 中打开本文件点 Run，或在终端运行：python3 06_rr_clean_preview.py
参数读取同目录 parameters.py 的 PARAMETERS["dataset"] 与 PARAMETERS["subjects"]。
输入（只读）：data/<数据集>/processed/physio/sub-P###/clean/（rr.csv、holes.csv，由工具 05 生成）
    以及同目录下 merged/（rr.csv、markers.csv、segments.csv）
输出：data/<数据集>/processed/physio/preview/signal/P###_rr_clean.png（每人一张，覆盖旧图）
    原始 RR 浅灰，清理后 RR 按处置类型着色；丢包空洞浅红底、段间空档灰底；按标记画五个阶段背景带。
实现在 analysis/tools/physio_rr_preview.py。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p / "global_settings.py").is_file())
sys.path[:0] = [str(PROJECT), str(PROJECT / "analysis"), str(PROJECT / "analysis/tools")]

from workflow import load_script
from physio_rr_preview import run

# ================= 设置区 =================
# 纵轴范围："clip" 按 handling≠4 的拍确定范围（上下各留 5%），超出的点画成边缘三角形（默认）；
# "full" 显示全部数据。
YAXIS_MODE = "clip"
# ==========================================


def main():
    parameters = load_script(Path(__file__).with_name("parameters.py"), "parameters_physio").PARAMETERS
    try:
        run(parameters["dataset"], parameters.get("subjects", "*"), {"YAXIS_MODE": YAXIS_MODE})
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
