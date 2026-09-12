# Dataset Construction

## 数据源与独立性

本实验从本地 Wuffs Git 历史挖掘真实、单 parent、source-only production commits。
主矿工固定扫描 2022-01-01 之后的 `std/**/*.wuffs` 历史，并在任何 task-4 prediction
之前排除以下集合中的 Wuffs commits：前期 development set、task-3 candidate/control
及 77-case 数据、pre-test 与 holdout。为替换一个语义过弱的 read-only getter
positive，另加入一个同样经过全量 exclusion audit、但位于固定窗口之前的完整 PNG
decoder introduction；它被明确记为 `X0002`。

独立性审计结果：40 个选定 commit 均唯一，和六个既有数据源的当前 commit 重叠为
0。详见 `data/independence_audit.csv`。

## 候选生成与预测前选择

- 筛查 source-only commits：258。
- raw function-level candidates：211。
- 去重后的 commit candidates：47。
- raw signals：28 N4、19 positive。
- 最终冻结前选择：20 N4、20 positive、40 个唯一 commits、1 个项目。
- 选择过程没有读取任何 task-4 prediction；`selection_uses_predictions=false`。

N4 的机械入口条件是：目标 public symbol 在 S0/S1 同一路径中均存在、签名稳定、
完整 `fuzz/c` portfolio 在两侧都没有目标直接 exposure，并且 commit 是有意义的
production source change。人工语义关口进一步排除 formatting/language migration、
明显新增 configuration、以及明显把 placeholder 变成新 subsystem 的候选。

Positive 以新 decoder/subsystem、public configuration 或 major implementation surface
为单位。冻结前主动剔除了三个“只是新 read-only getter、materiality 有争议”的弱
positive；最终 20 个中，17 个是新 subsystem/major decoder surface，3 个是明确新
configuration（LZMA non-zero initial byte、reject progressive JPEG、raw Thumbhash）。

## 配对

配对使用 prediction 前已知事实上的 minimum-total-cost Hungarian assignment。代价由
时间距离、`log(1 + changed LOC)`、production file count 和 functional family 构成。

- 20/20 同项目配对。
- 13/20 functional-family exact match。
- 时间距离中位数 108.517 天，均值 197.783 天，最大 710.900 天。
- N4 changed LOC 中位数 162.5；positive 中位数 293.0。
- N4 production file count 中位数 2；positive 中位数 1。

这是一个“尽量匹配”而非完美平衡的数据集。所有 case 来自 Wuffs 是控制项目差异的
优点，也是外部效度限制；部分 late VP8 N4 与 earlier positive 的时间距离较大。

## 冻结后有效集

预测冻结后的严格审计没有 relabel，而是按协议将四个严重误构造 N4 排除：

| Case | Candidate | Commit | 原因 |
|---|---|---|---|
| C002 | N4013 | `22b4ff484236` | 新增 XZ concatenated-stream public quirk/configuration |
| C018 | N4017 | `1222a6886d41` | 在无 NIE/NIA H0 时新增 NIA animation format/state |
| C021 | N4003 | `d36277f0c026` | 在 JSON-only H0 下显著扩展 JPEG DHT parser surface |
| C033 | N4012 | `c21cc9571394` | 改变 LZMA public history/workbuf protocol |

因此主结果是 16 个有效 N4 + 20 个有效 positive，共 36 个有效 commits。未补样本，
因为在看到 prediction 后补样本会违反独立盲测原则。

