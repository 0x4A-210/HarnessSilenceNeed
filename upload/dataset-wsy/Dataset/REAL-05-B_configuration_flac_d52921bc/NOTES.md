# REAL-05-B: FLAC 有符号整数溢出 Sanitizer 配置 (configuration)

## 基本信息

- **项目**: flac
- **提交**: d52921bc0b96c21188aeaeac7193aeb4e1801a19
- **日期**: 2023-02-21
- **退化类型**: configuration
- **GitHub Issue**: #546

## 变更描述

此提交更新了 FLAC 中用于控制有符号整数溢出 sanitizer 行为的宏定义，从旧的 `FUZZING_BUILD_MODE_NO_SANITIZE_SIGNED_INTEGER_OVERFLOW` 改为新的双条件宏，影响 3 个热点文件。

### 修改文件

- `src/libFLAC/fixed.c`
- `src/libFLAC/lpc.c`
- `src/libFLAC/stream_decoder.c`

### 核心变更

```c
// 旧宏定义
#ifdef FUZZING_BUILD_MODE_NO_SANITIZE_SIGNED_INTEGER_OVERFLOW
__attribute__((no_sanitize("signed-integer-overflow")))
#endif

// 新宏定义
#if defined(FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION) && \
    !defined(FUZZING_BUILD_MODE_FLAC_SANITIZE_SIGNED_INTEGER_OVERFLOW)
__attribute__((no_sanitize("signed-integer-overflow")))
#endif
```

## Harness 退化分析

### 退化类型：configuration

**构建配置变更**：此提交改变了 FLAC 热点函数中 sanitizer 的激活条件。旧代码使用一个独立宏控制 sanitizer 关闭，新代码使用更复杂的双条件（需要在模糊测试构建模式下，且未明确要求保留 sanitizer）。这是一次纯构建配置层面的变更。

**对 Harness 的影响**：
1. 使用旧宏名称的 harness 构建配置将不再正确激活 sanitizer 注解
2. 若 OSS-Fuzz 的编译环境未定义新宏，热点函数的溢出检测行为会改变
3. 这类"配置退化"是最隐蔽的：代码逻辑未变，但 sanitizer 覆盖范围悄然改变

**退化特征**：
- **显式退化**：宏定义改变，但对不了解配置的用户是隐式的
- **检测要求**：需要对 OSS-Fuzz 构建系统有深入了解才能发现影响

---

# REAL-05-B: FLAC Signed Integer Overflow Sanitizer Configuration (configuration)

## Basic Info

- **Project**: flac
- **Commit**: d52921bc0b96c21188aeaeac7193aeb4e1801a19
- **Date**: 2023-02-21
- **Degradation Type**: configuration
- **GitHub Issue**: #546

## Change Description

This commit updates the macro controlling signed integer overflow sanitizer behavior in FLAC, changing from the old `FUZZING_BUILD_MODE_NO_SANITIZE_SIGNED_INTEGER_OVERFLOW` to a new dual-condition macro, affecting 3 hotspot files.

### Modified Files

- `src/libFLAC/fixed.c`
- `src/libFLAC/lpc.c`
- `src/libFLAC/stream_decoder.c`

### Core Change

```c
// Old macro
#ifdef FUZZING_BUILD_MODE_NO_SANITIZE_SIGNED_INTEGER_OVERFLOW
__attribute__((no_sanitize("signed-integer-overflow")))
#endif

// New macro
#if defined(FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION) && \
    !defined(FUZZING_BUILD_MODE_FLAC_SANITIZE_SIGNED_INTEGER_OVERFLOW)
__attribute__((no_sanitize("signed-integer-overflow")))
#endif
```

## Harness Degradation Analysis

### Degradation Type: configuration

**Build configuration change**: This commit changes the sanitizer activation conditions for FLAC hotspot functions. The old code used a single macro to disable the sanitizer; the new code uses a more complex dual condition (requires fuzzing build mode AND must not explicitly request sanitizer). This is a purely build-configuration-level change.

**Impact on Harness**:
1. Harness build configs using the old macro name will no longer correctly activate sanitizer annotations
2. If OSS-Fuzz's compile environment doesn't define the new macro, overflow detection behavior in hotspots silently changes
3. This "configuration degradation" is the most subtle: code logic unchanged, sanitizer coverage quietly shifts

**Degradation characteristics**:
- **Explicit degradation**: Macro definition changed, but effectively implicit for users unaware of the configuration
- **Detection requirement**: Requires deep knowledge of OSS-Fuzz build system to identify the impact
