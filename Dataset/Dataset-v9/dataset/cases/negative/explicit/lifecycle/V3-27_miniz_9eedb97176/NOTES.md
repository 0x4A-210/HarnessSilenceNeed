# V3-27 — miniz @ 9eedb9717640

- label: **negative** / explicit / type `lifecycle` / introduced_by_this_change = None
- change: https://github.com/richgel999/miniz/commit/9eedb97176408008a2263cef9b4bac5c7f955d4f (Clear whole tree to prevent uninitialized value)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['tests/uncompress_fuzzer.c'] (target `uncompress_fuzzer`)

## 理由
本次提交修改解压器内部 Huffman 树的初始化：改为按当前树类型清零整棵树（tinfl_clear_tree），以消除未初始化读取，属于对象初始化（lifecycle）方面的改动，且位于 uncompress() → tinfl_decompress() 这条 harness 每次都会走的路径上。harness 只调用 uncompress() 并释放缓冲区，不接触内部结构：变更前后都能编译，回放语料无新崩溃，新增的清零函数被执行。harness 仍然充分，属于显式 lifecycle 阴性。

## Rationale
This commit changes how the decompressor initialises its internal Huffman trees, clearing the whole tree for the current type (tinfl_clear_tree) to avoid uninitialised reads: an object-initialisation (lifecycle) change on the uncompress() -> tinfl_decompress() path the harness takes on every input. The harness only calls uncompress() and frees its buffer, never touching internal structures: it builds before and after, replay shows no new crash, and the new clearing function runs. The harness stays adequate: explicit lifecycle negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 17,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 9882894,
    "gap_covered": [
     8
    ]
   },
   {
    "seed": 2,
    "execs": 2237639,
    "gap_covered": [
     8
    ]
   },
   {
    "seed": 3,
    "execs": 4096391,
    "gap_covered": [
     8
    ]
   }
  ]
 }
}
```
