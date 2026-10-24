# 制表流程

track、psycho、physio 分别将对应原始数据生成最终分析表；integration 将来协调流程、补充信息并合成长表与宽表。流程结构暂定，获得预测试数据后再确定具体清理、指标与表结构。

每个流程有自己的 01_parameters.py 和 02_run.py。日常只改本地参数、保存并在本地入口点 Run；也支持命令行覆盖。integration/02_run.py 是今后整合任务的入口，项目根目录不设总运行器。这些参数不供 data_lab 读取。

track 已实现：02_run.py 读取 01_parameters.py 的数据集、被试与 runs，调用 analysis/tools/track_metrics.py 计算《实验记录-埋点》§十 的全部指标，输出到 data/<数据集>/final/track/（track_metrics.csv 指标宽表、track_dwells.csv、track_ap.csv、track_areas.csv、track_per_minute.csv、track_columns.csv 列名对照、_provenance/）。场景可达范围由景观标注计算，整场景只算一次。

psycho、physio、integration 尚未实现。入口的 --list 可查看状态；真正执行会明确提示尚未实现，以非零状态结束，不生成数据或报告。共享原始规范来自 global_settings.py，不把 Lab 的候选方法直接当成正式生产流程。

处理数据归入 data/processed，最终分析表归入 data/final；将来的过程观察与文字结果可放各流程自己的 outputs。报告细节当前不预造。
