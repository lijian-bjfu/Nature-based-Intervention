"""
流程单系统 · 启动入口

两种跑法都可以：
  1. VS Code 里打开本文件，点右上角的 Run（或 Shift+Enter）。
  2. 在 Terminal 里：
       cd 流程单系统
       python3 run.py      （Windows 上用 python run.py）

跑起来之后，按提示在浏览器打开 http://127.0.0.1:8765（端口在 config.py 里改）。
所有可调参数都在同目录的 config.py 里，改完重新启动即可生效。
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app"))

from server import run_server  # noqa: E402  (必须先插入上面的路径才能导入)

if __name__ == "__main__":
    run_server()
