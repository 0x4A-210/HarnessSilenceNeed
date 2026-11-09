# V3-03 — jq @ 6ce3bdf3829f

- label: **positive** / explicit / type `configuration` / introduced_by_this_change = False
- change: https://github.com/jqlang/jq/commit/6ce3bdf3829fc15030e084119535b059f4f09e74 (fix: preserve numerical precision on unary negation (#3242))
- origin: real_commit; route: ossfuzz_signal; gt: maintainer_fix
- harness: intree ['tests/jq_fuzz_execute.cpp'] (target `jq_fuzz_execute`)
- fix H: https://github.com/google/oss-fuzz/commit/489ed279844fe422ce72dda8cfd081918c32fc7e

## 理由
本次提交只修改 jv.c 的一元取负数值精度，属于 jq_fuzz_execute 可达的代码。但早在 9727721（把 oniguruma 与 decNumber 移入 vendor/）时，harness 的构建配置仍链接 ./modules/oniguruma/src/.libs/libonig.a，从那以后所有 fuzz 目标都无法链接。这次变更没有修复该问题，harness 在变更前后都无法构建，属于非本次引入的显式 configuration 退化；维护者在 oss-fuzz 489ed2798 中改为 vendor/ 路径。

## Rationale
This commit only changes unary-negation precision in jv.c, which jq_fuzz_execute reaches. But since 9727721 (oniguruma and decNumber moved to vendor/), the harness build configuration still links ./modules/oniguruma/src/.libs/libonig.a, so every fuzz target fails to link. This change does not repair that: the harness is unbuildable before and after it. Pre-existing explicit configuration degradation; fixed in oss-fuzz 489ed2798 (vendor/ paths).

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(W0^1)": "ok",
  "h(M^1) x lib(W0)": "fail",
  "h(M^1) x lib(M^1)": "fail",
  "h(M^1) x lib(M)": "fail",
  "h(fix) x lib(M)": "ok"
 },
 "explicit_signal": "compile_failure"
}
```
