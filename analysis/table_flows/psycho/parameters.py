"""psycho 制表流程的本地参数；不供 data_lab 读取。

dataset：pilot=被试预实验；formal=正式数据；test=开发测试。
subjects：要处理的被试。
    "*"          处理全部被试（raw/psycho/ 下所有 sub-P### 文件夹，下划线开头的文件夹跳过）
    ["P001"]     只处理列出的被试，可写多个，如 ["P001", "P002"]
修改并保存后，在本目录 01_completeness_check.py 点 Run。
"""
PARAMETERS = {
    "dataset": "formal",
    "subjects": "*",
}
