# V3-12 — inih @ 498f34b78610

- label: **positive** / silent / type `configuration` / introduced_by_this_change = False
- change: https://github.com/benhoyt/inih/commit/498f34b78610cf9e42197d22730c91f942431ea4 (Fix bug when INI_ALLOW_NO_VALUE is set where name only options are not (#197))
- origin: real_commit; route: forward_scan; gt: counterfactual_fix
- harness: oss ['projects/inih/inihfuzz.c', 'projects/inih/build.sh'] (target `inihfuzz`)

## 理由
本次提交修复 INI_ALLOW_NO_VALUE 打开时“出错后不再处理只有 name 的行”的 bug，改动全部位于 #if INI_ALLOW_NO_VALUE 分支内。OSS-Fuzz 的 harness 构建脚本只用默认宏编译 ini.c，INI_ALLOW_NO_VALUE 默认为 0，这段代码根本不会编进 fuzz 目标，覆盖映射里不存在。harness 照常编译运行，只是静默错过这类代码；该构建配置缺口在本次变更前就存在。属于非本次引入的隐式 configuration 退化。反事实修复：在 build.sh 中为 ini.c 加 -DINI_ALLOW_NO_VALUE=1（1 行，dumper 不读 value，NULL 安全）。

## Rationale
This commit fixes a bug where, with INI_ALLOW_NO_VALUE enabled, name-only lines stop being handled after an error. All changed logic is inside #if INI_ALLOW_NO_VALUE. The OSS-Fuzz build script compiles ini.c with default macros and INI_ALLOW_NO_VALUE defaults to 0, so this code is never compiled into the fuzz target and is absent from the coverage mapping. The harness builds and runs normally while silently missing this code; the build-configuration gap existed before this change. Pre-existing silent configuration degradation. Counterfactual fix: compile ini.c with -DINI_ALLOW_NO_VALUE=1 in build.sh (one line; the harness's dumper never reads value, so NULL is safe).

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
    "execs": 79382077,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 73190709,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 87542881,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 84287134,
    "gap_covered": [
     3
    ]
   },
   {
    "seed": 2,
    "execs": 156595399,
    "gap_covered": [
     3
    ]
   }
  ]
 },
 "fuzz_Mparent_replay": {
  "without_fix": [
   {
    "seed": 1,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": "n/a (replay)",
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": "n/a (replay)",
    "gap_covered": [
     3
    ]
   },
   {
    "seed": 2,
    "execs": "n/a (replay)",
    "gap_covered": [
     3
    ]
   }
  ]
 },
 "applies_to_parent": true
}
```
