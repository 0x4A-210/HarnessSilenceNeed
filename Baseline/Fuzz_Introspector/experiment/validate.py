#!/usr/bin/env python3
"""Audit completed artifacts and input identity; no detection/classification."""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    rows = json.loads((ROOT / 'experiment/results/native-results.json').read_text())
    failures = []
    checks = []
    expected_ids = {f'V3-{i:02}' for i in range(1, 49)}
    if {r['case_id'] for r in rows} != expected_ids or len(rows) != 48:
        failures.append('Exactly 48 unique main-set cases are required.')
    provenance = json.loads((ROOT / 'experiment/provenance.json').read_text())
    for repo_name, key in [('fuzz-introspector', 'fuzz_introspector'), ('oss-fuzz', 'oss_fuzz')]:
        repo = ROOT / 'upstream' / repo_name
        head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        if head != provenance[key]['commit']:
            failures.append(f'{repo_name}: commit mismatch')
        # DrvFS mode emulation is distinct from a source-content modification.
        rc = subprocess.run(['git', '-C', str(repo), '-c', 'core.fileMode=false', 'diff', '--quiet', 'HEAD']).returncode
        if rc:
            failures.append(f'{repo_name}: tracked content differs from HEAD')
        checks.append({'repository': repo_name, 'head': head, 'tracked_content_clean': rc == 0})
    for row in rows:
        folder = ROOT / row['run_folder']
        launch = json.loads((folder / 'launch.json').read_text())
        context = ROOT / launch['project_context']
        manifest = json.loads((context / 'input-manifest.json').read_text())
        case = json.loads((context / 'case.json').read_text())
        if digest(context / 'input.tar') != manifest['input_tar_sha256']:
            failures.append(f"{row['case_id']}: staged input hash mismatch")
        with tarfile.open(context / 'input.tar') as archive:
            files = {x.name.removeprefix('./'): x for x in archive.getmembers() if x.isfile()}
            if case['harness_location'] == 'intree':
                harness = 'harness/' + case['harness_files'][0]
            else:
                suffix = '/'.join(Path(case['harness_files'][0]).parts[2:])
                harness = 'harness/oss-fuzz/' + suffix
                if harness not in files:
                    harness = 'harness/oss-fuzz-project/' + suffix
            if harness not in files:
                failures.append(f"{row['case_id']}: expected original harness not found: {harness}")
                expected_hash = None
            else:
                expected_hash = hashlib.sha256(archive.extractfile(files[harness]).read()).hexdigest()
            if any(x.endswith('label.json') or '/verification/' in x for x in files):
                failures.append(f"{row['case_id']}: evaluation labels in staged archive")
        for phase, status in row['build_phases'].items():
            if status['harness_sha256'] != expected_hash:
                failures.append(f"{row['case_id']} {phase}: old harness content changed")
            if status['fi_commit'] != provenance['fuzz_introspector']['commit']:
                failures.append(f"{row['case_id']} {phase}: FI commit differs")
            if status['official_compile_sha256'] != '305afe5c34fb7fc11ce629415218079a2d8d236448cb5a879e1ffa45d79cb565':
                failures.append(f"{row['case_id']} {phase}: official compile differs")
            if status['compile_returncode'] == 0 and not status['target_is_elf']:
                failures.append(f"{row['case_id']} {phase}: successful build has no declared ELF target")
        if row['build_phases'].get('introspector', {}).get('compile_returncode') == 0:
            if row['harness_target'] not in row['native_profiles']:
                failures.append(f"{row['case_id']}: native report lacks the declared compiled target profile")
        for field, hash_field in [('native_report', 'report_sha256'), ('native_summary', 'summary_sha256')]:
            if row[field] and digest(ROOT / row[field]) != row[hash_field]:
                failures.append(f"{row['case_id']}: report integrity mismatch")
        if row['maintenance_prediction'] is not None or row['classification_metrics'] is not None:
            failures.append(f"{row['case_id']}: unexpected local classification")
        checks.append({'case_id': row['case_id'], 'phases_checked': sorted(row['build_phases']), 'harness_sha256': expected_hash})
    result = {'passed': not failures, 'case_count': len(rows), 'failures': failures, 'checks': checks}
    (ROOT / 'experiment/results/validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'case_count': len(rows), 'failures': failures}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
