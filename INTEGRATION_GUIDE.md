# Hospital integration / 医院接入说明

The clinical front door is `app.py`; the older audit and resource-analysis workspace is `research_app.py`, opened through Advanced options. The public cloud edition uses invented records. Actual hospital records remain local.

## Supported import routes

- Patient JSON: patient ID → birthdate, gender, dated events, optional numeric lab values and units.
- CSV / TSV / GB18030 CSV named `.rds`; binary RDS must be exported first.
- Excel: each sheet is treated as a table.
- Multi-file / ZIP: link demographics and dated diagnosis/lab/medication rows by a stable patient ID. Up to 20 ZIP members and 40 MB uncompressed per batch.
- Wide measurement templates: the explicitly documented units are HbA1c `%`, glucose `mmol/L`, ALT `IU/L`, NT-proBNP `pg/mL`. Column names do not establish unit correctness; the clinician must confirm the template units. Long lab tables must provide units.

Common Chinese/English headers are detected. The adjustment panel maps unfamiliar field names. A verified CSV code map uses `source_code,target_code`. Ambiguous columns, missing demographics, unrecognised diagnosis names and incompatible units stop conversion or prediction rather than being guessed. Numeric sex codes require an explicitly confirmed coding convention. Age is not converted into an invented DOB. Images, arbitrary prose, PDFs, proprietary API schemas and FHIR/HL7 are not automatically understood; they need a separately verified adapter.

## Loopback development API

`local_api.py` binds only to `127.0.0.1:8504`, requires a secret of at least 32 characters in `T2D_LOCAL_API_TOKEN`, and does not log request payloads. Start it using the authorised Python environment after setting this variable securely. It is not started by default and is not a production hospital API.

POST `/v1/convert`, header `Authorization: Bearer <local secret>`:

```json
{"tables":[{"name":"patients","rows":[{"患者编号":"EXAMPLE-001","出生日期":"1964-06-15","性别":"男"}]},{"name":"events","rows":[{"患者编号":"EXAMPLE-001","记录日期":"2026-09-01","诊断代码":"E11.9"},{"患者编号":"EXAMPLE-001","记录日期":"2026-09-01","诊断代码":"I10"}]}]}
```

The response includes converted `records` and an audit. Conversion is not clinical approval. POST `/v1/predict` with `records`, `assessment_date` (`YYYY-MM-DD`) and `mapping_confirmed: true` only after mapping/units have been verified. The response contains the five risks for both supplied weights, exclusions and provenance. `followup_date` is null; follow-up requires clinician review. No real hospital system is connected by this code.

Production integration additionally needs hospital authorisation, a scoped read-only connector, authenticated users, transport security, access controls, monitoring/audit, retention rules and institution-specific validation. These are not implemented by a loopback developer endpoint.

## Few-input route and attribution

The key-data form constructs a sparse dated record and runs the original longitudinal model. It does not train or validate a reduced-feature model and is labelled a research trial. A genuine few-feature product requires a separately trained/distilled model and independent calibration/performance/decision evaluation against the original model.

The supplied IG files describe a 60-month output among participants with events, per the accompanying notes. Pre-event intervals are not future prediction windows. Aggregate mean absolute attribution is not an individual risk contribution, coefficient, causal factor or treatment effect; it is not a mandatory feature list. Correspondence between those attribution results and the deployed weight identities remains unverified.

The plotting exclusion `^(Z|C[0-9]|D[0-4])` is applied only to diagnosis displays. It does not remove original model inputs, and must not accidentally remove ATC `RX_C...` medication tokens. The original CSVs and R code are preserved.
