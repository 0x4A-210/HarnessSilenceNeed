# Case ID

P004

## Existing Fuzz Harness H0

### `c/fuzz/decode_fuzzer.c`

~~~~c
// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

#include <brotli/decode.h>

// Entry point for LibFuzzer.
int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  size_t addend = 0;
  if (size > 0)
    addend = data[size - 1] & 7;
  const uint8_t* next_in = data;

  const int kBufferSize = 1024;
  uint8_t* buffer = (uint8_t*) malloc(kBufferSize);
  if (!buffer) {
    // OOM is out-of-scope here.
    return 0;
  }
  /* The biggest "magic number" in brotli is 16MiB - 16, so no need to check
     the cases with much longer output. */
  const size_t total_out_limit = (addend == 0) ? (1 << 26) : (1 << 24);
  size_t total_out = 0;

  BrotliDecoderState* state = BrotliDecoderCreateInstance(0, 0, 0);

  if (addend == 0)
    addend = size;
  /* Test both fast (addend == size) and slow (addend <= 7) decoding paths. */
  for (size_t i = 0; i < size;) {
    size_t next_i = i + addend;
    if (next_i > size)
      next_i = size;
    size_t avail_in = next_i - i;
    i = next_i;
    BrotliDecoderResult result = BROTLI_DECODER_RESULT_NEEDS_MORE_OUTPUT;
    while (result == BROTLI_DECODER_RESULT_NEEDS_MORE_OUTPUT) {
      size_t avail_out = kBufferSize;
      uint8_t* next_out = buffer;
      result = BrotliDecoderDecompressStream(
          state, &avail_in, &next_in, &avail_out, &next_out, &total_out);
      if (total_out > total_out_limit)
        break;
    }
    if (total_out > total_out_limit)
      break;
    if (result != BROTLI_DECODER_RESULT_NEEDS_MORE_INPUT)
      break;
  }

  BrotliDecoderDestroyInstance(state);
  free(buffer);
  return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/c/common/platform.h b/c/common/platform.h
index f1c1dc7..7406f3f 100644
--- a/c/common/platform.h
+++ b/c/common/platform.h
@@ -209,8 +209,13 @@ OR:
 #define BROTLI_TARGET_RISCV64
 #endif
 
+#if defined(__loongarch_lp64)
+#define BROTLI_TARGET_LOONGARCH64
+#endif
+
 #if defined(BROTLI_TARGET_X64) || defined(BROTLI_TARGET_ARMV8_64) || \
-    defined(BROTLI_TARGET_POWERPC64) || defined(BROTLI_TARGET_RISCV64)
+    defined(BROTLI_TARGET_POWERPC64) || defined(BROTLI_TARGET_RISCV64) || \
+    defined(BROTLI_TARGET_LOONGARCH64)
 #define BROTLI_TARGET_64_BITS 1
 #else
 #define BROTLI_TARGET_64_BITS 0
@@ -269,7 +274,7 @@ OR:
 #define BROTLI_UNALIGNED_READ_FAST (!!0)
 #elif defined(BROTLI_TARGET_X86) || defined(BROTLI_TARGET_X64) ||       \
     defined(BROTLI_TARGET_ARMV7) || defined(BROTLI_TARGET_ARMV8_ANY) || \
-    defined(BROTLI_TARGET_RISCV64)
+    defined(BROTLI_TARGET_RISCV64) || defined(BROTLI_TARGET_LOONGARCH64)
 /* These targets are known to generate efficient code for unaligned reads
  * (e.g. a single instruction, not multiple 1-byte loads, shifted and or'd
  * together). */
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
