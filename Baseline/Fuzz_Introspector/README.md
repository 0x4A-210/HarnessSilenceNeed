# Fuzz Introspector 官方流程复现（Dataset-v9）

输入、模块方法、逐步流程、输出文件及判断指标详见 [实现方案.md](实现方案.md)。

2026-11-16 已按后续要求启动 V3-48 独立重跑，结束后合并前 47 条冻结结果。执行与资源变化见 [独立重跑记录](V3-48-独立重跑.md)，进度见 [实时状态](experiment/results/v3-48-rerun-state.json)。下文的 47 条结果和 11 月 15 日中断记录属于此前运行。

`upstream/fuzz-introspector/` 为从 https://github.com/ossf/fuzz-introspector 克隆的官方仓库，固定在 `341ebbd72bc9116733bcfcfab5adfd7f9b633e07`，与现有官方 OSS-Fuzz 镜像内的 LLVM FI pass 匹配。不是声称使用最新 main。

`upstream/oss-fuzz/` 为从 https://github.com/google/oss-fuzz 克隆的官方仓库，固定提交见 `experiment/provenance.json`，采用 sparse checkout 检出 infra、docs 和根文件。两个仓库均不修改已跟踪源码。

`experiment/` 包含 Dataset-v9 输入装载、项目构建适配、批量执行、结果索引及独立的外部评测脚本。检测流程无 LLM、义务提取、diff 函数分类、R_any/R_all 或其他本地维护判定规则。不会将编译失败或崩溃另作为维护告警。

本轮对主集 48 条执行官方 `infra/helper.py introspector <project> --seconds=30`：ASan 构建 → 运行 fuzzer 产生语料 → coverage 构建与覆盖率报告 → introspector 构建及官方原生 HTML/JSON 报告。辅助补跑只使用官方子命令，并分别记录，不把补跑结果冒充完整流程成功。

官方工具没有对应数据集标签的维护二分类输出，因此原生结果中的维护指标仍为 N/A。按用户后续要求，新增独立的外部评测：以官方原生 `blocked` 提示作为告警事件，与维护标签对照，计算 Acc、Precision、Recall、FPR、FNR 和 F1。此映射不修改官方检测器、不重新设定阈值，也不表示 FI 自带维护分类器；完整口径及 47 条对照见 [外部评测报告](REPORT-47-EVALUATION.md)。标签仅用于运行后的评分。

构建适配只为装入对应历史源码与旧 harness、选择声明的 target、配置依赖和工具链兼容。数据集目录只读；标签及 verification 不参与运行。完整工程适配、版本、命令与日志保存在 experiment 中。

## 目录与复跑

- `upstream/`：官方 Git 仓库原文；Windows 挂载盘的执行权限差异不属于源码修改。
- `experiment/adapter/`：本地数据集构建接入，和官方分析源码分开存放。
- `experiment/workspace/projects/`：每个样本的完整输入包、哈希和构建上下文。
- `experiment/runs/`：每次实际执行的命令、日志、构建状态和官方报告。
- `experiment/results/`：原生字段索引、冻结快照、外部告警评测及完整性验证。本轮最终保留 47 条已结束结果，V3-48 已中断。

在仓库根目录执行。Docker 和 Python 3.11+ 是运行前提，基础镜像及依赖版本见 `experiment/provenance.json` 和 `experiment/toolchain.txt`。镜像标签可能变化，应先核对其 ID；本轮不是对任意最新镜像的结果承诺。

```bash
docker build -f Fuzz_Introspector/experiment/adapter/Dockerfile.environment -t fi-official-v9-environment:20261114 Fuzz_Introspector/experiment/adapter
python3 Fuzz_Introspector/experiment/run.py --run my-fresh-run --prefix fi-my-fresh --workers 4 --seconds 30
python3 Fuzz_Introspector/experiment/collect.py --run my-fresh-run
python3 Fuzz_Introspector/experiment/validate.py
```

每次使用新的 `--run` 和 `--prefix`，避免复用语料或构建产物。输入默认来自相邻的 `Dataset-v9/Dataset-v9/dataset`；已展开的每样本 Docker 上下文也可直接交给官方 helper。运行不导入其他方案目录的代码。`validate.py` 验证 48 条集合、输入包、旧 harness、官方组件及结果文件哈希，不做检测判断。

2026-11-15 16:29（UTC+8）已按用户要求停止 V3-48 及 `experiment/finalize_when_done.py`，不再后台等待。V3-48 出现 OOM 事件后，profile 工作进程等待信号量、主进程等待子进程，疑似同步挂起；见 [停止原因与现场](V3-48-停止原因.md)。`vm.mmap_rnd_bits` 已恢复为原值 32 并核验。执行状态见 `experiment/results/finalization-state.json`。

复算已冻结的 47 条外部评测（不重跑检测器）：

```bash
python3 Fuzz_Introspector/experiment/evaluate_native_alerts.py
```
