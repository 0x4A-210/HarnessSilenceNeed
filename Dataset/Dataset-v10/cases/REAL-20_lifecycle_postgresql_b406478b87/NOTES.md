# REAL-20 — lifecycle / explicit / postgresql

> 编号变更（2026-11-23）：本样本最初编为 `REAL-21`；同日先与 tidy-html5 的 `REAL-13` 互换，
> 随后随 `REAL-07`~`REAL-18` 整体后移 7 位，最终定为 `REAL-20`。样本内容与实测数据未变。


## 一句话

M 把后端启动序列拆开了：`BaseInit()` **不再**顺带调用 `CreateSharedMemoryAndSemaphores()`，
并且要求 `InitProcess()` 必须在 `BaseInit()` 之前。旧 harness 还是 `BaseInit(); InitProcess();`——
函数签名一个没变、编译链接全过，但跑起来 `InitProcess()` 里 `ProcGlobal` 还是 NULL，
直接 `PANIC: proc header uninitialized`，进程 SIGABRT。

## 判定链

| 环节 | 结果 |
|---|---|
| `h(M^1=0de13bbc47d1) × lib(M^1)` | **rc=0**，cov 339，3 次执行 |
| `h(M^1) × lib(M=b406478b87e2)` | **PANIC: proc header uninitialized** → SIGABRT，**rc=134** |
| `h(H=0ec1cb2549) × lib(M)` | **rc=0**，cov 339 |

日志原样（`verification/run_old_on_M.log` 全文就一行）：

```
2026-11-23 02:41:04.457 CST [463] PANIC:  proc header uninitialized
```

对应源码 `src/backend/storage/lmgr/proc.c:311`：

```c
	/* ProcGlobal should be set up already (if we are a backend, we inherit
	 * this by fork() or EXEC_BACKEND mechanism from the postmaster). */
	if (ProcGlobal == NULL)
		elog(PANIC, "proc header uninitialized");
```

`ProcGlobal` 是 `CreateSharedMemoryAndSemaphores()` 这条链建起来的。M 之前 `BaseInit()` 里顺手调了它，
所以 harness 只要 `BaseInit(); InitProcess();` 就能跑；M 之后这一步没了，`ProcGlobal` 保持 NULL。

## M 说了什么

`b406478b87e2`（2021-08-05）标题：`process startup: Always call Init[Auxiliary]Process() before BaseInit().`
提交正文：

> For EXEC_BACKEND InitProcess()/InitAuxiliaryProcess() needs to have been called well before we call
> BaseInit(), as SubPostmasterMain() needs LWLocks to work. ... To be able to change the order,
> **BaseInit() cannot trigger CreateSharedMemoryAndSemaphores() anymore** - obviously that needs to have
> happened before we can call InitProcess()

改动覆盖 8 个文件（postinit.c、postgres.c、bufmgr.c、bootstrap.c、autovacuum.c、auxprocess.c、bgworker.c、bufmgr.h）。

H = `0ec1cb2549`（2021-09-20）的 diff 只有三行，`input/change.diff` 全文 582 字节：

```diff
-  BaseInit();
+  CreateSharedMemoryAndSemaphores();
   InitProcess();
+  BaseInit();
```

## 为什么这条算 explicit

编译期完全无感——`BaseInit`、`InitProcess`、`CreateSharedMemoryAndSemaphores` 三个符号都在，
参数也没变，任何编译器都不会吭声。只有真跑起来、走到 `InitProcess()` 才炸，而且炸得很硬（PANIC + abort）。
所以它和 REAL-25（参数类型变了、有 `-Wincompatible-pointer-types` 警告可循）形成对照：
**同是 explicit，一个编译器能提示，一个只能靠运行**。

## 复现过程中踩的坑（都会影响结论，记下来）

1. **initdb 跑不通**。带 `-DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION` 时，`add_fuzzers.diff` 把
   `ReadCommand()` 改成永远走 `SocketBackend()`，而 initdb 的 post-bootstrap 是单用户模式（走 stdin），
   于是 `performing post-bootstrap initialization ... child process exited with exit code 1`。
   OSS-Fuzz 的解法是另建一个**不带 FUZZING 宏**的构建目录 `bld` 来跑 `make createdb`，本项目照做。
2. **`dbfuzz` 库**。harness 里 `InitPostgres("dbfuzz", ...)`，光有 initdb 的库不够；
   `make createdb`（dbfuzz.c）实际是 initdb → 起 postmaster → `CREATE DATABASE "dbfuzz" TEMPLATE=template0` → 停库。
   我们照这个流程把 data/ 造出来，否则报 `FATAL: database "dbfuzz" does not exist`。
3. **data 目录权限**。PG 要求 `0700`/`0750`。drvfs（/mnt/d）上目录恒为 0777 且 chmod 无效，
   必须把运行目录放到 ext4（家目录）上再 `chmod -R go-rwx`，否则报
   `FATAL: data directory "/tmp/query_db/data" has invalid permissions`。
4. **语料路径必须绝对**。harness 里 `ChangeToDataDir()` 会 chdir 到数据目录，
   相对路径 `corpus` 会解析到数据目录下，libFuzzer 报 `required directory "corpus" does not exist`。
5. **静默 abort**。`EmitErrorReport()` 被 `#ifndef FUZZING_BUILD_MODE` 屏蔽，PANIC 文本默认不输出，
   进程直接 abort、日志空白。为了拿到那行 PANIC，M 树上的 `elog.c` 用**不带该宏**的方式单独重编过一次
   （只去掉日志抑制，不改任何控制流）；`run_old_on_M.log` 就是这次构建的产物。
6. **`tmp_install/` 必须存在**。harness 里 `av[0] = "tmp_install/usr/local/pgsql/bin/postgres"`，
   `InitStandaloneProcess()` 要按这个相对路径定位自身可执行文件，缺了就报
   `FATAL: could not locate my own executable path`。OSS-Fuzz 是把 `tmp_install` 一起 `cp -r $OUT/` 的。

## 文件清单

- `input/change.diff` — H 的 oss-fuzz 提交（582 字节，三行改动）
- `input/harness/oss-fuzz/` — H 时刻 `projects/postgresql/` 全套（Dockerfile、build.sh、project.yaml、add_fuzzers.diff、fuzzer/ 6 文件）
- `input/source/` — M 树全量 6012 文件
- `verification/fuzzer_initialize.c.pre_fix` — H^1 的旧 harness，git blob `0ab9d7dcdddc…`（= diff index 旧侧）
- `verification/run_{new_on_M,old_on_M1,old_on_M}.log` — 三格运行日志
- `verification/measured.json` — 实测结果汇总（编译矩阵、信号、检查项、构建说明）
- `verification/source_blob_hashes_sha1.json` — M 树 6012 个文件的 git blob sha1
