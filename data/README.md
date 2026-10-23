# 数据

正式数据在 formal/；预实验与开发测试在 pilot_and_test/ 下各自的数据集中。每个数据集分为 raw/（只读原始输入）、processed/（按数据性质划分的多阶段处理数据）、final/（最终分析表）和 supplementary/（分组、被试表、编码等补充信息）。

对象名称统一使用 track、psycho、physico。已经存在的物理目录 app、questionnaire、physio 暂时保留，由 analysis/tools/paths.py 映射，不为代码改名移动原始数据。共享原始字段、标签与单位见根目录 global_settings.py，埋点读写统一使用 analysis/tools/track_io.py。

当前记录描述实验的清理和格式表写到 processed/app/data_lab/record_description/<run_id>/；此前的处理结果保留。标准化七表不是最终研究分析表。table_flows 尚未实现，具体流程及参数等待预测试后确定，final 目前仍预留。

描述统计表、图和文字报告跟随具体工作，当前位于 analysis/data_lab/track/description/record_description/outputs/，不再使用根目录 reports。实验选择与候选参数在当前入口脚本中调整，不读取 table_flows 的 01_parameters.py。各制表流程将来只使用自己目录内的参数和入口。

原始数据、处理数据、展示结果由运行编号及 manifest 关联。完整使用说明、时间追溯和 Git 约定见项目根目录 README.md。
