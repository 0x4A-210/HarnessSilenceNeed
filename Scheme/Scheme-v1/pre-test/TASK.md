TASK.md

Fuzz Harness Maintenance Need — Feasibility Pilot

1. 研究目标

本阶段进行一个小规模可行性实验，验证以下研究假设：

在一次 source commit 发生时，仅根据当时能够获得的 Source Diff、Existing Fuzz Harness 和必要代码上下文，LLM 是否能够提前判断该 commit 是否产生 Fuzz Harness Maintenance Need。

换句话说：

这次代码演化是否会使现有 Harness 不再充分适配新的软件状态，从而需要同步修改 Harness？

本阶段只验证 LLM 是否具备这种初步判断能力，不训练机器学习模型，不进行大规模动态实验。

2. 已有数据

上一阶段已经完成：

项目数：10

Commit 总数：16,155

Confirmed degradation commits：13

项目包括：

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

上一阶段结论：

degradation positive 数量过少，不适合直接进行 supervised ML prediction。

3. 本阶段实验规模

构造一个共 105 个 case 的 Blind Evaluation Dataset：

Positive

从现有 13 个 confirmed degradation cases 中筛选：

5 个 Positive

必须是 source evolution 与 Harness degradation 之间关系明确的 case

尽量覆盖不同类型的 Harness Maintenance Need

剩余 8 个 confirmed degradation cases：

本阶段不使用

保留为后续独立 hold-out set

Negative

从 16,155 个 commits 中筛选：

100 个 Negative

必须是真实 source-code change

不允许使用 README-only、comment-only、formatting-only、tests-only 等明显简单样本

应包含一定比例的 hard negatives

最终：

Positive = 5

Negative = 100

Total = 105

4. 实验要回答的问题

Q1

5 个真实 Positive 中，LLM 能提前识别出几个？

Q2

100 个 Negative 中，LLM 会误报多少个需要修改 Harness？

Q3

LLM 给出的判断理由是否真正基于 Source Diff 和 Existing Harness 中的代码证据？

Q4

LLM 是否存在明显的“只要代码变化就建议更新 Harness”的过度报警倾向？

Q5

这个 Idea 是否值得进入下一阶段的动态验证？

5. Positive Case 筛选

5.1 Positive 的基本要求

5 个 Positive 必须来自已有 13 个 confirmed degradation commits。

在筛选前，逐个检查其 degradation 是否可以合理归因于 source evolution 导致的 Harness 不适配。

优先选择以下类型：

P1. New Entry Point / New Feature

例如：

新增 parser

新增 decoder

新增 public API

新增 protocol handler

新增 externally reachable functionality

但 Existing Harness 无法有效测试。

P2. API Protocol Change

例如：

Before:

parse(data)

After:

ctx = create()
configure(ctx)
parse(ctx, data)

Existing Harness 未适配新的调用协议。

P3. State / Initialization Requirement

例如新增：

if (!ctx->initialized)
    return ERROR

Existing Harness 缺少必要初始化，导致无法进入目标逻辑。

P4. Configuration Change

例如：

#ifdef ENABLE_X

或者新功能需要新的 build/runtime configuration，而 Existing Harness 无法测试。

P5. Input Constraint Change

例如：

if (!valid_header(data))
    return ERROR

导致 Existing Harness / 旧输入大部分停留在浅层路径。

5.2 Positive 剔除条件

以下情况不能作为本实验 Positive：

OSS-Fuzz infrastructure failure

coverage collection error

historical data missing

unrelated build environment failure

target temporarily disabled

external dependency failure

degradation 与 source evolution 无明显关系

5.3 Positive 选择原则

优先选择：

证据最清楚的 5 个

机制尽量不同

能够明确指出涉及的函数/API/config/state change

不要随机选 5 个。

输出：

data/selected_positive_cases.csv

字段至少包括：

case_id
project
commit_id
degradation_type
maintenance_need_type
affected_function
affected_file
reason_for_selection
evidence

6. Negative Case 筛选

6.1 数量

从 16,155 commits 中筛选：

100 Negative

6.2 基本要求

Negative 必须：

修改真实 source code

不只是文档、注释、格式化

不只是测试文件

不存在已知 degradation

Existing Harness 没有明显维护需求

6.3 Negative 类型

建议分成三类：

Easy Negative：20 个

明显不会影响 Harness requirements 的 source change。

例如：

小型内部实现调整

非入口函数的简单 bug fix

局部性能优化

Matched Negative：60 个

尽量与 Positive 在以下维度匹配：

project

时间范围

changed LOC

files changed

source complexity

但实际上不需要修改 Harness。

Hard Negative：20 个

表面看起来可能影响 Harness，但实际上 Existing Harness 仍然充分。

例如：

新增 internal helper function

parser 内部重构

call graph 内部变化

bounds check 增加

error handling change

internal data structure change

新增函数但已被 Existing Harness 的原调用路径覆盖

Hard Negative 是本实验的重要部分。

6.4 项目分布

尽量保证 10 个项目都有 Negative。

优先目标：

每个项目约 10 个 Negative

如果个别项目不满足，则允许调整，但避免样本集中在少数项目。

输出：

data/selected_negative_cases.csv

7. Blind Input 构造

每个 case 只允许向待测 LLM 提供 commit 当时可获得的信息。

7.1 可以提供

Existing Harness H0

commit 发生前的 fuzz harness。

Source Diff

S0 -> S1 的 source-code diff。

Necessary Context

仅在判断确实需要时提供：

changed function

caller/callee

public API declaration

relevant type definitions

configuration macro

nearby source code

7.2 严禁提供

不得让待测 LLM 看到：

Positive / Negative label

degradation result

post-commit coverage

Fuzz Introspector result

future commits

updated Harness H1

Harness diff

developer 后续维护行为

CVE / OSS-Fuzz issue 结论

明显泄露答案的 commit message

如果 commit message 中出现：

update fuzz target
add fuzz harness
fix fuzzer
fuzz coverage

等明显提示，应删除 commit message 或不提供。

8. Case 标准格式

每个 case 整理为独立 Markdown 文件：

cases/C001.md
cases/C002.md
...

模板：

Case ID

C001

Existing Fuzz Harness

...

Source Change

...

Relevant Code Context

...

Question

Based only on the source-code evolution and the existing fuzz harness:

Does this commit introduce a fuzz-harness maintenance need?

A maintenance need exists when the source-code change introduces or modifies functionality, entry points, API usage requirements, state/configuration requirements, or input constraints such that the existing harness is no longer adequate for testing the changed functionality.

Return:

YES or NO

Confidence: 0–100

Main reason

Affected function/API

Concrete code evidence

Recommended harness action, if any

9. 固定 Prompt

所有 105 个 case 使用同一个 Prompt。

禁止：

针对 Positive 单独改 Prompt

针对某个错误 case 重写 Prompt

根据前几个结果不断调 Prompt

建议系统 Prompt：

You are reviewing whether a software commit requires maintenance
of an existing fuzz harness.

You must reason only from:
- the existing fuzz harness,
- the source-code changes,
- the provided code context.

Do not assume future coverage results, developer changes,
or fuzzing outcomes.

A harness maintenance need may arise from:
- new entry points or features,
- API protocol changes,
- new initialization or state requirements,
- configuration changes,
- new input constraints,
- attack-surface expansion.

Do not recommend updating the harness merely because source code changed.

Return a structured decision with concrete code evidence.

保存：

prompts/fixed_prompt.md

10. Blind Prediction

10.1 执行要求

将 105 个 case：

随机打乱

使用匿名 Case ID

不区分 Positive / Negative

每个 case 只进行一次主实验

不允许：

同一 case 连续重复调用直到得到期望结果

人工挑选“最好的一次回答”

10.2 输出格式

统一保存为 JSON：

{
  "case_id": "C001",
  "maintenance_needed": true,
  "confidence": 86,
  "change_types": [
    "new_entry_point"
  ],
  "affected_functions": [
    "parse_avif"
  ],
  "reason": "The source change introduces a new parser that is not exercised by the existing harness.",
  "evidence": [
    "parse_avif is introduced in src/avif.c",
    "the existing harness does not invoke parse_avif or a caller that reaches it"
  ],
  "recommended_action": "Extend the existing fuzz target or add a dedicated AVIF target."
}

保存：

results/llm_predictions.jsonl

11. Evaluation

构造 Confusion Matrix：



Actual Positive

Actual Negative

Predicted YES

TP

FP

Predicted NO

FN

TN

12. 本阶段重点指标

由于 Positive 只有 5 个，不要过度强调 Accuracy。

12.1 Positive Detection

重点报告：

TP / 5

例如：

5 / 5
4 / 5
3 / 5

不要将小样本 Recall 描述成精确总体性能。

12.2 Negative False Alarms

重点报告：

FP / 100

例如：

2 / 100
5 / 100
12 / 100

这是本阶段最重要的工程指标之一。

需要判断：

LLM 是否对普通 source commits 产生大量不必要的 Harness update 建议？

12.3 Hard-Negative False Alarms

额外单独报告：

FP_hard / 20

因为 Hard Negative 更能验证模型是否真正理解 Harness maintenance semantics。

13. Reasoning Quality Evaluation

不能只评 YES / NO。

对所有：

5 Positive

所有 False Positive

所有 False Negative

人工检查以下三个字段：

Decision Correct

0 / 1

Reason Correct

0 / 1

Evidence Grounded

0 / 1

例如：

Case

Decision Correct

Reason Correct

Evidence Grounded

C001

1

1

1

C002

1

0

0

如果模型判断 YES 碰巧正确，但理由与真实 Harness gap 无关，不能视为高质量预测。

输出：

results/reasoning_quality.csv

14. False Positive Analysis

对全部 FP 分析原因。

重点检查是否存在：

FP-1

看到 new function 就建议更新 Harness，但该函数已经位于 Existing Harness 的可达路径中。

FP-2

看到 new condition 就认为 fuzzing 被阻断，但实际上输入空间没有明显变化。

FP-3

内部 API implementation change 被误判为 external API protocol change。

FP-4

普通重构被误认为 attack-surface expansion。

输出：

reports/false_positive_analysis.md

15. False Negative Analysis

对全部 FN 分析：

是否缺少必要代码 context

是否涉及跨文件调用

是否涉及 configuration

是否涉及隐式 state dependency

是否涉及复杂 API protocol

是否需要 call graph 信息才能判断

输出：

reports/false_negative_analysis.md

16. Go / No-Go 标准

本阶段仅判断是否值得继续研究，不用于发表最终性能结论。

Strong GO

如果满足：

Positive detected >= 4 / 5

并且：

False Positive <= 5 / 100

同时：

大部分 TP 的 Reason 和 Evidence 正确

则：

STRONG GO

进入下一阶段。

Moderate GO

如果：

Positive detected >= 3 / 5

并且：

False Positive <= 10 / 100

则：

MODERATE GO

需要进一步研究：

context selection

call graph evidence

configuration/state information

NO-GO

如果出现以下任一情况：

Positive detected <= 2 / 5

或者：

False Positive > 10 / 100

或者：

大量判断虽正确但 Reason/Evidence 错误

则当前简单 LLM semantic review 不具备足够可行性。

17. 剩余 8 个 Positive 的处理

剩余：

8 个 confirmed degradation cases

本阶段严格禁止使用。

不得用于：

Prompt tuning

case selection

few-shot example

rule design

如果本阶段结果为 GO：

下一阶段将这 8 个 case 作为完全独立的 Blind Hold-out Set。

18. 下一阶段（本 TASK 不执行）

只有本阶段达到 GO 后，再开展：

S1 + H0
    VS
S1 + H1

的 counterfactual dynamic validation。

重点比较：

changed-code coverage

new-function reachability

entry-point exposure

build/runtime compatibility

state/configuration adequacy

本阶段暂时不要实现 Harness 自动修改，也不要做复杂 Prompt Engineering。

19. 最终交付目录

harness-maintenance-feasibility/
│
├── TASK.md
├── README.md
│
├── data/
│   ├── selected_positive_cases.csv
│   ├── selected_negative_cases.csv
│   └── case_mapping.csv
│
├── cases/
│   ├── C001.md
│   ├── C002.md
│   └── ...
│
├── prompts/
│   └── fixed_prompt.md
│
├── results/
│   ├── llm_predictions.jsonl
│   ├── confusion_matrix.csv
│   ├── reasoning_quality.csv
│   └── summary.csv
│
└── reports/
    ├── feasibility_results.md
    ├── false_positive_analysis.md
    ├── false_negative_analysis.md
    └── go_no_go.md

20. feasibility_results.md 必须回答

最终报告必须明确给出：

5 个 Positive 中识别出几个？

100 个 Negative 中误报几个？

20 个 Hard Negative 中误报几个？

TP 的理由是否真正对应 Harness maintenance mechanism？

FP 主要来自什么类型的误判？

FN 主要缺少什么信息？

是否达到预定义 Go / No-Go 标准？

是否值得使用剩余 8 个 Positive 做第二阶段独立验证？

禁止只报告 Accuracy。