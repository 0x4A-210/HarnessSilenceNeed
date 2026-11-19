#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_faithful_on_v9.py —— 用忠实版（Java 判据）跑 v9 开发集，产出"启发式退化"证据。

结论预期：48/48 全部 test_stale，且 has_test_change 全为 False。
原因：v9 的 input/change.diff 只含库侧改动，harness 停在 H，不在 diff 里；
     同时 .c/.h 不满足 src/test/java 判据。

用法：python run_faithful_on_v9.py --dataset <Dataset-v9/dataset> --out results/bsm_v9_java_faithful.json
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify_bsm as J


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--out', default='results/bsm_v9_java_faithful.json')
    args = ap.parse_args()

    man = json.load(open(os.path.join(args.dataset, 'dataset.json'), encoding='utf-8'))
    rows = []
    for s in man['samples']:
        diff = os.path.join(args.dataset, s['path'], 'input', 'change.diff')
        r = J.analyze_diff_file(diff, commit_id=s['dir_id'])
        # 用相对路径，结果文件才可跨机器复现（绝对路径会让每次重跑的 hash 都不同）
        r['diff_file'] = (s['path'] + '/input/change.diff').replace('\\', '/')
        r.update(gt_label=s['label'], gt_visibility=s['need_visibility'],
                 gt_type=s['degradation_type'])
        rows.append(r)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(rows, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print("标签分布:", dict(Counter(r['test_change_type'] for r in rows)))
    print("有测试文件改动的样本:", sum(1 for r in rows if r['has_test_change']), "/", len(rows))
    print("[out]", args.out)


if __name__ == '__main__':
    main()
