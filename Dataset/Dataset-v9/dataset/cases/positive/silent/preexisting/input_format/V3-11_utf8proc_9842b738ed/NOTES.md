# V3-11 — utf8proc @ 9842b738ed77

- label: **positive** / silent / type `input_format` / introduced_by_this_change = False
- change: https://github.com/JuliaStrings/utf8proc/commit/9842b738ed779aad54b5d12af950bec80f9d76a1 (normalize_utf32: keep invalid codepoints in the compose loop (#355))
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['test/fuzzer.c'] (target `utf8proc_fuzzer`)
- fix H: https://github.com/JuliaStrings/utf8proc/commit/8a7db0fb93393c261dc286ab1a067e022b202e66

## 理由
本次提交修改 utf8proc_normalize_utf32()（合成循环中对非法码点的处理），harness 本意正是把原始字节当作 UTF-32 数组、以 STRIPCC / NLF2LS / NLF2PS 等选项直接喂给 normalize_utf32：这条“原始 UTF-32 直接输入”的入口是唯一会带着单独的 NLF2LS、单独的 NLF2PS 或 STRIPCC 进入换行/控制字符处理分支的路径（经 utf8proc_map 的调用都不带这些组合）。但该 harness 自 2022 年起把分配条件写反（size>=4 时 copy 为 NULL，size<4 时长度变成 0），直接输入从未带过任何码点：换行转 U+2028 / U+2029 / 空格、制表符转空格这些分支覆盖恒为 0，harness 却照常运行。退化早于本次 diff，属于非本次引入的隐式 input_format 退化（harness 构造的 UTF-32 输入为空）；维护者在 8a7db0fb93 修正分配与长度。

## Rationale
This commit changes utf8proc_normalize_utf32() (how the compose loop treats invalid code points). The harness intends to feed raw bytes to normalize_utf32 as a UTF-32 array under options such as STRIPCC, NLF2LS and NLF2PS; this direct raw-UTF-32 entry is the only path that reaches the newline/control-character branches with NLF2LS alone, NLF2PS alone or STRIPCC (calls through utf8proc_map never use those combinations). Since 2022, however, the harness inverts its allocation condition (copy is NULL whenever size >= 4, and for size < 4 the length becomes 0), so the direct input never carries a single code point: the branches mapping newlines to U+2028 / U+2029 / space and tab to space keep zero coverage while the harness runs normally. The degradation predates this diff: pre-existing silent input_format degradation (the harness builds an empty UTF-32 input); fixed upstream in 8a7db0fb93 (allocation and length corrected).

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
    "execs": 8179220,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 8302309,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 4346496,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 9517597,
    "gap_covered": [
     4
    ]
   },
   {
    "seed": 2,
    "execs": 8672814,
    "gap_covered": [
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
     4
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     4
    ]
   }
  ]
 },
 "applies_to_parent": true
}
```
