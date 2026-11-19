#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_tables.py —— 把 results/ir_v9.json + results/eval_ir_v9.json 渲染成 VERIFY.md §12 的表格

只做渲染，不做计算：所有数字都来自 eval_v9.py 的输出，避免"文档里的数"和"能复跑的数"分叉。

    python make_tables.py > /tmp/sec124.md
"""

import json
import os
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = ('test_breaking', 'test_stale', 'test_missing', 'no_update')
CN = {'test_breaking': 'breaking', 'test_stale': 'stale',
      'test_missing': 'missing', 'no_update': 'no_update'}


def reach_status(r):
    """可达集是否算得出来。旧字段 reach_unavailable 已改名，语义也一起收紧。"""
    reach = r['evidence'].get('reach') or {}
    return reach.get('status') or ('unknown' if r['evidence'].get('reach_unavailable') else 'ok')


def reach_reason(r):
    reach = r['evidence'].get('reach') or {}
    return reach.get('status_reason') or 'no_entry_symbol'


def main():
    rows = json.load(open(os.path.join(HERE, 'results/ir_v9.json'), encoding='utf-8'))
    ev = json.load(open(os.path.join(HERE, 'results/eval_ir_v9.json'), encoding='utf-8'))
    pos = [r for r in rows if r['gt_label'] == 'positive']
    neg = [r for r in rows if r['gt_label'] == 'negative']

    out = []
    w = out.append

    w('| 预测 \\ GT | 阳性（24） | 阴性（24） | 合计 |')
    w('|---|---:|---:|---:|')
    for lab in LABELS:
        p = sum(1 for r in pos if r['label'] == lab)
        n = sum(1 for r in neg if r['label'] == lab)
        w('| `%s` | %d | %d | %d |' % (lab, p, n, p + n))
    w('| **合计** | %d | %d | %d |' % (len(pos), len(neg), len(rows)))
    w('')

    w('| 口径 | 判正 | TP | FP | FN | P | R | F1 |')
    w('|---|---:|---:|---:|---:|---:|---:|---:|')
    for k in ('A_any_positive', 'B_breaking_only', 'C_specific', 'D_abstain_negative'):
        c = ev['counts'][k]
        p, r, f1 = ev[k]
        w('| %s | %d | %d | %d | %d | %s | %s | %s |' % (
            k, c['pred_positive'], c['tp'], c['fp'], c['fn'], p, r, f1))
    w('')

    ab = ev['abstain']
    w('弃权 %d 条：阴性 %d 条、阳性 %d 条，弃权精确率 %s%%。'
      % (ab['n'], ab['on_negative'], ab['on_positive'], ab['precision_of_abstain']))
    w('')

    # 阳性按类型 × 预测
    w('| 类型 | n | breaking | missing | stale | no_update | 抓到的 |')
    w('|---|---:|---:|---:|---:|---:|---:|')
    for t in ('api', 'configuration', 'input_format', 'lifecycle', 'state', 'mix'):
        sub = [r for r in pos if r['gt_type'] == t]
        c = Counter(r['label'] for r in sub)
        hit = len(sub) - c['no_update']
        w('| %s | %d | %d | %d | %d | %d | %d/%d |' % (
            t, len(sub), c['test_breaking'], c['test_missing'],
            c['test_stale'], c['no_update'], hit, len(sub)))
    w('')

    # 阳性按可见性 × 预测
    w('| GT 可见性 | n | breaking | missing | stale | no_update | 抓到的 |')
    w('|---|---:|---:|---:|---:|---:|---:|')
    for vis in ('explicit', 'silent'):
        sub = [r for r in pos if r['gt_visibility'] == vis]
        c = Counter(r['label'] for r in sub)
        hit = len(sub) - c['no_update']
        w('| %s | %d | %d | %d | %d | %d | %d/%d |' % (
            vis, len(sub), c['test_breaking'], c['test_missing'],
            c['test_stale'], c['no_update'], hit, len(sub)))
    w('')

    # 各标签的"独占精度"
    w('| 标签 | 阳性 | 阴性 | 该标签的精度 |')
    w('|---|---:|---:|---:|')
    for lab in LABELS[:3]:
        p = sum(1 for r in pos if r['label'] == lab)
        n = sum(1 for r in neg if r['label'] == lab)
        w('| `%s` | %d | %d | %s%% |' % (lab, p, n,
                                         round(100.0 * p / (p + n), 1) if p + n else '-'))
    w('')

    w('漏检（阳性判 no_update，%d 条）：' % sum(1 for r in pos if r['label'] == 'no_update'))
    w('')
    w('| 编号 | 类型 | 可见性 | 可达集 | ast 失败 | 直接原因 |')
    w('|---|---|---|---:|---:|---|')
    for r in pos:
        if r['label'] != 'no_update':
            continue
        e = r['evidence']
        note = e.get('reason') or ''
        if reach_status(r) != 'ok':
            note = '**无证据**：可达集算不出来（%s）' % reach_reason(r)
        elif e.get('timeout'):
            note = '**无证据**：case 超时收缩'
        elif (e.get('ast') or {}).get('fail_n', 0) >= 5:
            note = 'AST 大面积不完整，结论偏弱'
        elif e.get('reach', {}).get('size', 0) > 0:
            note = '可达集里没有签名/结构差异（改动在静态 IR 之外）'
        w('| %s | %s | %s | %s | %s | %s |' % (
            r['id'], r['gt_type'], r['gt_visibility'],
            (e.get('reach') or {}).get('size', '-'),
            (e.get('ast') or {}).get('fail_n', 0), note))
    w('')

    w('误报（阴性判 B/S/M，%d 条）：' % sum(1 for r in neg if r['label'] != 'no_update'))
    w('')
    w('| 编号 | 类型 | 预测 | 触发证据 |')
    w('|---|---|---|---|')
    for r in neg:
        if r['label'] == 'no_update':
            continue
        d = (r['evidence'].get('decision') or {})
        ev_list = (d.get('body_changed_reachable') or [])[:3] + \
                  (d.get('missing_unreachable') or [])[:3]
        w('| %s | %s | %s | %s |' % (r['id'], r['gt_type'], CN[r['label']],
                                     ', '.join(ev_list) if ev_list else '-'))
    w('')

    ab2 = ev.get('ablation_body_static')
    if ab2:
        c = ab2['counts']
        w('敏感性：行为层改成"公开 + 可达 static"（`--body-static`，由 evidence 离线复算）→ '
          'D 口径 TP=%d FP=%d FN=%d，P/R/F1=%s，阴性弃权 %d/24。'
          % (c['tp'], c['fp'], c['fn'], ab2['D_abstain_negative'],
             ab2['abstain_on_negative']))
        w('')

    no_ev = [r for r in rows if reach_status(r) != 'ok']
    w('运行期状态：`reach.status != ok`（可达集算不出来 → 该条 no_update 是"无证据"，不是结论）'
      '= %s；`timeout` = %s；ast 失败总数 %d 条（%d 个 case 有失败）。'
      % ([(r['id'], r['gt_label'][:3], reach_reason(r)) for r in no_ev],
         [r['id'] for r in rows if r['evidence'].get('timeout')],
         sum(r['evidence'].get('ast', {}).get('fail_n', 0) for r in rows),
         sum(1 for r in rows if r['evidence'].get('ast', {}).get('fail_n', 0))))

    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
