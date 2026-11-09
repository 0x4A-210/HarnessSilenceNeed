# 代码组织与数据流（v8）

> 2026-11-09 更新。方案的完整说明见 `方案说明.md`，判定条款见 `docs/判定规格.md`。

默认配置（`configs/default.yaml`）是：级联会话引擎（`cascade_session`）+ Codex CLI 后端，完整读取函数，并开启 `program_facts`。旧的双模块引擎（`obligation_ledger_dual`）只作为消融配置保留。

## 数据流

1. **读取输入**（`context/reader.py`）：读取中性的 `case.json` 和文件清单，检查路径边界和逐文件哈希。输入只包括修改后的源码、diff 和旧 harness；标签只保存在 `workspace/private/`，只有评测时才读取。
2. **解析与检索**：
   - `analysis/changes.py` 解析 diff；
   - `analysis/syntax.py` 用 Tree-sitter 解析 C/C++；
   - `context/search.py` 用 `rg` 查找符号。
3. **构建证据包**（`llm/attribution/retrieval.py` 的 `initial_packet`）：
   - 完整的 harness，构建脚本 / helper / Dockerfile / project.yaml，根目录的 Makefile；
   - harness 入口的直接调用（最多 16 个）及其下一层被调函数；
   - 变更所在的完整函数（`llm/whole_functions.py`、`controlled_reader.py`）；
   - diff 无损分页（`llm/diff_pages.py`）。
4. **构建配置事实**（`llm/build_facts.py`）：
   - A：编译期条件、宏定义、构建配方中的配置设置；
   - B：构建路径检查。

   结果作为 `program_facts` 放进证据包，对应的原始行加入证据。
5. **证据库**（`llm/evidence_locations.py`）：给每个单元分配 `unit_id`、行号区间和内容哈希；模型的引用由程序取出原文并核验。
6. **级联会话**（`llm/attribution/cascade.py`）：
   - 发现（`DISCOVER`）→ 复核（`REVIEW`，Claude 用分叉，Codex 用续接）；
   - 按需进行：新候选复核、引用修复（`REPAIR`）、补读后复核；
   - 只在 `needs_update` 时进行时间判断（`TIMING`）；
   - 每轮的输出都由程序核验：`policy.verify_gate`（五项前提）、`scope.verify_closure`（阴性闭合）、`validate_answer` 和 `verify_attribution`（时间由两侧事实推导）。
7. **修改前的源码**：`preimage.py` 和 `patch_alignment.py` 由 diff 反推并做往返校验，`paired_source.py` 配对修改前后的单元。
8. **综合输出**（`combine.combine_cascade`）：生成 `prediction.json`，包括维护、时间、综合结论和成本。
9. **批量运行**（`runner.py`）：
   - 并发执行，处理技术重试，额度耗尽时停止整批；
   - 记录代码快照和输入身份，冻结所有产物的哈希。
10. **评测**（`evaluation/`）：只有在冻结之后才关联标签，生成三组指标、六维统计和逐条对照，报告写到 `reports/<run>.md`。

## 模块职责

| 位置 | 职责 |
|---|---|
| `cli.py`、`__main__.py` | 命令入口：analyze / batch / evaluate / verify |
| `engine.py` | 按 `llm.engine` 选择引擎，并给出对应的协议哈希 |
| `runner.py` | 批量运行、技术重试、额度停止、冻结 |
| `budget.py`、`models.py`、`source_text.py`、`util.py` | 预算、数据对象、行坐标、哈希 / JSON / 配置（支持 `extends:`） |
| `analysis/` | diff 分组、语法树 |
| `context/` | 输入白名单、缓存、符号搜索 |
| `llm/backends.py` | 可替换模型后端（`codex_cli`、`claude_cli`）、续接 / 分叉、用量换算、故障分类与重试 |
| `llm/build_facts.py` | 程序提取的构建配置事实（A1–A3、B） |
| `llm/evidence_locations.py` | 引用定位、原文物化、哈希核验 |
| `llm/whole_functions.py`、`controlled_reader.py`、`diff_pages.py`、`catalog.py`、`context.py` | 证据单元的读取与组织 |
| `llm/obligation_packets.py`、`obligation_ledger.py` | 按容量分段、义务归并（双模块引擎使用） |
| `llm/schema.py`、`verify.py` | 严格的 schema 校验（支持 `anyOf` / `null`）、引用核对 |
| `llm/attribution/spec.py` | 规格条款与提示词渲染（判定性提示词的唯一来源） |
| `llm/attribution/cascade.py` | 级联会话引擎 |
| `llm/attribution/policy.py`、`necessity_proof.py` | 两类义务、五项前提闸门 |
| `llm/attribution/maintenance.py`、`scope.py`、`temporal.py`、`verify.py`、`schema.py` | 判定结构与程序侧校验 |
| `llm/attribution/retrieval.py`、`build_context.py`、`callers.py`、`missing_context.py`、`symbols.py`、`paths.py`、`target_contract.py` | 证据检索与补读 |
| `llm/attribution/preimage.py`、`patch_alignment.py`、`paired_source.py` | 修改前源码的重建与前后配对 |
| `llm/attribution/combine.py` | 综合输出规则 |
| `llm/attribution/pipeline.py`、`head.py`、`necessity.py` | 旧的双模块引擎（消融用） |
| `evaluation/` | 指标、六维统计、报告 |
| `tests/` | 114 项测试：合成样本，不是标签开发集 |
| `tools/` | 后端验证脚本 |

## 方法边界

- 语义判断由模型完成：发现义务、判断核心行为与可达性、做必要性闸门和时间事实判断。程序负责证据检索、定位与哈希核验、状态汇总和指标计算。
- 本方案没有完整的控制流图、静态可达性证明或符号执行。语法树和符号匹配只能提供候选关联。
- 有限的预算并不意味着已经阅读了整个项目；证据不足时输出 `unknown`，不能据此判为阴性。
