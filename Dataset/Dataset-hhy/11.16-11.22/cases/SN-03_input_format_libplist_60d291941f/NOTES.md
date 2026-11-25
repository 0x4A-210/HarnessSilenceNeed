# SN-03 — libplist @ 60d291941fad

- label: **positive** / silent / type `input_format` / introduced_by_this_change = true
- change: Add support for OpenStep plist format (2023-01-08)
- M: `60d291941fadb72b66d11502710add5899e21a2d`
- M^1: `3f9360e33c13c22648036da42e36f8668e29fb60`
- H: `79f7772097edd3a28984398d073e92d27e345452`
- H^1: `f59601ac2becf03e3f97727a5e20086150fb3c97`
- source: `input/source/` = 248 files; `change.diff` = M^1→M

## 变更文件索引

本次变更涉及 18 个文件：

- `docs/plistutil.1`
- `include/plist/plist.h`
- `src/Makefile.am`
- `src/oplist.c`
- `src/plist.c`
- `test/Makefile.am`
- `test/data/o1.ostep`
- `test/data/o2.ostep`
- `test/data/o3.ostep`
- `test/data/test.strings`
- `test/ostep-comments.test`
- `test/ostep-invalid-types.test`
- 其余 6 个文件见 `input/change.diff`。

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `oplist_fuzzer`
- 修复 patch: `_evidence/SN-03_input_format_libplist_60d291941f/fix.diff`
- 原始运行/构建日志: `_evidence/SN-03_input_format_libplist_60d291941f/recheck_2026-11-19/`
- 静态核对: `_evidence/SN-03_input_format_libplist_60d291941f/static_checks.json`

## 理由

libplist M 新增 OpenStep plist 格式解析；旧 build.sh 没有 oplist_fuzzer，新格式无法被 fuzz 到；H 把 oplist_fuzzer 加入构建。

## Rationale

libplist M adds OpenStep plist parsing; the old build.sh has no oplist_fuzzer, so the new format is unreachable. H adds oplist_fuzzer to the build.

## Verification summary

| 组合 | 结果 | 错误 |
|---|---|---|
| h(M^1) x lib(M^1) | ok | — |
| h(M^1) x lib(M) | ok | — |
| h(fix) x lib(M) | ok | — |

```json
{"verdict": "PASS_PARTIAL", "M": "60d291941fadb72b66d11502710add5899e21a2d", "H": "79f7772097edd3a28984398d073e92d27e345452"}
```

- [PASS] H patch exists and touches the harness — 79f7772097edd3a28984398d073e92d27e345452
- [PASS] H patch contains the expected new call/path — oplist_fuzzer
- [PASS] M diff exists — 60d291941fadb72b66d11502710add5899e21a2d
- [PASS] M source tree is complete — 248 files
- [PASS] harness files fetched at H^1 — 1 files
- [PASS] fixed oplist_fuzzer builds and runs on seed — oplist.c:827 hit 1, exit 0

## 讲解

### 1. 库改了什么

- **input_format_target**：M adds the OpenStep plist parser, but the old build.sh only builds bplist/xplist fuzzers; the new format is never fed to a target.

### 2. 原来的 harness 为什么不够

旧 harness 是 H^1 的 `oplist_fuzzer`，没有针对 M 的新接口/新格式/新状态做适配。

### 3. 修复怎么做的

H（`79f7772097ed`）按新契约修改了 harness；`_evidence/SN-03_input_format_libplist_60d291941f/fix.diff` 是完整 patch。

### 4. 证据是怎么来的

构建/运行日志与 gcov 在 `_evidence/SN-03_input_format_libplist_60d291941f/recheck_2026-11-19/`；没有跑的部分在 `verification` 中如实标为 `partial`/`static_expected`，没有伪造 PASS。

### 5. 为什么是这个标签

libplist M 新增 OpenStep plist 格式解析；旧 build.sh 没有 oplist_fuzzer，新格式无法被 fuzz 到；H 把 oplist_fuzzer 加入构建。
