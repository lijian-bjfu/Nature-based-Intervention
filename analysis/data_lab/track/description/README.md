# 埋点原始记录的描述

## 一、问题

APP 记录下来的原始数据（七张表，规范见《研究思路/实验记录-埋点.md》附A）实际是什么样子：每张表是否齐全、记录了哪些行为、这些行为在时间和空间上如何分布。

这是设计埋点指标之前的基础工作。指标要从原始记录里算出来，先看清原始记录实际捕捉到了什么、有没有漏记或异常，再决定指标怎么定义、阈值大概在哪里。这里只描述事实，不定义新的行为指标，也不把行为解释为兴趣、注意、无聊或动机。

## 二、这些工具怎样帮助回答问题

| 要回答的问题 | 看哪里 |
|---|---|
| 数据齐不齐、能不能用 | 报告"记录范围与可用性"一节；`index.md` 的 warnings 列 |
| 被试去了哪里、在哪里停留 | `fig1_space`（轨迹与点击位置） |
| 行为随时间怎样变化：什么时候走、什么时候点、什么时候转头 | `fig2_time`（四条时间轴） |
| 点击打中了什么、摸到了什么、被什么挡住 | `fig3_actions` 左半；`table_layers.csv`；`touch_records.csv` |
| 环视主要来自拖动还是点击后的转向、转了多少 | `fig3_actions` 右半；`table_look.csv` |
| 点击和受阻在各个时段的数量 | `table_time_bins.csv` |
| 世界事件是否发生、为什么没发生 | 报告的世界事件一节 |

## 三、脚本

运行入口只有一个：`track_describe.py`。其余脚本由它按顺序调用，不需要单独运行。

| 脚本 | 做什么 |
|---|---|
| `track_describe.py` | **入口**。顶部 PARAMETERS 设置参数；依次调用下面各步，最后计算描述、画图 |
| `track_inventory.py` | 第 1 步，核对：每场会话的文件是否齐全，区分"文件不存在"和"文件存在但没有行"（前者不能当作零次行为） |
| `track_clean.py` | 第 2 步，清理：在副本中处理已确认的历史取值（早期数据中的 None 转为 NoHit / NotBlocked），原始数据不改动 |
| `track_format.py` | 第 3 步，格式：统一数据类型；出现规范外的取值时记录下来，并附上产生该数据的 APP 代码版本（app_commit） |
| `track_report.py` | 把描述结果写成每场会话的报告（report.md） |
| `experiment.py` | 参数检查与各步的调度，研究者一般不需要打开 |

清理和格式两步的中间数据写在 `data/<数据集>/processed/app/data_lab/description/`，供检查用。

## 四、怎么运行、怎么设置参数

1. 在 VS Code 打开 `track_describe.py`。
2. 修改顶部 `PARAMETERS`，保存。
3. 点右上角的 Run（Run Python File）。
4. 运行结束后打开 `results/index.md`。

| 参数 | 含义 | 可选值 |
|---|---|---|
| `selection.dataset` | 描述哪个数据集 | `logging_test`（埋点开发测试）、`pilot`（预实验）、`formal`（正式实验） |
| `selection.sessions` | 描述哪几份实验记录 | `["*"]` 全部；`["sub-P999*"]` 按通配符；或写完整的会话文件夹名 |
| `selection.modules` | 描述哪个模块 | `Interactive`（实验条件）；`Practice`、`Passive` 目前只有会话信息 |
| `selection.tasks` | 跑到哪一步 | 通常保持 `["track_describe"]`（自动包含前三步）；只想核对文件可选 `track_inventory` |
| `report_language` | 报告语言 | `auto`（正式数据用英文，其余用中文）、`zh`、`en` |
| `description.time_bin_seconds` | 时间轴分段的宽度（秒） | 默认 60；只影响 `fig2_time` 和 `table_time_bins.csv` 的分段，不改变原始数据 |
| `description.interval_quantiles` | 报告采样间隔的哪些分位数 | 默认 0.5、0.95、0.99，用于检查时空表是否按 0.1 秒均匀记录 |
| `description.colors` | 图中各类别的颜色 | 一般不用改 |
| `figure` | 图的分辨率、格式、字体、字号 | 一般不用改 |

## 五、结果

每次运行先清空 `results/` 再写入，只保留最近一次。想保留某次结果，把它复制到 `save/` 并按含义命名。

一次运行会描述所选的每一份实验记录（被试进入一次实验条件所产生的一份原始数据，如 `sub-P999_ses-S001_mod-Interactive_run-002`），每份记录在 `results/` 里各有一个文件夹。这些文件夹属于同一次运行，不是历次运行的过程。

```
results/
├── index.md          本次描述的所有记录的总览表：时长、各表行数、触摸数、受阻数、警告数，并链接到各场报告
├── sessions.csv      同上，表格形式
├── sub-…/            每份实验记录一个文件夹
│   ├── report.md     这份记录的报告
│   ├── fig1_space    空间：左为行走轨迹与每次点击时被试的位置；右为点击打中的位置与是否摸到
│   ├── fig2_time     时间：自上而下四条时间轴——水平位置的变化；每次点击及其受阻类型、摸到的时刻；
│   │                 每段转动（拖拽式与点击式分开）；按时间分段统计的点击数与受阻数
│   ├── fig3_actions  操作：左为点击按命中层的次数及摸到的次数；右为拖拽式与点击式转动的累计角度
│   ├── table_layers.csv     命中层 × 是否摸到 的次数
│   ├── table_look.csv       拖拽式、点击式转动各自的段数、次数、时长、累计角度
│   ├── table_time_bins.csv  每个时间段的点击数、摸到数、各受阻类型的次数
│   ├── touch_records.csv    每一次摸到的完整记录（时间、位置、命中层）
│   └── summary.json         这份记录的全部描述数字，供程序读取
└── _provenance/      追溯信息：参数、Git 提交号、规范快照、检查结果。平时不用打开
```

## 六、结论

尚未得出。探索过程见 `log.md`。
