#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify_gap_bsm.py —— 用 label.json 的 gap.blockers 补齐 stale vs missing 的细分，
                       给出"如果我们看得见正确的信号（harness diff + API 变化），B/S/M 能到多准"。

背景
----
13.2 已经证明：执行差分（compile_matrix）能让二分类到 100%，但它自带答案（h(fix) 行只存在于阳性），
而且只能区分"编译失败(breaking)"和"编译通过但有修复(stale/missing)"，分不开 stale 和 missing。

13.3 里写"需要 harness 修复 diff"才能分开——本脚本来核实这一点。数据集的 label.json 里，
gap.blockers[].kind 其实就是作者人工标注后的那张"harness diff 语义表"，不需要再去 OSS-Fuzz 克隆：

    blocker.kind            → 论文标签（本次映射）
    api_signature           → test_breaking（改接口，旧 harness 编译失败）
    api_misuse              → test_breaking（API 用法错，旧 harness 编译/链接失败）
    build_layout            → test_breaking（构建布局变化）
    build_macro             → test_breaking（构建宏变化）
    harness_const           → test_stale   （旧 harness 的常量/断言失效，但仍能编译）
    call_sequence           → test_missing （需要新增调用序列覆盖新行为）
    behavior                → test_stale   （行为变了、旧断言不再成立）
    unsatisfied_condition   → test_missing （新分支/新条件无人测试）

这仍然是"上界"分析：相当于把数据集里作者写的语义理由直接翻译成 B/S/M，测的是
"如果有完美检测，标签空间本身表达得了吗"，而不是"我们的自动检测有多好"。

用法：
  python3 classify_gap_bsm.py --dataset <Dataset-v9/dataset> --out results/gap_bsm_v9.json
"""
import argparse
import json
import os
import sys
from collections import Counter, OrderedDict

_KIND2LABEL = {
    'api_signature': 'test_breaking',
    'api_misuse': 'test_breaking',
    'build_layout': 'test_breaking',
    'build_macro': 'test_breaking',
    'harness_const': 'test_stale',
    'call_sequence': 'test_missing',
    'behavior': 'test_stale',
    'unsatisfied_condition': 'test_missing',
}

# 关键修正：论文定义 breaking = "测试编译**或执行**失败"（§1.3）。
# 所以显式信号是 B 的第一判据，blocker.kind 只在"无显式信号"(silent)时决定 S 还是 M：
#   explicit_signal = compile_failure / runtime_failure_on_replay → breaking
#   explicit_signal = None（silent）→ 按 _KIND2LABEL 细分 stale / missing
_SILENT_ORDER = ['test_stale', 'test_missing']  # 供 silent 用例排序用（非必需）


def find_cases(root):
    cases_root = os.path.join(root, 'cases')
    if not os.path.isdir(cases_root):
        cases_root = root
    out = []
    for dp, dn, fn in os.walk(cases_root):
        if os.path.basename(dp).startswith('V3-') and os.path.exists(os.path.join(dp, 'case.json')):
            out.append(dp)
    return sorted(set(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--out', default='results/gap_bsm_v9.json')
    args = ap.parse_args()

    rows = []
    for c in find_cases(args.dataset):
        lab = json.load(open(os.path.join(c, 'label.json'), encoding='utf-8'))
        exp = json.load(open(os.path.join(c, 'verification', 'experiments.json'),
                            encoding='utf-8'))
        gap = lab.get('gap') or {}
        blockers = gap.get('blockers') or []
        kinds = [b.get('kind') for b in blockers if isinstance(b, dict)]
        signal = exp.get('explicit_signal')

        # 显式信号（编译失败 / 运行时失败）→ breaking（论文：测试编译或执行失败）
        if signal in ('compile_failure', 'runtime_failure_on_replay'):
            label = 'test_breaking'
        elif signal is None:
            mapped = [_KIND2LABEL.get(k, 'unknown') for k in kinds]
            prio = {'test_breaking': 0, 'test_missing': 1, 'test_stale': 2}
            labels = sorted({m for m in mapped if m != 'unknown'}, key=lambda x: prio[x])
            label = labels[0] if labels else 'no_update'
        else:
            label = 'no_update'

        rows.append({
            'id': lab.get('id'),
            'gt_label': lab.get('label'),
            'gt_visibility': lab.get('need_visibility'),
            'gt_type': lab.get('degradation_type'),
            'explicit_signal': signal,
            'blocker_kinds': kinds,
            'label': label,
        })

    pos = [r for r in rows if r['gt_label'] == 'positive']
    neg = [r for r in rows if r['gt_label'] == 'negative']

    def pred_pos(r):
        return r['label'] in ('test_breaking', 'test_stale', 'test_missing')

    tp = sum(1 for r in pos if pred_pos(r))
    fp = sum(1 for r in neg if pred_pos(r))
    fn = len(pos) - tp
    tn = len(neg) - fp
    p = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * p * rec / (p + rec)) if p and rec else None

    # 类型判别（显式→breaking，隐式→stale|missing）
    tacc = {'explicit': {'n': 0, 'ok': 0}, 'silent': {'n': 0, 'ok': 0}}
    for r in pos:
        vis = r['gt_visibility']
        key = 'explicit' if vis == 'explicit' else 'silent'
        tacc[key]['n'] += 1
        if vis == 'explicit' and r['label'] == 'test_breaking':
            tacc[key]['ok'] += 1
        elif vis != 'explicit' and r['label'] in ('test_stale', 'test_missing'):
            tacc[key]['ok'] += 1

    summary = OrderedDict(
        n_samples=len(rows), n_positive=len(pos), n_negative=len(neg),
        pred_dist=dict(Counter(r['label'] for r in rows)),
        tp=tp, fp=fp, fn=fn, tn=tn,
        P=round(p * 100, 1) if p is not None else None,
        R=round(rec * 100, 1) if rec is not None else None,
        F1=round(f1 * 100, 1) if f1 is not None else None,
        type_acc_detail=tacc,
        note='上界分析：把 gap.blockers 的语义类别映射成 B/S/M，等价于"有完美检测时的标签空间表达能力"。',
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump({'summary': summary, 'rows': rows},
              open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('== gap.blockers → B/S/M 上界（GT=label.json）==', file=sys.stderr)
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
