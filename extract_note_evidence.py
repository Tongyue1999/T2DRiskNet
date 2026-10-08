"""Full note census: explicit demographics and candidate endpoints; no age->DOB."""
from pathlib import Path
import re,json,hashlib
from collections import defaultdict,Counter
import pandas as pd

root=Path(__file__).resolve().parent;out=root/'data/hospital_outcomes'
path=next(root.parent.glob('*/**/sample_note.rds'))
dob=re.compile(r'(?:出生日期|出生年月日|生日|birth\s*date|DOB)\s*[:：]?\s*((?:18|19|20)\d{2})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})(?:日)?',re.I)
sex=re.compile(r'性别\s*[:：]?\s*([男女])')
age=re.compile(r'年龄\s*[:：]?\s*(\d{1,3})\s*岁?')
cvd=re.compile(r'(?<![A-Z0-9])I(?:2[0-5]|50|6[0-4])(?:\.?\d*)',re.I)
terms=re.compile(r'心肌梗[死塞]|冠状动脉粥样硬化性心脏病|冠心病|心力衰竭|心衰|脑梗[死塞]|脑出血|蛛网膜下腔出血|卒中')
states={};evidence=[];counts=Counter();total=0
for chunk in pd.read_csv(path,encoding='gb18030',dtype=str,usecols=['PERSON_ID_NEW','NOTE_DATE','NOTE_TYPE','NOTE_TEXT'],chunksize=10000):
    total+=len(chunk)
    days=pd.to_datetime(chunk.NOTE_DATE,errors='coerce',format='mixed').dt.strftime('%Y-%m-%d')
    for key,day,nt,text in zip(chunk.PERSON_ID_NEW,days,chunk.NOTE_TYPE,chunk.NOTE_TEXT.fillna('')):
        if pd.isna(key):continue
        pid='H-'+hashlib.sha256(str(key).encode()).hexdigest()[:24]
        s=states.setdefault(pid,{'dobs':Counter(),'sexes':Counter(),'ages':Counter(),'raw_key':key,'notes':0})
        s['notes']+=1
        for y,m,d in dob.findall(text):
            try:
                val=pd.Timestamp(int(y),int(m),int(d)).strftime('%Y-%m-%d')
                if pd.notna(day) and val<=day:s['dobs'][val]+=1;counts['valid_explicit_DOB_mentions']+=1
                else:counts['DOB_after_note_date_or_missing_note_date']+=1
            except ValueError:counts['invalid_DOB_mentions']+=1
        for v in sex.findall(text):s['sexes'][v]+=1
        for v in age.findall(text):
            if int(v)<=120:s['ages'][int(v)]+=1
        codes=sorted(set(x.upper() for x in cvd.findall(text)))
        words=sorted(set(terms.findall(text)))
        if codes or words:
            evidence.append({'patient_id':pid,'note_date':day,'note_type':nt,'ICD_mentions':'|'.join(codes),'term_mentions':'|'.join(words),'status':'unadjudicated_text_mention_not_incident_event'})
    print('notes scanned',total,flush=True)
rows=[];inputrows=[]
for pid,s in states.items():
    ds=s['dobs'];ss=s['sexes'];a=s['ages']
    consistent=len(ds)==1 and len(ss)==1
    repeated=consistent and next(iter(ds.values()))>=2 and next(iter(ss.values()))>=2
    rows.append({'patient_id':pid,'note_count':s['notes'],'explicit_birthdate_candidates':'|'.join(ds),'birthdate_mentions':sum(ds.values()),'explicit_sex_candidates':'|'.join(ss),'sex_mentions':sum(ss.values()),'reported_age_min':min(a) if a else None,'reported_age_max':max(a) if a else None,'demographic_conflict':len(ds)>1 or len(ss)>1,'consistent_explicit_DOB_and_sex':consistent,'repeated_consistent_explicit_DOB_and_sex':repeated,'clinical_verification':'pending_patient_header_confirmation'})
    if repeated:inputrows.append({'PERSON_ID_NEW':s['raw_key'],'birthdate':next(iter(ds)),'gender':next(iter(ss)),'source':'repeated_consistent_explicit_note_labels','verification':'pending_header_adjudication'})
df=pd.DataFrame(rows);ev=pd.DataFrame(evidence)
df.to_csv(out/'note_demographic_candidates.csv',index=False,encoding='utf-8-sig')
ev.to_csv(out/'note_cvd_candidates.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(inputrows,columns=['PERSON_ID_NEW','birthdate','gender','source','verification']).to_csv(out/'local_note_demographics.csv',index=False,encoding='utf-8-sig')
p=pd.read_csv(out/'patients.csv');post=set(p.loc[p.recorded_CVD_after_first_E11,'patient_id'])
summary={'notes_scanned':total,'patients_with_notes':len(df),'patients_with_explicit_DOB':int(df.birthdate_mentions.gt(0).sum()),'patients_with_explicit_sex':int(df.sex_mentions.gt(0).sum()),'consistent_explicit_DOB_and_sex':int(df.consistent_explicit_DOB_and_sex.sum()),'repeated_consistent_DOB_and_sex':len(inputrows),'demographic_conflicts':int(df.demographic_conflict.sum()),'note_CVD_candidate_patients':ev.patient_id.nunique() if len(ev) else 0,'post_E11_CVD_patients_with_repeated_DOB_sex':int(df.loc[df.patient_id.isin(post),'repeated_consistent_explicit_DOB_and_sex'].sum()),'counts':dict(counts),'rule':'Explicit note labels are candidates; no age-derived birthdate. Text CVD mentions may be history, negation or family history and are not incident endpoints.'}
(out/'note_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
