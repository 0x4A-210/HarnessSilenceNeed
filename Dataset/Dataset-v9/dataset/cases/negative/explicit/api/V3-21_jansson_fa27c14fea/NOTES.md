# V3-21 — jansson @ fa27c14fea39

- label: **negative** / explicit / type `api` / introduced_by_this_change = None
- change: https://github.com/akheron/jansson/commit/fa27c14fea399c3bfdef663d1d4c3e2300b15bdb (Merge pull request #731 from indel-ag/unpackerrorkey)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['test/ossfuzz/json_pack_unpack_fuzzer.cc'] (target `json_pack_unpack_fuzzer`)

## 理由
本次提交改进 json_unpack() 系列在解包失败时的错误信息（在 error 文本中带上出错的 key），改动遍布 pack_unpack.c 的 unpack 路径，正是 json_pack_unpack_fuzzer 调用的接口。接口签名与返回约定不变，harness 只检查返回值、不解析 error 文本：变更前后均可编译，回放语料无新崩溃，新增的错误拼接代码被语料执行到。harness 仍然充分，属于显式 api 阴性。

## Rationale
This commit improves the error message of the json_unpack() family on failure (the offending key is now included in the error text); the changes span the unpack paths of pack_unpack.c, which json_pack_unpack_fuzzer calls. The signature and return conventions are unchanged and the harness only checks return values, never the error text: it builds before and after, replay shows no new crash, and the new error-formatting code is executed by the corpus. The harness stays adequate: explicit api negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 108,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.179
}
```
