# REAL-02 — c-ares @ 7d3591ee8a

- label: **positive** / silent / type `api` / introduced_by_this_change = True
- change: https://github.com/c-ares/c-ares/commit/7d3591ee8a1a63e7748e68e6d880bd1763a32885 (getaddrinfo enhancements)
- origin: real_github; route: cispa_case_study; gt: TBD
- harness: oss ['test/ares-test-fuzz.c', 'test/ares-test-fuzz-name.c'] (targets `ares_parse_reply_fuzzer`, `ares_create_query_fuzzer`)
- fix H: TBD

## 理由

c-ares库对`getaddrinfo()`进行了大幅增强：
1. **增加Service支持** - getaddrinfo现在支持服务名解析
2. **代码重构** - ares_parse_a/aaaa_record与addrinfo parser共享代码
3. **扩展内部结构** - 私有ares_addrinfo结构增加了ttl和cname链
4. **新增核心函数**：
   - `ares__parse_into_addrinfo()` (266行)
   - `ares__readaddrinfo()` (261行)
5. **重写主函数** - ares_getaddrinfo.c从372行增加到933行

然而，旧的fuzz harness只调用基本的DNS解析和查询创建函数，不测试新增的getaddrinfo增强功能。新增的527行代码和重构的逻辑在旧harness下无法触达。

编译和运行都正常，所以这是**隐式**缺口。属于本次引入的API类退化。

## Rationale

The c-ares library significantly enhanced `getaddrinfo()`:
1. **Added Service support** - getaddrinfo now supports service name resolution
2. **Code refactoring** - ares_parse_a/aaaa_record now shares code with the addrinfo parser
3. **Extended internal structures** - private ares_addrinfo structure with ttl and cname chain support
4. **New core functions**:
   - `ares__parse_into_addrinfo()` (266 lines)
   - `ares__readaddrinfo()` (261 lines)
5. **Major rewrite** - ares_getaddrinfo.c grew from 372 to 933 lines

However, the old fuzz harness only calls basic DNS parsing and query creation functions, not testing the new getaddrinfo enhancements. The 527 lines of new code and refactored logic remain unreachable under the old harness.

The code compiles and runs normally, so this is a **silent** gap. It's an API degradation introduced by this change.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok (but new API code unreachable)",
  "h(fix) x lib(M)": "pending"
 },
 "coverage_data": {
   "before": "https://storage.googleapis.com/oss-fuzz-coverage/c-ares/reports/20190618/linux/src/c-ares/report.html",
   "after": "https://storage.googleapis.com/oss-fuzz-coverage/c-ares/reports/20190619/linux/src/c-ares/report.html"
 },
 "verdict": "PASS"
}
```

## 讲解 

**c-ares getaddrinfo增强**：阳性 · 隐式 · 本次引入 · api

> 库对getaddrinfo进行了重大增强和重构，但旧harness只测试基本功能，导致新API代码无法触达。

### 1. 库改了什么（`input/change.diff`）

这是一次大规模的API增强（+1899/-929行）：

**新增文件**：
- `ares__parse_into_addrinfo.c` (266行) - 将DNS响应解析到addrinfo结构
- `ares__readaddrinfo.c` (261行) - 读取和处理addrinfo数据
- `ares_freeaddrinfo.c` (57行) - 释放addrinfo结构

**主要变更**：
- `ares_getaddrinfo.c`: 372行 → 933行（完全重写，增加Service支持）
- `ares_parse_a_reply.c`: 重构，与addrinfo共享代码
- `ares_parse_aaaa_reply.c`: 重构，与addrinfo共享代码
- `ares.h`: 扩展公开API
- `ares_private.h`: 扩展私有ares_addrinfo结构

**核心改进**：
1. getaddrinfo现在支持服务名（如"http"）而不只是端口号
2. 返回完整的TTL信息
3. 支持CNAME链追踪
4. A/AAAA记录解析器重构为共享代码

### 2. 原来的harness（`input/harness/oss-fuzz/`）

OSS-Fuzz中c-ares有两个主要fuzzer：

**ares-test-fuzz.c** (ares_parse_reply_fuzzer):
```c
// 只测试DNS响应解析
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    // 调用各种 ares_parse_*_reply 函数
    // 不调用 ares_getaddrinfo 或新的 ares__parse_into_addrinfo
}
```

**ares-test-fuzz-name.c** (ares_create_query_fuzzer):
```c
// 只测试DNS查询创建
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    // 调用 ares_create_query, ares_mkquery 等
    // 不测试 getaddrinfo 的增强功能
}
```

### 3. 为什么harness出问题了

新增的API增强代码在旧harness下完全不可达：
- `ares__parse_into_addrinfo()` - 从未被调用
- `ares__readaddrinfo()` - 从未被调用
- `ares_getaddrinfo()` 的新逻辑（Service支持、TTL、CNAME链）- 未测试

根据CISPA的覆盖率报告：
- 2019-06-18（M前）: https://storage.googleapis.com/oss-fuzz-coverage/c-ares/reports/20190618/linux/src/c-ares/report.html
- 2019-06-19（M后）: https://storage.googleapis.com/oss-fuzz-coverage/c-ares/reports/20190619/linux/src/c-ares/report.html

新增的527行代码覆盖率为0%。

### 4. 怎么修（ground truth待定）

需要添加测试getaddrinfo的fuzzer：

```c
// getaddrinfo_fuzzer.c
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size < 2) return 0;
    
    // 分割输入：一部分作为hostname，一部分作为service
    size_t split = data[0] % size;
    
    char hostname[256];
    char service[256];
    size_t host_len = (split < 255) ? split : 255;
    size_t serv_len = ((size - split) < 255) ? (size - split) : 255;
    
    memcpy(hostname, data, host_len);
    hostname[host_len] = '\0';
    memcpy(service, data + split, serv_len);
    service[serv_len] = '\0';
    
    struct ares_addrinfo_hints hints;
    memset(&hints, 0, sizeof(hints));
    
    ares_getaddrinfo(channel, hostname, service, &hints, callback, NULL);
    // ... process results ...
}
```

### 5. 为什么是这个标签

- **阳性**：新的API增强功能完全未被测试，需要更新harness。
- **隐式**：编译、链接、运行都正常。只有通过覆盖率分析才能发现新代码未被触达。
- **本次引入**：getaddrinfo增强是这次提交新增的。
- **API**：问题的根源是harness没有调用新增/增强的API函数。

### 6. 数据来源

- **库变更**: c-ares commit `7d3591ee8a1a63e7748e68e6d880bd1763a32885`
- **旧harness**: c-ares仓库test/目录（M^1时刻）
- **CISPA案例研究**: https://raw.githubusercontent.com/CISPA-SysSec/fuzz-harness-degradation/main/case_studies/notes.md
- **覆盖率报告**: Google OSS-Fuzz Coverage Storage
