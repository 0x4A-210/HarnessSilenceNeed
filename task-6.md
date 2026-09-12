# NEXT_STEP_DYNAMIC_BASELINE.md
# Next Experiment — Delta-Aware vs. Dynamic Coverage-Based Detection

## 1. 实验目的

本阶段专门回答一个可能来自审稿人的核心质疑：

> 既然已经有 `S1` 和旧 Harness `H0`，为什么不直接在沙箱中运行 `S1 + H0`，测 coverage / reachability，就能判断 Harness 是否需要更新？为什么还需要 Delta-Aware LLM？

本实验的目标不是继续优化 Delta-Aware，而是做一次 **kill test**：

> **比较 Delta-Aware 与动态 Coverage / Reachability Baseline，判断 LLM 是否提供了动态执行之外的独立价值。**

如果简单动态方法能够以较低成本达到或超过 Delta-Aware，则当前 Idea 的方法价值明显下降。

如果动态方法需要更高执行成本、较长 fuzzing budget，或者仍无法可靠识别 Silent Maintenance Need / Existing Gap Attribution，而 Delta-Aware 可以在 commit-time 静态输入上取得更好的 Recall-FPR 权衡，则 Idea 得到进一步支撑。

---

## 2. 研究问题

### RQ-D1
仅运行 `S1 + H0` 的 overall coverage，能否识别 Harness Maintenance Need？

### RQ-D2
使用 `S0 + H0` 与 `S1 + H0` 的 coverage delta，能否识别 commit-induced Harness Maintenance Need？

### RQ-D3
Changed-Code Coverage 是否可以替代 Delta-Aware？

### RQ-D4
New / Changed Function Reachability 是否可以替代 Delta-Aware？

### RQ-D5
在相同 case 上，动态方法与 Delta-Aware 的 Recall、FPR、N4 FPR、Latency、CPU Cost 分别如何？

### RQ-D6
Delta-Aware 更适合作为动态方法的替代方案，还是更适合作为低成本 commit-time triage / trigger？

---

## 3. 核心对象

### Explicit Maintenance Need

旧 Harness 在新版本中：

    S1 + H0
        ->
    build / link / runtime FAIL

### Silent Maintenance Need

旧 Harness：

    build PASS
    runtime PASS

但对本次 commit 新引入或改变的 entry point、API、parser/decoder/writer、state、configuration、protocol 或 input semantics 测试不足。

### N4 Existing Gap

Harness Gap 确实存在，但：

    S0 + H0
    S1 + H0

中都已经存在，当前 commit 没有新引入，也没有明显加剧。

正确答案：

    Maintenance Need = NO

---

# Phase A — Diagnostic Kill Test

## 4. 数据

优先使用当前已有并完成 Ground Truth 审计的：

    t5-delta-aware-validation

有效 case：

    19 N4
    20 Commit-Induced Positive

共：

    39 cases

注意：

> 这批数据已经用于 Delta-Aware 方法评测，因此本阶段只能作为 diagnostic / sensitivity experiment，不能作为新的最终无偏主实验。

本阶段禁止：

- 修改 Delta-Aware v2
- 修改已有 LLM 输出
- 重新运行 LLM 获取更好答案

直接复用已有冻结的 Delta-Aware predictions，只新增动态 baseline。

---

## 5. Baselines

### B0 — Build-Only

输入：

    S1 + H0

规则：

    build/link/runtime FAIL
        -> maintenance_needed = YES

否则：

    NO

---

### B1 — S1 Overall Coverage

仅运行：

    S1 + H0

收集：

- line coverage
- branch coverage
- function coverage

测试绝对 coverage 是否足以判断 Maintenance Need。

禁止根据完整测试标签人工挑 threshold。

---

### B2 — Overall Coverage Delta

分别运行：

    S0 + H0
    S1 + H0

计算：

    DeltaLineCoverage
    DeltaBranchCoverage
    DeltaFunctionCoverage

例如：

    DeltaLineCoverage =
        Coverage(S1,H0) - Coverage(S0,H0)

目标：

> 测试“coverage 是否下降”能不能直接作为 Harness maintenance signal。

---

### B3 — Changed-Code Coverage

针对：

    S0 -> S1

提取：

- added lines
- modified functions
- new functions

在：

    S1 + H0

上测量：

    ChangedLineCoverage
    ChangedFunctionCoverage

如果可行，再测：

    ChangedBranchCoverage

这是本实验最重要的动态 baseline。

---

### B4 — Changed-Code Coverage with H1 Oracle

该 baseline 仅用于 Ground Truth / upper-bound 分析，不用于真实 commit-time prediction。

比较：

    S1 + H0
    S1 + H1

计算：

    DeltaChangedCoverage_H1 =
        ChangedCoverage(S1,H1)
        -
        ChangedCoverage(S1,H0)

用于回答：

> H1 的真实 Harness 更新是否确实改善了 changed functionality 的 exposure？

禁止把 H1 结果提供给 Delta-Aware。

---

### B5 — Function Reachability

针对 commit 新增或修改的函数集合：

    F_changed

分别统计：

    Reachable(S0,H0)
    Reachable(S1,H0)

以及：

    Reachable(S1,H1)   # 仅用于 oracle / GT 分析

重点判断：

- new function 是否从 H0 可达
- changed function 是否出现 reachability regression
- existing gap 是否在 commit 前已经存在

---

## 6. 动态执行 Budget

为了回答“跑一下不就行了吗”，必须测试多个预算。

推荐：

    Corpus Replay Only
    1 minute fuzzing
    5 minutes fuzzing
    15 minutes fuzzing
    30 minutes fuzzing

如果资源受限，最低执行：

    Corpus Replay
    1 min
    5 min
    15 min

每个 budget 独立记录结果。

---

## 7. 固定运行环境

必须尽量统一：

- compiler
- compiler version
- sanitizer
- instrumentation
- fuzzing engine
- corpus
- seed handling
- CPU allocation
- memory limit
- timeout
- environment variables

推荐：

    libFuzzer
    coverage instrumentation
    ASan/UBSan 仅用于 runtime sanity

coverage 测量必须使用统一 pipeline。

---

## 8. Corpus 规则

默认优先使用：

1. commit 时可获得的已有 corpus
2. OSS-Fuzz / upstream historical corpus
3. 如果无 corpus，则使用空 corpus + 固定 seed strategy

禁止：

> 使用 commit 之后开发者新增的 corpus 来帮助 `S1 + H0`。

所有 corpus 来源记录到：

    dynamic-baseline/corpus_manifest.csv

---

## 9. Coverage 数据

每个 case、每个 budget 记录：

    case_id
    budget
    s0_h0_line_cov
    s1_h0_line_cov
    s0_h0_branch_cov
    s1_h0_branch_cov
    s0_h0_function_cov
    s1_h0_function_cov

以及：

    changed_line_cov_s1_h0
    changed_function_cov_s1_h0
    new_function_reachability_s1_h0

如果有 H1 oracle：

    changed_line_cov_s1_h1
    changed_function_cov_s1_h1
    new_function_reachability_s1_h1

---

## 10. 动态 Baseline 决策规则

重要：

> 不能在看完整测试标签后再人工设置阈值。

### Strategy A — Development Threshold

从历史 Development Set 上选择 threshold。

例如：

    DeltaCoverage < -X
        -> YES

或：

    ChangedCodeCoverage < Y
        -> YES

然后冻结 X / Y，再用于当前 39-case diagnostic set。

### Strategy B — Threshold Sweep

如果没有独立 Development Set：

对所有 threshold 画：

- ROC
- Precision-Recall Curve

报告：

    Best possible diagnostic performance

但必须明确标记：

> oracle threshold / post-hoc upper-bound

不能作为正式 deployment result。

---

## 11. Changed-Code Coverage 特殊规则

不能简单规定：

    0% = Positive
    >0% = Negative

因为 coverage 不等于 adequacy。

至少分别记录：

### C1
changed-code coverage 是否很低

### C2
new entry / function 是否不可达

### C3
coverage 是否显著低于 H1 oracle

### C4
是否存在 attack-surface expansion 但 overall coverage 不降

不要提前把所有信号合成一个复杂模型。

---

## 12. 运行成本测量

每个 case / baseline 记录：

    checkout_time
    configure_time
    build_time
    instrumentation_time
    corpus_replay_time
    fuzz_time
    coverage_collection_time
    total_wall_clock_time
    cpu_seconds
    peak_memory

Delta-Aware 记录：

    input_preparation_time
    llm_inference_time
    total_wall_clock_time

如可获得，也记录：

    input_tokens
    output_tokens
    monetary_cost

---

## 13. 动态失败必须保留

统一标记：

    DYNAMIC_UNAVAILABLE
    BUILD_UNAVAILABLE
    COVERAGE_UNAVAILABLE
    NONDETERMINISTIC
    TIMEOUT

禁止静默删除。

输出：

    dynamic-baseline/execution_failures.csv

---

## 14. 重复性检查

Coverage 存在波动。

对于：

    5 min
    15 min
    30 min

至少对可执行 case：

    repeat = 3

如果资源不足：

    5 min 至少 repeat = 3

报告：

- mean
- median
- std
- min/max

Delta-Aware 继续复用原 one-shot 结果，不重新运行。

---

## 15. Phase A 核心指标

### Classification

- Positive Recall
- Silent Positive Recall
- N4 FPR
- Overall FPR
- Precision
- F1

### Dynamic Signal

- Overall Coverage Delta
- Changed-Code Coverage
- Function Reachability

### Cost

- Median wall-clock time
- CPU time
- build cost
- fuzzing time
- failure rate

---

## 16. 核心结果表

至少输出：

| Method | Silent Recall | N4 FPR | Overall FPR | Median Time | Dynamic Execution |
|---|---:|---:|---:|---:|---|
| Build-Only | | | | | Yes |
| Overall Coverage Delta | | | | | Yes |
| Changed-Code Coverage | | | | | Yes |
| Function Reachability | | | | | Yes |
| Delta-Aware | | | | | No |

---

## 17. Budget 曲线

| Budget | Silent Recall | N4 FPR | Median Time |
|---|---:|---:|---:|
| Corpus-only | | | |
| 1 min | | | |
| 5 min | | | |
| 15 min | | | |
| 30 min | | | |

目的：

> 测试动态方法需要多长时间才能接近 Delta-Aware。

---

## 18. 必须重点分析的 Case

### Case Type A — Coverage 正常但存在 Silent Need

    overall coverage 不下降
    changed functionality 未充分测试
    Delta-Aware = YES

这些 case 是对“跑 coverage 就够了”的直接反例。

### Case Type B — Coverage 降低但无需 Harness Update

    overall coverage decline
    但属于 refactor / code-size change / unrelated fluctuation

正确：

    Maintenance Need = NO

这些 case 用于说明：

> coverage degradation != maintenance need

### Case Type C — Existing Gap

    S0+H0 already has gap
    S1+H0 same gap

如果动态 coverage baseline 报 YES，而 Delta-Aware 报 NO：

> 说明 attribution 是关键。

---

## 19. Phase A Kill-Test 判定

本阶段必须允许 Idea 被否定。

### KILL / MAJOR WEAKENING

如果简单动态 baseline 在低预算，例如：

    <= 5 min

达到：

    Silent Recall >= Delta-Aware - 5%
    N4 FPR <= Delta-Aware + 5%

并且：

    动态执行成功率高
    总成本可接受

则：

> 当前 Delta-Aware 作为独立方法的必要性明显下降。

此时考虑：

- 改为 dynamic-first
- 或放弃当前方法论文定位

### CONTINUE

如果出现以下任一：

1. 动态 coverage Recall 明显低于 Delta-Aware
2. 动态 N4 FPR 明显更高
3. 需要长 fuzzing budget 才接近 Delta-Aware
4. 历史版本 build / instrumentation 成本或失败率明显较高
5. Delta-Aware 能识别 coverage 不敏感的 state/config/API protocol mismatch

则继续。

---

# Phase B — New Independent Confirmatory Set

只有 Phase A 通过 CONTINUE 后执行。

## 20. 数据规模

目标：

    6–10 projects
    100–150 new commits

推荐：

    30+ Silent Positive
    20+ Explicit Positive
    30–40 N4 Existing Gap
    30–50 Other Negative

所有 commit 必须未参与现有 Prompt / 方法开发。

---

## 21. Phase B Ground Truth

必须在 prediction 前完成：

    S0 + H0
    S1 + H0
    S1 + H1

完整审计至少包括：

- Build / Runtime
- Changed-Code Coverage
- Reachability
- State / Config evidence
- Entry-point evidence

然后：

    Freeze GT
    Freeze Input
    Freeze Prompt
    Freeze Dynamic Thresholds

再做 blind evaluation。

---

## 22. Phase B 正式比较方法

至少：

    Build-Only
    Overall Coverage Delta
    Changed-Code Coverage
    Function Reachability
    Direct Evolution-Aware
    Delta-Aware

如果资源允许：

    Combined Dynamic Baseline

禁止为了追求最优结果无限组合 feature。

---

## 23. 推荐最终定位

### Position A — Standalone Commit-Time Detector

如果 Delta-Aware：

- Recall 更高
- FPR 更低
- 无需动态执行
- 延迟明显更低

则定位：

> low-cost commit-time preventive detector

### Position B — Dynamic Validation Trigger

如果动态方法最终性能较强，但代价高：

    Every Commit
        |
        v
    Delta-Aware
        |
    +---+---+
    |       |
   LOW     HIGH
            |
            v
      Dynamic Validation

则定位：

> Delta-Aware 是 expensive dynamic harness validation 的低成本触发器。

---

## 24. 与 Harness Degradation 工作的差异验证

最终报告必须专门回答：

1. 原 degradation-style overall coverage monitoring 能识别多少 Silent Maintenance Need？
2. Changed-Code Coverage 是否足够？
3. 哪些 Maintenance Need 在 coverage 没明显下降时仍能被 Delta-Aware 识别？
4. 哪些 coverage degradation 并不对应 current commit maintenance need？
5. 动态 baseline 需要多少运行时间才能达到相似性能？

---

## 25. 输出目录

    t6-dynamic-baseline-validation/
    │
    ├── NEXT_STEP_DYNAMIC_BASELINE.md
    ├── README.md
    │
    ├── dataset/
    │   ├── cases.csv
    │   └── corpus_manifest.csv
    │
    ├── scripts/
    │   ├── build_versions.py
    │   ├── run_corpus_replay.py
    │   ├── run_fuzz_budget.py
    │   ├── collect_coverage.py
    │   ├── extract_changed_code.py
    │   ├── measure_changed_coverage.py
    │   ├── measure_reachability.py
    │   └── evaluate_dynamic_baselines.py
    │
    ├── raw/
    │   ├── coverage/
    │   ├── reachability/
    │   ├── timings/
    │   └── logs/
    │
    ├── results/
    │   ├── build_only.csv
    │   ├── overall_coverage.csv
    │   ├── coverage_delta.csv
    │   ├── changed_code_coverage.csv
    │   ├── reachability.csv
    │   ├── budget_comparison.csv
    │   ├── runtime_cost.csv
    │   ├── classification_metrics.csv
    │   └── execution_failures.csv
    │
    └── reports/
        ├── dynamic_baseline_results.md
        ├── cost_analysis.md
        ├── coverage_failure_cases.md
        ├── reviewer_kill_test.md
        └── go_no_go.md

---

## 26. reviewer_kill_test.md 必须回答

1. 仅 `S1+H0` overall coverage 是否足够判断 Harness 要不要更新？
2. `S0+H0 -> S1+H0` overall coverage delta 是否足够？
3. Changed-Code Coverage 是否足够？
4. Function Reachability 是否足够？
5. 哪个动态 baseline 性能最好？
6. 最佳动态 baseline 在 1/5/15/30 min 下表现如何？
7. Delta-Aware 与最佳动态 baseline 的 Silent Recall 差多少？
8. N4 FPR 差多少？
9. Median latency 差多少？
10. CPU cost 差多少？
11. 动态方法有多少 case 无法可靠执行？
12. 是否存在“coverage 看起来正常但确有 Maintenance Need”的 case？
13. 是否存在“coverage 下降但其实无需 Harness maintenance”的 case？
14. Delta-Aware 应定位为 standalone detector 还是 dynamic-validation trigger？
15. 该实验是否支持继续当前 Idea？

---

## 27. 禁止事项

1. 不修改 Delta-Aware v2。
2. 不重新运行已有 LLM case 以选择更好答案。
3. 不根据当前 39 case GT 人工挑动态 threshold 后当成正式结果。
4. H1 coverage 只能做 oracle / GT analysis。
5. 不把 overall coverage 当成 adequacy 的唯一定义。
6. 不删除动态执行失败 case。
7. 不隐藏 build/instrumentation cost。
8. 不因为动态 baseline 表现太好而修改实验目标。
9. 必须允许实验给出 KILL / MAJOR WEAKENING。
10. Phase A 只作为 diagnostic kill test；正式主结论必须由 Phase B 独立数据确认。

---

## 28. 一句话目标

> 正面验证“直接在沙箱中运行旧 Harness 并观察 coverage / reachability 是否已经足以判断 Harness Maintenance Need”，从准确性、Existing-Gap Attribution 和执行成本三个维度比较动态方法与 Delta-Aware，决定 LLM 的必要性以及最终论文定位。
