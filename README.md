# T2DRiskNet Web · 心血管风险研究工作台

Bilingual Streamlit research prototype for longitudinal cardiovascular risk assessment and capacity-constrained review prioritisation in adults with type 2 diabetes.

面向医生和研究人员的中英文研究原型，支持纵向临床资料接入、五个风险时间窗和固定复查容量的策略比较。行动范围是额外评估、强化复诊或管理复核；低风险预测不改变指南推荐治疗。预测识别事件不等于预防事件，药物归因不代表个体治疗效应。

## Simple clinical view / 简洁版

The clinician interface has two routes: hospital-file import and simple prediction. Simple prediction uses five inputs (age, sex, recorded hypertension, HbA1c and creatinine). A collapsed panel adds systolic/diastolic blood pressure, LDL cholesterol, glucose and recorded aspirin use, switching to the corresponding ten-input model when enabled. These are locally trained, code-defined-outcome research models, not the previous teacher-distilled student and not sparse inputs passed to the original longitudinal model. The default invented patient is scored by the five-input runtime. Five-year estimates are explicitly unvalidated. Original full-model inference remains available for hospital-file import. More input data does not establish greater accuracy.

中英文界面保留“上传医院数据”和“简单预测”。默认填写5项，补充指标折叠显示；使用对应精简模型计算，入口标注研究试用。五年估计待验证，复查安排由医生确认。患者视图只显示示例或已审核报告。公开在线版仅允许虚构病例；真实医院资料保留在本地或院内。高级研究工作区仍可通过 `?workspace=research` 访问。常见文件格式需要核对字段、代码和单位，不承诺任意医院资料无需确认即可适配。

## Run / 运行

Live synthetic research workbench: https://t2drisknet-research.streamlit.app/ (use `?lang=en` for English). Real model inference, invented cases/outcomes, no real hospital uploads. The separately deployed runtime repository is private; no model weights are distributed here.

公开在线版已支持真实模型计算、合成结局容量仿真与医生审核后的双语报告。医院对接仍需授权接口、身份认证及核实的数据映射；不是已上线的医院系统。

```bash
python -m venv .venv
# Activate the environment for your operating system.
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8501/`; use the sidebar language switch or `?lang=en`.

The input interface opens without model files; simple prediction requires the separately authorised `simple_models.json`. Actual inference requires the authorised original bundle under `vendor/`: retain its `requirements.txt`, `scripts/`, `config/`, and `weights/model_02.pt`, `weights/model_03.pt` layout. Install and validate the model runtime locally. The weight identities remain unverified; the app does not label them as a confirmed model-versus-clinical-baseline comparison.

输入界面可直接打开；简单预测需要另行提供已授权的 `simple_models.json`。完整模型预测需要将已授权模型包放入 `vendor/`，保留原包目录结构。模型权重、医院资料、患者样本、病历及本地分析结果不包含在公开仓库中。

## Inputs / 输入

- Patient JSON: birthdate, gender, dated diagnosis/medication/laboratory events. Only records at or before the assessment date are used for current predictions.
- Retrospective evaluation: compatible patient-level predictions, event types and follow-up times; external NPZ import supports the supplied package's result format.
- Local hospital conversion: GB18030 CSV files with `.rds` suffix, exactly linked demographics and verified training-vocabulary mappings.
- `templates/` contains header-only demographic and mapping templates.

The original package's retrospective landmark selection uses future outcome information and is exposed for reproduction only. It must not be reported as a prospective deployment simulation. The separate outcome extraction pipeline uses a provisional first-recorded-E11 landmark; eligibility, outcome ascertainment and text candidates require clinical verification.

## Research evaluation / 研究分析

Top-risk 5%, 10%, and 20% denote fixed review capacity, not probability thresholds. The analysis reports capture, PPV, missed events and paired bootstrap differences, with censoring adjustment and competing-death handling. Fixed-capacity comparisons do not add reviews. Superiority and prevention benefits are not established by this prototype.

疾病文本提及、诊断段落候选、首次提及日期均不能自动等同于新发事件。人口学缺失不通过年龄虚构出生日期。正式分析需要独立队列、完整随访、核实的模型身份和预先确定的比较策略。

## Deployment / 部署

GitHub Pages hosts the bilingual entry page; Streamlit Community Cloud runs `cloud_app.py` from a separate private runtime repository. Model weights stay private. The public application defaults to synthetic-only demo mode. A hospital deployment needs authentication, access control, verified integration and outcome validation.

默认仅绑定本机。实际医院数据继续在本机或经批准的院内环境运行。公开演示应单独部署，使用合成资料，不上传医院原始数据或患者记录。

## Validation / 核验

`analysis.py` can be tested independently of model weights. Full integration tests in `test_platform.py` require authorised local model/sample artifacts. `run_outcome_pipeline.ps1` documents local extraction order; update its Python path for your environment. Original supplied model code is intentionally excluded pending distribution permission.

No software licence is asserted for third-party model code or weights. A project licence can be added by the owner when appropriate.


### Simple prediction / 简单预测

The product now offers five research inputs (age, sex, recorded hypertension, HbA1c and creatinine), with a collapsed optional panel for blood pressure, LDL cholesterol, glucose and recorded aspirin use. The 5/10-input predictors use a parameter-only cause-specific survival runtime in `simple_predictor.py`, not sparse inputs passed to the original longitudinal model. The learned `simple_models.json` is supplied separately in the private runtime repository; it is not included here. Public cloud use remains synthetic-only. Full-record upload preserves more information but is not established to be more accurate. Five-year estimates are explicitly unvalidated.

产品提供5项主输入及折叠的补充指标，中英文同步。入口为研究试用；精简模型是编码结局的本院内部探索，尚未完成临床验证。原始医院资料未上传，线上仅使用虚构病例。
