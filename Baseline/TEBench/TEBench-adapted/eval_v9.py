#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_v9.py —— 从 bsm_v9.json 重算 eval_v9.json 的全部指标（可独立复跑）

为什么要单独一个脚本
--------------------
之前只留了 results/eval_v9.json 这个结果文件，P/R/F1 是手算/临时脚本算的，
别人拿到仓库无法复核。本脚本把口径写死在代码里，任何人跑一遍都能得到同一组数字。

标签空间与任务定义
------------------
一次 commit 涉及的测试改动，只有两种"任务层面"的答案：

    positive = 这个测试**需要**更新（B / S / M 三种机制之一）
    negative = 这个测试**不需要**更新

分类器只输出 {test_breaking, test_stale, test_missing} 三种标签，**没有弃权出口**，
所以"预测为正"必须由三种口径分别定义（这是本记录的核心争议点）：

    A_any_positive    任意标签都算"需要更新"      → 预测为正 = 48/48（必然）
    B_breaking_only   只有 breaking 算"需要更新"  → 最保守
    C_specific        breaking 或 missing 算       → 有具体结构信号才算（stale 当弃权）

指标定义（单位：% ，保留 1 位小数）

    P  = TP / (TP + FP)        precision：判"需要更新"的里面有多少真的需要
    R  = TP / (TP + FN)        recall：真需要更新的里面抓到了多少
    F1 = 2PR / (P + R)

此外还有两个非 P/R 指标：

    type_accuracy  类型判别率。论文的 B/S/M 与 v9 的 explicit/silent 存在对应关系：
                   explicit（测试会编译失败/直接报错）应判 breaking；
                   silent（测试仍通过但语义失效）应判 stale 或 missing。
                   这个指标只有 24 条阳性参与，且 silent 侧 12/12 来自"默认类恰好落在
                   stale"，**不能当作识别能力**（见 VERIFY.md §5.2）。
    by_type        阳性按 6 种退化类型的预测分布，用来看规则在哪类上失效。

用法
----
    python eval_v9.py --pred results/bsm_v9.json --out results/eval_v9.json
    python eval_v9.py --pred results/bsm_v9.json --dataset <Dataset-v9/dataset> \
        --out results/eval_v9.json          # 额外用 dataset.json 核对 GT 是否被写错

依赖：只用标准库（Python 3.8+ 语法，无 3.9+ 特性）。
"""

import argparse
import json
import os
import sys
from collections import Counter, OrderedDict

LABELS = ('test_breaking', 'test_stale', 'test_missing')
ABSTAIN = 'no_update'                 # 路线 1.5 新增的第四类：弃权 = 判"不需要更新"
VALID = LABELS + (ABSTAIN,)

# "预测为正（需要更新）"的口径：名字 -> 判为正的标签集合
# D 是路线 1.5 的主口径：弃权算阴性；A/B/C 保留，供与路线 1 对照。
POSITIVE_RULES = OrderedDict([
    ('A_any_positive', set(LABELS)),
    ('B_breaking_only', {'test_breaking'}),
    ('C_specific', {'test_breaking', 'test_missing'}),
    ('D_abstain_negative', set(LABELS)),
])

# 路线 2（编译执行 + 覆盖率）额外统计：只保留"两个版本至少有一个真的编出来了"的样本。
# 这不是新的标签空间，而是把"没有执行证据"的行从分母里拿掉——和 §12.4.2 的
# reach.status 读法同构：算不出来的样本不该混进 P/R 里。
EXEC_OK = 'ok'


def pct(x):
    return None if x is None else round(x * 100.0, 1)


def prf(tp, fp, fn):
    """返回 (P, R, F1)，均为百分数、保留 1 位小数；分母为 0 时记 None。"""
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * p * r / (p + r)) if (p is not None and r is not None and (p + r)) else None
    return pct(p), pct(r), pct(f1)


def is_positive(row):
    return row.get('gt_label') == 'positive'


def expected_label(visibility):
    """explicit → breaking；silent → stale|missing。"""
    return {'explicit': {'test_breaking'},
            'silent': {'test_stale', 'test_missing'}}.get(visibility, set())


def load_rows(pred_path, dataset_path=None):
    rows = json.load(open(pred_path, encoding='utf-8'))
    if not isinstance(rows, list):
        raise SystemExit('%s 应该是 list[dict]（classify_bsm_c.py 的输出格式）' % pred_path)

    errors = [r for r in rows if r.get('label') not in VALID]
    if errors:
        print('[warn] %d 条样本没有有效预测，已排除：%s'
              % (len(errors), [r.get('id') for r in errors]), file=sys.stderr)
    rows = [r for r in rows if r.get('label') in VALID]

    # 用 dataset.json 反向核对 GT，避免"GT 写在预测文件里被改写"这类不可复核问题
    if dataset_path:
        man = json.load(open(os.path.join(dataset_path, 'dataset.json'), encoding='utf-8'))
        gt = {s['dir_id']: s for s in man['samples']}
        mismatch = []
        for r in rows:
            s = gt.get(r.get('id'))
            if s is None:
                mismatch.append((r.get('id'), 'not-in-dataset'))
                continue
            for k_row, k_ds in (('gt_label', 'label'),
                                ('gt_visibility', 'need_visibility'),
                                ('gt_type', 'degradation_type')):
                if r.get(k_row) != s.get(k_ds):
                    mismatch.append((r.get('id'), k_row, r.get(k_row), s.get(k_ds)))
        if mismatch:
            print('[warn] 预测文件里的 GT 与 dataset.json 不一致 %d 处：' % len(mismatch),
                  file=sys.stderr)
            for m in mismatch[:10]:
                print('   ', m, file=sys.stderr)
        else:
            print('[ok] GT 与 dataset.json 一致（%d 条）' % len(rows), file=sys.stderr)
    return rows


def dataset_tag(path):
    """把 .../Dataset-v9/dataset 记成 Dataset-v9，便于在结果里看出用的是哪套数据。"""
    if not path:
        return None
    p = os.path.normpath(path)
    base = os.path.basename(p)
    return os.path.basename(os.path.dirname(p)) if base == 'dataset' else base


def reach_unknown(row):
    """可达集是否算不出来（入口 TU 解析失败 / 超时）。

    这种样本的 no_update 是"没证据"，不是"确认不需要更新"，不能和真正的弃权混着引用。
    """
    e = row.get('evidence') or {}
    reach = e.get('reach') or {}
    st = reach.get('status')
    if st is None:                       # 兼容旧结果：那时字段叫 reach_unavailable
        return bool(e.get('reach_unavailable'))
    return st != 'ok'


def evaluate(rows, pred_path, dataset_path):
    pos = [r for r in rows if is_positive(r)]
    neg = [r for r in rows if not is_positive(r)]

    out = OrderedDict()
    counts = OrderedDict()

    for name, positive_labels in POSITIVE_RULES.items():
        tp = sum(1 for r in pos if r['label'] in positive_labels)
        fn = len(pos) - tp
        fp = sum(1 for r in neg if r['label'] in positive_labels)
        out[name] = list(prf(tp, fp, fn))
        counts[name] = OrderedDict([('tp', tp), ('fp', fp), ('fn', fn),
                                    ('pred_positive', tp + fp)])

    # 类型判别：只用阳性；explicit→breaking，silent→stale|missing
    vis_stat = OrderedDict()
    correct = 0
    for vis in ('explicit', 'silent'):
        sub = [r for r in pos if r.get('gt_visibility') == vis]
        ok = sum(1 for r in sub if r['label'] in expected_label(vis))
        vis_stat[vis] = OrderedDict([('correct', ok), ('n', len(sub))])
        correct += ok
    out['type_accuracy'] = pct(correct / len(pos)) if pos else None

    by_type = OrderedDict()
    for t in sorted({r.get('gt_type') for r in pos if r.get('gt_type')}):
        c = Counter(r['label'] for r in pos if r.get('gt_type') == t)
        by_type[t] = OrderedDict((k, c[k]) for k in VALID if c[k])
    out['by_type'] = by_type

    c = Counter(r['label'] for r in neg)
    out['negatives'] = OrderedDict((k, c[k]) for k in VALID if c[k])

    n_abstain = sum(1 for r in rows if r['label'] == ABSTAIN)
    abstain_right = sum(1 for r in neg if r['label'] == ABSTAIN)
    out['abstain'] = OrderedDict([
        ('n', n_abstain),
        ('on_positive', sum(1 for r in pos if r['label'] == ABSTAIN)),
        ('on_negative', abstain_right),
        ('precision_of_abstain', pct(abstain_right / n_abstain) if n_abstain else None),
    ])

    out['type_accuracy_detail'] = vis_stat

    # 无证据样本：可达集算不出来（reach.status != ok），它的 no_update 不能当结论引用
    ne = [r for r in rows if reach_unknown(r)]
    out['no_evidence'] = OrderedDict([
        ('n', len(ne)),
        ('ids', [r.get('id') for r in ne]),
        ('on_positive', sum(1 for r in ne if is_positive(r))),
        ('on_negative', sum(1 for r in ne if not is_positive(r))),
        ('note', 'reach.status != ok：harness 入口 TU 没解析出来，可达集算不出。'
                 '这些行的 no_update 含义是"没证据"，既不能算正确弃权，也不能算漏检；'
                 '引用 abstain / FN 数字时应把命中它们的部分扣掉。'),
    ])

    # ---- 路线 2：执行证据口径 ----
    if rows and any('exec_status' in r for r in rows):
        ok_rows = [r for r in rows if r.get('exec_status') == EXEC_OK]
        ok_pos = [r for r in ok_rows if is_positive(r)]
        ok_neg = [r for r in ok_rows if not is_positive(r)]
        tp = sum(1 for r in ok_pos if r['label'] in POSITIVE_RULES['D_abstain_negative'])
        fn = len(ok_pos) - tp
        fp = sum(1 for r in ok_neg if r['label'] in POSITIVE_RULES['D_abstain_negative'])
        out['E_exec_evidence'] = list(prf(tp, fp, fn))
        counts['E_exec_evidence'] = OrderedDict([('tp', tp), ('fp', fp), ('fn', fn),
                                                 ('pred_positive', tp + fp)])
        ne = [r for r in rows if r.get('exec_status') != EXEC_OK]
        out['exec_no_evidence'] = OrderedDict([
            ('n', len(ne)),
            ('ids', [r.get('id') for r in ne]),
            ('on_positive', sum(1 for r in ne if is_positive(r))),
            ('on_negative', sum(1 for r in ne if not is_positive(r))),
            ('note', '两版库/harness 都没编出来：这一行的标签没有执行证据支撑，'
                     '既不算正确弃权也不算漏检；口径 E 把它们整体剔出分母。'),
        ])

    out['counts'] = counts
    out['meta'] = OrderedDict([
        ('pred_file', os.path.basename(pred_path)),
        ('dataset', dataset_tag(dataset_path)),
        ('n_samples', len(rows)),
        ('n_positive', len(pos)),
        ('n_negative', len(neg)),
        ('classifier_has_abstain', n_abstain > 0),
        ('note', 'negative 的正确答案是"不需要更新"；有弃权出口时，'
                 'no_update 命中阴性不算 FP，判成 B/S/M 才算 FP。'),
    ])
    return out, counts, vis_stat, len(pos)


def print_report(rows, out, counts, vis_stat):
    print('样本 %d（阳性 %d / 阴性 %d）'
          % (len(rows), out['meta']['n_positive'], out['meta']['n_negative']))
    print()
    print('%-20s %5s %5s %5s %6s %7s %7s %7s' %
          ('口径', 'TP', 'FP', 'FN', '判正', 'P', 'R', 'F1'))
    for name in POSITIVE_RULES:
        c, (p, r, f1) = counts[name], out[name]
        print('%-20s %5d %5d %5d %6d %7s %7s %7s'
              % (name, c['tp'], c['fp'], c['fn'], c['pred_positive'], p, r, f1))
    if 'E_exec_evidence' in out:
        c, (p, r, f1) = counts['E_exec_evidence'], out['E_exec_evidence']
        print('%-20s %5d %5d %5d %6d %7s %7s %7s'
              % ('E_exec_evidence', c['tp'], c['fp'], c['fn'], c['pred_positive'], p, r, f1))
    ab = out['abstain']
    print('弃权 %d 条：其中阴性 %d 条（弃权精确率 %s%%），阳性 %d 条'
          % (ab['n'], ab['on_negative'], ab['precision_of_abstain'], ab['on_positive']))
    ne = out['no_evidence']
    if ne['n']:
        ne_rows = [r for r in rows if reach_unknown(r)]
        ne_tn = sum(1 for r in ne_rows if not is_positive(r) and r['label'] == ABSTAIN)
        ne_fn = sum(1 for r in ne_rows if is_positive(r) and r['label'] == ABSTAIN)
        print('无证据 %d 条（%s）：no_update 在这几行上是"算不出可达集"，'
              '不算正确弃权也不算漏检；扣掉后有证据支撑的弃权 = 阴性 %d 条、阳性漏检 %d 条'
              % (ne['n'], ','.join(ne['ids']),
                 ab['on_negative'] - ne_tn, ab['on_positive'] - ne_fn))
    ne2 = out.get('exec_no_evidence')
    if ne2 and ne2['n']:
        print('无执行证据 %d 条（%s）：两版都没编出来，口径 E 已剔除'
              % (ne2['n'], ','.join(ne2['ids'])))
    print()
    print('type_accuracy = %s%%  (explicit %d/%d, silent %d/%d)'
          % (out['type_accuracy'],
             vis_stat['explicit']['correct'], vis_stat['explicit']['n'],
             vis_stat['silent']['correct'], vis_stat['silent']['n']))
    print('注意：silent 侧全部由"默认类恰好是 stale"贡献，不代表识别能力。')
    print()
    print('阳性按退化类型：')
    for t, c in out['by_type'].items():
        print('  %-14s %s' % (t, dict(c)))
    print('阴性预测分布：%s' % dict(out['negatives']))


def relabel_body_static(rows):
    """离线复算：把行为层从"只算公开符号"切到"公开 + 可达 static"。

    ir_bsm.py 的 evidence.decision 里同时记了 body_changed_public_n / body_changed_static_n，
    所以这条口径切换不需要重跑 clang，直接在标签上复算即可（用于 §12 的敏感性分析）。
    rows 里没有这两个字段（路线 1 的旧输出）时返回 None。
    """
    if not any('body_changed_static_n' in (r.get('evidence', {}).get('decision') or {})
               for r in rows):
        return None
    out = []
    for r in rows:
        d = (r.get('evidence') or {}).get('decision') or {}
        q = dict(r)
        if d.get('sig_changed_reachable') or d.get('removed_reachable'):
            q['label'] = 'test_breaking'
        elif d.get('missing_unreachable'):
            q['label'] = 'test_missing'
        elif (d.get('body_changed_public_n') or 0) + (d.get('body_changed_static_n') or 0):
            q['label'] = 'test_stale'
        elif d:
            q['label'] = ABSTAIN
        out.append(q)
    return out


def main():
    ap = argparse.ArgumentParser(description='从 bsm_v9.json 重算指标')
    ap.add_argument('--pred', default='results/bsm_v9.json')
    ap.add_argument('--dataset', default=None,
                    help='Dataset-v9/dataset 根目录；给出则用 dataset.json 核对 GT')
    ap.add_argument('--out', default='results/eval_v9.json')
    args = ap.parse_args()

    if not args.dataset:
        # meta.dataset 会是 null，GT 核对也跳过——指标不受影响（GT 在预测文件里），
        # 但第三方拿到这份 JSON 就看不出用的是哪套数据，所以显式提醒一次。
        print('[warn] 没传 --dataset：meta.dataset 将写成 null，且跳过与 dataset.json 的 GT 核对；'
              '对外复现请带上这个参数。', file=sys.stderr)

    rows = load_rows(args.pred, args.dataset)
    out, counts, vis_stat, _ = evaluate(rows, args.pred, args.dataset)

    alt = relabel_body_static(rows)
    if alt is not None:
        alt_pos = [r for r in alt if is_positive(r)]
        alt_neg = [r for r in alt if not is_positive(r)]
        tp = sum(1 for r in alt_pos if r['label'] in POSITIVE_RULES['D_abstain_negative'])
        fn = len(alt_pos) - tp
        fp = sum(1 for r in alt_neg if r['label'] in POSITIVE_RULES['D_abstain_negative'])
        n_ab = sum(1 for r in alt if r['label'] == ABSTAIN)
        out['ablation_body_static'] = OrderedDict([
            ('note', 'D 口径下把行为层扩到"公开 + 可达 static"的复算结果（不重跑 clang）'),
            ('counts', OrderedDict([('tp', tp), ('fp', fp), ('fn', fn), ('pred_positive', tp + fp)])),
            ('D_abstain_negative', list(prf(tp, fp, fn))),
            ('abstain_on_negative', sum(1 for r in alt_neg if r['label'] == ABSTAIN)),
            ('abstain_n', n_ab),
        ])
        print('\n[ablation] 行为层含可达 static：D 口径 TP=%d FP=%d FN=%d  P/R/F1=%s'
              % (tp, fp, fn, out['ablation_body_static']['D_abstain_negative']))

    print_report(rows, out, counts, vis_stat)

    if args.out:
        d = os.path.dirname(os.path.abspath(args.out))
        if not os.path.isdir(d):
            os.makedirs(d)
        json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n[out] %s' % args.out)


if __name__ == '__main__':
    main()
