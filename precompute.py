import json
from engine import ROOT, sample_path, infer
from analysis import evaluate
records=json.loads(sample_path().read_text(encoding='utf-8'))
for mode in ['current','retrospective']:
    print('Starting',mode,flush=True)
    frame,excluded,manifest=infer(records,mode,progress=lambda q:print('Progress',round(100*q),flush=True))
    frame.to_csv(ROOT/'data'/f'sample_{mode}.csv',index=False)
    excluded.to_csv(ROOT/'data'/f'sample_{mode}_exclusions.csv',index=False)
    (ROOT/'data'/f'sample_{mode}_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(mode,'included',len(frame),'excluded',len(excluded),flush=True)
    if mode=='retrospective':
        try:
            result=evaluate(frame,['risk_02_12','risk_03_12'],12,bootstrap=200)
            quality=result['quality']
        except ValueError as exc:
            quality={'status':'not_estimable','reason':str(exc),'observed_cvd_events':int((frame.event_type==1).sum()),'n':len(frame)}
        (ROOT/'reports'/'sample_analysis_quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Evaluation quality',quality,flush=True)
