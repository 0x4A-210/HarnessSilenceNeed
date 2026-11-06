# False Positive Analysis

正式结果中共有 6 个 FP：3 个 matched negative、3 个 hard negative；easy negative 为 0 个 FP。所有 FP 的 evidence 都能在 H0 或 source diff 中直接找到，但中心推论跨过了冻结 negative label 所采用的 harness 职责边界。

## 逐例审计

| Case | Project / commit | Stratum | Category | 为什么模型判 YES | 为什么按冻结标签是 FP | Label ambiguity |
|---|---|---|---|---|---|---|
| C018 | jansson `78418c84f162` | matched | FP-4 | H0 不调用改动的 update/equality/copy/unpack APIs，模型把 length-aware key handling 看成新输入语义 | commit 在既有实现中复用已存 key length，未新增入口、状态或调用协议；要求 load/dump target 顺便覆盖其他 API 是扩大 scope | low |
| C021 | wuffs `55aedb34f9f4` | matched | FP-4 | 私有 GIF copy 函数从 8/16/24/32 bpp 判断改为任意 byte-aligned `<=512`，模型推断新 pixel-format 空间 | 改动是 private bytes-per-pixel 计算简化；H0 已经通过 decoder 到达该函数，case 中没有新 public mode 或 caller setup 的证据 | low |
| C022 | jansson `63fb81faa55e` | hard | FP-3 | `json_deep_copy` 新增 parents-set loop check，而 parser 无法从 serialized JSON 创建 cycle | API 签名和调用前置条件未变；这是既有 API 的内部错误处理，不要求当前 load/dump target 同步改变 | medium |
| C025 | jansson `00d2d274bc42` | hard | FP-3 | `json_object_update_recursive` 新增 loop tracking，H0 不构造 cyclic graphs | 与 C022 相同：内部防环状态不是 caller 必须提供的新初始化/state protocol | medium |
| C054 | leptonica `022ab9bd6c02` | matched | FP-2 | TIFF decoder 新接受 `tiffbpl` 约为 `packedbpl` 的 2/3，而现有目标只读取 SPIX | 冻结标签把它视为 H0 当前 SPIX/barcode scope 之外的既有 codec 局部 validation change，不是 H0 调用/setup 退化 | high |
| C075 | libplist `810e1a593686` | hard | FP-1 | 新增 `PLIST_NULL`、constructor 和 writer behavior，而 H0 不调用 writer | 回答已承认 `plist_from_bin` 能到达新的 NULL parsing；它因未覆盖 constructor/writer 才建议扩展，未指出现有 parser 路径的 barrier | medium |

## 主要错误模式

### 1. “changed code 未覆盖”被等同于“现有 H0 必须维护”

C018、C022、C025 和 C075 都正确指出 H0 没有调用某些 API，但一个面向 parsing/load-dump 的 fuzz target 不需要因库内每个既有 programmatic API 的实现修正而同步扩展。否则几乎任何未覆盖函数的 commit 都会成为 positive，maintenance need 将退化为 generic coverage gap。

### 2. 没有区分 internal state 与 caller-visible state requirement

C022、C025 中的 parents set 是函数内部实现。真正的 P2/P3 positive 应有 caller 需要新增 `create/configure/initialize/attach` 等步骤，或者旧调用在新状态机上提前返回；这两个 case 没有这种变化。

### 3. 没有稳定识别 harness 的目标边界

C054 是最明显的定义边界：从项目级安全覆盖角度，新接受的 TIFF input class 确实值得 fuzz；从“这次 commit 是否使 SPIX/barcode H0 不再适配其原目标”角度，则不需要修改 H0。冻结 mapping 采用后一口径。后续必须在不查看 8 个 hold-out 标签的前提下预注册 scope 规则。

### 4. 高 confidence 未能表达边界不确定性

6 个 FP 的 confidence 范围为 92–97。模型对代码事实很确信，也对规范性结论同样确信；当前 confidence 没有校准“事实证据”和“维护职责边界”这两种不确定性。

## 对下一阶段的直接含义

- Prompt 或 adjudication protocol 要明确区分：`new externally consumable attack surface`、`existing H0 path 被阻断/漏配`、`unrelated existing API remains uncovered`。
- 给出 H0 的 target intent 或 entry-point scope，避免模型自行假定 harness 必须覆盖整个项目。
- 对 YES 要求一条具体反事实：说明 `S1+H0` 中哪条 changed path 因哪个缺失的 input/state/config/API action 而不可达；只说“H0 没调用函数 X”不够。
- 使用 dynamic reachability/changed-code coverage 仲裁 C054 这类高争议样本。
- 本阶段不得事后重标或重跑。上述分析只用于下一阶段预注册方案。
