# SN-01 — haproxy @ 5b52df4c4d05

- label: **positive** / explicit / type `api` / introduced_by_this_change = true
- change: MEDIUM: startup: load and parse configs from memory (2024-08-07)
- M: `5b52df4c4d05ddcbcfdec9792520d2495614547c`
- M^1: `2bb34edb0b17040d6bfc40715f94b7f434c0fdd9`
- H: `9fa746636837745f877706bc97e8878b9ad581e6`
- H^1: `01d256abe4bca19b58de4b6959ca7fc7ad3ae4e1`
- source: `input/source/` = 1260 files; `change.diff` = M^1→M

## 变更文件索引

本次变更涉及 5 个文件：

- `addons/ot/src/parser.c`
- `include/haproxy/cfgparse.h`
- `src/cfgparse.c`
- `src/flt_spoe.c`
- `src/haproxy.c`

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `fuzz_cfg_parser`
- 修复 patch: `_evidence/SN-01_api_haproxy_5b52df4c4d/fix.diff`
- 原始运行/构建日志: `_evidence/SN-01_api_haproxy_5b52df4c4d/recheck_2026-11-19/`
- 静态核对: `_evidence/SN-01_api_haproxy_5b52df4c4d/static_checks.json`

## 理由

HAProxy M 把配置读取改成基于内存的 parse_cfg(struct cfgfile *)，旧 fuzzer 仍调用 readcfgfile(filename)，编译失败；H 改成构造 cfgfile 并调用 parse_cfg。

## Rationale

HAProxy M replaces readcfgfile(filename) with parse_cfg(struct cfgfile *); the old fuzzer still calls readcfgfile(). H constructs a cfgfile and calls parse_cfg.

## Verification summary

| 组合 | 结果 | 错误 |
|---|---|---|
| h(M^1) x lib(M^1) | ok | — |
| h(M^1) x lib(M) | fail | undefined reference to readcfgfile |
| h(fix) x lib(M) | ok | — |

```json
{"verdict": "PASS_PARTIAL", "M": "5b52df4c4d05ddcbcfdec9792520d2495614547c", "H": "9fa746636837745f877706bc97e8878b9ad581e6"}
```

- [PASS] H patch exists and touches the harness — 9fa746636837745f877706bc97e8878b9ad581e6
- [PASS] H patch contains the expected new call/path — parse_cfg
- [PASS] M diff exists — 5b52df4c4d05ddcbcfdec9792520d2495614547c
- [PASS] M source tree is complete — 1260 files
- [PASS] harness files fetched at H^1 — 2 files
- [PASS] old fuzzer vs M: link fails undefined readcfgfile — recheck_2026-11-19/old_link.log
- [PASS] fixed fuzzer vs M: link succeeds — recheck_2026-11-19/new_link.log
- [PASS] baseline haproxy 2bb34edb + old fuzzer runs — exit 0; recheck_2026-11-19/hap_m1c_run.log

## 讲解

### 1. 库改了什么

- **api_signature**：readcfgfile(filename) was replaced by parse_cfg(struct cfgfile *); the old harness still calls readcfgfile().

### 2. 原来的 harness 为什么不够

旧 harness 是 H^1 的 `fuzz_cfg_parser`，没有针对 M 的新接口/新格式/新状态做适配。

### 3. 修复怎么做的

H（`9fa746636837`）按新契约修改了 harness；`_evidence/SN-01_api_haproxy_5b52df4c4d/fix.diff` 是完整 patch。

### 4. 证据是怎么来的

构建/运行日志与 gcov 在 `_evidence/SN-01_api_haproxy_5b52df4c4d/recheck_2026-11-19/`；没有跑的部分在 `verification` 中如实标为 `partial`/`static_expected`，没有伪造 PASS。

### 5. 为什么是这个标签

HAProxy M 把配置读取改成基于内存的 parse_cfg(struct cfgfile *)，旧 fuzzer 仍调用 readcfgfile(filename)，编译失败；H 改成构造 cfgfile 并调用 parse_cfg。
