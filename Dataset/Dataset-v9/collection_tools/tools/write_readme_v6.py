#!/usr/bin/env python3
"""README.md for the dataset root, generated from dataset.json (v6)."""
import json, sys

HD = '/home/claude/hd'
ROOT = sys.argv[1] if len(sys.argv) > 1 else f'{HD}/Dataset-v6/dataset'
ds = json.load(open(f'{ROOT}/dataset.json'))
ZH = {'positive': '阳', 'negative': '阴', 'explicit': '显式', 'silent': '隐式', 'introduced': '本次', 'preexisting': '非本次'}
TYPES = ['api', 'configuration', 'input_format', 'state', 'lifecycle', 'mix']

L = []
A = L.append
A('# Harness Degradation 数据集 v6（真实 commit）')
A('')
A(f"生成时间 {ds['generated']} · schema {ds['schema']} · 目标 {ds['target_size']} 条 · 实际 **{ds['size']}** 条")
A('')
A('本文件与 `dataset.json`、`known_windows.csv`、`canonical_map.csv`、`review/` 均由 `cases/` 下的实际样本目录重新生成。'
  '样本按《数据集收集方案（v3 草案）》采集、按《数据量分布设计（含 mix）》配额、按《目录组织要求》落盘；'
  '类型定义以《数据量分布设计》为准（运行期 flags/options 归 configuration）。'
  '所有样本的 source / harness / change.diff 都来自真实开源项目的真实 commit；'
  '`change_origin = real_commit_lib_hunks_only` 的样本来自耦合 commit 的库侧拆分（方案 §3.3 R2），单独计数。'
  '凑不满的格子保留空目录并在 `dataset.json → gaps` 登记，**没有构造任何数据**。')
A('')
A('## 分布矩阵（实际 / 要求）')
A('')
cols = [('positive', 'explicit', 'introduced'), ('positive', 'explicit', 'preexisting'),
        ('positive', 'silent', 'introduced'), ('positive', 'silent', 'preexisting'),
        ('negative', 'explicit', None), ('negative', 'silent', None)]
A('| 类型 | ' + ' | '.join('-'.join(ZH[x] for x in c if x) for c in cols) + ' | 合计（要求 8） |')
A('|' + '---|' * (len(cols) + 2))
cmap = {c['cell']: c for c in ds['cells']}
tot = [0] * len(cols)
for t in TYPES:
    r = [t]; s = 0
    for i, c in enumerate(cols):
        cc = cmap['/'.join(x for x in (*c, t) if x)]
        mark = '' if cc['have'] == cc['need'] else (' ⚠缺' if cc['have'] < cc['need'] else ' ↑多')
        r.append(f"{cc['have']}/{cc['need']}{mark}")
        s += cc['have']; tot[i] += cc['have']
    r.append(str(s))
    A('| ' + ' | '.join(r) + ' |')
A('| **合计** | ' + ' | '.join(f'{x}/{6 if i < 4 else 12}' for i, x in enumerate(tot)) + f" | **{sum(tot)}/48** |")
A('')
d = ds['distribution']
A(f"- 阳 : 阴 = {d['by_label'].get('positive', 0)} : {d['by_label'].get('negative', 0)}（要求 24 : 24）；"
  f"显式 : 隐式 = {d['by_visibility'].get('explicit', 0)} : {d['by_visibility'].get('silent', 0)}（要求 24 : 24）；"
  f"阳性中 本次 : 非本次 = {d['by_introduced(positive)'].get('True', 0)} : {d['by_introduced(positive)'].get('False', 0)}（要求 12 : 12）")
A(f"- 每类型条数：{d['by_type']}（要求各 8）")
A(f"- change_origin：{d['by_change_origin']}")
A(f"- gt_source：{d['by_gt_source']}（阳性中反事实修复占比 {ds['counterfactual_share_of_positives']}，方案上限 0.4）")
A(f"- 发现路线：{d['by_discovery_route']}")
A(f"- 样本来源：{d['by_origin_dataset']}")
A(f"- 项目（按规范仓库计 {len(d['by_canonical_repo'])} 个）：{d['by_project']}")
A('')
A('## 缺口（不构造，如实登记）')
A('')
if not ds['gaps']:
    A('无。')
for g in ds['gaps']:
    A(f"- `{g['cell']}`：缺 {g['missing']} 条 — {g['reason']}")
A('')
if ds['overfull_cells']:
    A('## 超出配额的格子')
    A('')
    for o in ds['overfull_cells']:
        A(f"- `{o['cell']}`：多 {o['extra']} 条（{', '.join(o['samples'])}）— {o['note']}")
    A('')
if ds['known_issues']:
    A('## 已知问题')
    A('')
    for k in ds['known_issues']:
        A(f"- **{k['sample']}**（{k['rule']}）：{k['detail']}")
    A('')
old_ids = '（编号为连续化之前的旧编号）' if ds.get('id_renumbering') else ''
if ds.get('id_renumbering'):
    rn = ds['id_renumbering']
    A(f"## 编号连续化（{rn['date']}）")
    A('')
    A(rn['note_zh'])
    A('')
    A(f"| 原编号（{rn['from_dataset']}） | 新编号 | 目录 |")
    A('|---|---|---|')
    for m in rn['map']:
        A(f"| {m['from'].split('_')[0]} | {m['to'].split('_')[0]} | {m['to']} |")
    A('')
if ds.get('removed_samples'):
    A('## 本版移除的样本' + old_ids)
    A('')
    for r in ds['removed_samples']:
        A(f"- `{r['dir']}`（原 `{r['cell']}`）：{r['reason']}；由 `{r['replaced_by']}` 替补。")
    A('')
if ds.get('renamed_samples'):
    A(('## 早先重新编号的样本' if old_ids else '## 本版重新编号的样本') + old_ids)
    A('')
    for r in ds['renamed_samples']:
        A(f"- `{r['from']}` → `{r['to']}`（原内部编号 {r['internal_id_before']}）：{r['reason']}")
    A('')
if ds.get('imported_samples'):
    A('## 导入样本')
    A('')
    A(ds['imported_samples'])
    A('')
A('## 样本一览')
A('')
A('| 目录 | 内部 ID | 项目 | 格子 | mix 组成 | 来源 | ground truth | 变更 |')
A('|---|---|---|---|---|---|---|---|')
for s in ds['samples']:
    cell = '/'.join(s['path'].split('/')[1:-1])
    A(f"| {s['dir']} | {s['internal_id']} | {s['project']} | {cell} | {','.join(s['mix_components'] or [])} "
      f"| {s['change_origin']} | {s['gt_source']} | [{s['M'][:10]}]({s['url']}) ({s['M_date']}) |")
A('')
A('## 每条样本的目录')
A('')
A('```')
A('<ID>_<project>_<M短哈希>/')
A('  input/            ← 评测时只给模型这一部分 + case.json')
A('    source/         变更之后的完整工作树（R2 样本：库已改、harness 为 M^1 版本）')
A('    harness/        harness 文件（in-tree 的按原路径；oss-fuzz/ 为按日期固定的 OSS-Fuzz 项目目录，'
  '若 in-tree harness 目录本身就叫 oss-fuzz/ 则为 oss-fuzz-project/；build/ 为自定义构建脚本）')
A('    change.diff     M^1 → M 的 diff（v3 样本为 git diff；v5 导入样本为 git show --format=fuller 原文；R2 样本只含库侧 hunk）')
A('  case.json         任务描述（不含标签）')
A('  label.json        标签 + 证据 + 中英理由 + verification')
A('  meta.json         上游 URL、M/M^1/H、构建所用 oss-fuzz 修订、diff 统计')
A('  NOTES.md          人类可读说明')
A('  verification/     v3 样本：experiments.json、source_blobs.json、counterfactual_fix.diff（若有）；v5 导入样本：构建/运行日志')
A('```')
A('')
A('## 判定实验（方案 §5）')
A('')
for k, v in ds['conventions'].items():
    A(f'- **{k}**：{v}')
A('')
A('## 与方案的偏差')
A('')
for x in ds['deviations_from_plan']:
    A(f'- {x}')
A('')
A(f"工具链：{ds['toolchain']}")
A('')
A('## 复验')
A('')
A('`collection_tools/tools/verify_v6.py <dataset 根目录>`：目录名与 label.json 一致性、mix_components、case.json 不泄露标签、'
  'M^1/主线/祖先关系、harness 在 M^1 与 M 均存在、change.diff 与 git 一致、源码 blob 哈希（v3 样本）、'
  'commit/patch-id/事件唯一性、R-cap（按规范仓库）、阴性不落在 known_windows.csv 的已知退化窗口内、缺口与超额已在 dataset.json 登记。'
  '复验需要对应上游仓库的本地克隆。')
A('')
open(f'{ROOT}/README.md', 'w').write('\n'.join(L) + '\n')
print('README written')
