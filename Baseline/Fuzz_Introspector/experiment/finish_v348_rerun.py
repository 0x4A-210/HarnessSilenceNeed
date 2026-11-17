#!/usr/bin/env python3
"""Monitor the isolated official run, merge 47 frozen cases, score, clean up.

This process does not alter upstream analysis, inputs, or alert thresholds.
If a worker is OOM-killed, preserve diagnostics and stop the affected container
so the unmodified loader cannot hang forever with a lost semaphore permit.
"""
import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiment'
RESULTS = EXPERIMENT / 'results'
RUN = 'official-v9-gas-isolated-20261116'
CASE = EXPERIMENT / 'runs' / RUN / 'V3-48'
IMAGE = 'gcr.io/oss-fuzz/fi-v9-gas-isolated-v3-48'
ENVIRONMENT = 'fi-official-v9-environment:20261114'
RESOURCE = Path('/tmp/fi-v3-48-resources-20261116')
SNAPSHOT47 = RESULTS / 'snapshot-47-20261115-142004'
SNAPSHOT48 = RESULTS / 'snapshot-48-isolated-20261116'
STATE = RESULTS / 'v3-48-rerun-state.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def command(args, timeout=30):
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def active_containers():
    result = command(['docker', 'ps', '-q', '--filter', f'ancestor={IMAGE}'])
    if result['returncode']:
        raise RuntimeError(result)
    return result['stdout'].split()


def save_oom_and_stop(container, observation):
    diagnostics = EXPERIMENT / 'diagnostics' / f'V3-48-isolated-oom-{container}'
    diagnostics.mkdir(exist_ok=True)
    write(diagnostics / 'observation.json', observation)
    for name, args in [
        ('inspect.json', ['docker', 'inspect', container]),
        ('processes.txt', ['docker', 'exec', container, 'ps', '-eo', 'pid,ppid,etime,stat,args']),
    ]:
        result = command(args)
        (diagnostics / name).write_text(result['stdout'] + result['stderr'])
    write(CASE / 'resource-failure.json', dict(time_utc=now(), container=container,
          reason='Native container recorded an OOM kill; stop to prevent lost-semaphore indefinite wait',
          action='Stop container; preserve helper failure, no automatic fallback',
          observation=observation))
    result = command(['docker', 'stop', '--timeout', '10', container])
    write(diagnostics / 'stop.json', result)
    if result['returncode']:
        raise RuntimeError(result)


def poll_native(state):
    observations = []
    for container in active_containers():
        result = command(['docker', 'exec', container, 'sh', '-c',
                          'cat /sys/fs/cgroup/memory.events; '
                          'printf "memory_current "; cat /sys/fs/cgroup/memory.current; '
                          'printf "swap_current "; cat /sys/fs/cgroup/memory.swap.current'])
        if result['returncode']:
            continue  # A successful stage may exit between ps and exec.
        values = {}
        for line in result['stdout'].splitlines():
            parts = line.split()
            if len(parts) == 2:
                values[parts[0]] = int(parts[1])
        observation = dict(time_utc=now(), container=container, **values)
        observations.append(observation)
        with (RESULTS / 'v3-48-rerun-resource-history.jsonl').open('a') as stream:
            stream.write(json.dumps(observation) + '\n')
        if values.get('oom_kill', 0):
            save_oom_and_stop(container, observation)
            state['resource_failure_observed'] = True
    log = CASE / 'helper.log'
    state.update(last_checked_utc=now(), containers=observations,
                 helper_log_bytes=log.stat().st_size if log.exists() else 0,
                 helper_log_mtime_utc=datetime.fromtimestamp(log.stat().st_mtime, timezone.utc).isoformat() if log.exists() else None)


def run_script(name, *args):
    with (EXPERIMENT / 'logs' / f'isolated-finalize-{name}.log').open('w') as stream:
        return subprocess.run([sys.executable, str(EXPERIMENT / name), *map(str, args)],
                              cwd=ROOT.parent, stdout=stream, stderr=subprocess.STDOUT).returncode


def finalize(state):
    codes = {}
    codes['collect'] = run_script('collect.py', '--run', 'official-v9-final-20261114',
                                 '--extra-runs', 'official-v9-onig-20261114',
                                 'official-v9-xz-20261114', RUN)
    if codes['collect']:
        raise RuntimeError(f'Collection failed: {codes}')
    original = json.loads((SNAPSHOT47 / 'native-results.json').read_text())
    merged = json.loads((RESULTS / 'native-results.json').read_text())
    assert len(merged) == 48 and len({r['case_id'] for r in merged}) == 48
    for row in original:
        assert row == next(r for r in merged if r['case_id'] == row['case_id']), row['case_id']
    assert next(r for r in merged if r['case_id'] == 'V3-48')['run_folder'] == str(CASE.relative_to(ROOT))
    for name, expected in json.loads((SNAPSHOT47 / 'sha256.json').read_text()).items():
        assert digest(SNAPSHOT47 / name) == expected, name
    SNAPSHOT48.mkdir(exist_ok=True)
    for name in ('native-results.json', 'native-results.csv', 'run-summary.json'):
        shutil.copy2(RESULTS / name, SNAPSHOT48 / name)
    write(SNAPSHOT48 / 'sha256.json', {p.name: digest(p) for p in SNAPSHOT48.iterdir()
                                      if p.is_file() and p.name != 'sha256.json'})
    codes['evaluation'] = run_script('evaluate_native_alerts.py', '--expected-count', '48',
                                    '--native-results', SNAPSHOT48 / 'native-results.json')
    codes['archive'] = run_script('archive_artifacts.py')
    codes['validation'] = run_script('validate.py')
    state.update(finalization_exit_codes=codes, original_47_unchanged=True,
                 completed_samples=48, pending_samples=[])
    if any(codes.values()):
        raise RuntimeError(f'Finalization failed: {codes}')
    # Independent check of the external scores and all 48 report rows.
    import re
    rows = json.loads((RESULTS / 'evaluation-48-native-blocked/per-case.json').read_text())
    metrics = json.loads((RESULTS / 'evaluation-48-native-blocked/metrics.json').read_text())
    tp = sum(r['truth_label'] == 'positive' and r['native_blocked_alarm'] for r in rows)
    fp = sum(r['truth_label'] == 'negative' and r['native_blocked_alarm'] for r in rows)
    tn = sum(r['truth_label'] == 'negative' and not r['native_blocked_alarm'] for r in rows)
    fn = sum(r['truth_label'] == 'positive' and not r['native_blocked_alarm'] for r in rows)
    assert (tp, fp, tn, fn) == tuple(metrics['all_48'][k] for k in ('tp', 'fp', 'tn', 'fn'))
    text = (ROOT / 'REPORT-48-EVALUATION.md').read_text()
    assert len(re.findall(r'^\| V3-\d{2} \|', text, re.M)) == 48
    for link in re.findall(r'\]\(([^)]+)\)', text):
        assert (ROOT / link).exists(), link
    write(RESULTS / 'evaluation-48-native-blocked/validation.json',
          dict(checked_utc=now(), rows=48, original_47_unchanged=True,
               metric_counts_independently_verified=True, all_report_links_exist=True,
               contingency=dict(tp=tp, fp=fp, tn=tn, fn=fn)))
    state.update(all_48=metrics['all_48'], case_48=next(r for r in rows if r['case_id'] == 'V3-48'))


def cleanup():
    if active_containers():
        return {'performed': False, 'reason': 'Native analysis container still active; keep resources'}
    # Swapped pages belonging to terminated native processes have been freed.
    # Restore the original kernel setting and remove only our dedicated swap.
    result = command(['docker', 'run', '--rm', '--privileged', '-v', f'{RESOURCE}:/fi-resources',
                      ENVIRONMENT, 'bash', '-eu', '-c',
                      'sysctl -w vm.mmap_rnd_bits=32; '
                      'if [ -f /fi-resources/swapfile ]; then '
                      'swapoff /fi-resources/swapfile; rm /fi-resources/swapfile; fi; '
                      'sysctl -n vm.mmap_rnd_bits; cat /proc/swaps'], timeout=60)
    result.update(time_utc=now(), temporary_swap_file_removed=not (RESOURCE / 'swapfile').exists())
    write(RESULTS / 'v3-48-rerun-resource-cleanup.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runner-pid', type=int, required=True)
    args = parser.parse_args()
    state = dict(state='running', started_utc=now(), monitor_pid=os.getpid(), runner_pid=args.runner_pid,
                 run=RUN, completed_samples=47, pending_samples=['V3-48'],
                 additional_swap_gib=64, upstream_modified=False)
    with open('/tmp/fi-v348-isolated-finalizer.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write(STATE, state)
        try:
            while not (CASE / 'completed.json').exists():
                poll_native(state)
                write(STATE, state)
                if not Path(f'/proc/{args.runner_pid}').exists():
                    if not (CASE / 'completed.json').exists():
                        raise RuntimeError('Runner exited without a completion record')
                    break
                time.sleep(30)
            state.update(state='finalizing', native_completed_utc=now())
            write(STATE, state)
            finalize(state)
            state['state'] = 'finished'
        except Exception as error:
            state.update(state='failed', error=repr(error))
        finally:
            try:
                state['resource_cleanup'] = cleanup()
                if state['resource_cleanup'].get('returncode') != 0:
                    state['state'] = 'cleanup_pending' if state['state'] == 'finished' else state['state']
            except Exception as error:
                state['cleanup_error'] = repr(error)
                if state['state'] == 'finished':
                    state['state'] = 'cleanup_pending'
            state['finished_utc'] = now()
            write(STATE, state)
            print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
    return 0 if state['state'] == 'finished' else 1


if __name__ == '__main__':
    raise SystemExit(main())
