# 数据生成与数据实验工程

## 原理

本工程服务两类工作。table_flows 将原始数据生成可供 JASP、SPSS 等软件使用的最终分析表；data_lab 用于研究清理方法、检验指标、描述数据、快速分析及定制展示。两类工作共用已经确定的基础工具，但实验中的候选方法不能自动成为正式制表方法。

日常只需修改并保存 01_parameters.py，再打开 02_run.py 点击 VS Code 的 Run Python File。00_settings.py 保存已经同意的固定规范；新增科学方法或修改字段含义，仍须先讨论并写入研究规范。根入口与命令行共用同一执行逻辑。

data 保存原始、处理、最终与补充数据；analysis 只放脚本；reports 保存描述统计结果、图和文字报告。处理后的数据表仍然属于 data，不能因为它是 CSV 就将其当作报告。

## 工程结构

```text
Nature-based Intervention/
├── 00_settings.py                  固定字段、路径、命名和任务依赖
├── 01_parameters.py                用户选择与可调参数
├── 02_run.py                       统一入口，通常只点击运行
├── requirements.txt
├── data/
│   ├── formal/
│   │   ├── raw/
│   │   ├── processed/
│   │   ├── final/
│   │   └── supplementary/
│   └── pilot_and_test/
│       ├── pilot/                  同样分为上述四类目录
│       └── logging_test/           同样分为上述四类目录
├── analysis/
│   ├── table_flows/                制表流程，仅预留，细节等预测试后确定
│   │   ├── track/
│   │   ├── psycho/
│   │   ├── physico/
│   │   └── integration/
│   ├── data_lab/
│   │   ├── track/
│   │   │   ├── processing/         核对、清理、格式转换等实验性处理
│   │   │   ├── description/        描述计算与绘图
│   │   │   ├── analysis/           快速检验、专门分析；当前预留
│   │   │   ├── report/             从同次结果组织文字与展示
│   │   │   └── deprecated/         被否决或放弃的工具，不参与运行
│   │   ├── psycho/                同样有上述五个目录
│   │   └── physico/               同样有上述五个目录
│   └── tools/                     公共操作与明确标注对象的底层适配器
├── reports/
│   ├── formal/<工作内容>/runs/<run_id>/
│   ├── pilot_and_test/track/
│   │   ├── runs/<run_id>/          本次描述表、图与报告
│   │   └── checks/                工程检查结果
│   └── _runtime_cache/             绘图库缓存
└── 研究思路/                       科学依据与已经同意的研究规范
```

track 表示虚拟自然行为记录，psycho 表示问卷，physico 表示生理测量。table_flows 的前三个对象流程以生成表为目标，原则上包含载入、清理、指标计算、制表；integration 负责补充信息、协调对象流程及合并长表与宽表。共同的被试 ID 和时间格式是对齐要求，具体表结构、同步办法与指标细节待预测试后确定，当前不创建虚假的可运行实现。

data_lab 的二级目录按对象划分，第三级按 processing、description、analysis、report 划分。这四个环节不是每项实验都要完整执行的强制流水线。例如记录描述可以完成必要清理、描述和报告，不必先做回归。当前 Track 报告文字已独立放在 report/，读取同次描述结果，不另算一套数值。

deprecated 是“弃用工具”的目录。废弃源码留作判断依据，不作为新任务的依赖或可选实现；任务登记验证会拒绝此目录。弃用工具时，应在文件开头写明原因、日期及替代工具；没有替代工具时明确写明。历史报告、工程备份属于 reports 中的 archive，与废弃源码的用途不同。

## 共用工具与重复代码

对象目录负责研究含义：选择什么字段、什么时间段、怎样分类、采用什么方法、怎样解释结果。tools 负责可以独立说明的基础操作，例如路径、序列化、表格排版、绘图样式和保存。

共用工具按实际使用逐步提取。第二个真实使用场景出现时，先比较输入、输出、计算含义和异常处理；这些部分相同，才提取公共函数。允许少量短暂重复，不为尚未获得的问卷和生理数据预造通用框架。

例如，两类数据都使用带分组颜色的折线图时，可以共用画线、图例和导出操作；时间单位转换、分组依据、误差条计算和缺失值处理仍由对象代码决定。若只是图形长得相似、统计含义不同，应保留各自的实现。

已有公共函数不在新脚本中复制。对象工具优先组合公共函数，仅保留参数映射和对象规则。tools 不反向依赖对象分析脚本；调度器按固定登记加载任务、工程检查加载被测脚本是明确的调度用途。不同对象之间不直接借用对方的分析脚本。跨 table_flows 与 data_lab 使用的对象适配器也可放 tools，但须保留对象前缀，例如 track_io.py，不能伪装成适用于全部对象的读取器。

脚本采用“对象_动作.py”，例如 track_describe.py、track_clean.py。对象无关的工具用功能名，如 plotting.py、artifacts.py。不以被试编号、数据集名称、日期或 v2 命名共用分析工具。新增工具先检查现有接口，必要时将原使用者一并改为调用公共实现，避免“提取后旧副本仍各算各的”。

## 固定规范与日常参数

| 位置 | 内容与使用方式 |
|---|---|
| 00_settings.py | 固定字段、类型、单位、分类、历史值映射、路径及任务依赖。日常不改。 |
| 01_parameters.py：RUN | 工作空间、任务组合、数据范围与会话筛选。 |
| 01_parameters.py：COMMON | 共用语言、图格式、分辨率和字体。 |
| 01_parameters.py：DATA_LAB.track.description | 当前 Track 描述的时间分箱、分位数与配色。 |
| 02_run.py | 读取参数、检查选择、执行任务；通常无需修改。 |

参数按工作空间、数据对象、具体环节组织。只登记已经实现并有说明的参数，不提前堆放未来计分、切窗或指标阈值。原始采样间隔与描述图分箱宽度含义不同：前者是采集规范，后者是展示参数。

七表定义暂沿用固定设置中的 APP_SCHEMA、APP_COLUMNS 等内部名称；它们是唯一字段依据，未因目录迁移改变。用户可见的对象名和任务名统一使用 Track、track_*。现有数据的 raw/app、processed/app、questionnaire、physio 物理目录保留，通过 DATA_SOURCE_FOLDERS 映射到新对象名，避免改动原始数据和历史引用。用户无需在脚本中手工改路径。

## 运行选项与两种执行方式

| 参数 | 可选值 | 含义 |
|---|---|---|
| workspace | data_lab | 当前可执行的数据实验。 |
| workspace | table_flows | 仅预留；选择后会在写出结果前提示尚未实现。 |
| tasks | track_describe | 记录描述模板：自动包含核对、历史值清理和格式统一，生成描述、图与报告。 |
| tasks | track_inventory | 仅核对原始文件。 |
| tasks | track_clean | 核对后清理已定历史取值。 |
| tasks | track_format | 核对、清理后统一类型；这是标准输入表，不是最终研究分析表。 |
| dataset | logging_test / pilot / formal | 开发测试 / 被试预实验 / 正式实验数据范围。 |
| sessions | ["*"] / ["sub-P999*"] / ["具体会话名"] | 全部 / 通配符筛选 / 单场；也可填写多个模式。 |
| modules | Interactive / Practice / Passive | 自由交互 / 练习 / 被动观看模块，不是实验组别。 |

完整选项说明同时写在参数旁，不要求用户记忆英文。Practice、Passive 当前按规范只有会话信息，筛选它们不会补出未记录的操作数据。

在 VS Code 打开根目录 01_parameters.py，修改并保存后，打开 02_run.py 点击 Run Python File。默认任务是对 logging_test 中全部 Interactive 会话做记录描述。只看一场时，将 sessions 改为 ["sub-P999_ses-S001_mod-Interactive_run-002"]。时间分箱位于 DATA_LAB["track"]["description"]["time_bin_seconds"]。

命令行只是另一种入口，临时选项覆盖本次运行，不回写参数文件：

```bash
python3 02_run.py
python3 02_run.py --list
python3 02_run.py --tasks track_describe --dataset logging_test
python3 02_run.py --tasks track_describe --sessions sub-P999_ses-S001_mod-Interactive_run-002 --time-bin-seconds 30
python3 02_run.py --tasks track_clean
python3 analysis/data_lab/track/description/track_describe.py --sessions 'sub-P999*'
```

单独运行可执行工作脚本时，默认选择该脚本任务，其余设置仍来自 01_parameters.py，并通过同一调度器补齐依赖。工具模块及 track_report.py 等结果组织函数由任务调用，不是独立的用户任务。

当前需要 Python 3.10+ 与 requirements.txt 中的依赖。VS Code 应选择已装依赖的解释器。工作目录不必是项目根目录，路径从固定设置解析。运行 01_parameters.py 只显示操作提示，不执行分析。

## 输入、输出与复现

当前记录描述的内部步骤标识仍为 01_import → 02_clean → 03_format → 06_analysis；它们用于任务依赖与处理目录，不再代表 analysis 的一级文件夹。前面三步在 processing/，描述在 description/，文字组织在 report/。没有增加新的指标计算或正式制表步骤。

清理和格式转换的副本写入 data/<数据集根>/processed/<物理来源目录>/data_lab/<run_id>/；正式制表今后使用独立位置，避免把探索中的候选处理误作已定流程。新报告写入 reports/<formal 或 pilot_and_test>/track/runs/<run_id>/。报告按工作内容分类，不在其中再创建 logging_test 或 pilot 数据集目录。

每次运行新建目录，保存输入与脚本 SHA-256、参数和固定规范快照、依赖版本与运行状态。报告有 index.md 和分会话报告，manifest 指向同次处理数据。只核对或清理时不创建报告目录。raw 只读；缺文件与存在但零行的表分开说明，None 字面值仅在规范指定的字段中转换，不按缺失值自动吞掉。

工程检查位于 analysis/tools/track_check.py，结果写入 reports/pilot_and_test/track/checks/。空间描述必须出图，引用数值须写明表与字段，事实、离线分类与结合访谈的解释分开。日志不能直接证明兴趣、无聊、注意或动机。网格覆盖率不用于被试排名。

analysis 只放脚本，处理数据放 data，结果放 reports，不将分析产物放 /tmp。原有报告及工程备份仍位于 reports/pilot_and_test/app/ 下，原文件与历史清单不改写；该旧路径不是新结果的输出位置。尚未开展原两份描述的对照评估。
