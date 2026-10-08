"""Exploratory only: repeated explicit DOB/sex candidates at fixed first-E11 dates."""
from pathlib import Path
import pandas as pd,json,hashlib
from hospital_adapter import convert
from engine import infer
root=Path(__file__).resolve().parent;out=root/'data/hospital_outcomes'
d=pd.read_csv(out/'local_note_demographics.csv',dtype=str)
p=pd.read_csv(out/'patients.csv',low_memory=False).set_index('patient_id')
d['patient_id']=d.PERSON_ID_NEW.map(lambda k:'H-'+hashlib.sha256(str(k).encode()).hexdigest()[:24])
d['end_of_data']=d.patient_id.map(p.last_observed_contact_date)
d['death_date']=d.patient_id.map(p.earliest_recorded_death_date)
d['landmark']=d.patient_id.map(p.first_recorded_E11_date)
d=d[d.landmark.notna()]
allrows=[];exclusions=[]
if len(d):
    converted,quality=convert(d)
    quality['demographics_source']='repeated_explicit_note_candidates_not_clinically_adjudicated'
    (out/'local_exploratory_note_patients.json').write_text(json.dumps(converted,ensure_ascii=False),encoding='utf-8')
    for _,row in d.iterrows():
        key=row.PERSON_ID_NEW
        try:
            f,ex,manifest=infer({key:converted[key]},'current',row.landmark)
            f['outcome_patient_id']=row.patient_id;f['demographics_source']='repeated_explicit_note_candidates_not_adjudicated';f['ready_for_clinical_use']=False;f['ready_for_publication']=False
            allrows.append(f)
        except ValueError as e:exclusions.append({'patient_id':row.patient_id,'reason':str(e)})
    result=pd.concat(allrows,ignore_index=True) if allrows else pd.DataFrame()
    result.to_csv(out/'exploratory_note_predictions.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(exclusions).to_csv(out/'exploratory_note_exclusions.csv',index=False,encoding='utf-8-sig')
    summary={'candidate_patients_with_E11':len(d),'predictions':len(result),'exclusions':exclusions,'conversion':quality,'landmark':'first recorded E11, not outcome-conditioned','status':'exploratory_candidate_demographics_only','clinical_comparison_ready':False}
else:summary={'candidate_patients_with_E11':0,'predictions':0,'clinical_comparison_ready':False}
(out/'exploratory_model_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False),flush=True)
