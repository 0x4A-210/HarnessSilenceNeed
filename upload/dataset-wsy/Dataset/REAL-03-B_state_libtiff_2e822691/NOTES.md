# REAL-03-B: libtiff TIFFStartStrip 状态一致性检查 (state)

## 基本信息

- **项目**: libtiff
- **提交**: 2e822691d750c01cec5b5cc4ee73567a204ab2a3
- **日期**: 2020-10-26
- **退化类型**: state
- **OSS-Fuzz Issue**: 26650

## 变更描述

此提交修复了 OSS-Fuzz issue 26650，在 `TIFFStartStrip()` 中增加了对 WebP 编解码器初始化状态的一致性检查。

### 修改文件

- `libtiff/tif_read.c`

### 核心变更

在通过扫描线访问 WebP 数据之前，新增对编解码器状态的检查，当状态不一致时返回错误而非继续执行导致崩溃。

## Harness 退化分析

### 退化类型：state

**状态管理变更**：此提交在扫描线读取路径上增加了对编解码器初始化状态的检查。在此之前，对损坏文件执行扫描线访问会因状态不一致而崩溃，OSS-Fuzz 能发现这类崩溃。修复后，同样的输入会被优雅地拒绝，不再产生崩溃报告。

**对 Harness 的影响**：
1. 原先能触发崩溃的输入现在只会得到错误返回，不再被标记为有趣的用例
2. Harness 若要继续覆盖深层状态逻辑，需要生成能通过新状态检查的输入
3. 这是一次从"不安全状态→崩溃"到"不安全状态→错误返回"的转变

**退化特征**：
- **显式退化**：新增明确的状态检查
- **影响路径**：WebP codec + 扫描线访问路径

---

# REAL-03-B: libtiff TIFFStartStrip State Consistency Check (state)

## Basic Info

- **Project**: libtiff
- **Commit**: 2e822691d750c01cec5b5cc4ee73567a204ab2a3
- **Date**: 2020-10-26
- **Degradation Type**: state
- **OSS-Fuzz Issue**: 26650

## Change Description

This commit fixes OSS-Fuzz issue 26650 by adding codec initialization state consistency checks in `TIFFStartStrip()`.

### Modified File

- `libtiff/tif_read.c`

### Core Change

Before accessing WebP data via scanline API, a new state check is added that returns an error when state is inconsistent rather than proceeding to a crash.

## Harness Degradation Analysis

### Degradation Type: state

**State management change**: This commit adds a codec initialization state check on the scanline read path. Before the fix, scanline access on corrupted files would crash due to inconsistent state — OSS-Fuzz would detect this crash. After the fix, the same inputs are rejected gracefully with no crash.

**Impact on Harness**:
1. Inputs that previously triggered crashes now only return errors and are no longer flagged as interesting
2. To maintain coverage of deep state logic, the harness must generate inputs that pass the new state checks
3. This transforms "invalid state → crash" into "invalid state → error return"

**Degradation characteristics**:
- **Explicit degradation**: New explicit state check added
- **Affected path**: WebP codec + scanline access path
