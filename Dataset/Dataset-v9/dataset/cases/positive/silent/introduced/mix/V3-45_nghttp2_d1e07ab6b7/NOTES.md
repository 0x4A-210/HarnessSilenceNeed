# V3-45 — nghttp2 @ d1e07ab6b728

- label: **positive** / silent / type `mix` ['configuration', 'input_format'] / introduced_by_this_change = True
- change: https://github.com/nghttp2/nghttp2/commit/d1e07ab6b728e7cba16f37ff17b5b6eb68c91e9d (Merge pull request #1729 from nghttp2/rfc9218-priority-update-frame)
- origin: real_commit; route: head_audit; gt: counterfactual_fix
- harness: intree ['fuzz/fuzz_target.cc'] (target `nghttp2_fuzzer`)

## 理由
本次合并（PR #1729）实现 RFC 9218 的 PRIORITY_UPDATE 帧：新增帧类型 0x10 及其载荷格式（input_format：服务器端新接受的一种帧格式），但只有在两项配置同时满足时才处理——会话选项 nghttp2_option_set_builtin_recv_extension_type(NGHTTP2_PRIORITY_UPDATE) 打开内建扩展，且本端 SETTINGS 中声明 NO_RFC7540_PRIORITIES=1（configuration）。harness 自 2017 年起用 nghttp2_session_server_new(..., nullptr) 建会话、只提交 MAX_CONCURRENT_STREAMS 一项设置，因此任何 0x10 帧都在 session.c:6354 被忽略；只开选项不发设置又会在 6383 行被忽略。新帧格式的解包、处理与优先级更新代码覆盖恒为 0，harness 照常运行。两个维度缺一不可：新格式本身需要新配置才可达，正是分布设计中“新格式分支需要新 flag 才可达”的隐式 mix。反事实修复 Δh（约 16 行，只改 harness）打开选项并按输入奇偶决定是否发送该设置；打开后定额 fuzz 很快在新路径上触发库内断言（session.c:6845），说明这段从未被 fuzz 过的代码确有问题。M^1 不存在该帧类型，缺口由本次引入。

## Rationale
This merge (PR #1729) implements the RFC 9218 PRIORITY_UPDATE frame: a new frame type 0x10 with its own payload format (input_format: a frame format the server now accepts), processed only when two configuration conditions hold - the session option nghttp2_option_set_builtin_recv_extension_type(NGHTTP2_PRIORITY_UPDATE) enables the built-in extension and the local SETTINGS announce NO_RFC7540_PRIORITIES=1 (configuration). Since 2017 the harness creates the session with nghttp2_session_server_new(..., nullptr) and submits only MAX_CONCURRENT_STREAMS, so every 0x10 frame is ignored at session.c:6354; enabling only the option still drops it at line 6383. The unpacking, processing and priority-update code of the new frame format keeps zero coverage while the harness runs normally. Both dimensions are needed: the new format is reachable only through the new configuration - the 'new format branch that needs a new flag' silent mix of the distribution design. The counterfactual fix (about 16 lines, harness only) enables the option and sends the setting for odd-sized inputs; with it, budgeted fuzzing soon trips a library assertion on the new path (session.c:6845), showing that this never-fuzzed code does have problems. The frame type does not exist at M^1, so the gap is introduced by this change.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok",
  "h(fix) x lib(M)": "ok"
 },
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 7199498,
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 2,
    "execs": 5838404,
    "gap_covered": [
     0,
     0
    ]
   },
   {
    "seed": 3,
    "execs": 9608804,
    "gap_covered": [
     0,
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 2153605,
    "gap_covered": [
     7,
     12
    ]
   },
   {
    "seed": 2,
    "execs": 1327156,
    "gap_covered": [
     7,
     12
    ]
   }
  ]
 },
 "applies_to_parent": false
}
```
