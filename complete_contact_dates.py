from pathlib import Path
import pandas as pd,json,hashlib
root=Path(__file__).resolve().parent;out=root/'data/hospital_outcomes'
p=pd.read_csv(out/'patients.csv',low_memory=False).set_index('patient_id')
paths={x.name:x for x in root.parent.glob('*/**/sample_*.rds')}
audit=[]
for file,col in [('sample_vital_sign.rds','MEASURE_TIME'),('sample_prescription.rds','ORDER_START_TIME')]:
    rows=0
    for df in pd.read_csv(paths[file],encoding='gb18030',dtype=str,usecols=['PERSON_ID_NEW',col],chunksize=100000):
        rows+=len(df);df['day']=pd.to_datetime(df[col],errors='coerce',format='mixed').dt.strftime('%Y-%m-%d');df=df.dropna(subset=['PERSON_ID_NEW','day'])
        a=df.groupby('PERSON_ID_NEW').day.agg(['min','max'])
        for key,lo,hi in a.itertuples():
            pid='H-'+hashlib.sha256(str(key).encode()).hexdigest()[:24]
            if pid not in p.index:continue
            first=p.at[pid,'first_observed_date'];last=p.at[pid,'last_observed_contact_date']
            p.at[pid,'first_observed_date']=min(lo,first) if isinstance(first,str) else lo
            p.at[pid,'last_observed_contact_date']=max(hi,last) if isinstance(last,str) else hi
    audit.append({'file':file,'rows':rows,'date_field':col});print(file,rows,flush=True)
p.reset_index().to_csv(out/'patients.csv',index=False,encoding='utf-8-sig')
s=json.loads((out/'summary.json').read_text(encoding='utf-8'));s['additional_contact_sources']=audit;(out/'summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
