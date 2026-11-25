# SN-01 — h3 @ 583de2fe5f6a

- label: **positive** / explicit / type `api` / introduced_by_this_change = true
- change: Add error return codes to gridDisk functions (#505) (2021-10-18)
- M: `583de2fe5f6a68cb0040a955d87f16f9b9478e15`
- M^1: `f2786a4fc9a809c3a4a31a898d7028d432dc6f2f`
- H: `d5cf2bbe991b485a3b3a870f90a596c2f028100e`
- H^1: `9aa85855b4748b5dfa028e4065f0c17791eb11b8`
- source: `input/source/` = 351 files，全部与 M 的上游 git blob 逐一比对一致（0 mismatch）；`change.diff` = M^1→M (20 files)

## 变更文件索引

- `src/apps/miscapps/generatePentagonDirectionFaces.c`
- `src/apps/testapps/testCompactCells.c`
- `src/apps/testapps/testDirectedEdge.c`
- `src/apps/testapps/testGridDisk.c`
- `src/apps/testapps/testGridDisksUnsafe.c`
- `src/apps/testapps/testGridDistanceExhaustive.c`
- `src/apps/testapps/testGridPathCellsExhaustive.c`
- `src/apps/testapps/testGridRingUnsafe.c`
- `src/apps/testapps/testH3Memory.c`
- `src/apps/testapps/testH3NeighborRotations.c`
- `src/apps/testapps/testH3SetToLinkedGeo.c`
- `src/apps/testapps/testH3ToLocalIjExhaustive.c`
- `src/apps/testapps/testVertexExhaustive.c`
- `src/h3lib/include/algos.h`
- `src/h3lib/include/h3api.h.in`
- `src/h3lib/lib/algos.c`
- `src/h3lib/lib/directedEdge.c`
- `src/h3lib/lib/vertex.c`
- `website/docs/api/regions.mdx`
- `website/docs/api/traversal.mdx`

## Harness 与证据

- harness: `input/harness/oss-fuzz/`（H^1 的 OSS-Fuzz 项目文件）
- fuzzer target: `h3_fuzzer`
- 修复 patch: `_evidence/SN-01_api_h3_583de2fe5f/fix.diff`
- 原始运行/构建日志: `_evidence/SN-01_api_h3_583de2fe5f/recheck_2026-11-25/`

## 理由

h3 的 M 提交把内部函数 h3NeighborRotations 的签名从 3 个参数改成 4 个参数（新增 `H3Index *out`）并改为返回 `H3Error`。旧 harness 没有包含 `algos.h`，按旧的 3 参数调用，编译时只产生隐式声明警告，运行时会向一个不存在的第 4 个参数所指向的地址写入，直接 SEGV。属于本次变更引入的显式 api 退化。

## Rationale

h3 M changes the internal h3NeighborRotations() signature from 3 parameters to 4 (adding H3Index *out) and makes it return H3Error. The old harness does not include algos.h and still calls it with 3 arguments; it compiles with an implicit-declaration warning but at runtime writes through a 4th argument that was never supplied, causing a SEGV. Explicit api degradation introduced by this change.

## Verification summary

| 组合 | 结果 | 说明 |
|---|---|---|
| h(M^1) x lib(M^1) | ok | 旧 harness 在 M^1 上 exit 0 |
| h(M^1) x lib(M) | crash | AddressSanitizer SEGV (WRITE) @ algos.c:457 |
| h(fix) x lib(M) | ok | H 修复版 exit 0 |

```json
{"verdict": "PASS", "M": "583de2fe5f6a68cb0040a955d87f16f9b9478e15", "H": "d5cf2bbe991b485a3b3a870f90a596c2f028100e"}
```

- [PASS] H patch exists and touches the harness — d5cf2bbe991b: projects/h3/h3_fuzzer.c (+4/-1)
- [PASS] H patch adds algos.h and the new H3Index *out argument
- [PASS] M diff exists and changes h3NeighborRotations
- [PASS] input/source matches upstream M blob-for-blob — 351 files, 0 mismatch
- [PASS] harness files fetched at H^1
- [PASS] old harness x lib(M^1): builds and runs — exit 0
- [PASS] old harness x lib(M): runtime crash — ASan SEGV
- [PASS] fixed harness x lib(M): builds and runs — exit 0

## 讲解

### 1. 库改了什么

`src/h3lib/include/algos.h` 中 `h3NeighborRotations` 由

```c
H3Index h3NeighborRotations(H3Index origin, Direction dir, int *rotations);
```

改成

```c
H3Error h3NeighborRotations(H3Index origin, Direction dir, int *rotations,
                            H3Index *out);
```

即新增第 4 个输出参数 `out`，返回值类型改为 `H3Error`。该函数是库内部函数，不在公开的 `h3api.h` 中，因此调用方需要额外 `#include "algos.h"` 才能拿到新原型。

### 2. 原来的 harness（`input/harness/oss-fuzz/h3_fuzzer.c`）

旧 harness 只包含了 `h3api.h` 和 `utility.h`，调用：

```c
int rotations = 0;
for (int i = 0; i < 7; i++) {
    h3NeighborRotations(h3, DIGITS[i], &rotations);
}
```

### 3. 为什么 harness 出问题了

旧调用少传了第 4 个 `H3Index *out`。由于没有 `algos.h` 原型，编译器只给出隐式声明警告；链接仍然成功。运行时函数按新 ABI 读取第 4 个参数（实际是未初始化的寄存器/栈槽），把结果写到那个垃圾地址，AddressSanitizer 报 `SEGV on WRITE`，栈顶就是 `h3NeighborRotations`（`algos.c:457`）。

### 4. 怎么修（`fix.diff`）

H 提交（d5cf2bbe991b）做了两件事：

```diff
+#include "algos.h"
...
-    h3NeighborRotations(h3, DIGITS[i], &rotations);
+    H3Index neighborRotationsOut;
+    h3NeighborRotations(h3, DIGITS[i], &rotations, &neighborRotationsOut);
```

### 5. 为什么是这个标签

- **阳性**：不改 harness 就无法继续 fuzz（运行即崩）。
- **显式**：崩溃在运行期直接暴露，不需要覆盖率分析。
- **本次引入**：变更前同一份旧 harness 在 M^1 上 exit 0；是 M 的签名变更打破的。
- **api**：公开/内部函数 `h3NeighborRotations` 的**签名**变了。
