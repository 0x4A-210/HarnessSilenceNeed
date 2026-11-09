# V3-34 — tinyobjloader @ 7b3ba0be7146

- label: **negative** / silent / type `input_format` / introduced_by_this_change = None
- change: https://github.com/tinyobjloader/tinyobjloader/commit/7b3ba0be7146b0414463203c31bdf6a9376accb2 (Fix parsing [w] component in `v` line. Improve python binding.   - Expose more attrib to Python.)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['fuzzer/fuzz_ParseFromString.cc'] (target `fuzz_ParseFromString`)

## 理由
本次提交修正 OBJ 顶点行 v 的可选第四分量 [w] 的解析，并把它暴露到属性中：这是一个新的输入格式分支（v x y z w 的写法）。表面上与“新格式变体只在 harness 不构造的封装下可达”的隐式 input_format 阳性相同。但 fuzz_ParseFromString 把原始字节整体交给 ObjReader::ParseFromString()，不加任何封装或长度限制，带第四分量的 v 行由 fuzzer 自然生成；定额 fuzz 下新增的解析代码在多个种子中被执行。harness 无需修改，属于隐式 input_format 阴性。

## Rationale
This commit fixes parsing of the optional fourth component [w] of OBJ 'v' lines and exposes it in the attributes: a new input-format branch ('v x y z w'). On the surface this matches a silent input_format positive, where a new format variant is only reachable under framing the harness never builds. But fuzz_ParseFromString hands the raw bytes to ObjReader::ParseFromString() with no framing or length restriction, so 'v' lines with a fourth component arise naturally; under the fuzz budget the new parsing code runs in several seeds. No harness update needed: silent input_format negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 4551,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.839,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 5388053,
    "gap_covered": [
     47
    ]
   },
   {
    "seed": 2,
    "execs": 4570531,
    "gap_covered": [
     47
    ]
   },
   {
    "seed": 3,
    "execs": 10690776,
    "gap_covered": [
     47
    ]
   }
  ]
 }
}
```
