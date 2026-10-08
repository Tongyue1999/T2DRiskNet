import json
import pandas as pd
from engine import ROOT

def render(st,lang):
    out=ROOT/'data/hospital_outcomes';sp=out/'summary.json'
    if not sp.exists():return
    en=lang=='en';t=lambda zh,eng:eng if en else zh
    summary=json.loads(sp.read_text(encoding='utf-8'))
    st.subheader(t('省立医院全量结局提取','Hospital-wide outcome extraction'))
    for c,label,n in zip(st.columns(3),[t('患者总数','Patients'),t('记录2型糖尿病','Recorded E11'),t('暂定起点后的CVD记录','CVD after provisional landmark')],[summary['patients'],summary['E11_patients'],summary['recorded_CVD_after_first_E11']]):c.metric(label,f'{n:,}')
    st.warning(t('这些是已记录结局。首次E11作为暂定起点，尚未核实年龄、完整输入病史及结局捕获范围，不能据此报告模型优越性。','These are recorded outcomes. First E11 is a provisional landmark. Age, input histories and outcome ascertainment remain unverified; model superiority cannot yet be estimated.'))
    data=[]
    for horizon,s in summary['windows'].items():
        data.append({t('窗口（月）','Horizon (months)'):int(horizon),t('已记录CVD','Recorded CVD'):s.get('observed_CVD',0),t('已记录竞争死亡','Recorded competing deaths'):s.get('recorded_competing_death',0),t('记录提前结束','Contact ended before horizon'):s.get('censored_contact_only',0),t('记录延续但未记录CVD','Contact beyond horizon without recorded CVD'):s.get('no_recorded_CVD_with_contact_beyond_window',0)})
    st.dataframe(pd.DataFrame(data),hide_index=True,use_container_width=True)
    st.caption(t('窗口已与模型统一为30天/月。记录延续不等于完整随访。','Windows use the model’s 30-day month convention. Continued contact does not establish complete follow-up.'))
    np=out/'note_audit.json'
    if np.exists():
        note=json.loads(np.read_text(encoding='utf-8'))
        st.write(t(f'全量扫描 {note["notes_scanned"]:,} 条病历；{note["patients_with_explicit_DOB"]:,} 人有明确出生日期候选，{note["note_CVD_candidate_patients"]:,} 人有心血管文本候选。候选尚未人工核实。',f'All {note["notes_scanned"]:,} notes scanned; {note["patients_with_explicit_DOB"]:,} patients have explicit DOB candidates and {note["note_CVD_candidate_patients"]:,} have CVD text mentions. Candidates remain unadjudicated.'))
    dp=out/'diagnostic_section_audit.json'
    if dp.exists():
        diagnostic=json.loads(dp.read_text(encoding='utf-8'))
        st.caption(t(f'诊断段落候选涉及 {diagnostic["diagnostic_section_patients"]:,} 人；暂定起点后未触发否定等规则的候选涉及 {diagnostic["post_E11_unflagged_candidate_patients"]:,} 人。仍须排查既往病史与复制记录。',f'Diagnostic-section candidates involve {diagnostic["diagnostic_section_patients"]:,} patients; {diagnostic["post_E11_unflagged_candidate_patients"]:,} have unflagged mentions after the provisional landmark. Prior disease and copied records still require review.'))
    ep=out/'exploratory_model_audit.json'
    if ep.exists():
        exploratory=json.loads(ep.read_text(encoding='utf-8'))
        st.info(t(f'已用病历人口学候选完成 {exploratory["predictions"]} 人的真实模型推理。仅用于流程测试；人口学与既往CVD未完成临床核实，不能用于临床决策或优越性比较。',f'Real model inference completed for {exploratory["predictions"]} patients using candidate demographics from notes. Workflow testing only: demographics and prior CVD remain unadjudicated; these predictions cannot support clinical decisions or superiority comparisons.'))
    labels={'patients.csv':('患者结局表','Patient outcomes'),'prediction_windows.csv':('预测窗口表','Prediction windows'),'cvd_evidence.csv':('诊断证据表','Diagnosis evidence'),'model_readiness.csv':('模型输入准备情况','Model readiness'),'note_cvd_candidates.csv':('病历文本候选','Note CVD candidates'),'post_landmark_text_candidates.csv':('起点后诊断段落候选','Post-landmark diagnostic candidates'),'local_event_patients_to_complete.csv':('优先补齐事件患者人口学资料','Priority event-patient demographic template'),'local_demographics_to_complete.csv':('全队列人口学补充表','Full cohort demographic template')}
    for file,(zh,eng) in labels.items():
        path=out/file
        if path.exists():st.download_button(t('下载'+zh,'Download '+eng),path.read_bytes(),file,'text/csv',key='outcome_'+file)
    pred=out/'exploratory_note_predictions.csv'
    if pred.exists():st.download_button(t('下载探索性流程测试预测','Download exploratory workflow predictions'),pred.read_bytes(),pred.name,'text/csv',key='exploratory_predictions')
    review=out/'priority_text_adjudication.csv'
    if review.exists():st.download_button(t('下载优先核实的文本结局候选','Download prioritised text adjudication candidates'),review.read_bytes(),review.name,'text/csv',key='text_adjudication')
