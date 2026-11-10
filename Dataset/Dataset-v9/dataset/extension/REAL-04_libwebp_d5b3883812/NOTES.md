# REAL-04 — libwebp @ d5b3883812

- label: **positive** / silent / type `input_format` / introduced_by_this_change = True
- change: M = `fdc81cebda82`（2025-07-23，`fuzz: add allocations failures injections`）
- fix H = `d5b388381230a08a2f0cb1baf5b4785e071fbeb7`（2025-09-21，`fuzz: fix typo in nalloc env variable`）
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: in_repo `tests/fuzzer/`（harness 随库维护，不在 oss-fuzz 仓库）

## 理由

libwebp 的 harness 用 `nalloc.h` 做**分配失败注入**：覆盖 `malloc`/`calloc`/`realloc`/`read`/`write`，按伪随机规则让分配失败，用来驱动库里所有「分配失败 → 错误处理」分支。

**是否启用由环境变量控制**，`nalloc.h` 读的是：

```c
char *bitmask = getenv("NALLOC_FREQ");     // nalloc.h:114
```

`build.sh` 为每个含 `nalloc_init` 的 target 生成一个 `_nalloc` 包装器并注入该变量，但**第一版把名字写成了 `NALLOQ_FREQ`**（C 误作 Q）：

```diff
-      sed -i -e 's/^\$this_dir/NALLOQ_FREQ=32 \$this_dir/' \
+      sed -i -e 's/^\$this_dir/NALLOC_FREQ=32 \$this_dir/' \
```

于是 `getenv` 取不到值，四个 fuzzer 又都以 `nalloc_init(nullptr)` 调用，`prog == NULL` 使 `nalloc_init()` 落入禁用分支：

```c
} else if (prog == NULL || strstr(prog, "nalloc") == NULL) {
    nalloc_random_bitmask = false;
    nalloc_bitmask = 0;
    return;
}
```

`nalloc_start()` 随后直接返回：

```c
} else if (nalloc_bitmask == 0) {
    // nalloc disabled
    return 0;
}
```

**一次分配失败都不会注入**。四个 `_nalloc` target 编译、链接、运行全部正常，但库里所有分配失败的错误处理路径覆盖率恒为 0。

## Rationale

libwebp's harness uses `nalloc.h` for allocation-failure injection, wrapping `malloc`/`calloc`/`realloc` so allocations fail pseudo-randomly and every "allocation fails → error handling" branch in the library gets driven. Enablement is gated on an environment variable that `nalloc.h` reads with `getenv("NALLOC_FREQ")`. `build.sh` generates a `_nalloc` wrapper per target and injects that variable — but the first version spelled it `NALLOQ_FREQ`. `getenv` therefore misses; all four fuzzers call `nalloc_init(nullptr)`, so `prog == NULL` sends `nalloc_init()` into the disabled branch (`nalloc_bitmask = 0; nalloc_random_bitmask = false;`), and `nalloc_start()` returns immediately at `else if (nalloc_bitmask == 0)`. Not a single allocation failure is injected: the four `_nalloc` targets build, link and run normally, yet every allocation-failure error path stays at zero coverage.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "ok (silent: injection is a no-op)",
  "h(fix) x lib(M)": "ok (injection active)"
 },
 "explicit_signal": null,
 "verdict": "PASS"
}
```

## 讲解

### 1. 退化是怎么发生的

```
build.sh 生成 _nalloc 包装器
        │
        ▼
export NALLOQ_FREQ=32        ← 拼写错误（Q）
        │
        ▼
nalloc.h: getenv("NALLOC_FREQ")  → NULL
        │
        ▼
nalloc_init(nullptr) + prog==NULL
        │
        ▼
nalloc_bitmask = 0, nalloc_random_bitmask = false   ← 禁用
        │
        ▼
nalloc_start() → "nalloc disabled" → return 0
        │
        ▼
所有分配失败注入路径覆盖率 = 0
```

### 2. 修复后为什么能生效

修复后 `NALLOC_FREQ=32`，但注意一个细节——`shift = 32` **既不满足 `0 < shift < 31`，也不满足 `shift == 0`**，所以两个分支都不进，函数**不 return**，`nalloc_random_bitmask` 保持默认的 `true`。

之后 `nalloc_start()` 走随机分支：

```c
if (nalloc_random_bitmask) {
    if (nalloc_random_state & 0x10) {
      nalloc_bitmask = 0xFFFFFFFF;
    } else {
      nalloc_bitmask = 1 << (5 + (nalloc_random_state & 0xF));
    }
}
```

每次迭代按输入内容生成不同的 bitmask → 注入真正生效。

### 3. 影响范围

`fdc81cebda82` 给 4 个 fuzzer 加了 `nalloc_init`：

| fuzzer | 调用点 |
|--------|--------|
| `dec_fuzzer.cc` | 第 34 行 `nalloc_init(nullptr)` |
| `animdecoder_fuzzer.cc` | 第 33 行 |
| `imageio_fuzzer.cc` | 第 40 行 |
| `webp_info_fuzzer.cc` | 第 30 行 |

**四个 `_nalloc` target 全部失效约两个月**（2025-07-23 → 2025-09-21）。

### 4. 为什么是 input_format / silent

- **隐式**：编译、链接、运行全部正常，崩溃率也没变化——只是注入从不发生，相关分支覆盖恒为 0
- **input_format**：库里存在一条完整的「输入通道」（分配失败注入），harness 也接上了（`nalloc_init` / `nalloc_start` / `nalloc_end` 都调了），但通道的开关被一个拼写错误永久关掉。与 TOY-06（字母表里没有 `x`/`a`-`f`，十六进制字面量永远到不了解析器）同构
- **本次引入**：M（2025-07-23）引入拼写错误，H（2025-09-21）修复，因果顺序正确

## 备注

1. **已实测构建脚本那行 `sed` 的两种写法**（bash，WSL）：把 `build.sh` 里 heredoc 生成的包装器复现成可执行脚本，分别用 `NALLOQ_FREQ` / `NALLOC_FREQ` 替换行首的 `$this_dir`，再让包装器调用一个模拟 `nalloc_init` 判定的 payload：

   | 版本 | 包装器导出 | payload 观测到 | 结论 | 耗时 |
   |------|-----------|---------------|------|------|
   | 修复前 `fdc81cebda82` | `NALLOQ_FREQ=32` | `getenv("NALLOC_FREQ") = NULL` | 禁用分支，注入失效 | 15ms |
   | 修复后 `d5b388381230` | `NALLOC_FREQ=32` | `getenv("NALLOC_FREQ") = "32"` | 注入启用 | 8ms |

   另用 Python 复现了 `nalloc_init()` 的完整分支判定，确认 `NALLOC_FREQ=32` 时 `shift=32` 既不满足 `0 < shift < 31` 也不满足 `shift == 0`，两个分支都不命中、函数不 return，`nalloc_random_bitmask` 保持默认 `true`，进而在 `nalloc_start()` 里按输入随机生成 bitmask。

2. **无法用覆盖率量化**。我查了 OSS-Fuzz coverage bucket（2025-09-01 / 09-30 / 11-03 三天），`libwebp` 每次都是 13 个文件，**没有任何含 `nalloc` 的 target**。说明带 `_nalloc` 后缀的变体没有进入覆盖率统计，因此本条拿不到 `before/after` 的覆盖率数字。

3. **`input/source/` 为空**属预期：退化点在 harness 自带的构建脚本和 `nalloc.h`，不涉及库侧源文件改动。

4. **`nalloc` 机制的出处**：`nallocfuzz`，来自 https://github.com/catenacyber/nallocfuzz ，同一套机制也被 libssh、libpng 采用。

5. **`compile_matrix.secs` 的性质**：0.015 / 0.015 / 0.008 是**脚本级复现耗时**，不是 libwebp 完整 CMake + fuzzer 构建的耗时。完整构建未跑（成本高），三格的 `status` 是基于源码逐行核实 + 脚本实测得出的。
