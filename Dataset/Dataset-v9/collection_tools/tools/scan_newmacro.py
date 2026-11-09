#!/usr/bin/env python3
"""R4 cheap pre-filter: first-parent commits that introduce a *new* preprocessor macro gating
library code (#ifdef NEW / #if NEW / #if defined(NEW)), after the project's harness existed.
Prints candidates for silent configuration degradations (and look-alike negatives)."""
import json, re, subprocess, sys, os

HD = '/home/claude/hd'
PROJ = json.load(open(f'{HD}/tools/projects.json'))
SRC_EXT = ('.c', '.h', '.cc', '.cpp', '.hpp', '.cxx', '.inc')
NONLIB = re.compile(r'(^|/)(test|tests|fuzz|fuzzing|fuzzer|fuzzers|ossfuzz|oss-fuzz|examples?|doc|docs|bench|programs|tools|contrib)(/|$)', re.I)
PAT = re.compile(r'^\+\s*#\s*(?:if|ifdef|elif)\s+(?:!?\s*defined\s*\(?\s*)?([A-Z][A-Z0-9_]{3,})')
SKIP = re.compile(r'^(_|__|HAVE_|SIZEOF_|WIN32|_WIN|__GNUC|__clang|NDEBUG|DEBUG|_MSC|__cplusplus|.*_H$|.*_H_$|.*_INCLUDED$)')


def git(repo, *a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True, errors='replace').stdout


def main(projects, since):
    for p in projects:
        inv = json.load(open(f'{HD}/data/inventory/{p}.json'))
        repo = f"{HD}/repos/{PROJ[p]['repo']}"
        first_h = None
        if inv['intree_commits']:
            first_h = min(c['date'] for c in inv['intree_commits'])
        if inv['oss_commits']:
            d = min(c['date'] for c in inv['oss_commits'])
            first_h = min(first_h, d) if first_h else d
        since_p = max(since, (first_h or since)[:10])
        log = git(repo, 'log', '--first-parent', f'--since={since_p}', '--format=%H %cs %s', 'HEAD')
        for line in log.splitlines():
            sha, date, subj = line.split(' ', 2)
            files = [f for f in git(repo, 'diff', '--name-only', sha + '^1', sha).split()
                     if f.endswith(SRC_EXT) and not NONLIB.search(f)]
            if not files:
                continue
            d = git(repo, 'diff', '-U0', sha + '^1', sha, '--', *files)
            macros = {m.group(1) for l in d.splitlines() if (m := PAT.match(l)) and not SKIP.match(m.group(1))}
            new = []
            for mc in sorted(macros):
                if not git(repo, 'grep', '-l', '-w', mc, sha + '^1', '--').strip():
                    new.append(mc)
            if new:
                print(f'{p:12s} {sha[:10]} {date} {",".join(new)[:80]:80s} | {subj[:70]}', flush=True)


if __name__ == '__main__':
    main(sys.argv[2:] or list(PROJ), sys.argv[1])
