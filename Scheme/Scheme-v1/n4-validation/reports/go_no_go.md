# Go / No-Go Decision

## Decision: NO-GO

| Criterion | STRONG GO | MODERATE GO | Observed | Result |
|---|---:|---:|---:|---|
| Valid N4 | ≥20 | — | 16 | Fail |
| Valid positive | ≥20 | — | 20 | Pass |
| Evolution N4 FPR | ≤10% | ≤20% | 43.75% | Fail; also >30% NO-GO boundary |
| Positive recall | ≥75% | ≥60% | 100% | Pass |
| FP reduction | ≥60% | ≥40% | 56.25% | Moderate-only pass |

两个硬失败足以决定 NO-GO：冻结后只有 16 个有效 N4，且 Evolution-Aware N4 FPR
为 43.75%，超过 task-4 的明确 NO-GO 阈值 30%。

## 为什么不能因为 FP reduction 而 GO

Evolution-Aware 从 16 个 FP 降到 7 个，paired exact p=0.003906，说明方法 prompt
确实改变了最终 maintenance 分类；recall 也没有下降。然而，只有 2/16 个 N4 完成
了实验目标的完整推理：

```text
gap_exists = YES
commit_induced = NO
maintenance_needed = NO
```

另 7 个 TN 来自 `gap_exists=NO`。所以观察到的 56.25% FP reduction 大部分是更严格
的 gap materiality 判断，而不是稳定的 evolution attribution。N4 attribution accuracy
仅 9/16 = 56.25%，完整目标模式仅 12.5%。

## 数据质量信号

冻结后 4/20（20%）N4 被 INVALIDATE，暴露出 candidate rule 只证明“某个旧 API
gap 不变”仍不够：同一 commit 可能同时引入另一个 configuration/state/subsystem
gap。按协议没有 relabel、补样本或重跑，因此这个缺陷没有被结果驱动的修补掩盖。

## 可支持与不可支持的结论

可以支持：在这个 Wuffs matched set 中，两步 prompt 保持 100% positive recall，并
显著减少最终 maintenance FP。

不可以支持：Evolution Attribution 已可靠区分 historical existing gap 与
commit-induced gap；跨项目外部效度也没有建立，因为本轮只有一个项目。

因此当前阶段应停止对强机制结论的扩展。下一轮若继续，应在预测前增加“commit 中
是否存在任意第二个新 gap”的全 diff 审计，并补充新项目；不能复用本轮输出做同一
test set 上的 prompt 调参。

作为保守敏感性检查，不排除四个 INVALIDATE、直接沿用全部原 frozen labels 时，
Evolution N4 FPR 为 11/20 = 55%，FP reduction 为 45%，仍然明确 NO-GO。因此
decision 不依赖 post-freeze exclusion。
