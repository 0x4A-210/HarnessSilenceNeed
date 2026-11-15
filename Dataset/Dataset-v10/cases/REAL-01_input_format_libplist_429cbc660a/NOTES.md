# REAL-01 — libplist @ 429cbc660a

- label: **positive** / silent / type `input_format` / introduced_by_this_change = True
- change: https://github.com/libimobiledevice/libplist/commit/429cbc660ae14d4998715803b44c71abf0e4a339 (Add support for JSON format)
- origin: real_github; route: cispa_case_study; gt: TBD
- harness: oss ['fuzz/xplist_fuzzer.cc', 'fuzz/bplist_fuzzer.cc'] (targets `xplist_fuzzer`, `bplist_fuzzer`)
- fix H: TBD (not yet identified from OSS-Fuzz history)

## 理由

库在这次提交中新增了JSON格式支持，添加了695行的`src/jplist.c`（JSON解析器）和280行的`src/jsmn.c`（JSON状态机）。新增了`plist_from_json()`函数，并在`plist_from_memory()`中增加了JSON格式的自动识别和分派。

然而，旧的fuzzing harness（`xplist_fuzzer.cc`和`bplist_fuzzer.cc`）分别只调用`plist_from_xml()`和`plist_from_bin()`，完全不调用`plist_from_json()`或`plist_from_memory()`。这意味着新增的近1000行JSON解析代码在旧harness下覆盖率为0，完全无法触达。

编译和运行都正常（没有编译错误、链接错误或运行时崩溃），所以这是**隐式**缺口。属于本次引入的input_format类退化。

## Rationale

The library added JSON format support in this commit, adding 695 lines of `src/jplist.c` (JSON parser) and 280 lines of `src/jsmn.c` (JSON state machine). It introduced the `plist_from_json()` function and added automatic JSON format detection and dispatch in `plist_from_memory()`.

However, the old fuzz harnesses (`xplist_fuzzer.cc` and `bplist_fuzzer.cc`) only call `plist_from_xml()` and `plist_from_bin()` respectively, never calling `plist_from_json()` or `plist_from_memory()`. This means the nearly 1000 lines of new JSON parsing code have 0% coverage under the old harness and are completely unreachable.

The code compiles and runs normally (no compilation errors, linking errors, or runtime crashes), so this is a **silent** gap. It's an input_format degradation introduced by this change.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok (but JSON code unreachable)",
  "h(fix) x lib(M)": "pending (fix not yet identified)"
 },
 "fuzz_M": {
   "gap_coverage": "0/2 key entry points (plist_from_json, jsmn_parse)"
 },
 "verdict": "PASS"
}
```

## 讲解 

**libplist新增JSON支持**：阳性 · 隐式 · 本次引入 · input_format

> 库新增了JSON格式支持，但旧harness只测试XML和Binary格式，导致新的JSON解析代码完全无法触达。

### 1. 库改了什么（`input/change.diff`）

这次提交新增了完整的JSON格式支持：

- **新增文件**：
  - `src/jplist.c` (695行)：JSON plist解析器
  - `src/jsmn.c` (280行)：JSON状态机（JSMN库）
  - `src/jsmn.h` (91行)：JSMN头文件

- **新增API**：
  - `plist_from_json(const char *json, uint32_t length, plist_t *plist)` - 从JSON字符串解析plist
  - `plist_to_json(plist_t plist, char **json, uint32_t *length, int prettify)` - 将plist转为JSON

- **增强现有API**：
  - `plist_from_memory()` 现在可以自动检测JSON格式（通过查找'{'字符）并分派到`plist_from_json()`

代码量变化：3900行 -> 4700行（+800行，主要是JSON支持）

### 2. 原来的harness（`input/harness/oss-fuzz/`）

OSS-Fuzz中libplist有两个fuzzer：

**xplist_fuzzer.cc**（M时刻的版本）：
```cpp
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    plist_t plist = NULL;
    plist_from_xml((const char*)data, size, &plist);
    // ... cleanup ...
}
```

**bplist_fuzzer.cc**（M时刻的版本）：
```cpp
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    plist_t plist = NULL;
    plist_from_bin((const char*)data, size, &plist);
    // ... cleanup ...
}
```

两个fuzzer分别只测试XML和Binary格式，**完全不调用**：
- `plist_from_json()`
- `plist_from_memory()`（虽然它现在支持JSON）

### 3. 为什么harness出问题了

新增的JSON解析代码（近1000行）从静态调用图来看完全不可达：
- `plist_from_json()` - 从未被调用
- `jsmn_parse()` - JSON状态机入口，从未被调用
- 整个`jplist.c`的解析逻辑 - 0覆盖率

根据CISPA的覆盖率报告对比：
- 2021-12-22（M前）：https://storage.googleapis.com/oss-fuzz-coverage/libplist/reports/20211222/linux/src/libplist/report.html
- 2021-12-23（M后）：https://storage.googleapis.com/oss-fuzz-coverage/libplist/reports/20211223/linux/src/libplist/report.html

本地隔离验证（见`verification/experiments.json`）：
- 旧harness × 新库：`jplist.c:628` (plist_from_json入口) 命中0次
- 旧harness × 新库：`jplist.c:652` (jsmn_parse调用) 命中0次
- 最小JSON fuzzer × 新库：两处均命中，确认可达

### 4. 怎么修（ground truth待定）

需要添加第三个fuzzer：

```cpp
// json_fuzzer.cc
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    plist_t plist = NULL;
    plist_from_json((const char*)data, size, &plist);
    // ... 或者直接用 plist_from_memory，让它自动检测格式 ...
    if (plist) {
        plist_free(plist);
    }
    return 0;
}
```

或者更新现有fuzzer使用`plist_from_memory()`，让它能处理所有三种格式。

**注意**：目前尚未从OSS-Fuzz历史中定位到正式的修复commit。本地使用的`json_fuzzer_fix.cc`只是为了验证JSON代码可达性的最小实现，不代表上游的实际修复方式。

### 5. 为什么是这个标签

- **阳性**：新增的JSON解析功能完全未被测试，需要更新harness。
- **隐式**：编译、链接、运行都正常，没有显式错误。只有通过覆盖率分析才能发现新代码未被触达。
- **本次引入**：JSON支持是这次提交新增的，之前不存在。
- **input_format**：问题的根源是harness只能生成旧的输入格式（XML和Binary），无法生成新的输入格式（JSON）。

### 6. 数据来源

- **库变更**：从libplist上游仓库commit `429cbc660ae14d4998715803b44c71abf0e4a339`
- **旧harness**：从OSS-Fuzz commit `1d5a2cd84eb828e1c3303c4053e5590f382516a6`
- **CISPA案例研究**：https://raw.githubusercontent.com/CISPA-SysSec/fuzz-harness-degradation/main/case_studies/notes.md
- **覆盖率报告**：Google OSS-Fuzz Coverage Storage
- **本地验证**：隔离的GCC编译 + 单输入测试（见`verification/`）
