# 数据、分析与报告工程

## 原理

本工程提供从原始数据到分析报告的可重复运行工具。settings.py 统一维护数据结构、命名、列名、路径、已有方法与参数，run.py 负责调度。切换数据集或已有选项不复制脚本，修改科学方法仍须先讨论并更新研究规范。

data 保存数据，analysis 保存可复用脚本，reports 保存分析结果与文字报告。清理、格式转换、切窗和指标计算产生的数据表仍然属于数据，不是报告。报告按工作内容分类，不按输入数据集建文件夹；数据来源记录在运行清单中供追溯。

## 目录与职责

```text
Nature-based Intervention/
├── settings.py
├── run.py
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

## 统一配置

| 配置 | 用途 |
|---|---|
| DATASETS | 数据根目录、所属正式/测试类别及默认报告语言。 |
| DATA_FOLDERS | raw、processed、final、supplementary 四类数据的目录名。 |
| REPORT_GROUPS、REPORT_TOPICS | 正式/测试报告根目录与工作内容目录。 |
| DATA_STAGE_DESTINATIONS | 各处理阶段写入 processed、final 还是 report。 |
| RUN_DATASET、RUN_SESSIONS、RUN_MODULES、RUN_STEPS | 无参数运行的数据范围与执行步骤。 |
| APP_SESSION_REGEX、APP_FILES | 埋点会话目录与七表文件命名。 |
| APP_COLUMNS | 七表 columns 表：程序语义对应文件中的实际列名。 |
| APP_TYPES、APP_UNITS、PRECISION | 类型、单位与原始记录精度，不提前舍入计算。 |
| APP_LEVELS、APP_LEGACY_VALUES、APP_TRUE、APP_FALSE | 分类取值、历史兼容与布尔序列化。 |
| APP_REQUIRED_TABLES | 各模块应有的表，缺失文件不当作零次行为。 |
| APP_DESCRIBE、PLOT、APP_FIGURES | 已有描述方法与绘图参数。 |
| STEP_ORDER、APP_PIPELINE | 运行顺序、已实现脚本和前置依赖。 |

变量含义以《研究思路/实验记录-埋点.md》为准，settings 是已同意规范的工程配置。仅改变外部列名时修改 APP_COLUMNS 右侧；改变物理含义、增加变量或引入新方法不能靠配置重命名代替实现。读写与分析均从这份 columns 表取列名。

## 运行

需要 Python 3.10+ 及 requirements.txt 中的依赖，已在本机 Python 3.11 验证。VS Code 打开根目录 run.py，选择装有依赖的解释器后可直接运行；不要求当前工作目录是项目根目录。

```bash
python3 run.py
python3 run.py --list
python3 run.py --dataset logging_test --sessions sub-P999_ses-S001_mod-Interactive_run-002
python3 run.py --steps 02_clean
python3 run.py --steps 06_analysis
python3 run.py --sessions 'sub-P999*' --language en
python3 analysis/06_analysis/describe/app_describe.py --dataset logging_test
```

无参数默认对 logging_test 的所有 Interactive 会话执行 01、02、03、06。选择某步会自动补齐当前已实现的前置步骤。04、05 尚未实现，选择它们会明确报错。每次运行使用新编号，不覆盖已有数据或报告。只运行 01–03 时只生成处理数据和处理记录，不创建分析报告目录。

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

处理数据目录保存 manifest.json 和 settings_snapshot.json；运行 06 时，报告目录也保存对应清单与快照，并指向同次处理数据。清单记录数据选择、脚本与输入 SHA-256、依赖版本和运行状态。raw 不改写；处理数据与报告可以由同一套工具重新生成。

## 读取、命名与分析纪律

埋点统一用 analysis/07_tools/app_io.py 读写，以 analysis/07_tools/paths.py 定位；配置唯一来源为根目录 settings.py。None 作为字面值保留，仅在 02 的指定字段中映射为 NoHit/NotBlocked。文件缺失与表存在但零行分别报告，不造数据。

脚本采用“来源_动作.py”，例如 app_describe.py、questionnaire_describe.py、physio_describe.py；流程目录表示阶段，不把被试编号、日期或 v2 写进共用脚本名。来源无关的读写、绘图等功能放 07_tools，各来源专有处理保留对应前缀。

引用数值时写明表与字段；空间分布出图；网格覆盖率不用于被试排名，不用个人轨迹作为其自身比较基准。事实、离线分类与心理解释分开，访谈先独立编码后交叉对照。原始日志不直接解释为兴趣、无聊或动机。

analysis 只放脚本，中间和最终数据放 data，图表与报告放 reports，通过运行编号和清单关联。不在 /tmp 存放分析脚本、数据结果或报告。姓名、联系方式、知情同意书、可识别身份录音等材料不放入本数据工程。

## 历史文件

原有单会话描述与旧代码来源保存在 reports/pilot_and_test/app/archive/before_pipeline_refactor。前一版流程误放在 reports 的 01–03 数据已迁入 logging_test/processed/app，原分析报告移到工作内容 app 下，文件内容经校验保持不变。历史清单保留当时的配置和旧路径，当前迁移关系另存 archive/layout_migration_*.json。未开展两份描述的内容对照。
