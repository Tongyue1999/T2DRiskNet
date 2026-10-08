"""Diagnostic-section candidates, with local snippets for adjudication. Not outcomes."""
from pathlib import Path
import pandas as pd,re,hashlib,json
root=Path(__file__).resolve().parent;out=root/'data/hospital_outcomes'
p=pd.read_csv(out/'patients.csv',low_memory=False).set_index('patient_id')
path=next(root.parent.glob('*/**/sample_note.rds'))
term=re.compile(r'心肌梗[死塞]|冠状动脉粥样硬化性心脏病|冠心病|心力衰竭|心衰|脑梗[死塞]|脑出血|蛛网膜下腔出血|卒中')
section=re.compile(r'(?:出院诊断|入院诊断|初步(?:<拟>)?诊断|主要诊断|最后诊断|诊断结果|诊断名称)\s*[:：]?([^\n\r]{0,500})')
neg=re.compile(r'否认|无.{0,10}(?:病史|表现|证据)|排除|未见|待排|可能|疑似|家族史|父亲|母亲')
rows=[];total=0
for chunk in pd.read_csv(path,encoding='gb18030',dtype=str,usecols=['PERSON_ID_NEW','NOTE_DATE','NOTE_TYPE','NOTE_TEXT'],chunksize=20000):
    total+=len(chunk);chunk=chunk[chunk.NOTE_TEXT.fillna('').str.contains(term)]
    for k,d,nt,text in chunk[['PERSON_ID_NEW','NOTE_DATE','NOTE_TYPE','NOTE_TEXT']].itertuples(index=False,name=None):
        pid='H-'+hashlib.sha256(str(k).encode()).hexdigest()[:24]
        date=pd.to_datetime(d,errors='coerce')
        if pd.isna(date):continue
        day=date.strftime('%Y-%m-%d');first=p.loc[pid,'first_recorded_E11_date'] if pid in p.index else None
        for sec in section.finditer(text):
            content=sec.group(1)
            for m in term.finditer(content):
                context=content[max(0,m.start()-25):min(len(content),m.end()+35)]
                flag=bool(neg.search(context))
                rows.append({'patient_id':pid,'note_date':day,'note_type':nt,'term':m.group(),'local_context':context,'negation_uncertainty_or_family_flag':flag,'after_first_E11':bool(isinstance(first,str) and day>first),'status':'diagnostic_section_candidate_requires_adjudication'})
    print('section notes scanned',total,flush=True)
df=pd.DataFrame(rows,columns=['patient_id','note_date','note_type','term','local_context','negation_uncertainty_or_family_flag','after_first_E11','status']).drop_duplicates()
df.to_csv(out/'local_diagnostic_section_candidates.csv',index=False,encoding='utf-8-sig')
positive=df[~df.negation_uncertainty_or_family_flag & df.after_first_E11]
agg=positive.groupby('patient_id').agg(first_candidate_date=('note_date','min'),candidate_rows=('note_date','size'),terms=('term',lambda s:'|'.join(sorted(set(s)))))
agg.to_csv(out/'post_landmark_text_candidates.csv',encoding='utf-8-sig')
summary={'notes_scanned':total,'diagnostic_section_rows':len(df),'diagnostic_section_patients':df.patient_id.nunique(),'post_E11_unflagged_candidate_patients':len(agg),'rule':'Unflagged diagnostic text is not confirmed new onset. History/copy-forward and negation errors need adjudication; no reclassification as primary ICD endpoint.'}
(out/'diagnostic_section_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False),flush=True)
