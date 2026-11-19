#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
factcheck_v0.py —— 只读核查：48 条样本里到底哪些有"修复后 harness"（V0）原料。

背景
----
路线 2 的论文口径需要三个版本：V−1（改前库+旧harness）、V−0.5（改后库+旧harness）、
V0（改后库+修复后 harness，即开发者测试补丁）。此前有结论说"V0 只有 3 条有 diff"，
但数据集 README 的 ground truth 分布是 maintainer_fix 18 + counterfactual_fix 5 +
coupled_commit 1 + experiment 24，暗示阳性 24 条都应有修复材料。本脚本不猜，逐条扫
verification/ 目录，把事实列成一张表，产出 results/v0_factcheck.json。

只读：不写数据集，不写 GT，只在 --out 写一张清单。

用法：
  python3 factcheck_v0.py --dataset /mnt/c/.../Dataset-v9/dataset --out results/v0_factcheck.json
"""
import argparse
import json
import os
import re
import sys

FIX_FILES = ('harness_fix.diff', 'fix.diff', 'harness.diff', 'test_fix.diff',
             'v0.diff', 'maintainer_fix.diff', 'counterfactual_fix.diff')


def find_cases(root):
    """只扫 cases/ 子树（排除 extension/ 里的 4 条旧样本）。"""
    cases_root = os.path.join(root, 'cases')
    if not os.path.isdir(cases_root):
        cases_root = root
    out = []
    for dirpath, dirnames, filenames in os.walk(cases_root):
        if os.path.basename(dirpath).startswith('V3-') and \
           os.path.exists(os.path.join(dirpath, 'case.json')):
            out.append(dirpath)
    return sorted(set(out))


def inspect_case(case_dir):
    cid = os.path.basename(case_dir)
    info = {'id': cid, 'path': os.path.relpath(case_dir)}

    # case.json / label.json
    for name in ('case.json', 'label.json'):
        p = os.path.join(case_dir, name)
        if os.path.exists(p):
            try:
                d = json.load(open(p, encoding='utf-8'))
                info[name.split('.')[0]] = d
            except Exception as e:
                info[name.split('.')[0] + '_error'] = str(e)

    # label.json 的正式键名：label / need_visibility / degradation_type / gt_source
    lab = info.get('label') or {}
    info['gt_label'] = lab.get('label')
    info['gt_visibility'] = lab.get('need_visibility') or lab.get('visibility')
    info['gt_type'] = lab.get('degradation_type') or lab.get('type')
    info['gt_source'] = lab.get('gt_source')

    # meta.json：M / M_parent / H（维护者修复 harness 的 oss-fuzz commit）
    mp = os.path.join(case_dir, 'meta.json')
    if os.path.exists(mp):
        try:
            meta = json.load(open(mp, encoding='utf-8'))
            info['M'] = meta.get('M')
            info['M_parent'] = meta.get('M_parent')
            info['H'] = meta.get('H')
        except Exception as e:
            info['meta_error'] = str(e)

    # verification/experiments.json：compile_matrix 是否含 h(fix) x lib(M)
    ep = os.path.join(case_dir, 'verification', 'experiments.json')
    info['experiments_matrix_keys'] = []
    if os.path.exists(ep):
        try:
            exp = json.load(open(ep, encoding='utf-8'))
            cm = exp.get('compile_matrix') or {}
            info['experiments_matrix_keys'] = sorted(cm.keys())
            info['has_v0_execution'] = any('fix' in k or k.startswith('h(H)') or 'W0' in k
                                           for k in cm)
        except Exception as e:
            info['experiments_error'] = str(e)

    # verification/ 目录内容
    vdir = os.path.join(case_dir, 'verification')
    info['verification_exists'] = os.path.isdir(vdir)
    info['verification_files'] = []
    fix_material = []
    if info['verification_exists']:
        for name in sorted(os.listdir(vdir)):
            full = os.path.join(vdir, name)
            info['verification_files'].append(name)
            if os.path.isfile(full):
                base = name.lower()
                if base.endswith(('.diff', '.patch')) or name in FIX_FILES or \
                   re.search(r'fix|repair|v0|harness', base):
                    fix_material.append(name)

    info['fix_candidates'] = fix_material

    # verification 里有没有"修复后的 harness 文件"（非 diff 形式）
    info['fix_full_files'] = []
    if info['verification_exists']:
        for name in info['verification_files']:
            full = os.path.join(vdir, name)
            if os.path.isfile(full) and not name.endswith(('.diff', '.patch', '.log', '.txt', '.md', '.json', '.py', '.sh')):
                info['fix_full_files'].append(name)

    info['has_v0_material'] = bool(fix_material) or bool(info['fix_full_files'])
    return info


def main():
    ap = argparse.ArgumentParser(description='核查 48 条样本的 V0 修复材料')
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--out', default='results/v0_factcheck.json')
    args = ap.parse_args()

    cases = find_cases(args.dataset)
    print('找到 %d 个样本目录' % len(cases), file=sys.stderr)

    rows = [inspect_case(c) for c in cases]

    # 汇总
    n_H = sum(1 for r in rows if r.get('H'))
    n_v0_exec = sum(1 for r in rows if r.get('has_v0_execution'))
    pos = [r for r in rows if r.get('gt_label') == 'positive']
    pos_H = [r for r in pos if r.get('H')]
    pos_v0 = [r for r in pos if r.get('has_v0_execution')]
    print('== 汇总 ==', file=sys.stderr)
    print('总样本 %d（cases/ 应为 48）' % len(rows), file=sys.stderr)
    print('带 meta.H（维护者修复 harness commit）: %d' % n_H, file=sys.stderr)
    print('verification/experiments.json 含 V0 执行矩阵（h(fix)×lib(M)）: %d' % n_v0_exec, file=sys.stderr)
    print('阳性 %d，其中带 meta.H %d、带 V0 执行矩阵 %d' % (len(pos), len(pos_H), len(pos_v0)),
          file=sys.stderr)

    from collections import Counter
    src = Counter()
    for r in pos:
        s = r.get('gt_source')
        if isinstance(s, list):
            for x in s:
                src[str(x)] += 1
        else:
            src[str(s)] += 1
    print('阳性 gt_source 分布:', dict(src), file=sys.stderr)

    pos_no_v0 = sorted(r['id'] for r in pos if not r.get('has_v0_execution'))
    print('阳性中无 V0 执行矩阵:', pos_no_v0, file=sys.stderr)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    compact = []
    for r in rows:
        compact.append({
            'id': r['id'],
            'gt_label': r.get('gt_label'),
            'gt_visibility': r.get('gt_visibility'),
            'gt_type': r.get('gt_type'),
            'gt_source': r.get('gt_source'),
            'M': r.get('M'),
            'H': r.get('H'),
            'experiments_matrix_keys': r.get('experiments_matrix_keys'),
            'has_v0_execution': r.get('has_v0_execution'),
            'verification_files': r.get('verification_files'),
            'fix_candidates': r.get('fix_candidates'),
        })
    json.dump(compact, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[out] %s' % args.out, file=sys.stderr)


if __name__ == '__main__':
    main()
