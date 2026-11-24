# REAL-21 — configuration / silent / speex

## 一句话

`build.sh` 用 `./configure --enable-fixed` 构建「定点」fuzz target，但 speex 的真实选项叫
`--enable-fixed-point`。autoconf 对未知选项只告警、不失败，于是 `speex_decode_fuzzer_fixed`
链接的是浮点库——**两个 target 字节完全相同**，定点解码器（526 行 `#ifdef FIXED_POINT` 代码）
从未被编译进任何产物。

## 判定链

| 环节 | 结果 |
|---|---|
| `configure --enable-fixed` | `WARNING: unrecognized options: --enable-fixed`，退出码 **0**，`config.h` 保持 `/* #undef FIXED_POINT */` |
| `configure --enable-fixed-point` | 无警告，`config.h` 为 `#define FIXED_POINT /**/` |
| `configure`（不带选项） | 与 `--enable-fixed` 完全一致 |
| 旧配置链接出的 `_fixed` vs `_float` | sha256 同为 `4b6b639b…`，同为 **2413504 字节** |
| 修复后 `_fixed` vs `_float` | `61af6068…`（2409656 B）≠ `ca42e8d7…`（2413504 B） |
| 四产物跑同一输入 | 全部 `rc=0`，无 ASan 报告 → **silent** |

`.text` 段逐成员指纹是更细的一层证据：旧配置（A）与「不带选项」（C）的 25 个目标文件
`.text` **逐字节相同**，而修复配置（B）与 C 有 13 个成员不同。

## 覆盖量化

同一 702 字节真实 `.spx`（speexenc 1.2.1 编码 8 kHz 正弦波）、同一 `-runs=2000 -seed=1`：

| 文件 | A 可执行行 | A 覆盖 | B 可执行行 | B 覆盖 |
|---|---|---|---|---|
| `filters.c` | 342 | 177 | 540 | 234 |
| `ltp.c` | 377 | 44 | 475 | 58 |
| `math_approx.h` | 71 | 20 | 161 | 46 |
| `vq.c` | 18 | 0 | 74 | 0 |
| `cb_search.c` | 336 | 31 | 378 | 34 |
| `lsp.c` | 167 | 57 | 191 | 72 |
| `lpc.c` | 34 | 0 | 53 | 0 |
| `stereo.c` | 136 | 19 | 145 | 29 |

多出来的 **526 行**全部落在 `#ifdef FIXED_POINT` 分支里，在旧产物中可执行行数为 **0**；
修复后其中 **125 行**被执行到。反向，旧产物独有 `filters_sse.h`(200) / `vq_sse.h`(76) /
`ltp_sse.h`(49) / `cb_search_sse.h`(41) 共 366 行浮点专用 SSE 头。

## 为什么是 silent 而不是 explicit

四个产物（A_fixed / A_float / B_fixed / B_float）跑同一条输入全部 `rc=0`、fuzzer 内 3–5 ms、
无任何 sanitizer 报告。退化不产生运行期输出——`configure` 的那条 WARNING 是唯一的痕迹，
而它出现在构建期、且不影响退出码。

这也是本条与 REAL-15 的关键差别：REAL-15（libjpeg-turbo 漏传四个 `*_SUPPORTED` 宏）
至少还能从「输入落 default 分支」看出间接迹象；本条连这个都没有，
**只有把两个 target 的二进制摆在一起比对**才会发现它们是同一个文件。

## 带病时间

`1bc9696491`（2019-06-19，`[speex] add fuzzer targets (#2529)`）的 `build.sh` 第 29 行就已经是
`--enable-fixed`，该提交同时新增 `Dockerfile` / `project.yaml` / `build.sh` 三个文件。
修复 `3675fa9bf6`（2025-01-10，`speex: fix configure option for fixed-point (#12928)`）只改这一行。
**约 5 年 7 个月**里，所有归到 fixed target 名下的 fuzz 结果其实都来自浮点实现。

## 复现

```bash
# 干净树，只跑 configure
./configure --enable-static --disable-shared --enable-fixed   # → WARNING + #undef FIXED_POINT
./configure --enable-static --disable-shared --enable-fixed-point  # → #define FIXED_POINT

# 按 build.sh 两步构建后比对
sha256sum $OUT/speex_decode_fuzzer_fixed $OUT/speex_decode_fuzzer_float
# 旧配置：两个哈希相同；修复后：不同
```

## 文件清单

- `input/change.diff` — H 的全量 diff（717 字节，单文件单 hunk）
- `input/harness/oss-fuzz/{build.sh,Dockerfile,project.yaml}` — H 版构建套件
- `input/harness/speex/contrib-oss-fuzz/{speexdec_fuzzer.cc,speexenc_fuzzer.cc}` — fuzzer 源码（在 speex 仓库内）
- `input/source/` — speex 1.2.1 完整源码树（238 文件）
- `verification/build.sh.pre_fix` — 旧版构建脚本
- `verification/config_option_effect.txt` — 三次 configure 的告警与 `config.h` 状态
- `verification/same_target_sha256.txt` — 两步构建产物指纹
- `verification/text_fp_{A,B,C}.txt` — 非插桩构建的 `.text` 逐成员指纹
- `verification/covrep_{A,B}.txt` + `cov_compare.txt` — llvm-cov 行覆盖与对比表
- `verification/run_four_targets.txt` — 四产物运行结果
- `verification/sample_input.spx` — 702 字节真实 Speex 输入
- `verification/source_blob_hashes_sha1.json` — 238 个文件的 git blob sha1

## 限制（如实披露）

- 未在 OSS-Fuzz 容器内构建（本地无 docker），用同版本 clang 21.1.8 + 1.2.1 release tarball 复现；
  `compile_matrix` 的 `secs` 留空，不给构建耗时结论。
- 覆盖对比只用了 1 条真实输入 + 2000 次确定性变异，覆盖面有限；
  这足以证明「定点实现是否存在」，但不足以给出定点实现的完整覆盖画像。
