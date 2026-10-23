from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

D=Path(__file__).resolve().parent
ROOT=Path('/Users/lijian/Working Projects/NBI proj/nature/Assets/_Project/Interaction')
e=pd.read_csv(D/'event_audit.csv',keep_default_na=False)
s=pd.read_csv(D/'session_summary.csv')
stops=pd.read_csv(D/'active_stops.csv')
out={}; short=[]; ring=[]; afterstop=[]; repeat_sens=[]; cases=[]
poses={}
for _,r in s.iterrows():
    sid=r.session;p=pd.read_csv(ROOT/'Logs~'/'Observer'/sid/'pose.tsv',sep='\t');poses[sid]=p
    t=p['时刻'].to_numpy();duration=r.duration_s
    w=np.diff(np.r_[t,duration]);v=p['速度'].to_numpy();g=e[e.session==sid]
    # Same-duration window, no claim that it controls order, starting idle, or scene exposure.
    hi=150.;wt=np.maximum(0,np.minimum(np.r_[t[1:],duration],hi)-t)
    xy=p[['X','Z']].to_numpy();dd=np.linalg.norm(np.diff(xy,axis=0),axis=1)
    ds=np.sum(dd*np.clip((np.minimum(t[1:],hi)-t[:-1])/np.diff(t),0,1))
    ge=g[g['时刻']<=hi]
    short.append(dict(session=sid,student=r.student,mode=r['mode'],seconds=150,events=len(ge),touch=int((ge['触碰']=='★触碰').sum()),blocked=int((ge['受阻']=='是').sum()),distance_m=ds,stationary_pct=100*np.sum(wt[v<=.05])/150,stops=int(((stops.session==sid)&(stops.t<=hi)).sum())))
    for _,z in g[(g['命中层']=='Terrain')&(g['意图']=='走过去')&(g['想走']==0)&(g['发出移动']=='否')].iterrows():
        idx=max(0,np.searchsorted(t,z['时刻'])-1)
        ring.append(dict(session=sid,student=r.student,mode=r['mode'],event=int(z['序号']),t=z['时刻'],distance=z['水平距'],speed_before=v[idx],moving_before=p.iloc[idx]['移动指令']))
    for secs in [2,3,5]:
        for meters in [.5,1,2]:
            m=(pd.to_numeric(g['next_gap_s'],errors='coerce')<=secs)&(pd.to_numeric(g['next_hit_distance_m'],errors='coerce')<=meters)&(g['命中']=='是')&(g['命中'].shift(-1)=='是')
            repeat_sens.append(dict(session=sid,max_seconds=secs,max_meters=meters,pairs=int(m.sum())))
    for _,z in stops[stops.session==sid].iterrows():
        cut=p[(p['时刻']>=z.t)&(p['时刻']<=z.t+1)]
        prior=g[g['时刻']<z.t].iloc[-1]
        afterstop.append(dict(session=sid,t=z.t,csv_line=int(z.csv_line),any_finger_next1s=bool((cut['手指']=='是').any()),prior_event=int(prior['序号']),prior_event_time=float(prior['时刻']),prior_hit=prior['命中层'],prior_distance=prior['水平距'],yaw_change=z.yaw_change_until_1s_or_next_event))

for sid,a,b,label in [('20260906_160018',85,97,'连续六次路径拒绝'),('20260906_155638',188,201,'倒木可达性拒绝'),('20260906_160428',180,216,'后段触摸簇'),('20260906_155148',25,40,'成功接近与低头'),('20260906_155638',77,83,'光圈范围内连续点击')]:
    p=poses[sid];g=e[(e.session==sid)&(e['时刻']>=a)&(e['时刻']<=b)];pp=p[(p['时刻']>=a)&(p['时刻']<=b)]
    cases.append(dict(label=label,session=sid,start=a,end=b,events=g[['序号','时刻','相机X','相机Z','命中X','命中Z','水平距','意图','想走','获准位移','受阻原因','触碰','说明','source_line','tap_csv_line']].to_dict('records'),x_range=[pp.X.min(),pp.X.max()],z_range=[pp.Z.min(),pp.Z.max()],pitch_range=[pp['俯仰'].min(),pp['俯仰'].max()]))
out['stop_stats']=[]
for (student,mode),g in stops.groupby(['student','mode'],sort=False):
    moving=g[g.intent=='停下来']
    out['stop_stats'].append(dict(student=student,mode=mode,n=len(g),moving_n=len(moving),empty_n=len(g)-len(moving),rate_per_min=len(g)*60/float(s[(s.student==student)&(s['mode']==mode)].duration_s.iloc[0]),median_brake_s=moving.time_to_speed05.median(),max_brake_s=moving.time_to_speed05.max(),median_brake_m=moving.displacement_to_speed05.median(),max_brake_m=moving.displacement_to_speed05.max()))
out['same150']=short
out['ring']=ring
out['post_stop_rotation']=afterstop
out['cases']=cases
out['block_families']=e[e['受阻']=='是']['block_family'].value_counts().to_dict()
out['path_reduced_but_not_flagged']=e[(e['受阻']=='否')&(e['想走']-e['获准位移']>.05)][['session','序号','时刻','想走','获准位移']].to_dict('records')
out['touch_by_layer']=e.groupby('命中层')['触碰'].agg(['size',lambda x:int((x=='★触碰').sum())]).reset_index().to_dict('records')
(D/'extended_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)),encoding='utf-8')
pd.DataFrame(short).to_csv(D/'equal150s.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(ring).to_csv(D/'ring_events.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(afterstop).to_csv(D/'post_stop_rotation.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(repeat_sens).to_csv(D/'repeat_sensitivity.csv',index=False,encoding='utf-8-sig')

fonts={f.name for f in font_manager.fontManager.ttflist}
font=next((f for f in ['Arial Unicode MS','PingFang SC','Heiti TC','STHeiti'] if f in fonts),'DejaVu Sans')
plt.rcParams.update({'font.family':font,'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
colors={'光圈':'#29827c','按钮':'#b57a19','双击':'#6659a8'}
fig,axes=plt.subplots(2,3,figsize=(12,9),sharex=True,sharey=True)
for row,student in enumerate(['S1','S2']):
    for col,mode in enumerate(['光圈','按钮','双击']):
        ax=axes[row,col];record=s[(s.student==student)&(s['mode']==mode)]
        ax.set_title(f'{student} · {mode}');ax.set_aspect('equal');ax.set_xlim(46,63);ax.set_ylim(34,76);ax.set_xlabel('世界 X（米）');ax.set_ylabel('世界 Z（米）');ax.grid(alpha=.15)
        if record.empty:
            ax.text(.5,.5,'没有可确认的录制\n不补零、不推断',transform=ax.transAxes,ha='center',va='center',color='#666666');continue
        r=record.iloc[0];p=poses[r.session];g=e[e.session==r.session]
        ax.plot(p.X,p.Z,color=colors[mode],lw=1,alpha=.65)
        ax.scatter(p.X.iloc[0],p.Z.iloc[0],marker='s',s=40,color='#333333',label='起点')
        ax.scatter(p.X.iloc[-1],p.Z.iloc[-1],marker='^',s=45,color=colors[mode],label='终点')
        b=g[g['受阻']=='是'];h=g[g['触碰']=='★触碰']
        ax.scatter(b['相机X'],b['相机Z'],marker='x',s=25,color='#b34b42',label='受阻时位置')
        ax.scatter(h['相机X'],h['相机Z'],s=35,facecolors='none',edgecolors='#168735',label='触摸启动位置')
        ax.text(.04,.02,f'{r.duration_s:.0f} 秒 / {r.distance_m:.1f} 米',transform=ax.transAxes,fontsize=9)
handles,labels=axes[1,0].get_legend_handles_labels()
fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.957),ncol=4,fontsize=9,frameon=False)
fig.suptitle('五段实际轨迹与事件位置',fontsize=16)
fig.text(.5,.012,'同一坐标尺度；无场景底图，不能据此命名河岸或小路。S1 光圈按逐条日志修正归类。',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.035,1,.915));fig.savefig(D/'trajectories.png',dpi=160);plt.close(fig)

fig,axes=plt.subplots(3,1,figsize=(12,7),sharex=True)
for ax,mode in zip(axes,['光圈','按钮','双击']):
    r=s[(s.student=='S2')&(s['mode']==mode)].iloc[0];p=poses[r.session];g=e[e.session==r.session]
    ax.plot(p['时刻'],p['速度'],lw=1,color=colors[mode],label='速度')
    b=g[g['受阻']=='是'];h=g[g['触碰']=='★触碰'];st=stops[stops.session==r.session]
    ax.scatter(b['时刻'],np.full(len(b),1.42),marker='x',color='#b34b42',s=28,label='路径受阻')
    ax.scatter(h['时刻'],np.full(len(h),1.6),marker='o',color='#168735',s=30,label='触摸启动')
    ax.scatter(st.t,np.full(len(st),1.24),marker='v',color='#111111',s=25,label='按钮/双击停止')
    if mode=='光圈':
        re=pd.DataFrame(ring);re=re[re.session==r.session]
        ax.scatter(re.t,np.full(len(re),1.24),marker='v',facecolors='none',edgecolors='#111111',s=30,label='地面零位移判定（意图未知）')
    ax.set_ylim(-.05,1.8);ax.set_ylabel(mode+'\n速度 m/s');ax.grid(alpha=.15);ax.legend(loc='upper left',bbox_to_anchor=(1,1),fontsize=8)
axes[-1].set_xlabel('录制开始后的秒数');axes[-1].set_xlim(0,230)
fig.suptitle('学生二：移动、停止、路径受阻与触摸的时间关系',fontsize=15)
fig.tight_layout(rect=(0,0,1,.95));fig.savefig(D/'s2_timeline.png',dpi=160);plt.close(fig)

# Independent recomputation using csv and math, rather than numpy trajectory code.
import csv,math
checks=[]
for _,r in s.iterrows():
    path=ROOT/'Logs~'/'Observer'/r.session/'pose.tsv'
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig'),delimiter='\t'))
    distance=sum(math.hypot(float(b['X'])-float(a['X']),float(b['Z'])-float(a['Z'])) for a,b in zip(rows,rows[1:]))
    stationary=sum((float(rows[i+1]['时刻']) if i+1<len(rows) else r.duration_s)-float(a['时刻']) for i,a in enumerate(rows) if float(a['速度'])<=.05)
    assert abs(distance-r.distance_m)<1e-8
    assert abs(stationary*100/r.duration_s-r.stationary_pct)<1e-8
    checks.append(dict(session=r.session,distance_difference_m=distance-r.distance_m,stationary_pct_difference=stationary*100/r.duration_s-r.stationary_pct))
pd.DataFrame(checks).to_csv(D/'independent_checks.csv',index=False,encoding='utf-8-sig')
source=pd.read_csv(D/'sources.csv')
extra=[Path('/Users/lijian/Desktop/访谈.txt'),ROOT/'TapLog.cs',ROOT/'Avatar Camera'/'TapMoveCamera_V5.cs',ROOT/'Avatar Camera'/'TapMoveCamera_V5_Observer.cs',ROOT/'Observer'/'ObserverRecorder.cs',ROOT/'Hand'/'IndicatorHand.cs']
source=pd.concat([source,pd.DataFrame([dict(path=str(f),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in extra])],ignore_index=True).drop_duplicates('path')
source.to_csv(D/'sources.csv',index=False,encoding='utf-8-sig')
print(json.dumps({k:v for k,v in out.items() if k not in ['cases','ring','post_stop_rotation']},ensure_ascii=False,indent=2))
print('Ring moving before:',pd.DataFrame(ring).groupby('session').speed_before.agg(['size',lambda x:int((x>.05).sum())]).to_string())
print('Rotation > 10deg:',pd.DataFrame(afterstop).query('abs(yaw_change)>10').to_dict('records'))
print('Font:',font)
