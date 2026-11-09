# V3-13（Dataset-v6_3 中编号 V3-17）— fmt @ 5420bcce2d29

- label: **positive** / silent / type `configuration` / introduced_by_this_change = True
- change: https://github.com/fmtlib/fmt/commit/5420bcce2d29f10129ea75bc863cf52ddd03ac29 (Make % an opt-in to improve compatibility with std::format)
- origin: real_commit; route: forward_scan; gt: counterfactual_fix
- harness: intree ['test/fuzzing/one_arg.cpp'] (target `fuzzer_one_arg`)

## 理由
本次提交把浮点格式的 '%' 类型改为需要宏 FMT_DEPRECATED_PERCENT 才启用（默认 0）：不定义该宏时，parse_float_type_spec() 遇到 '%' 不再设置 fspec.percent，后面“乘 100、追加 % 并调整小数位”的代码虽然仍在 format.h 中，却永远走不到。fuzz 目标（one_arg 等）的构建配置没有定义这个宏，harness 照常编译运行、随机格式串里的 '%' 也照样出现，只是这段百分号输出逻辑的覆盖静默归零。属于本次引入的隐式 configuration 退化。反事实修复：在 test/fuzzing/CMakeLists.txt 中为 fuzz 目标定义 FMT_DEPRECATED_PERCENT=1（2 行）。

## Rationale
This commit puts the '%' floating-point presentation type behind FMT_DEPRECATED_PERCENT (default 0): without the macro, parse_float_type_spec() no longer sets fspec.percent for '%', so the code that multiplies by 100, appends '%' and adjusts the decimal position remains in format.h but becomes unreachable. The fuzz targets' build configuration (one_arg etc.) does not define the macro; the harness builds and runs as before and random format strings still contain '%', but coverage of the percent output logic silently drops to zero. Silent configuration degradation introduced by this change. Counterfactual fix: define FMT_DEPRECATED_PERCENT=1 for the fuzz targets in test/fuzzing/CMakeLists.txt (2 lines).

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
    "execs": 17677305,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 19307160,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 16988988,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 18623033,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 2,
    "execs": 30069121,
    "gap_covered": [
     2
    ]
   }
  ]
 },
 "applies_to_parent": false
}
```
