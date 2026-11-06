# Dataset Selection Audit

## Positive

5 个 selected positive 均来自 phase-1 的 13 个 confirmed degradation commits，选择依据是 source evolution 与 H0 gap 清晰且机制尽量不同：

| Case | Project | Commit | Maintenance-need type |
|---|---|---|---|
| C004 | wuffs | `555e8eaaa36804bc8d6930d274941ec31b9eb464` | new decoder entry point |
| C038 | libspng | `cb18f38c1f2c62a70062d5d2d36b28e7384b954d` | configuration and input-constraint change |
| C055 | libplist | `429cbc660ae14d4998715803b44c71abf0e4a339` | new input format and parser entry point |
| C094 | brotli | `19d86fb9a60aa7034d4981b69a5b656f5b90017e` | API protocol and state requirement |
| C098 | c-ares | `7d3591ee8a1a63e7748e68e6d880bd1763a32885` | new public entry point and call protocol |

它们各自的 phase-1 artifact attribution、coverage before/after 和 Git mapping 保存在 `data/selected_positive_cases.csv`。

## Strict hold-out

剩余 8 个 confirmed event 未生成 case、未加入 prompt、未参与模型调用、未用于根据输出改规则。其 commit 清单在 `data/withheld_positive_cases.csv`，状态统一为 `withheld_not_used`。5 个 selected 与 8 个 withheld 无交集，合计覆盖 phase-1 的全部 13 个 confirmed event。

## Negative

100 个 negative 均来自 phase-1 的 16,155-commit universe，且不属于 13 个 confirmed events。分配如下：

| Stratum | Count | Per project |
|---|---:|---:|
| Easy | 20 | 2 |
| Matched | 60 | 6 |
| Hard | 20 | 2 |
| Total | 100 | 10 |

每个 negative 自动核验：

- commit 存在于对应本地 project Git；
- 是单 parent commit，且 parent 与 phase-1 universe 一致；
- 至少修改一个 production C/C++/Wuffs source file；
- 不只是 docs/tests/comments/formatting；
- 不修改 fuzz/harness path；
- 不与 13 个已知 positive 重合。

negative label 的含义是：无 phase-1 已知 degradation，且静态审查没有发现 H0 的入口、调用协议、caller-visible state/config 或输入构造必须同步变化。它不是动态 coverage 证明。

## 匹配质量

项目分布满足设计目标，但数值协变量匹配不充分：

| Group | Changed LOC min | median | max |
|---|---:|---:|---:|
| Selected positive | 320 | 1,193 | 2,802 |
| Matched negative | 2 | 13 | 359 |
| Hard negative | 4 | 58 | 651 |

因此 `matched` 应理解为按 project、时间附近和语义复杂度挑选的对照 strata，而不是严格的 propensity/LOC matching。positive 更大、更明显，可能让 5/5 偏乐观。后续实验应在冻结 hold-out 之前改善统一的匹配规则，但不能重跑本阶段来替换已经看到的结果。

## 解盲后的标签边界审计

不对任何 case 事后改标签。6 个 FP 中，C018/C021 的 ambiguity 为 low，C022/C025/C075 为 medium，C054 为 high。C054 暴露了核心定义边界：如果 maintenance need 是 project-wide attack-surface coverage，它可能需要新 TIFF target；如果是 current H0 对其既定 SPIX/barcode scope 是否退化，则是 negative。

这类分歧应由下一阶段预注册的 scope rule 和独立评审解决，而不是依据模型是否答对来回写标签。
