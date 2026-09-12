# Case ID

P041

## Existing Fuzz Harness H0

### `fuzz/c/std/gif_fuzzer.c`

~~~~c
// Copyright 2018 The Wuffs Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Silence the nested slash-star warning for the next comment's command line.
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wcomment"

/*
This fuzzer (the fuzz function) is typically run indirectly, by a framework
such as https://github.com/google/oss-fuzz calling LLVMFuzzerTestOneInput.

When working on the fuzz implementation, or as a sanity check, defining
WUFFS_CONFIG__FUZZLIB_MAIN will let you manually run fuzz over a set of files:

gcc -DWUFFS_CONFIG__FUZZLIB_MAIN gif_fuzzer.c
./a.out ../../../test/data/*.gif
rm -f ./a.out

It should print "PASS", amongst other information, and exit(0).
*/

#pragma clang diagnostic pop

// If building this program in an environment that doesn't easily accomodate
// relative includes, you can use the script/inline-c-relative-includes.go
// program to generate a stand-alone C file.
#include "../../../gen/c/base.c"
#include "../../../gen/c/std/gif.c"
#include "../../../gen/c/std/lzw.c"
#include "../fuzzlib/fuzzlib.c"

const char* fuzz(wuffs_base__io_reader src_reader, uint32_t hash) {
  const char* ret = NULL;
  void* pixbuf = NULL;

  // Use a {} code block so that "goto exit" doesn't trigger "jump bypasses
  // variable initialization" warnings.
  {
    wuffs_gif__status s = 0;
    wuffs_gif__decoder dec = ((wuffs_gif__decoder){});
    wuffs_gif__decoder__check_wuffs_version(&dec, sizeof dec, WUFFS_VERSION);

    wuffs_base__image_buffer ib = ((wuffs_base__image_buffer){});
    wuffs_base__image_config ic = ((wuffs_base__image_config){});
    s = wuffs_gif__decoder__decode_config(&dec, &ic, src_reader);
    if (s) {
      ret = wuffs_gif__status__string(s);
      goto exit;
    }
    if (!wuffs_base__image_config__is_valid(&ic)) {
      ret = "invalid image_config";
      goto exit;
    }

    size_t pixbuf_size = wuffs_base__image_config__pixbuf_size(&ic);
    // Don't try to allocate more than 64 MiB.
    if (pixbuf_size > 64 * 1024 * 1024) {
      ret = "image too large";
      goto exit;
    }
    pixbuf = malloc(pixbuf_size);
    if (!pixbuf) {
      ret = "out of memory";
      goto exit;
    }
    // TODO: check wuffs_base__image_buffer__set_from_slice errors?
    wuffs_base__image_buffer__set_from_slice(
        &ib, ic, ((wuffs_base__slice_u8){.ptr = pixbuf, .len = pixbuf_size}));

    bool seen_ok = false;
    while (true) {
      s = wuffs_gif__decoder__decode_frame(&dec, &ib, src_reader);
      if (s) {
        if ((s == WUFFS_GIF__SUSPENSION_END_OF_DATA) && seen_ok) {
          s = WUFFS_GIF__STATUS_OK;
        }
        ret = wuffs_gif__status__string(s);
        goto exit;
      }
      seen_ok = true;
    }
  }

exit:
  if (pixbuf) {
    free(pixbuf);
  }
  return ret;
}
~~~~
### `fuzz/c/std/zlib_fuzzer.c`

~~~~c
// Copyright 2018 The Wuffs Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Silence the nested slash-star warning for the next comment's command line.
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wcomment"

/*
This fuzzer (the fuzz function) is typically run indirectly, by a framework
such as https://github.com/google/oss-fuzz calling LLVMFuzzerTestOneInput.

When working on the fuzz implementation, or as a sanity check, defining
WUFFS_CONFIG__FUZZLIB_MAIN will let you manually run fuzz over a set of files:

gcc -DWUFFS_CONFIG__FUZZLIB_MAIN zlib_fuzzer.c
./a.out ../../../test/data/*.zlib
rm -f ./a.out

It should print "PASS", amongst other information, and exit(0).
*/

#pragma clang diagnostic pop

// If building this program in an environment that doesn't easily accomodate
// relative includes, you can use the script/inline-c-relative-includes.go
// program to generate a stand-alone C file.
#include "../../../gen/c/base.c"
#include "../../../gen/c/std/adler32.c"
#include "../../../gen/c/std/deflate.c"
#include "../../../gen/c/std/zlib.c"
#include "../fuzzlib/fuzzlib.c"

const char* fuzz(wuffs_base__io_reader src_reader, uint32_t hash) {
  const char* ret = NULL;
  wuffs_zlib__status s = 0;
  wuffs_zlib__decoder dec = ((wuffs_zlib__decoder){});
  wuffs_zlib__decoder__check_wuffs_version(&dec, sizeof dec, WUFFS_VERSION);

  // Ignore the checksum for 99.99%-ish of all input. When fuzzers generate
  // random input, the checkum is very unlikely to match. Still, it's useful to
  // verify that checksumming does not lead to e.g. buffer overflows.
  wuffs_zlib__decoder__set_ignore_checksum(&dec, hash & 0xFFFF);

  const size_t dstbuf_size = 65536;
  uint8_t dstbuf[dstbuf_size];
  wuffs_base__io_buffer dst = {.ptr = dstbuf, .len = dstbuf_size};
  wuffs_base__io_writer dst_writer = wuffs_base__io_buffer__writer(&dst);

  while (true) {
    dst.wi = 0;
    s = wuffs_zlib__decoder__decode(&dec, dst_writer, src_reader);
    if (s != WUFFS_ZLIB__SUSPENSION_SHORT_WRITE) {
      ret = wuffs_zlib__status__string(s);
      break;
    }
    if (dst.wi == 0) {
      fprintf(stderr, "wuffs_zlib__decoder__decode made no progress\n");
      intentional_segfault();
    }
  }
  return ret;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/gen/c/std/adler32.c b/gen/c/std/adler32.c
index d0eafda2..7715227b 100644
--- a/gen/c/std/adler32.c
+++ b/gen/c/std/adler32.c
@@ -1269,8 +1269,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_adler32__status;
-
 #define wuffs_adler32__packageid 681002  // 0x000A642A
 
 #define WUFFS_ADLER32__STATUS_OK 0                          // 0x00000000
@@ -1292,9 +1290,7 @@ typedef int32_t wuffs_adler32__status;
 #define WUFFS_ADLER32__ERROR_INVALID_CALL_SEQUENCE -301989888  // 0xEE000000
 #define WUFFS_ADLER32__SUSPENSION_END_OF_DATA 16777216         // 0x01000000
 
-bool wuffs_adler32__status__is_error(wuffs_adler32__status s);
-
-const char* wuffs_adler32__status__string(wuffs_adler32__status s);
+const char* wuffs_adler32__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1309,7 +1305,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_adler32__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_state;
@@ -1894,10 +1890,6 @@ static inline wuffs_base__empty_struct wuffs_base__io_writer__set_mark(
 
 // ---------------- Status Codes Implementations
 
-bool wuffs_adler32__status__is_error(wuffs_adler32__status s) {
-  return s < 0;
-}
-
 static const char wuffs_adler32__status__string_data[] = {
     0x00,
 };
@@ -1934,7 +1926,7 @@ static const uint16_t wuffs_adler32__status__string_offsets[] = {
     0x0000, 0x0000, 0x0000, 0x0000,
 };
 
-const char* wuffs_adler32__status__string(wuffs_adler32__status s) {
+const char* wuffs_adler32__status__string(wuffs_base__status s) {
   uint16_t o;
   switch (s & 0x1FFFFF) {
     case 0:
diff --git a/gen/c/std/crc32.c b/gen/c/std/crc32.c
index 665d4e9d..147217b6 100644
--- a/gen/c/std/crc32.c
+++ b/gen/c/std/crc32.c
@@ -1269,8 +1269,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_crc32__status;
-
 #define wuffs_crc32__packageid 810620  // 0x000C5E7C
 
 #define WUFFS_CRC32__STATUS_OK 0                          // 0x00000000
@@ -1291,9 +1289,7 @@ typedef int32_t wuffs_crc32__status;
 #define WUFFS_CRC32__ERROR_INVALID_CALL_SEQUENCE -301989888       // 0xEE000000
 #define WUFFS_CRC32__SUSPENSION_END_OF_DATA 16777216              // 0x01000000
 
-bool wuffs_crc32__status__is_error(wuffs_crc32__status s);
-
-const char* wuffs_crc32__status__string(wuffs_crc32__status s);
+const char* wuffs_crc32__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1308,7 +1304,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_crc32__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_state;
@@ -1893,10 +1889,6 @@ static inline wuffs_base__empty_struct wuffs_base__io_writer__set_mark(
 
 // ---------------- Status Codes Implementations
 
-bool wuffs_crc32__status__is_error(wuffs_crc32__status s) {
-  return s < 0;
-}
-
 static const char wuffs_crc32__status__string_data[] = {
     0x00,
 };
@@ -1933,7 +1925,7 @@ static const uint16_t wuffs_crc32__status__string_offsets[] = {
     0x0000, 0x0000, 0x0000, 0x0000,
 };
 
-const char* wuffs_crc32__status__string(wuffs_crc32__status s) {
+const char* wuffs_crc32__status__string(wuffs_base__status s) {
   uint16_t o;
   switch (s & 0x1FFFFF) {
     case 0:
diff --git a/gen/c/std/deflate.c b/gen/c/std/deflate.c
index 0799e481..688b67b1 100644
--- a/gen/c/std/deflate.c
+++ b/gen/c/std/deflate.c
@@ -1269,8 +1269,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_deflate__status;
-
 #define wuffs_deflate__packageid 848533  // 0x000CF295
 
 #define WUFFS_DEFLATE__STATUS_OK 0                          // 0x00000000
@@ -1321,9 +1319,7 @@ typedef int32_t wuffs_deflate__status;
 #define WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS \
   -1123224939  // 0xBD0CF295
 
-bool wuffs_deflate__status__is_error(wuffs_deflate__status s);
-
-const char* wuffs_deflate__status__string(wuffs_deflate__status s);
+const char* wuffs_deflate__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1338,7 +1334,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_deflate__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_bits;
@@ -1352,7 +1348,7 @@ typedef struct {
 
     struct {
       uint32_t coro_susp_point;
-      wuffs_deflate__status v_z;
+      wuffs_base__status v_z;
       uint64_t v_n_copied;
       uint32_t v_already_full;
     } c_decode[1];
@@ -1418,10 +1414,9 @@ void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
 
 // ---------------- Public Function Prototypes
 
-wuffs_deflate__status wuffs_deflate__decoder__decode(
-    wuffs_deflate__decoder* self,
-    wuffs_base__io_writer a_dst,
-    wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
+                                                  wuffs_base__io_writer a_dst,
+                                                  wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
@@ -1983,10 +1978,6 @@ static inline wuffs_base__empty_struct wuffs_base__io_writer__set_mark(
 
 // ---------------- Status Codes Implementations
 
-bool wuffs_deflate__status__is_error(wuffs_deflate__status s) {
-  return s < 0;
-}
-
 static const char wuffs_deflate__status__string_data[] = {
     0x00, 0x64, 0x65, 0x66, 0x6C, 0x61, 0x74, 0x65, 0x3A, 0x20, 0x69, 0x6E,
     0x74, 0x65, 0x72, 0x6E, 0x61, 0x6C, 0x20, 0x65, 0x72, 0x72, 0x6F, 0x72,
@@ -2078,7 +2069,7 @@ static const uint16_t wuffs_deflate__status__string_offsets[] = {
     0x01EF, 0x021B, 0x0242, 0x026F,
 };
 
-const char* wuffs_deflate__status__string(wuffs_deflate__status s) {
+const char* wuffs_deflate__status__string(wuffs_base__status s) {
   uint16_t o;
   switch (s & 0x1FFFFF) {
     case 0:
@@ -2140,36 +2131,36 @@ static const uint32_t wuffs_deflate__dcode_magic_numbers[32] = {
 
 // ---------------- Private Function Prototypes
 
-static wuffs_deflate__status wuffs_deflate__decoder__decode_blocks(
+static wuffs_base__status wuffs_deflate__decoder__decode_blocks(
     wuffs_deflate__decoder* self,
     wuffs_base__io_writer a_dst,
     wuffs_base__io_reader a_src);
 
-static wuffs_deflate__status wuffs_deflate__decoder__decode_uncompressed(
+static wuffs_base__status wuffs_deflate__decoder__decode_uncompressed(
     wuffs_deflate__decoder* self,
     wuffs_base__io_writer a_dst,
     wuffs_base__io_reader a_src);
 
-static wuffs_deflate__status wuffs_deflate__decoder__init_fixed_huffman(
+static wuffs_base__status wuffs_deflate__decoder__init_fixed_huffman(
     wuffs_deflate__decoder* self);
 
-static wuffs_deflate__status wuffs_deflate__decoder__init_dynamic_huffman(
+static wuffs_base__status wuffs_deflate__decoder__init_dynamic_huffman(
     wuffs_deflate__decoder* self,
     wuffs_base__io_reader a_src);
 
-static wuffs_deflate__status wuffs_deflate__decoder__init_huff(
+static wuffs_base__status wuffs_deflate__decoder__init_huff(
     wuffs_deflate__decoder* self,
     uint32_t a_which,
     uint32_t a_n_codes0,
     uint32_t a_n_codes1,
     uint32_t a_base_symbol);
 
-static wuffs_deflate__status wuffs_deflate__decoder__decode_huffman_fast(
+static wuffs_base__status wuffs_deflate__decoder__decode_huffman_fast(
     wuffs_deflate__decoder* self,
     wuffs_base__io_writer a_dst,
     wuffs_base__io_reader a_src);
 
-static wuffs_deflate__status wuffs_deflate__decoder__decode_huffman_slow(
+static wuffs_base__status wuffs_deflate__decoder__decode_huffman_slow(
     wuffs_deflate__decoder* self,
     wuffs_base__io_writer a_dst,
     wuffs_base__io_reader a_src);
@@ -2203,10 +2194,9 @@ void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
 
 // -------- func decoder.decode
 
-wuffs_deflate__status wuffs_deflate__decoder__decode(
-    wuffs_deflate__decoder* self,
-    wuffs_base__io_writer a_dst,
-    wuffs_base__io_reader a_src) {
+wuffs_base__status wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
+                                                  wuffs_base__io_writer a_dst,
+                                                  wuffs_base__io_reader a_src) {
   if (!self) {
     return WUFFS_DEFLATE__ERROR_BAD_RECEIVER;
   }
@@ -2217,9 +2207,9 @@ wuffs_deflate__status wuffs_deflate__decoder__decode(
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
   }
-  wuffs_deflate__status status = WUFFS_DEFLATE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
-  wuffs_deflate__status v_z;
+  wuffs_base__status v_z;
   wuffs_base__slice_u8 v_written;
   uint64_t v_n_copied;
   uint32_t v_already_full;
@@ -2261,7 +2251,7 @@ wuffs_deflate__status wuffs_deflate__decoder__decode(
         if (a_dst.private_impl.buf) {
           a_dst.private_impl.buf->wi = ioptr_dst - a_dst.private_impl.buf->ptr;
         }
-        wuffs_deflate__status t_0 =
+        wuffs_base__status t_0 =
             wuffs_deflate__decoder__decode_blocks(self, a_dst, a_src);
         if (a_dst.private_impl.buf) {
           ioptr_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
@@ -2342,11 +2332,11 @@ exit:
 
 // -------- func decoder.decode_blocks
 
-static wuffs_deflate__status wuffs_deflate__decoder__decode_blocks(
+static wuffs_base__status wuffs_deflate__decoder__decode_blocks(
     wuffs_deflate__decoder* self,
     wuffs_base__io_writer a_dst,
     wuffs_base__io_reader a_src) {
-  wuffs_deflate__status status = WUFFS_DEFLATE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_final;
   uint32_t v_type;
@@ -2497,11 +2487,11 @@ short_read_src:
 
 // -------- func decoder.decode_uncompressed
 
-static wuffs_deflate__status wuffs_deflate__decoder__decode_uncompressed(
+static wuffs_base__status wuffs_deflate__decoder__decode_uncompressed(
     wuffs_deflate__decoder* self,
     wuffs_base__io_writer a_dst,
     wuffs_base__io_reader a_src) {
-  wuffs_deflate__status status = WUFFS_DEFLATE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_length;
   uint32_t v_n_copied;
@@ -2643,9 +2633,9 @@ short_read_src:
 
 // -------- func decoder.init_fixed_huffman
 
-static wuffs_deflate__status wuffs_deflate__decoder__init_fixed_huffman(
+static wuffs_base__status wuffs_deflate__decoder__init_fixed_huffman(
     wuffs_deflate__decoder* self) {
-  wuffs_deflate__status status = WUFFS_DEFLATE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_i;
 
@@ -2708,10 +2698,10 @@ exit:
 
 // -------- func decoder.init_dynamic_huffman
 
-static wuffs_deflate__status wuffs_deflate__decoder__init_dynamic_huffman(
+static wuffs_base__status wuffs_deflate__decoder__init_dynamic_huffman(
     wuffs_deflate__decoder* self,
     wuffs_base__io_reader a_src) {
-  wuffs_deflate__status status = WUFFS_DEFLATE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_bits;
   uint32_t v_n_bits;
@@ -2968,13 +2958,13 @@ short_read_src:
 
 // -------- func decoder.init_huff
 
-static wuffs_deflate__status wuffs_deflate__decoder__init_huff(
+static wuffs_base__status wuffs_deflate__decoder__init_huff(
     wuffs_deflate__decoder* self,
     uint32_t a_which,
     uint32_t a_n_codes0,
     uint32_t a_n_codes1,
     uint32_t a_base_symbol) {
-  wuffs_deflate__status status = WUFFS_DEFLATE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint16_t v_counts[16];
   uint32_t v_i;
@@ -3249,11 +3239,11 @@ exit:
 
 // -------- func decoder.decode_huffman_fast
 
-static wuffs_deflate__status wuffs_deflate__decoder__decode_huffman_fast(
+static wuffs_base__status wuffs_deflate__decoder__decode_huffman_fast(
     wuffs_deflate__decoder* self,
     wuffs_base__io_writer a_dst,
     wuffs_base__io_reader a_src) {
-  wuffs_deflate__status status = WUFFS_DEFLATE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_bits;
   uint32_t v_n_bits;
@@ -3603,11 +3593,11 @@ exit:
 
 // -------- func decoder.decode_huffman_slow
 
-static wuffs_deflate__status wuffs_deflate__decoder__decode_huffman_slow(
+static wuffs_base__status wuffs_deflate__decoder__decode_huffman_slow(
     wuffs_deflate__decoder* self,
     wuffs_base__io_writer a_dst,
     wuffs_base__io_reader a_src) {
-  wuffs_deflate__status status = WUFFS_DEFLATE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_bits;
   uint32_t v_n_bits;
diff --git a/gen/c/std/gif.c b/gen/c/std/gif.c
index 706c96a9..7577b486 100644
--- a/gen/c/std/gif.c
+++ b/gen/c/std/gif.c
@@ -1278,8 +1278,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_lzw__status;
-
 #define wuffs_lzw__packageid 1316776  // 0x001417A8
 
 #define WUFFS_LZW__STATUS_OK 0                          // 0x00000000
@@ -1303,9 +1301,7 @@ typedef int32_t wuffs_lzw__status;
 #define WUFFS_LZW__ERROR_BAD_CODE -15460440               // 0xFF1417A8
 #define WUFFS_LZW__ERROR_CYCLICAL_PREFIX_CHAIN -32237656  // 0xFE1417A8
 
-bool wuffs_lzw__status__is_error(wuffs_lzw__status s);
-
-const char* wuffs_lzw__status__string(wuffs_lzw__status s);
+const char* wuffs_lzw__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1320,7 +1316,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_lzw__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_literal_width;
@@ -1362,9 +1358,9 @@ void wuffs_lzw__decoder__check_wuffs_version(wuffs_lzw__decoder* self,
 void wuffs_lzw__decoder__set_literal_width(wuffs_lzw__decoder* self,
                                            uint32_t a_lw);
 
-wuffs_lzw__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
-                                             wuffs_base__io_writer a_dst,
-                                             wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
+                                              wuffs_base__io_writer a_dst,
+                                              wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
@@ -1380,8 +1376,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_gif__status;
-
 #define wuffs_gif__packageid 1017222  // 0x000F8586
 
 #define WUFFS_GIF__STATUS_OK 0                          // 0x00000000
@@ -1412,9 +1406,7 @@ typedef int32_t wuffs_gif__status;
 #define WUFFS_GIF__ERROR_INTERNAL_ERROR_INCONSISTENT_RI_WI \
   -1072724602  // 0xC00F8586
 
-bool wuffs_gif__status__is_error(wuffs_gif__status s);
-
-const char* wuffs_gif__status__string(wuffs_gif__status s);
+const char* wuffs_gif__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1429,7 +1421,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_gif__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_width;
@@ -1522,7 +1514,7 @@ typedef struct {
       uint32_t v_argb;
       uint8_t v_lw;
       uint64_t v_block_size;
-      wuffs_gif__status v_z;
+      wuffs_base__status v_z;
       uint64_t scratch;
     } c_decode_id_part1[1];
   } private_impl;
@@ -1541,17 +1533,17 @@ void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
 
 // ---------------- Public Function Prototypes
 
-wuffs_gif__status wuffs_gif__decoder__decode_config(
+wuffs_base__status wuffs_gif__decoder__decode_config(
     wuffs_gif__decoder* self,
     wuffs_base__image_config* a_dst,
     wuffs_base__io_reader a_src);
 
-wuffs_gif__status wuffs_gif__decoder__decode_frame(
+wuffs_base__status wuffs_gif__decoder__decode_frame(
     wuffs_gif__decoder* self,
     wuffs_base__image_buffer* a_dst,
     wuffs_base__io_reader a_src);
 
-wuffs_gif__status wuffs_gif__decoder__decode_up_to_id_part1(
+wuffs_base__status wuffs_gif__decoder__decode_up_to_id_part1(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
@@ -2115,10 +2107,6 @@ static inline wuffs_base__empty_struct wuffs_base__io_writer__set_mark(
 
 // ---------------- Status Codes Implementations
 
-bool wuffs_gif__status__is_error(wuffs_gif__status s) {
-  return s < 0;
-}
-
 static const char wuffs_gif__status__string_data[] = {
     0x00, 0x67, 0x69, 0x66, 0x3A, 0x20, 0x69, 0x6E, 0x74, 0x65, 0x72, 0x6E,
     0x61, 0x6C, 0x20, 0x65, 0x72, 0x72, 0x6F, 0x72, 0x3A, 0x20, 0x69, 0x6E,
@@ -2171,7 +2159,7 @@ static const uint16_t wuffs_gif__status__string_offsets[] = {
     0x0074, 0x0084, 0x009D, 0x00B6,
 };
 
-const char* wuffs_gif__status__string(wuffs_gif__status s) {
+const char* wuffs_gif__status__string(wuffs_base__status s) {
   uint16_t o;
   switch (s & 0x1FFFFF) {
     case 0:
@@ -2210,40 +2198,40 @@ static const uint8_t wuffs_gif__netscape2dot0[11] = {
 
 // ---------------- Private Function Prototypes
 
-static wuffs_gif__status wuffs_gif__decoder__decode_header(
+static wuffs_base__status wuffs_gif__decoder__decode_header(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
-static wuffs_gif__status wuffs_gif__decoder__decode_lsd(
+static wuffs_base__status wuffs_gif__decoder__decode_lsd(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
-static wuffs_gif__status wuffs_gif__decoder__decode_extension(
+static wuffs_base__status wuffs_gif__decoder__decode_extension(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
-static wuffs_gif__status wuffs_gif__decoder__skip_blocks(
+static wuffs_base__status wuffs_gif__decoder__skip_blocks(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
-static wuffs_gif__status wuffs_gif__decoder__decode_ae(
+static wuffs_base__status wuffs_gif__decoder__decode_ae(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
-static wuffs_gif__status wuffs_gif__decoder__decode_gc(
+static wuffs_base__status wuffs_gif__decoder__decode_gc(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
-static wuffs_gif__status wuffs_gif__decoder__decode_id_part0(
+static wuffs_base__status wuffs_gif__decoder__decode_id_part0(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
-static wuffs_gif__status wuffs_gif__decoder__decode_id_part1(
+static wuffs_base__status wuffs_gif__decoder__decode_id_part1(
     wuffs_gif__decoder* self,
     wuffs_base__image_buffer* a_dst,
     wuffs_base__io_reader a_src);
 
-static wuffs_gif__status wuffs_gif__decoder__copy_to_image_buffer(
+static wuffs_base__status wuffs_gif__decoder__copy_to_image_buffer(
     wuffs_gif__decoder* self,
     wuffs_base__image_buffer* a_ib);
 
@@ -2279,7 +2267,7 @@ void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
 
 // -------- func decoder.decode_config
 
-wuffs_gif__status wuffs_gif__decoder__decode_config(
+wuffs_base__status wuffs_gif__decoder__decode_config(
     wuffs_gif__decoder* self,
     wuffs_base__image_config* a_dst,
     wuffs_base__io_reader a_src) {
@@ -2296,7 +2284,7 @@ wuffs_gif__status wuffs_gif__decoder__decode_config(
     self->private_impl.status = WUFFS_GIF__ERROR_BAD_ARGUMENT;
     return WUFFS_GIF__ERROR_BAD_ARGUMENT;
   }
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_num_loops;
 
@@ -2356,7 +2344,7 @@ exit:
 
 // -------- func decoder.decode_frame
 
-wuffs_gif__status wuffs_gif__decoder__decode_frame(
+wuffs_base__status wuffs_gif__decoder__decode_frame(
     wuffs_gif__decoder* self,
     wuffs_base__image_buffer* a_dst,
     wuffs_base__io_reader a_src) {
@@ -2373,7 +2361,7 @@ wuffs_gif__status wuffs_gif__decoder__decode_frame(
     self->private_impl.status = WUFFS_GIF__ERROR_BAD_ARGUMENT;
     return WUFFS_GIF__ERROR_BAD_ARGUMENT;
   }
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t coro_susp_point =
       self->private_impl.c_decode_frame[0].coro_susp_point;
@@ -2428,7 +2416,7 @@ exit:
 
 // -------- func decoder.decode_up_to_id_part1
 
-wuffs_gif__status wuffs_gif__decoder__decode_up_to_id_part1(
+wuffs_base__status wuffs_gif__decoder__decode_up_to_id_part1(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src) {
   if (!self) {
@@ -2440,7 +2428,7 @@ wuffs_gif__status wuffs_gif__decoder__decode_up_to_id_part1(
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
   }
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_block_type;
 
@@ -2545,10 +2533,10 @@ short_read_src:
 
 // -------- func decoder.decode_header
 
-static wuffs_gif__status wuffs_gif__decoder__decode_header(
+static wuffs_base__status wuffs_gif__decoder__decode_header(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_c[6];
   uint32_t v_i;
@@ -2629,10 +2617,10 @@ short_read_src:
 
 // -------- func decoder.decode_lsd
 
-static wuffs_gif__status wuffs_gif__decoder__decode_lsd(
+static wuffs_base__status wuffs_gif__decoder__decode_lsd(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_c[7];
   uint32_t v_i;
@@ -2774,10 +2762,10 @@ short_read_src:
 
 // -------- func decoder.decode_extension
 
-static wuffs_gif__status wuffs_gif__decoder__decode_extension(
+static wuffs_base__status wuffs_gif__decoder__decode_extension(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_label;
 
@@ -2885,10 +2873,10 @@ short_read_src:
 
 // -------- func decoder.skip_blocks
 
-static wuffs_gif__status wuffs_gif__decoder__skip_blocks(
+static wuffs_base__status wuffs_gif__decoder__skip_blocks(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_block_size;
 
@@ -2973,10 +2961,10 @@ short_read_src:
 
 // -------- func decoder.decode_ae
 
-static wuffs_gif__status wuffs_gif__decoder__decode_ae(
+static wuffs_base__status wuffs_gif__decoder__decode_ae(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_c;
   uint8_t v_block_size;
@@ -3186,10 +3174,10 @@ short_read_src:
 
 // -------- func decoder.decode_gc
 
-static wuffs_gif__status wuffs_gif__decoder__decode_gc(
+static wuffs_base__status wuffs_gif__decoder__decode_gc(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_flags;
 
@@ -3324,10 +3312,10 @@ short_read_src:
 
 // -------- func decoder.decode_id_part0
 
-static wuffs_gif__status wuffs_gif__decoder__decode_id_part0(
+static wuffs_base__status wuffs_gif__decoder__decode_id_part0(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_frame_x;
   uint32_t v_frame_y;
@@ -3522,11 +3510,11 @@ short_read_src:
 
 // -------- func decoder.decode_id_part1
 
-static wuffs_gif__status wuffs_gif__decoder__decode_id_part1(
+static wuffs_base__status wuffs_gif__decoder__decode_id_part1(
     wuffs_gif__decoder* self,
     wuffs_base__image_buffer* a_dst,
     wuffs_base__io_reader a_src) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_flags;
   bool v_use_local_palette;
@@ -3542,7 +3530,7 @@ static wuffs_gif__status wuffs_gif__decoder__decode_id_part1(
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(u_w);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(ioptr_w);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(iobounds1_w);
-  wuffs_gif__status v_z;
+  wuffs_base__status v_z;
   wuffs_base__slice_u8 v_palette;
 
   uint8_t* ioptr_src = NULL;
@@ -3727,7 +3715,7 @@ static wuffs_gif__status wuffs_gif__decoder__decode_id_part1(
               a_src.private_impl.buf->ri =
                   ioptr_src - a_src.private_impl.buf->ptr;
             }
-            wuffs_gif__status t_5 = wuffs_lzw__decoder__decode(
+            wuffs_base__status t_5 = wuffs_lzw__decoder__decode(
                 &self->private_impl.f_lzw, v_w, a_src);
             ioptr_w = u_w.ptr + u_w.wi;
             if (a_src.private_impl.buf) {
@@ -3840,10 +3828,10 @@ short_read_src:
 
 // -------- func decoder.copy_to_image_buffer
 
-static wuffs_gif__status wuffs_gif__decoder__copy_to_image_buffer(
+static wuffs_base__status wuffs_gif__decoder__copy_to_image_buffer(
     wuffs_gif__decoder* self,
     wuffs_base__image_buffer* a_ib) {
-  wuffs_gif__status status = WUFFS_GIF__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   wuffs_base__slice_u8 v_dst;
   wuffs_base__slice_u8 v_src;
diff --git a/gen/c/std/gzip.c b/gen/c/std/gzip.c
index bf366e59..76f907ad 100644
--- a/gen/c/std/gzip.c
+++ b/gen/c/std/gzip.c
@@ -1278,8 +1278,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_crc32__status;
-
 #define wuffs_crc32__packageid 810620  // 0x000C5E7C
 
 #define WUFFS_CRC32__STATUS_OK 0                          // 0x00000000
@@ -1300,9 +1298,7 @@ typedef int32_t wuffs_crc32__status;
 #define WUFFS_CRC32__ERROR_INVALID_CALL_SEQUENCE -301989888       // 0xEE000000
 #define WUFFS_CRC32__SUSPENSION_END_OF_DATA 16777216              // 0x01000000
 
-bool wuffs_crc32__status__is_error(wuffs_crc32__status s);
-
-const char* wuffs_crc32__status__string(wuffs_crc32__status s);
+const char* wuffs_crc32__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1317,7 +1313,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_crc32__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_state;
@@ -1365,8 +1361,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_deflate__status;
-
 #define wuffs_deflate__packageid 848533  // 0x000CF295
 
 #define WUFFS_DEFLATE__STATUS_OK 0                          // 0x00000000
@@ -1417,9 +1411,7 @@ typedef int32_t wuffs_deflate__status;
 #define WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS \
   -1123224939  // 0xBD0CF295
 
-bool wuffs_deflate__status__is_error(wuffs_deflate__status s);
-
-const char* wuffs_deflate__status__string(wuffs_deflate__status s);
+const char* wuffs_deflate__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1434,7 +1426,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_deflate__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_bits;
@@ -1448,7 +1440,7 @@ typedef struct {
 
     struct {
       uint32_t coro_susp_point;
-      wuffs_deflate__status v_z;
+      wuffs_base__status v_z;
       uint64_t v_n_copied;
       uint32_t v_already_full;
     } c_decode[1];
@@ -1514,10 +1506,9 @@ void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
 
 // ---------------- Public Function Prototypes
 
-wuffs_deflate__status wuffs_deflate__decoder__decode(
-    wuffs_deflate__decoder* self,
-    wuffs_base__io_writer a_dst,
-    wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
+                                                  wuffs_base__io_writer a_dst,
+                                                  wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
@@ -1533,8 +1524,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_gzip__status;
-
 #define wuffs_gzip__packageid 1041911  // 0x000FE5F7
 
 #define WUFFS_GZIP__STATUS_OK 0                          // 0x00000000
@@ -1560,9 +1549,7 @@ typedef int32_t wuffs_gzip__status;
 #define WUFFS_GZIP__ERROR_BAD_ENCODING_FLAGS -49289737      // 0xFD0FE5F7
 #define WUFFS_GZIP__ERROR_BAD_HEADER -66066953              // 0xFC0FE5F7
 
-bool wuffs_gzip__status__is_error(wuffs_gzip__status s);
-
-const char* wuffs_gzip__status__string(wuffs_gzip__status s);
+const char* wuffs_gzip__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1577,7 +1564,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_gzip__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     wuffs_deflate__decoder f_flate;
@@ -1591,7 +1578,7 @@ typedef struct {
       uint16_t v_xlen;
       uint32_t v_checksum_got;
       uint32_t v_decoded_length_got;
-      wuffs_gzip__status v_z;
+      wuffs_base__status v_z;
       uint32_t v_checksum_want;
       uint32_t v_decoded_length_want;
       uint64_t scratch;
@@ -1615,7 +1602,7 @@ void wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
 void wuffs_gzip__decoder__set_ignore_checksum(wuffs_gzip__decoder* self,
                                               bool a_ic);
 
-wuffs_gzip__status wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
+wuffs_base__status wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
                                                wuffs_base__io_writer a_dst,
                                                wuffs_base__io_reader a_src);
 
@@ -2179,10 +2166,6 @@ static inline wuffs_base__empty_struct wuffs_base__io_writer__set_mark(
 
 // ---------------- Status Codes Implementations
 
-bool wuffs_gzip__status__is_error(wuffs_gzip__status s) {
-  return s < 0;
-}
-
 static const char wuffs_gzip__status__string_data[] = {
     0x00, 0x67, 0x7A, 0x69, 0x70, 0x3A, 0x20, 0x62, 0x61, 0x64, 0x20, 0x68,
     0x65, 0x61, 0x64, 0x65, 0x72, 0x00, 0x67, 0x7A, 0x69, 0x70, 0x3A, 0x20,
@@ -2226,7 +2209,7 @@ static const uint16_t wuffs_gzip__status__string_offsets[] = {
     0x0001, 0x0012, 0x002B, 0x0048,
 };
 
-const char* wuffs_gzip__status__string(wuffs_gzip__status s) {
+const char* wuffs_gzip__status__string(wuffs_base__status s) {
   uint16_t o;
   switch (s & 0x1FFFFF) {
     case 0:
@@ -2304,7 +2287,7 @@ void wuffs_gzip__decoder__set_ignore_checksum(wuffs_gzip__decoder* self,
 
 // -------- func decoder.decode
 
-wuffs_gzip__status wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
+wuffs_base__status wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
                                                wuffs_base__io_writer a_dst,
                                                wuffs_base__io_reader a_src) {
   if (!self) {
@@ -2317,14 +2300,14 @@ wuffs_gzip__status wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
   }
-  wuffs_gzip__status status = WUFFS_GZIP__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint8_t v_flags;
   uint8_t v_c;
   uint16_t v_xlen;
   uint32_t v_checksum_got;
   uint32_t v_decoded_length_got;
-  wuffs_gzip__status v_z;
+  wuffs_base__status v_z;
   uint32_t v_checksum_want;
   uint32_t v_decoded_length_want;
 
@@ -2520,7 +2503,7 @@ wuffs_gzip__status wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
         if (a_src.private_impl.buf) {
           a_src.private_impl.buf->ri = ioptr_src - a_src.private_impl.buf->ptr;
         }
-        wuffs_gzip__status t_8 = wuffs_deflate__decoder__decode(
+        wuffs_base__status t_8 = wuffs_deflate__decoder__decode(
             &self->private_impl.f_flate, a_dst, a_src);
         if (a_dst.private_impl.buf) {
           ioptr_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
diff --git a/gen/c/std/lzw.c b/gen/c/std/lzw.c
index 4683c181..6dc23a3e 100644
--- a/gen/c/std/lzw.c
+++ b/gen/c/std/lzw.c
@@ -1269,8 +1269,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_lzw__status;
-
 #define wuffs_lzw__packageid 1316776  // 0x001417A8
 
 #define WUFFS_LZW__STATUS_OK 0                          // 0x00000000
@@ -1294,9 +1292,7 @@ typedef int32_t wuffs_lzw__status;
 #define WUFFS_LZW__ERROR_BAD_CODE -15460440               // 0xFF1417A8
 #define WUFFS_LZW__ERROR_CYCLICAL_PREFIX_CHAIN -32237656  // 0xFE1417A8
 
-bool wuffs_lzw__status__is_error(wuffs_lzw__status s);
-
-const char* wuffs_lzw__status__string(wuffs_lzw__status s);
+const char* wuffs_lzw__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1311,7 +1307,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_lzw__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_literal_width;
@@ -1353,9 +1349,9 @@ void wuffs_lzw__decoder__check_wuffs_version(wuffs_lzw__decoder* self,
 void wuffs_lzw__decoder__set_literal_width(wuffs_lzw__decoder* self,
                                            uint32_t a_lw);
 
-wuffs_lzw__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
-                                             wuffs_base__io_writer a_dst,
-                                             wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
+                                              wuffs_base__io_writer a_dst,
+                                              wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
@@ -1917,10 +1913,6 @@ static inline wuffs_base__empty_struct wuffs_base__io_writer__set_mark(
 
 // ---------------- Status Codes Implementations
 
-bool wuffs_lzw__status__is_error(wuffs_lzw__status s) {
-  return s < 0;
-}
-
 static const char wuffs_lzw__status__string_data[] = {
     0x00, 0x6C, 0x7A, 0x77, 0x3A, 0x20, 0x63, 0x79, 0x63, 0x6C, 0x69,
     0x63, 0x61, 0x6C, 0x20, 0x70, 0x72, 0x65, 0x66, 0x69, 0x78, 0x20,
@@ -1960,7 +1952,7 @@ static const uint16_t wuffs_lzw__status__string_offsets[] = {
     0x0000, 0x0000, 0x0001, 0x001C,
 };
 
-const char* wuffs_lzw__status__string(wuffs_lzw__status s) {
+const char* wuffs_lzw__status__string(wuffs_base__status s) {
   uint16_t o;
   switch (s & 0x1FFFFF) {
     case 0:
@@ -2031,9 +2023,9 @@ void wuffs_lzw__decoder__set_literal_width(wuffs_lzw__decoder* self,
 
 // -------- func decoder.decode
 
-wuffs_lzw__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
-                                             wuffs_base__io_writer a_dst,
-                                             wuffs_base__io_reader a_src) {
+wuffs_base__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
+                                              wuffs_base__io_writer a_dst,
+                                              wuffs_base__io_reader a_src) {
   if (!self) {
     return WUFFS_LZW__ERROR_BAD_RECEIVER;
   }
@@ -2043,7 +2035,7 @@ wuffs_lzw__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
   }
-  wuffs_lzw__status status = WUFFS_LZW__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint32_t v_literal_width;
   uint32_t v_clear_code;
diff --git a/gen/c/std/zlib.c b/gen/c/std/zlib.c
index 2467d03f..495aa797 100644
--- a/gen/c/std/zlib.c
+++ b/gen/c/std/zlib.c
@@ -1278,8 +1278,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_adler32__status;
-
 #define wuffs_adler32__packageid 681002  // 0x000A642A
 
 #define WUFFS_ADLER32__STATUS_OK 0                          // 0x00000000
@@ -1301,9 +1299,7 @@ typedef int32_t wuffs_adler32__status;
 #define WUFFS_ADLER32__ERROR_INVALID_CALL_SEQUENCE -301989888  // 0xEE000000
 #define WUFFS_ADLER32__SUSPENSION_END_OF_DATA 16777216         // 0x01000000
 
-bool wuffs_adler32__status__is_error(wuffs_adler32__status s);
-
-const char* wuffs_adler32__status__string(wuffs_adler32__status s);
+const char* wuffs_adler32__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1318,7 +1314,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_adler32__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_state;
@@ -1366,8 +1362,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_deflate__status;
-
 #define wuffs_deflate__packageid 848533  // 0x000CF295
 
 #define WUFFS_DEFLATE__STATUS_OK 0                          // 0x00000000
@@ -1418,9 +1412,7 @@ typedef int32_t wuffs_deflate__status;
 #define WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS \
   -1123224939  // 0xBD0CF295
 
-bool wuffs_deflate__status__is_error(wuffs_deflate__status s);
-
-const char* wuffs_deflate__status__string(wuffs_deflate__status s);
+const char* wuffs_deflate__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1435,7 +1427,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_deflate__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_bits;
@@ -1449,7 +1441,7 @@ typedef struct {
 
     struct {
       uint32_t coro_susp_point;
-      wuffs_deflate__status v_z;
+      wuffs_base__status v_z;
       uint64_t v_n_copied;
       uint32_t v_already_full;
     } c_decode[1];
@@ -1515,10 +1507,9 @@ void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
 
 // ---------------- Public Function Prototypes
 
-wuffs_deflate__status wuffs_deflate__decoder__decode(
-    wuffs_deflate__decoder* self,
-    wuffs_base__io_writer a_dst,
-    wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
+                                                  wuffs_base__io_writer a_dst,
+                                                  wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
@@ -1534,8 +1525,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_zlib__status;
-
 #define wuffs_zlib__packageid 2064249  // 0x001F7F79
 
 #define WUFFS_ZLIB__STATUS_OK 0                          // 0x00000000
@@ -1563,9 +1552,7 @@ typedef int32_t wuffs_zlib__status;
 #define WUFFS_ZLIB__ERROR_TODO_UNSUPPORTED_PRESET_DICTIONARY \
   -1071677575  // 0xC01F7F79
 
-bool wuffs_zlib__status__is_error(wuffs_zlib__status s);
-
-const char* wuffs_zlib__status__string(wuffs_zlib__status s);
+const char* wuffs_zlib__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1580,7 +1567,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_zlib__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     wuffs_deflate__decoder f_flate;
@@ -1591,7 +1578,7 @@ typedef struct {
       uint32_t coro_susp_point;
       uint16_t v_x;
       uint32_t v_checksum_got;
-      wuffs_zlib__status v_z;
+      wuffs_base__status v_z;
       uint32_t v_checksum_want;
       uint64_t scratch;
     } c_decode[1];
@@ -1614,7 +1601,7 @@ void wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
 void wuffs_zlib__decoder__set_ignore_checksum(wuffs_zlib__decoder* self,
                                               bool a_ic);
 
-wuffs_zlib__status wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
+wuffs_base__status wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
                                                wuffs_base__io_writer a_dst,
                                                wuffs_base__io_reader a_src);
 
@@ -2178,10 +2165,6 @@ static inline wuffs_base__empty_struct wuffs_base__io_writer__set_mark(
 
 // ---------------- Status Codes Implementations
 
-bool wuffs_zlib__status__is_error(wuffs_zlib__status s) {
-  return s < 0;
-}
-
 static const char wuffs_zlib__status__string_data[] = {
     0x00, 0x7A, 0x6C, 0x69, 0x62, 0x3A, 0x20, 0x54, 0x4F, 0x44, 0x4F, 0x3A,
     0x20, 0x75, 0x6E, 0x73, 0x75, 0x70, 0x70, 0x6F, 0x72, 0x74, 0x65, 0x64,
@@ -2230,7 +2213,7 @@ static const uint16_t wuffs_zlib__status__string_offsets[] = {
     0x002B, 0x0042, 0x0064, 0x0081,
 };
 
-const char* wuffs_zlib__status__string(wuffs_zlib__status s) {
+const char* wuffs_zlib__status__string(wuffs_base__status s) {
   uint16_t o;
   switch (s & 0x1FFFFF) {
     case 0:
@@ -2308,7 +2291,7 @@ void wuffs_zlib__decoder__set_ignore_checksum(wuffs_zlib__decoder* self,
 
 // -------- func decoder.decode
 
-wuffs_zlib__status wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
+wuffs_base__status wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
                                                wuffs_base__io_writer a_dst,
                                                wuffs_base__io_reader a_src) {
   if (!self) {
@@ -2321,11 +2304,11 @@ wuffs_zlib__status wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
   }
-  wuffs_zlib__status status = WUFFS_ZLIB__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
 
   uint16_t v_x;
   uint32_t v_checksum_got;
-  wuffs_zlib__status v_z;
+  wuffs_base__status v_z;
   uint32_t v_checksum_want;
 
   uint8_t* ioptr_dst = NULL;
@@ -2427,7 +2410,7 @@ wuffs_zlib__status wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
         if (a_src.private_impl.buf) {
           a_src.private_impl.buf->ri = ioptr_src - a_src.private_impl.buf->ptr;
         }
-        wuffs_zlib__status t_2 = wuffs_deflate__decoder__decode(
+        wuffs_base__status t_2 = wuffs_deflate__decoder__decode(
             &self->private_impl.f_flate, a_dst, a_src);
         if (a_dst.private_impl.buf) {
           ioptr_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
diff --git a/gen/h/std/adler32.h b/gen/h/std/adler32.h
index 5f822b44..5dd42cb2 100644
--- a/gen/h/std/adler32.h
+++ b/gen/h/std/adler32.h
@@ -1269,8 +1269,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_adler32__status;
-
 #define wuffs_adler32__packageid 681002  // 0x000A642A
 
 #define WUFFS_ADLER32__STATUS_OK 0                          // 0x00000000
@@ -1292,9 +1290,7 @@ typedef int32_t wuffs_adler32__status;
 #define WUFFS_ADLER32__ERROR_INVALID_CALL_SEQUENCE -301989888  // 0xEE000000
 #define WUFFS_ADLER32__SUSPENSION_END_OF_DATA 16777216         // 0x01000000
 
-bool wuffs_adler32__status__is_error(wuffs_adler32__status s);
-
-const char* wuffs_adler32__status__string(wuffs_adler32__status s);
+const char* wuffs_adler32__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1309,7 +1305,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_adler32__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_state;
diff --git a/gen/h/std/crc32.h b/gen/h/std/crc32.h
index 09a447f0..d1cc12cf 100644
--- a/gen/h/std/crc32.h
+++ b/gen/h/std/crc32.h
@@ -1269,8 +1269,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_crc32__status;
-
 #define wuffs_crc32__packageid 810620  // 0x000C5E7C
 
 #define WUFFS_CRC32__STATUS_OK 0                          // 0x00000000
@@ -1291,9 +1289,7 @@ typedef int32_t wuffs_crc32__status;
 #define WUFFS_CRC32__ERROR_INVALID_CALL_SEQUENCE -301989888       // 0xEE000000
 #define WUFFS_CRC32__SUSPENSION_END_OF_DATA 16777216              // 0x01000000
 
-bool wuffs_crc32__status__is_error(wuffs_crc32__status s);
-
-const char* wuffs_crc32__status__string(wuffs_crc32__status s);
+const char* wuffs_crc32__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1308,7 +1304,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_crc32__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_state;
diff --git a/gen/h/std/deflate.h b/gen/h/std/deflate.h
index 351f958b..92670af3 100644
--- a/gen/h/std/deflate.h
+++ b/gen/h/std/deflate.h
@@ -1269,8 +1269,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_deflate__status;
-
 #define wuffs_deflate__packageid 848533  // 0x000CF295
 
 #define WUFFS_DEFLATE__STATUS_OK 0                          // 0x00000000
@@ -1321,9 +1319,7 @@ typedef int32_t wuffs_deflate__status;
 #define WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS \
   -1123224939  // 0xBD0CF295
 
-bool wuffs_deflate__status__is_error(wuffs_deflate__status s);
-
-const char* wuffs_deflate__status__string(wuffs_deflate__status s);
+const char* wuffs_deflate__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1338,7 +1334,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_deflate__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_bits;
@@ -1352,7 +1348,7 @@ typedef struct {
 
     struct {
       uint32_t coro_susp_point;
-      wuffs_deflate__status v_z;
+      wuffs_base__status v_z;
       uint64_t v_n_copied;
       uint32_t v_already_full;
     } c_decode[1];
@@ -1418,10 +1414,9 @@ void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
 
 // ---------------- Public Function Prototypes
 
-wuffs_deflate__status wuffs_deflate__decoder__decode(
-    wuffs_deflate__decoder* self,
-    wuffs_base__io_writer a_dst,
-    wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
+                                                  wuffs_base__io_writer a_dst,
+                                                  wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
diff --git a/gen/h/std/gif.h b/gen/h/std/gif.h
index 1e1a1730..fec14adc 100644
--- a/gen/h/std/gif.h
+++ b/gen/h/std/gif.h
@@ -1278,8 +1278,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_lzw__status;
-
 #define wuffs_lzw__packageid 1316776  // 0x001417A8
 
 #define WUFFS_LZW__STATUS_OK 0                          // 0x00000000
@@ -1303,9 +1301,7 @@ typedef int32_t wuffs_lzw__status;
 #define WUFFS_LZW__ERROR_BAD_CODE -15460440               // 0xFF1417A8
 #define WUFFS_LZW__ERROR_CYCLICAL_PREFIX_CHAIN -32237656  // 0xFE1417A8
 
-bool wuffs_lzw__status__is_error(wuffs_lzw__status s);
-
-const char* wuffs_lzw__status__string(wuffs_lzw__status s);
+const char* wuffs_lzw__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1320,7 +1316,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_lzw__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_literal_width;
@@ -1362,9 +1358,9 @@ void wuffs_lzw__decoder__check_wuffs_version(wuffs_lzw__decoder* self,
 void wuffs_lzw__decoder__set_literal_width(wuffs_lzw__decoder* self,
                                            uint32_t a_lw);
 
-wuffs_lzw__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
-                                             wuffs_base__io_writer a_dst,
-                                             wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
+                                              wuffs_base__io_writer a_dst,
+                                              wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
@@ -1380,8 +1376,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_gif__status;
-
 #define wuffs_gif__packageid 1017222  // 0x000F8586
 
 #define WUFFS_GIF__STATUS_OK 0                          // 0x00000000
@@ -1412,9 +1406,7 @@ typedef int32_t wuffs_gif__status;
 #define WUFFS_GIF__ERROR_INTERNAL_ERROR_INCONSISTENT_RI_WI \
   -1072724602  // 0xC00F8586
 
-bool wuffs_gif__status__is_error(wuffs_gif__status s);
-
-const char* wuffs_gif__status__string(wuffs_gif__status s);
+const char* wuffs_gif__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1429,7 +1421,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_gif__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_width;
@@ -1522,7 +1514,7 @@ typedef struct {
       uint32_t v_argb;
       uint8_t v_lw;
       uint64_t v_block_size;
-      wuffs_gif__status v_z;
+      wuffs_base__status v_z;
       uint64_t scratch;
     } c_decode_id_part1[1];
   } private_impl;
@@ -1541,17 +1533,17 @@ void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
 
 // ---------------- Public Function Prototypes
 
-wuffs_gif__status wuffs_gif__decoder__decode_config(
+wuffs_base__status wuffs_gif__decoder__decode_config(
     wuffs_gif__decoder* self,
     wuffs_base__image_config* a_dst,
     wuffs_base__io_reader a_src);
 
-wuffs_gif__status wuffs_gif__decoder__decode_frame(
+wuffs_base__status wuffs_gif__decoder__decode_frame(
     wuffs_gif__decoder* self,
     wuffs_base__image_buffer* a_dst,
     wuffs_base__io_reader a_src);
 
-wuffs_gif__status wuffs_gif__decoder__decode_up_to_id_part1(
+wuffs_base__status wuffs_gif__decoder__decode_up_to_id_part1(
     wuffs_gif__decoder* self,
     wuffs_base__io_reader a_src);
 
diff --git a/gen/h/std/gzip.h b/gen/h/std/gzip.h
index 9e403d54..6c97286b 100644
--- a/gen/h/std/gzip.h
+++ b/gen/h/std/gzip.h
@@ -1278,8 +1278,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_crc32__status;
-
 #define wuffs_crc32__packageid 810620  // 0x000C5E7C
 
 #define WUFFS_CRC32__STATUS_OK 0                          // 0x00000000
@@ -1300,9 +1298,7 @@ typedef int32_t wuffs_crc32__status;
 #define WUFFS_CRC32__ERROR_INVALID_CALL_SEQUENCE -301989888       // 0xEE000000
 #define WUFFS_CRC32__SUSPENSION_END_OF_DATA 16777216              // 0x01000000
 
-bool wuffs_crc32__status__is_error(wuffs_crc32__status s);
-
-const char* wuffs_crc32__status__string(wuffs_crc32__status s);
+const char* wuffs_crc32__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1317,7 +1313,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_crc32__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_state;
@@ -1365,8 +1361,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_deflate__status;
-
 #define wuffs_deflate__packageid 848533  // 0x000CF295
 
 #define WUFFS_DEFLATE__STATUS_OK 0                          // 0x00000000
@@ -1417,9 +1411,7 @@ typedef int32_t wuffs_deflate__status;
 #define WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS \
   -1123224939  // 0xBD0CF295
 
-bool wuffs_deflate__status__is_error(wuffs_deflate__status s);
-
-const char* wuffs_deflate__status__string(wuffs_deflate__status s);
+const char* wuffs_deflate__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1434,7 +1426,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_deflate__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_bits;
@@ -1448,7 +1440,7 @@ typedef struct {
 
     struct {
       uint32_t coro_susp_point;
-      wuffs_deflate__status v_z;
+      wuffs_base__status v_z;
       uint64_t v_n_copied;
       uint32_t v_already_full;
     } c_decode[1];
@@ -1514,10 +1506,9 @@ void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
 
 // ---------------- Public Function Prototypes
 
-wuffs_deflate__status wuffs_deflate__decoder__decode(
-    wuffs_deflate__decoder* self,
-    wuffs_base__io_writer a_dst,
-    wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
+                                                  wuffs_base__io_writer a_dst,
+                                                  wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
@@ -1533,8 +1524,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_gzip__status;
-
 #define wuffs_gzip__packageid 1041911  // 0x000FE5F7
 
 #define WUFFS_GZIP__STATUS_OK 0                          // 0x00000000
@@ -1560,9 +1549,7 @@ typedef int32_t wuffs_gzip__status;
 #define WUFFS_GZIP__ERROR_BAD_ENCODING_FLAGS -49289737      // 0xFD0FE5F7
 #define WUFFS_GZIP__ERROR_BAD_HEADER -66066953              // 0xFC0FE5F7
 
-bool wuffs_gzip__status__is_error(wuffs_gzip__status s);
-
-const char* wuffs_gzip__status__string(wuffs_gzip__status s);
+const char* wuffs_gzip__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1577,7 +1564,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_gzip__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     wuffs_deflate__decoder f_flate;
@@ -1591,7 +1578,7 @@ typedef struct {
       uint16_t v_xlen;
       uint32_t v_checksum_got;
       uint32_t v_decoded_length_got;
-      wuffs_gzip__status v_z;
+      wuffs_base__status v_z;
       uint32_t v_checksum_want;
       uint32_t v_decoded_length_want;
       uint64_t scratch;
@@ -1615,7 +1602,7 @@ void wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
 void wuffs_gzip__decoder__set_ignore_checksum(wuffs_gzip__decoder* self,
                                               bool a_ic);
 
-wuffs_gzip__status wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
+wuffs_base__status wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
                                                wuffs_base__io_writer a_dst,
                                                wuffs_base__io_reader a_src);
 
diff --git a/gen/h/std/lzw.h b/gen/h/std/lzw.h
index 07296641..12dd027a 100644
--- a/gen/h/std/lzw.h
+++ b/gen/h/std/lzw.h
@@ -1269,8 +1269,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_lzw__status;
-
 #define wuffs_lzw__packageid 1316776  // 0x001417A8
 
 #define WUFFS_LZW__STATUS_OK 0                          // 0x00000000
@@ -1294,9 +1292,7 @@ typedef int32_t wuffs_lzw__status;
 #define WUFFS_LZW__ERROR_BAD_CODE -15460440               // 0xFF1417A8
 #define WUFFS_LZW__ERROR_CYCLICAL_PREFIX_CHAIN -32237656  // 0xFE1417A8
 
-bool wuffs_lzw__status__is_error(wuffs_lzw__status s);
-
-const char* wuffs_lzw__status__string(wuffs_lzw__status s);
+const char* wuffs_lzw__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1311,7 +1307,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_lzw__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_literal_width;
@@ -1353,9 +1349,9 @@ void wuffs_lzw__decoder__check_wuffs_version(wuffs_lzw__decoder* self,
 void wuffs_lzw__decoder__set_literal_width(wuffs_lzw__decoder* self,
                                            uint32_t a_lw);
 
-wuffs_lzw__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
-                                             wuffs_base__io_writer a_dst,
-                                             wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
+                                              wuffs_base__io_writer a_dst,
+                                              wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
diff --git a/gen/h/std/zlib.h b/gen/h/std/zlib.h
index ec64315d..73f7c97c 100644
--- a/gen/h/std/zlib.h
+++ b/gen/h/std/zlib.h
@@ -1278,8 +1278,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_adler32__status;
-
 #define wuffs_adler32__packageid 681002  // 0x000A642A
 
 #define WUFFS_ADLER32__STATUS_OK 0                          // 0x00000000
@@ -1301,9 +1299,7 @@ typedef int32_t wuffs_adler32__status;
 #define WUFFS_ADLER32__ERROR_INVALID_CALL_SEQUENCE -301989888  // 0xEE000000
 #define WUFFS_ADLER32__SUSPENSION_END_OF_DATA 16777216         // 0x01000000
 
-bool wuffs_adler32__status__is_error(wuffs_adler32__status s);
-
-const char* wuffs_adler32__status__string(wuffs_adler32__status s);
+const char* wuffs_adler32__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1318,7 +1314,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_adler32__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_state;
@@ -1366,8 +1362,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_deflate__status;
-
 #define wuffs_deflate__packageid 848533  // 0x000CF295
 
 #define WUFFS_DEFLATE__STATUS_OK 0                          // 0x00000000
@@ -1418,9 +1412,7 @@ typedef int32_t wuffs_deflate__status;
 #define WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS \
   -1123224939  // 0xBD0CF295
 
-bool wuffs_deflate__status__is_error(wuffs_deflate__status s);
-
-const char* wuffs_deflate__status__string(wuffs_deflate__status s);
+const char* wuffs_deflate__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1435,7 +1427,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_deflate__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     uint32_t f_bits;
@@ -1449,7 +1441,7 @@ typedef struct {
 
     struct {
       uint32_t coro_susp_point;
-      wuffs_deflate__status v_z;
+      wuffs_base__status v_z;
       uint64_t v_n_copied;
       uint32_t v_already_full;
     } c_decode[1];
@@ -1515,10 +1507,9 @@ void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
 
 // ---------------- Public Function Prototypes
 
-wuffs_deflate__status wuffs_deflate__decoder__decode(
-    wuffs_deflate__decoder* self,
-    wuffs_base__io_writer a_dst,
-    wuffs_base__io_reader a_src);
+wuffs_base__status wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
+                                                  wuffs_base__io_writer a_dst,
+                                                  wuffs_base__io_reader a_src);
 
 #ifdef __cplusplus
 }  // extern "C"
@@ -1534,8 +1525,6 @@ extern "C" {
 
 // ---------------- Status Codes
 
-typedef int32_t wuffs_zlib__status;
-
 #define wuffs_zlib__packageid 2064249  // 0x001F7F79
 
 #define WUFFS_ZLIB__STATUS_OK 0                          // 0x00000000
@@ -1563,9 +1552,7 @@ typedef int32_t wuffs_zlib__status;
 #define WUFFS_ZLIB__ERROR_TODO_UNSUPPORTED_PRESET_DICTIONARY \
   -1071677575  // 0xC01F7F79
 
-bool wuffs_zlib__status__is_error(wuffs_zlib__status s);
-
-const char* wuffs_zlib__status__string(wuffs_zlib__status s);
+const char* wuffs_zlib__status__string(wuffs_base__status s);
 
 // ---------------- Public Consts
 
@@ -1580,7 +1567,7 @@ typedef struct {
   //
   // It is a struct, not a struct*, so that it can be stack allocated.
   struct {
-    wuffs_zlib__status status;
+    wuffs_base__status status;
     uint32_t magic;
 
     wuffs_deflate__decoder f_flate;
@@ -1591,7 +1578,7 @@ typedef struct {
       uint32_t coro_susp_point;
       uint16_t v_x;
       uint32_t v_checksum_got;
-      wuffs_zlib__status v_z;
+      wuffs_base__status v_z;
       uint32_t v_checksum_want;
       uint64_t scratch;
     } c_decode[1];
@@ -1614,7 +1601,7 @@ void wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
 void wuffs_zlib__decoder__set_ignore_checksum(wuffs_zlib__decoder* self,
                                               bool a_ic);
 
-wuffs_zlib__status wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
+wuffs_base__status wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
                                                wuffs_base__io_writer a_dst,
                                                wuffs_base__io_reader a_src);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
