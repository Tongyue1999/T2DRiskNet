"""Bilingual clinician/patient front door. Research tools remain a separate workspace."""
from pathlib import Path
from datetime import date,timedelta
import json,hashlib,html
import pandas as pd
import streamlit as st
from engine import infer,resources,HORIZONS
from risk_profile import profile_html
from clinical_io import report,synthetic_patients
from patient_examples import example_patient,example_zip,ASSESSMENT
from data_intake import ingest,read_tables,ALIASES,LABS

ROOT=Path(__file__).resolve().parent

@st.cache_data(show_spinner=False,max_entries=2)
def demo_prediction():
    return infer(example_patient(),'current',ASSESSMENT)

def load_demo(lang):
    try:return demo_prediction()
    except Exception:
        st.info('模型暂未就绪，请联系维护者检查授权模型配置。' if lang=='zh' else 'The model is unavailable. Ask the maintainer to check the authorised model configuration.')
        return None

def digest(records,assessment):
    return hashlib.sha256((json.dumps(records,sort_keys=True,ensure_ascii=False)+assessment).encode()).hexdigest()

def check_model_mapping(records):
    package,vendor,_,cfg,_=resources();unknown=set();bad_units=set()
    units=pd.read_csv(package/'config/lab_units.csv').set_index('code')['unit'].to_dict()
    normal=lambda x:str(x).strip().lower().replace('μ','u').replace('µ','u').replace(' ','')
    for rec in records.values():
        for event in rec['events']:
            token=str(event['codes'])
            if token.startswith(('LAB_','RX_','OP_')):
                if token not in cfg['code_to_index_map']:unknown.add(token)
            elif vendor.code(token,cfg) not in cfg['code_to_index_map']:unknown.add(token)
            if token.startswith('LAB_') and event.get('value') is not None:
                expected=next((v for k,v in units.items() if k.upper()==token[4:].upper()),None)
                if pd.isna(expected):bad_units.add(token+': training unit is unspecified; numeric mapping needs verification')
                elif normal(event.get('unit',''))!=normal(expected):bad_units.add(token+': '+str(event.get('unit'))+' → '+str(expected))
    if unknown:raise ValueError('这些代码尚未完成模型映射 / Unmapped model codes: '+', '.join(sorted(unknown)[:12]))
    if bad_units:raise ValueError('请按模型规范核对单位，当前不猜测换算 / Verify lab units: '+', '.join(sorted(bad_units)[:10]))

def latest_labs(rec,assessment):
    out={}
    for e in sorted(rec['events'],key=lambda x:x['admdate']):
        if e['admdate']<=assessment and (e['codes'].startswith('LAB_') or e['codes'] in {'SBP','DBP'}) and e.get('value') is not None and e.get('_numeric_usable',True):
            try:
                v=float(e['value'])
                if not __import__('math').isfinite(v):continue
            except (ValueError,TypeError):continue
            out[e['codes']]=dict(e,value=v)
    return out

def render_result(records,frame,manifest,assessment,lang,role,synthetic=False,sparse=False,review_override=None,model_override=None):
    zh=lang=='zh';t=lambda a,b:a if zh else b
    model=model_override or st.session_state.get('simple_weight','02')
    if len(frame)>1:
        st.success(t(f'完成：{len(frame)}位患者获得评估。',f'Completed: {len(frame)} patients assessed.'))
        with st.expander(t('查看批量结果与优先复核清单','Batch results and review priorities')):
            horizon=st.selectbox(t('排序时间范围','Ranking horizon'),HORIZONS,index=2,key='simple_batch_h')
            capacity=st.select_slider(t('本批额外复核名额占比','Additional review capacity'),[5,10,20],value=10,key='simple_capacity')
            from analysis import selected
            table=frame.copy();table['review_candidate']=selected(table,f'risk_{model}_{horizon}',capacity/100)
            table=table.sort_values([f'risk_{model}_{horizon}','patient_key'],ascending=[False,True])
            st.dataframe(table[['patient_key','assessment_date',f'risk_{model}_{horizon}','review_candidate']],hide_index=True,use_container_width=True)
            st.caption(t('入选表示本批名额排序，随访时间由医生确认。','Selection reflects cohort capacity; a clinician confirms follow-up timing.'))
            st.download_button(t('下载医生清单','Download clinician list'),table.to_csv(index=False).encode('utf-8-sig'),'clinician_list.csv','text/csv')
        person=st.selectbox(t('查看一位患者','View a patient'),frame.patient_key.tolist(),key='simple_result_patient')
        row=frame[frame.patient_key==person].iloc[0]
    else:row=frame.iloc[0]
    reverse={'P-'+hashlib.sha256(str(k).encode()).hexdigest()[:16]:k for k in records};rec=records[reverse[row.patient_key]]
    if sparse:st.info(t('关键资料试算：当前仍使用完整病历模型；少量指标输入的准确性尚未验证，建议正式评估时导入完整病历。','Key-data trial: this still uses the longitudinal model. Accuracy with a few inputs is unvalidated; import the full history for a formal research assessment.'))
    age=int((pd.Timestamp(assessment)-pd.Timestamp(rec['birthdate'])).days/365.25)
    st.markdown('### '+t('示例患者的风险概览' if synthetic else '患者风险概览','Example patient’s risk overview' if synthetic else 'Patient risk overview'))
    st.caption(t(f'{age}岁 · {"男性" if rec["gender"]=="男" else "女性"} · 评估日 {assessment}',f'Age {age} · {"Male" if rec["gender"]=="男" else "Female"} · Assessed {assessment}'))
    panel=profile_html(row,model,lang).replace('T2DRISKNET / MODEL '+model,t('风险时间线','Risk timeline'))
    panel=panel.replace(' 天 · 截至 ',' 天</small><small>截至 ').replace(' days · through ',' days</small><small>Through ')
    st.markdown(panel,unsafe_allow_html=True)
    st.caption(t('预测的是未来首次冠心病、心衰或脑血管事件的累积概率。继续医生建议的常规治疗。','Values estimate the cumulative probability of a first coronary, heart-failure or cerebrovascular event. Continue clinician-recommended routine care.'))
    st.markdown('### '+t('本次已有的临床指标','Clinical measurements available'))
    labs=latest_labs(rec,assessment);codes=['LAB_HBA1C','LAB_GLU','LAB_NTPROBNP','LAB_ALT'];cols=st.columns(4)
    for col,code in zip(cols,codes):
        label=LABS[code][0 if zh else 1];e=labs.get(code)
        col.metric(label,('—' if not e else f'{float(e["value"]):g}'),help=t('未提供的指标不按0处理。','Missing measurements are not replaced with zero.'))
        col.caption(t('未提供','Not provided') if not e else str(e.get('unit',''))+' · '+e['admdate'])
    st.caption(t('这里展示实际输入的指标，不表示它们就是本人的主要风险原因。','These are supplied measurements, not an explanation of this person’s main risk drivers.'))
    st.markdown('### '+t('下一次复查','Next review'))
    context=hashlib.sha256((digest(records,assessment)+str(row.patient_key)+model+json.dumps(manifest,sort_keys=True)).encode()).hexdigest()[:20]
    saved=review_override or st.session_state.get('simple_review_'+context)
    if saved:
        st.success(t('医生确认的复查日期：','Clinician-confirmed review: ')+saved['date'])
        st.caption(t('审核医生：','Reviewer: ')+saved['reviewer'])
    elif synthetic and assessment==ASSESSMENT and 'SYNTHETIC-EXAMPLE-001' in records:
        st.markdown('<div class="visit-card">'+t('示例复查安排：2026-10-31','Example review plan: 2026-10-31')+'</div>',unsafe_allow_html=True)
        st.caption(t('这是虚构医生预先设定的演示安排，不是模型根据风险自动推断的日期。','A fictional clinician preset this example plan; the model did not infer the date from risk.'))
    else:st.info(t('待医生结合病情确认复查日期。','The clinician will confirm a review date in clinical context.'))
    if role=='doctor':
        with st.expander(t('医生审核与导出报告','Clinician review and report')):
            reviewer=st.text_input(t('审核医生（演示请使用虚构姓名）','Reviewer (invented name in demo)'),key='simple_reviewer_'+context)
            followup=st.date_input(t('确认复查日期','Confirm review date'),value=None,min_value=date.fromisoformat(assessment)+timedelta(days=1),key='simple_followup_'+context)
            approved=st.checkbox(t('已核对资料、适用性和复查安排','I reviewed the data, applicability and review plan'),key='simple_approve_'+context)
            if st.button(t('确认并生成报告','Confirm and prepare report'),key='simple_review_button_'+context):
                if not reviewer.strip() or followup is None or not approved:st.warning(t('请填写审核人、日期并确认审核。','Provide the reviewer, date and approval.'))
                else:
                    review={'reviewer':reviewer.strip(),'date':followup.isoformat()}
                    st.session_state['simple_review_'+context]=review
                    st.session_state['simple_latest_approved']={'records':{reverse[row.patient_key]:rec},'frame':pd.DataFrame([row.to_dict()]),'manifest':manifest,'assessment':assessment,'synthetic':synthetic,'sparse':sparse,'review':review,'model':model}
                    st.rerun()
    if saved:
        for code,label in [('zh','中文报告'),('en','English report')]:
            text=report(row,model,12,saved['reviewer'],saved['date'],assessment,code,True,synthetic)
            measurements=[]
            for token in ['LAB_HBA1C','LAB_GLU','LAB_NTPROBNP','LAB_ALT']:
                e=labs.get(token)
                if e:
                    label=LABS[token][0 if code=='zh' else 1]
                    measurements.append('<tr><th>'+html.escape(label)+'</th><td>'+html.escape(str(e['value'])+' '+str(e.get('unit',''))+' · '+e['admdate'])+'</td></tr>')
            heading='本次提供的临床指标' if code=='zh' else 'Clinical measurements supplied'
            text=text.replace('</html>','<h2>'+heading+'</h2><table>'+''.join(measurements)+'</table></html>')
            if sparse:text=text.replace('<h1>','<p>简化输入研究试算，准确性未验证 / Sparse-input research trial; accuracy unvalidated.</p><h1>',1)
            st.download_button(label,text.encode('utf-8'),'patient_report_'+code+'.html','text/html')
    elif role=='patient':st.caption(t('正式患者报告由医生审核后提供。','Your clinician provides the report after review.'))
    with st.expander(t('了解研究参考信息','Understand the research reference')):
        reference=json.loads((ROOT/'feature_reference.json').read_text(encoding='utf-8'))
        st.write(t('研究中较突出的记录包括：','Records prominent in the supplied research include:'))
        items=reference['features'][:10]
        st.dataframe(pd.DataFrame([{t('记录或指标','Record or measurement'):x[lang],t('类别','Type'):{'diagnosis':t('诊断或症状','Diagnosis/symptom'),'medication':t('用药记录','Medication record'),'laboratory':t('检验','Laboratory')}[x['modality']]} for x in items]),hide_index=True,use_container_width=True)
        st.caption(t('这是60个月输出、发生事件的研究人群的总体归因参考；与当前权重的对应关系待确认。不是本人的风险贡献，不是必填清单，不说明某药对谁有效。图中的事件前区间不是未来预测窗口。','This is a cohort attribution reference for the 60-month output among research participants with events. Correspondence to current weights is unverified. It is not personal attribution, a mandatory input list, or evidence of drug effects. Pre-event intervals are not future prediction horizons.'))
        st.caption(t('图示排除 Z、C类、D0–D4类诊断；模型输入仍保留原记录。','The display excludes Z, C and D0–D4 diagnoses; original records remain in model inputs.'))
    with st.expander(t('查看使用了哪些资料','View the input record')):
        st.caption(t(f'使用 {int(row.matched_events)} 条匹配记录；有效数值检验 {int(row.numeric_labs)} 条。',f'{int(row.matched_events)} matched records; {int(row.numeric_labs)} numeric labs.'))
        st.dataframe(pd.DataFrame(rec['events']),hide_index=True,use_container_width=True);st.json(manifest)

def individual(lang,public_demo,role):
    zh=lang=='zh';t=lambda a,b:a if zh else b
    mode=st.radio(t('从哪里开始','Start here'),[t('先看一位示例患者','View an example patient'),t('精简模型研究进度','Reduced-input study')],horizontal=True,key='simple_case_mode')
    if mode in ['先看一位示例患者','View an example patient']:
        with st.spinner(t('正在读取示例评估…','Loading example assessment…')):result=load_demo(lang)
        if result is None:return
        frame,ex,manifest=result
        render_result(example_patient(),frame,manifest,ASSESSMENT,lang,role,True);return
    st.subheader(t('少填几个指标，能否保留预测能力？','Can fewer inputs preserve prediction performance?'))
    st.info(t('已完成一轮精简模型探索训练，尚未通过真实结局验证，因此暂不提供个人风险计算。','An exploratory reduced model has been trained. Patient-level risk calculation is unavailable pending real-outcome validation.'))
    path=ROOT/'reduced_status.json'
    if not path.exists():
        st.caption(t('研究结果尚待维护者核验。请使用完整病历评估入口。','Study results await verification. Use the full-record assessment route.'));return
    status=json.loads(path.read_text(encoding='utf-8'))
    st.write(t('目前仅能比较精简模型与完整模型输出是否接近，不能证明对真实事件的预测准确率相同。','Current comparisons measure agreement with the full model, not accuracy for actual clinical events.'))
    chosen=next(r for r in status['results_12m'] if r['extra_features']==status['selected_budget_by_training_cv'])
    a,b=st.columns(2)
    a.metric(t('12个月风险平均差','Mean 12-month risk difference'),str(chosen['mae_pp'])+t(' 个百分点',' pp'))
    b.metric(t('最高风险10%名单重合','Top-decile list overlap'),str(chosen['teacher_top10_overlap_pct'])+'%')
    st.caption(t(f"训练阶段选定：年龄、性别 + {status['selected_budget_by_training_cv']}项记录；{status['test_patients']}人留出比较。数值均为与完整模型的差异。",f"Training selected age/sex + {status['selected_budget_by_training_cv']} record features; {status['test_patients']} held-out patients. Values compare against the teacher model."))
    with st.expander(t('查看候选指标与比较详情','Candidate features and comparison details')):
        st.write(t('5项候选组合（另含年龄、性别）：','Five-feature candidate panel (+ age/sex):'))
        for f in status['candidate5']:st.write('• '+f['zh' if zh else 'en'])
        st.caption(t('这些是病历中的记录标志或检验值，并非推荐患者自填的最终组合。E11.9有无记录不等于是否患糖尿病；所有研究对象均须符合2型糖尿病纳入条件。','These are record indicators or laboratory values, not a final self-entry panel. E11.9 recording is not diabetes presence; all study patients meet type-2-diabetes eligibility.'))
        rows=[{t('额外特征数','Extra features'):r['extra_features'],t('12个月平均差（百分点）','12m mean difference (pp)'):r['mae_pp'],t('与完整模型最高风险10%重合','Teacher top-decile overlap'):str(r['teacher_top10_overlap_pct'])+'%'} for r in status['results_12m']]
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        st.caption(status['unit_note_zh' if zh else 'unit_note_en'])
    st.warning(t('当前可分析队列尚无已确认的首次目标心血管事件可供监督训练。需要补齐并审核事件与随访，才能判断精简后是否保持临床准确性。','The analysis cohort has no adjudicated incident target events available for supervised training. Event and follow-up adjudication are needed to assess clinical accuracy preservation.'))
    st.caption(t('请通过“导入一批患者”使用完整病历模型。精简模型未替换原模型，未接入患者报告或医院API。','Use Import a patient group for full-record inference. The student has not replaced the original model and is not used in patient reports or the hospital API.'))


def batch(lang,public_demo):
    zh=lang=='zh';t=lambda a,b:a if zh else b
    st.subheader(t('导入资料 → 核对匹配 → 生成评估','Import → check matches → assess'))
    st.caption(t('支持常见表格、标准JSON和多表ZIP。系统能识别常见字段；未知代码、单位及自由文本需要核对适配。','Common tables, patient JSON and multi-table ZIP are supported. Common fields are detected; unknown codes, units and free text require verified adaptation.'))
    st.download_button(t('下载虚构数据示例（两张表）','Download an invented two-table example'),example_zip(),'example_hospital_export.zip','application/zip')
    if public_demo:
        st.info(t('公开版可体验虚构数据转换。真实医院资料请在本地或院内版导入。','Try invented-data conversion here. Import actual hospital records in the local or institutional edition.'))
        files=[('example_hospital_export.zip',example_zip())]
    else:
        uploads=st.file_uploader(t('选择医院导出文件，可同时选择多张表','Choose hospital exports; multiple tables are supported'),type=['csv','tsv','xlsx','xlsm','json','zip','rds'],accept_multiple_files=True)
        files=[(u.name,u.getvalue()) for u in uploads] if uploads else []
    if not files:return
    mappings={};code_mapping={};gender_mapping={}
    try:
        tables,patients=read_tables(files)
        with st.expander(t('需要时调整字段匹配','Adjust field matches if needed')):
            coding=st.selectbox(t('性别编码约定','Sex coding convention'),['男/女 · Male/Female','1=男/Male, 2=女/Female','1=男/Male, 0=女/Female','0=男/Male, 1=女/Female'])
            if coding.startswith('1=男/Male, 2'):gender_mapping={'1':'男','2':'女'}
            elif coding.startswith('1=男/Male, 0'):gender_mapping={'1':'男','0':'女'}
            elif coding.startswith('0=男'):gender_mapping={'0':'男','1':'女'}
            for name,df in tables:
                st.write(name)
                edits={}
                for target,label in [('patient_id',t('患者编号','Patient ID')),('birthdate',t('出生日期','Date of birth')),('gender',t('性别','Sex')),('admdate',t('记录日期','Record date')),('codes',t('事件代码','Event code')),('value',t('检验值','Lab value')),('unit',t('单位','Unit'))]:
                    choice=st.selectbox(label,['自动识别 / Auto']+df.columns.tolist(),key='mapping_'+name+'_'+target)
                    if choice!='自动识别 / Auto':edits[target]=choice
                mappings[name]=edits
            cm=st.file_uploader(t('可选：已核对的代码对应表（source_code,target_code）','Optional verified code map (source_code,target_code)'),type=['csv'],key='simple_code_map') if not public_demo else None
            if cm:
                df=pd.read_csv(cm,dtype=str)
                if not {'source_code','target_code'}<=set(df) or df.source_code.duplicated().any():raise ValueError('Code map requires unique source_code and target_code.')
                code_mapping=dict(zip(df.source_code,df.target_code))
        records,audit=ingest(files,mappings,code_mapping,gender_mapping)
        a,b=st.columns(2);a.metric(t('识别到的患者','Patients detected'),audit['patients']);b.metric(t('带日期的记录','Dated records'),audit['events'])
        st.success(t('格式转换完成，请核对后计算。','Format conversion completed. Check before calculating.'))
        with st.expander(t('查看匹配结果和未使用字段','View matches and unused columns')):st.json(audit)
        assessment=st.date_input(t('这批患者的评估日期','Assessment date for this batch'),value=date.fromisoformat(ASSESSMENT) if public_demo else date.today(),key='simple_batch_assess').isoformat()
        ctx=digest(records,assessment)+json.dumps(mappings,sort_keys=True)+json.dumps(code_mapping,sort_keys=True)+json.dumps(gender_mapping,sort_keys=True)
        confirmed=st.checkbox(t('已确认字段、患者关联、编码及检验单位；宽表遵循示例单位','Confirm fields, patient linkage, codes and units; wide tables use the example units'),key='simple_mapping_confirm_'+hashlib.sha256(ctx.encode()).hexdigest()[:20])
        if st.button(t('核对并开始评估','Start assessment'),disabled=not confirmed,type='primary'):
            check_model_mapping(records)
            with st.spinner(t('正在评估…','Assessing…')):f,ex,m=infer(records,'current',assessment)
            st.session_state['simple_batch_result']=(ctx,records,f,ex,m,assessment)
        saved=st.session_state.get('simple_batch_result')
        if saved and saved[0]==ctx:
            _,records,f,ex,m,assessment=saved;render_result(records,f,m,assessment,lang,'doctor',public_demo)
            if len(ex):
                with st.expander(t('需要补资料或核实的患者','Patients needing data or eligibility review')):st.dataframe(ex,hide_index=True)
    except Exception as exc:st.error(t('还需要补充或核对：','Please complete or check: ')+str(exc))

def main(public_demo=False):
    from product_ui import main as product_main
    product_main(public_demo)
