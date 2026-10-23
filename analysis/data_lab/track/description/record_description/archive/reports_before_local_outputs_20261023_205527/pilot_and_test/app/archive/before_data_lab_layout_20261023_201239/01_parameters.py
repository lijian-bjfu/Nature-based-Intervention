"""日常运行参数：在 VS Code 修改并保存本文件，再打开根目录 02_run.py 点 Run。

这里只调整已实现任务的选择和展示。固定字段、分类、单位、采样规范不在这里改。
命令行指定的选项仅覆盖本次运行，不改写本文件。
"""

# 一、本次运行：先选“做什么”，再选“用哪些数据”。
#
# tasks = 工作任务（可选多个，系统自动补齐前置步骤）：
#   "app_inventory"  核对埋点原始文件是否齐全，不做清理或报告。
#   "app_clean"      清理已确认的历史取值，只生成处理数据，不生成报告。
#   "app_format"     清理后统一字段类型，生成标准表，不生成报告。
#   "app_describe"   埋点描述、绘图与文字报告；已包含前三项，通常只选它。
#
# dataset = 输入数据范围（不是实验组别，也不是报告分类）：
#   "formal"        正式实验数据，位置：data/formal/
#   "pilot"         被试预实验数据，位置：data/pilot_and_test/pilot/
#   "logging_test"  编辑器/开发期间的埋点测试，位置：data/pilot_and_test/logging_test/
#   目前这四场开发记录应选 "logging_test"。
#
# sessions = 上述范围内要处理哪些“会话文件夹”：
#   ["*"]                          全部匹配会话
#   ["sub-P999*"]                  文件夹名以 sub-P999 开头的会话
#   ["具体会话名"]                  只选一场；直接从 raw/app/ 复制文件夹名称
#   ["具体会话名1", "具体会话名2"]   选择多场
#   "*" 是文件名通配符，不代表某个被试编号；无需填写路径。
#
# modules = APP 模块（名称区分大小写，不是实验组别）：
#   "Interactive"  正式场景中的自由交互体验，目前埋点描述主要分析这一模块。
#   "Practice"     练习场，按规范只记录会话信息，不具备操作行为表。
#   "Passive"      被动观看视频，当前只记录会话信息，行为描述不适用。
#   选择模块只筛选已有记录，不会补出未采集的行为数据。
#
# 查词：本段已列出 RUN 的全部选项；根目录 README.md 的“运行选项对照”有同一说明。
# 日常不需要查 00_settings.py 或分析代码。保留引号内的英文，只改选择的值。
RUN = {
    "tasks": ["app_describe"],             # 做什么：埋点描述、绘图与报告
    "dataset": "logging_test",           # 用哪些数据：开发埋点测试（选项见上）
    "sessions": ["*"],                    # * 表示全部，也可填具体会话名或多个通配符
    # 单场示例：["sub-P999_ses-S001_mod-Interactive_run-002"]
    "modules": ["Interactive"],           # 筛选哪种模块：自由交互（选项见上）
}

# 二、所有数据来源共用的展示参数。
COMMON = {
    "report_language": "auto",            # auto 自动按下表选择 / zh 中文 / en 英文
    "language_by_group": {                # auto 时使用；与数据集路径登记分开
        "formal": "en",
        "pilot_and_test": "zh",
    },
    "figure": {
        "dpi": 160,                      # 正整数
        "formats": ["png"],              # 可选 png / svg / pdf；可同时保存多种
        "font": "Arial Unicode MS",      # 中文报告需使用支持中文的字体
        "font_size": 10,                 # 正数
    },
}

# 三、按数据性质分组，再按工作任务分组。
# 目前只有埋点描述；问卷和生理参数在对应功能实现时再增加。
APP = {
    "describe": {
        "time_bin_seconds": 60.0,         # 描述图分箱宽度，单位秒，必须大于 0
                                         # 与原始 0.1 秒采样规范是两件事
        "interval_quantiles": [0.5, 0.95, 0.99],  # 采样间隔的描述分位数，范围 0–1
        "colors": {                      # 只改变展示，不改变类别含义
            "NotBlocked": "#22866B",
            "CutShort": "#D69325",
            "NoStart": "#C44545",
            "Drag": "#22866B",
            "Tap": "#4169A2",
            "event": "#A34EAA",
        },
    },
}

if __name__ == "__main__":
    print("参数已载入。请保存修改，再打开同目录 02_run.py 点击 Run 执行。")
