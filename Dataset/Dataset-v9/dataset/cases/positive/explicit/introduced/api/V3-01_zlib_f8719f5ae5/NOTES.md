# V3-01 — zlib @ f8719f5ae5ac

- label: **positive** / explicit / type `api` / introduced_by_this_change = True
- change: https://github.com/madler/zlib/commit/f8719f5ae5acdc31d3794ddfea8ac963359de41e (Speed up software CRC-32 computation by a factor of 1.5 to 3.)
- origin: real_commit; route: fix_anchored; gt: maintainer_fix
- harness: oss ['projects/zlib/checksum_fuzzer.c'] (target `checksum_fuzzer`)
- fix H: https://github.com/google/oss-fuzz/commit/b41592118ef76b7a0af7c543c0cd13125049e5a1

## 理由
该提交把 crc32_combine_gen() 从“填充 32 项 z_crc_t 表”改为“返回单个 uLong 算子”，crc32_combine_op() 的第三个参数随之变为整数。OSS-Fuzz 托管的 checksum_fuzzer.c 仍按旧接口传入 z_crc_t op[32]，编译直接失败（too many arguments / incompatible pointer to integer）。属于本次引入的显式 api 退化，维护者在 oss-fuzz b41592118e 中修复。

## Rationale
This commit changes crc32_combine_gen() from filling a 32-entry z_crc_t table to returning a single uLong operator, and crc32_combine_op() now takes that integer. The OSS-Fuzz checksum_fuzzer.c still passes z_crc_t op[32], so it no longer compiles (too many arguments / incompatible pointer-to-integer). Explicit api degradation introduced by this change; fixed upstream in oss-fuzz b41592118e.

## Verification summary
```json
{
 "compile_matrix": {
  "h(M^1) x lib(M^1)": "ok",
  "h(M^1) x lib(M)": "fail",
  "h(fix) x lib(M)": "ok"
 },
 "explicit_signal": "compile_failure"
}
```
