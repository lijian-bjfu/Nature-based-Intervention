"""integration 制表入口：读取同目录 01_parameters.py，支持 VS Code Run 与命令行。

此流程尚未实现，不会把实验性处理当作正式制表输出。
未来由本入口协调 track / psycho / physio 流程、补充信息并合并长表与宽表。
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT),str(PROJECT/"analysis/tools")]
from table_flow import cli, run_flow
from workflow import load_script

def run(parameters=None):
    if parameters is None:
        parameters = load_script(Path(__file__).with_name("01_parameters.py"),"parameters_integration").PARAMETERS
    return run_flow("integration",parameters)

if __name__ == "__main__":
    raise SystemExit(cli("integration",Path(__file__).with_name("01_parameters.py")))
