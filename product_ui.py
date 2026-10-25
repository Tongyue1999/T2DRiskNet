"""Interactive bilingual product: import or key records, then actual model inference."""
from pathlib import Path
from datetime import date,timedelta
import copy,hashlib,html,json
import pandas as pd
import streamlit as st
from engine import infer,HORIZONS
from data_intake import ingest,read_tables,LABS as INTAKE_LABS
from patient_examples import example_patient,example_zip,ASSESSMENT
from clinical_io import report
from product_visuals import CSS,portrait_html,risk_cards

ROOT=Path(__file__).resolve().parent
LABS={**INTAKE_LABS,'SBP':('收缩压','Systolic BP','mmHg',[]),'DBP':('舒张压','Diastolic BP','mmHg',[])}
SYMPTOMS={'I10':('高血压记录','Hypertension record'),'R07':('胸痛记录','Chest pain record'),'R09':('呼吸 / 循环系统症状记录','Respiratory / circulatory symptom record'),'R42':('头晕记录','Dizziness record'),'R00':('心跳异常记录','Abnormal heartbeat record')}
MEDS={'RX_B01AC04':('氯吡格雷','Clopidogrel'),'RX_C01DA02':('硝酸甘油','Glyceryl trinitrate'),'RX_B01AC06':('阿司匹林','Aspirin'),'RX_C10AA05':('阿托伐他汀','Atorvastatin')}
FIELDS=['LAB_NTPROBNP','LAB_ALT','LAB_CTNT']

def saved_assessment(records,f,ex,m,assessment,synthetic,mode):
    active={'records':records,'frame':f,'excluded':ex,'manifest':m,'assessment':assessment,'synthetic':synthetic,'mode':mode}
    if m.get('model_family')=='reduced':active.update(model=m['model'],mode='reduced')
    return active

def use_example():
    records,f,ex,m=product_example()
    st.session_state['product_empty']=False
    st.session_state['product_result']=saved_assessment(records,f,ex,m,ASSESSMENT,True,'key')

@st.cache_data(show_spinner=False,max_entries=1)
def product_example():
    from simple_predictor import assess
    day=(date.fromisoformat(ASSESSMENT)-timedelta(days=7)).isoformat()
    return assess({'age':62,'male':1,'I10':1,'LAB_HBA1C':7.8,'LAB_CR':85.},ASSESSMENT,{'LAB_HBA1C':day,'LAB_CR':day},synthetic=True)

def build_key_record(dob,gender,diabetes,assessment,prior,diagnoses,history_date,medications,med_date,labs,lab_date,synthetic):
    """Only explicit dated records, no silent clinical negatives or synthetic old labs."""
    if not dob or not diabetes or gender not in ['男','女'] or prior!='no':
        raise ValueError('请补齐人口资料及糖尿病日期，并确认无既往目标心血管病。 / Complete patient details and confirm no prior target CVD.')
    if not dob<=diabetes<=assessment or dob>=assessment:raise ValueError('请检查日期先后。 / Check date order.')
    events=[{'admdate':diabetes.isoformat(),'codes':'E11.9'}]
    for codes,day in [(diagnoses,history_date),(medications,med_date)]:
        if codes and (day is None or not dob<=day<=assessment):raise ValueError('请补充有效病史或用药日期。 / Provide a valid history or medication date.')
        for c in codes:events.append({'admdate':day.isoformat(),'codes':c})
    for c,v in labs.items():
        if v is None:continue
        if lab_date is None or not dob<=lab_date<=assessment:raise ValueError('请补充有效检验日期。 / Provide a valid lab date.')
        events.append({'admdate':lab_date.isoformat(),'codes':c,'value':float(v),'unit':LABS[c][2]})
    return {'SYNTHETIC-KEY-CASE' if synthetic else 'LOCAL-KEY-CASE':{'birthdate':dob.isoformat(),'gender':gender,'events':events}}

def key_input(lang,public_demo):
    zh=lang=='zh';t=lambda a,b:a if zh else b
    note=t('研究试用','Research trial')
    scope=t('适用于确诊2型糖尿病≥90天且无既往冠心病、心衰或脑血管病的成人。','For adults with type 2 diabetes for at least 90 days and no prior coronary, heart-failure or cerebrovascular disease.')
    st.markdown('<div class="entry-label">02 / '+t('简单预测','SIMPLE PREDICTION')+'</div><div class="input-title">'+t('填写5项指标','Enter 5 key inputs')+'</div><div class="mini-note" title="'+html.escape(scope,quote=True)+'">'+note+'</div>',unsafe_allow_html=True)
    example=st.session_state.get('product_editor_example',True)
    a,b=st.columns(2)
    if a.button(t('载入示例','Load example'),use_container_width=True):
        st.session_state['product_editor_example']=True;st.session_state['product_form_version']=st.session_state.get('product_form_version',0)+1;use_example();st.rerun()
    if b.button(t('新建患者' if not public_demo else '新建模拟病例','New patient' if not public_demo else 'New invented case'),use_container_width=True):
        st.session_state['product_editor_example']=False;st.session_state['product_empty']=True;st.session_state['product_form_version']=st.session_state.get('product_form_version',0)+1
        for k in ['product_result','product_approved']:st.session_state.pop(k,None)
        st.rerun()
    suffix=str(st.session_state.get('product_form_version',0))
    with st.form('simple_prediction_'+suffix):
        a,b=st.columns(2)
        age=a.number_input(t('年龄（岁）','Age (years)'),min_value=18,max_value=119,value=62 if example else None,step=1)
        gender=b.selectbox(t('性别','Sex'),[t('请选择','Choose'),t('男','Male'),t('女','Female')],index=1 if example else 0)
        ht=st.selectbox(t('既往高血压记录','Recorded hypertension'),[t('不清楚','Uncertain'),t('有明确记录','Documented'),t('无明确记录','Not documented')],index=1 if example else 0)
        assessment=st.date_input(t('评估日期','Assessment date'),date.fromisoformat(ASSESSMENT) if example else date.today())
        values={'age':age,'male':1 if gender==t('男','Male') else 0 if gender==t('女','Female') else None,'I10':1 if ht==t('有明确记录','Documented') else 0 if ht==t('无明确记录','Not documented') else None}
        dates={};default_day=assessment-timedelta(days=7)
        for code,zhlabel,enlabel,unit,value in [('LAB_HBA1C','糖化血红蛋白 HbA1c','HbA1c','%',7.8),('LAB_CR','血清肌酐','Serum creatinine','μmol/L',85.)]:
            a,b=st.columns([1.1,1])
            values[code]=a.number_input(t(zhlabel,enlabel)+' ('+unit+')',min_value=0.,value=value if example else None,step=.1)
            dates[code]=b.date_input(t(zhlabel+'检测日期',enlabel+' date'),default_day if example else None,max_value=assessment)
        with st.expander(t('补充指标（可选）','Additional inputs (optional)'),expanded=False):
            extended=st.checkbox(t('加入补充指标','Use additional inputs'),value=False)
            for code,zhlabel,enlabel,unit in [('SBP','收缩压','Systolic BP','mmHg'),('DBP','舒张压','Diastolic BP','mmHg'),('LAB_LDL','LDL胆固醇','LDL cholesterol','mmol/L'),('LAB_GLU','血糖','Glucose','mmol/L')]:
                a,b=st.columns([1.1,1]);values[code]=a.number_input(t(zhlabel,enlabel)+' ('+unit+')',min_value=0.,value=None,step=.1)
                dates[code]=b.date_input(t(zhlabel+'检测日期',enlabel+' date'),value=None,max_value=assessment)
            aspirin=st.selectbox(t('近一年阿司匹林使用记录','Recorded aspirin use in the past year'),[t('不清楚','Uncertain'),t('有明确记录','Documented'),t('无明确记录','Not documented')])
            values['RX_B01AC06']=1 if aspirin==t('有明确记录','Documented') else 0 if aspirin==t('无明确记录','Not documented') else None
        submit=st.form_submit_button(t('生成风险画像 →','Generate risk profile →'),type='primary',use_container_width=True)
    if submit:
        try:
            from simple_predictor import assess
            dates={c:day.isoformat() if day else None for c,day in dates.items()}
            records,f,ex,m=assess(values,assessment.isoformat(),dates,extended,public_demo or example)
            st.session_state['product_empty']=False;st.session_state.pop('product_approved',None)
            st.session_state['product_result']=saved_assessment(records,f,ex,m,assessment.isoformat(),public_demo or example,'reduced')
        except Exception as e:
            st.session_state.pop('product_result',None);st.session_state.pop('product_approved',None);st.session_state['product_empty']=True;st.error(str(e))

def hospital_input(lang,public_demo):
    zh=lang=='zh';t=lambda a,b:a if zh else b
    st.markdown('<div class="entry-label">01 / '+t('医院数据','HOSPITAL DATA')+'</div><div class="input-title">'+t('上传并自动匹配','Import and match')+'</div><div class="mini-note">CSV · Excel · JSON · ZIP</div>',unsafe_allow_html=True)
    files=[]
    if public_demo:
        st.file_uploader(t('真实医院资料请在院内版上传','Import actual hospital records in the local edition'),disabled=True,key='product_public_disabled')
        if st.button(t('使用示例医院文件','Use example hospital files'),use_container_width=True):st.session_state['product_example_import']=True
        if st.session_state.get('product_example_import'):files=[('example_hospital.zip',example_zip())]
    else:
        uploads=st.file_uploader(t('拖入文件，可同时选择多张表','Drop files; multiple tables supported'),type=['csv','tsv','xlsx','xlsm','json','zip','rds'],accept_multiple_files=True,key='product_hospital_files')
        if uploads:
            files=[(f.name,f.getvalue()) for f in uploads];st.session_state['product_example_import']=False
        elif st.button(t('使用示例医院文件','Use example hospital files'),use_container_width=True):st.session_state['product_example_import']=True
        if not uploads and st.session_state.get('product_example_import'):files=[('example_hospital.zip',example_zip())]
    st.download_button(t('下载数据示例','Download example'),example_zip(),'example_hospital.zip','application/zip',use_container_width=True)
    if not files:
        if st.session_state.pop('product_upload_token',None):
            for key in ['product_result','product_approved','product_hospital_cache']:st.session_state.pop(key,None)
            st.session_state['product_empty']=True
        st.caption(t('字段、日期与患者关联自动匹配。','Automatically matches fields, dates and patient linkage.'))
        with st.expander(t('医院系统接入','Connect an EHR')):
            st.write(t('尚未连接医院。院内接口已提供：','No hospital connected. Local development endpoints:'))
            st.code('POST /v1/convert\nPOST /v1/predict',language='text')
        return
    # Cache real-data conversion only in this local session, never globally.
    upload_token=hashlib.sha256(b''.join(name.encode()+hashlib.sha256(raw).digest() for name,raw in files)).hexdigest()
    if st.session_state.get('product_upload_token')!=upload_token:
        st.session_state['product_upload_token']=upload_token
        for key in ['product_result','product_approved','product_hospital_cache']:st.session_state.pop(key,None)
        st.session_state['product_empty']=True
    try:
        from hospital_upload import is_hospital_profile,convert_hospital_tables
        cached=st.session_state.get('product_hospital_cache')
        if cached and cached['token']==upload_token:
            return hospital_profile_input(cached,lang)
        tables,patients=read_tables(files)
        if not public_demo and is_hospital_profile(tables):
            with st.spinner(t('正在关联医院原始表并核对检验单位…','Linking hospital tables and checking units…')):
                records,dates,audit=convert_hospital_tables(tables)
            cached={'token':upload_token,'records':records,'dates':dates,'audit':audit}
            st.session_state['product_hospital_cache']=cached
            return hospital_profile_input(cached,lang)
    except Exception as e:
        st.error(t('需要核对：','Check required: ')+str(e));return
    mappings={};code_mapping={};gender_mapping={}
    try:
        with st.expander(t('调整字段匹配（需要时）','Adjust field mapping (if needed)')):
            coding=st.selectbox(t('数字性别编码','Numeric sex convention'),['男/女 · Male/Female','1=男/Male, 2=女/Female','1=男/Male, 0=女/Female','0=男/Male, 1=女/Female'])
            if coding.startswith('1=男/Male, 2'):gender_mapping={'1':'男','2':'女'}
            elif coding.startswith('1=男/Male, 0'):gender_mapping={'1':'男','0':'女'}
            elif coding.startswith('0=男'):gender_mapping={'0':'男','1':'女'}
            for name,df in tables:
                st.caption(name);edits={}
                for target,label in [('patient_id',t('患者编号','Patient ID')),('birthdate',t('出生日期','Date of birth')),('gender',t('性别','Sex')),('admdate',t('记录日期','Record date')),('codes',t('事件代码','Event code')),('value',t('检验值','Value')),('unit',t('单位','Unit'))]:
                    val=st.selectbox(label,['自动 / Auto']+df.columns.tolist(),key='product_map_'+name+'_'+target)
                    if val!='自动 / Auto':edits[target]=val
                mappings[name]=edits
            cm=st.file_uploader(t('代码映射表（可选）','Code map (optional)'),type=['csv'],key='product_map_upload') if not public_demo else None
            if cm:
                d=pd.read_csv(cm,dtype=str)
                if not {'source_code','target_code'}<=set(d) or d.source_code.duplicated().any():raise ValueError('source_code / target_code required; source_code must be unique.')
                code_mapping=dict(zip(d.source_code,d.target_code))
        from data_intake import convert_tables
        records,audit=convert_tables(tables,patients,mappings,code_mapping,gender_mapping)
        st.success(t(f"已识别 {audit['patients']} 位患者 · {audit['events']} 条记录",f"{audit['patients']} patients · {audit['events']} dated records"))
        assessment=st.date_input(t('评估日期','Assessment date'),date.fromisoformat(ASSESSMENT) if public_demo or files[0][0]=='example_hospital.zip' else date.today(),key='product_upload_assess').isoformat()
        ctx=hashlib.sha256((json.dumps(records,sort_keys=True)+assessment+json.dumps(code_mapping,sort_keys=True)).encode()).hexdigest()
        with st.expander(t('查看自动匹配结果','View automatic matches')):st.json(audit)
        confirmed=st.checkbox(t('字段、编码及检验单位已核对','Fields, codes and units checked'),key='product_confirm_'+ctx)
        if st.button(t('生成风险画像 →','Generate risk profile →'),type='primary',disabled=not confirmed,use_container_width=True):
            from simple_ui import check_model_mapping
            check_model_mapping(records)
            with st.spinner(t('正在评估…','Assessing…')):f,ex,m=infer(records,'current',assessment)
            st.session_state['product_result']=saved_assessment(records,f,ex,m,assessment,public_demo or files[0][0]=='example_hospital.zip','history')
    except Exception as e:st.error(t('需要核对：','Check required: ')+str(e))

def hospital_profile_input(cached,lang):
    zh=lang=='zh';t=lambda a,b:a if zh else b
    audit=cached['audit'];token=cached['token']
    st.success(t(f"识别 {audit['source_patients']} 位真实来源患者 · {audit['events']:,} 条匹配记录",f"{audit['source_patients']} source patients · {audit['events']:,} mapped records"))
    st.caption(t('历史资料回放：使用文件中每位患者各自的评估日期。','Historical replay using each patient’s supplied assessment date.'))
    count=audit['numeric_preprocessing'].get('unverified_unit_numeric_values_not_used',0)
    st.caption(t(f"{len(audit['held_patients'])} 位既往病史待核对者另列；{count:,} 条单位未核定的数值不进入数值计算。",f"{len(audit['held_patients'])} patients held for history review; {count:,} unit-unverified values excluded from numeric encoding."))
    with st.expander(t('查看自动匹配结果','View automatic matches')):
        st.json({k:v for k,v in audit.items() if k not in ['held_patients','numeric_issues','unmapped_code_counts']})
        st.download_button(t('下载转换审计','Download conversion audit'),json.dumps(audit,ensure_ascii=False,indent=2).encode('utf-8'),'local_conversion_audit.json','application/json')
    confirmed=st.checkbox(t('确认按上述历史日期回放，保留缺失并另列未匹配记录','Confirm historical replay, missing-value handling and unmapped-record audit'),key='product_hospital_confirm_'+token)
    if st.button(t('生成风险画像 →','Generate risk profile →'),type='primary',disabled=not confirmed,use_container_width=True):
        from hospital_upload import run_hospital_upload
        bar=st.progress(0);last=[-1.]
        def update(q):
            if q>=1 or q-last[0]>=.03:last[0]=q;bar.progress(min(1.,q))
        with st.spinner(t('正在计算真实资料的五个时间窗…','Calculating five risk windows from hospital records…')):
            f,ex,m=run_hospital_upload(cached['records'],cached['dates'],audit,update)
        bar.empty()
        st.session_state['product_result']=saved_assessment(cached['records'],f,ex,m,'per_patient',False,'history')
    saved=st.session_state.get('product_result')
    if saved and saved['manifest'].get('upload_profile'):
        st.caption(t(f"完成 {len(saved['frame'])} 位；另列 {len(saved['excluded'])} 位不可纳入者。",f"Completed {len(saved['frame'])}; {len(saved['excluded'])} excluded/held."))
        st.download_button(t('下载完整预测结果（两个权重 × 五窗口）','Download predictions (two weights × five windows)'),saved['frame'].to_csv(index=False).encode('utf-8-sig'),'hospital_predictions.csv','text/csv')
        with st.expander(t('未纳入者及原因','Excluded/held patients and reasons')):st.dataframe(saved['excluded'],hide_index=True,use_container_width=True)

def review_and_reports(active,row,rec,lang,role,model):
    zh=lang=='zh';t=lambda a,b:a if zh else b
    from simple_ui import digest,latest_labs
    assessment=str(row.assessment_date);ctx=hashlib.sha256((digest({row.patient_key:rec},assessment)+str(row.patient_key)+model+json.dumps(active['manifest'],sort_keys=True)).encode()).hexdigest()[:20]
    saved=active.get('review') or st.session_state.get('product_review_'+ctx)
    if saved:value=saved['date'];desc=t('医生确认复查','Clinician-confirmed review')
    elif active['synthetic'] and 'SYNTHETIC-EXAMPLE-001' in active['records'] and assessment==ASSESSMENT:value='2026-10-31';desc=t('示例复查（虚构安排）','Example review (fictional plan)')
    else:value=t('待医生确认','Awaiting clinical review');desc=t('下一次复查','Next review')
    st.markdown('<div class="review-strip"><div><small>'+desc+'</small><b>'+value+'</b></div><span style="color:#8cafb3">◷</span></div>',unsafe_allow_html=True)
    if role=='doctor':
        with st.expander(t('安排复查 · 导出报告','Schedule review · Export report')):
            a,b=st.columns(2);name=a.text_input(t('审核医生','Reviewer'),key='product_reviewer_'+ctx)
            day=b.date_input(t('复查日期','Review date'),value=None,min_value=date.fromisoformat(assessment)+timedelta(days=1),key='product_followup_'+ctx)
            approved=st.checkbox(t('已审核资料及复查安排','Data and review plan approved'),key='product_approval_'+ctx)
            if st.button(t('确认并生成报告','Confirm and prepare report'),key='product_approve_'+ctx):
                if not name.strip() or not day or not approved:st.warning(t('请补全审核人、日期并确认。','Complete reviewer, date and approval.'))
                else:
                    saved={'reviewer':name.strip(),'date':day.isoformat()};st.session_state['product_review_'+ctx]=saved
                    key=next(k for k in active['records'] if 'P-'+hashlib.sha256(str(k).encode()).hexdigest()[:16]==row.patient_key)
                    st.session_state['product_approved']={**active,'records':{key:rec},'frame':pd.DataFrame([row.to_dict()]),'excluded':pd.DataFrame(),'review':saved,'model':model};st.rerun()
    if not saved and not active['synthetic'] and role=='doctor':
        from draft_reports import patient_draft
        labs=latest_labs(rec,assessment)
        a,b=st.columns(2)
        for col,code in [(a,'zh'),(b,'en')]:
            measurements=[(LABS[c][0 if code=='zh' else 1],str(e['value'])+' '+str(e.get('unit',''))+' · '+e['admdate']) for c,e in labs.items() if c in LABS]
            doc=patient_draft(row,model,code,measurements)
            col.download_button('下载中文草稿' if code=='zh' else 'Download English draft',doc.encode('utf-8'),'hospital_draft_'+code+'.html','text/html',use_container_width=True)
    if saved:
        a,b=st.columns(2)
        labs=latest_labs(rec,assessment)
        for col,code in [(a,'zh'),(b,'en')]:
            doc=report(row,model,12,saved['reviewer'],saved['date'],assessment,code,True,active['synthetic'])
            labrows=''.join('<tr><td>'+html.escape(LABS[c][0 if code=='zh' else 1])+'</td><td>'+html.escape(str(e['value'])+' '+str(e.get('unit',''))+' · '+e['admdate'])+'</td></tr>' for c,e in labs.items() if c in LABS)
            doc=doc.replace('</html>','<h2>'+('输入检验结果' if code=='zh' else 'Supplied measurements')+'</h2><table>'+labrows+'</table></html>')
            if active['mode']=='key':doc=doc.replace('<h1>','<p>关键资料研究试算，准确性未独立验证 / Key-data trial; accuracy not independently validated.</p><h1>',1)
            col.download_button('下载中文报告' if code=='zh' else 'Download English report',doc.encode('utf-8'),'patient_report_'+code+'.html','text/html',use_container_width=True)

def render_assessment(active,lang,role):
    zh=lang=='zh';t=lambda a,b:a if zh else b
    frame=active['frame'];model=active.get('model') or st.session_state.get('simple_weight','02')
    if len(frame)>1:
        person=st.selectbox(t('选择患者','Select patient'),frame.patient_key.tolist(),key='product_selected_patient')
        row=frame[frame.patient_key==person].iloc[0].copy()
    else:row=frame.iloc[0].copy()
    row['input_mode']=active['mode'];reverse={'P-'+hashlib.sha256(str(k).encode()).hexdigest()[:16]:k for k in active['records']};rec=active['records'][reverse[row.patient_key]]
    st.markdown('<div class="entry-label">'+t('评估结果','ASSESSMENT')+'</div><div class="input-title">'+t('患者数字画像','Patient digital profile')+'</div>',unsafe_allow_html=True)
    st.caption(t('示例病例 · ' if active['synthetic'] else '本次评估 · ','Invented case · ' if active['synthetic'] else 'Current assessment · ')+str(row.assessment_date)+(' · '+t('关键资料试算','Key-data trial') if active['mode']=='key' else ''))
    selected=st.select_slider(t('探索未来风险','Explore future risk'),options=HORIZONS,value=12,format_func=lambda h:str(h)+t('个月',' months'),key='product_horizon')
    st.markdown(risk_cards(row,model,lang,selected),unsafe_allow_html=True)
    st.markdown(portrait_html(rec,row,model,selected,lang,active['synthetic']),unsafe_allow_html=True)
    from simple_ui import latest_labs
    labs=latest_labs(rec,str(row.assessment_date));tokens=[c for c in ['LAB_HBA1C','LAB_CR','SBP','DBP','LAB_LDL','LAB_GLU','LAB_NTPROBNP','LAB_ALT','LAB_CTNT'] if c in labs][:6]
    st.markdown('<div class="section-line">'+t('本次输入的指标','Measurements supplied')+'<small>'+t('不是个体风险归因','Not personal risk attribution')+'</small></div>',unsafe_allow_html=True)
    if tokens:
        for col,c in zip(st.columns(len(tokens)),tokens):
            e=labs[c];col.metric(LABS[c][0 if zh else 1],f"{float(e['value']):g}");col.caption(str(e.get('unit',''))+' · '+e['admdate'])
    else:st.caption(t('尚未提供数值检验','No numeric measurements supplied'))
    review_and_reports(active,row,rec,lang,role,model)
    if len(frame)>1:
        with st.expander(t('医生优先复核清单','Clinician review priorities')):
            from analysis import selected as choose
            cap=st.select_slider(t('额外复核名额','Additional review capacity'),[5,10,20],value=10)
            table=frame.copy();table['review_candidate']=choose(table,f'risk_{model}_{selected}',cap/100);table=table.sort_values([f'risk_{model}_{selected}','patient_key'],ascending=[False,True])
            st.dataframe(table[['patient_key',f'risk_{model}_{selected}','review_candidate']],hide_index=True,use_container_width=True)
            st.download_button(t('下载医生清单','Download clinician list'),table.to_csv(index=False).encode('utf-8-sig'),'clinician_list.csv','text/csv')

def main(public_demo=False):
    st.set_page_config(page_title='T2DRiskNet · Care Studio',page_icon='🫀',layout='wide',initial_sidebar_state='collapsed')
    language=st.sidebar.selectbox('语言 / Language',['中文','English'],index=1 if st.query_params.get('lang')=='en' else 0,key='simple_language')
    lang='zh' if language=='中文' else 'en';zh=lang=='zh';t=lambda a,b:a if zh else b
    label=st.sidebar.radio(t('我是','View as'),[t('医生','Clinician'),t('患者','Patient')],key='simple_role');role='doctor' if label in ['医生','Clinician'] else 'patient'
    st.markdown(CSS,unsafe_allow_html=True)
    st.markdown('<div class="studio-head"><div class="studio-brand"><div class="studio-icon">T2D</div><div><b>T2DRiskNet</b><small>'+t('患者风险工作台','PATIENT RISK WORKSPACE')+'</small></div></div><span class="studio-pill">'+t('研究试用 · 在线演示' if public_demo else '研究试用 · 本地计算','Research demo' if public_demo else 'Local research edition')+'</span></div>',unsafe_allow_html=True)
    if 'product_result' not in st.session_state and not st.session_state.get('product_empty',False):
        try:use_example()
        except Exception:pass
    if role=='patient':
        active=st.session_state.get('product_approved')
        if active is None:
            try:
                records,f,ex,m=product_example();active=saved_assessment(records,f,ex,m,ASSESSMENT,True,'key')
            except Exception:pass
        if active:render_assessment(active,lang,role)
        else:st.info(t('请由医生完成评估后查看报告。','Your clinician can provide a reviewed assessment.'))
    else:
        route=st.radio(t('选择输入方式','Choose input'),[t('上传医院数据','Import hospital data'),t('简单预测','Simple prediction')],horizontal=True,index=1,key='product_route',label_visibility='collapsed')
        left,right=st.columns([1,1.65],gap='large')
        with left:
            with st.container(border=True):
                if route in ['上传医院数据','Import hospital data']:hospital_input(lang,public_demo)
                else:key_input(lang,public_demo)
        with right:
            active=st.session_state.get('product_result')
            if active:render_assessment(active,lang,role)
            else:st.info(t('填入资料，生成五个时间窗的风险画像。','Enter patient records to generate a five-window risk profile.'))
    st.markdown('<div class="studio-footer">'+t('研究试用 · 复查安排由医生确认','Research trial · Review timing requires a clinician')+'</div>',unsafe_allow_html=True)
