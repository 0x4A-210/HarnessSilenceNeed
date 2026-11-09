#!/usr/bin/env python3
"""Reproduce an OSS-Fuzz style build of project P at commit SHA, offline.

- project source  = `git archive SHA` of the upstream clone (repos/<P>)
- oss-fuzz files  = projects/<ossname>/ at the last oss-fuzz commit *before the
                    project commit date* (date-pinned, as the plan §2.4 asks)
- toolchain       = local clang 18 + self-built compiler-rt (recorded in result)

Overlays let us build mixed states for the compile matrix (§5.1):
  --overlay path=SHA2     replace one file of the project tree with its SHA2 version
  --overlay-oss name=REV  replace one oss-fuzz project file with its version at REV
  --patch file.diff       apply a diff (e.g. counterfactual Δh) inside $SRC

Every failure is explicit: missing harness / empty build output => status != ok.
"""
import argparse, json, os, re, shutil, subprocess, sys, time, hashlib, glob

HD = '/home/claude/hd'
REPOS = f'{HD}/repos'
OSS = f'{HD}/oss-fuzz'
EXTRA = f'{HD}/repos/_extra'

PROJ = json.load(open(f'{HD}/tools/projects.json'))

MODES = {
    # coverage build: no ASan (faster), profile instrumentation for llvm-cov
    'cov':  '-O1 -g -fno-omit-frame-pointer -gline-tables-only -fprofile-instr-generate -fcoverage-mapping -fsanitize=fuzzer-no-link',
    # crash-finding build used for replay / explicit runtime signals
    'asan': '-O1 -g -fno-omit-frame-pointer -gline-tables-only -fsanitize=address,fuzzer-no-link -fsanitize-address-use-after-scope',
    # plain (fast) build, used only for compile checks
    'plain': '-O0 -g -fsanitize=fuzzer-no-link',
    # fast fuzzing build (no sanitizer): used only to grow corpora for the coverage experiments
    'fuzz': '-O1 -g -fno-omit-frame-pointer -gline-tables-only -fsanitize=fuzzer-no-link',
}
DEF = '-DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION'


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def git(repo, *args):
    r = subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'git {args} failed: {r.stderr[:400]}')
    return r.stdout


def commit_date(repo, sha):
    return git(repo, 'show', '-s', '--format=%cI', sha).strip()


def oss_rev_at(ossname, date):
    out = git(OSS, 'rev-list', '-1', f'--before={date}', 'master', '--', f'projects/{ossname}').strip()
    return out


def archive(repo, sha, dst, paths=None):
    os.makedirs(dst, exist_ok=True)
    idx = dst.rstrip('/') + '.idx'
    cmd = (f"GIT_INDEX_FILE={idx} git -C {repo} read-tree {sha} && "
           f"GIT_INDEX_FILE={idx} git -C {repo} --work-tree={dst} checkout-index -a -f "
           + (f"&& true" if not paths else "") + f"; rc=$?; rm -f {idx}; exit $rc")
    if paths:
        cmd = f"git -C {repo} archive {sha} {' '.join(paths)} | tar -x -C {dst}"
    r = sh(cmd)
    if r.returncode:
        raise RuntimeError(f'archive {repo}@{sha} failed: {r.stderr[:300]}')
    if not paths:
        add_submodules(repo, sha, dst)


def add_submodules(repo, sha, dst):
    """populate git submodules at the gitlink commits recorded in `sha` (Dockerfiles use --recursive)"""
    gm = f'{dst}/.gitmodules'
    if not os.path.exists(gm):
        return
    cfg = sh(f'git config -f {gm} --get-regexp "submodule\\..*\\.(path|url)"').stdout.split('\n')
    mods = {}
    for line in cfg:
        if not line.strip():
            continue
        k, val = line.split(' ', 1)
        name, attr = k.rsplit('.', 1)
        mods.setdefault(name, {})[attr] = val.strip()
    for name, m in mods.items():
        path, url = m.get('path'), m.get('url')
        if not path or not url:
            continue
        ls = sh(f'git -C {repo} ls-tree {sha} -- {path}').stdout.split()
        if len(ls) < 3 or ls[1] != 'commit':
            continue
        sub_sha = ls[2]
        if url.startswith('.'):
            continue
        local = f"{REPOS}/_sub/{re.sub(r'[^A-Za-z0-9]+', '_', url)}"
        if not os.path.isdir(local):
            os.makedirs(os.path.dirname(local), exist_ok=True)
            sh(f'git clone -q --bare {url} {local}')
        if sh(f'git -C {local} cat-file -e {sub_sha}^{{commit}}').returncode:
            sh(f'git -C {local} fetch -q origin {sub_sha}')
        os.makedirs(f'{dst}/{path}', exist_ok=True)
        idx = f'{dst}/{path}.subidx'
        r = sh(f'GIT_INDEX_FILE={idx} git -C {local} read-tree {sub_sha} && '
               f'GIT_INDEX_FILE={idx} git -C {local} --work-tree={dst}/{path} checkout-index -a -f; rm -f {idx}')
        add_submodules(local, sub_sha, f'{dst}/{path}')


def build(p, sha, out, mode='cov', overlays=(), oss_overlays=(), patches=(), oss_rev=None,
          timeout=1500, keep=False, harness_filter=None):
    cfg = PROJ[p]
    repo = f"{REPOS}/{cfg['repo']}"
    sha = git(repo, 'rev-parse', sha).strip()
    date = commit_date(repo, sha)
    ossname = cfg['oss']
    oss_rev = oss_rev or oss_rev_at(ossname, date)
    if not oss_rev and not cfg.get('custom_build'):
        return {'status': 'no_ossfuzz_project_at_date', 'sha': sha, 'date': date}
    out = os.path.abspath(out)
    work = out + '.work'
    shutil.rmtree(work, ignore_errors=True); shutil.rmtree(out, ignore_errors=True)
    SRC = f'{work}/src'; WORK = f'{work}/work'
    os.makedirs(SRC); os.makedirs(WORK); os.makedirs(out)
    srcdir = f"{SRC}/{cfg['srcname']}"
    archive(repo, sha, srcdir)
    for ov in overlays:                       # path=SHA2 (or path=@/abs/file)
        path, rev = ov.split('=', 1)
        dst = f'{srcdir}/{path}'
        if rev == 'DELETE':
            if os.path.exists(dst): os.remove(dst)
            continue
        if rev.startswith('@'):
            shutil.copy(rev[1:], dst); continue
        r = subprocess.run(['git', '-C', repo, 'show', f'{rev}:{path}'], capture_output=True)
        if r.returncode:
            return {'status': 'overlay_missing', 'detail': f'{path}@{rev}', 'sha': sha}
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(r.stdout)
    # oss-fuzz project files -> $SRC (Dockerfile COPY semantics)
    tmpo = f'{work}/oss'
    if oss_rev:
        archive(OSS, oss_rev, tmpo, [f'projects/{ossname}'])
    for f in glob.glob(f'{tmpo}/projects/{ossname}/*'):
        if os.path.basename(f) in ('Dockerfile', 'project.yaml'):
            continue
        if os.path.isfile(f):
            shutil.copy(f, SRC)
    for ov in oss_overlays:
        name, rev = ov.split('=', 1)
        if rev.startswith('@'):
            shutil.copy(rev[1:], f'{SRC}/{name}')
        else:
            r = subprocess.run(['git', '-C', OSS, 'show', f'{rev}:projects/{ossname}/{name}'], capture_output=True)
            if r.returncode:
                return {'status': 'oss_overlay_missing', 'detail': ov}
            open(f'{SRC}/{name}', 'wb').write(r.stdout)
    for c in cfg.get('copy_into_src', []):    # e.g. inih: COPY inihfuzz.c $SRC/inih/
        a, b = c.split('->')
        if os.path.exists(f'{SRC}/{a}'):
            shutil.copy(f'{SRC}/{a}', f'{SRC}/{b}')
    for ex in cfg.get('extra', []):           # extra repos cloned by Dockerfile
        name, dst = ex.split('->')
        shutil.copytree(f'{EXTRA}/{name}', f'{SRC}/{dst}', symlinks=True)
    for pf in patches:
        r = sh(f'cd {SRC} && patch -p1 --no-backup-if-mismatch < {pf}')
        if r.returncode:
            return {'status': 'patch_failed', 'detail': r.stdout[-500:] + r.stderr[-300:]}
    bs = f'{SRC}/build.sh'
    if cfg.get('custom_build'):
        shutil.copy(f"{HD}/tools/recipes/{cfg['custom_build']}", bs)
    if not os.path.exists(bs):
        return {'status': 'no_build_sh'}
    txt = open(bs).read()
    for a, b in cfg.get('build_sed', []):
        txt = re.sub(a, b, txt)
    open(bs, 'w').write(txt)
    cflags = f'{MODES[mode]} {DEF} ' + cfg.get('extra_cflags', '')
    env = dict(os.environ, PATH=HD+'/bin:'+os.environ['PATH'], SRC=SRC, OUT=out, WORK=WORK, CC=HD+'/bin/clang', CXX=HD+'/bin/clang++',
               CFLAGS=cflags, CXXFLAGS=cflags, LIB_FUZZING_ENGINE='-fsanitize=fuzzer',
               SANITIZER='coverage' if mode == 'cov' else 'address', FUZZING_ENGINE='libfuzzer',
               ARCHITECTURE='x86_64', FUZZING_LANGUAGE='c++', MAKEFLAGS='-j2')
    wd = cfg.get('workdir', cfg['srcname'])
    t0 = time.time()
    try:
        r = subprocess.run(['bash', '-ux', bs],
                           cwd=f'{SRC}/{wd}', env=env, capture_output=True, text=True, timeout=timeout)
        rc, log = r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired as e:
        rc, log = -9, 'TIMEOUT'
    open(f'{out}/build.log', 'w').write(log)
    bins = sorted(os.path.basename(f) for f in glob.glob(f'{out}/*')
                  if os.path.isfile(f) and os.access(f, os.X_OK) and not f.endswith(('.sh', '.zip', '.log')))
    ok = bool(bins) if not harness_filter else (harness_filter in bins)
    res = {'status': 'ok' if ok else 'fail', 'rc': rc, 'sha': sha, 'date': date,
           'oss_rev': oss_rev, 'mode': mode, 'secs': round(time.time() - t0, 1),
           'binaries': bins, 'overlays': list(overlays), 'oss_overlays': list(oss_overlays),
           'patches': list(patches), 'toolchain': 'clang-18.1.3 + compiler-rt llvmorg-18.1.3 (self-built)'}
    if not ok:
        res['detail'] = f'target {harness_filter or "(any)"} not produced'
    if rc != 0 or not ok:
        # keep only meaningful error lines
        errs = [l for l in log.splitlines() if re.search(r'error[: ]|undefined reference|Error \d', l)]
        res['errors'] = errs[:25]
    # keep sources for coverage mapping when requested
    if keep:
        res['src'] = SRC
    else:
        shutil.rmtree(work, ignore_errors=True)
    json.dump(res, open(f'{out}/result.json', 'w'), indent=1)
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('sha'); ap.add_argument('out')
    ap.add_argument('--mode', default='cov')
    ap.add_argument('--overlay', action='append', default=[])
    ap.add_argument('--oss-overlay', action='append', default=[])
    ap.add_argument('--patch', action='append', default=[])
    ap.add_argument('--oss-rev')
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--target')
    a = ap.parse_args()
    r = build(a.project, a.sha, a.out, a.mode, a.overlay, a.oss_overlay, a.patch, a.oss_rev,
              keep=a.keep, harness_filter=a.target)
    print(json.dumps({k: v for k, v in r.items() if k != 'errors'}, indent=1))
    for e in r.get('errors', []):
        print('  ERR', e[:220])
