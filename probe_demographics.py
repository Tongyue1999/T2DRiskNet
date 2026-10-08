from engine import ROOT
import pandas as pd,re,json
p=next(ROOT.parent.glob('*/**/sample_note.rds'))
df=pd.read_csv(p,encoding='gb18030',dtype=str,usecols=['NOTE_TEXT'],nrows=2000)
texts=df.NOTE_TEXT.fillna('')
patterns={'explicit_full_birth_date':r'(?:出生日期|出生年月日|生日|birth\s*date|DOB)\s*[:：]?\s*(?:19|20)\d{2}[-/年]\d{1,2}[-/月]\d{1,2}', 'explicit_sex':r'性别\s*[:：]?\s*[男女]', 'explicit_age':r'年龄\s*[:：]?\s*\d{1,3}'}
report={'file':p.name,'notes_checked':len(df),'scope':'first 2000 notes only; not a full-table absence claim','matches':{key:int(texts.str.contains(pattern,flags=re.IGNORECASE,regex=True).sum()) for key,pattern in patterns.items()},'rule':'Age alone must not be converted to an invented date of birth; free-text values require patient linkage and consistency checks.'}
(ROOT/'reports/demographics_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report))
