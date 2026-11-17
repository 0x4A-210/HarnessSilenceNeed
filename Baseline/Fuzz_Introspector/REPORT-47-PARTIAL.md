# Fuzz Introspector：47 条阶段性统计

> 后续状态：2026-11-15 16:29（UTC+8）已按用户要求中断 V3-48，后台等待已停止。参见 [47 条外部告警评测](REPORT-47-EVALUATION.md) 与 [中断原因](V3-48-停止原因.md)。以下保留 14:20 的阶段性记录。

统计时间：2026-11-15T14:20:04+08:00。已结束 V3-01 至 V3-47；V3-48 尚未结束，不纳入以下分母。

官方分析代码未修改，未添加维护判定规则。采用官方 FI 提交 `341ebbd72bc9116733bcfcfab5adfd7f9b633e07` 和 OSS-Fuzz helper；版本与接入细节见 [执行协议](experiment/PROTOCOL.md) 和 [版本记录](experiment/provenance.json)。

## 总体运行结果

| 互斥的运行结果 | 条数 | 占已结束 47 条比例 |
|---|---:|---:|
| 官方完整流程成功 | 42 | 89.36% |
| 旧 harness 编译失败，仅生成官方源码分析报告 | 4 | 8.51% |
| PostgreSQL 运行及静态补跑失败，无最终 FI 报告 | 1 | 2.13% |
| 合计 | 47 | 100.00% |

另外，46/47 条生成了官方 HTML 报告（97.87%）；其中 42 条为完整流程报告，4 条仅为源码分析报告。5 条出现官方原生 `Fuzzer … is blocked` 提示。以上是运行/报告统计，**不是维护检测准确率**。

## 维护分类指标

| Precision | Recall | FPR | FNR | F1 |
|---|---|---|---|---|
| N/A | N/A | N/A | N/A | N/A |

本轮原生输出没有对应数据集“需要维护 / 不需要维护”的预测标签。`blocked` 表示运行覆盖相对静态可达范围受阻；编译失败和运行崩溃也不直接作为维护标签。本轮按“不加本地规则”的要求不做标签映射，因此不能直接计算维护分类的 TP、FP、TN、FN 及上述指标。

## 官方原生 blocked 提示

| 样本 | 项目 | 声明 target | 官方目标覆盖/可达比 |
|---|---|---|---:|
| V3-07 | lz4 | `compress_frame_fuzzer` | 0.00% |
| V3-10 | libyaml | `libyaml_emitter_fuzzer` | 16.03% |
| V3-13 | flac | `fuzzer_tool_flac` | 15.54% |
| V3-18 | libxml2 | `xinclude` | 16.28% |
| V3-31 | libxml2 | `xml` | 27.37% |

提示的原文保存在快照 JSON 中。未出现提示不等于被判定为维护阴性。

## 未完整跑通的五条

| 样本 | 项目 | 实际错误 |
|---|---|---|
| V3-01 | zlib | 旧 harness 调用参数过多：期望 1 个、实际 2 个。 |
| V3-04 | json-c | 使用未声明的 `jobj`，且 `json_object_to_json_string` 调用不匹配。 |
| V3-06 | mbedtls | 旧调用传入 5 个参数，当前接口要求 7 个。 |
| V3-08 | unbound | 旧调用传入 7 个参数，当前接口要求 8 个。 |
| V3-47 | postgresql | ASan 运行出现 ABRT，未生成可用覆盖率；静态补跑随后被终止，返回码 137，未生成最终 FI 报告。仅凭该返回码不认定为 OOM。 |

完整流程返回成功的样本也可能曾在语料生成时崩溃，官方 helper 允许继续。运行错误摘要还出现在 V3-05、V3-07、V3-18、V3-46；相关原文保留在逐条 JSON 和 helper 日志中。

## 47 条逐条记录

覆盖/可达比直接读取官方 target profile。源码分析报告没有对应的运行覆盖数据时用 —；blocked 列只记录原生提示是否出现，不能作为维护预测。

| 样本 | 项目 | 运行结果 | 目标覆盖/可达比 | 原生 blocked | 官方结果或日志 |
|---|---|---|---:|---|---|
| V3-01 | zlib | 编译失败；仅源码报告 | — | 不作运行覆盖判断 | [HTML](experiment/runs/official-v9-final-20261114/V3-01/official-report/introspector-only/fuzz_report.html) |
| V3-02 | c-ares | 完整成功 | 85.29% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-02/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-03 | jq | 完整成功 | 74.50% | 未出现 | [HTML](experiment/runs/official-v9-onig-20261114/V3-03/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-04 | json-c | 编译失败；仅源码报告 | — | 不作运行覆盖判断 | [HTML](experiment/runs/official-v9-final-20261114/V3-04/official-report/introspector-only/fuzz_report.html) |
| V3-05 | libucl | 完整成功 | 39.07% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-05/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-06 | mbedtls | 编译失败；仅源码报告 | — | 不作运行覆盖判断 | [HTML](experiment/runs/official-v9-final-20261114/V3-06/official-report/introspector-only/fuzz_report.html) |
| V3-07 | lz4 | 完整成功 | 0.00% | 出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-07/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-08 | unbound | 编译失败；仅源码报告 | — | 不作运行覆盖判断 | [HTML](experiment/runs/official-v9-final-20261114/V3-08/official-report/introspector-only/fuzz_report.html) |
| V3-09 | pcre2 | 完整成功 | 80.47% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-09/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-10 | libyaml | 完整成功 | 16.03% | 出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-10/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-11 | utf8proc | 完整成功 | 94.44% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-11/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-12 | nlohmann-json | 完整成功 | 68.55% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-12/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-13 | flac | 完整成功 | 15.54% | 出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-13/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-14 | xz | 完整成功 | 76.92% | 未出现 | [HTML](experiment/runs/official-v9-xz-20261114/V3-14/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-15 | zstd | 完整成功 | 75.19% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-15/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-16 | json-c | 完整成功 | 53.21% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-16/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-17 | libpng | 完整成功 | 31.58% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-17/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-18 | libxml2 | 完整成功 | 16.28% | 出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-18/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-19 | utf8proc | 完整成功 | 94.44% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-19/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-20 | pugixml | 完整成功 | 86.34% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-20/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-21 | jansson | 完整成功 | 79.10% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-21/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-22 | cjson | 完整成功 | 79.49% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-22/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-23 | libyaml | 完整成功 | 90.80% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-23/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-24 | libcbor | 完整成功 | 97.60% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-24/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-25 | cmark | 完整成功 | 93.78% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-25/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-26 | lz4 | 完整成功 | 81.58% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-26/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-27 | miniz | 完整成功 | 100.00% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-27/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-28 | zstd | 完整成功 | 52.18% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-28/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-29 | tinyxml2 | 完整成功 | 95.35% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-29/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-30 | md4c | 完整成功 | 93.65% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-30/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-31 | libxml2 | 完整成功 | 27.37% | 出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-31/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-32 | fmt | 完整成功 | 82.88% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-32/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-33 | zstd | 完整成功 | 57.11% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-33/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-34 | tinyobjloader | 完整成功 | 49.19% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-34/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-35 | libspng | 完整成功 | 57.02% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-35/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-36 | expat | 完整成功 | 78.82% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-36/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-37 | jansson | 完整成功 | 78.62% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-37/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-38 | pugixml | 完整成功 | 77.11% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-38/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-39 | cjson | 完整成功 | 82.05% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-39/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-40 | cmark | 完整成功 | 88.04% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-40/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-41 | libyaml | 完整成功 | 91.94% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-41/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-42 | zlib | 完整成功 | 79.69% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-42/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-43 | expat | 完整成功 | 80.43% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-43/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-44 | libspng | 完整成功 | 51.67% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-44/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-45 | nghttp2 | 完整成功 | 56.26% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-45/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-46 | nlohmann-json | 完整成功 | 75.38% | 未出现 | [HTML](experiment/runs/official-v9-final-20261114/V3-46/official-report/introspector-report/inspector/fuzz_report.html) |
| V3-47 | postgresql | 运行及补跑失败 | — | 不作运行覆盖判断 | [日志](experiment/runs/official-v9-final-20261114/V3-47/helper.log) |

## 尚未结束的 V3-48

截至 2026-11-15 14:20:04 +0800，binutils 修正重跑进程仍存在，尚无 `completed.json`。
最近采样：主进程在 `load_all_profiles` 中等待子进程退出；三个存活的工作进程在 `_load_profile` 的信号量获取位置等待。CPU 接近空闲，日志最后更新于 2026-11-15 04:54:48（UTC+8），已约 9 小时无更新。容器 `memory.events` 记录 `oom_kill 6`，说明发生过 6 次 OOM 杀进程事件；结合剩余工作进程全部等待信号量、主进程等待 join 的状态，疑似在工作进程异常退出后出现同步等待停滞。此状态不能表述为已完成，也不能保证仅继续等待就会自然结束。

遵照继续等待的要求，原任务及自动收尾程序保留运行。进程状态、原生退出结果和最终 48 条结果分别保留，不会以未完成样本补齐统计。

## 冻结快照与实时状态

- [47 条 CSV](experiment/results/snapshot-47-20261115-142004/native-results.csv)、[47 条完整原生 JSON](experiment/results/snapshot-47-20261115-142004/native-results.json)、[本次汇总 JSON](experiment/results/snapshot-47-20261115-142004/run-summary.json)。
- [实时收尾状态](experiment/results/finalization-state.json)。V3-48 结束后，后台程序会生成最终 `REPORT.md`；本阶段性报告保留原 47 条快照。
- [V3-48 内存事件](experiment/diagnostics/V3-48-memory-events-20261115.txt)。
- [V3-48 主进程栈](experiment/diagnostics/V3-48-stack-20261115-afternoon.txt)、[工作进程栈](experiment/diagnostics/V3-48-worker-131-20261115.txt)。

47 条输入、目标 harness、官方源码版本和结果文件哈希均已检查。严格的 48 条集合校验目前仅报告“缺少完整 48 条集合”，尚未完成的 V3-48 未被伪装为已通过。
