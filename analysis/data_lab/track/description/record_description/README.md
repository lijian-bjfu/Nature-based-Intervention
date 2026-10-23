# Track 记录描述实验

本工作描述记录中实际出现的环境接触、操作及系统反馈，用于了解交互过程和记录可用性；不从日志直接解释动机，也不新增正式行为指标。当前方法先核对数据，再呈现点击和触摸、受阻与转动、世界事件，以及时间和空间分布。

入口是本目录 track_describe.py。可调参数在顶部 PARAMETERS；experiment.py 只管理本项工作的校验、依赖、路径和复现记录。数据结构和标签读取根目录 global_settings.py，处理及报告函数分别位于 track/processing 与 track/report。

在 VS Code 修改、保存入口参数后点击 Run；命令行可以临时覆盖。默认读取 logging_test 中所有 Interactive 会话。结果在本目录 outputs 中按正式/测试分开，清理与标准表在项目 data/processed 中，二者通过 manifest 对应。

每次运行保存整次与各步骤的起止时间、参数、共享规范、输入校验值、Git 信息和完整源码快照。SCRIPT_HISTORY 记方法或工程的重要变化；修改本实验时追加历史条目。历史根 reports 原样迁到 archive，迁移清单保留路径与逐文件校验，未开展原两套描述的内容对照。
