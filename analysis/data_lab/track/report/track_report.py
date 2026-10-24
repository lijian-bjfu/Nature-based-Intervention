"""Track 描述报告：接收本次计算结果，不重新读取或计算原始数据。"""
SCRIPT_HISTORY = [
    {"at": "2026-10-23T20:36:13+08:00", "action": "first_versioned",
     "summary": "已有报告工具首次纳入 Git；原始创建时间未知。", "commit": "38cdd46dd4da3d1f614d5f558a10f886d96cbafb"},
    {"at": "2026-10-23T20:48:27+08:00", "action": "refactor",
     "summary": "改用共享原始字段规范及实验自己的方法登记，更新本地参数、输出与运行追溯说明。"},
    {"at": "2026-10-24T12:55:00+08:00", "action": "modified",
     "summary": "运行追溯说明改为：已提交源码凭提交号还原，只复制未提交的源码。"},
]

from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0] = [str(PROJECT),str(PROJECT/"analysis"),str(PROJECT/"analysis/tools")]
import pandas as pd
import global_settings as settings
from artifacts import markdown_table
from data_lab.track.description.record_description.experiment import TrackDescribeOptions, FIGURES

def make_report(summary,layers,look_stats,bins,tables,dest,images,language,options: TrackDescribeOptions):
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
        text("本记录描述实验依次核对文件、在副本中处理已定历史取值、统一类型，再从标准表生成描述。原始字段与标签来自 global_settings.py；参数来自入口 track_describe.py 的 PARAMETERS，方法与依赖属于本实验；未定义新的行为指标。",
             "This local experiment executes inventory, specified legacy-value cleaning, type formatting and description. Raw field definitions and labels come from global_settings.py; adjustable options come from PARAMETERS in track_describe.py. No new behavioral metric is defined."),
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
    for stem in FIGURES.values():
        image=next((name for ext in ("png","svg","pdf") for name in images
                    if name==stem+"."+ext),None)
        if image:
            fragments += [f"[{image}]({image})" if image.endswith(".pdf") else f"![{image}]({image})"]
    fragments += ["## "+text("复现","Reproduction"),
        text("本次结果目录含 manifest.json、global_settings_snapshot.json、parameters_snapshot.json，若有未提交的源码修改另含 uncommitted_sources。manifest 记录整次和各步骤的起止时间、Git 提交号、工作树状态与输入/源码 SHA-256；已提交的源码凭提交号还原，未提交的修改单独保存副本。原始数据不改写，文字与图表由同次计算生成。",
             "The result directory contains manifest.json, global_settings_snapshot.json and parameters_snapshot.json, plus uncommitted_sources when sources had uncommitted edits. It records run and step timestamps, Git commit and working-tree status, and input/source SHA-256. Committed sources are recoverable from the commit; uncommitted edits are copied. Raw data remain unchanged; text and figures derive from the same computation.")]
    (dest/"report.md").write_text("\n\n".join(fragments)+"\n",encoding="utf-8")

