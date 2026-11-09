from __future__ import annotations
from scheme_v8.evaluation.dimensions import CELLS
from scheme_v8.evaluation.dimensions import TYPES

def _rate(n, d):
    return n / d if d else None

def _binary(tp, fp, tn, fn):
    return {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn, 'accuracy': _rate(tp + tn, tp + fp + tn + fn), 'recall': _rate(tp, tp + fn), 'false_positive_rate': _rate(fp, fp + tn), 'false_negative_rate': _rate(fn, tp + fn), 'precision': _rate(tp, tp + fp), 'f1': _rate(2 * tp, 2 * tp + fp + fn)}

def three_metrics(rows):
    pos = [r for r in rows if r['truth'] == 'positive']
    neg = [r for r in rows if r['truth'] == 'negative']
    maintenance = _binary(sum((r['maintenance_alarm'] for r in pos)), sum((r['maintenance_alarm'] for r in neg)), sum((not r['maintenance_alarm'] for r in neg)), sum((not r['maintenance_alarm'] for r in pos)))
    intro = [r for r in pos if r['truth_introduced_by_this_change'] is True]
    old = [r for r in pos if r['truth_introduced_by_this_change'] is False]
    if len(intro) + len(old) != len(pos):
        raise ValueError('Timing truth absent from a maintenance-positive sample')
    time_tp = sum((r['temporal_status'] == 'introduced' for r in intro))
    time_fp = sum((r['temporal_status'] == 'introduced' for r in old))
    time_tn = sum((r['temporal_status'] == 'preexisting' for r in old))
    temporal = _binary(time_tp, time_fp, time_tn, len(intro) - time_tp)
    temporal['accuracy'] = _rate(time_tp + time_tn, len(pos))
    temporal['false_positive_rate'] = _rate(time_fp, len(old))
    temporal['total'] = len(pos)
    temporal['unresolved_preexisting'] = len(old) - time_fp - time_tn
    temporal['unknown_or_no_gap'] = sum((r['temporal_status'] not in ('introduced', 'preexisting') for r in pos))
    temporal['wrong_decided'] = sum((r['temporal_status'] == 'preexisting' for r in intro)) + time_fp
    temporal['false_gap_alarms_on_negatives'] = sum((r['temporal_status'] in ('introduced', 'preexisting') for r in neg))
    temporal['policy'] = 'Introduced is positive; only maintenance positives have timing truth. Unknown/no_gap on a true positive counts as an error, never as preexisting.'
    exact_positive = sum((r['joint_alarm'] and r['joint_origin'] == ('introduced' if r['truth_introduced_by_this_change'] else 'preexisting') for r in pos))
    joint = _binary(exact_positive, sum((r['joint_alarm'] for r in neg)), sum((not r['joint_alarm'] for r in neg)), len(pos) - exact_positive)
    joint['policy'] = 'Strict end-to-end: positive counts correct only with correct timing; negative counts correct only with no joint alarm. Wrong/unknown timing on a positive counts as a miss, even if maintenance head alerted.'
    joint['alert_only'] = _binary(sum((r['joint_alarm'] for r in pos)), sum((r['joint_alarm'] for r in neg)), sum((not r['joint_alarm'] for r in neg)), sum((not r['joint_alarm'] for r in pos)))
    return {'maintenance': maintenance, 'temporal': temporal, 'joint': joint}

def three_matrices(rows):
    result = {name: {} for name in ('maintenance', 'temporal', 'joint')}
    for kind in (*TYPES, '合计'):
        for section in result:
            result[section][kind] = {}
        for title, category, visibility, origin in CELLS:
            group = [r for r in rows if (kind == '合计' or r['degradation_type'] == kind) and r['truth'] == category and (r['need_visibility'] == visibility) and (category == 'negative' or r['truth_introduced_by_this_change'] is origin)]
            n = len(group)
            if category == 'positive':
                exact = lambda r: r['temporal_status'] == ('introduced' if origin else 'preexisting')
                result['maintenance'][kind][title] = {'total': n, 'detected': sum((r['maintenance_alarm'] for r in group))}
                result['temporal'][kind][title] = {'total': n, 'correct': sum((exact(r) for r in group)), 'wrong': sum((r['temporal_status'] in ('introduced', 'preexisting') and (not exact(r)) for r in group)), 'unresolved': sum((r['temporal_status'] not in ('introduced', 'preexisting') for r in group))}
                result['joint'][kind][title] = {'total': n, 'exact': sum((r['joint_alarm'] and r['joint_origin'] == ('introduced' if origin else 'preexisting') for r in group)), 'alert': sum((r['joint_alarm'] for r in group))}
            else:
                result['maintenance'][kind][title] = {'total': n, 'false_alarms': sum((r['maintenance_alarm'] for r in group)), 'no_alarm': sum((not r['maintenance_alarm'] for r in group))}
                result['temporal'][kind][title] = {'total': n, 'gap_alarms': sum((r['temporal_status'] in ('introduced', 'preexisting') for r in group)), 'no_gap': sum((r['temporal_status'] == 'no_gap' for r in group)), 'unresolved': sum((r['temporal_status'] == 'unknown' for r in group))}
                result['joint'][kind][title] = {'total': n, 'false_alarms': sum((r['joint_alarm'] for r in group)), 'no_alarm': sum((not r['joint_alarm'] for r in group))}
    return result

def maintenance_resolution(rows):
    """Keep affirmative negatives separate from abstentions in alarm metrics."""
    counts = {truth: {status: sum((r['truth'] == truth and r['maintenance_verdict'] == status for r in rows)) for status in ('needs_update', 'satisfied_in_scope', 'unknown')} for truth in ('positive', 'negative')}
    positive, negative = (counts['positive'], counts['negative'])
    decided = sum((v for group in counts.values() for k, v in group.items() if k != 'unknown'))
    correct = positive['needs_update'] + negative['satisfied_in_scope']
    return {'counts': counts, 'negative_confirmation_rate': _rate(negative['satisfied_in_scope'], sum(negative.values())), 'satisfied_precision': _rate(negative['satisfied_in_scope'], negative['satisfied_in_scope'] + positive['satisfied_in_scope']), 'decided_rate': _rate(decided, len(rows)), 'strict_decision_accuracy': _rate(correct, len(rows)), 'decided_accuracy': _rate(correct, decided), 'policy': 'Unknown is abstention, not a confirmed negative; strict accuracy counts it as incorrect.'}
