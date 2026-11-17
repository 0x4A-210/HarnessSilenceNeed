# Dataset-v9：47 条官方原生 blocked 告警的外部评测

V3-48 已按用户要求中断，不进入本表。使用已经冻结的 V3-01 至 V3-47 原生结果，未重新运行或改动官方检测器。

## 统计口径

- 阳性真值来自数据集 `label.json` 的 `label=positive`。标签仅用于本次结果对照，不参与先前的构建或原生分析。
- 评测信号：官方 HTML 中声明 target 的原生 `Fuzzer … is blocked` 提示。有该提示记为告警，没有提示记为未告警。不重新计算覆盖率阈值，不增加编译失败、崩溃或 diff 匹配规则。
- 47 条总体统计包含 5 条执行失败；这些样本没有可用的完整分析结果，**不是被证明为阴性**。端到端检出统计按未发出告警处理，其中 5 条真实阳性计入 FN。同时列出排除执行失败后的 42 条子集。
- 这是“原生覆盖受阻提示”对“维护真值”的**外部代理评测**，不表示官方 FI 自带维护分类器。之前原生报告中的维护指标 N/A 保留；本文件明确新增评测映射口径。
- Accuracy=(TP+TN)/N；Precision=TP/(TP+FP)；Recall=TP/(TP+FN)；FPR=FP/(FP+TN)；FNR=FN/(TP+FN)；F1=2TP/(2TP+FP+FN)。

## 总体指标

| 统计范围 | N | TP | FP | TN | FN | 准确率 Acc | 精确率 P | 召回率 | 误报率 FPR | 漏报率 FNR | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 全部已结束样本 | 47 | 4 | 1 | 23 | 19 | 57.45% | 80.00% | 17.39% | 4.17% | 82.61% | 28.57% |
| 完整流程成功子集 | 42 | 4 | 1 | 23 | 14 | 64.29% | 80.00% | 22.22% | 4.17% | 77.78% | 34.78% |

47 条中阳性 23 条、阴性 24 条；有告警 5 条，其中 4 条为真阳性，1 条为假阳性。19 条漏报包含 14 条完整运行后未告警及 5 条执行失败。

- TP：V3-07、V3-10、V3-13、V3-18。
- FP：V3-31。
- FN：V3-01、V3-02、V3-03、V3-04、V3-05、V3-06、V3-08、V3-09、V3-11、V3-12、V3-14、V3-15、V3-16、V3-17、V3-43、V3-44、V3-45、V3-46、V3-47。

## 类型与六维分组

每格为“判对数量 / 该格总数”；阳性判对是发出原生告警，阴性判对是未发出原生告警。类型、本次/非本次与显隐均为真值分组，不是 FI 输出。

| 类型 | 阳-显-本次 | 阳-显-非本次 | 阳-隐-本次 | 阳-隐-非本次 | 阴-显 | 阴-隐 |
|---|---:|---:|---:|---:|---:|---:|
| api | 0/1 | 0/1 | 0/1 | 1/1 | 2/2 | 1/2 |
| configuration | 0/1 | 0/1 | 0/1 | 0/1 | 2/2 | 2/2 |
| input_format | 0/1 | 1/1 | 0/1 | 0/1 | 2/2 | 2/2 |
| state | 0/0 | 1/1 | 0/1 | 0/1 | 2/2 | 2/2 |
| lifecycle | 0/1 | 0/1 | 1/1 | 0/1 | 2/2 | 2/2 |
| mix | 0/1 | 0/1 | 0/1 | 0/1 | 2/2 | 2/2 |
| 合计 | 0/5 | 2/6 | 1/6 | 1/6 | 12/12 | 11/12 |

## 47 条逐条对照

| 样本 | 项目 | 类型 | 真值分组 | 原生输出状态 | 统计结果 | 报告/日志 |
|---|---|---|---|---|---|---|
| V3-01 | zlib | api | 阳-显-本次 | 执行失败，无可用完整结果 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-01/official-report/introspector-only/fuzz_report.html) |
| V3-02 | c-ares | configuration | 阳-显-本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-02/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-03 | jq | configuration | 阳-显-非本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-onig-20261114/V3-03/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-04 | json-c | api | 阳-显-非本次 | 执行失败，无可用完整结果 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-04/official-report/introspector-only/fuzz_report.html) |
| V3-05 | libucl | lifecycle | 阳-显-非本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-05/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-06 | mbedtls | mix | 阳-显-本次 | 执行失败，无可用完整结果 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-06/official-report/introspector-only/fuzz_report.html) |
| V3-07 | lz4 | input_format | 阳-显-非本次 | blocked 告警 | TP | [HTML](experiment/runs/official-v9-final-20261114/V3-07/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-08 | unbound | mix | 阳-显-非本次 | 执行失败，无可用完整结果 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-08/official-report/introspector-only/fuzz_report.html) |
| V3-09 | pcre2 | configuration | 阳-隐-本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-09/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-10 | libyaml | api | 阳-隐-非本次 | blocked 告警 | TP | [HTML](experiment/runs/official-v9-final-20261114/V3-10/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-11 | utf8proc | input_format | 阳-隐-非本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-11/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-12 | nlohmann-json | configuration | 阳-隐-非本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-12/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-13 | flac | state | 阳-显-非本次 | blocked 告警 | TP | [HTML](experiment/runs/official-v9-final-20261114/V3-13/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-14 | xz | state | 阳-隐-非本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-xz-20261114/V3-14/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-15 | zstd | input_format | 阳-隐-本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-15/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-16 | json-c | state | 阳-隐-本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-16/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-17 | libpng | lifecycle | 阳-隐-非本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-17/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-18 | libxml2 | lifecycle | 阳-隐-本次 | blocked 告警 | TP | [HTML](experiment/runs/official-v9-final-20261114/V3-18/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-19 | utf8proc | mix | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-19/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-20 | pugixml | api | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-20/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-21 | jansson | api | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-21/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-22 | cjson | lifecycle | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-22/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-23 | libyaml | input_format | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-23/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-24 | libcbor | input_format | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-24/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-25 | cmark | configuration | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-25/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-26 | lz4 | state | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-26/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-27 | miniz | lifecycle | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-27/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-28 | zstd | configuration | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-28/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-29 | tinyxml2 | mix | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-29/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-30 | md4c | mix | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-30/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-31 | libxml2 | api | 阴-隐 | blocked 告警 | FP | [HTML](experiment/runs/official-v9-final-20261114/V3-31/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-32 | fmt | configuration | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-32/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-33 | zstd | configuration | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-33/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-34 | tinyobjloader | input_format | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-34/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-35 | libspng | input_format | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-35/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-36 | expat | state | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-36/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-37 | jansson | lifecycle | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-37/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-38 | pugixml | mix | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-38/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-39 | cjson | lifecycle | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-39/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-40 | cmark | api | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-40/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-41 | libyaml | state | 阴-隐 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-41/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-42 | zlib | state | 阴-显 | 完整运行，未告警 | TN | [HTML](experiment/runs/official-v9-final-20261114/V3-42/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-43 | expat | api | 阳-隐-本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-43/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-44 | libspng | mix | 阳-隐-非本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-44/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-45 | nghttp2 | mix | 阳-隐-本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-45/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-46 | nlohmann-json | input_format | 阳-显-本次 | 完整运行，未告警 | FN | [HTML](experiment/runs/official-v9-final-20261114/V3-46/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-47 | postgresql | lifecycle | 阳-显-本次 | 执行失败，无可用完整结果 | FN | [日志](experiment/runs/official-v9-final-20261114/V3-47/helper.log) |

## 结果解释与复核

官方 `blocked` 提示关注运行覆盖与静态可达范围的比例。本轮所用版本在该比例低于 30% 时给出此原生提示（见官方 `html_report.py:355`）；此阈值未改动。它既不针对本次 diff，也不验证维护义务是否满足。局部维护缺口未必使整体比例低于阈值；短时语料运行或初始化条件也可能让无需维护的样本覆盖偏低。因此上述低召回及 V3-31 的误报不能解释为 FI 对维护语义进行了同等判断。

每个 target 的语料生成预算为 30 秒；不做重复运行置信区间估计。V3-48 被排除，结果不能标为完整 48 条结果。

- [指标 JSON](experiment/results/evaluation-47-native-blocked/metrics.json)、[逐条 CSV](experiment/results/evaluation-47-native-blocked/per-case.csv)、[逐条 JSON](experiment/results/evaluation-47-native-blocked/per-case.json)。
- [原始 47 条快照](experiment/results/snapshot-47-20261115-142004/native-results.json)。
- [V3-48 停止原因](V3-48-停止原因.md)。

复算命令（在工程根目录）：

```bash
python3 Fuzz_Introspector/experiment/evaluate_native_alerts.py
```
