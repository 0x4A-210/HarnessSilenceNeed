# REAL-01-B: libtiff WebP 维度验证 (input_format)

## 基本信息

- **项目**: libtiff
- **提交**: b0469e8157cb8b694f261d28c98674c1d0ce85e6
- **日期**: 2020-10-20
- **退化类型**: input_format

## 变更描述

此提交在 libtiff 的 WebP 编解码器中增加了对 tile/strip 尺寸的验证，限制宽高最大值为 16383。

### 修改文件

- `libtiff/tif_webp.c`

### 核心变更

```c
// 新增验证逻辑
if (segment_width > 16383 || segment_height > 16383) {
    TIFFErrorExt(tif->tif_clientdata, "WebPPreDecode",
                 "WebP maximum image dimensions are 16383 x 16383");
    return 0;
}
```

## Harness 退化分析

### 退化类型：input_format

**输入格式限制的改变**：此提交引入了对 WebP 瓦片尺寸的硬性上限（16383×16383）。在此提交之前，模糊测试 harness 可以生成任意尺寸的瓦片数据，它们都会被 WebP 解码器接受并尝试处理。提交之后，超出范围的尺寸在解码器入口处被拒绝，不再进入实际解码逻辑。

**对 Harness 的影响**：
1. 原有 harness 生成的超大尺寸输入现在在第一关就被拒绝，无法再测试深层解码逻辑
2. Harness 需要感知新的尺寸上限约束，生成接近边界值（16382、16383、16384）的测试用例
3. 若不更新 harness，模糊测试的有效覆盖率会下降

**退化特征**：
- **显式退化**：代码中新增了明确的尺寸检查和错误返回
- **边界点**：16383（最大允许值），16384（最小拒绝值）

---

# REAL-01-B: libtiff WebP Dimension Validation (input_format)

## Basic Info

- **Project**: libtiff
- **Commit**: b0469e8157cb8b694f261d28c98674c1d0ce85e6
- **Date**: 2020-10-20
- **Degradation Type**: input_format

## Change Description

This commit adds validation of tile/strip dimensions in libtiff's WebP codec, limiting width and height to a maximum of 16383.

### Modified File

- `libtiff/tif_webp.c`

### Core Change

```c
// Added dimension validation
if (segment_width > 16383 || segment_height > 16383) {
    TIFFErrorExt(tif->tif_clientdata, "WebPPreDecode",
                 "WebP maximum image dimensions are 16383 x 16383");
    return 0;
}
```

## Harness Degradation Analysis

### Degradation Type: input_format

**Change in input format constraints**: This commit introduces a hard upper limit (16383×16383) on WebP tile dimensions. Before this commit, a fuzzing harness could generate tiles of arbitrary size, all of which would be accepted by the WebP codec for processing. After the commit, out-of-range dimensions are rejected at the codec's entry point and never reach the actual decoding logic.

**Impact on Harness**:
1. Previously valid oversized inputs are now rejected at the first check, losing coverage of deep decoding logic
2. The harness must be aware of the new dimension constraint and generate boundary values (16382, 16383, 16384)
3. Without harness updates, effective fuzzing coverage decreases

**Degradation characteristics**:
- **Explicit degradation**: New dimension check with explicit error return
- **Boundary point**: 16383 (max allowed), 16384 (min rejected)
