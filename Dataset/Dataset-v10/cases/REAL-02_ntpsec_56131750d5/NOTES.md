# REAL-02 — ntpsec @ 56131750d5

- label: **positive** / explicit / type `api` / introduced_by_this_change = True
- change: M = `32a950f65`（2026-03-25，`nts now works with pool`），已用 `.patch` 验证
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: oss ['projects/ntpsec/fuzz/setup.c', 'projects/ntpsec/fuzz/FuzzServer.c', 'projects/ntpsec/fuzz/Makefile'] (target `FuzzServer`)
- fix H: https://github.com/google/oss-fuzz/commit/56131750d5491fafee3914bf8b855ab5868eddd5 (ntpsec: fix build #15303)

## 理由

M 让库**第一次引用** `dns_take_pool`：`ntpd/nts_client.c` 的 `nts_check()` 新增 `if (peer->cast_flags & MDF_POOL)` 分支，在 NTS + pool 场景下调用 `dns_take_pool(peer, &sockaddr)`；同时 `include/ntp_dns.h` 的 `DNS_Status` 枚举新增 `DNS_NTS_pool`。

harness 的 `setup.c` 是专门用来提供 daemon 符号 stub、避免链接 `libntpd_lib.a` 的，它的 stub 集合只有 `dns_take_server` 和 `dns_take_status`，**没有跟上这次新引用**，于是链接阶段报 `dns_take_pool` 未定义。

修复 H 只做一件事：在 `setup.c` 里补上 `dns_take_pool` 的声明与空实现（+7 行），构建恢复。

## Rationale

M makes the library reference `dns_take_pool` for the first time: `nts_check()` in `ntpd/nts_client.c` gains an `MDF_POOL` branch calling it for NTS pools, and `include/ntp_dns.h` adds `DNS_NTS_pool` to the enum. The harness `setup.c` exists to stub daemon symbols so the link does not pull in `libntpd_lib.a`; its stub set covers only `dns_take_server` and `dns_take_status`, so it misses the new reference and the link fails. Fix H adds the declaration plus an empty definition (7 lines) and the build recovers.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "fail (link: undefined reference to dns_take_pool)",
  "h(fix) x lib(M)": "ok (stub added)"
 },
 "explicit_signal": "link_failure",
 "verdict": "PASS"
}
```

## 讲解

### 1. 库改了什么（input/change.diff）

`ntpd/nts_client.c` 的 `nts_check()`：

```diff
 	if (addrOK) {
-		dns_take_server(peer, &sockaddr);
-		dns_take_status(peer, DNS_good);
+		if (peer->cast_flags & MDF_POOL) {
+			dns_take_pool(peer, &sockaddr);
+			dns_take_status(peer, DNS_NTS_pool);
+		} else {
+			dns_take_server(peer, &sockaddr);
+			dns_take_status(peer, DNS_good);
+		}
```

`include/ntp_dns.h`：

```diff
-typedef enum {DNS_good, DNS_temp, DNS_error} DNS_Status;
+typedef enum {DNS_good, DNS_NTS_pool, DNS_temp, DNS_error} DNS_Status;
```

**注意一个容易看错的地方**：`dns_take_pool` 这个函数**不是 M 新增的**。M 的 diff 里它的 hunk header（`@@ ... dns_take_pool(`）是**上下文**，说明函数体在 M 之前就存在。M 做的是**让 `nts_client.c` 第一次调用它**，此前它没有调用者。

### 2. 原来的 harness（input/harness/oss-fuzz/）

`setup.c`（取自 oss-fuzz rev `aa7bc69268b9`）：

```c
void dns_take_server(struct peer *a, sockaddr_u *b);
void dns_take_status(struct peer *a, DNS_Status b);
// ← 没有 dns_take_pool
```

实测该文件里 `dns_take_pool` 出现次数为 **0**。

### 3. 为什么 harness 出问题

`setup.c` 的职责就是为 fuzzer 提供 daemon 侧符号的空实现，让链接不必拉进 `libntpd_lib.a` 的一堆依赖。库开始引用一个新符号后，这份 stub 清单没更新，链接就断在 `undefined reference to dns_take_pool`。

### 4. 怎么修（H = 56131750d5）

只在 `setup.c` 追加 7 行：

```c
+void dns_take_pool(struct peer *a, sockaddr_u *b);
...
+void dns_take_pool(struct peer *a, sockaddr_u *b) {
+	UNUSED_ARG(a);
+	UNUSED_ARG(b);
+	return;
+}
```

### 5. 为什么是这个标签

- **阳性**：不改 harness 链接不过。
- **显式**：链接失败，一眼可见。
- **本次引入**：M（2026-03-25）引入新引用，H（2026-04-05）修复，因果顺序正确。
- **api**：单一缺失符号，**不涉及签名变更，也不涉及链接顺序**。

## 与 REAL-05 的关系

这两条都落在同一个 harness 文件 `setup.c` 上，但**是完全独立的两次断裂**：

| | REAL-02（本条） | REAL-05 |
|---|---|---|
| M | `32a950f65`（2026-03-25） | `ecc1b5ef974d`（2026-04-22） |
| H | `56131750d`（2026-04-05） | `a70f55cc2b`（2026-06-15） |
| 类型 | api（缺符号） | mix（api + configuration） |
| 断裂点 | `dns_take_pool` 未定义 | `nts_ke_process_receive` 参数 2→5 + 链接顺序 |

版本链可以印证先后关系：

```
2c51f843a458  ← H 56131750d 的基线（只有 dns_take_server/status）
7774c434af50  ← H 56131750d 产出（加 dns_take_pool）  ← 也是 H a70f55cc2b 的基线
79fe17233128  ← H a70f55cc2b 产出（再加 record_ntske_log）
```

本条的 `h(M^1)` 是 `2c51f843a458` 之前的版本；而 `a70f55cc2b` 的 diff 里 `dns_take_pool` 已作为**上下文行**出现，说明它继承了本条的修复结果。

## 备注

- **已实测三格**（WSL，gcc 15.2.0）：用最小复现验证，做法是以精简 `ntpd.h` + 真实 `ntp_dns.h` 提供 `sockaddr_u` 与 `struct peer`，用 `caller.c` 精确模拟 M 之后 `ntpd/nts_client.c::nts_check()` 对 `dns_take_pool` 的引用：

  | 格 | 结果 | 耗时 |
  |----|------|------|
  | h(M^1) × lib(M^1) | ok | 0.093s |
  | h(M^1) × lib(M) | **fail**：`undefined reference to dns_take_pool` | 0.084s |
  | h(fix) × lib(M) | ok | 0.088s |

  未跑 ntpsec 全量 waf 构建（OSS-Fuzz 的 Makefile 依赖 waf + openssl + libaes_siv，成本远高于本复现）。
- **本条替换了旧版 REAL-02**（旧版 M=`ecc1b5ef974d` / H=`a70f55cc2b85`，讲的是 `nts_ke_process_receive` 签名变更）。旧版覆盖的签名变更主题现在由 REAL-05 承载。
- 旧版 `M_parent` 已填完整哈希，本条的 `M_parent` 未单独验证，标为 `n/a`。
