# V3-25 — cmark @ d8de8c7686e4

- label: **negative** / explicit / type `configuration` / introduced_by_this_change = None
- change: https://github.com/commonmark/cmark/commit/d8de8c7686e439ea6ae0e659ef5a86a16d1262d0 (re2c: Disable UTF-8)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['fuzz/cmark-fuzz.c'] (target `cmark_fuzzer`)

## 理由
本次提交改变扫描器生成配置：在 Makefile 中关闭 re2c 的 UTF-8 模式并重新生成 src/scanners.c（约 4000 行变化），属于构建/代码生成配置的变化，且生成的扫描器正是 cmark_fuzzer 每次解析都会调用的代码。harness 的构建（CMake 编译 libcmark 后链接 fuzz/cmark-fuzz.c）不依赖该生成选项：变更前后都能编译，回放语料无新崩溃，新生成的扫描代码被大量执行。harness 仍然充分，属于显式 configuration 阴性。

## Rationale
This commit changes the scanner generation configuration: re2c's UTF-8 mode is disabled in the Makefile and src/scanners.c is regenerated (about 4000 changed lines), a build/code-generation configuration change, and the generated scanners are code cmark_fuzzer calls on every parse. The harness build (CMake builds libcmark, then links fuzz/cmark-fuzz.c) does not depend on that generator option: it builds before and after, replay shows no new crash, and the regenerated scanner code is executed heavily. The harness stays adequate: explicit configuration negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 690,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.256
}
```
