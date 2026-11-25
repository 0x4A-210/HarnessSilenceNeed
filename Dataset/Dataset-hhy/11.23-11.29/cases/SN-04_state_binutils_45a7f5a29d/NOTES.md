# SN-04 — binutils @ 45a7f5a29de7

- label: **positive** / silent / type `state` / introduced_by_this_change = true
- change: dlltool leading_underscore (2024-10-02)
- M: `45a7f5a29de78755dd0d5e8f7beaf2bd07736d20`
- M^1: `d2ea1a941173223907ef8a91d674af3417ba9dbc`
- H: `9af538448e597768723f17d44dcb67d0f9498d15`
- H^1: `9905549cb14269aac9880913a6139937135c489d`
- source: `input/source/` = 28449 files（**binutils 2.44 release 树** `6cf91d2b68`，包含 M）；`change.diff` = M^1→M
- M^1 精确源码未打包：baseline 用 binutils 2.43.1 release（`ddf04874`，M 之前的祖先版本）

## 变更文件索引

本次变更涉及 1 个文件：

- `binutils/dlltool.c`

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `fuzz_dlltool`
- 修复 patch: `_evidence/SN-04_state_binutils_45a7f5a29d/fix.diff`
- 原始运行/构建日志: `_evidence/SN-04_state_binutils_45a7f5a29d/recheck_2026-11-19/`
- 静态核对: `_evidence/SN-04_state_binutils_45a7f5a29d/static_checks.json`

## 理由

binutils M (`dlltool leading_underscore`) 改变 dlltool 的 leading_underscore 类型/默认值，并引入新的 dll_name_set_by_exp_name 状态；旧 fuzz_dlltool 没有重置这些全局状态；H 更新 init_dlltool_global_state。

## Rationale

binutils M ('dlltool leading_underscore') changes the leading_underscore type/default and dll_name_set_by_exp_name state; the old fuzz_dlltool does not reset them. H updates init_dlltool_global_state.

## Verification summary

| 组合 | 结果 | 错误 |
|---|---|---|
| binutils 2.43.1 baseline (pre-M) x lib(2.43.1) | ok | — |
| h(M^1) x lib(M) | ok | — |
| h(fix) x lib(M) | ok | — |

```json
{"verdict": "PASS", "M": "45a7f5a29de78755dd0d5e8f7beaf2bd07736d20", "H": "9af538448e597768723f17d44dcb67d0f9498d15"}
```

- [PASS] H patch exists and touches the harness — 9af538448e597768723f17d44dcb67d0f9498d15
- [PASS] H patch contains the expected new call/path — leading_underscore = "_"
- [PASS] M diff exists — 45a7f5a29de78755dd0d5e8f7beaf2bd07736d20
- [PASS] source tree is complete — 28449 files (binutils 2.44 release, contains M)
- [PASS] harness files fetched at H^1 — 15 files
- [PASS] old and fixed fuzz_dlltool build/run on two .def inputs — recheck_2026-11-19/old_ab.log / fixed_ab.log exit 0

## 源码树说明

`input/source/` 是完整的 binutils 2.44 release 源码树（28449 个文件），它包含 M 提交；`input/change.diff` 是 M^1→M 的精确 diff。baseline 使用 2.43.1 release（M 之前的祖先版本）。没有只放一段源码。

## 讲解

### 1. 库改了什么

- **global_state_reset**：M changes dlltool leading_underscore from int to char* and updates dll_name_set_by_exp_name/identify_strict; the old fuzzer does not reset the new state between inputs.

### 2. 原来的 harness 为什么不够

旧 harness 是 H^1 的 `fuzz_dlltool`，没有针对 M 的新接口/新格式/新状态做适配。

### 3. 修复怎么做的

H（`9af538448e59`）按新契约修改了 harness；`_evidence/SN-04_state_binutils_45a7f5a29d/fix.diff` 是完整 patch。

### 4. 证据是怎么来的

构建/运行日志与 gcov 在 `_evidence/SN-04_state_binutils_45a7f5a29d/recheck_2026-11-19/`；证据为旧/修复 `fuzz_dlltool` 在 binutils 2.44 上的真实构建/运行日志；state 重置差异是 M diff + H patch 的确定性代码事实（静态证据，已注明）。

### 5. 为什么是这个标签

binutils M (`dlltool leading_underscore`) 改变 dlltool 的 leading_underscore 类型/默认值，并引入新的 dll_name_set_by_exp_name 状态；旧 fuzz_dlltool 没有重置这些全局状态；H 更新 init_dlltool_global_state。
