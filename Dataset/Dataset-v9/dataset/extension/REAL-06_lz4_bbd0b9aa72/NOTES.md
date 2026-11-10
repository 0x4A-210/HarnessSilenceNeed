# REAL-06 — lz4 @ bbd0b9aa726a

- label: **positive** / silent / type `state` / introduced_by_this_change = **False**
- change: 无单一引入 commit —— 库的「压缩失败 → 状态置脏 → 复位时全量重建」语义早于本次修复就存在
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: in_repo ['ossfuzz/compress_hc_fuzzer.c', 'ossfuzz/fuzz_helpers.h', 'ossfuzz/fuzz_data_producer.h'] (target `compress_hc_fuzzer`)
- fix H: https://github.com/lz4/lz4/commit/bbd0b9aa726ac56d8cee4d31c0c913175561aab0

## 理由

lz4 的 HC 流对象**携带跨调用状态**：

1. `LZ4HC_compress_generic_internal()` 在压缩失败（`result <= 0`）时把 `ctx->dirty` 置为 1
2. 下一次 `LZ4_resetStreamHC_fast()` 看到脏标记，走全量重建分支，调用 `LZ4_initStreamHC()`
3. `LZ4_initStreamHC()` 用 `MEM_INIT(hcstate, 0, sizeof(*hcstate))` 把整个内部上下文清零

**副作用**：先前由 `LZ4_favorDecompressionSpeed()` 设好的 `favorDecSpeed` 也被清成 0，导致后续所有块都忽略用户请求的「解码速度优先」偏好（帧本身仍然合法，所以不会报错）。

修复只是在重建前后保存并恢复这一个字段。

**harness 侧的问题**：`compress_hc_fuzzer.c` 每轮输入都 `malloc(LZ4_sizeofStateHC())` 新建一个 state、用完 `free`，**从不复用**。因此：

- `dirty` 标记永远不会被置位
- 「失败后复位」这条路径永远走不到

编译与运行完全正常，两条相关分支的覆盖率恒为 0 —— 典型的**隐式（silent）state 退化**。

## Rationale

An lz4 HC stream object carries state across compressions: a failed compression sets `ctx->dirty`, and the next `LZ4_resetStreamHC_fast()` fully re-initialises the object through `LZ4_initStreamHC()`, which `MEM_INIT`s the whole internal context and thereby also clears `favorDecSpeed`. The change saves and restores that one field across the re-init. On the harness side, `compress_hc_fuzzer.c` allocates a fresh state per input and frees it afterwards, so the state is never reused: the dirty flag is never raised and the post-failure reset path is never taken, leaving those branches at zero coverage while the target still compiles and runs normally.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok (silent: state-reuse path unreachable)",
  "h(fix) x lib(M)": "ok"
 },
 "fuzz_M": {
  "harness": "h(M^1)", "lib": "M",
  "summary": "gap lines covered: 1/4, 1/4, 1/4 (3 runs); crashes: 0"
 },
 "with_fix": {
  "harness": "h(fix)", "lib": "M",
  "summary": "gap lines covered: 4/4, 4/4, 4/4 (3 runs); crashes: 0"
 },
 "explicit_signal": null,
 "verdict": "PASS"
}
```

### 实测一：三格 compile_matrix（gcc 15.2.0）

两棵源码树分别取自 `bbd0b9a^` 与 `bbd0b9a`，每格编译 `lib/lz4.c` + `lib/lz4hc.c` 并链接同一个行为探针（先设 `favorDecSpeed=1` → 标记 `dirty` → 调用 `LZ4_resetStreamHC_fast()` → 观测该字段）：

| 格 | 组合 | 构建 | 耗时 | `favorDecSpeed` |
|----|------|------|------|----------------|
| `h(M^1) × lib(M^1)` | 旧 harness × 旧库 | ok | 1.846s | **LOST**（缺陷存在） |
| `h(M^1) × lib(M)` | 旧 harness × 新库 | ok | 1.569s | **PRESERVED**（已修复） |
| `h(fix) × lib(M)` | 新 harness × 新库 | ok | 1.630s | **PRESERVED** |

关键读法：**格 2 的库已经修好，但 harness 仍然测不到**——因为 fuzzer 每轮 `malloc` 新 state、从不复用，那条复位路径根本不会被走到。三格全是 `ok`（无编译/链接失败），这正是「隐式」的体现。

### 实测二：fuzz_M / with_fix（clang 21.1.8 + llvm-cov gcov）

3 个 seed × 10 秒，统计 `lz4hc.c` 的 gap 行命中次数（1649/1650 是注释行，不计入可执行行）：

| 行号 | 含义 | `h(M^1)`（每轮新建 state） | `h(fix)`（复用 state） |
|------|------|--------------------------|----------------------|
| `1648` | `if (s->dirty)` 判断 | ~70–77 万 | ~142–153 万 |
| `1651` | `LZ4_i8 const favorDecSpeed = s->favorDecSpeed;` | **0** | 18–23 万 |
| `1652` | `LZ4_initStreamHC(...)` | **0** | 18–23 万 |
| `1653` | `s->favorDecSpeed = favorDecSpeed;` | **0** | 18–23 万 |

**这是「silent」最硬的证据**：旧 harness 确实每轮都调用了 `LZ4_resetStreamHC_fast()`（1648 命中 70 万+），但 `dirty` 分支体（1651-1653）**一次都没执行过**——因为 state 每轮都是新建的，永远不会带上「上次失败」的脏标记。换成复用 state 的 h(fix) 后，这三行稳定命中 18–23 万次。

两次运行均 `crashed: 0`，`execs` 在 70–77 万区间。

## 讲解

### 1. 库改了什么（input/change.diff）

```diff
 void LZ4_resetStreamHC_fast (LZ4_streamHC_t* LZ4_streamHCPtr, int compressionLevel)
 {
     LZ4HC_CCtx_internal* const s = &LZ4_streamHCPtr->internal_donotuse;
     if (s->dirty) {
+        /* a failed compression left the tables in an undefined state : start from scratch,
+         * but preserve parameters, as a reset without prior failure would */
+        LZ4_i8 const favorDecSpeed = s->favorDecSpeed;
         LZ4_initStreamHC(LZ4_streamHCPtr, sizeof(*LZ4_streamHCPtr));
+        s->favorDecSpeed = favorDecSpeed;
     } else {
         ...
```

### 2. 状态是如何被污染的

```
压缩失败 (result <= 0)
        │
        ▼
ctx->dirty = 1                    ← lib/lz4hc.c
        │
        ▼
LZ4_resetStreamHC_fast() 看到 dirty
        │
        ▼
LZ4_initStreamHC()
        │
        ▼
MEM_INIT(hcstate, 0, ...)         ← 整个上下文清零
        │
        ▼
favorDecSpeed 也从 1 变成 0        ← 缺陷
```

### 3. 原来的 harness（input/harness/ossfuzz/）

```c
void* state = malloc(LZ4_sizeofStateHC());        // 每轮新建
int const dstSize = LZ4_compress_HC_destSize(state, ...);
...
free(state);                                       // 用完即弃
```

实测该文件中：

| 关键调用 | 出现次数 |
|---------|---------|
| `LZ4_resetStreamHC_fast` | **0** |
| `LZ4_favorDecompressionSpeed` | **0** |

state 从未复用 → 脏标记永不置位 → 失败复位路径永不执行。

### 4. 为什么是「非本次引入」

按时间归因规则：

- **Source code 侧**：脏状态语义（`dirty` 字段、`result <= 0` 置位、复位时全量重建）在修复之前就存在
- **Source + diff 侧**：修复只是让重建时保留一个字段，没有新增「必须复用 state」这一要求
- **两侧被同一个阻塞挡住**：harness 从写下起就每轮新建 state，不复用

因此记为 `introduced_by_this_change = false`。

### 5. 为什么是这个标签

- **阳性**：harness 不复用 state，库的脏状态复位路径就永远测不到，需要更新 harness 才能覆盖
- **隐式**：编译运行一切正常，只是目标代码分支覆盖为 0
- **非本次引入**：见上
- **state**：阻塞点是「跨调用存活的状态没有被 harness 复用/驱动」

## 与 TOY-08 的对照

| | TOY-08 (strbuf) | REAL-06 (lz4) |
|---|-----------------|---------------|
| 库的新路径 | `sb_init()` 复用已初始化对象 | `resetStreamHC_fast` 失败后保留配置 |
| harness 写法 | 每输入新建零值对象、只 init 一次 | 每轮 malloc 新 state、用完即弃 |
| 结果 | 复用分支永远走不到 | 失败复位路径永远走不到 |
| 可见性 | silent | silent |

## 备注

1. **一处需要如实说明的限制**：探针里的 `dirty` 是**显式置位**的。我用 `LZ4_compress_HC_destSize` 构造的失败（`dstCapacity` 极小）并未自动把 `dirty` 置 1，因此「自然触发 dirty」的那条具体调用路径尚未单独复现。这不影响核心结论（harness 不复用 state ⇒ 该路径测不到），但写论文/验收时应如实标注。

2. **harness 位置特殊**：lz4 的 fuzz target 维护在库仓库的 `ossfuzz/` 目录，不在 oss-fuzz 仓库。这也解释了为什么 `oss_rev` 字段填的是 lz4 自己的 sha。

3. **`compile_matrix.secs` 的性质**：1.846 / 1.569 / 1.630 是「编译库 + 链接探针 + 运行」的实测耗时（gcc 15.2.0），**不是** `compress_hc_fuzzer` 完整 libFuzzer 构建的耗时（后者需 `-fsanitize=fuzzer`，本机未跑）。
