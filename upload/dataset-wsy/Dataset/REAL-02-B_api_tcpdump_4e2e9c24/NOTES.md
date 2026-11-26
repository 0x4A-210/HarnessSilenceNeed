# REAL-02-B: tcpdump OpenFlow API 重构 (api)

## 基本信息

- **项目**: tcpdump
- **提交**: 4e2e9c244affec1bdf012083a8af3c91403962f0
- **日期**: 2020-09-23
- **退化类型**: api

## 变更描述

此提交重构了 tcpdump 中所有 OpenFlow 1.0 解析函数的 API，将原来的 `const u_char*` 返回值改为 `void`，错误通过 `nd_trunc()` 机制传播。

### 修改文件

- `print-openflow-1.0.c`（主要变更，+483/-553）
- `print-openflow.c`
- `openflow.h`
- `netdissect.h`
- `netdissect-stdinc.h`

### 核心变更

```c
// 旧 API
static const u_char *
of10_match_print(netdissect_options *ndo, const char *indent,
                 const u_char *cp, const u_char *ep);

// 新 API
static void
of10_match_print(netdissect_options *ndo, const char *indent,
                 const u_char *cp, u_int len);
```

## Harness 退化分析

### 退化类型：api

**API 契约变更**：此提交将所有 `of10_*` 系列函数的签名从"返回当前解析位置指针 `(cp, ep, len)`"改为"无返回值 `(cp, len)`，通过 `nd_trunc()` 信号传递截断"。这是一次接口破坏性变更（breaking change）。

**对 Harness 的影响**：
1. 任何直接调用 `of10_*` 函数并使用其返回指针的 harness 将无法编译
2. 错误传播机制从"检查返回值是否为 NULL"改为"检查 ndo->ndo_truncated 标志"
3. Harness 对解析进度的追踪方式需要完全重写

**退化特征**：
- **显式退化**：编译时即会失败（类型不匹配）
- **范围**：整个 OpenFlow 1.0 解析模块，约 24 个函数全部变更

---

# REAL-02-B: tcpdump OpenFlow API Refactoring (api)

## Basic Info

- **Project**: tcpdump
- **Commit**: 4e2e9c244affec1bdf012083a8af3c91403962f0
- **Date**: 2020-09-23
- **Degradation Type**: api

## Change Description

This commit refactors all OpenFlow 1.0 parsing functions in tcpdump, changing the return type from `const u_char*` to `void` and propagating errors through the `nd_trunc()` mechanism.

### Modified Files

- `print-openflow-1.0.c` (main changes, +483/-553)
- `print-openflow.c`
- `openflow.h`
- `netdissect.h`
- `netdissect-stdinc.h`

### Core Change

```c
// Old API
static const u_char *
of10_match_print(netdissect_options *ndo, const char *indent,
                 const u_char *cp, const u_char *ep);

// New API
static void
of10_match_print(netdissect_options *ndo, const char *indent,
                 const u_char *cp, u_int len);
```

## Harness Degradation Analysis

### Degradation Type: api

**API contract change**: This commit changes all `of10_*` function signatures from "return current parse position pointer with `(cp, ep, len)`" to "void return with `(cp, len)`, signaling truncation via `nd_trunc()`". This is a breaking change.

**Impact on Harness**:
1. Any harness calling `of10_*` functions and using their return pointers will fail to compile
2. Error propagation changes from "check for NULL return" to "check ndo->ndo_truncated flag"
3. Harness logic for tracking parse progress needs complete rewrite

**Degradation characteristics**:
- **Explicit degradation**: Compile-time failure (type mismatch)
- **Scope**: The entire OpenFlow 1.0 parsing module; ~24 functions all changed
