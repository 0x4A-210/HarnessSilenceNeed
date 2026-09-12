# 剩余 8 个 Positive 的独立盲测结果

## 核心结果

- Phase-1 confirmed positive：8
- GPT 判 YES：**3 / 8**
- GPT 判 NO：**5 / 8**
- 技术失败：0
- 重试：0
- 与原 pilot 描述性合并：**8 / 13** confirmed degradation labels 被判 YES

`3/8` 是严格按历史 coverage-degradation ground truth 计算的 hold-out detection；不能因为部分标签与 semantic maintenance need 不完全一致就事后改成更高数字。

## 每个 case

| Case | Project | Commit | GPT | Conf. | Strict result | 精确输入 | 原始输出 | 事后解释 |
|---|---|---|---:|---:|---:|---|---|---|
| C106 | tidy-html5 | `c8fbde59031e` | NO | 96 | FN | [input](../inputs/C106.txt) | [JSON](../results/raw/C106.json) | 静态上 H0 仍进入 parser；真实 drop 是 recursive-to-stack 重写后的 fuzzing performance regression，固定定义无运行时性能信号 |
| C107 | leptonica | `f201a12680be` | NO | 99 | FN | [input](../inputs/C107.txt) | [JSON](../results/raw/C107.json) | 真实成因是同 commit 的 fuzzer 将 TIFF 提前 return；该 H1 diff 按协议隐藏，输入只剩无关的 cleanpdf cleanup |
| C108 | wuffs | `f6f2ac4206d9` | YES | 98 | TP | [input](../inputs/C108.txt) | [JSON](../results/raw/C108.json) | 正确识别 BMP 32-bpp、header/mask 和 pixel-swizzler 新路径不在所给 GIF/zlib H0 中 |
| C109 | jansson | `50953fb1facc` | NO | 97 | FN | [input](../inputs/C109.txt) | [JSON](../results/raw/C109.json) | H0 已通过 real parsing 和两种 dump API 到达新的 dtoa path；coverage ratio drop 与新的调用需求并不等价 |
| C110 | meshoptimizer | `1296f84bc719` | NO | 100 | FN | [input](../inputs/C110.txt) | [JSON](../results/raw/C110.json) | anchor 只修改 `tools/codecfuzz.cpp` 并删除 scalar path；禁止 H1 后 source diff 为空，真实原因不可观察 |
| C111 | h2o | `93af1383b248` | YES | 99 | TP | [input](../inputs/C111.txt) | [JSON](../results/raw/C111.json) | 正确识别 HTTP/3/QUIC/QPACK 的新入口、datagram/stream state 和 H0 仅 HTTP1/2 的 gap |
| C112 | c-ares | `955df983d7f6` | NO | 96 | FN | [input](../inputs/C112.txt) | [JSON](../results/raw/C112.json) | H0 已把任意 name 送入 changed `ares_create_query` 的 `.onion` branch；其他 lookup APIs 未覆盖，但没有新 caller protocol |
| C113 | libplist | `3aa5f6a3a663` | YES | 99 | TP | [input](../inputs/C113.txt) | [JSON](../results/raw/C113.json) | 正确识别三个新 output format、public writer APIs/options 完全不被 parser-only H0 调用 |

逐 case 的完整 JSON、完整理由和 SHA-256 见 [case_by_case.md](case_by_case.md)。该文件中的 input 链接指向实际 pipe 给模型的完整 UTF-8 文本，并非报告摘要。

## 对 5 个 FN 的机制分类

| Category | Cases | Count | 是否能从允许输入可靠推断 |
|---|---|---:|---|
| Hidden harness change | C107, C110 | 2 | 否；关键 H1 diff 被协议明确禁止 |
| Performance degradation outside static definition | C106 | 1 | 仅部分；diff 可见，但无 throughput/coverage observation |
| Coverage degradation vs semantic adequacy mismatch | C109, C112 | 2 | 有歧义；H0 已进入至少一个核心 changed path |

真正符合首轮所选 P1–P5 语义、且从输入中清楚可见的三例正好是 C108、C111、C113，模型全部判 YES。这个观察是事后解释，不是新的 performance denominator，也不能把 nominal `3/8` 改写为 `3/3`。

## 原 5/5 是否得到复现

没有。原 pilot 的 5 个 positive 是有意选择的清晰 source-evolution → H0-gap case；hold-out 包含 performance regression、harness-self-change 和 coverage-denominator/semantic ambiguity。结果从 5/5 降到 3/8，显示强烈的 positive-selection effect。

描述性合并两个批次：

- detected：8；
- confirmed events：13；
- `8/13 = 61.5%`。

两个批次的 case 可观察性和选择过程不同，因此这个比例也不是总体 recall 估计。

## 现在可以准确得出的结论

1. 固定 LLM semantic review 能检测清晰的新入口、新格式、新协议和 caller-visible state gap。
2. 它不能在看不到 H1 的情况下预测由 harness 自身修改直接造成的 degradation；这不是增加静态 source context 可以解决的问题。
3. 当前 degradation ground truth 与预测目标没有完全对齐：论文指标测量 project-aggregate coverage percentage drop，而 prompt 判断 semantic harness adequacy。
4. 若研究目标仍是“预测论文定义的所有 degradation”，特征必须加入 performance/cost signals，并处理 harness-change events；仅有 `S0→S1 + H0` 不足。
5. 若研究目标是“source evolution 是否产生 semantic maintenance need”，则应先过滤不可观察的 harness-self-change，并对 C109/C112 这类 label ambiguity 做独立双评审和动态 changed-path validation。

本轮没有 negative，所以无法重新估计 FP；原 pilot 的 `6/100` 不因本轮改变。
