from pathlib import Path
import pandas as pd
import numpy as np
D=Path(__file__).resolve().parent
e=pd.read_csv(D/'event_audit.csv',keep_default_na=False)
s=pd.read_csv(D/'active_stops.csv')
cols=['session','序号','时刻','命中层','水平距','意图','想走','获准位移','受阻原因','发出移动','触碰','说明']
print('NEAR TERRAIN NO MOVE')
for sid,g in e.groupby('session',sort=False):
    near=g[(g['命中层']=='Terrain')&(g['想走']==0)]
    print(sid,near[['序号','时刻','水平距','坡度','意图']].to_dict('records'))
print('HAND ENTRIES')
print(e[(e['触碰']=='★触碰')|e['说明'].str.contains('不出手|手正忙')][cols].to_string(index=False))
print('S2 BUTTON BLOCKED')
print(e[(e['session']=='20260906_160018')&(e['受阻']=='是')][cols+['相机X','相机Z','命中X','命中Z']].to_string(index=False))
print('STOPS')
print(s.round(3).to_string(index=False))
print('MINUTE BINS')
print(pd.read_csv(D/'minute_bins.csv').round(2).to_string(index=False))
print('LONGEST DWELLS')
print(pd.read_csv(D/'dwells.csv').sort_values('duration',ascending=False).head(12).round(3).to_string(index=False))
print('GRID SENSITIVITY')
print(pd.read_csv(D/'grid_sensitivity.csv').query('min_dwell_s == 1 and size_m >= 5').round(2).to_string(index=False))
print('TOTALS',pd.read_csv(D/'session_summary.csv')[['duration_s','pose_n','event_n','tap_rows','active_stops','distance_m','touch_n','blocked_n','zero_granted_block_n']].sum().to_dict())
