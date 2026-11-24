# REAL-14 — libyaml @ d94076d68f

- label: **positive** / silent / type `api` / introduced_by_this_change = **False**
- change: 无单一引入 commit —— 倒置判断随 harness 引入即存在（`8a74af8f5`, 2020-08-12）
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: oss ['projects/libyaml/libyaml_emitter_fuzzer.c', 'projects/libyaml/yaml_write_handler.h'] (target `libyaml_emitter_fuzzer`)
- fix H: https://github.com/google/oss-fuzz/commit/d94076d68f841419e155dad6c43e399b2824dbf3

## 理由

libyaml 的全部 `yaml_*_event_initialize()` 遵循 **1 = 成功、0 = 失败** 的约定，harness 的 `copy_event()` 只是把它们包了一层。但 harness 在第 250 行把返回值**当布尔真值直接判断**：

```c
if (copy_event(&events[event_number++], &event)) {
    yaml_event_delete(&event);
    goto delete_parser;      // ← 成功时反而走错误路径
}
```

**对任何合法 YAML 输入，fuzzer 在解析出的第一个 event 处就短路退出。** 后面的代码全部成为死代码：

- `yaml_emitter_emit()` —— 整个发射器路径
- 第二遍解析循环（重解析输出并比对 event）
- `events_equal()` 比对逻辑

commit message 自己的估计：**约 50% 的 fuzzer 逻辑是死代码**。

编译、链接、运行全部正常，崩溃率也没变化 —— 只是**一半逻辑永远执行不到**。典型的**隐式（silent）api 退化**。

## Rationale

Every `yaml_*_event_initialize()` in libyaml follows the convention 1 = success, 0 = failure, and the harness's `copy_event()` merely wraps them. Yet line 250 tests the return value directly as a boolean, so it takes the error path precisely when the call succeeds. For any valid YAML input the fuzzer short-circuits at the very first event it parses, leaving the emitter path, the second parse loop and `events_equal()` as dead code. Compilation, linking and execution are all normal and the crash rate does not change — roughly half of the fuzzer's logic never runs.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok (silent: emitter path unreachable)",
  "h(fix) x lib(M)": "ok"
 },
 "fuzz_M": { "parse_events": 20, "gap_hits": {"emitter_emit": 0, "second_parse_loop": 0, "events_equal": 0} },
 "with_fix": { "parse_events": 202, "gap_hits": {"emitter_emit": 202, "second_parse_loop": 18, "events_equal": 190} },
 "explicit_signal": null,
 "verdict": "PASS"
}
```

### 实测（gcc 15.2.0 + libyaml master）

给两版 harness 各注入 4 个计数器，用 20 个种子输入（10 种 YAML 结构 × 是否 canonical）驱动：

| 指标 | `h(M^1)` | `h(fix)` |
|------|---------|---------|
| `parse_events` | **20** | **202** |
| `gap_emit`（`yaml_emitter_emit` 调用次数） | **0** | **202** |
| `gap_reparse`（第二遍解析循环） | **0** | **18** |
| `gap_equal`（`events_equal` 比对） | **0** | **190** |

**关键读法**：旧 harness 用 20 个输入只解析出 **20 个 event —— 正好每个输入 1 个**，即在第一个 event 就停了。修复版同样 20 个输入解析出 **202 个**。

### H 自带的覆盖率证据（commit message）

| 指标 | 修复前 | 修复后 | 变化 |
|------|--------|--------|------|
| Edges | 166 | **2479** | **+1393%** |
| Features | 437 | 10285 | **+2253%** |
| Corpus | 135 | 2258 | +1573% |

## 讲解

### 1. 库的约定是什么

`yaml_*_event_initialize()` 系列全部返回 `int`，**1 表示成功，0 表示失败**。这是 libyaml 的标准约定，`writer.c` 里的用法可以佐证：

```c
if (emitter->write_handler(emitter->write_handler_data, ...) {
    ...
} else {
    return yaml_emitter_set_writer_error(emitter, "write error");
}
```

### 2. harness 怎么用错的

```c
bool copy_event(yaml_event_t *event_to, yaml_event_t *event_from) {
  switch (event_from->type) {
  case YAML_STREAM_START_EVENT:
    return yaml_stream_start_event_initialize(...);   // 返回 1 = 成功
  ...
}
```

调用处：

```c
if (copy_event(&events[event_number++], &event)) {     // 1 为真 → 进错误分支
    yaml_event_delete(&event);
    goto delete_parser;
}
```

**判断反了。** 修复只是加一个 `!`：

```diff
-    if (copy_event(&events[event_number++], &event)) {
+    if (!copy_event(&events[event_number], &event)) {
```

### 3. 倒置造成的连锁死代码

```
第一个 event 解析出来
        │
        ▼
copy_event() 成功返回 1
        │
        ▼
if (1) → goto delete_parser     ← 直接跳走
        │
        ▼
后面全部不执行：
  · yaml_emitter_emit()        ← 发射器路径
  · 第二遍 parse + events_equal ← 输出正确性校验
```

### 4. 顺带修的两个被掩盖的问题

**Bug 2**：`event_number++` 写在函数调用参数里。如果 `copy_event` 失败，`event_number` 已经自增，但 `events[old]` 未初始化，后面的清理循环会对未初始化对象调 `yaml_event_delete()`。

**Bug 3**：空 YAML 流时 emitter 无输出，`out.buf` 为 NULL，第二遍解析把它传给 `yaml_parser_set_input_string()`，而该函数有 `assert(input)`。第 1 个 bug 掩盖了这个问题（第二遍循环从没执行过）。

### 5. 为什么是「非本次引入」

倒置判断从 `copy_event()` **被引入那一刻就是错的**：

```bash
git log -S "copy_event" -- projects/libyaml/
# 8a74af8f5  2020-08-12  [libyaml] Add more fuzz targets (#4043)
```

```diff
+    if (copy_event(&events[event_number++], &event)) {     ← 2020 年引入时就写反了
```

它一直存活到 **2026-03-07**，**约 5 年半**。期间没有任何库侧变更要求「新增这个能力」，是 harness 从一开始就用错了。

按时间归因规则：Source code 侧和 Source+diff 侧都不要求「新增能力」，属于 harness 自身长期缺陷，故 `introduced_by_this_change = false`。

### 6. 为什么是这个标签

- **阳性**：不修 harness，约一半逻辑永远测不到
- **隐式**：编译、链接、运行全部正常，崩溃率不变
- **非本次引入**：见上
- **api**：阻塞点是**返回值约定被误读**，不是签名变化

## 与 TOY-02 / REAL-02 的关系

| | TOY-02 | REAL-14（本条） | REAL-02 |
|---|--------|----------------|---------|
| 约定 | `num_parse()` 成功 1 / 失败 0 | `yaml_*_event_initialize()` 成功 1 / 失败 0 | — |
| harness 判断 | 把 `!= 0` 当失败 | 把真值当失败 | — |
| 结果 | `num_kind()` 永收 0 | emitter 路径永远死代码 | — |
| 可见性 | silent | **silent** | explicit（缺符号，链接失败） |

本条与 `TOY-02` 结构完全同构，是它在真实项目里的对应物。

## 备注

1. **一处必须说明的探针改动**：上游 `yaml_output_buffer_t out = {NULL, 0, /*capacity=*/1000}` 里 `capacity=1000` 但 `buf=NULL`，导致第一次 write 时既不进 `realloc` 分支、又因 `buf` 为空直接返回失败（实测报 `emit fail @8: write error`）。这是 harness 的**另一个独立缺陷**，会掩盖第二遍解析路径。探针里把 capacity 改成 0 之后，才测出 `gap_reparse` / `gap_equal`。

2. **统计口径**：`gap_hits` 是 harness 内注入的**调用计数器**，不是 gcov 行覆盖。选这个口径是因为 gap 位置在 harness 自身代码里，计数器比行覆盖更直观。

3. **未独立复跑的部分**：H 的 commit message 里 166→2479 的 edges 数字没有自己重跑，只作为佐证引用。

4. **harness 在 oss-fuzz 仓库**（`kind = oss`），所以 `input/harness/oss-fuzz/` 放的是 `libyaml_emitter_fuzzer.c` + `yaml_write_handler.h` 两个文件。


## 具体 diff（更改内容）

完整 diff 见 `input/change.diff`，核心改动如下：

```diff
diff --git a/projects/libyaml/libyaml_emitter_fuzzer.c b/projects/libyaml/libyaml_emitter_fuzzer.c
index 817416123227..dc1651c92060 100644
--- a/projects/libyaml/libyaml_emitter_fuzzer.c
+++ b/projects/libyaml/libyaml_emitter_fuzzer.c
@@ -247,10 +247,11 @@ int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
       goto delete_parser;
     }
 
-    if (copy_event(&events[event_number++], &event)) {
+    if (!copy_event(&events[event_number], &event)) {
       yaml_event_delete(&event);
       goto delete_parser;
     }
+    event_number++;
 
     if (!yaml_emitter_emit(&emitter, &event)) {
       goto delete_parser;
@@ -260,6 +261,9 @@ int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
 
   yaml_parser_delete(&parser);
 
+  if (!out.buf || out.size == 0)
+    goto error;
+
   done = false;
   if (!yaml_parser_initialize(&parser))
     goto error;
--
2.43.0
```
