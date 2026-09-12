# Validation Report

## 最终状态

`scripts/validate_artifact.py` 返回 `PASS`：

- cases：105；
- selected positive：5；
- selected negative：100；
- withheld positive：8；
- predictions：105；
- raw attempts：105；
- failed predictions：0。

## Dataset checks

- class allocation 为 5 positive / 100 negative；
- negative strata 为 20 easy / 60 matched / 20 hard；
- 10 个项目各有 10 个 negative；
- selected 5 和 withheld 8 均来自 phase-1 confirmed set、互不重叠、合计 13；
- 每个 negative 都在 phase-1 commit universe 中，parent 一致，且不属于 confirmed set；
- 105 个 case ID、mapping ID、prediction ID 和 raw-result ID 完全一致。

`build_dataset.py` 还在物化阶段验证了 negative 的 single-parent、production-source path 和无 fuzz/harness-file change 条件。

## Blindness and leakage checks

对 105 个 case 全量检查：

- case SHA-256 同时匹配 `case_mapping.csv`、`case_materialization.csv` 和正式 `run_manifest.json`；
- case 内不含对应 source commit ID 或 previous commit ID；
- diff 删除 Git `index oldblob..newblob` 行；
- case 内无 `actual_label`、degradation metric 字段、ClusterFuzz testcase、CVE cue；
- commit message、post-commit coverage、future commit、H1/harness diff 和 developer outcome 未作为输入；
- runner 的 label mapping 未被读取或传给 predictor；
- 105 个 stderr 在 anonymous-case 边界之后均无工具调用 marker。

H0 来自 source commit parent；OSS-Fuzz build wiring 取 source commit 时间之前最近的本地 OSS-Fuzz revision。精确来源写入 `data/case_materialization.csv`。

## Prediction integrity

- manifest status 为 `complete`；
- 105 个 attempt 的 case ID 唯一，每个 `exit_code=0` 且 `valid_prediction=true`；
- 每个输出字段严格为 schema 的 8 个字段；
- decision 是 boolean，confidence 在 0–100，reason/evidence 非空；
- 每个 case 使用新的 ephemeral process 和共同的空临时工作目录；
- 无 retry，也无人工挑选多个回答。

固定输入哈希：

- prompt SHA-256：`066f8f1bb1a87c644224ff4cd210be4ac1e0be49fd5f6d09aa00c35bdc4fd16f`
- schema SHA-256：`e3d637b8e0c73dcd4c2a87ee0a3d6ae80c3e1a576dfe780d8356b8d3b78e2441`

## Evaluation integrity

`scripts/evaluate.py` 从冻结 mapping 与 prediction 计算出：TP=5、FP=6、FN=0、TN=94；easy/matched/hard FP 分别为 0/3/3；预注册 gate 为 `MODERATE GO`。

reasoning audit 覆盖集合由程序强制为“全部 actual positive + 全部 FP + 全部 FN”，本次为 11 个 case。任何漏审或额外审计 case 都会导致 evaluation 失败。

## 已知限制和 erratum

1. case 文本中的固定说明对未 excerpt 的 diff 使用了“complete diff for the production-source files listed below”措辞；但 C055、C094 的实际 diff 是配置中 mechanism-relevant file subset，完整 production file list 只用于披露。确切差异以 `case_materialization.csv` 的 `source_diff_paths` 与 `production_source_paths` 为准。为了保持正式 case hash，不在运行后修改冻结输入。
2. C098 是唯一 `diff_excerpted=true` 的 case；其 excerpt 是已知机制关键词中心选择，可能提高 positive 可识别性。
3. 负例没有 counterfactual dynamic validation，不能等同于已证明 coverage 不变。
4. reasoning audit 不是独立人类双评审。
5. matched negative 的 LOC 分布没有真正匹配 positive；详见 `selection_audit.md`。

这些限制不改变 nominal confusion matrix，但限制其外部有效性和可发表性解释。
