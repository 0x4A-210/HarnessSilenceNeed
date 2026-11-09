#!/usr/bin/env python3
"""Pick a deterministic, stratified 20% sample for human review (plan §7: two reviewers,
independent labelling, disagreements go back to the experiments) and write
dataset/review/checklist.md + dataset/review/review_sheet.csv."""
import json, os, csv, hashlib, math

HD = '/home/claude/hd'
import sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else f'{HD}/Dataset-v6/dataset'
ds = json.load(open(f'{ROOT}/dataset.json'))
samples = ds['samples']
os.makedirs(f'{ROOT}/review', exist_ok=True)

# stratify by (label, visibility); inside a stratum order by sha1(id) -> deterministic
strata = {}
for s in samples:
    strata.setdefault((s['label'], s['need_visibility']), []).append(s)
target = math.ceil(0.2 * len(samples))
picked = []
for k in sorted(strata):
    lst = sorted(strata[k], key=lambda s: hashlib.sha1(s['dir'].encode()).hexdigest())
    n = max(1, round(len(lst) * target / len(samples)))
    picked += lst[:n]
rest = [s for k in sorted(strata, key=lambda k: -len(strata[k]))
        for s in sorted(strata[k], key=lambda s: hashlib.sha1(s['dir'].encode()).hexdigest()) if s not in picked]
while len(picked) < target and rest:
    picked.append(rest.pop(0))
picked = sorted(picked, key=lambda s: s['dir'])

L = []
A = L.append
A('# 人工复核清单（20% 分层抽样）')
A('')
A(f'从 {len(samples)} 条样本中按（阳/阴 × 显式/隐式）分层、以 sha1(ID) 排序确定性抽取 {len(picked)} 条。'
  '两名复核人**各自独立**只看 `input/` 与 `case.json` 先给出判断，再对照 `label.json` 与 `verification/`；'
  '不一致的样本回到实验数据裁决（方案 §7），结论填入 `review_sheet.csv`。')
A('')
A('## 每条样本要核对的项')
A('')
A('1. **变更真实性**：打开 `meta.json` 中的 M 链接，确认 `input/change.diff` 与上游 commit 一致（R2 样本只含库侧 hunk）。')
A('2. **harness 归属**：harness 文件在 M^1 时存在且非空；in-tree 样本的 `input/source` 中 harness 为 M^1 版本。')
A('3. **标签**：阳/阴、显式/隐式、本次/非本次、类型（mix 需核对 mix_components 每一项都必要）是否与理由及证据相符。')
A('4. **证据**：显式——编译矩阵或 ASan 回放的栈顶帧；隐式——缺口行在无修复的 3 个种子中覆盖为 0、有修复的 ≥2 个种子中 >0；'
  '阴性——编译/回放无新失败、改动行被覆盖。')
A('5. **修复 H / Δh**：H 是否真的只改 harness、是否对应同一缺口；Δh（counterfactual_fix.diff）是否 ≤30 行且只改 harness。')
A('6. **非本次**：确认 M^1 上同样退化（交叉回放或 window_start 处的编译结果）。')
A('')
A('## 抽中的样本')
A('')
A('| 目录 | 内部 ID | 项目 | 路径 | 来源 | ground truth |')
A('|---|---|---|---|---|---|')
for s in picked:
    A(f"| {s['dir']} | {s['internal_id']} | {s['project']} | `{s['path']}` | {s['change_origin']} | {s['gt_source']} |")
A('')
open(f'{ROOT}/review/checklist.md', 'w').write('\n'.join(L) + '\n')
with open(f'{ROOT}/review/review_sheet.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['id', 'path', 'reviewer', 'label_ok', 'visibility_ok', 'introduced_ok', 'type_ok',
                'evidence_ok', 'fix_ok', 'disagreement', 'resolution', 'notes'])
    for s in picked:
        for r in ('A', 'B'):
            w.writerow([s['dir'], s['path'], r] + [''] * 9)
print(f'{len(picked)} samples picked for review')
