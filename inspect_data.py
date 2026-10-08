from pathlib import Path
import sys, json
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.deps'))
import pandas as pd
summary = []
for p in ROOT.parent.glob('*/**/sample_*.rds'):
    try:
        for d in [pd.read_csv(p, low_memory=False, encoding='gb18030', nrows=1000)]:
            item = {'file': p.name, 'file_bytes':p.stat().st_size, 'format':'CSV text with .rds extension', 'encoding':'gb18030', 'preview_rows': len(d), 'columns': {str(c): str(d[c].dtype) for c in d.columns}, 'missing_in_preview': {str(c): int(d[c].isna().sum()) for c in d.columns}}
            summary.append(item)
    except Exception as exc:
        summary.append({'file': p.name, 'error': str(exc)})
p = next((ROOT / 'vendor').rglob('ustc_200patients_demo.json'))
data = json.loads(p.read_text(encoding='utf-8'))
r = next(iter(data.values()))
summary.append({'file': p.name, 'patients': len(data), 'fields': list(r), 'event_fields': list(r['events'][0]), 'birthdate_present': sum(bool(x.get('birthdate')) for x in data.values()), 'deathdate_present': sum(bool(x.get('death_date')) for x in data.values())})
(ROOT / 'reports' / 'data_inventory.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=True, indent=2))
