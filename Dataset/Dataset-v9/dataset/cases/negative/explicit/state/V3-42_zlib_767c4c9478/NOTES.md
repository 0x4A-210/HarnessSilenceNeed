# V3-42 — zlib @ 767c4c947852

- label: **negative** / explicit / type `state` / introduced_by_this_change = None
- change: https://github.com/madler/zlib/commit/767c4c947852e143f582c85f14cf573411df1b35 (Honor deflateReset promise to reset the header.)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: oss ['projects/zlib/example_flush_fuzzer.c'] (target `example_flush_fuzzer`)

## 理由
本次提交修改 deflate 流的重置契约：gzip 头指针 s->gzhead 不再只在 deflateInit2_() 里清空，而是在每次 deflateResetKeep()（deflateReset 的核心）中清空，使 deflateReset() 真正兑现文档“重置一切状态（含头）”的承诺；提交说明还提醒“依赖头部在 reset 后仍保留的代码可能会被破坏”。这正是会让依赖旧复用语义的调用方失配的状态契约变化。harness 每个输入都经 deflateInit() 进入 deflateReset()，改动行在固定语料回放中被执行；但它从不调用 deflateSetHeader()，也不依赖 reset 后的头部残留，编译通过、回放无新崩溃，harness 无需修改，属于显式 state 阴性。

## Rationale
This commit changes the reset contract of a deflate stream: the gzip header pointer s->gzhead is no longer cleared only in deflateInit2_() but in every deflateResetKeep() (the core of deflateReset), so deflateReset() now honours the documented promise to reset all state including the header; the commit message warns that code relying on the header persisting across resets may break. That is exactly the kind of state-contract change that breaks callers relying on the old reuse semantics. The harness enters deflateReset() through deflateInit() on every input, so the changed line runs on fixed-corpus replay; but it never calls deflateSetHeader() and does not depend on a header surviving a reset: it builds, replay shows no new crash, and no harness change is needed - an explicit state negative.

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
 "patch_cov": 1.0
}
```
