# REAL-23 — lcms @ d5394562c8

- label: **positive** / **silent** / type `mix`（api + lifecycle）/ `introduced_by_this_change = false`
- change: 无库侧变更（lcms 树固定为 `fb48851f`，2026-04-09）；OSS-Fuzz harness 自身两处契约违规
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: `oss` `['projects/lcms/cms_dict_fuzzer.c']`（target `cms_dict_fuzzer`）
- fix H: https://github.com/google/oss-fuzz/commit/d5394562c8ca171570e9c5c3357e7012d184fe86（2026-04-14，PR #15077）
- 带病引入: https://github.com/google/oss-fuzz/commit/3464f489f7b7178ab048cd9df35d62b93a2b7864（2023-11-06，PR #11165，`Fuzzing Coverage Expansion of Little-CMS`）

## 理由

一条提交同时点了两个问题：标题原文是 **“Fix context leak and type confusion in cms_dict_fuzzer”**。

### blocker 1（api）：`cmsMLUalloc` 收到的是字典句柄，不是上下文

```c
cmsContext context = cmsCreateContext(NULL, (void *)data);
cmsHANDLE  hDict   = cmsDictAlloc(context);
cmsMLU *mlu = cmsMLUalloc(hDict, 0);   // ← 第一个参数类型是 cmsContext
```

`cmsMLUalloc(cmsContext ContextID, cmsUInt32Number nItems)`，第一个参数要上下文，传进去的是 `cmsHANDLE`。
两者都是不透明 `void*`，编译期不会有任何警告——典型类型混淆。

为什么运行期看不出来：`src/cmsplugin.c:714` 的 `_cmsGetContext()` 在全局池 `_cmsContextPoolHead` 里按指针比对，
**找不到就当作 NULL、静默回退到 `&globalContext`**：

```c
for (ctx = _cmsContextPoolHead; ctx != NULL; ctx = ctx->Next) {
    if (id == ctx) return ctx;          // 命中才是新式上下文
}
return &globalContext;                   // 不命中：静默回退，无 assert、无 cmsSignalError
```

`hDict` 永远不在池里，所以每次 `_cmsGetContext(hDict)` 都返回全局上下文。MLU 照样建得出来、`cmsMLUsetWide`
照样成功、`cmsMLUfree` 照样成功——**行为与正确写法完全一致**。这一半只能从源码契约判定，没有运行期数值，已在
`label.evidence` 与 `verification.checks` 里写明。

### blocker 2（lifecycle）：`cmsCreateContext` 之后从不 `cmsDeleteContext`

四条返回路径（主路径 + hDict 空 + mlu 空 + wideString 空）全部漏掉。libFuzzer 同进程跨迭代复用，
于是上下文在全局池里线性累积。

**这个泄漏 LSan 抓不到**：`cmsCreateContext()` 把新上下文插到全局链表头（`src/cmsplugin.c:850` / `917`，
`_cmsContextPoolHead = ctx`），泄漏对象始终可以从全局根到达，属 reachable 而非 unreachable。
实测 `detect_leaks=1` 下两版都**没有** LeakSanitizer 报告——这个阴性结果如实写进了证据，没有粉饰。

所以改用跨迭代增长来量化（`verification/iter_scaling.txt`，同一固定输入，`-runs=N`）：

| N | old 最大常驻 | new 最大常驻 | old−new |
|---|---|---|---|
| 100 | 36608 KB | 36352 KB | 256 KB |
| 500 | 38528 KB | 37760 KB | 768 KB |
| 1000 | 40684 KB | 39168 KB | 1516 KB |
| 2000 | 44228 KB | 41728 KB | 2500 KB |
| 8000 | 59596 KB | 53888 KB | 5708 KB |

差值随迭代数线性涨，斜率 **(5708−2500)/6000 ≈ 0.535 KB/次**，与一个 `_cmsContext_struct`（含 chunks 数组与
内存插件副本）的量级吻合。new 版因为每轮 `cmsDeleteContext` 把池清回 1 个，不累积。

### 顺带的可观测后果：每次迭代越来越慢

关掉 libFuzzer 的泄漏扫描以隔离 harness 自身耗时（`ASAN_OPTIONS=detect_leaks=0`，2 次取最小，
`verification/lean_timing.txt`）：

| N | old min_ms | old ms/iter | new min_ms | new ms/iter |
|---|---|---|---|---|
| 2000 | 206 | 0.1030 | 51 | 0.0255 |
| 20000 | 15967 | 0.7984 | 216 | 0.0108 |

old 的每次迭代成本从 0.10 ms 涨到 0.80 ms（池越长约慢），new 持平在 0.01–0.03 ms。20000 次迭代差 **74 倍**。
这条曲线我**不**归因于某一个具体机制（池扫描只是最可能的解释，没有单独证明），只作为「泄漏有可测量的运行期代价」的证据。

`introduced_by_this_change = false`：`cms_dict_fuzzer.c` 自 2023-11-06 的 `3464f489f7` 起就是这样，带病约 2 年 5 个月。

## Rationale (en)

One commit names both problems in its subject: **"Fix context leak and type confusion in cms_dict_fuzzer"**.
`cmsMLUalloc(cmsContext, nItems)` is handed the `cmsHANDLE` from `cmsDictAlloc` instead of the `cmsContext`.
Both are opaque `void*`, so nothing warns. At runtime the misuse is invisible because `_cmsGetContext()`
(`src/cmsplugin.c:714`) compares the pointer against the global context pool and, on a miss, silently returns
`&globalContext` — no assert, no `cmsSignalError`. `hDict` is never in the pool, so every lookup falls back and the
MLU behaves exactly as if the correct context had been passed; this half is source-contract only and has no runtime
number. Separately, `cmsCreateContext` is called every iteration and `cmsDeleteContext` is never called on any of the
four return paths, so contexts accumulate in the global pool. LSan cannot see this: the leaked objects stay reachable
from `_cmsContextPoolHead` (`cmsplugin.c:850`/`917`), and indeed neither harness produced a LeakSanitizer report with
`detect_leaks=1` — a negative result recorded as-is. Quantification therefore uses cross-iteration growth: the old−new
peak-RSS delta rises from 2500 KB at 2000 iterations to 5708 KB at 8000, a slope of about 0.535 KB per input. With
leak checking disabled to isolate harness cost, 20000 iterations take 15.97 s with the old harness and 0.22 s with the
new one, with per-iteration cost rising 0.10→0.80 ms for the old harness and staying flat for the new one.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok (旧 harness 编译链接运行均正常，exit 0)",
  "h(M^1) x lib(M)":   "ok (silent: 每轮泄漏一个 cmsContext，RSS 斜率 0.535KB/次；cmsMLUalloc 收到 cmsHANDLE)",
  "h(fix) x lib(M)":   "ok (cmsMLUalloc(context,0) + cmsDeleteContext；RSS 不再累积，每次迭代耗时恒定)"
 },
 "silent_signal": "跨迭代 RSS 斜率 0.535KB/次；detect_leaks=0 下 20000 次迭代 15.97s vs 0.22s",
 "verdict": "PASS"
}
```

## 复现步骤

```bash
# 1. lcms @fb48851f
cmake -S . -B build -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=clang -DCMAKE_C_FLAGS="-g -O1 -fsanitize=fuzzer-no-link,address -fno-omit-frame-pointer" \
  -DLCMS2_BUILD_SHARED=OFF
cmake --build build -j14

# 2. 两版 harness（pre_fix 无扩展名，必须 -x c ... -x none）
LIB=build/liblcms2.a; INC=include
clang -g -O1 -fsanitize=fuzzer,address -I "$INC" -x c \
  <case>/verification/cms_dict_fuzzer.c.pre_fix -x none "$LIB" -lm -o fz_lcms_old
clang -g -O1 -fsanitize=fuzzer,address -I "$INC" \
  <case>/input/harness/oss-fuzz/cms_dict_fuzzer.c "$LIB" -lm -o fz_lcms_new

# 3. 泄漏不可用 LSan 判（两版都无报告），改用迭代标度
for N in 2000 8000; do
  ASAN_OPTIONS=detect_leaks=0 /usr/bin/time -f "%M KB" ./fz_lcms_old -runs=$N -max_len=64 corpus_old/
  ASAN_OPTIONS=detect_leaks=0 /usr/bin/time -f "%M KB" ./fz_lcms_new -runs=$N -max_len=64 corpus_new/
done
```

## 取证细节

- `verification/cms_dict_fuzzer.c.pre_fix` 逐字节算 git blob sha1 = `635b5150adcb4968543a4a93be03db987352b0c3`，
  与 `input/change.diff` 里 `index 635b5150adcb..bf95c2dbe2ad` 的旧侧一致。
- `input/source/` 339 个文件全部记录在 `verification/source_blob_hashes_sha1.json`。
- `input/harness/oss-fuzz/` 23 个文件，是 H 时刻 `projects/lcms/` 的完整套件（17 个 target）。

## 未做 / 局限

1. **类型混淆没有运行期证据，也不可能有**：lcms 对未知 context 静默回退是设计行为，两版在任何输入上行为一致。
   这一半的证据强度只到「源码契约 + 函数原型」。
2. LSan 对该泄漏无效（reachable），所以不存在「LSan 报告 1704B」那种更硬的数字；本条用的是 RSS 斜率。
3. 每次迭代越来越慢的机制我**没有**单独证明是池扫描导致，只报了现象与数字。
4. 没取 OSS-Fuzz 线上 coverage bucket；本条缺陷本就不影响覆盖率（两版边覆盖差异全部来自 harness 新增的判空分支）。
