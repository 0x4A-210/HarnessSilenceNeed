# 复现指南 — REAL-03

本目录下的文件可以独立复现 `label.json` 里记录的所有关键证据。

## 环境要求

```bash
sudo apt-get install -y gcc libarchive-dev pkg-config
pkg-config --modversion libarchive   # 期望 3.8.5 或更高
```

## 一、复现 `add_passphrase` 的顺序约束（核心证据）

```bash
gcc -O1 repro_passphrase_order.c -o repro $(pkg-config --cflags --libs libarchive)
./repro
```

**期望输出**（本机实测，gcc 15.2.0 + libarchive 3.8.5）：

```
加密 zip 大小 = 148 字节

OLD  open_memory    = 0
OLD  add_passphrase = -30  <-- INTERNAL ERROR: Function 'archive_read_add_passphrase' invoked with archive structure in state 'header', should be in state 'new'
OLD  next_header    = -30, entries = 0

FIX  add_passphrase = 0
FIX  open_memory    = 0
FIX  next_header    = 1, entries = 1

耗时: OLD=0.001s  FIX=0.000s
```

**怎么读这组输出**：

| 行 | 含义 |
|----|------|
| `OLD open_memory = 0` | `open` 本身**成功**（ARCHIVE_OK） |
| `OLD add_passphrase = -30` | 但 `open` 之后再设口令，被库**拒绝**（ARCHIVE_FATAL） |
| 后面的 `INTERNAL ERROR ...` | 库自己给出的原因：此刻状态是 `header`，而该函数要求 `new` |
| `OLD entries = 0` | 结果是一条 entry 都读不到 |
| `FIX add_passphrase = 0` | 先设口令，成功 |
| `FIX entries = 1` | 能正常读到 entry |

**注意**：`libarchive_fuzzer.cc` 里 `add_passphrase` 的返回值**没有被检查**，所以旧 harness 编译运行全正常，只是读不到东西 —— 这就是本条属于 `silent` 而非 `explicit` 的原因。

## 二、复现 `compile_matrix` 的三格

三格都只需要链接系统库，不需要编译整个 libarchive：

| 格 | 组合 | 期望 |
|----|------|------|
| `h(M^1) × lib(M^1)` | `input/harness/oss-fuzz/libarchive_fuzzer.cc` | 编译通过 |
| `h(M^1) × lib(M)` | 同上 | 编译通过（**不报错**，silent） |
| `h(fix) × lib(M)` | 把 `add_passphrase` 挪到 `open` 前 | 编译通过 |

`label.json` 里记录的 `secs` 是 `0.004` 秒，量级可复现（`time` 命令测）。

## 三、复现 `fuzz_M` / `with_fix` 的 gap 统计

`label.json` 里记录的是「41 个 fuzz 语料输入下，`add_passphrase` 成功次数」：

| 版本 | 成功次数 |
|------|---------|
| `h(M^1)`（OLD 顺序） | **0 / 41** |
| `h(fix)`（FIX 顺序） | **41 / 41** |

复现方法：把 `repro_passphrase_order.c` 的 `main()` 改成遍历语料目录里的每个文件，对每个文件跑一遍 `run()`，统计 `add_passphrase` 返回 0 的次数。

语料可以从 OSS-Fuzz 的 corpus 或者自己用 libarchive 造（任意格式均可，加密与否不影响 `add_passphrase` 本身的成败判定）。

## 四、验证 commit 真实性

```bash
# H 必须真实存在于 oss-fuzz 仓库
curl -s "https://api.github.com/repos/google/oss-fuzz/commits/d5b74d5cccd0601ef4f88b19ea9f32740fcb10ba" \
  -H "Accept: application/vnd.github+json" | grep -E '"(sha|message)"' | head -4
```

期望看到 `d5b74d5cccd0601ef4f88b19ea9f32740fcb10ba` 和标题 `libarchive: fix fuzzer to cover encrypted archives`。

## 五、无法复现的部分（如实说明）

| 项 | 原因 |
|----|------|
| commit message 里的「15% → 45%」覆盖率 | 需要跑完整的 OSS-Fuzz 覆盖率流程。已用 OSS-Fuzz 公开的覆盖率快照间接验证：2024-06-01 = 15.2%，2024-09-01 = 49.1% |
| 真实 OSS-Fuzz 构建（Docker） | 需要 Docker，本机未安装 |
