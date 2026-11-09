# V3-15 — zstd @ 824f75ea7c48

- label: **positive** / silent / type `input_format` / introduced_by_this_change = True
- change: https://github.com/facebook/zstd/commit/824f75ea7c48a2db26693699a2178ecea84dfb7a (Merge pull request #863 from facebook/newFormats)
- origin: real_commit; route: head_audit; gt: counterfactual_fix
- harness: intree ['tests/fuzz/stream_decompress.c'] (target `stream_decompress`)

## 理由
本次合并（PR #863 newFormats）为解码器新增了无魔数帧格式 ZSTD_f_zstd1_magicless，只能通过 ZSTD_DCtx_setFormat() 选择；输入接受的帧格式因此扩展了一种。in-tree 解码 harness stream_decompress.c 未作任何修改，从不设置格式，dctx->format 恒为 ZSTD_f_zstd1：ZSTD_startingInputLength 的无魔数分支、ZSTD_getFrameHeader_internal 中 format==magicless 的分支覆盖恒为 0，harness 却照常运行。这一新输入格式的解码路径直到 2024-03 的 741b87bbe 才被新 fuzzer 覆盖，并随即修复了无魔数解码中的真实 bug。属于本次引入的隐式 input_format 退化；反事实修复 Δh 用种子的一位选择帧格式。

## Rationale
This merge (PR #863 newFormats) adds the magicless frame format ZSTD_f_zstd1_magicless to the decoder, selectable only through ZSTD_DCtx_setFormat(), i.e. the decoder now accepts one more frame format. The in-tree decoding harness stream_decompress.c is unchanged and never sets the format, so dctx->format is always ZSTD_f_zstd1: the magicless arm of ZSTD_startingInputLength and the format==magicless branch of ZSTD_getFrameHeader_internal keep zero coverage while the harness runs normally. The magicless decoding path was first fuzzed by a new fuzzer in 741b87bbe (2024-03), which immediately fixed real magicless-decoding bugs. Introduced silent input_format degradation; the counterfactual fix Δh selects the frame format from one seed bit.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok",
  "h(fix) x lib(M)": "ok"
 },
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 3327731,
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 2,
    "execs": 2111713,
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 3,
    "execs": 1717140,
    "gap_covered": [
     0,
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 6945801,
    "gap_covered": [
     1,
     2
    ]
   },
   {
    "seed": 2,
    "execs": 2555442,
    "gap_covered": [
     1,
     2
    ]
   }
  ]
 },
 "applies_to_parent": false
}
```
