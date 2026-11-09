#!/usr/bin/env python3
"""Judgement experiments of plan §5: compile matrix, corpus replay, budgeted fuzz, line coverage.

All functions raise ExpError when a precondition fails (no silent pass on empty data)."""
import glob, json, os, re, shutil, subprocess, time, zipfile, hashlib, random
import sys
sys.path.insert(0, os.path.dirname(__file__))
import ossbuild

HD = ossbuild.HD
CACHE = f'{HD}/cache'
os.makedirs(CACHE, exist_ok=True)

# Reduced budget B (user-approved): 3 seeds x 600 s, exec threshold scaled from 1e6/h
SEED_SECS = int(os.environ.get('HD_SEED_SECS', 600))
EXEC_MIN = int(1_000_000 * SEED_SECS / 3600)
REPLAY_MAX = int(os.environ.get('HD_REPLAY_MAX', 600))


class ExpError(Exception):
    pass


def key(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def build(project, sha, mode, overlays=(), oss_rev=None, oss_overlays=(), patches=(), target=None):
    """cached build; returns result dict with 'out' dir"""
    k = key(project, sha, mode, list(overlays), oss_rev, list(oss_overlays),
            [open(p).read() for p in patches], target)
    out = f'{CACHE}/b_{project}_{k}'
    rj = f'{out}/result.json'
    if os.path.exists(rj):
        r = json.load(open(rj))
    else:
        r = ossbuild.build(project, sha, out, mode, overlays, oss_overlays, patches, oss_rev,
                           harness_filter=target)
    r['out'] = out
    return r


def seed_corpus(build_out, target, dst):
    """unpack <target>_seed_corpus.zip (or any seed zip) produced by the build"""
    os.makedirs(dst, exist_ok=True)
    zips = [f'{build_out}/{target}_seed_corpus.zip'] + sorted(glob.glob(f'{build_out}/*seed_corpus.zip'))
    for z in zips:
        if os.path.exists(z):
            try:
                with zipfile.ZipFile(os.path.realpath(z)) as zf:
                    for i, n in enumerate(zf.namelist()):
                        if n.endswith('/'):
                            continue
                        data = zf.read(n)
                        if len(data) > 1 << 20:
                            continue
                        open(f'{dst}/{hashlib.sha1(data).hexdigest()}', 'wb').write(data)
            except zipfile.BadZipFile:
                pass
            break
    return len(os.listdir(dst))


def run_fuzz(binary, corpus_in, out_dir, seed, secs=SEED_SECS, extra=()):
    """libFuzzer for `secs` wall seconds, restarting after crashes; returns stats"""
    os.makedirs(out_dir, exist_ok=True)
    art = out_dir + '_artifacts/'
    os.makedirs(art, exist_ok=True)
    t_end = time.time() + secs
    execs, crashes, restarts = 0, 0, 0
    while True:
        left = int(t_end - time.time())
        if left < 2:
            break
        cmd = [binary, f'-seed={seed + restarts}', f'-max_total_time={left}', '-print_final_stats=1',
               '-rss_limit_mb=2560', '-timeout=10', '-max_len=65536', f'-artifact_prefix={art}',
               *extra, out_dir] + ([corpus_in] if corpus_in and os.path.isdir(corpus_in) else [])
        p = subprocess.run(cmd, capture_output=True, text=True, errors='replace', timeout=left + 120)
        m = re.findall(r'stat::number_of_executed_units:\s*(\d+)', p.stderr)
        if m:
            execs += int(m[-1])
        else:
            m2 = re.findall(r'#(\d+)\s', p.stderr)
            execs += int(m2[-1]) if m2 else 0
        if p.returncode != 0:
            crashes += 1
            restarts += 1
            if restarts > 200:
                break
            continue
        break
    return {'seed': seed, 'secs': secs, 'execs': execs, 'crash_restarts': crashes,
            'corpus_size': len(os.listdir(out_dir)), 'artifacts': len(os.listdir(art))}


def collect_profile(cov_bin, inputs_dir, profdata):
    """run coverage binary over all inputs; robust to crashing inputs"""
    tmp = profdata + '.raw'
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    files = sorted(glob.glob(f'{inputs_dir}/*'))
    if not files:
        raise ExpError(f'empty input set {inputs_dir}')
    env = dict(os.environ, LLVM_PROFILE_FILE=f'{tmp}/all-%p.profraw')
    p = subprocess.run([cov_bin, '-runs=0', '-timeout=20', '-rss_limit_mb=2560', inputs_dir],
                       env=env, capture_output=True, timeout=3600)
    if p.returncode != 0 or not glob.glob(f'{tmp}/*.profraw'):
        shutil.rmtree(tmp); os.makedirs(tmp)
        # per-file fallback in chunks
        for i in range(0, len(files), 50):
            chunk = files[i:i + 50]
            for f in chunk:
                env = dict(os.environ, LLVM_PROFILE_FILE=f'{tmp}/f{i}-%p.profraw')
                subprocess.run([cov_bin, '-runs=1', '-timeout=20', '-rss_limit_mb=2560', f], env=env,
                               capture_output=True, timeout=120)
    raws = glob.glob(f'{tmp}/*.profraw')
    if not raws:
        raise ExpError('no profile produced')
    # merge in batches
    p = subprocess.run(['llvm-profdata', 'merge', '-sparse', '-o', profdata] + raws, capture_output=True, text=True)
    if p.returncode:
        raise ExpError('profdata merge failed: ' + p.stderr[:300])
    shutil.rmtree(tmp)
    return len(files)


def line_cov(cov_bin, profdata, path_suffix, branches=False):
    """{line: count} for the source file whose path ends with path_suffix (None if not instrumented);
    with branches=True returns {line: [taken counts of each BRDA entry in order]}"""
    p = subprocess.run(['llvm-cov', 'export', '-format=lcov', f'-instr-profile={profdata}', cov_bin],
                       capture_output=True, text=True, errors='replace')
    if p.returncode:
        raise ExpError('llvm-cov export failed: ' + p.stderr[:300])
    cur, res, found = None, {}, False
    for line in p.stdout.splitlines():
        if line.startswith('SF:'):
            cur = line[3:]
            if cur.endswith('/' + path_suffix) or cur == path_suffix:
                found = True
            else:
                cur = None
        elif cur and line.startswith('DA:') and not branches:
            ln, c = line[3:].split(',')[:2]
            res[int(ln)] = res.get(int(ln), 0) + int(c)
        elif cur and line.startswith('BRDA:') and branches:
            ln, blk, br, taken = line[5:].split(',')
            res.setdefault(int(ln), []).append(0 if taken == '-' else int(taken))
    return res if found else None


def gap_cov(cov_bin, profdata, gap):
    """gap = {'file': path, 'lines': [..]} or {'file', 'branches': [[line, idx], ..]}
    -> {'instrumented': bool, 'hits': {...}, 'covered_lines': n, 'total_lines': m}"""
    if gap.get('branches'):
        bc = line_cov(cov_bin, profdata, gap['file'], branches=True)
        if bc is None:
            return {'instrumented': False, 'hits': {}, 'covered_lines': 0, 'total_lines': len(gap['branches'])}
        hits = {f'{l}#{i}': (bc.get(l, [])[i] if i < len(bc.get(l, [])) else None) for l, i in gap['branches']}
        meas = {k: c for k, c in hits.items() if c is not None}
        return {'instrumented': bool(meas), 'hits': hits, 'kind': 'branch',
                'covered_lines': sum(1 for c in meas.values() if c > 0), 'total_lines': len(meas),
                'all_branches_on_lines': {l: bc.get(l) for l, _ in gap['branches']}}
    lc = line_cov(cov_bin, profdata, gap['file'])
    if lc is None:
        return {'instrumented': False, 'hits': {}, 'covered_lines': 0, 'total_lines': len(gap['lines'])}
    hits = {l: lc.get(l) for l in gap['lines']}
    meas = {l: c for l, c in hits.items() if c is not None}
    if not meas:
        return {'instrumented': False, 'hits': hits, 'covered_lines': 0, 'total_lines': len(gap['lines'])}
    return {'instrumented': True, 'hits': hits, 'covered_lines': sum(1 for c in meas.values() if c > 0),
            'total_lines': len(meas)}


def replay(binary, inputs_dir, mode='separate', timeout=20):
    """replay corpus on an ASan build. mode separate = one process per input; sequential = one process"""
    files = sorted(glob.glob(f'{inputs_dir}/*'))
    if not files:
        raise ExpError('empty replay corpus')
    if mode == 'separate' and len(files) > REPLAY_MAX:
        # deterministic subsample (sorted by content hash name) to bound per-process replay cost
        step = len(files) / REPLAY_MAX
        files = [files[int(i * step)] for i in range(REPLAY_MAX)]
    res = []
    if mode == 'separate':
        for f in files:
            p = subprocess.run([binary, '-runs=1', f'-timeout={timeout}', '-rss_limit_mb=2560', f],
                               capture_output=True, text=True, errors='replace', timeout=timeout * 3 + 30)
            res.append(classify(p.returncode, p.stderr, os.path.basename(f)))
    else:
        p = subprocess.run([binary, '-runs=0', f'-timeout={timeout}', '-rss_limit_mb=2560', inputs_dir],
                           capture_output=True, text=True, errors='replace', timeout=3600)
        res.append(classify(p.returncode, p.stderr, '<sequential>'))
    return res


def classify(rc, err, name):
    if rc == 0:
        return {'input': name, 'status': 'ok'}
    kind = 'crash'
    m = re.search(r'ERROR: (AddressSanitizer|LeakSanitizer|UndefinedBehaviorSanitizer|libFuzzer)[: ]+([\w-]+)', err)
    if m:
        kind = f'{m.group(1)}:{m.group(2)}'
    elif 'Assertion' in err:
        kind = 'assertion'
    elif 'terminate called' in err or 'uncaught' in err.lower():
        kind = 'uncaught_exception'
    frames = re.findall(r'#\d+ 0x[0-9a-f]+ in (\S+) (\S+)', err)[:6]
    am = re.search(r'(Assertion .*?failed\.?|terminate called after throwing.*|what\(\): .*)', err)
    return {'input': name, 'status': 'crash', 'kind': kind, 'rc': rc,
            'top_frames': [f'{fn} {loc.split("/")[-1]}' for fn, loc in frames],
            'message': am.group(1)[:200] if am else None}


def fuzz_many(tasks, jobs=2):
    """tasks: list of (fuzz_bin, seed_dir, out_dir, seed, secs); run on a shared worker pool"""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(jobs) as ex:
        return list(ex.map(lambda t: run_fuzz(t[0], t[1], t[2], t[3], t[4]), tasks))


def measure(stats, cov_bin, workdir, gaps):
    per = []
    for st in stats:
        s = st['seed']
        cdir = f'{workdir}/corpus_s{s}'
        if not os.listdir(cdir):
            raise ExpError(f'seed {s}: empty corpus')
        prof = f'{workdir}/s{s}.profdata'
        st['replayed_inputs'] = collect_profile(cov_bin, cdir, prof)
        st['gaps'] = [gap_cov(cov_bin, prof, g) for g in gaps]
        st['exec_ok'] = st['execs'] >= EXEC_MIN
        per.append(st)
    return per


def fuzz_campaign(fuzz_bin, cov_bin, seed_dir, workdir, gaps, seeds=(1, 2, 3), secs=SEED_SECS, jobs=2):
    """run seeds (parallel `jobs`), then measure gap coverage per seed on the cov build"""
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(workdir, exist_ok=True)
    with ThreadPoolExecutor(jobs) as ex:
        stats = list(ex.map(lambda s: run_fuzz(fuzz_bin, seed_dir, f'{workdir}/corpus_s{s}', s, secs), seeds))
    per = []
    for st in stats:
        s = st['seed']
        cdir = f'{workdir}/corpus_s{s}'
        if not os.listdir(cdir):
            raise ExpError(f'seed {s}: empty corpus')
        prof = f'{workdir}/s{s}.profdata'
        n = collect_profile(cov_bin, cdir, prof)
        st['replayed_inputs'] = n
        st['gaps'] = [gap_cov(cov_bin, prof, g) for g in gaps]
        st['exec_ok'] = st['execs'] >= EXEC_MIN
        per.append(st)
    return per
