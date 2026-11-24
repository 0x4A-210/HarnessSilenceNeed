# REAL-24 — libevent @ 532abdbe62

- label: **positive** / **silent** / type `state` / `introduced_by_this_change = false`
- change: 无库侧变更（libevent 树固定为 `d82464a2`，2026-08-29）；OSS-Fuzz harness 自己把 socket 留在阻塞态
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: `oss` `['projects/libevent/dns_fuzzer.cc']`（target `dns_fuzzer`）
- fix H: https://github.com/google/oss-fuzz/commit/532abdbe62918a51f004a25318a7c1fb3ea60e36（2026-11-12，PR #16534）
- 带病引入: https://github.com/google/oss-fuzz/commit/7dbf92d52804f4160e28ae3eddc5d4d2511cf233（2026-05-05，PR #15465，`libevent: refine project`）

## 理由

`dns_fuzzer.cc` 用 `mode = 末字节 % 3` 分三条支路：配置解析、服务端报文解析、客户端响应解析。
服务端那条分支自己造报文：

```c
int fds[2];
if (socketpair(AF_UNIX, SOCK_DGRAM, 0, fds) == 0) {
    struct evdns_server_port *port =
        evdns_add_server_port_with_base(base, fds[0], 0, dns_server_cb, nullptr);
    if (port) {
        ...
        send(fds[1], packet.data(), packet.size(), 0);
        event_base_loop(base, EVLOOP_NONBLOCK);   // ← 卡在这里
    }
```

libevent 的读回调契约是「**非阻塞 fd** + 读到 `EAGAIN` 为止」。`evdns` 服务端口把报文交给
`evdns_server_request_respond()` 之后，会**继续 `recvfrom` 直到 `EAGAIN`**。`EVLOOP_NONBLOCK`
只约束 `epoll_wait` 不阻塞，管不到回调内部的系统调用。旧 harness 没给 `fds[0]` 设 `O_NONBLOCK`，
于是：报文被读走 → 请求被解析 → `dns_server_cb` 被调用 → 第二次 `recvfrom` 就地睡死，
`LLVMFuzzerTestOneInput` 永不返回。

H 的修复就是这一行（外加 4 行注释）：

```c
evutil_make_socket_nonblocking(fds[0]);
```

**判成 state 而不是 api/configuration/lifecycle**：缺的是 fd 的状态位（`O_NONBLOCK`），
是「把对象摆到库要求的状态」这一步没做，既不是 API 签名用错，也不是编译期宏缺失，更不是对象没释放。

## 为什么是 silent 而不是 explicit（如实说明偏差）

README 对 silent 的括号注释写的是「覆盖率掉到 0」。**本条不是那一型**，必须讲清楚：

- 单条 `mode%3==1` 输入回放，两版的 `evdns.c` 行覆盖**同为 4.38%**（`verification/covrep_old.txt` / `covrep_new.txt`）。
  原因是卡死发生在**报文已解析、回调已 respond 之后**的第二次 `recvfrom`，所以「代码可达性」没变。
- 两版都 `exit 0`，无 ASan/LSan 报告、无 assert、无任何错误输出——退化**完全不可见**。
- 真实损失在**预算**：每遇到一个 `mode%3==1` 的输入，整轮预算就烧在等待上；libFuzzer 只在 `-timeout`
  到点时才用闹钟把这次 unit 掐断，然后当作正常结束继续。

所以本条属于「**unit 永不返回、预算被吃光**」型 silent，量化口径用**等预算下的边覆盖**而不是归零：

| 种子 | 旧版 runs | 旧版边覆盖 | 新版 runs | 新版边覆盖 |
|---|---|---|---|---|
| 1 | 33 | 582 | 6200 | 727 |
| 2 | 111 | 592 | 4982 | 717 |
| 3 | 39 | 572 | 4859 | 667 |

（8 s、`-timeout=5`、同一语料；吞吐差 45~188 倍，边覆盖差 +15~19%）

`introduced_by_this_change = false`：`dns_fuzzer.cc` 在 2026-05-05 的 `7dbf92d52804` 引入时就没设非阻塞，
带病存在约 6 个月，直到 H（2026-11-12）修。库侧那段时间没有对应变更。

## Rationale (en)

`dns_fuzzer.cc` dispatches on `mode = last_byte % 3`. The server branch builds its own datagram over a
`socketpair(AF_UNIX, SOCK_DGRAM)` and hands `fds[0]` to `evdns_add_server_port_with_base`. libevent's read
callback contract is "non-blocking fd, read until EAGAIN": after `evdns_server_request_respond()` the server
port loops back into `recvfrom` until EAGAIN. `EVLOOP_NONBLOCK` only keeps `epoll_wait` from blocking; it does
nothing about syscalls inside the callback. Without `O_NONBLOCK` on `fds[0]` the harness consumes the packet,
parses the request, calls the callback, and then sleeps forever in the second `recvfrom` —
`LLVMFuzzerTestOneInput` never returns. H fixes it with one line plus a four-line comment:
`evutil_make_socket_nonblocking(fds[0]);`. Classified as `state` because the missing piece is the fd's
`O_NONBLOCK` status bit, an object-state precondition, not an API misuse, a compile-time configuration, or a
lifecycle step.

Honest caveat on visibility: the README glosses `silent` as "coverage drops to 0", and this case is **not**
that shape. On a single `mode%3==1` input the line coverage of `evdns.c` is 4.38% for *both* harnesses,
because the stall happens after parsing. Both versions exit 0 with no sanitizer report, no assert and no
output at all. The damage is budget: every `mode%3==1` input burns the whole run waiting, and libFuzzer only
cuts the unit loose when `-timeout` fires. It is therefore a "unit never returns, budget consumed" silent,
quantified by equal-budget edge coverage (582/592/572 vs 727/717/667 over 8 s, seeds 1/2/3) rather than by a
drop to zero.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok (旧 harness 编译链接运行均正常，exit 0)",
  "h(M^1) x lib(M)":   "ok (silent: mode%3==1 输入在 recvfrom 永久阻塞，等预算边覆盖 582/592/572)",
  "h(fix) x lib(M)":   "ok (补 evutil_make_socket_nonblocking(fds[0])，同一输入 0~2 ms，边覆盖 727/717/667)"
 },
 "silent_signal": "等预算 8 s：旧 33/111/39 runs / 582/592/572 edges；新 6200/4982/4859 runs / 727/717/667 edges",
 "verdict": "PASS"
}
```

### 实测数据（clang 21.1.8 + compiler-rt，libevent @d82464a2，Ubuntu on WSL）

**1) 阻塞点取证** `verification/blocked_wchan.log`

```
旧 harness，-runs=1 -timeout=0（关掉 libFuzzer 闹钟），输入 srv_a.bin
pid=591
进程状态(stat 第3列 R/S/D): S
wchan=__skb_wait_for_more_packets        ← 内核在 socket 收队列上等待
  tid=591 state=S wchan=__skb_wait_for_more_packets
  tid=595 state=S wchan=hrtimer_nanosleep
12s 后进程仍存活（仍在 recvfrom 中阻塞）
--- libFuzzer 输出里没有 "Executed ... in N ms" 行 ---
```

对照：同一条输入换新 harness，`-timeout=0` 下 0~2 ms 返回 `Executed ... in 1 ms`。

**2) 逐输入分支矩阵** `verification/per_input_matrix.txt`

```
input      mode  old_exec   old_wall | new_exec   new_wall
cfg_a.bin  0     1ms        29       | 1ms        27
cfg_b.bin  0     1ms        25       | 1ms        26
cfg_c.bin  0     0ms        23       | 0ms        25
cfg_d.bin  0     1ms        26       | 1ms        25
cli_a.bin  2     0ms        25       | 0ms        24
cli_b.bin  2     0ms        24       | 0ms        24
cli_c.bin  2     0ms        24       | 0ms        23
cli_d.bin  2     0ms        23       | 0ms        24
srv_a.bin  1     3000ms     3026     | 1ms        32      ← 只有这一支退化
srv_b.bin  1     3000ms     3028     | 2ms        31
srv_c.bin  1     3000ms     3026     | 1ms        30
srv_d.bin  1     3000ms     3025     | 0ms        29
```

（`mode` 是**末字节** `% 3`——`FuzzedDataProvider` 从缓冲区尾部取整数，按首字节分类会全部分错）

**3) 耗时由闹钟决定而非由工作量决定** `verification/timeout_mapping.txt`

```
-timeout(s)  1     2     3     5     8     12
exec(ms)     1000  2000  2000  3000  5000  7000
```

**4) 等预算 fuzz 对比** `verification/fuzzmode_table.txt` + `fuzz_seed{1,2,3}_{old,new}.log`

见上表。旧版 8 s 内只跑出 33~111 次执行，新版 4859~6200 次。

## 复现步骤

```bash
# 1. 取 libevent @d82464a2（input/source/ 就是这棵树）
cmake -S . -B build -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=clang -DCMAKE_C_FLAGS="-g -O1 -fsanitize=fuzzer-no-link,address -fno-omit-frame-pointer" \
  -DEVENT__DISABLE_OPENSSL=ON -DEVENT__DISABLE_MBEDTLS=ON -DEVENT__LIBRARY_TYPE=STATIC \
  -DEVENT__DISABLE_TESTS=ON -DEVENT__DISABLE_SAMPLES=ON -DEVENT__DISABLE_BENCHMARK=ON
cmake --build build -j14

# 2. 链接两版 harness（注意 pre_fix 无扩展名，必须 -x c++ ... -x none）
LIBS="build/lib/libevent.a build/lib/libevent_core.a build/lib/libevent_pthreads.a build/lib/libevent_extra.a"
clang++ -g -O1 -fsanitize=fuzzer,address -std=c++17 -I include -I build/include -I . \
  -x c++ <case>/verification/dns_fuzzer.cc.pre_fix -x none $LIBS -lpthread -o fz_dns_old
clang++ -g -O1 -fsanitize=fuzzer,address -std=c++17 -I include -I build/include -I . \
  -x c++ <case>/input/harness/oss-fuzz/dns_fuzzer.cc -x none $LIBS -lpthread -o fz_dns_new

# 3. 决定性对比
fz_dns_old -runs=1 -timeout=0 <case>/verification/sample_input_dns_query.bin   # 永不返回，需外部 timeout
fz_dns_old -runs=1 -timeout=5 <case>/verification/sample_input_dns_query.bin   # Executed ... in 3000 ms
fz_dns_new -runs=1 -timeout=5 <case>/verification/sample_input_dns_query.bin   # Executed ... in 1 ms
```

## 取证细节

- `verification/dns_fuzzer.cc.pre_fix` 逐字节算 git blob sha1 = `8d50487567a6834b1bac14934c21ed0ef4d9b4fa`，
  与 `input/change.diff` 里 `index 8d50487567a6..9d6378f98a91` 的旧侧一致 → 归档的是 H^1 原文，不是拼凑。
- `input/source/` 266 个文件全部记录在 `verification/source_blob_hashes_sha1.json`。
- 同一个 H 还顺手修了 `listener_fuzzer.cc` 的 `LEV_OPT_CLOSE_ON_FREE` fd 泄漏——那是 lifecycle 类，
  本条不取，避免与 `backup/` 中 REAL-21（tidy-html5）的类型语义混淆。
- `change.diff` 里另有 9 个新增 fuzzer/dict/头文件（`evdns_client`、`evdns_failover`、`evdns_server`、
  `bufferevent_*`、`evdns_fuzzer.dict`、`virtual_clock.h`），都不属于本条 gap。

## 未做 / 局限

- 没取 OSS-Fuzz 线上 coverage bucket，全部数据是同机实测。
- `wall_ms` 有 ±5 ms 抖动，但 3000 ms vs 1 ms、33 vs 6200 runs 不在这个量级。
- 只验证了 `dns_fuzzer` 一条；同 commit 的 `listener_fuzzer.cc` 改动未单独成样。
