"""推荐入口，支持 VS Code 点 Run 和命令行两种方式。

VS Code：先修改并保存同目录 01_parameters.py，再运行本文件，无需输入命令。
命令行：python3 02_run.py --tasks track_describe --dataset logging_test
日常不修改 00_settings.py 或分析脚本；运行结束会显示可打开的报告索引路径。
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from importlib import import_module
settings = import_module("00_settings")
sys.path.insert(0,str(settings.TOOLS_DIR))
from pipeline import cli

def main():
    return cli()

if __name__=="__main__":
    main()
