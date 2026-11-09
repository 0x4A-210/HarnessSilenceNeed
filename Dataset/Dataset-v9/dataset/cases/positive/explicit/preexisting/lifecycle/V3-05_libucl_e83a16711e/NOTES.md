# V3-05 — libucl @ e83a16711eed

- label: **positive** / explicit / type `lifecycle` / introduced_by_this_change = False
- change: https://github.com/vstakhov/libucl/commit/e83a16711eedc9ee2219748f9a427f94b1bb70a5 (Merge pull request #412 from tregua87/fix-saved-comment-leak)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['tests/fuzzers/ucl_add_string_fuzzer.c'] (target `ucl_add_string_fuzzer`)
- fix H: https://github.com/vstakhov/libucl/commit/cfc517cf42a5d63ed76ca5e14de1de5be09f91f3

## 理由
本次提交修复了库在保存注释时的内存泄漏（ucl_parser.c / ucl_util.c），属于 ucl_add_string_fuzzer 驱动的解析路径。但该 harness 自 2020 年创建起，在 ucl_parser_get_error() 非空时直接 return，跳过了 ucl_parser_free()：每个触发解析错误的输入都会泄漏整个 parser。默认 sanitizer 设置下回放语料，LeakSanitizer 在变更前后都会对大量输入报告泄漏，分配栈落在 harness 的 ucl_parser_new() 调用上。OSS-Fuzz 只能在 options 里设 detect_leaks=0 规避，连带让本次修复的这类库内泄漏也无法被发现。退化早于本次 diff，属于非本次引入的显式 lifecycle 退化；维护者在 cfc517cf42 中补上错误路径的 ucl_parser_free()。

## Rationale
This commit fixes a library memory leak when saving comments (ucl_parser.c / ucl_util.c), on the parsing path that ucl_add_string_fuzzer drives. Since its creation in 2020, however, the harness returns as soon as ucl_parser_get_error() is non-NULL, skipping ucl_parser_free(): every input that causes a parse error leaks the whole parser. Replaying the corpus with default sanitizer settings, LeakSanitizer reports leaks on many inputs before and after this change, with the allocation stack at the harness's ucl_parser_new() call. OSS-Fuzz had to set detect_leaks=0 in the options file, which also hides library leaks of exactly the kind this commit fixes. Pre-existing explicit lifecycle degradation; fixed upstream in cfc517cf42 (ucl_parser_free() on the error path).

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok",
  "h(fix) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 12065,
  "crashes_lib_parent": 552,
  "crashes_lib_M": 552,
  "crashes_fixed_harness_lib_M": 0
 },
 "explicit_signal": "runtime_failure_on_replay"
}
```
