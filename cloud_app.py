"""Public synthetic research demo; private hospital deployment is a separate mode."""
import os,json,io
from datetime import date,timedelta
import numpy as np
import pandas as pd
import streamlit as st
from engine import infer,HORIZONS
from analysis import evaluate,selected
from risk_profile import render_profile
from clinical_io import detect,event_table,synthetic_patients,report

st.set_page_config(page_title='T2DRiskNet Research Workbench',page_icon='🫀',layout='wide')
lang=st.sidebar.selectbox('语言 / Language',['中文','English'],index=1 if st.query_params.get('lang')=='en' else 0)
zh=lang=='中文';t=lambda a,b:a if zh else b
st.title(t('T2DRiskNet 风险与复查研究工作台','T2DRiskNet Risk and Review Research Workbench'))
demo=os.environ.get('T2D_MODE','demo')=='demo'
if demo:st.warning(t('公开合成病例演示：运行真实模型，但患者和随访结局均为虚构。不接收真实医院资料，不构成临床验证。','Public synthetic demo: real model inference, invented patients and outcomes. Real hospital uploads are disabled. This is not clinical validation.'))
else:st.warning(t('院内研究模式：请仅在有身份认证和授权的数据环境使用。','Institutional research mode: use only within an authenticated, authorised environment.'))
st.info(t('模型输出风险及队列排序，不自动给出医学随访间隔。患者报告须由医生确认日期后生成。两个模型的正式身份及本地校准尚待核实。','Models output risk and cohort ranking, not a medically validated follow-up interval. A clinician must confirm the report date. Model identities and local calibration remain unverified.'))
page=st.sidebar.radio(t('功能','Workspace'),[t('数据接入与预测','Data and prediction'),t('资源约束仿真','Capacity simulation'),t('医生审核与患者报告','Clinician review and patient report')])
records=synthetic_patients()
assessment='2025-01-01'
if page in ['数据接入与预测','Data and prediction']:
    st.subheader(t('自动识别格式，明确核对字段与语义','Detect format; verify fields and clinical semantics'))
    if demo:
        fmt=st.selectbox(t('模拟医院导出格式','Simulated hospital export format'),['JSON','CSV (UTF-8)','CSV (GB18030)'])
        if fmt=='JSON':raw=json.dumps(records,ensure_ascii=False).encode();name='synthetic.json'
        else:raw=event_table(records).to_csv(index=False).encode('gb18030' if 'GB18030' in fmt else 'utf-8-sig');name='synthetic.csv'
        records,audit=detect(raw,name)
        st.download_button(t('下载合成输入示例','Download synthetic input'),raw,name)
    else:
        upload=st.file_uploader(t('授权患者资料（JSON、CSV、Excel）','Authorised patient input (JSON, CSV, Excel)'),type=['json','csv','xlsx','rds'])
        if not upload:st.stop()
        try:records,audit=detect(upload.getvalue(),upload.name)
        except Exception as e:st.error(str(e));st.stop()
        assessment=st.date_input(t('统一评估日期','Assessment date'),date.today()).isoformat()
    st.json(audit)
    st.caption(t('自动识别文件结构不等于自动理解任意医院编码。未知字段、单位和代码必须映射核实；不会猜测出生日期。','Format detection is not automatic interpretation of arbitrary hospital codes. Unknown fields, units and codes require verified mapping; birthdates are not guessed.'))
    import hashlib
    digest=hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).hexdigest()+assessment
    if st.session_state.get('input_digest') not in [None,digest]:st.session_state.pop('cloud_predictions',None)
    st.session_state['input_digest']=digest
    confirmed=st.checkbox(t('已确认字段映射、日期及编码含义（演示时仅模拟确认）','Confirm field mapping, dates and code meaning (simulated confirmation in demo)'))
    if st.button(t('运行两个真实模型','Run both real models'),disabled=not confirmed,type='primary'):
        st.session_state.pop('cloud_predictions',None)
        try:
            with st.spinner(t('CPU 模型计算中…','Running CPU inference…')):
                f,ex,manifest=infer(records,'current',assessment)
            st.session_state['cloud_predictions']=(f,ex,manifest,demo)
        except Exception as e:st.error(str(e))

if 'cloud_predictions' not in st.session_state:
    st.info(t('请先在“数据接入与预测”中确认输入并运行模型。','Confirm input and run models in Data and prediction first.'));st.stop()
f,ex,manifest,synthetic=st.session_state['cloud_predictions']
model=st.selectbox(t('模型权重标识','Weight identifier'),['02','03'])
horizon=st.selectbox(t('排序与仿真时间窗（月）','Ranking and simulation horizon (months)'),HORIZONS,index=2)
score=f'risk_{model}_{horizon}'
ranking=f.sort_values([score,'patient_key'],ascending=[False,True]).reset_index(drop=True)
if page in ['数据接入与预测','Data and prediction']:
    st.metric(t('获得预测的人数','Patients with predictions'),len(f))
    profile_patient=st.selectbox(t('查看五个时间窗的风险','View all five risk windows'),ranking.patient_key.tolist(),key='profile_patient')
    render_profile(st,ranking[ranking.patient_key==profile_patient].iloc[0],model,'zh' if zh else 'en')
    cap=st.select_slider(t('额外复查容量（队列百分比）','Additional review capacity (% of cohort)'),options=[5,10,20],value=10)
    ranking['priority_review_candidate']=selected(ranking,score,cap/100)
    st.dataframe(ranking[['patient_key','assessment_date','age','sex',score,'priority_review_candidate']],hide_index=True,use_container_width=True)
    st.caption(t('优先复查候选仅表示当前队列的容量排序，不是已验证的高低风险阈值或随访日程。','Priority candidates indicate cohort capacity ranking, not a validated risk threshold or follow-up schedule.'))
    st.download_button(t('下载医生工作清单','Download clinician worklist'),ranking.to_csv(index=False).encode('utf-8-sig'),'clinician_worklist.csv')
    with st.expander(t('排除原因与运行版本','Exclusions and run provenance')):st.dataframe(ex);st.json(manifest)
elif page in ['资源约束仿真','Capacity simulation']:
    st.subheader(t('同等名额下的事件捕获比较','Event capture at equal review capacity'))
    if synthetic:
        st.warning(t('结局由固定随机数独立生成，未根据模型分数生成。仅演示计算流程，差值和置信区间不能证明任何模型更优，也不是预防事件数。','Outcomes are generated from a fixed random seed independently of model scores. Differences and confidence intervals demonstrate the workflow only; they establish neither superiority nor events prevented.'))
        work=f.sort_values('patient_key').reset_index(drop=True).copy();rng=np.random.default_rng(76321)
        # A fixed, score-independent invented outcome process. No observed clinical outcomes.
        work['event_type']=rng.choice([0,1,2],size=len(work),p=[.68,.27,.05]);work['duration_days']=np.where(work.event_type==0,2000,rng.integers(1,1800,len(work)))
        st.caption(t('比较对象是两个身份待核实的权重；没有现行临床策略，不能声称优于现行策略。','These are two unverified weight identities; no current-care comparator is supplied.'))
    else:
        upload=st.file_uploader(t('同一评估时点的结局与比较分数CSV','Matched outcomes and comparator scores CSV'),type=['csv'])
        if not upload:st.stop()
        labels=pd.read_csv(upload)
        required=['patient_key','assessment_date','duration_days','event_type','comparator_score']
        if not set(required)<=set(labels) or labels.patient_key.duplicated().any():st.error('Required: unique patient_key, assessment_date, duration_days, event_type, comparator_score');st.stop()
        if set(labels.patient_key)!=set(f.patient_key):st.error('Patient sets must match exactly.');st.stop()
        work=f.merge(labels[required],on=['patient_key','assessment_date'],validate='one_to_one')
        if len(work)!=len(f):st.error('Assessment dates must match exactly.');st.stop()
    if st.button(t('计算5%、10%、20%容量','Evaluate 5%, 10%, 20% capacities')):
        try:
            scores=[score,f'risk_{"03" if model=="02" else "02"}_{horizon}'] if synthetic else [score,'comparator_score']
            result=evaluate(work,scores,horizon,bootstrap=200)
            labels={'table':t('事件捕获、PPV与漏识别','Capture, PPV and missed events'),'comparison':t('同容量差值（每千人）','Equal-capacity differences per 1,000'),'marginal':t('扩大容量的边际代价','Marginal cost of expanding capacity')}
            for key,label in labels.items():st.write(label);st.dataframe(result[key],hide_index=True,use_container_width=True);st.download_button(t('下载 ','Download ')+label,result[key].to_csv(index=False).encode('utf-8-sig'),key+'.csv')
            st.json(result['quality'])
        except Exception as e:st.error(str(e))
else:
    pid=st.selectbox(t('匿名病例','Pseudonymous case'),ranking.patient_key.tolist())
    row=ranking[ranking.patient_key==pid].iloc[0]
    import hashlib
    review_context=hashlib.sha256((pid+model+str(horizon)+row.assessment_date+repr([float(row[f'risk_{model}_{h}']) for h in HORIZONS])+json.dumps(manifest,sort_keys=True)).encode()).hexdigest()[:24]
    render_profile(st,row,model,'zh' if zh else 'en')
    st.write(t('系统建议：结合临床情况审核是否额外评估。模型不能确定治疗效果或自动决定随访间隔。','System prompt: review whether additional assessment is warranted in clinical context. The model cannot determine treatment effects or automatically decide a follow-up interval.'))
    reviewer=st.text_input(t('审核医生（演示请填虚构姓名）','Reviewing clinician (use an invented name in demo)'),key='reviewer_'+review_context)
    followup=st.date_input(t('医生确认随访日期','Clinician-confirmed follow-up date'),value=None,min_value=date.fromisoformat(row.assessment_date)+timedelta(days=1),key='followup_'+review_context)
    st.caption(t('日期需由医生选择；模型不自动推荐随访间隔。','The clinician must select a date; the model does not automatically recommend an interval.'))
    approved=st.checkbox(t('医生已审核风险及适用性，并独立确认随访日期','Clinician reviewed risk and applicability, and independently confirmed the follow-up date'),key='approved_'+review_context)
    if approved and reviewer.strip() and followup is not None:
        for language,label in [('zh','中文报告'),('en','English report')]:
            document=report(row,model,horizon,reviewer,followup.isoformat(),row.assessment_date,language,approved,synthetic)
            st.download_button(label,document.encode('utf-8'),'patient_report_'+language+'.html','text/html')
    else:st.info(t('审核完成前不生成可发给患者的报告。','No patient-facing report is generated before review.'))
