# V3-22 — cjson @ 542fb0eadd3d

- label: **negative** / explicit / type `lifecycle` / introduced_by_this_change = None
- change: https://github.com/DaveGamble/cJSON/commit/542fb0eadd3db62630c1eb958e685f1d8e30694e (Set free'd pointers to NULL whenever they are not reassigned immediately after)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['fuzzing/cjson_read_fuzzer.c'] (target `cjson_read_fuzzer`)

## 理由
本次提交在 cJSON 的释放路径上把已释放指针置为 NULL（cJSON_Delete、打印缓冲区的释放与重分配等），属于对象销毁与所有权（lifecycle）方面的改动，且落在 harness 每次都会走到的 cJSON_Delete()/打印函数上。harness 的创建—打印—释放顺序不受影响，不会二次释放：变更前后都能编译，回放语料无新崩溃，新增的置空语句被执行到。harness 仍然充分，属于显式 lifecycle 阴性。

## Rationale
This commit sets freed pointers to NULL on cJSON's release paths (cJSON_Delete, freeing and reallocating print buffers), a lifecycle/ownership change on functions the harness reaches on every input (cJSON_Delete() and the print functions). The harness's create-print-delete order is unaffected and nothing is freed twice: it builds before and after, replay shows no new crash, and the new NULL assignments are executed. The harness stays adequate: explicit lifecycle negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 14,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.375,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 25592776,
    "gap_covered": [
     3
    ]
   },
   {
    "seed": 2,
    "execs": 15539062,
    "gap_covered": [
     3
    ]
   },
   {
    "seed": 3,
    "execs": 32533570,
    "gap_covered": [
     3
    ]
   }
  ]
 }
}
```
