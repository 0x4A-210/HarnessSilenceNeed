# V3-13 — flac @ 9c83e6e43414

- label: **positive** / explicit / type `state` / introduced_by_this_change = False
- change: https://github.com/xiph/flac/commit/9c83e6e434143afba6eee8550aa8dcc9160fccf7 (Add missing *local_fixed_compute_best_predictor_wide member)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: intree `oss-fuzz/tool_flac.c` (target `fuzzer_tool_flac`)
- fix H: https://github.com/xiph/flac/commit/9593b949c293a45816b957581e6319c2a22a8a2e

## 理由

FLAC 的 oss-fuzz/tool_flac.c 在一个进程内连续调用 LLVMFuzzerTestOneInput。第一次 --force --sector-align 多文件编码后，全局变量 align_reservoir_samples 没有被重置，第二次普通 WAV 编码在 src/flac/encode.c:1024 触发断言。本次变更 M 只在 src/libFLAC/stream_encoder.c 的私有结构体里增加一个成员声明，与该缺口无关；同样的回放在 M^1 上也会 abort，因此归为 preexisting。维护者在后续提交 H（9593b949）中给 harness 加上了 align_reservoir_samples 重置，打上这部分改动后，回放在 M^1 和 M 上都返回 0。

## 可复现性

`verification/in.wav` 与 `verification/in2.wav` 是合法的双声道 16-bit/44100 Hz WAV fixtures。`verification/multi2.bin` 的第一次调用参数为 `--force --sector-align /tmp/in.wav /tmp/in2.wav`，第二次调用使用 `verification/plain.bin`。H 同时改了库和 harness，`verification/harness_fix.diff` 只保存其中 harness 的改动，验证修复时把它打到 `input/harness/oss-fuzz/tool_flac.c` 上。

| harness | lib | 日志 | 结果 |
|---|---|---|---|
| M（与 M^1 相同） | M^1 | `verification/replay_parent.log` | 断言失败，exit 134 |
| M（与 M^1 相同） | M | `verification/replay_M.log` | 断言失败，exit 134 |
| 打上 H 的改动 | M^1 | `verification/replay_fixed_parent.log` | 两次调用都返回 0 |
| 打上 H 的改动 | M | `verification/replay_fixed.log` | 两次调用都返回 0 |

## Rationale

The in-tree FLAC oss-fuzz/tool_flac.c invokes LLVMFuzzerTestOneInput repeatedly in one process. After a multi-file --force --sector-align encode the global align_reservoir_samples stays non-zero, and a later ordinary WAV encode aborts at src/flac/encode.c:1024. Change M only adds one member declaration to a private struct in src/libFLAC/stream_encoder.c and is unrelated to this gap; the same replay also aborts at M^1, so the gap is preexisting. The maintainer later added the align_reservoir_samples reset to the harness in H (9593b949); with that harness change the replay returns 0 at both M^1 and M.

## Verification summary

```json
{
 "source_fields": {
  "split": null,
  "manifests_as": "runtime_error",
  "negative_subtype": null,
  "existing_gap": "cross-call global state",
  "paired_with": null,
  "reused_from": null
 },
 "confidence": "verified",
 "method": "two-call sequential replay: first input runs --force --sector-align over two valid WAV fixtures and leaves align_reservoir_samples non-zero; second input is a valid ordinary WAV encode",
 "result": "The harness at M (identical to the harness at M^1) aborts on the second call at src/flac/encode.c:1024 with both lib(M^1) and lib(M); the harness with the change of H returns 0 for both calls with both lib(M^1) and lib(M).",
 "files": [
  "verification/replay_parent.log",
  "verification/replay_M.log",
  "verification/replay_fixed_parent.log",
  "verification/replay_fixed.log",
  "verification/multi2.bin",
  "verification/plain.bin",
  "verification/in.wav",
  "verification/in2.wav",
  "verification/harness_fix.diff"
 ],
 "compile_matrix": {
  "h(M^1) x lib(M^1)": {
   "status": "ok",
   "sha": "383512d551de2ebf640a95d010b38ad58b0d12ae",
   "oss_rev": "4a5ea89566ce81a71b08b65c1e1c35b2460a5ebe",
   "mode": "plain",
   "overlays": [
    "oss-fuzz/tool_flac.c=383512d551de2ebf640a95d010b38ad58b0d12ae"
   ]
  },
  "h(M^1) x lib(M)": {
   "status": "ok",
   "sha": "9c83e6e434143afba6eee8550aa8dcc9160fccf7",
   "oss_rev": "4a5ea89566ce81a71b08b65c1e1c35b2460a5ebe",
   "mode": "plain",
   "overlays": [
    "oss-fuzz/tool_flac.c=383512d551de2ebf640a95d010b38ad58b0d12ae"
   ]
  },
  "h(H) x lib(M^1)": {
   "status": "ok",
   "sha": "383512d551de2ebf640a95d010b38ad58b0d12ae",
   "oss_rev": "4a5ea89566ce81a71b08b65c1e1c35b2460a5ebe",
   "mode": "plain",
   "overlays": [
    "oss-fuzz/tool_flac.c=9593b949c293a45816b957581e6319c2a22a8a2e"
   ]
  },
  "h(H) x lib(M)": {
   "status": "ok",
   "sha": "9c83e6e434143afba6eee8550aa8dcc9160fccf7",
   "oss_rev": "4a5ea89566ce81a71b08b65c1e1c35b2460a5ebe",
   "mode": "plain",
   "overlays": [
    "oss-fuzz/tool_flac.c=9593b949c293a45816b957581e6319c2a22a8a2e"
   ]
  }
 },
 "replay": {
  "corpus_source": "two documented sequential inputs plus two checked-in valid WAV fixtures",
  "corpus_size": 2,
  "mode": "sequential",
  "crashes_lib_parent": 1,
  "crashes_lib_M": 1,
  "examples_parent": [
   {
    "input": "multi2.bin -> plain.bin",
    "status": "crash",
    "kind": "assertion",
    "rc": 134,
    "top_frames": [
     "flac__encode_file src/flac/encode.c:1024"
    ],
    "message": "Assertion `options.sector_align || *options.align_reservoir_samples == 0' failed."
   }
  ],
  "examples_M": [
   {
    "input": "multi2.bin -> plain.bin",
    "status": "crash",
    "kind": "assertion",
    "rc": 134,
    "top_frames": [
     "flac__encode_file src/flac/encode.c:1024"
    ],
    "message": "Assertion `options.sector_align || *options.align_reservoir_samples == 0' failed."
   }
  ],
  "crashes_fixed_harness_lib_parent": 0,
  "crashes_fixed_harness_lib_M": 0,
  "examples_fixed": [
   {
    "input": "multi2.bin -> plain.bin",
    "status": "ok",
    "calls": 2
   }
  ]
 },
 "explicit_signal": "runtime_failure_on_replay",
 "applies_to_parent": true,
 "toolchain": "gcc 15.2.0, cmake 4.2.3, Debug build with input/harness/build/build.sh, no sanitizers (WSL Ubuntu 26.04)"
}
```
