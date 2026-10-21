"""Entirely invented dated records, not sampled from the hospital cohort."""
import json,io,zipfile
import pandas as pd

ASSESSMENT='2026-10-01'
def example_patient():
    return {'SYNTHETIC-EXAMPLE-001':{'birthdate':'1964-06-15','gender':'男','events':[
        {'admdate':'2019-03-01','codes':'E11.9'},
        {'admdate':'2019-03-01','codes':'I10'},
        {'admdate':'2024-10-01','codes':'LAB_HBA1C','value':7.6,'unit':'%'},
        {'admdate':'2024-10-01','codes':'LAB_GLU','value':8.1,'unit':'mmol/L'},
        {'admdate':'2025-10-01','codes':'E11.9'},
        {'admdate':'2025-10-01','codes':'I10'},
        {'admdate':'2025-10-01','codes':'RX_C10AA05'},
        {'admdate':'2026-09-25','codes':'LAB_HBA1C','value':7.8,'unit':'%'},
        {'admdate':'2026-09-25','codes':'LAB_GLU','value':8.4,'unit':'mmol/L'},
        {'admdate':'2026-09-25','codes':'LAB_ALT','value':28.,'unit':'IU/L'},
        {'admdate':'2026-09-25','codes':'LAB_NTPROBNP','value':110.,'unit':'pg/mL'}]}}

def example_zip():
    records=example_patient();key=next(iter(records));r=records[key]
    people=pd.DataFrame([{'患者编号':key,'出生日期':r['birthdate'],'性别':r['gender']}])
    events=pd.DataFrame([{'患者编号':key,'记录日期':e['admdate'],'诊断代码':e['codes'],'检验值':e.get('value'),'单位':e.get('unit')} for e in r['events']])
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('patients.csv',people.to_csv(index=False).encode('utf-8-sig'))
        z.writestr('events.csv',events.to_csv(index=False).encode('utf-8-sig'))
    return buf.getvalue()
