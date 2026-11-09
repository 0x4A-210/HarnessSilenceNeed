# V3-48 — binutils-gas @ af3d7ab74f0a

- label: **positive** / explicit / type `state` / introduced_by_this_change = True
- change: https://sourceware.org/git/?p=binutils-gdb.git;a=commit;h=af3d7ab74f0aff2eb2af68d0d1df2e27e5757ecd (gas: set up notes obstack earlier)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: oss ['projects/binutils/fuzz_as.c'] (target `fuzz_as`)
- fix H: https://github.com/google/oss-fuzz/commit/db7354e3d31cd9052c0d8dd0b961c862fbb2e889

## 理由
fuzz_as 绕过 main()，自己按顺序组合调用 gas 的各个 init/begin 函数，依赖『read_begin 会建立 notes obstack』这一状态约定。M（gas: set up notes obstack earlier）把 obstack_begin(&notes) 从 read_begin 移到 main，harness 组合出的状态缺少 notes，首次分配段信息即跳到空函数指针 SEGV。S0 正常，故本次引入。H（oss-fuzz #9400，注明 upstream gas has changed / issue 48997）在 harness 中补上 obstack_begin(&notes) 等初始化。注：该例也可视为 lifecycle（初始化顺序）；按『组合调用依赖的状态约定』归为 state。

## Rationale
fuzz_as bypasses main() and calls the gas init/begin functions itself in a fixed order, relying on the state convention that read_begin() sets up the notes obstack. M (gas: set up notes obstack earlier) moves obstack_begin(&notes) from read_begin() into main(), so the state built by the harness has no notes obstack and the first section-info allocation jumps through a null function pointer (SEGV). The harness works with S0 (M^1), so the degradation is introduced by this change. H (oss-fuzz #9400, which cites "upstream gas has changed" and issue 48997) adds obstack_begin(&notes) and other initialisation to the harness. Note: the case could also be read as lifecycle (initialisation order); it is labelled state because it is about a state convention that the composed calls rely on.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok",
  "h(fix) x lib(M)": "not_run"
 },
 "replay": {
  "corpus_size": 1,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 1,
  "crashes_fixed_harness_lib_M": null
 },
 "explicit_signal": "runtime_failure_on_replay"
}
```
