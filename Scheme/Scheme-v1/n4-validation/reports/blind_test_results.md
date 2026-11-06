# Blind Test Results

## 主结果

主结果排除 4 个冻结后 `INVALIDATE`，使用 16 N4 + 20 positive。

| Method | Positive Recall | N4 Existing-Gap FPR | Overall FPR | Accuracy |
|---|---:|---:|---:|---:|
| Gap-Only | 20/20 = **100%** | 16/16 = **100%** | 100% | 20/36 = 55.56% |
| Evolution-Aware | 20/20 = **100%** | 7/16 = **43.75%** | 43.75% | 29/36 = 80.56% |

Wilson 95% CI：positive recall 100% 的区间为 [83.89%, 100%]；Gap-Only N4 FPR
为 [80.64%, 100%]；Evolution-Aware N4 FPR 为 [23.10%, 66.82%]。

Gap-Only 的 16 个 N4 全部误报。Evolution-Aware 修复其中 9 个、没有新增反向错误：

```text
FP Reduction = (16 - 7) / 16 = 56.25%
paired exact McNemar/binomial p = 0.00390625
```

但 maintenance 分类改善不能直接等同于 attribution 成功。在 16 个有效 N4 中：

- `commit_induced=NO`：9/16。
- `gap_exists=YES`：9/16。
- 同时给出目标模式 `gap=YES, induced=NO, maintenance=NO`：仅 2/16 = 12.5%。
- 另外 7 个 TN 是通过 `gap_exists=NO` 获得，而不是识别 existing gap 后正确归因。

整体 evolution-attribution accuracy 为 29/36 = 80.56%；positive attribution 为
20/20，N4 attribution 为 9/16。

### Frozen-label sensitivity

四个 post-freeze invalidation 都被 Evolution-Aware 预测为 maintenance YES。为明确
展示排除的影响，全部 40 个原冻结标签下的 sensitivity 是：Gap-Only N4 FPR
20/20 = 100%，Evolution-Aware N4 FPR 11/20 = 55%，FP reduction 45%，positive
recall 20/20。它仍跨过 30% NO-GO 边界，因此最终结论不依赖 invalidation 带来的
指标改善。该视图只做敏感性分析，不把已知错误 GT 重新放回主结果。

## `task-4.md` 的 14 个问题

1. **最终有效 N4 Existing-Gap case 有多少？** 16。冻结时 20，之后 4 个按协议
   INVALIDATE，未补样本。
2. **最终有效 Commit-Induced Positive 有多少？** 20。
3. **Gap-Only 在 N4 上误报多少？** 16/16。
4. **Evolution-Aware 在 N4 上误报多少？** 7/16。
5. **N4 FPR 从多少下降到多少？** 100% 降至 43.75%，绝对下降 56.25 percentage
   points。
6. **FP Reduction 是多少？** 56.25%。
7. **Evolution-Aware Positive Recall 是多少？** 20/20 = 100%。
8. **Evolution Attribution 是否显著降低 Existing-Gap FP？** 对最终 maintenance
   prediction，paired exact p=0.003906，说明本样本内下降明确；但只有 2 个 N4 以
   `gap yes / induced no` 的目标路径修复，因此不能据此声称 attribution mechanism
   本身稳定有效。
9. **Recall 损失是否可接受？** 为 0 percentage points；两种方法都是 100%，可接受。
10. **哪类 Existing Gap 最容易被错误归因？** “已有 subsystem/API 完全不在 H0，
    当前 commit 修改内部实现或 CPU-specific fast path”最易被当作当前 commit 加剧，
    primary category FP-N4-3（4/7 FP）。
11. **哪类 Commit-Induced Gap 最容易识别？** 明确新增且 H0 未编译/实例化的 decoder/
    hasher subsystem，以及显式新增但 H0 未设置的 public quirk；本集两类均 100% recall。
12. **Ground Truth 是否在 Prediction 前冻结？** 是。GT 08:30:37Z，输入/config
    08:30:39–40Z，首个 prediction 08:32:27Z。
13. **Prediction 后是否发生 relabel 或 INVALID？** 0 relabel；4 INVALIDATE；0 replacement。
14. **是否达到 STRONG GO / MODERATE GO / NO-GO？** **NO-GO**。有效 N4 <20、
    Evolution N4 FPR 43.75% >30%，且目标 attribution pattern 只有 12.5%。

## 解释边界

FP reduction 超过 MODERATE GO 的 40% 条件，recall 也超过门槛，但 MODERATE GO 同时
要求 N4 FPR ≤20%，本结果不满足。样本又因冻结后 invalidation 降至 16，置信区间较宽。
因此可以说“两步 prompt 对最终分类有明显帮助”，不能说“Evolution Attribution 已经
可靠地区分 historical gap 和 commit-induced gap”。
