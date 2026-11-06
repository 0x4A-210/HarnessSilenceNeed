# False-Positive Analysis

## Evolution-Aware 的全部 7 个有效 FP

| Case | Candidate / commit | Primary type | 模型错误归因 |
|---|---|---|---|
| C006 | N4007 / `d89ec2d40b8f` | FP-N4-5 | 把 JPEG `bitstream_is_closed` 在既有 `restart_frame!` 中的内部 reset，当成新 exposure requirement。 |
| C016 | N4010 / `920ac3e5c567` | FP-N4-3 | 把 CRC64 slicing-by-8 内部优化新增分支，当成对既有 absent-module gap 的 material aggravation。 |
| C020 | N4005 / `442533f08c40` | FP-N4-3 | 把 `scan_count` 与 swizzle/yield 内部重排解释为 H0 新缺失 streaming protocol。 |
| C025 | N4014 / `f32bfe95c621` | FP-N4-3 | 把 CRC64 x86 SSE4.2 fast path 当成必须新增 harness exposure 的 attack surface。 |
| C032 | N4011 / `dc269f3f5443` | FP-N4-5 | `get_quirk` 函数行为被修复，但 API 和 H0 不调用它的事实均早已存在；模型把“函数变化”当成“reachability requirement 变化”。 |
| C034 | N4008 / `b9b28dbe8b15` | FP-N4-3 | 把 XXHash32 CPU-selected internal implementation 视为 commit-induced exposure gap。 |
| C036 | N4004 / `06ffee27a2ed` | FP-N4-5 | DQT ordinary path 已由 JPEG H0 可达，模型仍因既有 `restart_frame!` 未调用而将保存/恢复内部状态判为新 gap。 |

Primary 分布：FP-N4-3 为 4/7，FP-N4-5 为 3/7。共同模式不是模型没看到 H0，而是
它采用了“只要新增内部路径落在既有未覆盖 API/subsystem 中，gap 就被加剧”的过宽
因果标准。这个标准会把 source-change magnitude 当成 evolution attribution。

## Gap-Only FP 中被 Evolution-Aware 修复的全部 9 个 case

| Case | Candidate | Evolution result | 修复机制 |
|---|---|---|---|
| C003 | N4006 | gap=NO, induced=NO | 认为 JPEG block smoothing 由现有 decode path 自动到达。 |
| C005 | N4018 | gap=NO, induced=NO | 认为 WebP H0 已内部满足新的 VP8 source-length protocol。 |
| C015 | N4019 | gap=NO, induced=NO | 认为 VP8X/width-height state 由 WebP input 自动提供。 |
| C019 | N4001 | gap=YES, induced=NO | 正确认出 restart gap 已存在，state-value refactor 不改变 external protocol。 |
| C026 | N4016 | gap=NO, induced=NO | 将 workbuf validation change 判断为非 material harness requirement。 |
| C031 | N4015 | gap=NO, induced=NO | 认为 ordinary JPEG path 已覆盖 multiple-scan validation。 |
| C035 | N4009 | gap=YES, induced=NO | 正确认出 JSON H0 不覆盖 XXHash 的 gap 已存在，而 commit 只是撤回 SSE path。 |
| C039 | N4002 | gap=NO, induced=NO | 将 truncated-input wrapper 判断为既有 decode path 上的 error handling。 |
| C040 | N4020 | gap=NO, induced=NO | 认为 WebP ALPH path 已内部设置 VP8 quirk，H0 无需新动作。 |

只有 C019 和 C035（2/9）是实验目标要求的“先发现 gap，再正确归因”。其余 7 个通过
否认 material gap 修复 maintenance FP。它们对最终分类有价值，但不能单独证明
Evolution Attribution 的价值。

## 冻结后 INVALID 与 FP 的区分

C002、C018、C021、C033 的 Evolution-Aware positive 判断在冻结标签下看似 FP，
但 post-freeze audit 证明原 N4 GT 不成立，因此这四个 case 被 INVALIDATE，绝不进入
上面的 7 个 FP 或主指标，也没有被事后改标成 TP。

