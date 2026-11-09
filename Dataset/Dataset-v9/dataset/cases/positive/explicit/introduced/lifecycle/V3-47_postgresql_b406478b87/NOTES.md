# V3-47 — postgresql @ b406478b87e2

- label: **positive** / explicit / type `lifecycle` / introduced_by_this_change = True
- change: https://github.com/postgres/postgres/commit/b406478b87e2234c0be4ca4105eee3bb466a646b (process startup: Always call Init[Auxiliary]Process() before BaseInit().)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: oss ['projects/postgresql/fuzzer/simple_query_fuzzer.c', 'projects/postgresql/fuzzer/fuzzer_initialize.c'] (target `simple_query_fuzzer`)
- fix H: https://github.com/google/oss-fuzz/commit/0ec1cb2549775c68bac6f446818668784d131ad9

## 理由
M 统一进程启动顺序：BaseInit() 不再调用 InitCommunication()/CreateSharedMemoryAndSemaphores()，要求先建共享内存、InitProcess() 再 BaseInit()。H0 的 FuzzerInitialize 仍按旧顺序 BaseInit(); InitProcess();，共享内存从未创建，InitProcess 直接 PANIC 中止。S0 正常，本次引入。H 的提交标题直接引用 Postgres commit b406478b，把顺序改为 CreateSharedMemoryAndSemaphores(); InitProcess(); BaseInit();。

## Rationale
M unifies the process startup order: BaseInit() no longer calls InitCommunication()/CreateSharedMemoryAndSemaphores(), so callers must create shared memory and call InitProcess() before BaseInit(). FuzzerInitialize in the harness H0 still calls BaseInit(); InitProcess(); in the old order, shared memory is never created, and InitProcess() aborts with PANIC. The same harness works with S0 (M^1), so the degradation is introduced by this change. The title of the fix H cites Postgres commit b406478b; it changes the order to CreateSharedMemoryAndSemaphores(); InitProcess(); BaseInit();.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok",
  "h(fix) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 1,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 1,
  "crashes_fixed_harness_lib_M": 0
 },
 "explicit_signal": "runtime_failure_on_replay"
}
```
