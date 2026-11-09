# V3-35 — libspng @ e68ba5df5717

- label: **negative** / silent / type `input_format` / introduced_by_this_change = None
- change: https://github.com/randy408/libspng/commit/e68ba5df571726bf001d9ea150980463ea395a75 (decode: fix invalid error return for 0-length EXIF (#248))
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['tests/spng_read_fuzzer.c'] (target `spng_read_fuzzer`)

## 理由
本次提交改变对零长度 eXIf 块的处理：此前把它当作错误返回，现在作为合法输入接受，这是一个输入格式边界上的新分支。表面上与隐式 input_format 阳性相同（新格式分支）。但 spng_read_fuzzer 以 SPNG_CRC_USE 忽略 CRC、并读取全部非 IDAT 块，fuzzer 很容易构造出零长度的 eXIf；定额 fuzz 下新分支在多个种子中被执行。harness 无需修改，属于隐式 input_format 阴性。

## Rationale
This commit changes how a zero-length eXIf chunk is handled: previously reported as an error, it is now accepted, a new branch at an input-format boundary. On the surface this matches a silent input_format positive. But spng_read_fuzzer ignores CRCs (SPNG_CRC_USE) and reads all non-IDAT chunks, so the fuzzer easily produces a zero-length eXIf; under the fuzz budget the new branch runs in several seeds. No harness update needed: silent input_format negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 1018,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 6571346,
    "gap_covered": [
     1
    ]
   },
   {
    "seed": 2,
    "execs": 6767884,
    "gap_covered": [
     1
    ]
   },
   {
    "seed": 3,
    "execs": 16908764,
    "gap_covered": [
     1
    ]
   }
  ]
 }
}
```
