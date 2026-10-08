from pathlib import Path
import pandas as pd,json,hashlib
root=Path(__file__).resolve().parent;out=root/'data/hospital_outcomes'
p=pd.read_csv(out/'patients.csv',low_memory=False);needed=set(p.loc[p.first_recorded_E11_date.notna(),'patient_id'])
source=next(root.parent.glob('*/**/sample_diag.rds'));mapping={}
for chunk in pd.read_csv(source,encoding='gb18030',dtype=str,usecols=['PERSON_ID_NEW'],chunksize=100000):
    for k in chunk.PERSON_ID_NEW.dropna().unique():
        h='H-'+hashlib.sha256(str(k).encode()).hexdigest()[:24]
        if h in needed:mapping[h]=k
d=p[p.patient_id.isin(needed)].copy();d['PERSON_ID_NEW']=d.patient_id.map(mapping)
assert d.PERSON_ID_NEW.notna().all()
fields=['PERSON_ID_NEW','birthdate','gender']
d[fields].to_csv(out/'local_demographics_to_complete.csv',index=False,encoding='utf-8-sig')
notes=pd.read_csv(out/'note_demographic_candidates.csv')
priority=d[d.recorded_CVD_after_first_E11].merge(notes[['patient_id','explicit_sex_candidates','reported_age_min','reported_age_max']],on='patient_id',how='left')
priority[fields+['patient_id','first_recorded_E11_date','first_primary_ICD_CVD_date','explicit_sex_candidates','reported_age_min','reported_age_max']].to_csv(out/'local_event_patients_to_complete.csv',index=False,encoding='utf-8-sig')
r=p.merge(notes,on='patient_id',how='left',validate='one_to_one')
r['model_input_status']=r.demographics_verified.map({True:'demographics_available_history_eligibility_to_check',False:'missing_verified_birthdate_or_sex'})
r['outcome_status']='recorded_contact_only_ascertainment_unverified'
r.loc[r.recorded_CVD_after_first_E11,'outcome_status']='recorded_post_landmark_CVD_requires_adjudication'
r.to_csv(out/'model_readiness.csv',index=False,encoding='utf-8-sig')
summary={'E11_patients':len(d),'E11_patients_with_supplied_demographics':int(d.demographics_verified.sum()),'post_E11_CVD_patients':int(d.recorded_CVD_after_first_E11.sum()),'post_E11_CVD_patients_missing_demographics':int((d.recorded_CVD_after_first_E11 & ~d.demographics_verified).sum()),'note_demographics':'candidates_only_not_automatically_adopted','clinical_comparison_ready':False,'month_days':30,'remaining_requirements':['verify demographics and pre-landmark model histories','adjudicate primary ICD and text/merged-code candidates','confirm target diagnoses extraction completeness and observation coverage','confirm two weight identities and clinical comparator']}
(out/'readiness_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
