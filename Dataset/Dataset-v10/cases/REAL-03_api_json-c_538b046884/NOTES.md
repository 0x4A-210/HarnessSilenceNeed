# REAL-03 — json-c @ 538b046884

- label: **positive** / silent / type `api` / introduced_by_this_change = True
- change: https://github.com/json-c/json-c/commit/538b0468847660d52191ad202edb4ab585b6fd19 (json_patch: add first implementation)
- origin: real_github; route: manual_analysis; gt: identified_from_commit_history
- harness: oss ['fuzz/*.cc'] - NO json_patch_fuzzer
- fix H: None (json_patch still not fuzzed as of 2024)

## 理由

json-c库添加了完整的json_patch模块（249行json_patch.c + 46行json_patch.h），实现了RFC 6902 JSON Patch规范。这提供了全新的API：`json_patch_apply()`用于应用JSON补丁操作（add, remove, replace, move, copy, test）。

然而，OSS-Fuzz的`projects/json-c/fuzz/`目录中只有4个fuzzer：
- tokener_parse_ex_fuzzer.cc
- json_object_fuzzer.cc  
- json_pointer_fuzzer.cc
- json_array_fuzzer.cc

**完全没有json_patch_fuzzer**，导致整个json_patch.c模块（249行）从未被fuzz测试，覆盖率0%。

编译和运行都正常（json_patch是可选功能），所以这是**隐式**缺口。属于本次引入的API类退化。

## Rationale

The json-c library added a complete json_patch module (249 lines json_patch.c + 46 lines json_patch.h), implementing RFC 6902 JSON Patch specification. This provides entirely new APIs: `json_patch_apply()` for applying JSON patch operations (add, remove, replace, move, copy, test).

However, OSS-Fuzz's `projects/json-c/fuzz/` directory only contains 4 fuzzers:
- tokener_parse_ex_fuzzer.cc
- json_object_fuzzer.cc
- json_pointer_fuzzer.cc  
- json_array_fuzzer.cc

There is **NO json_patch_fuzzer at all**, causing the entire json_patch.c module (249 lines) to have never been fuzz tested, with 0% coverage.

The code compiles and runs normally (json_patch is an optional feature), so this is a **silent** gap. It's an API degradation introduced by this change.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok (json_patch doesn't exist)",
  "h(M^1) x lib(M)": "ok (but json_patch.c untested)",
  "h(fix) x lib(M)": "N/A (no fix as of 2024)"
 },
 "coverage_data": {
   "json_patch.c": "0% (249 lines never tested)",
   "verification": "Manual inspection of OSS-Fuzz fuzz directory"
 },
 "verdict": "PASS"
}
```

## 讲解

**json-c JSON Patch功能**：阳性 · 隐式 · 本次引入 · api

> 库添加了完整的JSON Patch模块，但OSS-Fuzz没有对应的fuzzer，导致新模块完全未被测试。

### 1. 库改了什么

这次提交新增了完整的JSON Patch功能：

**新增文件**：
- `json_patch.c` (249行) - JSON Patch实现
- `json_patch.h` (46行) - 公开API

**主要API**：
```c
int json_patch_apply(struct json_object *base, 
                     struct json_object *patch,
                     struct json_object **res,
                     json_patch_error *error);
```

**功能**：实现RFC 6902定义的6种操作
- add: 添加值
- remove: 删除值  
- replace: 替换值
- move: 移动值
- copy: 复制值
- test: 测试值

**测试覆盖**：commit同时添加了完整的单元测试（test_json_patch.c），但这是传统测试，不是fuzz测试。

### 2. 原来的harness

OSS-Fuzz中json-c有4个fuzzer（位于json-c仓库的fuzz/目录）：

1. **tokener_parse_ex_fuzzer.cc** - 测试JSON解析
2. **json_object_fuzzer.cc** - 测试对象操作
3. **json_pointer_fuzzer.cc** - 测试JSON Pointer (RFC 6901)
4. **json_array_fuzzer.cc** - 测试数组操作

这4个fuzzer都**不调用json_patch_apply()**，json_patch.c的249行代码完全不可达。

### 3. 为什么harness出问题了

json_patch是一个全新的功能模块，与现有fuzzer测试的功能（parsing, objects, arrays, pointers）是独立的。

**证据**：
1. 手动检查`projects/json-c/fuzz/`目录：没有json_patch_fuzzer.cc
2. json_patch.c自2021-04-24添加以来从未被fuzz测试
3. OSS-Fuzz的build.sh会编译fuzz/目录下的所有*_fuzzer.cc，但没有json_patch的

### 4. 怎么修

需要添加json_patch_fuzzer：

```cpp
// json_patch_fuzzer.cc
#include <json.h>
#include <stdint.h>

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size < 2) return 0;
    
    // Split input: first half as base, second half as patch
    size_t split = size / 2;
    
    // Parse base JSON
    struct json_object *base = json_tokener_parse_ex(
        (const char*)data, split);
    if (!base) return 0;
    
    // Parse patch JSON
    struct json_object *patch = json_tokener_parse_ex(
        (const char*)(data + split), size - split);
    if (!patch) {
        json_object_put(base);
        return 0;
    }
    
    // Apply patch
    struct json_object *result = NULL;
    json_patch_error error;
    json_patch_apply(base, patch, &result, &error);
    
    // Cleanup
    if (result) json_object_put(result);
    json_object_put(patch);
    json_object_put(base);
    
    return 0;
}
```

### 5. 为什么是这个标签

- **阳性**：新的JSON Patch功能完全未被fuzz测试，需要添加fuzzer。
- **隐式**：编译、链接、运行都正常。只有通过手动检查fuzz目录才能发现缺失。
- **本次引入**：json_patch模块是这次提交新增的。
- **API**：问题是新增的API模块没有对应的fuzzer。

### 6. 数据来源

- **库变更**: json-c commit `538b0468847660d52191ad202edb4ab585b6fd19`
- **旧harness**: json-c/fuzz/目录（M时刻和当前都一样，都没有json_patch_fuzzer）
- **验证**: 手动检查OSS-Fuzz和json-c仓库
- **RFC**: https://tools.ietf.org/html/rfc6902 (JSON Patch)
