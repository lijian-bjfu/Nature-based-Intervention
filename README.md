# Nature-based Intervention：数据生成与数据实验

## 原理与职责

本工程包含两类工作。table_flows 将原始数据生成可供 JASP、SPSS 等软件使用的最终分析表；data_lab 用于比较清理方法、检验候选指标、描述数据、快速分析和定制展示。实验中效果较好的方法，须经过研究讨论并形成规范后，才能成为正式制表方法。

global_settings.py 是两类工作共同遵守的数据规范，主要描述原始表结构、字段、类型、标签、单位、命名和历史取值兼容。已确认的指标定义也逐项登记在这里。运行选择、实验候选参数、任务依赖、展示样式及结果路径不放入共享规范。

table_flows 各流程拥有本地 01_parameters.py 和 02_run.py。data_lab 不读取这些参数，也没有全 Lab 固定参数面板；具体实验在自己的入口脚本中设置参数，复杂实验可另设局部参数文件。根目录不再设置统一 parameters、run 或 reports。

## 目录结构

```text
Nature-based Intervention/
├── global_settings.py
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── formal/
│   │   ├── raw/
│   │   ├── processed/
│   │   ├── final/
│   │   └── supplementary/
│   └── pilot_and_test/
│       ├── pilot/                        同样分为上述四类目录
│       └── test/                         开发测试，同样分为上述四类目录
├── analysis/
│   ├── table_flows/
│   │   ├── track/                        01_parameters.py、02_run.py
│   │   ├── psycho/                       01_parameters.py、02_run.py
│   │   ├── physio/                       01_parameters.py、02_run.py
│   │   └── integration/                  01_parameters.py、02_run.py
│   ├── data_lab/
│   │   ├── README.md
│   │   ├── track/
│   │   │   ├── description/              一个研究问题：埋点原始记录的描述
│   │   │   │   ├── README.md             问题、方法、结论
│   │   │   │   ├── log.md                研究过程日志
│   │   │   │   ├── track_describe.py     入口，顶部有 PARAMETERS；本问题用到的其他脚本也直接放在这一层
│   │   │   │   ├── results/              最近一次结果，每次运行覆盖（本机）
│   │   │   │   └── save/                 研究者认可的结果，按含义命名（本机）
│   │   ├── psycho/                       尚无研究问题
│   │   └── physio/                       尚无研究问题
│   └── tools/                            通用操作及带对象前缀的适配器
└── 研究思路/                             科学依据与已同意的研究规范
```

track 表示虚拟自然行为，psycho 表示问卷，physio 表示生理测量。data_lab 的二级目录按对象划分，第三级是环节（processing、description、analysis、report）或弃用源码（deprecated）。环节文件夹不预先建立，出现这类研究问题时再建。

data_lab 的组织原则是**先研究，再整理**：一个文件夹对应一个研究问题，不预设子目录。本问题用到的脚本直接放在该文件夹下；README.md 总结问题、方法和结论；log.md 记录研究过程（试了什么、为什么、看到了什么）；results/ 只保留最近一次运行的结果，每次覆盖，不按时间建文件夹；研究者认可、要保留的结果手动复制到 save/，按含义命名，作为日后晋升为正式规范的依据。每次运行的参数、提交号等追溯信息自动写在 results/_provenance/，平时不用打开。results/ 与 save/ 只存本机，不入库。

analysis 现在可以保存本项工作的图表和文字，原先“analysis 只放脚本”的约定已更新。数据用途决定其位置：供后续处理使用的清理、格式转换、切窗及特征表放 data/processed；最终研究分析表放 data/final；用于展示处理效果或说明分析结果的描述表、图、文字放该研究问题的 results/（认可的放 save/）。不能仅按 CSV 文件格式判断它属于数据还是报告。

## 共享数据规范

[global_settings.py](global_settings.py) 中的 TRACK_SCHEMA 是埋点七表字段的唯一声明。TRACK_COLUMNS、TRACK_TYPES、TRACK_LEVELS 等索引由它生成；读写器通过这些索引取字段，不在各个实验中复制 columns。其他数据对象的原始格式获得并确认后，再加入相应规范，不预造尚未确定的字段。

共享规范保留 session、spacetime、tap、backstep、look、world_event、tech_glitch 七表，以及现有类型、单位、类别和必要文件规则。历史 None 按字段分别转换为 NoHit 或 NotBlocked，原始字符串读取时不作为空值吞掉。文件不存在与文件存在但零行必须区别报告。

METRICS 按 track、psycho、physio 分类，目前为空。经确认后，逐项登记指标名称、定义、输入字段、输出单位、计算口径和规范出处。计算函数仍放在适当的工具或流程中。候选指标、试验阈值和参数优劣比较留在 data_lab，不直接升级成全局规范。

埋点科学口径以《研究思路/实验记录-埋点.md》为依据。先讨论、写入规范，再改代码；代码依据文档实现，不依据对话记忆。APP 仅记录原始量，指标离线计算。日志字段须与实际判定函数同源，事实、离线分类、结合访谈与回放的解释分开，不能从行为日志直接推断兴趣、注意、无聊或动机。

## 制表流程的使用

table_flows 的前三个对象流程原则上包含载入、清理、指标计算和生成表单。integration 将来协调三个流程，加入分组、访谈编码等补充信息并生成长表与宽表。共同的被试 ID 和时间格式是数据对齐要求，具体细节等预测试数据到位后确定。

各流程的参数仅服务本流程。例如，研究者修改并保存 analysis/table_flows/track/01_parameters.py 后，在同目录 02_run.py 点 Run。整合任务的入口位于 analysis/table_flows/integration/02_run.py，根目录不再有总运行器。

**目前四个制表流程都只是结构预留。** 入口可以显示状态，但执行制表会明确提示尚未实现并以非零状态结束，不创建数据、报告，也不调用 Lab 描述充当制表。清理、切窗、计分、指标和合表参数待规范确定后再加入。未来需要的生成效果观察结果，可保存在对应流程自己的 outputs，当前不预先实现报告体系。

## data_lab 的使用

每个研究问题文件夹里的 README.md 说明该问题的运行入口、参数和结果，以那里为准。目前有一个：

- [analysis/data_lab/track/description/](analysis/data_lab/track/description/README.md)：埋点原始记录的描述。在 VS Code 打开 track_describe.py，修改顶部 PARAMETERS（数据集、要分析的那一份实验记录等），保存后点 Run，结果在同一文件夹的 results/。

入口同时支持命令行，命令行选项只覆盖当次运行，不回写脚本；`--list` 查看可选项。制表入口中的 --list 只是查看状态，不带 --list 执行时会说明尚未实现并停止。本机需 Python 3.10+ 和 requirements.txt 的依赖，在 VS Code 选择已装依赖的解释器即可。

## 数据与结果位置

### 数据命名规范（项目规范）

任何一份数据都由四个名字定位，制表和数据实验一律按此调用：

| 名字 | 含义 | 取值 |
|---|---|---|
| `dataset` | 哪一套数据 | `formal`（正式实验）、`pilot`（预实验）、`test`（开发测试）。formal 与另两者绝对隔离：formal 在 data/formal/，pilot、test 在 data/pilot_and_test/ 下 |
| `layer` | 加工程度 | `raw`（原始，只读）、`processed`（处理中间结果）、`final`（最终分析表）；另有 `supplementary` 放分组、被试表、访谈编码等补充信息 |
| `pipeline` | 数据类型，与 table_flows 的流程对应 | `track`（虚拟自然行为）、`psycho`（问卷）、`physio`（生理） |
| `subject` | 被试编号 | 如 `P040`。不含组别，组别记在被试表里由程序按编号查 |

磁盘位置为 `data/<dataset>/<layer>/<pipeline>/<记录文件>`，例如 data/pilot_and_test/test/raw/track/sub-P999_ses-S001_mod-Interactive_run-002/。APP 和 LSL 生成的原始文件名保持原样，`P040` 是分析端的简写，由程序对应。raw 下另有 interview、session_notes 两类不属于任何 pipeline 的原始材料。

**调取数据一律用 analysis/tools/data_access.py**，不在脚本里拼路径、不各自写找文件的逻辑：

```python
from data_access import subjects, find, load
subjects("test", "track")                    # 这个数据集有哪些被试
find("test", "track", ["P999"], run="002")   # 被试 → 记录位置
load("test", "track", "P999", run="002")     # 载入这名被试的七张埋点表
```

track 下一名被试对应他在实验条件中的那一份记录（实验组 Interactive、对照组 Passive）；练习场记录不用于分析，不会返回。同一被试有多份记录（如测试中重跑）时须用 run 指明。psycho、physio 在原始格式确定后接入同一接口。数据在哪由 analysis/tools/paths.py 与 data_access.py 管理，数据是什么由 global_settings.py 规定，二者分开。

data_lab 的清理和格式中间表写入 data/<dataset>/processed/track/data_lab/<研究问题>/。

data_lab 的图表和文字写入各研究问题的 results/，每次运行先清空再写，处理数据目录同样只保留最近一次。所用数据记录在 results/_provenance/manifest.json 中，并在该问题的 log.md 里注明。想保留某次结果，手动复制到 save/ 并按含义命名。

## 时间检索和版本追溯

每个活跃 Lab 脚本声明 SCRIPT_HISTORY，以带时区的 ISO 时间登记创建、重要修改、迁移或弃用事件，并说明原因。记录重要变化，不记录逐次敲键或无关过程。以后改 Lab 脚本时，保留旧条目并追加本次事件，不只覆盖一个“最后修改时间”。

现有脚本无法可靠确定原始创建时间，因此明确标为未知，2026-10-23T20:36:13+08:00 仅表示首次纳入 Git 的可核实时间。新增脚本记录实际建立时的登记时间。不要用复制文件后的修改时间反推先后顺序。

[analysis/tools/lab_history.py](analysis/tools/lab_history.py) 只解析历史声明，不执行实验。直接在 VS Code 运行它会生成 analysis/data_lab/history_index.csv；可在其顶部 PARAMETERS 设置起止日期及对象，也可以使用：

```bash
python3 analysis/tools/lab_history.py --since 2026-10-23 --until 2026-10-23 --object track   # 生成的 history_index.csv 只存本机
```

索引按登记时间排序，包含对象、环节、脚本、事件、原因、已有提交号及原路径；不扫描 results、save 等结果目录。deprecated 中有历史声明的源码仍可检索，并标记弃用状态。同一次批量调整可能登记同一时间，不能据此臆造更细的操作顺序。

每次运行的 manifest 另记整次运行及每个步骤的开始、结束时间、状态和错误。工程时间使用 Asia/Shanghai 的 ISO 表示；它与原始数据中的 t_session、t_device 是不同用途，不能混为数据同步依据。

版本库为 [lijian-bjfu/Nature-based-Intervention](https://github.com/lijian-bjfu/Nature-based-Intervention)。运行时记录 Git 提交号、分支、源码工作树状态和每个源码文件的 SHA-256。已提交的源码凭提交号即可还原，不再整份复制；只有当次有未提交修改或尚未纳入版本库的文件，才逐个复制到 uncommitted_sources。Git 不可用时全部复制，并明确记录缺失原因。

日常可在 GitHub Desktop 查看改动、提交与历史，代码改动和 SCRIPT_HISTORY 一起提交即可。无需依赖命令行管理版本。入库与不入库的划分：
- **入库**：table_flows 的流程与工具、data_lab 的脚本、global_settings.py、说明文档。GitHub 端的价值在于制表规范流程和工具。
- **不入库，只存本机硬盘**：data/ 下的全部数据（只保留目录骨架与说明文件）；data_lab 各研究问题的 results/ 与 save/；缓存和本机元数据。数据不上传到 GitHub 是出于被试隐私与伦理要求：伦理申请中的存储位置是 iPad 本机与研究者电脑，GitHub 属第三方服务器。数据另用移动硬盘备份。

## 公共工具、命名与废弃工具

对象代码决定研究含义、变量选择、时间段、分类和统计方法；tools 提供路径、序列化、通用选项校验、绘图样式、依赖解析与复现记录。track_io.py 是供制表与实验共用的 Track 适配器，保留对象前缀，不假称适用于所有数据。

共用函数按真实需要逐步提取。第二个实际使用场景出现时，比较输入输出、计算含义及异常处理；这些相同才共用。图形外观相似并不意味着统计方法相同。可以复用画线、图例和保存操作，把单位转换、分组依据、误差条计算等留在对象代码。不为尚未获得的数据预造框架，也不长期维护两份已经确认等价的计算。

对象无关工具不反向依赖具体实验。对象之间不直接借用对方分析脚本。脚本用“对象_动作.py”，具体实验目录按工作问题命名；不同候选版本通过局部参数与 Git 追踪，不以被试编号命名共用工具。

deprecated 只放已确认弃用的源码，文件中记录日期、原因和替代工具。调度器拒绝执行 deprecated、results、save 中的代码。

## 验证与分析约定

运行 analysis/tools/track_check.py 检查原始读取、局部参数传递、依赖、弃用隔离、运行时间和源码记录。检查结果放在 track/description/results/_provenance/checks。先运行一次当前记录描述，再运行检查。

引用数值须说明表和字段，空间数据须出图。网格覆盖率对原点敏感，不用于被试排名。描述与解释分开，技术异常不自动转成被试排除或心理分类。分析文字用完整句子，先说明原理、再写方法。不将分析脚本或结果放 /tmp。
