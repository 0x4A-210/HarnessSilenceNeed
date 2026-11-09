# V3-24 — libcbor @ 031dc9eb7583

- label: **negative** / explicit / type `input_format` / introduced_by_this_change = None
- change: https://github.com/PJK/libcbor/commit/031dc9eb7583aaff47f2b0182ef0558c7f5c8870 (Decode all well-formed simple values (#445))
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['oss-fuzz/cbor_load_fuzzer.cc'] (target `cbor_load_fuzzer`)

## 理由
本次提交让解码器接受所有格式良好的 CBOR simple value（此前未定义的 simple value 被拒绝），扩大了可接受的输入格式，改动位于 cbor_load() 使用的 builder 回调中。cbor_load_fuzzer 直接把原始字节交给 cbor_load()，新的输入形态由 fuzzer 自然产生，harness 的调用与释放逻辑无需调整：变更前后都能编译，回放无新崩溃，新增分支被覆盖。harness 仍然充分，属于显式 input_format 阴性。

## Rationale
This commit makes the decoder accept every well-formed CBOR simple value (previously unassigned simple values were rejected), widening the accepted input format; the change sits in the builder callbacks used by cbor_load(). cbor_load_fuzzer hands raw bytes to cbor_load(), the new input shapes arise naturally from fuzzing, and the harness's call and release logic needs no change: it builds before and after, replay shows no new crash, and the new branch is covered. The harness stays adequate: explicit input_format negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 2262,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0
}
```
