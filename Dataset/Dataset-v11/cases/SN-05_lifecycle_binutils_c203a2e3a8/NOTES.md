# SN-05 — binutils @ ba64682044d3

- label: **positive** / explicit / type `lifecycle` / introduced_by_this_change = true
- change: gas: Add --gcodeview option (2022-11-23)
- M: `ba64682044d3828909fd5356f0282abaaefa6425`
- M^1: `e2a1b0a0d1bf0e9282e4902b2a2b2e75400104b4`
- H: `db7354e3d31cd9052c0d8dd0b961c862fbb2e889`
- H^1: `cc655c2129de3428c3dc2e6ac6f49e73a89088e7`
- source: `input/source/` = 26930 files; `change.diff` = M^1→M

## 变更文件索引

本次变更涉及 4 个文件：

- `gas/as.c`
- `gas/as.h`
- `gas/output-file.c`
- `gas/output-file.h`

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `fuzz_as`
- 修复 patch: `_evidence/SN-05_lifecycle_binutils_c203a2e3a8/fix.diff`
- 原始运行/构建日志: `_evidence/SN-05_lifecycle_binutils_c203a2e3a8/recheck_2026-11-19/`
- 静态核对: `_evidence/SN-05_lifecycle_binutils_c203a2e3a8/static_checks.json`

## 理由

binutils M (`gas: Add --gcodeview option`) 引入 codeview 相关状态和销毁流程；旧 fuzz_as 缺少 codeview_finish/输出清理等新生命周期调用，在 M 上运行会 SIGSEGV；H 按新流程补齐初始化和销毁。

## Rationale

binutils M ('gas: Add --gcodeview option') adds codeview state/teardown; the old fuzz_as lacks codeview_finish/output cleanup and crashes (SIGSEGV) at M. H adds the new init/cleanup flow.

## Verification summary

| 组合 | 结果 | 错误 |
|---|---|---|
| h(M^1) x lib(M^1) | ok | — |
| h(M^1) x lib(M) | ok | runtime SIGSEGV (exit 139) on seed.s |
| h(fix) x lib(M) | ok | — |

```json
{"verdict": "PASS_PARTIAL", "M": "ba64682044d3828909fd5356f0282abaaefa6425", "H": "db7354e3d31cd9052c0d8dd0b961c862fbb2e889"}
```

- [PASS] H patch exists and touches the harness — db7354e3d31cd9052c0d8dd0b961c862fbb2e889
- [PASS] H patch contains the expected new call/path — output_file_close
- [PASS] M diff exists — 07e64e0b7c6cd4a73220eb57588d0db6b2a192e3
- [PASS] M source tree is complete — 37697 files
- [PASS] harness files fetched at H^1 — 15 files
- [PASS] old fuzz_as vs M crashes on seed — exit 139; recheck_2026-11-19/as_old_run.log
- [PASS] fixed fuzz_as vs M runs seed — exit 0; recheck_2026-11-19/as_fixed_run.log

## 讲解

### 1. 库改了什么

- **init_order**：M changes gas output/cleanup flow (output_file_close and related init); the old fuzz_as does not call the new init/cleanup sequence.

### 2. 原来的 harness 为什么不够

旧 harness 是 H^1 的 `fuzz_as`，没有针对 M 的新接口/新格式/新状态做适配。

### 3. 修复怎么做的

H（`db7354e3d31c`）按新契约修改了 harness；`_evidence/SN-05_lifecycle_binutils_c203a2e3a8/fix.diff` 是完整 patch。

### 4. 证据是怎么来的

构建/运行日志与 gcov 在 `_evidence/SN-05_lifecycle_binutils_c203a2e3a8/recheck_2026-11-19/`；没有跑的部分在 `verification` 中如实标为 `partial`/`static_expected`，没有伪造 PASS。

### 5. 为什么是这个标签

binutils M (`gas: Add --gcodeview option`) 引入 codeview 相关状态和销毁流程；旧 fuzz_as 缺少 codeview_finish/输出清理等新生命周期调用，在 M 上运行会 SIGSEGV；H 按新流程补齐初始化和销毁。
