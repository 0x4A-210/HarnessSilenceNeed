# V3-36 — expat @ 34b598c5f594

- label: **negative** / silent / type `state` / introduced_by_this_change = None
- change: https://github.com/libexpat/libexpat/commit/34b598c5f594b015c513c73f06e7ced3323edbf1 (Merge pull request #789 from SonyMobile/partial-token-perf)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['expat/fuzz/xml_parse_fuzzer.c'] (target `xml_parse_fuzzer_UTF-8`)

## 理由
本次提交为分块解析引入“重解析延迟”（reparse deferral）：解析器新增状态字段（上次尝试的长度、是否延迟等），在遇到未完成的大 token 时推迟重新解析。这是新增内部状态与复用契约的改动，表面上与隐式 state 阳性相同。但 xml_parse_fuzzer 对同一个解析器按块多次调用 XML_Parse，并对奇数长度输入调用 XML_ParserReset 复用解析器，新状态的设置、判断与重置在定额 fuzz 下于多个种子中被执行。harness 无需修改，属于隐式 state 阴性。

## Rationale
This commit introduces reparse deferral for chunked parsing: the parser gains new state fields (last attempted length, whether to defer) and postpones re-parsing when a large token is still incomplete. This adds internal state and changes the reuse contract, which on the surface matches a silent state positive. But xml_parse_fuzzer calls XML_Parse repeatedly on the same parser and reuses it via XML_ParserReset for odd-sized inputs, so setting, testing and resetting the new state runs in several seeds under the fuzz budget. No harness update needed: silent state negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 8907,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.803,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 14272868,
    "gap_covered": [
     49
    ]
   },
   {
    "seed": 2,
    "execs": 15168427,
    "gap_covered": [
     49
    ]
   },
   {
    "seed": 3,
    "execs": 24226229,
    "gap_covered": [
     49
    ]
   }
  ]
 }
}
```
