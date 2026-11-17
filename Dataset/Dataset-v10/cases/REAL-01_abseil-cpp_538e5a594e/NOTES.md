# REAL-01 — abseil-cpp @ 2370ccf579bd

- label: **positive** / explicit / type `configuration` / introduced_by_this_change = True
- change: https://github.com/abseil/abseil-cpp/commit/2370ccf579bd (PR #1939: Add missing rules_cc loads)
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: oss ['projects/abseil-cpp/WORKSPACE', 'projects/abseil-cpp/build.sh'] (target `string_escape_fuzzer`)
- fix H: https://github.com/google/oss-fuzz/commit/538e5a594e (abseil-cpp: fix broken build #14472)

## 理由

库在 BUILD.bazel 里开始 `load("@rules_cc//...")`，同时要求 C++17。旧 harness 的 WORKSPACE 没声明 rules_cc/bazel_features 依赖，build.sh 也没设 `-std=c++17`，bazel 构建直接失败。修复 H 一次性补齐两处后恢复。属于本次引入的显式 configuration 退化。

## Rationale

abseil's BUILD.bazel now loads @rules_cc (new build dependency), and abseil requires C++17. The old harness WORKSPACE declares no rules_cc, and build.sh does not pass -std=c++17, so the bazel build fails. Fix H adds rules_cc + bazel_features in WORKSPACE and --cxxopt=-std=c++17 in build.sh, after which the build recovers. Explicit configuration degradation introduced by this change.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "not measured (fetch 阶段网络超时)",
  "h(M^1) x lib(M)": "fail (missing rules_cc)",
  "h(fix) x lib(M)": "ok"
 },
 "explicit_signal": "build_failure",
 "verdict": "PASS"
}
```

### 实测（bazel 7.4.0）

| 格 | 组合 | rc | 耗时 | 结果 |
|----|------|-----|------|------|
| `h(M^1) × lib(M^1)` | 旧 WORKSPACE × M^1 的 abseil | — | — | 未测出（见下） |
| `h(M^1) × lib(M)` | 旧 WORKSPACE × M 的 abseil | **1** | **29.27s** | `cannot load '@@rules_cc//cc:cc_test.bzl': no such file` |
| `h(fix) × lib(M)` | 修复版 WORKSPACE × M 的 abseil | **0** | **84.33s** | 构建成功 |

**格2 的完整报错**：

```
ERROR: error loading package '@@com_google_absl//absl/debugging':
cannot load '@@rules_cc//cc:cc_test.bzl': no such file
ERROR: Analysis of target '//:probe' failed: build aborted: Analysis failed
```

**修复版 WORKSPACE 补的两个依赖**（对比旧版可直接看出）：

| 依赖 | 旧 WORKSPACE | 修复版 WORKSPACE |
|------|-------------|-----------------|
| `bazel_features` 1.21.0 | ❌ | ✅ |
| `rules_cc` 0.2.14 | ❌ | ✅ |

**格1 为什么没测出**：该组合要解析旧 WORKSPACE 的 `rules_fuzzing → rules_python 0.20.0` 依赖链，bazel 在 fetch 阶段因 `github.com` 连接超时失败（`Connect timed out`）。这是环境问题，与本样本的 `rules_cc` 退化无关。佐证：修复版的 bazel 缓存里同样没有 `rules_python`，说明修复版根本不走这条依赖链。

> 另有 OSS-Fuzz 真实 fix commit `538e5a594e` 作为佐证（标题即 "fix broken build"，其 diff 补的正是 rules_cc + C++17）。
> **C++17 那个子问题本次未单独实测**（build.sh 缺 `-std=c++17`），build.sh 的实测留待后续。

## 讲解

### 1. 库改了什么（input/change.diff）

`absl/debugging/BUILD.bazel` 新增 3 行 `load("@rules_cc//...")`：把 cc_binary / cc_library / cc_test 三个规则符号改为从 rules_cc 显式加载。这使库的构建要求 workspace 声明 rules_cc 仓库。

```diff
+load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
+load("@rules_cc//cc:cc_library.bzl", "cc_library")
+load("@rules_cc//cc:cc_test.bzl", "cc_test")
```

（注：变更前该文件已有 9 处 `@rules_cc//cc/compiler:...` 标签引用，但未 load 这三个规则；本次变更使 rules_cc 成为必需依赖。）

### 2. 原来的 harness（input/harness/oss-fuzz/）

`WORKSPACE` 里只有 bazel_skylib + rules_fuzzing，**没有 rules_cc、没有 bazel_features**；
`build.sh` 的 BAZEL_EXTRA_BUILD_FLAGS 只设 `--features=-layering_check`，**没有 `-std=c++17`**。

### 3. 为什么 harness 出问题

- 库现在 load @rules_cc → 构建时 Bazel 找不到 rules_cc 仓库 → analysis 失败。
- abseil 要求 C++17 → 未传 -std=c++17 → 编译失败。

### 4. 怎么修（OSS-Fuzz 的 H = 538e5a594e）

WORKSPACE 补 rules_cc + bazel_features 两个 http_archive 及 load；build.sh 加 `--cxxopt=-std=c++17`。

### 5. 为什么是这个标签

- **阳性**：不改 harness 就无法继续 fuzz。
- **显式**：构建失败，问题在构建阶段就暴露。
- **本次引入**：变更前同一个 harness 能正常构建。
- **configuration**：问题在构建依赖与编译标准，不在被测 API 签名。
