# REAL-09 — binutils (oss-fuzz) @ 9de297cc736f

- label: **positive** / **explicit** / type `lifecycle` / `introduced_by_this_change = false`
- change: 无单一引入 commit——harness 自加入起就在每轮迭代 free 三个 CTF 全局指针但不置 NULL，跨迭代 double free 于 2021-01-20 由 issue 27734 暴露
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: oss ['projects/binutils/fuzz_readelf.c']（target `fuzz_readelf`）
- fix H: https://github.com/google/oss-fuzz/commit/9de297cc736fe5c2579e89d970f366d3703139dc（Issue 27734: binutils:fuzz_readelf: Abrt with empty stacktrace #4945）

## 理由

readelf（binutils）解析含 CTF section 的 ELF 时，会用 xstrdup 分配三个**库全局变量** `dump_ctf_symtab_name` / `dump_ctf_strtab_name` / `dump_ctf_parent_name`。harness `fuzz_readelf.c` 在每轮 `LLVMFuzzerTestOneInput()` 末尾无条件 `free()` 这三个指针，却**从不置 NULL**。libFuzzer 在同一进程里反复调用 harness：上一轮是 CTF 输入（指针被分配后 free 成悬垂）、本轮是非 CTF 输入（decoder 不重新分配）时，harness 对同一个已经 free 过的指针再次 `free()` → glibc 检测到 double free → 直接 abort，崩溃栈近乎为空（issue 27734 标题即 'Abrt with empty stacktrace'）。这是 harness 自身缺陷，lifecycle（free 后未置空）错误，显式崩。修复 H 只加三行置 NULL。

## Rationale (en)

binutils' readelf, when parsing an ELF carrying a CTF section, allocates three library globals (dump_ctf_symtab_name / dump_ctf_strtab_name / dump_ctf_parent_name) via xstrdup. The fuzz_readelf harness calls free() on all three at the end of every LLVMFuzzerTestOneInput() iteration but never nulls them. libFuzzer invokes the harness repeatedly in one process: after a CTF input (pointers allocated then freed, now dangling), the next non-CTF input does not re-allocate, and the harness frees the same already-freed pointer again — glibc's double-free detection aborts with an almost-empty stack (issue 27734 is titled 'Abrt with empty stacktrace'). A harness defect; lifecycle (free-without-null) error; explicit crash. Fix H adds only three nulling lines.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "crash (double free -> Abrt) on the second non-CTF iteration",
  "h(fix) x lib(M)": "ok (free(NULL) is a no-op)"
 },
 "explicit_signal": "double free -> abort(); 对应 issue 27734 'Abrt with empty stacktrace'",
 "verdict": "PASS"
}
```

### 实测（MinGW gcc 8.1.0，verification/probe_doublefree.c）

最小探针模拟：轮次 0 = CTF 输入（decoder 分配三个全局指针，harness free）；轮次 1 = 非 CTF 输入（decoder 不分配，harness 再次 free 同一指针）。

```
$ gcc -o probe_doublefree.exe probe_doublefree.c
$ ./probe_doublefree.exe old    # OLD：free 后不置 NULL
iteration 0 (CTF input): decoder allocates
iteration 1 (non-CTF input): decoder allocates nothing, harness frees again
exit=127                       # double free -> Abrt

$ ./probe_doublefree.exe fix    # FIX：free 后置 NULL
iteration 0 (CTF input): decoder allocates
iteration 1 (non-CTF input): decoder allocates nothing, harness frees again
survived (no crash)
exit=0
```

### 边界（budget_note）

- H 的 diff 与父提交 c3d69abf148c 的旧 harness 全文、修复版（旧版+三行 = NULL）均已落盘；
- 未跑完整 binutils + libFuzzer（需整套 binutils 构建与 ASan），崩溃复现是同一 double-free 模式的最小等价探针，非原始 fuzz_readelf 二进制实测。

## 判定链

```
h(M^1) × lib(M^1) = ok          // 单次迭代内环境基线（无 CTF 轮次不崩，但潜在悬垂）
h(M^1) × lib(M)   = crash       // 跨迭代：第二次 non-CTF free 同一个悬垂指针 → double free → Abrt
h(fix) × lib(M)   = ok          // free 后置 NULL，free(NULL) 为 no-op，不再崩
```


## 具体 diff（更改内容）

完整 diff 见 `input/change.diff`，核心改动如下：

```diff
diff --git a/projects/binutils/fuzz_readelf.c b/projects/binutils/fuzz_readelf.c
index beb3c64..f2a9c10 100644
--- a/projects/binutils/fuzz_readelf.c
+++ b/projects/binutils/fuzz_readelf.c
@@ -47,8 +47,11 @@ LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
 	unlink(filename);
 
 	free (dump_ctf_symtab_name);
+	dump_ctf_symtab_name = NULL;
 	free (dump_ctf_strtab_name);
+	dump_ctf_strtab_name = NULL;
 	free (dump_ctf_parent_name);
+	dump_ctf_parent_name = NULL;
 
 	return 0;
 }
```

## 坏 harness 存档（verification/fuzz_readelf.c.pre_fix）

`input/harness/oss-fuzz/` 现在是 H=9de297cc736f 的完整套件（其中 `fuzz_readelf.c` 已含三处置 NULL）。
出问题的那一版另存为：

- `verification/fuzz_readelf.c.pre_fix` ← oss-fuzz `c3d69abf148c966f4ea11b2f56856df016fc5b00`
  （H 的父提交，2021-01-20「[cryptofuzz] Use latest version of xxHash (#5003)」）的
  `projects/binutils/fuzz_readelf.c`，blob sha1 `df50601710c8fb822c017636dd640194611eb2df`。

该版三处 `free (...)` 后都没有置 `NULL`；与 `verification/fuzz_readelf.c.fixed` 相减，正好还原
`input/change.diff` 里那 3 行 patch。文件按 git 对象取原始字节写出，blob sha1 与上面一致。
