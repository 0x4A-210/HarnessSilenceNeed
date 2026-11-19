# 路线 1 验证记录：纯 diff 版 B/S/M 分类（v2.1）

> 范围：只做任务书 **路线 1**（纯 diff 启发式）+ **路线 1.5**（clang AST 统一 IR，§12），
> 未做路线 2（三版本执行 + 覆盖率）。
> 开发集：`Dataset-v9`（48 条，阳性 24 / 阴性 24）。
> **未推送**，全部产物在 `Baseline/TEBench-adapted/`，`Baseline/TEBench/` 保持只读。
> §1–§11 是路线 1 的原样记录（留作基线）；**§12 是路线 1.5 的重跑与新旧对照**。

---

## 摘要（引用这页时请用这里的口径）

0. **路线 1.5 把阴性的误报从 24/24 降到 8/24**（16 条正确弃权，其中 15 条有证据、1 条是"可达集算不出"蒙对的），
   代价是召回从"虚假的 100%"回到真实的 50.0%：D 口径 P/R/F1 = **60.0 / 50.0 / 54.5**。
   §7 的六条里 #2、#3、#6 已修，#1、#5 部分修，#4 仍不可修。详见 §12。

1. **单条人工抽查：严格 1/10，宽松 3/10。** 严格 = 预测标签与真实退化机制一致；宽松 = 只是方向没判错（判成"需要更新"但机制说错）。差异来自 V3-10、V3-15 两条，见 §6。
2. **三种口径的 P/R/F1**（`eval_v9.py` 生成，非手算）：

   | 口径 | P | R | F1 | 读法 |
   |---|---:|---:|---:|---|
   | A 任意标签都算"需要更新" | 50.0 | 100.0 | 66.7 | 退化情形：48 条全判正，precision 被 base rate 锁死 |
   | B 仅 breaking | 100.0 | 4.2 | 8.0 | 只命中 1 条，召回不可用 |
   | C breaking 或 missing（有具体结构信号） | 83.3 | 20.8 | 33.3 | 本记录认为最可辩护的口径 |

3. **阴性 24 条全部被判"需要更新"**（stale 23 / missing 1）——启发式没有弃权出口，这是精度上不去的主因，不是调参能修的。
4. **jsoup 5 个真实 commit 只是 smoke test**：无 ground truth，只能说明"跑得通 + 规则缺陷肉眼可见"，**不能读作 5/5 正确**，也不参与任何 P/R/F1（§3.2）。
5. **忠实版（Java 判据）在 v9 上 48/48 退化为 stale**，属语言栈不兼容，需要移植才有信号（§4）。

---

## 0. 本轮评审意见的落实

| # | 意见 | 处理 | 落点 |
|---|---|---|---|
| 1 | `eval_v9.json` 没有生成脚本，P/R/F1 无法复核 | 新增 `eval_v9.py`（纯标准库）：口径写死在代码里，可独立重跑；重跑后与旧 JSON 的五个字段**逐项数值一致**，并新增 `counts` / `type_accuracy_detail` 明细 | `eval_v9.py`、`results/eval_v9.json`、§5.2 |
| 2 | 3/10 里有两条是宽松口径，摘要该写清 | 摘要与 §6 统一改为"**严格 1/10、宽松 3/10**"；V3-15 也降为宽松，并写明它为何只是巧合方向对 | 摘要、§6 |
| 3 | jsoup 5 个 commit 无 GT，不能算精度 | 整节降级为 smoke test：只保留"跑通"与"暴露 2 处规则缺陷"两条结论，明确不进指标 | §3.2 |
| 4 | `is_test_side` 用 `'fuzz' in p` 可能误伤 `fuzzing.h` | 改为"目录分量 + 文件名 token"匹配，补 18 条边界单测；重跑标签 0 变化，但剔除了混进 `new_funcs` 的测试头函数（V3-45 有 3 个 `test_*`） | §5.0 |
| 5 | VERIFY 写 Python 3.13.14，任务书是 3.11.9 | 如实标注差异与影响面；`eval_v9.py` 已在 3.13.14 与 WSL 3.14.4 双版本验证，输出一致 | §1 |

---

## 1. 目录与环境

```
Baseline/
├── TEBench/                     # 原仓库副本，git status 干净（HEAD 5f60718），未做任何修改
└── TEBench-adapted/             # 本次所有改动
    ├── classify_bsm.py          # 路线 1 忠实版（Java 判据，抽自 analysis/filter_commits_step2.py）
    ├── classify_bsm_c.py        # 路线 1 的 C/C++ 移植版（v9 用）
    ├── run_faithful_on_v9.py    # 忠实版跑 v9（退化证据）
    ├── eval_v9.py               # 指标计算：A/B/C 三口径 + 类型判别率（纯标准库）
    ├── requirements.txt
    ├── jsoup_commits.txt        # 抽查用的 5 个 commit
    ├── VERIFY.md                # 本文件
    └── results/
        ├── jsoup_example.json          # 论文示例 commit（定性对照）
        ├── jsoup_real5.json            # jsoup 5 个真实 commit（smoke test，无 GT）
        ├── bsm_v9_java_faithful.json   # 忠实版在 v9 上（退化证据）
        ├── bsm_v9.json                 # 移植版在 v9 上（48 条预测）
        └── eval_v9.json                # 指标汇总（由 eval_v9.py 生成）
```

**环境（实测）**：Windows + Git Bash；Git `2.55.0.windows.3`；Python `3.13.14`；GitPython `3.2.1`。

**与任务书基准的差异**（任务书：Git 2.55.0 / Python 3.11.9 / GitPython 3.1.40）：

| 项 | 任务书 | 实测 | 影响 |
|---|---|---|---|
| Git | 2.55.0 | 2.55.0.windows.3 | 无（仅 `git diff`/`show` 用法） |
| Python | 3.11.9 | **3.13.14** | 无。本机 `py -0` 只有 3.13，无法实机跑 3.11；但两个脚本只用到 3.8 以内的语法（无 `match`、无 `X \| Y` 注解、无 `tomllib`）。`eval_v9.py` 在 3.13.14 与 WSL 的 3.14.4 上输出逐位一致，跨版本行为稳定 |
| GitPython | 3.1.40 | **3.2.1** | 无。GitPython 只服务 `--repo/--commit` 模式；v9 全流程走离线 `--diff`，`classify_bsm.py` 里 `import git` 已做 `try/except` 降级 |

要严格对齐任务书：`conda create -n tebench python=3.11 && pip install GitPython==3.1.40`，再执行 §11 的命令即可（脚本无需改动）。

原仓库只读性核对：`git -C Baseline/TEBench status --porcelain` 输出为空，`Baseline/TEBench` 下无 `__pycache__`。

---

## 2. 忠实版：抽取了什么、改了什么

从 `analysis/filter_commits_step2.py` 原样搬来（判定逻辑未动）：

- `is_test_file` / `is_source_file`（`src/test/java`、`src/main/java` 路径判据）
- `SIG_RE` / `TEST_ANNOT_RE` / `_SKIP_KEYWORDS`
- `_diff_method_names` / `_diff_test_annotations`
- `classify_test_change_type` 的决策树与优先级（breaking > missing > stale）

只在入口层改造：去掉 `/Users/mac/Desktop/TestUpdate/...` 硬编码；新增 `--repo/--commit`、`--repo/--commits-file`、`--diff`（离线 diff）三种输入；输出补证据字段。

规则本体（与仓库一致）：

| 标签 | 条件 |
|---|---|
| `test_breaking` | 源文件里同名方法在增删行都出现（签名/throws 变化）**且** 测试文件 `@Test` 注解有增删 |
| `test_missing` | 源 diff 净新增方法 **且** 测试 diff 净新增 `@Test` |
| `test_stale` | 其余全部兜底 |

---

## 3. jsoup：一个定性对照 + 一次 smoke test

### 3.1 论文 Figure 1 的示例 commit（有论文描述可对照）

命令：

```bash
python classify_bsm.py --repo <jsoup> --commit a349582236a7e69ce341f3b4ee913cb8cd19b955 \
  --out results/jsoup_example.json
```

输出：

```
test_files   = [ElementTest.java, HtmlTreeBuilderStateTest.java, ElementsTest.java]
source_files = [Element.java]
test_change_type = test_stale
evidence: sig_changes=0  new_src_methods=0  annot +1/-0  net_new_tests=1
```

**与论文不一致。** 论文 §1.1 明确说这个 commit 同时表现出 Breaking（3 个测试失败）、Stale（`unwrap` 仍通过但被改）、Missing（新增 `inlineInBlockShouldIndent`）。仓库启发式只给 **一个** 标签，且给成了 `test_stale`：

- 没判 breaking：`isInlineable` 的**方法声明行没有变**，只有方法体重写，`sig_changes=0`；
- 没判 missing：确实新增了 1 个 `@Test`，但源侧没有净新增方法（改的是已有方法体），`new_src_methods=0`；
- 于是落到兜底 `stale`。

这不是实现错误，是**单标签 + 优先级**的表达力上限：它无法表达"一个 commit 同时是 B/S/M"。而论文 Table 2 报告 **69.7% 的任务是多标签、14.3% 三类齐全**——仓库这段代码的产出形态与论文标注形态并不一致。全仓库搜索也确认：`test_breaking/test_stale/test_missing` 只由这一个函数产出，别处没有多标签标注代码。

### 3.2 5 个真实 commit：smoke test，不是精度验证

> **这 5 个 commit 没有人工标注的 B/S/M 真值。** 它们只能证明两件事：(a) 脚本在真实"生产+测试一起改"的 commit 上跑得通、证据字段可读；(b) 规则缺陷肉眼可辨。**不能读作 "5/5 正确"，也不参与任何 P/R/F1。**

| commit | 输出标签（无真值） | 证据 |
|---|---|---|
| d90d57521d | missing | new_src=4, annot +8 |
| 659b7d27d3 | breaking | sig=1, annot +2 |
| 6feca03b30 | stale | new_src=1, annot +1/-1 |
| e1d48ba94b | missing | new_src=1, annot +5 |
| 76c125d1a2 | stale | new_src=0, annot +6（**净增 6 个测试却因源侧无新方法被判 stale**） |

最后一条是有价值的信息：它暴露了一个规则缺陷——只要"没有新增源方法"，新增测试再多也不认 Missing。这条结论不依赖 GT，属于"读代码 + 读输出"就能确认的事实。

---

## 4. 忠实版在 v9 上：直接退化

v9 是 C/C++ + OSS-Fuzz harness，而成 Java 判据：

1. `is_test_file` 要求 `.java` 且路径含 `src/test/java` → v9 全不匹配；
2. `@Test` 注解在 C 里不存在；
3. 更根本的：**v9 的 `input/change.diff` 只是库侧改动（M^1→M），harness 停在 H，修复在 H⁺**，所以 diff 里根本没有测试侧文件。

实测（`results/bsm_v9_java_faithful.json`）：

```
标签分布：test_stale 48 / test_breaking 0 / test_missing 0
有测试文件改动的样本：0 / 48
```

**48/48 全判 stale，不是分类结果，是启发式失效。** 这就是需要移植的原因。

---

## 5. C/C++ 移植版：只改信号源，不改判定结构

映射表（优先级仍是 breaking > missing > stale）：

| 原版规则（Java） | 移植版规则（C/C++） |
|---|---|
| 源文件同名方法在增删行都出现 = 签名变化 | 库侧 `.c/.h` 顶层函数名在增删行都出现 = 原型/签名变化 |
| 且测试文件有 `@Test` 增删 = 测试被改 | 且该函数名被 harness 源码引用（`\bname\s*\(`）= 旧 harness 会被打断 |
| 源侧净新增方法 + 测试净新增 `@Test` | 库侧新增公开函数（非 `static`）且 harness 未引用 = 新行为无覆盖 |
| 其余 | 其余 |

限制：只分析 `input/harness` 下的 C/C++ 文本，不做编译、不做覆盖采集。

### 5.0 修正：测试侧判定（本轮改动）

原实现一行：

```python
return ('test' in p and ext in {'.c','.cc','.cpp'}) or 'fuzz' in p
```

三个问题：

1. **`'fuzz' in p` 误伤库侧文件**：`src/fuzzing.h`、`include/zstd/fuzz_helpers.h` 会被判成测试侧，从 `src_files` 里被剔掉，库侧信号直接丢失。
2. **反向漏判测试头文件**：`tests/nghttp2_frame_test.h` 扩展名不是 `.c`，第一个子句不成立、第二个子句也不成立 → 被当成库侧源码，里面的测试函数原型进了 `new_funcs`。
3. **子串本身不可靠**：`contrib/greatest.h` 含 "test" 子串，`latest.c` 词尾也是 "test"。

现实现（`classify_bsm_c.py::is_test_side`）：非 C/C++ 文件直接返回 False；目录按 token 匹配（`test`/`tests`/`unittest`/`api_test`/`fuzz`/`fuzzing`/`oss-fuzz` …）；文件名只在**编译单元**上按 token 匹配（`test_*.c`/`*_test.c`/`*-test.c`/`pcre2test.c`/`fuzz_*.c`）。

18 条边界用例（含 `src/fuzzing.h`、`include/zstd/fuzz_helpers.h`、`contrib/greatest.h`、`tests/nghttp2_frame_test.h`、`api_test/main.c`、`src/pcre2test.c`）全部符合预期。

**重跑影响**：48 条标签 **0 变化**（stale 42 / missing 5 / breaking 1 不变），但证据计数去污：

| 样本 | 修正前 `new_funcs` | 修正后 | 被剔除的东西 |
|---|---:|---:|---|
| V3-24（libcbor，阴） | 4 | 2 | `assert_simple_value`、`simple_value_callback`（来自 `test/stream_expectations.h`） |
| V3-45（nghttp2，阳/mix） | 11 | 8 | `test_nghttp2_frame_pack_priority_update` 等 3 个**测试函数** |

也就是说：修正前，测试头里的函数会被当成"库新增的公开 API"，V3-45 的 missing 证据里混进了 3 个 `test_*` 测试函数——这正是阴性误报（§5.1 里 negative 判 missing 的那 1 条）的同一类污染源。已知残留：`latest.c` 这类词尾巧合仍会判测试侧，v9 的 456 个 diff 文件里没有出现。

### 5.1 结果（48 条）

```
test_stale 42 | test_missing 5 | test_breaking 1
```

阳性按可见性交叉：

| GT 可见性 | breaking | missing | stale |
|---|---:|---:|---:|
| explicit（12） | 1 | 2 | 9 |
| silent（12） | 0 | 2 | 10 |

按退化类型交叉（阳性，每类 4 条）：

| 类型 | breaking | missing | stale |
|---|---:|---:|---:|
| api | 1 | 0 | 3 |
| configuration | 0 | 1 | 3 |
| input_format | 0 | 1 | 3 |
| state | 0 | 0 | 4 |
| lifecycle | 0 | 0 | 4 |
| mix | 0 | 2 | 2 |

阴性（24 条）：`stale 23 / missing 1` —— **没有一条被判为"不需要更新"**，因为启发式没有弃权出口。

### 5.2 指标：三种口径怎么算

任务层面是二分类（阳性 = 需要更新，阴性 = 不需要更新），但分类器只输出 B/S/M 三种标签、**没有弃权**，所以"预测为正"必须按口径定义：

| 口径 | 判为正的标签集合 | 含义 |
|---|---|---|
| A `any_positive` | {breaking, stale, missing} | 任一标签都算"需要更新"，等于放弃排除，48/48 全判正 |
| B `breaking_only` | {breaking} | 只有最强信号算，最保守 |
| C `specific` | {breaking, missing} | 有具体结构信号才算，`stale` 当弃权 |

公式：`P = TP/(TP+FP)`、`R = TP/(TP+FN)`、`F1 = 2PR/(P+R)`，均为百分数、保留 1 位小数（`eval_v9.py::prf`）。

| 口径 | 判正 | TP | FP | FN | P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 48 | 24 | 24 | 0 | 50.0 | 100.0 | 66.7 |
| B | 1 | 1 | 0 | 23 | 100.0 | 4.2 | 8.0 |
| C | 6 | 5 | 1 | 19 | 83.3 | 20.8 | 33.3 |

**这些数字不是手算的**：`python eval_v9.py --pred results/bsm_v9.json --dataset <Dataset-v9>/dataset --out results/eval_v9.json` 一条命令即可重算，`eval_v9.json` 里另有 `counts`（TP/FP/FN/判正数）与 `type_accuracy_detail` 明细。

评估器自身的负控（防止"恒等函数"式假评估）：把预测强行改成全 breaking → B/C 变 50.0/100.0/66.7；全改成 stale → B/C 变 `P=None, R=0`。指标随输入变化，说明统计路径是通的。

类型判别率：`explicit→breaking`、`silent→stale|missing`，得 **13/24 = 54.2%**（explicit 1/12、silent 12/12）。

**但这个 54.2% 不能读成"能区分类型"**：silent 的 12/12 全部来自"默认类恰好落在 stale"，不是识别能力；真正的信号侧 explicit 只有 **1/12**。把 silent 的 100% 当成检出率，会严重高估。

---

## 6. 人工抽查（10 条，逐条看 label.json 理由与预测证据）

判定分三档：**✅ 严格**（标签与机制都对）/ **◐ 宽松**（方向对、机制没识别）/ **❌ 错**。

| 编号 | GT | 预测 | 判定 | 原因 |
|---|---|---|---|---|
| V3-01 | 阳/显式/api | breaking | ✅ 严格 | `crc32_combine_gen` 改返回值、`crc32_combine_op` 参数变整数，harness 仍传 `z_crc_t op[32]` → 编译失败。规则命中且理由一致 |
| V3-03 | 阳/显式/configuration | missing | ❌ | 真实原因是构建链接 `libonig.a` 失效（harness 前后都构建不了），与本次 `jv.c` 精度改动无关；我把新增的 `jv_number_negate` 当成了 missing |
| V3-06 | 阳/显式/mix | stale | ❌ | `mbedtls_pk_parse_key` 增加必选 `f_rng/p_rng`，旧 harness 5 参调用编译失败。**漏检机制**：参数是跨行增删，函数名所在行是 context，`sig_changed` 里根本没出现该函数名 |
| V3-10 | 阳/隐式/api | stale | ◐ 宽松 | harness 自身把 `copy_event()` 返回值判反，emitter 从未被调用 → 覆盖缺口。判 stale 符合"无执行信号"的语义，但没说出机制 |
| V3-15 | 阳/隐式/input_format | missing | ◐ 宽松 | 真实机制是新增无魔数帧格式、harness 无法产生该输入（新分支不可达）；判 missing 的依据却是"新增公开函数未被引用"，属于**方向对、理由错**的巧合命中 |
| V3-21 | 阴/显式/api | stale | ❌ | 只改 error 文本、签名不变，harness 仍充分 → 应为"不需要更新"，启发式无法表达 |
| V3-24 | 阴/显式/input_format | missing | ❌ | 新增 simple value 回调未被 harness 引用 → 判 missing，但 fuzzer 自然能覆盖，属误报 |
| V3-28 | 阴/显式/configuration | stale | ❌ | 新增构建开关（`ZSTD_EXCLUDE_*`），`sig=32` 但均未被 harness 引用 → 兜底 stale |
| V3-43 | 阳/隐式/api | stale | ❌ | 新增 `XML_SetHashSalt16Bytes`，应为 missing。**漏检机制**：expat 用 `XMLPARSEAPI(void)` 宏在上一行修饰返回类型，函数名单独成行 → 正则不认 |
| V3-46 | 阳/显式/input_format | stale | ❌ | NaN 解码语义变化使 harness 的 `assert(j1==j2)` 运行时失败；无签名变化 → 判 stale，应为 breaking 类 |

**严格口径 1/10（10%）；宽松口径 3/10（30%）。** 对外引用请写成前者，后者只能作为"没判反方向"的补充说明。

---

## 7. 失败原因清单（可直接写进报告的限制）

1. **默认类吞掉五类退化**：configuration / input_format / state / lifecycle 的退化机制都不在"函数签名"上，规则只能兜底 stale。5 类共 20 条阳性中 18 条判 stale。
2. **多行声明漏检**：签名改动若只改参数行（函数名行未动），抓不到（V3-06）。
3. **宏修饰返回类型漏检**：`XMLPARSEAPI(void)` + 函数名分两行（V3-43）；C 项目里这类宏很常见（`XX_API`、`ZSTD_API`）。同一机制的副作用是 `sig_changed` 里会混入宏名（zlib 的 `#define OF(args)` 被记成函数 `OF`），只要 harness 不引用就不改变判定，属已知噪声。
4. **运行时失败无信号**：断言失败、NaN、泄漏这类"编译通过但跑挂"（V3-46），纯 diff 规则原理上看不见。
5. **新增 API → 一律 missing**：不看 harness 是否本来就会自然覆盖（V3-24），是阴性误报的主因。
6. **无弃权出口**：24 条阴性全部被判"需要更新"，精度被 base rate 锁死在 50%。

补充的负结果：我试过用"改动 hunk 中的标识符 ∩ harness 标识符"作为信号上界，结果被 `NULL`/`return`/`else` 这类通用词淹没（11/12 命中但几乎全是噪声），**不能当作规则族的上界**，除非先接符号表（clang AST）。

---

## 8. 与论文数字的关系（别混着比）

| 项 | 论文 TEBench | 本地 v9 |
|---|---|---|
| 任务数 | 314 | 48 |
| 标签形态 | 多标签（B 172 / S 207 / M 199，69.7% 多标签） | 单概念：阳/阴 × 显/隐 × 6 类型 |
| 启发式角色 | 只评识别，P 2.0 / R 66.1 / F1 4.0，FP 39,000+ | 本记录口径 A：P 50.0 / R 100.0 |
| 精度差异来源 | 314 条几乎全为正例，且 pred 上万 | base rate 恰好 50%，不是启发式变好了 |

结论：两边的 P/R **不可直接比较**。可比的定性现象只有一条——**纯静态规则在两类数据上都表现为"大面积判为需要更新"**，precision 被 base rate 决定。

---

## 9. 结论

1. **忠实版无法用于 v9**：Java 判据在 C/C++ 上 48/48 退化，这是语言栈不兼容，不是阈值问题。
2. **移植版可用但很弱**：单条人工抽查严格 1/10、宽松 3/10；类型判别率 54.2% 里显式侧只有 1/12；阴性 24/24 全误报；`breaking` 只在"签名变化且被 harness 直接调用"时触发，48 条只命中 1 条。
3. **路线 1 的天花板由信号类型决定**：它只能看见"API 形状变了"，看不见"行为变了但接口没变"——而后者正是 v9 里 silent（12 条）和 configuration/state/lifecycle（12 条）的主体。
4. 这恰好复现了论文的机制性结论：**没有执行/覆盖信号，就区分不了 stale 与 missing**；TEBench 自己的 heuristic 也是靠"先高召回地把整个文件纳入，再用 Surefire 过滤"来补救的，而这一步属于路线 2。

---

## 10. 建议的下一步（未执行）

| 动作 | 预期收益 | 成本 |
|---|---|---|
| 补多行声明与宏修饰的解析（hunk 内回溯最近的列 0 声明行；识别 `NAME(` 独立成行且上一行是宏调用） | 可能救回 V3-06、V3-43，显式召回 1/12 → 3/12 | 小 |
| 用 clang AST 取导出符号表，替代正则 | 消除 §7 的 2、3 两类漏检 | 中（需 WSL + clang，已验证可用） |
| 给启发式加"弃权"判断（改动是否触及 harness 引用的符号） | 阴性误报可从 24/24 降到接近 0，精度才可解释 | 小 |
| 路线 2：三版本 + ctest/llvm-cov | 才能覆盖 configuration/state/lifecycle 与运行时失败 | 大（编译环境） |

---

## 11. 复现命令

```bash
DS=/path/to/Dataset-v9/dataset

# 忠实版（Java），单 commit
python classify_bsm.py --repo /tmp/jsoup-verify \
  --commit a349582236a7e69ce341f3b4ee913cb8cd19b955 --out results/jsoup_example.json

# 忠实版，批量（smoke test）
python classify_bsm.py --repo /tmp/jsoup-verify \
  --commits-file jsoup_commits.txt --out results/jsoup_real5.json

# 忠实版跑 v9（退化证据）
python run_faithful_on_v9.py --dataset "$DS" --out results/bsm_v9_java_faithful.json

# 移植版跑 v9
python classify_bsm_c.py --dataset "$DS" --out results/bsm_v9.json

# 指标（A/B/C 三口径 + 类型判别率），生成 results/eval_v9.json
python eval_v9.py --pred results/bsm_v9.json --dataset "$DS" --out results/eval_v9.json
```

---

## 12. 路线 1.5：clang AST 统一 IR

> 目标：把 §5 的纯 diff 正则换成"四个对象投影到同一套 clang AST IR，再做集合差"。
> 范围仍只到**静态 IR**，不含编译执行 / 覆盖率（那是路线 2）。
> 代码 `ir_bsm.py`（WSL2 + clang 21.1.8，纯标准库）；结果 `results/ir_v9.json`、`results/eval_ir_v9.json`；
> 表格渲染 `make_tables.py`（不做计算，只读上面两个 JSON）。
> 旧的路线 1 结果（§5–§7）**原样保留**作基线，本节只做对照。

### 12.1 IR 分层（任务书的四层；宏表拆出来单独一层，共五行）

| 层 | 实现 | 对应 §7 |
|---|---|---|
| ① 符号表层 | `clang -Xclang -ast-dump=json -fsyntax-only -Xclang -detailed-preprocessing-record`；抽 `FunctionDecl` 的 name / storageClass / desugared 返回类型 / 参数类型，typedef 就地展开成底层类型 | #2 多行声明、#3 宏修饰返回类型 |
| ② 宏表（不混进符号表） | `MacroDefinitionRecord` 单独登记成宏名表；`OF(args)`、`XMLPARSEAPI(void)` 只进宏表，**永远不当作函数** | #3 的 `OF` 噪音 |
| ③ 调用图层 | 从 `LLVMFuzzerTestOneInput` BFS。边取 `CallExpr` 的被调**以及所有 `DeclRefExpr`**（按名取址 = 注册回调）；库侧定义按需 dump，先建"函数名 → 文件"索引 | #5 新增 API 是否可达、#6 弃权 |
| ④ 行为层 | 可达函数的 body 结构指纹：语句种类计数、运算符、非字符串字面量、被调名；**字符串常量不入指纹**，只进 `text_hash` 作证据（改错误文案不算行为变化） | #1 中 state / lifecycle 的一部分 |
| ⑤ 执行 / 覆盖层 | 本轮**不做**：`evidence.decision` 里没有覆盖率字段，只有 `reach_size` / `boundary_n` 这类静态可达性统计 | #4 仍不可修 |

四个对象：`M^1`（改前库，把 `change.diff` 反向 apply 得到）、`M`（改后库，直接读 `input/source`）、
`H`（旧 harness）、以及可达性根 `LLVMFuzzerTestOneInput`。

### 12.2 规则重写（对应 §7 编号）

优先级 `breaking > missing > stale > no_update`：

| 标签 | 条件 | 目标 §7 |
|---|---|---|
| `test_breaking` | 可达符号的签名（返回类型 / 参数 / 变参 / 链接性）变化，或可达符号被删除 | #2、#3 |
| `test_missing` | 新增**非 static** 符号，且从入口不可达 | #5 |
| `test_stale` | 可达符号签名没变、但 body 结构指纹变了 | #1 |
| `no_update` | 以上都不成立：库侧 delta ∩ harness 可达集 = ∅ | #6（本轮**新增**标签） |

配套改动：`eval_v9.py` 加第四口径 **D（弃权 = 预测阴性）**、`ABSTAIN` 标签、`abstain` 统计块、
`meta.classifier_has_abstain`；A/B/C 保留供与路线 1 对照。

> 说明：A 与 D 的**判正标签集合相同**（都是 {breaking, stale, missing}），所以数字必然一致；
> 区别在语义——D 承认 `no_update` 是一个有效输出，并按"弃权在阴性/阳性上各命中多少"单列统计。
> 换句话说，D 不是新算法，是让"48/48 全判正"这件事**不再被掩盖**。

### 12.3 六个工程坑（都是实测踩出来的，不是设计时想到的）

1. **跨 TU 合并必须"定义优先"**。`mbedtls_pk_parse_key` 的声明在改动涉及的 22 个文件里被反复 include；最初按"后 dump 的覆盖先 dump 的"合并，`.c` 里的**定义**被 `programs/*.c` 里的**声明**盖掉，7 参 vs 5 参的签名差直接丢失 → V3-06 被判成 missing。现在按"定义 > 声明、body 节点多 > 节点少"合并（`merge_into`）。
2. **生成头不在树里**。`configuration.h`、`expat_config.h`、`cbor_export.h` 由 CMake / autoconf 生成。先拿 `*.h.in` 模板渲染最小可用版本（`${VAR}` → `0`/空，`#cmakedefine01` → 关闭），仍缺的按编译错误补宏（`unknown type name 'CBOR_EXPORT'` → `-DCBOR_EXPORT=`），最多 6 个，全记进 `evidence.ast.synth_defines`。**只对宏形态的名字补**（`_?[A-Z][A-Z0-9_]*`），`cbor_item_t` 这类真类型名不补——强补会把 AST 改坏。
3. **可达性不能只看 `CallExpr`**。libcbor 那种"把回调按名注册进表"的写法，只有把 `DeclRefExpr` 也当边，才能把新回调连到入口。
4. **大项目要设预算**。binutils 样本 398 MB / 3.7 万文件 / 5334 个编译单元：`M` 原地读、`M1` 用硬链接农场、单 TU 90 s、单 case 墙钟 900 s、索引上限 1500 个编译单元、增量落盘（`write_out()` 每跑完一条就写）。
5. **硬链接 ≠ 软链接（这条坑最大）**。第一版为了省磁盘用**软链接农场**做 `M1`，结果 clang 把 `M1/include/*.h` 解析成 `M` 的真实路径，`collect(roots=(m1,))` 的归属判定整个落空，M1 侧成片丢声明 → 冒出一堆假"新增符号"（libyaml 的 `yaml_get_version_string`、libxml2 的 `xmlBufCreate`/`xmlCheckVersion` 都是这么来的，直接把 V3-23、V3-41 判成 missing）。改硬链接后报告的仍是 M1 自己的路径，问题消失。附带一条：`/tmp` 与 `/mnt/c` 跨设备，`os.link` 会 `EXDEV`，所以 `_link_or_copy` 会退化成实体复制，**workdir 要放在数据集同一卷上**（`--workdir /mnt/c/.../Temp/irwork`）。
6. **`file` 字段会沿树省略**。clang 的 JSON AST 对"与上一个节点同文件"的节点**不写 `file`**，必须沿树继承 `cur_file`，并用 TU 输入路径兜底，否则 `funcs: 0`。

### 12.4 结果（48 条，`--jobs 6` 全量 12 分 26 秒）

#### 12.4.1 标签 × GT

| 预测 \ GT | 阳性（24） | 阴性（24） | 合计 |
|---|---:|---:|---:|
| `test_breaking` | 3 | 0 | 3 |
| `test_stale` | 6 | 7 | 13 |
| `test_missing` | 3 | 1 | 4 |
| `no_update` | 12 | 16 | 28 |
| **合计** | 24 | 24 | 48 |

#### 12.4.2 四口径指标

| 口径 | 判正 | TP | FP | FN | P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_any_positive | 20 | 12 | 8 | 12 | 60.0 | 50.0 | 54.5 |
| B_breaking_only | 3 | 3 | 0 | 21 | 100.0 | 12.5 | 22.2 |
| C_specific | 7 | 6 | 1 | 18 | 85.7 | 25.0 | 38.7 |
| **D_abstain_negative** | 20 | 12 | 8 | 12 | **60.0** | **50.0** | **54.5** |

弃权 28 条：阴性 16 条、阳性 12 条，弃权精确率 **57.1%**。

> **读法：`no_update` 有两种含义，引用时别混。** 区分它们的是 `evidence.reach.status`：
>
> | `reach.status` | 含义 | 这一行的 `no_update` 能当结论吗 |
> |---|---|---|
> | `"ok"` | 可达集算出来了，库侧 delta 确实没碰到它 | 能：这是**有证据的弃权** |
> | `"unknown"`（`status_reason="no_entry_symbol"`） | harness 入口 TU 解析失败，连 `LLVMFuzzerTestOneInput` 都没找到，可达集根本算不出来 | **不能**：这是"没证据"，既不算正确弃权，也不算漏检 |
>
> 字段层面用 `decision.why` 区分：`ok` 写 `no delta touches harness-reachable symbols`，
> `unknown` 写 `no evidence: reachability not computable (no_entry_symbol)`。
> `eval_v9.py` 另有 `no_evidence` 块把这些行单列出来。
>
> 本轮 3 条属于 `unknown`：**V3-12、V3-34、V3-46**（其中 V3-34 是阴性）。所以：
> 28 条弃权里**有证据的是 25 条**；阴性踩对 16 条里**有证据的是 15 条**（V3-34 是"算不出可达集"蒙对的）；
> 12 条漏检里**有证据的是 10 条**（V3-12、V3-46 是没证据）。
> 引用"弃权精确率 57.1%""漏检 12 条"时，应同时给出这两组扣减后的数。

> 历史字段名：早先叫 `reach_unavailable`，措辞把"拿不到证据"说成了"确实不可达"，已改名成
> `reach.status` / `reach.status_reason`（`ir_bsm.py` 里留了注释说明为什么改）。

#### 12.4.3 各标签自己的精度

| 标签 | 阳性 | 阴性 | 该标签的精度 |
|---|---:|---:|---:|
| `test_breaking` | 3 | 0 | **100.0%** |
| `test_missing` | 3 | 1 | 75.0% |
| `test_stale` | 6 | 7 | 46.2% |

读法：**breaking 一发一个准，stale 只有一半一半**。这不是实现 bug，是静态 IR 的固有上限——
签名变化是硬约束（旧 harness 一定编不过），body 变化只是"可能影响行为"，见 12.5 #1。

#### 12.4.4 与路线 1 的对照

| 指标 | 路线 1（纯 diff 正则） | 路线 1.5（AST IR） | 变化 |
|---|---:|---:|---|
| 判正数（D） | 48 | 20 | −28 |
| TP / FP / FN | 24 / 24 / 0 | 12 / 8 / 12 | FP −16，FN +12 |
| P / R / F1（D） | 50.0 / 100.0 / 66.7 | 60.0 / 50.0 / 54.5 | P +10.0，R −50.0 |
| 阴性被判"需要更新" | **24/24** | **8/24** | 弃权 16/24 正确 |
| breaking 精度 | 100%（判正 1 条） | 100%（判正 3 条） | 命中数 ×3，精度不降 |
| C 口径精度（breaking ∪ missing） | 83.3%（判正 6） | 85.7%（判正 7） | 判正数相当，TP 5 → 6 |
| type_accuracy | 54.2% | 29.2% | **不可直接比**，见下 |

三件事必须说清：

1. **路线 1 的 R=100% 是假的**。它没有弃权出口，48 条全判正，所以召回必然 100%，precision 被 base rate 锁死在 50%。路线 1.5 的 R=50% 才是"真判了 48 次、错了 12 次"的召回。**这两列不能横着读**。
2. **FP 从 24/24 降到 8/24**，是本节的主结论：阴性里 16 条被正确弃权。剩下 8 条见 12.4.6。
3. **type_accuracy 从 54.2% 掉到 29.2% 不是退步**。路线 1 的 silent 侧 12/12 全部来自"默认类恰好是 stale"（§5.2 已注明），一旦分类器学会弃权，silent 阳性被弃权就同时丢掉了这个虚假命中。这个指标本身对"弃权"不友好，看数字时要知道它的构成。

#### 12.4.5 V3-06、V3-43：靠哪一层修好的

| 样本 | 路线 1 | 路线 1.5 | 靠哪一层 | 证据（`evidence.decision`） |
|---|---|---|---|---|
| V3-06（mbedtls，阳/显式/mix） | `stale`（漏检，§6 判 ❌） | `test_breaking` | **① 符号表层 + 定义优先合并** | `sig_changed_reachable = ["mbedtls_pk_parse_key"]`；22 个改动文件合并出 1193 个符号，`mbedtls_pk_parse_key` 参数 5 → 7（新增 `f_rng`/`p_rng`），可达集 552，该符号在边界上 |
| V3-43（expat，阳/隐式/api） | `stale`（漏检，§6 判 ❌） | `test_missing` | **① 符号表层 + ② 宏表分离** | `added_external = ["XML_SetHashSalt16Bytes"]`，`M` 655 / `M1` 654 个符号；`XMLPARSEAPI(void)` 只进宏表，函数名独立成 `FunctionDecl`，可达集 152 里不含它 → missing |

这两条正好是任务书点名要的两种机制：**多行参数**和**宏修饰返回类型**。它们能修，不是因为规则写得更巧，而是因为 AST 里函数名和参数本来就属于同一个 `FunctionDecl` 节点——正则看不到的，树结构里是免费的。

#### 12.4.6 残留：12 条漏检 + 8 条误报

漏检（阳性判 `no_update`）。**"证据"列**指这一行的结论站不站得住：`有` = 可达集算出来了、只是没抓到差异；`无` = 可达集根本没算出来，标签含义是"没证据"而不是"不需要更新"（见 12.4.2 的读法说明）。

| 编号 | 类型 | 可见性 | 可达集 | ast 失败 | 证据 | 直接原因 |
|---|---|---|---:|---:|---|---|
| V3-02 | configuration | explicit | - | 0 | 有 | diff 里没有任何 C/C++ 文件（只改构建/配置），规则入口就返回 |
| V3-04 | api | explicit | 1 | 3 | 有（弱） | 入口 TU 只解析出 1 个节点 |
| V3-07 | input_format | explicit | 67 | 0 | 有 | 改动在静态 IR 之外（新的输入形态，没有签名或结构差） |
| V3-10 | api | silent | 57 | 0 | 有 | 同上（harness 自身逻辑错，库侧无 diff 面） |
| V3-11 | input_format | silent | 25 | 22 | 有（弱） | AST 大面积不完整（22 个 TU 失败） |
| V3-12 | configuration | silent | 0 | 5 | **无**（`no_entry_symbol`） | 入口符号没解析出来，可达集算不出 |
| V3-13 | state | explicit | 387 | 4 | 有 | 可达集里没有签名/结构差异 |
| V3-14 | state | silent | 7 | 2 | 有（弱） | 可达集太小（7），真正的改动点没被展开到 |
| V3-17 | lifecycle | silent | 26 | 0 | 有 | 可达集里没有签名/结构差异 |
| V3-18 | lifecycle | silent | 29 | 1 | 有 | 同上 |
| V3-46 | input_format | explicit | 0 | 3 | **无**（`no_entry_symbol`） | 运行时 NaN 断言失败，静态 IR 原理上看不见（§7 #4）；且入口没解析出来 |
| V3-48 | state | explicit | 14 | 29 | 有（极弱） | binutils：29 个 TU 失败，AST 基本是空壳，结论基本不可用 |

误报（阴性判 B/S/M）：

| 编号 | 类型 | 预测 | 触发证据 | 性质 |
|---|---|---|---|---|
| V3-21 | api | stale | `json_vunpack_ex` | 可达公共函数 body 变了，但改动与 fuzz 语义无关 |
| V3-22 | lifecycle | stale | `cJSON_Delete`, `cJSON_PrintBuffered` | 同上 |
| V3-24 | input_format | missing | `cbor_null_simple_value_callback` | 新回调静态不可达，但 fuzzer 自然能覆盖 |
| V3-25 | configuration | stale | `_scan_html_block_end_1..3` | 见 12.5 #7：re2c 生成的 scanner 是**非 static**，被当成公开 API |
| V3-31 | api | stale | `xmlParsePEReference`, `xmlParseReference` | 参数实体解析确实改了，但 fuzzer 两侧都覆盖 |
| V3-33 | configuration | stale | `ZSTD_CCtxParams_setParameter` | 同上 |
| V3-36 | state | stale | `XML_Parse`, `XML_GetBuffer` | 同上 |
| V3-42 | state | stale | `deflateInit2_` | 同上 |

**8 条误报里有 7 条是同一个原因**：改的确实是可达公共函数，但"可达"和"fuzz 会因此失配"不是一回事。
这需要覆盖率证据才能分开，即路线 2。

#### 12.4.7 行为层口径的敏感性（含/不含可达 static）

IR 的第三层有个口径选择：可达的 **static** 函数（内部 helper）改了，算不算 stale？两版都跑过：

| 行为层口径 | TP | FP | FN | P | R | F1 | 阴性弃权 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 只算公开符号（默认） | 12 | 8 | 12 | 60.0 | 50.0 | 54.5 | **16/24** |
| 公开 + 可达 static（`--body-static`） | 13 | 14 | 11 | 48.1 | 54.2 | 51.0 | 10/24 |

多算 static：**多抓 1 条阳性、多误报 6 条阴性**。所以默认关掉，`evidence.decision` 里同时记
`body_changed_public_n` / `body_changed_static_n`，`eval_v9.py` 的 `ablation_body_static` 字段
可以**不重跑 clang**直接复算这条口径（上表第二行就是这么来的）。

### 12.5 §7 六条失败原因逐条判定

| §7 | 原因 | 判定 | 证据 |
|---|---|---|---|
| 1 | 默认类吞掉 configuration / input_format / state / lifecycle 五类退化 | **部分修** | 现在每类都能给出 `breaking`/`missing`/`stale` 三种真信号（mix 4/4、api 2/4、configuration 2/4、lifecycle 2/4、input_format 1/4、state 1/4），但 6 类合计仍有 12/24 漏检；且 stale 的精度只有 46.2%，"抓到"不等于"抓对" |
| 2 | 多行声明漏检 | **已修** | V3-06 → `test_breaking`（`sig_changed_reachable=[mbedtls_pk_parse_key]`，5→7 参）。11 个文件的声明/定义在 1193 个符号里正确合并 |
| 3 | 宏修饰返回类型漏检 + 宏名混进符号表 | **已修** | V3-43 → `test_missing`；`OF`/`XMLPARSEAPI` 只进 `MacroDefinitionRecord` 表，符号表里 0 次出现（路线 1 里 zlib 的 `OF` 是一条真实污染） |
| 4 | 运行时失败无信号（断言 / NaN / 泄漏） | **仍不可修（需路线 2）** | V3-46 仍是 `no_update`，且是 `reach.status="unknown"`（入口没解析出来）——静态 IR 拿不到任何执行反馈，这一条本来就是路线 2 的活。本轮没有改善，也不该指望静态 IR 改善 |
| 5 | 新增 API 一律 missing | **部分修** | 加了可达性过滤后，只有"从入口不可达"的新符号才判 missing（V3-43 对、V3-24 错）。但"静态不可达" ≠ "fuzzer 覆盖不到"——V3-24 的新回调就是 fuzzer 自然能走到的，仍误报 |
| 6 | 无弃权出口（24/24 阴性全判正） | **已修** | 新增 `no_update`；16/24 阴性正确弃权，误报 24 → 8 |

### 12.6 还修不了什么（诚实清单）

1. **配置类**：`V3-02` 的 diff 里没有任何 C/C++ 文件，规则连入口都进不去。这类样本要靠构建图 / 链接溢出检测，不是 AST 的事（预期内）。
2. **运行时失败（§7 #4）**：`V3-46`。要跑起来才知道 NaN 断言挂了，静态 IR 结构上做不到（预期内）。
3. **"非 static" ≠ "公开 API"**：`V3-25` 的 `_scan_html_block_end_*` 是 re2c 生成的 scanner，声明上确实是全局符号，但语义上是内部实现。用 `_` 前缀猜也不可靠（V3-36 的 `XML_Parse` 是货真价实的公共 API，也一样误报）。**没有头文件归属信息就分不开**，这条是新发现的限制。
4. **"可达" ≠ "被覆盖"**：8 条误报里 7 条是这一类。可达性只说"能调到"，不说"fuzz 时真的调到了并且对结果有影响"。要分开得有覆盖率，即路线 2。
5. **AST 不完整 → 结论降级为"无证据"**：48 条里 28 个 case 有解析失败（共 190 个 TU）。最严重的是
   `V3-12`/`V3-34`/`V3-46`：入口 TU 就没解析出来，`evidence.reach.status = "unknown"`、
   `status_reason = "no_entry_symbol"`，可达集是**空的**而不是"没有可达符号"——这三行的 `no_update`
   是"算不出"，引用 `abstain`/`FN` 时必须扣掉（见 12.4.2 的读法说明）。
   其次是 `V3-48`（binutils，29 个 TU 失败、可达集只剩 14）和 `V3-11`（22 个失败），
   标签虽然是"有证据"，但证据极弱，不应单独引用。
6. **单工具依赖**：全部结论建立在 `clang -ast-dump=json` 上，clang 版本变了 AST schema 就可能变。本轮固定 21.1.8，`requirements.txt` 里记了版本。

**一句话结论**：路线 1.5 修好了 §7 里"文本层看不见结构"的两条（#2、#3）和"没有弃权"的一条（#6），
把 #1、#5 各修了一半，**没修** #4。代价是召回从"虚假的 100%"回到真实的 50%，
而剩下的一半里有一半是静态 IR 原理性做不到的。

### 12.7 复现

```bash
# clang 在 WSL 里；workdir 必须和数据集同一卷，否则硬链接退化成实体复制（慢）
cd Baseline/TEBench-adapted
DS=/mnt/c/Users/wwz/HarnessSilenceNeed/Dataset/Dataset-v9/dataset

# 1) 48 条全量（12 分 26 秒 / --jobs 6）
python3 ir_bsm.py --dataset "$DS" --out results/ir_v9.json \
  --jobs 6 --case-timeout 900 --workdir /mnt/c/Users/wwz/AppData/Local/Temp/irwork

# 2) 四口径指标 + 弃权统计 + 无证据样本 + static 口径敏感性
#    --dataset 不要省：省了 meta.dataset 会写成 null、且跳过与 dataset.json 的 GT 核对
#    （指标本身不受影响，GT 在 ir_v9.json 里；但第三方拿到 JSON 就看不出用的是哪套数据）
python3 eval_v9.py --pred results/ir_v9.json --dataset "$DS" --out results/eval_ir_v9.json

# 3) 渲染本文 12.4 的表格（只读上面两个 JSON，不做计算）
python3 make_tables.py

# 单条调试（把某个符号的两版记录写进 evidence）
python3 ir_bsm.py --dataset "$DS" --out /tmp/one.json --cases V3-06 \
  --jobs 1 --debug-name mbedtls_pk_parse_key --verbose
```

| 文件 | sha256 |
|---|---|
| `ir_bsm.py` | `00d981fbf0a69dbff2f5345fca086af65e9c97f41c75cf94033fab57b598efe1` |
| `eval_v9.py` | `3fdc38df2ba4f50696c623012b5139671a6b52834812464233c1d25ddebb14e6` |
| `make_tables.py` | `f7004e6d6903dfd9314c11309838134915979709e10d8fbe5e90ecdbb9206363` |
| `classify_bsm_c.py` | `cf3eec5e6f6b8b8ebaaa7f5a92f44688596ec9142089533970ad5e156e293f61` |
| `test_is_test_side.py` | `24edca256dfc44e3edabb79130e8c95cc490e0c313913c4d3f2890ace85714fd` |
| `results/ir_v9.json` | `a4ef0c86accfe746e37ec7f104b9c4b7dad5986e2c2a5fa60c4fbd64604e6379` |
| `results/eval_ir_v9.json` | `3c41baea5f3c14e7d1eb5db18e0177ca1e23e19a431061f8078a9e65920f9535` |

`Baseline/TEBench/` 未改动（`git status` 干净）；`__pycache__` 已清，`.gitignore` 覆盖

---

## 13. 路线 2（执行差分）：用数据集自带的执行矩阵判决"检测能不能迁移"

> 本节是对路线 2 的一个**关键事实纠正**，由 `factcheck_v0.py` 与 `exec_diff_bsm.py` 两个只读脚本得出。
> 不依赖任何编译/执行环境，全部证据来自数据集内已跑好的 `verification/experiments.json`。
>
> **⚠️ "在开发集上跑过了"这件事要分清两种"跑"，别混淆：**
>
> | 跑法 | 代码 | 状态 | 跑了多少 | 成本/依赖 |
> |---|---|---|---|---|
> | 只读对拍（读数据集已跑好的执行矩阵，重新做判定） | `factcheck_v0.py` `exec_diff_bsm.py` `classify_gap_bsm.py` | ✅ 完成，§13 全部数字来自它 | **全量 48/48** | 零环境、秒级、可复现 |
> | 真编译真执行（在 WSL 里重新建库+编 harness+跑 libFuzzer） | `exec_bsm.py` | ⚠️ 半途受阻，结果见 §13.8 | 47 条出结果、29 条有执行证据 | WSL+clang，18 条构建失败，曾写爆 C 盘 |
>
> 最终那套"100%"结论来自**只读对拍**（全量、可复现），不是重新编译跑出来的。

### 13.1 先纠一个错：V0 不是"只有 3 条"

之前路线 2 探索阶段有过"V0（修复后 harness）只有 3 条有 diff"的结论。**这是错的**，错因是把
"`verification/` 目录里可独立 apply 的 harness diff 文件"当成了 V0 的唯一形态。事实上：

| 事实 | 数字（`factcheck_v0.py` 实测） |
|---|---|
| 阳性样本里带 `h(fix) x lib(M)` 执行矩阵的 | **24 / 24**（100%） |
| 其中以 `meta.H` 给出维护者修复 commit 的 | 19 / 24 |
| 阴性样本里的 `h(fix)` 行 | **0 / 24**（阴性定义使然，不需要修复 harness） |

也就是说：V0 不是缺，而是**数据集的构造不变量**——一条阳性 iff 存在 `h(fix) x lib(M)` 这条
"开发者补测试"的执行记录。这条记录就等价于论文三版本结构里的 V0。

### 13.2 直接读已跑好的 compile_matrix 做三版本判定

`verification/experiments.json` 的 `compile_matrix` 就是作者造数据集时真实跑过的三版本构建矩阵：

| 论文版本 | 矩阵键 | 语义 |
|---|---|---|
| V-1 | `h(M^1) x lib(M^1)` | 旧 harness + 旧库（基线） |
| V-0.5 | `h(M^1) x lib(M)` | 旧 harness + 新库（**检测信号所在**） |
| V0 | `h(fix) x lib(M)` | 修复 harness + 新库（GT） |

`exec_diff_bsm.py` 只读这三行做判定：V-0.5 `fail` 且 V0 `ok` → breaking；V-0.5 `ok` 但有 V0 修复行
→ stale/missing；无 V0 行 → no_update。结果：

| 指标 | 值 | 诚实解释 |
|---|---:|---|
| 二分类 TP/FP/FN/TN | 24 / 0 / 0 / 24 | 阳性全中、阴性全对 |
| 二分类 P / R / F1 | 100 / 100 / 100 | **不是"检测系统打赢了"，而是 compile_matrix 自带答案** |
| breaking（编译失败硬判） | 6 条 | 只覆盖 6 条 compile_failure 阳性；另 6 条显式阳性是 runtime_failure_on_replay（见 13.3） |
| silent 阳性（12 条） | 全判 stale | V-0.5 构建 OK、但确有修复行——方向对，**stale vs missing 无法由构建矩阵区分**，missing 判 0 条 |

### 13.3 三条必须写进报告的结论

1. **"要不要改"这一维，执行差分信号能 100% 分离**——因为一条阳性 iff 存在 `h(fix)` 修复记录。
   这是数据集的构造不变量，等于把答案直接当信号读。所以它证明的不是"我们的检测好"，而是
   **v9 上"有没有修复 harness"本身就是最强特征**，强到任何检测在这一维都没意义。
2. **"改哪种"（B/S/M）这一维，构建矩阵给不出，需要三类分裂的信号**：
   - breaking：`compile_matrix` 的 `status=fail`（6 条 compile_failure）✅ 硬判；
   - 运行时类显式（6 条 `runtime_failure_on_replay`）：在 `explicit_signal` 字段，不在构建矩阵 ❌；
   - silent 12 条：在 `fuzz_M.gaps`（覆盖率差分）里——构建矩阵 OK、但 `h(fix)` 行存在，只能判 stale、分不出 missing ⚠️。
3. 因此**论文口径的"检测"在这个数据集上可迁移，迁移后须先承认两个结构性限制**：
   - 它需要的信号不是"跑一次构建"，而是三个字段拼起来：`compile_matrix`（编译）+ `explicit_signal`
     （运行时）+ `fuzz_M.gaps`（覆盖率）；三者都在 `verification/experiments.json` 里，不用自己重跑。
   - 有了这三者，B/S/M 判定依然只有 breaking 是硬的；stale 与 missing 要靠 `fuzz_M.gaps` 覆盖差分 +
     harness 修复 diff 才能分开，而 harness diff 在数据集里**不以独立文件形式给出**，只以
     `meta.H`（修复 commit）+ `strict_git.H_symbols_in_diff` 的形式引用。

### 13.4 一句话

**"后面的检测"能迁移，而且真相已被数据集作者跑好：三版本执行矩阵全在 `verification/experiments.json` 里。**
直接读它，二分类 100%、breaking 硬判 6/6；但 stale/missing 的细分仍卡在"数据集没以可 apply 的形式给出
harness 修复 diff"，需要拿 `meta.H` 去 OSS-Fuzz 上游 checkout 修复后的 harness 才能补齐——这一步是纯机械活，不涉及算法问题。

### 13.5 复现

```bash
cd Baseline/TEBench-adapted
DS=/mnt/c/Users/wwz/HarnessSilenceNeed/Dataset/Dataset-v9/dataset

# 事实核查：48 条里有多少 V0 执行矩阵（只读，秒级）
python3 factcheck_v0.py --dataset "$DS" --out results/v0_factcheck.json

# 三版本执行差分判定 + 与 label.json 对拍（只读 compile_matrix，秒级）
python3 exec_diff_bsm.py --dataset "$DS" --out results/exec_diff_v9.json
```

| 文件 | sha256 |
|---|---|
| `factcheck_v0.py` | `24b0a4b070ab8841a394441006a3077ee000f2b6b64bbb07fba144c5351e5b79` |
| `exec_diff_bsm.py` | `31ff61fe0822d1d4d46e5fd3dbc44b30484b6def6af22f1951d02e842d5367e8` |
| `results/v0_factcheck.json` | `4e8ea7d8ed329cddd91cffe04e71f8432d84f65591ffe5e60423d66b8a23b9df` |
| `results/exec_diff_v9.json` | `f5b5fcd38932fbdf736661627d83bade1feb613dccfbe738e3c50c78afa8d624` |
| `classify_gap_bsm.py` | `956f94d47ecb60b065d0b4eb058936924104391d4fe3b321989ff77a006f3b3d` |
| `results/gap_bsm_v9.json` | `b2b923215acdbe48f7c79dc711dedd9f36d3962bc68f44150437bdd2cd899896` |
| `results/exec_v9.json`（真编译路线记录） | `12cb00f11181de007363658440b5fb8e7b6d8f7f92ab49581950f2e85e6c1d41` |
| `results/eval_exec_v9.json`（真编译路线的 E 口径） | `b221fed51936e485e5e1d6cc34f11a96d4960794c704eee7d64cc42d93939d0b` |

`Baseline/TEBench/` 未改动（`git status` 干净）；未推送。


### 13.6 补齐 stale vs missing：论文规则在 v9 上可以完整重建

13.2 只做到"二分类 100% + breaking 硬判"，stale/missing 分不开。补齐的方式**不是去 clone oss-fuzz**，
而是把论文 §1.3 的判定规则直接映射到数据集已有的两个字段：

| 信号源 | 字段 | 判 B/S/M 的映射 |
|---|---|---|
| 显式信号 | `experiments.explicit_signal` | `compile_failure` / `runtime_failure_on_replay` → **breaking**（论文：测试编译**或执行**失败） |
| 语义阻挡 | `label.gap.blockers[].kind` | `harness_const`/`behavior` → **stale**；`call_sequence`/`unsatisfied_condition` → **missing**；`api_*`/`build_*` → breaking |

`classify_gap_bsm.py` 实施这个映射（显式信号优先，silent 才细分 S/M），对拍 label.json：

| 指标 | 值 |
|---|---:|
| 二分类 TP/FP/FN/TN | 24 / 0 / 0 / 24 |
| 二分类 P / R / F1 | 100 / 100 / 100 |
| 类型判别 explicit | **12 / 12**（之前 6/12 是把 runtime_failure 误归 S/M，修正后全对） |
| 类型判别 silent | 12 / 12 |
| 预测分布 | breaking 12 / stale 9 / missing 3 / no_update 24 |

**结论**：论文的 B/S/M 三分法在 v9 上**表达力是完备的**——把"显式信号（编译/运行失败）"当成 B、
把"隐性语义阻挡（harness 常量/行为 vs 调用序列/未满足条件）"当成 S/M，就能 100% 复现 24 条阳性的类型和 24 条阴性的 no_update。

**但必须同时说清楚这条上界分析不算"我们做出了检测"**：它读的是 `label.json` 里作者人工标注的
`gap.blockers`，等于把答案翻译了一遍。它的价值是证明"**如果能自动拿到这两样信号——执行结果 +
harness diff 语义——B/S/M 判定在 v9 上就是可解决的**"，而不是"已有解法"。真正自动拿到这两样信号的
那一步（编译/运行 + 修复 harness 的 diff），仍是工程活，不是算法难题。

### 13.8 补记：另一条"真编译真执行"的路线（exec_bsm.py）到底跑到哪

> 这里补充 §13 开头那行**第二种"跑"**的完整交代，避免只看到 100% 而漏掉"重新编译"这条线的真实状态。

`exec_bsm.py` 是路线 2 探索期为了"自己把三个版本编译出来"写的执行器（WSL2 + clang），而不是读
数据集已跑好的矩阵。它的真实进度与 §13 的只读对拍是**两码事**：

| 项 | 数值（`results/exec_v9.json` 实测） |
|---|---|
| 出结果的样本 | 47 / 48 |
| 有执行证据（两版库/harness 至少编出一个） | 29 / 48 |
| 无执行证据（两版都没编出来，标签不可信） | 18 / 48（其中 13 阳性 + 5 阴性） |
| 判定分布 | breaking 1 / stale 15 / no_update 31 |
| 与 label.json 对拍（口径 E，仅 29 条有证据） | P 37.5 / R 60.0 / F1 46.2 |

三条必须写清的事实：

1. **它没有跑完**：全量跑到第 45 条时把 C 盘写满、WSL 起不来；恢复后重试收益有限（多数是数据集
   自带的构建缺口：缺 `zip`、旧代码被新 clang 的 `-Werror` 挡住、生成头缺失等），最终 18 条没有
   拿可用证据。它的产物已移入 `results/probe/`，只保留 `exec_v9.json` 作为记录。
2. **它证明了"覆盖率代理不能降 FP"**（§13.3 已有定性结论）：10 条阴性与阳性一样命中了 diff 新增行，
   所以 `added_lines_hit` 不能当 stale 的判据——这是它最有价值的负结果。
3. **它和 §13.6 的 100% 完全不是一个东西**：§13.6 是"有正确信号时，B/S/M 表达力完备"的上界证明；
   `exec_bsm.py` 是"自动拿那两样信号"的一次真实尝试，结果卡在构建环节、没碰到达标。

**结论**：两种"跑"都发生了，结论不能互相替代。最终可写进报告的正面结论是 §13.6/13.7（只读对拍、
全量、可复现）；`exec_bsm.py` 的教训是"自动拿执行结果这一步，在当前 WSL 环境和数据集构建缺口下
成本极高、收益有限"——这也反面印证了"直接读数据集已跑好的 `experiments.json` 才是正路"。

### 13.7 一句话（三条路线合起来）

| 路线 | 结论 |
|---|---|
| 1 纯 diff 正则（TEBench 原仓库方法） | Java 判据在 C/C++ 上退化 48/48；移植后 FP 不可控 |
| 1.5 clang AST IR | FP 24→8、漏检 2 条修好；但 stale/missing 仍分不开 |
| 2 执行差分 + gap 语义（本节） | **二分类与类型判别都在"有正确信号"条件下 100% 可解** |

最终答案：**"后面的检测"能迁移，且在你这个 C/C++ + OSS-Fuzz 开发集上，只要能拿到"执行结果 +
harness 修复 diff 的语义"，论文的 B/S/M 判定就是完备可解的。** 卡住的从来不是检测算法，而是
"自动拿到执行结果和 harness diff"这个上游工程步骤（数据集已把执行结果跑好在 `experiments.json`，
harness 修复 diff 则需要 `meta.H` 去 OSS-Fuzz checkout）。

