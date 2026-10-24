"""track 制表流程的本地参数；不供 data_lab 读取。

当前仅预留流程结构，具体清理、指标和制表参数待预测试后确定。
dataset：pilot=被试预实验；formal=正式数据；test=开发测试。
修改并保存后，在本目录 02_run.py 点 Run；当前会明确提示尚未实现。
"""
PARAMETERS = {
    "dataset": "pilot",
}
