#!/usr/bin/env python3
"""Compact digest of harness-modifying commits (in-tree + oss-fuzz hosted) for manual triage.
Skips: harness file creation/deletion only, pure whitespace/comment/licence edits."""
import json, subprocess, sys, re, os, glob

HD = '/home/claude/hd'
PROJ = json.load(open(f'{HD}/tools/projects.json'))


def git(repo, *a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True, errors='replace').stdout


def meaningful(lines):
    out = []
    for l in lines:
        if not l or l[0] not in '+-' or l.startswith(('+++', '---')):
            continue
        body = l[1:].strip()
        if not body or body.startswith(('//', '/*', '*', '#!')) or 'Copyright' in body or 'License' in body:
            continue
        out.append(l)
    return out


def digest(p, maxl=18):
    inv = json.load(open(f'{HD}/data/inventory/{p}.json'))
    repo = f"{HD}/repos/{inv['repo']}"
    res = []
    for c in inv['intree_commits']:
        d = git(repo, 'diff', '--diff-filter=M', c['parent'] or c['sha'] + '^', c['sha'], '--', *c['harness_files'])
        m = meaningful(d.splitlines())
        if not m:
            continue
        res.append(('T', c['sha'][:10], c['date'][:10], 'C' if c['coupled'] else '-', c['subject'][:90], m[:maxl], len(m),
                    len(c['lib_files'])))
    oss = PROJ[p]['oss']
    for c in inv['oss_commits']:
        files = [f for f in c['files'] if f.endswith(('.c', '.cc', '.cpp', 'build.sh', 'Dockerfile'))]
        if not files:
            continue
        d = git(f'{HD}/oss-fuzz', 'diff', '--diff-filter=M', c['sha'] + '^', c['sha'], '--', *files)
        m = meaningful(d.splitlines())
        m = [l for l in m if not re.search(r'MAINTAINER|apt-get|^\S\s*(RUN|FROM)\s', l)]
        if not m:
            continue
        res.append(('O', c['sha'][:10], c['date'][:10], '-', c['subject'][:90], m[:maxl], len(m), 0))
    return res


if __name__ == '__main__':
    os.makedirs(f'{HD}/data/triage', exist_ok=True)
    for p in (sys.argv[1:] or PROJ):
        if not os.path.exists(f'{HD}/data/inventory/{p}.json'):
            continue
        with open(f'{HD}/data/triage/{p}.txt', 'w') as f:
            for r in sorted(digest(p), key=lambda r: r[2]):
                f.write(f"## {r[0]} {r[1]} {r[2]} {r[3]} lib={r[7]} n={r[6]} | {r[4]}\n")
                for l in r[5]:
                    f.write('    ' + l[:150] + '\n')
        print(p, sum(1 for l in open(f'{HD}/data/triage/{p}.txt') if l.startswith('##')))
