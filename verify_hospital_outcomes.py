from pathlib import Path
import json,hashlib
import pandas as pd
root=Path(__file__).resolve().parent
out=root/'data/hospital_outcomes'
p=pd.read_csv(out/'patients.csv',dtype={'patient_id':str},low_memory=False)
w=pd.read_csv(out/'prediction_windows.csv')
demo=json.loads(next((root/'vendor').rglob('ustc_200patients_demo.json')).read_text(encoding='utf-8'))
lookup={'H-'+hashlib.sha256(str(k).encode()).hexdigest()[:24]:v for k,v in demo.items()}
p['birthdate']=p.patient_id.map(lambda x:lookup.get(x,{}).get('birthdate'))
p['gender']=p.patient_id.map(lambda x:lookup.get(x,{}).get('gender'))
p['demographics_verified']=p.birthdate.notna() & p.gender.notna()
p['demographics_source']=p.patient_id.map(lambda x:'supplied_200_person_exact_identifier_link' if x in lookup else 'not_available_in_current_structured_export')
p.to_csv(out/'patients.csv',index=False,encoding='utf-8-sig')
assert p.patient_id.is_unique
assert not w.duplicated(['patient_id','horizon_months']).any()
assert len(w)==5*p.first_recorded_E11_date.notna().sum()
events=w[w.status=='observed_CVD']
assert (events.observation_end>events.provisional_landmark).all()
assert (events.observation_end<=events.window_end).all()
result={'checks':'passed','patients_with_linked_demographics':int(p.demographics_verified.sum()),'post_E11_CVD_patients_with_linked_demographics':int((p.demographics_verified & p.recorded_CVD_after_first_E11).sum()),'event_death_date_disagreements':int(p.death_date_disagreement.sum()),'unique_merged_code_candidates':int(pd.read_csv(out/'cvd_evidence.csv').query("evidence_level=='merged_icd_candidate'").patient_id.nunique())}
(out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
