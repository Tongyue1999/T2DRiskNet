"""One product definition shared by the bilingual UI and standalone briefs."""
from pathlib import Path
import html
import pandas as pd

COPY={
'zh':{
'title':'面向医生的糖尿病心血管复查决策支持工具',
'summary':'T2DRiskNet 使用成人 2 型糖尿病患者截至评估日的纵向临床记录，估计首次心血管事件风险，帮助医生决定谁需要优先获得额外评估、强化复诊或管理复核。当前版本是研究原型。',
'who':'谁使用，谁受益',
'roles':[('主要用户','内分泌科、糖尿病门诊或相关临床医生。'),('资源使用者','门诊或科室负责人：分配有限的额外复查名额。'),('研究使用者','用有真实随访结局的独立队列，评估排序效率。'),('患者角色','受益者；将来可查看医生审核过的风险解释与复诊安排。当前不提供患者自助诊断或治疗决策。')],
'input_title':'输入从哪里来',
'inputs':[('推荐输入','由医院导出或通过接口取得结构化的历史诊断、药物、检验和操作记录，并保留各条记录的日期。'),('目前如何输入','研究团队上传统一格式的患者 JSON；省立医院表经适配器转换后进入同一流程。医生无需手工输入全部历史资料。'),('后续如何接系统','经授权由医院信息部门提供只读的数据导出或接口；平台完成编码、单位、日期检查，再送入模型。目前尚未连接实时医院系统。'),('手工填关键数值是否够','不等价。现有模型是纵向 EHR 模型，不是只填年龄、血压、血脂和 HbA1c 的简易评分器。单次少量输入需要另建或验证简化模型。'),('病历 PDF 或自由文本','当前不直接作为模型输入。抽取后仍需日期与编码核对，不能仅凭上传病历就承诺可预测。')],
'required_title':'模型需要哪些资料',
'required':[('患者对应标识','用于合并不同医院表；对外导出使用匿名标识。'),('出生日期、性别','现有权重必需的静态输入。'),('评估日期','模型只能使用当日及以前可获得的资料。'),('历史诊断、用药、检验、操作','编码、日期；检验附原始数值与单位。数量达到接口下限不等于临床上充分有效。'),('T2D 诊断与适用人群','成人、已确认 E11，且符合首次事件预测条件；正式使用还需复现完整队列标准。'),('死亡与后续事件','当前风险推理不需要未来结局；有真实结局的研究验证必须另外提供可靠随访和结局。')],
'workflow_title':'医生实际怎么用',
'workflow':['医院导出患者截至本次评估的历史资料。','平台检查缺失、日期、编码和检验单位，不满足条件者提示补资料。','模型生成 3、6、12、36、60 个月首次复合 CVD 风险。','医生查看个人风险；科室可设置每千人 50、100 或 200 个额外复查名额。','平台列出本批优先复查对象，由医生结合临床情况审核。','有后续真实结局时，研究团队评估事件捕获率、PPV、漏识别率和相对现行策略的增量。'],
'output_title':'产品交付什么',
'outputs':[('个人层面','各时间窗风险、评估日期、资料质量与本批排序。'),('科室层面','固定名额下的优先名单，以及本机患者编号对应表。'),('研究层面','5%、10%、20% 容量表现、比较差异及置信区间；仅在结局资料支持时计算。')],
'boundaries_title':'结果怎么解释',
'boundaries':'风险预测用于额外复查优先排序，不替代诊断和指南推荐治疗。未优先入选者继续常规管理。捕获未来事件患者不等于已预防事件；药物归因或修改输入后的分数变化不能证明某种治疗对个人更有效。两个权重的正式身份、本地校准和前瞻性效果仍需核实。',
'hospital_title':'省立医院数据现在能做什么',
'hospital':'已识别 16 个文件的真实格式，支持分块读取 GB18030 CSV。诊断与就诊表已做全表核对，并生成可复用的匿名诊断轨迹。200 人 JSON 的患者编号与医院表精确对应，可复用这 200 人已有的人口学资料，从原始诊断、检验与 ATC 药物表重建模型输入。其余患者仍需补齐出生日期和性别。已有检验 class 和药物 ATC 只在精确匹配训练词表时采用，不猜测编码；原始诊断字段优先于含混合编码的 HF 字段。不能将同一批 200 人当作新增独立验证队列。',
'versions_title':'分阶段建设',
'versions':[('当前研究原型','文件接入、真实模型推理、个人查看、批量排序、资源验证、中英文界面。'),('下一阶段院内试点','人口学补齐、完整编码映射、固定就诊时点验证、现行策略比较和静默试运行。'),('后续临床服务','接医院数据接口与医生工作流程；在影响评估后考虑患者端的审核后解释页面。')],
'name':'T2DRiskNet 心血管复查决策支持平台',
},
'en':{
'title':'A clinician-facing cardiovascular review decision-support tool for diabetes',
'summary':'T2DRiskNet uses longitudinal clinical records available by the assessment date in adults with type 2 diabetes to estimate first cardiovascular-event risk. It helps clinicians prioritise additional assessment, closer follow-up or management review. The current version is a research prototype.',
'who':'Users and beneficiaries',
'roles':[('Primary users','Clinicians in endocrinology, diabetes clinics and related services.'),('Capacity users','Clinic or department leads allocating limited additional review slots.'),('Research users','Teams evaluating prioritisation using independent cohorts with observed follow-up outcomes.'),('Patient role','Beneficiaries. A future patient view may explain clinician-reviewed risk and follow-up plans. The current tool does not provide patient self-diagnosis or treatment decisions.')],
'input_title':'Where the inputs come from',
'inputs':[('Recommended input','Hospital-exported or interface-retrieved structured histories of diagnoses, medications, laboratory tests and procedures, with dates.'),('Current input route','A research team uploads standard patient JSON. Provincial Hospital tables are converted into the same format by the adapter. Clinicians do not manually re-enter the full history.'),('Future hospital integration','An authorised read-only export or interface supplied by hospital IT, followed by code, unit and date checks. A live hospital system is not connected yet.'),('Are a few manually entered values enough?','They are not equivalent. The supplied model uses longitudinal EHRs, rather than only age, blood pressure, lipids and HbA1c. A simplified single-visit model needs separate development or validation.'),('PDF notes or free text','Not direct inputs to the current model. Any extraction needs date and code verification; uploading a note alone does not establish model compatibility.')],
'required_title':'Required model inputs',
'required':[('Patient linkage identifier','Links tables locally; exports use pseudonymous identifiers.'),('Birth date and sex','Required static inputs for the supplied weights.'),('Assessment date','Only information available on or before this date may enter the model.'),('Dated clinical history','Diagnosis, medication, lab and procedure codes; labs include original values and units. Meeting an interface minimum does not establish clinical adequacy.'),('T2D and eligibility','Adults with confirmed E11 who meet first-event prediction criteria; full cohort eligibility must be reproduced before deployment.'),('Death and subsequent events','Future outcomes are not required for current risk inference. Research evaluation separately requires reliable observed follow-up and outcomes.')],
'workflow_title':'Clinical workflow',
'workflow':['The hospital exports records available up to the assessment date.','The platform checks missingness, timing, codes and lab units; incompatible inputs are flagged.','The models estimate first composite CVD risk at 3, 6, 12, 36 and 60 months.','The clinician reviews individual risk; the clinic can specify 50, 100 or 200 additional slots per 1,000 patients.','The platform lists priority patients for clinician review in context.','With observed outcomes, the research team evaluates event capture, PPV, miss rate and gains over current practice.'],
'output_title':'What the product provides',
'outputs':[('Individual level','Risks by horizon, assessment date, input quality and batch priority.'),('Clinic level','A priority list at fixed capacity and a local patient-reference table.'),('Research level','Performance at 5%, 10% and 20% capacity, paired differences and confidence intervals when outcomes support estimation.')],
'boundaries_title':'Interpreting the outputs',
'boundaries':'Risk estimates prioritise additional review; they do not replace diagnosis or guideline-recommended treatment. Patients not prioritised continue usual care. Capturing future event patients does not mean preventing their events. Drug attribution or score changes after modifying inputs do not establish individual treatment effects. Weight identities, local calibration and prospective impact require verification.',
'hospital_title':'What can be done with the Provincial Hospital data now',
'hospital':'All 16 files are GB18030 CSV with .rds filenames. Diagnosis and visit tables have been audited across all rows and reusable pseudonymous diagnosis trajectories have been created. The 200 JSON identifiers match the hospital tables exactly, allowing existing demographics to be reused and histories to be rebuilt from actual diagnosis, lab and ATC medication tables. Other patients still need birth date and sex. Lab class and medication ATC codes are used only when they match training tokens exactly; codes are not guessed. Original diagnosis codes take priority over mixed-code HF fields. The same 200 patients must not be counted as a new independent validation cohort.',
'versions_title':'Delivery stages',
'versions':[('Current research prototype','File input, actual model inference, individual risk, batch prioritisation, resource evaluation and bilingual interface.'),('Next institutional pilot','Demographic linkage, complete verified mappings, fixed-visit landmark validation, current-practice comparison and silent evaluation.'),('Later clinical service','Hospital interfaces and clinician workflow integration; consider a clinician-reviewed patient explanation view after impact evaluation.')],
'name':'T2DRiskNet Cardiovascular Review Decision Support',
}}

def render(st,lang):
    c=COPY[lang]
    def table(rows):
        content='<table class="product-table" style="width:100%;border-collapse:collapse;background:white">'+''.join('<tr><th style="width:24%;text-align:left;vertical-align:top;padding:14px;border:1px solid #dce5ed">'+html.escape(a)+'</th><td style="padding:14px;border:1px solid #dce5ed;overflow-wrap:anywhere">'+html.escape(b)+'</td></tr>' for a,b in rows)+'</table>'
        st.markdown(content,unsafe_allow_html=True)
    st.subheader(c['title']);st.write(c['summary'])
    for key,items in [('who','roles'),('input_title','inputs'),('required_title','required')]:
        st.markdown('**'+c[key]+'**')
        table(c[items])
    st.markdown('**'+c['workflow_title']+'**')
    st.markdown('\n'.join(f'{i}. {text}' for i,text in enumerate(c['workflow'],1)))
    st.markdown('**'+c['output_title']+'**')
    table(c['outputs'])
    st.info(c['boundaries'])
    st.markdown('**'+c['hospital_title']+'**');st.write(c['hospital'])
    st.markdown('**'+c['versions_title']+'**')
    table(c['versions'])

def export_briefs():
    root=Path(__file__).resolve().parent
    for lang,c in COPY.items():
        chunks=[f'<h1>{html.escape(c["name"])}</h1><h2>{html.escape(c["title"])}</h2><p>{html.escape(c["summary"])}</p>']
        for title,items in [('who','roles'),('input_title','inputs'),('required_title','required'),('output_title','outputs'),('versions_title','versions')]:
            chunks.append('<h2>'+html.escape(c[title])+'</h2><table>'+''.join('<tr><th>'+html.escape(a)+'</th><td>'+html.escape(b)+'</td></tr>' for a,b in c[items])+'</table>')
        chunks.append('<h2>'+html.escape(c['workflow_title'])+'</h2><ol>'+''.join('<li>'+html.escape(t)+'</li>' for t in c['workflow'])+'</ol>')
        for title,body in [('boundaries_title','boundaries'),('hospital_title','hospital')]:
            chunks.append('<h2>'+html.escape(c[title])+'</h2><p>'+html.escape(c[body])+'</p>')
        document='<!doctype html><html lang="'+lang+'"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(c['name'])+'</title><style>body{max-width:1000px;margin:40px auto;padding:0 24px;font:17px/1.7 system-ui;color:#183247;background:#f5f7fb}h1,h2{color:#123c50}table{border-collapse:collapse;width:100%;background:white}th,td{border:1px solid #dce5ed;padding:14px;text-align:left;vertical-align:top}th{width:22%}li{margin:10px 0}@media print{body{background:white;margin:0;font-size:12pt}}</style><body>'+''.join(chunks)+'</body></html>'
        (root/f'product_brief_{lang}.html').write_text(document,encoding='utf-8')
if __name__=='__main__':export_briefs()
