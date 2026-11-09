# V3-29 — tinyxml2 @ 26ab0bd591bd

- label: **negative** / explicit / type `mix` ['lifecycle', 'state'] / introduced_by_this_change = None
- change: https://github.com/leethomason/tinyxml2/commit/26ab0bd591bdfb7991cc76e3d1348ddf8aa33934 (Merge branch 'master' of github.com:leethomason/tinyxml2)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: oss ['projects/tinyxml2/xmltest.cpp'] (target `xmltest`)

## 理由
本次提交为 XMLNode 析构引入快速路径：节点即将销毁时不再逐个维护 _firstChild/_lastChild 及兄弟节点的 _prev/_next 链接，只把子节点的 _parent 清零后直接 DeleteNode。这同时涉及对象销毁（lifecycle）与销毁过程中树结构状态不再保持一致（state）两个维度，且落在 xmltest 每个输入都会经过的 XMLDocument 析构上。harness 只解析后随作用域销毁文档，销毁期间不再访问树：变更前后都能编译，回放语料无新崩溃，新的析构循环被执行。harness 仍然充分，属于显式 mix(lifecycle+state) 阴性。

## Rationale
This commit adds a fast path to XMLNode destruction: when a node is dying, _firstChild/_lastChild and the siblings' _prev/_next links are no longer maintained one by one; children only get _parent zeroed before DeleteNode. Two dimensions are involved, object destruction (lifecycle) and the tree no longer being kept consistent during teardown (state), both on the XMLDocument destructor that xmltest runs for every input. The harness only parses and lets the document go out of scope, never touching the tree during teardown: it builds before and after, replay shows no new crash, and the new destructor loop runs. The harness stays adequate: explicit mix(lifecycle+state) negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 780,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0
}
```
