# Selection audit for the 10-project subset

作者 artifact 的 classification lists 在这 10 个项目中共有 18 个 coverage-drop case。下表说明 13 个最终 commit mapping 与 5 个排除项，避免把“没有收录”误读成 negative。

## Included：13

| artifact category | cases | mapping rule |
|---|---:|---|
| Project Code Added - Coverage Drops | 9 | notes 明示一个 commit；`wuffs-2020-02-06` 明示 two-part change，以 part 2 完成 commit 为 anchor |
| Code Churn - Coverage Decrease | 4 | notes 明示一个 commit |

13 个 included case 均重新下载前后 coverage，并通过 artifact 的 day/center/max 三个 `< -5pp` 条件。

## Excluded：5

| case | artifact category | reason |
|---|---|---|
| `c-ares-2023-10-26` | Project Code Added | notes 将原因写为“likely”来自 3 个项目 commit，并同时排除 2 个 formatting harness commit；无法唯一映射 |
| `libspng-2021-07-29` | Project Code Added | notes 同列 4 个相邻 commit；无法唯一映射 |
| `tidy-html5-2022-08-15` | Harness Build Failure | 不属于本阶段选定的 project-code/code-churn cause stratum |
| `libspng-2019-09-06` | Library Code Vendored | drop 来自 vendored zlib 进入 coverage，而非明确的主项目 code-evolution commit |
| `c-ares-2021-10-13` | gcov Error | coverage 计数错误，不是 harness/project degradation commit |

排除规则没有把这些 case 标作 negative；它们只是不进入本阶段“明确、唯一、主项目 Git commit 可归因”的 positive CSV。

## Coverage of the selected stratum

在这 10 个项目中，artifact 的 `Project Code Added` / `Code Churn` 两类一共有 15 个 case：13 个可唯一映射并纳入，2 个多 commit 歧义 case 被排除。也就是说，对预先声明的 cause stratum，本选择审计是完整枚举，而不是只挑看起来方便的事件。

