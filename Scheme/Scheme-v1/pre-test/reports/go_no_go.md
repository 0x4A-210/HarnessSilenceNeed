# Go / No-Go Decision

## 决策：MODERATE GO

| 预注册条件 | 本次结果 | 是否满足 |
|---|---:|---:|
| Strong GO：TP >= 4 / 5 | 5 / 5 | 是 |
| Strong GO：FP <= 5 / 100 | 6 / 100 | **否** |
| Strong GO：大部分 TP reason/evidence 正确 | 5 / 5、5 / 5 | 是 |
| Moderate GO：TP >= 3 / 5 | 5 / 5 | 是 |
| Moderate GO：FP <= 10 / 100 | 6 / 100 | 是 |
| No-Go：TP <= 2 / 5 或 FP > 10 / 100 | TP=5, FP=6 | 否 |

因此只能按预注册规则判定 **MODERATE GO**。距离 Strong GO 差 1 个 false positive；不能把 `6` 四舍五入成 `5`，也不能在看到输出后删除或重标争议负例。

## 当前阶段说明了什么

1. 在给出 H0、source diff 和必要上下文时，LLM 能识别本轮 5 个清晰的 new-entry-point、configuration、API protocol 和 state requirement 机制，而且能指出具体函数和缺失调用。
2. 模型没有简单地对所有 source change 报警：100 个 negative 中 94 个判 NO，20 个 easy negative 全部判 NO。
3. 困难边界仍不稳定：20 个 hard negative 中误报 3 个；6 个 FP 的 confidence 都超过 90。
4. 误报主要是 scope 判断，而不是代码幻觉。模型能看到真实未覆盖路径，却不能稳定判断它属于“应同步维护当前 H0”还是“项目内另一个既有 API/子系统”。
5. 本结果支持继续研究 semantic review，但不支持宣称已有可部署的自动告警器，更不支持从 5 个 positive 推断总体 recall。

## 为什么上一阶段是 No-Go，而这里不是

上一阶段的 No-Go 针对的是 **监督学习数据可用性**：10 个项目、16,155 个 commit 中只有 13 个经论文原定义和 artifact 确认的 degradation commit，远低于任务设定的 30 个 positive 门槛；其余 16,142 个也只能叫 unlabeled，不能直接冒充 negative 训练模型。

本阶段换了一个更窄的问题：不训练模型，只用固定 LLM prompt 对 105 个经人工构造的 case 做一次性 blind semantic review。这个问题的门槛独立，因此可以得到 Moderate GO，同时保留“监督学习仍 No-Go”的结论。

## 是否使用剩余 8 个 Positive

**值得，但应以独立 hold-out 的形式进行。** 在解封前应完成以下冻结动作：

- 明确 current target scope 与 project-wide coverage expansion 的边界；
- 使用与 label 无关、对正负例统一的 context-selection 算法；
- 预注册 ambiguous-negative adjudication 和双评审分歧处理；
- 预注册 `S1+H0` vs `S1+H1` changed-code reachability/coverage 验证；
- 保留单次调用、匿名 case 和失败处理规则。

完成这些后，才一次性运行 8 个 hold-out positive。不要用它们做 prompt tuning、few-shot、规则设计或反复试跑。

## 暂不授权的推论

- 不能说模型总体 recall 是 100%。
- 不能把 100 个静态 adjudicated negative 当成动态证明的 true negatives。
- 不能因为达到 Moderate GO 就直接进入自动 harness 修改或大规模部署。
- 不能忽略 positive/negative 的 LOC 和 context-selection 不平衡。
