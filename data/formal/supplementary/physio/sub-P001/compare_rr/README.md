# P001 RR 比较实验

本次按研究者确认使用正式实验P001，不是P002。仅输出实验结果，未修改既有流程代码或源数据。

## 主要结果文件

- rr_ecg.csv / rr_ecg.png：调用 PhysicoAnalysis/scripts/3_select_rr.py 当前选中的 _ecg_to_rr_v2 原函数，从ECG提取；此份未再清理。
- rr_h10_clean.csv / rr_h10_clean.png：调用 PhysicoAnalysis/scripts/4a_clean_rr.py 的 clean_device_rr 原函数，使用原脚本当前参数，先split、再interp（PCHIP）。图中灰色点为原始H10 RR。
- rr_comparison_induction.png：诱导期三路对照（原始H10、ECG提取、H10清理），使用同一坐标范围。

两份CSV字段与merged表一致：t_unix（Unix秒）、time_lsl（LSL秒）、part、ms（RR毫秒）。
图的横轴为北京时间。两张主图均包含全程和诱导期放大图，坐标范围相同，未按百分位裁掉极值。全程面板显示完整纵轴；诱导期放大面板纵轴为250–1400 ms，超出范围的数据以边缘三角标记并在图例注明数量，完整极值仍可在全程面板和CSV中查看。
ECG转换结果5794条，H10清理前5505条、清理后5594条，split净增加89条。

## 算法与参数

使用AST读取并原样执行指定脚本中的函数，跳过它们的目录初始化、被试清单和main批处理。
数据通过列名适配的临时副本传入；原清理函数的文件读写仅作用于临时副本。两个外部脚本保持只读。
ECG v2使用时间戳估计采样率（本次约126.008 Hz），5–20 Hz三阶带通，最小峰距0.30秒，显著度为滤波信号1–99百分位跨度的20%，RR由相邻峰时间差计算。
H10清理参数：RR_REPAIR_METHOD=['split', 'interp']，RR_MULTI_MIN_MS=1200，RR_MULTI_MAX_K=5，RR_MULTI_REL_TOL=0.12；RR_LOW_MS=510.0，RR_HIGH_MS=2000.0，RR_REL_THR=0.2，RR_DABS_MS=150.0，RUN_MAX=10，INTERP_METHOD=pchip，MERGE_ENABLE=False。
这些是旧脚本当前设置，并非本项目新确认的全局质量标准。本次未针对P001调参。
原清理脚本另用NeuroKit2产生ECG参考用于“两路皆异常”提示，和主结果rr_ecg.csv的v2算法不同。
本机NeuroKit2因依赖不兼容未能导入：ValueError('numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject')。原参考加载函数有异常回退，会返回None；本次由此停用可选的“两路皆异常”提示。该参考在clean_device_rr中只影响warning文字，不参与split、插值或输出RR数值。不能将未出现该提示解释为两路均正常。

## 检查与解释限制

ECG v2原函数不剔除跨缺口RR；本次保持原算法，不额外填补采集缺失或修正ECG时间轴。
H10的split依据相邻样本时间差生成分割RR，interp替换短异常段，因此图变平滑不代表真实心跳已被恢复。
RR图仅供比较，不能凭平滑程度判定HRV结果有效。comparison_summary.csv中的局部1.5倍长间隔是探索性描述，不是通过/剔除标准。
当前ECG时间戳推算采样率与设备标称130Hz有差异，应在正式重建RR前另行核查。既有丢包和时间轴问题未在本实验中修复。
算法原函数、参数、输入及源脚本SHA256、运行环境版本保存在provenance.json；清理提示在algorithm_log.txt；清理统计在h10_clean_summary.csv，插值候选段在h10_clean_segments.csv。
原始XDF、merged中的RR/ECG/markers及此前P002人工更正均未改动。


## 后续追加：观察用组合RR

已按研究者要求生成 `rr_combin.csv` 和 `rr_combin.png`：训练前、诱导期、干预后静息结束后使用既有clean RR，其余保留原始RR。四个指定保留阶段已逐行核对。详细边界、来源与替换数量见 `rr_combin_notes.md` 和 `rr_combin_provenance.json`。此组合数据仅用于观察，不替代正式指标数据。
