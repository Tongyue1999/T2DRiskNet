from pathlib import Path
import pandas as pd,json
root=Path(__file__).resolve().parent;out=root/'data/hospital_outcomes'
p=pd.read_csv(out/'patients.csv',low_memory=False).set_index('patient_id')
e=pd.read_csv(out/'local_diagnostic_section_candidates.csv')
unflagged=e[~e.negation_uncertainty_or_family_flag]
first=unflagged.groupby('patient_id').note_date.min()
c=pd.read_csv(out/'post_landmark_text_candidates.csv')
c['first_unflagged_diagnostic_mention']=c.patient_id.map(first)
c['provisional_landmark']=c.patient_id.map(p.first_recorded_E11_date)
c['has_text_candidate_at_or_before_landmark']=c.first_unflagged_diagnostic_mention<=c.provisional_landmark
c['adjudication_required']=True;c['confirmed_incident_event']=False
c['actual_event_date']=None;c['adjudicated_endpoint']=None;c['reviewer']=None
c.to_csv(out/'post_landmark_text_candidates.csv',index=False,encoding='utf-8-sig')
# Prioritise cases without a recorded pre-landmark candidate, not proof of disease absence.
priority=c[~c.has_text_candidate_at_or_before_landmark].copy()
priority.to_csv(out/'priority_text_adjudication.csv',index=False,encoding='utf-8-sig')
note=json.loads((out/'diagnostic_section_audit.json').read_text(encoding='utf-8'))
note['post_landmark_candidates_with_pre_landmark_mentions']=int(c.has_text_candidate_at_or_before_landmark.sum())
note['post_landmark_candidates_without_recorded_prior_mentions']=len(priority)
(out/'diagnostic_section_audit.json').write_text(json.dumps(note,ensure_ascii=False,indent=2),encoding='utf-8')
assert not c.confirmed_incident_event.any()
print(json.dumps(note,ensure_ascii=False))
