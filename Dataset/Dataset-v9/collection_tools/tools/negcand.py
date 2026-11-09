#!/usr/bin/env python3
"""List negative candidates: first-parent commits that modify library C/C++ files reachable by the
harness (same files the harness's target links), do not touch harness files, have a modest diff.
Prints added-line sets for neg_lines.  usage: negcand.py PROJECT SINCE [N] [path-regex]"""
import json, re, subprocess, sys

HD = '/home/claude/hd'
PROJ = json.load(open(f'{HD}/tools/projects.json'))
NONLIB = re.compile(r'(^|/)(test|tests|fuzz|fuzzing|fuzzer|fuzzers|ossfuzz|oss-fuzz|examples?|doc|docs|bench|programs|tools|contrib|apps|util|utils/.*test)(/|$)', re.I)


def git(repo, *a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True, errors='replace').stdout


def added_lines(repo, sha, f):
    d = git(repo, 'diff', '-U0', sha + '^1', sha, '--', f)
    out = []
    for h in re.finditer(r'^@@ -\S+ \+(\d+)(?:,(\d+))? @@', d, re.M):
        start, n = int(h.group(1)), int(h.group(2) or 1)
        out += list(range(start, start + n))
    return out


def main(p, since, n=40, pathre=None):
    repo = f"{HD}/repos/{PROJ[p]['repo']}"
    inv = json.load(open(f'{HD}/data/inventory/{p}.json'))
    hfiles = set(inv['harness_paths'])
    log = git(repo, 'log', '--first-parent', f'--since={since}', '--format=%H %cs %s', 'HEAD').splitlines()
    k = 0
    for line in log:
        sha, date, subj = line.split(' ', 2)
        files = git(repo, 'diff', '--name-only', sha + '^1', sha).split()
        if any(f in hfiles for f in files):
            continue
        lib = [f for f in files if f.endswith(('.c', '.h', '.cc', '.cpp', '.hpp')) and not NONLIB.search(f)]
        if pathre:
            lib = [f for f in lib if re.search(pathre, f)]
        if not lib:
            continue
        stat = git(repo, 'diff', '--shortstat', sha + '^1', sha).strip()
        m = re.search(r'(\d+) insertion', stat); ins = int(m.group(1)) if m else 0
        if ins > 300 or ins == 0:
            continue
        al = {f: added_lines(repo, sha, f) for f in lib if not f.endswith(('.h', '.hpp'))}
        print(f'{sha[:10]} {date} +{ins:<4d} {subj[:70]}')
        for f, ls in al.items():
            if ls:
                print(f'      {f}: {ls[:40]}{" ..." if len(ls) > 40 else ""}')
        k += 1
        if k >= n:
            break


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]) if len(a) > 2 else 40, a[3] if len(a) > 3 else None)
