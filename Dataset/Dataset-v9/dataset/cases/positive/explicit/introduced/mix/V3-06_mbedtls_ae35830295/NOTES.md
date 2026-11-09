# V3-06 — mbedtls @ ae3583029507

- label: **positive** / explicit / type `mix` ['api', 'lifecycle'] / introduced_by_this_change = True
- change: https://github.com/Mbed-TLS/mbedtls/commit/ae35830295073b6ea7f327e6e42ccdc41dda5ed1 (Merge pull request #4661 from mpg/make-blinding-mandatory)
- origin: real_commit_lib_hunks_only; route: coupled_split; gt: coupled_commit
- harness: intree ['programs/fuzz/fuzz_privkey.c'] (target `fuzz_privkey`)
- fix H: https://github.com/Mbed-TLS/mbedtls/commit/6d2479516c8373ed8a335f664ee4e05c4d12dd62

## 理由
该提交（“blinding 强制化”）给 mbedtls_pk_parse_key() 增加了必选的 f_rng/p_rng 参数，并要求解析私钥时可用 RNG（例如从 EC 私钥推导公钥时会调用 f_rng 做 blinding）。只看库部分改动：旧 fuzz_privkey.c 仍以 5 个参数调用，编译失败，这是 api 维度。仅补参数也不够：同一提交里维护者给 harness 传的是 (dummy_random, NULL)，而 dummy_random 会把 NULL 当作 ctr_drbg 上下文使用，回放语料时 EC 私钥（如 *nopub*）触发空指针崩溃，必须先初始化并 seed 一个 ctr_drbg，这是 lifecycle 维度。两个维度各自独立要求更新 harness，属于本次引入的显式 mix(api+lifecycle) 退化；完整修复见 6d2479516c。

## Rationale
This commit (making blinding mandatory) adds mandatory f_rng/p_rng arguments to mbedtls_pk_parse_key() and requires a usable RNG while parsing private keys (deriving an EC public key now calls f_rng for blinding). Library part only: the old fuzz_privkey.c still calls it with 5 arguments and fails to compile (api component). Adding the arguments is not enough: in this same commit the maintainers passed (dummy_random, NULL), and dummy_random uses NULL as a ctr_drbg context, so replaying the corpus crashes on EC private keys (e.g. *nopub*). A ctr_drbg must be initialised and seeded first (lifecycle component). Each component independently requires a harness update: explicit mix(api+lifecycle) degradation introduced by this change; complete fix in 6d2479516c.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "fail",
  "h(fix) x lib(M)": "ok"
 },
 "explicit_signal": "compile_failure"
}
```
