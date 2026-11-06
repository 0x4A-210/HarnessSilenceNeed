# Independent Eight-Positive Hold-out

这是原 105-case pilot 之后执行的独立 hold-out 批次。8 个 phase-1 confirmed degradation events 在原实验期间未生成 case、未用于 prompt tuning，也未进入先前模型上下文。

## 结果

| Metric | Result |
|---|---:|
| Hold-out confirmed positives | 8 |
| Predicted YES / TP | **3 / 8** |
| Predicted NO / FN | **5 / 8** |
| Technical failures | 0 |
| Retries | 0 |
| Pilot + hold-out（描述性） | **8 / 13** positive labels detected |

命中的三个 case：

- C108 / wuffs：BMP 32-bpp 与新 pixel paths；
- C111 / h2o：HTTP/3、QUIC、QPACK 新协议和状态；
- C113 / libplist：新 output-only formats 与 writer APIs。

未命中的五个 case：C106 tidy-html5、C107 leptonica、C109 jansson、C110 meshoptimizer、C112 c-ares。

## 必须区分的两种解释

按 phase-1 的历史 coverage-degradation label 严格计数，结果就是 `TP=3, FN=5`。但这 5 个 FN 并非同质：

- C107 和 C110 的历史成因就是 anchor commit 中的 harness change。按本次协议，H1/harness diff 必须隐藏，所以真实成因在输入中不可观察；C110 因此没有任何 eligible production-source diff。
- C106 是 parser 重写造成的 fuzzing performance/throughput regression。固定 semantic maintenance definition 没有运行时性能指标，仅凭静态 diff 很难判定 coverage 会下降。
- C109 和 C112 的 changed path 已经能由 H0 进入。它们是论文原 coverage-ratio 定义下的 positive，但是否构成新的 semantic harness maintenance need 有定义歧义。

因此，独立测试明确否定了“先前 5/5 可以直接泛化到全部 13 个 degradation events”的说法；同时也说明 13 个 coverage positives 不能不经可观察性/语义筛选就直接作为 source-only maintenance-need prediction 的同质 ground truth。

## 独立性保证

- 固定 prompt、schema、model、reasoning effort、concurrency 和 timeout 与 pilot 的 SHA/值完全相同。
- 继续使用原 `build_dataset.py` 的 H0、diff、excerpt 和 case template 函数；没有修改原文件。
- 8 个事件使用 seed `20260909` 单独洗牌为 C106–C113。
- 每个 case 使用新的 ephemeral Codex process；工作目录为空；一次调用，无重试。
- runner 只读取 `inputs/Cxxx.txt` 和共同 schema，不读取 mapping、degradation evidence、pilot predictions 或 reports。
- GPT 每次只看到一个 anonymous case；prompt 没有告诉它批次大小、class composition 或这 8 个都是 positive。
- 输入中没有 label、coverage、artifact conclusion、commit message、H1/harness diff、先前 5 个回答或 FP/FN 分析。

模型和运行信息：`gpt-5.6-sol`，reasoning effort `high`，Codex CLI `0.145.0`。8/8 输出有效。

## 精确输入和输出

- `inputs/C106.txt` ... `inputs/C113.txt`：逐字节送给 GPT 的完整内容，包含 fixed prompt、case 和 boundary markers。
- `results/raw/Cxxx.json`：每个 case 的原始 JSON 输出。
- `results/input_output_pairs.jsonl`：8 对完整输入和输出的机器可读副本。
- `reports/case_by_case.md`：逐 case commit、判断、confidence、精确 input/output 链接及原始 JSON。
- `reports/holdout_results.md`：中文结果与解释。
- `reports/validation.md`：独立性、hash、泄漏和一次性执行验证。

## 本地复核

```bash
python3 pre-test/holdout/scripts/evaluate_holdout.py
python3 pre-test/holdout/scripts/validate_holdout.py
sha256sum -c pre-test/holdout/checksums.sha256
```

正式结果存在后，builder 和 runner 都会拒绝重建或重跑，防止 case 漂移和选择性 retry。
