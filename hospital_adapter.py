"""Chunked CSV-with-rds-extension adapter; no demographic or coding imputation."""
from pathlib import Path
import json, hashlib
import pandas as pd
from engine import ROOT, resources

def convert(demographics, mapping=None):
    required={'PERSON_ID_NEW','birthdate','gender'}
    if not required.issubset(demographics.columns):
        raise ValueError('人口学资料必须包含 PERSON_ID_NEW、birthdate、gender。')
    if demographics[list(required)].isna().any().any() or demographics.PERSON_ID_NEW.duplicated().any():
        raise ValueError('人口学资料有缺失或重复患者。')
    if len(demographics)>10000:
        raise ValueError('首版适配器每批最多 10,000 名患者。')
    _,vendor,_,cfg,_=resources()
    vocab=cfg['code_to_index_map']
    maps={}
    if mapping is not None:
        if not {'source','name','token'}.issubset(mapping.columns):
            raise ValueError('映射表需要 source、name、token。source 为 lab、med 或 op。')
        if mapping[['source','name','token']].isna().any().any() or mapping.duplicated(['source','name']).any():
            raise ValueError('映射表存在缺失或同一名称的重复映射。')
        for _,row in mapping.iterrows():
            source,token=str(row['source']).strip(),str(row['token']).strip()
            prefix={'lab':'LAB_','med':'RX_','op':'OP_'}.get(source)
            if prefix is None or not token.startswith(prefix) or token not in vocab:
                raise ValueError('映射 token 必须属于相应类型且存在于训练词表。')
            maps[(source,str(row['name']).strip())]=token
    paths={p.name:p for p in ROOT.parent.glob('*/**/sample_*.rds')}
    records={}
    for _,row in demographics.iterrows():
        key=str(row.PERSON_ID_NEW)
        dob=vendor.parse_date(row.birthdate,True)
        sex=vendor.gender_value(row.gender)
        if sex not in {0.,1.}:
            raise ValueError('人口学资料性别编码无法识别。')
        records[key]={'birthdate':dob.isoformat(),'gender':'男' if sex else '女','end_of_data':None,'death_date':None,'events':[]}
        for col in ['end_of_data','death_date']:
            if col in demographics and pd.notna(row[col]) and str(row[col]).strip():
                records[key][col]=vendor.parse_date(row[col],True).isoformat()
    last_contact={}
    report={'patients_requested':len(records),'diagnosis_events':0,'lab_events':0,'med_events':0,'op_events':0,'unmapped_rows':{},'invalid_dates':0,'notes':'原始诊断代码优先；药物 ATC 和检验 class 仅按精确训练 token 匹配；不猜测生日、性别或药物代码；死亡来自明确记录的 death 事件，不等于完整死亡登记。'}
    def stream(filename,cols):
        if filename not in paths:
            return
        for chunk in pd.read_csv(paths[filename],encoding='gb18030',dtype=str,usecols=cols,chunksize=25000):
            subset=chunk[chunk.PERSON_ID_NEW.isin(records)].copy()
            for column in cols:
                if column in {'VISIT_START_DATE','VISIT_END_DATE','CONDITION_START_DATE','PROCEDURE_DATE','DETECT_TIME','DRUG_START_DATE','date'}:
                    parsed=pd.to_datetime(subset[column],errors='coerce',format='mixed')
                    report['invalid_dates']+=int(parsed.isna().sum())
                    subset[column]=parsed.dt.strftime('%Y-%m-%d')
            yield subset
    def day(value):
        return None if pd.isna(value) else str(value)
    for chunk in stream('sample_visit.rds',['PERSON_ID_NEW','VISIT_START_DATE','VISIT_END_DATE']):
        for key,start,end in chunk.itertuples(index=False,name=None):
            for val in [start,end]:
                d=day(val)
                if d:
                    last_contact[key]=max(last_contact.get(key,d),d)
    specs=[('sample_diag.rds','diagnosis','CONDITION_CODE','CONDITION_START_DATE',None,None),
           ('sample_oper.rds','op','PROCEDURE_NAME','PROCEDURE_DATE',None,None),
           ('sample_lab.rds','lab','MEASUREMENT_NAME_NEW','DETECT_TIME','VALUE_AS_NUMBER_NEW','UNIT_NEW'),
           ('sample_atc.rds','med','DRUG_NAME','DRUG_START_DATE',None,None)]
    for filename,source,namecol,datecol,valuecol,unitcol in specs:
        if source=='op' and not any(k[0]==source for k in maps):
            report['unmapped_rows'][source]='未提供映射，未加载该数据源'
            continue
        cols=['PERSON_ID_NEW',namecol,datecol]+([valuecol,unitcol] if valuecol else [])
        if source in {'lab','med'}:cols.append('class')
        for chunk in stream(filename,cols):
            for _,row in chunk.iterrows():
                key=row.PERSON_ID_NEW
                d=day(row[datecol])
                if not d:
                    continue
                last_contact[key]=max(last_contact.get(key,d),d)
                name=str(row[namecol]).strip()
                token=vendor.code(name,cfg) if source=='diagnosis' else maps.get((source,name))
                if not token and source in {'lab','med'}:
                    source_code=str(row['class']).strip()
                    candidate=('LAB_' if source=='lab' else 'RX_')+source_code.upper()
                    if candidate in vocab:token=candidate
                # Preserve raw diagnosis even if unmapped, so prevalent CVD is detected.
                if source=='diagnosis':
                    token=name
                if not token:
                    report['unmapped_rows'][source]=report['unmapped_rows'].get(source,0)+1
                    continue
                event={'admdate':d,'codes':token}
                if valuecol:
                    event.update(value=row[valuecol] if pd.notna(row[valuecol]) else None,unit=row[unitcol] if pd.notna(row[unitcol]) else None)
                records[key]['events'].append(event)
                report[{'diagnosis':'diagnosis_events','lab':'lab_events','med':'med_events','op':'op_events'}[source]]+=1
    recorded_deaths={}
    for chunk in stream('sample_event.rds',['PERSON_ID_NEW','class','date']):
        for _,row in chunk[chunk['class']=='death'].iterrows():
            key=row.PERSON_ID_NEW;d=day(row['date'])
            if d:recorded_deaths[key]=min(recorded_deaths.get(key,d),d)
    report['patients_with_explicit_recorded_death']=len(recorded_deaths)
    output={}
    inferred=0
    for key,rec in records.items():
        if key in recorded_deaths and rec['death_date'] is None:rec['death_date']=recorded_deaths[key]
        rec['events'].sort(key=lambda e:e['admdate'])
        if rec['end_of_data'] is None:
            rec['end_of_data']=last_contact.get(key)
            inferred+=1
        # Same local source identifier gives a stable patient hash across all inputs.
        output[key]=rec
    report.update(patients_with_events=sum(bool(r['events']) for r in output.values()),inferred_followup_end=inferred,demographics_source='user supplied; not inferred')
    return output,report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--demographics',required=True)
    p.add_argument('--mapping')
    p.add_argument('--output',required=True)
    args=p.parse_args()
    records,report=convert(pd.read_csv(args.demographics,dtype=str),pd.read_csv(args.mapping,dtype=str) if args.mapping else None)
    Path(args.output).write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
