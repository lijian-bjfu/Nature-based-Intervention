from pathlib import Path
import csv, json, hashlib, math
import numpy as np
import pandas as pd

ROOT=Path('/Users/lijian/Working Projects/NBI proj/nature/Assets/_Project/Interaction')
OUT=Path(__file__).resolve().parent
SESSIONS=[('S1','双击','154826','154418'),('S1','光圈','155148','154912'),('S2','光圈','155638','155249'),('S2','按钮','160018','155658'),('S2','双击','160428','160040')]
def read_tap(path):
    lines=path.read_text(encoding='utf-8-sig').splitlines()
    rows=list(csv.reader([l for l in lines if l and not l.startswith('#')]))
    header=rows[0]
    assert all(len(r)==len(header)+1 and r[-1]=='' for r in rows[1:]), path
    df=pd.DataFrame([r[:-1] for r in rows[1:]],columns=header)
    for c in ['序号','时刻','距上击秒','上击后位移m','相机X','相机Y','相机Z','偏航','俯仰','水平距m','想走m','实走m','命中X','命中Y','命中Z']:
        df[c]=pd.to_numeric(df[c])
    df['source_line']=np.arange(len(df))+4
    return df
def segments(mask,t,end):
    starts=np.flatnonzero(mask & np.r_[True,~mask[:-1]])
    stops=np.flatnonzero(mask & np.r_[~mask[1:],True])+1
    return [(float(t[a]),float(t[b] if b<len(t) else end),int(a),int(b)) for a,b in zip(starts,stops)]
def circdiff(a): return (np.diff(a)+180)%360-180
def gridstats(p,size,origin=(0,0),minstay=0):
    xy=p[['X','Z']].to_numpy(); t=p['时刻'].to_numpy()
    cells=np.floor((xy-origin)/size).astype(int)
    ix=np.r_[0,np.flatnonzero(np.any(np.diff(cells,axis=0)!=0,axis=1))+1]
    stops=np.r_[ix[1:],len(p)-1]
    seq=[tuple(cells[a]) for a,b in zip(ix,stops) if t[b]-t[a]>=minstay]
    seq=[x for i,x in enumerate(seq) if not i or x!=seq[i-1]]
    return len(set(seq)),len(seq), (len(seq)-len(set(seq)))/max(1,len(seq)-1)

summary=[]; audited=[]; all_events=[]; all_stops=[]; all_bins=[]; all_dwells=[]; sensitivity=[]; source_files=[]; detail={}
for student,mode,folder,tapfile in SESSIONS:
    sid='20260906_'+folder; d=ROOT/'Logs~'/'Observer'/sid
    meta=dict(l.split('\t',1) for l in (d/'session.txt').read_text(encoding='utf-8-sig').splitlines())
    p=pd.read_csv(d/'pose.tsv',sep='\t',encoding='utf-8-sig',keep_default_na=False)
    e=pd.read_csv(d/'event.tsv',sep='\t',encoding='utf-8-sig',keep_default_na=False)
    e['source_line']=np.arange(len(e))+2
    tap_path=ROOT/'Logs~'/'Tap'/('tap_20260906_'+tapfile+'.csv'); tap=read_tap(tap_path)
    for path in [d/'session.txt',d/'pose.tsv',d/'event.tsv',tap_path]:
        source_files.append(dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    declared_duration=float(meta['时长秒']); t=p['时刻'].to_numpy(); duration=max(declared_duration,float(t[-1])); dt=np.diff(t); weights=np.diff(np.r_[t,duration])
    assert (dt>0).all() and (weights>=0).all(),(sid,dt.min(),weights.min())
    assert len(p)==int(meta['位姿行数']) and len(e)==int(meta['点击数'])
    assert (e['序号'].to_numpy()==np.arange(1,len(e)+1)).all()
    ordinary=tap[tap['停止触发']==''].copy(); stops=tap[tap['停止触发']!=''].copy()
    assert set(tap['停止模式'])=={mode},(sid,mode,set(tap['停止模式']))
    assert len(ordinary)==len(e),(sid,len(ordinary),len(e))
    offsets=ordinary['时刻'].to_numpy()-e['时刻'].to_numpy(); offset=float(np.median(offsets))
    assert np.max(abs(offsets-offset))<.011
    for tc,ec in [('命中层','命中层'),('意图','意图'),('触碰','触碰')]: assert list(ordinary[tc])==list(e[ec])
    err=np.linalg.norm(ordinary[['相机X','相机Z']].to_numpy()-e[['相机X','相机Z']].to_numpy(),axis=1)
    assert err.max()<.015
    stops['observer_t']=stops['时刻']-offset
    speed=p['速度'].to_numpy(); xy=p[['X','Z']].to_numpy(); dist=np.linalg.norm(np.diff(xy,axis=0),axis=1)
    blocked=e['受阻']=='是'; touch=e['触碰']=='★触碰'; moving=e['发出移动']=='是'
    e['student']=student;e['mode']=mode;e['session']=sid
    e['tap_csv_line']=ordinary['source_line'].to_numpy()
    e['no_move_no_touch']=(~moving)&(~touch)
    e['next_gap_s']=e['时刻'].shift(-1)-e['时刻']
    hitxy=e[['命中X','命中Z']].to_numpy(); camxy=e[['相机X','相机Z']].to_numpy()
    e['next_hit_distance_m']=np.r_[np.linalg.norm(np.diff(hitxy,axis=0),axis=1),np.nan]
    e['next_camera_displacement_m']=np.r_[np.linalg.norm(np.diff(camxy,axis=0),axis=1),np.nan]
    e['near_repeat_1m_3s']=(e['next_gap_s']<=3)&(e['next_hit_distance_m']<=1)&(e['命中']=='是')&(e['命中'].shift(-1)=='是')
    e['block_family']=e['受阻原因'].str.split().str[0].where(blocked,'-')
    # Strict hand-entry attempts: success OR explicit hand refusal. Far approach is not an attempted hand launch.
    explicit_refusal=e['说明'].str.contains('不触碰：手正忙|不触碰：不出手：',regex=True)&(~touch)
    detail[sid]={'touch_notes':e['说明'].value_counts().to_dict(),'intents':e['意图'].value_counts().to_dict(),'layers':e['命中层'].value_counts().to_dict(),'blocks':e.loc[blocked,'受阻原因'].value_counts().to_dict(),'touch_kind':e['触碰种类'].value_counts().to_dict(),'tap_modes':tap['停止模式'].value_counts().to_dict()}
    dwells=segments(speed<=.05,t,duration)
    for a,b,ia,ib in dwells:
        if b-a>=2: all_dwells.append(dict(student=student,mode=mode,session=sid,start=a,end=b,duration=b-a,x=float(xy[ia,0]),z=float(xy[ia,1]),initial=ia==0,terminal=ib==len(p)))
    for _,r in stops.iterrows():
        st=float(r.observer_t); before=max(0,np.searchsorted(t,st)-1); after=min(len(p)-1,np.searchsorted(t,st))
        quiet=np.flatnonzero((t>=st)&(speed<=.05))
        q=int(quiet[0]) if len(quiet) else len(p)-1
        other=tap[(tap['时刻']>r['时刻'])&(tap['时刻']<=t[q]+offset)]
        x0=float(np.interp(st,t,xy[:,0]));z0=float(np.interp(st,t,xy[:,1]))
        next_e=e[e['时刻']>st]
        until=min(st+1,float(next_e['时刻'].iloc[0]) if len(next_e) else duration,duration)
        yaw=np.rad2deg(np.unwrap(np.deg2rad(p['视线偏航'])))
        prev=ordinary[ordinary['时刻']<r['时刻']].iloc[-1] if (ordinary['时刻']<r['时刻']).any() else None
        all_stops.append(dict(student=student,mode=mode,session=sid,csv_line=int(r.source_line),t=st,trigger=r['停止触发'],intent=r['意图'],speed_before=float(speed[before]),time_to_speed05=float(t[q]-st),displacement_to_speed05=float(np.hypot(xy[q,0]-x0,xy[q,1]-z0)),intervening_events=len(other),prior_event_gap=float(r['时刻']-prev['时刻']) if prev is not None else None,yaw_change_until_1s_or_next_event=float(np.interp(until,t,yaw)-np.interp(st,t,yaw)),yaw_observation_s=until-st))
    gs=gridstats(p,5)
    s=dict(student=student,mode=mode,session=sid,started=meta['录制时刻'],duration_s=duration,pose_n=len(p),event_n=len(e),event_per_min=len(e)*60/duration,tap_rows=len(tap),active_stops=len(stops),nonempty_stops=int((stops['意图']=='停下来').sum()),empty_stops=int((stops['意图']=='停下来·空停').sum()),distance_m=dist.sum(),distance_speed_integral_m=np.sum(speed*weights),moving_time_s=weights[speed>.05].sum(),stationary_pct=100*weights[speed<=.05].sum()/duration,blocked_n=int(blocked.sum()),zero_granted_block_n=int((blocked&(e['获准位移']<.05)).sum()),movement_issued_n=int(moving.sum()),no_move_no_touch=int(e['no_move_no_touch'].sum()),touch_n=int(touch.sum()),first_touch_s=float(e.loc[touch,'时刻'].min()) if touch.any() else None,touch_refusals=int(explicit_refusal.sum()),median_gap_s=float(e['时刻'].diff().median()),grid5_n=gs[0],grid5_entries=gs[1],grid5_revisit_pct=100*gs[2],pitch30_pct=100*weights[p['俯仰']>=30].sum()/duration,yaw_travel_deg=float(abs(circdiff(p['视线偏航'].to_numpy())).sum()),repeat_pairs=int(e['near_repeat_1m_3s'].sum()),x_min=xy[:,0].min(),x_max=xy[:,0].max(),z_min=xy[:,1].min(),z_max=xy[:,1].max(),aspect=float(meta['相机宽高比']),meta_ring_radius=float(meta['停下光圈半径']))
    summary.append(s)
    audited.append(dict(session=sid,pose_rows=len(p),event_rows=len(e),tap_ordinary_rows=len(ordinary),tap_stop_rows=len(stops),pose_duration=float(t[-1]),declared_duration=declared_duration,effective_hz=(len(p)-1)/(t[-1]-t[0]),max_gap_s=dt.max(),gaps_over100ms=int((dt>.1).sum()),time_offset_s=offset,max_time_match_residual_s=max(abs(offsets-offset)),max_position_match_error_m=err.max(),unique_modes=','.join(tap['停止模式'].unique()),missing_desired_y=int((e['期望落点Y']=='').sum())))
    for size in [2.5,5,10]:
        for shift in [0,size/2]:
            for dwell in [0,1]:
                g=gridstats(p,size,(shift,shift),dwell)
                sensitivity.append(dict(session=sid,size_m=size,origin_shift_m=shift,min_dwell_s=dwell,unique_cells=g[0],entries=g[1],revisit_pct=100*g[2]))
    for threshold in [.02,.05,.1]:
        detail[sid]['stationary_pct_'+str(threshold)]=100*weights[speed<=threshold].sum()/duration
    for low,high in [(0,60),(60,120),(120,180),(180,duration)]:
        high=min(high,duration)
        if high<=low:continue
        w=np.maximum(0,np.minimum(np.r_[t[1:],duration],high)-np.maximum(t,low))
        sel=(e['时刻']>=low)&(e['时刻']<high)
        all_bins.append(dict(session=sid,student=student,mode=mode,start=low,end=high,events=int(sel.sum()),blocked=int((sel&blocked).sum()),touch=int((sel&touch).sum()),stationary_pct=100*w[speed<=.05].sum()/(high-low),distance_m=float(np.sum(dist*np.clip((np.minimum(t[1:],high)-np.maximum(t[:-1],low))/dt,0,1)))))
    all_events.append(e)

for name,records in [('session_summary',summary),('audit',audited),('active_stops',all_stops),('minute_bins',all_bins),('dwells',all_dwells),('grid_sensitivity',sensitivity),('sources',source_files)]:
    pd.DataFrame(records).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
pd.concat(all_events).to_csv(OUT/'event_audit.csv',index=False,encoding='utf-8-sig')
(OUT/'details.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)),encoding='utf-8')
print(pd.DataFrame(summary).round(3).to_string(index=False))
print('\nAUDIT\n'+pd.DataFrame(audited).round(4).to_string(index=False))
print('\nDETAILS\n'+json.dumps(detail,ensure_ascii=False,indent=2))
