# 论文实验设计与第一阶段复现说明

## 1. 版本与研究问题

本文档以最终的 arXiv v2（2026-06-25，DOI `10.1145/3808172`）为准，不混用早期 v1 的样本数字。论文研究 OSS-Fuzz 中 C/C++ fuzz harness 随项目演化后，coverage 和 bug-finding capability 是否退化，并用人工 case study 分析明显 coverage drop 的原因。[^1][^2]

论文地址：https://arxiv.org/html/2505.06177

本阶段要构造 commit-level positive ground truth，因此直接复现 RQ4 的“明显 coverage drop”筛选及作者的人工 commit 归因；RQ1–RQ3 用于解释实验设计，不被改造成新的标签定义。

## 2. Dataset

论文收集区间为 2016-10 至 2024-10，数据来源包括 OSS-Fuzz 项目配置、每日 coverage HTML、各项目 `main_repo` 默认分支 Git 历史、harness changes 和 Monorail issues。[^1]

| 数据 | Raw | Clean | Filter |
|---|---:|---:|---:|
| Projects | 510 | 491 | 342 |
| Coverage reports | 665,165 | 574,840 | 453,744 |
| Commits | 8,297,824 | 2,556,947 | 2,357,857 |
| Harness changes / versions | 42,412 | 29,923 | 9,609 |
| Monorail issues | 68,486 | 53,460 | 49,020 |

清洗与过滤的关键规则：

1. 只保留 C/C++ 项目；Git 仓库取 OSS-Fuzz `project.yaml` 的 `main_repo`，只分析默认分支。
2. 去掉项目加入 OSS-Fuzz 之前和离开之后的数据；coverage 缺失日不算一条观测，但显式跟踪缺失。
3. 最终项目必须至少有一条 coverage、一项 harness update、一条 bug，并且累计至少 5,000 changed lines。
4. 论文的 `changed lines` / code churn 实际取 Git 报告的 C/C++ 文件 **added lines**；修改行也会以删除加新增中的新增部分计入。依赖的其他仓库不计入主项目 commit 总数。
5. harness-change heuristic：OSS-Fuzz 项目目录的相关修改，以及项目仓库内路径含 `fuzz`（排除 `fuzzy`）的 C/C++ 文件或包含 `LLVMFuzzerTestOneInput` / `LLVMFuzzerInitialize` 的文件。三日内连续更新合并成一次，以最后一次为该版本边界。
6. Monorail 最后一条数据为 2024-09-11；类型含 security bug、普通 bug 和 build failure。build failure 用于构建状态分析，不应误算成发现的程序 bug。[^1]

## 3. Degradation definition

论文有三个相关但用途不同的定义，不能混为一个标签：

### 3.1 RQ1：harness update 的即时效果

取 update 前后各 7 日的最大 line coverage；排除前后 7 日内还有另一次 harness update 的事件，并要求两侧都有 coverage。bug rate 同样比较 update 前后窗口。最终 6,411 个 harness versions，且对 `bugs / changed lines > 1` 的 176 个极端值做剔除/敏感性分析。统计检验为 paired Wilcoxon signed-rank。[^1]

这不是本阶段的 positive 标签。

### 3.2 RQ2：未更新 harness 的寿命退化

每个 harness version 的基线是其生命期前 3 日内的最高 coverage，用来吸收 coverage 饱和和 OSS-Fuzz 部署延迟。之后按时间或累计 churn 观察相对 coverage 变化；完整 build failure 被作为缺失排除，而不是当作 0 coverage。图中的 `degraded_5` 指相对该基线下降至少 5 个百分点。[^1][^4]

这也不是本阶段的 event/commit 标签。

### 3.3 RQ4：用于 case study 的 coverage-degradation event

论文文字描述是：

- drop 前后月度水平相差至少 5 个 coverage percentage points；
- 事件日相对上一有效观测下降至少 5pp；
- 后一月的最大 coverage 相对前一月最大值也下降至少 5pp，以去掉周期性抖动；
- 排除完全不能构建的 harness。

自动筛出 257 个重点事件；两名评审分别对 drop 前后 coverage、可用的 Fuzz Introspector、Git commits 和 build logs 做判断，再讨论达成一致。加上探索阶段记录，共 322 个 case studies。[^1][^5]

#### 本复现采用的 artifact 精确定义

设事件日为 `t`，`c_t` 为 OSS-Fuzz 项目聚合 line coverage 百分比。缺失报告在窗口统计中跳过：

- `B_t = {c[t-30], ..., c[t-1]}`；
- `A_t = {c[t], ..., c[t+30]}`，即 artifact 的 Julia 闭区间实现含事件日和后续 30 日；
- `center(S) = (mean(S) + median(S)) / 2`；
- `day_swing = c_t - 最近一个非缺失的先前 c`；
- `long_swing = center(A_t) - center(B_t)`；
- `max_swing = max(A_t) - max(B_t)`。

本阶段 positive 必须同时满足：

```text
not in first 30 project days
c_t > 0
day_swing  < -5
long_swing < -5
max_swing  < -5
```

阈值单位是绝对百分点（percentage points），不是相对下降 5%。artifact 使用严格 `< -5`，不是 `<= -5`。

需要特别记录一个可复现性差异：论文 prose 写“monthly average”，而当前 artifact 的 `calc_swing_long` 实际使用 `(mean + median) / 2`。为了“不重新设计定义”，本阶段以固定 artifact commit 的可执行代码为准，并在详细指标 CSV 中同时保留 mean、median、max，便于核查。[^1][^4]

原始实现位置：`artifact/harnesses_pluto.jl` 的 `calc_swing_long`、`calc_swing_day`、`calc_swing_long_max` 和 `df_swing_subset`。

## 4. Coverage metric

OSS-Fuzz 每日 HTML 来自 Clang source-based coverage，包含 line、function 和 region coverage。论文主分析采用：[^1][^7]

```text
line_coverage_percentage = covered_executable_lines / reachable_executable_lines * 100
```

分母并非项目源码总 LOC，而是经过 dead-code elimination 后，从任一 fuzz target 可达的行的并集。因此，仅改变 harness 或链接内容就可能改变分母；vendored library 进入报告也会严重扭曲百分比。论文同时检查绝对 covered lines，称主要结论相似，但 RQ4 筛选和本阶段 event metric 使用相对 line coverage。

这也解释了为什么本阶段 `harness_id` 是 `<project>::project_aggregate`：event 是从项目内所有 fuzz targets 的聚合日报识别出来的。artifact 没有给这些 RQ4 event 发布一个可靠的单 target coverage 序列，不能事后把聚合 drop 冒充成单一 target 标签。

## 5. Bug-finding capability metric

论文将 bug-finding capability 操作化为 code-churn-adjusted bug rate：

```text
bug_finding_rate = OSS-Fuzz bugs found / C/C++ changed lines
```

其中分母仍是 Git 在相关 C/C++ 文件中报告的 added lines（包含新增和修改后的行），而不是时间本身，也不是总 LOC。主要设计细节：

- RQ1 比较 harness update 前后 7 日的 `bugs / changed lines`；
- RQ3 以每个 harness version 为单位按周计算，并相对第一周比较；
- 另按每 2,000 changed lines 分桶，以区分时间流逝和实际代码演化；
- 删除 `> 1 bug / changed line` 的极端值，并做含极端值的敏感性分析；
- 对 harness 抽样 bootstrap 10,000 次，报告 95% CI；数据少于 100 个 active harnesses 时截断；
- coverage 分桶为 `<=20%`、`20–50%`、`>50%`；使用 Wilcoxon 检验。

论文观察到 update 后短暂 bug burst，但按 churn 校正后，未更新 harness 的 bug-finding rate 总体相当稳定。该指标用于 RQ1/RQ3，不参与本阶段 coverage-drop positive 的定义，避免标签泄漏和定义漂移。[^1]

## 6. Artifact

公开材料分为两部分：

1. GitHub artifact：Rust scraper、Julia 1.11.5 Pluto notebook、数据清洗代码、322 个 case-study notes、评审分歧 PDF、Fuzz Introspector alert 数据。这里固定到 commit `73843108273b97f05a583bc5226fa8177d88eb04`，避免上游后续变化。[^3][^5]
2. Zenodo `10.5281/zenodo.14000867`：十个 7z 分卷，总计 38.7 GB；解压后的 SQLite 约 90 GB，官方脚本说明临时空间约需 150 GB。artifact README 还说明 notebook 约需 15 GB 内存、运行可超过 10 分钟。[^3][^6]

重要限制：artifact 的原 Monorail scraper 已因 Monorail 被 Google Issue Tracker 取代而不能直接重跑；从零抓取论文全量数据还曾消耗超过 1 TB 网络和 250 GB 磁盘。因此本阶段没有声称从零重建论文全量数据库，而是固定作者 notes，并独立下载所选事件的 OSS-Fuzz 原始 coverage 与 Git 历史复算阈值。[^3]

artifact case-study notes 中 322 个 drop 的分类计数为：27 partial harness build failure、43 project code added、47 vendored library、71 queue entries decrease、87 low/unstable queue、28 code churn、6 gcov error、4 intended removal、9 unknown。核心的 project-code/code-churn 71 个案例进一步以 `cause:` 记录为 29 features、4 fuzzer regression/stricter checks、12 harness failure/mistake、3 other、23 revival。[^1][^5]

本阶段只从 `projectCode` 和 `codeChurn` 中选择能清晰落到 Git commit 且仍通过自动阈值的事件；没有把测量错误、外部库进入报告、corpus 失败或 unknown 混作“普通代码演化导致的 positive commit”。

## 7. 10 项目子集与 commit 映射

| project | commit 总数 | positive |
|---|---:|---:|
| c-ares | 1,046 | 2 |
| libplist | 361 | 2 |
| libspng | 776 | 1 |
| tidy-html5 | 248 | 1 |
| brotli | 388 | 1 |
| leptonica | 951 | 1 |
| meshoptimizer | 1,001 | 1 |
| wuffs | 3,064 | 2 |
| jansson | 145 | 1 |
| h2o | 8,175 | 1 |
| **合计** | **16,155** | **13** |

选择/映射规则：

1. 项目必须为 OSS-Fuzz C/C++ 项目，作者 notes 有 `projectCode` 或 `codeChurn` drop，并且 `main_repo` Git 历史可访问。
2. notes 必须给出明确 commit；不能只凭 diff 的语义自行猜测。一个透明例外是 notes 明示的 `wuffs-2020-02-06` two-part change，本数据以完成 part 的 commit 为 event anchor，并在配置和 README 标出。
3. commit 必须真实存在、位于当前默认分支祖先链、在项目加入 OSS-Fuzz 后且不晚于 2024-10-01。为避免今天的仓库中“后来合入但 author date 很老”的 commit 泄入，额外要求 committer time 不晚于数据库快照 2024-10-30；这只是冻结 commit universe，不改变 degradation 定义。
4. `commit_time` 取 Git author time 并统一为 UTC；`previous_commit` 取第一父节点。
5. 对事件日前 30 日、事件日起 31 日逐日下载公开 coverage HTML，完全按 artifact 公式复算。13/13 均通过全部自动谓词。[^4][^7]
6. `evidence_source` 同时给出固定 artifact 条目、drop 前/事件日 coverage URL 和 Git commit URL。

事件日期是 OSS-Fuzz coverage report 的日期，不必等于 Git author date；日报可能在提交次日才体现。精确构建时刻没有公开，因此因果归因来自两位作者评审的 notes，时间一致性只核验到 UTC 日粒度。

对 10 个项目中的 artifact case 做了完整选择审计：两类核心 cause 共 15 个 case，13 个唯一/明确映射纳入，另 2 个因为 notes 同时列出多个候选 commit 而排除；此外还有 3 个不属于本阶段 cause stratum 的测量/依赖/构建类 case。逐项原因见 `reports/selection_audit.md`，排除项仍是未标注而非 negative。

## 8. Ground-truth 语义与 Go / No-Go

最终 `degradation_events.csv` 的 13 行都满足两个层次：

- 数据层：公开 coverage 重算通过原始自动筛选；
- 归因层：作者 artifact 的人工 case study 将 drop 指向记录的 Git change。

`commit_universe.csv` 的其余 16,142 行标作 `unlabeled`，而不是 `negative`。原因是作者 artifact 发布的是经过筛选和人工研究的 coverage-drop cases，并没有逐 commit 证明所有其他 commit 都不导致 degradation。

因此本阶段准确结论是：**10 projects、16,155 commits、13 positive degradation commits**。按任务门槛，positive `< 30`，结论为 **NO-GO：先暂停，不建议直接做 ML**。

## 9. 可复核材料

- 最终事件：`data/processed/degradation_events.csv`
- 全 commit universe：`data/processed/commit_universe.csv`
- 阈值分解：`data/processed/coverage_event_metrics.csv`
- 原始逐日报告与 hash：`data/raw/coverage/download_manifest.csv`
- 逐事件完整证据：`evidence/positive_event_evidence.json`
- 13 个 positive 的独立检查汇总：`reports/validation.md`
- 10 项目内纳入/排除审计：`reports/selection_audit.md`
- 三个数字的机器可读版本：`summary.json`

## Sources

[^1]: Philipp Görz, Joschua Schilling, Nicolai Bissantz, and Thorsten Holz. “[An Empirical Study of Fuzz Harness Degradation](https://arxiv.org/html/2505.06177).” arXiv:2505.06177v2, 25 June 2026; DOI 10.1145/3808172.
[^2]: ACM SIGSOFT FSE. “[An Empirical Study of Fuzz Harness Degradation](https://conf.researchr.org/details/fse-2026/fse-2026-research-papers/126/An-Empirical-Study-of-Fuzz-Harness-Degradation).” FSE 2026 Research Papers.
[^3]: CISPA-SysSec. “[Fuzz Harness Degradation artifact README](https://github.com/CISPA-SysSec/fuzz-harness-degradation/blob/73843108273b97f05a583bc5226fa8177d88eb04/README.md).” Commit `73843108273b97f05a583bc5226fa8177d88eb04`.
[^4]: CISPA-SysSec. “[Julia Pluto analysis notebook](https://github.com/CISPA-SysSec/fuzz-harness-degradation/blob/73843108273b97f05a583bc5226fa8177d88eb04/harnesses_pluto.jl).” Commit `73843108273b97f05a583bc5226fa8177d88eb04`, especially `calc_swing_long`, `calc_swing_day`, and the RQ4 filters.
[^5]: CISPA-SysSec. “[Case-study classifications and notes](https://github.com/CISPA-SysSec/fuzz-harness-degradation/blob/73843108273b97f05a583bc5226fa8177d88eb04/case_studies/notes.md).” Commit `73843108273b97f05a583bc5226fa8177d88eb04`.
[^6]: Zenodo. “[Fuzz Harness Degradation](https://zenodo.org/records/14000867).” Dataset record 10.5281/zenodo.14000867, created 30 October 2024.
[^7]: Google OSS-Fuzz. “[Public coverage archive](https://storage.googleapis.com/oss-fuzz-coverage/).” Individual project-day URLs and SHA-256 values are recorded in `data/raw/coverage/download_manifest.csv`.
