# V3-37 — jansson @ c52e770a3f15

- label: **negative** / silent / type `lifecycle` / introduced_by_this_change = None
- change: https://github.com/akheron/jansson/commit/c52e770a3f153701b0b41f9d76bd478a771f23ac (Merge pull request #741 from akheron/depth-limit)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['test/ossfuzz/json_load_dump_fuzzer.cc'] (target `json_load_dump_fuzzer`)

## 理由
本次提交为序列化、比较和深拷贝增加递归深度上限，超过上限时返回错误：这是在 harness 调用的 json_dumpb() 上新增的错误通道。表面上与“新增错误通道而 harness 不读取”的隐式 lifecycle 阳性相同。但 json_load_dump_fuzzer 本来就检查 json_dumpb 的返回值并据此释放资源，新的错误返回会被既有检查消化；定额 fuzz 下 dump 的深度检查代码在多个种子中被执行。harness 无需修改，属于隐式 lifecycle 阴性。

## Rationale
This commit adds a recursion-depth limit to serialisation, comparison and deep copy, returning an error beyond the limit: a new error channel on json_dumpb(), which the harness calls. On the surface this matches a silent lifecycle positive (a new error channel the harness never reads). But json_load_dump_fuzzer already checks json_dumpb's return value and releases resources accordingly, so the new error return is absorbed by existing checks; under the fuzz budget the depth check in dump runs in several seeds. No harness update needed: silent lifecycle negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 108,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.042,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 6193992,
    "gap_covered": [
     1,
     0
    ]
   },
   {
    "seed": 2,
    "execs": 5278504,
    "gap_covered": [
     1,
     0
    ]
   },
   {
    "seed": 3,
    "execs": 9505573,
    "gap_covered": [
     1,
     0
    ]
   }
  ]
 }
}
```
