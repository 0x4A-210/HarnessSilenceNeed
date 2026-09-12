# Task 4 — N4 Existing-Gap Validation

本目录是 `task-4.md` 的完整、可审计实验产物。实验专门比较 Gap-Only 与
Evolution-Aware 是否能区分历史 Harness Gap 和当前 commit 引入/加剧的 Gap。

## 最终结论

**NO-GO**。冻结时为 20 N4 + 20 positive；预测冻结后，严格复审按不可变协议
将 4 个错误构造的 N4 标记为 `INVALIDATE`，没有 relabel 或补样本。因此主结果
使用 16 N4 + 20 positive：

| Method | Positive Recall | N4 Existing-Gap FPR | Accuracy |
|---|---:|---:|---:|
| Gap-Only | 20/20 = 100% | 16/16 = 100% | 55.56% |
| Evolution-Aware | 20/20 = 100% | 7/16 = 43.75% | 80.56% |

Evolution-Aware 消除了 9 个 FP，FP reduction 为 56.25%，但 N4 FPR 仍高于
NO-GO 边界 30%。更关键的是，只有 2/16 个有效 N4 输出了目标推理模式
`gap_exists=true, commit_induced=NO, maintenance_needed=false`；另 7 个 TN 是
通过 `gap_exists=false` 得到的，不能作为 evolution attribution 成功的证据。

为避免 invalidation 造成选择性乐观，`results/frozen_label_sensitivity.csv` 也保留全部
原冻结标签：在 20 个 frozen N4 上 Evolution-Aware FPR 是 11/20 = 55%，FP
reduction 是 45%。这个不排除任何 case 的视图同样是 NO-GO。

## 实验完整性

- 项目：Wuffs（1 个项目）；40 个唯一 commit，和既有 development/77-case/
  pre-test 数据的 commit 重叠为 0。
- Ground truth 冻结：`2026-09-10T08:30:37.725376Z`。
- Prediction 冻结：`2026-09-10T08:44:50.993034Z`，之后才 reveal labels。
- 模型：`gpt-5.6-sol`，reasoning effort `high`，temperature/max tokens 未设置，
  每 case 每 method 一个独立 ephemeral process，0 retry。
- 80 次预测全部成功；两个方法看到逐 case 相同的冻结 case 内容，只有方法
  prompt/schema 不同。
- 两个 prompt/schema 与上一阶段已经冻结的版本逐字节相同，未按本实验结果调参。

## 目录导航

- `data/`：候选池、20+20 选择、配对、排除原因和独立性审计。
- `ground-truth/`：预测前审计表以及每 case 的 source diff、H0、静态调用路径和
  S0/S1 build/run 证据。
- `frozen-ground-truth/`：不可变 labels、hash manifest 和冻结后 invalidations。
- `frozen-inputs/`：40 个 neutral-ID blind inputs 与逐文件 hash。
- `prompts/`：两种方法的冻结 prompt 和 JSON schema。
- `predictions/`：原始模型输出、完整 model input/output pair、stderr/stdout 和
  run/prediction freeze manifests。
- `results/`：逐 case outcome、confusion matrix、N4/attribution/matched-pair 指标。
- `reports/`：数据构造、GT、主结果、FP/FN 和 go/no-go 分析。

## 执行顺序

在干净副本中按以下顺序执行；freeze 脚本会拒绝覆盖既有冻结产物：

```text
mine_candidates.py
select_cases.py
audit_ground_truth.py
freeze_ground_truth_inputs_config.py
run_gap_only.py
run_evolution_aware.py
freeze_predictions.py
post_freeze_audit.py
evaluate.py
validate_artifact.py
```

依赖为 Python 3、NumPy/SciPy、git、gcc/g++、Codex CLI 0.145.0，以及本 workspace
中的 Wuffs repository mirror。重新调用模型会产生新的随机服务输出，因此当前
`predictions/` 才是本次正式 one-shot run。
