#!/usr/bin/env python3
"""Independent re-check of the assembled dataset (layout rules + strict v3 checks that can be
re-run from git without re-fuzzing).  Exit code 1 on any violation.

Layout (dataset-directory-layout.md):
  - fixed directory names; positive: label/visibility/introduced|preexisting/type; negative: label/visibility/type
  - each sample directory's path must agree with label.json (label, need_visibility,
    introduced_by_this_change, degradation_type); mix samples need mix_components (>=2, no 'mix')
  - per-cell counts: positive 1, negative 2 (shortfalls are reported, must be registered in dataset.json)
Strict (plan §6) re-checked from git:
  1 harness exists & non-empty at M^1 (in-tree) / pinned oss rev (oss)   2 M^1 = first parent, both on mainline
  3 H relations (ancestor, mainline, touches harness)                     8 uniqueness (commit, patch-id, event)
  9 negatives outside known windows                                       11 change.diff == git diff; blob hashes
  12 URLs present
"""
import json, os, re, subprocess, sys, hashlib, glob

HD = '/home/claude/hd'
ROOT = sys.argv[1] if len(sys.argv) > 1 else f'{HD}/dataset'
PROJ = json.load(open(f'{HD}/tools/projects.json'))
TYPES = ['api', 'configuration', 'input_format', 'state', 'lifecycle', 'mix']
errors, warnings = [], []


def err(m):
    errors.append(m)


def git(repo, *a, binary=False):
    r = subprocess.run(['git', '-C', repo, *a], capture_output=True)
    return r.returncode, (r.stdout if binary else r.stdout.decode('utf-8', 'replace'))


def cells():
    for vis in ('explicit', 'silent'):
        for intro in ('introduced', 'preexisting'):
            for t in TYPES:
                yield ('positive', vis, intro, t), f'positive/{vis}/{intro}/{t}', 1
        for t in TYPES:
            yield ('negative', vis, None, t), f'negative/{vis}/{t}', 2


def main():
    cases = f'{ROOT}/cases'
    # 1. no stray directories
    allowed = {p for _, p, _ in cells()}
    for dp, dn, fn in os.walk(cases):
        rel = os.path.relpath(dp, cases)
        depth = rel.count('/') + 1 if rel != '.' else 0
        if rel == '.':
            bad = set(dn) - {'positive', 'negative'}
            if bad: err(f'bad top-level dirs {bad}')
            continue
        if rel in allowed:
            for d in dn:
                if not re.match(r'^V3-\d\d_[A-Za-z0-9_.+-]+_[0-9a-f]{7,12}$', d):
                    err(f'bad sample dir name {rel}/{d}')
            dn[:] = []      # don't descend into samples
            continue
        if not any(a.startswith(rel + '/') for a in allowed):
            err(f'unexpected directory {rel}')
    samples, counts = [], {}
    for key, path, need in cells():
        d = f'{cases}/{path}'
        if not os.path.isdir(d):
            err(f'missing cell directory {path}')
            continue
        items = sorted(x for x in os.listdir(d) if os.path.isdir(f'{d}/{x}'))
        counts[path] = (len(items), need)
        if len(items) > need:
            err(f'{path}: {len(items)} samples > {need}')
        for it in items:
            samples.append((key, path, f'{d}/{it}'))
    # 2. per-sample checks
    seen_commit, seen_patch, seen_event = {}, {}, {}
    quadrant_proj = {}
    windows = load_windows()
    for key, path, sd in samples:
        sid = os.path.basename(sd).split('_')[0]
        for f in ('label.json', 'meta.json', 'case.json', 'NOTES.md', 'input/change.diff'):
            if not os.path.exists(f'{sd}/{f}'):
                err(f'{sid}: missing {f}')
        if not os.path.isdir(f'{sd}/input/source') or not os.path.isdir(f'{sd}/input/harness'):
            err(f'{sid}: missing input/source or input/harness')
        try:
            lab = json.load(open(f'{sd}/label.json')); meta = json.load(open(f'{sd}/meta.json'))
        except Exception as e:
            err(f'{sid}: bad json {e}'); continue
        label, vis, intro, typ = key
        exp_intro = None if label == 'negative' else (intro == 'introduced')
        if lab['label'] != label: err(f'{sid}: label {lab["label"]} != path {label}')
        if lab['need_visibility'] != vis: err(f'{sid}: visibility mismatch')
        if lab['introduced_by_this_change'] != exp_intro: err(f'{sid}: introduced mismatch')
        if lab['degradation_type'] != typ: err(f'{sid}: type mismatch')
        if typ == 'mix':
            mc = lab.get('mix_components') or []
            if len(mc) < 2 or 'mix' in mc or any(c not in TYPES for c in mc):
                err(f'{sid}: bad mix_components {mc}')
        elif 'mix_components' in lab:
            err(f'{sid}: mix_components on non-mix sample')
        # case.json must not leak the label
        cj = open(f'{sd}/case.json').read()
        for leak in ('positive', 'negative', '"label"', 'introduced_by', 'degradation_type'):
            if leak in cj:
                err(f'{sid}: case.json leaks label field {leak}')
        p = meta['project']; repo = f"{HD}/repos/{PROJ[p]['repo']}"
        M, P = meta['M'], meta['M_parent']
        # strict 2
        rc, par = git(repo, 'show', '-s', '--format=%P', M)
        if par.split()[0] != P: err(f'{sid}: M^1 mismatch')
        rc, fp = git(repo, 'rev-list', '--first-parent', 'HEAD')
        fps = set(fp.split())
        if M not in fps or P not in fps: err(f'{sid}: not on mainline')
        # strict 1
        h = meta['harness']
        if h['kind'] == 'intree':
            for f in h['files']:
                for rev in (P, M):
                    rc, out = git(repo, 'show', f'{rev}:{f}', binary=True)
                    if rc or not out.strip(): err(f'{sid}: harness {f} missing at {rev[:10]}')
        else:
            for f in h['files']:
                rc, out = git(f'{HD}/oss-fuzz', 'show', f"{h['oss_rev']}:{f}", binary=True)
                if rc or not out.strip(): err(f'{sid}: oss harness {f} missing')
        # strict 3
        if meta.get('H') and lab['gt_source'] in ('maintainer_fix', 'coupled_commit'):
            Hh = meta['H']
            where = 'oss' if 'oss-fuzz' in lab['urls'].get('H', '') else 'project'
            r = f'{HD}/oss-fuzz' if where == 'oss' else repo
            rc, _ = git(r, 'cat-file', '-e', Hh)
            if rc: err(f'{sid}: H not found')
            if where == 'project':
                rc, _ = git(repo, 'merge-base', '--is-ancestor', M, Hh)
                if rc: err(f'{sid}: M not ancestor of H')
                if Hh not in fps: err(f'{sid}: H not on mainline')
        # strict 11: change.diff
        d = open(f'{sd}/input/change.diff', 'rb').read()
        if lab['change_origin'] == 'real_commit':
            rc, ref = git(repo, 'diff', '--binary', '--full-index', P, M, binary=True)
        else:
            excl = [f':(exclude){f}' for f in h['files'] + h.get('aux_files', [])]
            rc, ref = git(repo, 'diff', '--binary', '--full-index', P, M, '--', '.', *excl, binary=True)
        if d != ref: err(f'{sid}: change.diff differs from git diff')
        bh = f'{sd}/verification/source_blobs.json'
        if os.path.exists(bh):
            want = json.load(open(bh))
            got = {}
            for dp, dn, fn in os.walk(f'{sd}/input/source'):
                for fl in fn:
                    pth = os.path.join(dp, fl)
                    if os.path.islink(pth): continue
                    data = open(pth, 'rb').read()
                    got[os.path.relpath(pth, f'{sd}/input/source')] = hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()
            if got != want: err(f'{sid}: source blob hashes differ from recorded')
            # tree vs git: every tracked file of M (outside harness overlay) must match
            rc, ls = git(repo, '-c', 'core.quotepath=off', 'ls-tree', '-r', '-z', M, binary=True)
            hfiles = set(h['files'] + h.get('aux_files', [])) if h['kind'] == 'intree' else set()
            mism = 0
            for line in ls.split(b'\0'):
                if not line:
                    continue
                meta_, path_ = line.split(b'\t', 1)
                path_ = path_.decode('utf-8', 'surrogateescape')
                mode, typ_, sha = meta_.decode().split()
                if typ_ != 'blob' or path_ in hfiles or mode == '120000':
                    continue
                if got.get(path_) != sha:
                    mism += 1
            if mism: err(f'{sid}: {mism} source files differ from git tree at M')
        else:
            err(f'{sid}: no source_blobs.json')
        # strict 12
        if not lab.get('urls', {}).get('M'): err(f'{sid}: missing URL')
        # strict 8 uniqueness
        k = (p, M)
        if k in seen_commit: err(f'{sid}: commit reused by {seen_commit[k]}')
        seen_commit[k] = sid
        pid = lab['uniqueness'].get('patch_id')
        if pid in seen_patch: err(f'{sid}: patch-id equals {seen_patch[pid]}')
        seen_patch[pid] = sid
        if label == 'positive':
            ek = (p, lab['event_key']['harness'], lab['event_key']['gap_signature'])
            seen_event.setdefault(ek, []).append((sid, exp_intro))
        quad = (label, vis)
        quadrant_proj.setdefault(quad, {}).setdefault(p, []).append(sid)
        # strict 9
        if label == 'negative':
            for w in windows:
                if w['project'] == p and w['harness'] in h['files'] and in_window(repo, M, w):
                    err(f'{sid}: negative inside known window {w["event"]}')
        # verification sanity
        ver = lab.get('verification', {})
        cm = ver.get('compile_matrix', {})
        if not cm: err(f'{sid}: no compile matrix')
        if vis == 'silent' or (label == 'negative'):
            for kk, vv in ver.items():
                if kk.startswith('fuzz_') and not kk.endswith('_replay'):
                    for s in vv.get('without_fix', []):
                        if not s.get('exec_ok'): err(f'{sid}: seed {s["seed"]} below exec threshold')
    for ek, lst in seen_event.items():
        if len(lst) > 2 or (len(lst) == 2 and lst[0][1] == lst[1][1]):
            err(f'event {ek[:2]} used by {lst}')
    for quad, pj in quadrant_proj.items():
        for p, ids in pj.items():
            if len(ids) > 1:
                err(f'R-cap: project {p} appears {len(ids)}x in quadrant {quad}: {ids}')
    per_proj = {}
    for (key, path, sd) in samples:
        p = json.load(open(f'{sd}/meta.json'))['project']
        per_proj[p] = per_proj.get(p, 0) + 1
    for p, n in per_proj.items():
        if n > max(2, int(0.1 * 48)):
            err(f'R-cap: project {p} has {n} samples (> 10% of 48)')
    short = {k: v for k, v in counts.items() if v[0] < v[1]}
    ds = f'{ROOT}/dataset.json'
    if os.path.exists(ds):
        reg = {g['cell']: g for g in json.load(open(ds)).get('gaps', [])}
        for k, (have, need) in short.items():
            if k not in reg or reg[k]['missing'] != need - have:
                err(f'cell {k} short ({have}/{need}) but not registered in dataset.json')
    else:
        err('dataset.json missing')
    print(f'samples: {len(samples)}; cells short: {len(short)}')
    for e in errors:
        print('ERROR', e)
    print('verify:', 'FAIL' if errors else 'PASS')
    return 1 if errors else 0


def load_windows():
    f = f'{ROOT}/known_windows.csv'
    out = []
    if os.path.exists(f):
        import csv
        for r in csv.DictReader(open(f)):
            out.append(r)
    return out


def in_window(repo, M, w):
    s = w['start_commit']; e = w['end_commit']
    rc1, _ = git(repo, 'merge-base', '--is-ancestor', s, M)
    if rc1: return False
    if e in ('', 'HEAD'): return True
    rc2, _ = git(repo, 'merge-base', '--is-ancestor', e, M)
    return rc2 != 0          # M before end


if __name__ == '__main__':
    sys.exit(main())
