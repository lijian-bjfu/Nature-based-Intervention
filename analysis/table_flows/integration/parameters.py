"""integration 制表流程的本地参数；不供 data_lab 读取。

dataset：pilot=被试预实验；formal=正式数据；test=开发测试。默认 formal。
本流程总是处理全部被试（以 raw/session_notes 的流程单名单为准），不设 subjects。
修改并保存后，在本目录 03_merge_tables.py 点 Run。
"""
PARAMETERS = {
    "dataset": "formal",
}
