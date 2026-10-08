"""Local interface translation; widget option values stay stable across languages."""
import re

EN = {
'省立医院关联样本（真实院内表）':'Linked Provincial Hospital sample (actual source tables)',
'产品定位说明 中文':'Product brief Chinese',
'人口学资料必须包含 PERSON_ID_NEW、birthdate、gender。':'Demographics must contain PERSON_ID_NEW, birthdate and gender.',
'人口学资料有缺失或重复患者。':'Demographics contain missing values or duplicate patients.',
'首版适配器每批最多 10,000 名患者。':'The prototype adapter accepts up to 10,000 patients per batch.',
'映射表需要 source、name、token。source 为 lab、med 或 op。':'Mapping requires source, name and token; source must be lab, med or op.',
'映射表存在缺失或同一名称的重复映射。':'The mapping contains missing values or duplicate mappings for a name.',
'映射 token 必须属于相应类型且存在于训练词表。':'A mapped token must match its event type and exist in the training vocabulary.',
'人口学资料性别编码无法识别。':'Sex coding in the demographics table is unrecognised.',
'输入必须是非空患者字典，格式与提供的 JSON 样例一致。':'Input must be a non-empty patient dictionary matching the supplied JSON schema.',
'本地首版每次最多处理 10,000 名患者，请分批。':'The prototype accepts up to 10,000 patients per run; split larger inputs into batches.',
'没有可推理患者。':'No patients have compatible inference inputs. ',
'性别缺失或编码无法识别':'Sex is missing or unrecognised',
'没有事件记录':'No clinical events',
'评估日已有目标 CVD 诊断，不属于首次事件预测人群':'Target CVD was recorded by assessment; not eligible for first-event prediction',
'存在其他糖尿病类型编码，需人工确认适用人群':'Other diabetes-type codes are present; eligibility requires review',
'匹配词表后的记录不足 2 条':'Fewer than two events match the vocabulary',
'记录日期早于出生日期':'A record predates the birth date',
'无可用回顾性评估时点':'No eligible retrospective landmark',
'评估日已记录死亡':'Death was recorded by assessment',
'评估时未满 18 岁':'Under age 18 at assessment',
'评估日前未记录 E11 型 2 型糖尿病诊断':'No E11 type 2 diabetes diagnosis was recorded by assessment',
'缺少可用随访终止日期':'No valid end-of-follow-up date',
'模型输出不是预期的五个时间窗概率，停止展示。':'Model output is not five valid horizon probabilities; display stopped.',
'模型风险不满足累计发生概率的单调性，停止展示。':'Model risks are not monotone cumulative incidences; display stopped.',
'缺少患者标识、随访、事件类型或策略分数。':'Patient identifier, follow-up, outcome type or strategy score is missing.',
'每次分析必须每名患者一行，患者标识不能重复或缺失。':'Use one row per patient; identifiers must be present and unique.',
'event_type 必须为 0 删失、1 CVD、2 竞争死亡。':'event_type must be 0 (censoring), 1 (CVD) or 2 (competing death).',
'随访或分数存在缺失、非有限值或负随访。':'Follow-up or scores contain missing/non-finite values, or follow-up is negative.',
'评估当日已有事件或死亡，不能用于首次事件预测分析。':'An event or death occurred on the assessment date; incompatible with first-event evaluation.',
'T2DRiskNet 心血管风险工作台':'T2DRiskNet Cardiovascular Review Workbench',
'纵向临床记录 · 五个预测时间窗 · 有限复查名额下的优先排序':'Longitudinal clinical records · Five risk horizons · Prioritised additional review',
'本地研究原型｜两个权重的正式身份尚未确认｜仅预测首次复合 CVD，目前权重不提供独立 CHD、卒中或 HF 输出':'Local research prototype | Weight identities require confirmation | First composite CVD only; no separate CHD, stroke or HF output',
'行动范围：额外评估、强化复诊或管理复核。未被优先选中者继续指南推荐的常规治疗。预测捕获不等于事件预防。':'Intended action: additional assessment, closer follow-up or management review. All patients continue guideline-recommended care. Event capture does not mean event prevention.',
'工作台':'Workbench','功能':'Navigation','产品定位与使用流程':'Product and workflow',
'患者风险与复查排序':'Patient risk and review priorities','资源约束验证':'Capacity-constrained evaluation','数据接入与模型说明':'Data integration and model details',
'**数据保留在本机**':'**Data stay on this computer**',
'上传文件在当前会话中处理；原始上传不永久保存。内置结果仅来自用户提供的 200 人样例。':'Uploads are processed within this session and are not permanently retained. Built-in predictions come from the supplied 200-patient sample.',
'清除当前会话结果':'Clear session results','数据来源':'Data source','已计算的 200 人样例':'Precomputed 200-patient sample','上传患者 JSON':'Upload patient JSON','重新运行内置 JSON 样例':'Run the supplied JSON sample again','导入外部验证 NPZ':'Import external-validation NPZ',
'接口验证样例；是否属于训练、调参或独立测试集尚未确认，不作为论文独立验证证据。':'Interface test sample; training/tuning/test independence is unverified. Do not use it as independent validation evidence.',
'预计算结果尚未生成，可选择运行内置样例。':'Precomputed results are unavailable. Run the supplied sample instead.',
'外部验证 result_01.npz 或 result_02.npz':'External-validation result_01.npz or result_02.npz',
'随访筛选组':'Follow-up eligibility group','随机种子索引（从 0 开始）':'Seed index (starts at 0)','评估时点方案索引':'Landmark-selection index','读取 NPZ':'Load NPZ','NPZ 格式或索引不匹配：':'NPZ format or index mismatch: ',
'患者 JSON（标准事件序列格式）':'Patient JSON (standard event sequence)','评估时点':'Assessment date','每名患者最后记录日':'Each patient’s last recorded date','指定统一评估日期':'Specify one assessment date','只使用该日期及之前的记录':'Use records on or before this date',
'该回顾性入口按原包 sensitivity、seed=42 选择事件前时点，使用结局信息选时点，仅用于复现和探索；不能视为前瞻性部署模拟。':'This retrospective route reproduces vendor sensitivity/seed=42 landmarks. Landmark selection uses outcome information; it is exploratory reproduction, not a prospective deployment simulation.',
'运行真实模型':'Run the actual models','CPU 正在运行两个模型…':'Running both models on CPU…','推理未完成：':'Inference did not complete: ',
'从已有临床记录评估未来风险':'Estimate future risk from existing clinical records','查看模型':'Model','排序时间窗（月）':'Priority horizon (months)','额外复查容量（每 1,000 人）':'Additional review slots per 1,000 patients',
'可评估患者':'Patients with predictions','本批额外复查名额':'Review slots in this batch','本批入选风险分界':'Risk cutoff in this batch',
'风险分界随本批人群和容量变化。输出供医生复核，不自动触发转诊或治疗。':'The cutoff depends on the cohort and capacity. Clinician review is required; outputs do not automatically trigger referral or treatment.',
'**个人风险查看**':'**Individual risk**','个人风险查看':'Individual risk','匿名患者':'Pseudonymous patient','评估日期：':'Assessment date: ','未提供':'Not provided','排序建议：':'Priority suggestion: ','优先安排额外评估':'Prioritise additional assessment','继续常规管理，本批未优先入选':'Continue usual care; not prioritised in this batch',
'不足一半事件匹配训练词表，需检查数据映射。':'Fewer than half of the events match the training vocabulary. Check the mapping.',
'时间窗（月）':'Horizon (months)','预测风险':'Predicted risk','**批量复查优先名单**':'**Batch review priorities**','批量复查优先名单':'Batch review priorities','优先复查':'Prioritised review',
'导出排序与五个时间窗风险':'Export priorities and risks at five horizons','下载本机患者编号对应表':'Download the local patient-reference table',
'对应表用于在本院定位患者，包含上传文件中的患者编号，应留在本院。预测结果默认使用匿名标识。':'This table links outputs to identifiers in your upload. Keep it within your institution. Predictions use pseudonymous identifiers by default.',
'导出运行信息':'Export run metadata','未满足输入条件的患者':'Patients without valid model inputs',
'同样复查名额下，哪种排序捕获更多未来事件？':'Which strategy captures more future events at the same review capacity?',
'当前内置数据是 200 人样例，独立性及代表性未确认。结果只用于接口验证和探索，不能证明临床获益。':'The built-in data are a 200-patient sample with unverified independence and representativeness. Results support interface testing and exploration, not claims of clinical benefit.',
'这份样例未记录目标 CVD 事件，能验证风险预测接口，但不能计算事件捕获获益。请接入有真实结局的验证队列或 NPZ。':'This sample contains no recorded target CVD events. It can test inference, but cannot establish event-capture gains. Import a validation cohort with observed outcomes.',
'待评估模型':'Model to evaluate','结局时间窗（月）':'Outcome horizon (months)','配对 bootstrap 次数':'Paired bootstrap resamples','比较策略':'Comparator','另一个已提供模型':'Other supplied model','上传现行策略分数':'Upload current-strategy scores',
'两个模型权重的身份待核实；这不是已确认的现行临床策略比较。':'The two weight identities remain unverified. This is not a confirmed comparison against current clinical practice.',
'下载现行策略分数模板':'Download current-strategy score template','同一评估时点的现行策略分数 CSV；分数越高越优先':'CSV of current-strategy scores at the same landmark; higher scores mean higher priority',
'必须包含唯一 patient_key 和 current_score。':'Unique patient_key and current_score columns are required.','患者集合必须完全匹配，不能静默删除患者。':'Patient sets must match exactly; patients cannot be silently dropped.',
'计算 5% / 10% / 20% 容量分析':'Evaluate 5% / 10% / 20% capacity','估计删失校正指标和配对置信区间…':'Estimating censoring-adjusted metrics and paired confidence intervals…',
'分析患者':'Patients analysed','已观察目标事件':'Observed target events','时间窗前提前删失':'Censored before the horizon',
'采用边际 IPCW 校正提前删失，竞争死亡不作为删失；依赖独立删失假设。不同时间窗不能累加；每月按原包 30 天计算。':'Marginal IPCW adjusts for early censoring; competing death is not censoring. Independent censoring is assumed. Horizons cannot be summed; one month equals 30 days in the vendor convention.',
'部分 IPCW 估计超出概率范围，相关 PPV 和非事件数已留空；需更多随访或条件删失模型。':'Some IPCW estimates fall outside the probability range; related PPV and non-event counts are omitted. More follow-up or a conditional censoring model is needed.',
'额外复查名额／1,000 人':'Additional reviews per 1,000 patients','捕获未来目标事件／1,000 人':'Captured future events per 1,000 patients','策略':'Strategy',
'**固定容量下的策略表现**':'**Performance at fixed capacity**','**同等名额下的替换收益及 95% CI**':'**Replacement gains at equal capacity and 95% CI**','**扩大容量的边际收益**':'**Marginal gains from increasing capacity**',
'固定容量下新增复查总量为零；“每多捕获一例所需新增复查”只用于扩大容量比较。空白比值表示无正向增益或无法估计。':'At fixed capacity, the difference in total reviews is zero. Additional reviews per additional event apply only to capacity expansion. Blank ratios indicate no positive gain or an unestimable result.',
'导出分析方法与数据版本':'Export methods and data version','导出 ':'Export ',
'现有数据和模型接入状态':'Data and model integration status',
'**已接通：**标准患者 JSON、两个真实 TorchScript 权重、外部验证 NPZ、现行策略分数 CSV。原始文件与模型包保留不变。':'**Connected:** standard patient JSON, two actual TorchScript weights, external-validation NPZ and current-strategy score CSV. Original source files and model packages are preserved.',
'**医院抽样表：**实际为 GB18030 CSV，文件名保留 `.rds`。当前表中没有出生日期和性别；院内人口学资料与药物、检验编码映射补齐后，可通过适配器转换为标准 JSON。':'**Hospital sample tables:** GB18030 CSV content with `.rds` filenames. Structured tables lack birth date and sex. Supply institutional demographics and verified code mappings to convert them to standard JSON.',
'文件':'File','大小（MB）':'Size (MB)','预览行数':'Preview rows','字段':'Columns',
'下载人口学资料模板':'Download demographics template','下载编码映射模板':'Download code-mapping template','**医院表转换**':'**Convert hospital tables**',
'人口学资料 CSV（PERSON_ID_NEW、birthdate、gender）':'Demographics CSV (PERSON_ID_NEW, birthdate, gender)','药物、检验或手术映射 CSV（source、name、token）':'Medication, lab or procedure mapping CSV (source, name, token)',
'转换本项目医院抽样表':'Convert local hospital sample tables','分块读取本地抽样表，合并人口学信息…':'Reading local tables in chunks and joining demographics…','下载转换后的本地患者 JSON':'Download converted local patient JSON','**输入格式**':'**Input format**',
'匿名患者编号':'pseudonymous_patient_id','男或女':'Male or Female','训练词表中的编码':'CODE_FROM_TRAINING_VOCABULARY',
'医生端不要求未来结局。回顾性验证需要真实随访终止日期与结局；缺失死亡日期不能自动解释为已确认存活。当前原型尚未核验正式部署资格、数据可得时点或本地校准。':'Clinical inference does not require future outcomes. Retrospective evaluation requires observed follow-up and outcomes; missing death dates do not confirm survival. Deployment eligibility, data-availability timing and local calibration still require verification.',
'评估日期':'Assessment date','年龄':'Age','性别':'Sex','匹配事件数':'Matched events','原始事件数':'Original events','匹配比例':'Matched fraction','有效数值检验':'Numeric lab results','历史跨度（天）':'History span (days)','资料距评估日（天）':'Record gap (days)',
'容量（%）':'Capacity (%)','实际复查人数':'Reviews in batch','复查人数／千人':'Reviews per 1,000','捕获事件／千人':'Captured events per 1,000','未发生目标事件的复查／千人':'Non-event reviews per 1,000','事件捕获率':'Event capture rate','阳性预测值':'Positive predictive value','漏识别率':'Miss rate','概率估计有效':'Probability estimate valid',
'额外捕获／千人':'Additional events captured per 1,000','95% CI 下限':'95% CI lower','95% CI 上限':'95% CI upper','未发生目标事件复查的变化／千人':'Change in non-event reviews per 1,000','容量变化':'Capacity change','新增复查／千人':'Additional reviews per 1,000','每多捕获一例所需新增复查':'Additional reviews per extra event','新增入选人数':'Newly selected','移出人数':'No longer selected','共同入选人数':'Selected by both','有效重采样次数':'Valid resamples','比较':'Comparison',
'该时间窗没有已观察到的目标 CVD 事件，无法评价事件捕获增益。风险预测仍可运行；资源验证需要有真实事件和随访的独立队列。':'No target CVD events were observed at this horizon, so event-capture gains cannot be evaluated. Risk inference remains available. Evaluation requires an independent cohort with observed events and follow-up.',
'该时间窗随访支持不足（G(t-) < 0.10），不输出获益估计；请选择较短时间窗。':'Follow-up support is insufficient at this horizon (G(t-) < 0.10). No gain estimate is reported; choose a shorter horizon.',
}

def translate(text, lang):
    if lang!='en' or not isinstance(text,str):return text
    if text in EN:return EN[text]
    match=re.fullmatch(r'未来 (\d+) 个月首次 CVD 风险',text)
    if match:return f'First CVD risk within {match[1]} months'
    match=re.fullmatch(r'匹配事件 (\d+) 条 · 有效数值检验 (\d+) 条',text)
    if match:return f'{match[1]} matched events · {match[2]} numeric lab results'
    match=re.fullmatch(r'完成：(\d+) 人获得预测，(\d+) 人未满足输入条件。',text)
    if match:return f'Complete: {match[1]} patients predicted; {match[2]} patients did not meet input requirements.'
    for key in sorted(EN,key=len,reverse=True):
        if key in text:text=text.replace(key,EN[key])
    return text

class LocalizedUI:
    def __init__(self,target,lang):self.target,self.lang=target,lang
    def __enter__(self):self.target.__enter__();return self
    def __exit__(self,*args):return self.target.__exit__(*args)
    def __getattr__(self,name):
        attr=getattr(self.target,name)
        if name=='sidebar':return LocalizedUI(attr,self.lang)
        if not callable(attr):return attr
        def invoke(*args,**kwargs):
            if name in {'title','header','subheader','markdown','caption','info','warning','error','success','write','text','code','metric','button','download_button','file_uploader','selectbox','radio','slider','number_input','date_input','expander','spinner','progress'} and args:
                args=(translate(args[0],self.lang),)+args[1:]
            for key in ['text','label','help','placeholder']:
                if key in kwargs:kwargs[key]=translate(kwargs[key],self.lang)
            if name in {'radio','selectbox'}:
                existing=kwargs.get('format_func',str)
                kwargs['format_func']=lambda x:translate(existing(x),self.lang)
            if name=='dataframe' and args and hasattr(args[0],'rename'):
                frame=args[0].rename(columns=lambda c:translate(c,self.lang))
                if self.lang=='en':frame=frame.replace({'男':'Male','女':'Female'})
                args=(frame,)+args[1:]
            value=attr(*args,**kwargs)
            if name=='columns':return [LocalizedUI(v,self.lang) for v in value]
            if name in {'expander','spinner','container','progress'}:return LocalizedUI(value,self.lang)
            return value
        return invoke
