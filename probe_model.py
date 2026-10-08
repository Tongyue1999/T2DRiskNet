import sys, json, importlib.util, zipfile, gzip
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.deps'))
import torch
torch.set_num_threads(4)
package = next(p.parent for p in (ROOT / 'vendor').rglob('requirements.txt'))
spec = importlib.util.spec_from_file_location('vendor_inference', package / 'scripts/run_inference.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
cfg = json.loads((package / 'config/input_config.json').read_text(encoding='utf-8'))
data = next((ROOT / 'vendor').rglob('ustc_200patients_demo.json'))
prepared = ROOT / 'data' / 'prepared_sample.json'
import subprocess
subprocess.run([sys.executable, str(package / 'scripts/prepare_json.py'), '--input', str(data), '--output', str(prepared), '--config-dir', str(package / 'config')], check=True)
patients = module.load_patients(prepared, cfg)
rows = module.selected_patients(patients, 0, 42, 'primary')[:2]
for name in ['02', '03']:
    with (package / f'weights/model_{name}.pt').open('rb') as handle:
        model = torch.jit.load(handle, map_location='cpu').eval()
    result = module.predict(model, rows, cfg, torch.device('cpu'), 2)
    print('model', name, 'shape', result.shape, 'risk_range', float(result.min()), float(result.max()))
    print('graph_tail', str(model.code)[-1500:])
for p in ROOT.parent.rglob('*.rds'):
    raw = p.read_bytes()
    try:
        unpack = gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw
        print('RDS', p.name, 'header', repr(unpack[:35]))
        import rdata
        converted = rdata.read_rds(p)
        print('RDS type', type(converted).__name__, 'shape', getattr(converted, 'shape', None), 'columns', list(converted.columns) if hasattr(converted, 'columns') else list(converted)[:12])
    except Exception as exc:
        print('RDS error', type(exc).__name__, str(exc)[:180])
