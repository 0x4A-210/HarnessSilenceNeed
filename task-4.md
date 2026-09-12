# N4 Existing-Gap Validation

## 1. 实验目标

本阶段只验证一个核心机制：

> **Evolution Attribution 是否能够区分“历史已经存在的 Harness Gap”和“由当前 commit 新引入或加剧的 Harness Gap”。**

这里不是为了单纯增加 Negative 数量，而是为了验证当前方法最关键的一步：

```text
Gap Detection
    +
Evolution Attribution
```

是否真的能够避免以下典型误报：

> Harness 确实存在测试盲区，但该盲区在当前 commit 之前就已经存在，因此不应该把它归因为本次 commit 的 Harness Maintenance Need。

---

## 2. 核心研究问题

### RQ-N4

当 `H0` 中已经存在一个 Harness Gap，而当前 commit 并没有新引入或加剧这个 Gap 时，Evolution-Aware 方法能否正确判断：

```text
gap_exists = YES
commit_induced = NO
maintenance_needed = NO
```

---

## 3. 核心定义

### 3.1 Existing Gap

在 commit 发生之前：

```text
S0 + H0
```

中已经存在某个 Harness Gap。

commit 之后：

```text
S1 + H0
```

该 Gap 仍然存在，但没有被当前 commit 新引入，也没有明显加剧。

因此：

```text
Gap(S0,H0) = YES
Gap(S1,H0) = YES
DeltaGap(S0->S1,H0) ≈ 0
```

最终：

```text
CommitInduced = NO
MaintenanceNeed = NO
```

### 3.2 Commit-Induced Gap

在 commit 前：

```text
S0 + H0
```

不存在目标 Gap，或该 Gap 明显较弱。

commit 后：

```text
S1 + H0
```

出现新的不可达、未暴露、状态不满足、配置不适配、输入约束加剧等问题。

因此：

```text
Gap(S0,H0) = NO / weaker
Gap(S1,H0) = YES / worse
CommitInduced = YES
MaintenanceNeed = YES
```

---

## 4. 本阶段数据构成

构造一个专门用于 Evolution Attribution 的独立测试集。

推荐规模：

```text
N4 Existing-Gap Negative      20–30
Matched Commit-Induced Positive 20–30
```

最低建议：

```text
20 N4 Negative
20 Positive
Total = 40
```

更理想：

```text
25 N4 Negative
25 Positive
Total = 50
```

---

## 5. 数据独立性要求

禁止使用已经参与以下用途的 case：

- 前期 60-case development set；
- 后续 77-case 有效集；
- 已用于 Prompt 调整的 case；
- 已用于错误分析或方法设计的 case；
- 已经人工看过结果后再挑选的 case。

优先从以下来源筛选：

- 新项目；
- 新 commit；
- 尚未进入现有实验集的历史 commit。

---

## 6. Task 1：挖掘 N4 Existing-Gap Candidates

筛选满足以下模式的真实 source commit：

```text
S0 + H0 中已经存在某个 Harness Gap
            ↓
当前 commit 修改了真实 production source
            ↓
S1 + H0 中该 Gap 仍然存在
            ↓
但当前 commit 没有新引入或明显加剧该 Gap
```

### N4-A：已有未覆盖 API

提交前已经存在：

```text
foo_api()
```

但 `H0` 从未调用。

当前 commit 修改：

```text
foo_cache()
foo_helper()
```

提交后 `foo_api()` 仍未被 H0 覆盖。

正确标签：

```text
gap_exists = YES
commit_induced = NO
maintenance_needed = NO
```

### N4-B：已有未覆盖子系统

项目已有：

```text
PNG
JPEG
WEBP
```

H0 长期只覆盖：

```text
PNG
JPEG
```

WEBP 从 commit 前就未覆盖。

当前 commit 只修改 PNG 内部逻辑。

则 WEBP 属于 Existing Gap，而不是当前 commit 的 Maintenance Need。

### N4-C：已有 State Gap

H0 一直没有进入某个 optional state / mode。

当前 commit 修改其他状态逻辑，但没有改变该 mode 的可达性要求。

则该 state gap 属于 Existing Gap。

### N4-D：已有 Configuration Gap

某 feature 长期依赖：

```text
#ifdef ENABLE_X
```

而 H0 从未启用该配置。

当前 commit 修改 X 内部实现，但没有改变 exposure/config requirement。

则该 config gap 属于 Existing Gap。

### N4-E：已有入口缺失

某 parser 在 S0 中已经存在，但 H0 一直没有 fuzz 它。

当前 commit 只是修改 parser 内部实现，没有改变 Harness 应如何到达它。

则不能把“该 parser 未覆盖”归因为当前 commit。

---

## 7. N4 的硬性筛选条件

一个 case 只有满足以下全部条件才可以成为 N4：

### N4-1

`S0 + H0` 中可以证明 Harness Gap 已经存在。

### N4-2

`S1 + H0` 中该 Gap 仍然存在。

### N4-3

当前 commit 没有新引入该 Gap。

### N4-4

当前 commit 没有明显加剧该 Gap。

### N4-5

commit 必须是真实且有意义的 production source change，不允许：

- docs-only；
- comment-only；
- formatting-only；
- trivial rename。

---

## 8. N4 Ground Truth 验证

每个 N4 case 必须在 Prediction 前完成审计。

至少比较：

```text
S0 + H0
S1 + H0
```

必要时允许参考：

```text
S1 + H1
```

但 `H1` 只能用于 Ground Truth，绝不能进入预测输入。

---

## 9. N4 Ground Truth 证据

每个 N4 至少需要一种客观证据。

### 9.1 Reachability Evidence

例如：

```text
foo_api:
S0+H0 = unreachable
S1+H0 = unreachable
```

说明 gap 在 commit 前已经存在。

### 9.2 Coverage Evidence

例如：

```text
relevant subsystem coverage:
S0+H0 = 0%
S1+H0 = 0%
```

且当前 commit 没有改变该 subsystem 的 exposure requirement。

### 9.3 Static Call-Path Evidence

例如：

```text
H0 -> A -> B
```

目标 `foo_api()` 在 S0 和 S1 中都不在 H0 的可达调用路径。

### 9.4 Configuration Evidence

例如：

```text
ENABLE_X = off
```

在 S0 和 S1 中保持不变。

### 9.5 State Evidence

例如目标逻辑需要：

```text
SPECIAL_MODE
```

而 H0 在 S0、S1 中都从未进入该状态。

---

## 10. Task 2：构造 Matched Commit-Induced Positive

为了避免 N4 太容易，必须为 N4 构造真正的 Commit-Induced Positive 对照。

尽量匹配以下维度：

- 同项目；
- 相近时间；
- 相近 changed LOC；
- 相近文件数；
- 相近功能类型；
- 相近 API / parser / state / config 场景。

目标是防止模型仅根据 commit size、文件名、是否新增函数等浅层特征做判断。

---

## 11. Matched Positive 硬性条件

### P-1

`S0 + H0` 中目标 Gap 不存在，或明显较弱。

### P-2

`S1 + H0` 中出现新的 Gap，或 Gap 明显加剧。

### P-3

该变化与当前 commit 存在明确因果关系。

### P-4

必须存在客观证据，例如：

- new function unreachable；
- new entry point not exposed；
- new state requirement unmet；
- new configuration requirement missing；
- changed-code coverage 显著降低；
- 新 API protocol 无法由旧 Harness 满足。

---

## 12. Ground Truth Freeze

必须先完成全部 N4 和 Positive 的 Ground Truth 审计，再进行任何 LLM Prediction。

输出：

```text
n4-validation/frozen-ground-truth/labels.csv
```

字段至少包括：

```text
case_id
project
label
case_type
gap_exists_s0
gap_exists_s1
commit_induced
maintenance_needed
evidence_type
evidence_summary
audit_status
```

其中：

```text
case_type =
N4_EXISTING_GAP
COMMIT_INDUCED_POSITIVE
```

冻结时必须生成：

```text
dataset_hash
ground_truth_hash
frozen_at
```

冻结后禁止 relabel。

如果预测完成后发现 Ground Truth 严重错误，只允许：

```text
INVALIDATE
```

不得把 Negative 改成 Positive 或反之继续计入主结果。

---

## 13. Blind Input

每个 case 的待测 LLM 只能看到：

- Existing Harness H0；
- `S0 -> S1` production source diff；
- 按统一规则选择的必要 S0/S1 context；
- 必要 caller/callee/API/type/config declaration。

严禁包含：

- N4 / Positive 标签；
- H1；
- Harness diff；
- Ground Truth；
- coverage 结果；
- reachability 结果；
- future developer action；
- 人工审计结论；
- “existing gap”等泄漏答案的描述。

---

## 14. 必须比较的两个方法

### B1 — Gap-Only

只判断：

> `S1 + H0` 中是否存在 Harness Gap？

如果：

```text
gap_exists = YES
```

则直接：

```text
maintenance_needed = YES
```

预期：N4 上可能产生大量 FP。

### B2 — Evolution-Aware

强制分两步。

#### Step A — Gap Detection

> `S1 + H0` 中是否存在 Harness Gap？

输出：

```text
gap_exists = YES / NO
```

#### Step B — Evolution Attribution

> 如果 Gap 存在，该 Gap 是否由当前 `S0 -> S1` commit 新引入或明显加剧？

输出：

```text
commit_induced = YES / NO / UNCERTAIN
```

最终：

```text
maintenance_needed = gap_exists AND commit_induced
```

---

## 15. Evolution-Aware 输出格式

统一输出 JSON：

```json
{
  "case_id": "N401",
  "gap_exists": true,
  "gap_type": "uncovered_existing_api",
  "commit_induced": false,
  "maintenance_needed": false,
  "confidence": 91,
  "affected_functions": [
    "foo_api"
  ],
  "reason": "The API is not exercised by H0, but the source diff does not introduce or aggravate this exposure gap.",
  "evidence": [
    "foo_api already exists in S0",
    "H0 does not exercise foo_api",
    "the commit does not alter the exposure path or harness requirement for foo_api"
  ]
}
```

---

## 16. Prediction Freeze

正式运行前冻结：

```text
model
model_version
prompt
reasoning_effort
temperature
context_selection_version
dataset_hash
input_hash
prompt_hash
```

保存：

```text
n4-validation/frozen-experiment-config.json
```

每个 case：

- 单次运行；
- 独立上下文；
- 0 retry；
- 不补 context；
- 不修改 Prompt；
- 不人工纠正输出。

---

## 17. 核心指标

### 17.1 N4 Existing-Gap FPR

定义：

```text
N4_FPR
=
N4 cases predicted maintenance YES
/
all valid N4 cases
```

这是本实验最核心指标。

### 17.2 Commit-Induced Positive Recall

```text
Positive Recall
=
correctly identified commit-induced positives
/
all valid commit-induced positives
```

### 17.3 Attribution Accuracy

在真正存在 Gap 的 case 中，统计：

```text
commit_induced
```

是否判断正确。

### 17.4 FP Reduction

比较 Gap-Only 与 Evolution-Aware：

```text
FP Reduction
=
(FP_gap_only - FP_evolution_aware)
/
FP_gap_only
```

---

## 18. 必须输出的主结果表

```text
| Method          | Positive Recall | N4 Existing-Gap FPR | Overall FPR |
|-----------------|----------------:|--------------------:|------------:|
| Gap-Only        |                 |                     |             |
| Evolution-Aware |                 |                     |             |
```

如果数据规模允许，再报告 95% confidence interval，但不要用小样本过度解释显著性。

---

## 19. 预期研究信号

理想模式：

```text
Gap-Only:
Positive Recall 高
N4 Existing-Gap FPR 高

Evolution-Aware:
Positive Recall 仅小幅下降
N4 Existing-Gap FPR 显著下降
```

示例：

```text
Gap-Only:
Recall = 90%
N4 FPR = 80%

Evolution-Aware:
Recall = 80%
N4 FPR = 10%
```

这种结果才能直接支撑：

> Evolution Attribution 的价值不是“多问一步”，而是能够过滤真实存在、但并非当前 commit 引入的 Historical / Existing Harness Gaps。

---

## 20. Error Analysis

必须人工分析：

- 所有 Evolution-Aware FP；
- 所有 Evolution-Aware FN；
- Gap-Only FP 中被 Evolution-Aware 正确修复的 case。

### 20.1 N4 False Positive 分类

#### FP-N4-1

模型发现 existing API gap，但错误认为当前 commit 与其相关。

#### FP-N4-2

模型看到同一文件被修改，就错误建立因果关系。

#### FP-N4-3

模型把 internal implementation change 错误解释为 exposure change。

#### FP-N4-4

模型把 existing configuration gap 错误归因于 current commit。

#### FP-N4-5

模型无法区分：

```text
目标函数被修改
```

与：

```text
目标函数的 Harness reachability requirement 被修改
```

### 20.2 Positive False Negative 分类

重点检查：

- new entry point 未识别；
- state/config requirement 隐式；
- 跨文件语义不足；
- API protocol change 不明显；
- context selection 不足。

---

## 21. Go / No-Go 标准

### STRONG GO

建议同时满足：

```text
Valid N4 >= 20
Valid Commit-Induced Positive >= 20
Evolution-Aware N4 FPR <= 10%
Positive Recall >= 75%
FP Reduction vs Gap-Only >= 60%
```

并且大部分 TP / TN 的 attribution reasoning 有具体代码证据支撑。

### MODERATE GO

建议满足：

```text
Evolution-Aware N4 FPR <= 20%
Positive Recall >= 60%
FP Reduction >= 40%
```

### NO-GO

出现以下任一情况：

```text
N4 FPR > 30%
Positive Recall < 50%
Gap-Only 与 Evolution-Aware 差异很小
Evolution Attribution 无法稳定判断
Ground Truth 冻结后再次大量 INVALID
```

---

## 22. 最终目录结构

```text
n4-validation/
├── N4_EXISTING_GAP_VALIDATION.md
├── README.md
├── data/
│   ├── n4_candidates.csv
│   ├── positive_candidates.csv
│   ├── matched_pairs.csv
│   └── excluded_cases.csv
├── ground-truth/
│   ├── n4_audit.csv
│   ├── positive_audit.csv
│   └── evidence/
├── frozen-ground-truth/
│   ├── labels.csv
│   └── manifest.json
├── frozen-inputs/
│   ├── C001.md
│   ├── C002.md
│   └── manifest.json
├── prompts/
│   ├── gap_only_prompt.md
│   └── evolution_aware_prompt.md
├── predictions/
│   ├── gap_only.jsonl
│   └── evolution_aware.jsonl
├── results/
│   ├── metrics.csv
│   ├── n4_metrics.csv
│   ├── attribution_metrics.csv
│   ├── confusion_matrix.csv
│   └── matched_pair_results.csv
└── reports/
    ├── dataset_construction.md
    ├── ground_truth_audit.md
    ├── blind_test_results.md
    ├── false_positive_analysis.md
    ├── false_negative_analysis.md
    └── go_no_go.md
```

---

## 23. 最终报告必须回答

`reports/blind_test_results.md` 必须明确回答：

1. 最终有效 N4 Existing-Gap case 有多少？
2. 最终有效 Commit-Induced Positive 有多少？
3. Gap-Only 在 N4 上误报多少？
4. Evolution-Aware 在 N4 上误报多少？
5. N4 FPR 从多少下降到多少？
6. FP Reduction 是多少？
7. Evolution-Aware Positive Recall 是多少？
8. Evolution Attribution 是否显著降低 Existing-Gap FP？
9. Recall 损失是否可接受？
10. 哪类 Existing Gap 最容易被错误归因？
11. 哪类 Commit-Induced Gap 最容易识别？
12. Ground Truth 是否在 Prediction 前冻结？
13. Prediction 后是否发生 relabel 或 INVALID？
14. 是否达到 STRONG GO / MODERATE GO / NO-GO？

---

## 24. 最重要的执行原则

1. **先审计 Ground Truth，再冻结，再预测。**
2. N4 必须是真实存在的 Gap，而不是没有 Gap 的普通 Negative。
3. N4 的核心是：`Gap exists = YES`，但 `Commit induced = NO`。
4. Positive 的核心是：`Gap exists = YES`，且 `Commit induced = YES`。
5. 不允许在预测后调整标签进入主结果。
6. H1、coverage、reachability 等证据只用于 Ground Truth，不得泄漏给预测模型。
7. Gap-Only 与 Evolution-Aware 必须在完全相同的 case 上比较。

---

## 25. 一句话实验目标

> 专门构造“Gap 真实存在，但不是当前 commit 引入”的 N4 Hard Negatives，并与真正的 Commit-Induced Positives 对照，验证 Evolution Attribution 是否能够完成正确的演化归因，而不是仅仅发现 Harness 中存在测试盲区。
