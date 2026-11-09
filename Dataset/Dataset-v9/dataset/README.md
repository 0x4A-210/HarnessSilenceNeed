# Harness Degradation 数据集 v9

共 **48** 条样本，编号 V3-01…V3-48，来自 32 个开源项目的真实 commit，没有构造数据。每条样本给出一次库变更和当时的 fuzz harness，任务是判断 harness 是否已经退化、需要更新。

schema 3.0 · 更新于 2026-11-09

## 目录结构

```
dataset/
  cases/              48 条样本
    positive/<显隐>/<引入>/<类型>/<样本>/
    negative/<显隐>/<类型>/<样本>/
  extension/          4 条目：2 条扩展样本 + 2 条被替换下来的旧样本，都不计入 48 条
  dataset.json        机器可读清单：分布、样本列表、判定标准、采集偏差
  canonical_map.csv   项目 → 规范仓库、样本编号
  known_windows.csv   已知退化窗口，阴性样本的 M 不能落在同一 harness 的窗口内（也含没有样本的项目）
  review/             人工复核清单 checklist.md 和记录表 review_sheet.csv
```

每条样本的目录名为 `<编号>_<项目>_<M 前 10 位>`，内容如下：

```
input/          评测时只给模型这部分和 case.json
  source/       变更之后的完整工作树（V3-06 的 harness 为 M^1 版本）
  harness/      harness 文件和构建脚本
  change.diff   M^1 → M 的 diff
case.json       任务描述，不含标签
label.json      标签、证据、中英文理由、验证结果
meta.json       上游地址、M / M^1 / H、OSS-Fuzz 修订、diff 统计
NOTES.md        人类可读说明
verification/   实验记录和修复 diff
```

## 术语

| 术语 | 含义 |
|---|---|
| M | 被研究的库变更 commit |
| M^1 | M 的第一个父提交，即变更之前的版本 |
| H | 维护者修复 harness 的 commit |
| 阳 / 阴 | harness 退化、需要更新 / 没有退化 |
| 显式（阳性） | 构建失败，或语料回放时出现 harness 相关的崩溃、断言、泄漏 |
| 隐式（阳性） | 能构建能运行，但缺口代码没有被覆盖：无修复时 3 个种子覆盖均为 0，有修复时至少 2 个种子覆盖 > 0 |
| 显式（阴性） | M 前后都能构建，语料回放没有新崩溃，改动行被固定语料覆盖 |
| 隐式（阴性） | 满足显式阴性的条件，且改动行在 3 个 fuzz 种子中至少 2 个被覆盖 |
| 本次 / 非本次 | 退化由 M 引入 / M^1 上已经存在（只用于阳性） |

| 类型 | 含义 |
|---|---|
| api | harness 调用的公开 API 的签名、语义变化，或新增必须调用的 API |
| configuration | 编译宏、运行时 flags / options、构建开关 |
| input_format | 可接受的输入格式、语法、编码、magic |
| state | 内部状态、全局变量、reset / 复用约定 |
| lifecycle | 初始化、销毁、创建顺序、所有权 |
| mix | 同时涉及上面至少两类 |

## 分布

每个格子都达到目标：阳性每格 1 条，阴性每格 2 条。

| 类型 | 阳-显式-本次 | 阳-显式-非本次 | 阳-隐式-本次 | 阳-隐式-非本次 | 阴-显式 | 阴-隐式 | 合计 |
|---|---|---|---|---|---|---|---|
| api | 1 | 1 | 1 | 1 | 2 | 2 | 8 |
| configuration | 1 | 1 | 1 | 1 | 2 | 2 | 8 |
| input_format | 1 | 1 | 1 | 1 | 2 | 2 | 8 |
| state | 1 | 1 | 1 | 1 | 2 | 2 | 8 |
| lifecycle | 1 | 1 | 1 | 1 | 2 | 2 | 8 |
| mix | 1 | 1 | 1 | 1 | 2 | 2 | 8 |
| **合计** | 6 | 6 | 6 | 6 | 12 | 12 | **48** |

| 维度 | 分布 |
|---|---|
| 标签 | 阳 24，阴 24 |
| 可见性 | 显式 24，隐式 24 |
| 阳性的引入方式 | 本次 12，非本次 12 |
| ground truth | experiment 24（阴性实验结论），maintainer_fix 18，counterfactual_fix 5，coupled_commit 1 |
| 变更来源 | real_commit 47，real_commit_lib_hunks_only 1（V3-06，耦合 commit 只保留库侧改动，harness 停在 M^1） |
| 样本来源 | HarnessDegradation-v3 46，HarnessDegradation-MiniDataset-v5 2（V3-47、V3-48） |
| 项目 | libyaml 3，zstd 3，cjson 2，cmark 2，expat 2，jansson 2，json-c 2，libspng 2，libxml2 2，lz4 2，nlohmann-json 2，pugixml 2，utf8proc 2，zlib 2，binutils-gas 1，c-ares 1，flac 1，fmt 1，jq 1，libcbor 1，libpng 1，libucl 1，mbedtls 1，md4c 1，miniz 1，nghttp2 1，pcre2 1，postgresql 1，tinyobjloader 1，tinyxml2 1，unbound 1，xz 1 |

## 样本一览

| 编号 | 目录 | 标签 | 可见性 | 引入 | 类型 | ground truth | M |
|---|---|---|---|---|---|---|---|
| V3-01 | V3-01_zlib_f8719f5ae5 | 阳 | 显式 | 本次 | api | maintainer_fix | [f8719f5ae5](https://github.com/madler/zlib/commit/f8719f5ae5acdc31d3794ddfea8ac963359de41e) (2018-12-26) |
| V3-02 | V3-02_c-ares_0bf721cdd7 | 阳 | 显式 | 本次 | configuration | maintainer_fix | [0bf721cdd7](https://github.com/c-ares/c-ares/commit/0bf721cdd7f64b893c4ad015c341de680617411b) (2020-09-09) |
| V3-03 | V3-03_jq_6ce3bdf382 | 阳 | 显式 | 非本次 | configuration | maintainer_fix | [6ce3bdf382](https://github.com/jqlang/jq/commit/6ce3bdf3829fc15030e084119535b059f4f09e74) (2025-02-06) |
| V3-04 | V3-04_json-c_9749b0cb66 | 阳 | 显式 | 非本次 | api | maintainer_fix | [9749b0cb66](https://github.com/json-c/json-c/commit/9749b0cb66b32ddac4bbbca28dd9009968722a9f) (2022-07-30) |
| V3-05 | V3-05_libucl_e83a16711e | 阳 | 显式 | 非本次 | lifecycle | maintainer_fix | [e83a16711e](https://github.com/vstakhov/libucl/commit/e83a16711eedc9ee2219748f9a427f94b1bb70a5) (2026-10-03) |
| V3-06 | V3-06_mbedtls_ae35830295 | 阳 | 显式 | 本次 | mix（api, lifecycle） | coupled_commit | [ae35830295](https://github.com/Mbed-TLS/mbedtls/commit/ae35830295073b6ea7f327e6e42ccdc41dda5ed1) (2021-06-18) |
| V3-07 | V3-07_lz4_d5ceafd411 | 阳 | 显式 | 非本次 | input_format | maintainer_fix | [d5ceafd411](https://github.com/lz4/lz4/commit/d5ceafd4118c88e2372b0ccb35f8352f25f172a1) (2019-09-21) |
| V3-08 | V3-08_unbound_8c751d48a2 | 阳 | 显式 | 非本次 | mix（api, configuration） | maintainer_fix | [8c751d48a2](https://github.com/NLnetLabs/unbound/commit/8c751d48a24b74e4ac0bbfd948d2b7e87dd87f6a) (2023-09-07) |
| V3-09 | V3-09_pcre2_32f03ad588 | 阳 | 隐式 | 本次 | configuration | counterfactual_fix | [32f03ad588](https://github.com/PCRE2Project/pcre2/commit/32f03ad588908bdf3365e6fe827465ec0a0cfcc8) (2024-10-02) |
| V3-10 | V3-10_libyaml_588eabff23 | 阳 | 隐式 | 非本次 | api | maintainer_fix | [588eabff23](https://github.com/yaml/libyaml/commit/588eabff23ba2292f537872bbea5b64bce1e1a21) (2024-05-06) |
| V3-11 | V3-11_utf8proc_9842b738ed | 阳 | 隐式 | 非本次 | input_format | maintainer_fix | [9842b738ed](https://github.com/JuliaStrings/utf8proc/commit/9842b738ed779aad54b5d12af950bec80f9d76a1) (2026-09-23) |
| V3-12 | V3-12_nlohmann-json_756b28c2b8 | 阳 | 隐式 | 非本次 | configuration | maintainer_fix | [756b28c2b8](https://github.com/nlohmann/json/commit/756b28c2b85d668c9e74e3fc3c4688039ebc2901) (2026-10-04) |
| V3-13 | V3-13_flac_9c83e6e434 | 阳 | 显式 | 非本次 | state | maintainer_fix | [9c83e6e434](https://github.com/xiph/flac/commit/9c83e6e434143afba6eee8550aa8dcc9160fccf7) (2023-03-11) |
| V3-14 | V3-14_xz_fe4d763d56 | 阳 | 隐式 | 非本次 | state | maintainer_fix | [fe4d763d56](https://github.com/tukaani-project/xz/commit/fe4d763d566a38ad61d4c5022520c25578a3a464) (2026-09-09) |
| V3-15 | V3-15_zstd_824f75ea7c | 阳 | 隐式 | 本次 | input_format | counterfactual_fix | [824f75ea7c](https://github.com/facebook/zstd/commit/824f75ea7c48a2db26693699a2178ecea84dfb7a) (2017-09-28) |
| V3-16 | V3-16_json-c_6eac6986c9 | 阳 | 隐式 | 本次 | state | counterfactual_fix | [6eac6986c9](https://github.com/json-c/json-c/commit/6eac6986c9a734b183e55a80e84fa67e58c637ff) (2020-06-27) |
| V3-17 | V3-17_libpng_397c7eea38 | 阳 | 隐式 | 非本次 | lifecycle | maintainer_fix | [397c7eea38](https://github.com/pnggroup/libpng/commit/397c7eea385c22b6033e0310badfadbd9f578422) (2017-09-19) |
| V3-18 | V3-18_libxml2_2829a21a95 | 阳 | 隐式 | 本次 | lifecycle | counterfactual_fix | [2829a21a95](https://github.com/GNOME/libxml2/commit/2829a21a956d2d11bb533aaa4a7298918580569d) (2023-12-21) |
| V3-19 | V3-19_utf8proc_3522df61f0 | 阴 | 显式 | — | mix（api, input_format） | experiment | [3522df61f0](https://github.com/JuliaStrings/utf8proc/commit/3522df61f03ecb1e5787696c901b8bce23705855) (2026-10-12) |
| V3-20 | V3-20_pugixml_71418cc5c9 | 阴 | 显式 | — | api | experiment | [71418cc5c9](https://github.com/zeux/pugixml/commit/71418cc5c971346e009e2d76084cb569ced3add9) (2026-06-13) |
| V3-21 | V3-21_jansson_fa27c14fea | 阴 | 显式 | — | api | experiment | [fa27c14fea](https://github.com/akheron/jansson/commit/fa27c14fea399c3bfdef663d1d4c3e2300b15bdb) (2026-06-30) |
| V3-22 | V3-22_cjson_542fb0eadd | 阴 | 显式 | — | lifecycle | experiment | [542fb0eadd](https://github.com/DaveGamble/cJSON/commit/542fb0eadd3db62630c1eb958e685f1d8e30694e) (2024-05-13) |
| V3-23 | V3-23_libyaml_840b65c406 | 阴 | 显式 | — | input_format | experiment | [840b65c406](https://github.com/yaml/libyaml/commit/840b65c40675e2d06bf40405ad3f12dec7f35923) (2024-05-20) |
| V3-24 | V3-24_libcbor_031dc9eb75 | 阴 | 显式 | — | input_format | experiment | [031dc9eb75](https://github.com/PJK/libcbor/commit/031dc9eb7583aaff47f2b0182ef0558c7f5c8870) (2026-09-17) |
| V3-25 | V3-25_cmark_d8de8c7686 | 阴 | 显式 | — | configuration | experiment | [d8de8c7686](https://github.com/commonmark/cmark/commit/d8de8c7686e439ea6ae0e659ef5a86a16d1262d0) (2024-04-02) |
| V3-26 | V3-26_lz4_950c1cecda | 阴 | 显式 | — | state | experiment | [950c1cecda](https://github.com/lz4/lz4/commit/950c1cecda204fdb9b93ec492a1cbe5fcb5d2a76) (2026-10-09) |
| V3-27 | V3-27_miniz_9eedb97176 | 阴 | 显式 | — | lifecycle | experiment | [9eedb97176](https://github.com/richgel999/miniz/commit/9eedb97176408008a2263cef9b4bac5c7f955d4f) (2022-02-27) |
| V3-28 | V3-28_zstd_ed6953772f | 阴 | 显式 | — | configuration | experiment | [ed6953772f](https://github.com/facebook/zstd/commit/ed6953772f41ff9308dd958a35e24ec613b83878) (2023-05-22) |
| V3-29 | V3-29_tinyxml2_26ab0bd591 | 阴 | 显式 | — | mix（lifecycle, state） | experiment | [26ab0bd591](https://github.com/leethomason/tinyxml2/commit/26ab0bd591bdfb7991cc76e3d1348ddf8aa33934) (2026-05-23) |
| V3-30 | V3-30_md4c_1e82998ea3 | 阴 | 隐式 | — | mix（configuration, input_format） | experiment | [1e82998ea3](https://github.com/mity/md4c/commit/1e82998ea3619d4239ca5d0468370bf754bb2740) (2026-05-01) |
| V3-31 | V3-31_libxml2_02cc5c3609 | 阴 | 隐式 | — | api | experiment | [02cc5c3609](https://github.com/GNOME/libxml2/commit/02cc5c3609532709a180287a8d901fe31c452520) (2024-01-05) |
| V3-32 | V3-32_fmt_56e63078ff | 阴 | 隐式 | — | configuration | experiment | [56e63078ff](https://github.com/fmtlib/fmt/commit/56e63078ffa3db89d2ae82b38686c9e8f34d51d2) (2020-07-03) |
| V3-33 | V3-33_zstd_26486db9ab | 阴 | 隐式 | — | configuration | experiment | [26486db9ab](https://github.com/facebook/zstd/commit/26486db9ab20fdd8b8c77cdbafd46a338a3e1199) (2021-10-08) |
| V3-34 | V3-34_tinyobjloader_7b3ba0be71 | 阴 | 隐式 | — | input_format | experiment | [7b3ba0be71](https://github.com/tinyobjloader/tinyobjloader/commit/7b3ba0be7146b0414463203c31bdf6a9376accb2) (2024-01-27) |
| V3-35 | V3-35_libspng_e68ba5df57 | 阴 | 隐式 | — | input_format | experiment | [e68ba5df57](https://github.com/randy408/libspng/commit/e68ba5df571726bf001d9ea150980463ea395a75) (2023-04-28) |
| V3-36 | V3-36_expat_34b598c5f5 | 阴 | 隐式 | — | state | experiment | [34b598c5f5](https://github.com/libexpat/libexpat/commit/34b598c5f594b015c513c73f06e7ced3323edbf1) (2024-01-30) |
| V3-37 | V3-37_jansson_c52e770a3f | 阴 | 隐式 | — | lifecycle | experiment | [c52e770a3f](https://github.com/akheron/jansson/commit/c52e770a3f153701b0b41f9d76bd478a771f23ac) (2026-06-13) |
| V3-38 | V3-38_pugixml_a3fad540a7 | 阴 | 隐式 | — | mix（configuration, lifecycle） | experiment | [a3fad540a7](https://github.com/zeux/pugixml/commit/a3fad540a70bbba9349e8361aff8bff4dfdf7e67) (2020-09-10) |
| V3-39 | V3-39_cjson_5cc0e39f42 | 阴 | 隐式 | — | lifecycle | experiment | [5cc0e39f42](https://github.com/DaveGamble/cJSON/commit/5cc0e39f42dfe28cb8541f95fa2c513f0d550210) (2026-02-25) |
| V3-40 | V3-40_cmark_2734f21486 | 阴 | 隐式 | — | api | experiment | [2734f21486](https://github.com/commonmark/cmark/commit/2734f2148612767d28c12c17abd2e95d55d3f396) (2024-08-18) |
| V3-41 | V3-41_libyaml_8362c8dd96 | 阴 | 隐式 | — | state | experiment | [8362c8dd96](https://github.com/yaml/libyaml/commit/8362c8dd96b644bda4e4d24cc405ef7f0e642d21) (2026-05-05) |
| V3-42 | V3-42_zlib_767c4c9478 | 阴 | 显式 | — | state | experiment | [767c4c9478](https://github.com/madler/zlib/commit/767c4c947852e143f582c85f14cf573411df1b35) (2026-09-20) |
| V3-43 | V3-43_expat_ed80eaea0c | 阳 | 隐式 | 本次 | api | maintainer_fix | [ed80eaea0c](https://github.com/libexpat/libexpat/commit/ed80eaea0ce7179b56713fb22fe933b993aee814) (2026-04-20) |
| V3-44 | V3-44_libspng_3a115ee4bf | 阳 | 隐式 | 非本次 | mix（configuration, input_format） | maintainer_fix | [3a115ee4bf](https://github.com/randy408/libspng/commit/3a115ee4bf1292030370fabf4cf15723f4b660ab) (2019-01-26) |
| V3-45 | V3-45_nghttp2_d1e07ab6b7 | 阳 | 隐式 | 本次 | mix（configuration, input_format） | counterfactual_fix | [d1e07ab6b7](https://github.com/nghttp2/nghttp2/commit/d1e07ab6b728e7cba16f37ff17b5b6eb68c91e9d) (2022-06-13) |
| V3-46 | V3-46_nlohmann-json_8feaf8dc94 | 阳 | 显式 | 本次 | input_format | maintainer_fix | [8feaf8dc94](https://github.com/nlohmann/json/commit/8feaf8dc94a88393510637af36a24163c95a1b45) (2017-03-12) |
| V3-47 | V3-47_postgresql_b406478b87 | 阳 | 显式 | 本次 | lifecycle | maintainer_fix | [b406478b87](https://github.com/postgres/postgres/commit/b406478b87e2234c0be4ca4105eee3bb466a646b) (2021-08-05) |
| V3-48 | V3-48_binutils-gas_af3d7ab74f | 阳 | 显式 | 本次 | state | maintainer_fix | [af3d7ab74f](https://sourceware.org/git/?p=binutils-gdb.git;a=commit;h=af3d7ab74f0aff2eb2af68d0d1df2e27e5757ecd) (2022-07-09) |

## 扩展样本

`extension/` 下另有 4 个目录，都不计入上面的 48 条和分布：

- **扩展样本** 2 条（V3-13_fmt、V3-49_zstd）：额外收集、不进入主集的样本。
- **被替换下来的旧样本** 2 条（V3-12_inih、V3-33_zlib）：原来的 V3-12、V3-33，2026-11-09 分别被 nlohmann-json、zstd 的新样本替换后移到这里，目录名加了后缀标明原因（`-CompileError`：旧 inih 样本编译失败；`-HarnessBroken`：旧 zlib 样本 harness 失效）。

编号 V3-12、V3-13、V3-33 都同时用于 `extension/` 和 `cases/`（如 V3-13 用于 fmt（这里）和 flac（`cases/`），V3-12 用于旧 inih（这里）和 nlohmann-json（`cases/`）），需要用目录名区分。

| 编号 | 目录 | 标签 | 可见性 | 引入 | 类型 | ground truth | M | 说明 |
|---|---|---|---|---|---|---|---|---|
| V3-13 | V3-13_fmt_5420bcce2d | 阳 | 隐式 | 本次 | configuration | counterfactual_fix | [5420bcce2d](https://github.com/fmtlib/fmt/commit/5420bcce2d29f10129ea75bc863cf52ddd03ac29) (2019-11-18) | 扩展样本 |
| V3-49 | V3-49_zstd_9c3265a53f | 阳 | 显式 | 本次 | mix（api, state） | coupled_commit | [9c3265a53f](https://github.com/facebook/zstd/commit/9c3265a53f0431d388b00d420d7ee7418207e174) (2018-12-10) | 扩展样本 |
| V3-12 | V3-12_inih_498f34b786-CompileError | 阳 | 隐式 | 非本次 | configuration | counterfactual_fix | [498f34b786](https://github.com/benhoyt/inih/commit/498f34b78610cf9e42197d22730c91f942431ea4) (2025-07-10) | 旧样本，被 nlohmann-json 替换（编译失败） |
| V3-33 | V3-33_zlib_fd366384cf-HarnessBroken | 阴 | 隐式 | — | configuration | experiment | [fd366384cf](https://github.com/madler/zlib/commit/fd366384cf324d750596feb03be44ddf4d1e6acd) (2026-01-05) | 旧样本，被 zstd 替换（harness 失效） |

## 更多信息

- 判定标准、采集偏差、工具链：`dataset.json` 的 `conventions`、`deviations_from_plan`、`toolchain`
- 复验：`collection_tools/tools/verify_v6.py <dataset 根目录>`，需要上游仓库的本地克隆
