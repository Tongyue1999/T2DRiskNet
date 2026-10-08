"""Use real hospital CSV tables without inventing demographic inputs."""
from pathlib import Path
import hashlib,json,re
import pandas as pd
from engine import ROOT

def audit():
    paths={p.name:p for p in ROOT.parent.glob('*/**/sample_*.rds')}
    diag=paths['sample_diag.rds']
    patients=set(); t2d=set(); targets=set(); rows=0; invalid=0; first_dates={}; last_dates={}; tokens=set(); diagnoses={}
    for chunk in pd.read_csv(diag,encoding='gb18030',dtype=str,usecols=['PERSON_ID_NEW','CONDITION_CODE','CONDITION_START_DATE'],chunksize=50000):
        rows+=len(chunk)
        parsed=pd.to_datetime(chunk.CONDITION_START_DATE,errors='coerce',format='mixed')
        invalid+=int(parsed.isna().sum())
        chunk=chunk.assign(parsed_date=parsed.dt.strftime('%Y-%m-%d'))
        for key,code,day in chunk[['PERSON_ID_NEW','CONDITION_CODE','parsed_date']].itertuples(index=False,name=None):
            if pd.isna(key): continue
            patients.add(key)
            code='' if pd.isna(code) else str(code).strip().replace('.','').upper()
            tokens.add(code[:3])
            if code.startswith('E11'): t2d.add(key)
            if code[:3] in {'I20','I21','I22','I23','I24','I25','I50','I60','I61','I62','I63','I64'}: targets.add(key)
            if pd.isna(day):continue
            first_dates[key]=min(first_dates.get(key,day),day)
            last_dates[key]=max(last_dates.get(key,day),day)
            diagnoses.setdefault(key,[]).append({'admdate':day,'codes':code})
    visits=0; visit_people=set(); discharge_values={}
    for chunk in pd.read_csv(paths['sample_visit.rds'],encoding='gb18030',dtype=str,usecols=['PERSON_ID_NEW','VISIT_START_DATE','VISIT_END_DATE','OUT_CONDITION'],chunksize=50000):
        visits+=len(chunk); visit_people.update(chunk.PERSON_ID_NEW.dropna())
        for value,count in chunk.OUT_CONDITION.fillna('MISSING').value_counts().items():
            discharge_values[str(value)]=discharge_values.get(str(value),0)+int(count)
    sample=json.loads(next((ROOT/'vendor').rglob('ustc_200patients_demo.json')).read_text(encoding='utf-8'))
    overlap=patients & set(sample)
    payload={
        'diagnosis_rows':rows,'diagnosis_patients':len(patients),'patients_with_E11':len(t2d),
        'patients_with_target_CVD_record':len(targets),'patients_with_E11_and_CVD_record':len(t2d & targets),
        'visit_rows':visits,'visit_patients':len(visit_people),'invalid_diagnosis_dates':invalid,
        'earliest_diagnosis_date':min(first_dates.values()),'latest_diagnosis_date':max(last_dates.values()),
        'json_sample_identifier_overlap':len(overlap),'out_condition_counts':discharge_values,
        'demographics_available_in_structured_tables':False,
        'interpretation':'CVD counts are recorded diagnoses, NOT incident events after a valid landmark. No risk inference from missing demographics. No inference of mortality from discharge text without validation.'}
    (ROOT/'reports/hospital_audit.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    # Reusable anonymous trajectories, explicitly incomplete and not inferable.
    incomplete={'schema':'incomplete_hospital_diagnosis_trajectories_v1','ready_for_model':False,'missing_required':['birthdate','gender'],'patients':{ 'H-'+hashlib.sha256(key.encode()).hexdigest()[:24]:{'first_record_date':first_dates[key],'last_record_date':last_dates[key],'has_E11':key in t2d,'has_recorded_CVD':key in targets,'events':sorted(diagnoses[key],key=lambda x:x['admdate'])} for key in t2d if key in diagnoses}}
    (ROOT/'data/hospital_diagnosis_trajectories.json').write_text(json.dumps(incomplete,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(payload,ensure_ascii=True),flush=True)
if __name__=='__main__':audit()
