"""Install a private, locally supplied model bundle, never fetch from user URLs."""
from pathlib import Path
import os,tempfile,zipfile,shutil

_bundle=None
def install_private_bundle():
    global _bundle
    if _bundle:return _bundle
    root=Path(__file__).resolve().parent
    if not (root/'runtime_support.zip').exists():return None
    weights=[root/'model_02.pt',root/'model_03.pt']
    if not all(p.exists() for p in weights):raise ValueError('Private model weights are missing.')
    target=Path(tempfile.mkdtemp(prefix='t2d_models_'))
    with zipfile.ZipFile(root/'runtime_support.zip') as archive:
        for entry in archive.infolist():
            resolved=(target/entry.filename).resolve()
            if not resolved.is_relative_to(target.resolve()):raise ValueError('Unsafe bundle path.')
        archive.extractall(target)
    (target/'weights').mkdir(exist_ok=True)
    for weight in weights:shutil.copyfile(weight,target/'weights'/weight.name)
    os.environ['T2D_BUNDLE_PATH']=str(target);_bundle=target
    return target
