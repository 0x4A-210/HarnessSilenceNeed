# V3-18 — libxml2 @ 2829a21a956d

- label: **positive** / silent / type `lifecycle` / introduced_by_this_change = True
- change: https://github.com/GNOME/libxml2/commit/2829a21a956d2d11bb533aaa4a7298918580569d (xinclude: Improve error handling)
- origin: real_commit; route: head_audit; gt: counterfactual_fix
- harness: intree ['fuzz/xinclude.c'] (target `xinclude`)

## 理由
本次提交为 XInclude 引入按上下文设置的结构化错误通道 xmlXIncludeSetErrorHandler()：设置后，XInclude 会把该处理器转交给被包含文档的解析上下文（xmlXIncludeParseFile）以及 XPointer 求值上下文，错误不再走全局通道。xinclude harness 未作修改，只设置了全局的 generic error 函数，从不为 XInclude 上下文注册处理器，ctxt->errorHandler 恒为 NULL：错误处理器转交给子解析器 / XPath 上下文的分支覆盖恒为 0，harness 照常运行。错误通道的建立属于上下文生命周期中的初始化步骤，因此是本次引入的隐式 lifecycle 退化；反事实修复 Δh 在创建 XInclude 上下文后注册一个空的结构化错误处理器。

## Rationale
This commit introduces a per-context structured error channel for XInclude, xmlXIncludeSetErrorHandler(): once set, XInclude forwards the handler to the parser context of included documents (xmlXIncludeParseFile) and to the XPointer evaluation context, instead of using the global channel. The xinclude harness is unchanged; it only sets the global generic error function and never registers a handler on the XInclude context, so ctxt->errorHandler is always NULL: the branches forwarding the handler to the sub-parser and XPath contexts keep zero coverage while the harness runs normally. Setting up the error channel is an initialisation step of the context lifecycle, so this is an introduced silent lifecycle degradation; the counterfactual fix Δh registers an empty structured error handler right after the XInclude context is created.

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
    "execs": 828243,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 2,
    "execs": 899238,
    "gap_covered": [
     0
    ]
   },
   {
    "seed": 3,
    "execs": 1115393,
    "gap_covered": [
     0
    ]
   }
  ],
  "with_fix": [
   {
    "seed": 1,
    "execs": 942157,
    "gap_covered": [
     2
    ]
   },
   {
    "seed": 2,
    "execs": 1102874,
    "gap_covered": [
     2
    ]
   }
  ]
 },
 "applies_to_parent": false
}
```
