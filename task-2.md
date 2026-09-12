TEST.md

Evolution-Induced Fuzz Harness Maintenance Need — Feasibility Experiment

1. 实验目标

本阶段验证新的研究假设：

当一次 source commit 发生时，是否能够仅根据 commit 前后的生产代码变化、现有 Fuzz Harness 及必要上下文，识别本次软件演化是否新引入或加剧了 Harness 测试盲区，从而产生 Harness Maintenance Need（Harness 维护需求）。

本实验不再使用 future coverage degradation 作为直接预测目标。

核心判断是：

软件变了以后，原来的 Harness 还够不够？

2. 核心定义

2.1 Source Version

S0：commit 前的生产代码

S1：commit 后的生产代码

2.2 Fuzz Harness

H0：commit 前已有 Harness

H1：commit 后开发者真实更新后的 Harness（仅用于 Ground Truth 验证，不允许提供给预测模型）

2.3 Harness Gap

Harness Gap 指：当前 Harness 无法充分测试某一应该被 fuzz 的功能、入口、状态、配置或输入语义。

典型包括：

新 API / 新入口不可达

新 parser / decoder 未进入 fuzzing

新状态要求未满足

新 configuration 未启用

新输入约束导致大量 early return

API protocol 发生变化但 Harness 未适配

2.4 Evolution-Induced Gap

仅当 Harness Gap 是本次 commit 新引入，或本次 commit 明显加剧时，才认为与当前 commit 相关。

历史已经存在的 Harness Gap 不属于当前 commit 的 Maintenance Need。

2.5 Harness Maintenance Need

定义：

Maintenance Need
    =
Harness Gap
    AND
Commit-Induced / Commit-Aggravated

即：只有当本次 source evolution 使旧 Harness H0 对 S1 的适配性明显下降时，才判定需要维护 Harness。

3. 本阶段不再使用的 Ground Truth

上一阶段已经证明：

Coverage degradation event 与 Harness Maintenance Need 并非同质概念。

因此本阶段：

不再直接把历史 degradation commits 当 Positive Ground Truth

不再使用 future coverage drop 作为 prediction label

不再以“开发者后来修改了 Harness”直接作为 Positive

开发者真实 Harness 修改只能作为候选信号。

最终 Positive 必须通过 counterfactual validation 验证。

4. 实验总体设计

本阶段目标：

从真实 Git 历史中挖掘 Source + Harness Co-evolution commits

构造候选 Positive

通过 S1 + H0 与 S1 + H1 对比建立 Verified Positive

构造 Verified Negative

对全部 case 进行 Blind LLM Prediction

分两阶段判断：

是否存在 Harness Gap

是否由当前 commit 引入 / 加剧

评价 LLM 是否可以识别真正的 Maintenance Need

5. Pilot 数据规模

第一阶段可行性实验目标：

Positive Candidate：30–50

最终 Verified Positive：至少 20

Verified Negative：40

总测试集目标：约 60 cases

如果无法得到至少 15–20 个 Verified Positive，则优先判断数据条件不足，不继续扩大实验。

6. Task 1：挖掘 Source + Harness Co-evolution Commits

从已有项目优先开始：

c-ares

libplist

libspng

tidy-html5

brotli

leptonica

meshoptimizer

wuffs

jansson

h2o

搜索满足以下条件的 commit：

Production Source Changed
        +
Fuzz Harness Changed

Harness 文件匹配规则可包括：

fuzz/
fuzzing/
fuzzers/
*_fuzz.c
*_fuzz.cc
*_fuzz.cpp
*_fuzzer.c
*_fuzzer.cc
*_fuzzer.cpp
LLVMFuzzerTestOneInput

记录：

project

commit_id

parent_commit

timestamp

source_files_changed

harness_files_changed

commit_message

输出：

data/co_evolution_candidates.csv

第一轮目标：

>= 30–50 candidates

7. Task 2：过滤无关 Harness 修改

以下 Harness 修改不能直接作为 Maintenance Positive：

formatting

rename

comment

warning fix

build cleanup

test infrastructure refactor

performance-only optimization

unrelated fuzz target cleanup

需要保留：Harness 修改与本次 Source Evolution 在语义上存在明确关联。

例如：

Source：

+ parse_avif()

Harness：

+ add AVIF fuzz entry

则：

RELATED

输出分类：

RELATED
UNRELATED
UNCERTAIN

生成：

data/co_evolution_semantic_labels.csv

8. Task 3：构造 S0 / S1 / H0 / H1

对每个 RELATED candidate：

S0 = commit 前 Source
S1 = commit 后 Source

H0 = commit 前 Harness
H1 = commit 后 Harness

保存：

cases/<case_id>/
    metadata.json
    source_diff.patch
    harness_diff.patch
    H0/
    H1/

metadata.json 至少包含：

case_id

project

commit

parent

source_files

harness_files

candidate_change_type

9. Task 4：Counterfactual Ground Truth 验证

真实历史：

S1 + H1

构造反事实：

S1 + H0

目的：如果开发者没有同步更新 Harness，旧 H0 是否真的不足？

比较：

S1 + H0
    VS
S1 + H1

至少使用以下验证指标。

9.1 Build / Runtime Compatibility

记录：

compile_success

link_success

harness_start_success

runtime_success

若：

S1 + H0 = FAIL
S1 + H1 = PASS

则属于 Strong Maintenance Evidence。

9.2 Changed-Code Coverage

仅统计当前 commit 新增/修改代码。

计算：

ChangedCoverage(S1, H0)
ChangedCoverage(S1, H1)

DeltaChangedCoverage
    =
ChangedCoverage(S1,H1)
-
ChangedCoverage(S1,H0)

不要只使用 overall coverage。

9.3 New Function Reachability

识别 commit 新增函数集合 F_new。

分别统计：

Reachable(S1,H0)
Reachable(S1,H1)

9.4 New API / Entry-Point Exposure

如果本 commit 新增：

public API

parser

decoder

protocol handler

writer / reader API

判断：

H0 是否可达？
H1 是否可达？

9.5 State / Configuration Adequacy

检查本 commit 是否新增：

initialization requirement

state transition

build configuration

runtime configuration

input validation

判断 H0 是否因这些变化：

early return

feature disabled

initialization fail

shallow execution

而 H1 是否改善。

10. Verified Positive 定义

一个 candidate 只有满足以下条件之一，才可进入 Verified Positive：

VP1

S1 + H0 无法 build/run
S1 + H1 正常

VP2

H1 显著提高 changed-code coverage

VP3

H1 使本次 commit 新增的关键 function/API 从不可达变为可达

VP4

H1 修复了本次 commit 新增的 state/configuration/input requirement

VP5

存在明确可重复的动态或静态证据表明：

本次 commit
    ->
H0 adequacy 下降
    ->
H1 恢复

注意：

“开发者修改了 Harness”本身不是 Positive Ground Truth。

输出：

data/verified_positive_cases.csv

11. Task 5：构造 Verified Negative

选择至少 40 个真实 source commits。

要求：

有实际 source code change

不是 docs/comments/formatting-only

Harness 未修改或无必要修改

H0 对 changed functionality 仍然足够

优先选择：

internal refactoring

helper function addition

performance optimization

internal data structure change

error handling change

bounds check change

call graph internal change

但要求：不引入新的 Harness requirement。

尽量包含 Hard Negative：

看起来像可能影响 Harness

但实际上 H0 已经能够覆盖 / 到达

输出：

data/verified_negative_cases.csv

12. Task 6：Blind Prediction 输入

对每个 case，预测模型只能看到：

允许输入

S0 的必要上下文

S0 -> S1 的 Source Diff

Existing Harness H0

必要 caller / callee / API / type / macro context

严禁输入

H1

Harness Diff

developer 后续 Harness 修改

future coverage

degradation result

counterfactual result

Positive / Negative label

commit message 中明显泄露答案的内容

Ground Truth

13. LLM 两阶段判断

不要只问：

Should the harness be updated?

必须要求模型分两步回答。

Stage 1 — Harness Gap Identification

问题：

在 S1 + H0 中，是否存在值得关注的 Harness Gap？

输出：

gap_exists = YES / NO

同时说明：

gap type

affected function/API/state/configuration

concrete evidence

Stage 2 — Evolution Attribution

问题：

如果 gap 存在，它是否由本次 S0 -> S1 commit 新引入或明显加剧？

输出：

commit_induced = YES / NO / UNCERTAIN

必须对比：

S0 + H0
    VS
S1 + H0

Final Decision

仅当：

gap_exists = YES
AND
commit_induced = YES

时：

maintenance_needed = YES

否则：

maintenance_needed = NO

14. 统一 LLM 输出格式

{
  "case_id": "C001",
  "gap_exists": true,
  "gap_type": ["new_entry_point"],
  "commit_induced": true,
  "maintenance_needed": true,
  "confidence": 87,
  "affected_functions": ["parse_avif"],
  "reason": "The commit introduces a new parser that is not reachable from the existing harness.",
  "evidence": [
    "parse_avif is newly added in src/avif.c",
    "H0 does not invoke parse_avif or a caller that reaches it"
  ],
  "recommended_action": "Extend the current fuzz target or add an AVIF-specific harness."
}

15. Fixed Prompt 约束

所有 case 使用同一 Prompt。

禁止：

case-specific prompt

针对错误结果重新提示

多次运行选最佳答案

few-shot 使用测试集

提供 H1

提供 future coverage

每个 case 默认一次正式预测。

16. Baseline 设计

至少做两个 baseline。

B1 — Gap-Only LLM

只判断：

S1 + H0 是否存在 Harness Gap

不做 commit attribution。

目的：观察不区分 historical gap / commit-induced gap 时 FP 有多高。

B2 — Evolution-Aware LLM

使用：

Gap Detection
    +
Evolution Attribution

最终判断 Maintenance Need。

目的：验证 evolution attribution 是否能减少 FP。

17. Evaluation

构造：



Actual Positive

Actual Negative

Predicted YES

TP

FP

Predicted NO

FN

TN

计算：

Precision

Recall

F1

False Positive Rate

Accuracy（仅辅助）

重点：

Positive Recall

FP

Hard-Negative FP

Reason Correct

Evidence Grounded

18. 最重要的对比

必须比较：

Gap-Only LLM
    VS
Evolution-Aware LLM

重点看：

加入 Evolution Attribution 后，FP 是否明显下降，同时不显著损失 Positive Recall。

19. Case Study

至少分析：

5 TP

5 FP

所有 FN

每个 case 输出：

Source Evolution

本 commit 改了什么。

Existing Harness

H0 原来覆盖什么。

Gap

是否存在。

Attribution

是否由本 commit 引入。

Counterfactual Evidence

S1 + H0 与 S1 + H1 的差异。

LLM Prediction

模型判断。

Root Cause

为什么正确 / 错误。

20. Go / No-Go 标准

G1 — 数据可行性

至少：

Verified Positive >= 20

如果：

< 15

则数据条件偏弱，优先 NO-GO。

G2 — Positive 可识别

Evolution-Aware LLM：

Recall >= 70%

作为 pilot 的推荐门槛。

G3 — False Positive 可控

目标：

FP <= 10%

更理想：

FP <= 5%

G4 — Attribution 有实际作用

相比 Gap-Only baseline：

Evolution-Aware FP 明显下降

同时 Recall 不应大幅下降。

G5 — Reasoning 可解释

大多数 TP：

reason correct

evidence grounded

如果大量 decision 正确但理由错误，则不能认为方法成立。

21. Pilot 结果分类

STRONG GO

建议满足：

Verified Positive >= 20

Recall >= 75%

FP <= 5%

Attribution 明显降低 FP

TP reason/evidence 大部分正确

MODERATE GO

建议满足：

Verified Positive >= 15

Recall >= 60%

FP <= 10%

Attribution 有一定收益

NO-GO

出现任一：

Verified Positive < 15

Recall < 50%

FP > 15%

Attribution 无法改善 FP

Ground Truth 无法稳定构造

22. 最终交付目录

harness-maintenance-new-pilot/
│
├── TEST.md
├── README.md
│
├── data/
│   ├── co_evolution_candidates.csv
│   ├── co_evolution_semantic_labels.csv
│   ├── verified_positive_cases.csv
│   └── verified_negative_cases.csv
│
├── cases/
│   └── <case_id>/
│       ├── metadata.json
│       ├── source_diff.patch
│       ├── harness_diff.patch
│       ├── blind_input.md
│       └── ground_truth.md
│
├── prompts/
│   ├── gap_only_prompt.md
│   └── evolution_aware_prompt.md
│
├── scripts/
│   ├── mine_coevolution_commits.py
│   ├── prepare_cases.py
│   ├── build_counterfactual.py
│   ├── measure_changed_coverage.py
│   ├── measure_reachability.py
│   ├── run_gap_only.py
│   └── run_evolution_aware.py
│
├── results/
│   ├── gap_only_predictions.jsonl
│   ├── evolution_aware_predictions.jsonl
│   ├── coverage_results.csv
│   ├── reachability_results.csv
│   ├── evaluation.csv
│   └── confusion_matrix.csv
│
└── reports/
    ├── feasibility_results.md
    ├── case_studies.md
    ├── false_positive_analysis.md
    ├── false_negative_analysis.md
    └── go_no_go.md

23. feasibility_results.md 必须回答

最终报告必须明确回答：

找到了多少 Source + Harness Co-evolution candidates？

其中多少能够通过 counterfactual validation 成为 Verified Positive？

Verified Positive 的主要 maintenance mechanism 是什么？

Gap-Only LLM 的 TP / FP / FN / TN 是多少？

Evolution-Aware LLM 的 TP / FP / FN / TN 是多少？

Evolution Attribution 是否明显降低了 FP？

是否仍存在“existing gap 被误判为 current commit maintenance need”？

哪类 Maintenance Need 最容易识别？

哪类最难识别？

是否达到预注册 Go / No-Go 条件？

24. 本阶段最重要的研究边界

本实验研究的是：

本次 commit 是否新产生或加剧了 Harness inadequacy。

不是：

当前 Harness 是否完美

项目是否存在任何未覆盖 API

future overall coverage 是否下降

developer 是否曾经修改 Harness

核心一定是：

S0 + H0
    ->
S1 + H0

产生了新的 adequacy delta，并且：

S1 + H1

能够验证 Harness adaptation 的实际收益。