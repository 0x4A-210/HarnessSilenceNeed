# FINAL_CONFIRMATORY_EVALUATION.md
# Final Confirmatory Evaluation — Evolution-Induced Fuzz Harness Maintenance

## 1. 阶段目标

前序实验已经完成：
- 区分 Harness Degradation 与 Harness Maintenance Need；
- 定义 Silent Maintenance Need；
- 证明 Gap-Only 会产生大量 Existing-Gap 误报；
- 证明 Direct Evolution Attribution 不够稳定；
- 提出 Delta-Aware：
  - GapBefore = Gap(S0, H0)
  - GapAfter = Gap(S1, H0)
  - Delta = NEW / AGGRAVATED / UNCHANGED / REMOVED / NONE
- 动态 baseline 表明 Overall Coverage Delta 很弱；
- Changed-Code Coverage 能发现部分 gap，但 attribution 较差；
- Exact-target Reachability 很强，但依赖提前知道真实 target；
- Diff-Derived Reachability 表明真正瓶颈是 commit impact scope / fuzz-relevant target identification。

本阶段不再做小规模 feasibility test，而是：

> 在一个全新的、多项目、预测前完全冻结 Ground Truth 的独立数据集上，做最终确认性评测，验证 Delta-Aware 是否真正具备跨项目泛化能力，以及它相对传统方法的独立价值。

---

## 2. 核心研究问题

- RQ1：是否存在 Harness 仍能正常 build/run、但已经需要更新的 Silent Maintenance Need？
- RQ2：Build failure、Overall Coverage Delta、Changed-Code Coverage 是否足以判断 Harness 是否需要维护？
- RQ3：Gap-Only 是否会把历史已有 Gap 错归因给当前 commit？
- RQ4：不使用 Ground Truth target 的 Diff-Derived Reachability 是否足以替代 Delta-Aware？
- RQ5：Delta-Aware 是否能保持较高 Silent Recall，同时显著降低 N4 Existing-Gap FPR？
- RQ6：Delta-Aware 是否能更准确识别本次 commit 真正改变 fuzzing requirements 的 impact scope？
- RQ7：在 unseen projects 上是否仍然有效？
- RQ8：在 applicability、latency、execution cost 上与动态方法相比如何？

---

## 3. 方法冻结

在任何 Final Test prediction 前，冻结以下方法：

### M0 — Build-Only
规则：
```text
if S1 + H0 build/link/runtime FAIL:
    maintenance_needed = YES
else:
    maintenance_needed = NO
```

### M1 — Overall Coverage Delta
输入：
```text
S0 + H0
S1 + H0
```
使用预先冻结的 threshold。禁止在 Final Test label 解封后重新调阈值。

### M2 — Changed-Code Coverage
使用冻结规则。禁止在 Final Test 上调阈值。

### M3 — Diff-Derived Reachability
必须使用上一阶段冻结 deterministic rules：
```text
Source Diff
 -> Candidate Target Discovery
 -> Ranking
 -> Before/After Reachability
 -> Delta Attribution
 -> Maintenance Decision
```
禁止：
- 使用 Ground Truth target
- 使用 H1
- 调用 LLM
- 根据 Final Test 修改 ranking

至少报告 Top-1 / Top-3 / Top-5。

### M4 — Direct Evolution-Aware
复用冻结旧版 Prompt / Schema，作为消融对比。

### M5 — Delta-Aware v2
复用冻结版本。禁止：
- 改 Prompt
- 改 Schema
- 改 context rule
- 针对新项目 tuning
- 根据 case 手工补 context

### M6 — Hybrid（可选）
只有在正式 prediction 前已经实现并冻结，才允许进入主实验。
若尚未完成，不要在看完 Final Results 后再补。

---

## 4. Final Dataset 规模

目标：
```text
100–150 个全新 commit
```

推荐组成：
```text
30–40 Silent Positive
15–20 Explicit Positive
30–40 N4 Existing-Gap Negative
30–50 Other Negative
```

最低可接受：
```text
>=25 Silent Positive
>=25 N4
>=30 Other Negative
```

---

## 5. 项目要求

目标：
```text
6–10 个项目
```

要求：
- 至少 6 个项目产生有效 case；
- 任何单项目不得占总 case 的 25% 以上；
- 更理想 <=20%。

---

## 6. Unseen-Project Holdout

至少保留：
```text
2–3 个项目
```
作为：
```text
UNSEEN_PROJECT_HOLDOUT
```

这些项目必须从未参与：
- Prompt 调整
- taxonomy development
- ranking rule development
- Delta-Aware v2 开发
- deterministic baseline rule development

最终单独报告：
```text
Seen-Project Performance
Unseen-Project Performance
```

---

## 7. 新数据独立性

禁止使用：
- 原始 13 degradation cases
- 早期 60-case development set
- 77-case evaluation set
- N4 development set
- t5 39-case blind set
- t6 dynamic baseline set
- target-discovery diagnostic set
- 任何参与 prompt / rule development 的 commit

Final Dataset 必须全部是此前未使用的新 commit。

---

## 8. Candidate Mining

### 8.1 Source + Harness Co-evolution
用于挖 Positive candidate：
```text
production source changed
+
fuzz harness changed
```
注意：Harness change 只是 candidate signal，不等于 Positive。

### 8.2 Source-only Evolution
用于挖：
- N4 Existing Gap
- Other Negative
- latent Silent Positive

---

## 9. Ground Truth Taxonomy

### P1 — Explicit Positive
```text
S1 + H0 build/link/runtime FAIL
S1 + H1 PASS
```

### P2 — Silent Coverage/Exposure Positive
```text
S1 + H0 build PASS
S1 + H0 runtime PASS
```
但 changed/new functionality 测试不足，H1 明显改善。

### P3 — New Entry/API Positive
新增或改变 parser / decoder / writer / reader / public API / protocol handler，H0 不足、H1 改善。

### P4 — State / Configuration Positive
新增或改变 state / initialization / config / build flag / runtime flag / protocol setup，H0 未满足、H1 满足。

### P5 — Other Silent Positive
其他可证明：
```text
S0 + H0 -> S1 + H0
```
产生 NEW / AGGRAVATED inadequacy 的 case。

### N4 — Existing Gap Negative
必须满足：
```text
S0 + H0: target gap exists
S1 + H0: same target gap exists
current commit does NOT introduce
current commit does NOT aggravate
expected_delta = UNCHANGED
maintenance_needed = NO
```

### N1–N6 — Other Negative
建议包括：
- internal refactor
- new internal helper
- error handling change
- bounds check
- side subsystem
- state/config already satisfied
- API change still adequately covered

---

## 10. Ground Truth 必须预测前完成

每个 case 必须构造并审计：
```text
S0 + H0
S1 + H0
S1 + H1
```

必要时补充：
- build/runtime
- changed-code coverage
- function reachability
- entry-point exposure
- state/config evidence
- API protocol evidence

---

## 11. Impact Scope Ground Truth

本阶段新增正式标注：
```text
Impact Scope Ground Truth
```

不要只标唯一 exact function。

每个 case 至少记录：
```text
impact_scope_type
impact_scope_files
impact_scope_functions
impact_scope_api
impact_scope_state
impact_scope_config
equivalent_targets
```

例如：
```text
scope = AVIF parser subsystem
```
则 parse_avif / decode_avif / avif_dispatch 都可属于同一 semantic impact scope。

正式评测同时报告：
- Exact Target Recall
- Impact-Scope Recall

其中 Impact-Scope Recall 是更重要指标。

---

## 12. Ground Truth Freeze

完成全部审计后，生成：
```text
frozen-ground-truth/
    labels.csv
    impact_scope.csv
    evidence.csv
    audit_manifest.json
```

必须包含：
```text
case_id
project
split
label
positive_type
expected_gap_before
expected_gap_after
expected_delta
maintenance_needed
exact_target
impact_scope
evidence_type
audit_status
```

同时生成：
```text
dataset_hash
ground_truth_hash
frozen_at
```

冻结后禁止 relabel。

若发现严重错误：
```text
INVALIDATE
```

禁止 replacement 或预测后补样本。

---

## 13. Blind Input Freeze

每个 case 预测输入仅允许：
- H0
- S0 -> S1 production diff
- 固定规则选择的 S0/S1 context

禁止：
- H1
- Harness diff
- Ground Truth
- coverage result
- reachability GT
- future developer action
- issue/CVE outcome
- label hint

---

## 14. Context Selection Rule

冻结统一规则。

必选：
- complete production diff
- H0
- changed function bodies

固定规则补充最多：
- one-hop callers
- one-hop callees
- public API declarations
- relevant types
- relevant macro/config declarations

禁止根据 Ground Truth 特别补 context。

---

## 15. Experiment Freeze Manifest

正式 prediction 前生成：
```text
frozen-experiment-config.json
```

记录：
```text
model
model_version
reasoning_effort
temperature
prompts
schema
context_selection_version
deterministic_rule_version
coverage_threshold_version
dataset_hash
ground_truth_hash
input_hash
prompt_hash
frozen_at
```

---

## 16. Prediction Protocol

所有 LLM：
- one-shot
- independent context
- 0 retry
- 0 manual correction
- 0 context patch
- 0 prompt tuning

所有 deterministic baseline：
- 使用冻结规则
- 不查看 Ground Truth target
- 不查看 LLM 输出

---

## 17. 主要结果表

至少输出：

| Method | Explicit Recall | Silent Recall | N4 FPR | Overall FPR | Applicability | Impact-Scope Recall |
|---|---:|---:|---:|---:|---:|---:|
| Build-Only | | | | | | N/A |
| Overall Coverage Delta | | | | | | N/A |
| Changed-Code Coverage | | | | | | N/A |
| Diff-Derived Reachability | | | | | | |
| Direct Evolution-Aware | | | | | | |
| Delta-Aware | | | | | | |

---

## 18. Delta-Aware 专项指标

必须报告：
```text
GapBefore Accuracy
GapAfter Accuracy
Delta Attribution Accuracy
N4 Target-Pattern Accuracy
Impact-Scope Recall
Exact Target Recall
```

---

## 19. Diff-Derived Reachability 专项指标

必须报告：
```text
Top-1 Target Recall
Top-3 Target Recall
Top-5 Target Recall
Top-1 Impact-Scope Recall
Top-3 Impact-Scope Recall
Top-5 Impact-Scope Recall
Positive ITT Recall
N4 FPR
Applicability
UNKNOWN rate
NOT_APPLICABLE rate
```

---

## 20. Seen vs. Unseen Project

必须单独报告：

| Split | Method | Silent Recall | N4 FPR | Impact-Scope Recall |
|---|---|---:|---:|---:|
| Seen | Diff-Derived | | | |
| Seen | Delta-Aware | | | |
| Unseen | Diff-Derived | | | |
| Unseen | Delta-Aware | | | |

同时必须给：
```text
macro-average across projects
```
不能只报告 micro-average。

---

## 21. Statistical Analysis

至少做：
- McNemar exact test
- bootstrap 95% CI
- project-level sensitivity analysis

报告：
```text
Recall CI
FPR CI
method difference CI
```

---

## 22. Ablation

至少比较：

### A1 — Gap-Only
去掉 attribution。

### A2 — Direct Attribution
不做 explicit Before/After decomposition。

### A3 — Delta-Aware
完整方法。

目的：
> 验证 Delta decomposition 的必要性。

---

## 23. Reviewer Kill Test

Final Evaluation 必须回答：

1. 如果已经知道 exact target，传统 Reachability 是否足够？
2. 不知道 GT target 时，Diff-Derived Reachability 性能下降多少？
3. Delta-Aware 的优势是否主要来自 impact-scope identification？
4. state/config/protocol semantic case 上，function reachability applicability 如何？
5. Diff-Derived 若接近 Delta-Aware，LLM 是否还有必要？

---

## 24. Final Kill Criteria

如果全新 Final Dataset 上：

```text
Diff-Derived Reachability
Silent Recall >= Delta-Aware - 5pp
N4 FPR <= Delta-Aware + 5pp
Applicability >= 95%
```

并且：
```text
latency 显著更低
unseen-project performance 相近
```

则：

> LLM 作为主要技术贡献的必要性明显不足。

应考虑转向 deterministic method。

---

## 25. Final Success Criteria

如果 Delta-Aware 在全新 Final Dataset 上达到：

```text
Silent Recall >= 75%
N4 FPR <= 10%
Impact-Scope Recall >= 80%
```

且相对 Diff-Derived 满足至少一项：

```text
Recall 高 >= 10pp
或 N4 FPR 低 >= 5pp
或 Applicability 明显更高
```

并且 unseen-project 结果没有明显崩溃，则支持论文主张。

更理想：
```text
Silent Recall >= 80%
N4 FPR <= 5%
Impact-Scope Recall >= 85%
Unseen Silent Recall >= 70%
Unseen N4 FPR <= 10%
```

---

## 26. Case Study

至少选择：
- 3 个 Delta-Aware 正确而 Diff-Derived 错的 Positive
- 3 个 N4，Gap-Only / Diff-Derived 误报而 Delta-Aware 正确
- 2 个 state/config/protocol case
- 2 个 Delta-Aware FN
- 2 个 deterministic baseline 优于 Delta-Aware 的 case

禁止只挑对 Proposed Method 有利的案例。

---

## 27. Failure Taxonomy

至少分类：
- F1 Impact Scope Miss
- F2 Helper Confusion
- F3 Existing Gap Misattribution
- F4 State/Config Semantic Miss
- F5 Cross-file Context Insufficiency
- F6 Reachability Limitation
- F7 LLM Hallucination

---

## 28. 推荐最终目录

```text
t8-final-confirmatory-evaluation/
├── FINAL_CONFIRMATORY_EVALUATION.md
├── README.md
├── mining/
├── ground-truth/
├── frozen-ground-truth/
├── frozen-inputs/
├── prompts/
├── predictions/
├── results/
└── reports/
```

其中 reports 至少包括：
```text
dataset_construction.md
ground_truth_audit.md
main_results.md
unseen_project_results.md
ablation.md
reviewer_kill_test.md
failure_analysis.md
final_go_no_go.md
```

---

## 29. main_results.md 必须回答

1. Final Dataset 有多少 case？
2. 覆盖多少项目？
3. 单项目最大占比？
4. Silent / Explicit / N4 / Other Negative 各多少？
5. Ground Truth 是否预测前冻结？
6. prediction 后多少 INVALID？
7. Build-Only Silent Recall？
8. Overall Coverage Delta Silent Recall？
9. Changed-Code Coverage Recall/FPR？
10. Diff-Derived Top-1/3/5 表现？
11. Delta-Aware Silent Recall / N4 FPR？
12. Delta-Aware Impact-Scope Recall？
13. Exact Target Recall 与 Impact-Scope Recall 差异？
14. Direct Attribution 与 Delta-Aware 差异？
15. Delta-Aware 是否显著优于 Diff-Derived？
16. unseen projects 是否保持效果？
17. state/config/protocol case 哪种方法更好？
18. latency / applicability / failure 如何？
19. 是否满足 Final Success Criteria？
20. 当前工作是否具备论文主实验条件？

---

## 30. 本阶段禁止事项

1. 不修改 Delta-Aware v2。
2. 不使用旧 case 作为 Final Test。
3. 不在 Final Dataset 上 Prompt tuning。
4. 不在 label 解封后调整 deterministic ranking。
5. 不使用 GT target 帮助 Diff-Derived。
6. H1 只用于 Ground Truth。
7. 不删除失败 / abstain / UNKNOWN。
8. 不隐藏 INVALIDATE。
9. 不只报告 micro-average。
10. 不因结果不理想而补新 case。
11. 不使用 final test error 反向修改方法再重新声称无偏结果。
12. 若必须开发新方法，则重新建立下一批独立 test set。

---

## 31. 一句话目标

> 在完全独立、多项目、预测前冻结 Ground Truth 的 Final Dataset 上，验证 Delta-Aware 是否真正优于 Build/Coverage/Diff-Derived Reachability，并证明其核心价值来自对 software evolution 中 fuzz-relevant impact scope 的语义识别和 Before/After 演化归因，而不是单纯依赖 LLM 做最终二分类。
