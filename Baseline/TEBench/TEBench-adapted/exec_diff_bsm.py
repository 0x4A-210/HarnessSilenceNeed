#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exec_diff_bsm.py —— 用数据集自带的执行矩阵，验证论文口径的三版本检测到底能到多准。

背景与关键事实
--------------
路线 2 之前想把三个版本自己编译出来（exec_bsm.py），但做到一半发现一个被忽略的事实：

    verification/experiments.json 的 compile_matrix 里，数据集作者已经把
    "旧 harness × 旧库 / 旧 harness × 新库 / 修复 harness × 新库" 全部跑过一遍了。

论文 2.2.1 的三版本在做数据集时就是按这个矩阵构造的，映射关系：

    论文版本    compile_matrix 键            含义
    V-1         h(M^1) x lib(M^1)            改前：旧 harness + 旧库（应 ok）
    V-0.5       h(M^1) x lib(M)              只改库：旧 harness + 新库（检测信号）
    V0          h(fix) x lib(M)              完整修复：修复 harness + 新库（应 ok）

所以"后面的检测能不能迁移"不再需要自己编译，直接读这份已跑好的执行结果，
实现论文第 2.1.3 节的判定规则，再和 label.json 的 GT 对拍。这是零成本、无环境依赖、
可复现的判决实验。旧路线 1/1.5/路线2 的产物全部保留作对照，本脚本只做加法。

判定规则（对齐论文 §1.3 + 2.1.3，映射到 compile_matrix）：
    breaking : V-0.5 编译失败（status=fail），且 V0 编译通过（status=ok）
               —— 旧 harness 被改坏的接口/移除的符号打断，开发者修 harness 恢复。
    stale    : V-0.5 编译通过，但 V0 修复行存在 —— 开发者仍补了 harness，
               对应"测试还过但语义失效"（无执行失败的 stale）。
    missing  : V-0.5 编译通过、V0 修复行存在，且 gap.blockers 是新增 API 类
               —— 对应"新行为要补测试"。
    no_update: 阴性（V-0.5 也 ok，且无 h(fix) 行）→ 不需要更新。

诚实声明：compile_matrix 是"构建通过性"矩阵，它能直接判定 breaking（编译失败是硬证据），
stale 和 missing 无法靠构建矩阵直接区分（需要 harness diff/覆盖率）。所以本脚本：
  - breaking 用 status 硬判（可信）；
  - stale/missing 的细分用 label.json 的 gap.blockers 做"上界"参考，并在证据里写明，
    不假装是执行差分判出来的。

用法：
  python3 exec_diff_bsm.py --dataset <Dataset-v9/dataset> --out results/exec_diff_v9.json
"""
import argparse
import json
import os
import sys
from collections import Counter, OrderedDict


def find_cases(root):
    cases_root = os.path.join(root, 'cases')
    if not os.path.isdir(cases_root):
        cases_root = root
    out = []
    for dp, dn, fn in os.walk(cases_root):
        if os.path.basename(dp).startswith('V3-') and os.path.exists(os.path.join(dp, 'case.json')):
            out.append(dp)
    return sorted(set(out))


def detect(case_dir):
    lab = json.load(open(os.path.join(case_dir, 'label.json'), encoding='utf-8'))
    meta = json.load(open(os.path.join(case_dir, 'meta.json'), encoding='utf-8'))
    exp = json.load(open(os.path.join(case_dir, 'verification', 'experiments.json'), encoding='utf-8'))
    cm = exp.get('compile_matrix') or {}

    cid = lab.get('id')
    gt_label = lab.get('label')
    gt_vis = lab.get('need_visibility')
    gt_type = lab.get('degradation_type')

    # 三版本矩阵行
    row_vm1 = cm.get('h(M^1) x lib(M^1)') or {}
    row_v05 = cm.get('h(M^1) x lib(M)') or {}
    row_v0 = None
    for k, v in cm.items():
        if k.startswith('h(fix)') or k.startswith('h(H)'):
            row_v0 = (k, v)
            break

    st_m1 = row_vm1.get('status')
    st_05 = row_v05.get('status')
    st_0 = row_v0[1].get('status') if row_v0 else None

    gap = lab.get('gap') or {}
    blockers = gap.get('blockers') or []
    kinds = sorted({b.get('kind') for b in blockers if isinstance(b, dict)})

    ev = OrderedDict(
        gt_label=gt_label, gt_visibility=gt_vis, gt_type=gt_type,
        v1=st_m1, v05=st_05,
        v0_key=(row_v0[0] if row_v0 else None), v0=st_0,
        v05_errors=(row_v05.get('errors') or [])[:3],
        explicit_signal=exp.get('explicit_signal'),
        gap_blocker_kinds=kinds,
    )

    # ---- 判定 ----
    if st_05 == 'fail' and st_0 == 'ok':
        label, why = 'test_breaking', 'V-0.5 build fails, V0 build passes'
    elif st_05 == 'fail':
        label, why = 'test_breaking', 'V-0.5 build fails (no V0 row in matrix)'
    elif st_05 == 'ok' and st_m1 == 'ok' and exp.get('explicit_signal') in \
            ('runtime_crash', 'assert_fail', 'leak', 'NaN_assert', 'crash'):
        label, why = 'test_breaking', 'runtime failure signal: ' + exp.get('explicit_signal', '')
    elif st_05 == 'ok' and row_v0 is not None:
        if any(k in ('api_signature', 'new_api_call', 'api_semantic') for k in kinds):
            label, why = 'test_missing', 'new/changed API needed (blocker: %s)' % ','.join(kinds)
        else:
            label, why = 'test_stale', 'V-0.5 passes but fix harness exists (semantic-gap fix)'
    elif st_05 == 'ok' and row_v0 is None:
        label, why = 'no_update', 'V-0.5 passes and no fix harness exists'
    else:
        label, why = 'no_update', 'no conclusive execution signal'

    return {'id': cid, 'label': label, 'why': why, 'evidence': ev,
            'M': meta.get('M'), 'H': meta.get('H'), 'project': meta.get('project')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--out', default='results/exec_diff_v9.json')
    args = ap.parse_args()

    cases = find_cases(args.dataset)
    rows = []
    for c in cases:
        try:
            rows.append(detect(c))
        except Exception as e:
            rows.append({'id': os.path.basename(c), 'error': '%s: %s' % (type(e).__name__, e)})

    pos = [r for r in rows if r.get('evidence', {}).get('gt_label') == 'positive']
    neg = [r for r in rows if r.get('evidence', {}).get('gt_label') == 'negative']

    def pred_pos(r):
        return r.get('label') in ('test_breaking', 'test_stale', 'test_missing')

    tp = sum(1 for r in pos if pred_pos(r))
    fp = sum(1 for r in neg if pred_pos(r))
    fn = len(pos) - tp
    tn = len(neg) - fp
    p = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * p * rec / (p + rec)) if p and rec else None

    summary = OrderedDict(
        n_samples=len(rows), n_positive=len(pos), n_negative=len(neg),
        pred_dist=dict(Counter(r.get('label') for r in rows)),
        tp=tp, fp=fp, fn=fn, tn=tn,
        P=round(p * 100, 1) if p is not None else None,
        R=round(rec * 100, 1) if rec is not None else None,
        F1=round(f1 * 100, 1) if f1 is not None else None,
    )
    tacc = {'explicit': {'n': 0, 'ok': 0}, 'silent': {'n': 0, 'ok': 0}}
    for r in pos:
        vis = r['evidence']['gt_visibility']
        key = 'explicit' if vis == 'explicit' else 'silent'
        tacc[key]['n'] += 1
        if vis == 'explicit' and r.get('label') == 'test_breaking':
            tacc[key]['ok'] += 1
        elif vis != 'explicit' and r.get('label') in ('test_stale', 'test_missing'):
            tacc[key]['ok'] += 1
    summary['type_acc_detail'] = tacc

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump({'summary': summary, 'rows': rows},
              open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('== 判定结果（GT=label.json）==', file=sys.stderr)
    print('样本 %d（阳性 %d / 阴性 %d）' % (len(rows), len(pos), len(neg)), file=sys.stderr)
    print('预测分布:', dict(summary['pred_dist']), file=sys.stderr)
    print('TP=%d FP=%d FN=%d TN=%d' % (tp, fp, fn, tn), file=sys.stderr)
    print('P=%.1f R=%.1f F1=%.1f' % (p * 100 if p else 0, rec * 100 if rec else 0, f1 * 100 if f1 else 0), file=sys.stderr)
    print('类型判别: explicit %d/%d, silent %d/%d' % (
        tacc['explicit']['ok'], tacc['explicit']['n'],
        tacc['silent']['ok'], tacc['silent']['n']), file=sys.stderr)
    print('[out] %s' % args.out, file=sys.stderr)


if __name__ == '__main__':
    main()
