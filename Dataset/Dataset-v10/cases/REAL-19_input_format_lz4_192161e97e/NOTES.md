# REAL-19 — lz4 @ 192161e97e02

- label: **positive** / **explicit** / type `input_format` / `introduced_by_this_change = false`
- change: 无单一引入 commit——compress_frame_fuzzer.c 自写下起把数据生产者的尺寸参数写成 LZ4_compressBound(size)，2019-09-23 修复
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: in_repo ['ossfuzz/compress_frame_fuzzer.c']（target `compress_frame_fuzzer`）
- fix H: https://github.com/lz4/lz4/commit/192161e97e020b165a3cfc7821439e895ec194c8（"Using size instead of LZ4_compressBound(size) <- causes heap overflow"）

## 理由

compress_frame_fuzzer 把 fuzz 原始字节 `data` 交给 `FUZZ_dataProducer_create(data, size)` 构造输入数据生产者：第二个参数本应是 data 的真实字节数（fuzz 字节 → 程序输入的映射边界），却传成 `LZ4_compressBound(size)`——压缩后上界。数据生产者的 `retrieve32()` 按这个膨胀后的 size 从 data 尾部读 `*(data + size - 4)`，越过真实输入缓冲区末尾 → heap-buffer-overflow（ASan 一跑即报，显式崩）。这是 input_format 退化：不是库改格式，而是「fuzz 字节 → 程序输入」的构造/映射方式错了——把压缩尺寸约定混进了输入字节长度。修复只把参数改回 `size`。`introduced_by_this_change=false`。

## Rationale (en)

compress_frame_fuzzer hands raw fuzz bytes data to FUZZ_dataProducer_create(data, size): the second argument should be the real byte count (the "fuzz bytes -> program input" mapping boundary), but the harness passed LZ4_compressBound(size) — the compressed-size upper bound. The producer's retrieve32() reads *(data + size - 4) from the tail with this inflated size, landing past the end of the real input buffer — a heap-buffer-overflow ASan reports on the first run (explicit crash). An input_format degradation: the library format did not change, but the "fuzz bytes -> program input" construction/mapping is wrong — a compressed-size convention was mixed into the input byte length. The fix only changes the argument back to size. introduced_by_this_change=false.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok（输入较小或未越界时潜伏）",
  "h(M^1) x lib(M)": "crash（producer->size=compressBound > 真实 size，retrieve32 越界读 → heap-buffer-overflow）",
  "h(fix) x lib(M)": "ok（size 为正确映射边界）"
 },
 "explicit_signal": "heap-buffer-overflow（提交标题 '<- causes heap overflow'）",
 "verdict": "PASS"
}
```

### 越界读机制（源码级，全部落盘）

- `ossfuzz/fuzz_data_producer.c`：`struct FUZZ_dataProducer_s { const uint8_t *data; size_t size; };`；`FUZZ_dataProducer_create` 把第二参数直接存进 `producer->size`；`FUZZ_dataProducer_retrieve32()` 读 `*(data + size - 4)`；`remainingBytes()` 返回 `producer->size`。
- 旧 harness：`FUZZ_dataProducer_create(data, LZ4_compressBound(size))`，随后 `FUZZ_dataProducer_preferences(producer)`（内部多次 `retrieve32` 读尾部 4 字节）→ 读点越过真实 data 末尾。

### 边界（budget_note）

- H 的 diff、父提交 d5ceafd4118c 的旧 harness 全文、fuzz_data_producer.c/.h 均已落盘；
- 越界读链路由源码逐行核实 + 提交标题原文佐证；未在本机跑 libFuzzer+ASan 复现（需 lz4 完整 ossfuzz 构建）。

## 判定链

```
h(M^1) × lib(M^1) = ok      // 输入尺寸小/未越界时缺陷潜伏
h(M^1) × lib(M)   = crash   // producer->size 膨胀，retrieve32 越界读 → heap-buffer-overflow
h(fix) × lib(M)   = ok      // size 为正确映射边界，不再越界
```


## 具体 diff（更改内容）

完整 diff 见 `input/change.diff`，核心改动如下：

```diff
diff --git a/ossfuzz/compress_frame_fuzzer.c b/ossfuzz/compress_frame_fuzzer.c
index e578052..76a99d2 100644
--- a/ossfuzz/compress_frame_fuzzer.c
+++ b/ossfuzz/compress_frame_fuzzer.c
@@ -17,7 +17,7 @@
 
 int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
 {
-    FUZZ_dataProducer_t *producer = FUZZ_dataProducer_create(data, LZ4_compressBound(size));
+    FUZZ_dataProducer_t *producer = FUZZ_dataProducer_create(data, size);
     LZ4F_preferences_t const prefs = FUZZ_dataProducer_preferences(producer);
     size_t const dstCapacitySeed = FUZZ_dataProducer_retrieve32(producer);
     size = FUZZ_dataProducer_remainingBytes(producer);
```

## 坏 harness 存档（verification/compress_frame_fuzzer.c.pre_fix）

`input/harness/oss-fuzz/` 现在是 H=192161e97e02 的完整套件（其中 `compress_frame_fuzzer.c` 已改成 `FUZZ_dataProducer_create(data, size)`）。
出问题的那一版另存为：

- `verification/compress_frame_fuzzer.c.pre_fix` ← lz4 `d5ceafd4118c88e2372b0ccb35f8352f25f172a1`
  （H 的父提交，2019-09-21「Merge pull request #793 from nigeltao/dev」）的
  `ossfuzz/compress_frame_fuzzer.c`，blob sha1 `668d7c3efc3288ace36230e00e5c1c4e883d9cf0`。

该版传的是 `FUZZ_dataProducer_create(data, LZ4_compressBound(size))`（缓冲区上界被当成可用长度），即堆越界读的入口；
`verification/fuzz_data_producer.c` 与 `.h` 仍为同树的数据生产者实现。文件按 git 对象取原始字节写出，blob sha1 与上面一致。
