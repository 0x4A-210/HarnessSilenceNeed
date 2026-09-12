# False-Negative Analysis

Evolution-Aware 在 20 个有效 commit-induced positives 上为 20 TP、0 FN；Gap-Only
同样为 20 TP、0 FN。因此本轮没有可逐项分析的 positive false negative，recall loss
为 0 percentage points。

## Positive 类型

- 17 个新增 decoder/hasher subsystem 或 major decoding surface：20 个 positive 中的
  P001–P011、P013–P014、P016–P017、P019–P020（按 candidate ID）。
- 3 个显式 public configuration：P012
  `QUIRK_ALLOW_NON_ZERO_INITIAL_BYTE`、P015
  `QUIRK_REJECT_PROGRESSIVE_JPEGS`、P018 `QUIRK_JUST_RAW_THUMBHASH`。

模型对这两类都稳定使用了 concrete identifiers：它识别 H0 编译/实例化的是另一个
module，或识别 H0 没有设置新增 quirk，并在 S0/S1 对比中指出该 surface/configuration
在 S0 不存在。完整输出位于 `predictions/evolution_aware.jsonl`，逐 case 完整输入输出
位于 `predictions/evolution_aware_input_output_pairs.jsonl`。

## 不应过度解释

100% recall 的 Wilson 95% CI 仍为 [83.89%, 100%]。本 positive 集的新增边界较显式，
不覆盖隐式跨文件 protocol change 的全部难度；它只能说明本轮没有因 attribution
步骤损失 recall，不能推出一般场景的真实 recall 为 100%。

