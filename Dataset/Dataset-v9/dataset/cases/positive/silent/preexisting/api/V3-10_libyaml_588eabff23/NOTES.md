# V3-10 — libyaml @ 588eabff23ba

- label: **positive** / silent / type `api` / introduced_by_this_change = False
- change: https://github.com/yaml/libyaml/commit/588eabff23ba2292f537872bbea5b64bce1e1a21 (Handle closing flow sequence after explicit key)
- origin: real_commit; route: ossfuzz_signal; gt: maintainer_fix
- harness: oss ['projects/libyaml/libyaml_emitter_fuzzer.c'] (target `libyaml_emitter_fuzzer`)
- fix H: https://github.com/google/oss-fuzz/commit/d94076d68f841419e155dad6c43e399b2824dbf3

## 理由
本次提交在 parser.c 中处理“显式 key 之后关闭 flow sequence”的情况，emitter harness 会先用 parser 产生事件再交给 emitter。但该 harness 自 2020 年创建起，就把 copy_event()（成功返回 1，沿用 libyaml 约定）的返回值判反：复制成功就 goto delete_parser。于是只解析出第一个事件就退出，yaml_emitter_emit() 一次都没被调用，本次新增的 parser 路径也到不了。harness 照常编译运行、不报错，只是静默丢掉整个 emitter 的覆盖。这一退化早于本次 diff，属于非本次引入的隐式 api 退化；维护者在 oss-fuzz d94076d68f 中改为 !copy_event()。

## Rationale
This commit handles closing a flow sequence after an explicit key in parser.c; the emitter harness parses events and feeds them to the emitter. Since its creation in 2020, however, the harness inverts the result of copy_event() (which returns 1 on success, following libyaml convention): a successful copy jumps to delete_parser. It stops after the first event, yaml_emitter_emit() is never called, and the new parser path is not reached either. The harness builds and runs without any error while silently losing all emitter coverage. The degradation predates this diff: pre-existing silent api degradation, fixed in oss-fuzz d94076d68f (!copy_event()).

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
    "execs": 177411297,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 166605933,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 144936958,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 10144676,
    "gap_covered": [
     6
    ]
   },
   {
    "seed": 2,
    "execs": 10917807,
    "gap_covered": [
     6
    ]
   }
  ]
 },
 "fuzz_Mparent": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 227650999,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 160648159,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 219217621,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 9962438,
    "gap_covered": [
     6
    ]
   },
   {
    "seed": 2,
    "execs": 10545802,
    "gap_covered": [
     6
    ]
   }
  ]
 },
 "applies_to_parent": true
}
```
