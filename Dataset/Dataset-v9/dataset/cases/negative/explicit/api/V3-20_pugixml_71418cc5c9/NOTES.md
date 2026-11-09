# V3-20 — pugixml @ 71418cc5c971

- label: **negative** / explicit / type `api` / introduced_by_this_change = None
- change: https://github.com/zeux/pugixml/commit/71418cc5c971346e009e2d76084cb569ced3add9 (Fix xml_parse_result::encoding for empty document load)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['tests/fuzz_parse.cpp'] (target `fuzz_parse`)

## 理由
本次提交修改 load_buffer 系列接口对空文档的返回值：size==0 时提前返回的 xml_parse_result 现在会带上检测到的 encoding。fuzz_parse 正是用 doc.load_buffer() 以三种解析选项加载原始输入，变更直接落在 harness 调用的接口上。但 harness 只调用接口、不依赖 encoding 字段，签名和调用方式都没变：变更前后都能编译，回放固定语料无新崩溃，空输入即可执行到新增的赋值分支。harness 仍然充分，属于显式 api 阴性。

## Rationale
This commit changes what the load_buffer family returns for empty documents: the early-return xml_parse_result for size==0 now carries the detected encoding. fuzz_parse loads raw input with doc.load_buffer() under three option sets, so the change lands directly on an API the harness calls. The harness does not depend on the encoding field and neither the signature nor the calling convention changes: it builds before and after, corpus replay shows no new crash, and the empty input executes the new branch. The harness stays adequate: explicit api negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 6,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0
}
```
