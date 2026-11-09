# V3-33 — zstd @ 26486db9ab20

- label: **negative** / silent / type `configuration` / introduced_by_this_change = None
- change: https://github.com/facebook/zstd/commit/26486db9ab20fdd8b8c77cdbafd46a338a3e1199 (Merge pull request #2819 from terrelln/ldm-hash-rate-log)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['tests/fuzz/simple_round_trip.c'] (target `simple_round_trip`)

## 理由
本次提交修改运行时压缩参数 ZSTD_c_ldmHashRateLog 的取值校验：原先只检查上界（value > ZSTD_WINDOWLOG_MAX - ZSTD_HASHLOG_MIN 时报错），现在 0 表示使用默认值并跳过检查，非 0 值改用统一的 BOUNDCHECK 同时检查上下界。表面上这是容易使 harness 失效的配置变化：参数校验一旦变严，harness 对 ZSTD_CCtx_setParameter() 返回值的断言（FUZZ_ZASSERT）就可能失败；新拆出的“0 即默认”分支也可能在 harness 的取值下到不了。但 simple_round_trip 通过 FUZZ_setRandomParameters() 在输入上用 [ZSTD_LDM_HASHRATELOG_MIN, ZSTD_LDM_HASHRATELOG_MAX] 内的随机值设置该参数，取值包含 0 且不越过新边界，两个分支都会执行，断言不会失败。变更前后都能构建，语料回放没有新崩溃，改动行在定额 fuzz 的多个种子中被覆盖，harness 无需修改。属于隐式 configuration 阴性。

## Rationale
This commit changes the validation of the runtime compression parameter ZSTD_c_ldmHashRateLog: it used to check only an upper bound (error if value > ZSTD_WINDOWLOG_MAX - ZSTD_HASHLOG_MIN); now 0 means the default and skips the check, and any other value goes through the common BOUNDCHECK of both bounds. On the surface this kind of configuration change can break a harness: stricter validation can make the harness's FUZZ_ZASSERT on the result of ZSTD_CCtx_setParameter() fail, and the new '0 = default' branch may be unreachable with the values the harness uses. But simple_round_trip sets this parameter through FUZZ_setRandomParameters() to a random value in [ZSTD_LDM_HASHRATELOG_MIN, ZSTD_LDM_HASHRATELOG_MAX], a range that includes 0 and stays inside the new bounds, so both branches run and the assertion holds. It builds before and after, corpus replay shows no new crash, and the changed lines are covered in several seeds of the budgeted fuzzing; the harness needs no update: silent configuration negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 25942,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 1.0,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 258089,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 2,
    "execs": 252320,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 3,
    "execs": 259691,
    "gap_covered": [
     2
    ]
   }
  ]
 }
}
```
