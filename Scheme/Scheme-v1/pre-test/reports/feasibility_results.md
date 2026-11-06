# Feasibility Results

## 冻结结果

| 核心问题 | 结果 |
|---|---:|
| 5 个 Positive 中识别出几个？ | **5 / 5** |
| 100 个 Negative 中误报几个？ | **6 / 100** |
| 20 个 Hard Negative 中误报几个？ | **3 / 20** |
| TP 的 Reason Correct | **5 / 5** |
| TP 的 Evidence Grounded | **5 / 5** |
| 预注册决策 | **MODERATE GO** |

不要把 `5/5` 写成总体 recall 估计：这里只有 5 个经目的性选择的清晰 positive。

## Confusion Matrix

| | Actual Positive | Actual Negative |
|---|---:|---:|
| Predicted YES | TP = 5 | FP = 6 |
| Predicted NO | FN = 0 | TN = 94 |

模型共给出 11 个 YES。负例分层结果为：

| Negative stratum | FP | Total | Nominal false-alarm rate |
|---|---:|---:|---:|
| Easy | 0 | 20 | 0% |
| Matched | 3 | 60 | 5% |
| Hard | 3 | 20 | 15% |
| All negative | 6 | 100 | 6% |

## Positive 检测

| Case | Project | Commit | 主要 maintenance mechanism | Decision | Confidence | Reason / Evidence audit |
|---|---|---|---|---:|---:|---:|
| C004 | wuffs | `555e8eaaa368` | 新的独立 `config_decoder` 入口与状态序列 | YES | 98 | 1 / 1 |
| C038 | libspng | `cb18f38c1f2c` | H0 固定 `SPNG_CRC_USE`，无法进入新的 `CRC_DISCARD` 配置路径 | YES | 90 | 1 / 1 |
| C055 | libplist | `429cbc660ae1` | 新 JSON parser/format；H0 仅调用 binary/XML parser | YES | 99 | 1 / 1 |
| C094 | brotli | `19d86fb9a60a` | shared dictionary 必须在 decode 前 attach | YES | 99 | 1 / 1 |
| C098 | c-ares | `7d3591ee8a1a` | 新 `ares_getaddrinfo` 异步 workflow、hints/service/callback state | YES | 96 | 1 / 1 |

五个回答都不只是看到代码新增后给 YES，而是分别指出了 H0 中缺失的 decoder type、configuration value、format entry point、pre-decode state setup 或异步 API workflow。逐例审计认为 5/5 主理由对应预选的真实 maintenance mechanism，5/5 证据可在冻结 case 内直接核对。

## False Positive 概况

| FP category | 数量 | Cases | 主要模式 |
|---|---:|---|---|
| FP-1：看到新增 API 就扩大 harness | 1 | C075 | 新 node type 的 parser 路径已经由 H0 覆盖，但回答要求额外覆盖 constructor/writer |
| FP-2：把 validation/input change 当作 H0 barrier | 1 | C054 | TIFF 的局部接受条件变化被解释为 SPIX/barcode H0 必须扩展到 TIFF |
| FP-3：内部状态实现误作外部调用协议 | 2 | C022, C025 | 既有 API 内的 loop tracking 被解释为 H0 必须新增图构造模式 |
| FP-4：重构/优化误作功能扩张 | 2 | C018, C021 | key-length reuse 或 private bpp 算法简化被解释为新的输入空间 |

六个 FP 的代码引用均 grounded；它们不是凭空捏造函数。错误发生在结论层：回答把“目标未覆盖某个既有 API、内部状态或旁支 codec”自动提升为“这次 commit 要求同步维护当前 H0”。因此 Q4 的答案是：没有“任何 source change 都报警”的简单倾向（94/100 negative 判 NO、20/20 easy 判 NO），但有明显的 **scope-expansion bias**。

全部 FP 的 confidence 为 92–97，中位数 94。这说明 confidence 尚不能区分 TP 与 scope-boundary FP，后续不能把高 confidence 直接当作高优先级告警。

详见 `false_positive_analysis.md`。

## False Negative

本轮 `FN=0`，所以无法从本样本归纳“FN 缺少何种 context”。任何关于跨文件调用、configuration 或隐式 state 导致 FN 的结论都将是样本外猜测。详见 `false_negative_analysis.md`。

## Reasoning Quality

任务要求对全部 5 个 positive、全部 FP 和全部 FN 审计。本轮共审计 11 个 case：

| Audited subset | Cases | Decision Correct | Reason Correct | Evidence Grounded |
|---|---:|---:|---:|---:|
| True Positive | 5 | 5 | 5 | 5 |
| False Positive | 6 | 0 | 0 | 6 |
| False Negative | 0 | N/A | N/A | N/A |

对 FP，`reason_correct=0` 表示其中心论证不足以支持冻结的 negative label；`evidence_grounded=1` 表示引用的函数、条件和 H0 调用关系真实存在。这两个字段不能混为一谈。

审计由 Codex 在 105 个预测全部完成并冻结后逐例执行，未用于重试或挑选回答；它不等价于独立人类双评审。

## 对五个研究问题的回答

1. **Q1：能识别几个 positive？** 5/5。
2. **Q2：会误报多少 negative？** 6/100；其中 hard negative 为 3/20。
3. **Q3：理由是否基于代码？** 5 个 TP 全部机制正确且证据 grounded；6 个 FP 也都引用真实代码，但维护范围推论错误。
4. **Q4：是否“只要变化就报警”？** 没有普遍报警；但对不在 H0 当前职责内的既有 API/子系统存在扩大覆盖范围的倾向。
5. **Q5：是否值得下一阶段？** 值得，但仅达到 Moderate GO。应冻结更明确的 target-scope adjudication 规则后，再一次性测试剩余 8 个 hold-out positive，并加入动态 counterfactual validation。

## 有效性限制

- positive 是人工选择的 5 个清晰事件，并且规模显著大于 negative：positive changed LOC 中位数 1,193；matched negative 中位数 13、最大值 359。
- positive 的 context selection 使用已知 mechanism 选择关键文件；C098 的 diff 超过限制后使用关键词中心 excerpt。这可能降低 positive 的判断难度。
- negative 的“无 maintenance need”是静态 adjudication，不是 `S1+H0` 与 `S1+H1` 动态实验结论。
- C054 的 label boundary 尤其有争议：若把“项目级 harness portfolio 应覆盖任何新接受的 codec input class”作为定义，它可能不应当是 negative。本报告不事后改标签，因此仍按预运行 mapping 计为 FP。
- 样本量太小，不能据此声称跨项目泛化性能或给出精确置信区间。
