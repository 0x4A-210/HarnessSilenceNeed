# REAL-25 — api / explicit / haproxy

> 编号变更（2026-11-23）：本样本最初编为 `REAL-19`；同日先与 bzip2 的 `REAL-18` 互换，
> 随后随 `REAL-07`~`REAL-18` 整体后移 7 位，最终定为 `REAL-25`。样本内容与实测数据未变。


## 一句话

`readcfgfile()` 的入参在 M 里从 `const char *file` 变成了 `const struct cfgfile *cfg`。
旧 harness 照旧传 `char filename[256]`：C 只报一条 `incompatible-pointer-types` 警告，编译链接都过，
但运行期被调函数把这块栈内存当结构体解引用——`cfg->content` 取到文件名里 pid 的末两位 ASCII，
当成指针就是 `0x3232`，`cfg_apply_default_path` 一读就 SEGV。M 之后这个 fuzzer **连一次解析都跑不完**。

## 判定链

| 环节 | 结果 |
|---|---|
| `h(M^1=2bb34edb0b) × lib(M^1)` | 编译无相关警告，运行 **rc=0 / 5 ms** |
| `h(M^1) × lib(M=5b52df4c4d)` | 编译 **rc=0**（仅 `-Wincompatible-pointer-types`），链接 rc=0；运行 **SEGV 0x3232** |
| `h(H) × lib(M)` | 编译失败：`call to undeclared function 'parse_cfg'` |
| `h(H) × lib(c6cfa7cb4a)` | 编译运行 **ok / 2 ms** |

崩溃栈（原样摘自 `verification/run_M_old.log`）：

```
UndefinedBehaviorSanitizer: SEGV on unknown address 0x000000003232 (READ)
 #1 cfg_apply_default_path  src/cfgparse.c:1609:8
 #2 readcfgfile             src/cfgparse.c:1859:7
 #3 LLVMFuzzerTestOneInput  fuzz_cfg_parser.c:42:2
```

`0x3232` 的低 16 位是 ASCII `"22"`——正是本次复跑 `/tmp/libfuzzer.422` 里 pid 的末两位。
崩溃地址随 pid 变化（首次运行 pid=2099 时为 `0x000000393930`，即 `".99"`），
但形状完全确定：**把字符串当指针**。

## 为什么会踩到

M 的 patch 只有几行（`include/haproxy/cfgparse.h`）：

```diff
-int readcfgfile(const char *file);
+int readcfgfile(const struct cfgfile *cfg);
```

`src/cfgparse.c` 里同步改成：

```c
int readcfgfile(const struct cfgfile *cfg)
{
    ...
    const char *cur_position = cfg->content;
    char *file = cfg->filename;
```

也就是说，函数体从此**不再 open 文件**，而是直接读 `cfg->content`。旧 harness 传进来的 `char[256]`
被解释成 `{filename, content, size}` 三个字段：`content` 拿到的是 `"/tmp/lib"` 这几个字节，
`size` 拿到的是后面的字节——所以一进 `cfg_apply_default_path` 就死。

## 为什么归 api 而不是 input_format

input_format 是"fuzz 字节到程序输入的构造方式变了"，而这里**输入字节到配置文本的映射没变**（仍然是直接写进文件/内存）。
变的是**调用契约**：同一个函数名，参数从路径字符串换成了结构体。修法也是纯 API 层面的——在栈上把三个字段填好。

## 必须如实说明的两点

1. **M 与 H 之间还有一次改名**。`c6cfa7cb4a`（2024-08，`MINOR: startup: rename readcfgfile in parse_cfg`）
   把函数名从 `readcfgfile` 换成 `parse_cfg`，签名沿用 M 的 `const struct cfgfile *`。H 的修复用的是新名字，
   所以严格三格里的 `h(H) × lib(M)` 会因 `parse_cfg` 未声明而**编译失败**，必须补一格
   `h(H) × lib(c6cfa7cb4a)` 才闭合。退化的因果起点仍然是 M（签名），改名只是同一轮重构的下一步。
   这一点没有藏，`verification.json` 的 `compile_matrix` 里有第四格，`budget_note` 里也写了。
2. **这个退化在 CI 上是"绿"的**。clang 默认不把 `incompatible-pointer-types` 当错误，链接也不报错，
   所以只有真正跑一次输入才会发现。这也是为什么它值得作为 explicit 样本——不是编译失败型，
   而是"编译成功、启动即崩"型。

## 四格编译矩阵（实测）

| 格 | 库版本 | harness | 结果 |
|---|---|---|---|
| 1 | `2bb34edb0b`（M^1） | `fuzz_cfg_parser.c.pre_fix` | ok，rc=0，5 ms |
| 2 | `5b52df4c4d`（M） | `fuzz_cfg_parser.c.pre_fix` | 编译警告 + 链接 ok，运行 SEGV |
| 3 | `5b52df4c4d`（M） | `fuzz_cfg_parser.c`（H） | 编译失败：`parse_cfg` 未声明 |
| 4 | `c6cfa7cb4a`（M 之后改名） | `fuzz_cfg_parser.c`（H） | ok，rc=0，2 ms |

## 复现

```bash
# 1) 取两棵库树（codeload 归档）
curl -L https://codeload.github.com/haproxy/haproxy/tar.gz/5b52df4c4d05ddcbcfdec9792520d2495614547c -o ha-M.tgz
curl -L https://codeload.github.com/haproxy/haproxy/tar.gz/2bb34edb0b17040d6bfc40715f94b7f434c0fdd9 -o ha-M1.tgz

# 2) 按 projects/haproxy/build.sh 构建
cd haproxy-<sha>
make -j$(nproc) TARGET=generic CC=clang
sed -i 's/int main(int argc/int main2(int argc/g' src/haproxy.c
sed -i 's/dladdr(main,/dladdr(main2,/g; s/(void*)main/(void*)main2/g' src/tools.c
clang -Iinclude -g -DUSE_POLL -DUSE_TPROXY -DCONFIG_HAPROXY_VERSION='""' -DCONFIG_HAPROXY_DATE='""' -c src/haproxy.c -o src/haproxy.o
ar cr libhaproxy.a src/*.o

# 3) 编译 harness 并跑
clang -g -O1 -Iinclude -DUSE_POLL -DUSE_TPROXY -DCONFIG_HAPROXY_VERSION='""' -DCONFIG_HAPROXY_DATE='""' \
      -fsanitize=fuzzer -c fuzz_cfg_parser.c -o /tmp/h.o
clang -fsanitize=fuzzer /tmp/h.o libhaproxy.a -o fuzz_cfg_parser
./fuzz_cfg_parser -runs=1 seed_cfg.txt
```

## 文件与哈希

- `input/change.diff` — H=9fa7466368 的完整 diff（913 字节），`git patch-id --stable` = `fbfd468045c81ba568c2b774e8282bba2a81feae`
- `verification/fuzz_cfg_parser.c.pre_fix` — H^1=01d256ab 的原文，git blob `e79225702bd896a2c3258f7daa522183a8b236fd`，与 diff index 旧侧 `e79225702bd8` 吻合
- `input/harness/oss-fuzz/fuzz_cfg_parser.c` — H 版，git blob `9b41537728078b0f71bbbae730105794de0430c6`，与 diff index 新侧 `9b4153772807` 吻合
- `input/source/` — M 树全量（1271 个 blob 的 sha1 在 `verification/source_blob_hashes_sha1.json`）
- `verification/run_{M1_old,M_old,M_new,MH_new}.log` — 四格实测输出
