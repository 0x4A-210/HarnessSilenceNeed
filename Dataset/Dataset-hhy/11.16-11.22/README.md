# SixTypeDataset New（六条全新 OSS-Fuzz 样本）

> 与上周 ST-01～ST-06 不重复；六条全部 `introduced_by_this_change=true`。

| id | 类型 | 项目 | M | H | 源码文件数 |
|---|---|---|---|---|---:|
| SN-01 | `api` | haproxy | `c6cfa7cb4acc` | `9fa746636837` | 1260 |
| SN-02 | `configuration` | openh264 | `3164a792a8a2` | `3ad6236b0f0c` | 722 |
| SN-03 | `input_format` | libplist | `60d291941fad` | `79f7772097ed` | 248 |
| SN-04 | `state` | binutils | `45a7f5a29de7` | `9af538448e59` | 28449 |
| SN-05 | `lifecycle` | binutils | `ba64682044d3` | `db7354e3d31c` | 26930 |
| SN-06 | `mix` | memcached | `9723c0ea8ec1` | `e75a15b717ea` | 273 |

## 证据范围

本版本做了真实提交/diff/完整源码/H patch 核对。SN-01、SN-02 已完成真实 full compile+link（旧 harness 失败、H 修复后成功）；SN-06 复现旧 harness 的 proxy_init 参数错误，H 修复版用正确 config 编译通过；SN-03 已构建并运行 oplist_fuzzer，`oplist.c:827` 覆盖 1；SN-04 已构建并运行旧/修复 fuzz_dlltool（两个 .def 输入均 exit 0，状态重置差异为静态证据）；SN-05 已构建 binutils 2.40 + fuzz_as：旧 harness 运行时 SIGSEGV（exit 139），H 修复版 exit 0。六条 `verdict` 均为 `PASS_PARTIAL`。

SN-04 的 `input/source/` 使用 binutils 2.44 release 树（包含 M），`change.diff` 是 M 提交的精确 diff；其余样本源码在 M/包含 M 的树。
