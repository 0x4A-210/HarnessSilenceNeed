# Ground-Truth Audit

## 预测前审计

所有 40 个冻结 case 都在任何 task-4 model prediction 前完成以下检查：

1. 从真实 commit/parent 提取完整 hand-written Wuffs production diff。
2. 确认 N4 目标 declaration 在 S0/S1 均存在；positive 目标在 S0 缺失、S1 出现。
3. 扫描完整 `fuzz/c` C/C++ portfolio，确认选定 exposure/config identifier 在两侧
   都没有直接引用。
4. 确认 H0 translation unit 字节级不变，commit 未改 C/C++ harness code。
5. 在 S0+H0 和 S1+H0 各自构建并以统一种子运行。40/40 pair 全通过，即 80 次
   build/run 均成功。
6. 确认 production change 非 docs/comment/format/trivial rename。

N4 的冻结标签是 `gap_s0=YES, gap_s1=YES, commit_induced=NO,
maintenance_needed=NO`；positive 是 `NO, YES, YES, YES`。每 case 的 source diff、
declaration context、H0、portfolio grep 和 build/run JSON 都保存在
`ground-truth/evidence/<candidate_id>/`。

## 冻结与 blind-input 边界

- Ground truth frozen at: `2026-09-10T08:30:37.725376Z`
- Dataset hash: `568f19e722cd334ada649bd6b2644e2eeb309724530c55b05d8d7a7ccab6457d`
- Frozen label hash: `02d89228c5c1eff8090eede817a7e4b40a45811f74a5bf28c32dc73ca3ffb394`
- Input hash: `77bbde8eaf75105dfd159cfe3c11eea4a2bc26b1c3e556f4d9c275eb55472227`
- Prompt/config frozen at: `2026-09-10T08:30:40.289429Z`
- First prediction started at: `2026-09-10T08:32:27.864334Z`
- Prediction frozen before label reveal at: `2026-09-10T08:44:50.993034Z`

Blind input 只含 complete H0、直接 semantic fuzzlib helper、完整 changed
`std/**/*.wuffs` diff、以及统一机械选择的 S0/S1 declaration context。它不含 H1、
harness diff、label、GT evidence、coverage/reachability/build result、future action、
commit ID/time/message。Neutral `C001`–`C040` 由 prediction 前固定 hash ordering 分配，
ID 不编码标签。

## 冻结后审计

冻结后未改动 `labels.csv`；hash 校验仍与 manifest 一致。语义复审发现 4 个严重
错误，全部仅做 `INVALIDATE`：

- `N4003`：新增实质性 JPEG DHT attack surface，而 H0 根本没有 JPEG exposure。
- `N4012`：LZMA 从 retained output history 转为 caller workbuf，改变 public protocol。
- `N4013`：引入新的 XZ concatenated-stream quirk 和 gated state machine。
- `N4017`：引入新的 NIA animated input format 和 multi-frame state protocol。

这些 case 没有改标为 positive，也没有替换。冻结后统计为 4 invalidations、0 relabel、
0 replacement；有效 N4 从 20 降为 16，positive 保持 20。这一质量损失本身纳入
NO-GO 判定。

四个 invalidation 恰好都被 Evolution-Aware 判断为 positive，因此主报告同时给出
不排除它们、完全按原 frozen labels 计算的 sensitivity（N4 FPR 55%、FP reduction
45%）。主结果与 sensitivity 都为 NO-GO，避免审计排除造成结论反转。
