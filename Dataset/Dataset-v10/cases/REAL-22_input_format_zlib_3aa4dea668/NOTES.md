# REAL-22 — zlib @ 3aa4dea668

- label: **positive** / **explicit** / type `input_format` / `introduced_by_this_change = false`
- change: 无库侧变更；OSS-Fuzz 的 `zlib_uncompress3_fuzzer` 自身把三字节乘积当成输出缓冲区容量
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: `oss` `['projects/zlib/zlib_uncompress3_fuzzer.cc']`（target `zlib_uncompress3_fuzzer`）
- fix H: https://github.com/google/oss-fuzz/commit/3aa4dea6681e006c906cbb72138bb14937422252（2026-04-04，PR #15266）

## 理由

旧 harness 的输入约定是「前三个字节是三个乘数，其余是压缩流」：

```c
static Bytef buffer[256 * 1024] = { 0 };            // 真实目标缓冲区：固定 262144 字节
uLong basesz      = size ? (--size, *data++) : 8;
uLong multiplier0 = size ? (--size, *data++) : 1;
uLong multiplier1 = size ? (--size, *data++) : 1;

uLongf buffer_length = basesz * multiplier0 * multiplier1;   // ≤ 255*255*255 = 16,581,375
uncompress2(buffer, &buffer_length, data, &buf_size);        // buffer_length 是「可写容量」入参
```

`uncompress2` 的 `destLen` 是**入参容量**：库照着这个数决定能往 `buffer` 写多少。三个字节相乘最大 1660 万，
而 `buffer` 只有 262144 字节 —— harness 等于向库声明「有 8 MB 可写」。inflate 照办，解压到第 262145 字节就越界。
修复 H 只加三行：

```c
if (buffer_length > sizeof(buffer))
    buffer_length = sizeof(buffer);
```

这是 input_format 类型的退化：不是库改格式，而是「fuzz 字节 → 程序输入」的**尺寸约定**错了 —— 把「解压后可能多长」
当成了「缓冲区有多大」，没和真实缓冲区尺寸对齐。`introduced_by_this_change = false`：该 fuzzer 2025 年加入时就这样。

## Rationale (en)

The old harness's input convention is "first three bytes are multipliers, the rest is a deflate stream". But
`uncompress2`'s `destLen` is an **input**: the capacity the library may write into. The product of three bytes reaches
16.6M while the real buffer is a fixed 262144-byte global, so the harness effectively declares "8 MB writable" and
inflate runs past the end at byte 262145. H adds a three-line clamp to `sizeof(buffer)`. This is an input_format
degradation: the library format did not change; the "fuzz bytes -> program input" size convention is wrong — "how long
the output might be" was treated as "how large the buffer is". `introduced_by_this_change=false`: the fuzzer was added
in 2025 already in this shape.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok (旧 harness 编译链接成功)",
  "h(M^1) x lib(M)":   "fail (explicit: ASan global-buffer-overflow，0 bytes after global 'buffer' size 262144)",
  "h(fix) x lib(M)":   "ok (clamp 后同输入干净退出)"
 },
 "explicit_signal": "AddressSanitizer: global-buffer-overflow（inffast.c:254 inflate_fast，越界 0 字节）",
 "verdict": "PASS"
}
```

### 确定性复现（clang 21.1.8 + ASan，zlib @1c2519c8）

构造输入 `verification/sample_input_overflow.bin`（1042 字节）：

```
C8 C8 C8                → basesz=200, multiplier0=200, multiplier1=200
                            => buffer_length = 8,000,000（声明容量）
<deflate stream>        → 解压后 1,048,576 字节（1 MiB 零字节）
```

旧 harness（`verification/asan_old_harness.log`）：

```
==1783==ERROR: AddressSanitizer: global-buffer-overflow ...
    #4 ... in LLVMFuzzerTestOneInput .../zlib_uncompress3_fuzzer.cc.pre_fix:35:3
0x...fe0 is located 0 bytes after global variable 'buffer' defined in
          .../zlib_uncompress3_fuzzer.cc.pre_fix:23 ... of size 262144
SUMMARY: AddressSanitizer: global-buffer-overflow .../inffast.c:254:32 in inflate_fast
```

新 harness 同一输入：正常退出、无任何 sanitizer 报告（`verification/run_new_harness.log`）。

### 一个值得记的细节：30s 随机 fuzz 找不到它

`verification/fuzz30_old_harness.log`：空语料跑 30 秒，0 崩溃。原因是要同时满足三件事——乘积 > 262144、
存在合法 deflate 流、解压后长度 > 262144 —— 随机变异在 30s 内撞不出来。这既解释了它为什么能长期躺在 OSS-Fuzz
里不被发现，也说明本条的判定不能靠"fuzz 没崩"来否定，必须用构造输入。

## 判定链

```
h(H^1) × lib(zlib@1c2519c8) = fail/explicit   // 声明容量 8,000,000 → 越界写
h(H)   × lib(zlib@1c2519c8) = ok              // clamp 到 262144 → Z_BUF_ERROR
```

无库侧 M，两侧共用同一棵 zlib 树，故 `introduced_by_this_change=false`。

## 边界（budget_note）

- 崩溃为确定性复现，非 fuzz 发现；30s 探索性 fuzz 明确 0 崩溃，已如实记录；
- 未跑 3×3600s 完整 campaign，未统计修复后 `uncompress2` 的返回值分布；
- zlib 树取 H 时代 HEAD `1c2519c8`（2026-02-23），与 OSS-Fuzz Dockerfile 的 `git clone` 行为一致。
