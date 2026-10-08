"""Align stored endpoints with the supplied model's 30-day-month convention."""
from pathlib import Path
import pandas as pd,json
root=Path(__file__).resolve().parent;out=root/'data/hospital_outcomes'
p=pd.read_csv(out/'patients.csv',low_memory=False)
p=p[p.first_recorded_E11_date.notna()].copy()
t=pd.to_datetime(p.first_recorded_E11_date);c=pd.to_datetime(p.first_primary_ICD_CVD_date);d=pd.to_datetime(p.earliest_recorded_death_date);last=pd.to_datetime(p.last_observed_contact_date)
allframes=[]
for m in [3,6,12,36,60]:
    end=t+pd.to_timedelta(m*30,unit='D')
    status=pd.Series('censored_contact_only',index=p.index);time=last.copy();why=pd.Series('outcome_capture_not_verified',index=p.index)
    supported=last>=end;status[supported]='no_recorded_CVD_with_contact_beyond_window';time[supported]=end[supported]
    tied=(c==d)&(c<=end)&(c>t);status[tied]='same_day_CVD_death_needs_review';time[tied]=c[tied];why[tied]='ordering_unknown'
    dead=(d>t)&(d<=end)&(c.isna()|(d<c));status[dead]='recorded_competing_death';time[dead]=d[dead];why[dead]='recorded_death'
    event=(c>t)&(c<=end)&(d.isna()|(c<d));status[event]='observed_CVD';time[event]=c[event];why[event]='primary_ICD'
    predeath=d<=t;status[predeath]='excluded_death_at_landmark';time[predeath]=d[predeath];why[predeath]='death_on_or_before_landmark'
    precvd=c<=t;status[precvd]='excluded_preexisting_CVD';time[precvd]=c[precvd];why[precvd]='CVD_on_or_before_landmark'
    frame=pd.DataFrame({'patient_id':p.patient_id,'provisional_landmark':t.dt.strftime('%Y-%m-%d'),'horizon_months':m,'window_end':end.dt.strftime('%Y-%m-%d'),'status':status,'observation_end':time.dt.strftime('%Y-%m-%d'),'reason':why,'ready_for_publication':False,'month_days':30})
    allframes.append(frame)
w=pd.concat(allframes,ignore_index=True)
orig=out/'prediction_windows_calendar_months.csv'
if not orig.exists():(out/'prediction_windows.csv').replace(orig)
w.to_csv(out/'prediction_windows.csv',index=False,encoding='utf-8-sig')
summary=json.loads((out/'summary.json').read_text(encoding='utf-8'));summary['month_days']=30;summary['windows']={str(m):g.status.value_counts().to_dict() for m,g in w.groupby('horizon_months')}
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
assert not w.duplicated(['patient_id','horizon_months']).any()
events=w[w.status=='observed_CVD'];assert (events.observation_end>events.provisional_landmark).all();assert (events.observation_end<=events.window_end).all()
print(json.dumps(summary['windows'],ensure_ascii=False))
