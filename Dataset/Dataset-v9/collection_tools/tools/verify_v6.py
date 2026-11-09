#!/usr/bin/env python3
"""Independent re-check of a v6 dataset root (layout rules + strict v3 checks that can be re-run
from git without re-fuzzing).  Handles native v3 samples and samples imported from MiniDataset-v5.
Exit code 1 on any ERROR; WARN lines are reported but do not fail.

usage: verify_v6.py [DATASET_ROOT]"""
import json, os, re, subprocess, sys, hashlib, csv

HD = '/home/claude/hd'
ROOT = sys.argv[1] if len(sys.argv) > 1 else f'{HD}/Dataset-v6/dataset'
PROJ = json.load(open(f'{HD}/tools/projects.json'))
# local clones for projects not in projects.json (imported samples); None = repo not reachable here
EXTRA_REPOS = {'postgresql': 'postgresql', 'libexpat': 'libexpat', 'binutils-gas': 'binutils-gdb'}
TYPES = ['api', 'configuration', 'input_format', 'state', 'lifecycle', 'mix']
errors, warns = [], []


def err(m): errors.append(m)
def warn(m): warns.append(m)


def git(repo, *a, binary=False):
    r = subprocess.run(['git', '-C', repo, *a], capture_output=True)
    return r.returncode, (r.stdout if binary else r.stdout.decode('utf-8', 'replace'))


def repo_of(project):
    if project in PROJ:
        return f"{HD}/repos/{PROJ[project]['repo']}"
    r = EXTRA_REPOS.get(project)
    return f'{HD}/repos/{r}' if r else None


def canon(url):
    return (url or '').rstrip('/').lower().replace('.git', '')


def cells():
    for vis in ('explicit', 'silent'):
        for intro in ('introduced', 'preexisting'):
            for t in TYPES:
                yield ('positive', vis, intro, t), f'positive/{vis}/{intro}/{t}', 1
        for t in TYPES:
            yield ('negative', vis, None, t), f'negative/{vis}/{t}', 2


def in_window(repo, M, w):
    s, e = w['start_commit'], w['end_commit']
    if s.startswith('oss:') or s == 'harness-creation':
        return None                      # window bounds live in another repository: cannot decide here
    if git(repo, 'merge-base', '--is-ancestor', s, M)[0]:
        return False
    if e in ('', 'HEAD'):
        return True
    if e.startswith('oss:'):
        return None
    return git(repo, 'merge-base', '--is-ancestor', e, M)[0] != 0


def main():
    cases = f'{ROOT}/cases'
    allowed = {p for _, p, _ in cells()}
    for dp, dn, fn in os.walk(cases):
        rel = os.path.relpath(dp, cases)
        if rel == '.':
            if set(dn) - {'positive', 'negative'}: err(f'bad top-level dirs {set(dn)}')
            continue
        if rel in allowed:
            for d in dn:
                if not re.match(r'^V\d-\d\d_[A-Za-z0-9_.+-]+_[0-9a-f]{7,12}$', d):
                    err(f'bad sample dir name {rel}/{d}')
            dn[:] = []
            continue
        if not any(a.startswith(rel + '/') for a in allowed):
            err(f'unexpected directory {rel}')
    samples, counts = [], {}
    for key, path, need in cells():
        d = f'{cases}/{path}'
        if not os.path.isdir(d):
            err(f'missing cell directory {path}'); continue
        items = sorted(x for x in os.listdir(d) if os.path.isdir(f'{d}/{x}'))
        counts[path] = (len(items), need)
        for it in items:
            samples.append((key, path, f'{d}/{it}'))
    ds = json.load(open(f'{ROOT}/dataset.json')) if os.path.exists(f'{ROOT}/dataset.json') else None
    if ds is None:
        err('dataset.json missing')
    windows = list(csv.DictReader(open(f'{ROOT}/known_windows.csv'))) if os.path.exists(f'{ROOT}/known_windows.csv') else []
    seen_commit, seen_patch, seen_event, seen_dir = {}, {}, {}, {}
    quad_repo, repo_count = {}, {}
    for key, path, sd in samples:
        name = os.path.basename(sd); sid = name
        dir_id = name.split('_')[0]
        seen_dir.setdefault(dir_id, []).append(name)
        for f in ('label.json', 'meta.json', 'case.json', 'input/change.diff'):
            if not os.path.exists(f'{sd}/{f}'): err(f'{sid}: missing {f}')
        if not os.path.exists(f'{sd}/NOTES.md'): warn(f'{sid}: no NOTES.md')
        if not os.path.isdir(f'{sd}/input/source') or not os.path.isdir(f'{sd}/input/harness'):
            err(f'{sid}: missing input/source or input/harness')
        try:
            lab = json.load(open(f'{sd}/label.json')); meta = json.load(open(f'{sd}/meta.json'))
        except Exception as e:
            err(f'{sid}: bad json {e}'); continue
        imported = 'MiniDataset-v5' in str((meta.get('provenance') or {}).get('dataset', ''))
        label, vis, intro, typ = key
        exp_intro = None if label == 'negative' else (intro == 'introduced')
        if lab['label'] != label: err(f'{sid}: label {lab["label"]} != path {label}')
        if lab['need_visibility'] != vis: err(f'{sid}: visibility mismatch')
        if lab['introduced_by_this_change'] != exp_intro: err(f'{sid}: introduced mismatch')
        if lab['degradation_type'] != typ: err(f'{sid}: type mismatch')
        if typ == 'mix':
            mc = lab.get('mix_components') or []
            if len(mc) < 2 or 'mix' in mc or any(c not in TYPES for c in mc): err(f'{sid}: bad mix_components {mc}')
        elif lab.get('mix_components'):
            err(f'{sid}: mix_components on non-mix sample')
        if lab['id'] != dir_id: warn(f'{sid}: internal id {lab["id"]} differs from directory prefix {dir_id}')
        cj = open(f'{sd}/case.json').read()
        for leak in ('positive', 'negative', '"label"', 'introduced_by', 'degradation_type'):
            if leak in cj: err(f'{sid}: case.json leaks label field {leak}')
        p = meta['project']; cr = canon(lab.get('canonical_repo') or meta.get('upstream'))
        repo_count.setdefault(cr, []).append(sid)
        quad_repo.setdefault((label, vis), {}).setdefault(cr, []).append(sid)
        M, P = meta['M'], meta['M_parent']
        k = (cr, M)
        if k in seen_commit: err(f'{sid}: commit reused by {seen_commit[k]}')
        seen_commit[k] = sid
        pid = (lab.get('uniqueness') or {}).get('patch_id')
        if pid:
            if pid in seen_patch: err(f'{sid}: patch-id equals {seen_patch[pid]}')
            seen_patch[pid] = sid
        if label == 'positive' and lab.get('event_key'):
            ek = (cr, lab['event_key']['harness'], lab['event_key']['gap_signature'])
            seen_event.setdefault(ek, []).append((sid, exp_intro))
        if not lab.get('urls', {}).get('M'): err(f'{sid}: missing URL')
        repo = repo_of(p)
        h = meta['harness']
        if not repo or not os.path.isdir(repo):
            warn(f'{sid}: upstream repo not available locally -> git-level checks (mainline, M^1, harness, diff, blobs, windows) skipped')
            continue
        rc, par = git(repo, 'show', '-s', '--format=%P', M)
        if rc or not par.split() or par.split()[0] != P: err(f'{sid}: M^1 mismatch')
        rc, fp = git(repo, 'rev-list', '--first-parent', 'origin/HEAD' if git(repo, 'rev-parse', '-q', '--verify', 'origin/HEAD')[0] == 0 else 'HEAD')
        fps = set(fp.split())
        if M not in fps or P not in fps: err(f'{sid}: not on first-parent mainline')
        if h['kind'] == 'intree':
            for f in h['files']:
                for rev in (P, M):
                    rc, out = git(repo, 'show', f'{rev}:{f}', binary=True)
                    if rc or not out.strip(): err(f'{sid}: harness {f} missing at {rev[:10]}')
        else:
            for f in h['files']:
                rc, out = git(f'{HD}/oss-fuzz', 'show', f"{h['oss_rev']}:{f}", binary=True)
                if rc or not out.strip(): err(f'{sid}: oss harness {f} missing at {h["oss_rev"][:10]}')
        d = open(f'{sd}/input/change.diff', 'rb').read()
        if imported and d.startswith(b'commit '):          # imported diff not yet converted to git diff
            rc, ref = git(repo, 'show', '--format=fuller', M, binary=True)
            norm = lambda b: re.sub(rb'(?m)^index [0-9a-f]+\.\.[0-9a-f]+', b'index', b)   # abbrev length varies
            if norm(d) != norm(ref):
                err(f'{sid}: change.diff differs from `git show --format=fuller M` (imported format)')
        elif lab['change_origin'] == 'real_commit':
            rc, ref = git(repo, 'diff', '--binary', '--full-index', P, M, binary=True)
            if d != ref: err(f'{sid}: change.diff differs from git diff')
        else:
            excl = [f':(exclude){f}' for f in h['files'] + h.get('aux_files', [])]
            rc, ref = git(repo, 'diff', '--binary', '--full-index', P, M, '--', '.', *excl, binary=True)
            if d != ref: err(f'{sid}: change.diff differs from git diff (R2 lib hunks)')
        bh = f'{sd}/verification/source_blobs.json'
        if os.path.exists(bh) or imported:
            got = {}
            for dp, dn, fn in os.walk(f'{sd}/input/source'):
                for fl in fn:
                    pth = os.path.join(dp, fl)
                    if os.path.islink(pth): continue
                    data = open(pth, 'rb').read()
                    got[os.path.relpath(pth, f'{sd}/input/source')] = hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()
            if os.path.exists(bh) and got != json.load(open(bh)):
                err(f'{sid}: source blob hashes differ from recorded source_blobs.json')
            rc, ls = git(repo, '-c', 'core.quotepath=off', 'ls-tree', '-r', '-z', M, binary=True)
            hfiles = set(h['files'] + h.get('aux_files', [])) if h['kind'] == 'intree' and not imported else set()
            mism, missing = 0, 0
            for line in ls.split(b'\0'):
                if not line: continue
                meta_, path_ = line.split(b'\t', 1)
                path_ = path_.decode('utf-8', 'surrogateescape')
                mode, typ_, sha = meta_.decode().split()
                if typ_ != 'blob' or path_ in hfiles or mode == '120000': continue
                if path_ not in got: missing += 1
                elif got[path_] != sha: mism += 1
            if mism or missing:
                (warn if imported else err)(f'{sid}: source tree vs git tree at M: {missing} missing, {mism} differing files')
        else:
            err(f'{sid}: no source_blobs.json')
        if label == 'negative':
            for w in windows:
                same_repo = canon(w['project']) in (canon(p), cr.split('/')[-1]) or \
                    {w['project'], p} <= {'expat', 'libexpat'}
                if same_repo and w['harness'] in h['files']:
                    iw = in_window(repo, M, w)
                    if iw: err(f'{sid}: negative inside known window "{w["event"]}" ({w["start_commit"]}..{w["end_commit"]})')
                    elif iw is None: warn(f'{sid}: cannot decide window "{w["event"]}" (bounds in another repo)')
        ver = lab.get('verification', {})
        if not imported:
            if not ver.get('compile_matrix'): err(f'{sid}: no compile matrix')
            for kk, vv in ver.items():
                if kk.startswith('fuzz_') and not kk.endswith('_replay') and isinstance(vv, dict):
                    for s in vv.get('without_fix', []):
                        if not s.get('exec_ok'): err(f'{sid}: seed {s["seed"]} below exec threshold')
    for dir_id, names in seen_dir.items():
        if len(names) > 1: warn(f'directory id {dir_id} used by {names}')
    for ek, lst in seen_event.items():
        if len(lst) > 2 or (len(lst) == 2 and lst[0][1] == lst[1][1]): err(f'event {ek[:2]} used by {lst}')
    for (lab_, vis_), m in quad_repo.items():
        for r, ids in m.items():
            if len(ids) > 1: err(f'R-cap: {r} appears {len(ids)}x in quadrant {lab_}/{vis_}: {ids}')
    for r, ids in repo_count.items():
        if len(ids) > max(2, int(0.1 * 48)): err(f'R-cap: {r} has {len(ids)} samples (> 10% of 48)')
    if ds:
        gaps = {g['cell']: g for g in ds.get('gaps', [])}
        overs = {o['cell']: o for o in ds.get('overfull_cells', [])}
        if ds.get('size') != len(samples): err(f"dataset.json size {ds.get('size')} != {len(samples)} sample dirs")
        listed = {s['dir'] for s in ds.get('samples', [])}
        actual = {os.path.basename(sd) for _, _, sd in samples}
        if listed != actual: err(f'dataset.json samples differ from cases/: missing {actual - listed}, extra {listed - actual}')
        for k, (have, need) in counts.items():
            if have < need and (k not in gaps or gaps[k]['missing'] != need - have):
                err(f'cell {k} short ({have}/{need}) but not registered in dataset.json gaps')
            if have > need and (k not in overs or overs[k]['extra'] != have - need):
                err(f'cell {k} overfull ({have}/{need}) but not registered in dataset.json overfull_cells')
            if have == need and (k in gaps or k in overs):
                err(f'cell {k} complete but still registered as gap/overfull')
    short = sum(1 for h_, n in counts.values() if h_ < n); over = sum(1 for h_, n in counts.values() if h_ > n)
    print(f'samples: {len(samples)}; cells short: {short}; cells overfull: {over}')
    for w in warns: print('WARN ', w)
    for e in errors: print('ERROR', e)
    print('verify:', 'FAIL' if errors else 'PASS')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
