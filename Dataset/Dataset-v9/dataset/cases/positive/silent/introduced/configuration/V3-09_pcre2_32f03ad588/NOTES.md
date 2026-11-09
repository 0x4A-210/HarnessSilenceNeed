# V3-09 — pcre2 @ 32f03ad58890

- label: **positive** / silent / type `configuration` / introduced_by_this_change = True
- change: https://github.com/PCRE2Project/pcre2/commit/32f03ad588908bdf3365e6fe827465ec0a0cfcc8 (Add option to disable callouts (#499))
- origin: real_commit; route: head_audit; gt: counterfactual_fix
- harness: intree ['src/pcre2_fuzzsupport.c'] (target `pcre2_fuzzer`)

## 理由
本次提交新增编译期 extra 选项 PCRE2_EXTRA_NEVER_CALLOUT：开启后，模式中的 (?C...) 会被拒绝（ERR103）。该选项只能通过 pcre2_set_compile_extra_options() 设置，模式文本无法开启。harness 创建了 compile_context，却从不设置 extra 选项，xoptions 恒为 0，新分支在 harness 下永远不可达。harness 照常编译运行，只是静默丢失这段新代码的覆盖，属于本次引入的隐式 configuration 退化。反事实修复：用输入中未使用的随机位驱动 extra 选项（≤15 行，只改 harness）。

## Rationale
This commit adds the compile-time extra option PCRE2_EXTRA_NEVER_CALLOUT, which rejects (?C...) callouts with ERR103. The option can only be set via pcre2_set_compile_extra_options(); no pattern syntax enables it. The harness creates a compile context but never sets extra options, so xoptions is always 0 and the new branch is unreachable. The harness builds and runs normally and silently loses coverage of the new code: silent configuration degradation introduced by this change. Counterfactual fix: drive the extra options from unused random bits of the input (≤15 lines, harness only).

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
    "execs": 1539932,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 1560606,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 1858728,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 1816803,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 2,
    "execs": 1828491,
    "gap_covered": [
     2
    ]
   }
  ]
 },
 "applies_to_parent": false
}
```
