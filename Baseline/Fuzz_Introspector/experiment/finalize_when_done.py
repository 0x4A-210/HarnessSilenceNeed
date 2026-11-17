#!/usr/bin/env python3
"""Finish artifact collection after upstream runs exit; never classify samples."""
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiment'
RUNS = EXPERIMENT / 'runs'
RESULTS = EXPERIMENT / 'results'
BASE = 'official-v9-final-20261114'
EXTRA = ['official-v9-onig-20261114', 'official-v9-xz-20261114', 'official-v9-gas-final-20261114']
OVERRIDES = {'V3-03': EXTRA[0], 'V3-14': EXTRA[1], 'V3-48': EXTRA[2]}
EXPECTED = {f'V3-{n:02}' for n in range(1, 49)}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_state(state):
    temp = RESULTS / 'finalization-state.tmp'
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    temp.replace(RESULTS / 'finalization-state.json')


def finished():
    completed = {}
    for name in [BASE, *EXTRA]:
        for path in (RUNS / name).glob('V3-*/completed.json'):
            if (path.parent / 'superseded.txt').exists():
                continue
            case = path.parent.name
            if case in OVERRIDES and name != OVERRIDES[case]:
                continue
            completed[case] = name
    return completed


def run_script(name, *args):
    return subprocess.run([sys.executable, str(EXPERIMENT / name), *args], cwd=ROOT).returncode


def restore_kernel():
    provenance = json.loads((EXPERIMENT / 'provenance.json').read_text())
    original = int(provenance['original_vm_mmap_rnd_bits'])
    command = ['docker', 'run', '--rm', '--privileged', 'fi-official-v9-environment:20261114',
               'sysctl', '-w', f'vm.mmap_rnd_bits={original}']
    restored = subprocess.run(command, text=True, capture_output=True)
    verify = subprocess.run(['docker', 'run', '--rm', '--privileged',
                             'fi-official-v9-environment:20261114', 'sysctl', '-n',
                             'vm.mmap_rnd_bits'], text=True, capture_output=True)
    result = {'time_utc': now(), 'original_value': original, 'returncode': restored.returncode,
              'stdout': restored.stdout.strip(), 'stderr': restored.stderr.strip(),
              'observed_value': verify.stdout.strip(),
              'verified': restored.returncode == 0 and verify.returncode == 0
                          and verify.stdout.strip() == str(original)}
    (RESULTS / 'kernel-restore.json').write_text(json.dumps(result, indent=2) + '\n')
    return result['verified']


def main():
    RESULTS.mkdir(exist_ok=True)
    key = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    with open(f'/tmp/fi-finalizer-{key}.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = {'state': 'waiting', 'pid': os.getpid(), 'started_utc': now(),
                 'expected_samples': 48, 'classification_metrics': None}
        print(f'Finalizer started: pid={os.getpid()}', flush=True)
        previous = None
        while True:
            complete = finished()
            pending = sorted(EXPECTED - set(complete))
            state.update(last_checked_utc=now(), completed_samples=len(complete),
                         pending_samples=pending, selected_runs=complete)
            write_state(state)
            if pending != previous:
                print(f'{now()} completed={len(complete)} pending={pending}', flush=True)
                previous = pending
            if not pending:
                break
            time.sleep(30)
        state['state'] = 'finalizing'
        write_state(state)
        checks = {}
        try:
            checks['collection_exit'] = run_script('collect.py', '--run', BASE, '--extra-runs', *EXTRA)
            if checks['collection_exit'] == 0:
                checks['archive_exit'] = run_script('archive_artifacts.py')
                checks['validation_exit'] = run_script('validate.py')
        except Exception as error:
            state['error'] = repr(error)
        finally:
            try:
                checks['kernel_restored'] = restore_kernel()
            except Exception as error:
                checks['kernel_restored'] = False
                state['kernel_restore_error'] = repr(error)
        state.update(checks=checks, finished_utc=now())
        successful = all(checks.get(name) == 0 for name in ['collection_exit', 'archive_exit', 'validation_exit'])
        successful = successful and checks.get('kernel_restored') is True
        state['state'] = 'finished' if successful else 'finalization_failed'
        write_state(state)
        print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
        return 0 if successful else 1


if __name__ == '__main__':
    raise SystemExit(main())
