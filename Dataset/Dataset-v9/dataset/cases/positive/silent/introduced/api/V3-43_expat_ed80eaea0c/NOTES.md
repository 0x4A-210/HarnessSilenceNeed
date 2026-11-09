# V3-43 — expat @ ed80eaea0ce7

- label: **positive** / silent / type `api` / introduced_by_this_change = True
- change: https://github.com/libexpat/libexpat/commit/ed80eaea0ce7179b56713fb22fe933b993aee814 (Merge pull request #1183 from libexpat/issue-47-improve-protection-against-hash-flooding)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['expat/fuzz/xml_parse_fuzzer.c'] (target `xml_parse_fuzzer_UTF-8`)
- fix H: https://github.com/libexpat/libexpat/commit/fc71c2ca0e8c2920cbcbddd7a127f5a4566bb93c

## 理由
本次合并（PR #1183，加强 hash flooding 防护）新增公开 API XML_SetHashSalt16Bytes()：用 16 字节熵设置 128 位 hash salt，并把旧的 XML_SetHashSalt()（只接受 unsigned long）标为 deprecated。harness xml_parse_fuzzer.c 未修改，仍然只调用旧的 XML_SetHashSalt，照常编译运行、不报错；新函数的 NULL 检查、parserBusy 保护、sip_tokey 写入 128 位 salt 等行在定额 fuzz 下执行 0 次。维护者在 b019c28f（经 PR #1362 合并进主线 fc71c2ca）把 harness 迁到 XML_SetHashSalt16Bytes，同语料下这些行被覆盖。M^1 时该 API 不存在，缺口由本次引入，属于隐式 api 阳性。

## Rationale
This merge (PR #1183, stronger hash-flooding protection) adds the public API XML_SetHashSalt16Bytes(), which sets the 128-bit hash salt from 16 bytes of entropy, and deprecates the old XML_SetHashSalt() that takes an unsigned long. The harness xml_parse_fuzzer.c is unchanged and still calls only the old XML_SetHashSalt; it builds and runs without complaint, while the new function's NULL checks, parserBusy guard and sip_tokey into the 128-bit salt execute zero times under the fuzz budget. The maintainers moved the harness to XML_SetHashSalt16Bytes in b019c28f (merged to mainline in fc71c2ca, PR #1362), after which these lines are covered on the same corpus. The API does not exist at M^1, so the gap is introduced by this change: a silent api positive.

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
    "execs": 18262225,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 15233629,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 17048041,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 15281332,
    "gap_covered": [
     7
    ]
   },
   {
    "seed": 2,
    "execs": 12160542,
    "gap_covered": [
     7
    ]
   }
  ]
 },
 "applies_to_parent": false
}
```
