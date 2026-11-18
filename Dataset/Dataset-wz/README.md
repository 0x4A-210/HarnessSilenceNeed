# Fuzz Driver Dataset（真实案例版）v1

真实开源项目里"库更新 → OSS-Fuzz harness 退化"的阳性样本，格式对齐 ToyDataset v1（schema 3.0）。

## 当前进度

| Gap 类型            | 样本                 | 状态         |
| ----------------- | ------------------ | ---------- |
| configuration（显式） | REAL-01 abseil-cpp | ✅ 完整       |
| configuration（隐式） | REAL-08 libjpeg-turbo | ✅ 完整       |
| api（显式）           | REAL-02 ntpsec     | ✅ 完整（M/H 已验证） |
| api（隐式）           | REAL-07 libyaml    | ✅ 完整（非本次引入） |
| lifecycle（隐式）     | REAL-03 libarchive | ✅ 完整（非本次引入） |
| lifecycle（显式）     | REAL-09 binutils   | ✅ 完整（非本次引入） |
| mix（显式）           | REAL-05 ntpsec     | ✅ 完整（api + configuration） |
| mix（隐式）           | REAL-11 gdk-pixbuf | ✅ 完整（api + lifecycle，非本次引入） |
| input_format（隐式）  | REAL-04 libwebp    | ✅ 完整       |
| input_format（显式）  | REAL-12 lz4        | ✅ 完整（非本次引入） |
| state（隐式）          | REAL-06 lz4        | ✅ 完整（非本次引入） |
| state（显式）          | REAL-10 lz4        | ✅ 完整（非本次引入） |

## 目录结构（同 ToyDataset）

```
dataset/
├── README.md
├── index.json                      样本清单
└── cases/
    ├── explicit/                    显式型（编译/链接失败或运行即崩）
    │   └── <ID>_<类型>_<project>_<H 前 10 位>/   例：REAL-01_configuration_abseil-cpp_538e5a594e
    └── silent/                      隐式型（照常运行但目标代码测不到）
        └── <ID>_<类型>_<project>_<H 前 10 位>/   例：REAL-03_lifecycle_libarchive_d5b74d5cc
            ├── case.json            任务描述
            ├── label.json           标签与证据（schema 3.0）
            ├── meta.json            提交哈希、diff 统计等元数据
            ├── NOTES.md             人读说明 + 讲解
            ├── verification/        verification.json + source_blob_hashes_sha1.json（+ 坏 harness *.pre_fix / 复现探针）
            └── input/
                ├── change.diff      库的这次变更（git diff M^1..M）
                ├── source/          该 rev 的完整库树（保持原目录结构）
                └── harness/
                    └── oss-fuzz/    该 rev 的完整 harness 套件（Dockerfile/build.sh/project.yaml + 全部 target）
```

## 记号（同 ToyDataset）

- **M**：库的这次变更提交
- **M^1**：M 的父提交
- **h(M^1)**：变更时已有的 harness（`input/harness/`）
- **H**：修复 harness 的提交

## label.json 字段说明

与 ToyDataset schema 3.0 一致，关键字段：

- `label`：positive（harness 需要更新）/ negative
- `need_visibility`：explicit（编译/链接/运行崩）/ silent（覆盖率掉到 0）
- `degradation_type`：api / configuration / input_format / state / lifecycle / mix
- `gap.blockers`：导致退化的原因（kind + detail）
- `evidence`：支持标签的实验结论
- `verification`：compile_matrix 三格 + explicit_signal（显式）或 fuzz 覆盖率（隐式）

## 与 ToyDataset 的唯一区别

1. `discovery_route` = `mined`（真实挖掘），非 `constructed`；
2. `gt_source` = `oss_fuzz_fix`（以 OSS-Fuzz 真实 fix commit 为 ground truth），非 `counterfactual_fix`；
3. `change_origin` = `real`（真实变更），非 `synthetic_toy`。

## 待办（TODO）

已完成：
- REAL-02（**已替换**）：新版 M = `32a950f65`（2026-03-25 "nts now works with pool"）、H = `56131750d5491fafee3914bf8b855ab5868eddd5`（2026-04-05），主题为库首次引用 `dns_take_pool` 而 harness stub 未跟上导致链接失败（纯 api）。旧版（`nts_ke_process_receive` 签名变更）已弃用，该主题现由 REAL-05 承载。
- REAL-01/02/03/04/05/06：`gap_signature`、`patch_id` 均已计算，且五条互不冲突。
- REAL-02 / REAL-05 已完成三格 compile_matrix 实测（gcc 15.2.0）；REAL-01 已完成 `h(M^1) × lib(M)` 格实测（bazel 7.4.0）。
- REAL-05：mix（api + configuration）样本已落盘并实测，三个断点（api_signature / link_order / missing_symbol）分别复现。
- **REAL-06（新增）**：state / silent / `introduced_by_this_change=false`。lz4 的 HC 流对象在压缩失败后置脏，`LZ4_resetStreamHC_fast()` 全量重建会丢掉 `favorDecSpeed`；harness 每轮 `malloc` 新 state 从不复用，两条相关分支覆盖恒为 0。已在 `bbd0b9a^` 与 `bbd0b9a` 两棵树上实测（favorDecSpeed 1→0 / 保持 1）。
- **REAL-04（新增）**：input_format / silent / `introduced_by_this_change=true`。libwebp 的分配失败注入靠环境变量 `NALLOC_FREQ` 启用，而 `build.sh` 生成的 `_nalloc` 包装器把它写成了 `NALLOQ_FREQ`；`getenv` 取不到 + `nalloc_init(nullptr)` 落入禁用分支，四个 `_nalloc` target 两个月内一次失败都没注入。M=`fdc81cebda82`（2025-07-23）、H=`d5b388381230`（2025-09-21），修复只改一个字母。

- **REAL-08（新增）**：configuration / silent / `introduced_by_this_change=true`。libjpeg-turbo 3.0 beta1 的 M=`7fec5074f`（2022-03-08）把构建重构为 8/12/16-bit 同一套构建并把编译标志收敛到 `CDJPEG_COMPILE_FLAGS`，但 `fuzz/CMakeLists.txt` 没跟上，继续用旧路径和 `${COMPILE_FLAGS}`，缺 `BMP_SUPPORTED`/`GIF_SUPPORTED`/`PPM_SUPPORTED`/`TARGA_SUPPORTED` 四个宏 → `src/cjpeg.c` 的 `select_file_type()` 里四种格式 reader 被 `#ifdef` 编译掉，cjpeg_fuzzer 照常编译运行但四种格式永远测不到（silent）。H=`26553873dda0`（2026-01-30）的提交信息原文点名引入者并修复。补齐 configuration/silent 缺口。

- **REAL-09（新增）**：lifecycle / explicit / `introduced_by_this_change=false`。binutils `fuzz_readelf.c` 每轮迭代 free 三个 CTF 全局指针 `dump_ctf_symtab_name`/`dump_ctf_strtab_name`/`dump_ctf_parent_name` 但不置 NULL；libFuzzer 跨迭代复用同一进程，非 CTF 输入轮次 decoder 不重新分配、harness 又 free 同一悬垂指针 → double free → Abrt（issue 27734 标题即 "Abrt with empty stacktrace"）。修复 H=`9de297cc736f`（2021-01-20）只加三行置 NULL。已在本地 MinGW gcc 用最小探针实测：OLD 顺序 exit=127 崩、FIX 顺序 exit=0 存活。补齐 lifecycle/explicit 缺口。

- **REAL-10（新增）**：state / explicit / `introduced_by_this_change=false`。lz4 `round_trip_stream_fuzzer.c` 的 `state_create()` 对 `cstreamHC` 判空写了 `FUZZ_ASSERT(state.cstream)`（重复断言已非空的 cstream，而非新创建的 cstreamHC）；OOM 注入下 `LZ4_createStreamHC()` 返回 NULL 漏过断言，`state_reset()` 的 `LZ4_resetStreamHC_fast(NULL, level)` 解引用空指针崩。修复 H=`73ee988e95f9`（2026-10-10）只改一行断言。本地 MinGW gcc 最小探针实测：OLD 顺序 exit=139（Segfault）、FIX 顺序 exit=3（assert 拦截）。补齐 state/explicit 缺口。

- **REAL-11（新增）**：mix / silent / `introduced_by_this_change=false`。gdk-pixbuf `pixbuf_cons_fuzzer.c` 同时有 API 契约违规（`gdk_pixbuf_scale(pixbuf, pixbuf, ...)` src==dest 静默出 artifact）与对象泄漏（中间 `tmp` 反复覆写不 unref + `GBytes` 不释放，LSan 报 1704B/8alloc）两个独立 silent blocker。修复 H=`e244e64313bb`（2026-03-23）一次改三处（scale_simple + 逐个 unref + bytes unref），提交信息原文点明 "not a bug in gdk-pixbuf … a bug in the fuzz harness"。补齐 mix/silent 缺口。

- **REAL-12（新增）**：input_format / explicit / `introduced_by_this_change=false`。lz4 `compress_frame_fuzzer.c` 把 fuzz 字节交给 `FUZZ_dataProducer_create(data, LZ4_compressBound(size))`——尺寸参数应为输入字节数却传了压缩上界，`retrieve32()` 按膨胀后的 size 越界读 `*(data+size-4)` → heap-buffer-overflow 崩。修复 H=`192161e97e02`（2019-09-23）只把参数改回 size（提交标题原文 "… <- causes heap overflow"）。补齐 input_format/explicit 缺口，矩阵 12/12 全覆盖。

已移除：
- **REAL-04 zstd（原 input_format）**：实测推翻原标注。M 与 H 是同一个 commit（`741b87bbe1`），并非"先坏后修"；且 magicless 是 opt-in 特性——实测显示默认 DCtx 对标准帧仍返回 `ok`，旧 harness 用默认格式解标准帧完全正常，不存在"目标代码测不到"。该 commit 的性质是"库新增可选能力 + 同步补 fuzz"，不构成阳性样本。

待办：
- **矩阵 12/12 格全部补齐**（六类型 × 显隐，见下方矩阵）。input_format/explicit 由 REAL-12（lz4）补齐——注：本格最终按「fuzz 字节 → 程序输入的构造/映射方式错误」的定义落盘，而非最初设想的「库格式变更 → 旧 harness 解析崩」：后者在全量检索（oss-fuzz 2016→2026 全历史、20+ 库侧、跨库 commit 搜索、coverage 历史跌落、crash+fuzzer+fix 全 36 条核对）中确证无真阳性——库改格式几乎总向后兼容或与 harness 同步提交。
- 已排除的 input_format/explicit 候选（均非真阳性）：zstd magicless `741b87bb`（M==H 且 opt-in 特性，见「已移除」）；opencv `424072109061`（harness 无操作，open() 被注释成 TODO）；bzip2 `bfba469f6bc7`/`ebf450186035`（harness 整数溢出/自身 bug，非库格式变更）；jackson-dataformats-binary 各条（初始化 blocker）；uriparser `bdb0b339d`（未初始化变量）。这些要么是 harness 自身缺陷、要么是库 bug 修复，无一满足「库格式变更 M → 旧 harness 解析崩 + 独立修复 H」。

类型 × 可见性矩阵（12/12 格）：
```
api            explicit=REAL-02   silent=REAL-07   [OK]
configuration  explicit=REAL-01   silent=REAL-08   [OK]
input_format   explicit=REAL-12   silent=REAL-04   [OK]
lifecycle      explicit=REAL-09   silent=REAL-03   [OK]
mix            explicit=REAL-05   silent=REAL-11   [OK]
state          explicit=REAL-10   silent=REAL-06   [OK]
```

- 一个已验证但缺库侧变更的候选：**boost filesystem** `2e468d049`（`ConsumeRandomLengthString(5)` → 无上限，edge coverage 584→712，+21.92%），属 TOY-06 的"输入字母表受限"模式，可作 `introduced_by_this_change=false` 的 input_format 样本备选。
- 各条 `compile_matrix.secs` 多为 null；REAL-01 因修复版 WORKSPACE 需联网拉取 bazel_features / rules_cc，另两格未完成。
- `input/source/` 已按「完整库树」补齐（2026-11-16）：12 条各自放的是 `source_blob_hashes_sha1.json` 对应 rev 的**整棵树**，保持原目录结构，文件数与该 json 条目数一一相等（合计 42,086）。取树 rev 与依据见 `SOURCE_TREES.md`。此前「REAL-03/06/08 的 source 为空属预期」的说法已失效。
