# 数据实验

本目录按 track、psycho、physico 分对象，分别设置 processing、description、analysis、report 和 deprecated。具体工作在对应环节下建立自己的目录，参数随工作设置，不存在全 Lab 固定参数文件。

当前可执行入口是 track/description/record_description/track_describe.py。修改其顶部 PARAMETERS，保存后直接在 VS Code 点 Run；命令行也调用同一入口。实验只复用 global_settings.py 中的原始规范和已确认指标定义，不读取 table_flows 参数。

图、描述统计表及文字放在工作的 outputs 中，并区分 formal、pilot_and_test；清理、格式化等后续可用数据仍放项目 data/processed，最终分析表放 data/final。

活跃脚本的 SCRIPT_HISTORY 保留带时区的创建或重要修改记录。原始创建时间无法核实的旧脚本明确标为未知，不以首次提交时间冒充创建时间。运行 analysis/tools/lab_history.py 可生成本目录 history_index.csv，按时间检索脚本的变化。Git 提供内容版本；运行记录保存提交号，并只复制当次未提交的源码，两者用途互补。data_lab 的脚本入库，outputs 与 archive 只存本机。

具体方法经确认后，先写研究规范，再登记共享指标并进入制表流程。公共工具按真实重复需求提取；废弃源码保留原因、时间和替代关系，不作为运行依赖。
