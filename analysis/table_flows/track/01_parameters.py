"""track 制表流程的本地参数；不供 data_lab 读取。

改完保存，在本目录 02_run.py 点 Run。
  dataset：pilot=预实验，formal=正式实验，test=开发测试。
  subjects："*" 表示这个数据集里的全部被试；也可写一个编号或一组编号，如 ["P041", "P042"]。
  runs：同一被试有多份实验条件记录时（例如测试中重跑），在这里指明用哪一份，如 {"P000": "004"}；
        没写而又有多份时，流程会停下并列出可选项，不会自己挑。
指标的口径与参数不在这里改：它们登记在 global_settings.METRICS["track"]，定义见《研究思路/实验记录-埋点.md》第十节。
"""
PARAMETERS = {
    "dataset": "pilot",
    "subjects": "*",
    "runs": {},
}
