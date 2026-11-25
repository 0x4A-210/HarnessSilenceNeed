# SixTypeDataset New v2（六条 OSS-Fuzz 阳性样本）

六类各一条（api / configuration / input_format / state / lifecycle / mix），每条一个目录，位于 `dataset/cases/`。

> **2026-11-25 终检替换**：原 `SN-01`（haproxy `5b52df4c4d`，H `9fa746636837`）与
> [HarnessSilenceNeed](https://github.com/0x4A-210/HarnessSilenceNeed) `Dataset-v10/cases/REAL-25_api_haproxy_5b52df4c4d`
> **完全相同**（同 M、同 H）。按“与已有数据集不重复”的要求已移除（保存在 `_removed_duplicate_SN-01_api_haproxy_5b52df4c4d/`），
> 换成 `uber/h3` 的真实 OSS-Fuzz 案例。逐条去重见 `AUDIT.md`。

> **2026-11-25 终检复核**：直接对 GitHub / sourceware 拉取验证——SN-01/02/03/06 的 `input/source/`
> 与上游 M 的 git tree **逐 blob 完全一致**（h3 351/351、openh264 722/722、libplist 248/248、memcached 273/273），
> SN-04/05 的 M 在 sourceware 真实存在（源码为包含 M 的完整 release 树）；六条 H 均为真实 OSS-Fuzz 修复提交。
> 目录名统一按 M 前 10 位（SN-04→`45a7f5a29d`、SN-05→`ba64682044`）。详见 `AUDIT.md` §9。

| id | 类型 | 项目 | M | H | 源码文件数 | verdict |
|---|---|---|---|---|---|---:|---|
| SN-01 | `api` | h3 | `583de2fe5f6a68cb0040a955d87f16f9b9478e15` | `d5cf2bbe991b485a3b3a870f90a596c2f028100e` | 351 | PASS |
| SN-02 | `configuration` | openh264 | `3164a792a8a22f9d7456c7e2db9280ce5cc7e31b` | `3ad6236b0f0c58ec73ed09c90dea6eb4bfa4194b` | 722 | PASS |
| SN-03 | `input_format` | libplist | `60d291941fadb72b66d11502710add5899e21a2d` | `79f7772097edd3a28984398d073e92d27e345452` | 248 | PASS |
| SN-04 | `state` | binutils | `45a7f5a29de78755dd0d5e8f7beaf2bd07736d20` | `9af538448e597768723f17d44dcb67d0f9498d15` | 28449 | PASS |
| SN-05 | `lifecycle` | binutils | `ba64682044d3828909fd5356f0282abaaefa6425` | `db7354e3d31cd9052c0d8dd0b961c862fbb2e889` | 26930 | PASS |
| SN-06 | `mix` | memcached | `9723c0ea8ec1237b8364410ba982af8ea020a2b6` | `e75a15b717ea9a224ab289a9324539953389ab0d` | 273 | PASS |

M = 库的上游变更提交；H = 修 harness 的 OSS-Fuzz 提交。六条都满足
`introduced_by_this_change = true`：M 之前旧 harness 正常，M 之后不适配。

## 目录结构（与 ToyDataset 一致）

```
SixTypeDataset_new/
├── AUDIT.md                          终检报告、去重表、证据说明
├── dataset/
│   ├── README.md
│   ├── index.json                    六条清单
│   └── cases/
│       └── <ID>_<type>_<project>_<M 前 10 位>/
│           ├── case.json             任务描述：判断哪个 harness
│           ├── label.json            标签与证据（schema 3.0）
│           ├── meta.json             提交、harness 版本、diff 统计
│           ├── NOTES.md              人读说明：标签、理由、复验摘要、讲解
│           ├── input/
│           │   ├── change.diff       M^1 → M（git diff --full-index）
│           │   ├── source/           完整源码树
│           │   └── harness/oss-fuzz/ H^1 的 OSS-Fuzz 项目文件
│           └── verification/
│               ├── experiments.json
│               └── source_blobs.json input/source/ 每个文件的 git blob sha1
└── _evidence/<case>/                 构建/运行原始日志、H patch、M diff
```

## 源码完整性

- **SN-01（h3）**：`input/source/` 是 M 提交的**完整仓库树（351 个文件）**，与 GitHub 上 M 的 git blob **逐一比对，0 mismatch**（含全部 C 源码与构建文件）。
- **SN-02（openh264）/ SN-03（libplist）**：`input/source/` 与 M 的 Git tree 逐 blob 一致（722/722、248/248）。
- **SN-06（memcached）**：`input/source/` 是 1.6.22 release，与 `1.6.22` tag 的 tree 逐 blob 一致（273/273）；
  这一条是 release-to-release 样本（1.6.21→1.6.22，40 files），见 `AUDIT.md` §7。
- **SN-04 / SN-05（binutils）**：`input/source/` 是**完整的 binutils release 源码树**（2.44 / 2.40，28449 / 26930 个文件），
  包含 M；`change.diff` 是 M^1→M 的精确 diff。受网络限制没有下载“恰好等于 M”的 binutils 源码树，
  但**不是只放片段**，整棵 release 树都在；baseline 用 M 的前一个 release（2.43.1 / 2.39）验证。

## 验证

- SN-01：三格全部真实跑通——旧 harness × lib(M^1) exit 0；旧 harness × lib(M) 在 `h3NeighborRotations` 处
  AddressSanitizer SEGV；H 修复版 × lib(M) exit 0。verdict = `PASS`。
- SN-02：旧 build.sh 在 M 上 `codec_def.h: No such file or directory`；H 同步 include 路径后构建通过。
- SN-03：真实构建/运行 `oplist_fuzzer`，并用 gcov 记录 `oplist.c` 覆盖。
- SN-04：旧/修复 `fuzz_dlltool` 都在 binutils 2.44 上构建并运行；状态重置差异为静态证据。
- SN-05：旧 `fuzz_as` 在 binutils 2.40 上 SIGSEGV（exit 139），H 修复版 exit 0。
- SN-06：旧 harness 在 M 上编译失败（`proxy_init` 参数/新目标文件），H 修复版按正确 config 编译通过。

六条 `verdict` 均为 `PASS`。每条都有真实的构建/运行日志；SN-04 的 state 重置差异是 M diff + H patch 的确定性代码事实（NOTES 中注明为静态证据），其余均有实际编译/运行/gcov 日志。
