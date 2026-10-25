"""Explicit hospital raw-table profile for the local uploader.

Matches raw schema and exact training tokens; retains diagnoses for eligibility.
Unmatched procedures/drugs/labs are audited, never guessed. Original laboratory
preprocessing decides numeric masks; unverified units are counted explicitly.
"""
from collections import Counter
from pathlib import Path
import hashlib,math,json
import pandas as pd
from data_intake import full_date,sex

def is_hospital_profile(tables):
    context=any({'PERSON_ID_NEW','birthdate','gender','assessment_date'}<=set(df) for _,df in tables)
    events=any({'CONDITION_CODE','CONDITION_START_DATE'}<=set(df) or {'DETECT_TIME','class','VALUE_AS_NUMBER_NEW'}<=set(df) or {'DRUG_START_DATE','class'}<=set(df) for _,df in tables)
    return context and events

def private_key(pid):return 'P-'+hashlib.sha256(str(pid).encode()).hexdigest()[:16]

def convert_hospital_tables(tables):
    from engine import resources
    package,vendor,prep,cfg,_=resources();vocab=cfg['code_to_index_map']
    contexts=[df for _,df in tables if {'PERSON_ID_NEW','birthdate','gender','assessment_date'}<=set(df)]
    if len(contexts)!=1:raise ValueError('需要一张已关联的人口学及评估日期表 / One linked demographic/assessment table required.')
    context=contexts[0].fillna('');records={};dates={};held=[]
    if context.PERSON_ID_NEW.duplicated().any():raise ValueError('人口学患者编号重复 / Duplicate demographic patient IDs.')
    for r in context.to_dict('records'):
        pid=str(r['PERSON_ID_NEW']);reason=str(r.get('eligibility_hold_reason','')).strip()
        if reason:held.append({'patient_key':private_key(pid),'reason':'source history review hold: '+reason});continue
        try:
            dob=full_date(r['birthdate']);gender=sex(r['gender']);anchor=full_date(r['assessment_date'])
        except Exception:
            held.append({'patient_key':private_key(pid),'reason':'missing or invalid demographics/assessment date'});continue
        rec={'birthdate':dob,'gender':gender,'events':[]}
        for col in ['end_of_data','death_date']:
            rec[col]=full_date(r[col]) if r.get(col) else None
        records[pid]=rec;dates[pid]=anchor
    counters=Counter();unmapped=Counter();tables_audit=[]
    def source_order(item):
        name,df=item
        if 'CONDITION_START_DATE' in df:priority=0
        elif 'PROCEDURE_DATE' in df:priority=1
        elif 'DETECT_TIME' in df:priority=2
        elif 'DRUG_START_DATE' in df:priority=3
        else:priority=4
        return priority,name
    # Frozen package/history adapter order. Same-day token order affects the model.
    # ZIP member order and file-selection order must not change a patient's result.
    for name,df in sorted(tables,key=source_order):
        if 'CONDITION_START_DATE' in df and 'CONDITION_CODE' in df:kind,dc,cc='diagnosis','CONDITION_START_DATE','CONDITION_CODE'
        elif 'DETECT_TIME' in df and 'VALUE_AS_NUMBER_NEW' in df and 'class' in df:kind,dc,cc='laboratory','DETECT_TIME','class'
        elif 'DRUG_START_DATE' in df and 'class' in df:kind,dc,cc='medication','DRUG_START_DATE','class'
        elif 'PROCEDURE_DATE' in df:kind,dc,cc='procedure','PROCEDURE_DATE','class'
        else:continue
        if 'PERSON_ID_NEW' not in df or cc not in df:raise ValueError('医院表缺少关联或代码列 / Missing hospital linkage/code column.')
        counters[kind+'_raw_rows']+=len(df)
        frame=df[df.PERSON_ID_NEW.astype(str).isin(records)].copy()
        parsed=pd.to_datetime(frame[dc],format='mixed',errors='coerce');valid=parsed.notna()
        counters['invalid_date_rows']+=int((~valid).sum());frame=frame.loc[valid].copy();frame[dc]=parsed.loc[valid].dt.strftime('%Y-%m-%d')
        cols=['PERSON_ID_NEW',dc,cc]+(['VALUE_AS_NUMBER_NEW','UNIT_NEW'] if kind=='laboratory' else [])
        for values in frame[cols].itertuples(index=False,name=None):
            pid,day,raw=values[:3];pid=str(pid);raw='' if pd.isna(raw) else str(raw).strip()
            if not raw or raw.lower()=='nan':counters['missing_code_rows']+=1;continue
            if kind=='diagnosis':
                # Preserve original ICD including unmapped target diagnoses.
                token=raw
                if vendor.code(raw,cfg) not in vocab:counters['unmapped_diagnoses_retained_for_eligibility']+=1
            else:
                if kind=='laboratory':token=raw if raw.startswith('LAB_') else 'LAB_'+raw.upper()
                elif kind=='medication':token=raw if raw.startswith('RX_') else 'RX_'+raw.upper()
                else:token=raw  # No invented procedure mapping.
                if token not in vocab:
                    counters[kind+'_unmapped_rows']+=1;unmapped[kind+':'+raw]+=1;continue
            e={'admdate':day,'codes':token}
            if kind=='laboratory':
                e.update(value=None if pd.isna(values[3]) else str(values[3]),unit=None if pd.isna(values[4]) else str(values[4]))
            records[pid]['events'].append(e);counters[kind+'_events']+=1
        tables_audit.append({'file':name,'rows':len(df),'profile':kind,'patient_linkage':'PERSON_ID_NEW','date_column':dc,'code_column':cc})
    for pid,rec in records.items():rec['events'].sort(key=lambda e:e['admdate'])
    # Audit the SAME functions/config used by the frozen model preprocessing.
    aliases,byunit,conversions=prep.load_mapping(package/'config/lab_mapping.json')
    stats=prep.load_stats(package/'config/lab_stats.json');expected=prep.load_expected_units(package/'config/lab_units.csv')
    numeric=Counter();issues=[]
    for pid,rec in records.items():
        rejected=Counter()
        for e in rec['events']:
            if e['admdate']>dates[pid]:continue
            if not e['codes'].startswith('LAB_'):continue
            token=aliases.get(e['codes'],e['codes']);token=byunit.get((token,prep.unit(e.get('unit'))),token)
            value=prep.numeric(e.get('value'))
            if value is None:
                e['_numeric_usable']=False
                numeric['qualitative_or_missing_values']+=1;continue
            numeric['raw_numeric_values']+=1
            converted=prep.convert(token,value,e.get('unit'),expected.get(token,''),conversions)
            if converted is None:
                e['_numeric_usable']=False
                numeric['unverified_unit_numeric_values_not_used']+=1;rejected[token+': unverified or unspecified unit']+=1
            elif prep.transform(converted,stats.get(token,{})) is None:
                e['_numeric_usable']=False
                numeric['unsupported_numeric_transform_not_used']+=1;rejected[token+': no numeric transform']+=1
            else:
                e['_numeric_usable']=True
                numeric['usable_numeric_values_before_deduplication']+=1
        for reason,count in rejected.items():issues.append({'patient_key':private_key(pid),'issue':reason,'records':count})
    audit={'profile':'hospital_raw_tables_v1','source_patients':len(context),'patients':len(records),'events':sum(len(r['events']) for r in records.values()),
           'held_patients':held,'tables':tables_audit,'conversion_counts':dict(counters),'numeric_preprocessing':dict(numeric),
           'unmapped_code_counts':dict(unmapped),'numeric_issues':issues,'mapping_confirmation_required':True,
           'assessment_policy':'per-patient supplied historical first-E11 date; no invented common current date',
           'same_day_order':'diagnosis, procedure, laboratory, medication; stable source row order within each table',
           'numeric_policy':'original frozen prep.convert/transform; no guessed unit equivalence or missing-to-zero',
           'future_records_used_as_predictors':False,'procedure_mapping':'only exact OP_ training tokens; otherwise not used'}
    return records,dates,audit

def run_hospital_upload(records,dates,audit,progress=None):
    from engine import infer
    f,ex,m=infer(records,'current',assessment_dates=dates,progress=progress)
    held=pd.DataFrame(audit['held_patients'],columns=['patient_key','reason'])
    ex=pd.concat([held,ex],ignore_index=True)
    m.update(source_patients=audit['source_patients'],input_patients=len(records),included=len(f),excluded_total=len(ex),
             upload_profile=audit['profile'],assessment_policy=audit['assessment_policy'],numeric_policy=audit['numeric_policy'],clinical_verification=False)
    return f,ex,m
