# Case ID

P045

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

// Wuffs ships as a "single file C library" or "header file library" as per
// https://github.com/nothings/stb/blob/master/docs/stb_howto.txt
//
// To use that single file as a "foo.c"-like implementation, instead of a
// "foo.h"-like header, #define WUFFS_IMPLEMENTATION before #include'ing or
// compiling it.
#define WUFFS_IMPLEMENTATION

// If building this program in an environment that doesn't easily accommodate
// relative includes, you can use the script/inline-c-relative-includes.go
// program to generate a stand-alone C file.
#include "../../../release/c/wuffs-unsupported-snapshot.h"
#include "../fuzzlib/fuzzlib.c"

const char* fuzz(wuffs_base__io_reader src_reader, uint32_t hash) {
  const char* ret = NULL;
  void* pixbuf = NULL;

  // Use a {} code block so that "goto exit" doesn't trigger "jump bypasses
  // variable initialization" warnings.
  {
    wuffs_base__status s = 0;
    wuffs_gif__decoder dec = ((wuffs_gif__decoder){});
    wuffs_gif__decoder__check_wuffs_version(&dec, sizeof dec, WUFFS_VERSION);

    wuffs_base__image_config ic = ((wuffs_base__image_config){});
    s = wuffs_gif__decoder__decode_image_config(&dec, &ic, src_reader);
    if (s) {
      ret = wuffs_gif__status__string(s);
      goto exit;
    }
    if (!wuffs_base__image_config__is_valid(&ic)) {
      ret = "invalid image_config";
      goto exit;
    }

    size_t pixbuf_size = wuffs_base__pixel_config__pixbuf_size(
        wuffs_base__image_config__pixel_config(&ic));
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
    wuffs_base__pixel_buffer pb = ((wuffs_base__pixel_buffer){});
    s = wuffs_base__pixel_buffer__set_from_slice(
        &pb, wuffs_base__image_config__pixel_config(&ic),
        ((wuffs_base__slice_u8){.ptr = pixbuf, .len = pixbuf_size}));
    if (s) {
      ret = wuffs_gif__status__string(s);
      goto exit;
    }

    bool seen_ok = false;
    while (true) {
      s = wuffs_gif__decoder__decode_frame(&dec, &pb, 0, 0, src_reader,
                                           ((wuffs_base__slice_u8){}));
      if (s) {
        if ((s == WUFFS_BASE__SUSPENSION_END_OF_DATA) && seen_ok) {
          s = WUFFS_BASE__STATUS_OK;
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

// Wuffs ships as a "single file C library" or "header file library" as per
// https://github.com/nothings/stb/blob/master/docs/stb_howto.txt
//
// To use that single file as a "foo.c"-like implementation, instead of a
// "foo.h"-like header, #define WUFFS_IMPLEMENTATION before #include'ing or
// compiling it.
#define WUFFS_IMPLEMENTATION

// If building this program in an environment that doesn't easily accommodate
// relative includes, you can use the script/inline-c-relative-includes.go
// program to generate a stand-alone C file.
#include "../../../release/c/wuffs-unsupported-snapshot.h"
#include "../fuzzlib/fuzzlib.c"

const char* fuzz(wuffs_base__io_reader src_reader, uint32_t hash) {
  const char* ret = NULL;
  wuffs_base__status s = 0;
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
    if (s != WUFFS_BASE__SUSPENSION_SHORT_WRITE) {
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
diff --git a/cmd/wuffs-c/internal/cgen/base/base-private.h b/cmd/wuffs-c/internal/cgen/base/base-private.h
index 43fd2a55..53efd0f5 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-private.h
+++ b/cmd/wuffs-c/internal/cgen/base/base-private.h
@@ -23,6 +23,9 @@ extern "C" {
 
 #define WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(x) (void)(x)
 
+static inline void wuffs_base__ignore_check_wuffs_version_status(
+    wuffs_base__status z) {}
+
 // WUFFS_BASE__MAGIC is a magic number to check that initializers are called.
 // It's not foolproof, given C doesn't automatically zero memory before use,
 // but it should catch 99.99% of cases.
diff --git a/cmd/wuffs-c/internal/cgen/base/base-public.h b/cmd/wuffs-c/internal/cgen/base/base-public.h
index 86640512..4628cc6b 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-public.h
+++ b/cmd/wuffs-c/internal/cgen/base/base-public.h
@@ -59,6 +59,13 @@ extern "C" {
 #define WUFFS_BASE__MAYBE_STATIC
 #endif
 
+// Clang also defines "__GNUC__".
+#if defined(__GNUC__)
+#define WUFFS_BASE__WARN_UNUSED_RESULT __attribute__((warn_unused_result))
+#else
+#define WUFFS_BASE__WARN_UNUSED_RESULT
+#endif
+
 // wuffs_base__empty_struct is used when a Wuffs function returns an empty
 // struct. In C, if a function f returns void, you can't say "x = f()", but in
 // Wuffs, if a function g returns empty, you can say "y = g()".
diff --git a/release/c/wuffs-unsupported-snapshot.h b/release/c/wuffs-unsupported-snapshot.h
index 7561915f..e83ef242 100644
--- a/release/c/wuffs-unsupported-snapshot.h
+++ b/release/c/wuffs-unsupported-snapshot.h
@@ -83,6 +83,13 @@ extern "C" {
 #define WUFFS_BASE__MAYBE_STATIC
 #endif
 
+// Clang also defines "__GNUC__".
+#if defined(__GNUC__)
+#define WUFFS_BASE__WARN_UNUSED_RESULT __attribute__((warn_unused_result))
+#else
+#define WUFFS_BASE__WARN_UNUSED_RESULT
+#endif
+
 // wuffs_base__empty_struct is used when a Wuffs function returns an empty
 // struct. In C, if a function f returns void, you can't say "x = f()", but in
 // Wuffs, if a function g returns empty, you can say "y = g()".
@@ -133,8 +140,7 @@ typedef int32_t wuffs_base__status;
 #define WUFFS_BASE__ERROR_BAD_RECEIVER -50331648                   // 0xFD000000
 #define WUFFS_BASE__ERROR_BAD_ARGUMENT -67108864                   // 0xFC000000
 #define WUFFS_BASE__ERROR_BAD_ARGUMENT_LENGTH_TOO_SHORT -67108864  // 0xFC000000
-#define WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED \
-  -268435456  // 0xF0000000
+#define WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING -268435456   // 0xF0000000
 #define WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE \
   -285212672                                                     // 0xEF000000
 #define WUFFS_BASE__ERROR_INVALID_CALL_SEQUENCE -301989888       // 0xEE000000
@@ -2056,8 +2062,8 @@ typedef struct {
   } private_impl;
 
 #ifdef __cplusplus
-  inline void check_wuffs_version(size_t sizeof_star_self,
-                                  uint64_t wuffs_version);
+  inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+  check_wuffs_version(size_t sizeof_star_self, uint64_t wuffs_version);
   inline uint32_t update(wuffs_base__slice_u8 a_x);
 #endif  // __cplusplus
 
@@ -2070,9 +2076,10 @@ typedef struct {
 // It should be called before any other wuffs_adler32__hasher__* function.
 //
 // Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
-void wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
-                                                size_t sizeof_star_self,
-                                                uint64_t wuffs_version);
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
+                                           size_t sizeof_star_self,
+                                           uint64_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2084,11 +2091,11 @@ wuffs_adler32__hasher__update(wuffs_adler32__hasher* self,
 
 #ifdef __cplusplus
 
-inline void  //
+inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
 wuffs_adler32__hasher::check_wuffs_version(size_t sizeof_star_self,
                                            uint64_t wuffs_version) {
-  wuffs_adler32__hasher__check_wuffs_version(this, sizeof_star_self,
-                                             wuffs_version);
+  return wuffs_adler32__hasher__check_wuffs_version(this, sizeof_star_self,
+                                                    wuffs_version);
 }
 
 inline uint32_t  //
@@ -2137,8 +2144,8 @@ typedef struct {
   } private_impl;
 
 #ifdef __cplusplus
-  inline void check_wuffs_version(size_t sizeof_star_self,
-                                  uint64_t wuffs_version);
+  inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+  check_wuffs_version(size_t sizeof_star_self, uint64_t wuffs_version);
   inline uint32_t update(wuffs_base__slice_u8 a_x);
 #endif  // __cplusplus
 
@@ -2151,10 +2158,10 @@ typedef struct {
 // It should be called before any other wuffs_crc32__ieee_hasher__* function.
 //
 // Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
-void wuffs_crc32__ieee_hasher__check_wuffs_version(
-    wuffs_crc32__ieee_hasher* self,
-    size_t sizeof_star_self,
-    uint64_t wuffs_version);
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_crc32__ieee_hasher__check_wuffs_version(wuffs_crc32__ieee_hasher* self,
+                                              size_t sizeof_star_self,
+                                              uint64_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2166,11 +2173,11 @@ wuffs_crc32__ieee_hasher__update(wuffs_crc32__ieee_hasher* self,
 
 #ifdef __cplusplus
 
-inline void  //
+inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
 wuffs_crc32__ieee_hasher::check_wuffs_version(size_t sizeof_star_self,
                                               uint64_t wuffs_version) {
-  wuffs_crc32__ieee_hasher__check_wuffs_version(this, sizeof_star_self,
-                                                wuffs_version);
+  return wuffs_crc32__ieee_hasher__check_wuffs_version(this, sizeof_star_self,
+                                                       wuffs_version);
 }
 
 inline uint32_t  //
@@ -2309,8 +2316,8 @@ typedef struct {
   } private_impl;
 
 #ifdef __cplusplus
-  inline void check_wuffs_version(size_t sizeof_star_self,
-                                  uint64_t wuffs_version);
+  inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+  check_wuffs_version(size_t sizeof_star_self, uint64_t wuffs_version);
   inline wuffs_base__status decode(wuffs_base__io_writer a_dst,
                                    wuffs_base__io_reader a_src);
 #endif  // __cplusplus
@@ -2324,9 +2331,10 @@ typedef struct {
 // It should be called before any other wuffs_deflate__decoder__* function.
 //
 // Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
-void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 size_t sizeof_star_self,
-                                                 uint64_t wuffs_version);
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
+                                            size_t sizeof_star_self,
+                                            uint64_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2339,11 +2347,11 @@ wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
 
 #ifdef __cplusplus
 
-inline void  //
+inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
 wuffs_deflate__decoder::check_wuffs_version(size_t sizeof_star_self,
                                             uint64_t wuffs_version) {
-  wuffs_deflate__decoder__check_wuffs_version(this, sizeof_star_self,
-                                              wuffs_version);
+  return wuffs_deflate__decoder__check_wuffs_version(this, sizeof_star_self,
+                                                     wuffs_version);
 }
 
 inline wuffs_base__status  //
@@ -2420,8 +2428,8 @@ typedef struct {
   } private_impl;
 
 #ifdef __cplusplus
-  inline void check_wuffs_version(size_t sizeof_star_self,
-                                  uint64_t wuffs_version);
+  inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+  check_wuffs_version(size_t sizeof_star_self, uint64_t wuffs_version);
   inline void set_literal_width(uint32_t a_lw);
   inline wuffs_base__status decode(wuffs_base__io_writer a_dst,
                                    wuffs_base__io_reader a_src);
@@ -2436,9 +2444,10 @@ typedef struct {
 // It should be called before any other wuffs_lzw__decoder__* function.
 //
 // Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
-void wuffs_lzw__decoder__check_wuffs_version(wuffs_lzw__decoder* self,
-                                             size_t sizeof_star_self,
-                                             uint64_t wuffs_version);
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_lzw__decoder__check_wuffs_version(wuffs_lzw__decoder* self,
+                                        size_t sizeof_star_self,
+                                        uint64_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2454,11 +2463,11 @@ wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
 
 #ifdef __cplusplus
 
-inline void  //
+inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
 wuffs_lzw__decoder::check_wuffs_version(size_t sizeof_star_self,
                                         uint64_t wuffs_version) {
-  wuffs_lzw__decoder__check_wuffs_version(this, sizeof_star_self,
-                                          wuffs_version);
+  return wuffs_lzw__decoder__check_wuffs_version(this, sizeof_star_self,
+                                                 wuffs_version);
 }
 
 inline void  //
@@ -2621,8 +2630,8 @@ typedef struct {
   } private_impl;
 
 #ifdef __cplusplus
-  inline void check_wuffs_version(size_t sizeof_star_self,
-                                  uint64_t wuffs_version);
+  inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+  check_wuffs_version(size_t sizeof_star_self, uint64_t wuffs_version);
   inline wuffs_base__status decode_image_config(wuffs_base__image_config* a_dst,
                                                 wuffs_base__io_reader a_src);
   inline uint64_t num_decoded_frame_configs();
@@ -2646,9 +2655,10 @@ typedef struct {
 // It should be called before any other wuffs_gif__decoder__* function.
 //
 // Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
-void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
-                                             size_t sizeof_star_self,
-                                             uint64_t wuffs_version);
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
+                                        size_t sizeof_star_self,
+                                        uint64_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2683,11 +2693,11 @@ wuffs_gif__decoder__decode_frame(wuffs_gif__decoder* self,
 
 #ifdef __cplusplus
 
-inline void  //
+inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
 wuffs_gif__decoder::check_wuffs_version(size_t sizeof_star_self,
                                         uint64_t wuffs_version) {
-  wuffs_gif__decoder__check_wuffs_version(this, sizeof_star_self,
-                                          wuffs_version);
+  return wuffs_gif__decoder__check_wuffs_version(this, sizeof_star_self,
+                                                 wuffs_version);
 }
 
 inline wuffs_base__status  //
@@ -2795,8 +2805,8 @@ typedef struct {
   } private_impl;
 
 #ifdef __cplusplus
-  inline void check_wuffs_version(size_t sizeof_star_self,
-                                  uint64_t wuffs_version);
+  inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+  check_wuffs_version(size_t sizeof_star_self, uint64_t wuffs_version);
   inline void set_ignore_checksum(bool a_ic);
   inline wuffs_base__status decode(wuffs_base__io_writer a_dst,
                                    wuffs_base__io_reader a_src);
@@ -2811,9 +2821,10 @@ typedef struct {
 // It should be called before any other wuffs_gzip__decoder__* function.
 //
 // Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
-void wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
-                                              size_t sizeof_star_self,
-                                              uint64_t wuffs_version);
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
+                                         size_t sizeof_star_self,
+                                         uint64_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2829,11 +2840,11 @@ wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
 
 #ifdef __cplusplus
 
-inline void  //
+inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
 wuffs_gzip__decoder::check_wuffs_version(size_t sizeof_star_self,
                                          uint64_t wuffs_version) {
-  wuffs_gzip__decoder__check_wuffs_version(this, sizeof_star_self,
-                                           wuffs_version);
+  return wuffs_gzip__decoder__check_wuffs_version(this, sizeof_star_self,
+                                                  wuffs_version);
 }
 
 inline void  //
@@ -2913,8 +2924,8 @@ typedef struct {
   } private_impl;
 
 #ifdef __cplusplus
-  inline void check_wuffs_version(size_t sizeof_star_self,
-                                  uint64_t wuffs_version);
+  inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+  check_wuffs_version(size_t sizeof_star_self, uint64_t wuffs_version);
   inline void set_ignore_checksum(bool a_ic);
   inline wuffs_base__status decode(wuffs_base__io_writer a_dst,
                                    wuffs_base__io_reader a_src);
@@ -2929,9 +2940,10 @@ typedef struct {
 // It should be called before any other wuffs_zlib__decoder__* function.
 //
 // Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
-void wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
-                                              size_t sizeof_star_self,
-                                              uint64_t wuffs_version);
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
+                                         size_t sizeof_star_self,
+                                         uint64_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2947,11 +2959,11 @@ wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
 
 #ifdef __cplusplus
 
-inline void  //
+inline wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
 wuffs_zlib__decoder::check_wuffs_version(size_t sizeof_star_self,
                                          uint64_t wuffs_version) {
-  wuffs_zlib__decoder__check_wuffs_version(this, sizeof_star_self,
-                                           wuffs_version);
+  return wuffs_zlib__decoder__check_wuffs_version(this, sizeof_star_self,
+                                                  wuffs_version);
 }
 
 inline void  //
@@ -2993,6 +3005,9 @@ extern "C" {
 
 #define WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(x) (void)(x)
 
+static inline void wuffs_base__ignore_check_wuffs_version_status(
+    wuffs_base__status z) {}
+
 // WUFFS_BASE__MAGIC is a magic number to check that initializers are called.
 // It's not foolproof, given C doesn't automatically zero memory before use,
 // but it should catch 99.99% of cases.
@@ -3712,15 +3727,15 @@ static const char wuffs_base__status__string_data[] = {
     0x66, 0x66, 0x73, 0x5F, 0x76, 0x65, 0x72, 0x73, 0x69, 0x6F, 0x6E, 0x20,
     0x63, 0x61, 0x6C, 0x6C, 0x65, 0x64, 0x20, 0x74, 0x77, 0x69, 0x63, 0x65,
     0x00, 0x63, 0x68, 0x65, 0x63, 0x6B, 0x5F, 0x77, 0x75, 0x66, 0x66, 0x73,
-    0x5F, 0x76, 0x65, 0x72, 0x73, 0x69, 0x6F, 0x6E, 0x20, 0x6E, 0x6F, 0x74,
-    0x20, 0x63, 0x61, 0x6C, 0x6C, 0x65, 0x64, 0x00, 0x62, 0x61, 0x64, 0x20,
-    0x61, 0x72, 0x67, 0x75, 0x6D, 0x65, 0x6E, 0x74, 0x20, 0x28, 0x6C, 0x65,
-    0x6E, 0x67, 0x74, 0x68, 0x20, 0x74, 0x6F, 0x6F, 0x20, 0x73, 0x68, 0x6F,
-    0x72, 0x74, 0x29, 0x00, 0x62, 0x61, 0x64, 0x20, 0x72, 0x65, 0x63, 0x65,
-    0x69, 0x76, 0x65, 0x72, 0x00, 0x62, 0x61, 0x64, 0x20, 0x73, 0x69, 0x7A,
-    0x65, 0x6F, 0x66, 0x20, 0x72, 0x65, 0x63, 0x65, 0x69, 0x76, 0x65, 0x72,
-    0x00, 0x62, 0x61, 0x64, 0x20, 0x77, 0x75, 0x66, 0x66, 0x73, 0x20, 0x76,
-    0x65, 0x72, 0x73, 0x69, 0x6F, 0x6E, 0x00,
+    0x5F, 0x76, 0x65, 0x72, 0x73, 0x69, 0x6F, 0x6E, 0x20, 0x6D, 0x69, 0x73,
+    0x73, 0x69, 0x6E, 0x67, 0x00, 0x62, 0x61, 0x64, 0x20, 0x61, 0x72, 0x67,
+    0x75, 0x6D, 0x65, 0x6E, 0x74, 0x20, 0x28, 0x6C, 0x65, 0x6E, 0x67, 0x74,
+    0x68, 0x20, 0x74, 0x6F, 0x6F, 0x20, 0x73, 0x68, 0x6F, 0x72, 0x74, 0x29,
+    0x00, 0x62, 0x61, 0x64, 0x20, 0x72, 0x65, 0x63, 0x65, 0x69, 0x76, 0x65,
+    0x72, 0x00, 0x62, 0x61, 0x64, 0x20, 0x73, 0x69, 0x7A, 0x65, 0x6F, 0x66,
+    0x20, 0x72, 0x65, 0x63, 0x65, 0x69, 0x76, 0x65, 0x72, 0x00, 0x62, 0x61,
+    0x64, 0x20, 0x77, 0x75, 0x66, 0x66, 0x73, 0x20, 0x76, 0x65, 0x72, 0x73,
+    0x69, 0x6F, 0x6E, 0x00,
 };
 
 static const uint16_t wuffs_base__status__string_offsets[] = {
@@ -3752,7 +3767,7 @@ static const uint16_t wuffs_base__status__string_offsets[] = {
     0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
     0x0000, 0x0000, 0x0000, 0x0000, 0x0042, 0x0058, 0x0079, 0x0000, 0x0000,
     0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
-    0x0098, 0x00B8, 0x00C5, 0x00D9,
+    0x0095, 0x00B5, 0x00C2, 0x00D6,
 };
 
 const char*  //
@@ -3827,27 +3842,25 @@ const char* wuffs_adler32__status__string(wuffs_base__status s) {
 
 // ---------------- Initializer Implementations
 
-void wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
-                                                size_t sizeof_star_self,
-                                                uint64_t wuffs_version) {
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
+                                           size_t sizeof_star_self,
+                                           uint64_t wuffs_version) {
   if (!self) {
-    return;
+    return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
-    return;
+    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
-    return;
+    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
   }
   if (self->private_impl.magic != 0) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
-    return;
+    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
+  return WUFFS_BASE__STATUS_OK;
 }
 
 // ---------------- Function Implementations
@@ -3861,8 +3874,7 @@ wuffs_adler32__hasher__update(wuffs_adler32__hasher* self,
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return 0;
@@ -4360,28 +4372,25 @@ static const uint32_t wuffs_crc32__ieee_table[8][256] = {
 
 // ---------------- Initializer Implementations
 
-void wuffs_crc32__ieee_hasher__check_wuffs_version(
-    wuffs_crc32__ieee_hasher* self,
-    size_t sizeof_star_self,
-    uint64_t wuffs_version) {
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_crc32__ieee_hasher__check_wuffs_version(wuffs_crc32__ieee_hasher* self,
+                                              size_t sizeof_star_self,
+                                              uint64_t wuffs_version) {
   if (!self) {
-    return;
+    return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
-    return;
+    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
-    return;
+    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
   }
   if (self->private_impl.magic != 0) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
-    return;
+    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
+  return WUFFS_BASE__STATUS_OK;
 }
 
 // ---------------- Function Implementations
@@ -4395,8 +4404,7 @@ wuffs_crc32__ieee_hasher__update(wuffs_crc32__ieee_hasher* self,
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return 0;
@@ -4737,27 +4745,25 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
 
 // ---------------- Initializer Implementations
 
-void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 size_t sizeof_star_self,
-                                                 uint64_t wuffs_version) {
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
+                                            size_t sizeof_star_self,
+                                            uint64_t wuffs_version) {
   if (!self) {
-    return;
+    return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
-    return;
+    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
-    return;
+    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
   }
   if (self->private_impl.magic != 0) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
-    return;
+    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
+  return WUFFS_BASE__STATUS_OK;
 }
 
 // ---------------- Function Implementations
@@ -4772,8 +4778,7 @@ wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
     return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
@@ -6688,30 +6693,33 @@ wuffs_gif__decoder__copy_to_image_buffer(wuffs_gif__decoder* self,
 
 // ---------------- Initializer Implementations
 
-void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
-                                             size_t sizeof_star_self,
-                                             uint64_t wuffs_version) {
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
+                                        size_t sizeof_star_self,
+                                        uint64_t wuffs_version) {
   if (!self) {
-    return;
+    return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
-    return;
+    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
-    return;
+    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
   }
   if (self->private_impl.magic != 0) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
-    return;
+    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
+  }
+  {
+    wuffs_base__status z = wuffs_lzw__decoder__check_wuffs_version(
+        &self->private_impl.f_lzw, sizeof(self->private_impl.f_lzw),
+        WUFFS_VERSION);
+    if (z) {
+      return z;
+    }
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  wuffs_lzw__decoder__check_wuffs_version(&self->private_impl.f_lzw,
-                                          sizeof(self->private_impl.f_lzw),
-                                          WUFFS_VERSION);
+  return WUFFS_BASE__STATUS_OK;
 }
 
 // ---------------- Function Implementations
@@ -6726,8 +6734,7 @@ wuffs_gif__decoder__decode_image_config(wuffs_gif__decoder* self,
     return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
@@ -6811,8 +6818,7 @@ wuffs_gif__decoder__num_decoded_frame_configs(wuffs_gif__decoder* self) {
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return 0;
@@ -6829,8 +6835,7 @@ wuffs_gif__decoder__num_decoded_frames(wuffs_gif__decoder* self) {
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return 0;
@@ -6847,8 +6852,7 @@ wuffs_gif__decoder__work_buffer_size(wuffs_gif__decoder* self) {
     return ((wuffs_base__range_ii_u64){});
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return ((wuffs_base__range_ii_u64){});
@@ -6868,8 +6872,7 @@ wuffs_gif__decoder__decode_frame_config(wuffs_gif__decoder* self,
     return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
@@ -7050,8 +7053,7 @@ wuffs_gif__decoder__decode_frame(wuffs_gif__decoder* self,
     return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
@@ -8360,9 +8362,10 @@ wuffs_gif__decoder__decode_id_part1(wuffs_gif__decoder* self,
                                 .len = 1024}));
     if (self->private_impl.f_previous_lzw_decode_ended_abruptly) {
       (memset(&self->private_impl.f_lzw, 0, sizeof((wuffs_lzw__decoder){})),
-       wuffs_lzw__decoder__check_wuffs_version(&self->private_impl.f_lzw,
-                                               sizeof((wuffs_lzw__decoder){}),
-                                               WUFFS_VERSION),
+       wuffs_base__ignore_check_wuffs_version_status(
+           wuffs_lzw__decoder__check_wuffs_version(
+               &self->private_impl.f_lzw, sizeof((wuffs_lzw__decoder){}),
+               WUFFS_VERSION)),
        wuffs_base__return_empty_struct());
     }
     {
@@ -8683,33 +8686,41 @@ const char* wuffs_gzip__status__string(wuffs_base__status s) {
 
 // ---------------- Initializer Implementations
 
-void wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
-                                              size_t sizeof_star_self,
-                                              uint64_t wuffs_version) {
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
+                                         size_t sizeof_star_self,
+                                         uint64_t wuffs_version) {
   if (!self) {
-    return;
+    return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
-    return;
+    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
-    return;
+    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
   }
   if (self->private_impl.magic != 0) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
-    return;
+    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
+  }
+  {
+    wuffs_base__status z = wuffs_deflate__decoder__check_wuffs_version(
+        &self->private_impl.f_flate, sizeof(self->private_impl.f_flate),
+        WUFFS_VERSION);
+    if (z) {
+      return z;
+    }
+  }
+  {
+    wuffs_base__status z = wuffs_crc32__ieee_hasher__check_wuffs_version(
+        &self->private_impl.f_checksum, sizeof(self->private_impl.f_checksum),
+        WUFFS_VERSION);
+    if (z) {
+      return z;
+    }
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  wuffs_deflate__decoder__check_wuffs_version(
-      &self->private_impl.f_flate, sizeof(self->private_impl.f_flate),
-      WUFFS_VERSION);
-  wuffs_crc32__ieee_hasher__check_wuffs_version(
-      &self->private_impl.f_checksum, sizeof(self->private_impl.f_checksum),
-      WUFFS_VERSION);
+  return WUFFS_BASE__STATUS_OK;
 }
 
 // ---------------- Function Implementations
@@ -8722,8 +8733,7 @@ wuffs_gzip__decoder__set_ignore_checksum(wuffs_gzip__decoder* self, bool a_ic) {
     return;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return;
@@ -8742,8 +8752,7 @@ wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
     return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
@@ -9170,27 +9179,25 @@ const char* wuffs_lzw__status__string(wuffs_base__status s) {
 
 // ---------------- Initializer Implementations
 
-void wuffs_lzw__decoder__check_wuffs_version(wuffs_lzw__decoder* self,
-                                             size_t sizeof_star_self,
-                                             uint64_t wuffs_version) {
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_lzw__decoder__check_wuffs_version(wuffs_lzw__decoder* self,
+                                        size_t sizeof_star_self,
+                                        uint64_t wuffs_version) {
   if (!self) {
-    return;
+    return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
-    return;
+    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
-    return;
+    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
   }
   if (self->private_impl.magic != 0) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
-    return;
+    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
+  return WUFFS_BASE__STATUS_OK;
 }
 
 // ---------------- Function Implementations
@@ -9203,8 +9210,7 @@ wuffs_lzw__decoder__set_literal_width(wuffs_lzw__decoder* self, uint32_t a_lw) {
     return;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return;
@@ -9227,8 +9233,7 @@ wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
     return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
@@ -9523,33 +9528,41 @@ const char* wuffs_zlib__status__string(wuffs_base__status s) {
 
 // ---------------- Initializer Implementations
 
-void wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
-                                              size_t sizeof_star_self,
-                                              uint64_t wuffs_version) {
+wuffs_base__status WUFFS_BASE__WARN_UNUSED_RESULT  //
+wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
+                                         size_t sizeof_star_self,
+                                         uint64_t wuffs_version) {
   if (!self) {
-    return;
+    return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
-    return;
+    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
-    return;
+    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
   }
   if (self->private_impl.magic != 0) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
-    return;
+    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
+  }
+  {
+    wuffs_base__status z = wuffs_deflate__decoder__check_wuffs_version(
+        &self->private_impl.f_flate, sizeof(self->private_impl.f_flate),
+        WUFFS_VERSION);
+    if (z) {
+      return z;
+    }
+  }
+  {
+    wuffs_base__status z = wuffs_adler32__hasher__check_wuffs_version(
+        &self->private_impl.f_checksum, sizeof(self->private_impl.f_checksum),
+        WUFFS_VERSION);
+    if (z) {
+      return z;
+    }
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  wuffs_deflate__decoder__check_wuffs_version(
-      &self->private_impl.f_flate, sizeof(self->private_impl.f_flate),
-      WUFFS_VERSION);
-  wuffs_adler32__hasher__check_wuffs_version(
-      &self->private_impl.f_checksum, sizeof(self->private_impl.f_checksum),
-      WUFFS_VERSION);
+  return WUFFS_BASE__STATUS_OK;
 }
 
 // ---------------- Function Implementations
@@ -9562,8 +9575,7 @@ wuffs_zlib__decoder__set_ignore_checksum(wuffs_zlib__decoder* self, bool a_ic) {
     return;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return;
@@ -9582,8 +9594,7 @@ wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
     return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_NOT_CALLED;
+    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
   }
   if (self->private_impl.status < 0) {
     return self->private_impl.status;
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
