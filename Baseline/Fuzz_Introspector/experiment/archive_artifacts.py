#!/usr/bin/env python3
"""Preserve native intermediate evidence without changing or classifying it."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
rows = json.loads((ROOT / 'experiment/results/native-results.json').read_text())
records = []
for row in rows:
    source = ROOT / row['official_out']
    destination = ROOT / row['run_folder'] / 'native-evidence'
    destination.mkdir(exist_ok=True)
    for name in ['dumps']:
        if (source / name).is_dir():
            shutil.copytree(source / name, destination / name, dirs_exist_ok=True)
    artifacts = []
    for prefix in ['crash-', 'leak-', 'oom-', 'timeout-', 'slow-unit-']:
        for path in source.glob(prefix + '*'):
            if path.is_file():
                shutil.copy2(path, destination / path.name)
                artifacts.append(path.name)
    files = {}
    for path in sorted(destination.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                files[str(path.relative_to(ROOT))] = hashlib.file_digest(stream, 'sha256').hexdigest()
    records.append({'case_id': row['case_id'], 'files_sha256': files, 'native_artifact_names': artifacts})
(ROOT / 'experiment/results/native-evidence-manifest.json').write_text(json.dumps(records, indent=2) + '\n')
print(f'Archived native evidence for {len(records)} completed samples.')
