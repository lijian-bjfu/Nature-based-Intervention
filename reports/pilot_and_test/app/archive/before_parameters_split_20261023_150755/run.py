"""根目录入口：VS Code 直接运行使用 settings.py 默认配置；也支持命令行选择。"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings
sys.path.insert(0, str(settings.TOOLS_DIR))
from pipeline import cli

if __name__ == "__main__":
    cli()
