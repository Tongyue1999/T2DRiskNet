"""Local inference adapter. Original vendor scripts and weights stay unchanged."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import threading
from datetime import date
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.deps'))
HORIZONS = [3, 6, 12, 36, 60]
LOCK = threading.Lock()

@lru_cache(maxsize=1)
def resources():
    import torch
    torch.set_num_threads(4)
    package = next((p.parent for p in (ROOT / 'vendor').rglob('requirements.txt')), None)
    if package is None:
        raise ValueError('Model bundle is not installed. Place the authorised bundle under vendor/; model weights and clinical data are intentionally excluded from this repository.')
    modules = []
    for label, filename in [('t2d_vendor_inference', 'run_inference.py'), ('t2d_vendor_prepare', 'prepare_json.py')]:
        spec = importlib.util.spec_from_file_location(label, package / 'scripts' / filename)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[label] = mod
        spec.loader.exec_module(mod)
        modules.append(mod)
    cfg = json.loads((package / 'config/input_config.json').read_text(encoding='utf-8'))
    models = {}
    for name in ['02', '03']:
        with (package / f'weights/model_{name}.pt').open('rb') as handle:
            models[name] = torch.jit.load(handle, map_location='cpu').eval()
    return package, modules[0], modules[1], cfg, models

def sample_path():
    path=next((ROOT / 'vendor').rglob('ustc_200patients_demo.json'), None)
    if path is None:
        raise ValueError('No local clinical sample installed. Use an authorised local JSON input.')
    return path

def prepare_records(records, prep, package):
    # Reuse the supplied laboratory conversions in a temporary directory.
    with tempfile.TemporaryDirectory(prefix='t2d_local_') as tmp:
        source, out = Path(tmp) / 'input.json', Path(tmp) / 'prepared.json'
        source.write_text(json.dumps(records, ensure_ascii=False), encoding='utf-8')
        args = type('Args', (), {'input': source, 'output': out, 'config_dir': package / 'config'})()
        original = prep.arguments
        try:
            prep.arguments = lambda: args
            prep.main()
        finally:
            prep.arguments = original
        return json.loads(out.read_text(encoding='utf-8'))

def validate_records(records):
    if not isinstance(records, dict) or not records:
        raise ValueError('输入必须是非空患者字典，格式与提供的 JSON 样例一致。')
    if len(records) > 10000:
        raise ValueError('本地首版每次最多处理 10,000 名患者，请分批。')
    for position, rec in enumerate(records.values(), 1):
        if not isinstance(rec, dict) or not isinstance(rec.get('events'), list):
            raise ValueError(f'第 {position} 个患者缺少 events 列表。')
        if len(rec['events']) > 50000:
            raise ValueError(f'第 {position} 个患者事件过多。')
        try:
            date.fromisoformat(str(rec['birthdate'])[:10])
            for event in rec['events']:
                date.fromisoformat(str(event['admdate'])[:10])
                if not isinstance(event.get('codes'), str):
                    raise ValueError('missing code')
        except (KeyError, TypeError, ValueError):
            raise ValueError(f'第 {position} 个患者出生日期或事件字段不符合格式。') from None

def infer(records, mode='current', assessment_date=None, progress=None):
    """Current: no outcome-dependent landmark. Retrospective: vendor seed-42 protocol."""
    validate_records(records)
    if mode not in {'current', 'retrospective'}:
        raise ValueError('Unknown mode')
    fixed = date.fromisoformat(assessment_date) if assessment_date else None
    with LOCK:
        package, vendor, prep, cfg, models = resources()
        prepared = prepare_records(records, prep, package)
        rows, metadata, exclusions = [], [], []
        source_hash = hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        for i, (key, rec) in enumerate(prepared.items(), 1):
            pseudonym = 'P-' + hashlib.sha256(str(key).encode()).hexdigest()[:16]
            try:
                dob = vendor.parse_date(rec['birthdate'], required=True)
                sex = vendor.gender_value(rec.get('gender'))
                if sex not in {0., 1.}:
                    raise ValueError('性别缺失或编码无法识别')
                raw_events = rec['events']
                if not raw_events:
                    raise ValueError('没有事件记录')
                if mode == 'current':
                    cutoff = fixed or max(vendor.parse_date(e['admdate'], True) for e in raw_events)
                    history = [e for e in raw_events if vendor.parse_date(e['admdate'], True) <= cutoff]
                else:
                    history = raw_events
                    cutoff = None
                # Target diagnosis detection uses all codes, including unmapped diagnoses.
                raw_target = vendor.first_target([dict(e, date=vendor.parse_date(e['admdate'], True)) for e in raw_events], cfg)
                if mode == 'current':
                    if raw_target <= cutoff:
                        raise ValueError('评估日已有目标 CVD 诊断，不属于首次事件预测人群')
                    if any(vendor.code(e['codes'], cfg) in {'E10', 'E13'} or str(e['codes']).replace('.','').startswith('O244') for e in history):
                        raise ValueError('存在其他糖尿病类型编码，需人工确认适用人群')
                events = vendor.process_events(history, cfg)
                real = [e for e in events if not str(e['codes']).startswith('TIME_GAP_')]
                if len(real) < cfg['min_events_length']:
                    raise ValueError('匹配词表后的记录不足 2 条')
                if any(e['date'] < dob for e in events):
                    raise ValueError('记录日期早于出生日期')
                end = vendor.parse_date(rec.get('end_of_data'))
                death = vendor.parse_date(rec.get('death_date'))
                patient = vendor.Patient(str(key), dob, sex, end, death, raw_target, events, {})
                if mode == 'retrospective':
                    options = vendor.candidate_indices(events, raw_target, death, end, 0, cfg)
                    if not options:
                        raise ValueError('无可用回顾性评估时点')
                    patient.candidates = {0: options}
                    # One explicit seeded landmark per patient, matching vendor sensitivity rule.
                    _, selected = vendor.selected_patients([patient], 0, 42, 'sensitivity')[0]
                    assess = events[selected]['date']
                else:
                    selected = len(events) - 1
                    assess = cutoff
                    if death <= assess:
                        raise ValueError('评估日已记录死亡')
                if (assess - dob).days < 18 * 365.25:
                    raise ValueError('评估时未满 18 岁')
                used = vendor.canonical_history(patient, selected, cfg)
                codes_at_assessment = [str(e['codes']).replace('.','') for e in raw_events if vendor.parse_date(e['admdate'],True) <= assess]
                if not any(token.startswith('E11') for token in codes_at_assessment):
                    raise ValueError('评估日前未记录 E11 型 2 型糖尿病诊断')
                if any(token.startswith(('E10','E13','O244')) for token in codes_at_assessment):
                    raise ValueError('存在其他糖尿病类型编码，需人工确认适用人群')
                matched = sum(not str(e['codes']).startswith(('TIME_GAP_', '<UNK>')) for e in used)
                total = sum(vendor.parse_date(e['admdate'], True) <= assess for e in raw_events)
                row = {'patient_key': pseudonym, 'assessment_date': assess.isoformat(), 'age': round((assess-dob).days/365.25, 1), 'sex': '男' if sex else '女', 'matched_events': matched, 'raw_events': total, 'mapped_fraction': matched / max(total, 1), 'numeric_labs': sum(int(e.get('lab_value_mask', 0)) for e in used), 'history_days': (assess - min(e['date'] for e in used)).days, 'last_record_gap_days': (assess-real[-1]['date']).days if mode == 'current' else 0}
                if mode == 'retrospective':
                    if end == vendor.MISSING or end < assess:
                        raise ValueError('缺少可用随访终止日期')
                    dates = [(end, 0)]
                    if raw_target != vendor.MISSING and raw_target > assess and raw_target <= end:
                        dates.append((raw_target, 1))
                    if death != vendor.MISSING and death > assess and death <= end:
                        dates.append((death, 2))
                    terminal_date, kind = min(dates, key=lambda x: (x[0], {1:0,2:1,0:2}[x[1]]))
                    row.update(duration_days=(terminal_date-assess).days, event_type=kind)
                rows.append((patient, selected))
                metadata.append(row)
            except (ValueError, RuntimeError, KeyError, TypeError) as exc:
                exclusions.append({'patient_key': pseudonym, 'reason': str(exc)})
        if not rows:
            raise ValueError('没有可推理患者。' + '; '.join(sorted({r['reason'] for r in exclusions})))
        import torch
        for name, model in models.items():
            batches = []
            for start in range(0, len(rows), 8):
                items = []
                for offset, (patient, index) in enumerate(rows[start:start+8]):
                    item = vendor.tensor_item(patient, index, cfg)
                    anchor = date.fromisoformat(metadata[start+offset]['assessment_date'])
                    history = vendor.canonical_history(patient, index, cfg)
                    # Exact doctor-selected date; no invented event at the anchor.
                    time_seq = vendor.positional([(anchor-e['date']).days for e in history], cfg['time_embed_dim'])
                    item['time_seq'] = vendor.left_pad(np.concatenate([time_seq, np.zeros((1,cfg['time_embed_dim']))]).astype(np.float32), cfg['pad_size'])
                    age_seq = vendor.positional([(e['date']-patient.dob).days for e in history] + [(anchor-patient.dob).days], cfg['time_embed_dim'])
                    item['age_seq'] = vendor.left_pad(age_seq.astype(np.float32), cfg['pad_size'])
                    item['age'] = float((anchor-patient.dob).days)
                    items.append(item)
                def tensor(key, dtype):
                    return torch.as_tensor(np.stack([item[key] for item in items]), dtype=dtype)
                with torch.inference_mode():
                    batch = model(tensor('x',torch.long),tensor('mask',torch.long),tensor('visit_pos',torch.long),tensor('time_seq',torch.float32),tensor('age_seq',torch.float32),tensor('age',torch.float32),tensor('gender',torch.float32),tensor('lab_type',torch.long),tensor('lab_flag',torch.long),tensor('lab_value',torch.float32),tensor('lab_mask',torch.long)).detach().cpu().numpy()
                batches.append(batch)
                if progress:
                    progress((int(name)-2)/2 + min(start+8, len(rows))/len(rows)/2)
            risks = np.concatenate(batches)
            if risks.shape != (len(rows), 5) or not np.isfinite(risks).all() or (risks < -1e-6).any() or (risks > 1+1e-6).any():
                raise ValueError('模型输出不是预期的五个时间窗概率，停止展示。')
            if (np.diff(risks, axis=1) < -1e-5).any():
                raise ValueError('模型风险不满足累计发生概率的单调性，停止展示。')
            for j, record in enumerate(metadata):
                record.update({f'risk_{name}_{h}': float(risks[j,k]) for k,h in enumerate(HORIZONS)})
        manifest = {'mode': mode, 'source_sha256': source_hash, 'input_patients': len(records), 'included': len(rows), 'excluded': len(exclusions), 'horizon_months': HORIZONS, 'month_days': 30, 'endpoint': '首次 CVD（I20–I25、I50、I60–I64）', 'landmark': 'specified_date_or_latest_record' if mode=='current' else 'outcome_conditioned_vendor_sensitivity_seed42', 'model_names_verified': False, 'weights_sha256': {name: hashlib.sha256((package/f'weights/model_{name}.pt').read_bytes()).hexdigest() for name in models}}
        return pd.DataFrame(metadata), pd.DataFrame(exclusions), manifest

def import_npz(content, followup=0, seed_index=0, analysis_index=0):
    with np.load(io.BytesIO(content), allow_pickle=False) as z:
        tag = f'fu{followup}'
        keys = z[f'patient_key_{tag}'].astype(str)
        durations = z[f'duration_days_{tag}'][seed_index, analysis_index]
        kinds = z[f'event_type_{tag}'][seed_index, analysis_index]
        data = {'patient_key': keys, 'duration_days': durations, 'event_type': kinds}
        for name in ['02','03']:
            risks = z[f'risk_{name}_{tag}'][seed_index, analysis_index]
            for index, horizon in enumerate(HORIZONS):
                data[f'risk_{name}_{horizon}'] = risks[:,index]
        frame = pd.DataFrame(data)
        manifest = {'mode':'retrospective','source_sha256':str(z['source_sha256'].item()), 'landmark':'imported_vendor_npz', 'seed':int(z['seed'][seed_index]), 'analysis':str(z['analysis'][analysis_index]), 'followup_months':followup, 'horizon_months':HORIZONS, 'month_days':30, 'model_names_verified':False}
        return frame, pd.DataFrame(), manifest
