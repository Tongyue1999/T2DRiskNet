"""Explicit schema detection, conservative conversion, and reviewed reports."""
import io,json,html
import pandas as pd
from risk_profile import profile_html

ALIASES={'patient_id':['patient_id','PERSON_ID_NEW','患者编号','patient_key'],'birthdate':['birthdate','出生日期','date_of_birth'],'gender':['gender','性别','sex'],'admdate':['admdate','event_date','日期','诊断日期'],'codes':['codes','code','诊断代码','CONDITION_CODE'],'value':['value','检验值'],'unit':['unit','单位']}

def detect(data,name):
    if len(data)>10_000_000:raise ValueError('Maximum input size is 10 MB.')
    if name.lower().endswith('.json'):
        obj=json.loads(data.decode('utf-8-sig'))
        if not isinstance(obj,dict) or not obj or not all(isinstance(r,dict) and isinstance(r.get('events'),list) for r in obj.values()):raise ValueError('Expected a patient dictionary with events lists.')
        return obj,{'format':'patient JSON','patients':len(obj),'requires_mapping_confirmation':False}
    if name.lower().endswith('.xlsx'):df=pd.read_excel(io.BytesIO(data),dtype=str)
    else:
        df=None
        for enc in ['utf-8-sig','gb18030']:
            try:df=pd.read_csv(io.BytesIO(data),encoding=enc,dtype=str);break
            except UnicodeDecodeError:continue
        if df is None:raise ValueError('Unsupported text encoding.')
    mapping={}
    for target,aliases in ALIASES.items():
        hits=[x for x in aliases if x in df.columns]
        if len(hits)>1:raise ValueError('Ambiguous field: '+target+'; keep exactly one source column.')
        if hits:mapping[target]=hits[0]
    missing=set(['patient_id','birthdate','gender','admdate','codes'])-mapping.keys()
    if missing:raise ValueError('Missing fields: '+', '.join(sorted(missing))+'. Diagnosis/lab tables alone require linked demographics and a verified code mapping.')
    df=df.rename(columns={v:k for k,v in mapping.items()})
    if df[list(['patient_id','birthdate','gender','admdate','codes'])].isna().any().any():raise ValueError('Required fields contain missing values.')
    result={}
    for pid,g in df.groupby('patient_id',sort=False):
        if g.birthdate.nunique()!=1 or g.gender.nunique()!=1:raise ValueError('Conflicting patient demographics.')
        events=[]
        for _,row in g.iterrows():
            day=pd.to_datetime(row.admdate,format='%Y-%m-%d',errors='raise').strftime('%Y-%m-%d')
            event={'admdate':day,'codes':row.codes}
            for col in ['value','unit']:
                if col in row and pd.notna(row[col]):event[col]=row[col]
            events.append(event)
        dob=pd.to_datetime(g.birthdate.iloc[0],format='%Y-%m-%d',errors='raise').strftime('%Y-%m-%d')
        result[str(pid)]={'birthdate':dob,'gender':g.gender.iloc[0],'events':events}
    return result,{'format':'long event table','patients':len(result),'rows':len(df),'field_mapping':mapping,'requires_mapping_confirmation':True,'code_semantics':'Exact training-vocabulary mapping still required; column names do not verify clinical meaning.'}

def event_table(records):
    return pd.DataFrame([dict(patient_id=k,birthdate=v['birthdate'],gender=v['gender'],**e) for k,v in records.items() for e in v['events']])

def synthetic_patients(n=80):
    # Entirely invented fixtures, never sampled from hospital records.
    return {f'SYNTHETIC-{i:03}':{'birthdate':f'{1948+i%40}-06-15','gender':'男' if i%2 else '女','events':[{'admdate':'2024-01-01','codes':'E11'}]+[{'admdate':f'2024-{1+j//2:02}-{1+(j%2)*14:02}','codes':'I10' if (i+j)%3 else 'E78'} for j in range(4+i%14)]} for i in range(n)}

def report(row,model,horizon,reviewer,followup,assessment,lang='zh',approved=False,synthetic=True):
    if not approved or not reviewer.strip():raise ValueError('Clinician approval and reviewer are required.')
    if pd.Timestamp(followup)<=pd.Timestamp(assessment):raise ValueError('Follow-up must be after assessment.')
    risk=float(row[f'risk_{model}_{horizon}'])
    if not 0<=risk<=1:raise ValueError('Invalid risk.')
    zh=lang=='zh';esc=lambda x:html.escape(str(x))
    title='患者随访报告' if zh else 'Patient follow-up report'
    explanation='这是预测的首次心血管事件风险，不是诊断或治疗效果。随访日期由审核医生确认；不能因为低风险而停止常规治疗。' if zh else 'This is predicted first cardiovascular event risk, not a diagnosis or treatment effect. The reviewing clinician confirms follow-up; a low prediction does not justify stopping routine treatment.'
    warning=('合成病例演示，不能用于真实患者。' if zh else 'Synthetic case demonstration; not for actual patient care.') if synthetic else ('研究原型，适用性和本地校准待核实。' if zh else 'Research prototype; eligibility and local calibration require verification.')
    fields=[('编号 / ID',row['patient_key']),('评估日期 / Assessment',assessment),('模型 / Model','model_'+model),('时间窗 / Horizon',f'{horizon} months (30 days/month)'),('风险 / Risk',f'{risk:.1%}'),('医生确认随访日期 / Clinician-confirmed follow-up',followup),('审核人 / Reviewer',reviewer)]
    return '<!doctype html><html lang="'+lang+'"><meta charset="utf-8"><title>'+title+'</title><style>body{max-width:800px;margin:40px auto;padding:24px;font:17px/1.7 system-ui;color:#183247}td,th{padding:12px;border:1px solid #ccd8dc;text-align:left}table{border-collapse:collapse;width:100%}</style><h1>'+title+'</h1><p>'+esc(warning)+'</p><table>'+''.join('<tr><th>'+esc(a)+'</th><td>'+esc(b)+'</td></tr>' for a,b in fields)+'</table>'+profile_html(dict(row,assessment_date=assessment),model,lang)+'<p>'+esc(explanation)+'</p></html>'
