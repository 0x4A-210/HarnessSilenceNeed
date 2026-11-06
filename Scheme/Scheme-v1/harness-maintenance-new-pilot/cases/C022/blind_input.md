# Case ID

C022

## Existing Fuzz Harness H0

The following target source and OSS-Fuzz build wiring are from before the source commit.

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

### `historical OSS-Fuzz:projects/brotli/build.sh`

~~~~text
#!/bin/bash -eu

cmake . -DBUILD_TESTING=OFF
make clean
make -j$(nproc) brotlidec-static

$CC $CFLAGS -c -std=c99 -I. -I./c/include c/fuzz/decode_fuzzer.c 

$CXX $CXXFLAGS ./decode_fuzzer.o  -o $OUT/decode_fuzzer \
    $LIB_FUZZING_ENGINE ./libbrotlidec-static.a ./libbrotlicommon-static.a

cp java/org/brotli/integration/fuzz_data.zip $OUT/decode_fuzzer_seed_corpus.zip
chmod a-x $OUT/decode_fuzzer_seed_corpus.zip # we will try to run it otherwise
~~~~

## Source Change (S0 -> S1)

Tests, documentation, commit messages, generated snapshots, and any fuzz-harness changes are excluded. The complete diff for the production-source files listed below is included.

- `c/common/platform.h`

~~~~diff
diff --git a/c/common/platform.h b/c/common/platform.h
--- a/c/common/platform.h
+++ b/c/common/platform.h
@@ -37,13 +37,13 @@
 /* Let's try and follow the Linux convention */
 #define BROTLI_X_BYTE_ORDER BYTE_ORDER
 #define BROTLI_X_LITTLE_ENDIAN LITTLE_ENDIAN
 #define BROTLI_X_BIG_ENDIAN BIG_ENDIAN
 #endif
 
-#if BROTLI_MSVC_VERSION_CHECK(12, 0, 0)
+#if BROTLI_MSVC_VERSION_CHECK(18, 0, 0)
 #include <intrin.h>
 #endif
 
 #if defined(BROTLI_ENABLE_LOG) || defined(BROTLI_DEBUG)
 #include <assert.h>
 #include <stdio.h>
@@ -526,13 +526,13 @@ BROTLI_MIN_MAX(size_t) BROTLI_MIN_MAX(uint32_t) BROTLI_MIN_MAX(uint8_t)
 }
 
 #if BROTLI_64_BITS
 #if BROTLI_GNUC_HAS_BUILTIN(__builtin_ctzll, 3, 4, 0) || \
     BROTLI_INTEL_VERSION_CHECK(16, 0, 0)
 #define BROTLI_TZCNT64 __builtin_ctzll
-#elif BROTLI_MSVC_VERSION_CHECK(12, 0, 0)
+#elif BROTLI_MSVC_VERSION_CHECK(18, 0, 0)
 #if defined(BROTLI_TARGET_X64)
 #define BROTLI_TZCNT64 _tzcnt_u64
 #else /* BROTLI_TARGET_X64 */
 static BROTLI_INLINE uint32_t BrotliBsf64Msvc(uint64_t x) {
   uint32_t lsb;
   _BitScanForward64(&lsb, x);
@@ -543,13 +543,13 @@ static BROTLI_INLINE uint32_t BrotliBsf64Msvc(uint64_t x) {
 #endif /* __builtin_ctzll */
 #endif /* BROTLI_64_BITS */
 
 #if BROTLI_GNUC_HAS_BUILTIN(__builtin_clz, 3, 4, 0) || \
     BROTLI_INTEL_VERSION_CHECK(16, 0, 0)
 #define BROTLI_BSR32(x) (31u ^ (uint32_t)__builtin_clz(x))
-#elif BROTLI_MSVC_VERSION_CHECK(12, 0, 0)
+#elif BROTLI_MSVC_VERSION_CHECK(18, 0, 0)
 static BROTLI_INLINE uint32_t BrotliBsr32Msvc(uint32_t x) {
   unsigned long msb;
   _BitScanReverse(&msb, x);
   return (uint32_t)msb;
 }
 #define BROTLI_BSR32 BrotliBsr32Msvc
~~~~

## Relevant Code Context

No post-commit harness, future commit, coverage result, issue outcome, or vulnerability information is provided. The pre-change harness and source diff above are the available evidence.

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
