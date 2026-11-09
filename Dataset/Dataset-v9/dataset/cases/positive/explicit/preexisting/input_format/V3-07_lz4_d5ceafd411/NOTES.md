# V3-07 — lz4 @ d5ceafd4118c

- label: **positive** / explicit / type `input_format` / introduced_by_this_change = False
- change: https://github.com/lz4/lz4/commit/d5ceafd4118c88e2372b0ccb35f8352f25f172a1 (Merge pull request #793 from nigeltao/dev)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['ossfuzz/compress_frame_fuzzer.c'] (target `compress_frame_fuzzer`)
- fix H: https://github.com/lz4/lz4/commit/e9d8e15263df4a0529dcd22ca48c82869d19abb9

## 理由
本次提交调整 lz4.c 的压缩核心，compress_frame_fuzzer 经 LZ4F_compressFrame() 驱动这段代码。但自 64e3134b2a 起，该 harness 在封装输入时把缓冲区长度写成 LZ4_compressBound(size)（比真实输入更大）：数据生产器从“缓冲区末尾”取参数时直接越界读，交给 LZ4F_compressFrame() 的输入长度也超出真实数据。回放语料时几乎每个输入都在 harness 的 FUZZ_dataProducer_* 中触发 ASan heap-buffer-overflow，变更前后一致，fuzzer 实际上无法工作。退化早于本次 diff，属于非本次引入的显式 input_format 退化（harness 对输入的切分/封装与真实输入不符）；维护者在 e9d8e15263 改为 FUZZ_dataProducer_create(data, size)。

## Rationale
This commit adjusts the compression core in lz4.c, which compress_frame_fuzzer drives through LZ4F_compressFrame(). Since 64e3134b2a, however, the harness frames its input with a buffer length of LZ4_compressBound(size), larger than the real input: the data producer reads its parameters from the 'end' of that buffer, i.e. out of bounds, and the input length passed to LZ4F_compressFrame() exceeds the real data. Replaying the corpus, nearly every input hits an ASan heap-buffer-overflow inside the harness's FUZZ_dataProducer_* helpers, before and after the change; the fuzzer cannot do useful work. The degradation predates this diff: pre-existing explicit input_format degradation (the harness splits/frames its input inconsistently with the real input); fixed upstream in e9d8e15263 (FUZZ_dataProducer_create(data, size)).

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok",
  "h(fix) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 1390,
  "crashes_lib_parent": 600,
  "crashes_lib_M": 600,
  "crashes_fixed_harness_lib_M": 0
 },
 "explicit_signal": "runtime_failure_on_replay"
}
```
