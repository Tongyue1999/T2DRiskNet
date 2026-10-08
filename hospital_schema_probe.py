from engine import ROOT
import pandas as pd,json
paths={p.name:p for p in ROOT.parent.glob('*/**/sample_*.rds')}
report={}
for filename,cols,nrows in [('sample_diag.rds',['CONDITION_CODE','CONDITION_CODE_HF'],None),('sample_event.rds',['cond','class'],None),('sample_lab.rds',['MEASUREMENT_NAME_NEW','class'],5000),('sample_sub_atc.rds',['DRUG_NAME','class'],5000),('sample_oper.rds',['PROCEDURE_CODE','PROCEDURE_CODE_HF','class'],None)]:
    d=pd.read_csv(paths[filename],encoding='gb18030',dtype=str,usecols=cols,nrows=nrows)
    report[filename]={'scope':'full' if nrows is None else 'first 5000 rows','rows':len(d),'common_values':{c:d[c].value_counts().head(12).to_dict() for c in cols}}
cfg=json.loads(next((ROOT/'vendor').rglob('lab_stats.json')).read_text(encoding='utf-8'))
report['lab_stats_record_keys']=list(cfg.get('records',{}))[:5]
node=next(iter(cfg.get('records',{}).values()))
report['lab_stats_fields']=list(node[0] if isinstance(node,list) else node)
(ROOT/'reports/hospital_schema_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))
