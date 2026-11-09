# V3-44 — libspng @ 3a115ee4bf12

- label: **positive** / silent / type `mix` ['configuration', 'input_format'] / introduced_by_this_change = False
- change: https://github.com/randy408/libspng/commit/3a115ee4bf1292030370fabf4cf15723f4b660ab (decode: Use the stack for 512-byte gamma LUT)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['tests/spng_read_fuzzer.cc'] (target `spng_read_fuzzer`)
- fix H: https://github.com/randy408/libspng/commit/60fc57f47d790b6a2c299e91bb8dafeda5077ca3

## 理由
本次提交改写了 gAMA 伽马校正的查找表代码（8 位 LUT 改为栈上数组，16 位仍走堆分配）。这段代码同时受两个维度门控：一是解码选项 SPNG_DECODE_USE_GAMA（运行期 flag，configuration），二是输入中必须带 gAMA 块（ctx->stored_gama，input_format：只有特定格式字段的输入才走这条路径）。harness 自 2018-07 创建起就硬编码 spng_decode_image(..., SPNG_FMT_RGBA8, SPNG_DECODE_USE_TRNS)，从不传 USE_GAMA；种子语料里虽有 18 个带 gAMA 的 PngSuite 文件，查找表构建和逐像素校正行的覆盖仍恒为 0，harness 却照常运行。缺口早于本次 diff（M^1 上同样为 0），属于非本次引入的隐式 mix(configuration+input_format) 退化；维护者在 60fc57f 给 harness 加上 SPNG_DECODE_USE_GAMA，次日即由 OSS-Fuzz 在这段代码中发现了 gamma 为 0 的 bug（e97f3219）。

## Rationale
This commit rewrites the lookup-table code of gAMA gamma correction (the 8-bit LUT moves to the stack, the 16-bit one stays on the heap). That code is gated by two dimensions: the decode option SPNG_DECODE_USE_GAMA (a runtime flag, configuration) and a gAMA chunk in the input (ctx->stored_gama, input_format: only inputs carrying that format field take the path). Since its creation in 2018-07 the harness hardcodes spng_decode_image(..., SPNG_FMT_RGBA8, SPNG_DECODE_USE_TRNS) and never passes USE_GAMA; although the seed corpus contains 18 PngSuite files with a gAMA chunk, the LUT construction and per-pixel correction lines keep zero coverage while the harness runs normally. The gap predates this diff (also zero at M^1): a pre-existing silent mix(configuration+input_format) degradation; the maintainer added SPNG_DECODE_USE_GAMA to the harness in 60fc57f, and the next day OSS-Fuzz found a zero-gamma bug in exactly this code (e97f3219).

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
    "execs": 22098884,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 20229236,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 21145224,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 18961261,
    "gap_covered": [
     11
    ]
   },
   {
    "seed": 2,
    "execs": 31101627,
    "gap_covered": [
     11
    ]
   }
  ]
 },
 "fuzz_Mparent_replay": {
  "without_fix": [
   {
    "seed": 1,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": "n/a (replay)",
    "gap_covered": [
     12
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     12
    ]
   }
  ]
 },
 "applies_to_parent": true
}
```
