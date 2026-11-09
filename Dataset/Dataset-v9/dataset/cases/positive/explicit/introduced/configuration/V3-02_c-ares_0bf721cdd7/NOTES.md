# V3-02 — c-ares @ 0bf721cdd7f6

- label: **positive** / explicit / type `configuration` / introduced_by_this_change = True
- change: https://github.com/c-ares/c-ares/commit/0bf721cdd7f64b893c4ad015c341de680617411b (Reorganize source tree (#349))
- origin: real_commit; route: ossfuzz_signal; gt: maintainer_fix
- harness: intree ['test/ares-test-fuzz.c'] (target `ares_parse_reply_fuzzer`)
- fix H: https://github.com/google/oss-fuzz/commit/008f2177e428aa7644117c551eeaff376b28bb15

## 理由
该提交重组源码树：公共头文件移入 include/，库源码与产物移入 src/lib/。harness 的构建配置（OSS-Fuzz build.sh）仍用 -I. 查找 ares.h、链接 .libs/libcares.a，test/ares-test-fuzz.c 因找不到 ares.h 而编译失败。harness 代码本身未变，坏在构建配置上，属于本次引入的显式 configuration 退化；维护者两天后在 oss-fuzz 008f2177e 把路径改为 -Iinclude -Isrc/lib 与 src/lib/.libs/libcares.a。

## Rationale
The commit reorganises the source tree: public headers move to include/, library sources and the built archive to src/lib/. The harness build configuration (OSS-Fuzz build.sh) still compiles with -I. and links .libs/libcares.a, so test/ares-test-fuzz.c fails to compile (ares.h not found). The harness code itself is unchanged; its build configuration is what broke. Explicit configuration degradation introduced by this change; fixed two days later in oss-fuzz 008f2177e (-Iinclude -Isrc/lib, src/lib/.libs/libcares.a).

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
