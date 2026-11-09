# 人工复核清单（20% 分层抽样）

共 11 条：10 条按（阳/阴 × 显式/隐式）分层抽样，另加 V3-13 flac。两名复核人**各自独立**只看 `input/` 与 `case.json` 先给出判断，再对照 `label.json` 与 `verification/`；不一致的样本回到实验数据裁决，结论填入 `review_sheet.csv`。

## 每条样本要核对的项

1. **变更真实性**：打开 `meta.json` 中的 M 链接，确认 `input/change.diff` 与上游 commit 一致（R2 样本只含库侧 hunk）。
2. **harness 归属**：harness 文件在 M^1 时存在且非空；in-tree 样本的 `input/source` 中 harness 为 M^1 版本。
3. **标签**：阳/阴、显式/隐式、本次/非本次、类型（mix 需核对 mix_components 每一项都必要）是否与理由及证据相符。
4. **证据**：显式——编译矩阵或 ASan 回放的栈顶帧；隐式——缺口行在无修复的 3 个种子中覆盖为 0、有修复的 ≥2 个种子中 >0；阴性——编译/回放无新失败、改动行被覆盖。
5. **修复 H / Δh**：H 是否真的只改 harness、是否对应同一缺口；Δh（counterfactual_fix.diff）是否 ≤30 行且只改 harness。
6. **非本次**：确认 M^1 上同样退化（交叉回放或 window_start 处的编译结果）。

## 抽中的样本

| 目录 | 内部 ID | 项目 | 路径 | 来源 | ground truth |
|---|---|---|---|---|---|
| V3-05_libucl_e83a16711e | V3-05 | libucl | `cases/positive/explicit/preexisting/lifecycle/V3-05_libucl_e83a16711e` | real_commit | maintainer_fix |
| V3-09_pcre2_32f03ad588 | V3-09 | pcre2 | `cases/positive/silent/introduced/configuration/V3-09_pcre2_32f03ad588` | real_commit | counterfactual_fix |
| V3-12_nlohmann-json_756b28c2b8 | V3-12 | nlohmann-json | `cases/positive/silent/preexisting/configuration/V3-12_nlohmann-json_756b28c2b8` | real_commit | maintainer_fix |
| V3-15_zstd_824f75ea7c | V3-15 | zstd | `cases/positive/silent/introduced/input_format/V3-15_zstd_824f75ea7c` | real_commit | counterfactual_fix |
| V3-17_libpng_397c7eea38 | V3-17 | libpng | `cases/positive/silent/preexisting/lifecycle/V3-17_libpng_397c7eea38` | real_commit | maintainer_fix |
| V3-26_lz4_950c1cecda | V3-26 | lz4 | `cases/negative/explicit/state/V3-26_lz4_950c1cecda` | real_commit | experiment |
| V3-27_miniz_9eedb97176 | V3-27 | miniz | `cases/negative/explicit/lifecycle/V3-27_miniz_9eedb97176` | real_commit | experiment |
| V3-31_libxml2_02cc5c3609 | V3-31 | libxml2 | `cases/negative/silent/api/V3-31_libxml2_02cc5c3609` | real_commit | experiment |
| V3-40_cmark_2734f21486 | V3-40 | cmark | `cases/negative/silent/api/V3-40_cmark_2734f21486` | real_commit | experiment |
| V3-46_nlohmann-json_8feaf8dc94 | V3-46 | nlohmann-json | `cases/positive/explicit/introduced/input_format/V3-46_nlohmann-json_8feaf8dc94` | real_commit | maintainer_fix |
| V3-13_flac_9c83e6e434 | V3-13 | flac | `cases/positive/explicit/preexisting/state/V3-13_flac_9c83e6e434` | real_commit | maintainer_fix |

