# V3-23 — libyaml @ 840b65c40675

- label: **negative** / explicit / type `input_format` / introduced_by_this_change = None
- change: https://github.com/yaml/libyaml/commit/840b65c40675e2d06bf40405ad3f12dec7f35923 (Fix closing flow sequence after explicit key)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: oss ['projects/libyaml/libyaml_parser_fuzzer.c'] (target `libyaml_parser_fuzzer`)

## 理由
本次提交修正 YAML 语法处理：在显式 key（?）之后关闭 flow sequence 时的解析行为（parser.c）。这是可接受输入格式的变化，libyaml_parser_fuzzer 对任意输入反复调用 yaml_parser_parse()，正好驱动该语法分支。harness 不对输入加任何封装或限制，构造的输入在变更后依然有效：变更前后都能编译，回放无新崩溃，新增分支被覆盖。harness 仍然充分，属于显式 input_format 阴性。

## Rationale
This commit corrects how a flow sequence is closed after an explicit key (?) in parser.c, a change to the accepted input syntax. libyaml_parser_fuzzer calls yaml_parser_parse() on arbitrary input and drives exactly this grammar branch; it adds no framing or restriction to the input, so the inputs it produces stay valid after the change: it builds before and after, replay shows no new crash, and the new branch is covered. The harness stays adequate: explicit input_format negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 3258,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0
}
```
