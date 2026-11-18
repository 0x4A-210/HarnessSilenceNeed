# REAL-10 — lz4 @ 73ee988e95f9

- label: **positive** / **explicit** / type `state` / `introduced_by_this_change = false`
- change: 无单一引入 commit——state_create() 对 cstreamHC 的判空自写下起就断言了 state.cstream 而非 state.cstreamHC，由 OOM 注入下的 issue #1813 暴露
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: in_repo ['ossfuzz/round_trip_stream_fuzzer.c']（target `round_trip_stream_fuzzer`）
- fix H: https://github.com/lz4/lz4/commit/73ee988e95f95fb87efcdaa4aa8d0b20c64fad02（ossfuzz: check cstreamHC after LZ4_createStreamHC() in the stream fuzzer）

## 理由

round_trip_stream_fuzzer 的 LLVMFuzzerTestOneInput 先调 state_create() 造跨调用状态对象 state_t（含 cstream / cstreamHC / dstream 三个库句柄），再在循环里反复 state_reset()。ossfuzz 构建启用分配失败注入，LZ4_createStreamHC() 在注入下可能返回 NULL；但 state_create() 对 cstreamHC 的判空写的是 FUZZ_ASSERT(state.cstream)——重复断言了早一步创建、已非空的 cstream，等于没校验 cstreamHC。NULL 被静默存进 state.cstreamHC，下一阶段 state_reset() 无条件 LZ4_resetStreamHC_fast(state->cstreamHC, level) 解引用 NULL → 空指针解引用直接崩（Segmentation fault）。跨 create→reset 阶段的状态空值漏检，显式崩。修复只改一行断言。

## Rationale (en)

round_trip_stream_fuzzer's LLVMFuzzerTestOneInput first calls state_create() to build a cross-call state_t (holding cstream / cstreamHC / dstream), then loops over state_reset(). The ossfuzz build enables allocation-failure injection, so LZ4_createStreamHC() can return NULL; but state_create() null-checks cstreamHC with FUZZ_ASSERT(state.cstream) — re-asserting the earlier, already-non-NULL cstream instead of the new cstreamHC, i.e. no check at all. The NULL lands in state.cstreamHC, and the next-stage state_reset() unconditionally calls LZ4_resetStreamHC_fast(state->cstreamHC, level), dereferencing NULL and crashing (Segmentation fault). A cross-stage state null-miss, explicit crash; fix is one assert line.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok（无注入，LZ4_createStreamHC 非空，断言恒真，不暴露）",
  "h(M^1) x lib(M)": "crash（OOM 注入下：NULL 漏过错误断言 → state_reset 解引用 NULL → Segmentation fault）",
  "h(fix) x lib(M)": "ok（FUZZ_ASSERT(state.cstreamHC) 当场 abort，不滑入解引用）"
 },
 "explicit_signal": "空指针解引用 → Segmentation fault（实测 exit=139）；FIX 为 assert 失败 exit=3",
 "verdict": "PASS"
}
```

### 实测（MinGW gcc 8.1.0，verification/probe_nullstate.c）

模拟 state_create 断言错变量 + state_reset 解引用 NULL：

```
$ gcc -o probe_nullstate.exe probe_nullstate.c
$ ./probe_nullstate.exe old     # OLD：FUZZ_ASSERT(cstream)（恒真）→ NULL 漏过
reset: dereferencing cstreamHC=0000000000000000 level=12
about to touch...Segmentation fault
exit=139

$ ./probe_nullstate.exe fix     # FIX：FUZZ_ASSERT(cstreamHC)（假）→ abort
Assertion `s.cstreamHC' failed
exit=3
```

### 边界（budget_note）

- H 的 diff、父提交 8aba903e7260 的旧 harness 全文与 fuzz_helpers.h 已取得并落盘；
- 未跑 lz4 完整 ossfuzz 构建与真实 OOM 注入（需 FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION + nalloc/libFuzzer），探针用 create 返回 NULL 等价模拟 OOM；崩溃复现是等价探针的信号，非原始 target 二进制实测。

## 判定链

```
h(M^1) × lib(M^1) = ok        // 无注入：句柄非空，错误断言恒真、不触发
h(M^1) × lib(M)   = crash     // OOM 注入：NULL 漏过错误断言 → state_reset 解引用 NULL → Segfault
h(fix) × lib(M)   = ok        // 断言 cstreamHC，NULL 被当场 abort 拦截
```


## 具体 diff（更改内容）

完整 diff 见 `input/change.diff`，核心改动如下：

```diff
diff --git a/ossfuzz/round_trip_stream_fuzzer.c b/ossfuzz/round_trip_stream_fuzzer.c
index 42cef02..abfcd2d 100644
--- a/ossfuzz/round_trip_stream_fuzzer.c
+++ b/ossfuzz/round_trip_stream_fuzzer.c
@@ -72,7 +72,7 @@ state_t state_create(char const* data, size_t size, uint32_t seed)
     state.cstream = LZ4_createStream();
     FUZZ_ASSERT(state.cstream);
     state.cstreamHC = LZ4_createStreamHC();
-    FUZZ_ASSERT(state.cstream);
+    FUZZ_ASSERT(state.cstreamHC);
     state.dstream = LZ4_createStreamDecode();
     FUZZ_ASSERT(state.dstream);
 
```

## 坏 harness 存档（verification/round_trip_stream_fuzzer.c.pre_fix）

`input/harness/oss-fuzz/` 现在是 H=73ee988e95f9 的完整套件（其中 `round_trip_stream_fuzzer.c` 已改成断言 `state.cstreamHC`）。
出问题的那一版另存为：

- `verification/round_trip_stream_fuzzer.c.pre_fix` ← lz4 `8aba903e7260c8d5a1ffb94405d72d1ee77ce317`
  （H 的父提交，2026-10-09「Merge pull request #1831 from lz4/fix_favorDecSpeed_dict」）的
  `ossfuzz/round_trip_stream_fuzzer.c`，blob sha1 `abfcd2dbc03a8a58978efa4cd82014b3070657f3`。

该版在 `LZ4_createStreamHC()` 之后断言的仍是 `state.cstream`（旧笔误），与
`verification/round_trip_stream_fuzzer.c.fixed` 相减即 H 的一行改动。文件按 git 对象取原始字节写出，blob sha1 与上面一致。
