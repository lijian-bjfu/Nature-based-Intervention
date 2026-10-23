"""Track 描述报告：接收本次计算结果，不重新读取或计算原始数据。"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"00_settings.py").is_file())
sys.path.insert(0,str(PROJECT))
from importlib import import_module
settings = import_module("00_settings")
sys.path.insert(0,str(settings.TOOLS_DIR))
import pandas as pd
from artifacts import markdown_table
from configuration import AppDescribeOptions

def make_report(summary,layers,look_stats,bins,tables,dest,images,language,options: AppDescribeOptions):
    zh=language=="zh"
    text=lambda cn,en: cn if zh else en
    number=lambda x,precision=3: "—" if x is None else f"{x:.{precision}f}"
    duration=number(summary["duration_s"])
    sp=summary["space"]
    table_status=pd.DataFrame([{"table":name,**value} for name,value in summary["tables"].items()])
    tap_n=summary["tables"]["tap"]["rows"]
    touches=summary["tap"]["is_touched_TRUE_n"]
    blocked=summary["tap"]["blocked_n"]
    fragments=[
        "# "+text("埋点数据描述","Track record description"),
        summary["session_dir"],
        "## "+text("原理与方法","Purpose and methods"),
        text("本报告描述记录到的环境接触与操作过程。先交代可用数据，再呈现触摸、世界事件、受阻、转动以及时间和空间分布。行为事实不直接解释为兴趣、注意、无聊或动机。",
             "This report describes recorded environmental contact and interaction. It first establishes data availability, then summarizes touches, world events, path restrictions, turns, and temporal and spatial distributions. Behavior alone does not establish interest, attention, boredom or motivation."),
        text("数据由根目录 02_run.py 调度：01 核对文件，02 在副本中处理已定的历史取值，03 统一类型，06 从标准表生成描述。固定字段、方法与路径来自 00_settings.py，可调参数来自 01_parameters.py；未定义新的行为指标。",
             "The root runner executes inventory, configured legacy-value cleaning, type formatting and description. Fixed columns, methods and paths come from 00_settings.py; adjustable options come from 01_parameters.py. No new behavioral metric is defined."),
        "## "+text("记录范围与可用性","Recording scope and availability"),
        text(f"session.t_device_end − session.t_device_start = {duration} 秒。缺失文件的行数显示为空，不按零次行为解释。",
             f"session.t_device_end − session.t_device_start = {duration} seconds. Missing-file counts are unavailable, rather than zero."),
        markdown_table(table_status),
        "## "+text("操作与实际接触","Actions and recorded contact"),
        text(f"tap 行数为 {tap_n if tap_n is not None else '不可用'}；tap.is_touched=TRUE 为 {touches if touches is not None else '不可用'}；tap.block_type 为 CutShort/NoStart 的行数合计 {blocked if blocked is not None else '不可用'}。未触摸不等于操作失败，LookAt 也不等于明确的触摸意图。",
             f"tap rows: {tap_n}; tap.is_touched=TRUE: {touches}; rows with tap.block_type CutShort/NoStart: {blocked}. A non-touch is not necessarily a failed action, and LookAt does not establish an intention to touch."),
        markdown_table(layers) if not layers.empty else text("点击数据不可用或无记录。","Tap data are unavailable or empty."),
        text("下列类别计数由 summary.json 保存；历史 None 已按配置分别映射为 NoHit/NotBlocked。","The following category counts are stored in summary.json. Legacy None values are mapped to NoHit/NotBlocked only in configured fields."),
    ]
    for field in ("intent","block_type","block_reason"):
        data=summary["tap"][field]
        if data is not None:
            fragments += [markdown_table(pd.DataFrame([{"field":f"tap.{settings.column('tap',field)}","level":k,"rows":v} for k,v in data.items()]))]
    fragments += ["## "+text("转动、后退与世界事件","Turns, backsteps and world events"),
        markdown_table(look_stats) if not look_stats.empty else text("没有可用的环视记录。","No available look records."),
        text("转动段数与触屏次数分开，Drag 包含惯性；Tap 是系统响应。累计角路程不代表净转圈数或操作负担。","Look episodes and touch IDs are distinct. Drag includes inertia; Tap is a system response. Angular path is neither net rotations nor operational burden.")]
    for table in ("backstep","world_event","tech_glitch"):
        fragments += ["### "+table,
                      markdown_table(tables[table]) if not tables[table].empty else
                      text("表存在但没有记录。" if tables[table].attrs["present"] else "文件缺失，无法判断次数。",
                           "Table present with no rows." if tables[table].attrs["present"] else "File missing; count unavailable.")]
    fragments += ["## "+text("时间与空间","Time and space"),
        text(f"按相邻 spacetime.cam_x/cam_z 连线求和的水平折线长为 {number(sp['horizontal_path_m'],2)} 米。这是采样近似，未做平滑或插补，不解释为体力消耗、停留或覆盖率。命中点不是到达点。",
             f"Horizontal polyline length from consecutive spacetime.cam_x/cam_z samples: {number(sp['horizontal_path_m'],2)} m. This is a sampling approximation without smoothing or interpolation, not physical effort, dwell or coverage. A hit location is not an arrival location."),
        text(f"时间箱宽度设置为 {options.time_bin_seconds:g} 秒，每箱实际 observed_s 单独列出。","Time bins use the configured width; observed_s reports each bin's actual duration."),
        markdown_table(bins) if not bins.empty else text("无法生成时间分箱或没有记录。","Time bins are unavailable or empty."),
        "## "+text("数据检查","Data checks"),
        text("技术异常保留在原始时段中；本轮不执行被试排除或行为分类。world_event 的 Fired 不证明注意，HandStartle 只对应常驻停落生物，不能覆盖所有手触发剧本事件。",
             "Technical interruptions remain in the recorded timeline; no participant exclusion or behavioral classification is applied. Fired does not establish attention. HandStartle concerns resident perched creatures and does not enumerate all hand-triggered scripted events."),
    ]
    notes=summary["quality"]["notes"]
    fragments += ["\n".join("- "+note for note in notes) if notes else text("未发现文件缺失或时间顺序警告；这不等于已检验全部研究数据质量。","No missing-file or time-order warning; this does not establish full research-data validity.")]
    for stem in settings.APP_FIGURES.values():
        image=next((name for ext in ("png","svg","pdf") for name in images
                    if name==stem+"."+ext),None)
        if image:
            fragments += [f"[{image}]({image})" if image.endswith(".pdf") else f"![{image}]({image})"]
    fragments += ["## "+text("复现","Reproduction"),
        text("本次运行的根目录含 manifest.json、settings_snapshot.json 与 parameters_snapshot.json，可核对输入 SHA-256、脚本 SHA-256、选择范围与配置。原始数据不改写，文字与图表由同次计算生成。",
             "The run root contains manifest.json, settings_snapshot.json and parameters_snapshot.json with input and script SHA-256, selection and configuration. Raw data remain unchanged; text and figures derive from the same computation.")]
    (dest/"report.md").write_text("\n\n".join(fragments)+"\n",encoding="utf-8")

