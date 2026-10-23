# 数据、分析与报告工程

## 原理

本工程提供从原始数据到分析报告的可重复运行工具。00_settings.py 保存固定规范，01_parameters.py 保存研究者可调参数，02_run.py 负责调度。日常在参数文件中修改并保存，再在 VS Code 点击 Run；同时保留命令行执行。切换数据集或已有选项不复制脚本，修改科学方法仍须先讨论并更新研究规范。

data 保存数据，analysis 保存可复用脚本，reports 保存分析结果与文字报告。清理、格式转换、切窗和指标计算产生的数据表仍然属于数据，不是报告。报告按工作内容分类，不按输入数据集建文件夹；数据来源记录在运行清单中供追溯。

## 目录与职责

```text
Nature-based Intervention/
├── 00_settings.py                          固定规范，日常不改
├── 01_parameters.py                        日常运行与展示参数
├── 02_run.py
├── requirements.txt
├── README.md
├── data/
│   ├── formal/                          正式数据
│   │   ├── raw/                         原始输入，只读
│   │   │   └── app/、questionnaire/、physio/、interview/、session_notes/
│   │   ├── processed/                   处理中的数据，先按性质分
│   │   │   ├── app/<run_id>/            埋点处理过程
│   │   │   │   ├── 01_import/
│   │   │   │   ├── 02_clean/<session>/tables/
│   │   │   │   └── 03_format/<session>/tables/
│   │   │   ├── questionnaire/           未来的问卷清理与计分
│   │   │   └── physio/                  未来的生理清理、切窗等
│   │   ├── final/                       最终分析数据表
│   │   └── supplementary/               被试表、区域标注、编码表等补充数据
│   └── pilot_and_test/
│       ├── pilot/                       同样有上述四类目录
│       └── logging_test/                同样有上述四类目录
├── analysis/                            只放可复用脚本
│   ├── 01_import/app_inventory.py
│   ├── 02_clean/app_clean.py
│   ├── 03_format/app_format.py
│   ├── 04_features/                      指标，尚未实现
│   ├── 05_integrate/                     最终表整理，尚未实现
│   ├── 06_analysis/describe/app_describe.py
│   └── 07_tools/                        共用工具，不是第七个处理阶段
├── reports/
│   ├── formal/
│   │   └── app/runs/<run_id>/            正式埋点分析结果
│   ├── pilot_and_test/
│   │   └── app/                         测试期的埋点工作结果
│   │       ├── runs/<run_id>/
│   │       │   ├── index.md
│   │       │   ├── sessions.csv
│   │       │   └── <session>/            摘要、描述表、图、report.md
│   │       ├── checks/                  工程检查结果
│   │       └── archive/                 历史描述与旧代码来源
│   └── _runtime_cache/                  不含研究数据的绘图缓存
└── 研究思路/                            科学依据与已经同意的决定
```

数据的正式类别统一使用 formal，原 main 已更名。每个数据集内部均分为 raw、processed、final、supplementary。processed 先按数据性质划分，各性质内部容纳自己的处理阶段，不要求问卷、生理和埋点具有完全相同的处理步骤。当前只实现埋点，不预先写生理切窗或问卷计分算法。

final 用于后续 05 整理出的最终分析表，当前尚无此类产物，不能把 03 标准化表叫作最终表。被试基本信息表放在 supplementary/participants.csv；采集得到的原始实验记录单仍属于 raw/session_notes，不与后补标注混淆。

reports 只有 formal 与 pilot_and_test 两类研究报告，再按 app、questionnaire、physio 等工作内容分。pilot 和 logging_test 的埋点结果都放在 pilot_and_test/app，不能在报告路径中再套 pilot 或 logging_test。运行编号用于避免覆盖结果；输入数据集只写入清单，不作为报告分类。

## 固定规范与可调参数

| 文件/分组 | 内容 | 谁在什么时候修改 |
|---|---|---|
| 00_settings.py | 七表 APP_SCHEMA、字段/类型/单位/分类、历史兼容、命名与目录、任务及依赖。 | 日常不改；研究或工程规范正式调整后维护。 |
| 01_parameters.py：RUN | 本次任务、数据集、会话与模块。 | 研究者日常修改。 |
| 01_parameters.py：COMMON | 报告语言、图格式、分辨率、字体。 | 研究者日常修改。 |
| 01_parameters.py：APP.describe | 描述分箱、采样间隔分位数、埋点配色。 | 在已有功能允许的范围内修改。 |

参数主要按数据性质分组，再按工作任务分；工作流目录仍按阶段组织。以后增加 QUESTIONNAIRE、PHYSIO 时各自包含清理、切窗、计分、描述等已经实现的任务，不预先堆放参数占位。

APP_SCHEMA 按表逐行写明实际列名、类型、单位和类别，APP_COLUMNS 等程序索引由它生成，避免维护两份清单。原始 0.1 秒采样、俯仰正负、分类含义属于固定规范；60 秒描述分箱是展示参数。水平轨迹目前只有一种实现，不作为用户方法选择器。新的指标阈值或科学方法须先讨论并更新研究规范。

## 运行选项对照

日常只编辑 01_parameters.py，保存后在 02_run.py 点 Run；00_settings.py 与 02_run.py 都不用日常修改。下面的英文是程序识别的选项值，中文是含义，不要求用户记住这些词。参数文件的 RUN 上方也就地列出全部选项。

| 参数 | 选项值 | 含义与适用范围 |
|---|---|---|
| tasks | app_describe | 埋点描述、绘图与报告，已包含核对、清理、格式化；通常只选它。 |
| tasks | app_inventory | 只核对埋点文件。 |
| tasks | app_clean | 核对后清理历史取值，只生成处理数据。 |
| tasks | app_format | 核对、清理后统一类型，生成标准表。 |
| dataset | logging_test | 开发期间的埋点测试；当前四场记录在 data/pilot_and_test/logging_test/。 |
| dataset | pilot | 被试预实验数据，在 data/pilot_and_test/pilot/。 |
| dataset | formal | 正式实验数据，在 data/formal/。 |
| sessions | ["*"] | 选择该数据范围中全部符合模块条件的会话。 |
| sessions | ["sub-P999*"] | 按会话文件夹名前缀选择。 |
| sessions | ["具体会话名"] | 单场；到对应数据集的 raw/app/ 复制文件夹名称，不填完整路径。 |
| modules | Interactive | 自由交互体验模块，目前埋点行为描述主要分析它。 |
| modules | Practice | 练习场，按规范只有会话信息，没有行为表。 |
| modules | Passive | 被动观看视频，当前只有会话信息，不能据此描述操作行为。 |

tasks 回答“做什么”，dataset 回答“用哪批数据”，sessions 回答“选哪些会话”，modules 回答“筛选哪种 APP 模块”。dataset 与 modules 都不是实验组别；选择某个模块不会补出未采集的表。英文选项值区分大小写，请从参数旁的说明复制。

例如当前默认设置的意思是：**对开发埋点测试中全部自由交互会话，生成描述、图和报告。** 新增选项须同时提供用户可读名称、适用说明，并更新参数旁的选项说明；不能只增加一个内部英文标识。填错任务、数据范围或模块时，程序也会提示带中文含义的可选项。

## 方式一：VS Code 点 Run（推荐）

无需输入命令。

1. 打开根目录 01_parameters.py。RUN 默认选择 app_describe、logging_test、全部 Interactive 会话。只看一场时，把 sessions 的 ["*"] 改为具体会话目录名的列表。
2. 如需调整，在 APP["describe"] 改 time_bin_seconds，在 COMMON 改语言、图格式等；每项旁边有单位、范围和示例。auto 语言规则也在此文件调整，不与数据目录登记绑定。
3. 保存 01_parameters.py，打开同目录 02_run.py，点击 VS Code 的 **Run Python File**。
4. 系统检查参数、筛选数据并补齐前置步骤，结束时显示“打开报告”的完整 index.md 路径。点击该路径查看结果。

需要 Python 3.10+ 和 requirements.txt 中的依赖，已在本机 Python 3.11 验证。首次在 VS Code 选择装有依赖的解释器即可；无需填写命令行选项，也不要求当前工作目录是项目根目录。01_parameters.py 本身不是分析入口，运行它只提示去运行 02_run.py。

| RUN.tasks 中的任务 | 做什么 | 自动执行阶段 |
|---|---|---|
| app_inventory | 核对原始埋点文件。 | 01 |
| app_clean | 清理已经确认的历史取值。 | 01、02 |
| app_format | 生成标准类型表。 | 01、02、03 |
| app_describe | 描述、绘图与文字报告。 | 01、02、03、06 |

可选多个任务，系统合并依赖后按固定顺序执行，不重复运行同一步。04 指标、05 最终表整理尚未实现。每次运行新建目录，不覆盖已有成果；只核对、清理或格式化时不创建报告目录。

## 方式二：命令行执行（可选）

命令行与点 Run 共用加载和执行逻辑。只有明确提供的选项覆盖 01_parameters.py，其余保留文件设置；不会回写参数文件。

```bash
python3 02_run.py
python3 02_run.py --list
python3 02_run.py --tasks app_describe --dataset logging_test
python3 02_run.py --tasks app_describe --sessions sub-P999_ses-S001_mod-Interactive_run-002 --time-bin-seconds 30
python3 02_run.py --tasks app_clean
python3 02_run.py --language en --figure-formats png svg --figure-dpi 200
```

--steps 兼容旧阶段名；日常优先选任务名称，不要求研究者理解前置步骤。非法参数会在处理前提示具体参数键与要求。

## 单独运行工作脚本与函数工具

app_describe.py 也支持 VS Code 直接点 Run，或命令行执行：

```bash
python3 analysis/06_analysis/describe/app_describe.py --sessions 'sub-P999*'
```

单独运行工作脚本默认选择它自己的任务，数据范围与展示设置仍读 01_parameters.py，也通过统一调度补齐前置步骤。推荐日常使用根目录 02_run.py。

| 接口 | 职责 |
|---|---|
| load_config() | 读取参数、应用临时覆盖、检查合法性，生成 RunConfig。 |
| resolve_tasks() | 根据固定任务登记计算依赖。 |
| execute(config) | 创建路径、记录来源，逐步调用 run(context)。 |
| app_describe.run(context) | 接收具名 RunContext，组织本次描述。 |
| describe(tables, session_name, options) | 接收标准表与 AppDescribeOptions，返回描述和结果表。 |
| plots(..., options, figure) | 明确接收埋点描述参数与通用 FigureOptions。 |
| make_report(..., options) | 根据同次结果与实际参数生成文字。 |
| 07_tools | 提供 read_session、stage_dir、write_json、markdown_table、pyplot、save_figure 等工具。 |

用户不需要手工构造 context、七张表或输出路径。新增可执行工作脚本须提供 run(context)，并在 __main__ 中接入同一 cli 默认任务，使点 Run 和命令行都有效；纯工具模块不作为独立任务。

## 阶段输入输出

| 阶段 | 当前做法 | 保存位置 |
|---|---|---|
| 01_import | 核对已拷入 raw/app 的文件和 SHA-256，不自动从 iPad 复制。 | data/<dataset>/processed/app/<run_id>/01_import/ |
| 02_clean | 只在副本中转换已定的历史取值，保留处理记录。 | 同次 processed/app/<run_id>/02_clean/ |
| 03_format | 按配置统一类型；非法数字/布尔值报错，未知类别另记。 | 同次 processed/app/<run_id>/03_format/ |
| 04_features | 未来计算已定指标。 | 预留 processed 中对应性质的处理阶段。 |
| 05_integrate | 未来生成最终分析表。 | data/<dataset>/final/<run_id>/，尚未实现。 |
| 06_analysis | 从标准表生成描述统计、图和同次计算的文字。 | reports/<formal或pilot_and_test>/<工作内容>/runs/<run_id>/ |
| 07_tools | 路径、读写、调度、绘图和序列化工具。 | 不作为独立分析阶段。 |

表中的 <dataset> 表示 formal 或 pilot_and_test 下的某个数据集的根目录。分析产生的描述统计表属于 reports 的结果；清理、格式化、切窗等供后续处理使用的表属于 data/processed；最终研究分析表属于 data/final。三者不能仅因文件格式都是 CSV 就混为一类。

处理数据目录保存 manifest.json、settings_snapshot.json 和 parameters_snapshot.json；运行 06 时，报告目录也保存对应清单与快照，并指向同次处理数据。固定规范与可调参数分别保存；后者记录参数文件内容、实际生效值和命令行覆盖。清单记录数据选择、脚本与输入 SHA-256、依赖版本和运行状态。raw 不改写；处理数据与报告可以由同一套工具重新生成。

## 读取、命名与分析纪律

埋点统一用 analysis/07_tools/app_io.py 读写，以 analysis/07_tools/paths.py 定位；固定规范来自根目录 00_settings.py，可调参数由 configuration.py 从 01_parameters.py 读取并明确传入各函数。None 作为字面值保留，仅在 02 的指定字段中映射为 NoHit/NotBlocked。文件缺失与表存在但零行分别报告，不造数据。

脚本采用“来源_动作.py”，例如 app_describe.py、questionnaire_describe.py、physio_describe.py；流程目录表示阶段，不把被试编号、日期或 v2 写进共用脚本名。来源无关的读写、绘图等功能放 07_tools，各来源专有处理保留对应前缀。

引用数值时写明表与字段；空间分布出图；网格覆盖率不用于被试排名，不用个人轨迹作为其自身比较基准。事实、离线分类与心理解释分开，访谈先独立编码后交叉对照。原始日志不直接解释为兴趣、无聊或动机。

analysis 只放脚本，中间和最终数据放 data，图表与报告放 reports，通过运行编号和清单关联。不在 /tmp 存放分析脚本、数据结果或报告。姓名、联系方式、知情同意书、可识别身份录音等材料不放入本数据工程。

## 历史文件

原有单会话描述与旧代码来源保存在 reports/pilot_and_test/app/archive/before_pipeline_refactor。前一版流程误放在 reports 的 01–03 数据已迁入 logging_test/processed/app，原分析报告移到工作内容 app 下，文件内容经校验保持不变。历史清单保留当时的配置和旧路径，当前迁移关系另存 archive/layout_migration_*.json。未开展两份描述的内容对照。
