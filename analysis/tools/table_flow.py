"""尚未实现的制表流程入口约定；不借用 Lab 方法冒充正式流程。"""
from pathlib import Path
import argparse
import sys
from paths import DATASETS
from workflow import load_script

FLOW_LABELS = {"track": "虚拟自然行为制表", "psycho": "问卷制表",
               "physico": "生理制表", "integration": "补充信息与流程整合"}

def run_flow(name, parameters):
    """统一的流程调用接口；获得预测试数据并确定规范后再实现具体生产流程。"""
    if name not in FLOW_LABELS:
        raise ValueError(f"未知流程 {name}")
    if parameters["dataset"] not in DATASETS:
        raise ValueError(f"dataset 应为 {tuple(DATASETS)}")
    raise NotImplementedError(f"{FLOW_LABELS[name]}尚未实现；等待预测试后确定细节，未生成数据或报告。")

def cli(name, parameter_file, argv=None):
    parser = argparse.ArgumentParser(description=FLOW_LABELS[name]+"（结构预留）")
    parser.add_argument("--dataset", choices=tuple(DATASETS), default=None)
    parser.add_argument("--list", action="store_true", help="显示流程状态，不执行")
    args = parser.parse_args(argv)
    if args.list:
        print(FLOW_LABELS[name]+"：结构预留，尚未实现。")
        print("本地参数："+str(parameter_file))
        return 0
    module = load_script(Path(parameter_file),"nbi_parameters_"+name)
    parameters = dict(module.PARAMETERS)
    if args.dataset is not None:
        parameters["dataset"] = args.dataset
    try:
        return run_flow(name,parameters)
    except (ValueError,NotImplementedError) as error:
        print(str(error),file=sys.stderr)
        return 2
