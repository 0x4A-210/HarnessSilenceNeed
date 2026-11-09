# V3-14 — xz @ fe4d763d566a

- label: **positive** / silent / type `state` / introduced_by_this_change = False
- change: https://github.com/tukaani-project/xz/commit/fe4d763d566a38ad61d4c5022520c25578a3a464 (liblzma: Make lzma_lz_decoder_init() safe to reinit after alloc failure)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['tests/ossfuzz/fuzz_decode_alone.c'] (target `fuzz_decode_alone`)
- fix H: https://github.com/tukaani-project/xz/commit/d4217668a79e6ca440e673115155559c81e89b84

## 理由
本次提交修改 lzma_lz_decoder_init() 的“复用已有字典”逻辑，使其在内存分配失败后被再次初始化时也安全；这段逻辑只有在同一个 lzma_stream 被重复初始化（coder 与字典已存在）时才会走到。fuzz_decode_alone 每个输入都新建一个 lzma_stream、只初始化一次，复用分支（coder != NULL、字典大小相同）从未执行，复用状态下的缺陷也就无从暴露。harness 照常运行不报错，只是静默缺失状态复用路径的覆盖；这一缺口自 harness 创建以来一直存在，属于非本次引入的隐式 state 退化。维护者随后在 d4217668a7 让 fuzzer 对同一 stream 连续初始化三次。

## Rationale
This commit changes the reuse-the-existing-dictionary logic of lzma_lz_decoder_init() so that re-initialisation after an allocation failure is safe; that logic only runs when the same lzma_stream is initialised again (coder and dictionary already exist). fuzz_decode_alone creates a fresh lzma_stream for every input and initialises it once, so the reuse branches (coder != NULL, same dictionary size) never execute and defects in the reused state cannot surface. The harness runs normally while silently missing coverage of the state-reuse paths; the gap has existed since the harness was written. Pre-existing silent state degradation; the maintainers then made the fuzzers re-initialise the same stream three times in d4217668a7.

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
    "execs": 3197179,
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 2,
    "execs": 2366431,
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 3,
    "execs": 1238555,
    "gap_covered": [
     0,
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 1171331,
    "gap_covered": [
     1,
     1
    ]
   },
   {
    "seed": 2,
    "execs": 2364252,
    "gap_covered": [
     1,
     1
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
     1,
     1
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     1,
     1
    ]
   }
  ]
 },
 "applies_to_parent": true
}
```
