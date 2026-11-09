#!/usr/bin/env python3
"""Inventory harness-touching commits for every project (in-tree and oss-fuzz hosted).

Output: data/inventory/<p>.json with
  harness_paths: every path that ever contained LLVMFuzzerTestOneInput (in-tree)
  oss_harness:   oss-fuzz files of the project that define LLVMFuzzerTestOneInput
  intree_commits:  first-parent commits touching an in-tree harness, with flags
                   coupled (also touches library files), files
  oss_commits:   oss-fuzz commits touching projects/<oss>/ (harness or build.sh)
"""
import json, os, subprocess, re, sys

HD = '/home/claude/hd'
PROJ = json.load(open(f'{HD}/tools/projects.json'))
os.makedirs(f'{HD}/data/inventory', exist_ok=True)

LIBEXT = ('.c', '.h', '.cc', '.cpp', '.hpp', '.cxx', '.hh', '.inc', '.inl')
NONLIB = re.compile(r'(^|/)(test|tests|testing|fuzz|fuzzing|fuzzer|fuzzers|ossfuzz|oss-fuzz|examples?|doc|docs|bench|benchmarks?|contrib|programs|tools|ci|\.github)(/|$)', re.I)


def git(repo, *a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True, errors='replace').stdout


def harness_paths(repo):
    # every path in history whose content ever had LLVMFuzzerTestOneInput
    out = git(repo, 'log', '--all', '--format=', '--name-only', '-G', 'LLVMFuzzerTestOneInput', '--',
              '*.c', '*.cc', '*.cpp', '*.cxx')
    paths = sorted({l for l in out.splitlines() if l.strip()})
    return [p for p in paths if not re.search(r'third_party|vendor/|deps/|external/|googletest|/_?build/', p)]


def is_lib(path):
    return path.endswith(LIBEXT) and not NONLIB.search(path)


def main(only=None):
    for p, cfg in PROJ.items():
        if only and p not in only:
            continue
        repo = f"{HD}/repos/{cfg['repo']}"
        if not os.path.isdir(repo):
            continue
        hp = harness_paths(repo)
        commits = []
        if hp:
            log = git(repo, 'log', '--first-parent', '--format=@@%H %P|%cI|%s', '--name-only', 'HEAD')
            cur = None
            for line in log.splitlines():
                if line.startswith('@@'):
                    h, rest = line[2:].split(' ', 1)
                    parents, date, subj = rest.split('|', 2)
                    cur = {'sha': h, 'parent': parents.split()[0] if parents else None,
                           'date': date, 'subject': subj, 'files': []}
                    commits.append(cur)
                elif line.strip() and cur:
                    cur['files'].append(line.strip())
            hs = set(hp)
            sel = []
            for c in commits:
                th = [f for f in c['files'] if f in hs]
                if th:
                    lib = [f for f in c['files'] if is_lib(f) and f not in hs]
                    sel.append({**{k: c[k] for k in ('sha', 'parent', 'date', 'subject')},
                                'harness_files': th, 'lib_files': lib, 'coupled': bool(lib),
                                'n_files': len(c['files'])})
            commits = sel
        # oss-fuzz side
        oss = cfg['oss']
        ofiles = git(f'{HD}/oss-fuzz', 'log', '--format=', '--name-only', '--', f'projects/{oss}')
        ofiles = sorted({l for l in ofiles.splitlines() if l.strip()})
        oss_h = []
        for f in ofiles:
            if f.endswith(('.c', '.cc', '.cpp')):
                if git(f'{HD}/oss-fuzz', 'log', '-1', '--format=%H', '-G', 'LLVMFuzzerTestOneInput', '--', f).strip():
                    oss_h.append(f)
        olog = git(f'{HD}/oss-fuzz', 'log', '--first-parent', '--format=@@%H|%cI|%s', '--name-only', 'master', '--', f'projects/{oss}')
        ocs, cur = [], None
        for line in olog.splitlines():
            if line.startswith('@@'):
                h, d, s = line[2:].split('|', 2)
                cur = {'sha': h, 'date': d, 'subject': s, 'files': []}
                ocs.append(cur)
            elif line.strip() and cur:
                cur['files'].append(line.strip())
        res = {'project': p, 'repo': cfg['repo'], 'harness_paths': hp, 'oss_harness': oss_h,
               'intree_commits': commits, 'oss_commits': ocs}
        json.dump(res, open(f'{HD}/data/inventory/{p}.json', 'w'), indent=1)
        print(f"{p:14s} intree_h={len(hp):3d} h_commits={len(commits):4d} coupled={sum(c['coupled'] for c in commits):4d} "
              f"oss_h={len(oss_h):2d} oss_commits={len(ocs):3d}")


if __name__ == '__main__':
    main(sys.argv[1:] or None)
