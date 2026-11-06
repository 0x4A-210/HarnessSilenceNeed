# NEXT_STEP_TARGET_DISCOVERY_REACHABILITY.md

# Next Experiment — Automatic Target Discovery + Reachability Kill Test

## 1. 实验目标

上一阶段发现：

- Overall Coverage Delta 很弱；
- Changed-Code Coverage 能发现部分 gap，但 N4 Existing-Gap FPR 很高；
- Exact-target Function Reachability 在 complete-case 上达到：
  - Positive Recall = 100%
  - N4 FPR = 0%
- 但该 baseline 使用了“已经知道真正 maintenance target 是哪个函数”的信息，因此属于 target-conditioned / oracle-assisted baseline；
- Delta-Aware 不需要提前知道 exact target，但是否真的有必要使用 LLM，仍未被证明。

本阶段只回答一个关键问题：

> **如果不使用 Ground Truth target，只根据 `S0 -> S1` production diff 和旧 Harness `H0`，能否用确定性的 target discovery + reachability analysis 达到接近 Delta-Aware 的效果？**

这是当前 Idea 的关键 kill test。

## 2. 核心研究问题

### RQ-T1
仅根据 production diff，能否自动识别本 commit 中真正 fuzz-relevant 的目标函数 / API / entry point？

### RQ-T2
在不知道 Ground Truth target 的情况下，Diff-Derived Reachability 能否正确判断 Existing Gap 与 Commit-Induced Gap？

### RQ-T3
Diff-Derived Reachability 与 Exact-Target Reachability 的性能差距有多大？

### RQ-T4
Diff-Derived Reachability 与 Delta-Aware 的 Positive Recall、N4 FPR、Attribution Accuracy、Applicability、Latency 分别如何？

### RQ-T5
LLM 的真正价值是否主要来自 Commit Impact Scope / Target Identification，而不是 reachability 本身？

## 3. 本阶段比较的方法

### M0 — Exact-Target Reachability Oracle

输入：
- S0
- S1
- H0
- Ground Truth exact target

用途：
> 作为 reachability 的 oracle upper bound。

该方法不能作为 deployable baseline，禁止把它的 target 信息泄漏给其他方法。

### M1 — Diff-Derived Reachability

这是本阶段最重要的传统 baseline。

输入只能包含：
- S0
- S1 / source diff
- H0
- 固定规则允许的静态代码上下文

禁止输入：
- Ground Truth target
- H1
- harness diff
- label
- coverage oracle
- LLM prediction

该方法必须自动完成：

    Production Diff
        ↓
    Candidate Target Extraction
        ↓
    Target Ranking / Filtering
        ↓
    Reachability Before
        ↓
    Reachability After
        ↓
    Delta Attribution
        ↓
    Maintenance Decision

### M2 — Delta-Aware v2

直接复用上一阶段冻结版本。

禁止：
- 改 Prompt
- 改 Schema
- 改 context rule
- 重跑并挑更好的答案

若已有 prediction，直接复用。

## 4. 数据

Phase A 使用当前已有、已完成审计的 diagnostic cases。

优先复用 `t5-delta-aware-validation` 或 `t6-dynamic-baseline-validation` 中已经明确映射到 Ground Truth 的有效 cases。

目标规模：

    19 N4 Existing-Gap
    20 Commit-Induced Positive
    共 39 cases

注意：
> 这批数据已经参与方法开发，因此本阶段属于 diagnostic kill test，不是最终无偏主实验。

本阶段不要扩展到大规模新数据，先判断 baseline 是否足以替代 LLM。

## 5. Ground Truth Target 规范

为每个 case 记录：

    case_id
    project
    label
    exact_target_type
    exact_target_function
    exact_target_api
    exact_target_config
    exact_target_state
    expected_delta

其中：

    expected_delta =
        NEW
        AGGRAVATED
        UNCHANGED

该 Ground Truth 只允许用于：
- M0 Exact-Target Oracle
- 最终 evaluation

不得用于 M1 target discovery。

## 6. Task 1 — 构建 Automatic Target Discovery

M1 必须完全确定性，不调用 LLM。

### 6.1 从 Production Diff 提取候选

至少提取：

- T1 — Newly Added Functions
- T2 — Modified Public / Exported APIs
- T3 — Parser / Decoder / Encoder / Writer / Reader Candidates
- T4 — New / Modified Callers
- T5 — New Enum / Mode / State Handler
- T6 — Configuration / Macro Targets
- T7 — Modified Functions Already Reachable From H0

候选提取应使用固定、可解释规则。

## 7. Candidate Target 输出

每个 case 保存：

    target-discovery/<case_id>.json

格式示例：

```json
{
  "case_id": "T5001",
  "candidates": [
    {
      "target": "parse_avif",
      "target_type": "new_function",
      "source": "src/avif.c",
      "reason": [
        "newly_added_function",
        "parser_name_pattern"
      ],
      "rank_score": 4
    }
  ]
}
```

## 8. Target Ranking

不要训练 ML。

使用透明、固定规则排序。推荐初始评分：

    +3 newly added public/exported function
    +3 parser/decoder/encoder/writer/reader/protocol naming
    +2 changed public API
    +2 new function directly connected to changed caller
    +2 new enum/state/config handler
    +1 modified function in fuzz-relevant file
    -2 static/internal helper
    -2 test-only helper
    -2 obvious utility / logging / formatting function

最终保存 Top-1 / Top-3 / Top-5。

禁止根据 Ground Truth 修改评分。

## 9. Task 2 — Target Discovery Evaluation

先单独评价 target discovery，不看最终 maintenance 分类。

必须报告：

- Top-1 Target Recall
- Top-3 Target Recall
- Top-5 Target Recall
- Target Type Coverage

分别统计：
- function/API target
- state/config target
- non-function target

## 10. Function-only Applicability

必须区分：

    FUNCTION_TARGET
    NON_FUNCTION_TARGET

如果真实 maintenance target 是 configuration / state / macro / protocol semantic condition，且不能合理映射成具体 function target，则 M1 输出：

    NOT_APPLICABLE

禁止强制映射成假函数。

## 11. Task 3 — Reachability Before / After

对 M1 自动提取到的 candidate target，分别判断：

    Reachable(S0, H0, target)
    Reachable(S1, H0, target)

优先使用：
1. static call graph
2. symbol/caller-callee analysis
3. existing runtime reachability tooling

禁止使用 Ground Truth target 修正自动候选。

## 12. Static Reachability 优先

为了避免 build availability 影响，优先实现 source-level / callgraph-level reachability。

从 H0 入口：

    LLVMFuzzerTestOneInput
    or harness entry

向目标函数建立调用图。

输出：

    STATIC_REACHABLE
    STATIC_UNREACHABLE
    UNKNOWN

同时记录：
- path
- caller chain
- unresolved indirect calls

## 13. Dynamic Reachability 作为补充

如果项目可构建，则进一步检查：

    corpus-only
    optional short runtime

用于验证 static result。

但 M1 的核心结果不能依赖 Ground Truth-selected target。

## 14. Task 4 — Delta Attribution Rule

对每个自动候选 target 计算：

### NEW / AGGRAVATED GAP

若：
- target 在 S0 不存在或不相关，在 S1 出现且 H0 不可达；或
- reachable_before = YES，reachable_after = NO

则：

    delta = NEW / AGGRAVATED
    candidate_maintenance = YES

### EXISTING GAP

若：

    target exists in S0
    target unreachable in S0
    target unreachable in S1

且 commit 未改变 exposure requirement：

    delta = UNCHANGED
    candidate_maintenance = NO

### NO GAP

若：

    target reachable before
    target reachable after

则：

    delta = NONE
    candidate_maintenance = NO

## 15. 多候选聚合规则

分别测试：

### Top-1 Mode
只使用排名第一 candidate。

### Top-3 Mode
Top-3 中任意 candidate 判 NEW / AGGRAVATED，则 maintenance_needed = YES。

### Top-5 Mode
同理。

必须分别报告 Recall / FPR。

目的：
> 衡量 target discovery 与 false alarm 的 trade-off。

## 16. Existing Gap Attribution

N4 case 的正确目标行为：

    target exists in S0
    target gap exists in S0
    target gap still exists in S1
    delta = UNCHANGED
    maintenance_needed = NO

必须单独统计：

    N4 Target-Pattern Accuracy

不能只看最终 NO。

## 17. Task 5 — 比较 M0 / M1 / M2

核心结果表：

| Method | Target Info | Positive Recall | N4 FPR | Attribution Acc. | Applicability |
|---|---|---:|---:|---:|---:|
| Exact-Target Reachability | GT target | | | | |
| Diff-Derived Reachability Top-1 | automatic | | | | |
| Diff-Derived Reachability Top-3 | automatic | | | | |
| Diff-Derived Reachability Top-5 | automatic | | | | |
| Delta-Aware v2 | semantic | | | | |

## 18. Applicability 指标

必须报告：

    evaluable_cases / total_cases

原因：Reachability baseline 可能无法处理：
- config target
- state-only target
- indirect dispatch
- unresolved function pointer
- historical build unavailable

不要把 abstain 删除。

同时报告：

### Complete-case
只统计可评估 case。

### ITT
全部 case 中：

    abstain = miss / unresolved

至少报告 Positive ITT Recall。

## 19. Latency / Cost

M1 记录：

    diff_parse_time
    candidate_extraction_time
    callgraph_build_time
    reachability_time
    total_time
    peak_memory

M2 Delta-Aware 继续使用已有：

    input prep
    inference time
    tokens
    cost

比较 median 和 p90。

## 20. Kill Criteria

### KILL

如果 Diff-Derived Reachability 在不使用 GT target 的情况下满足：

    Positive ITT Recall >= Delta-Aware - 5 percentage points
    N4 FPR <= Delta-Aware + 5 percentage points
    Applicability >= 95%

并且：

    median latency <= Delta-Aware
    implementation complexity reasonable

则：

> LLM 作为主要方法的必要性基本被否定。

建议转向 deterministic static analysis / reachability method。

### MAJOR WEAKENING

如果 M1：
- Recall 接近 Delta-Aware
- FPR 接近 Delta-Aware

但：
- applicability 明显不足
- 或 state/config case 处理不了
- 或 indirect call / build 问题较多

则：

> 不宜继续把 Delta-Aware 定位为纯独立 detector，考虑 hybrid。

### CONTINUE

如果：
1. Top-1/3 automatic target discovery recall 明显不足；
2. Diff-Derived Reachability 的 N4 FPR 明显高于 Delta-Aware；
3. Reachability 对 state/config/protocol semantic target 大量 NOT_APPLICABLE；
4. 需要较复杂项目级构建 / instrumentation 才能接近 Delta-Aware；
5. Delta-Aware 能在不知道 exact target 的情况下保持明显更高 ITT Recall；

则：

> Delta-Aware 的语义 impact-scope identification 具有独立价值。

## 21. Hybrid 分支

如果结果是 MAJOR WEAKENING，而不是 CONTINUE / KILL，则额外评估：

    Diff
      ↓
    Delta-Aware Target Identification
      ↓
    Deterministic Reachability / Config Check
      ↓
    Final Maintenance Decision

Hybrid 不作为本阶段默认主方法，只有在 M1 和 M2 暴露明显互补缺陷后再实现。

## 22. Error Analysis

必须分析：

- E1 — Target Miss
- E2 — Target Overgeneration
- E3 — Reachability Error
- E4 — Existing Gap Attribution Error
- E5 — Non-Function Target
- E6 — Indirect Call

## 23. 输出目录

    t7-target-discovery-reachability/
    │
    ├── NEXT_STEP_TARGET_DISCOVERY_REACHABILITY.md
    ├── README.md
    │
    ├── dataset/
    │   ├── cases.csv
    │   └── gt_targets.csv
    │
    ├── target-discovery/
    │   ├── T5001.json
    │   └── ...
    │
    ├── scripts/
    │   ├── extract_diff_targets.py
    │   ├── rank_targets.py
    │   ├── build_callgraph.py
    │   ├── static_reachability.py
    │   ├── dynamic_reachability.py
    │   └── evaluate.py
    │
    ├── results/
    │   ├── target_recall.csv
    │   ├── exact_target_oracle.csv
    │   ├── diff_reachability_top1.csv
    │   ├── diff_reachability_top3.csv
    │   ├── diff_reachability_top5.csv
    │   ├── delta_aware.csv
    │   ├── applicability.csv
    │   ├── latency.csv
    │   └── comparison.csv
    │
    └── reports/
        ├── target_discovery_results.md
        ├── reachability_results.md
        ├── non_function_cases.md
        ├── error_analysis.md
        ├── reviewer_kill_test.md
        └── go_no_go.md

## 24. reviewer_kill_test.md 必须回答

1. Exact-target Reachability 的性能是多少？
2. 自动 Target Discovery 的 Top-1 / Top-3 / Top-5 Recall 分别是多少？
3. 自动化后 Reachability 性能下降多少？
4. N4 FPR 是否仍然接近 0？
5. 哪些 FP 来自错误 target discovery？
6. 哪些 FN 来自 target miss？
7. 哪些 case 无法用 function reachability 表达？
8. Diff-Derived Reachability 的 ITT Recall 是多少？
9. Applicability 是多少？
10. Median latency 与 Delta-Aware 相比如何？
11. 是否满足 KILL 条件？
12. 如果不满足，Delta-Aware 的独立价值究竟来自哪里？
13. 是否应该继续纯 Delta-Aware？
14. 是否应该改成 Hybrid：LLM target identification + deterministic reachability？
15. 下一阶段是否值得构造更大的独立数据集？

## 25. 本阶段禁止事项

1. M1 禁止使用 Ground Truth target。
2. M1 禁止调用 LLM。
3. 不修改 Delta-Aware v2。
4. 不因为 target recall 低而根据 GT 修改规则后再把同一结果当正式 test。
5. Development-style rule adjustment 必须明确记录版本。
6. Exact-target baseline 必须标记为 ORACLE。
7. NOT_APPLICABLE / UNKNOWN 不得删除。
8. 不隐藏 indirect-call / config / state case。
9. 不扩展大规模新数据，先完成 kill test。
10. 必须允许最终结论为 KILL。

## 26. 一句话目标

> 去掉“已知真正 target”这一不现实前提，测试一个完全不依赖 LLM、只根据 source diff 自动发现 fuzz-relevant target 并做 Before/After Reachability 的传统方法，判断它是否已经足以替代 Delta-Aware；如果不能，则定位 Delta-Aware 真正提供价值的环节是 commit impact scope / target identification。
