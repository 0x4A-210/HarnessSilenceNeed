# V3-38 — pugixml @ a3fad540a70b

- label: **negative** / silent / type `mix` ['configuration', 'lifecycle'] / introduced_by_this_change = None
- change: https://github.com/zeux/pugixml/commit/a3fad540a70bbba9349e8361aff8bff4dfdf7e67 (Merge pull request #369 from zeux/xpath-rec)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['tests/fuzz_xpath.cpp'] (target `fuzz_xpath`)

## 理由
本次提交限制 XPath 语法树深度以防栈溢出：新增编译期配置宏 PUGIXML_XPATH_DEPTH_LIMIT（configuration，带默认值 1024），并在解析超深表达式时抛出新的 xpath_exception 错误（lifecycle：新的错误通道）。表面上同时具有“新宏”和“新错误通道”两种隐式阳性特征。但宏有默认值、无需在构建中定义；fuzz_xpath 本就用 try/catch 捕获 xpath_exception，新的错误会被既有处理吸收，而嵌套括号等超深表达式很容易由 fuzzer 生成；定额 fuzz 下深度计数与报错代码在多个种子中被执行。harness 无需修改，属于隐式 mix(configuration+lifecycle) 阴性。

## Rationale
This commit limits XPath AST depth to prevent stack overflow: a new compile-time macro PUGIXML_XPATH_DEPTH_LIMIT (configuration, defaulting to 1024) and a new xpath_exception raised for over-deep expressions (lifecycle: a new error channel). On the surface it shows both silent-positive traits, a new macro and a new error channel. But the macro has a default and needs no build definition, fuzz_xpath already catches xpath_exception so the new error is absorbed by existing handling, and over-deep expressions such as nested parentheses are easy for the fuzzer to produce; under the fuzz budget the depth accounting and error code run in several seeds. No harness update needed: silent mix(configuration+lifecycle) negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 5,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.96,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 8017497,
    "gap_covered": [
     24
    ]
   },
   {
    "seed": 2,
    "execs": 7723584,
    "gap_covered": [
     24
    ]
   },
   {
    "seed": 3,
    "execs": 12651956,
    "gap_covered": [
     24
    ]
   }
  ]
 }
}
```
