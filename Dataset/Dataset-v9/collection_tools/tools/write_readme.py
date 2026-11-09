#!/usr/bin/env python3
"""Human-readable README.md for the dataset root, generated from dataset.json."""
import json

HD = '/home/claude/hd'
ds = json.load(open(f'{HD}/dataset/dataset.json'))

CELL_ZH = {'positive': '阳', 'negative': '阴', 'explicit': '显式', 'silent': '隐式',
           'introduced': '本次', 'preexisting': '非本次'}


def row(cell):
    parts = cell['cell'].split('/')
    return parts


lines = []
A = lines.append
A('# Harness Degradation 数据集 v3（真实 commit）')
A('')
A(f"生成时间 {ds['generated']} · schema {ds['schema']} · 目标 {ds['target_size']} 条 · 实际 **{ds['size']}** 条")
A('')
A('按《数据集收集方案（v3 草案）》采集、《数据量分布设计（含 mix）》配额、《目录组织要求》落盘。'
  '所有样本的 source / harness / change.diff 都来自真实开源项目的真实 commit；'
  '其中 `change_origin = real_commit_lib_hunks_only` 的样本来自耦合 commit 的库侧拆分（方案 §3.3 R2），单独计数。'
  '凑不满的格子保留空目录，并在 `dataset.json → gaps` 登记，**没有构造任何数据**。')
A('')
A('## 分布矩阵（实际 / 要求）')
A('')
types = ['api', 'configuration', 'input_format', 'state', 'lifecycle', 'mix']
cols = [('positive', 'explicit', 'introduced'), ('positive', 'explicit', 'preexisting'),
        ('positive', 'silent', 'introduced'), ('positive', 'silent', 'preexisting'),
        ('negative', 'explicit', None), ('negative', 'silent', None)]
hdr = ['类型'] + ['-'.join(CELL_ZH[x] for x in c if x) for c in cols] + ['合计']
A('| ' + ' | '.join(hdr) + ' |')
A('|' + '---|' * len(hdr))
cmap = {c['cell']: c for c in ds['cells']}
tot_c = [0] * len(cols)
for t in types:
    r = [t]; s = 0
    for i, c in enumerate(cols):
        key = '/'.join(x for x in (*c, t) if x)
        cc = cmap[key]
        r.append(f"{cc['have']}/{cc['need']}" + ('' if cc['have'] == cc['need'] else ' ⚠'))
        s += cc['have']; tot_c[i] += cc['have']
    r.append(str(s))
    A('| ' + ' | '.join(r) + ' |')
A('| **合计** | ' + ' | '.join(str(x) for x in tot_c) + f" | **{sum(tot_c)}** |")
A('')
d = ds['distribution']
A(f"- 阳 : 阴 = {d['by_label'].get('positive', 0)} : {d['by_label'].get('negative', 0)}；"
  f"显式 : 隐式 = {d['by_visibility'].get('explicit', 0)} : {d['by_visibility'].get('silent', 0)}；"
  f"阳性中 本次 : 非本次 = {d['by_introduced(positive)'].get('True', 0)} : {d['by_introduced(positive)'].get('False', 0)}")
A(f"- change_origin：{d['by_change_origin']}")
A(f"- gt_source：{d['by_gt_source']}（阳性中反事实修复占比 {ds['counterfactual_share_of_positives']}，方案上限 0.4）")
A(f"- 发现路线：{d['by_discovery_route']}")
A(f"- 项目（{len(d['by_project'])} 个）：{d['by_project']}")
A('')
A('## 缺口（不构造，如实登记）')
A('')
for g in ds['gaps']:
    A(f"- `{g['cell']}`：缺 {g['missing']} 条 — {g['reason']}")
A('')
A('## 样本一览')
A('')
A('| ID | 项目 | 格子 | mix 组成 | 来源 | ground truth | 变更 |')
A('|---|---|---|---|---|---|---|')
for s in sorted(ds['samples'], key=lambda x: x['id']):
    cell = s['path'].split('/')[1:-1]
    A(f"| {s['id']} | {s['project']} | {'/'.join(cell)} | {','.join(s['mix_components']) if s['mix_components'] else ''} "
      f"| {s['change_origin']} | {s['gt_source']} | [{s['M'][:10]}]({s['url']}) ({s['M_date']}) |")
A('')
A('## 每条样本的目录')
A('')
A('```')
A('<ID>_<project>_<M短哈希>/')
A('  input/            ← 评测时只给模型这一部分 + case.json')
A('    source/         变更之后的完整工作树（R2 样本：库已改、harness 为 M^1 版本）')
A('    harness/        harness 文件（in-tree 的按原路径；oss-fuzz/ 为按日期固定的 OSS-Fuzz 项目目录（若 in-tree harness 目录本身就叫 oss-fuzz/，则为 oss-fuzz-project/）；build/ 为自定义构建脚本）')
A('    change.diff     M^1 → M 的统一 diff（R2 样本只含库侧 hunk）')
A('  case.json         任务描述（不含标签）')
A('  label.json        标签 + 证据 + 中英理由 + verification（实验原始结果）')
A('  meta.json         上游 URL、M/M^1/H、构建所用 oss-fuzz 修订、diff 统计')
A('  NOTES.md          人类可读说明')
A('  verification/     experiments.json、source_blobs.json、counterfactual_fix.diff（若有）')
A('```')
A('')
A('## 判定实验（方案 §5，实测）')
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
A('`tools/verify.py <dataset 根目录>` 独立重做：目录名与 label.json 一致性、mix_components、case.json 不泄露标签、'
  'M^1/主线/祖先关系、harness 在 M^1 与 M 均存在且非空、change.diff 与 git diff 逐字节一致、源码 blob 哈希与 git tree 一致、'
  'commit/patch-id/事件唯一性、R-cap、阴性不落在 known_windows.csv 的已知退化窗口内、缺口已在 dataset.json 登记。'
  '复验需要对应上游仓库的本地克隆（路径见脚本顶部）。')
A('')
open(f'{HD}/dataset/README.md', 'w').write('\n'.join(lines) + '\n')
print('README written')
