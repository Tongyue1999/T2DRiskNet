from pathlib import Path
import io, json, sys, hashlib
from datetime import date
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from engine import ROOT, HORIZONS, sample_path, infer, import_npz
from analysis import evaluate, selected
from i18n import LocalizedUI, translate
from product import render as render_product
from outcome_panel import render as render_outcomes

if 'ui_language' not in st.session_state:
    st.session_state['ui_language']='English' if st.query_params.get('lang')=='en' else '中文'

st.set_page_config(page_title='T2DRiskNet · Cardiovascular Review' if st.session_state.get('ui_language')=='English' else 'T2DRiskNet · 心血管风险工作台', page_icon='🫀', layout='wide')
language=st.sidebar.selectbox('Language / 语言',['中文','English'],key='ui_language')
lang='en' if language=='English' else 'zh'
st=LocalizedUI(st,lang)
st.markdown('''<style>
.stApp{background:#f5f7fb;color:#183247} .block-container{padding-top:2rem;max-width:1400px}
h1,h2,h3{color:#123c50!important} [data-testid="stMetric"]{background:white;padding:18px;border-radius:14px;border:1px solid #dce5ed}
[data-testid="stSidebar"]{background:#eaf0f6} .hero{background:#123c50;color:white;padding:25px 30px;border-radius:18px;margin-bottom:22px}.hero h1{color:white!important;font-size:30px}.hero p{margin-bottom:0;color:#c9e2e8}
</style>''', unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>T2DRiskNet 心血管风险工作台</h1><p>纵向临床记录 · 五个预测时间窗 · 有限复查名额下的优先排序</p></div>',unsafe_allow_html=True)
st.caption('本地研究原型｜两个权重的正式身份尚未确认｜仅预测首次复合 CVD，目前权重不提供独立 CHD、卒中或 HF 输出')
st.info('行动范围：额外评估、强化复诊或管理复核。未被优先选中者继续指南推荐的常规治疗。预测捕获不等于事件预防。')

with st.sidebar:
    st.title('工作台')
    page=st.radio('功能',['产品定位与使用流程','患者风险与复查排序','资源约束验证','数据接入与模型说明'],key='navigation')
    st.divider()
    st.markdown('**数据保留在本机**')
    st.caption('上传文件在当前会话中处理；原始上传不永久保存。内置结果仅来自用户提供的 200 人样例。')
    if st.button('清除当前会话结果'):
        for key in list(st.session_state):
            if key.startswith(('result_','evaluation_')):
                del st.session_state[key]
        st.rerun()

def load_result(mode):
    current=mode=='current'
    options=['上传患者 JSON']
    if (ROOT/'data'/f'sample_{mode}.csv').exists():options.insert(0,'已计算的 200 人样例')
    if next((ROOT/'vendor').rglob('ustc_200patients_demo.json'),None):options.append('重新运行内置 JSON 样例')
    if (ROOT/'data'/f'hospital_{mode}.csv').exists():
        options.insert(1,'省立医院关联样本（真实院内表）')
    if not current:
        options.append('导入外部验证 NPZ')
    source=st.selectbox('数据来源',options,key='source_'+mode)
    result_key='result_'+mode
    context_key='result_context_'+mode
    context=None
    if source in {'已计算的 200 人样例','省立医院关联样本（真实院内表）'}:
        hospital=source=='省立医院关联样本（真实院内表）'
        filename=ROOT/'data'/f'{"hospital" if hospital else "sample"}_{mode}.csv'
        if filename.exists():
            frame=pd.read_csv(filename)
            manifest=json.loads((ROOT/'data'/f'{"hospital" if hospital else "sample"}_{mode}_manifest.json').read_text(encoding='utf-8'))
            if current:
                keys=json.loads(((ROOT/'data/hospital_linked_200.json') if hospital else sample_path()).read_text(encoding='utf-8')).keys()
                st.session_state['result_mapping_current']=pd.DataFrame([{'patient_key':'P-'+hashlib.sha256(str(key).encode()).hexdigest()[:16],'local_patient_reference':str(key)} for key in keys])
            st.caption('接口验证样例；是否属于训练、调参或独立测试集尚未确认，不作为论文独立验证证据。')
            if hospital:
                st.caption('来自省立医院原始诊断、检验、ATC 药物表；200 人人口学资料按同一患者编号与已有 JSON 精确关联。不是新加入的 200 名独立验证患者。' if lang=='zh' else 'Rebuilt from actual Provincial Hospital diagnosis, lab and ATC medication tables. Demographics are linked to the supplied JSON by the same 200 identifiers; these are not 200 new independent validation patients.')
                report=json.loads((ROOT/'reports/hospital_linkage_report.json').read_text(encoding='utf-8'))
                st.caption(f'接入 {report["diagnosis_events"]:,} 条诊断、{report["lab_events"]:,} 条检验、{report["med_events"]:,} 条药物记录。未匹配训练词表的药物和检验已跳过；手术和自由文本未接入。' if lang=='zh' else f'Included {report["diagnosis_events"]:,} diagnosis, {report["lab_events"]:,} lab and {report["med_events"]:,} medication records. Unmatched lab/medication rows were skipped; procedures and free text are not included.')
                with st.expander('医院关联与映射质量' if lang=='zh' else 'Hospital linkage and mapping quality'):
                    st.json(report)
            return frame,manifest
        st.warning('预计算结果尚未生成，可选择运行内置样例。')
        return None,None
    if source=='导入外部验证 NPZ':
        upload=st.file_uploader('外部验证 result_01.npz 或 result_02.npz',type=['npz'],key='npz')
        col1,col2,col3=st.columns(3)
        fu=col1.selectbox('随访筛选组',[0,36])
        si=col2.number_input('随机种子索引（从 0 开始）',0,1000,0)
        ai=col3.selectbox('评估时点方案索引',[0,1],format_func=lambda x:['primary','sensitivity'][x])
        if upload:
            context=(source,hashlib.sha256(upload.getvalue()).hexdigest(),fu,si,ai)
        if upload and st.button('读取 NPZ'):
            try:
                f,_,m=import_npz(upload.getvalue(),fu,si,ai)
                st.session_state[result_key]=(f,m)
                st.session_state[context_key]=context
            except Exception as exc:
                st.error('NPZ 格式或索引不匹配：'+str(exc))
    else:
        upload=st.file_uploader('患者 JSON（标准事件序列格式）',type=['json'],key='json_'+mode) if source=='上传患者 JSON' else None
        fixed=None
        if current:
            method=st.radio('评估时点',['每名患者最后记录日','指定统一评估日期'],horizontal=True)
            if method=='指定统一评估日期':
                fixed=st.date_input('只使用该日期及之前的记录',date(2026,10,7)).isoformat()
        else:
            st.warning('该回顾性入口按原包 sensitivity、seed=42 选择事件前时点，使用结局信息选时点，仅用于复现和探索；不能视为前瞻性部署模拟。')
        content=upload.getvalue() if upload else (sample_path().read_bytes() if source=='重新运行内置 JSON 样例' else None)
        if content is not None:
            context=(source,hashlib.sha256(content).hexdigest(),fixed)
        if st.button('运行真实模型',type='primary',key='run_'+mode,disabled=source=='上传患者 JSON' and upload is None):
            try:
                content=upload.getvalue() if upload else sample_path().read_bytes()
                records=json.loads(content.decode('utf-8-sig'))
                bar=st.progress(0.,text='CPU 正在运行两个模型…')
                frame,excluded,manifest=infer(records,mode,fixed,lambda q:bar.progress(min(q,1.)))
                st.session_state[result_key]=(frame,manifest)
                st.session_state[context_key]=context
                st.session_state['result_exclusions_'+mode]=excluded
                if current:
                    st.session_state['result_mapping_current']=pd.DataFrame([{'patient_key':'P-'+hashlib.sha256(str(key).encode()).hexdigest()[:16],'local_patient_reference':str(key)} for key in records])
                bar.empty()
                st.success(f'完成：{len(frame)} 人获得预测，{manifest["excluded"]} 人未满足输入条件。')
            except Exception as exc:
                st.error('推理未完成：'+str(exc))
    if context is not None and st.session_state.get(context_key)==context and result_key in st.session_state:
        return st.session_state[result_key]
    return None,None

def csv_bytes(frame):
    return frame.to_csv(index=False).encode('utf-8-sig')

def translated(frame):
    names={'patient_key':'匿名患者','assessment_date':'评估日期','age':'年龄','sex':'性别','matched_events':'匹配事件数','raw_events':'原始事件数','mapped_fraction':'匹配比例','numeric_labs':'有效数值检验','history_days':'历史跨度（天）','last_record_gap_days':'资料距评估日（天）','strategy':'策略','capacity_pct':'容量（%）','selected_n':'实际复查人数','reviews_per1000':'复查人数／千人','captured_per1000':'捕获事件／千人','non_event_reviews_per1000':'未发生目标事件的复查／千人','capture_rate':'事件捕获率','ppv':'阳性预测值','miss_rate':'漏识别率','valid_probability_estimate':'概率估计有效','extra_captured_per1000':'额外捕获／千人','ci_low':'95% CI 下限','ci_high':'95% CI 上限','change_non_event_reviews_per1000':'未发生目标事件复查的变化／千人','capacity_change':'容量变化','extra_reviews_per1000':'新增复查／千人','reviews_per_extra_event':'每多捕获一例所需新增复查','added_patients':'新增入选人数','removed_patients':'移出人数','shared_patients':'共同入选人数','valid_bootstrap':'有效重采样次数','comparison':'比较'}
    return frame.rename(columns=names)

if page=='产品定位与使用流程':
    render_product(st,lang)
    for code,label in [('zh','产品定位说明 中文'),('en','Product brief English')]:
        path=ROOT/f'product_brief_{code}.html'
        if path.exists():st.download_button(label,path.read_bytes(),path.name,'text/html')

elif page=='患者风险与复查排序':
    st.subheader('从已有临床记录评估未来风险')
    frame,manifest=load_result('current')
    if frame is not None:
        c1,c2,c3=st.columns(3)
        model=c1.selectbox('查看模型',['02','03'],format_func=lambda x:'model_'+x)
        horizon=c2.selectbox('排序时间窗（月）',HORIZONS,index=2)
        capacity=c3.slider('额外复查容量（每 1,000 人）',10,300,100,10)
        score=f'risk_{model}_{horizon}'
        flag=selected(frame,score,capacity/1000)
        ranking=frame.assign(priority=flag).sort_values([score,'patient_key'],ascending=[False,True])
        a,b,c=st.columns(3)
        a.metric('可评估患者',len(frame))
        b.metric('本批额外复查名额',int(flag.sum()))
        c.metric('本批入选风险分界',f'{frame.loc[flag,score].min():.1%}')
        st.caption('风险分界随本批人群和容量变化。输出供医生复核，不自动触发转诊或治疗。')
        left,right=st.columns([1,2])
        with left:
            st.markdown('**个人风险查看**')
            person=st.selectbox('匿名患者',ranking.patient_key.tolist())
            row=frame.set_index('patient_key').loc[person]
            st.metric(f'未来 {horizon} 个月首次 CVD 风险',f'{row[score]:.1%}')
            st.write('评估日期：'+str(row.get('assessment_date','未提供')))
            st.write('排序建议：'+('优先安排额外评估' if bool(ranking.set_index('patient_key').loc[person,'priority']) else '继续常规管理，本批未优先入选'))
            if row.get('mapped_fraction',1)<.5:
                st.warning('不足一半事件匹配训练词表，需检查数据映射。')
            st.caption(f'匹配事件 {int(row.get("matched_events",0))} 条 · 有效数值检验 {int(row.get("numeric_labs",0))} 条')
        with right:
            chart=pd.DataFrame({'时间窗（月）':HORIZONS,'预测风险':[row[f'risk_{model}_{h}'] for h in HORIZONS]})
            st.altair_chart(alt.Chart(chart).mark_line(point=True,color='#087f8c').encode(x=alt.X('时间窗（月）:O',title=translate('时间窗（月）',lang)),y=alt.Y('预测风险:Q',title=translate('预测风险',lang),axis=alt.Axis(format='%'),scale=alt.Scale(domain=[0,1])),tooltip=[alt.Tooltip('时间窗（月）',title=translate('时间窗（月）',lang)),alt.Tooltip('预测风险:Q',format='.1%',title=translate('预测风险',lang))]).properties(height=280),use_container_width=True)
        st.markdown('**批量复查优先名单**')
        columns=['patient_key','assessment_date','age','sex',score,'priority','matched_events','mapped_fraction']
        display=ranking[[x for x in columns if x in ranking]].rename(columns={score:'预测风险','priority':'优先复查'})
        st.dataframe(translated(display),use_container_width=True,hide_index=True)
        st.download_button('导出排序与五个时间窗风险',csv_bytes(ranking),'risk_priority.csv','text/csv')
        local_map=st.session_state.get('result_mapping_current')
        if local_map is not None:
            local_map=local_map[local_map.patient_key.isin(frame.patient_key)]
            st.download_button('下载本机患者编号对应表',csv_bytes(local_map),'local_patient_reference.csv','text/csv')
            st.caption('对应表用于在本院定位患者，包含上传文件中的患者编号，应留在本院。预测结果默认使用匿名标识。')
        st.download_button('导出运行信息',json.dumps(manifest,ensure_ascii=False,indent=2),'run_manifest.json','application/json')
        excluded=st.session_state.get('result_exclusions_current')
        if excluded is not None and len(excluded):
            with st.expander('未满足输入条件的患者'):
                st.dataframe(excluded,use_container_width=True)

elif page=='资源约束验证':
    st.subheader('同样复查名额下，哪种排序捕获更多未来事件？')
    frame,manifest=load_result('retrospective')
    if frame is not None:
        st.warning('当前内置数据是 200 人样例，独立性及代表性未确认。结果只用于接口验证和探索，不能证明临床获益。')
        if not (frame.event_type==1).any():
            st.info('这份样例未记录目标 CVD 事件，能验证风险预测接口，但不能计算事件捕获获益。请接入有真实结局的验证队列或 NPZ。')
        c1,c2,c3=st.columns(3)
        model=c1.selectbox('待评估模型',['02','03'],format_func=lambda x:'model_'+x,key='evalmodel')
        horizon=c2.selectbox('结局时间窗（月）',HORIZONS,index=2,key='evalh')
        boot=c3.selectbox('配对 bootstrap 次数',[200,500,1000],index=0)
        comparator=st.selectbox('比较策略',['另一个已提供模型','上传现行策略分数'])
        work=frame.copy()
        score=f'risk_{model}_{horizon}'
        scores=[score]
        ready=True
        if comparator=='另一个已提供模型':
            scores.append(f'risk_{"03" if model=="02" else "02"}_{horizon}')
            st.caption('两个模型权重的身份待核实；这不是已确认的现行临床策略比较。')
        else:
            template=frame[['patient_key']].assign(current_score=np.nan)
            st.download_button('下载现行策略分数模板',csv_bytes(template),'current_strategy_template.csv')
            upload=st.file_uploader('同一评估时点的现行策略分数 CSV；分数越高越优先',type=['csv'])
            ready=False
            if upload:
                try:
                    comparison=pd.read_csv(upload)
                    if not {'patient_key','current_score'}.issubset(comparison.columns) or comparison.patient_key.duplicated().any():
                        raise ValueError('必须包含唯一 patient_key 和 current_score。')
                    if set(comparison.patient_key)!=set(frame.patient_key):
                        raise ValueError('患者集合必须完全匹配，不能静默删除患者。')
                    work=work.merge(comparison[['patient_key','current_score']],on='patient_key',validate='one_to_one')
                    scores.append('current_score')
                    ready=True
                except Exception as exc:
                    st.error(str(exc))
        config=(manifest.get('source_sha256'),horizon,tuple(scores),boot,manifest.get('seed'),manifest.get('analysis'),manifest.get('followup_months'),hash(work.to_csv(index=False)))
        if st.button('计算 5% / 10% / 20% 容量分析',type='primary',disabled=not ready):
            try:
                with st.spinner('估计删失校正指标和配对置信区间…'):
                    st.session_state['evaluation_result']=(config,evaluate(work,scores,horizon,bootstrap=boot))
            except Exception as exc:
                st.error(str(exc))
        cached=st.session_state.get('evaluation_result')
        if cached and cached[0]==config:
            result=cached[1]
            q=result['quality']
            a,b,c=st.columns(3)
            a.metric('分析患者',q['n'])
            b.metric('已观察目标事件',q['observed_target_events'])
            c.metric('时间窗前提前删失',q['censored_before_horizon'])
            st.caption('采用边际 IPCW 校正提前删失，竞争死亡不作为删失；依赖独立删失假设。不同时间窗不能累加；每月按原包 30 天计算。')
            if not result['table'].valid_probability_estimate.all():
                st.warning('部分 IPCW 估计超出概率范围，相关 PPV 和非事件数已留空；需更多随访或条件删失模型。')
            curve=result['curve']
            st.altair_chart(alt.Chart(curve).mark_line().encode(x=alt.X('reviews_per1000:Q',title=translate('额外复查名额／1,000 人',lang)),y=alt.Y('captured_per1000:Q',title=translate('捕获未来目标事件／1,000 人',lang)),color=alt.Color('strategy:N',title=translate('策略',lang)),tooltip=['strategy',alt.Tooltip('reviews_per1000',format='.1f'),alt.Tooltip('captured_per1000',format='.1f')]).properties(height=320),use_container_width=True)
            st.markdown('**固定容量下的策略表现**')
            st.dataframe(translated(result['table']).round(4),use_container_width=True,hide_index=True)
            st.markdown('**同等名额下的替换收益及 95% CI**')
            st.dataframe(translated(result['comparison']).round(3),use_container_width=True,hide_index=True)
            st.markdown('**扩大容量的边际收益**')
            st.dataframe(translated(result['marginal']).round(3),use_container_width=True,hide_index=True)
            st.caption('固定容量下新增复查总量为零；“每多捕获一例所需新增复查”只用于扩大容量比较。空白比值表示无正向增益或无法估计。')
            for label in ['table','comparison','marginal','curve']:
                st.download_button('导出 '+label,csv_bytes(result[label]),f'capacity_{label}.csv','text/csv',key='dl_'+label)
            st.download_button('导出分析方法与数据版本',json.dumps(dict(manifest=manifest,quality=q,bootstrap=boot,scores=scores),ensure_ascii=False,indent=2),'analysis_manifest.json')

else:
    render_outcomes(st,lang)
    st.subheader('现有数据和模型接入状态')
    st.markdown('**已接通：**标准患者 JSON、两个真实 TorchScript 权重、外部验证 NPZ、现行策略分数 CSV。原始文件与模型包保留不变。')
    st.markdown('**医院抽样表：**实际为 GB18030 CSV，文件名保留 `.rds`。当前表中没有出生日期和性别；院内人口学资料与药物、检验编码映射补齐后，可通过适配器转换为标准 JSON。')
    inventory_path=ROOT/'reports/data_inventory.json'
    inventory=json.loads(inventory_path.read_text(encoding='utf-8')) if inventory_path.exists() else []
    table=pd.DataFrame([{'文件':x['file'],'大小（MB）':round(x.get('file_bytes',0)/1e6,1),'预览行数':x.get('preview_rows',0),'字段':', '.join(x.get('columns',{}))} for x in inventory])
    st.dataframe(table,use_container_width=True,hide_index=True)
    audit_path=ROOT/'reports/hospital_audit.json'
    if audit_path.exists():
        audit=json.loads(audit_path.read_text(encoding='utf-8'))
        labels=['全表诊断记录','诊断表患者','记录 E11 的患者','记录 CVD 的患者'] if lang=='zh' else ['Diagnosis rows audited','Patients in diagnosis table','Patients with E11','Patients with recorded CVD']
        for col,label,key in zip(st.columns(4),labels,['diagnosis_rows','diagnosis_patients','patients_with_E11','patients_with_target_CVD_record']):col.metric(label,audit[key])
        st.caption('这些是已记录诊断，并非评估后首次事件；未补人口学资料的轨迹不能直接运行模型。' if lang=='zh' else 'These are recorded diagnoses, not incident events after assessment. Trajectories without demographics cannot be used for model inference.')
        st.download_button('下载医院全表核对报告' if lang=='zh' else 'Download hospital audit report',audit_path.read_bytes(),'hospital_audit.json','application/json')
        st.caption(f'200 人 JSON 与诊断表精确关联：{audit["json_sample_identifier_overlap"]} 人。已在风险页面提供关联后的真实医院子样本。' if lang=='zh' else f'Exact JSON-to-diagnosis identifier matches: {audit["json_sample_identifier_overlap"]}. The linked hospital subsample is available on the risk page.')
    st.download_button('下载人口学资料模板',(ROOT/'templates/demographics.csv').read_bytes(),'demographics.csv')
    st.download_button('下载编码映射模板',(ROOT/'templates/code_mapping.csv').read_bytes(),'code_mapping.csv')
    st.markdown('**医院表转换**')
    demographics=st.file_uploader('人口学资料 CSV（PERSON_ID_NEW、birthdate、gender）',type=['csv'],key='demo')
    mapping=st.file_uploader('药物、检验或手术映射 CSV（source、name、token）',type=['csv'],key='mapping')
    if st.button('转换本项目医院抽样表',disabled=demographics is None):
        try:
            from hospital_adapter import convert
            with st.spinner('分块读取本地抽样表，合并人口学信息…'):
                records,report=convert(pd.read_csv(demographics,dtype=str),pd.read_csv(mapping,dtype=str) if mapping else None)
            st.session_state['result_hospital_conversion']=(records,report)
        except Exception as exc:
            st.error(str(exc))
    if 'result_hospital_conversion' in st.session_state:
        records,report=st.session_state['result_hospital_conversion']
        st.json(report)
        st.download_button('下载转换后的本地患者 JSON',json.dumps(records,ensure_ascii=False).encode(),'hospital_patients.json','application/json')
        st.caption('中间 JSON 含本地患者编号，应留在本院；模型结果使用匿名标识。' if lang=='zh' else 'The intermediate JSON contains local patient identifiers; keep it in your institution. Prediction outputs use pseudonymous identifiers.')
    st.markdown('**输入格式**')
    st.code('''{
  "匿名患者编号": {
    "birthdate": "YYYY-MM-DD", "gender": "男或女",
    "end_of_data": "YYYY-MM-DD", "death_date": null,
    "events": [
      {"admdate": "YYYY-MM-DD", "codes": "E11"},
      {"admdate": "YYYY-MM-DD", "codes": "LAB_训练词表中的编码",
       "value": 6.8, "unit": "原始检验单位"}
    ]
  }
}''',language='json')
    st.caption('医生端不要求未来结局。回顾性验证需要真实随访终止日期与结局；缺失死亡日期不能自动解释为已确认存活。当前原型尚未核验正式部署资格、数据可得时点或本地校准。')
