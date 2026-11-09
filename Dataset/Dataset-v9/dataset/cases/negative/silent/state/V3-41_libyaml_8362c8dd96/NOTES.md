# V3-41 — libyaml @ 8362c8dd96b6

- label: **negative** / silent / type `state` / introduced_by_this_change = None
- change: https://github.com/yaml/libyaml/commit/8362c8dd96b644bda4e4d24cc405ef7f0e642d21 (Enforce nesting limit in scanner)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: oss ['projects/libyaml/libyaml_scanner_fuzzer.c'] (target `libyaml_scanner_fuzzer`)

## 理由
本次提交在扫描器的 yaml_parser_increase_flow_level() 中加入嵌套深度上限：flow_level 这一跨 token 维护的内部状态计数一旦达到 MAX_NESTING_LEVEL 就报扫描错误。提交说明特别指出此前只有 parser.c 检查深度，直接调用 yaml_parser_scan() 的使用者没有保护——而 scanner harness 正是这样的调用者，看上去像“库的内部状态约束变了、直接驱动扫描器的 harness 可能失配”。但 harness 只是循环调用 yaml_parser_scan() 直到出错或 STREAM-END，对新的错误返回按正常的失败分支处理；改动行在定额 fuzz 的多个种子中被执行，ASan 回放无新崩溃。harness 无需修改，属于隐式 state 阴性。

## Rationale
This commit adds a nesting-depth limit to the scanner's yaml_parser_increase_flow_level(): once flow_level, internal state maintained across tokens, reaches MAX_NESTING_LEVEL a scanner error is raised. The commit message points out that only parser.c checked the depth, so direct yaml_parser_scan() callers had no protection - and the scanner harness is exactly such a caller, so it looks like 'the library's internal state constraint changed and a harness driving the scanner directly may now mismatch'. But the harness just calls yaml_parser_scan() in a loop until an error or STREAM-END and handles the new error return on its ordinary failure path; the changed lines run in several seeds of the budgeted campaign and ASan replay shows no new crash. No harness change is needed: a silent state negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 3128,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 6262002,
    "gap_covered": [
     4
    ]
   },
   {
    "seed": 2,
    "execs": 5734583,
    "gap_covered": [
     4
    ]
   },
   {
    "seed": 3,
    "execs": 8539260,
    "gap_covered": [
     4
    ]
   }
  ]
 }
}
```
