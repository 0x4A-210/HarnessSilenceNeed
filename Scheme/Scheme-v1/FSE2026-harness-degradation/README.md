# FSE 2026 fuzz-harness degradation：第一阶段复现

本目录复现 FSE 2026 论文《An Empirical Study of Fuzz Harness Degradation》的第一阶段 ground truth。复现对象是论文 RQ4 的 coverage-degradation event；没有重新设计 degradation 定义，也没有用模型或自然语言猜标签。

## 冻结结果

| 指标 | 本阶段结果 |
|---|---:|
| 项目数 | **10** |
| commit 总数 | **16,155** |
| positive degradation commits | **13** |

Go / No-Go：**NO-GO**。13 个 positive 少于任务规定的 30 个门槛，因此应暂停后续 ML，不应把其余 commit 当成可靠 negative 后直接训练。

这里的 `commit 总数` 是 10 个项目各自从首次 OSS-Fuzz 集成到论文分析截止日之间、位于当前默认分支且满足数据库快照保护条件的 commit 数。它不是论文全量 342 项目的 2,357,857 个 commit。

## 主要结果文件

- `data/processed/degradation_events.csv`：最终 13 个 positive，字段严格为用户要求的 9 列。
- `data/processed/commit_universe.csv`：16,155 个 commit；13 个为 `positive`，其余为 `unlabeled`，没有虚构 negative ground truth。
- `data/processed/coverage_event_metrics.csv`：每个事件的日降幅、30 日中心降幅、30 日最大值降幅及四个布尔谓词。
- `evidence/positive_event_evidence.json`：每个 positive 的 Git、artifact、逐日 coverage 原始值和下载地址。
- `reports/experimental_design.md`：论文 dataset、定义、coverage、bug-finding metric、artifact 和复现口径分析。
- `reports/selection_audit.md`：10 项目内 18 个 artifact case 的 13 个纳入项与 5 个排除项。
- `reports/validation.md`：13/13 positive 的全量审计结果。
- `summary.json`：三个核心数字和逐项目计数的机器可读快照。

`harness_id` 使用 `<project>::project_aggregate`。原因是论文 RQ4 和 artifact 的 case-study filter 在 OSS-Fuzz 项目级聚合 coverage 上运行，无法从该指标诚实地反推出某个单独 fuzz target。这里明确表达原研究的测量单位，而不是伪造 target-level 标签。

## 一键复算

要求 Python 3、Git 和网络访问。已下载的 coverage 会走缓存：

```bash
cd /mnt/e/reseach/harness-stale-predict/FSE2026-harness-degradation
python3 scripts/reproduce.py all --workers 16
```

只使用本地缓存重建 CSV 和验证报告：

```bash
python3 scripts/reproduce.py build
```

配置入口：

- `config/selected_projects.csv`：10 个项目及其首次 OSS-Fuzz 集成时间。
- `config/positive_events.csv`：从固定 artifact case-study notes 中选出的 commit 映射。

## 下载状态

已保存在本目录中的材料包括：

- arXiv v2 的 PDF 和 HTML；
- 固定到 commit `73843108273b97f05a583bc5226fa8177d88eb04` 的作者 artifact；
- OSS-Fuzz 历史仓库；
- 10 个入选项目的 Git 历史（另有 6 个探索阶段 clone，不参与统计）；
- 13 个事件前后各 30 日所需的 675 份可用 OSS-Fuzz 原始 coverage HTML；另外 60 个日期在源站返回 404，按 artifact 的 missing-data 语义保留在 manifest 中。

Zenodo 完整 SQLite 分卷共 38.7 GB；当前环境访问 Zenodo 文件端点持续返回 504/超时，因而没有把错误响应冒充数据库。官方十个分卷的文件名、大小、MD5、URL 和状态记录在 `data/raw/zenodo_file_manifest.csv`。本阶段所选子集改由公开 OSS-Fuzz coverage、固定 artifact notes 和项目 Git 历史独立复算，完整清单见 `data/raw/download_inventory.md`。

## 复现边界

- `degradation_metric_before/after` 是 artifact 代码的 30 日中心统计量：`(mean + median) / 2`，单位为 line-coverage percentage points。
- positive 还同时满足：单日降幅 `< -5pp`、中心降幅 `< -5pp`、前后窗口最大值降幅 `< -5pp`、事件日 coverage `> 0`，且不是项目最初 30 日。
- commit 归因必须由 artifact 的双评审 case-study notes 明确支持；coverage 数值本身只证明 drop，不单独证明某个 commit 是原因。
- OSS-Fuzz 日报不公开当日精确构建时刻，因此“发生在 commit 之后”只能核验到日粒度；报告日不早于 commit 的 UTC 日期。
- `wuffs` 2020-02-06 是 artifact 明示的 two-part change；CSV 以覆盖转折前的完成 commit 为 anchor，并保留前一 part 为 `previous_commit`。其余事件均为 notes 明示的单 commit。

## 上游来源

- 最终论文（arXiv v2，2026-06-25）：https://arxiv.org/html/2505.06177
- 作者 artifact：https://github.com/CISPA-SysSec/fuzz-harness-degradation
- Zenodo dataset：https://zenodo.org/records/14000867
- OSS-Fuzz coverage archive：https://storage.googleapis.com/oss-fuzz-coverage/
