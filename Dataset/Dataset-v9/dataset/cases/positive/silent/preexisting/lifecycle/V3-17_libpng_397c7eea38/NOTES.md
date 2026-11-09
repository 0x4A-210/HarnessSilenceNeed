# V3-17 — libpng @ 397c7eea385c

- label: **positive** / silent / type `lifecycle` / introduced_by_this_change = False
- change: https://github.com/pnggroup/libpng/commit/397c7eea385c22b6033e0310badfadbd9f578422 ([libpng16] Add a memset() in png_read_buffer())
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['contrib/oss-fuzz/libpng_read_fuzzer.cc'] (target `libpng_read_fuzzer`)
- fix H: https://github.com/pnggroup/libpng/commit/f648294931aa7f5dbf33dc62990f870d8b9448ec

## 理由
本次提交只在 pngrutil.c 的 png_read_buffer() 中加了一个 memset，该函数位于逐行读取 IDAT 的路径上（png_read_IDAT_data 调用它）。但自 2017-08-26 起 harness 先调用 png_read_update_info()，随后又调用 png_start_read_image()：在 libpng 1.6 中两者都会做行初始化，第二次调用被判定为“duplicate call”的 png_app_error，未设置 APP_ERRORS_WARN 时即为 png_error，经 longjmp 跳回 harness 的清理分支。于是每个输入在读第一行之前就结束：png_read_row、png_read_IDAT_data、各种 filter/interlace 解码路径覆盖恒为 0，harness 却照常运行、不报错。这是初始化调用顺序（生命周期）契约被违反导致的隐式退化，早于本次 diff；维护者在 f648294931 删除了多余的 png_start_read_image() 调用。

## Rationale
This commit only adds a memset() to png_read_buffer() in pngrutil.c, a function on the row-reading path (png_read_IDAT_data calls it). Since 2017-08-26, however, the harness calls png_read_update_info() and then png_start_read_image(): in libpng 1.6 both perform row initialisation, the second one is a 'duplicate call' png_app_error, and without APP_ERRORS_WARN that is png_error, which longjmps to the harness cleanup. Every input therefore ends before the first row is read: png_read_row, png_read_IDAT_data and all filter/interlace decoding paths keep zero coverage while the harness runs without any visible error. A silent degradation caused by violating the initialisation call-order (lifecycle) contract, predating this diff; fixed by the maintainer in f648294931, which removes the redundant png_start_read_image() call.

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
    "execs": 16833837,
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 2,
    "execs": 11770188,
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 3,
    "execs": 16270693,
    "gap_covered": [
     0,
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 4055548,
    "gap_covered": [
     3,
     4
    ]
   },
   {
    "seed": 2,
    "execs": 1619626,
    "gap_covered": [
     3,
     4
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
     0,
     0
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 3,
    "execs": "n/a (replay)",
    "gap_covered": [
     0,
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": "n/a (replay)",
    "gap_covered": [
     3,
     4
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     3,
     4
    ]
   }
  ]
 },
 "applies_to_parent": true
}
```
