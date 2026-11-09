# V3-46 — nlohmann-json @ 8feaf8dc94a8

- label: **positive** / explicit / type `input_format` / introduced_by_this_change = True
- change: https://github.com/nlohmann/json/commit/8feaf8dc94a88393510637af36a24163c95a1b45 (:boom: implemented new handling of NaN and INF #70 #329 #388)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['test/src/fuzzer-parse_cbor.cpp'] (target `parse_cbor_fuzzer`)
- fix H: https://github.com/nlohmann/json/commit/b026591e9e566b3ecd80a0161bd845756986c4b3

## 理由
本次提交改变了输入编码中非有限浮点数的解码方式：此前 CBOR / MessagePack 输入里的 NaN、Inf 在构造值时一律被替换成 null；本次起按原样保存为 NaN/Inf（仅在 dump() 输出时写成 null）。CBOR harness 的往返检查写的是 assert(j1 == j2)：同一份输入解码出的值，经 to_cbor 再 from_cbor 后要求相等。现在任何带 NaN 编码的输入（如 3 字节的半精度 NaN F9 7E 00）都会解码出 NaN，而 NaN != NaN，harness 自己的断言立即 abort，栈顶就在 harness 的 LLVMFuzzerTestOneInput（fuzzer-parse_cbor.cpp:45）；同一输入在 M^1 上解码为 null，断言通过。M^1 不失败，失败由本次引入，属于显式 input_format 阳性（输入编码的解码语义变化触发 harness 侧断言）。维护者两天后在 b026591e 把断言改为比较再次序列化的结果。注：该变化也可看作 basic_json 值语义（api）的变化；这里按“输入中 NaN 编码的解码方式变化”归为 input_format。

## Rationale
This commit changes how non-finite floating-point values in the input encodings are decoded: before it, a NaN or Inf in CBOR / MessagePack input was replaced by null when the value was built; from now on it is kept as NaN/Inf (and written as null only by dump()). The CBOR harness checks its round trip with assert(j1 == j2): the value decoded from the input must equal the value decoded again after to_cbor. Now every input carrying a NaN encoding (e.g. the 3-byte half-precision NaN F9 7E 00) decodes to NaN, and since NaN != NaN the harness's own assertion aborts at once, in the harness's LLVMFuzzerTestOneInput (fuzzer-parse_cbor.cpp:45); at M^1 the same input decodes to null and the assertion holds. No failure at M^1, so it is introduced by this change: an explicit input_format positive (a change in how an input encoding is decoded trips a harness-side assertion). The maintainers changed the assertion two days later (b026591e) to compare the re-serialized bytes. Note: the change can also be read as a change of basic_json value semantics (api); it is classified here as input_format because what changed is how a NaN encoding in the input is decoded.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok",
  "h(fix) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 1984,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 5,
  "crashes_fixed_harness_lib_M": 0
 },
 "explicit_signal": "runtime_failure_on_replay"
}
```
