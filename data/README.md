# 数据

正式数据在 formal/；预实验与开发测试在 pilot_and_test/ 下各自的数据集中。每个数据集均分为 raw/（原始输入，只读）、processed/（按数据性质划分的多阶段处理数据）、final/（最终分析表）、supplementary/（分组、被试表与其他补充信息）。

工程中的对象名称统一为 track、psycho、physico。现有物理目录 app、questionnaire、physio 暂时保留，由根目录 00_settings.py 的 DATA_SOURCE_FOLDERS 映射，避免移动原始记录、破坏历史引用。脚本通过 analysis/tools/paths.py 定位，不自行拼接旧目录名。

当前数据实验的清理与格式表写到 processed/app/data_lab/<run_id>/ 下；此前 processed/app/<run_id>/ 中的结果保留。清理与格式化不是报告，标准化七表也不是最终研究分析表。table_flows 的四个制表流程只预留结构，待预测试后确定细节；final 目前仍预留。

描述统计表、图与文字报告写入项目根目录 reports/，按正式/测试与工作内容分类，不按输入数据集建报告文件夹。新 Track 结果位于 reports/pilot_and_test/track/ 或 reports/formal/track/。输入数据集、参数与处理路径记录在每次运行清单中。

完整规范见项目根目录 README.md。日常修改并保存 01_parameters.py，再在 02_run.py 点击 Run；也支持命令行覆盖。原始字段与历史取值规范不因工程目录调整而变化。
