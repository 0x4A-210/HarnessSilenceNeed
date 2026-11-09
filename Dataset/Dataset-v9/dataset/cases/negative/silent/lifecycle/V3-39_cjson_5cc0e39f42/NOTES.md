# V3-39 — cjson @ 5cc0e39f42df

- label: **negative** / silent / type `lifecycle` / introduced_by_this_change = None
- change: https://github.com/DaveGamble/cJSON/commit/5cc0e39f42dfe28cb8541f95fa2c513f0d550210 (Fix: add depth check to prevent stack overflow in cJSON_Print (#984))
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['fuzzing/cjson_read_fuzzer.c'] (target `cjson_read_fuzzer`)

## 理由
本次提交在打印数组/对象时增加嵌套深度检查，超过 CJSON_NESTING_LIMIT 即返回失败：cJSON_Print / cJSON_PrintBuffered 等 harness 调用的接口多了一条新的错误通道。表面上与“新增错误通道而 harness 不处理”的隐式 lifecycle 阳性相同。但 cjson_read_fuzzer 本就检查打印结果是否为 NULL 再释放，新的失败返回被既有检查吸收；深度检查代码在定额 fuzz 下于多个种子中执行。由于解析阶段已有同一上限，打印阶段的报错分支对任何经解析得到的对象都不可达，这是库内部的不变量，并非 harness 造成的缺口。harness 无需修改，属于隐式 lifecycle 阴性。

## Rationale
This commit adds a nesting-depth check when printing arrays/objects, failing beyond CJSON_NESTING_LIMIT: harness-called interfaces such as cJSON_Print and cJSON_PrintBuffered gain a new error channel. On the surface this matches a silent lifecycle positive (a new error channel the harness does not handle). But cjson_read_fuzzer already checks whether the printed result is NULL before freeing it, so the new failure return is absorbed, and the depth checks run in several seeds under the fuzz budget. Because parsing already enforces the same limit, the print-time error branch is unreachable for any object obtained by parsing; that is a library-internal invariant, not a gap caused by the harness. No harness update needed: silent lifecycle negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 14,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.25,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 30825541,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 2,
    "execs": 34526471,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 3,
    "execs": 62260769,
    "gap_covered": [
     2
    ]
   }
  ]
 }
}
```
