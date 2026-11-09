# V3-49（Dataset-v6_3 中编号 V3-08）— zstd @ 9c3265a53f04

- label: **positive** / explicit / type `mix` ['api', 'state'] / introduced_by_this_change = True
- change: https://github.com/facebook/zstd/commit/9c3265a53f0431d388b00d420d7ee7418207e174 (Merge pull request #1417 from facebook/advancedAPI)
- origin: real_commit_lib_hunks_only; route: coupled_split; gt: coupled_commit
- harness: intree ['tests/fuzz/stream_round_trip.c'] (target `stream_round_trip`)
- fix H: https://github.com/facebook/zstd/commit/9c3265a53f0431d388b00d420d7ee7418207e174

## 理由
该合并提交（advanced API 定型）改变了上下文的重置契约：ZSTD_CCtx_reset() 不再是“清空会话”的单参数调用，而必须显式给出 ZSTD_ResetDirective（只重置会话，还是连参数一起重置）。stream_round_trip 复用一个静态 ZSTD_CCtx，每个输入开始时以及每次 flush 之后都依赖 ZSTD_CCtx_reset(cctx) 清空会话状态。只应用库部分的改动，harness 在这些重置调用处编译失败。根因是状态重置/复用契约的变化（state），表现为显式编译失败；维护者在同一提交中改为 ZSTD_CCtx_reset(cctx, ZSTD_reset_session_only)，以保留随机参数、只清会话。属于本次引入的显式 state 退化。

## Rationale
This merge (finalising the advanced API) changes the context reset contract: ZSTD_CCtx_reset() is no longer a one-argument clear-the-session call but takes an explicit ZSTD_ResetDirective (reset the session only, or the parameters too). stream_round_trip reuses a static ZSTD_CCtx and relies on ZSTD_CCtx_reset(cctx) to clear session state at the start of every input and after every flush. With only the library hunks applied, the harness fails to compile at those reset calls. The root cause is a change to the state reset/reuse contract (state), surfacing as an explicit compile failure; the maintainers switched to ZSTD_CCtx_reset(cctx, ZSTD_reset_session_only) in the same commit to keep the random parameters and clear only the session. Explicit state degradation introduced by this change.

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
