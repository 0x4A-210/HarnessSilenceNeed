# REAL-15 — libjpeg-turbo @ 26553873dda0

- label: **positive** / **silent** / type `configuration` / `introduced_by_this_change = true`
- change: 库侧构建重构（M=7fec5074f，2022-03-08，libjpeg-turbo 3.0 beta1），harness 构建配置没跟上
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: in_repo ['fuzz/cjpeg.cc', 'fuzz/CMakeLists.txt']（target `cjpeg_fuzzer`，OSS-Fuzz 上传后叫 libjpeg_turbo_cjpeg_fuzzer）
- fix H: https://github.com/libjpeg-turbo/libjpeg-turbo/commit/26553873dda0b588964b583df489f6c88ca6927a（OSS-Fuzz: Fix cjpeg fuzzer，2026-01-30）

## 理由

M=7fec5074f 把 libjpeg-turbo 重构为 8/12/16-bit 同一套构建：cdjpeg.c 拆成 cjpeg.c/cdjpeg.c、rdppm.c 拆成 src/wrapper/rdppm-{8,12,16}.c，编译标志统一收敛到顶层 CMakeLists.txt 里的 CDJPEG_COMPILE_FLAGS（含 -DBMP_SUPPORTED -DGIF_SUPPORTED -DPPM_SUPPORTED -DTARGA_SUPPORTED）。但 fuzz/CMakeLists.txt 没跟上：继续用旧源文件路径、并把 COMPILE_FLAGS 设为 ${COMPILE_FLAGS}（不含四个宏）。由于 src/cjpeg.c 的 select_file_type() 用 #ifdef 包住 'B'/'G'/'P'/Targa 四个格式分支，四个宏缺失 → 这些 reader 被编译掉，任何 BMP/GIF/PPM/Targa 输入都落入 default 分支干净报错退出。cjpeg_fuzzer 照常编译、链接、运行，但四种格式的 reader 覆盖率恒为 0，而 harness 每次调用都传 -targa、注释还自称要测 "GIF and Targa readers"——属于「编译期配置项没生效」的隐式退化。

H 的提交信息原文点名了引入者："This was a regression introduced by 7fec5074f962b20ed00b4f5da4533e1e8d4ed8ac in libjpeg-turbo 3.0 beta1."

## Rationale (en)

M=7fec5074f restructured libjpeg-turbo into one 8/12/16-bit build: cdjpeg.c split into cjpeg.c/cdjpeg.c, rdppm.c into src/wrapper/rdppm-{8,12,16}.c, and the compile flags consolidated into CDJPEG_COMPILE_FLAGS (with -DBMP_SUPPORTED -DGIF_SUPPORTED -DPPM_SUPPORTED -DTARGA_SUPPORTED). fuzz/CMakeLists.txt fell behind, keeping the old source paths and ${COMPILE_FLAGS}. Since select_file_type() in src/cjpeg.c wraps the 'B'/'G'/'P'/Targa branches in #ifdef, the missing macros compile those readers out: every BMP/GIF/PPM/Targa input drops into the default branch and errors out cleanly. The fuzzer builds, links and runs, but the four format readers are unreachable — while the harness passes -targa each time and its comment claims to test "the GIF and Targa readers". This is a silent, compile-config degradation. H's commit message names the culprit "a regression introduced by 7fec5074f in libjpeg-turbo 3.0 beta1".

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok (silent: BMP/GIF/PPM/Targa readers compiled out; clean JERR_UNKNOWN_FORMAT / JERR_TGA_NOTCOMP)",
  "h(fix) x lib(M)": "ok (CDJPEG_COMPILE_FLAGS restores the four macros; readers reachable)"
 },
 "explicit_signal": null,
 "verdict": "PASS"
}
```

### 源码级证据（H=26553873dda0 树）

- 顶层 `CMakeLists.txt` L823-824：
  `set(CDJPEG_COMPILE_FLAGS "-DBMP_SUPPORTED -DGIF_SUPPORTED -DPPM_SUPPORTED -DTARGA_SUPPORTED ${USE_SETMODE}")`
- `src/cjpeg.c` `select_file_type()`：
  ```c
  if (is_targa) {
  #ifdef TARGA_SUPPORTED
      return jinit_read_targa(cinfo);
  #else
      ERREXIT(cinfo, JERR_TGA_NOTCOMP);
  #endif
  }
  ...
  switch (c) {
  #ifdef BMP_SUPPORTED  case 'B': return jinit_read_bmp(cinfo, TRUE); #endif
  #ifdef GIF_SUPPORTED  case 'G': return jinit_read_gif(cinfo); #endif
  #ifdef PPM_SUPPORTED  case 'P': ... #endif
  #ifdef TARGA_SUPPORTED case 0x00: return jinit_read_targa(cinfo); #endif
  default: ERREXIT(cinfo, JERR_UNKNOWN_FORMAT); break;
  }
  ```
- H 对 `fuzz/CMakeLists.txt` 的修复：`../cdjpeg.c → ../src/cdjpeg.c`、`../rdppm.c → ../src/wrapper/rdppm-{8,12,16}.c`、`COMPILE_FLAGS ${COMPILE_FLAGS} → ${CDJPEG_COMPILE_FLAGS}`。

### 本地宏开关探针（MinGW gcc 8.1.0）

`verification/probe_silent_reader.c` 用 `#ifdef TARGA_SUPPORTED` 复现 select_file_type 的开关。两种配置都能编译、都能运行、退出码都是 0：

```
$ gcc -o probe_old.exe   probe_silent_reader.c    # 旧配置（无宏），复现退化
$ gcc -DTARGA_SUPPORTED -o probe_fixed.exe probe_silent_reader.c  # 修复配置
$ ./probe_old.exe    → "reader targa UNREACHABLE -> clean reject" (exit=0)
$ ./probe_fixed.exe  → "reader targa reached"                    (exit=0)
```

### 边界（budget_note）

- M 的完整 82 文件 diff 已落盘并算得 `patch_id = 2ff69bb0e54fe6868968e8d5f1d8448503056b1a`；
- 未跑 libjpeg-turbo 带 SIMD/ASM 的完整 CMake 构建（本环境无 cmake/nasm），compile_matrix 的 `secs` 是脚本级复现耗时；
- 四种 reader 的真实覆盖率未从 OSS-Fuzz coverage bucket 取得。

## 判定链

```
h(M^1) × lib(M^1) = ok         // 旧配旧，基线（M 前使用 ../cdjpeg.c 等旧路径）
h(M^1) × lib(M)   = silent     // 旧 CMakeLists × 新库构建：编译运行正常，但四种格式 reader 编译掉、测不到
h(fix) × lib(M)   = ok         // H 用 CDJPEG_COMPILE_FLAGS + 新路径，reader 恢复可达
```


## 具体 diff（H 修复的内容）

注意：`input/change.diff` 是库侧 M=7fec5074f 的完整 82 文件重构 diff（238KB）。本条的退化修复是 H=26553873dda0 对 harness `fuzz/CMakeLists.txt` 的改动，即以下 `verification/CMakeLists.txt.pre_fix` → `verification/CMakeLists.txt.fixed` 的差异（`input/harness/oss-fuzz/CMakeLists.txt` 现在等于后者）：

```diff
@@ -25,27 +25,47 @@
   "${CMAKE_CXX_FLAGS} ${CMAKE_CXX_FLAGS_${CMAKE_BUILD_TYPE_UC}}")
 message(STATUS "C++ Compiler flags = ${EFFECTIVE_CXX_FLAGS}")
 
-add_executable(cjpeg_fuzzer cjpeg.cc ../cdjpeg.c ../rdbmp.c ../rdgif.c
-  ../rdppm.c ../rdswitch.c ../rdtarga.c)
-set_property(TARGET cjpeg_fuzzer PROPERTY COMPILE_FLAGS ${COMPILE_FLAGS})
-target_link_libraries(cjpeg_fuzzer ${FUZZ_LIBRARY} jpeg-static)
-install(TARGETS cjpeg_fuzzer RUNTIME DESTINATION ${FUZZ_BINDIR})
+add_executable(cjpeg_fuzzer${FUZZER_SUFFIX} cjpeg.cc ../src/cdjpeg.c
+  ../src/rdbmp.c ../src/rdgif.c ../src/wrapper/rdppm-8.c
+  ../src/wrapper/rdppm-12.c ../src/wrapper/rdppm-16.c ../src/rdswitch.c
+  ../src/rdtarga.c)
+set_property(TARGET cjpeg_fuzzer${FUZZER_SUFFIX} PROPERTY COMPILE_FLAGS
+  ${CDJPEG_COMPILE_FLAGS})
+target_link_libraries(cjpeg_fuzzer${FUZZER_SUFFIX} ${FUZZ_LIBRARY} jpeg-static)
+install(TARGETS cjpeg_fuzzer${FUZZER_SUFFIX}
+  RUNTIME DESTINATION ${FUZZ_BINDIR} COMPONENT bin)
 
 macro(add_fuzz_target target source_file)
-  add_executable(${target}_fuzzer ${source_file})
-  target_link_libraries(${target}_fuzzer ${FUZZ_LIBRARY} turbojpeg-static)
-  install(TARGETS ${target}_fuzzer RUNTIME DESTINATION ${FUZZ_BINDIR})
+  add_executable(${target}_fuzzer${FUZZER_SUFFIX} ${source_file})
+  target_link_libraries(${target}_fuzzer${FUZZER_SUFFIX} ${FUZZ_LIBRARY}
+    turbojpeg-static)
+  install(TARGETS ${target}_fuzzer${FUZZER_SUFFIX}
+    RUNTIME DESTINATION ${FUZZ_BINDIR} COMPONENT bin)
 endmacro()
 
 add_fuzz_target(compress compress.cc)
 
 add_fuzz_target(compress_yuv compress_yuv.cc)
 
+add_fuzz_target(compress_lossless compress_lossless.cc)
+
+add_fuzz_target(compress12 compress12.cc)
+
+add_fuzz_target(compress12_lossless compress12_lossless.cc)
+
+add_fuzz_target(compress16_lossless compress16_lossless.cc)
+
 # NOTE: This target is named libjpeg_turbo_fuzzer instead of decompress_fuzzer
 # in order to preserve the corpora from Google's OSS-Fuzz target for
 # libjpeg-turbo, which this target replaces.
 add_fuzz_target(libjpeg_turbo decompress.cc)
 
+add_executable(decompress_libjpeg_fuzzer${FUZZER_SUFFIX} decompress_libjpeg.cc)
+target_link_libraries(decompress_libjpeg_fuzzer${FUZZER_SUFFIX} ${FUZZ_LIBRARY}
+  jpeg-static)
+install(TARGETS decompress_libjpeg_fuzzer${FUZZER_SUFFIX}
+  RUNTIME DESTINATION ${FUZZ_BINDIR} COMPONENT bin)
+
 add_fuzz_target(decompress_yuv decompress_yuv.cc)
 
 add_fuzz_target(transform transform.cc)
```

## 坏 harness 存档（verification/CMakeLists.txt.pre_fix、verification/cjpeg.cc.pre_fix）

`input/harness/oss-fuzz/` 现在是 H=26553873dda0（2026-01-30「OSS-Fuzz: Fix cjpeg fuzzer」）的完整套件。
出问题时的那一版另存两份：

| 存档文件 | 来源 rev | 树内路径 | blob sha1 |
|---|---|---|---|
| `verification/CMakeLists.txt.pre_fix` | libjpeg-turbo `fc562d11f0574edf098047497af633b76e0974a2`（= M=7fec5074f 的父提交，2022-03-07「Bump version to 2.2 alpha1 ...」） | `fuzz/CMakeLists.txt` | `dcd19c3a892a991d422e2abe853e4048609e53cf` |
| `verification/cjpeg.cc.pre_fix` | 同上 | `fuzz/cjpeg.cc` | `ee7b7ab8c372ff47ab3e7ca46e619ec61ce31ff5` |

**为什么坏版取 M_parent 而不是 H^**：H^=3b18048a8ae7（2026-01-29）那一版的 `fuzz/CMakeLists.txt` 同样把
`COMPILE_FLAGS` 直接展开（M 之后父作用域已不再定义该变量，`-DBMP_SUPPORTED -DTARGA_SUPPORTED` 等全部丢失，
这正是本条的退化成因），但它的源文件路径已经改成 `../src/cdjpeg.c`、`../src/rd*.c`；而 `input/source/` 是 M 时点的树
（`cjpeg.c`、`rd*.c` 都还在仓库根），拿 H^ 的路径去配 M 的库树会直接找不到文件，重建不出本条记录的画面
（`rdtarga.o` 只剩 1.8KB 空壳、`jinit_read_targa` 等 4 个符号缺失、覆盖率 91 vs 1431）。
所以要重现「M 之后、H 之前」的坏状态，必须用 M_parent 那一版。

旧 `cjpeg.cc` 与 H 版也不是同一代写法（19+/35−），必须和旧 CMakeLists 配套：2022 版是
`#include "../cjpeg.c"` + `#define main cjpeg_main` + `mkstemp` 落盘再调 `cjpeg_main`；H 版已改成
`#include "../src/cjpeg.c"` + `cjpeg_fuzzer()` + `fmemopen`。两份一起存档才能重建坏配置。

两个 `.pre_fix` 均是按 git 对象取原始字节写出，现算 blob sha1 与表中值逐一相符。
