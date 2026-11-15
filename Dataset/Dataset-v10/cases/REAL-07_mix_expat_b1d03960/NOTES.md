# REAL-07 — expat @ b1d03960

- label: **positive** / silent / type `mix` (api + state + configuration) / introduced_by_this_change = True
- change: https://github.com/libexpat/libexpat/commit/b1d039607d3d8a042bf0466bfcc1c0f104e353c8 (lib: Protect against billion laughs attacks)
- origin: real_github; route: manual_analysis; gt: code_analysis
- harness: oss ['parse_fuzzer.c', 'xml_fuzzer.c'] (targets `parse_fuzzer`, `xml_fuzzer`)
- fix H: TBD (not yet identified from OSS-Fuzz history)

## 理由

库在这次提交中新增了全面的 Billion Laughs Attack（十亿笑攻击）防护机制，这是一个典型的 **mix 类型**退化，同时涉及三个维度：

### 1. API 维度
新增了 2 个防护配置 API：
- `XML_SetBillionLaughsAttackProtectionMaximumAmplification()` - 设置最大放大倍数
- `XML_SetBillionLaughsAttackProtectionActivationThreshold()` - 设置激活阈值

### 2. State 维度
新增了跨解析调用的状态跟踪机制：
- `accountingDiffTolerated()` - 检查实体扩展的放大倍数
- `entityTrackingOnOpen()` / `entityTrackingOnClose()` - 跟踪实体打开/关闭状态
- 需要在多次解析调用之间维护 `accountingDiff` 状态

### 3. Configuration 维度
新增了默认配置特性：
- `XML_FEATURE_BILLION_LAUGHS_ATTACK_PROTECTION_MAXIMUM_AMPLIFICATION_DEFAULT`
- `XML_FEATURE_BILLION_LAUGHS_ATTACK_PROTECTION_ACTIVATION_THRESHOLD_DEFAULT`

然而，OSS-Fuzz 的旧 harness 没有：
1. 调用新的 API 来配置防护参数
2. 测试实体扩展攻击场景
3. 测试跨解析调用的状态管理

这意味着新增的 1000+ 行防护代码在旧 harness 下覆盖率为 0，完全无法触达。编译和运行都正常（没有编译错误、链接错误或运行时崩溃），所以这是**隐式**缺口。

## Rationale

The library added comprehensive Billion Laughs Attack protection in this commit. This is a典型 **mix type** degradation involving three dimensions:

### 1. API Dimension
Added 2 protection configuration APIs:
- `XML_SetBillionLaughsAttackProtectionMaximumAmplification()` - set maximum amplification factor
- `XML_SetBillionLaughsAttackProtectionActivationThreshold()` - set activation threshold

### 2. State Dimension
Added state tracking across parse calls:
- `accountingDiffTolerated()` - check entity expansion amplification
- `entityTrackingOnOpen()` / `entityTrackingOnClose()` - track entity open/close state
- Requires maintaining `accountingDiff` state across multiple parse calls

### 3. Configuration Dimension
Added default configuration features:
- `XML_FEATURE_BILLION_LAUGHS_ATTACK_PROTECTION_MAXIMUM_AMPLIFICATION_DEFAULT`
- `XML_FEATURE_BILLION_LAUGHS_ATTACK_PROTECTION_ACTIVATION_THRESHOLD_DEFAULT`

However, the old OSS-Fuzz harness does not:
1. Call the new APIs to configure protection parameters
2. Test entity expansion attack scenarios
3. Test state management across parse calls

This means the 1000+ lines of new protection code have 0% coverage under the old harness and are completely unreachable. The code compiles and runs normally (no compilation errors, linking errors, or runtime crashes), so this is a **silent** gap.

## 为什么是 mix 类型

这个案例必须**同时修复三个维度**才能消除 gap：
1. **API** - harness 必须调用新的配置 API
2. **State** - harness 必须测试跨解析调用的实体扩展场景
3. **Configuration** - harness 必须测试不同的配置参数组合

单独修复任何一个维度都无法完全覆盖新增的防护逻辑。

## Why is it mix type

This case requires **fixing all three dimensions simultaneously** to eliminate the gap:
1. **API** - harness must call the new configuration APIs
2. **State** - harness must test entity expansion scenarios across parse calls
3. **Configuration** - harness must test different parameter combinations

Fixing any single dimension alone cannot fully cover the new protection logic.

## 变更内容摘要

```
+1132 lines, -53 lines
Files changed:
- expat/lib/expat.h (API declarations)
- expat/lib/internal.h (internal macros and types)
- expat/lib/xmlparse.c (protection implementation)
- expat/lib/libexpat.def (Windows export)
- expat/lib/libexpatw.def (Windows export, wide char)
- .github/workflows/data/exported-symbols.txt (symbol list)
```

## 关键代码路径

新增的防护逻辑包括：
- 实体放大倍数计算
- 跨解析调用的状态累积
- 超过阈值时触发 `XML_ERROR_AMPLIFICATION_LIMIT_BREACH` 错误

这些代码路径在旧 harness 下都无法触达。

## 修复方案

Harness 需要更新为：
1. 调用 `XML_SetBillionLaughsAttackProtection*` API
2. 构造包含嵌套实体的 XML 输入
3. 测试跨多次解析调用的场景
4. 验证防护机制能正确触发

## 数据来源

- Commit: https://github.com/libexpat/libexpat/commit/b1d039607d3d8a042bf0466bfcc1c0f104e353c8
- PR: https://github.com/libexpat/libexpat/pull/466
- OSS-Fuzz: https://github.com/google/oss-fuzz/tree/main/projects/expat
