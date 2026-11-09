#!/usr/bin/env python3
"""Regenerate the descriptive files of a dataset root from what is actually under cases/:
dataset.json, known_windows.csv, canonical_map.csv (README.md and review/ are written by
write_readme_v6.py / review_checklist_v6.py).  Works for both native v3 samples and samples
imported from MiniDataset-v5 (different label/meta layout).

usage: build_manifest_v6.py [DATASET_ROOT]"""
import json, os, csv, sys, datetime, re
from importlib.machinery import SourceFileLoader

HD = '/home/claude/hd'
ROOT = sys.argv[1] if len(sys.argv) > 1 else f'{HD}/Dataset-v6/dataset'
bm = SourceFileLoader('bm', f'{HD}/tools/build_manifest.py').load_module()
TYPES = ['api', 'configuration', 'input_format', 'state', 'lifecycle', 'mix']
EXTRA = json.load(open(f'{HD}/tools/manifest_v6_extra.json'))


def cells_spec():
    for lab in ('positive', 'negative'):
        for vis in ('explicit', 'silent'):
            for intro in (('introduced', 'preexisting') if lab == 'positive' else (None,)):
                for t in TYPES:
                    yield '/'.join(x for x in (lab, vis, intro, t) if x), (1 if lab == 'positive' else 2)


def main():
    cells, gaps, overs, samples = [], [], [], []
    for path, need in cells_spec():
        d = f'{ROOT}/cases/{path}'
        os.makedirs(d, exist_ok=True)
        items = sorted(x for x in os.listdir(d) if os.path.isdir(f'{d}/{x}') and os.path.exists(f'{d}/{x}/label.json'))
        cells.append({'cell': path, 'need': need, 'have': len(items), 'samples': items})
        if len(items) < need:
            gaps.append({'cell': path, 'missing': need - len(items),
                         'reason': EXTRA['gap_reasons'].get(path, bm.GAP_REASONS.get(path, 'no candidate passed the strict checks within the compute budget'))})
        if len(items) > need:
            overs.append({'cell': path, 'extra': len(items) - need, 'samples': items,
                          'note': EXTRA['over_notes'].get(path, '')})
        for it in items:
            sd = f'{d}/{it}'
            L = json.load(open(f'{sd}/label.json')); Mt = json.load(open(f'{sd}/meta.json'))
            prov = (Mt.get('provenance') or {}).get('dataset') or 'HarnessDegradation-v3'
            samples.append({
                'dir_id': it.split('_')[0], 'internal_id': L['id'], 'dir': it,
                'path': f'cases/{path}/{it}', 'project': Mt['project'],
                'canonical_repo': L.get('canonical_repo') or Mt.get('upstream'),
                'M': Mt['M'], 'M_date': (Mt.get('M_date') or '')[:10],
                'label': L['label'], 'need_visibility': L['need_visibility'],
                'introduced_by_this_change': L['introduced_by_this_change'],
                'degradation_type': L['degradation_type'],
                'mix_components': L.get('mix_components') if L['degradation_type'] == 'mix' else None,
                'change_origin': L['change_origin'], 'gt_source': L['gt_source'],
                'discovery_route': L['discovery_route'], 'url': L['urls']['M'],
                'origin_dataset': prov,
                'harness': (Mt.get('harness') or {}).get('files', [])[:1],
            })

    def cnt(key, lst=None):
        out = {}
        for s in (lst if lst is not None else samples):
            out[str(s[key])] = out.get(str(s[key]), 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))
    pos = [s for s in samples if s['label'] == 'positive']
    cf = sum(1 for s in pos if s['gt_source'] == 'counterfactual_fix')
    # identifier collisions (directory prefix reused, or internal id differs from directory prefix)
    by_dir = {}
    for s in samples:
        by_dir.setdefault(s['dir_id'], []).append(s['dir'])
    collisions = [{'dir_id': k, 'dirs': v} for k, v in sorted(by_dir.items()) if len(v) > 1]
    id_mismatch = [{'dir': s['dir'], 'internal_id': s['internal_id']} for s in samples if s['internal_id'] != s['dir_id']]
    # project counts by canonical repo (expat == libexpat)
    canon = {}
    for s in samples:
        canon.setdefault(s['canonical_repo'], []).append(s['dir'])
    quad = {}
    for s in samples:
        q = f"{s['label']}/{s['need_visibility']}"
        quad.setdefault(q, {}).setdefault(s['canonical_repo'], []).append(s['dir'])
    rcap = [{'quadrant': q, 'canonical_repo': r, 'samples': v} for q, m in quad.items() for r, v in m.items() if len(v) > 1]

    def tbl(filter_fn):
        return sum(1 for s in samples if filter_fn(s))
    target = {'by_label': {'positive': 24, 'negative': 24}, 'by_visibility': {'explicit': 24, 'silent': 24},
              'by_introduced(positive)': {'True': 12, 'False': 12}, 'by_type': {t: 8 for t in TYPES}}
    ds = {
        'name': 'Harness Degradation dataset v6 (real commits)',
        'schema': '3.0',
        'generated': datetime.datetime.now().isoformat(timespec='seconds'),
        'generated_from': 'contents of cases/ (this file, README.md, known_windows.csv, canonical_map.csv and review/ are regenerated from the sample directories)',
        'target_size': 48, 'size': len(samples),
        'layout': 'dataset-directory-layout.md: positive/<visibility>/<introduced|preexisting>/<type>/, negative/<visibility>/<type>/; positive cells hold 1 sample, negative cells 2',
        'target_distribution': target,
        'distribution': {'by_label': cnt('label'), 'by_visibility': cnt('need_visibility'),
                         'by_introduced(positive)': cnt('introduced_by_this_change', pos),
                         'by_type': {t: tbl(lambda s, t=t: s['degradation_type'] == t) for t in TYPES},
                         'by_change_origin': cnt('change_origin'), 'by_gt_source': cnt('gt_source'),
                         'by_discovery_route': cnt('discovery_route'), 'by_origin_dataset': cnt('origin_dataset'),
                         'by_project': cnt('project'),
                         'by_canonical_repo': {k: len(v) for k, v in sorted(canon.items(), key=lambda kv: -len(kv[1]))}},
        'counterfactual_share_of_positives': round(cf / len(pos), 3) if pos else None,
        'cells': cells, 'gaps': gaps, 'overfull_cells': overs,
        'identifier_collisions': collisions, 'internal_id_differs_from_dir': id_mismatch,
        'rcap_same_repo_in_quadrant': rcap,
        'known_issues': EXTRA['known_issues'],
        'id_renumbering': EXTRA.get('id_renumbering'),
        'removed_samples': EXTRA.get('removed_samples', []),
        'renamed_samples': EXTRA.get('renamed_samples', []),
        'imported_samples': EXTRA['imported_samples_note'],
        'samples': sorted(samples, key=lambda s: s['dir']),
        'conventions': {**bm.CONVENTIONS, **EXTRA['conventions_override']},
        'deviations_from_plan': bm.DEVIATIONS + EXTRA['extra_deviations'],
        'toolchain': 'native v3 samples: clang/LLVM 18.1.3 + self-built compiler-rt llvmorg-18.1.3 (see collection_tools); '
                     'samples imported from MiniDataset-v5: OSS-Fuzz base-builder:latest, unmodified build.sh (see each sample verification/NOTES.txt)',
        'evaluation_packaging': 'give a model only <sample>/input/ and <sample>/case.json; never the directory path, label.json, meta.json, NOTES.md or verification/',
    }
    json.dump(ds, open(f'{ROOT}/dataset.json', 'w'), indent=1, ensure_ascii=False)
    with open(f'{ROOT}/known_windows.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['project', 'harness', 'event', 'start_commit', 'end_commit'])
        for row in bm.WINDOWS + [tuple(r) for r in EXTRA['extra_windows']]:
            w.writerow(row)
    with open(f'{ROOT}/canonical_map.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['project_name_in_dataset', 'canonical_repo', 'samples', 'vendored_copies_excluded'])
        names = {}
        for s in samples:
            names.setdefault((s['project'], s['canonical_repo']), []).append(s['dir_id'])
        for (p, r), ids in sorted(names.items()):
            w.writerow([p, r, ' '.join(sorted(ids)), 'yes'])
    print(f"{len(samples)} samples, {len(gaps)} short cells, {len(overs)} overfull cells, "
          f"{len(collisions)} dir-id collisions")


if __name__ == '__main__':
    main()
