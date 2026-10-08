"""Link real hospital tables to existing demographics via exact identifiers."""
import json
import pandas as pd
from engine import ROOT,sample_path,infer
from hospital_adapter import convert
records=json.loads(sample_path().read_text(encoding='utf-8'))
demographics=pd.DataFrame([{'PERSON_ID_NEW':key,'birthdate':record['birthdate'],'gender':record['gender'],'end_of_data':record.get('end_of_data'),'death_date':record.get('death_date')} for key,record in records.items()])
# NA in the supplied sample denotes unknown, not a death date.
demographics=demographics.replace({'NA':None,'N/A':None,'' :None})
print('Linking 200 exact source identifiers; demographics from supplied JSON, clinical history from hospital tables.',flush=True)
converted,report=convert(demographics)
report['demographics_source']='supplied ustc_200patients_demo.json, exact source-identifier linkage; no age-to-birthdate imputation'
report['scope']='Only the 200 exactly linked identifiers; not all hospital patients.'
(ROOT/'data/hospital_linked_200.json').write_text(json.dumps(converted,ensure_ascii=False),encoding='utf-8')
(ROOT/'reports/hospital_linkage_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Conversion',json.dumps(report,ensure_ascii=True),flush=True)
for mode in ['current','retrospective']:
    print('Inference',mode,flush=True)
    frame,excluded,manifest=infer(converted,mode)
    manifest.update(cohort='hospital_exactly_linked_200',demographics_source=report['demographics_source'],source_files='real hospital diagnosis, laboratory, ATC, visit and explicit death-event tables',sample_independence_verified=False)
    frame.to_csv(ROOT/'data'/f'hospital_{mode}.csv',index=False)
    excluded.to_csv(ROOT/'data'/f'hospital_{mode}_exclusions.csv',index=False)
    (ROOT/'data'/f'hospital_{mode}_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Completed',mode,len(frame),'predictions',len(excluded),'excluded',flush=True)
