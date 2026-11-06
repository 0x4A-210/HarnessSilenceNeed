# Download inventory

记录日期：2026-09-09（Asia/Shanghai）。

## 已下载并参与复现

| material | local path / revision | status |
|---|---|---|
| Final paper PDF | `paper-arxiv-v2.pdf`, SHA-256 `245905a3214535d2397910b3041df19bc706ef36d4408bbdcaa0f4c70f7f1602` | complete |
| Final paper HTML | `paper-arxiv-v2.html`, SHA-256 `c357dd40574d99b2338ac5c53e87215cbb1e3c0998b33d91daed6743f236b897` | complete |
| Author artifact | `artifact/`, Git `73843108273b97f05a583bc5226fa8177d88eb04` | complete and pinned |
| OSS-Fuzz history | `sources/oss-fuzz/`, Git `6f96dc4ca0805f56c1405e7c1606e8b73099f8b7` at download time | complete for required history |
| Selected project histories | `sources/projects/{brotli,c-ares,h2o,jansson,leptonica,libplist,libspng,meshoptimizer,tidy-html5,wuffs}` | complete for required commits/default branches |
| Archived coverage | `data/raw/coverage/` | 675 HTML reports downloaded; SHA-256 per file in `download_manifest.csv` |

Coverage 下载共请求 735 个唯一的 project-day：675 个源站文件存在，60 个返回 HTTP 404。404 不视为下载失败；论文和 artifact 都将没有 coverage report 的日子记录为 missing，并在窗口运算时跳过。

探索阶段还 clone 了 `mbedtls`、`proj4`、`selinux`、`solidity`、`tpm2-tss`、`trafficserver`，但它们不在 `config/selected_projects.csv`，也不计入任何最终数字。

## 未下载的完整 Zenodo SQLite

Zenodo record `10.5281/zenodo.14000867` 的十个分卷总计 38.7 GB。当前运行环境访问其文件端点反复返回 504 Gateway Time-out 或连接超时；尝试产生的三个 92-byte HTML 错误响应已删除，没有冒充数据文件。

官方文件名、大小、MD5 和可重试 URL 在 `zenodo_file_manifest.csv`。这不影响 13 个已选事件的复算，因为所需原始 OSS-Fuzz coverage、作者人工归因 notes 和 Git 历史均已分别保存；但这意味着本目录**不是**论文 342 项目全量 SQLite 的本地镜像。

