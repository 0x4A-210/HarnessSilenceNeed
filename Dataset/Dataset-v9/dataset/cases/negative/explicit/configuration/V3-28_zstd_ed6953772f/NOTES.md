# V3-28 — zstd @ ed6953772f41

- label: **negative** / explicit / type `configuration` / introduced_by_this_change = None
- change: https://github.com/facebook/zstd/commit/ed6953772f41ff9308dd958a35e24ec613b83878 (Merge pull request #3623 from felixhandte/compile-out-compressors)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['tests/fuzz/stream_round_trip.c'] (target `stream_round_trip`)

## 理由
本次提交新增一组构建开关 ZSTD_EXCLUDE_*_BLOCK_COMPRESSOR（并接入 libzstd.mk），允许在编译时剔除部分块压缩器，同时重写了压缩策略到块压缩器的分派逻辑。这是构建配置层面的变化，直接作用于 stream_round_trip 通过随机参数驱动的各种压缩策略。harness 的构建不定义这些开关，默认仍编入全部压缩器：变更前后都能编译，回放语料的往返校验无新失败，改写后的分派代码被执行。harness 仍然充分，属于显式 configuration 阴性。

## Rationale
This commit adds build switches ZSTD_EXCLUDE_*_BLOCK_COMPRESSOR (wired into libzstd.mk) that let block compressors be compiled out, and rewrites how compression strategies dispatch to block compressors: a build-configuration change acting directly on the strategies stream_round_trip drives through random parameters. The harness build defines none of the switches, so all compressors are still compiled in by default: it builds before and after, round-trip checks on corpus replay show no new failure, and the rewritten dispatch code runs. The harness stays adequate: explicit configuration negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 24222,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.806
}
```
