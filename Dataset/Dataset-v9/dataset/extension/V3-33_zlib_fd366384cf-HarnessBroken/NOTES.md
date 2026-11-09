# V3-33 — zlib @ fd366384cf32

- label: **negative** / silent / type `configuration` / introduced_by_this_change = None
- change: https://github.com/madler/zlib/commit/fd366384cf324d750596feb03be44ddf4d1e6acd (Prevent the use of insecure functions without an explicit request.)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: oss ['projects/zlib/gzio_fuzzer.c'] (target `gzio_fuzzer`)

## 理由
本次提交引入编译宏 ZLIB_INSECURE：只有在平台缺少 vsnprintf()/snprintf() 时，gzprintf() 才会被编译成直接返回错误的桩函数，除非显式定义该宏。表面上这正是“新宏把 harness 调用的功能编译掉”的隐式 configuration 阳性形态，而 gzio_fuzzer 恰好大量调用 gzprintf()。但在提供标准 vsnprintf 的平台上（OSS-Fuzz 的 Linux 构建即是如此），新增的条件编译不生效，gzvprintf() 仍是完整实现；定额 fuzz 下其主体代码在多个种子中被执行。harness 的构建配置无需改动，属于隐式 configuration 阴性。

## Rationale
This commit introduces the compile-time macro ZLIB_INSECURE: only on platforms lacking vsnprintf()/snprintf() is gzprintf() compiled into a stub that returns an error, unless the macro is defined. On the surface this is the silent configuration positive pattern (a new macro compiling out functionality the harness calls), and gzio_fuzzer calls gzprintf() heavily. But on platforms with a standard vsnprintf (as in OSS-Fuzz's Linux build) the new conditional compilation does not apply and gzvprintf() remains the full implementation; under the fuzz budget its body runs in several seeds. The harness build configuration needs no change: silent configuration negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 63,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 1625889,
    "gap_covered": [
     6
    ]
   },
   {
    "seed": 2,
    "execs": 2614306,
    "gap_covered": [
     6
    ]
   },
   {
    "seed": 3,
    "execs": 1919757,
    "gap_covered": [
     6
    ]
   }
  ]
 }
}
```
