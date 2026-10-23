# 数据

正式数据在 formal/；预实验与开发测试在 pilot_and_test/ 下各自的数据集中。每个数据集均分为 raw/（原始输入，只读）、processed/（按数据性质划分的多阶段处理数据）、final/（最终分析表）、supplementary/（被试表与其他补充数据）。

例如埋点的处理表写到 processed/app/<run_id>/ 下各处理阶段；未来问卷和生理数据分别使用 processed/questionnaire/、processed/physio/，可有不同的阶段。participants.csv 放在 supplementary/。当前 final 预留，最终表整理尚未实现。

描述统计表、图和文字报告写到项目根目录 reports/，按正式/测试与工作内容分类，不按数据集建报告文件夹。完整规范见 ../README.md，固定路径与字段规范见 ../00_settings.py；日常选择与展示参数在 ../01_parameters.py 修改，保存后打开根目录 02_run.py 点击 Run。也支持命令行临时覆盖。
