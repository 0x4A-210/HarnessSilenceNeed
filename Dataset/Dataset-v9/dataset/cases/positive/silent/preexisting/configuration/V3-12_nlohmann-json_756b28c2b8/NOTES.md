# V3-12 — nlohmann-json @ 756b28c2b85d

- label: **positive** / silent / type `configuration` / introduced_by_this_change = False
- change: https://github.com/nlohmann/json/commit/756b28c2b85d668c9e74e3fc3c4688039ebc2901 (Keep a NUL byte ending a // comment as the end of input (#5696))
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['tests/src/fuzzer-parse_json.cpp'] (target `parse_afl_fuzzer`)
- fix H: https://github.com/nlohmann/json/commit/eb74fe2ab786ecb3e9188b5263cb90a7d7f93b54

## 理由
本次提交修复 #5659：在默认的 NUL 处理方式下（未定义 JSON_STRICT_NUL_HANDLING），// 单行注释遇到 NUL 字节时，scan_comment() 把 NUL 当作注释结束符一并读走，scan() 因而看不到输入结束，后续的 get() 会越过 NUL 继续读取。修复后遇到 NUL 先 unget() 再返回，由 scan() 将其识别为输入结束。改动全部位于 lexer::scan_comment() 中，而 scan() 只有在调用方传入 ignore_comments = true 时才会调用 scan_comment()。harness（tests/src/fuzzer-parse_json.cpp）一直以默认参数调用 json::parse(data, data + size)，自 3.9.0 引入 ignore_comments 以来从未打开这一选项。注释扫描代码照常编译、插桩，但在 fuzz 中始终执行不到。harness 照常构建运行，只是静默漏掉了这段代码；该配置缺口在本次变更之前就已存在。维护者在 eb74fe2ab 中让 harness 分别以 ignore_comments = false 和 true 解析输入。属于非本次引入的隐式 configuration 退化。

## Rationale
This commit fixes #5659: with the default NUL handling (JSON_STRICT_NUL_HANDLING not defined), a NUL byte that ends a `//` comment was consumed by scan_comment() as a comment terminator, so scan() never saw the end of input and the next get() kept reading past the NUL. The fix ungets the NUL and returns, so scan() reports it as end of input. All changed logic is in lexer::scan_comment(), which scan() calls only when the caller passes ignore_comments = true. The harness (tests/src/fuzzer-parse_json.cpp) has called json::parse(data, data + size) with default arguments ever since ignore_comments was introduced in 3.9.0, and never enables it, so the comment scanner is compiled and instrumented but never runs under fuzzing. The harness builds and runs normally while silently missing this code, and the configuration gap predates this change. The maintainer fix eb74fe2ab makes the harness parse the input with ignore_comments = false and true. Pre-existing silent configuration degradation.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok",
  "h(fix) x lib(M)": "ok"
 },
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 9611165,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 16369866,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 8599386,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 3644860,
    "gap_covered": [
     4
    ]
   },
   {
    "seed": 2,
    "execs": 3479950,
    "gap_covered": [
     4
    ]
   }
  ]
 },
 "fuzz_Mparent_replay": {
  "without_fix": [
   {
    "seed": 1,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": "n/a (replay)",
    "gap_covered": [
     1
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     1
    ]
   }
  ]
 },
 "applies_to_parent": true
}
```
