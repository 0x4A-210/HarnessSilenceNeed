#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify_bsm.py —— TEBench 路线 1：纯 diff 版 B/S/M 分类器（Java）

来源：从原仓库 analysis/filter_commits_step2.py 抽取，逻辑保持一致，只重写入口。
  - is_test_file / is_source_file
  - SIG_RE / TEST_ANNOT_RE / _SKIP_KEYWORDS
  - _diff_method_names / _diff_test_annotations
  - classify_test_change_type

与原实现的差异（仅入口层，判定逻辑未改）：
  1. 去掉 /Users/mac/Desktop/TestUpdate/... 等硬编码默认路径。
  2. 新增 CLI：支持 单 commit、commit 列表、以及离线 diff 文件三种输入。
  3. 输出增加证据字段（sig_changes / new_src_methods / net_new_tests 等）。
  4. 无测试文件改动时，仍按原实现返回 test_stale，但额外置 has_test_change=false，
     用于暴露"启发式退化"——v9 开发集的 diff 不含 harness 改动，会全部落到这里。

用法：
  python classify_bsm.py --repo /path/to/repo --commit <sha>
  python classify_bsm.py --repo /path/to/repo --commits-file commits.txt
  python classify_bsm.py --diff /path/to/change.diff            # 离线，不需要 git 仓库
  python classify_bsm.py --repo ... --commit ... --format csv --out out.csv
"""

import argparse
import csv
import json
import os
import re
import sys

try:
    from git import Repo
except ImportError:  # 离线 diff 模式不需要 GitPython
    Repo = None


# ── 常量（与原文一致） ──────────────────────────────────────────────────────────
TEST_PATH_PATTERNS = ['src/test/java', 'test/java', 'src/test']
SOURCE_PATH_PATTERNS = ['src/main/java', 'main/java', 'src/main']

_SKIP_KEYWORDS = {'if', 'while', 'for', 'switch', 'catch', 'return', 'else',
                  'try', 'new', 'class', 'interface', 'enum', 'assert', 'throw'}
_MOD = r'(?:(?:public|protected|private|static|final|abstract|synchronized|default|native)\s+)*'
_GTYPE = r'(?:<[^>]+>\s*)?'
_TYPE = r'[\w$][\w$.<>, \[\]]+'
_NAME = r'([\w$]+)'
_PAR = r'\s*\('
SIG_RE = re.compile(rf'^\s*{_MOD}{_GTYPE}{_TYPE}\s+{_NAME}{_PAR}')

TEST_ANNOT_RE = re.compile(r'@(Test|ParameterizedTest|RepeatedTest|TestFactory)\b')

TYPE_BREAKING = 'test_breaking'
TYPE_STALE = 'test_stale'
TYPE_MISSING = 'test_missing'


# ── 底层 diff 工具（与原文一致） ────────────────────────────────────────────────
def is_test_file(path: str) -> bool:
    return path.endswith('.java') and any(p in path for p in TEST_PATH_PATTERNS)


def is_source_file(path: str) -> bool:
    return path.endswith('.java') and any(p in path for p in SOURCE_PATH_PATTERNS)


def count_diff_changed_lines(diff_text: str) -> int:
    count = 0
    for line in diff_text.split('\n'):
        if (line.startswith('+') and not line.startswith('+++')) or \
           (line.startswith('-') and not line.startswith('---')):
            if line[1:].strip():
                count += 1
    return count


def _diff_method_names(diff_text: str):
    added, removed = set(), set()
    for line in diff_text.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            m = SIG_RE.match(line[1:])
            if m and m.group(1) not in _SKIP_KEYWORDS:
                added.add(m.group(1))
        elif line.startswith('-') and not line.startswith('---'):
            m = SIG_RE.match(line[1:])
            if m and m.group(1) not in _SKIP_KEYWORDS:
                removed.add(m.group(1))
    return added, removed


def _diff_test_annotations(diff_text: str):
    new_cnt, rem_cnt = 0, 0
    for line in diff_text.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            if TEST_ANNOT_RE.search(line[1:]):
                new_cnt += 1
        elif line.startswith('-') and not line.startswith('---'):
            if TEST_ANNOT_RE.search(line[1:]):
                rem_cnt += 1
    return new_cnt, rem_cnt


# ── 判定逻辑（与原文一致） ─────────────────────────────────────────────────────
def classify(test_diffs: dict, source_diffs: dict) -> dict:
    """输入：{path: diff_text}；输出：标签 + 证据。"""
    new_annots = rem_annots = 0
    for diff in test_diffs.values():
        n, r = _diff_test_annotations(diff)
        new_annots += n
        rem_annots += r

    sig_names, new_names = set(), set()
    for diff in source_diffs.values():
        added, removed = _diff_method_names(diff)
        sig_names |= (added & removed)
        new_names |= (added - removed)

    net_new_tests = new_annots - rem_annots

    if len(sig_names) > 0 and (rem_annots > 0 or new_annots > 0):
        label = TYPE_BREAKING
    elif net_new_tests > 0 and len(new_names) > 0:
        label = TYPE_MISSING
    else:
        label = TYPE_STALE

    return {
        'test_change_type': label,
        'evidence': {
            'sig_changes': len(sig_names),
            'sig_change_names': sorted(sig_names)[:20],
            'new_src_methods': len(new_names),
            'new_src_method_names': sorted(new_names)[:20],
            'test_annot_added': new_annots,
            'test_annot_removed': rem_annots,
            'net_new_tests': net_new_tests,
        },
    }


# ── 数据获取：git 仓库 / 离线 diff ─────────────────────────────────────────────
def files_from_diff(diff_text: str):
    """从 unified diff 中解析改动文件列表。"""
    return re.findall(r'^diff --git a/(\S+) b/', diff_text, re.M)


def split_diff_by_file(diff_text: str):
    """按文件切分 unified diff，返回 {path: chunk}。"""
    chunks, cur, cur_path = {}, [], None
    for line in diff_text.splitlines(keepends=True):
        m = re.match(r'^diff --git a/(\S+) b/', line)
        if m:
            if cur_path is not None:
                chunks[cur_path] = ''.join(cur)
            cur_path, cur = m.group(1), [line]
        elif cur_path is not None:
            cur.append(line)
    if cur_path is not None:
        chunks[cur_path] = ''.join(cur)
    return chunks


def analyze_git_commit(repo, sha: str) -> dict:
    commit = repo.commit(sha)
    if not commit.parents:
        return {'commit': sha, 'error': 'root commit（无父提交）'}
    parent = commit.parents[0].hexsha

    all_changed = repo.git.diff('--name-only', parent, sha).splitlines()
    test_files = [f for f in all_changed if is_test_file(f)]
    src_files = [f for f in all_changed if is_source_file(f)]

    test_diffs = {f: repo.git.diff('-U3', parent, sha, '--', f) for f in test_files}
    src_diffs = {f: repo.git.diff('-U3', parent, sha, '--', f) for f in src_files}

    res = classify(test_diffs, src_diffs)
    test_lines = sum(count_diff_changed_lines(d) for d in test_diffs.values())

    return {
        'commit': sha,
        'short': sha[:10],
        'subject': commit.summary,
        'date': commit.committed_datetime.strftime('%Y-%m-%d'),
        'parent': parent,
        'test_files': test_files,
        'source_files': src_files,
        'changed_files_total': len(all_changed),
        'test_changed_lines': test_lines,
        'has_test_change': bool(test_files),
        **res,
    }


def analyze_diff_file(path: str, commit_id: str = '') -> dict:
    diff_text = open(path, encoding='utf-8', errors='replace').read()
    chunks = split_diff_by_file(diff_text)
    test_files = [f for f in chunks if is_test_file(f)]
    src_files = [f for f in chunks if is_source_file(f)]

    res = classify({f: chunks[f] for f in test_files},
                   {f: chunks[f] for f in src_files})
    test_lines = sum(count_diff_changed_lines(chunks[f]) for f in test_files)

    return {
        'commit': commit_id or os.path.basename(os.path.dirname(path)),
        'diff_file': path,
        'test_files': test_files,
        'source_files': src_files,
        'changed_files_total': len(chunks),
        'test_changed_lines': test_lines,
        'has_test_change': bool(test_files),
        **res,
    }


# ── 输出 ──────────────────────────────────────────────────────────────────────
def write_rows(rows, out_path: str, fmt: str):
    if not out_path:
        out_path = 'bsm_results.' + ('csv' if fmt == 'csv' else 'json')
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    if fmt == 'csv':
        flat = []
        for r in rows:
            ev = r.get('evidence', {})
            flat.append({
                'commit': r.get('commit', ''),
                'subject': r.get('subject', ''),
                'test_change_type': r.get('test_change_type', ''),
                'has_test_change': r.get('has_test_change', ''),
                'changed_files_total': r.get('changed_files_total', ''),
                'test_files': ';'.join(r.get('test_files', [])),
                'source_files': ';'.join(r.get('source_files', [])),
                'sig_changes': ev.get('sig_changes', ''),
                'new_src_methods': ev.get('new_src_methods', ''),
                'test_annot_added': ev.get('test_annot_added', ''),
                'test_annot_removed': ev.get('test_annot_removed', ''),
                'net_new_tests': ev.get('net_new_tests', ''),
                'error': r.get('error', ''),
            })
        with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
            w.writeheader()
            w.writerows(flat)
    else:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)

    print(f"[out] {out_path}  ({len(rows)} 条)", file=sys.stderr)


def summarize(rows):
    from collections import Counter
    c = Counter(r.get('test_change_type') for r in rows)
    degenerate = sum(1 for r in rows if r.get('has_test_change') is False)
    print("── 分类分布 ──", file=sys.stderr)
    for k in (TYPE_BREAKING, TYPE_MISSING, TYPE_STALE):
        print(f"  {k:14s} {c.get(k, 0)}", file=sys.stderr)
    print(f"  无测试文件改动（启发式退化）: {degenerate}/{len(rows)}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description='TEBench 路线 1：纯 diff B/S/M 分类器（Java）')
    ap.add_argument('--repo', help='git 仓库路径')
    ap.add_argument('--commit', help='单个 commit sha')
    ap.add_argument('--commits-file', help='commit 列表（每行一个 sha，或 csv 含 hash 列）')
    ap.add_argument('--diff', help='离线 unified diff 路径（不需要 git 仓库）')
    ap.add_argument('--format', choices=['json', 'csv'], default='json')
    ap.add_argument('--out', help='输出文件路径')
    args = ap.parse_args()

    if args.diff:
        if not os.path.exists(args.diff):
            sys.exit(f'diff 不存在: {args.diff}')
        rows = [analyze_diff_file(args.diff)]
    else:
        if not args.repo or Repo is None:
            sys.exit('需要 --repo（并安装 GitPython），或改用 --diff')
        repo = Repo(args.repo)

        if args.commit:
            shas = [args.commit]
        elif args.commits_file:
            shas = []
            for line in open(args.commits_file, encoding='utf-8'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                shas.append(line.split(',')[0].strip())
        else:
            sys.exit('需要 --commit 或 --commits-file')

        rows = []
        for i, sha in enumerate(shas, 1):
            try:
                rows.append(analyze_git_commit(repo, sha))
            except Exception as e:
                rows.append({'commit': sha, 'error': f'{type(e).__name__}: {e}'})
            print(f"[{i}/{len(shas)}] {sha[:10]} -> {rows[-1].get('test_change_type', 'ERROR')}",
                  file=sys.stderr)

    write_rows(rows, args.out, args.format)
    summarize(rows)


if __name__ == '__main__':
    main()
