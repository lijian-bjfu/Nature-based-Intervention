# 数据实验

## 原则：先研究，再整理

data_lab 是探索性工作，事先无法确定探索会走哪条路、得出什么，因此不预设路径。按对象（track、psycho、physico）和环节（processing、description、analysis、report）分两级之后，**一个文件夹对应一个研究问题**，其下不再预设子目录：

- 本问题用到的**脚本**直接放在该文件夹下。
- **README.md**：总结性描述——要处理什么问题、用什么方法、得出什么结论。问题和方法开始时就写，结论在探索结束后补。
- **log.md**：研究过程日志——每次有进展时记下试了什么、为什么试、看到了什么、下一步打算。写给人读，不是程序流水。
- **results/**：最近一次运行的结果，每次运行覆盖，不按时间建文件夹。报告写给研究者读：先写发现，再附表和图。
- **save/**：研究者认可、要保留的结果，手动从 results/ 复制进来，按含义命名（如 save/清理方案A/）。它是日后晋升的依据。
- 每次运行的参数、Git 提交号等追溯信息自动写在 results/_provenance/，平时不用打开。

results/ 与 save/ 只存本机，不入库；脚本、README.md、log.md 入库。

## 晋升

探索中确认的方法或指标，经研究讨论后：定义写进研究文档（埋点指标写进《研究思路/实验记录-埋点.md》）并登记到 global_settings.py 的 METRICS；计算代码移到 analysis/tools/，供 table_flows 调用。save/ 中保留支持这次决定的结果。

## 其他约定

实验只复用 global_settings.py 中的原始规范和已确认指标定义，不读取 table_flows 参数。参数写在入口脚本顶部 PARAMETERS，保存后在 VS Code 点 Run。清理、格式化等供后续使用的数据放项目 data/.../processed，最终分析表放 data/.../final。

活跃脚本的 SCRIPT_HISTORY 保留带时区的创建或重要修改记录；analysis/tools/lab_history.py 可按时间检索（生成的 history_index.csv 只存本机）。

## 当前的研究问题

- track/description：埋点原始记录的描述。入口 track_describe.py。
