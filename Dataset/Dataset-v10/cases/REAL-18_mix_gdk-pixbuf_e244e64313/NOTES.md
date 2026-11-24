# REAL-18 — gdk-pixbuf (oss-fuzz) @ e244e64313bb

- label: **positive** / **silent** / type `mix`（api + lifecycle）/ `introduced_by_this_change = false`
- change: 无单一引入 commit——pixbuf_cons_fuzzer.c 自写下起同时存在 scale src==dest 契约违规与中间对象/GBytes 泄漏，2026-03-23 一并修复
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: oss ['projects/gdk-pixbuf/targets/pixbuf_cons_fuzzer.c']（target `pixbuf_cons_fuzzer`）
- fix H: https://github.com/google/oss-fuzz/commit/e244e64313bb7795a8665c974205712780eee5da

## 理由

pixbuf_cons_fuzzer 同时带两个相互独立的静默缺陷。其一 API 契约违规：`gdk_pixbuf_scale(pixbuf, pixbuf, ...)` 把同一个 pixbuf 既当 src 又当 dest，官方文档要求二者必须不同、重叠会 "overwritten … rendering artifacts"——缩放静默地把原地像素覆盖成错误结果，正确路径测不到。其二生命周期泄漏：rotate/flip/composite 返回的中间 GdkPixbuf 反复覆写 `tmp` 从不 unref，`GBytes` 也不释放，每轮泄漏 1704 字节（LSan 可见）。两条都照常编译、链接、运行、不崩，但目标代码测不到、错误结果静默蔓延——多 blocker 同时静默的 mix。修复一次改三处。`introduced_by_this_change=false`（提交信息明确 "not a bug in gdk-pixbuf … a bug in the fuzz harness"）。

## Rationale (en)

pixbuf_cons_fuzzer carries two independent silent defects. One, an API contract violation: gdk_pixbuf_scale(pixbuf, pixbuf, ...) uses the same pixbuf as both src and dest, which the docs require to differ and warn that overlap yields "overwritten … rendering artifacts" — the scaling silently clobbers pixels and the correct path is never tested. Two, object-lifecycle leaks: rotate/flip/composite intermediates repeatedly overwrite tmp without unref, and GBytes is never freed (1704 bytes/iteration under LSan). Both compile, link and run without crashing, yet the target code is unreachable and wrong results spread silently — a mix with several simultaneous silent blockers, fixed in one commit. introduced_by_this_change=false ("not a bug in gdk-pixbuf … a bug in the fuzz harness").

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok (silent: scale src==dest 静默 artifact + 每轮泄漏 1704B)",
  "h(fix) x lib(M)": "ok (scale_simple + 逐个 unref + bytes unref)"
 },
 "explicit_signal": null,
 "verdict": "PASS"
}
```

### 两个 blocker 的证据

1. **api_contract_violation**（P2，原文照抄）：
   "gdk_pixbuf_scale(pixbuf, pixbuf, ...) uses the same pixbuf as both source and destination. The API documentation requires they be different."
   文档：`If the source rectangle overlaps the destination rectangle on the same pixbuf, it will be overwritten during the scaling which results in rendering artifacts.`
2. **lifecycle_object_leak**（P1，原文照抄）：
   "Multiple intermediate GdkPixbuf objects leaked — tmp is overwritten repeatedly without freeing previous values … Also, GBytes from g_bytes_new_static() is never freed."
   LSan 报告：`SUMMARY: AddressSanitizer: 1704 byte(s) leaked in 8 allocation(s)`，且 "triggers on the first seed corpus input and is 100% reproducible"。

### 边界（budget_note）

- H 的完整 diff、父提交 e946b5e412fd 的旧 harness、修复版均已落盘；
- 静默属性由提交信息原文 + 官方 API 文档语义证实；泄漏数字照抄 H 的 LSan 报告原文；未在本地跑 gdk-pixbuf + LSan（无 gtk 依赖）。

## 判定链

```
h(M^1) × lib(M^1) = ok      // 旧 harness 旧库，编译运行正常（两个 silent blocker 潜伏）
h(M^1) × lib(M)   = silent  // scale 静默 artifact + 中间对象/GBytes 泄漏，均测不到正确处理路径
h(fix) × lib(M)   = ok      // scale_simple + 逐个 unref + bytes unref
```


## 具体 diff（更改内容）

完整 diff 见 `input/change.diff`，核心改动如下：

```diff
diff --git a/projects/gdk-pixbuf/targets/pixbuf_cons_fuzzer.c b/projects/gdk-pixbuf/targets/pixbuf_cons_fuzzer.c
index c1ba15d..5fd4b01 100644
--- a/projects/gdk-pixbuf/targets/pixbuf_cons_fuzzer.c
+++ b/projects/gdk-pixbuf/targets/pixbuf_cons_fuzzer.c
@@ -24,7 +24,7 @@ int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
         return 0;
     }
     const gchar *profile;
-    GdkPixbuf *pixbuf, *tmp;
+    GdkPixbuf *pixbuf, *tmp, *tmp2;
     GBytes *bytes;
     bytes = g_bytes_new_static(data, size);
     pixbuf = g_object_new(GDK_TYPE_PIXBUF,
@@ -36,25 +36,32 @@ int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
             "pixel-bytes", bytes,
             NULL);
     if (pixbuf == NULL) {
+        g_bytes_unref(bytes);
         return 0;
     }
-    gdk_pixbuf_scale(pixbuf, pixbuf,
-            0, 0, 
-            gdk_pixbuf_get_width(pixbuf) / 4, 
+
+    tmp = gdk_pixbuf_scale_simple(pixbuf,
+            gdk_pixbuf_get_width(pixbuf) / 4,
             gdk_pixbuf_get_height(pixbuf) / 4,
-            0, 0, 0.5, 0.5,
             GDK_INTERP_NEAREST);
+    if (tmp) g_object_unref(tmp);
+
     unsigned int rot_amount = ((unsigned int) data[0]) % 4;
     tmp = gdk_pixbuf_rotate_simple(pixbuf, rot_amount * 90);
+    if (tmp) g_object_unref(tmp);
+
     tmp = gdk_pixbuf_flip(pixbuf, TRUE);
+    if (tmp) g_object_unref(tmp);
+
     tmp = gdk_pixbuf_composite_color_simple(pixbuf,
-            gdk_pixbuf_get_width(pixbuf) / 4, 
+            gdk_pixbuf_get_width(pixbuf) / 4,
             gdk_pixbuf_get_height(pixbuf) / 4,
             GDK_INTERP_NEAREST,
             128,
             8,
             G_MAXUINT32,
             G_MAXUINT32/2);
+    if (tmp) g_object_unref(tmp);
 
     char *buf = (char *) calloc(size + 1, sizeof(char));
     memcpy(buf, data, size);
@@ -66,15 +73,17 @@ int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
             GDK_COLORSPACE_RGB,
             FALSE,
             gdk_pixbuf_get_bits_per_sample(pixbuf),
-            gdk_pixbuf_get_width(pixbuf), 
+            gdk_pixbuf_get_width(pixbuf),
             gdk_pixbuf_get_height(pixbuf),
             gdk_pixbuf_get_rowstride(pixbuf),
             NULL,
             NULL);
-    tmp = gdk_pixbuf_flip(tmp, TRUE);
+    tmp2 = gdk_pixbuf_flip(tmp, TRUE);
+    if (tmp) g_object_unref(tmp);
 
     free(buf);
+    g_bytes_unref(bytes);
     g_object_unref(pixbuf);
-    g_object_unref(tmp);
+    if (tmp2) g_object_unref(tmp2);
     return 0;
 }
```

## 坏 harness 存档（verification/pixbuf_cons_fuzzer.c.pre_fix）

`input/harness/oss-fuzz/` 现在是 H=e244e64313bb 的完整套件（`targets/pixbuf_cons_fuzzer.c` 已改成 `scale_simple`、逐个 unref、unref bytes）。
出问题的那一版另存为：

- `verification/pixbuf_cons_fuzzer.c.pre_fix` ← oss-fuzz `e946b5e412fd0be65c0cc191186c00304349935b`
  （H 的父提交，2026-03-22「cairo: fix raster_fuzzer — remove PDF API calls that prevent acquire callback (#15086)」）的
  `projects/gdk-pixbuf/targets/pixbuf_cons_fuzzer.c`，blob sha1 `c1ba15dbd4398b3d5b3db000436f0c81be82ff8a`。

该版用 `gdk_pixbuf_scale()` 原地缩放同一对象、只 unref 一次，也没有 `tmp2`；与
`verification/pixbuf_cons_fuzzer.c.fixed` 相减即 H 的 18+/9− 改动。文件按 git 对象取原始字节写出，blob sha1 与上面一致。
