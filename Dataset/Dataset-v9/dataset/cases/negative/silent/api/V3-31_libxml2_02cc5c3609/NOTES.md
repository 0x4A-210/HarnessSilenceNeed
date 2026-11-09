# V3-31 — libxml2 @ 02cc5c360953

- label: **negative** / silent / type `api` / introduced_by_this_change = None
- change: https://github.com/GNOME/libxml2/commit/02cc5c3609532709a180287a8d901fe31c452520 (parser: Add XML_PARSE_NO_XXE parser option)
- origin: real_commit; route: forward_scan; gt: experiment
- harness: intree ['fuzz/xml.c'] (target `xml`)

## 理由
本次提交新增解析选项 XML_PARSE_NO_XXE（禁止加载外部实体与外部 DTD），在 parser.c / SAX2.c 的多处实体加载判断中引入新的选项分支。这与“新增选项、harness 硬编码选项导致新分支不可达”的隐式阳性在表面上完全相同。但 xml 这个 harness 的解析选项来自输入（xmlFuzzReadInt(4)），只屏蔽了少数选项，新的选项位会被随机置位；定额 fuzz 下“选项已置位”的分支在多个种子中被实际执行。动了 harness 相关的选项接口但无需修改 harness，属于隐式 api 阴性。

## Rationale
This commit adds the parser option XML_PARSE_NO_XXE (no loading of external entities or the external DTD), introducing new option branches in several entity-loading checks in parser.c and SAX2.c. On the surface this is identical to a silent positive where a new option is unreachable because the harness hard-codes its options. But the xml harness takes its parser options from the input (xmlFuzzReadInt(4)) and masks only a few of them, so the new bit gets set at random; under the fuzz budget the option-set branches are executed in several seeds. A change touching the harness-relevant option interface that needs no harness update: silent api negative.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok"
 },
 "replay": {
  "corpus_size": 328,
  "crashes_lib_parent": 0,
  "crashes_lib_M": 0
 },
 "patch_cov": 0.667,
 "fuzz_M": {
  "without_fix": [
   {
    "seed": 1,
    "execs": 365893,
    "gap_covered": [
     1,
     1
    ]
   },
   {
    "seed": 2,
    "execs": 381216,
    "gap_covered": [
     1,
     1
    ]
   },
   {
    "seed": 3,
    "execs": 641276,
    "gap_covered": [
     1,
     1
    ]
   }
  ]
 }
}
```
