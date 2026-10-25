"""Parameter-only runtime for the locally trained research 5/10-input models.

No patient rows, pickle loading, lifelines, or hospital files are needed at runtime.
"""
from pathlib import Path
from functools import lru_cache
from datetime import date
import hashlib,json,math
import numpy as np
import pandas as pd

HORIZONS=[3,6,12,36,60]

@lru_cache(maxsize=1)
def load_models():
    root=Path(__file__).resolve().parent
    paths=[root/'simple_models.json',root/'data/simple_models.json']
    path=next((p for p in paths if p.exists()),None)
    if path is None:raise ValueError('研究模型尚未安装 / Research model is not installed.')
    return json.loads(path.read_text(encoding='utf8'))

def predict_values(values,model='simple5',bundle=None):
    bundle=bundle or load_models();node=bundle['models'][model];pre=node['preprocessing'];v={}
    for c in node['features']:
        raw=values.get(c);missing=raw is None or pd.isna(raw)
        v[c]=float(pre['median'][c]) if missing else min(max(float(raw),pre['lo'][c]),pre['hi'][c])
        if c in pre['indicators']:v[c+'__missing']=float(missing)
    multipliers=[];jumps=[]
    for cause in node['causes']:
        q=np.array([v[c] for c in cause['columns']]);coef=np.array(cause['coef']);mean=np.array(cause['mean'])
        multipliers.append(float(np.exp(np.clip((q-mean)@coef,-700,700))))
        jumps.append(dict(zip(cause['hazard_times'],cause['hazard_jumps'])))
    times=sorted(set(jumps[0])|set(jumps[1]));S=1.;F=0.;i=0;out=[]
    for horizon in bundle['horizons_months']:
        while i<len(times) and times[i]<=horizon*30:
            a=jumps[0].get(times[i],0.)*multipliers[0];b=jumps[1].get(times[i],0.)*multipliers[1];total=a+b
            if total:F+=S*a/total*(-math.expm1(-total));S*=math.exp(-total)
            i+=1
        out.append(F)
    if not np.isfinite(out).all() or any(not 0<=x<=1 for x in out):raise ValueError('Invalid probability')
    return out

def assess(values,assessment,lab_dates,extended=False,synthetic=False):
    anchor=date.fromisoformat(str(assessment));model='simple10' if extended else 'simple5'
    if values.get('age') is None or not 18<=float(values['age'])<120:raise ValueError('请填写18–119岁的年龄 / Enter age 18–119.')
    if values.get('male') not in [0,1]:raise ValueError('请选择性别 / Select sex.')
    if values.get('I10') not in [0,1]:raise ValueError('请核实既往高血压记录 / Confirm recorded hypertension history.')
    if extended and values.get('RX_B01AC06') not in [0,1]:raise ValueError('请核实近一年阿司匹林记录 / Confirm past-year aspirin records.')
    features=load_models()['models'][model]['features'];clean={c:values.get(c) for c in features}
    limits={'LAB_HBA1C':(0,100),'LAB_CR':(0,10000),'SBP':(60,260),'DBP':(30,160),'LAB_LDL':(0,100),'LAB_GLU':(0,1000)}
    for code,bounds in limits.items():
        if code not in clean or clean[code] is None:continue
        value=float(clean[code])
        if not math.isfinite(value) or not bounds[0]<=value<=bounds[1]:raise ValueError('请检查数值 / Check value: '+code)
        if not lab_dates.get(code):raise ValueError('请补充检测日期 / Add measurement date: '+code)
        day=date.fromisoformat(str(lab_dates[code]))
        if not 0<=(anchor-day).days<=365:raise ValueError('请使用评估日前365天内的数值 / Use measurements from the prior 365 days.')
    if extended and clean.get('SBP') is not None and clean.get('DBP') is not None and clean['DBP']>=clean['SBP']:
        raise ValueError('舒张压应低于收缩压 / Diastolic pressure must be below systolic pressure.')
    risks=predict_values(clean,model)
    rid='SYNTHETIC-SIMPLE-CASE' if synthetic else 'LOCAL-SIMPLE-CASE';pid='P-'+hashlib.sha256(rid.encode()).hexdigest()[:16]
    row={'patient_key':pid,'assessment_date':anchor.isoformat(),'age':float(clean['age']),'sex':'男' if clean['male'] else '女',
         'model_family':'reduced','input_count':len(features),'matched_events':0,'raw_events':0,'numeric_labs':sum(clean.get(c) is not None for c in limits if c in clean)}
    row.update({f'risk_{model}_{h}':r for h,r in zip(HORIZONS,risks)})
    units={'LAB_HBA1C':'%','LAB_CR':'μmol/L','LAB_LDL':'mmol/L','LAB_GLU':'mmol/L','SBP':'mmHg','DBP':'mmHg'}
    events=[{'admdate':str(lab_dates[c]),'codes':c,'value':float(clean[c]),'unit':units[c]} for c in units if c in clean and clean[c] is not None]
    # Age is supplied directly; never invent a birth date or diagnostic event date.
    rec={'gender':row['sex'],'age':row['age'],'events':events,'_simple_inputs':clean}
    manifest={'model':model,'model_family':'reduced','input_count':len(features),'status':'RESEARCH_TRIAL','unsupported_validation_horizons':[60],
              'month_days':30,'source_sha256':hashlib.sha256(json.dumps({'values':clean,'dates':lab_dates,'assessment':str(assessment)},sort_keys=True).encode()).hexdigest()}
    return {rid:rec},pd.DataFrame([row]),pd.DataFrame(columns=['patient_key','reason']),manifest
