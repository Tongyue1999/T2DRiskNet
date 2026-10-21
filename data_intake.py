"""Conservative multi-table EHR import. Unknown meanings require explicit mapping."""
import io,json,re,zipfile,math,csv
from datetime import date,datetime
import pandas as pd

ALIASES={
 'patient_id':['patient_id','patient_key','PERSON_ID_NEW','患者编号','患者ID','病人编号','病人ID','住院号','MRN'],
 'birthdate':['birthdate','date_of_birth','dob','出生日期','出生年月日'],
 'gender':['gender','sex','性别'],
 'admdate':['admdate','event_date','record_date','日期','记录日期','诊断日期','检验日期','采样日期','CONDITION_START_DATE','DETECT_TIME','DRUG_START_DATE','ORDER_START_TIME'],
 'codes':['codes','code','ICD10','icd_code','诊断代码','诊断编码','CONDITION_CODE','ATC','drug_code','lab_code','检验编码','项目编码','class'],
 'name':['name','项目名称','检验项目','MEASUREMENT_NAME_NEW','DRUG_NAME','药物名称'],
 'value':['value','result','检验值','结果','数值','VALUE_AS_NUMBER_NEW'],
 'unit':['unit','单位','UNIT_NEW']}
# These names and units are explicit input conventions, not universal clinical equivalences.
LABS={
 'LAB_HBA1C':('糖化血红蛋白','HbA1c','%',['hba1c','糖化血红蛋白','糖化血红蛋白(%)','hba1c(%)']),
 'LAB_GLU':('血糖','Glucose','mmol/L',['glucose','glu','血糖','血糖(mmol/l)']),
 'LAB_ALT':('谷丙转氨酶','ALT','IU/L',['alt','谷丙转氨酶','alt(iu/l)']),
 'LAB_NTPROBNP':('NT-proBNP','NT-proBNP','pg/mL',['ntprobnp','nt-probnp','nt-probnp(pg/ml)']),
 'LAB_CTNT':('肌钙蛋白T','Troponin T','ng/mL',['ctnt','troponin_t','肌钙蛋白t','肌钙蛋白t(ng/ml)'])
}

def norm(value):return re.sub(r'[\s_\-]','',str(value).replace('（','(').replace('）',')')).lower()
def full_date(value):
    s=str(value).strip()
    if not re.fullmatch(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)?|\d{4}年\d{1,2}月\d{1,2}日',s):
        raise ValueError('需要完整日期 YYYY-MM-DD / Full dates are required: '+s[:30])
    return pd.to_datetime(s.replace('年','-').replace('月','-').replace('日',''),errors='raise').strftime('%Y-%m-%d')
def sex(value):
    v=str(value).strip().lower()
    if v in ['男','male','m']:return '男'
    if v in ['女','female','f']:return '女'
    raise ValueError('性别编码需明确转换为 男/女 或 Male/Female；数字编码不自动猜测。 / Confirm sex coding.')
def read_tables(files):
    tables=[];patients={};total=0
    for name,raw in files:
        total+=len(raw)
        if total>40_000_000:raise ValueError('每批最多40 MB，请分批 / Maximum batch size is 40 MB.')
        ext=name.lower().rsplit('.',1)[-1]
        if ext=='zip':
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                entries=[i for i in z.infolist() if not i.is_dir() and not i.filename.startswith('__MACOSX')]
                if len(entries)>20 or sum(i.file_size for i in entries)>40_000_000:raise ValueError('ZIP最多20个文件、解压后40 MB / ZIP limits exceeded.')
                if any(i.filename.lower().endswith('.zip') for i in entries):raise ValueError('不支持嵌套ZIP / Nested ZIP is unsupported.')
                sub,p=read_tables([(i.filename,z.read(i)) for i in entries]);tables.extend(sub)
                if set(patients)&set(p):raise ValueError('JSON患者编号重复 / Duplicate JSON patient IDs.')
                patients.update(p)
        elif ext=='json':
            obj=json.loads(raw.decode('utf-8-sig'))
            if isinstance(obj,dict) and obj and all(isinstance(v,dict) and isinstance(v.get('events'),list) for v in obj.values()):
                if set(patients)&set(obj):raise ValueError('JSON患者编号重复 / Duplicate patient IDs.')
                patients.update(obj)
            elif isinstance(obj,list):tables.append((name,pd.DataFrame(obj)))
            else:raise ValueError('JSON需为标准患者序列或表格行数组 / Unsupported JSON structure.')
        elif ext in ['xlsx','xlsm']:
            for sheet,frame in pd.read_excel(io.BytesIO(raw),sheet_name=None).items():tables.append((name+' / '+sheet,frame))
        elif ext in ['csv','tsv','rds']:
            text=None
            for encoding in ['utf-8-sig','gb18030']:
                try:text=raw.decode(encoding);break
                except UnicodeDecodeError:pass
            if text is None or '\x00' in text:raise ValueError('二进制RDS/其他二进制文件请先导出CSV / Export binary RDS as CSV first.')
            try:delimiter='\t' if ext=='tsv' else csv.Sniffer().sniff(text[:8192],delimiters=',;\t').delimiter
            except csv.Error:delimiter=','
            tables.append((name,pd.read_csv(io.StringIO(text),sep=delimiter,dtype=str)))
        else:raise ValueError('支持 CSV、Excel、JSON、TSV、ZIP；影像、PDF或自由文本需专用适配器。 / Unsupported file type: '+ext)
    return tables,patients

def field_mapping(frame,overrides=None):
    found={};overrides=overrides or {}
    for target,aliases in ALIASES.items():
        if target in overrides and overrides[target]:
            if overrides[target] not in frame:raise ValueError('字段不在文件中 / Mapping column not found.')
            found[target]=overrides[target];continue
        hits=[c for c in frame if norm(c) in {norm(a) for a in aliases}]
        if len(hits)>1:raise ValueError('字段对应不唯一，请手动选择 / Ambiguous field: '+target)
        if hits:found[target]=hits[0]
    return found

def convert_tables(tables,patients=None,mappings=None,code_mapping=None,gender_mapping=None):
    patients=json.loads(json.dumps(patients or {},ensure_ascii=False));mappings=mappings or {};code_mapping=code_mapping or {}
    audit={'tables':[],'patients':0,'events':0,'unrecognised_columns':{},'mapping_confirmation_required':True,'unsupported_codes':[]}
    decode_gender=lambda value:sex((gender_mapping or {}).get(str(value).strip(),value))
    for rec in patients.values():rec['gender']=decode_gender(rec['gender'])
    normalized=[]
    for name,df in tables:
        mapping=field_mapping(df,mappings.get(name));audit['tables'].append({'file':name,'rows':len(df),'fields':mapping})
        if 'patient_id' not in mapping:raise ValueError(name+'：未识别患者编号，请调整字段匹配 / Missing patient ID.')
        normalized.append((name,df.rename(columns={v:k for k,v in mapping.items()}),mapping))
    # Link demographics before events; table ordering cannot change the conversion.
    for name,df,mapping in normalized:
        if 'birthdate' not in mapping or 'gender' not in mapping:continue
        for _,r in df.iterrows():
            if pd.isna(r.patient_id):raise ValueError('患者编号为空 / Missing patient ID.')
            pid=str(r.patient_id);dob=full_date(r.birthdate);gender=decode_gender(r.gender)
            if pid in patients and (patients[pid]['birthdate']!=dob or decode_gender(patients[pid]['gender'])!=gender):raise ValueError('患者人口学冲突 / Conflicting demographics: '+pid)
            patients.setdefault(pid,{'birthdate':dob,'gender':gender,'events':[]})
    for name,df,mapping in normalized:
        lab_columns={c:token for c in df for token,(_,_,_,aliases) in LABS.items() if norm(c) in {norm(x) for x in aliases}}
        audit['unrecognised_columns'][name]=[str(c) for c in df if c not in set(mapping) and c not in lab_columns]
        is_events='codes' in mapping or 'name' in mapping or bool(lab_columns)
        if not is_events:continue
        if 'admdate' not in mapping:raise ValueError(name+'：事件/检验缺少日期 / Event date required.')
        for _,r in df.iterrows():
            pid=str(r.patient_id)
            if pid not in patients:raise ValueError('患者缺少出生日期或性别，不能用年龄推算 / Missing linked demographics: '+pid)
            day=full_date(r.admdate)
            if lab_columns:
                for col,token in lab_columns.items():
                    if pd.isna(r[col]) or str(r[col]).strip()=='':continue
                    value=float(r[col]);
                    if not math.isfinite(value):raise ValueError('检验数值不是有限值 / Invalid lab value.')
                    # Wide columns use the explicitly documented template units.
                    patients[pid]['events'].append({'admdate':day,'codes':token,'value':value,'unit':LABS[token][2]})
            if 'codes' in mapping or 'name' in mapping:
                raw=str(r.get('codes',r.get('name',''))).strip()
                if not raw or raw.lower()=='nan':raise ValueError('事件代码为空 / Missing event code.')
                token=code_mapping.get(raw,raw)
                code_col=norm(mapping.get('codes',''))
                if token==raw and code_col in ['atc','drugcode'] or (token==raw and code_col=='class' and mapping.get('admdate')=='DRUG_START_DATE'):
                    token=raw if raw.startswith('RX_') else 'RX_'+raw.upper()
                elif token==raw and code_col in ['labcode','检验编码','项目编码'] or (token==raw and code_col=='class' and mapping.get('admdate')=='DETECT_TIME'):
                    token=raw if raw.startswith('LAB_') else 'LAB_'+raw.upper()
                if raw==token or token.startswith('LAB_'):
                    for lab,(_,_,_,aliases) in LABS.items():
                        if norm(raw) in {norm(a) for a in aliases}:token=lab;break
                # Never map free-text diagnoses or local hospital codes by resemblance.
                if not re.fullmatch(r'(?:LAB_|RX_|OP_).+|[A-Z]\d{2}(?:\.?[A-Z0-9]+)?',token,re.I):raise ValueError('需核对代码映射 / Verify code mapping: '+raw)
                event={'admdate':day,'codes':token}
                if 'value' in mapping and pd.notna(r.get('value')):
                    if 'unit' not in mapping or pd.isna(r.get('unit')):raise ValueError('检验缺少单位 / Lab unit is required.')
                    value=float(r['value'])
                    if not math.isfinite(value):raise ValueError('检验数值无效 / Invalid lab value.')
                    event.update(value=value,unit=str(r['unit']))
                patients[pid]['events'].append(event)
    if not patients:raise ValueError('没有可转换的患者 / No patients converted.')
    for pid,r in patients.items():
        r['birthdate']=full_date(r['birthdate']);r['gender']=decode_gender(r['gender'])
        if not isinstance(r.get('events'),list) or not r['events']:raise ValueError('缺少带日期的事件 / Missing dated events: '+pid)
        for event in r['events']:
            event['admdate']=full_date(event['admdate'])
            if event['admdate']<r['birthdate']:raise ValueError('记录早于出生日期 / Record predates birth.')
        r['events'].sort(key=lambda e:e['admdate'])
    audit.update(patients=len(patients),events=sum(len(r['events']) for r in patients.values()))
    return patients,audit

def ingest(files,mappings=None,code_mapping=None,gender_mapping=None):
    tables,patients=read_tables(files)
    return convert_tables(tables,patients,mappings,code_mapping,gender_mapping)
