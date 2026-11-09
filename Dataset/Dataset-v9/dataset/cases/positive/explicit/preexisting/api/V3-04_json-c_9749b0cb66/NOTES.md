# V3-04 — json-c @ 9749b0cb66b3

- label: **positive** / explicit / type `api` / introduced_by_this_change = False
- change: https://github.com/json-c/json-c/commit/9749b0cb66b32ddac4bbbca28dd9009968722a9f (When serializing with JSON_C_TO_STRING_PRETTY set, keep the opening and closing curly or square braces on same line for empty objects or arrays.  Issue #778.)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree ['fuzz/tokener_parse_ex_fuzzer.cc'] (target `tokener_parse_ex_fuzzer`)
- fix H: https://github.com/json-c/json-c/commit/41865375573ed9fa5cc00903ee327ade8a871839

## 理由
本次提交修改 JSON_C_TO_STRING_PRETTY 模式下空对象/空数组的序列化，正是 harness 想驱动的路径（它试图以 PRETTY|SPACED 调用序列化）。但从 4902f9cb87 起，in-tree 的 tokener_parse_ex_fuzzer.cc 用两个参数调用只接受一个参数的 json_object_to_json_string()，并遍历未声明的变量 jobj，harness 根本无法编译。变更前后都编译失败，退化早于本次 diff，属于非本次引入的显式 api 退化；维护者在 4186537557 改用 json_object_to_json_string_ext() 并遍历 obj。

## Rationale
This commit changes how empty objects/arrays are serialised under JSON_C_TO_STRING_PRETTY, exactly the path the harness means to drive (it tries to serialise with PRETTY|SPACED). But since 4902f9cb87 the in-tree tokener_parse_ex_fuzzer.cc calls the one-argument json_object_to_json_string() with two arguments and iterates an undeclared jobj, so the harness does not compile. It fails before and after this change; the degradation predates the diff. Pre-existing explicit api degradation, fixed upstream in 4186537557 (json_object_to_json_string_ext(), iterate obj).

## Verification summary
```json
{
 "compile_matrix": {
  "h(W0^1) x lib(W0^1)": "ok",
  "h(W0) x lib(W0)": "fail",
  "h(M^1) x lib(M^1)": "fail",
  "h(M^1) x lib(M)": "fail",
  "h(fix) x lib(M)": "ok"
 },
 "explicit_signal": "compile_failure"
}
```
