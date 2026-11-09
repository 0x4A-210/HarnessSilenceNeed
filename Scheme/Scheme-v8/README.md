# scheme-v8：静态的 fuzz harness 维护需求检测

> 2026-11-09 更新

给定一次库变更（diff 和变更后的源码）以及变更前就存在的 fuzz harness，本方案**不编译、不运行程序**，只做静态判断：
- **维护判断**：harness 是否需要更新，输出 `needs_update` / `satisfied_in_scope` / `unknown`；
- **时间判断**：问题是本次引入，还是原本就存在，输出 `introduced` / `preexisting`。

方法是“**判定规格 → 级联会话中的模型判断 → 程序侧证据核验**”。每条样本只开一个模型会话，平均 3.3 次调用、约 6 分钟。

本目录可以独立运行，不依赖其他工程目录。v7 的实现原样保留在 `../scheme-v7/`。

## 文档

| 文档 | 内容 |
|---|---|
| [方案说明.md](方案说明.md) | **方案的完整说明**：目标、规格、流程、程序侧保证、模型后端、实验结果、局限和下一步 |
| [context.md](context.md) | 代码组织、数据流、模块职责 |
| [docs/判定规格.md](docs/判定规格.md) | 判定条款 D1–D9 / J1–J6 / T1–T4 / E1–E4，提示词的唯一来源 |
| [docs/规则审计.md](docs/规则审计.md) | v7 提示词的逐句审计，以及之后每次规格修订的依据 |
| [docs/运行状态.md](docs/运行状态.md) | 每次全量运行和单样本重测的结果与分析 |
| [docs/级联流程与模型后端.md](docs/级联流程与模型后端.md) | 级联流程与模型后端的设计、会话 / 缓存验证记录 |
| `reports/<run>.md` | 各次全量运行的评测报告 |

## 当前结果（开发集 Dataset-v8 共 48 条，Codex `gpt-6-sol`，high，两次全量的平均）

| 准确率 | 精确率 | 召回率 | F1 | 误报率 | 漏报率 | 综合严格准确率 | 单条平均耗时 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 82.3% | 84.5% | 79.2% | 81.7% | 14.6% | 20.8% | 80.2% | 371 秒 |

这些都是**开发集**上的结果：多处规格修订是在看过开发集的错误之后做的，结论需要在独立测试集上验证。详见 `方案说明.md` 第 8、11 节。

## 环境与运行

推荐使用 Python 3.11 及以上。模型调用依赖本机已登录的 CLI：Codex CLI（ChatGPT 账户），或者 Claude Code CLI（Claude 订阅），**不使用 API key**。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
.venv/bin/pip install --no-build-isolation -e .
.venv/bin/python -m pytest -q                         # 114 项测试，不调用模型

# 单条样本（默认：级联流程 + Codex）
.venv/bin/python -m scheme_v8 analyze --input workspace/inputs/<case> --output workspace/single/<name>
# 换用 Claude，或旧的双模块流程（消融用）
.venv/bin/python -m scheme_v8 --config configs/claude.yaml analyze --input ... --output ...
.venv/bin/python -m scheme_v8 --config configs/legacy-dual.yaml analyze --input ... --output ...

# 全量运行（运行目录名必须是新的）与评测（这时才读标签）
.venv/bin/python -m scheme_v8 batch --run <run-name>
.venv/bin/python -m scheme_v8 evaluate --run <run-name>   # 报告写到 reports/<run-name>.md
.venv/bin/python -m scheme_v8 verify --run <run-name>     # 核验输入和冻结产物的哈希
```

- 批量运行的样本数量，由 `workspace/inputs/case-*/manifest.json` 自动发现。
- 账户额度耗尽时，批量运行会停止，并写入 `incomplete.json`，这次运行不会被冻结。
- 被安全过滤拦截的样本单独记为 `ContentFlagged`，结果为 `unknown`。
- 配置可以用 `extends:` 继承，只写需要覆盖的部分，例如 `configs/claude.yaml`。

## 数据

- `workspace/inputs/case-*`：Dataset-v8 中 48 条样本准备好的输入（`case.json`、`manifest.json`、`input/{change.diff, source/, harness/}`），样本 ID 为中性编号。
- `workspace/private/`：标签和样本映射，只有评测时才读取。
- `workspace/runs/<run>/`：每次全量运行的预测、逐轮原始记录（提示词、schema、事件流、用量）和冻结清单。

## 目录结构

```text
scheme-v8/
├── README.md                        # 本文件
├── 方案说明.md                      # 方案的完整说明
├── context.md                       # 代码组织与数据流
├── pyproject.toml / requirements-lock.txt / .gitignore
├── configs/
│   ├── default.yaml                 # 默认：级联流程 + Codex（gpt-6-sol，high）+ program_facts
│   ├── claude.yaml                  # 换用 Claude CLI（只覆盖 provider / model / effort）
│   └── legacy-dual.yaml             # 旧的双模块引擎（消融用）
├── docs/
│   ├── 判定规格.md                   # 判定条款（提示词的唯一来源）
│   ├── 规则审计.md                   # 规则审计与修订记录
│   ├── 运行状态.md                   # 运行与重测的结果
│   └── 级联流程与模型后端.md          # 流程与后端的设计、验证记录
├── src/scheme_v8/
│   ├── __main__.py / cli.py         # 命令入口：analyze / batch / evaluate / verify
│   ├── engine.py                    # 按配置选择引擎
│   ├── runner.py                    # 批量运行、技术重试、额度停止、冻结
│   ├── budget.py / models.py / source_text.py / util.py
│   ├── analysis/                    # changes.py（diff 解析）、syntax.py（Tree-sitter）
│   ├── context/                     # reader.py（白名单与哈希）、search.py（符号搜索）、cache.py
│   ├── evaluation/                  # metrics.py、dimensions.py、report.py
│   └── llm/
│       ├── backends.py              # 模型后端：Codex CLI / Claude CLI、续接 / 分叉、故障分类
│       ├── build_facts.py           # 构建配置事实（A 编译期配置、B 构建路径）
│       ├── evidence_locations.py    # 引用定位与内容哈希核验
│       ├── whole_functions.py / controlled_reader.py / diff_pages.py / catalog.py / context.py
│       ├── obligation_packets.py / obligation_ledger.py
│       ├── schema.py / verify.py
│       └── attribution/
│           ├── spec.py              # 规格条款 → 提示词
│           ├── cascade.py           # ★ 级联会话引擎
│           ├── policy.py / necessity_proof.py / necessity.py
│           ├── maintenance.py / scope.py / temporal.py / verify.py / schema.py
│           ├── retrieval.py / build_context.py / callers.py / missing_context.py
│           ├── symbols.py / paths.py / target_contract.py
│           ├── preimage.py / patch_alignment.py / paired_source.py
│           ├── combine.py
│           ├── pipeline.py / head.py  # 旧的双模块引擎
│           └── prompts/independent.txt
├── tests/                           # 114 项测试（test_cascade.py、test_build_facts.py、test_spec_prompts.py 等）
├── tools/
│   ├── verify_sessions.py           # 会话续接与缓存验证
│   └── verify_nullable.py           # “对象或 null” schema 的兼容性验证
├── reports/
│   ├── task1-spec.md … task4-b.md   # 各次全量运行的评测报告
│   └── verification/                # 后端验证的原始记录
└── workspace/
    ├── inputs/                      # 48 条准备好的输入（约 1.3 GB）
    ├── private/                     # 标签与映射（只在评测时读取）
    ├── dataset_manifest.json / preparation.json
    ├── runs/                        # task1-spec、task2-cascade-codex、task3-facts-timing-codex、task4-a、task4-b
    └── single/                      # 单样本调试与重测记录
```
