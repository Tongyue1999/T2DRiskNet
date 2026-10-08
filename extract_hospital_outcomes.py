"""Extract observed endpoints; absence of a record is never complete follow-up."""
from pathlib import Path
import hashlib,json,re
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'/'hospital_outcomes'
OUT.mkdir(exist_ok=True)
paths={p.name:p for p in ROOT.parent.glob('*/**/sample_*.rds')}
people={}; evidence=[]; audit=[]
cvd=re.compile(r'(?<![A-Z0-9])I(?:2[0-5]|50|6[0-4])(?:\.?\d*)',re.I)
names=re.compile(r'心肌梗[死塞]|冠状动脉粥样硬化性心脏病|冠心病|心力衰竭|心衰|脑梗[死塞]|脑出血|蛛网膜下腔出血|卒中')
def anon(k): return 'H-'+hashlib.sha256(str(k).encode()).hexdigest()[:24]
def person(k):
    if k not in people: people[k]={'first':None,'last':None,'t2d':None,'cvd':None,'death':None,'visit_death':None}
    return people[k]
def bounds(k,d):
    if not d or pd.isna(d):return
    p=person(k); p['first']=min(p['first'] or d,d);p['last']=max(p['last'] or d,d)
def earliest(k,field,d):
    if d and not pd.isna(d):
        p=person(k);p[field]=min(p[field] or d,d)
def dates(s):return pd.to_datetime(s,errors='coerce',format='mixed').dt.strftime('%Y-%m-%d')
for fname in ['sample_diag.rds','sample_event.rds','sample_visit.rds']:
    rows=0
    for df in pd.read_csv(paths[fname],encoding='gb18030',dtype=str,chunksize=25000):
        rows+=len(df)
        if fname=='sample_diag.rds':
            ds=dates(df.CONDITION_START_DATE)
            for k,d,code,hf,name in zip(df.PERSON_ID_NEW,ds,df.CONDITION_CODE.fillna(''),df.CONDITION_CODE_HF.fillna(''),df.CONDITION_NAME.fillna('')):
                if pd.isna(k):continue
                bounds(k,d)
                if re.match(r'^E11',code.strip(),re.I):earliest(k,'t2d',d)
                direct=bool(cvd.search(code.strip())); extra=bool(cvd.search(hf)); named=bool(names.search(name))
                if direct or extra or named:
                    level='primary_icd' if direct else 'merged_icd_candidate' if extra else 'diagnosis_name_candidate'
                    evidence.append({'patient_id':anon(k),'date':d,'source':fname,'evidence_level':level,'code':code,'merged_code':hf,'diagnosis_name':name})
                    if direct:earliest(k,'cvd',d)
        elif fname=='sample_event.rds':
            ds=dates(df['date'])
            for k,d,cl in zip(df.PERSON_ID_NEW,ds,df['class']):
                if pd.isna(k):continue
                bounds(k,d)
                if cl=='death':earliest(k,'death',d)
        else:
            starts=dates(df.VISIT_START_DATE);ends=dates(df.VISIT_END_DATE)
            for k,s,e,condition in zip(df.PERSON_ID_NEW,starts,ends,df.OUT_CONDITION):
                if pd.isna(k):continue
                bounds(k,s);bounds(k,e)
                if condition=='死亡':earliest(k,'visit_death',e if pd.notna(e) else s)
    audit.append({'file':fname,'rows':rows});print(fname,rows,flush=True)
# Dates from other structured files extend observed contact, not proven event-free follow-up.
inventory=json.loads((ROOT/'reports/data_inventory.json').read_text(encoding='utf-8'))
for entry in inventory:
    fname=entry['file']
    if fname not in paths:continue
    if fname in ['sample_diag.rds','sample_event.rds','sample_visit.rds','sample_note.rds']:continue
    cols=list(entry.get('columns',{})) or list(pd.read_csv(paths[fname],encoding='gb18030',nrows=0).columns)
    dc=next((x for x in ['DATE','date','MEASUREMENT_DATE','DETECT_TIME','DRUG_START_DATE','DRUG_EXPOSURE_START_DATE','PROCEDURE_DATE'] if x in cols),None)
    if not dc:continue
    rows=0
    for df in pd.read_csv(paths[fname],encoding='gb18030',dtype=str,usecols=['PERSON_ID_NEW',dc],chunksize=100000):
        rows+=len(df);ds=dates(df[dc]);df=df.assign(day=ds).dropna(subset=['PERSON_ID_NEW','day'])
        grouped=df.groupby('PERSON_ID_NEW')['day'].agg(['min','max'])
        for k,lo,hi in grouped.itertuples():bounds(k,lo);bounds(k,hi)
    audit.append({'file':fname,'rows':rows,'date_field':dc});print(fname,rows,flush=True)
# Clinical notes are only a contact-date source here; text mentions need clinical adjudication.
for df in pd.read_csv(paths['sample_note.rds'],encoding='gb18030',dtype=str,usecols=['PERSON_ID_NEW','NOTE_DATE'],chunksize=50000):
    df=df.assign(day=dates(df.NOTE_DATE)).dropna(subset=['PERSON_ID_NEW','day'])
    grouped=df.groupby('PERSON_ID_NEW')['day'].agg(['min','max'])
    for k,lo,hi in grouped.itertuples():bounds(k,lo);bounds(k,hi)
print('note dates complete',flush=True)
records=[]; windows=[]
for k,p in people.items():
    pid=anon(k);t=p['t2d'];c=p['cvd'];d=p['death'];vd=p['visit_death']
    death=min([x for x in [d,vd] if x],default=None)
    row={'patient_id':pid,'first_observed_date':p['first'],'last_observed_contact_date':p['last'],'first_recorded_E11_date':t,'first_primary_ICD_CVD_date':c,'explicit_event_death_date':d,'death_discharge_date':vd,'earliest_recorded_death_date':death,'death_date_disagreement':bool(d and vd and d!=vd),'CVD_at_or_before_first_E11':bool(t and c and c<=t),'recorded_CVD_after_first_E11':bool(t and c and c>t),'followup_completeness':'unverified','demographics_verified':False}
    records.append(row)
    if not t:continue
    # First recorded E11 is a reproducible provisional landmark, NOT confirmed disease onset.
    for m in [3,6,12,36,60]:
        end=(pd.Timestamp(t)+pd.DateOffset(months=m)).strftime('%Y-%m-%d')
        status='censored_contact_only';time=p['last'];why='outcome_capture_not_verified'
        if c and c<=t:status='excluded_preexisting_CVD';time=c;why='CVD_on_or_before_landmark'
        elif death and death<=t:status='excluded_death_at_landmark';time=death;why='death_on_or_before_landmark'
        elif c and c<=end and (not death or c<death):status='observed_CVD';time=c;why='primary_ICD'
        elif death and death<=end and (not c or death<c):status='recorded_competing_death';time=death;why='recorded_death'
        elif c and death and c==death and c<=end:status='same_day_CVD_death_needs_review';time=c;why='ordering_unknown'
        elif p['last'] and p['last']>=end:status='no_recorded_CVD_with_contact_beyond_window';time=end
        windows.append({'patient_id':pid,'provisional_landmark':t,'horizon_months':m,'window_end':end,'status':status,'observation_end':time,'reason':why,'ready_for_publication':False})
patients=pd.DataFrame(records);w=pd.DataFrame(windows);ev=pd.DataFrame(evidence)
patients.to_csv(OUT/'patients.csv',index=False,encoding='utf-8-sig');w.to_csv(OUT/'prediction_windows.csv',index=False,encoding='utf-8-sig');ev.to_csv(OUT/'cvd_evidence.csv',index=False,encoding='utf-8-sig')
summary={'patients':len(patients),'E11_patients':int(patients.first_recorded_E11_date.notna().sum()),'primary_ICD_CVD_patients':int(patients.first_primary_ICD_CVD_date.notna().sum()),'recorded_CVD_after_first_E11':int(patients.recorded_CVD_after_first_E11.sum()),'recorded_death_patients':int(patients.earliest_recorded_death_date.notna().sum()),'evidence_counts':ev.evidence_level.value_counts().to_dict(),'windows':{str(m):g.status.value_counts().to_dict() for m,g in w.groupby('horizon_months')},'scanned_sources':audit,'limitations':['First recorded E11 is provisional landmark, not onset; adult eligibility and input history not yet verified.','Contact beyond a horizon does not prove event ascertainment completeness.','Merged codes and diagnosis names are candidates, not adjudicated outcomes.','No inference from absence of CVD codes; no unvalidated model superiority claims.']}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
