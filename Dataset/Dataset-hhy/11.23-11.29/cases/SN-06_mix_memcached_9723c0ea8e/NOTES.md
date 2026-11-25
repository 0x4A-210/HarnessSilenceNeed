# SN-06 — memcached 1.6.21 → 1.6.22

- label: **positive** / explicit / type `mix`（api + configuration）/ introduced_by_this_change = true
- change: **1.6.21 → 1.6.22 release diff**（40 个文件）
- M: `9723c0ea8ec1237b8364410ba982af8ea020a2b6`（git tag `1.6.22` 指向的提交）
- base / M_parent: `efee763c93249358ea5b3b42c7fd4e57e2599c30`（git tag `1.6.21` 指向的提交）
- H: `e75a15b717ea9a224ab289a9324539953389ab0d`
- H^1: `76e8fc8df0d28316fb73243c9cdfc99af337347f`
- source: `input/source/` = 273 files，与 1.6.22 tag 提交的 git tree **逐 blob 一致（0 mismatch）**；`change.diff` = 1.6.21→1.6.22 的 git 格式 diff

> 说明：这一条是**发布级（release-to-release）**样本。1.6.22 对 harness 的影响由两个提交/改动共同造成：
> `proxy_init()` 新增 `bool proxy_memprofile` 参数（api），以及新增 `proxy_ratelim.c` 需要被编进
> `fuzzer_proxy`（configuration）。因此 M 取 1.6.22 tag 提交、M_parent 取 1.6.21 tag 提交，
> `change.diff` 是两个 release 之间的完整 diff，而不是单提交 diff。这是本数据集中唯一一条发布级样本，
> 其余五条都是单提交 M^1→M。

## 变更文件索引（40 个）

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
- `proxy.h`
- `proxy_config.c`
- `proxy_internal.c`
- `proxy_lua.c`
- `proxy_network.c`
- `proxy_ratelim.c`
- `proxy_request.c`
- `proxy_ustats.c`
- `storage.c`
- `t/flags.t`
- `t/metaget.t`
- `t/proxyantiflap.lua`
- `t/proxyantiflap.t`
- `t/proxyconfig.lua`
- `t/proxyconfig.t`
- `t/proxyinternal.t`
- `t/proxylimits.t`
- `t/proxyratelim.lua`
- `t/proxyratelim.t`
- `t/proxyunits.lua`
- `t/proxyunits.t`
- `t/proxyustats.lua`
- `t/proxyustats.t`
- `testapp.c`
- `thread.c`
- `util.c`
- `vendor/Makefile`

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `fuzzer_proxy`
- 修复 patch: `_evidence/SN-06_mix_memcached_9723c0ea8e/fix.diff`
- 原始运行/构建日志: `_evidence/SN-06_mix_memcached_9723c0ea8e/recheck_2026-11-19/`

## 理由

memcached 1.6.22 把 `proxy_init(bool)` 改成 `proxy_init(bool, bool)`（新增 proxy_memprofile），并新增
`proxy_ratelim.c`；旧 `fuzzer_proxy` 既按旧签名调用（`too few arguments`），也没有链接新目标文件，
在 1.6.22 上编译失败。H 同时补上 `memcached-proxy_ratelim.o` 和 `proxy_init(false, false)`，两处都必须修。

## Rationale

memcached 1.6.22 changes `proxy_init(bool)` to `proxy_init(bool, bool)` and adds `proxy_ratelim.c`.
The old `fuzzer_proxy` both calls the old signature (`too few arguments`) and fails to link the new object;
it does not build against 1.6.22. H fixes both: adds `memcached-proxy_ratelim.o` and calls `proxy_init(false, false)`.

## Verification summary

| 组合 | 结果 | 说明 |
|---|---|---|
| 旧 harness x 1.6.22 | fail | `too few arguments to function 'proxy_init'`；`proxy_ratelim` 未链接 |
| 修复 harness x 1.6.22 | ok | H 修复版编译通过 |

```json
{"verdict": "PASS", "M": "9723c0ea8ec1237b8364410ba982af8ea020a2b6", "H": "e75a15b717ea9a224ab289a9324539953389ab0d"}
```

- [PASS] change.diff 是 1.6.21→1.6.22 release diff（40 files，git 格式）
- [PASS] H patch 同时修了 build.sh（proxy_ratelim.o）和 fuzzer_proxy.c（proxy_init 参数）
- [PASS] input/source 与 1.6.22 tag tree 逐 blob 一致（273 files，0 mismatch）
- [PASS] 旧 harness 在 1.6.22 上编译失败
- [PASS] H 修复版在 1.6.22 上编译通过

## 讲解

### 1. 库改了什么

1.6.22 相对 1.6.21 修改了 `proto_proxy.h` 中 `proxy_init` 的签名：

```c
// 1.6.21
void *proxy_init(bool proxy_uring);
// 1.6.22
void *proxy_init(bool proxy_uring, bool proxy_memprofile);
```

同时 `Makefile.am` 新增 `proxy_ratelim.c`，1.6.22 release 需要把它一起编进 `fuzzer_proxy`。

### 2. 原来的 harness（`input/harness/oss-fuzz/`）

`fuzzer_proxy.c` 调用 `proxy_init(false)`；`build.sh` 的链接命令里没有 `memcached-proxy_ratelim.o`。

### 3. 为什么 harness 出问题了

在 1.6.22 上，`proxy_init(false)` 少一个参数，编译报 `too few arguments`；即使补了参数，链接还会缺
`proxy_ratelim` 的目标文件。两处都属于本次 release 引入的失配。

### 4. 怎么修（`fix.diff`）

H（e75a15b717ea）在 `build.sh` 加 `memcached-proxy_ratelim.o`，在 `fuzzer_proxy.c` 改成 `proxy_init(false, false)`。

### 5. 为什么是这个标签

- **阳性**：不改 harness 无法构建。
- **显式**：编译期直接失败。
- **本次引入**：1.6.21 上旧 harness 正常。
- **mix**：同时涉及 api（签名）和 configuration（新增目标文件），且两处都必须修。
