# Independent blind dataset

## Construction and independence

The deterministic miner searched local complete histories for six C/C++
projects and conservatively excluded every exact 40-character commit SHA found
in prior case sets, candidate pools, development artifacts, or the FSE source
selection. This produced 6,994 broad source-only candidates and excluded 135
project/commit rows backed by 1,053 unique prior SHAs.

The frozen selection contains 40 unique, single-parent commits from four
projects:

| Project | N4 frozen | Positive frozen | Total | Frozen share |
|---|---:|---:|---:|---:|
| c-ares | 5 | 5 | 10 | 25% |
| libplist | 5 | 5 | 10 | 25% |
| libspng | 5 | 5 | 10 | 25% |
| meshoptimizer | 5 | 5 | 10 | 25% |

Every selected commit is an ancestor of the locally archived project HEAD,
changes production C/C++ code, changes no C/C++ path containing `fuzz`, and is
absent from the conservative prior-SHA exclusion set.

## Ground-truth oracle

Before prediction, the audit required:

- complete H0 Harness inventory at the parent commit;
- zero literal H0 exposure of the audited entry/configuration identity;
- positive identity occurrence `0 -> present` in all changed production paths;
- N4 identity occurrence `present -> present` in all changed production paths;
- no changed Harness path; and
- manual confirmation that an N4 diff did not add a caller-side action, while
  a positive added an entry, format, option, or API protocol.

This is a static entry-exposure/protocol oracle; no dynamic coverage or runtime
build result is claimed. That is an important external-validity limitation,
especially for very small or initially stubbed public APIs.

## Freeze and post-freeze audit

- Ground Truth: 2026-09-10T10:34:05.846810Z
- Inputs: 2026-09-10T10:36:47.600835Z
- Prompt/model config: 2026-09-10T10:40:59.002606Z
- First prediction: after all three freezes (see prediction manifest)
- Dataset hash: `d041e28db6d6cef4ef187f0bf4304ccf044ced60f36e8d5ab0d2a2497b50fb43`
- Ground-truth hash: `6b5513fa02af4313e1d2ee1e9fc68f61a0d236d8a1a87bc842cf2a283f759683`
- Input hash: `7c55fd860e9cee127087de9ae65a89c87e95dd4dfcf0b7a0aa4caf8`

After prediction freeze, T5028 was invalidated rather than relabeled. Its diff
changes the public `vertex_uvs_stride` precondition from `>=12` to `>=8`, which
is a new caller-controlled input layout and therefore contradicts the frozen
N4/UNCHANGED label. The immutable label files were not edited, no replacement
was added, and the valid analysis set is consequently 19 N4 + 20 positives.
