#!/usr/bin/env python3
"""Write dataset/dataset.json, dataset/known_windows.csv, dataset/canonical_map.csv and
create every cell directory (empty cells are kept and registered as gaps)."""
import json, os, csv, glob, subprocess, datetime

HD = '/home/claude/hd'
ROOT = f'{HD}/dataset'
TYPES = ['api', 'configuration', 'input_format', 'state', 'lifecycle', 'mix']
PROJ = json.load(open(f'{HD}/tools/projects.json'))
from importlib.machinery import SourceFileLoader
mc = SourceFileLoader('mc', f'{HD}/tools/make_case.py').load_module()

# Known degradation windows established while building the dataset (plan §3.7). Each row is
# (project, harness, event, start = first commit with the gap, end = fixing commit or HEAD).
WINDOWS = [
    ('zlib', 'projects/zlib/checksum_fuzzer.c', 'crc32_combine_gen interface change (oss harness)', 'f8719f5', 'oss:b41592118e'),
    ('c-ares', 'test/ares-test-fuzz.c', 'source tree reorganisation breaks oss build paths', '0bf721cd', 'oss:008f2177e'),
    ('jq', 'tests/jq_fuzz_execute.cpp', 'oniguruma moved to vendor/, oss link line stale', '9727721', 'oss:489ed2798'),
    ('json-c', 'fuzz/tokener_parse_ex_fuzzer.cc', 'harness does not compile (jobj, 1-arg to_json_string)', '4902f9cb87', '4186537557'),
    ('json-c', 'fuzz/tokener_parse_ex_fuzzer.cc', 'foreach on non-object input crashes', '4186537557', '88bce2b38e'),
    ('libucl', 'tests/fuzzers/ucl_add_string_fuzzer.c', 'parser leaked on error path', '56ecce3', 'cfc517cf42'),
    ('lz4', 'ossfuzz/compress_frame_fuzzer.c', 'producer told compressBound(size) bytes: OOB read', '64e3134b2a', 'e9d8e15263'),
    ('mbedtls', 'programs/fuzz/fuzz_privkey.c', 'dummy_random called with NULL ctr_drbg', 'ae35830295', '6d2479516c'),
    ('libyaml', 'projects/libyaml/libyaml_emitter_fuzzer.c', 'copy_event result inverted, emitter never fed', 'oss:8a74af8f52', 'oss:d94076d68f'),
    ('utf8proc', 'test/fuzzer.c', 'UTF-32 buffer allocation inverted; normalize_utf32 never fed', '63f31c908e', '8a7db0fb93'),
    ('inih', 'projects/inih/inihfuzz.c', 'INI_ALLOW_NO_VALUE never enabled in fuzz build', 'oss:28760cff6b', 'HEAD'),
    ('inih', 'ini.c', 'harness passes NULL user to dumper', '9114067a92', 'fe1e8f82ae'),
    ('fmt', 'test/fuzzing/one_arg.cpp', 'percent spec compiled out (FMT_DEPRECATED_PERCENT)', '5420bcce2d', 'cbb4cb89'),
    ('brotli', 'c/fuzz/decode_fuzzer.cc', 'large-window parameter never set', '35e69fc', 'HEAD'),
    ('brotli', 'c/fuzz/decode_fuzzer.c', 'large-window parameter never set', '35e69fc', 'HEAD'),
    ('pcre2', 'src/pcre2_fuzzsupport.c', 'compile extra options never set', '32f03ad5', 'HEAD'),
    ('xz', 'tests/ossfuzz/fuzz_decode_alone.c', 'decoders never re-initialised', 'harness-creation', 'd4217668a7'),
    ('xz', 'tests/ossfuzz/fuzz_decode_stream.c', 'decoders never re-initialised', 'harness-creation', 'd4217668a7'),
    ('md4c', 'test/fuzzers/fuzz-mdhtml.c', 'typo "ize" breaks the harness build', 'a27f8dc093', '821477b1da'),
    ('jq', 'tests/jq_fuzz_parse_stream.c', 'JV_PARSE_STREAMING passed to the one-shot parser', 'harness-creation', 'b6a9e260cd'),
    ('zstd', 'tests/fuzz/stream_decompress.c', 'magicless frame format never selected (ZSTD_DCtx_setFormat never called)', '824f75ea7c', 'HEAD'),
    ('json-c', 'projects/json-c/tokener_parse_ex_fuzzer.cc', 'single parse_ex call: incremental resume state never exercised', '6eac6986c9', 'HEAD'),
    ('libpng', 'contrib/oss-fuzz/libpng_read_fuzzer.cc', 'png_start_read_image after png_read_update_info: duplicate-call error, no row read', 'da923d334d', 'f648294931'),
    ('libxml2', 'fuzz/xinclude.c', 'XInclude per-context error handler never set', '2829a21a95', 'HEAD'),
]


def main():
    os.makedirs(f'{ROOT}/cases', exist_ok=True)
    cells, gaps, samples = [], [], []
    for lab in ('positive', 'negative'):
        for vis in ('explicit', 'silent'):
            intros = ('introduced', 'preexisting') if lab == 'positive' else (None,)
            for intro in intros:
                for t in TYPES:
                    path = '/'.join(x for x in (lab, vis, intro, t) if x)
                    need = 1 if lab == 'positive' else 2
                    d = f'{ROOT}/cases/{path}'
                    os.makedirs(d, exist_ok=True)
                    items = sorted(x for x in os.listdir(d) if os.path.isdir(f'{d}/{x}') and os.path.exists(f'{d}/{x}/label.json'))
                    cells.append({'cell': path, 'need': need, 'have': len(items), 'samples': items})
                    if len(items) < need:
                        gaps.append({'cell': path, 'missing': need - len(items),
                                     'reason': GAP_REASONS.get(path, 'no candidate passed the strict checks within the compute budget')})
                    for it in items:
                        sd = f'{d}/{it}'
                        L = json.load(open(f'{sd}/label.json')); Mt = json.load(open(f'{sd}/meta.json'))
                        samples.append({'id': L['id'], 'path': f'cases/{path}/{it}', 'project': Mt['project'],
                                        'M': Mt['M'], 'M_date': Mt['M_date'][:10], 'label': L['label'],
                                        'need_visibility': L['need_visibility'],
                                        'introduced_by_this_change': L['introduced_by_this_change'],
                                        'degradation_type': L['degradation_type'],
                                        'mix_components': L.get('mix_components'),
                                        'change_origin': L['change_origin'], 'gt_source': L['gt_source'],
                                        'discovery_route': L['discovery_route'], 'url': L['urls']['M']})
    def cnt(key):
        out = {}
        for s in samples:
            out[str(s[key])] = out.get(str(s[key]), 0) + 1
        return out
    pos = [s for s in samples if s['label'] == 'positive']
    cf = sum(1 for s in pos if s['gt_source'] == 'counterfactual_fix')
    ds = {
        'name': 'Harness Degradation dataset v3 (real commits)',
        'schema': '3.0',
        'generated': datetime.datetime.now().isoformat(timespec='seconds'),
        'target_size': 48, 'size': len(samples),
        'layout': 'dataset-directory-layout.md: positive/<visibility>/<introduced|preexisting>/<type>/, negative/<visibility>/<type>/; positive cells hold 1 sample, negative cells 2',
        'distribution': {'by_label': cnt('label'), 'by_visibility': cnt('need_visibility'),
                         'by_type': cnt('degradation_type'), 'by_introduced(positive)': {str(k): v for k, v in
                         {True: sum(1 for s in pos if s['introduced_by_this_change'] is True),
                          False: sum(1 for s in pos if s['introduced_by_this_change'] is False)}.items()},
                         'by_change_origin': cnt('change_origin'), 'by_gt_source': cnt('gt_source'),
                         'by_discovery_route': cnt('discovery_route'), 'by_project': cnt('project')},
        'counterfactual_share_of_positives': round(cf / len(pos), 3) if pos else None,
        'cells': cells, 'gaps': gaps, 'samples': samples,
        'conventions': CONVENTIONS,
        'deviations_from_plan': DEVIATIONS,
        'toolchain': 'clang/LLVM 18.1.3 (Ubuntu); compiler-rt llvmorg-18.1.3 built from source (libFuzzer, ASan, UBSan, profile); '
                     'compiler wrapper drops -stdlib=libc++ (not installed) and turns clang>=15 new hard errors '
                     '(int-conversion, implicit-function-declaration, incompatible-pointer-types, ...) back into warnings to approximate period toolchains',
        'evaluation_packaging': 'give a model only <sample>/input/ and <sample>/case.json; never the directory path, label.json, meta.json, NOTES.md or verification/',
    }
    json.dump(ds, open(f'{ROOT}/dataset.json', 'w'), indent=1, ensure_ascii=False)
    with open(f'{ROOT}/known_windows.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['project', 'harness', 'event', 'start_commit', 'end_commit'])
        for row in WINDOWS:
            w.writerow(row)
    with open(f'{ROOT}/canonical_map.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['project', 'canonical_repo', 'oss_fuzz_project', 'vendored_copies_excluded'])
        for p, cfg in sorted(PROJ.items()):
            if p in mc.URLS:
                w.writerow([p, mc.URLS[p], f"https://github.com/google/oss-fuzz/tree/master/projects/{cfg['oss']}", 'yes'])
    print(f'{len(samples)} samples, {len(gaps)} short cells')


GAP_REASONS = {
    'positive/explicit/introduced/input_format': 'no real commit found where a library format/framing change makes the unchanged harness fail loudly; best lead (libxml2 834b8123, R2: xmlParserInputBufferCreateMem no longer pre-fills, old fuzz.c entity loader) only overflows for external entities > 8 KiB and was not reproducible on the fixed corpus',
    'positive/explicit/introduced/lifecycle': 'no real commit found: every lifecycle-type harness fix located (oss-fuzz + in-tree history of all 38 projects) was either harness-caused or pre-existing; libexpat cfce28e1 (allocation tracker vs assert(XML_ExternalEntityParserCreate)) does not trigger below the 64 MiB activation threshold',
    'positive/explicit/preexisting/state': 'only lead libsndfile 37609184/1998691e (virtual-IO vfseek lets offset leave [0,len], later negative-size memcpy) is a callback-contract (api) defect rather than state; not used to avoid mislabelling',
    'positive/explicit/preexisting/mix': 'candidates rejected: libyaml OSS-Fuzz dumper (inverted yaml_write_handler + error-path leaks) gives no loud failure on replay, the inversion only silences the round-trip check; libcbor 8ca9bf7 allocator hooks have no related library commit in the window and both loud defects are the same type',
    'positive/silent/introduced/mix': 'candidate brotli 35e69fc7cf (large-window streams + BrotliDecoderSetParameter never called; counterfactual Δh) showed the expected gap (0 in 3/3 seeds without the fix, hit in 2/2 with it) but failed the per-seed execution threshold: the decode harness decodes up to 64 MiB per input and reached only ~44k execs in 600 s even when run alone (threshold 166,666), so under plan §5 the campaign is invalid and the sample was not admitted',
    'positive/silent/preexisting/mix': 'candidate cmark 74e8f638 / H 8667a22 rejected: the state component (CR/LF carry-over between cmark_parser_feed chunks) was not reached in budgeted fuzzing and is not separable from the cmark_parse_file component (which also feeds 4096-byte chunks)',
}
CONVENTIONS = {
    'type_assignment': 'api = public symbol signature/semantics/return contract, and (plan §4.2) new option or flag VALUES that a harness with hard-coded options never sets; '
                       'configuration = compile-time macros, build switches/scripts, generated code; input_format = accepted syntax/encoding/magic, or how the harness frames/splits its input; '
                       'state = internal state, reuse/reset contracts, object reuse across calls; lifecycle = init/teardown, creation order, ownership, error channels; '
                       'mix = >=2 of these in the same change, each one needed (positives) or each one touching the harness path (negatives)',
    'explicit': 'compile/link failure of the harness, or loud runtime failure on corpus replay with the harness in the top frames / an API-contract message (ASan, LeakSanitizer, assertion)',
    'silent': 'builds and runs; gap lines/branches have zero coverage in all 3 seeds without the fix and non-zero in >= 2 seeds with the fix (maintainer fix H or counterfactual Δh)',
    'negative': 'builds before and after, no new crash on corpus replay, changed lines covered (> 0) by the fixed corpus; silent negatives must additionally be covered in >= 2 of 3 fuzz seeds',
    'introduced_vs_preexisting': 'introduced: gap absent or reachable at M^1; preexisting: the fix applied to M^1 lifts the same gap (verified by a second campaign at M^1) or the harness already failed at M^1',
    'corpus': 'fixed corpus decided at M^1: the project/OSS-Fuzz seed corpus at M^1 when it has >= 5 inputs, otherwise that plus 300 s of libFuzzer on the M^1 build',
    'gt_source': 'maintainer_fix / coupled_commit / counterfactual_fix for positives; negatives use "experiment" (the verdict of the negative experiment)',
    'change_origin': 'real_commit = M is a mainline commit used as-is; real_commit_lib_hunks_only = R2 split of a coupled commit (library hunks only, harness at M^1); report metrics separately',
}
DEVIATIONS = [
    'fuzz budget B reduced to 3 seeds x 600 s (plan: 3 x 3600 s); exec threshold scaled to 166,666 execs per seed; recorded per sample',
    'single 2-core machine: no R3 HEAD audit over the whole OSS-Fuzz pool; R3-style gaps were found by targeted audits of selected harnesses',
    'Δh counterfactual fixes were NOT submitted upstream (user decision); they ship in verification/counterfactual_fix.diff',
    'custom build recipes where the date-pinned OSS-Fuzz build.sh could not run offline: expat (protobuf LPM fuzzer), pcre2 (8-bit target only), xz (CMake instead of autotools/autopoint), fmt (no OSS-Fuzz project before 2020-10), mbedtls (generated sources via `make generated_files`, which the 2021 OSS-Fuzz build.sh lacked; the openssl/boringssl corpora cloned by the Dockerfile are replaced by the project\'s own tests/data_files DER/PEM/key files); recipes ship in input/harness/build/',
    'zstd V3-15 and pugixml V3-38 pin the first OSS-Fuzz project revision (zstd eebdc80cb 2017-09-29, pugixml 19a52805b6 2020-09-09; both within days of M) for every build, because no earlier revision exists for M^1',
    'libpng V3-17: the maintainer fix f648294931 is applied as its own one-line hunk ported onto the harness at M (verification/counterfactual_fix.diff), because the harness at H also carries unrelated additions',
    'extra repositories cloned by Dockerfiles (google/fuzzing, yaml-cpp-fuzzer, zlib for libspng) are taken at their current HEAD, not date-pinned',
    'cells with no sample are kept as empty directories and listed under gaps (plan §7.2: never synthesize)',
]

if __name__ == '__main__':
    main()
