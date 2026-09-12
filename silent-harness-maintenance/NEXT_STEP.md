# NEXT_STEP.md
# Next-Stage Execution Plan — Evolution-Induced Silent Fuzz Harness Maintenance

## 1. 目标

上一阶段已经得到以下结论：

- 旧的 `coverage degradation -> maintenance need` 标签定义不可靠；
- `Gap-Only` 会产生大量误报；
- `Evolution Attribution` 能显著降低误报；
- 当前 20 个 Verified Positive 中有 15 个属于 `VP1: S1+H0 FAIL, S1+H1 PASS`；
- VP1 主要是显式 build/runtime break，不足以支撑论文最核心的“静默 Harness 维护需求”；
- 上一阶段完整 Ground Truth 审计发生在预测之后，因此上一阶段只作为 development/pilot study，不作为最终无偏评测集。

本阶段目标是重新构造一个：

> **Ground Truth 在预测前完全冻结、重点包含 Silent Maintenance Positive 的独立数据集**

并在该独立数据集上重新评估：

1. Build-Only baseline
2. Gap-Only LLM
3. Evolution-Aware LLM

核心研究问题：

> 当一次 source commit 发生后，旧 Harness H0 仍然可以 build/run，但是否已经无法充分测试本次 commit 引入或改变的功能、入口、状态、配置或输入语义？

---

## 2. 核心定义

### 2.1 Explicit Maintenance Need

显式维护需求：

```text
S1 + H0
   -> build / link / runtime FAIL

S1 + H1
   -> PASS
```

记为：

```text
VP1
```

这类保留，但不是论文核心。

### 2.2 Silent Maintenance Need

静默维护需求：

```text
S1 + H0
   build PASS
   runtime PASS
```

但出现以下至少一种情况：

- 新增功能不可达；
- 新增 API / entry point 未暴露；
- 新 parser / decoder / writer / reader 未进入 fuzzing；
- 新协议状态无法进入；
- 新 configuration 未启用；
- 新 initialization / state requirement 未满足；
- 新 input constraint 导致浅层执行或 early return；
- changed-code coverage 明显不足；
- 新增关键函数的 reachability 明显不足。

并且：

```text
S1 + H1
```

能够明显改善上述问题。

这类为本阶段核心 Positive。

---

## 3. Positive Taxonomy

继续沿用以下分类：

### VP1 — Build / Runtime Compatibility

```text
S1 + H0 = FAIL
S1 + H1 = PASS
```

### VP2 — Changed-Code Coverage Recovery

`S1 + H0` 可正常运行，但 changed-code coverage 明显不足，且 `S1 + H1` 显著提高 changed-code coverage。

### VP3 — New Entry / API Exposure

本次 commit 新增 parser、decoder、writer、reader、public API、protocol handler 或 external entry point，H0 无法有效到达，而 H1 可以。

### VP4 — State / Configuration Adaptation

本次 commit 新增或改变 state requirement、initialization sequence、runtime configuration、compile-time configuration、API protocol requirement 或 semantic precondition，H0 无法满足，而 H1 可以。

### VP5 — Other Silent Adequacy Degradation

其他能够通过静态或动态证据证明：

```text
S0 + H0
   ->
S1 + H0
```

出现新的 Harness inadequacy，且：

```text
S1 + H1
```

能够恢复或显著改善。

---

## 4. 本阶段数据规模

目标独立数据集：

### Silent Positive

至少：

```text
20
```

优先：

```text
VP2 + VP3 + VP4 + VP5
```

要求：

```text
S1 + H0 build PASS
S1 + H0 runtime PASS
```

### Explicit Positive

可额外收集：

```text
10 VP1
```

单独报告，不与 Silent Positive 混合解释。

### Negative

目标：

```text
40–60
```

建议：

```text
50
```

最终推荐规模：

```text
20 Silent Positive
10 Explicit Positive
50 Negative
--------------------
Total = 80
```

如果无法得到至少 15 个 Silent Positive，则暂停扩展评测，优先判断数据可行性不足。

---

## 5. 强制实验顺序

必须严格按照以下顺序执行：

```text
Candidate Mining
    ↓
Full Ground Truth Audit
    ↓
Counterfactual Validation
    ↓
Ground Truth Freeze
    ↓
Blind Input Freeze
    ↓
Prompt Freeze
    ↓
Model/Parameter Freeze
    ↓
Blind Prediction
    ↓
Label Reveal
    ↓
Final Evaluation
```

禁止：

```text
Prediction
    ↓
再去修改 Ground Truth
```

本阶段所有 Ground Truth 必须在模型预测前完成并冻结。

---

## 6. Task 1：挖掘新的独立 Candidate

必须使用：

> **未参与上一阶段 60-case development dataset 的新 commit**

不得重复使用：

- 上一阶段 60 个 commit；
- 原始 13 个 degradation commit；
- 已用于 prompt / rule development 的 case。

优先从：

- 原有 10 个项目的新 commit；
- 额外新增 OSS-Fuzz C/C++ 项目；

中挖掘。

建议新增项目以降低 project-specific bias。

---

## 7. Candidate Mining 规则

优先寻找：

```text
Production Source Changed
        +
Fuzz Harness Changed
```

但 Harness Co-evolution 只作为 candidate signal，不等于 Positive。

Harness 路径匹配可包括：

```text
fuzz/
fuzzing/
fuzzers/
test/fuzz/
*_fuzz.c
*_fuzz.cc
*_fuzz.cpp
*_fuzzer.c
*_fuzzer.cc
*_fuzzer.cpp
LLVMFuzzerTestOneInput
```

记录：

```text
project
commit
parent
timestamp
source_files_changed
harness_files_changed
commit_message
changed_loc_source
changed_loc_harness
```

输出：

```text
data/new_candidates.csv
```

目标：

```text
>= 80 raw candidates
```

以保证后续可以筛出足够 Silent Positive。

---

## 8. Task 2：先做完整 Ground Truth Audit

注意：

> 本阶段必须先审计，再预测。

对每个 candidate 构造：

```text
S0
S1
H0
H1
```

其中：

```text
S0 = commit 前 production source
S1 = commit 后 production source
H0 = commit 前 Harness
H1 = commit 后 Harness
```

---

## 9. Task 3：Counterfactual 构建

对每个 candidate：

### Actual

```text
S1 + H1
```

### Counterfactual

```text
S1 + H0
```

同时保留：

```text
S0 + H0
```

用于判断该问题是否确实由本次 commit 引入。

最终需要比较：

```text
S0 + H0
S1 + H0
S1 + H1
```

---

## 10. Task 4：Build / Runtime Verification

必须记录：

```text
S0+H0 build
S0+H0 runtime

S1+H0 build
S1+H0 runtime

S1+H1 build
S1+H1 runtime
```

保存：

```text
results/build_runtime_validation.csv
```

字段至少包括：

```text
case_id
s0_h0_build
s0_h0_runtime
s1_h0_build
s1_h0_runtime
s1_h1_build
s1_h1_runtime
classification_hint
```

---

## 11. Task 5：Changed-Code Coverage

本阶段必须补充上一阶段未测量的：

> Changed-Code Coverage

不要只记录 overall coverage。

### 11.1 Changed Code 定义

针对：

```text
S0 -> S1
```

识别：

- newly added lines；
- modified functions；
- newly added functions；
- modified branches。

### 11.2 Coverage 测量

至少测：

```text
ChangedCoverage(S1,H0)
ChangedCoverage(S1,H1)
```

计算：

```text
DeltaChangedCoverage
    =
ChangedCoverage(S1,H1)
    -
ChangedCoverage(S1,H0)
```

保存：

```text
results/changed_code_coverage.csv
```

字段：

```text
case_id
changed_lines
changed_functions
h0_changed_lines_covered
h1_changed_lines_covered
h0_changed_coverage
h1_changed_coverage
delta_changed_coverage
```

如果某 case 无法可靠测量：

```text
NOT_MEASURED
```

禁止填估算值。

---

## 12. Task 6：New Function Reachability

识别：

```text
F_new = 本次 commit 新增的函数
```

测量：

```text
Reachable(S1,H0)
Reachable(S1,H1)
```

优先关注：

- public API；
- parser；
- decoder；
- protocol handler；
- writer / reader；
- externally reachable functionality。

保存：

```text
results/reachability_validation.csv
```

---

## 13. Task 7：State / Configuration Validation

若 commit 涉及：

- initialization；
- state transition；
- compile-time macro；
- runtime flag；
- protocol setup；
- context setup；
- semantic precondition；

必须明确记录：

```text
H0 是否满足
H1 是否满足
```

并保留具体代码证据。

输出：

```text
results/state_config_validation.csv
```

---

## 14. Verified Silent Positive 判定

一个 case 只有在以下条件全部满足时才可标为：

```text
VERIFIED_SILENT_POSITIVE
```

### Condition A

```text
S1 + H0 build PASS
```

### Condition B

```text
S1 + H0 runtime PASS
```

### Condition C

存在由本 commit 新引入或明显加剧的 Harness inadequacy。

### Condition D

该 inadequacy 可以通过至少一种客观证据证明：

- changed-code coverage；
- function reachability；
- entry-point exposure；
- early-return/state evidence；
- configuration evidence；
- API protocol evidence。

### Condition E

```text
S1 + H1
```

能够明显恢复或改善该 inadequacy。

---

## 15. Existing Gap 不得算 Positive

若：

```text
S0 + H0
```

已经存在同样 Harness gap，且：

```text
S1 + H0
```

没有明显加剧，则分类：

```text
EXISTING_GAP
```

不得作为 Maintenance Positive。

---

## 16. Negative Ground Truth

Negative 必须在预测前完成审计。

推荐 Negative 类型：

### N1 — Internal Refactor

代码变化明显，但 Harness requirements 不变。

### N2 — New Internal Helper

新增函数，但函数已经位于 H0 的现有调用路径。

### N3 — Bounds / Error Handling Change

源码改变，但 H0 仍然可以进入相关功能。

### N4 — Existing Gap

项目中存在未覆盖 API，但不是本 commit 新引入。

### N5 — Side Subsystem Change

commit 修改的子系统不属于当前 Harness 的目标 scope。

### N6 — State Change Already Satisfied

状态条件变化，但 H0 已满足要求。

---

## 17. Ground Truth Freeze

完整审计完成后，生成：

```text
frozen-ground-truth/
```

目录：

```text
frozen-ground-truth/
├── labels.csv
├── silent_positive.csv
├── explicit_positive.csv
├── negative.csv
└── audit_manifest.json
```

`labels.csv` 字段至少包括：

```text
case_id
project
label
positive_type
build_h0
runtime_h0
changed_coverage_h0
changed_coverage_h1
reachability_h0
reachability_h1
evidence_type
audit_status
```

必须生成：

```text
ground_truth_frozen_at
dataset_hash
```

Ground Truth Freeze 完成后：

> 禁止重新标注。

若发现严重错误：

```text
标记为 INVALID
```

不得事后改成另一标签继续计算主结果。

所有 invalidation 必须单独记录。

---

## 18. Blind Input Freeze

Ground Truth Freeze 后生成：

```text
frozen-inputs/
```

每个 case：

```text
frozen-inputs/C001.md
frozen-inputs/C002.md
...
```

只允许包含：

- Existing Harness H0；
- S0 -> S1 production source diff；
- 按固定规则选择的必要 context。

严禁包含：

- H1；
- Harness diff；
- Ground Truth；
- coverage result；
- reachability result；
- counterfactual result；
- developer 后续修改；
- label；
- positive type。

生成：

```text
input_manifest.json
input_hash
```

---

## 19. Context Selection 必须冻结

上下文选择规则必须在正式 prediction 前确定。

推荐：

### 必选

- complete source diff；
- H0；
- changed function body。

### 可选

仅按固定规则补充：

- one-hop caller；
- one-hop callee；
- relevant public API declaration；
- relevant type definition；
- relevant macro/configuration declaration。

禁止：

> 根据 Ground Truth 为某个 case 单独补充有利 context。

---

## 20. Prompt Freeze

必须在正式测试前冻结三个 baseline。

### B0 — Build-Only Baseline

不调用 LLM。

规则：

```text
if S1 + H0 build FAIL
   or S1 + H0 runtime FAIL:
    maintenance_needed = YES
else:
    maintenance_needed = NO
```

该 baseline 用于证明：

> LLM 是否只是检测显式 Harness break。

### B1 — Gap-Only LLM

只判断：

> S1 + H0 是否存在 Harness Gap？

不做 evolution attribution。

最终：

```text
gap_exists = YES
    ->
maintenance_needed = YES
```

### B2 — Evolution-Aware LLM

必须分两步：

#### Stage 1

```text
Does a Harness Gap exist?
```

#### Stage 2

```text
Is this gap introduced or aggravated by S0 -> S1?
```

最终：

```text
maintenance_needed
    =
gap_exists
    AND
commit_induced
```

---

## 21. 正式输出 Schema

Evolution-Aware 输出：

```json
{
  "case_id": "C001",
  "gap_exists": true,
  "gap_type": [
    "new_entry_point"
  ],
  "commit_induced": true,
  "maintenance_needed": true,
  "confidence": 91,
  "affected_functions": [
    "parse_avif"
  ],
  "reason": "...",
  "evidence": [
    "..."
  ],
  "recommended_action": "..."
}
```

所有模型输出必须严格保存原始结果。

---

## 22. Prediction Freeze

正式运行前记录：

```text
model
model_version
system_prompt
user_prompt_template
reasoning_effort
temperature
max_tokens
context_selection_version
dataset_hash
input_hash
prompt_hash
```

保存：

```text
frozen-experiment-config.json
```

---

## 23. Blind Prediction 要求

正式 prediction：

- 每个 case 一次；
- 独立 context；
- 不重试；
- 不根据结果修改 Prompt；
- 不根据结果补 context；
- 不查看 label；
- 不查看 H1；
- 不查看 counterfactual evidence。

输出：

```text
predictions/
├── build_only.csv
├── gap_only.jsonl
└── evolution_aware.jsonl
```

---

## 24. 正式评测顺序

全部 prediction 完成并冻结后：

```text
Reveal Ground Truth
```

然后计算指标。

---

## 25. 必须分开报告两类 Positive

正式结果禁止只报告：

```text
All Positive Recall
```

必须至少分别报告：

### Explicit Positive

```text
VP1 Recall
```

### Silent Positive

```text
VP2 + VP3 + VP4 + VP5 Recall
```

核心论文结果优先使用：

```text
Silent Positive Recall
```

---

## 26. Metrics

至少计算：

- TP；
- FP；
- FN；
- TN；
- Precision；
- Recall；
- F1；
- FPR；
- Specificity。

重点：

```text
Silent Positive Recall
Negative FPR
Hard Negative FPR
```

---

## 27. Baseline Comparison

必须至少报告：

| Baseline | Explicit Recall | Silent Recall | FPR |
|---|---:|---:|---:|
| Build-Only | | | |
| Gap-Only | | | |
| Evolution-Aware | | | |

核心关注：

1. Build-Only 能识别多少 VP1？
2. Build-Only 对 Silent Positive 是否基本无效？
3. Gap-Only 是否仍然高 FP？
4. Evolution Attribution 是否显著降低 FP？
5. Evolution-Aware 是否能够在保持较高 Silent Recall 的同时控制 FPR？

---

## 28. Evolution Attribution 的核心检验

计算：

```text
FP_reduction
    =
(FP_gap_only - FP_evolution_aware)
    /
FP_gap_only
```

同时计算：

```text
Recall_drop
    =
Recall_gap_only - Recall_evolution_aware
```

理想结果：

```text
FP 显著下降
Recall 仅小幅下降
```

---

## 29. Reason / Evidence Audit

对以下 case 做人工审计：

- 所有 Silent TP；
- 所有 FP；
- 所有 FN；
- 随机 10 个 TN。

记录：

```text
Decision Correct
Reason Correct
Evidence Grounded
Attribution Correct
```

输出：

```text
results/reasoning_audit.csv
```

---

## 30. 特别关注 Existing Gap FP

必须单独统计：

```text
existing_gap_fp
```

因为这是上一阶段最主要的 failure mode。

分析：

> Evolution-Aware 是否能把 historical gap 与 current commit-induced gap 区分开？

---

## 31. 本阶段 Go / No-Go

### STRONG GO

建议同时满足：

#### Data

```text
Silent Verified Positive >= 20
```

#### Silent Positive Detection

```text
Silent Recall >= 75%
```

#### False Positive

```text
FPR <= 5%
```

#### Attribution

相比 Gap-Only：

```text
FP reduction >= 50%
```

#### Explanation

大多数 Silent TP：

```text
Reason Correct
Evidence Grounded
Attribution Correct
```

### MODERATE GO

建议满足：

```text
Silent Positive >= 15
Silent Recall >= 60%
FPR <= 10%
Evolution Attribution 能明显降低 FP
```

### NO-GO

出现以下任一：

```text
Silent Positive < 15
Silent Recall < 50%
FPR > 15%
Evolution Attribution 无明显作用
Ground Truth 无法稳定冻结
changed-code coverage / reachability 无法可靠验证
```

---

## 32. 上一阶段数据的处理

上一阶段 60-case dataset 标记为：

```text
DEVELOPMENT_SET
```

用途仅限：

- taxonomy development；
- prompt design；
- failure analysis；
- method development。

不得加入：

```text
NEW_BLIND_TEST_SET
```

不得用于最终无偏主结果。

---

## 33. 最终目录结构

```text
silent-harness-maintenance/
│
├── NEXT_STEP.md
├── README.md
│
├── data/
│   ├── new_candidates.csv
│   ├── candidate_audit.csv
│   └── excluded_cases.csv
│
├── ground-truth/
│   ├── build_runtime_validation.csv
│   ├── changed_code_coverage.csv
│   ├── reachability_validation.csv
│   └── state_config_validation.csv
│
├── frozen-ground-truth/
│   ├── labels.csv
│   ├── silent_positive.csv
│   ├── explicit_positive.csv
│   ├── negative.csv
│   └── audit_manifest.json
│
├── frozen-inputs/
│   ├── C001.md
│   ├── C002.md
│   └── input_manifest.json
│
├── prompts/
│   ├── gap_only_prompt.md
│   └── evolution_aware_prompt.md
│
├── predictions/
│   ├── build_only.csv
│   ├── gap_only.jsonl
│   └── evolution_aware.jsonl
│
├── results/
│   ├── overall_metrics.csv
│   ├── silent_positive_metrics.csv
│   ├── explicit_positive_metrics.csv
│   ├── hard_negative_metrics.csv
│   ├── reasoning_audit.csv
│   └── baseline_comparison.csv
│
└── reports/
    ├── dataset_construction.md
    ├── ground_truth_audit.md
    ├── blind_test_results.md
    ├── false_positive_analysis.md
    ├── false_negative_analysis.md
    └── go_no_go.md
```

---

## 34. 最终报告必须回答

最终 `blind_test_results.md` 必须明确回答：

1. 新挖掘了多少 candidate？
2. 多少 candidate 最终成为 Verified Silent Positive？
3. Silent Positive 中 VP2/VP3/VP4/VP5 各有多少？
4. VP1 有多少？
5. Ground Truth 是否在 prediction 前完全冻结？
6. Prediction 后是否发生任何 relabel？
7. Build-Only 对 Explicit / Silent Positive 分别表现如何？
8. Gap-Only 的 Silent Recall 和 FPR 是多少？
9. Evolution-Aware 的 Silent Recall 和 FPR 是多少？
10. Evolution Attribution 将 FP 降低了多少？
11. Existing Gap FP 是否明显减少？
12. 哪类 Silent Maintenance Need 最容易识别？
13. 哪类最难识别？
14. FN 是否主要来自 context insufficiency、state/configuration、跨文件语义或动态性能因素？
15. 是否达到 STRONG GO / MODERATE GO / NO-GO？

---

## 35. 本阶段最重要的执行原则

1. **先做 Ground Truth，再做 Prediction。**
2. **Silent Positive 是核心，VP1 只是辅助。**
3. `S1 + H0 build/run PASS` 不代表 Harness 足够。
4. 只关心本 commit 新引入或加剧的 gap。
5. Existing Gap 不算当前 commit Maintenance Need。
6. Changed-Code Coverage 和 Reachability 是验证证据，不是预测输入。
7. H1 只用于 Ground Truth，不得泄漏给待测模型。
8. 上一阶段 60-case 数据只能作为 development set。

---

## 36. 当前阶段一句话目标

> 构造一个在预测前完成完整反事实审计的独立数据集，重点验证 LLM 是否能够识别“Harness 仍能正常运行，但已无法充分测试本次软件演化”的 Silent Harness Maintenance Need。
