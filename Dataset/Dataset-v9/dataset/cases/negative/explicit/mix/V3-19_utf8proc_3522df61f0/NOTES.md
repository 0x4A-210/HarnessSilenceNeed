# V3-19 — utf8proc @ 3522df61f03e

- label: **negative** / explicit / type `mix` ['api', 'input_format'] / introduced_by_this_change = None
- change: https://github.com/JuliaStrings/utf8proc/commit/3522df61f03ecb1e5787696c901b8bce23705855 (normalize_utf32: keep grapheme-break sentinels when stripping control characters (#371))
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['test/fuzzer.c'] (target `utf8proc_fuzzer`)

## 理由
本次提交修改 utf8proc_normalize_utf32() 在 UTF8PROC_STRIPCC 选项下的语义：剥除控制字符时保留字素分界哨兵（-1），涉及选项组合的行为（api）以及输入中的特殊码点/哨兵序列（input_format）两个维度。改动直接落在 harness 调用的 normalize_utf32 上，且 harness（2026-09-28 修复后）会以 STRIPCC 等多种选项把原始字节作为 UTF-32 数组传入，也会经 utf8proc_map(CHARBOUND|…) 产生哨兵。harness 的调用方式与新语义兼容：变更前后都能编译，回放语料无新崩溃，新增分支被执行。harness 仍然充分，属于显式 mix(api+input_format) 阴性。

## Rationale
This commit changes the semantics of utf8proc_normalize_utf32() under UTF8PROC_STRIPCC: grapheme-break sentinels (-1) are kept while control characters are stripped. Two dimensions are involved, the behaviour of an option combination (api) and special code points/sentinel sequences in the input (input_format). The change lands directly on normalize_utf32, which the harness calls: since its 2026-09-28 fix the harness passes raw bytes as a UTF-32 array under several options including STRIPCC, and utf8proc_map(CHARBOUND|...) produces sentinels. The harness's usage is compatible with the new semantics: it builds before and after, replay shows no new crash, and the new branch runs. The harness stays adequate: explicit mix(api+input_format) negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 684,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0
}
```
