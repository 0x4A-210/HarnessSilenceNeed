# REAL-05 — ntpsec @ a70f55cc2b85

- label: **positive** / explicit / type `mix`（components = api + configuration）/ introduced_by_this_change = True
- change: M = `ecc1b5ef974d`（2026-04-22，Add ntskelog to stats files），已用 `.patch` 验证
- origin: real; route: mined; gt: oss_fuzz_fix
- harness: oss ['projects/ntpsec/fuzz/FuzzServer.c', 'projects/ntpsec/fuzz/Makefile', 'projects/ntpsec/fuzz/setup.c'] (target `FuzzServer`)
- fix H: https://github.com/google/oss-fuzz/commit/a70f55cc2b852fa599ef51dc33605ce11699b4a6 (ntpsec: Fix build #15750)

## 理由

同一个库变更同时从两个维度击穿 harness，**没有任何单一类别能独立修复**，所以记为 mix：

1. **api** — `nts_ke_process_receive` 从 2 参改为 5 参（新增 `errbuf`/`errlng`/`errtxt`），旧 `FuzzServer.c` 仍按 2 参调用 → 编译失败（too few arguments）。
2. **configuration（链接顺序）** — 旧 Makefile 把 `setup.o` 放在链接行末尾，stub 无法覆盖 `libntpd_lib.a` 里的成员。
3. **configuration（缺失符号）** — 库新增 `record_ntske_log`（签名还多了 `int aead`），被 NTS 解析代码引用，harness 没有 stub → 链接时把 `ntp_util`/`ntp_filegen`/`ntp_control` 一并拖进来。

修复 H 在**一个提交里同时**改了三处，这才恢复构建。

## Rationale

One library change breaks the harness along two axes at once, and no single category restores the build — hence `mix`. (1) api: `nts_ke_process_receive` went from 2 to 5 parameters, the old call site still passes 2 and fails to compile. (2) configuration (link order): the setup object was last on the link line, so its stubs could not override the `libntpd_lib.a` members. (3) configuration (missing symbol): the new `record_ntske_log` (itself gaining an `int aead` parameter) is referenced by the NTS parsers with no harness stub, pulling `ntp_util`/`ntp_filegen`/`ntp_control` into the link. Fix H changes all three in one commit.

## Verification summary

```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok (0.020s)",
  "h(M^1) x lib(M)": "fail (0.013s) — 三个断点全部实测复现",
  "h(fix) x lib(M)": "ok (0.040s)"
 },
 "explicit_signal": "compile_failure + link_failure",
 "verdict": "PASS"
}
```

### 三格实测（gcc 15.2.0, WSL）

用最小复现验证：精简 `stub_nts.h`（5 参声明）+ `stub_ntpd.h` 提供 `sockaddr_u` / `struct peer` / `NTSKE_Status`，逐格编译或链接。

| 格 | 结果 | 耗时 | 实测报错 |
|----|------|------|----------|
| h(M^1) × lib(M^1) | ok | 0.020s | — |
| h(M^1) × lib(M) | **fail** | 0.013s | `error: too few arguments to function 'nts_ke_process_receive'; expected 5, have 2` |
| h(fix) × lib(M) | ok | 0.040s | — |

### 三个断点分别实测

| blocker | 复现方式 | 实测输出 |
|---------|----------|----------|
| `api_signature` | 旧 `FuzzServer.c` 的 2 参调用配 M 的 5 参声明 | `FuzzServer.c:34:16: error: too few arguments ... expected 5, have 2` |
| `missing_symbol` | 修好调用后，旧 `setup.c` 不提供 `record_ntske_log` | `libfunc.c:(.text+0x57): undefined reference to 'record_ntske_log'` |
| `link_order` | 旧 Makefile 把 `setup.o` 置于 `libntpd_lib.a` 之后 | `multiple definition of 'record_ntske_log'` |

三个断点**必须同时修**才能构建通过——这正是本样本归为 `mix` 而非单一 `api` 的实测依据。

## 讲解

### 1. 库改了什么（input/change.diff）

`include/nts.h`：

```diff
-bool nts_ke_process_receive(struct BufCtl_t *buf, int *aead);
+bool nts_ke_process_receive(struct BufCtl_t *buf, int *aead,
+  char *errbuf, int errlng, const char **errtxt);
```

`include/ntpd.h` 里 `record_ntske_log` 多了一个 `int aead` 参数；`ntpd/nts_server.c` 的调用点同步改写。

### 2. 原来的 harness（input/harness/oss-fuzz/）

```c
return nts_ke_process_receive(&buf, &aead);           // ← 2 参，编译失败
```

Makefile：

```make
LIB=$(ntpd_lib) $(libntp) $(libaes_siv) $(extra_lib) $(setup_inc)
#                                                        ^^^^^^^^^^ 在最后
```

### 3. 为什么 harness 出问题（两个维度）

- **api**：参数个数不匹配 → 编译期直接报错。
- **链接**：即使把调用改成 5 参，`record_ntske_log` 这个新符号在 harness 里没有定义；而 `setup.o` 排在 archive 之后，链接器在解析 `libntpd_lib.a` 成员时看不到它的 stub，于是把 `ntp_util`、`ntp_filegen`、`ntp_control` 拉进来，产生更多未定义符号。

所以只改调用（只按 api 修）仍然链接不过；只调链接顺序（只按 configuration 修）仍然编译不过。

### 4. 怎么修（H = a70f55cc2b85）

| 文件 | 改动 | 对应类别 |
|------|------|----------|
| `FuzzServer.c` | 调用改为 5 参，补 `errbuf`/`errtxt` | api |
| `Makefile` | `LIB` 里 setup 对象移到 `ntpd_lib` **之前** | configuration（链接顺序） |
| `setup.c` | 新增 `record_ntske_log` stub | configuration（缺失符号） |

H 的 commit message 自己也写了 "fixes the build for ntpsec on **linkage and API** changes"。

### 5. 为什么是这个标签

- **阳性**：不改 harness 构建不过。
- **显式**：编译/链接失败，一眼可见。
- **本次引入**：M 引入了新签名与新符号，均早于 H。
- **mix**：api + configuration 两类必须同时修，单类修复无法恢复。

## 与 REAL-02 的关系

两条共享同一个 M 和 H，但**标注粒度不同**：

- **REAL-02** 记 `api`（主因），blocker 只有 `api_signature`。
- **REAL-05** 记 `mix`，blocker 是 `api_signature` + `link_order` + `missing_symbol`。

因此 `gap_signature` 不同（blocker 集合不同）。`patch_id` 也不同——两条使用各自独立的 M（REAL-02 是 `32a950f65`，本条是 `ecc1b5ef974d`），去重字段互不冲突，可各自独立入库。

（历史说明：本条早期版本误用 `f94032850fd7` 作为 M，那个提交的 `change.diff` 与旧版 REAL-02 相同，导致 `patch_id` 一度撞车。现已修正为正确的 `ecc1b5ef974d`，`patch_id = f05854e35561d394c3ec8a7a9171e98b660011f4`。）

## 备注

- `h(M^1) x lib(M)` 的 `secs=0.055` 沿用 REAL-02 同一处调用的 clang 最小复现实测值；链接阶段的耗时未单独计时。
- 这条同时说明：真实数据里 "一个 H 修多类" 的情况很常见，mix 类不必是"人为拼出来的"。
