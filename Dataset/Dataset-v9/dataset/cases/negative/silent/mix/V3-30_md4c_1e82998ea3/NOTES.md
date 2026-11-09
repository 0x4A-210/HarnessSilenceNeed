# V3-30 — md4c @ 1e82998ea361

- label: **negative** / silent / type `mix` ['configuration', 'input_format'] / introduced_by_this_change = None
- change: https://github.com/mity/md4c/commit/1e82998ea3619d4239ca5d0468370bf754bb2740 (Add spoiler span extension (#308))
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['test/fuzzers/fuzz-mdhtml.c'] (target `fuzz-mdhtml`)

## 理由
本次提交新增 spoiler 扩展：一个新的解析器 flag（MD_FLAG_SPOILER）和与之配套的新内联语法（||text||），以及 HTML 渲染器对新 span 类型的输出。表面上这同时是“新增选项取值”（configuration）和“新增输入格式”（input_format）两个维度，正是隐式阳性常见的形态。但 fuzz-mdhtml 直接把输入前 8 字节当作 parser_flags / renderer_flags，任何新 flag 位都可能被置上，后续字节又可自由构造 || 语法；定额 fuzz 下 spoiler 的识别、配对与渲染代码在多个种子中被执行。harness 无需修改，属于隐式 mix(configuration+input_format) 阴性。

## Rationale
This commit adds the spoiler extension: a new parser flag (MD_FLAG_SPOILER), the matching inline syntax (||text||), and HTML rendering of the new span type. On the surface this spans two dimensions, a new option value (configuration) and a new input format (input_format), the usual shape of a silent positive. But fuzz-mdhtml takes the first 8 input bytes as parser_flags/renderer_flags, so any new flag bit can be set, and the remaining bytes freely form || syntax; under the fuzz budget the spoiler detection, pairing and rendering code runs in several seeds. No harness update needed: silent mix(configuration+input_format) negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 8736,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 5222023,
    "gap_covered": [
     43,
     2
    ]
   },
   {
    "seed": 2,
    "execs": 5199899,
    "gap_covered": [
     43,
     2
    ]
   },
   {
    "seed": 3,
    "execs": 8069393,
    "gap_covered": [
     43,
     2
    ]
   }
  ]
 }
}
```
