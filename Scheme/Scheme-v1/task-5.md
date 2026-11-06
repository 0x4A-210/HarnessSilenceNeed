# NEXT_STEP_DELTA_AWARE.md
# Next Step — Delta-Aware Fuzz Harness Maintenance Attribution

## 1. 当前阶段结论

上一轮 N4 Existing-Gap 验证结果：

- Gap-Only:
  - Positive Recall = 20/20 = 100%
  - N4 FPR = 16/16 = 100%
- Evolution-Aware:
  - Positive Recall = 20/20 = 100%
  - N4 FPR = 7/16 = 43.75%
- FP reduction = 56.25%
- Recall loss = 0
- paired exact p-value = 0.003906

进一步分析发现：

> 16 个有效 N4 中，仅 2 个真正输出了目标路径：

    gap_exists = YES
    commit_induced = NO
    maintenance_needed = NO

因此当前方法虽然减少误报，但尚未证明模型能够稳定地区分 Existing Gap 与 Commit-Induced Gap。

当前核心难点不是“能不能发现 Gap”，而是：

> **能不能对 Gap 做时间上的演化归因。**

---

# 2. 本阶段目标

本阶段不再继续扩大旧 Evolution-Aware 方法的测试规模。

开发并验证一个新的：

> **Delta-Aware Evolution Attribution（基于前后差异的演化归因）**

核心思想：

不要直接问模型：

    “这个 Gap 是不是本 commit 引入的？”

而是强制模型分别判断：

    GapBefore = Gap(S0, H0)
    GapAfter  = Gap(S1, H0)

再比较：

    DeltaGap = GapBefore -> GapAfter

最终将演化关系分类为：

    NEW
    AGGRAVATED
    UNCHANGED
    REMOVED
    NONE

然后再决定是否存在 Harness Maintenance Need。

---

# 3. 新方法总体流程

    Commit: S0 -> S1
            +
         Harness H0
            |
            v
    Stage 1: Commit Impact Scope
            |
            v
    Stage 2: Gap Before
         S0 + H0
            |
            v
    Stage 3: Gap After
         S1 + H0
            |
            v
    Stage 4: Delta Attribution
            |
            v
    NEW / AGGRAVATED / UNCHANGED / REMOVED / NONE
            |
            v
    Final Maintenance Decision

---

# 4. Stage 1 — Commit Impact Scope Identification

## 4.1 目标

首先识别：

> 当前 commit 真正改变了哪些与 fuzzing 相关的功能范围。

禁止模型在整个项目中自由寻找任意 Harness Gap。

后续只允许围绕：

> 本 commit 直接新增、修改或语义影响的功能范围

进行 Gap 判断。

---

## 4.2 Impact Scope 类型

至少识别：

### IS1 — New Function / Entry Point

例如：

- parser
- decoder
- encoder
- writer
- reader
- public API
- protocol handler

### IS2 — API Protocol Change

例如：

- 参数变化
- 调用顺序变化
- 新 context
- 新 lifecycle

### IS3 — State Change

例如：

- initialization requirement
- new state
- new transition
- mode selection

### IS4 — Configuration Change

例如：

- compile-time macro
- runtime flag
- feature enablement

### IS5 — Input Semantic Change

例如：

- 新格式
- 新 header
- 新 validation
- 新 input constraint

### IS6 — Internal-Only Change

例如：

- refactor
- internal helper
- optimization
- implementation-only change

---

# 5. Stage 1 输出

统一输出：

```json
{
  "impact_scope": [
    {
      "type": "new_entry_point",
      "files": ["src/foo.c"],
      "functions": ["parse_avif"],
      "description": "The commit adds a new AVIF parser entry point."
    }
  ]
}
```

如果 commit 不涉及 fuzz-relevant interface/state/configuration change：

    impact_scope = INTERNAL_ONLY

---

# 6. Stage 2 — Gap Before

针对 Stage 1 确定的同一个 impact scope，检查：

    S0 + H0

是否已经存在 Harness inadequacy。

输出：

```json
{
  "gap_before": true,
  "gap_before_type": "uncovered_api",
  "evidence": ["..."]
}
```

注意：

> 必须只判断与当前 commit impact scope 对应的 Gap。

禁止使用与当前 commit 无关的其他历史 Harness gap。

---

# 7. Stage 3 — Gap After

针对完全相同的 impact scope，检查：

    S1 + H0

输出：

```json
{
  "gap_after": true,
  "gap_after_type": "uncovered_api",
  "evidence": ["..."]
}
```

---

# 8. Stage 4 — Delta Attribution

根据：

    gap_before
    gap_after

以及两阶段 evidence，

输出：

    NEW
    AGGRAVATED
    UNCHANGED
    REMOVED
    NONE

---

## 8.1 NEW

    S0 + H0:
        gap = NO

    S1 + H0:
        gap = YES

说明：

> 当前 commit 新引入 Harness Gap。

最终：

    maintenance_needed = YES

---

## 8.2 AGGRAVATED

    S0 + H0:
        gap 已存在

    S1 + H0:
        gap 明显加剧

例如：

- 原来部分可达，commit 后完全不可达
- 原来 state 基本可进入，commit 后新增 requirement 导致大量 early return

最终：

    maintenance_needed = YES

---

## 8.3 UNCHANGED

    S0 + H0:
        gap = YES

    S1 + H0:
        相同 Gap 仍然存在

但当前 commit 没有新引入，也没有明显加剧。

最终：

    maintenance_needed = NO

这是 N4 Existing Gap 的目标模式。

---

## 8.4 REMOVED

    S0 + H0:
        gap = YES

    S1 + H0:
        gap = NO / weaker

最终：

    maintenance_needed = NO

---

## 8.5 NONE

    S0 + H0:
        gap = NO

    S1 + H0:
        gap = NO

最终：

    maintenance_needed = NO

---

# 9. 最终 Decision Rule

固定为：

```text
if explicit_build_or_runtime_failure:
    maintenance_needed = YES

else if delta_gap in {NEW, AGGRAVATED}:
    maintenance_needed = YES

else:
    maintenance_needed = NO
```

形式化：

    MaintenanceNeed
        =
    ExplicitFailure
        OR
    (DeltaGap ∈ {NEW, AGGRAVATED})

---

# 10. 第一阶段：旧 N4 数据只作为 Development Set

上一轮有效数据：

    16 N4
    20 Commit-Induced Positive

共：

    36 cases

从现在开始正式标记为：

    DELTA_AWARE_DEVELOPMENT_SET

允许：

- error analysis
- prompt development
- output schema development
- context rule development
- taxonomy refinement

禁止：

> 再把这 36 个 case 作为最终无偏测试集。

---

# 11. Task 1：分析当前 16 个 N4

对每个 N4 输出：

    development-analysis/N4xx.md

必须回答：

1. 当前 Evolution-Aware 原预测是什么？
2. 它有没有识别真实 Gap？
3. 它有没有正确判断 commit attribution？
4. 如果错：
   - 错在 gap_before？
   - 错在 gap_after？
   - 错在 impact scope？
   - 错在 delta attribution？
5. 是否错误关联了与 commit 无关的 API / subsystem？
6. 如果使用显式 Before/After 判断，是否能够避免该错误？

最终形成：

    reports/n4_failure_taxonomy.md

---

# 12. Task 2：分析当前 20 个 Positive

对每个 Positive 输出：

    development-analysis/Pxx.md

重点检查：

1. Impact scope 是否清晰？
2. S0+H0 中目标 Gap 是否不存在？
3. S1+H0 中是否出现新 Gap？
4. 正确分类应该是：
   - NEW
   - AGGRAVATED
5. 哪些 case 需要：
   - caller/callee
   - config
   - state
   - type
   - API declaration

输出：

    reports/positive_attribution_analysis.md

---

# 13. Task 3：开发 Delta-Aware Prompt

基于 Development Set 开发新的 Prompt。

Prompt 必须显式强制以下顺序：

### Step 1

Identify the commit's fuzz-relevant impact scope.

### Step 2

For that same scope, determine whether a harness gap exists in S0 + H0.

### Step 3

For that same scope, determine whether a harness gap exists in S1 + H0.

### Step 4

Compare the two states.

### Step 5

Classify:

    NEW
    AGGRAVATED
    UNCHANGED
    REMOVED
    NONE

### Step 6

Return Maintenance Need.

---

# 14. 推荐 Delta-Aware 输出 Schema

```json
{
  "case_id": "C001",

  "impact_scope": [
    {
      "type": "new_entry_point",
      "functions": ["parse_avif"],
      "files": ["src/avif.c"],
      "description": "The commit adds an AVIF parser."
    }
  ],

  "gap_before": {
    "exists": false,
    "type": "none",
    "evidence": [
      "parse_avif does not exist in S0"
    ]
  },

  "gap_after": {
    "exists": true,
    "type": "uncovered_new_entry",
    "evidence": [
      "parse_avif exists in S1",
      "H0 does not invoke parse_avif or a caller that reaches it"
    ]
  },

  "delta_attribution": "NEW",
  "maintenance_needed": true,
  "confidence": 92,
  "reason": "The commit introduces a new parser that is not exposed by the existing harness."
}
```

---

# 15. N4 的目标输出

```json
{
  "case_id": "N401",

  "impact_scope": [
    {
      "type": "internal_change",
      "functions": ["foo_cache"],
      "description": "The commit modifies internal cache handling."
    }
  ],

  "gap_before": {
    "exists": true,
    "type": "existing_uncovered_api",
    "evidence": [
      "foo_api exists in S0 and is not reached by H0"
    ]
  },

  "gap_after": {
    "exists": true,
    "type": "existing_uncovered_api",
    "evidence": [
      "foo_api remains unreachable in S1",
      "the current commit does not modify its exposure requirements"
    ]
  },

  "delta_attribution": "UNCHANGED",
  "maintenance_needed": false,
  "confidence": 90,
  "reason": "The harness gap predates the current commit and is not aggravated by it."
}
```

---

# 16. Task 4：在 Development Set 上调试

允许在：

    16 N4 + 20 Positive

上进行 Prompt / schema / context-rule 调整。

目标不是报告最终性能，而是验证新方法能否正确分解 attribution。

重点指标：

## N4

    GapBefore Accuracy
    GapAfter Accuracy
    Delta Attribution Accuracy
    Target-Pattern Accuracy

## Positive

    NEW/AGGRAVATED Attribution Recall

---

# 17. Development 阶段通过标准

建议达到：

## N4

    GapBefore Accuracy >= 80%
    GapAfter Accuracy >= 80%
    Delta Attribution Accuracy >= 75%

## Positive

    NEW/AGGRAVATED Attribution Recall >= 75%

## Final Maintenance

    N4 FPR <= 15%
    Positive Recall >= 75%

如果 Development Set 上仍然：

    N4 FPR > 20%

则暂时不要构造新的 blind test。

---

# 18. 第二阶段：构造全新 Multi-Project Blind Test

只有 Development 阶段通过后执行。

---

# 19. 新数据必须完全独立

禁止使用：

- 原 60-case development set
- 原 77-case test set
- 当前 36-case N4 development set
- 任何参与 Prompt 调试的 commit

必须使用：

> 全新的 commit。

---

# 20. 项目要求

目标至少：

    3–5 个项目

更理想：

    5–8 个项目

任何单一项目不得占：

    > 40%

更理想：

    <= 30%

避免再次出现：

    Wuffs 占绝大多数

---

# 21. 新 Blind Test 数据规模

推荐：

    20–30 N4 Existing-Gap Negatives
    20–30 Commit-Induced Positives

最低：

    20 + 20 = 40 cases

推荐：

    25 + 25 = 50 cases

---

# 22. N4 Ground Truth

必须在 prediction 前验证：

    S0 + H0:
        target gap exists

    S1 + H0:
        same target gap exists

同时：

    commit does NOT introduce
    commit does NOT aggravate

因此：

    expected_delta = UNCHANGED

---

# 23. Positive Ground Truth

必须在 prediction 前验证：

    S0 + H0
        ->
    S1 + H0

目标 Gap：

    NEW

或：

    AGGRAVATED

必须有客观证据，例如：

- reachability
- entry exposure
- state/config
- changed-code coverage
- API protocol
- build/runtime

---

# 24. Ground Truth Freeze

正式 blind prediction 前生成：

    frozen-ground-truth/

包括：

    labels.csv
    evidence.csv
    audit_manifest.json

字段至少包括：

    case_id
    project
    label
    expected_gap_before
    expected_gap_after
    expected_delta
    maintenance_needed
    evidence_type
    audit_status

必须生成：

    dataset_hash
    ground_truth_hash
    frozen_at

冻结后：

    禁止 relabel

发现问题只能：

    INVALIDATE

---

# 25. Blind Input Freeze

每个 case 输入只允许：

- H0
- S0 -> S1 production diff
- 固定规则选择的 S0/S1 context

禁止：

- H1
- Harness diff
- Ground Truth
- coverage result
- reachability result
- artificial label hints

---

# 26. Context Selection 规则

统一冻结。

推荐：

### 必选

- complete production diff
- H0
- changed function body in S0 and S1

### 固定规则补充

最多：

- one-hop caller
- one-hop callee
- relevant API declaration
- relevant type
- relevant macro/config declaration

禁止：

> 根据 Ground Truth 给某个 case 特别补充上下文。

---

# 27. 正式 Baselines

新 Blind Test 至少比较：

## B1 — Gap-Only

只判断：

    S1 + H0 有无 Gap

## B2 — Direct Evolution-Aware

复用上一阶段旧方法：

    Gap Detection
    +
    Direct commit attribution

## B3 — Delta-Aware

新方法：

    Impact Scope
    +
    Gap Before
    +
    Gap After
    +
    Delta Attribution

---

# 28. 必须比较的核心表

最终至少输出：

| Method | Positive Recall | N4 FPR | Attribution Accuracy |
|---|---:|---:|---:|
| Gap-Only | | | |
| Direct Evolution-Aware | | | |
| Delta-Aware | | | |

---

# 29. Delta-Aware 额外指标

必须单独统计：

## GapBefore Accuracy

    predicted gap_before
        vs
    GT gap_before

## GapAfter Accuracy

    predicted gap_after
        vs
    GT gap_after

## Delta Attribution Accuracy

分类：

    NEW
    AGGRAVATED
    UNCHANGED
    REMOVED
    NONE

## N4 Target-Pattern Accuracy

N4 上真正达到：

    gap_before = YES
    gap_after = YES
    delta = UNCHANGED
    maintenance = NO

的比例。

这是本阶段最关键指标之一。

---

# 30. 成功标准

## STRONG GO

建议：

    Valid N4 >= 20
    Valid Positive >= 20

同时：

    Delta-Aware N4 FPR <= 10%
    Positive Recall >= 75%
    N4 Target-Pattern Accuracy >= 70%
    Delta Attribution Accuracy >= 75%

并且：

    Delta-Aware 明显优于 Direct Evolution-Aware

---

## MODERATE GO

建议：

    Delta-Aware N4 FPR <= 20%
    Positive Recall >= 60%
    N4 Target-Pattern Accuracy >= 60%

且：

    attribution 指标明显改善

---

## NO-GO

出现任一：

    N4 FPR > 30%
    Positive Recall < 50%
    Target-Pattern Accuracy < 50%
    Direct 与 Delta-Aware 几乎无差异
    Ground Truth 冻结后大量 INVALID

---

# 31. Error Analysis

对以下全部分析：

- Delta-Aware FP
- Delta-Aware FN
- Direct Evolution-Aware FP
- 被 Delta-Aware 修复的旧 FP

重点分类：

## E1 — Impact Scope Error

错误定位 commit 影响范围。

## E2 — Gap Before Error

没有识别历史已有 Gap。

## E3 — Gap After Error

错误理解 commit 后状态。

## E4 — Delta Error

Before / After 都判断对，但演化关系判断错。

## E5 — Cross-Subsystem Confusion

把 commit 无关的旁支 subsystem 当成目标。

## E6 — Context Insufficiency

必要跨文件 / state / config 信息缺失。

---

# 32. 最终目录结构

    t5-delta-aware-validation/
    │
    ├── NEXT_STEP_DELTA_AWARE.md
    ├── README.md
    │
    ├── development-set/
    │   ├── n4/
    │   ├── positives/
    │   └── analysis/
    │
    ├── reports/
    │   ├── n4_failure_taxonomy.md
    │   ├── positive_attribution_analysis.md
    │   └── development_summary.md
    │
    ├── prompts/
    │   ├── gap_only.md
    │   ├── direct_evolution_aware.md
    │   └── delta_aware.md
    │
    ├── new-data/
    │   ├── candidates.csv
    │   ├── audit.csv
    │   └── excluded.csv
    │
    ├── frozen-ground-truth/
    │   ├── labels.csv
    │   ├── evidence.csv
    │   └── manifest.json
    │
    ├── frozen-inputs/
    │   └── ...
    │
    ├── predictions/
    │   ├── gap_only.jsonl
    │   ├── direct_evolution_aware.jsonl
    │   └── delta_aware.jsonl
    │
    └── results/
        ├── metrics.csv
        ├── attribution_metrics.csv
        ├── n4_target_pattern.csv
        ├── comparison.csv
        ├── false_positive_analysis.md
        └── false_negative_analysis.md

---

# 33. 最终报告必须回答

1. 当前 16 个 N4 的错误主要发生在哪一阶段？
2. Direct Evolution-Aware 为什么会产生 43.75% N4 FPR？
3. Delta-Aware 是否提高 GapBefore 判断能力？
4. Delta-Aware 是否提高 UNCHANGED attribution 能力？
5. N4 Target-Pattern Accuracy 是多少？
6. Delta-Aware N4 FPR 是否低于 Direct Evolution-Aware？
7. Positive Recall 是否保持？
8. 是否减少 cross-subsystem / existing-gap 误归因？
9. 新 Blind Test 覆盖多少项目？
10. 单项目最大占比是多少？
11. Ground Truth 是否在 prediction 前冻结？
12. prediction 后是否出现 relabel？
13. 是否达到 STRONG GO / MODERATE GO / NO-GO？

---

# 34. 本阶段一句话目标

> 不再直接让 LLM 猜“这个 Gap 是否由当前 commit 引入”，而是强制其对同一 commit impact scope 分别判断 S0+H0 与 S1+H0，再通过显式 Before/After Delta 推导 NEW、AGGRAVATED 或 UNCHANGED，从而真正验证 Evolution Attribution。
