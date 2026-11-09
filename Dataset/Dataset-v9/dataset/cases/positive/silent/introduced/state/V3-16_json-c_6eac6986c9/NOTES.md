# V3-16 — json-c @ 6eac6986c9a7

- label: **positive** / silent / type `state` / introduced_by_this_change = True
- change: https://github.com/json-c/json-c/commit/6eac6986c9a734b183e55a80e84fa67e58c637ff (Fix incremental parsing of invalid numbers with exponents, such as "0e+-" and "12.3E12E12", while still allowing "0e+" in non-strict mode. Deprecate the json_parse_double() function from json_util.h)
- origin: real_commit; route: forward_scan; gt: counterfactual_fix
- harness: oss ['projects/json-c/tokener_parse_ex_fuzzer.cc'] (target `tokener_parse_ex_fuzzer`)

## 理由
本次提交修改 json_tokener_parse_ex() 的增量解析行为：数字的指数状态不再跨调用保存，而是在下一次调用恢复到 number 状态时，根据 tok->pb 中已保存的字符串重新推导（新增 printbuf_length(tok->pb) > 0 时的状态重建块）。这段代码只有在同一个 tokener 被多次调用、且上一次恰好停在数字中间时才会执行。OSS-Fuzz harness 对每个输入只在新建的 tokener 上调用一次 parse_ex，每次新进入 number 状态都会先 printbuf_reset，因此这段跨调用状态重建逻辑覆盖恒为 0，harness 照常运行。属于本次引入的隐式 state 退化（解析器跨调用的状态恢复契约从未被测试）；反事实修复 Δh 用首字节作为切分点，把其余输入分两次喂给同一 tokener。

## Rationale
This commit changes the incremental behaviour of json_tokener_parse_ex(): the exponent state of a number is no longer saved across calls but re-derived, when a later call resumes in the number state, from the string already saved in tok->pb (the new state-reconstruction block guarded by printbuf_length(tok->pb) > 0). That code runs only when the same tokener is called repeatedly and the previous call stopped in the middle of a number. The OSS-Fuzz harness calls parse_ex once per input on a fresh tokener, and every fresh entry into the number state resets the print buffer, so the cross-call state reconstruction keeps zero coverage while the harness runs normally. Introduced silent state degradation (the parser's cross-call resume contract is never exercised); the counterfactual fix Δh uses the first byte as a split point and feeds the rest of the input to the same tokener in two chunks.

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
    "execs": 5353955,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 3217212,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 5280631,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 8399456,
    "gap_covered": [
     8
    ]
   },
   {
    "seed": 2,
    "execs": 12015727,
    "gap_covered": [
     8
    ]
   }
  ]
 },
 "applies_to_parent": false
}
```
