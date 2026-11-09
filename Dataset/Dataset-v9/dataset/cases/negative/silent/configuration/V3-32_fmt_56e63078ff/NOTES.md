# V3-32 — fmt @ 56e63078ffa3

- label: **negative** / silent / type `configuration` / introduced_by_this_change = None
- change: https://github.com/fmtlib/fmt/commit/56e63078ffa3db89d2ae82b38686c9e8f34d51d2 (Make the n specifier an opt-in)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['test/fuzzing/one_arg.cpp'] (target `fuzzer_one_arg`)

## 理由
本次提交把整数与浮点格式说明中的 'n' 类型放进新宏 FMT_DEPRECATED_N_SPECIFIER（默认未定义）之后。这与“新功能被默认关闭的宏包住、fuzz 构建不开宏导致代码不可达”的隐式 configuration 阳性在表面上一样，fuzz 构建也确实没有定义该宏。但 'n' 只是 'L' 的别名：被宏挡住的只是一个 case 标签，背后的 on_num() / locale 处理仍可经 'L' 到达。定额 fuzz 下这两处代码在多个种子中被执行，harness 无需修改，属于隐式 configuration 阴性。

## Rationale
This commit moves the 'n' presentation type of integer and floating-point specs behind a new macro FMT_DEPRECATED_N_SPECIFIER (undefined by default). On the surface this looks like a silent configuration positive, where a feature is wrapped in an off-by-default macro that the fuzz build does not define, and indeed the fuzz build does not define it. But 'n' is only an alias of 'L': the macro hides a case label, while the on_num()/locale handling behind it stays reachable through 'L'. Under the fuzz budget both code sites run in several seeds; the harness needs no update: silent configuration negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 2790,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 5358906,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 2,
    "execs": 5512932,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 3,
    "execs": 9459094,
    "gap_covered": [
     2
    ]
   }
  ]
 }
}
```
