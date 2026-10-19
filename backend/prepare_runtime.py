"""Bundle the saved read-only corpus; never train models during deployment."""
from pathlib import Path
from shutil import copy2

backend = Path(__file__).resolve().parent
destination = backend / 'runtime-data'
destination.mkdir(exist_ok=True)
for name in ('analysis.json', 'research.sqlite'):
    source = backend.parent / 'artifacts' / name
    if source.exists():
        copy2(source, destination / name)
    if not (destination / name).exists():
        raise FileNotFoundError(f'Missing saved artifact: {name}. Run train.py locally first.')
print('Saved analysis and corpus ready; no model training required.')
