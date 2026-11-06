# Case ID

P002

## Existing Fuzz Harness H0

### `fuzz/decode_fuzzer.cc`

~~~~cpp
// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <stddef.h>
#include <stdint.h>

#include <brotli/decode.h>

// Entry point for LibFuzzer.
extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  size_t addend = 0;
  if (size > 0)
    addend = data[size - 1] & 7;
  const uint8_t* next_in = data;

  const int kBufferSize = 1024;
  uint8_t* buffer = new uint8_t[kBufferSize];
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
  delete[] buffer;
  return 0;
}
~~~~
### `fuzz/run_decode_fuzzer.cc`

~~~~cpp
/* Copyright 2016 Google Inc. All Rights Reserved.

   Distributed under MIT license.
   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
*/

/* Simple runner for decode_fuzzer.cc */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>

extern "C" void LLVMFuzzerTestOneInput(const uint8_t* data, size_t size);

int main(int argc, char* *argv) {
  if (argc != 2) {
    fprintf(stderr, "Exactly one argument is expected.\n");
    exit(EXIT_FAILURE);
  }

  FILE* f = fopen(argv[1], "r");
  if (!f) {
    fprintf(stderr, "Failed to open input file.");
    exit(EXIT_FAILURE);
  }

  size_t max_len = 1 << 20;
  unsigned char* tmp = (unsigned char*)malloc(max_len);
  size_t len = fread(tmp, 1, max_len, f);
  if (ferror(f)) {
    fclose(f);
    fprintf(stderr, "Failed read input file.");
    exit(EXIT_FAILURE);
  }
  /* Make data after the end "inaccessible". */
  unsigned char* data = (unsigned char*)malloc(len);
  memcpy(data, tmp, len);
  free(tmp);

  LLVMFuzzerTestOneInput(data, len);
  free(data);
  exit(EXIT_SUCCESS);
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is a deterministic H0-identifier-anchored excerpt capped at 70,000 characters.

~~~~diff
... [unselected diff lines omitted by frozen H0-anchored rule] ...
diff --git a/c/common/constants.h b/c/common/constants.h
new file mode 100644
index 0000000..7b3d6a5
--- /dev/null
+++ b/c/common/constants.h
@@ -0,0 +1,55 @@
+/* Copyright 2016 Google Inc. All Rights Reserved.
+
+   Distributed under MIT license.
+   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
+*/
+
+#ifndef BROTLI_COMMON_CONSTANTS_H_
+#define BROTLI_COMMON_CONSTANTS_H_
+
+/* Specification: 7.3. Encoding of the context map */
+#define BROTLI_CONTEXT_MAP_MAX_RLE 16
+
+/* Specification: 2. Compressed representation overview */
+#define BROTLI_MAX_NUMBER_OF_BLOCK_TYPES 256
+
+/* Specification: 3.3. Alphabet sizes: insert-and-copy length */
+#define BROTLI_NUM_LITERAL_SYMBOLS 256
+#define BROTLI_NUM_COMMAND_SYMBOLS 704
+#define BROTLI_NUM_BLOCK_LEN_SYMBOLS 26
+#define BROTLI_MAX_CONTEXT_MAP_SYMBOLS (BROTLI_MAX_NUMBER_OF_BLOCK_TYPES + \
+                                        BROTLI_CONTEXT_MAP_MAX_RLE)
+#define BROTLI_MAX_BLOCK_TYPE_SYMBOLS (BROTLI_MAX_NUMBER_OF_BLOCK_TYPES + 2)
+
+/* Specification: 3.5. Complex prefix codes */
+#define BROTLI_REPEAT_PREVIOUS_CODE_LENGTH 16
+#define BROTLI_REPEAT_ZERO_CODE_LENGTH 17
+#define BROTLI_CODE_LENGTH_CODES (BROTLI_REPEAT_ZERO_CODE_LENGTH + 1)
+/* "code length of 8 is repeated" */
+#define BROTLI_INITIAL_REPEATED_CODE_LENGTH 8
+
+/* Specification: 4. Encoding of distances */
+#define BROTLI_NUM_DISTANCE_SHORT_CODES 16
+#define BROTLI_MAX_NPOSTFIX 3
+#define BROTLI_MAX_NDIRECT 120
+#define BROTLI_MAX_DISTANCE_BITS 24U
+/* BROTLI_NUM_DISTANCE_SYMBOLS == 520 */
+#define BROTLI_NUM_DISTANCE_SYMBOLS (BROTLI_NUM_DISTANCE_SHORT_CODES + \
+                                     BROTLI_MAX_NDIRECT +              \
+                                     (BROTLI_MAX_DISTANCE_BITS <<      \
+                                      (BROTLI_MAX_NPOSTFIX + 1)))
+
+/* 7.1. Context modes and context ID lookup for literals */
+/* "context IDs for literals are in the range of 0..63" */
+#define BROTLI_LITERAL_CONTEXT_BITS 6
+
+/* 7.2. Context ID for distances */
+#define BROTLI_DISTANCE_CONTEXT_BITS 2
+
+/* 9.1. Format of the Stream Header */
+/* Number of slack bytes for window size. Don't confuse
+   with BROTLI_NUM_DISTANCE_SHORT_CODES. */
+#define BROTLI_WINDOW_GAP 16
+#define BROTLI_MAX_BACKWARD_LIMIT(W) (((size_t)1 << (W)) - BROTLI_WINDOW_GAP)
+
+#endif  /* BROTLI_COMMON_CONSTANTS_H_ */
diff --git a/c/common/dictionary.c b/c/common/dictionary.c
new file mode 100644
index 0000000..578cf8c
--- /dev/null
+++ b/c/common/dictionary.c
@@ -0,0 +1,5886 @@
+/* Copyright 2013 Google Inc. All Rights Reserved.
+
+   Distributed under MIT license.
+   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
+*/
+
+#include "./dictionary.h"
+
+#if defined(__cplusplus) || defined(c_plusplus)
+extern "C" {
+#endif
+
+static const BrotliDictionary kBrotliDictionary = {
+  /* size_bits_by_length */
+  {
+    0, 0, 0, 0, 10, 10, 11, 11,
+    10, 10, 10, 10, 10, 9, 9, 8,
+    7, 7, 8, 7, 7, 6, 6, 5,
+    5, 0, 0, 0, 0, 0, 0, 0
+  },
+
+  /* offsets_by_length */
+  {
+    0, 0, 0, 0, 0, 4096, 9216, 21504,
+    35840, 44032, 53248, 63488, 74752, 87040, 93696, 100864,
+    104704, 106752, 108928, 113536, 115968, 118528, 119872, 121280,
+    122016, 122784, 122784, 122784, 122784, 122784, 122784, 122784
+  },
+
+  /* data */
+{
+116,105,109,101,100,111,119,110,108,105,102,101,108,101,102,116,98,97,99,107,99,
+111,100,101,100,97,116,97,115,104,111,119,111,110,108,121,115,105,116,101,99,105
+,116,121,111,112,101,110,106,117,115,116,108,105,107,101,102,114,101,101,119,111
+,114,107,116,101,120,116,121,101,97,114,111,118,101,114,98,111,100,121,108,111,
+118,101,102,111,114,109,98,111,111,107,112,108,97,121,108,105,118,101,108,105,
+110,101,104,101,108,112,104,111,109,101,115,105,100,101,109,111,114,101,119,111,
+114,100,108,111,110,103,116,104,101,109,118,105,101,119,102,105,110,100,112,97,
+103,101,100,97,121,115,102,117,108,108,104,101,97,100,116,101,114,109,101,97,99,
+104,97,114,101,97,102,114,111,109,116,114,117,101,109,97,114,107,97,98,108,101,
+117,112,111,110,104,105,103,104,100,97,116,101,108,97,110,100,110,101,119,115,
+101,118,101,110,110,101,120,116,99,97,115,101,98,111,116,104,112,111,115,116,117
+,115,101,100,109,97,100,101,104,97,110,100,104,101,114,101,119,104,97,116,110,97
+,109,101,76,105,110,107,98,108,111,103,115,105,122,101,98,97,115,101,104,101,108
+,100,109,97,107,101,109,97,105,110,117,115,101,114,39,41,32,43,104,111,108,100,
+101,110,100,115,119,105,116,104,78,101,119,115,114,101,97,100,119,101,114,101,
+115,105,103,110,116,97,107,101,104,97,118,101,103,97,109,101,115,101,101,110,99,
+97,108,108,112,97,116,104,119,101,108,108,112,108,117,115,109,101,110,117,102,
+105,108,109,112,97,114,116,106,111,105,110,116,104,105,115,108,105,115,116,103,
+111,111,100,110,101,101,100,119,97,121,115,119,101,115,116,106,111,98,115,109,
+105,110,100,97,108,115,111,108,111,103,111,114,105,99,104,117,115,101,115,108,97
+,115,116,116,101,97,109,97,114,109,121,102,111,111,100,107,105,110,103,119,105,
+108,108,101,97,115,116,119,97,114,100,98,101,115,116,102,105,114,101,80,97,103,
+101,107,110,111,119,97,119,97,121,46,112,110,103,109,111,118,101,116,104,97,110,
+108,111,97,100,103,105,118,101,115,101,108,102,110,111,116,101,109,117,99,104,
+102,101,101,100,109,97,110,121,114,111,99,107,105,99,111,110,111,110,99,101,108,
+111,111,107,104,105,100,101,100,105,101,100,72,111,109,101,114,117,108,101,104,
+111,115,116,97,106,97,120,105,110,102,111,99,108,117,98,108,97,119,115,108,101,
+115,115,104,97,108,102,115,111,109,101,115,117,99,104,122,111,110,101,49,48,48,
+37,111,110,101,115,99,97,114,101,84,105,109,101,114,97,99,101,98,108,117,101,102
+,111,117,114,119,101,101,107,102,97,99,101,104,111,112,101,103,97,118,101,104,97
+,114,100,108,111,115,116,119,104,101,110,112,97,114,107,107,101,112,116,112,97,
+115,115,115,104,105,112,114,111,111,109,72,84,77,76,112,108,97,110,84,121,112,
+101,100,111,110,101,115,97,118,101,107,101,101,112,102,108,97,103,108,105,110,
+107,115,111,108,100,102,105,118,101,116,111,111,107,114,97,116,101,116,111,119,
+110,106,117,109,112,116,104,117,115,100,97,114,107,99,97,114,100,102,105,108,101
+,102,101,97,114,115,116,97,121,107,105,108,108,116,104,97,116,102,97,108,108,97,
+117,116,111,101,118,101,114,46,99,111,109,116,97,108,107,115,104,111,112,118,111
+,116,101,100,101,101,112,109,111,100,101,114,101,115,116,116,117,114,110,98,111,
+114,110,98,97,110,100,102,101,108,108,114,111,115,101,117,114,108,40,115,107,105
+,110,114,111,108,101,99,111,109,101,97,99,116,115,97,103,101,115,109,101,101,116
+,103,111,108,100,46,106,112,103,105,116,101,109,118,97,114,121,102,101,108,116,
+116,104,101,110,115,101,110,100,100,114,111,112,86,105,101,119,99,111,112,121,49
+,46,48,34,60,47,97,62,115,116,111,112,101,108,115,101,108,105,101,115,116,111,
+117,114,112,97,99,107,46,103,105,102,112,97,115,116,99,115,115,63,103,114,97,121
+,109,101,97,110,38,103,116,59,114,105,100,101,115,104,111,116,108,97,116,101,115
+,97,105,100,114,111,97,100,118,97,114,32,102,101,101,108,106,111,104,110,114,105
+,99,107,112,111,114,116,102,97,115,116,39,85,65,45,100,101,97,100,60,47,98,62,
+112,111,111,114,98,105,108,108,116,121,112,101,85,46,83,46,119,111,111,100,109,
+117,115,116,50,112,120,59,73,110,102,111,114,97,110,107,119,105,100,101,119,97,
+110,116,119,97,108,108,108,101,97,100,91,48,93,59,112,97,117,108,119,97,118,101,
+115,117,114,101,36,40,39,35,119,97,105,116,109,97,115,115,97,114,109,115,103,111
+,101,115,103,97,105,110,108,97,110,103,112,97,105,100,33,45,45,32,108,111,99,107
+,117,110,105,116,114,111,111,116,119,97,108,107,102,105,114,109,119,105,102,101,
+120,109,108,34,115,111,110,103,116,101,115,116,50,48,112,120,107,105,110,100,114
+,111,119,115,116,111,111,108,102,111,110,116,109,97,105,108,115,97,102,101,115,
+116,97,114,109,97,112,115,99,111,114,101,114,97,105,110,102,108,111,119,98,97,98
+,121,115,112,97,110,115,97,121,115,52,112,120,59,54,112,120,59,97,114,116,115,
+102,111,111,116,114,101,97,108,119,105,107,105,104,101,97,116,115,116,101,112,
+116,114,105,112,111,114,103,47,108,97,107,101,119,101,97,107,116,111,108,100,70,
+111,114,109,99,97,115,116,102,97,110,115,98,97,110,107,118,101,114,121,114,117,
+110,115,106,117,108,121,116,97,115,107,49,112,120,59,103,111,97,108,103,114,101,
+119,115,108,111,119,101,100,103,101,105,100,61,34,115,101,116,115,53,112,120,59,
+46,106,115,63,52,48,112,120,105,102,32,40,115,111,111,110,115,101,97,116,110,111
+,110,101,116,117,98,101,122,101,114,111,115,101,110,116,114,101,101,100,102,97,
+99,116,105,110,116,111,103,105,102,116,104,97,114,109,49,56,112,120,99,97,109,
+101,104,105,108,108,98,111,108,100,122,111,111,109,118,111,105,100,101,97,115,
+121,114,105,110,103,102,105,108,108,112,101,97,107,105,110,105,116,99,111,115,
+116,51,112,120,59,106,97,99,107,116,97,103,115,98,105,116,115,114,111,108,108,
+101,100,105,116,107,110,101,119,110,101,97,114,60,33,45,45,103,114,111,119,74,83
+,79,78,100,117,116,121,78,97,109,101,115,97,108,101,121,111,117,32,108,111,116,
+115,112,97,105,110,106,97,122,122,99,111,108,100,101,121,101,115,102,105,115,104
+,119,119,119,46,114,105,115,107,116,97,98,115,112,114,101,118,49,48,112,120,114,
+105,115,101,50,53,112,120,66,108,117,101,100,105,110,103,51,48,48,44,98,97,108,
+108,102,111,114,100,101,97,114,110,119,105,108,100,98,111,120,46,102,97,105,114,
+108,97,99,107,118,101,114,115,112,97,105,114,106,117,110,101,116,101,99,104,105,
+102,40,33,112,105,99,107,101,118,105,108,36,40,34,35,119,97,114,109,108,111,114,
+100,100,111,101,115,112,117,108,108,44,48,48,48,105,100,101,97,100,114,97,119,
+104,117,103,101,115,112,111,116,102,117,110,100,98,117,114,110,104,114,101,102,
+99,101,108,108,107,101,121,115,116,105,99,107,104,111,117,114,108,111,115,115,
+102,117,101,108,49,50,112,120,115,117,105,116,100,101,97,108,82,83,83,34,97,103,
+101,100,103,114,101,121,71,69,84,34,101,97,115,101,97,105,109,115,103,105,114,
+108,97,105,100,115,56,112,120,59,110,97,118,121,103,114,105,100,116,105,112,115,
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+,209,129,209,130,208,178,208,176,208,177,208,181,208,183,208,190,208,191,208,176
+,209,129,208,189,208,190,209,129,209,130,208,184,224,164,170,224,165,129,224,164
+,184,224,165,141,224,164,164,224,164,191,224,164,149,224,164,190,224,164,149,224
+,164,190,224,164,130,224,164,151,224,165,141,224,164,176,224,165,135,224,164,184
+,224,164,137,224,164,168,224,165,141,224,164,185,224,165,139,224,164,130,224,164
+,168,224,165,135,224,164,181,224,164,191,224,164,167,224,164,190,224,164,168,224
+,164,184,224,164,173,224,164,190,224,164,171,224,164,191,224,164,149,224,165,141
+,224,164,184,224,164,191,224,164,130,224,164,151,224,164,184,224,165,129,224,164
+,176,224,164,149,224,165,141,224,164,183,224,164,191,224,164,164,224,164,149,224
+,165,137,224,164,170,224,165,128,224,164,176,224,164,190,224,164,135,224,164,159
+,224,164,181,224,164,191,224,164,156,224,165,141,224,164,158,224,164,190,224,164
+,170,224,164,168,224,164,149,224,164,190,224,164,176,224,165,141,224,164,176,224
+,164,181,224,164,190,224,164,136,224,164,184,224,164,149,224,165,141,224,164,176
+,224,164,191,224,164,175,224,164,164,224,164,190
+}
+};
+
+const BrotliDictionary* BrotliGetDictionary() {
+  return &kBrotliDictionary;
+}
+
+#if defined(__cplusplus) || defined(c_plusplus)
+}  /* extern "C" */
+#endif
diff --git a/c/common/dictionary.h b/c/common/dictionary.h
new file mode 100644
index 0000000..fc47c1e
--- /dev/null
+++ b/c/common/dictionary.h
@@ -0,0 +1,50 @@
+/* Copyright 2013 Google Inc. All Rights Reserved.
+
+   Distributed under MIT license.
+   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
+*/
+
+/* Collection of static dictionary words. */
+
+#ifndef BROTLI_COMMON_DICTIONARY_H_
+#define BROTLI_COMMON_DICTIONARY_H_
+
+#include <brotli/port.h>
+#include <brotli/types.h>
+
+#if defined(__cplusplus) || defined(c_plusplus)
+extern "C" {
+#endif
+
+typedef struct BrotliDictionary {
+  /**
+   * Number of bits to encode index of dictionary word in a bucket.
+   *
+   * Specification: Appendix A. Static Dictionary Data
+   *
+   * Words in a dictionary are bucketed by length.
+   * @c 0 means that there are no words of a given length.
+   * Dictionary consists of words with length of [4..24] bytes.
+   * Values at [0..3] and [25..31] indices should not be addressed.
+   */
+  uint8_t size_bits_by_length[32];
+
+  /* assert(offset[i + 1] == offset[i] + (bits[i] ? (i << bits[i]) : 0)) */
+  uint32_t offsets_by_length[32];
+
+  /* Data array is not bound, and should obey to size_bits_by_length values.
+     Specified size matches default (RFC 7932) dictionary. */
+  /* assert(sizeof(data) == offsets_by_length[31]) */
+  uint8_t data[122784];
+} BrotliDictionary;
+
+BROTLI_COMMON_API extern const BrotliDictionary* BrotliGetDictionary(void);
+
+#define BROTLI_MIN_DICTIONARY_WORD_LENGTH 4
+#define BROTLI_MAX_DICTIONARY_WORD_LENGTH 24
+
+#if defined(__cplusplus) || defined(c_plusplus)
+}  /* extern "C" */
+#endif
+
+#endif  /* BROTLI_COMMON_DICTIONARY_H_ */
diff --git a/c/common/version.h b/c/common/version.h
new file mode 100755
index 0000000..10fe01f
--- /dev/null
+++ b/c/common/version.h
@@ -0,0 +1,19 @@
+/* Copyright 2016 Google Inc. All Rights Reserved.
+
+   Distributed under MIT license.
+   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
+*/
+
+/* Version definition. */
+
+#ifndef BROTLI_COMMON_VERSION_H_
+#define BROTLI_COMMON_VERSION_H_
+
+/* This macro should only be used when library is compiled together with client.
+   If library is dynamically linked, use BrotliDecoderVersion and
+   BrotliEncoderVersion methods. */
+
+/* Semantic version, calculated as (MAJOR << 24) | (MINOR << 12) | PATCH */
+#define BROTLI_VERSION 0x1000000
+
+#endif  /* BROTLI_COMMON_VERSION_H_ */
diff --git a/c/dec/bit_reader.c b/c/dec/bit_reader.c
new file mode 100644
index 0000000..9925ba4
--- /dev/null
+++ b/c/dec/bit_reader.c
@@ -0,0 +1,48 @@
+/* Copyright 2013 Google Inc. All Rights Reserved.
+
+   Distributed under MIT license.
+   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
+*/
+
+/* Bit reading helpers */
+
+#include "./bit_reader.h"
+
+#include <brotli/types.h>
+#include "./port.h"
+
+#if defined(__cplusplus) || defined(c_plusplus)
+extern "C" {
+#endif
+
+void BrotliInitBitReader(BrotliBitReader* const br) {
+  br->val_ = 0;
+  br->bit_pos_ = sizeof(br->val_) << 3;
+}
+
+BROTLI_BOOL BrotliWarmupBitReader(BrotliBitReader* const br) {
+  size_t aligned_read_mask = (sizeof(br->val_) >> 1) - 1;
+  /* Fixing alignment after unaligned BrotliFillWindow would result accumulator
+     overflow. If unalignment is caused by BrotliSafeReadBits, then there is
+     enough space in accumulator to fix alignment. */
+  if (!BROTLI_ALIGNED_READ) {
+    aligned_read_mask = 0;
+  }
+  if (BrotliGetAvailableBits(br) == 0) {
+    if (!BrotliPullByte(br)) {
+      return BROTLI_FALSE;
+    }
+  }
+
+  while ((((size_t)br->next_in) & aligned_read_mask) != 0) {
+    if (!BrotliPullByte(br)) {
+      /* If we consumed all the input, we don't care about the alignment. */
+      return BROTLI_TRUE;
+    }
+  }
+  return BROTLI_TRUE;
+}
+
+#if defined(__cplusplus) || defined(c_plusplus)
+}  /* extern "C" */
+#endif
diff --git a/c/dec/bit_reader.h b/c/dec/bit_reader.h
new file mode 100644
index 0000000..30e6761
--- /dev/null
+++ b/c/dec/bit_reader.h
@@ -0,0 +1,360 @@
+/* Copyright 2013 Google Inc. All Rights Reserved.
+
+   Distributed under MIT license.
+   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
+*/
+
+/* Bit reading helpers */
+
+#ifndef BROTLI_DEC_BIT_READER_H_
+#define BROTLI_DEC_BIT_READER_H_
+
+#include <string.h>  /* memcpy */
+
+#include <brotli/types.h>
+#include "./port.h"
+
+#if defined(__cplusplus) || defined(c_plusplus)
+extern "C" {
+#endif
+
+#define BROTLI_SHORT_FILL_BIT_WINDOW_READ (sizeof(reg_t) >> 1)
+
+static const uint32_t kBitMask[33] = { 0x0000,
+    0x00000001, 0x00000003, 0x00000007, 0x0000000F,
+    0x0000001F, 0x0000003F, 0x0000007F, 0x000000FF,
+    0x000001FF, 0x000003FF, 0x000007FF, 0x00000FFF,
+    0x00001FFF, 0x00003FFF, 0x00007FFF, 0x0000FFFF,
+    0x0001FFFF, 0x0003FFFF, 0x0007FFFF, 0x000FFFFF,
+    0x001FFFFF, 0x003FFFFF, 0x007FFFFF, 0x00FFFFFF,
+    0x01FFFFFF, 0x03FFFFFF, 0x07FFFFFF, 0x0FFFFFFF,
+    0x1FFFFFFF, 0x3FFFFFFF, 0x7FFFFFFF, 0xFFFFFFFF
+};
+
+static BROTLI_INLINE uint32_t BitMask(uint32_t n) {
+  if (IS_CONSTANT(n) || BROTLI_HAS_UBFX) {
+    /* Masking with this expression turns to a single
+       "Unsigned Bit Field Extract" UBFX instruction on ARM. */
+    return ~((0xffffffffU) << n);
+  } else {
+    return kBitMask[n];
+  }
+}
+
+typedef struct {
+  reg_t val_;              /* pre-fetched bits */
+  uint32_t bit_pos_;       /* current bit-reading position in val_ */
+  const uint8_t* next_in;  /* the byte we're reading from */
+  size_t avail_in;
+} BrotliBitReader;
+
+typedef struct {
+  reg_t val_;
+  uint32_t bit_pos_;
+  const uint8_t* next_in;
+  size_t avail_in;
+} BrotliBitReaderState;
+
+/* Initializes the BrotliBitReader fields. */
+BROTLI_INTERNAL void BrotliInitBitReader(BrotliBitReader* const br);
+
+/* Ensures that accumulator is not empty. May consume one byte of input.
+   Returns 0 if data is required but there is no input available.
+   For BROTLI_ALIGNED_READ this function also prepares bit reader for aligned
+   reading. */
+BROTLI_INTERNAL BROTLI_BOOL BrotliWarmupBitReader(BrotliBitReader* const br);
+
+static BROTLI_INLINE void BrotliBitReaderSaveState(
+    BrotliBitReader* const from, BrotliBitReaderState* to) {
+  to->val_ = from->val_;
+  to->bit_pos_ = from->bit_pos_;
+  to->next_in = from->next_in;
+  to->avail_in = from->avail_in;
+}
+
+static BROTLI_INLINE void BrotliBitReaderRestoreState(
+    BrotliBitReader* const to, BrotliBitReaderState* from) {
+  to->val_ = from->val_;
+  to->bit_pos_ = from->bit_pos_;
+  to->next_in = from->next_in;
+  to->avail_in = from->avail_in;
+}
+
+static BROTLI_INLINE uint32_t BrotliGetAvailableBits(
+    const BrotliBitReader* br) {
+  return (BROTLI_64_BITS ? 64 : 32) - br->bit_pos_;
+}
+
+/* Returns amount of unread bytes the bit reader still has buffered from the
+   BrotliInput, including whole bytes in br->val_. */
+static BROTLI_INLINE size_t BrotliGetRemainingBytes(BrotliBitReader* br) {
+  return br->avail_in + (BrotliGetAvailableBits(br) >> 3);
+}
+
+/* Checks if there is at least |num| bytes left in the input ring-buffer
+   (excluding the bits remaining in br->val_). */
+static BROTLI_INLINE BROTLI_BOOL BrotliCheckInputAmount(
+    BrotliBitReader* const br, size_t num) {
+  return TO_BROTLI_BOOL(br->avail_in >= num);
+}
+
+static BROTLI_INLINE uint16_t BrotliLoad16LE(const uint8_t* in) {
+  if (BROTLI_LITTLE_ENDIAN) {
+    return *((const uint16_t*)in);
+  } else if (BROTLI_BIG_ENDIAN) {
+    uint16_t value = *((const uint16_t*)in);
+    return (uint16_t)(((value & 0xFFU) << 8) | ((value & 0xFF00U) >> 8));
+  } else {
+    return (uint16_t)(in[0] | (in[1] << 8));
+  }
+}
+
+static BROTLI_INLINE uint32_t BrotliLoad32LE(const uint8_t* in) {
+  if (BROTLI_LITTLE_ENDIAN) {
+    return *((const uint32_t*)in);
+  } else if (BROTLI_BIG_ENDIAN) {
+    uint32_t value = *((const uint32_t*)in);
+    return ((value & 0xFFU) << 24) | ((value & 0xFF00U) << 8) |
+        ((value & 0xFF0000U) >> 8) | ((value & 0xFF000000U) >> 24);
+  } else {
+    uint32_t value = (uint32_t)(*(in++));
+    value |= (uint32_t)(*(in++)) << 8;
+    value |= (uint32_t)(*(in++)) << 16;
+    value |= (uint32_t)(*(in++)) << 24;
+    return value;
+  }
+}
+
+#if (BROTLI_64_BITS)
+static BROTLI_INLINE uint64_t BrotliLoad64LE(const uint8_t* in) {
+  if (BROTLI_LITTLE_ENDIAN) {
+    return *((const uint64_t*)in);
+  } else if (BROTLI_BIG_ENDIAN) {
+    uint64_t value = *((const uint64_t*)in);
+    return
+        ((value & 0xFFU) << 56) |
+        ((value & 0xFF00U) << 40) |
+        ((value & 0xFF0000U) << 24) |
+        ((value & 0xFF000000U) << 8) |
+        ((value & 0xFF00000000U) >> 8) |
+        ((value & 0xFF0000000000U) >> 24) |
+        ((value & 0xFF000000000000U) >> 40) |
+        ((value & 0xFF00000000000000U) >> 56);
+  } else {
+    uint64_t value = (uint64_t)(*(in++));
+    value |= (uint64_t)(*(in++)) << 8;
+    value |= (uint64_t)(*(in++)) << 16;
+    value |= (uint64_t)(*(in++)) << 24;
+    value |= (uint64_t)(*(in++)) << 32;
+    value |= (uint64_t)(*(in++)) << 40;
+    value |= (uint64_t)(*(in++)) << 48;
+    value |= (uint64_t)(*(in++)) << 56;
+    return value;
+  }
+}
+#endif
+
+/* Guarantees that there are at least n_bits + 1 bits in accumulator.
+   Precondition: accumulator contains at least 1 bit.
+   n_bits should be in the range [1..24] for regular build. For portable
+   non-64-bit little-endian build only 16 bits are safe to request. */
+static BROTLI_INLINE void BrotliFillBitWindow(
+    BrotliBitReader* const br, uint32_t n_bits) {
+#if (BROTLI_64_BITS)
+  if (!BROTLI_ALIGNED_READ && IS_CONSTANT(n_bits) && (n_bits <= 8)) {
+    if (br->bit_pos_ >= 56) {
+      br->val_ >>= 56;
+      br->bit_pos_ ^= 56;  /* here same as -= 56 because of the if condition */
+      br->val_ |= BrotliLoad64LE(br->next_in) << 8;
+      br->avail_in -= 7;
+      br->next_in += 7;
+    }
+  } else if (!BROTLI_ALIGNED_READ && IS_CONSTANT(n_bits) && (n_bits <= 16)) {
+    if (br->bit_pos_ >= 48) {
+      br->val_ >>= 48;
+      br->bit_pos_ ^= 48;  /* here same as -= 48 because of the if condition */
+      br->val_ |= BrotliLoad64LE(br->next_in) << 16;
+      br->avail_in -= 6;
+      br->next_in += 6;
+    }
+  } else {
+    if (br->bit_pos_ >= 32) {
+      br->val_ >>= 32;
+      br->bit_pos_ ^= 32;  /* here same as -= 32 because of the if condition */
+      br->val_ |= ((uint64_t)BrotliLoad32LE(br->next_in)) << 32;
+      br->avail_in -= BROTLI_SHORT_FILL_BIT_WINDOW_READ;
+      br->next_in += BROTLI_SHORT_FILL_BIT_WINDOW_READ;
+    }
+  }
+#else
+  if (!BROTLI_ALIGNED_READ && IS_CONSTANT(n_bits) && (n_bits <= 8)) {
+    if (br->bit_pos_ >= 24) {
+      br->val_ >>= 24;
+      br->bit_pos_ ^= 24;  /* here same as -= 24 because of the if condition */
+      br->val_ |= BrotliLoad32LE(br->next_in) << 8;
+      br->avail_in -= 3;
+      br->next_in += 3;
+    }
+  } else {
+    if (br->bit_pos_ >= 16) {
+      br->val_ >>= 16;
+      br->bit_pos_ ^= 16;  /* here same as -= 16 because of the if condition */
+      br->val_ |= ((uint32_t)BrotliLoad16LE(br->next_in)) << 16;
+      br->avail_in -= BROTLI_SHORT_FILL_BIT_WINDOW_READ;
+      br->next_in += BROTLI_SHORT_FILL_BIT_WINDOW_READ;
+    }
+  }
+#endif
+}
+
+/* Mostly like BrotliFillBitWindow, but guarantees only 16 bits and reads no
+   more than BROTLI_SHORT_FILL_BIT_WINDOW_READ bytes of input. */
+static BROTLI_INLINE void BrotliFillBitWindow16(BrotliBitReader* const br) {
+  BrotliFillBitWindow(br, 17);
+}
+
+/* Pulls one byte of input to accumulator. */
+static BROTLI_INLINE BROTLI_BOOL BrotliPullByte(BrotliBitReader* const br) {
+  if (br->avail_in == 0) {
+    return BROTLI_FALSE;
+  }
+  br->val_ >>= 8;
+#if (BROTLI_64_BITS)
+  br->val_ |= ((uint64_t)*br->next_in) << 56;
+#else
+  br->val_ |= ((uint32_t)*br->next_in) << 24;
+#endif
+  br->bit_pos_ -= 8;
+  --br->avail_in;
+  ++br->next_in;
+  return BROTLI_TRUE;
+}
+
+/* Returns currently available bits.
+   The number of valid bits could be calculated by BrotliGetAvailableBits. */
+static BROTLI_INLINE reg_t BrotliGetBitsUnmasked(BrotliBitReader* const br) {
+  return br->val_ >> br->bit_pos_;
+}
+
+/* Like BrotliGetBits, but does not mask the result.
+   The result contains at least 16 valid bits. */
+static BROTLI_INLINE uint32_t BrotliGet16BitsUnmasked(
+    BrotliBitReader* const br) {
+  BrotliFillBitWindow(br, 16);
+  return (uint32_t)BrotliGetBitsUnmasked(br);
+}
+
+/* Returns the specified number of bits from |br| without advancing bit pos. */
+static BROTLI_INLINE uint32_t BrotliGetBits(
+    BrotliBitReader* const br, uint32_t n_bits) {
+  BrotliFillBitWindow(br, n_bits);
+  return (uint32_t)BrotliGetBitsUnmasked(br) & BitMask(n_bits);
+}
+
+/* Tries to peek the specified amount of bits. Returns 0, if there is not
+   enough input. */
+static BROTLI_INLINE BROTLI_BOOL BrotliSafeGetBits(
+    BrotliBitReader* const br, uint32_t n_bits, uint32_t* val) {
+  while (BrotliGetAvailableBits(br) < n_bits) {
+    if (!BrotliPullByte(br)) {
+      return BROTLI_FALSE;
+    }
+  }
+  *val = (uint32_t)BrotliGetBitsUnmasked(br) & BitMask(n_bits);
+  return BROTLI_TRUE;
+}
+
+/* Advances the bit pos by n_bits. */
+static BROTLI_INLINE void BrotliDropBits(
+    BrotliBitReader* const br, uint32_t n_bits) {
+  br->bit_pos_ += n_bits;
+}
+
+static BROTLI_INLINE void BrotliBitReaderUnload(BrotliBitReader* br) {
+  uint32_t unused_bytes = BrotliGetAvailableBits(br) >> 3;
+  uint32_t unused_bits = unused_bytes << 3;
+  br->avail_in += unused_bytes;
+  br->next_in -= unused_bytes;
+  if (unused_bits == sizeof(br->val_) << 3) {
+    br->val_ = 0;
+  } else {
+    br->val_ <<= unused_bits;
+  }
+  br->bit_pos_ += unused_bits;
+}
+
+/* Reads the specified number of bits from |br| and advances the bit pos.
+   Precondition: accumulator MUST contain at least n_bits. */
+static BROTLI_INLINE void BrotliTakeBits(
+  BrotliBitReader* const br, uint32_t n_bits, uint32_t* val) {
+  *val = (uint32_t)BrotliGetBitsUnmasked(br) & BitMask(n_bits);
+  BROTLI_LOG(("[BrotliReadBits]  %d %d %d val: %6x\n",
+      (int)br->avail_in, (int)br->bit_pos_, n_bits, (int)*val));
+  BrotliDropBits(br, n_bits);
+}
+
+/* Reads the specified number of bits from |br| and advances the bit pos.
+   Assumes that there is enough input to perform BrotliFillBitWindow. */
+static BROTLI_INLINE uint32_t BrotliReadBits(
+    BrotliBitReader* const br, uint32_t n_bits) {
+  if (BROTLI_64_BITS || (n_bits <= 16)) {
+    uint32_t val;
+    BrotliFillBitWindow(br, n_bits);
+    BrotliTakeBits(br, n_bits, &val);
+    return val;
+  } else {
+    uint32_t low_val;
+    uint32_t high_val;
+    BrotliFillBitWindow(br, 16);
+    BrotliTakeBits(br, 16, &low_val);
+    BrotliFillBitWindow(br, 8);
+    BrotliTakeBits(br, n_bits - 16, &high_val);
+    return low_val | (high_val << 16);
+  }
+}
+
+/* Tries to read the specified amount of bits. Returns 0, if there is not
+   enough input. n_bits MUST be positive. */
+static BROTLI_INLINE BROTLI_BOOL BrotliSafeReadBits(
+    BrotliBitReader* const br, uint32_t n_bits, uint32_t* val) {
+  while (BrotliGetAvailableBits(br) < n_bits) {
+    if (!BrotliPullByte(br)) {
+      return BROTLI_FALSE;
+    }
+  }
+  BrotliTakeBits(br, n_bits, val);
+  return BROTLI_TRUE;
+}
+
+/* Advances the bit reader position to the next byte boundary and verifies
+   that any skipped bits are set to zero. */
+static BROTLI_INLINE BROTLI_BOOL BrotliJumpToByteBoundary(BrotliBitReader* br) {
+  uint32_t pad_bits_count = BrotliGetAvailableBits(br) & 0x7;
+  uint32_t pad_bits = 0;
+  if (pad_bits_count != 0) {
+    BrotliTakeBits(br, pad_bits_count, &pad_bits);
+  }
+  return TO_BROTLI_BOOL(pad_bits == 0);
+}
+
+/* Copies remaining input bytes stored in the bit reader to the output. Value
+   num may not be larger than BrotliGetRemainingBytes. The bit reader must be
+   warmed up again after this. */
+static BROTLI_INLINE void BrotliCopyBytes(uint8_t* dest,
+                                          BrotliBitReader* br, size_t num) {
+  while (BrotliGetAvailableBits(br) >= 8 && num > 0) {
+    *dest = (uint8_t)BrotliGetBitsUnmasked(br);
+    BrotliDropBits(br, 8);
+    ++dest;
+    --num;
+  }
+  memcpy(dest, br->next_in, num);
+  br->avail_in -= num;
+  br->next_in += num;
+}
+
+#if defined(__cplusplus) || defined(c_plusplus)
+}  /* extern "C" */
+#endif
+
+#endif  /* BROTLI_DEC_BIT_READER_H_ */
diff --git a/c/dec/context.h b/c/dec/context.h
new file mode 100644
index 0000000..9402cbe
--- /dev/null
+++ b/c/dec/context.h
@@ -0,0 +1,251 @@
+/* Copyright 2013 Google Inc. All Rights Reserved.
+
+   Distributed under MIT license.
+   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
+*/
+
+/* Lookup table to map the previous two bytes to a context id.
+
+   There are four different context modeling modes defined here:
+     CONTEXT_LSB6: context id is the least significant 6 bits of the last byte,
+     CONTEXT_MSB6: context id is the most significant 6 bits of the last byte,
+     CONTEXT_UTF8: second-order context model tuned for UTF8-encoded text,
+     CONTEXT_SIGNED: second-order context model tuned for signed integers.
+
+   The context id for the UTF8 context model is calculated as follows. If p1
+   and p2 are the previous two bytes, we calculate the context as
+
+     context = kContextLookup[p1] | kContextLookup[p2 + 256].
+
+   If the previous two bytes are ASCII characters (i.e. < 128), this will be
+   equivalent to
+
+     context = 4 * context1(p1) + context2(p2),
+
+   where context1 is based on the previous byte in the following way:
+
+     0  : non-ASCII control
+     1  : \t, \n, \r
+     2  : space
+     3  : other punctuation
+     4  : " '
+     5  : %
+     6  : ( < [ {
+     7  : ) > ] }
+     8  : , ; :
+     9  : .
+     10 : =
+     11 : number
+     12 : upper-case vowel
+     13 : upper-case consonant
+     14 : lower-case vowel
+     15 : lower-case consonant
+
+   and context2 is based on the second last byte:
+
+     0 : control, space
+     1 : punctuation
+     2 : upper-case letter, number
+     3 : lower-case letter
+
+   If the last byte is ASCII, and the second last byte is not (in a valid UTF8
+   stream it will be a continuation byte, value between 128 and 191), the
+   context is the same as if the second last byte was an ASCII control or space.
+
+   If the last byte is a UTF8 lead byte (value >= 192), then the next byte will
+   be a continuation byte and the context id is 2 or 3 depending on the LSB of
+   the last byte and to a lesser extent on the second last byte if it is ASCII.
+
+   If the last byte is a UTF8 continuation byte, the second last byte can be:
+     - continuation byte: the next byte is probably ASCII or lead byte (assuming
+       4-byte UTF8 characters are rare) and the context id is 0 or 1.
+     - lead byte (192 - 207): next byte is ASCII or lead byte, context is 0 or 1
+     - lead byte (208 - 255): next byte is continuation byte, context is 2 or 3
+
+   The possible value combinations of the previous two bytes, the range of
+   context ids and the type of the next byte is summarized in the table below:
+
+   |--------\-----------------------------------------------------------------|
+   |         \                         Last byte                              |
+   | Second   \---------------------------------------------------------------|
+   | last byte \    ASCII            |   cont. byte        |   lead byte      |
+   |            \   (0-127)          |   (128-191)         |   (192-)         |
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+   |  (208-)     |                   |  context: 2 - 3     |                  |
+   |-------------|-------------------|---------------------|------------------|
+
+   The context id for the signed context mode is calculated as:
+
+     context = (kContextLookup[512 + p1] << 3) | kContextLookup[512 + p2].
+
+   For any context modeling modes, the context ids can be calculated by |-ing
+   together two lookups from one table using context model dependent offsets:
+
+     context = kContextLookup[offset1 + p1] | kContextLookup[offset2 + p2].
+
+   where offset1 and offset2 are dependent on the context mode.
+*/
+
+#ifndef BROTLI_DEC_CONTEXT_H_
+#define BROTLI_DEC_CONTEXT_H_
+
+#include <brotli/types.h>
+
+enum ContextType {
+  CONTEXT_LSB6 = 0,
+  CONTEXT_MSB6 = 1,
+  CONTEXT_UTF8 = 2,
+  CONTEXT_SIGNED = 3
+};
+
+/* Common context lookup table for all context modes. */
+static const uint8_t kContextLookup[1792] = {
+  /* CONTEXT_UTF8, last byte. */
+  /* ASCII range. */
+   0,  0,  0,  0,  0,  0,  0,  0,  0,  4,  4,  0,  0,  4,  0,  0,
+   0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
+   8, 12, 16, 12, 12, 20, 12, 16, 24, 28, 12, 12, 32, 12, 36, 12,
+  44, 44, 44, 44, 44, 44, 44, 44, 44, 44, 32, 32, 24, 40, 28, 12,
+  12, 48, 52, 52, 52, 48, 52, 52, 52, 48, 52, 52, 52, 52, 52, 48,
+  52, 52, 52, 52, 52, 48, 52, 52, 52, 52, 52, 24, 12, 28, 12, 12,
+  12, 56, 60, 60, 60, 56, 60, 60, 60, 56, 60, 60, 60, 60, 60, 56,
+  60, 60, 60, 60, 60, 56, 60, 60, 60, 60, 60, 24, 12, 28, 12,  0,
+  /* UTF8 continuation byte range. */
+  0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1,
+  0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1,
+  0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1,
+  0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1,
+  /* UTF8 lead byte range. */
+  2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3,
+  2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3,
+  2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3,
+  2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3,
+  /* CONTEXT_UTF8 second last byte. */
+  /* ASCII range. */
+  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
+  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
+  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
+  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
+  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
+};
+
+static const int kContextLookupOffsets[8] = {
+  /* CONTEXT_LSB6 */
+  1024, 1536,
+  /* CONTEXT_MSB6 */
+  1280, 1536,
+  /* CONTEXT_UTF8 */
+  0, 256,
+  /* CONTEXT_SIGNED */
+  768, 512,
+};
+
+#endif  /* BROTLI_DEC_CONTEXT_H_ */
diff --git a/c/dec/decode.c b/c/dec/decode.c
new file mode 100644
index 0000000..8e3dc02
--- /dev/null
+++ b/c/dec/decode.c
@@ -0,0 +1,2365 @@
+/* Copyright 2013 Google Inc. All Rights Reserved.
+
+   Distributed under MIT license.
+   See file LICENSE for detail or copy at https://opensource.org/licenses/MIT
+*/
+
+#include <brotli/decode.h>
+
+#ifdef __ARM_NEON__
+#include <arm_neon.h>
+#endif
+
+#include <stdlib.h>  /* free, malloc */
+#include <string.h>  /* memcpy, memset */
+
+#include "../common/constants.h"
+#include "../common/dictionary.h"
+#include "../common/version.h"
+#include "./bit_reader.h"
+#include "./context.h"
+#include "./huffman.h"
+#include "./port.h"
+#include "./prefix.h"
+#include "./state.h"
+#include "./transform.h"
+
+#if defined(__cplusplus) || defined(c_plusplus)
+extern "C" {
+#endif
+
+#define BROTLI_FAILURE(CODE) (BROTLI_DUMP(), CODE)
+
+#define BROTLI_LOG_UINT(name)                                       \
+  BROTLI_LOG(("[%s] %s = %lu\n", __func__, #name, (unsigned long)(name)))
+#define BROTLI_LOG_ARRAY_INDEX(array_name, idx)                     \
+  BROTLI_LOG(("[%s] %s[%lu] = %lu\n", __func__, #array_name,        \
+         (unsigned long)(idx), (unsigned long)array_name[idx]))
+
+#define HUFFMAN_TABLE_BITS 8U
+#define HUFFMAN_TABLE_MASK 0xff
+
+static const uint8_t kCodeLengthCodeOrder[BROTLI_CODE_LENGTH_CODES] = {
+  1, 2, 3, 4, 0, 5, 17, 6, 16, 7, 8, 9, 10, 11, 12, 13, 14, 15,
+};
+
+/* Static prefix code for the complex code length code lengths. */
+static const uint8_t kCodeLengthPrefixLength[16] = {
+  2, 2, 2, 3, 2, 2, 2, 4, 2, 2, 2, 3, 2, 2, 2, 4,
+};
+
+static const uint8_t kCodeLengthPrefixValue[16] = {
+  0, 4, 3, 2, 0, 4, 3, 1, 0, 4, 3, 2, 0, 4, 3, 5,
+};
+
+BrotliDecoderState* BrotliDecoderCreateInstance(
+    brotli_alloc_func alloc_func, brotli_free_func free_func, void* opaque) {
+  BrotliDecoderState* state = 0;
+  if (!alloc_func && !free_func) {
+    state = (BrotliDecoderState*)malloc(sizeof(BrotliDecoderState));
+  } else if (alloc_func && free_func) {
+    state = (BrotliDecoderState*)alloc_func(opaque, sizeof(BrotliDecoderState));
+  }
+  if (state == 0) {
+    BROTLI_DUMP();
+    return 0;
+  }
+  BrotliDecoderStateInitWithCustomAllocators(
+      state, alloc_func, free_func, opaque);
+  state->error_code = BROTLI_DECODER_NO_ERROR;
+  return state;
+}
+
+/* Deinitializes and frees BrotliDecoderState instance. */
+void BrotliDecoderDestroyInstance(BrotliDecoderState* state) {
+  if (!state) {
+    return;
+  } else {
+    brotli_free_func free_func = state->free_func;
+    void* opaque = state->memory_manager_opaque;
+    BrotliDecoderStateCleanup(state);
+    free_func(opaque, state);
+  }
+}
+
+/* Saves error code and converts it to BrotliDecoderResult */
+static BROTLI_NOINLINE BrotliDecoderResult SaveErrorCode(
+    BrotliDecoderState* s, BrotliDecoderErrorCode e) {
+  s->error_code = (int)e;
+  switch (e) {
+    case BROTLI_DECODER_SUCCESS:
+      return BROTLI_DECODER_RESULT_SUCCESS;
+    case BROTLI_DECODER_NEEDS_MORE_INPUT:
+      return BROTLI_DECODER_RESULT_NEEDS_MORE_INPUT;
+    case BROTLI_DECODER_NEEDS_MORE_OUTPUT:
+      return BROTLI_DECODER_RESULT_NEEDS_MORE_OUTPUT;
+    default:
+      return BROTLI_DECODER_RESULT_ERROR;
+  }
+}
+
+/* Decodes a number in the range [9..24], by reading 1 - 7 bits.
+   Precondition: bit-reader accumulator has at least 7 bits. */
+static uint32_t DecodeWindowBits(BrotliBitReader* br) {
+  uint32_t n;
+  BrotliTakeBits(br, 1, &n);
+  if (n == 0) {
+    return 16;
+  }
+  BrotliTakeBits(br, 3, &n);
+  if (n != 0) {
+    return 17 + n;
+  }
+  BrotliTakeBits(br, 3, &n);
+  if (n != 0) {
+    return 8 + n;
+  }
+  return 17;
+}
+
+static BROTLI_INLINE void memmove16(uint8_t* dst, uint8_t* src) {
+#if defined(__ARM_NEON__)
+  vst1q_u8(dst, vld1q_u8(src));
+#else
+  uint32_t buffer[4];
+  memcpy(buffer, src, 16);
+  memcpy(dst, buffer, 16);
+#endif
+}
+
+/* Decodes a number in the range [0..255], by reading 1 - 11 bits. */
+static BROTLI_NOINLINE BrotliDecoderErrorCode DecodeVarLenUint8(
+    BrotliDecoderState* s, BrotliBitReader* br, uint32_t* value) {
+  uint32_t bits;
+  switch (s->substate_decode_uint8) {
+    case BROTLI_STATE_DECODE_UINT8_NONE:
+      if (BROTLI_PREDICT_FALSE(!BrotliSafeReadBits(br, 1, &bits))) {
+        return BROTLI_DECODER_NEEDS_MORE_INPUT;
+      }
+      if (bits == 0) {
+        *value = 0;
+        return BROTLI_DECODER_SUCCESS;
+      }
+      /* No break, transit to the next state. */
+
+    case BROTLI_STATE_DECODE_UINT8_SHORT:
+      if (BROTLI_PREDICT_FALSE(!BrotliSafeReadBits(br, 3, &bits))) {
+        s->substate_decode_uint8 = BROTLI_STATE_DECODE_UINT8_SHORT;
+        return BROTLI_DECODER_NEEDS_MORE_INPUT;
+      }
+      if (bits == 0) {
+        *value = 1;
+        s->substate_decode_uint8 = BROTLI_STATE_DECODE_UINT8_NONE;
+        return BROTLI_DECODER_SUCCESS;
+      }
+      /* Use output value as a temporary storage. It MUST be persisted. */
+      *value = bits;
+      /* No break, transit to the next state. */
+
+    case BROTLI_STATE_DECODE_UINT8_LONG:
+      if (BROTLI_PREDICT_FALSE(!BrotliSafeReadBits(br, *value, &bits))) {
+        s->substate_decode_uint8 = BROTLI_STATE_DECODE_UINT8_LONG;
+        return BROTLI_DECODER_NEEDS_MORE_INPUT;
+      }
+      *value = (1U << *value) + bits;
+      s->substate_decode_uint8 = BROTLI_STATE_DECODE_UINT8_NONE;
+      return BROTLI_DECODER_SUCCESS;
+
+    default:
+      return
+          BROTLI_FAILURE(BROTLI_DECODER_ERROR_UNREACHABLE);
+  }
+}
+
+/* Decodes a metablock length and flags by reading 2 - 31 bits. */
+static BrotliDecoderErrorCode BROTLI_NOINLINE DecodeMetaBlockLength(
+    BrotliDecoderState* s, BrotliBitReader* br) {
+  uint32_t bits;
+  int i;
+  for (;;) {
+    switch (s->substate_metablock_header) {
+      case BROTLI_STATE_METABLOCK_HEADER_NONE:
+        if (!BrotliSafeReadBits(br, 1, &bits)) {
+          return BROTLI_DECODER_NEEDS_MORE_INPUT;
+        }
+        s->is_last_metablock = bits ? 1 : 0;
+        s->meta_block_remaining_len = 0;
+        s->is_uncompressed = 0;
+        s->is_metadata = 0;
+        if (!s->is_last_metablock) {
+          s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_NIBBLES;
+          break;
+        }
+        s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_EMPTY;
+        /* No break, transit to the next state. */
+
+      case BROTLI_STATE_METABLOCK_HEADER_EMPTY:
+        if (!BrotliSafeReadBits(br, 1, &bits)) {
+          return BROTLI_DECODER_NEEDS_MORE_INPUT;
+        }
+        if (bits) {
+          s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_NONE;
+          return BROTLI_DECODER_SUCCESS;
+        }
+        s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_NIBBLES;
+        /* No break, transit to the next state. */
+
+      case BROTLI_STATE_METABLOCK_HEADER_NIBBLES:
+        if (!BrotliSafeReadBits(br, 2, &bits)) {
+          return BROTLI_DECODER_NEEDS_MORE_INPUT;
+        }
+        s->size_nibbles = (uint8_t)(bits + 4);
+        s->loop_counter = 0;
+        if (bits == 3) {
+          s->is_metadata = 1;
+          s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_RESERVED;
+          break;
+        }
+        s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_SIZE;
+        /* No break, transit to the next state. */
+
+      case BROTLI_STATE_METABLOCK_HEADER_SIZE:
+        i = s->loop_counter;
+        for (; i < (int)s->size_nibbles; ++i) {
+          if (!BrotliSafeReadBits(br, 4, &bits)) {
+            s->loop_counter = i;
+            return BROTLI_DECODER_NEEDS_MORE_INPUT;
+          }
+          if (i + 1 == s->size_nibbles && s->size_nibbles > 4 && bits == 0) {
+            return BROTLI_FAILURE(BROTLI_DECODER_ERROR_FORMAT_EXUBERANT_NIBBLE);
+          }
+          s->meta_block_remaining_len |= (int)(bits << (i * 4));
+        }
+        s->substate_metablock_header =
+            BROTLI_STATE_METABLOCK_HEADER_UNCOMPRESSED;
+        /* No break, transit to the next state. */
+
+      case BROTLI_STATE_METABLOCK_HEADER_UNCOMPRESSED:
+        if (!s->is_last_metablock) {
+          if (!BrotliSafeReadBits(br, 1, &bits)) {
+            return BROTLI_DECODER_NEEDS_MORE_INPUT;
+          }
+          s->is_uncompressed = bits ? 1 : 0;
+        }
+        ++s->meta_block_remaining_len;
+        s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_NONE;
+        return BROTLI_DECODER_SUCCESS;
+
+      case BROTLI_STATE_METABLOCK_HEADER_RESERVED:
+        if (!BrotliSafeReadBits(br, 1, &bits)) {
+          return BROTLI_DECODER_NEEDS_MORE_INPUT;
+        }
+        if (bits != 0) {
+          return BROTLI_FAILURE(BROTLI_DECODER_ERROR_FORMAT_RESERVED);
+        }
+        s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_BYTES;
+        /* No break, transit to the next state. */
+
+      case BROTLI_STATE_METABLOCK_HEADER_BYTES:
+        if (!BrotliSafeReadBits(br, 2, &bits)) {
+          return BROTLI_DECODER_NEEDS_MORE_INPUT;
+        }
+        if (bits == 0) {
+          s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_NONE;
+          return BROTLI_DECODER_SUCCESS;
+        }
+        s->size_nibbles = (uint8_t)bits;
+        s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_METADATA;
+        /* No break, transit to the next state. */
+
+      case BROTLI_STATE_METABLOCK_HEADER_METADATA:
+        i = s->loop_counter;
+        for (; i < (int)s->size_nibbles; ++i) {
+          if (!BrotliSafeReadBits(br, 8, &bits)) {
+            s->loop_counter = i;
+            return BROTLI_DECODER_NEEDS_MORE_INPUT;
+          }
+          if (i + 1 == s->size_nibbles && s->size_nibbles > 1 && bits == 0) {
+            return BROTLI_FAILURE(
+                BROTLI_DECODER_ERROR_FORMAT_EXUBERANT_META_NIBBLE);
+          }
+          s->meta_block_remaining_len |= (int)(bits << (i * 8));
+        }
+        ++s->meta_block_remaining_len;
+        s->substate_metablock_header = BROTLI_STATE_METABLOCK_HEADER_NONE;
+        return BROTLI_DECODER_SUCCESS;
+
+      default:
+        return
+            BROTLI_FAILURE(BROTLI_DECODER_ERROR_UNREACHABLE);
+    }
+  }
+}
+
+/* Decodes the Huffman code.
+   This method doesn't read data from the bit reader, BUT drops the amount of
+   bits that correspond to the decoded symbol.
+   bits MUST contain at least 15 (BROTLI_HUFFMAN_MAX_CODE_LENGTH) valid bits. */
+static BROTLI_INLINE uint32_t DecodeSymbol(uint32_t bits,
+                                           const HuffmanCode* table,
+                                           BrotliBitReader* br) {
+  table += bits & HUFFMAN_TABLE_MASK;
+  if (table->bits > HUFFMAN_TABLE_BITS) {
+    uint32_t nbits = table->bits - HUFFMAN_TABLE_BITS;
+    BrotliDropBits(br, HUFFMAN_TABLE_BITS);
+    table += table->value;
+    table += (bits >> HUFFMAN_TABLE_BITS) & BitMask(nbits);
+  }
+  BrotliDropBits(br, table->bits);
+  return table->value;
+}
+
+/* Reads and decodes the next Huffman code from bit-stream.
+   This method peeks 16 bits of input and drops 0 - 15 of them. */
+static BROTLI_INLINE uint32_t ReadSymbol(const HuffmanCode* table,
+                                         BrotliBitReader* br) {
+  return DecodeSymbol(BrotliGet16BitsUnmasked(br), table, br);
+}
+
+/* Same as DecodeSymbol, but it is known that there is less than 15 bits of
+   input are currently available. */
+static BROTLI_NOINLINE BROTLI_BOOL SafeDecodeSymbol(
+    const HuffmanCode* table, BrotliBitReader* br, uint32_t* result) {
+  uint32_t val;
+  uint32_t available_bits = BrotliGetAvailableBits(br);
+  if (available_bits == 0) {
+    if (table->bits == 0) {
+      *result = table->value;
+      return BROTLI_TRUE;
+    }
+    return BROTLI_FALSE; /* No valid bits at all. */
+  }
+  val = (uint32_t)BrotliGetBitsUnmasked(br);
+  table += val & HUFFMAN_TABLE_MASK;
+  if (table->bits <= HUFFMAN_TABLE_BITS) {
+    if (table->bits <= available_bits) {
+      BrotliDropBits(br, table->bits);
+      *result = table->value;
+      return BROTLI_TRUE;
+    } else {
+      return BROTLI_FALSE; /* Not enough bits for the first level. */
+    }
+  }
+  if (available_bits <= HUFFMAN_TABLE_BITS) {
+    return BROTLI_FALSE; /* Not enough bits to move to the second level. */
+  }
+
+  /* Speculatively drop HUFFMAN_TABLE_BITS. */
+  val = (val & BitMask(table->bits)) >> HUFFMAN_TABLE_BITS;
+  available_bits -= HUFFMAN_TABLE_BITS;
+  table += table->value + val;
+  if (available_bits < table->bits) {
+    return BROTLI_FALSE; /* Not enough bits for the second level. */
+  }
+
+  BrotliDropBits(br, HUFFMAN_TABLE_BITS + table->bits);
+  *result = table->value;
+  return BROTLI_TRUE;
+}
+
+static BROTLI_INLINE BROTLI_BOOL SafeReadSymbol(
+    const HuffmanCode* table, BrotliBitReader* br, uint32_t* result) {
+  uint32_t val;
+  if (BROTLI_PREDICT_TRUE(BrotliSafeGetBits(br, 15, &val))) {
+    *result = DecodeSymbol(val, table, br);
+    return BROTLI_TRUE;
+  }
+  return SafeDecodeSymbol(table, br, result);
+}
+
+/* Makes a look-up in first level Huffman table. Peeks 8 bits. */
+static BROTLI_INLINE void PreloadSymbol(int safe,
+                                        const HuffmanCode* table,
+                                        BrotliBitReader* br,
+                                        uint32_t* bits,
+                                        uint32_t* value) {
+  if (safe) {
+    return;
+  }
+  table += BrotliGetBits(br, HUFFMAN_TABLE_BITS);
+  *bits = table->bits;
+  *value = table->value;
+}
+
+/* Decodes the next Huffman code using data prepared by PreloadSymbol.
+   Reads 0 - 15 bits. Also peeks 8 following bits. */
+static BROTLI_INLINE uint32_t ReadPreloadedSymbol(const HuffmanCode* table,
+                                                  BrotliBitReader* br,
+                                                  uint32_t* bits,
+                                                  uint32_t* value) {
+  uint32_t result = *value;
+  if (BROTLI_PREDICT_FALSE(*bits > HUFFMAN_TABLE_BITS)) {
+    uint32_t val = BrotliGet16BitsUnmasked(br);
+    const HuffmanCode* ext = table + (val & HUFFMAN_TABLE_MASK) + *value;
+    uint32_t mask = BitMask((*bits - HUFFMAN_TABLE_BITS));
+    BrotliDropBits(br, HUFFMAN_TABLE_BITS);
+    ext += (val >> HUFFMAN_TABLE_BITS) & mask;
+    BrotliDropBits(br, ext->bits);
+    result = ext->value;
+  } else {
+    BrotliDropBits(br, *bits);
+  }
+  PreloadSymbol(0, table, br, bits, value);
+  return result;
+}
+
+static BROTLI_INLINE uint32_t Log2Floor(uint32_t x) {
+  uint32_t result = 0;
+  while (x) {
+    x >>= 1;
+    ++result;
+  }
+  return result;
+}
+
+/* Reads (s->symbol + 1) symbols.
+   Totally 1..4 symbols are read, 1..10 bits each.
+   The list of symbols MUST NOT contain duplicates.
+ */
+static BrotliDecoderErrorCode ReadSimpleHuffmanSymbols(
+    uint32_t alphabet_size, BrotliDecoderState* s) {
+  /* max_bits == 1..10; symbol == 0..3; 1..40 bits will be read. */
+  BrotliBitReader* br = &s->br;
+  uint32_t max_bits = Log2Floor(alphabet_size - 1);
+  uint32_t i = s->sub_loop_counter;
+  uint32_t num_symbols = s->symbol;
+  while (i <= num_symbols) {
+    uint32_t v;
+    if (BROTLI_PREDICT_FALSE(!BrotliSafeReadBits(br, max_bits, &v))) {
+      s->sub_loop_counter = i;
+      s->substate_huffman = BROTLI_STATE_HUFFMAN_SIMPLE_READ;
+      return BROTLI_DECODER_NEEDS_MORE_INPUT;
+    }
+    if (v >= alphabet_size) {
+      return
+          BROTLI_FAILURE(BROTLI_DECODER_ERROR_FORMAT_SIMPLE_HUFFMAN_ALPHABET);
+    }
+    s->symbols_lists_array[i] = (uint16_t)v;
+    BROTLI_LOG_UINT(s->symbols_lists_array[i]);
+    ++i;
+  }
+
+  for (i = 0; i < num_symbols; ++i) {
+    uint32_t k = i + 1;
+    for (; k <= num_symbols; ++k) {
+      if (s->symbols_lists_array[i] == s->symbols_lists_array[k]) {
+        return BROTLI_FAILURE(BROTLI_DECODER_ERROR_FORMAT_SIMPLE_HUFFMAN_SAME);
+      }
+    }
+  }
+
+  return BROTLI_DECODER_SUCCESS;
+}
+
+/* Process single decoded symbol code length:
+    A) reset the repeat variable
+    B) remember code length (if it is not 0)
+    C) extend corresponding index-chain
+    D) reduce the Huffman space
+    E) update the histogram
+ */
+static BROTLI_INLINE void ProcessSingleCodeLength(uint32_t code_len,
+    uint32_t* symbol, uint32_t* repeat, uint32_t* space,
+    uint32_t* prev_code_len, uint16_t* symbol_lists,
+    uint16_t* code_length_histo, int* next_symbol) {
+  *repeat = 0;
+  if (code_len != 0) { /* code_len == 1..15 */
+    symbol_lists[next_symbol[code_len]] = (uint16_t)(*symbol);
+    next_symbol[code_len] = (int)(*symbol);
+    *prev_code_len = code_len;
+    *space -= 32768U >> code_len;
+    code_length_histo[code_len]++;
+    BROTLI_LOG(("[ReadHuffmanCode] code_length[%d] = %d\n", *symbol, code_len));
+  }
+  (*symbol)++;
+}
+
+/* Process repeated symbol code length.
+    A) Check if it is the extension of previous repeat sequence; if the decoded
+       value is not BROTLI_REPEAT_PREVIOUS_CODE_LENGTH, then it is a new
+       symbol-skip
+    B) Update repeat variable
+    C) Check if operation is feasible (fits alphabet)
+    D) For each symbol do the same operations as in ProcessSingleCodeLength
+
+   PRECONDITION: code_len == BROTLI_REPEAT_PREVIOUS_CODE_LENGTH or
+                 code_len == BROTLI_REPEAT_ZERO_CODE_LENGTH
+ */
+static BROTLI_INLINE void ProcessRepeatedCodeLength(uint32_t code_len,
+    uint32_t repeat_delta, uint32_t alphabet_size, uint32_t* symbol,
+    uint32_t* repeat, uint32_t* space, uint32_t* prev_code_len,
+    uint32_t* repeat_code_len, uint16_t* symbol_lists,
+    uint16_t* code_length_histo, int* next_symbol) {
+  uint32_t old_repeat;
+  uint32_t extra_bits = 3;  /* for BROTLI_REPEAT_ZERO_CODE_LENGTH */
+  uint32_t new_len = 0;  /* for BROTLI_REPEAT_ZERO_CODE_LENGTH */
+  if (code_len == BROTLI_REPEAT_PREVIOUS_CODE_LENGTH) {
+    new_len = *prev_code_len;
+    extra_bits = 2;
+  }
+  if (*repeat_code_len != new_len) {
+    *repeat = 0;
+    *repeat_code_len = new_len;
+  }
+  old_repeat = *repeat;
+  if (*repeat > 0) {
+    *repeat -= 2;
+    *repeat <<= extra_bits;
+  }
+  *repeat += repeat_delta + 3U;
+  repeat_delta = *repeat - old_repeat;
+  if (*symbol + repeat_delta > alphabet_size) {
+    BROTLI_DUMP();
+    *symbol = alphabet_size;
+    *space = 0xFFFFF;
+    return;
+  }
+  BROTLI_LOG(("[ReadHuffmanCode] code_length[%d..%d] = %d\n",
+              *symbol, *symbol + repeat_delta - 1, *repeat_code_len));
+  if (*repeat_code_len != 0) {
+    unsigned last = *symbol + repeat_delta;
+    int next = next_symbol[*repeat_code_len];
+    do {
+      symbol_lists[next] = (uint16_t)*symbol;
+      next = (int)*symbol;
+    } while (++(*symbol) != last);
+    next_symbol[*repeat_code_len] = next;
+    *space -= repeat_delta << (15 - *repeat_code_len);
+    code_length_histo[*repeat_code_len] =
+        (uint16_t)(code_length_histo[*repeat_code_len] + repeat_delta);
+  } else {
+    *symbol += repeat_delta;
+  }
+}
+
+/* Reads and decodes symbol codelengths. */
+static BrotliDecoderErrorCode ReadSymbolCodeLengths(
+    uint32_t alphabet_size, BrotliDecoderState* s) {
+  BrotliBitReader* br = &s->br;
+  uint32_t symbol = s->symbol;
+  uint32_t repeat = s->repeat;
+  uint32_t space = s->space;
+  uint32_t prev_code_len = s->prev_code_len;
+  uint32_t repeat_code_len = s->repeat_code_len;
+  uint16_t* symbol_lists = s->symbol_lists;
+  uint16_t* code_length_histo = s->code_length_histo;
+  int* next_symbol = s->next_symbol;
+  if (!BrotliWarmupBitReader(br)) {
+    return BROTLI_DECODER_NEEDS_MORE_INPUT;
+  }
+  while (symbol < alphabet_size && space > 0) {
+    const HuffmanCode* p = s->table;
+    uint32_t code_len;
+    if (!BrotliCheckInputAmount(br, BROTLI_SHORT_FILL_BIT_WINDOW_READ)) {
+      s->symbol = symbol;
+      s->repeat = repeat;
+      s->prev_code_len = prev_code_len;
+      s->repeat_code_len = repeat_code_len;
+      s->space = space;
+      return BROTLI_DECODER_NEEDS_MORE_INPUT;
+    }
+    BrotliFillBitWindow16(br);
+    p += BrotliGetBitsUnmasked(br) &
+        BitMask(BROTLI_HUFFMAN_MAX_CODE_LENGTH_CODE_LENGTH);
+    BrotliDropBits(br, p->bits);  /* Use 1..5 bits */
+    code_len = p->value;  /* code_len == 0..17 */
+    if (code_len < BROTLI_REPEAT_PREVIOUS_CODE_LENGTH) {
+      ProcessSingleCodeLength(code_len, &symbol, &repeat, &space,
+          &prev_code_len, symbol_lists, code_length_histo, next_symbol);
+    } else { /* code_len == 16..17, extra_bits == 2..3 */
+      uint32_t extra_bits =
+          (code_len == BROTLI_REPEAT_PREVIOUS_CODE_LENGTH) ? 2 : 3;
+      uint32_t repeat_delta =
+          (uint32_t)BrotliGetBitsUnmasked(br) & BitMask(extra_bits);
+      BrotliDropBits(br, extra_bits);
+      ProcessRepeatedCodeLength(code_len, repeat_delta, alphabet_size,
+          &symbol, &repeat, &space, &prev_code_len, &repeat_code_len,
+          symbol_lists, code_length_histo, next_symbol);
+    }
+  }
+  s->space = space;
+  return BROTLI_DECODER_SUCCESS;
+}
+
+static BrotliDecoderErrorCode SafeReadSymbolCodeLengths(
+    uint32_t alphabet_size, BrotliDecoderState* s) {
+  BrotliBitReader* br = &s->br;
+  BROTLI_BOOL get_byte = BROTLI_FALSE;
+  while (s->symbol < alphabet_size && s->space > 0) {
+    const HuffmanCode* p = s->table;
+    uint32_t code_len;
+    uint32_t available_bits;
+    uint32_t bits = 0;
+    if (get_byte && !BrotliPullByte(br)) return BROTLI_DECODER_NEEDS_MORE_INPUT;
+    get_byte = BROTLI_FALSE;
+    available_bits = BrotliGetAvailableBits(br);
+    if (available_bits != 0) {
+      bits = (uint32_t)BrotliGetBitsUnmasked(br);
+    }
+    p += bits & BitMask(BROTLI_HUFFMAN_MAX_CODE_LENGTH_CODE_LENGTH);
+    if (p->bits > available_bits) {
+      get_byte = BROTLI_TRUE;
+      continue;
+    }
+    code_len = p->value; /* code_len == 0..17 */
+    if (code_len < BROTLI_REPEAT_PREVIOUS_CODE_LENGTH) {
+      BrotliDropBits(br, p->bits);
+      ProcessSingleCodeLength(code_len, &s->symbol, &s->repeat, &s->space,
+          &s->prev_code_len, s->symbol_lists, s->code_length_histo,
+          s->next_symbol);
+    } else { /* code_len == 16..17, extra_bits == 2..3 */
+      uint32_t extra_bits = code_len - 14U;
+      uint32_t repeat_delta = (bits >> p->bits) & BitMask(extra_bits);
+      if (available_bits < p->bits + extra_bits) {
+        get_byte = BROTLI_TRUE;
+        continue;
+      }
+      BrotliDropBits(br, p->bits + extra_bits);
+      ProcessRepeatedCodeLength(code_len, repeat_delta, alphabet_size,
+          &s->symbol, &s->repeat, &s->space, &s->prev_code_len,
+          &s->repeat_code_len, s->symbol_lists, s->code_length_histo,
+          s->next_symbol);
+    }
+  }
+  return BROTLI_DECODER_SUCCESS;
+}
+
+/* Reads and decodes 15..18 codes using static prefix code.
+   Each code is 2..4 bits long. In total 30..72 bits are used. */
+static BrotliDecoderErrorCode ReadCodeLengthCodeLengths(BrotliDecoderState* s) {
+  BrotliBitReader* br = &s->br;
+  uint32_t num_codes = s->repeat;
+  unsigned space = s->space;
+  uint32_t i = s->sub_loop_counter;
+  for (; i < BROTLI_CODE_LENGTH_CODES; ++i) {
+    const uint8_t code_len_idx = kCodeLengthCodeOrder[i];
+    uint32_t ix;
+    uint32_t v;
+    if (BROTLI_PREDICT_FALSE(!BrotliSafeGetBits(br, 4, &ix))) {
+      uint32_t available_bits = BrotliGetAvailableBits(br);
+      if (available_bits != 0) {
+        ix = BrotliGetBitsUnmasked(br) & 0xF;
+      } else {
+        ix = 0;
+      }
+      if (kCodeLengthPrefixLength[ix] > available_bits) {
+        s->sub_loop_counter = i;
+        s->repeat = num_codes;
+        s->space = space;
+        s->substate_huffman = BROTLI_STATE_HUFFMAN_COMPLEX;
+        return BROTLI_DECODER_NEEDS_MORE_INPUT;
+      }
+    }
+    v = kCodeLengthPrefixValue[ix];
+    BrotliDropBits(br, kCodeLengthPrefixLength[ix]);
+    s->code_length_code_lengths[code_len_idx] = (uint8_t)v;
+    BROTLI_LOG_ARRAY_INDEX(s->code_length_code_lengths, code_len_idx);
+    if (v != 0) {
+      space = space - (32U >> v);
+      ++num_codes;
+      ++s->code_length_histo[v];
+      if (space - 1U >= 32U) {
+        /* space is 0 or wrapped around */
+        break;
+      }
+    }
+  }
+  if (!(num_codes == 1 || space == 0)) {
+    return BROTLI_FAILURE(BROTLI_DECODER_ERROR_FORMAT_CL_SPACE);
+  }
+  return BROTLI_DECODER_SUCCESS;
+}
+
+/* Decodes the Huffman tables.
+   There are 2 scenarios:
+    A) Huffman code contains only few symbols (1..4). Those symbols are read
+       directly; their code lengths are defined by the number of symbols.
+       For this scenario 4 - 45 bits will be read.
+
+    B) 2-phase decoding:
+    B.1) Small Huffman table is decoded; it is specified with code lengths
+         encoded with predefined entropy code. 32 - 74 bits are used.
+    B.2) Decoded table is used to decode code lengths of symbols in resulting
+         Huffman table. In worst case 3520 bits are read.
+*/
+static BrotliDecoderErrorCode ReadHuffmanCode(uint32_t alphabet_size,
+                                              HuffmanCode* table,
+                                              uint32_t* opt_table_size,
+                                              BrotliDecoderState* s) {
+  BrotliBitReader* br = &s->br;
+  /* Unnecessary masking, but might be good for safety. */
+  alphabet_size &= 0x3ff;
+  /* State machine */
+  for (;;) {
+    switch (s->substate_huffman) {
+      case BROTLI_STATE_HUFFMAN_NONE:
+        if (!BrotliSafeReadBits(br, 2, &s->sub_loop_counter)) {
+          return BROTLI_DECODER_NEEDS_MORE_INPUT;
+        }
+        BROTLI_LOG_UINT(s->sub_loop_counter);
+        /* The value is used as follows:
+           1 for simple code;
+           0 for no skipping, 2 skips 2 code lengths, 3 skips 3 code lengths */
+        if (s->sub_loop_counter != 1) {
+          s->space = 32;
+          s->repeat = 0; /* num_codes */
+          memset(&s->code_length_histo[0], 0, sizeof(s->code_length_histo[0]) *
+              (BROTLI_HUFFMAN_MAX_CODE_LENGTH_CODE_LENGTH + 1));
+          memset(&s->code_length_code_lengths[0], 0,
+              sizeof(s->code_length_code_lengths));
+          s->substate_huffman = BROTLI_STATE_HUFFMAN_COMPLEX;
+          continue;
+        }
+        /* No break, transit to the next state. */
+
+      case BROTLI_STATE_HUFFMAN_SIMPLE_SIZE:
+        /* Read symbols, codes & code lengths directly. */
+        if (!BrotliSafeReadBits(br, 2, &s->symbol)) { /* num_symbols */
+          s->substate_huffman = BROTLI_STATE_HUFFMAN_SIMPLE_SIZE;
+          return BROTLI_DECODER_NEEDS_MORE_INPUT;
+        }
+        s->sub_loop_counter = 0;
+        /* No break, transit to the next state. */
+      case BROTLI_STATE_HUFFMAN_SIMPLE_READ: {
+        BrotliDecoderErrorCode result =
+            ReadSimpleHuffmanSymbols(alphabet_size, s);
+        if (result != BROTLI_DECODER_SUCCESS) {
+          return result;
+        }
+        /* No break, transit to the next state. */
+      }
+      case BROTLI_STATE_HUFFMAN_SIMPLE_BUILD: {
+        uint32_t table_size;
+        if (s->symbol == 3) {
+          uint32_t bits;
+          if (!BrotliSafeReadBits(br, 1, &bits)) {
+            s->substate_huffman = BROTLI_STATE_HUFFMAN_SIMPLE_BUILD;
+            return BROTLI_DECODER_NEEDS_MORE_INPUT;
+          }
+          s->symbol += bits;
+        }
+        BROTLI_LOG_UINT(s->symbol);
+        table_size = BrotliBuildSimpleHuffmanTable(
+            table, HUFFMAN_TABLE_BITS, s->symbols_lists_array, s->symbol);
+        if (opt_table_size) {
+          *opt_table_size = table_size;
+        }
+        s->substate_huffman = BROTLI_STATE_HUFFMAN_NONE;
+        return BROTLI_DECODER_SUCCESS;
+      }
+
+      /* Decode Huffman-coded code lengths. */
+      case BROTLI_STATE_HUFFMAN_COMPLEX: {
+        uint32_t i;
+        BrotliDecoderErrorCode result = ReadCodeLengthCodeLengths(s);
+        if (result != BROTLI_DECODER_SUCCESS) {
+          return result;
+        }
+        BrotliBuildCodeLengthsHuffmanTable(s->table,
+                                           s->code_length_code_lengths,
+                                           s->code_length_histo);
+        memset(&s->code_length_histo[0], 0, sizeof(s->code_length_histo));
+        for (i = 0; i <= BROTLI_HUFFMAN_MAX_CODE_LENGTH; ++i) {
+          s->next_symbol[i] = (int)i - (BROTLI_HUFFMAN_MAX_CODE_LENGTH + 1);
+          s->symbol_lists[s->next_symbol[i]] = 0xFFFF;
+        }
+
+        s->symbol = 0;
+        s->prev_code_len = BROTLI_INITIAL_REPEATED_CODE_LENGTH;
+        s->repeat = 0;
+        s->repeat_code_len = 0;
+        s->space = 32768;
+        s->substate_huffman = BROTLI_STATE_HUFFMAN_LENGTH_SYMBOLS;
+        /* No break, transit to the next state. */
+      }
+      case BROTLI_STATE_HUFFMAN_LENGTH_SYMBOLS: {
+        uint32_t table_size;
+        BrotliDecoderErrorCode result = ReadSymbolCodeLengths(alphabet_size, s);
+        if (result == BROTLI_DECODER_NEEDS_MORE_INPUT) {
+          result = SafeReadSymbolCodeLengths(alphabet_size, s);
+        }
+        if (result != BROTLI_DECODER_SUCCESS) {
+          return result;
+        }
+
+        if (s->space != 0) {
+          BROTLI_LOG(("[ReadHuffmanCode] space = %d\n", s->space));
+          return BROTLI_FAILURE(BROTLI_DECODER_ERROR_FORMAT_HUFFMAN_SPACE);
+        }
+        table_size = BrotliBuildHuffmanTable(
+            table, HUFFMAN_TABLE_BITS, s->symbol_lists, s->code_length_histo);
+        if (opt_table_size) {
+          *opt_table_size = table_size;
+        }
+        s->substate_huffman = BROTLI_STATE_HUFFMAN_NONE;
+        return BROTLI_DECODER_SUCCESS;
+      }
+
+      default:
+        return
+            BROTLI_FAILURE(BROTLI_DECODER_ERROR_UNREACHABLE);
+    }
+  }
+}
+
+/* Decodes a block length by reading 3..39 bits. */
+static BROTLI_INLINE uint32_t ReadBlockLength(const HuffmanCode* table,
+                                              BrotliBitReader* br) {
+  uint32_t code;
+  uint32_t nbits;
+  code = ReadSymbol(table, br);
+  nbits = kBlockLengthPrefixCode[code].nbits; /* nbits == 2..24 */
+  return kBlockLengthPrefixCode[code].offset + BrotliReadBits(br, nbits);
+}
+
+/* WARNING: if state is not BROTLI_STATE_READ_BLOCK_LENGTH_NONE, then
+   reading can't be continued with ReadBlockLength. */
+static BROTLI_INLINE BROTLI_BOOL SafeReadBlockLength(
+    BrotliDecoderState* s, uint32_t* result, const HuffmanCode* table,
+    BrotliBitReader* br) {
+  uint32_t index;
+  if (s->substate_read_block_length == BROTLI_STATE_READ_BLOCK_LENGTH_NONE) {
+    if (!SafeReadSymbol(table, br, &index)) {
+      return BROTLI_FALSE;
+    }
+  } else {
+    index = s->block_length_index;
+  }
+  {
+    uint32_t bits;
+    uint32_t nbits = kBlockLengthPrefixCode[index].nbits; /* nbits == 2..24 */
+    if (!BrotliSafeReadBits(br, nbits, &bits)) {
+      s->block_length_index = index;
+      s->substate_read_block_length = BROTLI_STATE_READ_BLOCK_LENGTH_SUFFIX;
+      return BROTLI_FALSE;
+    }
+    *result = kBlockLengthPrefixCode[index].offset + bits;
+    s->substate_read_block_length = BROTLI_STATE_READ_BLOCK_LENGTH_NONE;
+    return BROTLI_TRUE;
+  }
+}
+
+/* Transform:
+    1) initialize list L with values 0, 1,... 255
+    2) For each input element X:
+    2.1) let Y = L[X]
+    2.2) remove X-th element from L
+    2.3) prepend Y to L
+    2.4) append Y to output
+
+   In most cases max(Y) <= 7, so most of L remains intact.
+   To reduce the cost of initialization, we reuse L, remember the upper bound
+   of Y values, and reinitialize only first elements in L.
+
+   Most of input values are 0 and 1. To reduce number of branches, we replace
+   inner for loop with do-while.
+ */
+static BROTLI_NOINLINE void InverseMoveToFrontTransform(
+    uint8_t* v, uint32_t v_len, BrotliDecoderState* state) {
+  /* Reinitialize elements that could have been changed. */
+  uint32_t i = 1;
+  uint32_t upper_bound = state->mtf_upper_bound;
+  uint32_t* mtf = &state->mtf[1];  /* Make mtf[-1] addressable. */
+  uint8_t* mtf_u8 = (uint8_t*)mtf;
+  /* Load endian-aware constant. */
+  const uint8_t b0123[4] = {0, 1, 2, 3};
+  uint32_t pattern;
+  memcpy(&pattern, &b0123, 4);
+
+  /* Initialize list using 4 consequent values pattern. */
+  mtf[0] = pattern;
+  do {
+    pattern += 0x04040404; /* Advance all 4 values by 4. */
+    mtf[i] = pattern;
+    i++;
+  } while (i <= upper_bound);
+
+  /* Transform the input. */
+  upper_bound = 0;
+  for (i = 0; i < v_len; ++i) {
+    int index = v[i];
+    uint8_t value = mtf_u8[index];
+    upper_bound |= v[i];
+    v[i] = value;
+    mtf_u8[-1] = value;
+    do {
+      index--;
+      mtf_u8[index + 1] = mtf_u8[index];
+    } while (index >= 0);
+  }
+  /* Remember amount of elements to be reinitialized. */
+  state->mtf_upper_bound = upper_bound >> 2;
+}
+
+/* Decodes a series of Huffman table using ReadHuffmanCode function. */
+static BrotliDecoderErrorCode HuffmanTreeGroupDecode(
+    HuffmanTreeGroup* group, BrotliDecoderState* s) {
+  if (s->substate_tree_group != BROTLI_STATE_TREE_GROUP_LOOP) {
+    s->next = group->codes;
+    s->htree_index = 0;
+    s->substate_tree_group = BROTLI_STATE_TREE_GROUP_LOOP;
+  }
+  while (s->htree_index < group->num_htrees) {
+    uint32_t table_size;
+    BrotliDecoderErrorCode result =
+        ReadHuffmanCode(group->alphabet_size, s->next, &table_size, s);
+    if (result != BROTLI_DECODER_SUCCESS) return result;
+    group->htrees[s->htree_index] = s->next;
+    s->next += table_size;
+    ++s->htree_index;
+  }
+  s->substate_tree_group = BROTLI_STATE_TREE_GROUP_NONE;
+  return BROTLI_DECODER_SUCCESS;
+}
+
+/* Decodes a context map.
+   Decoding is done in 4 phases:
+    1) Read auxiliary information (6..16 bits) and allocate memory.
+       In case of trivial context map, decoding is finished at this phase.
+    2) Decode Huffman table using ReadHuffmanCode function.
+       This table will be used for reading context map items.
+    3) Read context map items; "0" values could be run-length encoded.
+    4) Optionally, apply InverseMoveToFront transform to the resulting map.
+ */
+static BrotliDecoderErrorCode DecodeContextMap(uint32_t context_map_size,
+                                               uint32_t* num_htrees,
+                                               uint8_t** context_map_arg,
+                                               BrotliDecoderState* s) {
+  BrotliBitReader* br = &s->br;
+  BrotliDecoderErrorCode result = BROTLI_DECODER_SUCCESS;
+
+  switch ((int)s->substate_context_map) {
+    case BROTLI_STATE_CONTEXT_MAP_NONE:
+      result = DecodeVarLenUint8(s, br, num_htrees);
+      if (result != BROTLI_DECODER_SUCCESS) {
+        return result;
+      }
+      (*num_htrees)++;
+      s->context_index = 0;
+      BROTLI_LOG_UINT(context_map_size);
+      BROTLI_LOG_UINT(*num_htrees);
+      *context_map_arg = (uint8_t*)BROTLI_ALLOC(s, (size_t)context_map_size);
+      if (*context_map_arg == 0) {
+        return BROTLI_FAILURE(BROTLI_DECODER_ERROR_ALLOC_CONTEXT_MAP);
+      }
+      if (*num_htrees <= 1) {
+        memset(*context_map_arg, 0, (size_t)context_map_size);
+        return BROTLI_DECODER_SUCCESS;
+      }
+      s->substate_context_map = BROTLI_STATE_CONTEXT_MAP_READ_PREFIX;
+      /* No break, continue to next state. */
+    case BROTLI_STATE_CONTEXT_MAP_READ_PREFIX: {
+      uint32_t bits;
+      /* In next stage ReadHuffmanCode uses at least 4 bits, so it is safe
+         to peek 4 bits ahead. */
+      if (!BrotliSafeGetBits(br, 5, &bits)) {
+        return BROTLI_DECODER_NEEDS_MORE_INPUT;
+      }
+      if ((bits & 1) != 0) { /* Use RLE for zeros. */
+        s->max_run_length_prefix = (bits >> 1) + 1;
+        BrotliDropBits(br, 5);
+      } else {
+        s->max_run_length_prefix = 0;
+        BrotliDropBits(br, 1);
+      }
+      BROTLI_LOG_UINT(s->max_run_length_prefix);
+      s->substate_context_map = BROTLI_STATE_CONTEXT_MAP_HUFFMAN;
+      /* No break, continue to next state. */
+    }
+    case BROTLI_STATE_CONTEXT_MAP_HUFFMAN:
+      result = ReadHuffmanCode(*num_htrees + s->max_run_length_prefix,
+                               s->context_map_table, NULL, s);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
