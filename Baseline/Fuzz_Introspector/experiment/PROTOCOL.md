# 本轮执行协议

## 官方组件

- 官方 FI 原始仓库固定在与镜像编译器一致的提交，保留 Git 历史和来源。
- 官方 OSS-Fuzz helper.py 按原样执行，使用其支持的 OSS_FUZZ_DIR 环境变量定位独立实验工作区。
- 不修改官方 compile、LLVM pass、源码前端、报告分析器、blocked 阈值或官方报告。
- 两个 upstream 仓库运行前后检查 tracked diff；镜像代码另行检查提交号和工作区状态。

## 数据集适配

- 只装载主集 48 个 case.json 及 input/；不装载 label.json、NOTES、verification 或 extension。
- source 为修改后源码；in-tree harness 用 input/harness 中的旧文件覆盖。原始数据集不改动。
- 每个 case 生成独立 OSS-Fuzz 项目上下文；同一项目不同样本不共享构建目录或语料。
- input.tar 含完整输入，记录 SHA-256。每种 sanitizer 重新展开同一输入，清理自身 work 目录，保持源码快照一致。
- 项目构建入口适配历史路径、依赖和声明的 target；不修复旧 harness 的 API 或行为。
- 公共兼容项：gold 使用 DWARF4；json-c 的 GNU 声明及旧警告；libspng 的历史 fcommon；mbedTLS 关闭把全部警告提升为错误的项目开关。
- jq 使用数据集自带、由原 configure 选项构建的 oniguruma 静态库；兼容 vendor/ 与 modules/ 路径差异。初始系统库尝试保留但不作为最终结果。
- xz 的原 Makefile 将目标直接写到 `$OUT`；删除适配脚本中多余的二次复制后，独立重跑完整流程。
- 仅构建 case.json 声明的目标及所需库，不建立项目的所有可执行程序。未下载公共/私有语料，使用官方 helper 在新目录中生成语料；各项目随构建带出的字典、选项以逐条日志为准。这不是 OSS-Fuzz 线上长期语料覆盖率的重现。
- 构建脚本中的 libpng 配置、c-ares 宏处理、jansson 的链接选项及 binutils 的 main 重命名用于接入 fuzz target；全部保留在 adapter 和逐条快照中，不能声称与各项目线上构建环境逐项一致。
- PostgreSQL 为动态运行恢复提供的 createdb 初始化步骤；该准备不改变被测旧 harness。
- binutils 采用输入 OSS-Fuzz 配方中的单独 native GAS 配置，与其原链接对象一致；初始适配误用顶层多仿真目标配置，修正后以独立目录全流程重跑。
- 这些是构建和输入适配，不是与官方源码相同的组件。不能把整个 experiment/ 宣称为官方仓库代码。

## 运行流程

每条直接调用官方命令：

```
python3 upstream/oss-fuzz/infra/helper.py introspector fi-v9-v3-XX --seconds=30 --out <case-report>
```

官方执行 ASan 构建、运行 fuzzer、coverage 构建、覆盖率提取、introspector 构建和报告。完整流程失败后，另用官方 `build_fuzzers --sanitizer=introspector` 补跑源码/LTO分析，分别记录返回码，保留完整流程失败事实。

不调用上轮 t12 的编译包装器、FI 文件筛选器、ctags 映射器、分类器或评测脚本。项目构建适配被复制为此目录内的独立文件，运行不依赖旧目录。

## 统计语义

以下描述原生检测与结果索引的口径。2026-11-15 按用户后续要求新增了独立外部评测：将已冻结的官方 `blocked` 提示作为告警，与维护真值对照，失败样本单独标记，并分别汇报 47 条总体及 42 条完整运行子集。未修改原生检测流程；代理评测映射、公式与限制见 [实现方案](../实现方案.md) 和 [外部评测报告](../REPORT-47-EVALUATION.md)。

- 完整流程成功率、官方报告生成率、原生静态可达比例、原生运行覆盖比例，是运行/覆盖指标。
- 官方 blocked / branch blocker 信息按原报告展示，不重新设阈值、不转换为维护阳性。
- 不用编译失败替代维护阳性；不把无报告当作维护阴性。
- 不计算维护分类 Precision / Recall / FPR / FNR / F1，因为原生输出没有对应真值的预测标签。
- 30 秒为每个 fuzzer 的有限实验运行时间；不代表充分覆盖，也不证明不存在阻塞。
