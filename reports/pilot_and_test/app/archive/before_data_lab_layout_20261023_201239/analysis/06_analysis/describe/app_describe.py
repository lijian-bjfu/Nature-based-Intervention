"""06：可复用的 APP 埋点描述。读 03 标准表，生成本次运行的表、图与文字。"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
PROJECT = next(p for p in Path(__file__).resolve().parents if (p/"00_settings.py").is_file())
sys.path.insert(0,str(PROJECT))
from importlib import import_module
settings = import_module("00_settings")
sys.path.insert(0,str(settings.TOOLS_DIR))
from decimal import Decimal
import math
import numpy as np
import pandas as pd
from app_io import read_session
from artifacts import records, write_json, markdown_table
from paths import stage_dir
from plotting import pyplot, save_figure
from configuration import AppDescribeOptions, FigureOptions, RunContext

def series(tables, table, field):
    return tables[table][settings.column(table,field)]

def ordered_levels(values, configured):
    return list(configured)+[x for x in values.dropna().unique() if x not in configured]

def category_counts(tables, table, field, levels=None):
    if not tables[table].attrs["present"]:
        return None
    values=series(tables,table,field)
    levels=ordered_levels(values, levels if levels is not None else
                          settings.APP_LEVELS.get(table,{}).get(field,()))
    return {str(x):int(values.eq(x).fillna(False).sum()) for x in levels}

def describe(tables, session_name, options: AppDescribeOptions):
    meta=tables["session"]
    if len(meta)!=1:
        raise ValueError(f"{session_name}: session 表应恰有一行，实际 {len(meta)}")
    module=series(tables,"session","module").iloc[0]
    start=series(tables,"session","t_device_start").iloc[0]
    end=series(tables,"session","t_device_end").iloc[0]
    duration=None if pd.isna(start) or pd.isna(end) else float(Decimal(str(end))-Decimal(str(start)))
    notes=[]
    if duration is None:
        notes.append("Missing session.t_device_end/start; full session duration is unavailable.")
    elif duration<0:
        raise ValueError(f"{session_name}: 会话结束早于开始")
    required=settings.APP_REQUIRED_TABLES.get(module,("session",))
    status={}
    for name,frame in tables.items():
        present=bool(frame.attrs["present"])
        status[name]={"present":present,"rows":len(frame) if present else None,
                      "applicable":name in required}
        if name in required and not present:
            notes.append(f"Missing required file: {settings.APP_FILES[name]}; counts are unavailable, not zero.")
    sp=tables["spacetime"]
    space={"horizontal_path_m":None,"first_s":None,"last_s":None,"intervals_s":None,
           "start_xz":None,"end_xz":None,"start_end_displacement_m":None}
    if not sp.empty:
        t=series(tables,"spacetime","t_session").to_numpy(dtype=float,na_value=np.nan)
        x=series(tables,"spacetime","cam_x").to_numpy(dtype=float,na_value=np.nan)
        z=series(tables,"spacetime","cam_z").to_numpy(dtype=float,na_value=np.nan)
        if not np.isfinite(np.r_[t,x,z]).all():
            notes.append("Missing spacetime time/position; no path length calculated.")
        else:
            delta=np.diff(t)
            if (delta<=0).any():
                notes.append("spacetime.t_session is not strictly increasing; no path length calculated.")
            else:
                path=math.fsum(math.hypot(x1-x0,z1-z0)
                    for x0,z0,x1,z1 in zip(x[:-1],z[:-1],x[1:],z[1:]))
                space["horizontal_path_m"]=path
            space.update(first_s=float(t[0]),last_s=float(t[-1]),start_xz=[float(x[0]),float(z[0])],
                         end_xz=[float(x[-1]),float(z[-1])],
                         start_end_displacement_m=float(math.hypot(x[-1]-x[0],z[-1]-z[0])))
            if len(delta):
                space["intervals_s"]={"min":float(delta.min()),"max":float(delta.max()),
                    **{f"q{q:g}":float(np.quantile(delta,q))
                       for q in options.interval_quantiles}}
    tap=tables["tap"]
    layer_levels=settings.APP_LEVELS["tap"]["hit_layer"]
    layer_rows=[]
    touched=tap.iloc[:0].copy()
    if tap.attrs["present"]:
        flag=series(tables,"tap","is_touched")
        touched=tap.loc[flag.fillna(False)].copy()
        for layer in ordered_levels(series(tables,"tap","hit_layer"),layer_levels):
            mask=series(tables,"tap","hit_layer").eq(layer).fillna(False)
            layer_rows.append({"hit_layer":layer,"tap_n":int(mask.sum()),
                "is_touched_TRUE_n":int((mask & flag.fillna(False)).sum()),
                "is_touched_FALSE_n":int((mask & flag.eq(False).fillna(False)).sum()),
                "is_touched_missing_n":int((mask & flag.isna()).sum())})
    layers=pd.DataFrame(layer_rows,columns=["hit_layer","tap_n","is_touched_TRUE_n",
                                         "is_touched_FALSE_n","is_touched_missing_n"])
    block_counts=category_counts(tables,"tap","block_type")
    blocked=None if block_counts is None else (
        block_counts.get("CutShort",0)+block_counts.get("NoStart",0))
    touch_n=int(series(tables,"tap","is_touched").eq(True).sum()) if tap.attrs["present"] else None
    look_rows=[]
    look=tables["look"]
    if look.attrs["present"]:
        kinds=ordered_levels(series(tables,"look","look_type"),settings.APP_LEVELS["look"]["look_type"])
        for kind in kinds:
            mask=series(tables,"look","look_type").eq(kind).fillna(False)
            times=series(tables,"look","t_session_end")[mask]-series(tables,"look","t_session_start")[mask]
            if times.lt(0).any():
                notes.append(f"Negative look duration in {kind}; duration sum is unavailable.")
            look_rows.append({"look_type":kind,"segments_n":int(mask.sum()),
                "touch_ids_n":int(series(tables,"look","touch_id")[mask].nunique()),
                "duration_sum_s":float(times.sum()) if len(times) and not times.lt(0).any() and times.notna().all() else None,
                "duration_median_s":float(times.median()) if len(times) else None,
                "yaw_path_sum_deg":float(series(tables,"look","yaw_path")[mask].sum()) if mask.any() else 0.0,
                "pitch_path_sum_deg":float(series(tables,"look","pitch_path")[mask].sum()) if mask.any() else 0.0})
    look_stats=pd.DataFrame(look_rows,columns=["look_type","segments_n","touch_ids_n","duration_sum_s",
                                             "duration_median_s","yaw_path_sum_deg","pitch_path_sum_deg"])
    bin_rows=[]
    if duration and duration>0 and tap.attrs["present"]:
        edges=np.r_[np.arange(0,duration,options.time_bin_seconds),duration]
        for left,right in zip(edges[:-1],edges[1:]):
            # 最后一箱含结束点；其余采用左闭右开。
            mask=series(tables,"tap","t_session").ge(left) & (
                series(tables,"tap","t_session").le(right) if right==duration
                else series(tables,"tap","t_session").lt(right))
            item={"start_s":float(left),"end_s":float(right),"observed_s":float(right-left),
                  "tap_n":int(mask.sum()),"is_touched_TRUE_n":int((mask & series(tables,"tap","is_touched").fillna(False)).sum())}
            for kind in settings.APP_LEVELS["tap"]["block_type"]:
                item[kind]=int((mask & series(tables,"tap","block_type").eq(kind).fillna(False)).sum())
            bin_rows.append(item)
    bins=pd.DataFrame(bin_rows,columns=["start_s","end_s","observed_s","tap_n","is_touched_TRUE_n"]+
                      list(settings.APP_LEVELS["tap"]["block_type"]))
    # 质量描述只标记、不排除；出现缺失表不冒充零次操作。
    missing={name:{str(k):int(v) for k,v in frame.isna().sum().items() if v}
             for name,frame in tables.items() if frame.attrs["present"]}
    ordering={}
    for name,frame in tables.items():
        field="t_session_start" if name=="look" else "t_session"
        if frame.attrs["present"] and field in settings.APP_COLUMNS[name]:
            col=series(tables,name,field)
            ordering[name]=bool(col.is_monotonic_increasing)
            if not ordering[name]:
                notes.append(f"{name}.{settings.column(name,field)} is not monotonic.")
    known_ids=set()
    for name in ("tap","backstep","look"):
        known_ids.update(int(v) for v in series(tables,name,"touch_id").dropna())
    summary={"session_dir":session_name,"session":records(meta)[0],"duration_s":duration,
        "tables":status,"space":space,"tap":{"intent":category_counts(tables,"tap","intent"),
            "hit_layer":category_counts(tables,"tap","hit_layer"),
            "block_type":block_counts,"block_reason":category_counts(tables,"tap","block_reason"),
            "blocked_n":blocked,"is_touched_TRUE_n":touch_n},
        "look":records(look_stats),"backstep":records(tables["backstep"]) if tables["backstep"].attrs["present"] else None,
        "world_event":records(tables["world_event"]) if tables["world_event"].attrs["present"] else None,
        "tech_glitch":records(tables["tech_glitch"]) if tables["tech_glitch"].attrs["present"] else None,
        "quality":{"missing_cells":missing,"monotonic_time":ordering,"observed_touch_ids_n":len(known_ids),
            "touch_id_range":[min(known_ids),max(known_ids)] if known_ids else None,
            "missing_touch_ids_in_observed_range":sorted(set(range(1,max(known_ids)+1))-known_ids) if known_ids else [],
            "notes":notes},
        "methods":{"trajectory":settings.APP_DESCRIPTION_METHOD,
                   "time_bin_seconds":options.time_bin_seconds,
                   "scope":"description only; no new behavioral metric or threshold"}}
    return summary,layers,look_stats,bins,touched

def plots(tables, summary, layers, bins, look_stats, dest, lang, options: AppDescribeOptions, figure: FigureOptions):
    plt=pyplot(figure)
    zh=lang=="zh"
    colors=options.colors
    sp,tap,look,world=(tables[k] for k in ("spacetime","tap","look","world_event"))
    images=[]
    text=lambda cn,en: cn if zh else en
    def values(table,field,mask=None):
        s=series(tables,table,field)
        return (s if mask is None else s[mask]).to_numpy(dtype=float,na_value=np.nan)
    def legend(ax):
        if ax.get_legend_handles_labels()[0]: ax.legend(fontsize=8)
    fig,axs=plt.subplots(1,2,figsize=(13,7),layout="constrained")
    for ax in axs:
        if not sp.empty:
            ax.plot(values("spacetime","cam_x"),values("spacetime","cam_z"),color="#A8B9B3",lw=1,label="spacetime")
            ax.scatter(values("spacetime","cam_x")[[0,-1]],values("spacetime","cam_z")[[0,-1]],
                       marker="s",s=30,color="black",label=text("起止点","Start/end"))
        else: ax.text(.5,.5,text("没有位姿记录","No pose records"),ha="center",transform=ax.transAxes)
        ax.set(xlabel="World X (m)",ylabel="World Z (m)")
        ax.set_aspect("equal",adjustable="datalim");ax.grid(alpha=.15)
    for kind in settings.APP_LEVELS["tap"]["block_type"]:
        mask=series(tables,"tap","block_type").eq(kind).fillna(False)
        if mask.any():
            axs[0].scatter(values("tap","cam_x",mask),values("tap","cam_z",mask),
                           c=colors[kind],s=25,label=f"tap.block_type={kind}")
    if world.attrs["present"]:
        mask=series(tables,"world_event","action").eq("Fired").fillna(False)
        if mask.any():
            axs[0].scatter(values("world_event","cam_x",mask),values("world_event","cam_z",mask),
                           marker="D",s=55,c=colors["event"],label="world_event.Fired")
    cmap=plt.get_cmap("tab10")
    for i,layer in enumerate(settings.APP_LEVELS["tap"]["hit_layer"]):
        mask=series(tables,"tap","hit_layer").eq(layer).fillna(False)
        if mask.any():
            axs[1].scatter(values("tap","hit_x",mask),values("tap","hit_z",mask),s=25,
                           color=cmap(i%10),alpha=.8,label=layer)
    mask=series(tables,"tap","is_touched").eq(True).fillna(False)
    if mask.any():
        axs[1].scatter(values("tap","hit_x",mask),values("tap","hit_z",mask),marker="*",s=140,
                       c="white",edgecolors="black",label="tap.is_touched=TRUE",zorder=5)
    axs[0].set_title(text("轨迹与点击时相机位置","Trajectory and camera position at taps"))
    axs[1].set_title(text("命中点与最终触摸结果","Hit locations and final touch outcomes"))
    for ax in axs:legend(ax)
    fig.suptitle(summary["session_dir"],fontsize=12)
    images+=save_figure(fig,dest,settings.APP_FIGURES["space"],figure);plt.close(fig)

    fig,axs=plt.subplots(4,1,figsize=(13,11),sharex=True,layout="constrained")
    if not sp.empty:
        for field in ("cam_x","cam_z"):
            axs[0].plot(values("spacetime","t_session")/60,values("spacetime",field),label=f"spacetime.{field}",lw=1)
    axs[0].set_ylabel("m");legend(axs[0])
    for lane,kind in enumerate(settings.APP_LEVELS["tap"]["block_type"]):
        mask=series(tables,"tap","block_type").eq(kind).fillna(False)
        axs[1].scatter(values("tap","t_session",mask)/60,np.full(int(mask.sum()),lane),marker="|",s=30,c=colors[kind])
    mask=series(tables,"tap","is_touched").eq(True).fillna(False)
    axs[1].scatter(values("tap","t_session",mask)/60,np.full(int(mask.sum()),3),marker="*",s=70,c=colors["Drag"])
    axs[1].set_yticks([0,1,2,3],list(settings.APP_LEVELS["tap"]["block_type"])+["is_touched=TRUE"])
    for lane,kind in enumerate(settings.APP_LEVELS["look"]["look_type"]):
        mask=series(tables,"look","look_type").eq(kind).fillna(False)
        starts=values("look","t_session_start",mask)/60
        lengths=(values("look","t_session_end",mask)-values("look","t_session_start",mask))/60
        valid=np.isfinite(starts)&np.isfinite(lengths)&(lengths>=0)
        axs[2].broken_barh(list(zip(starts[valid],lengths[valid])),(lane-.2,.4),facecolors=colors[kind])
    axs[2].set_yticks(range(len(settings.APP_LEVELS["look"]["look_type"])),settings.APP_LEVELS["look"]["look_type"])
    if not bins.empty:
        bottom=np.zeros(len(bins))
        for kind in settings.APP_LEVELS["tap"]["block_type"]:
            axs[3].bar(bins.start_s/60,bins[kind],bottom=bottom,width=bins.observed_s/60*.92,
                       align="edge",color=colors[kind],label=kind)
            bottom+=bins[kind].to_numpy()
        legend(axs[3])
    titles=[text("水平位置","Horizontal position"),text("点击结果（触摸标记使用原点击时间）","Tap outcomes (touch marker uses original tap time)"),
            text("转动段：Drag 与点击系统转向分开","Look episodes: Drag and click-driven turns"),
            text("时间箱点击计数；末箱可能不足完整时长","Tap counts per time bin; final bin may be partial")]
    for ax,title in zip(axs,titles):
        ax.set_title(title,loc="left",fontsize=10);ax.grid(axis="x",alpha=.15)
        if summary["duration_s"]:ax.set_xlim(0,summary["duration_s"]/60)
    axs[-1].set_xlabel("t_session (min)")
    fig.suptitle(summary["session_dir"],fontsize=12)
    images+=save_figure(fig,dest,settings.APP_FIGURES["time"],figure);plt.close(fig)

    fig,axs=plt.subplots(1,2,figsize=(13,6),layout="constrained")
    if not layers.empty:
        pos=np.arange(len(layers))
        axs[0].barh(pos,layers.is_touched_FALSE_n,color="#B5C5C0",label="is_touched=FALSE")
        axs[0].barh(pos,layers.is_touched_TRUE_n,left=layers.is_touched_FALSE_n,
                    color=colors["Drag"],label="is_touched=TRUE")
        axs[0].set_yticks(pos,layers.hit_layer);axs[0].invert_yaxis();legend(axs[0])
    else:axs[0].text(.5,.5,text("没有可用的点击表记录","No available tap records"),ha="center",transform=axs[0].transAxes)
    if not look_stats.empty:
        pos=np.arange(len(look_stats))
        axs[1].bar(pos-.18,look_stats.yaw_path_sum_deg,width=.36,label="look.yaw_path",color=colors["Tap"])
        axs[1].bar(pos+.18,look_stats.pitch_path_sum_deg,width=.36,label="look.pitch_path",color=colors["Drag"])
        axs[1].set_xticks(pos,look_stats.look_type);legend(axs[1])
    else:axs[1].text(.5,.5,text("没有可用的环视表记录","No available look records"),ha="center",transform=axs[1].transAxes)
    axs[0].set(xlabel="tap rows",title=text("命中层和最终触摸结果","Hit layers and final touch outcomes"))
    axs[1].set(ylabel="degree",title=text("按来源累计转动角路程","Angular path by source"))
    fig.suptitle(summary["session_dir"],fontsize=12)
    images+=save_figure(fig,dest,settings.APP_FIGURES["actions"],figure);plt.close(fig)
    return images

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
        "# "+text("埋点数据描述","APP log description"),
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

def run(context: RunContext):
    overview=[]
    for source in context.sessions:
        incoming=stage_dir(context,"03_format",source.name)/settings.STAGE_TABLE_FOLDER
        tables=read_session(incoming,formatted=True)
        summary,layers,look_stats,bins,touched=describe(tables,source.name,context.config.app_describe)
        dest=stage_dir(context,"06_analysis",source.name)
        dest.mkdir(parents=True,exist_ok=False)
        write_json(dest/"summary.json",summary)
        for filename,frame in [("table_layers.csv",layers),("table_look.csv",look_stats),
                               ("table_time_bins.csv",bins),("touch_records.csv",touched)]:
            frame.to_csv(dest/filename,index=False,na_rep="")
        images=plots(tables,summary,layers,bins,look_stats,dest,context.language,context.config.app_describe,context.config.figure)
        make_report(summary,layers,look_stats,bins,tables,dest,images,context.language,context.config.app_describe)
        overview.append({"session_dir":source.name,"duration_s":summary["duration_s"],
                         "spacetime_rows":summary["tables"]["spacetime"]["rows"],
                         "tap_rows":summary["tables"]["tap"]["rows"],
                         "touched_TRUE_rows":summary["tap"]["is_touched_TRUE_n"],
                         "blocked_tap_rows":summary["tap"]["blocked_n"],
                         "warnings":len(summary["quality"]["notes"])})
    base=stage_dir(context,"06_analysis")
    frame=pd.DataFrame(overview)
    frame.to_csv(base/"sessions.csv",index=False,na_rep="")
    title="埋点描述运行索引" if context.language=="zh" else "APP description run index"
    links="\n".join(f"- [{row['session_dir']}]({row['session_dir']}/report.md)" for row in overview)
    (base/"index.md").write_text("# "+title+"\n\n"+markdown_table(frame)+"\n\n"+links+"\n",encoding="utf-8")

if __name__=="__main__":
    from pipeline import cli
    cli(("app_describe",))
