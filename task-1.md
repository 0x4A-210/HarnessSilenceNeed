需求 1：复现并明确 Degradation Ground Truth

这是最先做的，优先级最高。

给大模型的要求

阅读并复现 FSE 2026《An Empirical Study of Fuzz Harness Degradation》的实验设计，重点分析其 dataset、degradation definition、coverage metric、bug-finding capability metric 和 artifact。
不要重新设计 degradation 定义，第一阶段尽量复用论文原定义。
从其公开数据或 artifact 中选择 5–10 个 OSS-Fuzz C/C++ 项目，整理出能够明确对应到 Git commit 的 degradation events。

要求模型最终生成：

project
commit_id
commit_time
harness_id
previous_commit
degradation_label
degradation_metric_before
degradation_metric_after
evidence_source
你需要知道的结果

最重要的是三个数字：

项目数
commit 总数
positive degradation commits 数量

例如：

8 projects
12,430 commits
137 degradation events
怎么检验

随机抽 10–20 个 positive case：

commit 真实存在；
commit 时间正确；
Harness 对应正确；
degradation 确实发生在这个 commit 之后；
label 不是模型自己猜的，而来自论文数据或可重复计算。

禁止模型用自然语言自己判断“这个 commit 看起来像 degradation”。

Ground Truth 必须来自数据或计算。

Go / No-Go

如果最终只能得到：

< 30 个 positive cases

先暂停，不建议直接做 ML。

如果：

50+

可以继续。

最好：

100+
需求 2：构造 Commit-Level 数据集

第二步让模型把：

commit
+
当前 Harness

转成结构化数据。

给大模型的要求

对每个候选 commit，只使用该 commit 提交时或提交前能够获得的信息进行特征提取。严禁使用 commit 之后实际得到的 fuzzing coverage、bug discovery、degradation score 等信息作为预测特征。

对 Git diff、Harness、API 和代码结构提取 commit-time features。

第一版控制在 20–30 个特征。

建议至少包括：

Commit 特征
added_loc
deleted_loc
files_changed
functions_added
functions_deleted
functions_modified
branches_added
Harness 特征
harness_changed
harness_added_loc
harness_deleted_loc
number_of_fuzz_targets
API 特征
new_public_api
modified_public_api
deleted_public_api
Evolution / Exposure 特征
new_functions_reachable_from_harness
new_functions_unreachable_from_harness

changed_functions_reachable_from_harness
changed_functions_unreachable_from_harness

callgraph_distance_change
Constraint / Configuration 特征
new_if_conditions
new_error_returns
new_config_macros
new_initialization_calls
输出格式

最好统一成 CSV：

project,
commit_id,
timestamp,
label,
added_loc,
deleted_loc,
functions_added,
harness_changed,
new_public_api,
new_unreachable_functions,
...
怎么检验

随机抽：

20 commits

人工检查：

例如

模型输出：

functions_added = 4

你就：

git show <commit>

确认是不是 4。

模型输出：

harness_changed = false

确认 fuzz target 文件是否真的没变。

模型输出：

new_public_api = 2

必须能指出：

API name
file
line

不要接受只有数字没有 evidence 的输出。

所以要求模型同时生成：

feature_evidence.json

类似：

{
  "new_public_api": [
    "decode_webp",
    "decode_avif"
  ],
  "new_config_macros": [
    "ENABLE_AVIF"
  ]
}

这会非常方便后续核验。

需求 3：先做统计，不要立即训练模型

这一点很重要。

先验证：

positive degradation commits 和普通 commits 到底有没有可区分的特征。

给大模型的要求

对 positive 和 negative commits 做描述性统计和单变量分析，不训练复杂模型。

比较各类 commit-time feature 在两个群体中的分布。

例如最终得到：

Feature	Normal	Degradation
Harness unchanged	61%	89%
New public API	7%	32%
New unreachable function	11%	48%
New config condition	5%	29%

并计算适当统计检验：

Mann–Whitney U
Chi-square
Effect Size
Odds Ratio
你需要知道什么

不是只看：

p < 0.05

更重要的是：

有没有明显 effect size。

例如：

new_unreachable_function:

Normal:      12%
Degradation: 51%

Odds Ratio = 7.6

这种才有意义。

怎么检验

检查模型有没有犯典型错误：

错误 1

只告诉你：

p = 0.001

但是：

Normal = 10.1%
Positive = 10.5%

这虽然可能统计显著，但没工程价值。

错误 2

positive 与 negative 数量严重失衡，却只比较均值。

要求同时报告：

median
IQR
effect size
confidence interval
需求 4：做最简单的 Prediction Baseline

只有前三步成立，再训练模型。

给大模型的要求

将 Harness degradation prediction 定义为不平衡二分类问题。

仅使用 commit-time features。

第一轮只训练：

Logistic Regression
Random Forest
XGBoost

并加入简单 heuristic baseline。

Baseline 至少三个：

B0:
Always predict no degradation

B1:
Code churn only

B2:
Harness unchanged + source changed

然后你的完整 feature model：

B3:
Commit + Harness + API + Reachability features
最重要的要求：不要随机切分

明确告诉模型：

禁止随机拆 commit。

必须使用：

Temporal Split

例如：

Train:
早期 70%

Validation:
中间 15%

Test:
最后 15%

模拟：

用过去预测未来。

第二轮再做：

Cross-Project Split
Train:
Project A/B/C/D

Test:
Project E/F
评价指标

明确要求：

PR-AUC
ROC-AUC
Precision
Recall
F1

但是主要关注：

Recall@Top-K%

例如：

Top 5%
Top 10%
Top 20%

最高风险 commits 能覆盖多少 degradation events。

因为你的实际场景不是：

自动判定。

而是：

决定哪些 commit 值得维护者检查 Harness。

你真正想看到的结果

例如：

Top 5% high-risk commits
→ capture 48% degradation

Top 10%
→ capture 71%

Top 20%
→ capture 86%

这个结果比：

Accuracy = 97%

有意义得多。

需求 5：必须进行 Case Study

如果只得到一个：

XGBoost PR-AUC = 0.63

论文价值有限。

所以要求模型解释：

为什么这些 commit 会让 Harness stale？

给大模型的要求

选择：

10 True Positives
5 False Positives
5 False Negatives

每个 case 输出：

Commit summary

Software evolution

Harness state

Attack-surface change

Why model predicted high/low risk

Actual degradation mechanism

最好统一成结构：

Project:
Commit:

Code change:
新增 decode_avif API

Harness change:
无

Reachability:
新 API 不在现有 Harness call graph 中

Constraint change:
新增 ENABLE_AVIF 配置

Observed degradation:
AVIF functionality coverage = 0

Prediction:
High Risk

Root Cause:
Feature expansion without harness adaptation
怎么检验

每一个 case 都必须能够：

git show <commit>

验证。

尤其让模型给出：

file
function
API
config macro
call graph relation

不要接受这种描述：

“该 commit 引入了较复杂的软件演化，因此可能造成 Harness degradation。”

这属于废话。

需求 6：最后做 Go / No-Go 结论

最后让大模型不要“包装成果”，而是按预先定义好的标准判断。

你可以直接规定：

Go 条件
G1：数据足够
positive degradation events >= 50

最好：

>=100
G2：存在明显 prediction signal

至少有若干 feature：

positive / negative distribution
存在中等以上 effect size
G3：预测效果有工程意义

例如：

Top 10% risk commits
捕获 >= 50% degradation

如果：

>=70%

非常值得继续。

G4：Case study 有一致机制

至少能总结出 2–3 种重复出现的机制：

Feature Addition Without Harness Adaptation

New API / Entry Point

New State / Initialization Constraint

Configuration Expansion

New Validation Blocking Old Harness

如果全是互不相关的个例，说明问题难以泛化。

你可以直接给大模型的总任务描述

可以直接这么写：

我希望验证一个研究 Idea：Evolution-Aware Fuzz Harness Staleness Prediction。

研究问题不是检测 Harness 已经发生 degradation，而是：在一个 source commit 刚发生时，仅依赖该时刻可获得的信息，预测该 commit 是否会导致现有 Fuzz Harness 在后续出现 coverage/reachability degradation。

请基于 FSE 2026《An Empirical Study of Fuzz Harness Degradation》的数据和定义完成可行性实验。

整个实验分为：

复现 degradation ground truth；
构造 commit-level dataset；
提取 commit-time features；
分析 positive/negative commit 的特征差异；
使用 Logistic Regression、Random Forest、XGBoost 做预测；
使用 temporal split，禁止 random split；
使用 PR-AUC 和 Recall@Top-K% 为核心指标；
对 TP/FP/FN 做 case study；
最终按预定义 Go/No-Go 标准判断 Idea 是否值得继续。

关键约束：

禁止使用 commit 后产生的 coverage、degradation score 或 bug-finding result 作为 predictor input；
所有 Ground Truth 必须来自论文数据、artifact 或可重复计算，禁止 LLM 自行判断；
所有自动提取的 feature 必须保存 evidence，包括 file/function/API/line；
每一步必须能够由脚本重复执行；
不追求复杂模型，第一阶段目标只是判断 prediction signal 是否存在；
结果不理想时必须明确报告，不允许通过调整标签或数据过滤人为提高结果。
如果你打算让 Codex/Agent 直接做工程，我建议让它最终交付这些东西

目录可以直接规定：

harness-staleness-pilot/
│
├── README.md
│
├── docs/
│   ├── methodology.md
│   ├── dataset_definition.md
│   └── validation_protocol.md
│
├── data/
│   ├── raw/
│   ├── degradation_events.csv
│   ├── commits.csv
│   └── features.csv
│
├── scripts/
│   ├── collect_projects.py
│   ├── collect_commits.py
│   ├── extract_features.py
│   ├── build_callgraph.py
│   └── validate_labels.py
│
├── analysis/
│   ├── feature_statistics.py
│   ├── train_baseline.py
│   ├── temporal_evaluation.py
│   └── risk_budget_analysis.py
│
├── results/
│   ├── statistics.csv
│   ├── model_results.csv
│   ├── topk_results.csv
│   └── feature_importance.csv
│
└── cases/
    ├── true_positive/
    ├── false_positive/
    └── false_negative/

这样模型不是给你：

一堆 notebook + 一堆结论。

而是一个可重复的研究工程。

你个人最需要盯住的其实只有 5 件事

不需要检查模型每行代码。

你只重点核验：

① Label 到底是不是可靠的？
这是最重要的。

② 有没有数据泄漏？
特别检查是不是把 commit 后 coverage 偷偷作为 feature。

③ 特征是不是 commit-time 可获得？

④ Temporal test 上是否仍然有效？

⑤ 高风险 commit 是否能用真实代码变化解释？

只要这五点成立，Pilot 就有研究意义。

反过来，即使模型给你：

F1 = 0.95

但其中任何一项有问题，这个实验都没有价值。