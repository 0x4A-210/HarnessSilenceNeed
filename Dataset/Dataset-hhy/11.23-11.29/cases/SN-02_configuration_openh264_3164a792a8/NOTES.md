# SN-02 — openh264 @ 3164a792a8a2

- label: **positive** / explicit / type `configuration` / introduced_by_this_change = true
- change: Move the headers to a 'wels/' subdirectory in the source tree (#3502) (2022-05-27)
- M: `3164a792a8a22f9d7456c7e2db9280ce5cc7e31b`
- M^1: `ed110bb57ccc9baa5851279deca3da45820132b6`
- H: `3ad6236b0f0c58ec73ed09c90dea6eb4bfa4194b`
- H^1: `0a3b8f0cb43b7fe0a781048eca61298529175e0f`
- source: `input/source/` = 722 files; `change.diff` = M^1→M

## 变更文件索引

本次变更涉及 27 个文件：

- `Makefile`
- `codec/api/meson.build`
- `codec/api/wels/codec_api.h`
- `codec/api/wels/codec_app_def.h`
- `codec/api/wels/codec_def.h`
- `codec/api/wels/codec_ver.h`
- `codec/api/wels/meson.build`
- `codec/build/android/dec/jni/welsdecdemo.mk`
- `codec/build/android/enc/jni/welsencdemo.mk`
- `codec/build/generate_codec_ver.sh`
- `codec/build/iOS/common/common.xcodeproj/project.pbxproj`
- `codec/build/iOS/dec/demo/demo.xcodeproj/project.pbxproj`
- 其余 15 个文件见 `input/change.diff`。

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `decoder_fuzzer`
- 修复 patch: `_evidence/SN-02_configuration_openh264_3164a792a8/fix.diff`
- 原始运行/构建日志: `_evidence/SN-02_configuration_openh264_3164a792a8/recheck_2026-11-19/`
- 静态核对: `_evidence/SN-02_configuration_openh264_3164a792a8/static_checks.json`

## 理由

openh264 M 把头文件目录从 codec/api/svc 移到 codec/api/wels，旧 build.sh 的 -I 路径失效；H 同步 include 路径。

## Rationale

openh264 M moved headers from codec/api/svc to codec/api/wels; the old build.sh -I path is stale. H updates the include path.

## Verification summary

| 组合 | 结果 | 错误 |
|---|---|---|
| h(M^1) x lib(M^1) | ok | — |
| h(M^1) x lib(M) | fail | codec_def.h: No such file or directory |
| h(fix) x lib(M) | ok | — |

```json
{"verdict": "PASS", "M": "3164a792a8a22f9d7456c7e2db9280ce5cc7e31b", "H": "3ad6236b0f0c58ec73ed09c90dea6eb4bfa4194b"}
```

- [PASS] H patch exists and touches the harness — 3ad6236b0f0c58ec73ed09c90dea6eb4bfa4194b
- [PASS] H patch contains the expected new call/path — codec/api/wels
- [PASS] M diff exists — 3164a792a8a22f9d7456c7e2db9280ce5cc7e31b
- [PASS] M source tree is complete — 722 files
- [PASS] harness files fetched at H^1 — 1 files
- [PASS] old fuzzer vs M: compile fails on codec/api/svc include — recheck_2026-11-19/st02_old_build.log
- [PASS] fixed fuzzer vs M: compile+link succeeds — recheck_2026-11-19/st02_new_build.log

## 讲解

### 1. 库改了什么

- **build_include_path**：M moved public headers from codec/api/svc to codec/api/wels; the old build.sh and fuzzer still use codec/api/svc.

### 2. 原来的 harness 为什么不够

旧 harness 是 H^1 的 `decoder_fuzzer`，没有针对 M 的新接口/新格式/新状态做适配。

### 3. 修复怎么做的

H（`3ad6236b0f0c`）按新契约修改了 harness；`_evidence/SN-02_configuration_openh264_3164a792a8/fix.diff` 是完整 patch。

### 4. 证据是怎么来的

构建/运行日志与 gcov 在 `_evidence/SN-02_configuration_openh264_3164a792a8/recheck_2026-11-19/`；证据为 2026-11-25 在 WSL 里重新做的三格构建/运行日志（`recheck_2026-11-25/`）。

### 5. 为什么是这个标签

openh264 M 把头文件目录从 codec/api/svc 移到 codec/api/wels，旧 build.sh 的 -I 路径失效；H 同步 include 路径。
