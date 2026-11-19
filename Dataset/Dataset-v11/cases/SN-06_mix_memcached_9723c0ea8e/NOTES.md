# SN-06 — memcached @ 9723c0ea8ec1

- label: **positive** / explicit / type `mix` / introduced_by_this_change = true
- change: memcached 1.6.22 release (2023-10-15)
- M: `9723c0ea8ec1237b8364410ba982af8ea020a2b6`
- M^1: `efee763c93249358ea5b3b42c7fd4e57e2599c30`
- H: `e75a15b717ea9a224ab289a9324539953389ab0d`
- H^1: `76e8fc8df0d28316fb73243c9cdfc99af337347f`
- source: `input/source/` = 273 files; `change.diff` = M^1→M

## 变更文件索引

本次变更涉及 40 个文件：

- `Makefile.am`
- `configure.ac`
- `doc/protocol.txt`
- `items.c`
- `items.h`
- `logger.c`
- `logger.h`
- `memcached.c`
- `memcached.h`
- `proto_proxy.c`
- `proto_proxy.h`
- `proto_text.c`
- 其余 28 个文件见 `input/change.diff`。

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `fuzzer_proxy`
- 修复 patch: `_evidence/SN-06_mix_memcached_9723c0ea8e/fix.diff`
- 原始运行/构建日志: `_evidence/SN-06_mix_memcached_9723c0ea8e/recheck_2026-11-19/`
- 静态核对: `_evidence/SN-06_mix_memcached_9723c0ea8e/static_checks.json`

## 理由

memcached 1.6.22 改了 proxy_init 签名并新增 proxy_ratelim.c；旧 fuzzer 既编译失败又缺少新目标文件；H 同时改调用和 build.sh，是 mix(api+configuration)。

## Rationale

memcached 1.6.22 changes proxy_init and adds proxy_ratelim.c; the old fuzzer fails to compile and link. H fixes both: mix(api+configuration).

## Verification summary

| 组合 | 结果 | 错误 |
|---|---|---|
| h(M^1) x lib(M^1) | ok | — |
| h(M^1) x lib(M) | fail | too few arguments to function proxy_init |
| h(fix) x lib(M) | ok | — |

```json
{"verdict": "PASS_PARTIAL", "M": "9723c0ea8ec1237b8364410ba982af8ea020a2b6", "H": "e75a15b717ea9a224ab289a9324539953389ab0d"}
```

- [PASS] H patch exists and touches the harness — e75a15b717ea9a224ab289a9324539953389ab0d
- [PASS] H patch contains the expected new call/path — proxy_init(false, false)
- [PASS] M diff exists — 9723c0ea8ec1237b8364410ba982af8ea020a2b6
- [PASS] M source tree is complete — 273 files
- [PASS] harness files fetched at H^1 — 1 files
- [PASS] old fuzzer vs M: proxy_init arity error — recheck_2026-11-19/st06_old.log
- [PASS] build.sh old lacks proxy_ratelim.o — static_checks.json
- [PASS] fixed fuzzer compiles against M — recheck_2026-11-19/st06_fixed.log (0 bytes = success)

## 讲解

### 1. 库改了什么

- **api_signature**：proxy_init() gained a second argument; the old fuzzer calls proxy_init(false).
- **build_source_list**：1.6.22 adds proxy_ratelim.c; the old build.sh does not link memcached-proxy_ratelim.o.

### 2. 原来的 harness 为什么不够

旧 harness 是 H^1 的 `fuzzer_proxy`，没有针对 M 的新接口/新格式/新状态做适配。

### 3. 修复怎么做的

H（`e75a15b717ea`）按新契约修改了 harness；`_evidence/SN-06_mix_memcached_9723c0ea8e/fix.diff` 是完整 patch。

### 4. 证据是怎么来的

构建/运行日志与 gcov 在 `_evidence/SN-06_mix_memcached_9723c0ea8e/recheck_2026-11-19/`；没有跑的部分在 `verification` 中如实标为 `partial`/`static_expected`，没有伪造 PASS。

### 5. 为什么是这个标签

memcached 1.6.22 改了 proxy_init 签名并新增 proxy_ratelim.c；旧 fuzzer 既编译失败又缺少新目标文件；H 同时改调用和 build.sh，是 mix(api+configuration)。
