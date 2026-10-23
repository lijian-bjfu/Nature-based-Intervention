# 埋点数据描述

sub-P999_ses-S001_mod-Interactive_run-002

## 原理与方法

本报告描述记录到的环境接触与操作过程。先交代可用数据，再呈现触摸、世界事件、受阻、转动以及时间和空间分布。行为事实不直接解释为兴趣、注意、无聊或动机。

数据由根目录 run.py 调度：01 核对文件，02 在副本中处理已定的历史取值，03 统一类型，06 从标准表生成描述。字段、方法、参数与路径均来自 settings.py；未定义新的行为指标。

## 记录范围与可用性

session.t_device_end − session.t_device_start = 817.689 秒。缺失文件的行数显示为空，不按零次行为解释。

| table | present | rows | applicable |
| --- | --- | --- | --- |
| session | True | 1 | True |
| spacetime | True | 8177 | True |
| tap | True | 155 | True |
| backstep | True | 1 | True |
| look | True | 244 | True |
| world_event | True | 4 | True |
| tech_glitch | True | 1 | True |

## 操作与实际接触

tap 行数为 155；tap.is_touched=TRUE 为 6；tap.block_type 为 CutShort/NoStart 的行数合计 78。未触摸不等于操作失败，LookAt 也不等于明确的触摸意图。

| hit_layer | tap_n | is_touched_TRUE_n | is_touched_FALSE_n | is_touched_missing_n |
| --- | --- | --- | --- | --- |
| Terrain | 94 | 0 | 94 | 0 |
| Road | 10 | 0 | 10 | 0 |
| Rock | 11 | 0 | 11 | 0 |
| DeadWood | 1 | 0 | 1 | 0 |
| Flower | 0 | 0 | 0 | 0 |
| Creature | 3 | 1 | 2 | 0 |
| TouchFoliage | 4 | 0 | 4 | 0 |
| SweepFoliage | 6 | 1 | 5 | 0 |
| TouchRigid | 0 | 0 | 0 | 0 |
| WaterTouchSurface | 26 | 4 | 22 | 0 |
| NoHit | 0 | 0 | 0 | 0 |

下列类别计数由 summary.json 保存；历史 None 已按配置分别映射为 NoHit/NotBlocked。

| field | level | rows |
| --- | --- | --- |
| tap.intent | NoHit | 0 |
| tap.intent | WalkTo | 72 |
| tap.intent | LookAt | 83 |

| field | level | rows |
| --- | --- | --- |
| tap.block_type | NotBlocked | 77 |
| tap.block_type | CutShort | 46 |
| tap.block_type | NoStart | 32 |

| field | level | rows |
| --- | --- | --- |
| tap.block_reason | NotBlocked | 77 |
| tap.block_reason | BarrierDenseSlope | 24 |
| tap.block_reason | BarrierWater | 31 |
| tap.block_reason | BarrierUnlabeled | 0 |
| tap.block_reason | StepUp | 0 |
| tap.block_reason | DropTooHigh | 0 |
| tap.block_reason | TooSteep | 23 |
| tap.block_reason | NoGround | 0 |

## 转动、后退与世界事件

| look_type | segments_n | touch_ids_n | duration_sum_s | duration_median_s | yaw_path_sum_deg | pitch_path_sum_deg |
| --- | --- | --- | --- | --- | --- | --- |
| Drag | 130 | 97 | 275.636 | 1.702 | 4574.400 | 1699.400 |
| Tap | 114 | 113 | 154.516 | 1.132 | 2194.600 | 583.300 |

转动段数与触屏次数分开，Drag 包含惯性；Tap 是系统响应。累计角路程不代表净转圈数或操作负担。

### backstep

| touch_id | t_session | t_device | cam_x | cam_y | cam_z | back_dist | block_type | block_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 139 | 438.854 | 1792724183.966 | 52.240 | 3.120 | 36.410 | 1.000 | NotBlocked | NotBlocked |

### world_event

| t_session | t_device | event_name | action | cam_x | cam_y | cam_z | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 383.341 | 1792724128.453 | ScriptedEvent_bird_r3-r2 | Fired | 39.300 | 4.220 | 29.330 | — |
| 572.511 | 1792724317.623 | ScriptedEvent_R1-2_butterfly | Fired | 56.580 | 3.100 | 51.290 | — |
| 817.667 | 1792724562.779 | ScriptedEvent_R1_east_butterfly | NotFired | 55.270 | 4.130 | 65.620 | NeverEntered |
| 817.668 | 1792724562.780 | ScriptedEvent_bird_r1-r2 | NotFired | 55.270 | 4.130 | 65.620 | NoSight |

### tech_glitch

| t_session | t_device | status | duration |
| --- | --- | --- | --- |
| 817.419 | 1792724562.531 | Background | 0.250 |

## 时间与空间

按相邻 spacetime.cam_x/cam_z 连线求和的水平折线长为 211.39 米。这是采样近似，未做平滑或插补，不解释为体力消耗、停留或覆盖率。命中点不是到达点。

时间箱宽度设置为 60 秒，每箱实际 observed_s 单独列出。

| start_s | end_s | observed_s | tap_n | is_touched_TRUE_n | NotBlocked | CutShort | NoStart |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.000 | 60.000 | 60.000 | 20 | 1 | 7 | 9 | 4 |
| 60.000 | 120.000 | 60.000 | 4 | 0 | 2 | 2 | 0 |
| 120.000 | 180.000 | 60.000 | 5 | 0 | 5 | 0 | 0 |
| 180.000 | 240.000 | 60.000 | 12 | 0 | 5 | 5 | 2 |
| 240.000 | 300.000 | 60.000 | 16 | 0 | 9 | 2 | 5 |
| 300.000 | 360.000 | 60.000 | 11 | 2 | 8 | 2 | 1 |
| 360.000 | 420.000 | 60.000 | 16 | 0 | 5 | 6 | 5 |
| 420.000 | 480.000 | 60.000 | 8 | 0 | 6 | 2 | 0 |
| 480.000 | 540.000 | 60.000 | 13 | 1 | 6 | 5 | 2 |
| 540.000 | 600.000 | 60.000 | 5 | 2 | 5 | 0 | 0 |
| 600.000 | 660.000 | 60.000 | 12 | 0 | 5 | 5 | 2 |
| 660.000 | 720.000 | 60.000 | 9 | 0 | 4 | 1 | 4 |
| 720.000 | 780.000 | 60.000 | 20 | 0 | 6 | 7 | 7 |
| 780.000 | 817.689 | 37.689 | 4 | 0 | 4 | 0 | 0 |

## 数据检查

技术异常保留在原始时段中；本轮不执行被试排除或行为分类。world_event 的 Fired 不证明注意，HandStartle 只对应常驻停落生物，不能覆盖所有手触发剧本事件。

未发现文件缺失或时间顺序警告；这不等于已检验全部研究数据质量。

![fig1_space.png](fig1_space.png)

![fig2_time.png](fig2_time.png)

![fig3_actions.png](fig3_actions.png)

## 复现

本次运行的根目录含 manifest.json 与 settings_snapshot.json，可核对输入 SHA-256、脚本 SHA-256、选择范围与配置。原始数据不改写，文字与图表由同次计算生成。
