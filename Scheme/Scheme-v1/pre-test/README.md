# Fuzz Harness Maintenance Need：105-case 可行性预实验

本目录是 `task-2.md` 要求的盲测交付物。正式运行已经冻结：105 个匿名 case 各调用一次，105 个输出有效，0 失败，0 重试。

后续独立 hold-out 已于同日执行：剩余 8 个 confirmed event 中 **3 个判 YES、5 个判 NO**，0 失败、0 重试。完整输入、逐例输出和解释见 [`holdout/README.md`](holdout/README.md)。下文的 105-case 指标仍保持为原 pilot 的冻结结果，不用 hold-out 事后回写。

## 结论先行

| 指标 | 结果 |
|---|---:|
| 上一阶段项目数 | **10** |
| 上一阶段 commit 总数 | **16,155** |
| 上一阶段 confirmed degradation commits | **13** |
| 本阶段 Positive detection | **5 / 5** |
| 本阶段 Negative false alarms | **6 / 100** |
| 本阶段 Hard-negative false alarms | **3 / 20** |
| 混淆矩阵 | TP=5, FP=6, FN=0, TN=94 |
| 预注册门槛结论 | **MODERATE GO** |

这不是 Strong GO：虽然 `TP=5`，但 Strong GO 要求 `FP<=5`，实际 `FP=6`。这也不是 No-Go：`TP>2`、`FP<=10`，且 5 个 TP 的主理由和代码证据经事后逐例语义审计均正确。

上一阶段的 **NO-GO** 与这里的 **MODERATE GO** 不矛盾。前者表示只有 13 个 confirmed positive，不足以直接训练监督学习模型；后者表示在 105-case 小规模、人工筛选的语义审查实验上，LLM 值得进入独立 hold-out 验证。

## 正式协议

- 数据集：5 个 selected positive、100 个 adjudicated negative；100 个 negative 按 20 easy / 60 matched / 20 hard 分层，10 个项目各 10 个。
- 输入：source commit 的 parent harness `H0`、`S0 -> S1` production-source diff、历史 OSS-Fuzz build wiring。
- 隐藏：label、coverage、未来 commit、`H1`、harness diff、开发者后续行为、commit message、CVE/issue 结论和 Git blob ID。
- 洗牌：固定 seed `20260909`，匿名编号 `C001` 到 `C105`。
- 推理：`gpt-5.6-sol`，reasoning effort `high`，Codex CLI `0.145.0`。
- 隔离：每个 case 使用一个全新的 ephemeral 进程和空临时工作目录；固定 prompt 和固定 JSON schema；禁止工具、文件系统、网络和外部知识。
- 一次性：每个 case 只有一个主实验调用；正式 runner 在结果存在时拒绝再次运行。
- 时间：`2026-09-09T08:33:27Z` 至 `2026-09-09T08:44:27Z`。

## 目录

- `TASK.md`：原任务冻结副本。
- `config/selections.json`：105 个样本的预运行选择配置。
- `config/reasoning_audit.json`：解盲后，5 个 positive 及所有 FP/FN 的逐例审计。
- `data/selected_positive_cases.csv`：5 个正例和 phase-1 coverage 证据。
- `data/selected_negative_cases.csv`：100 个负例及分层。
- `data/withheld_positive_cases.csv`：在原 pilot 中 withheld、随后进入独立 hold-out 的 8 个 confirmed event。
- `data/case_mapping.csv`：解盲映射。
- `data/case_materialization.csv`：每个 case 的 source diff、H0 和 OSS-Fuzz revision 来源。
- `cases/C001.md` ... `cases/C105.md`：模型实际看到的冻结输入。
- `prompts/fixed_prompt.md`、`prompts/prediction_schema.json`：统一指令和输出 schema。
- `results/llm_predictions.jsonl`：105 个正式预测。
- `results/raw/`：每次调用的原始 JSON、stdout 和 stderr。
- `results/confusion_matrix.csv`、`summary.csv`、`case_outcomes.csv`、`reasoning_quality.csv`：解盲结果。
- `reports/`：选择、有效性、FP/FN 和 Go/No-Go 报告。
- `checksums.sha256`：核心交付物的 SHA-256。

## 本地复核

从项目根目录执行：

```bash
python3 pre-test/scripts/evaluate.py
python3 pre-test/scripts/validate_artifact.py
sha256sum -c pre-test/checksums.sha256
```

`build_dataset.py` 可以从上一阶段的本地 Git 仓库确定性地重新物化 case，但正式预测已经绑定到当前 case hash；不要在保存本次正式结果时重建后再混用旧预测。`run_blind_predictions.py` 是一次性 runner，检测到现有 manifest/results 时会退出，以防选择性重试。

## 解释边界

1. 5 个 positive 是从 13 个事件中刻意选出的最清晰案例，不是随机样本，因此 `5/5` 不能解释为总体 recall。
2. negative 是“未命中 phase-1 已知 degradation 且人工判断 H0 无明显同步维护需求”的控制样本，不是通过 counterfactual dynamic coverage 证明的 true negative。
3. 所谓 matched negative 主要在项目、时期和语义难度上匹配；LOC 匹配较弱。positive 的 production-source changed LOC 中位数为 1,193，matched negative 仅为 13。
4. 正例 context selection 使用了已知机制相关文件；`C098` 的超长 diff 还进行了 keyword-centered excerpt。这适合测试“给足必要上下文时是否能推理”，但会使检测结果偏乐观。
5. reasoning-quality 审计由 Codex 在结果冻结后逐例完成，不是独立的人类双评审。正式论文级实验仍需盲态双人 adjudication。
6. 6 个 FP 的 evidence 均能在代码中找到；错误集中在“已有 harness 的职责边界”而非虚构标识符。尤其 `C054` 具有较高标签边界争议，因此 nominal `6/100` 应保留原标签报告，同时做后续动态验证。

完整解读见 `reports/feasibility_results.md` 和 `reports/go_no_go.md`。
