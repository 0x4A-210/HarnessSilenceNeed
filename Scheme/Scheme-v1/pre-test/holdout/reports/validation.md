# Hold-out Validation Report

## Status

最终全量验证：`PASS`。

- Hold-out cases：8；
- Exact input files：8；
- Predictions：8；
- Unique attempts：8；
- Technical failures：0；
- Retries：0；
- Strict result：TP=3, FN=5。

## 与 pilot 完全相同的冻结项

| Item | Pilot | Hold-out | Match |
|---|---|---|---|
| Model | `gpt-5.6-sol` | `gpt-5.6-sol` | yes |
| Reasoning effort | `high` | `high` | yes |
| Codex CLI | `0.145.0` | `0.145.0` | yes |
| Concurrency | 4 | 4 | yes |
| Timeout | 900s | 900s | yes |
| Prompt SHA-256 | `066f8f1bb1a87c644224ff4cd210be4ac1e0be49fd5f6d09aa00c35bdc4fd16f` | same | yes |
| Schema SHA-256 | `e3d637b8e0c73dcd4c2a87ee0a3d6ae80c3e1a576dfe780d8356b8d3b78e2441` | same | yes |
| Base generator SHA-256 | `40424d8bd9a737fc7c86cedd2090caa75ab8fdd7859001c3f4c7296c0ca71fdb` | same unchanged file | yes |

## Blind input checks

对 C106–C113 全量检查：

- `inputs/Cxxx.txt` 精确等于 frozen prompt + anonymous case + 原 boundary markers；
- input SHA 同时匹配 pre-run dataset manifest、de-blind mapping 和 run manifest；
- case SHA 匹配 pre-run dataset manifest 和 mapping；
- 不含本 case commit ID、parent ID、label、degradation metric、CVE/ClusterFuzz 结论；
- 不含原 5 个 positive 的 case ID、commit ID、parent ID、答案、Moderate-Go 或 FP 分析 cue；
- source diff 不含 Git blob ID；
- source diff path 不包含任何已知 H0 文件或 `fuzz/fuzzer/fuzzing` directory；
- post-H0 harness diff、coverage、future commit 和 artifact conclusion 没有传给模型。

GPT 每次只看到一个 exact input。runner 源码不读取 case mapping、phase-1 evidence、pilot `llm_predictions.jsonl` 或任何 report。

## One-shot execution checks

- run manifest status：`complete`；
- 8 个 attempt ID 唯一；
- 8 个 exit code 均为 0，8 个 JSON 均有效；
- 每个输出严格具有原 schema 的 8 个字段；
- raw JSON 与 aggregate JSONL 逐对象一致；
- stderr 的 anonymous-case boundary 之后未出现 tool-call marker；
- builder 和 runner 在正式 manifest 存在后拒绝重建/重跑。

## Exact input/output preservation

- 8 个完整输入单独保存在 `inputs/`；
- 8 个 raw JSON、stdout、stderr 保存在 `results/raw/`；
- `results/input_output_pairs.jsonl` 再次逐字保存 exact input，并嵌入 exact parsed output；
- `reports/case_by_case.md` 提供逐 case 链接和原始 JSON；
- `checksums.sha256` 固定全部 hold-out 交付物。

## Case materialization facts

- C106、C109、C111 的 source diff 超过 58,000 字符，使用原 generator 的 keyword-centered excerpt。
- C110 的 anchor commit 只修改 `tools/codecfuzz.cpp`，它同时就是 H0 harness；按禁止 H1 的规则排除后，exact input 的 production-source diff 为空。
- C107 的 `prog/fuzzing/pix_rotate_shear_fuzzer.cc` diff 按 harness exclusion 隐藏；只保留同 commit 的 `prog/cleanpdf.c` production diff。
- H2O merge 的完整 production path list 沿用原 classifier，其中 `t/` 路径未被旧规则识别为 tests；实际 selected diff paths 只含 HTTP/3/QPACK production files。该已冻结规则没有在 hold-out 中修改。

这些事实影响可观察性，但没有在预测后修改 case 或补跑模型。
