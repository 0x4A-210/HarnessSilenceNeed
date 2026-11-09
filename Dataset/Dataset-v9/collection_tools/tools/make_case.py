#!/usr/bin/env python3
"""Build one dataset sample from a spec (specs/<ID>.json): strict checks -> experiments -> files.

Spec keys
  id, project, label(positive|negative), visibility(explicit|silent), introduced(true|false|null)
  type, mix_components?, origin(real_commit|real_commit_lib_hunks_only)
  M      : real commit (origin real_commit) or coupled commit C (origin lib_hunks_only)
  harness: {kind: intree|oss, files: [...], target: binary, oss_rev?: pinned oss-fuzz rev}
  H?     : {where: project|oss, sha}          maintainer fix (gt maintainer_fix)
  delta_h?: path to counterfactual diff (relative to $SRC, -p1)
  gap?   : [{file, lines:[...]}]               silent positives (lines at M)
  gap_parent?: [{file, lines}]                 same gap at M^1 (preexisting)
  neg_lines?: [{file, lines}]                  negatives: changed lines that must be covered
  explicit_kind?: compile|replay
  replay_mode?: separate|sequential
  discovery_route, gt_source, rationale_zh, rationale_en, evidence[], blockers[]
"""
import json, os, re, shutil, subprocess, sys, glob, hashlib, time
sys.path.insert(0, os.path.dirname(__file__))
import ossbuild, exp

HD = ossbuild.HD
OUTROOT = os.environ.get('HD_OUTROOT', f'{HD}/dataset/cases')
WORK = f'{HD}/work'
URLS = {'nlohmann-json': 'https://github.com/nlohmann/json', 'cjson': 'https://github.com/DaveGamble/cJSON', 'json-c': 'https://github.com/json-c/json-c',
        'expat': 'https://github.com/libexpat/libexpat', 'pcre2': 'https://github.com/PCRE2Project/pcre2',
        'utf8proc': 'https://github.com/JuliaStrings/utf8proc', 'tinyobjloader': 'https://github.com/tinyobjloader/tinyobjloader',
        'lz4': 'https://github.com/lz4/lz4', 'miniz': 'https://github.com/richgel999/miniz',
        'libyaml': 'https://github.com/yaml/libyaml', 'inih': 'https://github.com/benhoyt/inih',
        'jansson': 'https://github.com/akheron/jansson', 'brotli': 'https://github.com/google/brotli',
        'cmark': 'https://github.com/commonmark/cmark', 'md4c': 'https://github.com/mity/md4c',
        'pugixml': 'https://github.com/zeux/pugixml', 'libucl': 'https://github.com/vstakhov/libucl',
        'zlib': 'https://github.com/madler/zlib', 'libcbor': 'https://github.com/PJK/libcbor',
        'yaml-cpp': 'https://github.com/jbeder/yaml-cpp', 'tinyxml2': 'https://github.com/leethomason/tinyxml2',
        'xz': 'https://github.com/tukaani-project/xz', 'zstd': 'https://github.com/facebook/zstd',
        'jq': 'https://github.com/jqlang/jq', 'libxml2': 'https://github.com/GNOME/libxml2',
        'c-ares': 'https://github.com/c-ares/c-ares', 'libspng': 'https://github.com/randy408/libspng',
        'openjpeg': 'https://github.com/uclouvain/openjpeg', 'libsndfile': 'https://github.com/libsndfile/libsndfile',
        'flac': 'https://github.com/xiph/flac', 'nghttp2': 'https://github.com/nghttp2/nghttp2',
        'fmt': 'https://github.com/fmtlib/fmt', 'mbedtls': 'https://github.com/Mbed-TLS/mbedtls',
        'hiredis': 'https://github.com/redis/hiredis', 'libwebp': 'https://github.com/webmproject/libwebp',
        'libpng': 'https://github.com/pnggroup/libpng', 'llhttp': 'https://github.com/nodejs/llhttp'}
OSSURL = 'https://github.com/google/oss-fuzz'


class Reject(Exception):
    pass


def git(repo, *a, check=True):
    r = subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True, errors='replace')
    if check and r.returncode:
        raise Reject(f'git {a[:3]} failed: {r.stderr[:300]}')
    return r.stdout


def gitb(repo, *a):
    r = subprocess.run(['git', '-C', repo, *a], capture_output=True)
    return r.returncode, r.stdout


def log(spec, msg):
    print(f"[{spec['id']}] {msg}", flush=True)


# ---------------------------------------------------------------- strict checks (§6)
def strict_git(spec, repo):
    v = {}
    M = git(repo, 'rev-parse', spec['M']).strip()
    parents = git(repo, 'show', '-s', '--format=%P', M).split()
    if not parents:
        raise Reject('M has no parent')
    P = parents[0]
    fp = set(git(repo, 'rev-list', '--first-parent', 'HEAD').split())
    if M not in fp:
        raise Reject('M not on HEAD first-parent mainline')
    if P not in fp:
        raise Reject('M^1 not on HEAD first-parent mainline')
    v['M'] = M; v['M_parent'] = P; v['M_on_mainline'] = True
    h = spec['harness']
    if h['kind'] == 'intree':
        for f in h['files']:
            for rev, nm in ((P, 'M^1'), (M, 'M')):
                rc, out = gitb(repo, 'show', f'{rev}:{f}')
                if rc or not out.strip():
                    raise Reject(f'harness {f} missing/empty at {nm}')
        v['harness_exists_at'] = ['M^1', 'M']
    else:
        rev = h['oss_rev']
        for f in h['files']:
            rc, out = gitb(f'{HD}/oss-fuzz', 'show', f'{rev}:{f}')
            if rc or not out.strip():
                raise Reject(f'oss harness {f} missing/empty at oss rev {rev}')
        # harness version in use at dates of M^1 and M must be that same file content
        for sha, nm in ((P, 'M^1'), (M, 'M')):
            r2 = ossbuild.oss_rev_at(PROJ(spec)['oss'], ossbuild.commit_date(repo, sha))
            for f in h['files']:
                a = gitb(f'{HD}/oss-fuzz', 'show', f'{r2}:{f}')[1]
                b = gitb(f'{HD}/oss-fuzz', 'show', f'{rev}:{f}')[1]
                if a != b:
                    v.setdefault('oss_harness_note', []).append(f'{f} at date({nm}) differs from pinned rev; pinned rev used for both')
        v['harness_exists_at'] = ['pinned oss-fuzz rev']
    # M must not modify harness files for real_commit
    changed = git(repo, 'diff', '--name-only', P, M).split()
    if spec['origin'] == 'real_commit' and h['kind'] == 'intree':
        touched = [f for f in h['files'] if f in changed]
        if touched:
            raise Reject(f'real_commit M modifies harness {touched}')
    if spec.get('H'):
        Hs = spec['H']
        if Hs['where'] == 'project':
            Hh = git(repo, 'rev-parse', Hs['sha']).strip()
            if Hh not in fp:
                raise Reject('H not on mainline')
            rc = subprocess.run(['git', '-C', repo, 'merge-base', '--is-ancestor', M, Hh]).returncode
            if rc:
                raise Reject('M is not ancestor of H')
            hd = git(repo, 'diff', Hh + '^1', Hh, '--', *Hs.get('files', h['files']))
            if not hd.strip():
                raise Reject('H does not modify the harness')
            v['H'] = Hh
        else:
            Hh = git(f'{HD}/oss-fuzz', 'rev-parse', Hs['sha']).strip()
            ofp = set(git(f'{HD}/oss-fuzz', 'rev-list', '--first-parent', 'master').split())
            if Hh not in ofp:
                raise Reject('oss H not on oss-fuzz mainline')
            hd = git(f'{HD}/oss-fuzz', 'diff', Hh + '^1', Hh, '--', *Hs.get('files', h['files']))
            if not hd.strip():
                raise Reject('oss H does not modify the harness')
            if ossbuild.commit_date(f'{HD}/oss-fuzz', Hh) < ossbuild.commit_date(repo, M):
                raise Reject('oss H older than M')
            v['H'] = Hh
        for sym in Hs.get('symbols', []):
            if sym not in hd:
                raise Reject(f'H diff lacks symbol {sym}')
        v['H_symbols_in_diff'] = Hs.get('symbols', [])
    return v


def PROJ(spec):
    return ossbuild.PROJ[spec['project']]


# ---------------------------------------------------------------- experiment helpers
def harness_overlays(spec, rev):
    """overlay in-tree harness files with their version at rev"""
    h = spec['harness']
    if h['kind'] != 'intree':
        return []
    return [f'{f}={rev}' for f in h['files'] + h.get('aux_files', [])]


def lib_state(spec, v):
    """(sha_before, sha_after, overlays_after) describing lib(M^1) and lib(M) with harness h(M^1)"""
    P, M = v['M_parent'], v['M']
    return P, M, harness_overlays(spec, P)


def bld(spec, sha, mode, overlays=(), oss_rev=None, patches=()):
    h = spec['harness']
    rev = oss_rev or h.get('oss_rev')
    r = exp.build(spec['project'], sha, mode, overlays=overlays, oss_rev=rev,
                  patches=patches, target=h['target'])
    return r


def summarize_build(r):
    return {'status': r['status'], 'sha': r.get('sha'), 'oss_rev': r.get('oss_rev'), 'mode': r.get('mode'),
            'secs': r.get('secs'), 'errors': [e[-260:] for e in r.get('errors', [])][:8],
            'overlays': r.get('overlays'), 'patches': [os.path.basename(p) for p in r.get('patches', [])]}


def corpus_for(spec, v):
    """fixed corpus decided at M^1 (§5.2): seed corpus of the M^1 build; else fuzz-generated at M^1"""
    d = f"{WORK}/{spec['id']}/corpus_Mparent"
    if os.path.isdir(d) and os.listdir(d):
        return d, json.load(open(d + '.json'))
    P = v['M_parent']
    rb = bld(spec, P, 'fuzz', harness_overlays(spec, P))
    if rb['status'] != 'ok':
        raise Reject('cannot build M^1 fuzz binary for corpus')
    n = exp.seed_corpus(rb['out'], spec['harness']['target'], d)
    src = 'project/oss-fuzz seed corpus at M^1'
    if n < 5:
        st = exp.run_fuzz(f"{rb['out']}/{spec['harness']['target']}", d if n else None, d, 7, secs=300)
        src = f'seed corpus ({n}) + 300 s libFuzzer on M^1 (seed 7, {st["execs"]} execs)'
    trig = []
    for t in spec.get('trigger_inputs', []):      # documented reproducer inputs (stored with the sample)
        dst = f"{d}/trigger_{os.path.basename(t)}"
        shutil.copy(f'{HD}/{t}', dst); trig.append(os.path.basename(dst))
    if trig:
        src += f" + {len(trig)} documented trigger input(s): {', '.join(trig)}"
    meta = {'source': src, 'size': len(os.listdir(d)), 'trigger_inputs': trig}
    json.dump(meta, open(d + '.json', 'w'))
    return d, meta


def crashes(res):
    return [r for r in res if r['status'] == 'crash']


# ---------------------------------------------------------------- per-category experiments
def run_explicit(spec, v, ver):
    P, M, ov = lib_state(spec, v)
    cm = {}
    pre = spec.get('introduced') is False and spec.get('explicit_kind', 'compile') == 'compile'
    if pre:
        # preexisting compile break: harness already broken at M^1; premise = it built before the
        # window opened (W0^1) with the same harness version, and the break was caused by W0
        W0 = git(f"{HD}/repos/{PROJ(spec)['repo']}", 'rev-parse', spec['window_start']).strip()
        # window_cause=library: same harness, older lib builds; =harness: the harness edit at W0 broke it
        hv = W0 + '^' if spec.get('window_cause') == 'harness' else P
        w = bld(spec, W0 + '^', 'plain', harness_overlays(spec, hv))
        cm[f"h({'W0^1' if hv != P else 'M^1'}) x lib(W0^1)"] = summarize_build(w)
        if w['status'] != 'ok':
            raise Reject('premise: harness did not build before the window start')
        w2 = bld(spec, W0, 'plain', harness_overlays(spec, W0 if hv != P else P))
        cm[f"h({'W0' if hv != P else 'M^1'}) x lib(W0)"] = summarize_build(w2)
        if w2['status'] == 'ok':
            raise Reject('window start W0 does not break the harness')
        rc = subprocess.run(['git', '-C', f"{HD}/repos/{PROJ(spec)['repo']}", 'merge-base', '--is-ancestor',
                             W0, P]).returncode
        if rc:
            raise Reject('W0 is not an ancestor of M^1')
        v['window_start'] = W0
    a = bld(spec, P, 'plain', ov); cm['h(M^1) x lib(M^1)'] = summarize_build(a)
    if pre:
        if a['status'] == 'ok':
            raise Reject('preexisting: harness already builds at M^1')
    elif a['status'] != 'ok':
        raise Reject('premise h(M^1) x lib(M^1) does not build')
    b = bld(spec, M, 'plain', ov); cm['h(M^1) x lib(M)'] = summarize_build(b)
    fix = fix_args(spec, v)
    if fix:
        c = bld(spec, M, 'plain', **fix); cm['h(fix) x lib(M)'] = summarize_build(c)
        if c['status'] != 'ok':
            raise Reject('fixed harness does not build against lib(M)')
    ver['compile_matrix'] = cm
    if spec.get('explicit_kind', 'compile') == 'compile':
        if b['status'] == 'ok':
            raise Reject('expected compile failure but h(M^1) x lib(M) builds')
        ver['explicit_signal'] = 'compile_failure'
        run_mix_evidence(spec, v, ver, fix)
        return
    # runtime signal: replay fixed corpus on ASan builds
    if b['status'] != 'ok':
        raise Reject('runtime-explicit case but harness does not compile at M')
    corp, cmeta = corpus_for(spec, v)
    mode = spec.get('replay_mode', 'separate')
    tgt = spec['harness']['target']
    ra = bld(spec, P, 'asan', ov); rb = bld(spec, M, 'asan', ov)
    if ra['status'] != 'ok' or rb['status'] != 'ok':
        raise Reject('asan builds failed')
    before = exp.replay(f"{ra['out']}/{tgt}", corp, mode)
    after = exp.replay(f"{rb['out']}/{tgt}", corp, mode)
    rep = {'corpus_source': cmeta['source'], 'corpus_size': cmeta['size'], 'mode': mode,
           'crashes_lib_parent': len(crashes(before)), 'crashes_lib_M': len(crashes(after)),
           'examples_M': crashes(after)[:3], 'examples_parent': crashes(before)[:3]}
    if fix:
        rf = bld(spec, M, 'asan', **fix)
        fixed = exp.replay(f"{rf['out']}/{tgt}", corp, mode)
        rep['crashes_fixed_harness_lib_M'] = len(crashes(fixed))
    ver['replay'] = rep
    want_parent_crash = spec.get('introduced') is False
    if not crashes(after):
        raise Reject('no runtime failure at M')
    if spec.get('introduced') is True and crashes(before):
        raise Reject('introduced, but failures already at M^1')
    if want_parent_crash and not crashes(before):
        raise Reject('preexisting, but no failure at M^1')
    if fix and rep['crashes_fixed_harness_lib_M'] >= len(crashes(after)):
        raise Reject('fix does not reduce failures')
    ver['explicit_signal'] = 'runtime_failure_on_replay'


def run_mix_evidence(spec, v, ver, fix):
    """for mix samples: show that a partial harness update fixing only one component still fails"""
    evs = spec.get('mix_evidence', [])
    if not evs:
        return
    P, M = v['M_parent'], v['M']
    out = []
    for ev in evs:
        base = {o.split('=')[0]: o for o in harness_overlays(spec, P)}
        for o in ev['overlay']:
            base[o.split('=')[0]] = o
        ovl = list(base.values())
        rec = {'name': ev['name'], 'component': ev['component'], 'overlays': ovl, 'expect': ev['expect']}
        cb = bld(spec, M, 'plain', ovl)
        rec['compile'] = cb['status']
        if ev['expect'] == 'compile_fail':
            if cb['status'] == 'ok':
                raise Reject(f"mix evidence {ev['name']}: expected compile failure")
        else:
            if cb['status'] != 'ok':
                raise Reject(f"mix evidence {ev['name']}: partial fix does not compile")
            corp, cmeta = corpus_for(spec, v)
            ab = bld(spec, M, 'asan', ovl)
            res = exp.replay(f"{ab['out']}/{spec['harness']['target']}", corp, spec.get('replay_mode', 'separate'))
            rec['replay_crashes'] = len(crashes(res)); rec['examples'] = crashes(res)[:3]
            rec['corpus_size'] = cmeta['size']
            if fix:
                fb = bld(spec, M, 'asan', **fix)
                res2 = exp.replay(f"{fb['out']}/{spec['harness']['target']}", corp, spec.get('replay_mode', 'separate'))
                rec['replay_crashes_full_fix'] = len(crashes(res2))
                if len(crashes(res2)) >= len(crashes(res)):
                    raise Reject(f"mix evidence {ev['name']}: full fix does not remove the failures")
            if not crashes(res):
                raise Reject(f"mix evidence {ev['name']}: partial fix shows no runtime failure")
        out.append(rec)
    ver['mix_evidence'] = out


def fix_args(spec, v):
    """build kwargs for the fixed harness: maintainer fix H or counterfactual delta_h"""
    h = spec['harness']
    if spec.get('H') and not spec.get('prefer_delta_h'):
        if spec['H']['where'] == 'project':
            return {'overlays': [f"{f}={v['H']}" for f in h['files'] + h.get('aux_files', [])]}
        return {'oss_rev': v['H']}
    if spec.get('delta_h'):
        return {'overlays': harness_overlays(spec, v['M_parent']), 'patches': [os.path.abspath(spec['delta_h'])]}
    return None


def fuzz_pair(spec, v, sha, ov, fix, gaps, tag, ver, seeds_nofix=(1, 2, 3), seeds_fix=(1, 2)):
    tgt = spec['harness']['target']
    corp, cmeta = corpus_for(spec, v)
    fb = bld(spec, sha, 'fuzz', ov); cb = bld(spec, sha, 'cov', ov)
    if fb['status'] != 'ok' or cb['status'] != 'ok':
        raise Reject(f'{tag}: fuzz/cov build failed')
    res = {'corpus_source': cmeta['source'], 'corpus_size': cmeta['size'],
           'budget': {'seeds': len(seeds_nofix), 'seconds_each': exp.SEED_SECS, 'exec_min': exp.EXEC_MIN,
                      'note': 'reduced budget (plan §5.3 asks 3x1 CPU-h); see dataset.json'}}
    wd0 = f"{WORK}/{spec['id']}/{tag}_nofix"; wd1 = f"{WORK}/{spec['id']}/{tag}_fix"
    tasks = [(f"{fb['out']}/{tgt}", corp, f'{wd0}/corpus_s{s}', s, exp.SEED_SECS) for s in seeds_nofix]
    if fix:
        fb2 = bld(spec, sha, 'fuzz', **fix); cb2 = bld(spec, sha, 'cov', **fix)
        if fb2['status'] != 'ok' or cb2['status'] != 'ok':
            raise Reject(f'{tag}: fixed-harness build failed')
        tasks += [(f"{fb2['out']}/{tgt}", corp, f'{wd1}/corpus_s{s}', s, exp.SEED_SECS) for s in seeds_fix]
    stats = exp.fuzz_many(tasks)
    n0 = len(seeds_nofix)
    res['without_fix'] = exp.measure(stats[:n0], f"{cb['out']}/{tgt}", wd0, gaps)
    if fix:
        res['with_fix'] = exp.measure(stats[n0:], f"{cb2['out']}/{tgt}", wd1, gaps)
    ver[f'fuzz_{tag}'] = res
    return res


def gap_zero(run):
    return all(g['covered_lines'] == 0 for g in run['gaps'])


def gap_hit(run):
    return any(g['covered_lines'] > 0 for g in run['gaps'])


def run_silent_positive(spec, v, ver):
    P, M, ov = lib_state(spec, v)
    cm = {}
    a = bld(spec, P, 'plain', ov); cm['h(M^1) x lib(M^1)'] = summarize_build(a)
    if a['status'] != 'ok':
        raise Reject('premise build failed')
    b = bld(spec, M, 'plain', ov); cm['h(M^1) x lib(M)'] = summarize_build(b)
    if b['status'] != 'ok':
        raise Reject('silent case must compile at M')
    fix = fix_args(spec, v)
    if not fix:
        raise Reject('silent positive needs H or delta_h')
    c = bld(spec, M, 'plain', **fix); cm['h(fix) x lib(M)'] = summarize_build(c)
    if c['status'] != 'ok':
        raise Reject('fixed harness does not build')
    ver['compile_matrix'] = cm
    r = fuzz_pair(spec, v, M, ov, fix, spec['gap'], 'M', ver)
    for s in r['without_fix']:
        if not s['exec_ok']:
            raise Reject(f"seed {s['seed']} too few execs ({s['execs']})")
        if any(not g['instrumented'] for g in s['gaps']) and not spec.get('gap_static_ok'):
            pass
    if not all(gap_zero(s) for s in r['without_fix']):
        raise Reject('gap covered without fix -> not a silent positive')
    if sum(1 for s in r['with_fix'] if gap_hit(s)) < 2:
        raise Reject('fix does not cover gap in >=2 seeds')
    if spec.get('introduced') is False:
        # M^1 check by cross-replay: the per-seed corpora of the budgeted campaigns at M are replayed
        # on h(M^1) x lib(M^1) (without fix) and on h(fix) x lib(M^1) (with fix)
        tgt = spec['harness']['target']
        fixp = fix_args_parent(spec, v)
        cb0 = bld(spec, P, 'cov', ov); cb1 = bld(spec, P, 'cov', **fixp)
        if cb0['status'] != 'ok' or cb1['status'] != 'ok':
            raise Reject('preexisting: M^1 coverage builds failed')
        gp = spec.get('gap_parent', spec['gap'])
        out = {'method': 'cross-replay of the M campaign corpora on M^1 builds', 'without_fix': [], 'with_fix': []}
        for tag, cbx, wd in (('without_fix', cb0, 'M_nofix'), ('with_fix', cb1, 'M_fix')):
            for s in r[tag]:
                cdir = f"{WORK}/{spec['id']}/{wd}/corpus_s{s['seed']}"
                prof = f"{WORK}/{spec['id']}/parent_{tag}_s{s['seed']}.profdata"
                exp.collect_profile(f"{cbx['out']}/{tgt}", cdir, prof)
                out[tag].append({'seed': s['seed'], 'gaps': [exp.gap_cov(f"{cbx['out']}/{tgt}", prof, g) for g in gp]})
        ver['fuzz_Mparent_replay'] = out
        if not all(gap_zero(s) for s in out['without_fix']):
            raise Reject('preexisting: gap covered at M^1 without fix')
        if sum(1 for s in out['with_fix'] if gap_hit(s)) < 2:
            raise Reject('preexisting: fix does not cover gap at M^1')
        ver['applies_to_parent'] = True
    else:
        ver['applies_to_parent'] = False
        ver['introduced_check'] = spec.get('introduced_check', 'gap lines are added by M (absent at M^1)')
        if spec.get('gap_parent'):
            # G existed at M^1 but was reachable: replay the fixed M^1 corpus on h(M^1) x lib(M^1)
            corp, cmeta = corpus_for(spec, v)
            cb = bld(spec, P, 'cov', ov)
            prof = f"{WORK}/{spec['id']}/parent_replay.profdata"
            exp.collect_profile(f"{cb['out']}/{spec['harness']['target']}", corp, prof)
            pc = [exp.gap_cov(f"{cb['out']}/{spec['harness']['target']}", prof, g) for g in spec['gap_parent']]
            ver['parent_reachability'] = {'corpus_source': cmeta['source'], 'gaps': pc}
            if not any(g['covered_lines'] > 0 for g in pc):
                raise Reject('introduced: G not reachable at M^1 either')
            ver['introduced_check'] = 'G present and covered at M^1 by the fixed corpus; zero at M (lost coverage)'


def fix_args_parent(spec, v):
    f = fix_args(spec, v)
    return f


def run_negative(spec, v, ver):
    P, M, ov = lib_state(spec, v)
    cm = {}
    a = bld(spec, P, 'plain', ov); cm['h(M^1) x lib(M^1)'] = summarize_build(a)
    b = bld(spec, M, 'plain', ov); cm['h(M^1) x lib(M)'] = summarize_build(b)
    if a['status'] != 'ok' or b['status'] != 'ok':
        raise Reject('negative must compile before and after')
    ver['compile_matrix'] = cm
    corp, cmeta = corpus_for(spec, v)
    tgt = spec['harness']['target']
    ra = bld(spec, P, 'asan', ov); rb = bld(spec, M, 'asan', ov)
    before = exp.replay(f"{ra['out']}/{tgt}", corp, 'separate')
    after = exp.replay(f"{rb['out']}/{tgt}", corp, 'separate')
    new = [x for x in crashes(after) if x['input'] not in {y['input'] for y in crashes(before)}]
    ver['replay'] = {'corpus_source': cmeta['source'], 'corpus_size': cmeta['size'],
                     'crashes_lib_parent': len(crashes(before)), 'crashes_lib_M': len(crashes(after)),
                     'new_crashes': new[:3]}
    if new:
        raise Reject('negative: new crashes on replay')
    cb = bld(spec, M, 'cov', ov)
    prof = f"{WORK}/{spec['id']}/replay.profdata"
    os.makedirs(os.path.dirname(prof), exist_ok=True)
    exp.collect_profile(f"{cb['out']}/{tgt}", corp, prof)
    rc = [exp.gap_cov(f"{cb['out']}/{tgt}", prof, g) for g in spec['neg_lines']]
    ver['patch_cov_replay'] = rc
    covered = sum(g['covered_lines'] for g in rc)
    total = sum(g['total_lines'] for g in rc)
    ver['patch_cov'] = round(covered / total, 3) if total else None
    if spec['visibility'] == 'silent' or covered == 0:
        r = fuzz_pair(spec, v, M, ov, None, spec['neg_lines'], 'M', ver)
        for s in r['without_fix']:
            if not s['exec_ok']:
                raise Reject('too few execs')
        hit = sum(1 for s in r['without_fix'] if gap_hit(s))
        if hit < 2:
            raise Reject('negative: changed lines not covered by >=2 seeds')
        best = max(sum(g['covered_lines'] for g in s['gaps']) for s in r['without_fix'])
        ver['patch_cov'] = round(max(covered, best) / total, 3) if total else None
    if not ver['patch_cov']:
        raise Reject('negative: patch coverage 0')


# ---------------------------------------------------------------- materialize
def materialize(spec, v, ver, cdir):
    repo = f"{HD}/repos/{PROJ(spec)['repo']}"
    P, M = v['M_parent'], v['M']
    h = spec['harness']
    inp = f'{cdir}/input'
    shutil.rmtree(cdir, ignore_errors=True)
    os.makedirs(f'{inp}/source'); os.makedirs(f'{inp}/harness')
    # source = state after the change, harness as of M^1
    ossbuild.archive(repo, M, f'{inp}/source')
    if h['kind'] == 'intree':
        for f in h['files'] + h.get('aux_files', []):
            rc, data = gitb(repo, 'show', f'{P}:{f}')
            if rc == 0:
                open(f'{inp}/source/{f}', 'wb').write(data)
                dst = f'{inp}/harness/{f}'
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, 'wb').write(data)
    oss_rev = h.get('oss_rev') or ossbuild.oss_rev_at(PROJ(spec)['oss'], ossbuild.commit_date(repo, M))
    od = f'{inp}/harness/oss-fuzz'
    if os.path.exists(od):          # in-tree harness directory already called oss-fuzz/ (e.g. libcbor)
        od = f'{inp}/harness/oss-fuzz-project'
    tmp = f'{cdir}/.tmp_oss'
    if oss_rev:
        ossbuild.archive(f'{HD}/oss-fuzz', oss_rev, tmp, [f"projects/{PROJ(spec)['oss']}"])
        shutil.copytree(f"{tmp}/projects/{PROJ(spec)['oss']}", od)
        shutil.rmtree(tmp)
    if PROJ(spec).get('custom_build'):
        os.makedirs(f'{inp}/harness/build', exist_ok=True)
        shutil.copy(f"{HD}/tools/recipes/{PROJ(spec)['custom_build']}", f'{inp}/harness/build/build.sh')
    # change.diff
    if spec['origin'] == 'real_commit':
        d = gitb(repo, 'diff', '--binary', '--full-index', P, M)[1]
    else:
        excl = [f':(exclude){f}' for f in h['files'] + h.get('aux_files', [])]
        d = gitb(repo, 'diff', '--binary', '--full-index', P, M, '--', '.', *excl)[1]
    open(f'{inp}/change.diff', 'wb').write(d)
    # verification artifacts
    os.makedirs(f'{cdir}/verification', exist_ok=True)
    if spec.get('delta_h'):
        shutil.copy(spec['delta_h'], f'{cdir}/verification/counterfactual_fix.diff')
    for t in spec.get('trigger_inputs', []):
        os.makedirs(f'{cdir}/verification/trigger_inputs', exist_ok=True)
        shutil.copy(f'{HD}/{t}', f'{cdir}/verification/trigger_inputs/')
    json.dump(ver, open(f'{cdir}/verification/experiments.json', 'w'), indent=1)
    return oss_rev


def blob_hashes(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            if os.path.islink(p):
                continue
            data = open(p, 'rb').read()
            out[os.path.relpath(p, root)] = hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()
    return out


def write_meta(spec, v, ver, cdir, oss_rev):
    repo = f"{HD}/repos/{PROJ(spec)['repo']}"
    url = URLS[spec['project']]
    P, M = v['M_parent'], v['M']
    patch_id = subprocess.run(f"git -C {repo} diff {P} {M} | git patch-id --stable", shell=True,
                              capture_output=True, text=True).stdout.split()
    files_changed = git(repo, 'diff', '--name-only', P, M).split()
    urls = {'M': f'{url}/commit/{M}', 'M_parent': f'{url}/commit/{P}',
            'harness_oss_fuzz_rev': f'{OSSURL}/tree/{oss_rev}/projects/{PROJ(spec)["oss"]}' if oss_rev else None}
    if v.get('H'):
        urls['H'] = (f'{url}/commit/{v["H"]}' if spec['H']['where'] == 'project' else f'{OSSURL}/commit/{v["H"]}')
    label = {
        'schema': '3.0',
        'id': spec['id'],
        'label': spec['label'],
        'need_visibility': spec['visibility'],
        'degradation_type': spec['type'],
        **({'mix_components': spec['mix_components']} if spec['type'] == 'mix' else {}),
        'introduced_by_this_change': spec['introduced'],
        'discovery_route': spec['discovery_route'],
        'gt_source': spec['gt_source'],
        'change_origin': spec['origin'],
        'canonical_repo': url,
        'event_key': {'harness': spec['harness']['files'][0],
                      'gap_signature': 'sha256:' + hashlib.sha256(json.dumps(spec.get('blockers', []) + [spec['harness']['files'][0]], sort_keys=True).encode()).hexdigest()} if spec['label'] == 'positive' else None,
        'uniqueness': {'patch_id': patch_id[0] if patch_id else None},
        'gap': {'lines': [f"{g['file']}:{','.join(map(str, compress(g['lines'])))}" for g in spec.get('gap', []) if g.get('lines')],
                'branches': [f"{g['file']}:" + ','.join(f'{l}#{i}' for l, i in g['branches']) for g in spec.get('gap', []) if g.get('branches')],
                'blockers': spec.get('blockers', [])} if spec['label'] == 'positive' else None,
        'evidence': spec.get('evidence', []),
        'rationale': {'zh': spec['rationale_zh'], 'en': spec['rationale_en']},
        'verification': ver,
        'urls': urls,
    }
    json.dump(label, open(f'{cdir}/label.json', 'w'), indent=1, ensure_ascii=False)
    meta = {'id': spec['id'], 'project': spec['project'], 'upstream': url, 'license_note': 'see source/ LICENSE files',
            'M': M, 'M_parent': P, 'M_date': ossbuild.commit_date(repo, M),
            'M_subject': git(repo, 'show', '-s', '--format=%s', M).strip(),
            'harness': spec['harness'], 'oss_fuzz_rev_for_build': oss_rev,
            'H': v.get('H'), 'change_origin': spec['origin'],
            'diff_stats': {'files': len(files_changed), 'files_changed': files_changed[:200]},
            'source_blob_hashes_sha1': None}
    hashes = blob_hashes(f'{cdir}/input/source')
    json.dump(hashes, open(f'{cdir}/verification/source_blobs.json', 'w'))
    meta['source_file_count'] = len(hashes)
    json.dump(meta, open(f'{cdir}/meta.json', 'w'), indent=1, ensure_ascii=False)
    case = {'id': spec['id'], 'task': 'Given the library change (input/change.diff, applied; source/ is the post-change tree) and the '
            'current fuzz harness (input/harness/), decide whether the harness is degraded and needs an update.',
            'project': spec['project'], 'harness_target': spec['harness']['target'],
            'harness_files': spec['harness']['files'], 'harness_location': spec['harness']['kind'],
            'build_script': ('input/harness/build/build.sh' if PROJ(spec).get('custom_build')
                             else 'input/harness/oss-fuzz/build.sh')}
    json.dump(case, open(f'{cdir}/case.json', 'w'), indent=1, ensure_ascii=False)
    notes = [f"# {spec['id']} — {spec['project']} @ {M[:12]}", '',
             f"- label: **{spec['label']}** / {spec['visibility']} / type `{spec['type']}`"
             + (f" {spec.get('mix_components')}" if spec['type'] == 'mix' else '')
             + f" / introduced_by_this_change = {spec['introduced']}",
             f"- change: {urls['M']} ({meta['M_subject']})",
             f"- origin: {spec['origin']}; route: {spec['discovery_route']}; gt: {spec['gt_source']}",
             f"- harness: {spec['harness']['kind']} {spec['harness']['files']} (target `{spec['harness']['target']}`)"]
    if v.get('H'):
        notes.append(f"- fix H: {urls['H']}")
    notes += ['', '## 理由', spec['rationale_zh'], '', '## Rationale', spec['rationale_en'], '',
              '## Verification summary', '```json', json.dumps(summary(ver), indent=1, ensure_ascii=False), '```']
    open(f'{cdir}/NOTES.md', 'w').write('\n'.join(notes) + '\n')


def summary(ver):
    s = {}
    for k, val in ver.items():
        if k == 'compile_matrix':
            s[k] = {kk: vv['status'] for kk, vv in val.items()}
        elif k.startswith('fuzz_'):
            s[k] = {kk: [{'seed': x['seed'], 'execs': x.get('execs', 'n/a (replay)'),
                          'gap_covered': [g['covered_lines'] for g in x['gaps']]} for x in vv]
                    for kk, vv in val.items() if kk in ('without_fix', 'with_fix')}
        elif k == 'replay':
            s[k] = {kk: vv for kk, vv in val.items() if kk.startswith('crashes') or kk == 'corpus_size'}
        elif k in ('patch_cov', 'explicit_signal', 'applies_to_parent'):
            s[k] = val
    return s


def compress(lines):
    lines = sorted(set(lines)); out = []
    for l in lines:
        if out and isinstance(out[-1], list) and out[-1][1] == l - 1:
            out[-1][1] = l
        elif out and isinstance(out[-1], int) and out[-1] == l - 1:
            out[-1] = [out[-1], l]
        else:
            out.append(l)
    return [f'{a}-{b}' if isinstance(a := x, list) and (b := x[1]) else x for x in out] if False else \
        [f'{x[0]}-{x[1]}' if isinstance(x, list) else x for x in out]


def case_dir(spec):
    if spec['label'] == 'positive':
        sub = f"positive/{spec['visibility']}/{'introduced' if spec['introduced'] else 'preexisting'}/{spec['type']}"
    else:
        sub = f"negative/{spec['visibility']}/{spec['type']}"
    return f"{OUTROOT}/{sub}/{spec['id']}_{spec['project']}_{spec['M'][:10]}"


def make(spec_path):
    spec = json.load(open(spec_path))
    repo = f"{HD}/repos/{PROJ(spec)['repo']}"
    t0 = time.time()
    v = strict_git(spec, repo)
    spec['M'] = v['M']
    log(spec, f"git checks ok (M={v['M'][:10]})")
    ver = {'strict_git': v}
    if spec['label'] == 'positive' and spec['visibility'] == 'explicit':
        run_explicit(spec, v, ver)
    elif spec['label'] == 'positive':
        run_silent_positive(spec, v, ver)
    else:
        run_negative(spec, v, ver)
    ver['budget_note'] = f'B = 3 seeds x {exp.SEED_SECS}s (reduced; plan default 3 x 3600s)'
    ver['toolchain'] = 'clang 18.1.3, compiler-rt llvmorg-18.1.3 self-built (libFuzzer/ASan/UBSan/profile)'
    cdir = case_dir(spec)
    oss_rev = materialize(spec, v, ver, cdir)
    write_meta(spec, v, ver, cdir, oss_rev)
    log(spec, f'ACCEPTED -> {os.path.relpath(cdir, HD)} ({time.time() - t0:.0f}s)')
    return cdir


if __name__ == '__main__':
    for sp in sys.argv[1:]:
        st = os.path.splitext(sp)[0] + '.status.json'
        try:
            d = make(sp)
            json.dump({'status': 'accepted', 'dir': d}, open(st, 'w'))
        except (Reject, exp.ExpError) as e:
            print(f'[{os.path.basename(sp)}] REJECTED: {e}', flush=True)
            json.dump({'status': 'rejected', 'reason': str(e)}, open(st, 'w'))
