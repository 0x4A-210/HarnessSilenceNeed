# V3-26 — lz4 @ 950c1cecda20

- label: **negative** / explicit / type `state` / introduced_by_this_change = None
- change: https://github.com/lz4/lz4/commit/950c1cecda204fdb9b93ec492a1cbe5fcb5d2a76 (Merge pull request #1829 from lz4/stream_clear_table)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['ossfuzz/round_trip_stream_fuzzer.c'] (target `round_trip_stream_fuzzer`)

## 理由
本次提交优化小块压缩：在流式压缩上下文被重置/复用时，按需清理哈希表（table 的清空与类型标记逻辑改变），这是对 LZ4_stream_t 复用与重置契约的改动，直接落在 harness 使用的接口上——round_trip_stream_fuzzer 在同一个流上反复调用 LZ4_resetStream_fast()、加载/挂接字典并连续压缩多个块。harness 的复用方式与新逻辑兼容：变更前后都能编译，回放语料的往返校验无新失败，改动的清表代码被执行。harness 仍然充分，属于显式 state 阴性。

## Rationale
This commit speeds up compression of small blocks by clearing the hash table on demand when a streaming context is reset or reused (the clearing and table-type bookkeeping change), a change to the reuse/reset contract of LZ4_stream_t that lands directly on interfaces the harness uses: round_trip_stream_fuzzer repeatedly calls LZ4_resetStream_fast() on the same stream, loads/attaches dictionaries and compresses several blocks in a row. The harness's reuse pattern is compatible with the new logic: it builds before and after, the round-trip checks on corpus replay show no new failure, and the changed table-clearing code runs. The harness stays adequate: explicit state negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 5147,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0
}
```
