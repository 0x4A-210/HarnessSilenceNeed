# V3-08 — unbound @ 8c751d48a24b

- label: **positive** / explicit / type `mix` ['api', 'configuration'] / introduced_by_this_change = False
- change: https://github.com/NLnetLabs/unbound/commit/8c751d48a24b74e4ac0bbfd948d2b7e87dd87f6a (- Fix to print EDE text in readable form in output logs.)
- origin: real_commit; route: ossfuzz_signal; gt: maintainer_fix
- harness: oss ['projects/unbound/fuzz_1.c', 'projects/unbound/build.sh'] (target `fuzz_1_fuzzer`)
- fix H: https://github.com/google/oss-fuzz/commit/a5078ad416cfa781426ac091309c17214781b12f

## 理由
本次提交（8c751d48，把 EDE 文本以可读形式写入日志，改动 sldns/wire2str.c，位于 harness 的链接列表内）落在一个已持续数周的构建失败窗口里。OSS-Fuzz harness 同时有两个独立的显式缺陷，而且在 M^1 上都已存在：其一是构建配置。build.sh 用手写的 OBJECTS_TO_LINK 列表链接 fuzzer，而 a1c82ac5（2023-08-17，下游 DNS cookie）让 val_sigcrypt.o、edns.o 依赖新增的 util/rfc_1982.o 和 util/siphash.o，列表没有跟进，链接时报 compare_1982 / subtract_1982 / siphash 未定义。其二是 api。fdd5f8ff（2023-09-07）给 scrub_message() 增加了 struct module_qstate* 参数，fuzz_1.c、fuzz_4.c 仍按 7 个参数调用，编译报错。两者缺一不可：只修 build.sh，编译错误仍在；只修 fuzz_1.c/fuzz_4.c，链接仍失败。OSS-Fuzz 在 a5078ad4（2023-10-02，“unbound: fix build”）同时修复了两处。属于非本次引入的显式 mix(api+configuration) 阳性。

## Rationale
This commit (8c751d48, print EDE text in readable form in logs; it changes sldns/wire2str.c, which is on the harness's link list) lands inside a build-failure window that had lasted for weeks. The OSS-Fuzz harness has two independent explicit defects, both already present at M^1. The first is build configuration: build.sh links the fuzzers from a hand-written OBJECTS_TO_LINK list, and a1c82ac5 (2023-08-17, downstream DNS cookies) made val_sigcrypt.o and edns.o depend on the new util/rfc_1982.o and util/siphash.o, which the list does not include, so linking fails on undefined compare_1982 / subtract_1982 / siphash. The second is api: fdd5f8ff (2023-09-07) added a struct module_qstate* parameter to scrub_message(), and fuzz_1.c / fuzz_4.c still call it with 7 arguments, which is a compile error. Each is needed on its own: fixing only build.sh leaves the compile error, fixing only fuzz_1.c/fuzz_4.c leaves the link failure. OSS-Fuzz fixed both in a5078ad4 (2023-10-02, 'unbound: fix build'). A pre-existing explicit mix(api+configuration) positive.

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
