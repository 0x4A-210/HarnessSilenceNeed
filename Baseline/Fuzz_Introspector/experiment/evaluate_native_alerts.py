#!/usr/bin/env python3
"""Score frozen upstream blocked alerts against labels; never run a detector.

This is an external proxy evaluation, not an upstream maintenance classifier.
Failed executions remain distinct from successful runs without alerts. For the
end-to-end 47-case score they are undetected; also report the complete subset.
"""
import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'experiment/results/snapshot-47-20261115-142004'
DATASET = ROOT.parent / 'Dataset-v9/Dataset-v9/dataset/cases'
DEST = ROOT / 'experiment/results/evaluation-47-native-blocked'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(rows):
    counts = Counter(r['outcome'] for r in rows)
    tp, fp, tn, fn = (counts[k] for k in ('TP', 'FP', 'TN', 'FN'))
    ratio = lambda a, b: a / b if b else None
    return dict(n=len(rows), positive=tp+fn, negative=tn+fp,
                tp=tp, fp=fp, tn=tn, fn=fn,
                accuracy=ratio(tp+tn, len(rows)), precision=ratio(tp, tp+fp),
                recall=ratio(tp, tp+fn), false_positive_rate=ratio(fp, fp+tn),
                false_negative_rate=ratio(fn, tp+fn), f1=ratio(2*tp, 2*tp+fp+fn))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native-results', type=Path, default=SNAPSHOT / 'native-results.json')
    parser.add_argument('--expected-count', type=int, choices=(47, 48), default=47)
    args = parser.parse_args()
    native = json.loads(args.native_results.read_text())
    count = args.expected_count
    destination = ROOT / f'experiment/results/evaluation-{count}-native-blocked'
    expected = {f'V3-{n:02}' for n in range(1, count + 1)}
    assert len(native) == count and {r['case_id'] for r in native} == expected
    labels = {}
    for folder, dirs, files in os.walk(DATASET):
        dirs[:] = [d for d in dirs if d not in ('input', 'verification', '.git')]
        if 'label.json' not in files:
            continue
        path = Path(folder) / 'label.json'
        label = json.loads(path.read_text())
        assert label['id'] not in labels
        labels[label['id']] = (label, path)
        dirs.clear()

    rows = []
    for item in native:
        label, label_path = labels[item['case_id']]
        # Retain the original HTML conclusion. Do not recompute its threshold.
        alarms = item['native_blocked_conclusions']
        assert all(a.startswith(f"Fuzzer {item['harness_target']} is blocked:") for a in alarms)
        if item['native_report']:
            assert sha256(ROOT / item['native_report']) == item['report_sha256']
        positive = label['label'] == 'positive'
        alarm = bool(alarms)
        full = item['helper_exit'] == 0
        assert full or not alarm
        outcome = ('TP' if alarm else 'FN') if positive else ('FP' if alarm else 'TN')
        visibility = '显' if label['need_visibility'] == 'explicit' else '隐'
        cell = (f"阳-{visibility}-{'本次' if label['introduced_by_this_change'] else '非本次'}"
                if positive else f'阴-{visibility}')
        rows.append(dict(case_id=item['case_id'], project=item['project'],
                         truth_label=label['label'], degradation_type=label['degradation_type'],
                         visibility=label['need_visibility'],
                         introduced_by_this_change=label['introduced_by_this_change'],
                         cell=cell, native_blocked_alarm=alarm,
                         full_pipeline_success=full,
                         observation_status=('alert' if alarm else 'no_alert') if full else 'execution_failed',
                         outcome=outcome, native_conclusions=alarms,
                         native_report=item['native_report'], run_folder=item['run_folder'],
                         label_path=str(label_path.relative_to(ROOT.parent)),
                         label_sha256=sha256(label_path)))

    complete = [r for r in rows if r['full_pipeline_success']]
    failed = [r for r in rows if not r['full_pipeline_success']]
    all_key, complete_key = f'all_{count}', f'complete_{len(complete)}'
    summary = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                   evaluation_kind='external_native_blocked_proxy',
                   signal='Literal upstream Fuzzer <declared target> is blocked conclusion',
                   failure_policy='No emitted alert; failed positive cases count as missed positives in the end-to-end score, not as confirmed negative predictions',
                   local_detection_rules_added=False,
                   native_maintenance_classifier_available=False,
                   excluded_cases=sorted({f'V3-{n:02}' for n in range(1, 49)} - expected),
                   native_results_path=str(args.native_results.resolve()),
                   snapshot_json_sha256=sha256(args.native_results),
                   unavailable_case_ids=[r['case_id'] for r in rows if not r['full_pipeline_success']],
                   outcome_case_ids={k: [r['case_id'] for r in rows if r['outcome'] == k]
                                     for k in ('TP', 'FP', 'TN', 'FN')})
    summary[all_key] = metrics(rows)
    summary[complete_key] = metrics(complete)
    destination.mkdir(exist_ok=True)
    (destination / 'metrics.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    (destination / 'per-case.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
    fields = [k for k in rows[0] if k != 'native_conclusions']
    with (destination / 'per-case.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)

    report = [
        f'# Dataset-v9：{count} 条官方原生 blocked 告警的外部评测', '',
        ('V3-48 已按用户要求中断，不进入本表。使用已经冻结的 V3-01 至 V3-47 原生结果，未重新运行或改动官方检测器。' if count == 47 else
         '使用已冻结的 V3-01 至 V3-47 原生结果，合并 2026-11-16 启动的 V3-48 独立重跑结果。其他 47 条未重新运行，官方检测器未修改。'), '',
        '## 统计口径', '',
        '- 阳性真值来自数据集 `label.json` 的 `label=positive`。标签仅用于本次结果对照，不参与先前的构建或原生分析。',
        '- 评测信号：官方 HTML 中声明 target 的原生 `Fuzzer … is blocked` 提示。有该提示记为告警，没有提示记为未告警。不重新计算覆盖率阈值，不增加编译失败、崩溃或 diff 匹配规则。',
        f'- {count} 条总体统计包含 {len(failed)} 条执行失败；这些样本没有可用的完整分析结果，**不是被证明为阴性**。端到端检出统计按未发出告警处理，其中 {sum(r["truth_label"] == "positive" for r in failed)} 条真实阳性计入 FN。同时列出排除执行失败后的 {len(complete)} 条子集。',
        '- 这是“原生覆盖受阻提示”对“维护真值”的**外部代理评测**，不表示官方 FI 自带维护分类器。之前原生报告中的维护指标 N/A 保留；本文件明确新增评测映射口径。',
        '- Accuracy=(TP+TN)/N；Precision=TP/(TP+FP)；Recall=TP/(TP+FN)；FPR=FP/(FP+TN)；FNR=FN/(TP+FN)；F1=2TP/(2TP+FP+FN)。', '',
        '## 总体指标', '',
        '| 统计范围 | N | TP | FP | TN | FN | 准确率 Acc | 精确率 P | 召回率 | 误报率 FPR | 漏报率 FNR | F1 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for title, key in [('全部已结束样本', all_key), ('完整流程成功子集', complete_key)]:
        m = summary[key]
        counts = ' | '.join(str(m[k]) for k in ('n', 'tp', 'fp', 'tn', 'fn'))
        values = ' | '.join(f'{m[k]:.2%}' for k in ('accuracy', 'precision', 'recall', 'false_positive_rate', 'false_negative_rate', 'f1'))
        report.append(f'| {title} | {counts} | {values} |')
    total = summary[all_key]
    successful_fn = sum(r['outcome'] == 'FN' for r in complete)
    failed_fn = sum(r['outcome'] == 'FN' for r in failed)
    report += ['', f'{count} 条中阳性 {total["positive"]} 条、阴性 {total["negative"]} 条；有告警 {total["tp"]+total["fp"]} 条，其中 {total["tp"]} 条为真阳性，{total["fp"]} 条为假阳性。{total["fn"]} 条漏报包含 {successful_fn} 条完整运行后未告警及 {failed_fn} 条执行失败。', '',
               '- TP：'+'、'.join(summary['outcome_case_ids']['TP'])+'。',
               '- FP：'+'、'.join(summary['outcome_case_ids']['FP'])+'。',
               '- FN：'+'、'.join(summary['outcome_case_ids']['FN'])+'。', '',
               '## 类型与六维分组', '',
               '每格为“判对数量 / 该格总数”；阳性判对是发出原生告警，阴性判对是未发出原生告警。类型、本次/非本次与显隐均为真值分组，不是 FI 输出。', '']
    cells = ['阳-显-本次', '阳-显-非本次', '阳-隐-本次', '阳-隐-非本次', '阴-显', '阴-隐']
    report += ['| 类型 | '+' | '.join(cells)+' |', '|---|'+'---:|'*6]
    for kind in ['api', 'configuration', 'input_format', 'state', 'lifecycle', 'mix', '合计']:
        values = []
        for cell in cells:
            group = [r for r in rows if r['cell'] == cell and (kind == '合计' or r['degradation_type'] == kind)]
            values.append(f"{sum(r['outcome'] in ('TP','TN') for r in group)}/{len(group)}")
        report.append('| '+kind+' | '+' | '.join(values)+' |')
    report += ['', f'## {count} 条逐条对照', '',
               '| 样本 | 项目 | 类型 | 真值分组 | 原生输出状态 | 统计结果 | 报告/日志 |',
               '|---|---|---|---|---|---|---|']
    names = dict(alert='blocked 告警', no_alert='完整运行，未告警', execution_failed='执行失败，无可用完整结果')
    for r in rows:
        link = f"[HTML]({r['native_report']})" if r['native_report'] else f"[日志]({r['run_folder']}/helper.log)"
        report.append(f"| {r['case_id']} | {r['project']} | {r['degradation_type']} | {r['cell']} | {names[r['observation_status']]} | {r['outcome']} | {link} |")
    report += ['', '## 结果解释与复核', '',
               '官方 `blocked` 提示关注运行覆盖与静态可达范围的比例。本轮所用版本在该比例低于 30% 时给出此原生提示（见官方 `html_report.py:355`）；此阈值未改动。它既不针对本次 diff，也不验证维护义务是否满足。局部维护缺口未必使整体比例低于阈值；短时语料运行或初始化条件也可能让无需维护的样本覆盖偏低。因此上述低召回及 V3-31 的误报不能解释为 FI 对维护语义进行了同等判断。', '',
               '每个 target 的语料生成预算为 30 秒；不做重复运行置信区间估计。'+('V3-48 被排除，结果不能标为完整 48 条结果。' if count == 47 else 'V3-48 单独重跑时临时增加 64 GiB 交换空间；检测算法、输入、告警阈值及 fuzzing 时间预算未改动。其他 47 条沿用冻结结果。'), '',
               f'- [指标 JSON](experiment/results/evaluation-{count}-native-blocked/metrics.json)、[逐条 CSV](experiment/results/evaluation-{count}-native-blocked/per-case.csv)、[逐条 JSON](experiment/results/evaluation-{count}-native-blocked/per-case.json)。',
               '- [原始 47 条快照](experiment/results/snapshot-47-20261115-142004/native-results.json)。',
               '- [V3-48 停止原因](V3-48-停止原因.md)。', '',
               '复算命令（在工程根目录）：', '',
               '```bash', 'python3 Fuzz_Introspector/experiment/evaluate_native_alerts.py'+('' if count == 47 else ' --expected-count 48 --native-results Fuzz_Introspector/experiment/results/snapshot-48-isolated-20261116/native-results.json'), '```', '']
    if count == 48:
        report += ['## V3-48 独立重跑', '',
                   '- [资源设置](experiment/results/v3-48-rerun-resource-setup.json)、[输入一致性](experiment/results/v3-48-rerun-input.json)、[收尾状态](experiment/results/v3-48-rerun-state.json)。',
                   '- [48 条原生结果快照](experiment/results/snapshot-48-isolated-20261116/native-results.json)。', '']
    (ROOT / f'REPORT-{count}-EVALUATION.md').write_text('\n'.join(report))
    print(json.dumps({k: summary[k] for k in (all_key, complete_key, 'unavailable_case_ids')}, indent=2))


if __name__ == '__main__':
    main()
