#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify_bsm_c.py —— 路线 1 的 C/C++ 移植版，用于 v9 开发集（Harness Degradation v9）

为什么需要移植
--------------
原版 classify_bsm.py 的判据是 Java 专有的：
  - 测试文件：路径含 src/test/java，且扩展名 .java
  - 测试新增：@Test / @ParameterizedTest 注解计数
而 v9 是 C/C++ + OSS-Fuzz harness，两个判据都不成立。

更关键的是：v9 每条样本的 input/change.diff 只是**库侧**改动（M^1 → M），
harness 停在 H（旧版本），修复在 H^+ 里。所以原版在 v9 上 "test_files" 恒为空，
会 48/48 全部退化到 test_stale —— 这不是分类结果，是启发式失效。

移植方式（保持"只改信号源、不改判定结构"）
------------------------------------------
把 Java 的三条规则逐一映射到 C/C++ 语义，判定优先级不变（breaking > missing > stale）：

  原版规则                                   C/C++ 版规则
  ─────────────────────────────────────────────────────────────────────
  源文件里同名方法在增删行都出现 = 签名变化    库侧 .c/.h 顶层函数名在增删行都出现 = 签名/原型变化
  且测试文件有 @Test 增删 = 测试被改          且该函数名被 harness 源码引用 = 旧 harness 会被打断
  源文件净新增方法 + 测试净新增 @Test        库侧新增公开函数（非 static）且 harness 未引用 = 新行为无覆盖
  其余                                      其余

这里刻意不做执行、不做覆盖采集——那是路线 2。本脚本只回答"纯静态 diff 信号能走多远"。

变更记录
--------
- 2026-11-18 修正 is_test_side：原实现用 `'fuzz' in p` 子串判定，会把库里的
  fuzzing.h / fuzz_helpers.h 误判成测试侧（漏掉库侧信号），同时漏判
  tests/*_test.h 这类测试头（污染 new_funcs）。改为目录分量 + 文件名 token 匹配。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

C_EXTS = {'.c', '.h', '.cc', '.cpp', '.cxx', '.hh', '.hpp', '.hxx'}
HARNESS_EXTS = {'.c', '.cc', '.cpp', '.cxx'}

# 测试侧识别：按"路径分量 / 文件名 token"匹配，不用子串。
# 旧写法是 `'fuzz' in p`，会把库里的 fuzzing.h、fuzz_helpers.h 之类误判成测试侧，
# 也会让 tests/nghttp2_frame_test.h 这类测试头文件漏判（反过来污染 new_funcs）。
TEST_DIR_RE = re.compile(
    r'(?i)'
    r'(?:^(?:tests?|testing|unittests?|testsuites?|fuzz|fuzzer|fuzzers|fuzzing|oss-?fuzz)$)'
    r'|(?:(?:^|[-_])tests?(?:$|[-_]))'
    r'|(?:(?:^|[-_])fuzz(?:ing|ers?)?(?:$|[-_]))'
)
# 文件名（去扩展名）：test_*.c / *_test.c / *-test.c / pcre2test.c / fuzz_*.c / *_fuzz.c
# 注：`.*test$` 会连带命中 latest.c 这类词尾巧合，v9 里没有出现，作为已知限制记录。
TEST_FILE_RE = re.compile(r'(?i)^(tests?[-_].*|.*[-_]tests?|.*test|fuzz[-_].*|.*[-_]fuzz|fuzzers?)$')

# 顶层函数定义/原型：行首无缩进，形如 `int XML_Parse(XML_Parser parser, ...)`
FUNC_RE = re.compile(r'^(?!return\b)(?:[A-Za-z_]\w*[\s\*]+)+([A-Za-z_]\w*)\s*\(')
KEYWORDS = {'if', 'for', 'while', 'switch', 'return', 'sizeof', 'catch', 'do',
            'else', 'case', 'goto', 'typedef', 'struct', 'union', 'enum'}

TYPE_BREAKING = 'test_breaking'
TYPE_STALE = 'test_stale'
TYPE_MISSING = 'test_missing'


def split_diff_by_file(diff_text):
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


def is_code(path):
    return os.path.splitext(path)[1].lower() in C_EXTS


def is_test_side(path):
    """测试侧判定：目录分量或文件名 token 命中才算，避免子串误伤。

    - 目录：test / tests / unittest / api_test / fuzz / fuzzing / oss-fuzz ...
    - 文件名（仅编译单元）：test_parse.c / format-test.cc / pcre2test.c / fuzz_target.c ...
    - 头文件只要在测试目录下也算测试侧（否则测试头里的原型会污染 new_funcs）。
    - 非 C/C++ 文件一律返回 False，交给 is_code 处理。
    """
    parts = path.replace('\\', '/').lower().split('/')
    dirs, name = parts[:-1], parts[-1]
    stem, ext = os.path.splitext(name)
    if ext not in C_EXTS:            # 非 C/C++ 文件（脚本、数据、配置）不参与源码分析
        return False
    if any(TEST_DIR_RE.search(d) for d in dirs):
        return True
    # 只在"编译单元"上按文件名判；fuzz_helpers.h 这类库内头文件不算测试侧
    return ext in HARNESS_EXTS and bool(TEST_FILE_RE.match(stem))


def func_names(diff_text):
    """从单文件 diff 中提取 (added_names, removed_names)，只认列 0 的函数定义/原型。"""
    added, removed, added_static = set(), set(), set()
    for line in diff_text.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            body = line[1:]
            if not body or body[0] in ' \t#/*':
                continue
            m = FUNC_RE.match(body)
            if m and m.group(1) not in KEYWORDS:
                added.add(m.group(1))
                if 'static' in body.split('(')[0]:
                    added_static.add(m.group(1))
        elif line.startswith('-') and not line.startswith('---'):
            body = line[1:]
            if not body or body[0] in ' \t#/*':
                continue
            m = FUNC_RE.match(body)
            if m and m.group(1) not in KEYWORDS:
                removed.add(m.group(1))
    return added, removed, added_static


def load_harness_text(case_dir, case_meta):
    """读取 harness 源码文本（input/harness 下全部 C/C++ 文件）+ 目标 harness 文件。"""
    root = os.path.join(case_dir, 'input', 'harness')
    texts, files = {}, []
    for dirpath, _, names in os.walk(root):
        for n in names:
            if os.path.splitext(n)[1].lower() in HARNESS_EXTS:
                p = os.path.join(dirpath, n)
                try:
                    texts[p] = open(p, encoding='utf-8', errors='replace').read()
                    files.append(os.path.relpath(p, root).replace('\\', '/'))
                except OSError:
                    continue

    target = None
    for hf in case_meta.get('harness_files') or []:
        for p in texts:
            if p.replace('\\', '/').endswith(hf):
                target = texts[p]
                break
    corpus = '\n'.join(texts.values())
    return corpus, target or '', files


def classify(case_dir):
    case_json = os.path.join(case_dir, 'case.json')
    meta = json.load(open(case_json, encoding='utf-8')) if os.path.exists(case_json) else {}
    diff_path = os.path.join(case_dir, 'input', 'change.diff')
    diff_text = open(diff_path, encoding='utf-8', errors='replace').read()

    chunks = split_diff_by_file(diff_text)
    # 候选集只取"库侧代码文件"；测试侧（含测试目录下的头文件）不进 sig/new_funcs 统计
    src_files = [f for f in chunks if is_code(f) and not is_test_side(f)]
    test_files = sorted(f for f in chunks if is_code(f) and is_test_side(f))

    sig_changed, new_funcs, static_new = set(), set(), set()
    for f in src_files:
        added, removed, added_static = func_names(chunks[f])
        sig_changed |= (added & removed)
        new_funcs |= (added - removed)
        static_new |= (added_static - removed)

    corpus, target_text, harness_files = load_harness_text(case_dir, meta)

    def used_by_harness(name):
        return re.search(rf'\b{re.escape(name)}\s*\(', corpus) is not None

    hit_sig = sorted(n for n in sig_changed if used_by_harness(n))
    public_new = sorted(n for n in (new_funcs - static_new) if not used_by_harness(n))

    if hit_sig:
        label = TYPE_BREAKING
    elif public_new:
        label = TYPE_MISSING
    else:
        label = TYPE_STALE

    return {
        'label': label,
        'evidence': {
            'sig_changed': len(sig_changed),
            'sig_changed_names': sorted(sig_changed)[:15],
            'sig_changed_used_by_harness': hit_sig[:15],
            'new_public_funcs_uncovered': public_new[:15],
            'new_funcs_total': len(new_funcs),
            'harness_files_referenced': len(harness_files),
            'diff_test_side_files': test_files,
        },
        'changed_code_files': len(src_files),
    }


def main():
    ap = argparse.ArgumentParser(description='路线 1 的 C/C++ 移植版（v9 开发集）')
    ap.add_argument('--dataset', required=True, help='Dataset-v9/dataset 根目录')
    ap.add_argument('--out', default='results/bsm_v9.json')
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()

    ds = open(os.path.join(args.dataset, 'dataset.json'), encoding='utf-8')
    manifest = json.load(ds)
    samples = manifest['samples'][:args.limit] if args.limit else manifest['samples']

    rows = []
    for i, s in enumerate(samples, 1):
        case_dir = os.path.join(args.dataset, s['path'])
        try:
            r = classify(case_dir)
            row = {'id': s['dir_id'], 'dir': s['dir'], 'project': s['project'],
                   'gt_label': s['label'], 'gt_visibility': s['need_visibility'],
                   'gt_type': s['degradation_type'],
                   'gt_introduced': s['introduced_by_this_change'], **r}
        except Exception as e:
            row = {'id': s['dir_id'], 'dir': s['dir'], 'project': s['project'],
                   'gt_label': s['label'], 'error': f'{type(e).__name__}: {e}'}
        rows.append(row)
        print(f"[{i}/{len(samples)}] {s['dir_id']:6s} {s['label']:8s} "
              f"{s['need_visibility']:7s} -> {row.get('label', 'ERROR')}", file=sys.stderr)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(rows, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f"\n[out] {args.out}", file=sys.stderr)
    print("=== 预测分布 ===", file=sys.stderr)
    for k, v in Counter(r.get('label') for r in rows).most_common():
        print(f"  {str(k):14s} {v}", file=sys.stderr)
    print("=== 阳性：可见性 vs 预测 ===", file=sys.stderr)
    cross = defaultdict(Counter)
    for r in rows:
        if r.get('gt_label') == 'positive':
            cross[r['gt_visibility']][r.get('label')] += 1
    for vis, c in cross.items():
        print(f"  {vis:7s} {dict(c)}", file=sys.stderr)


if __name__ == '__main__':
    main()
