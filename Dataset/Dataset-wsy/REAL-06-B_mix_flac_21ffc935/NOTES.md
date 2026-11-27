# REAL-06-B: FLAC 命令行工具 Fuzzer 新增 (mix: api + state + configuration)

## 基本信息

- **项目**: flac
- **提交**: 21ffc935f052005c616fdbcdc4cf1925e746028a
- **日期**: 2023-01-31
- **退化类型**: mix (api + state + configuration)

## 变更描述

此提交新增了一个专门针对 FLAC 命令行工具（`flac` 可执行文件）的 OSS-Fuzz harness。在此之前，OSS-Fuzz 只通过库 API 对 libFLAC 进行模糊测试；此提交开辟了一个全新的测试面，同时引入了三个退化维度。

### 新增/修改文件

- `oss-fuzz/tool_flac.c`（新增，87 行）
- `src/flac/main.c`（修改，支持 fuzzer 入口）
- `oss-fuzz/Makefile.am`（修改，添加编译目标）

### 核心变更

```c
// tool_flac.c 新增 fuzzer 入口
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    // 将输入写入临时文件，然后调用 flac main() 解析
    // 通过 argc/argv 传递各种命令行选项组合
    ...
}
```

## Harness 退化分析

### 退化类型：mix (三维混合)

**为什么是 mix 类型**：此变更不属于单一的退化维度，而是同时引入了三个新维度：

#### 1. API 维度
- **旧 harness**：通过 `FLAC__stream_decoder_*()` 等库函数直接调用
- **新 harness**：通过 `argc/argv` 接口调用 `main()`，这是一个完全不同的 API 层
- **退化**：原 harness 完全不覆盖 CLI 参数解析代码路径

#### 2. State 维度
- **旧 harness**：数据在内存中直接处理，无文件 I/O 状态
- **新 harness**：需要创建临时文件、打开文件、读取、关闭——完整的文件 I/O 生命周期
- **退化**：原 harness 不测试文件句柄状态管理

#### 3. Configuration 维度
- **旧 harness**：只测试固定的解码配置
- **新 harness**：通过模糊 `argv` 覆盖 `--compression-level`、`--verify`、`--decode`、`--encode` 等选项组合
- **退化**：原 harness 完全不覆盖命令行选项的交叉影响

**总结**：一个 add-new-fuzzer 操作同时暴露了 API + State + Configuration 三个维度的 harness 覆盖缺口，构成典型的 mix 退化。

---

# REAL-06-B: FLAC Command-Line Tool Fuzzer Addition (mix: api + state + configuration)

## Basic Info

- **Project**: flac
- **Commit**: 21ffc935f052005c616fdbcdc4cf1925e746028a
- **Date**: 2023-01-31
- **Degradation Type**: mix (api + state + configuration)

## Change Description

This commit adds a new OSS-Fuzz harness specifically targeting the FLAC command-line tool (`flac` binary). Before this, OSS-Fuzz only fuzz-tested libFLAC via library API. This commit opens an entirely new attack surface and simultaneously introduces three degradation dimensions.

### Added/Modified Files

- `oss-fuzz/tool_flac.c` (new, 87 lines)
- `src/flac/main.c` (modified to support fuzzer entry point)
- `oss-fuzz/Makefile.am` (modified to add build target)

### Core Change

```c
// New fuzzer entry in tool_flac.c
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    // Write input to temp file, then call flac main() to parse it
    // Pass various command-line option combinations via argc/argv
    ...
}
```

## Harness Degradation Analysis

### Degradation Type: mix (three-dimensional)

**Why mix**: This change does not fall into a single degradation dimension; it simultaneously introduces three new dimensions:

#### 1. API Dimension
- **Old harness**: Direct library calls via `FLAC__stream_decoder_*()` etc.
- **New harness**: Calls `main()` via `argc/argv` — a completely different API layer
- **Degradation**: Original harness has zero coverage of CLI argument parsing code paths

#### 2. State Dimension
- **Old harness**: Data processed in memory, no file I/O state
- **New harness**: Must create temp file, open, read, close — full file I/O lifecycle
- **Degradation**: Original harness does not test file handle state management

#### 3. Configuration Dimension
- **Old harness**: Only tests fixed decoding configuration
- **New harness**: Fuzzes `argv` to cover `--compression-level`, `--verify`, `--decode`, `--encode` and their combinations
- **Degradation**: Original harness has zero coverage of command-line option cross-effects

**Summary**: A single add-new-fuzzer operation simultaneously exposes API + State + Configuration coverage gaps, forming a canonical mix degradation.
