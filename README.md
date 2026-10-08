# T2DRiskNet Web · 心血管风险研究工作台

Bilingual Streamlit research prototype for longitudinal cardiovascular risk assessment and capacity-constrained review prioritisation in adults with type 2 diabetes.

面向医生和研究人员的中英文研究原型，支持纵向临床资料接入、五个风险时间窗和固定复查容量的策略比较。行动范围是额外评估、强化复诊或管理复核；低风险预测不改变指南推荐治疗。预测识别事件不等于预防事件，药物归因不代表个体治疗效应。

## Run / 运行

```bash
python -m venv .venv
# Activate the environment for your operating system.
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8501/`; use the sidebar language switch or `?lang=en`.

The product overview opens without model files. Actual inference requires the authorised original bundle under `vendor/`: retain its `requirements.txt`, `scripts/`, `config/`, and `weights/model_02.pt`, `weights/model_03.pt` layout. Install and validate the model runtime locally. The weight identities remain unverified; the app does not label them as a confirmed model-versus-clinical-baseline comparison.

产品说明可直接打开。真实预测需要将已授权模型包放入 `vendor/`，保留原包目录结构。模型权重、医院资料、患者样本、病历及本地分析结果不包含在公开仓库中。

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

This repository contains source code, not a hosted Python service. GitHub Pages can display the static `product_brief_zh.html` and `product_brief_en.html`; running the interactive workbench requires Streamlit/Python hosting. Public hosting must use synthetic demonstration data and must not expose clinical uploads or local hospital paths. The application is currently a local research prototype without production authentication or access control.

默认仅绑定本机。实际医院数据继续在本机或经批准的院内环境运行。公开演示应单独部署，使用合成资料，不上传医院原始数据或患者记录。

## Validation / 核验

`analysis.py` can be tested independently of model weights. Full integration tests in `test_platform.py` require authorised local model/sample artifacts. `run_outcome_pipeline.ps1` documents local extraction order; update its Python path for your environment. Original supplied model code is intentionally excluded pending distribution permission.

No software licence is asserted for third-party model code or weights. A project licence can be added by the owner when appropriate.
