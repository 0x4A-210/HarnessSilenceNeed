# SN-05 — binutils @ ba64682044d3

- label: **positive** / explicit / type `lifecycle` / introduced_by_this_change = true
- change: gas: Add --gcodeview option (2022-11-23)
- M: `ba64682044d3828909fd5356f0282abaaefa6425`
- M^1: `e2a1b0a0d1bf0e9282e4902b2a2b2e75400104b4`
- H: `db7354e3d31cd9052c0d8dd0b961c862fbb2e889`
- H^1: `cc655c2129de3428c3dc2e6ac6f49e73a89088e7`
- source: `input/source/` = 26930 files（**binutils 2.40 release 树** `c203a2e3a8`，包含 M）；`change.diff` = M^1→M
- M^1 精确源码未打包：baseline 用 binutils 2.39 release（`749caa2c`，M 之前的祖先版本）

## 变更文件索引

本次变更涉及 11 个文件：

- `gas/Makefile.am`
- `gas/Makefile.in`
- `gas/as.c`
- `gas/as.h`
- `gas/codeview.c`
- `gas/codeview.h`
- `gas/read.c`
- `gas/testsuite/gas/i386/codeview-lines.d`
- `gas/testsuite/gas/i386/codeview.exp`
- `gas/testsuite/gas/i386/codeview1.s`
- `gas/testsuite/gas/i386/codeview2.s`

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `fuzz_as`
- 修复 patch: `_evidence/SN-05_lifecycle_binutils_ba64682044/fix.diff`
- 原始运行/构建日志: `_evidence/SN-05_lifecycle_binutils_ba64682044/recheck_2026-11-19/`
- 静态核对: `_evidence/SN-05_lifecycle_binutils_ba64682044/static_checks.json`

## 理由

binutils M (`gas: Add --gcodeview option`) 引入 codeview 相关状态和销毁流程；旧 fuzz_as 缺少 codeview_finish/输出清理等新生命周期调用，在 M 上运行会 SIGSEGV；H 按新流程补齐初始化和销毁。

## Rationale

binutils M ('gas: Add --gcodeview option') adds codeview state/teardown; the old fuzz_as lacks codeview_finish/output cleanup and crashes (SIGSEGV) at M. H adds the new init/cleanup flow.

## Verification summary

| 组合 | 结果 | 错误 |
|---|---|---|
| binutils 2.39 baseline (pre-M) x lib(2.39) | ok | — |
| h(M^1) x lib(M) | ok | runtime SIGSEGV (exit 139) on seed.s |
| h(fix) x lib(M) | ok | — |

```json
{"verdict": "PASS", "M": "ba64682044d3828909fd5356f0282abaaefa6425", "H": "db7354e3d31cd9052c0d8dd0b961c862fbb2e889"}
```

- [PASS] H patch exists and touches the harness — db7354e3d31cd9052c0d8dd0b961c862fbb2e889
- [PASS] H patch contains the expected new call/path — codeview_finish（另有 output_file_close/free_notes）
- [PASS] M diff exists — ba64682044d3828909fd5356f0282abaaefa6425
- [PASS] source tree is complete — 26930 files (binutils 2.40 release, contains M)
- [PASS] harness files fetched at H^1 — 15 files
- [PASS] old fuzz_as vs M crashes on seed — exit 139; recheck_2026-11-19/as_old_run.log
- [PASS] fixed fuzz_as vs M runs seed — exit 0; recheck_2026-11-19/as_fixed_run.log

## 源码树说明

`input/source/` 是完整的 binutils 2.40 release 源码树（26930 个文件），它包含 M 提交；`input/change.diff` 是 M^1→M 的精确 diff。baseline 使用 2.39 release（M 之前的祖先版本）。没有只放一段源码。

## 讲解

### 1. 库改了什么

- **init_order**：M 引入 gas codeview 状态（`--gcodeview`，`gas/codeview.c`，`gas/codeview.h` 声明 `codeview_finish()`）；旧 `fuzz_as` 既不调用 `codeview_finish()`，也不走 `output_file_close()`/`free_notes()` 清理，在 M 上运行会 SIGSEGV；H 补齐 codeview_finish 等 init/cleanup。

### 2. 原来的 harness 为什么不够

旧 harness 是 H^1 的 `fuzz_as`，没有针对 M 的新接口/新格式/新状态做适配。

### 3. 修复怎么做的

H（`db7354e3d31c`）按新契约修改了 harness；`_evidence/SN-05_lifecycle_binutils_ba64682044/fix.diff` 是完整 patch。

### 4. 证据是怎么来的

构建/运行日志与 gcov 在 `_evidence/SN-05_lifecycle_binutils_ba64682044/recheck_2026-11-19/`；证据为旧 `fuzz_as` 在 binutils 2.40 上 SIGSEGV（exit 139）、修复版 exit 0 的真实日志。

### 5. 为什么是这个标签

binutils M (`gas: Add --gcodeview option`) 引入 codeview 相关状态和销毁流程；旧 fuzz_as 缺少 codeview_finish/输出清理等新生命周期调用，在 M 上运行会 SIGSEGV；H 按新流程补齐初始化和销毁。
