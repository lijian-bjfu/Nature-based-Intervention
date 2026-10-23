"""日常运行参数：在 VS Code 修改并保存本文件，再打开根目录 run.py 点 Run。

这里只调整已实现任务的选择和展示。固定字段、分类、单位、采样规范不在这里改。
命令行指定的选项仅覆盖本次运行，不改写本文件。
"""

# 一、本次运行。下列任务可单独选，也可组合；系统自动补齐前置步骤。
# app_inventory：核对原始文件
# app_clean：清理历史取值
# app_format：生成标准格式表
# app_describe：描述、绘图与报告（自动先做以上三步）
RUN = {
    "tasks": ["app_describe"],
    "dataset": "logging_test",           # formal / pilot / logging_test
    "sessions": ["*"],                    # * 表示全部，也可填具体会话名或多个通配符
    # 单场示例：["sub-P999_ses-S001_mod-Interactive_run-002"]
    "modules": ["Interactive"],           # Interactive / Practice / Passive
}

# 二、所有数据来源共用的展示参数。
COMMON = {
    "report_language": "auto",            # auto / zh / en
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
    print("参数已载入。请保存修改，再打开同目录 run.py 点击 Run 执行。")
