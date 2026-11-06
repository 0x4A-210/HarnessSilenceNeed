# Case ID

P046

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
    wuffs_gif__decoder dec = ((wuffs_gif__decoder){});
    wuffs_base__status z = wuffs_gif__decoder__check_wuffs_version(
        &dec, sizeof dec, WUFFS_VERSION);
    if (z) {
      return wuffs_gif__status__string(z);
    }

    wuffs_base__image_config ic = ((wuffs_base__image_config){});
    z = wuffs_gif__decoder__decode_image_config(&dec, &ic, src_reader);
    if (z) {
      ret = wuffs_gif__status__string(z);
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
    z = wuffs_base__pixel_buffer__set_from_slice(
        &pb, wuffs_base__image_config__pixel_config(&ic),
        ((wuffs_base__slice_u8){.ptr = pixbuf, .len = pixbuf_size}));
    if (z) {
      ret = wuffs_gif__status__string(z);
      goto exit;
    }

    bool seen_ok = false;
    while (true) {
      z = wuffs_gif__decoder__decode_frame(&dec, &pb, 0, 0, src_reader,
                                           ((wuffs_base__slice_u8){}));
      if (z) {
        if ((z == WUFFS_BASE__SUSPENSION_END_OF_DATA) && seen_ok) {
          z = WUFFS_BASE__STATUS_OK;
        }
        ret = wuffs_gif__status__string(z);
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
  wuffs_zlib__decoder dec = ((wuffs_zlib__decoder){});
  wuffs_base__status z =
      wuffs_zlib__decoder__check_wuffs_version(&dec, sizeof dec, WUFFS_VERSION);
  if (z) {
    return wuffs_zlib__status__string(z);
  }

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
    z = wuffs_zlib__decoder__decode(&dec, dst_writer, src_reader);
    if (z != WUFFS_BASE__SUSPENSION_SHORT_WRITE) {
      ret = wuffs_zlib__status__string(z);
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

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is a deterministic H0-identifier-anchored excerpt capped at 70,000 characters.

~~~~diff
... [unselected diff lines omitted by frozen H0-anchored rule] ...
diff --git a/cmd/wuffs-c/internal/cgen/base/base-impl.c b/cmd/wuffs-c/internal/cgen/base/base-impl.c
index 8b45f58e..e8804f69 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-impl.c
+++ b/cmd/wuffs-c/internal/cgen/base/base-impl.c
@@ -25,8 +25,8 @@
 // !! INSERT wuffs_base__status__string data.
 
 const char*  //
-wuffs_base__status__string(wuffs_base__status s) {
-  uint16_t o = wuffs_base__status__string_offsets[(uint8_t)(s >> 24)];
+wuffs_base__status__string(int32_t status_code) {
+  uint16_t o = wuffs_base__status__string_offsets[(uint8_t)(status_code >> 24)];
   return o ? wuffs_base__status__string_data + o : "unknown status";
 }
 
diff --git a/cmd/wuffs-c/internal/cgen/base/base-private.h b/cmd/wuffs-c/internal/cgen/base/base-private.h
index 53efd0f5..70dd26ed 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-private.h
+++ b/cmd/wuffs-c/internal/cgen/base/base-private.h
@@ -56,9 +56,9 @@ static inline void wuffs_base__ignore_check_wuffs_version_status(
   case n:;
 
 #define WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(n) \
-  if (status < 0) {                                             \
+  if (status.code < 0) {                                        \
     goto exit;                                                  \
-  } else if (status == 0) {                                     \
+  } else if (status.code == 0) {                                \
     goto ok;                                                    \
   }                                                             \
   coro_susp_point = n;                                          \
diff --git a/cmd/wuffs-c/internal/cgen/base/base-public.h b/cmd/wuffs-c/internal/cgen/base/base-public.h
index 4628cc6b..33e6753d 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-public.h
+++ b/cmd/wuffs-c/internal/cgen/base/base-public.h
@@ -108,27 +108,38 @@ typedef struct {
 //
 // Do not manipulate these bits directly; they are private implementation
 // details. Use methods such as wuffs_base__status__is_error instead.
-typedef int32_t wuffs_base__status;
+typedef struct {
+  int32_t code;
+} wuffs_base__status;
 
 // !! INSERT wuffs_base__status names.
 
+// TODO: turn WUFFS_BASE__MAKE_STATUS into a macro, and add a msg field.
+
+static inline wuffs_base__status  //
+WUFFS_BASE__MAKE_STATUS(int32_t code) {
+  return ((wuffs_base__status){
+      .code = code,
+  });
+}
+
 static inline bool  //
 wuffs_base__status__is_error(wuffs_base__status s) {
-  return s < 0;
+  return s.code < 0;
 }
 
 static inline bool  //
 wuffs_base__status__is_ok(wuffs_base__status s) {
-  return s == 0;
+  return s.code == 0;
 }
 
 static inline bool  //
 wuffs_base__status__is_suspension(wuffs_base__status s) {
-  return s > 0;
+  return s.code > 0;
 }
 
 const char*  //
-wuffs_base__status__string(wuffs_base__status s);
+wuffs_base__status__string(int32_t status_code);
 
 // --------
 
diff --git a/cmd/wuffs-c/internal/cgen/base/image-public.h b/cmd/wuffs-c/internal/cgen/base/image-public.h
index 0178a5cf..3b844cde 100644
--- a/cmd/wuffs-c/internal/cgen/base/image-public.h
+++ b/cmd/wuffs-c/internal/cgen/base/image-public.h
@@ -809,17 +809,18 @@ wuffs_base__pixel_buffer__set_from_slice(wuffs_base__pixel_buffer* b,
                                          wuffs_base__pixel_config* pixcfg,
                                          wuffs_base__slice_u8 pixbuf_memory) {
   if (!b) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   *b = ((wuffs_base__pixel_buffer){});
   if (!pixcfg) {
-    return WUFFS_BASE__ERROR_BAD_ARGUMENT;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_ARGUMENT);
   }
   // TODO: don't assume 1 byte per pixel. Don't assume packed.
   uint64_t wh = ((uint64_t)pixcfg->private_impl.width) *
                 ((uint64_t)pixcfg->private_impl.height);
   if (wh > pixbuf_memory.len) {
-    return WUFFS_BASE__ERROR_BAD_ARGUMENT_LENGTH_TOO_SHORT;
+    return WUFFS_BASE__MAKE_STATUS(
+        WUFFS_BASE__ERROR_BAD_ARGUMENT_LENGTH_TOO_SHORT);
   }
   b->private_impl.pixcfg = *pixcfg;
   wuffs_base__table_u8* tab = &b->private_impl.planes[0];
@@ -827,7 +828,7 @@ wuffs_base__pixel_buffer__set_from_slice(wuffs_base__pixel_buffer* b,
   tab->width = pixcfg->private_impl.width;
   tab->height = pixcfg->private_impl.height;
   tab->stride = pixcfg->private_impl.width;
-  return WUFFS_BASE__STATUS_OK;
+  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 }
 
 // The palette argument is ignored unless its length is exactly 1024.
diff --git a/release/c/wuffs-unsupported-snapshot.h b/release/c/wuffs-unsupported-snapshot.h
index 94fd2865..5c2bf172 100644
--- a/release/c/wuffs-unsupported-snapshot.h
+++ b/release/c/wuffs-unsupported-snapshot.h
@@ -132,7 +132,9 @@ typedef struct {
 //
 // Do not manipulate these bits directly; they are private implementation
 // details. Use methods such as wuffs_base__status__is_error instead.
-typedef int32_t wuffs_base__status;
+typedef struct {
+  int32_t code;
+} wuffs_base__status;
 
 #define WUFFS_BASE__STATUS_OK 0                                    // 0x00000000
 #define WUFFS_BASE__ERROR_BAD_WUFFS_VERSION -16777216              // 0xFF000000
@@ -149,23 +151,32 @@ typedef int32_t wuffs_base__status;
 #define WUFFS_BASE__SUSPENSION_SHORT_READ 33554432               // 0x02000000
 #define WUFFS_BASE__SUSPENSION_SHORT_WRITE 50331648              // 0x03000000
 
+// TODO: turn WUFFS_BASE__MAKE_STATUS into a macro, and add a msg field.
+
+static inline wuffs_base__status  //
+WUFFS_BASE__MAKE_STATUS(int32_t code) {
+  return ((wuffs_base__status){
+      .code = code,
+  });
+}
+
 static inline bool  //
 wuffs_base__status__is_error(wuffs_base__status s) {
-  return s < 0;
+  return s.code < 0;
 }
 
 static inline bool  //
 wuffs_base__status__is_ok(wuffs_base__status s) {
-  return s == 0;
+  return s.code == 0;
 }
 
 static inline bool  //
 wuffs_base__status__is_suspension(wuffs_base__status s) {
-  return s > 0;
+  return s.code > 0;
 }
 
 const char*  //
-wuffs_base__status__string(wuffs_base__status s);
+wuffs_base__status__string(int32_t status_code);
 
 // --------
 
@@ -1909,17 +1920,18 @@ wuffs_base__pixel_buffer__set_from_slice(wuffs_base__pixel_buffer* b,
                                          wuffs_base__pixel_config* pixcfg,
                                          wuffs_base__slice_u8 pixbuf_memory) {
   if (!b) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   *b = ((wuffs_base__pixel_buffer){});
   if (!pixcfg) {
-    return WUFFS_BASE__ERROR_BAD_ARGUMENT;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_ARGUMENT);
   }
   // TODO: don't assume 1 byte per pixel. Don't assume packed.
   uint64_t wh = ((uint64_t)pixcfg->private_impl.width) *
                 ((uint64_t)pixcfg->private_impl.height);
   if (wh > pixbuf_memory.len) {
-    return WUFFS_BASE__ERROR_BAD_ARGUMENT_LENGTH_TOO_SHORT;
+    return WUFFS_BASE__MAKE_STATUS(
+        WUFFS_BASE__ERROR_BAD_ARGUMENT_LENGTH_TOO_SHORT);
   }
   b->private_impl.pixcfg = *pixcfg;
   wuffs_base__table_u8* tab = &b->private_impl.planes[0];
@@ -1927,7 +1939,7 @@ wuffs_base__pixel_buffer__set_from_slice(wuffs_base__pixel_buffer* b,
   tab->width = pixcfg->private_impl.width;
   tab->height = pixcfg->private_impl.height;
   tab->stride = pixcfg->private_impl.width;
-  return WUFFS_BASE__STATUS_OK;
+  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 }
 
 // The palette argument is ignored unless its length is exactly 1024.
@@ -2038,7 +2050,7 @@ extern "C" {
 
 #define wuffs_adler32__packageid 681002  // 0x000A642A
 
-const char* wuffs_adler32__status__string(wuffs_base__status s);
+const char* wuffs_adler32__status__string(int32_t status_code);
 
 // ---------------- Public Consts
 
@@ -2121,7 +2133,7 @@ extern "C" {
 
 #define wuffs_crc32__packageid 810620  // 0x000C5E7C
 
-const char* wuffs_crc32__status__string(wuffs_base__status s);
+const char* wuffs_crc32__status__string(int32_t status_code);
 
 // ---------------- Public Consts
 
@@ -2234,7 +2246,7 @@ extern "C" {
 #define WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS \
   -1140002155  // 0xBC0CF295
 
-const char* wuffs_deflate__status__string(wuffs_base__status s);
+const char* wuffs_deflate__status__string(int32_t status_code);
 
 // ---------------- Public Consts
 
@@ -2387,7 +2399,7 @@ extern "C" {
 #define WUFFS_LZW__ERROR_BAD_CODE -15460440               // 0xFF1417A8
 #define WUFFS_LZW__ERROR_CYCLICAL_PREFIX_CHAIN -32237656  // 0xFE1417A8
 
-const char* wuffs_lzw__status__string(wuffs_base__status s);
+const char* wuffs_lzw__status__string(int32_t status_code);
 
 // ---------------- Public Consts
 
@@ -2507,7 +2519,7 @@ extern "C" {
 #define WUFFS_GIF__ERROR_INTERNAL_ERROR_INCONSISTENT_RI_WI \
   -1072724602  // 0xC00F8586
 
-const char* wuffs_gif__status__string(wuffs_base__status s);
+const char* wuffs_gif__status__string(int32_t status_code);
 
 // ---------------- Public Consts
 
@@ -2768,7 +2780,7 @@ extern "C" {
 #define WUFFS_GZIP__ERROR_BAD_ENCODING_FLAGS -49289737      // 0xFD0FE5F7
 #define WUFFS_GZIP__ERROR_BAD_HEADER -66066953              // 0xFC0FE5F7
 
-const char* wuffs_gzip__status__string(wuffs_base__status s);
+const char* wuffs_gzip__status__string(int32_t status_code);
 
 // ---------------- Public Consts
 
@@ -2891,7 +2903,7 @@ extern "C" {
 #define WUFFS_ZLIB__ERROR_TODO_UNSUPPORTED_PRESET_DICTIONARY \
   -1071677575  // 0xC01F7F79
 
-const char* wuffs_zlib__status__string(wuffs_base__status s);
+const char* wuffs_zlib__status__string(int32_t status_code);
 
 // ---------------- Public Consts
 
@@ -3038,9 +3050,9 @@ static inline void wuffs_base__ignore_check_wuffs_version_status(
   case n:;
 
 #define WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(n) \
-  if (status < 0) {                                             \
+  if (status.code < 0) {                                        \
     goto exit;                                                  \
-  } else if (status == 0) {                                     \
+  } else if (status.code == 0) {                                \
     goto ok;                                                    \
   }                                                             \
   coro_susp_point = n;                                          \
@@ -3771,8 +3783,8 @@ static const uint16_t wuffs_base__status__string_offsets[] = {
 };
 
 const char*  //
-wuffs_base__status__string(wuffs_base__status s) {
-  uint16_t o = wuffs_base__status__string_offsets[(uint8_t)(s >> 24)];
+wuffs_base__status__string(int32_t status_code) {
+  uint16_t o = wuffs_base__status__string_offsets[(uint8_t)(status_code >> 24)];
   return o ? wuffs_base__status__string_data + o : "unknown status";
 }
 
@@ -3819,13 +3831,13 @@ static const uint16_t wuffs_adler32__status__string_offsets[] = {
     0x0000, 0x0000, 0x0000, 0x0000,
 };
 
-const char* wuffs_adler32__status__string(wuffs_base__status s) {
+const char* wuffs_adler32__status__string(int32_t status_code) {
   uint16_t o;
-  switch (s & 0x1FFFFF) {
+  switch (status_code & 0x1FFFFF) {
     case 0:
-      return wuffs_base__status__string(s);
+      return wuffs_base__status__string(status_code);
     case wuffs_adler32__packageid:
-      o = wuffs_adler32__status__string_offsets[(uint8_t)(s >> 24)];
+      o = wuffs_adler32__status__string_offsets[(uint8_t)(status_code >> 24)];
       if (o) {
         return wuffs_adler32__status__string_data + o;
       }
@@ -3847,20 +3859,21 @@ wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
                                            size_t sizeof_star_self,
                                            uint64_t wuffs_version) {
   if (!self) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   if (sizeof(*self) != sizeof_star_self) {
-    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER);
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_WUFFS_VERSION);
   }
   if (self->private_impl.magic != 0) {
-    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
+    return WUFFS_BASE__MAKE_STATUS(
+        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE);
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  return WUFFS_BASE__STATUS_OK;
+  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 }
 
 // ---------------- Function Implementations
@@ -3874,9 +3887,10 @@ wuffs_adler32__hasher__update(wuffs_adler32__hasher* self,
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return 0;
   }
 
@@ -3986,13 +4000,13 @@ static const uint16_t wuffs_crc32__status__string_offsets[] = {
     0x0000, 0x0000, 0x0000, 0x0000,
 };
 
-const char* wuffs_crc32__status__string(wuffs_base__status s) {
+const char* wuffs_crc32__status__string(int32_t status_code) {
   uint16_t o;
-  switch (s & 0x1FFFFF) {
+  switch (status_code & 0x1FFFFF) {
     case 0:
-      return wuffs_base__status__string(s);
+      return wuffs_base__status__string(status_code);
     case wuffs_crc32__packageid:
-      o = wuffs_crc32__status__string_offsets[(uint8_t)(s >> 24)];
+      o = wuffs_crc32__status__string_offsets[(uint8_t)(status_code >> 24)];
       if (o) {
         return wuffs_crc32__status__string_data + o;
       }
@@ -4377,20 +4391,21 @@ wuffs_crc32__ieee_hasher__check_wuffs_version(wuffs_crc32__ieee_hasher* self,
                                               size_t sizeof_star_self,
                                               uint64_t wuffs_version) {
   if (!self) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   if (sizeof(*self) != sizeof_star_self) {
-    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER);
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_WUFFS_VERSION);
   }
   if (self->private_impl.magic != 0) {
-    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
+    return WUFFS_BASE__MAKE_STATUS(
+        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE);
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  return WUFFS_BASE__STATUS_OK;
+  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 }
 
 // ---------------- Function Implementations
@@ -4404,9 +4419,10 @@ wuffs_crc32__ieee_hasher__update(wuffs_crc32__ieee_hasher* self,
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return 0;
   }
 
@@ -4647,13 +4663,13 @@ static const uint16_t wuffs_deflate__status__string_offsets[] = {
     0x0219, 0x0245, 0x026C, 0x0299,
 };
 
-const char* wuffs_deflate__status__string(wuffs_base__status s) {
+const char* wuffs_deflate__status__string(int32_t status_code) {
   uint16_t o;
-  switch (s & 0x1FFFFF) {
+  switch (status_code & 0x1FFFFF) {
     case 0:
-      return wuffs_base__status__string(s);
+      return wuffs_base__status__string(status_code);
     case wuffs_deflate__packageid:
-      o = wuffs_deflate__status__string_offsets[(uint8_t)(s >> 24)];
+      o = wuffs_deflate__status__string_offsets[(uint8_t)(status_code >> 24)];
       if (o) {
         return wuffs_deflate__status__string_data + o;
       }
@@ -4750,20 +4766,21 @@ wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
                                             size_t sizeof_star_self,
                                             uint64_t wuffs_version) {
   if (!self) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   if (sizeof(*self) != sizeof_star_self) {
-    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER);
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_WUFFS_VERSION);
   }
   if (self->private_impl.magic != 0) {
-    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
+    return WUFFS_BASE__MAKE_STATUS(
+        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE);
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  return WUFFS_BASE__STATUS_OK;
+  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 }
 
 // ---------------- Function Implementations
@@ -4775,15 +4792,16 @@ wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
                                wuffs_base__io_writer a_dst,
                                wuffs_base__io_reader a_src) {
   if (!self) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return self->private_impl.status;
   }
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   wuffs_base__status v_z;
   wuffs_base__slice_u8 v_written;
@@ -4834,12 +4852,13 @@ wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
         }
         v_z = t_0;
       }
-      if (!(v_z > 0)) {
+      if (!(v_z.code > 0)) {
         status = v_z;
-        if (status == 0) {
+        if (status.code == 0) {
           goto ok;
-        } else if (status > 0) {
-          status = WUFFS_BASE__ERROR_CANNOT_RETURN_A_SUSPENSION;
+        } else if (status.code > 0) {
+          status = WUFFS_BASE__MAKE_STATUS(
+              WUFFS_BASE__ERROR_CANNOT_RETURN_A_SUSPENSION);
         }
         goto exit;
       }
@@ -4912,7 +4931,7 @@ static wuffs_base__status  //
 wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
                                       wuffs_base__io_writer a_dst,
                                       wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t v_final;
   uint32_t v_type;
@@ -4950,7 +4969,7 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
             goto suspend;
           }
           uint8_t t_0 = *iop_a_src++;
@@ -4973,14 +4992,14 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
         if (a_src.private_impl.buf) {
           iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
         }
-        if (status) {
+        if (status.code) {
           goto suspend;
         }
         goto label_0_continue;
       } else if (v_type == 1) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
         status = wuffs_deflate__decoder__init_fixed_huffman(self);
-        if (status) {
+        if (status.code) {
           goto suspend;
         }
       } else if (v_type == 2) {
@@ -4992,11 +5011,11 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
         if (a_src.private_impl.buf) {
           iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
         }
-        if (status) {
+        if (status.code) {
           goto suspend;
... [unselected diff lines omitted by frozen H0-anchored rule] ...
@@ -5022,14 +5041,14 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
       if (a_src.private_impl.buf) {
         iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
       }
-      if (status) {
+      if (status.code) {
         goto suspend;
       }
       if (self->private_impl.f_end_of_block) {
         goto label_0_continue;
       }
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_END_OF_BLOCK;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_END_OF_BLOCK);
       goto exit;
     }
 
@@ -5060,7 +5079,7 @@ static wuffs_base__status  //
 wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
                                             wuffs_base__io_writer a_dst,
                                             wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t v_length;
   uint32_t v_n_copied;
@@ -5111,7 +5130,8 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
 
     if ((self->private_impl.f_n_bits >= 8) ||
         ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-      status = WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
       goto exit;
     }
     self->private_impl.f_n_bits = 0;
@@ -5127,7 +5147,7 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
         while (true) {
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
             goto suspend;
           }
           uint64_t* scratch =
@@ -5148,7 +5168,8 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
     }
     if ((((v_length) & ((1 << (16)) - 1)) + ((v_length) >> (32 - (16)))) !=
         65535) {
-      status = WUFFS_DEFLATE__ERROR_INCONSISTENT_STORED_BLOCK_LENGTH;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INCONSISTENT_STORED_BLOCK_LENGTH);
       goto exit;
     }
     v_length = ((v_length) & ((1 << (16)) - 1));
@@ -5156,15 +5177,15 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
       v_n_copied = wuffs_base__io_writer__copy_n_from_reader(
           &iop_a_dst, io1_a_dst, v_length, &iop_a_src, io1_a_src);
       if (v_length <= v_n_copied) {
-        status = WUFFS_BASE__STATUS_OK;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
         goto ok;
       }
       v_length -= v_n_copied;
       if (((uint64_t)(io1_a_dst - iop_a_dst)) == 0) {
-        status = WUFFS_BASE__SUSPENSION_SHORT_WRITE;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(3);
       } else {
-        status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(4);
       }
     }
@@ -5197,7 +5218,7 @@ exit:
 
 static wuffs_base__status  //
 wuffs_deflate__decoder__init_fixed_huffman(wuffs_deflate__decoder* self) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t v_i;
 
@@ -5233,12 +5254,12 @@ wuffs_deflate__decoder__init_fixed_huffman(wuffs_deflate__decoder* self) {
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
     status = wuffs_deflate__decoder__init_huff(self, 0, 0, 288, 257);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
     status = wuffs_deflate__decoder__init_huff(self, 1, 288, 320, 0);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
 
@@ -5263,7 +5284,7 @@ exit:
 static wuffs_base__status  //
 wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
                                              wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t v_bits;
   uint32_t v_n_bits;
@@ -5322,7 +5343,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
         if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-          status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+          status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
           goto suspend;
         }
         uint8_t t_0 = *iop_a_src++;
@@ -5332,13 +5353,15 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
     }
     v_n_lit = (((v_bits) & ((1 << (5)) - 1)) + 257);
     if (v_n_lit > 286) {
-      status = WUFFS_DEFLATE__ERROR_BAD_LITERAL_LENGTH_CODE_COUNT;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_BAD_LITERAL_LENGTH_CODE_COUNT);
       goto exit;
     }
     v_bits >>= 5;
     v_n_dist = (((v_bits) & ((1 << (5)) - 1)) + 1);
     if (v_n_dist > 30) {
-      status = WUFFS_DEFLATE__ERROR_BAD_DISTANCE_CODE_COUNT;
+      status =
+          WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_DISTANCE_CODE_COUNT);
       goto exit;
     }
     v_bits >>= 5;
@@ -5351,7 +5374,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
             goto suspend;
           }
           uint8_t t_1 = *iop_a_src++;
@@ -5371,7 +5394,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
     status = wuffs_deflate__decoder__init_huff(self, 0, 0, 19, 4095);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     v_mask = ((((uint32_t)(1)) << self->private_impl.f_n_huffs_bits[0]) - 1);
@@ -5390,7 +5413,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(4);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
             goto suspend;
           }
           uint8_t t_2 = *iop_a_src++;
@@ -5400,8 +5423,8 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       }
     label_1_break:;
       if ((v_table_entry >> 24) != 128) {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
       v_table_entry = ((v_table_entry >> 8) & 255);
@@ -5416,7 +5439,8 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       if (v_table_entry == 16) {
         v_n_extra_bits = 2;
         if (v_i <= 0) {
-          status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_REPETITION;
+          status = WUFFS_BASE__MAKE_STATUS(
+              WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_REPETITION);
           goto exit;
         }
         v_rep_symbol = self->private_impl.f_code_lengths[(v_i - 1)];
@@ -5430,15 +5454,15 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
         v_rep_symbol = 0;
         v_rep_count = 11;
       } else {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
       while (v_n_bits < v_n_extra_bits) {
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(5);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
             goto suspend;
           }
           uint8_t t_3 = *iop_a_src++;
@@ -5451,7 +5475,8 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       v_n_bits -= v_n_extra_bits;
       while (v_rep_count > 0) {
         if (v_i >= (v_n_lit + v_n_dist)) {
-          status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_COUNT;
+          status = WUFFS_BASE__MAKE_STATUS(
+              WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_COUNT);
           goto exit;
         }
         self->private_impl.f_code_lengths[v_i] = v_rep_symbol;
@@ -5460,22 +5485,24 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       }
     }
     if (v_i != (v_n_lit + v_n_dist)) {
-      status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_COUNT;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_COUNT);
       goto exit;
     }
     if (self->private_impl.f_code_lengths[256] == 0) {
-      status = WUFFS_DEFLATE__ERROR_MISSING_END_OF_BLOCK_CODE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_MISSING_END_OF_BLOCK_CODE);
       goto exit;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(6);
     status = wuffs_deflate__decoder__init_huff(self, 0, 0, v_n_lit, 257);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(7);
     status = wuffs_deflate__decoder__init_huff(self, 1, v_n_lit,
                                                (v_n_lit + v_n_dist), 0);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     self->private_impl.f_bits = v_bits;
@@ -5522,7 +5549,7 @@ wuffs_deflate__decoder__init_huff(wuffs_deflate__decoder* self,
                                   uint32_t a_n_codes0,
                                   uint32_t a_n_codes1,
                                   uint32_t a_base_symbol) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint16_t v_counts[16];
   uint32_t v_i;
@@ -5554,35 +5581,37 @@ wuffs_deflate__decoder__init_huff(wuffs_deflate__decoder* self,
   v_i = a_n_codes0;
   while (v_i < a_n_codes1) {
     if (v_counts[self->private_impl.f_code_lengths[v_i]] >= 320) {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     v_counts[self->private_impl.f_code_lengths[v_i]] += 1;
     v_i += 1;
   }
   if ((((uint32_t)(v_counts[0])) + a_n_codes0) == a_n_codes1) {
-    status = WUFFS_DEFLATE__ERROR_NO_HUFFMAN_CODES;
+    status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_NO_HUFFMAN_CODES);
     goto exit;
   }
   v_remaining = 1;
   v_i = 1;
   while (v_i <= 15) {
     if (v_remaining > 1073741824) {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     v_remaining <<= 1;
     if (v_remaining < ((uint32_t)(v_counts[v_i]))) {
-      status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_OVER_SUBSCRIBED;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_OVER_SUBSCRIBED);
       goto exit;
     }
     v_remaining -= ((uint32_t)(v_counts[v_i]));
     v_i += 1;
   }
   if (v_remaining != 0) {
-    status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_UNDER_SUBSCRIBED;
+    status = WUFFS_BASE__MAKE_STATUS(
+        WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_UNDER_SUBSCRIBED);
     goto exit;
   }
   memset(v_offsets, 0, sizeof(v_offsets));
@@ -5592,30 +5621,30 @@ wuffs_deflate__decoder__init_huff(wuffs_deflate__decoder* self,
     v_offsets[v_i] = ((uint16_t)(v_n_symbols));
     v_count = ((uint32_t)(v_counts[v_i]));
     if (v_n_symbols > (320 - v_count)) {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     v_n_symbols = (v_n_symbols + v_count);
     v_i += 1;
   }
   if (v_n_symbols > 288) {
-    status =
-        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+    status = WUFFS_BASE__MAKE_STATUS(
+        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
     goto exit;
   }
   memset(v_symbols, 0, sizeof(v_symbols));
   v_i = a_n_codes0;
   while (v_i < a_n_codes1) {
     if (v_i < a_n_codes0) {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     if (self->private_impl.f_code_lengths[v_i] != 0) {
       if (v_offsets[self->private_impl.f_code_lengths[v_i]] >= 320) {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
       v_symbols[v_offsets[self->private_impl.f_code_lengths[v_i]]] =
@@ -5630,7 +5659,8 @@ wuffs_deflate__decoder__init_huff(wuffs_deflate__decoder* self,
       goto label_0_break;
     }
     if (v_min_cl >= 9) {
-      status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_MINIMUM_CODE_LENGTH;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_MINIMUM_CODE_LENGTH);
       goto exit;
     }
     v_min_cl += 1;
@@ -5642,7 +5672,7 @@ label_0_break:;
       goto label_1_break;
     }
     if (v_max_cl <= 1) {
-      status = WUFFS_DEFLATE__ERROR_NO_HUFFMAN_CODES;
+      status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_NO_HUFFMAN_CODES);
       goto exit;
     }
     v_max_cl -= 1;
@@ -5656,13 +5686,13 @@ label_1_break:;
   v_i = 0;
   if ((v_n_symbols != ((uint32_t)(v_offsets[v_max_cl]))) ||
       (v_n_symbols != ((uint32_t)(v_offsets[15])))) {
-    status =
-        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+    status = WUFFS_BASE__MAKE_STATUS(
+        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
     goto exit;
   }
   if ((a_n_codes0 + ((uint32_t)(v_symbols[0]))) >= 320) {
-    status =
-        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+    status = WUFFS_BASE__MAKE_STATUS(
+        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
     goto exit;
   }
   v_initial_high_bits = 512;
@@ -5679,8 +5709,8 @@ label_1_break:;
   v_value = 0;
   while (true) {
     if ((a_n_codes0 + ((uint32_t)(v_symbols[v_i]))) >= 320) {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     v_cl = ((uint32_t)(self->private_impl.f_code_lengths[(
@@ -5688,8 +5718,8 @@ label_1_break:;
     if (v_cl > v_prev_cl) {
       v_code <<= (v_cl - v_prev_cl);
       if (v_code >= 32768) {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
     }
@@ -5710,8 +5740,8 @@ label_1_break:;
           }
           v_remaining -= ((uint32_t)(v_counts[v_j]));
           if (v_remaining > 1073741824) {
-            status =
-                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+            status = WUFFS_BASE__MAKE_STATUS(
+                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
             goto exit;
           }
           v_remaining <<= 1;
@@ -5719,16 +5749,16 @@ label_1_break:;
         }
       label_2_break:;
         if ((v_j <= 9) || (15 < v_j)) {
-          status =
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+          status = WUFFS_BASE__MAKE_STATUS(
+              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
           goto exit;
         }
         v_tmp = (v_j - 9);
         v_initial_high_bits = (((uint32_t)(1)) << v_tmp);
         v_top = v_next_top;
         if ((v_top + (((uint32_t)(1)) << v_tmp)) > 1234) {
-          status =
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+          status = WUFFS_BASE__MAKE_STATUS(
+              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
           goto exit;
         }
         v_next_top = (v_top + (((uint32_t)(1)) << v_tmp));
@@ -5740,8 +5770,8 @@ label_1_break:;
       }
     }
     if ((v_key >= 512) || (v_counts[v_prev_cl] <= 0)) {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     v_counts[v_prev_cl] -= 1;
@@ -5761,8 +5791,8 @@ label_1_break:;
         v_value = (wuffs_deflate__dcode_magic_numbers[(v_symbol & 31)] | v_cl);
       }
     } else {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     v_high_bits = v_initial_high_bits;
@@ -5770,8 +5800,8 @@ label_1_break:;
     while (v_high_bits >= v_delta) {
... [unselected diff lines omitted by frozen H0-anchored rule] ...
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
       self->private_impl
@@ -5784,8 +5814,8 @@ label_1_break:;
     }
     v_code += 1;
     if (v_code >= 32768) {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
   }
@@ -5801,7 +5831,7 @@ static wuffs_base__status  //
 wuffs_deflate__decoder__decode_huffman_fast(wuffs_deflate__decoder* self,
                                             wuffs_base__io_writer a_dst,
                                             wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t v_bits;
   uint32_t v_n_bits;
@@ -5853,7 +5883,8 @@ wuffs_deflate__decoder__decode_huffman_fast(wuffs_deflate__decoder* self,
 
   if ((self->private_impl.f_n_bits >= 8) ||
       ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-    status = WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS;
+    status = WUFFS_BASE__MAKE_STATUS(
+        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
     goto exit;
   }
   v_bits = self->private_impl.f_bits;
@@ -5900,8 +5931,8 @@ label_0_continue:;
       v_redir_top = ((v_table_entry >> 8) & 65535);
       v_redir_mask = ((((uint32_t)(1)) << ((v_table_entry >> 4) & 15)) - 1);
       if ((v_redir_top + (v_bits & v_redir_mask)) >= 1234) {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
       v_table_entry = self->private_impl
@@ -5919,23 +5950,23 @@ label_0_continue:;
         self->private_impl.f_end_of_block = true;
         goto label_0_break;
       } else if ((v_table_entry >> 28) != 0) {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       } else if ((v_table_entry >> 27) != 0) {
-        status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
         goto exit;
       } else {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     v_length = ((v_table_entry >> 8) & 32767);
@@ -5958,8 +5989,8 @@ label_0_continue:;
     } else {
     }
     if (v_length > 258) {
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     if (v_n_bits < 15) {
@@ -5988,8 +6019,8 @@ label_0_continue:;
       v_redir_top = ((v_table_entry >> 8) & 65535);
       v_redir_mask = ((((uint32_t)(1)) << ((v_table_entry >> 4) & 15)) - 1);
       if ((v_redir_top + (v_bits & v_redir_mask)) >= 1234) {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
       v_table_entry = self->private_impl
@@ -6001,11 +6032,11 @@ label_0_continue:;
     }
     if ((v_table_entry >> 24) != 64) {
       if ((v_table_entry >> 24) == 8) {
-        status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
         goto exit;
       }
-      status =
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
       goto exit;
     }
     v_dist_minus_1 = ((v_table_entry >> 8) & 32767);
@@ -6047,8 +6078,8 @@ label_0_continue:;
... [unselected diff lines omitted by frozen H0-anchored rule] ...
           if (v_length > 258) {
-            status =
-                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+            status = WUFFS_BASE__MAKE_STATUS(
+                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
             goto exit;
           }
         } else {
@@ -6056,7 +6087,7 @@ label_0_continue:;
           v_length = 0;
         }
         if (self->private_impl.f_history_index < v_hdist) {
-          status = WUFFS_DEFLATE__ERROR_BAD_DISTANCE;
+          status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_DISTANCE);
           goto exit;
         }
         v_hdist = (self->private_impl.f_history_index - v_hdist);
@@ -6088,7 +6119,8 @@ label_0_continue:;
                      .len = (size_t)(iop_a_dst - a_dst.private_impl.bounds[0]),
                  })
                     .len))) {
-          status = WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_DISTANCE;
+          status = WUFFS_BASE__MAKE_STATUS(
+              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_DISTANCE);
           goto exit;
         }
       }
@@ -6105,7 +6137,8 @@ label_0_break:;
     if (iop_a_src > io0_a_src) {
       (iop_a_src--, wuffs_base__return_empty_struct());
     } else {
-      status = WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_I_O;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_I_O);
       goto exit;
     }
   }
@@ -6113,7 +6146,8 @@ label_0_break:;
   self->private_impl.f_n_bits = v_n_bits;
   if ((self->private_impl.f_n_bits >= 8) ||
       ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-    status = WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS;
+    status = WUFFS_BASE__MAKE_STATUS(
+        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
     goto exit;
   }
   goto exit;
@@ -6134,7 +6168,7 @@ static wuffs_base__status  //
 wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
                                             wuffs_base__io_writer a_dst,
                                             wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t v_bits;
   uint32_t v_n_bits;
@@ -6208,7 +6242,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
 
     if ((self->private_impl.f_n_bits >= 8) ||
         ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-      status = WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
       goto exit;
     }
     v_bits = self->private_impl.f_bits;
@@ -6230,7 +6265,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
             goto suspend;
           }
           uint8_t t_0 = *iop_a_src++;
@@ -6242,7 +6277,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
       if ((v_table_entry >> 31) != 0) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
         if (iop_a_dst == io1_a_dst) {
-          status = WUFFS_BASE__SUSPENSION_SHORT_WRITE;
+          status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
           goto suspend;
         }
         *iop_a_dst++ = ((uint8_t)(((v_table_entry >> 8) & 255)));
@@ -6256,8 +6291,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         v_redir_mask = ((((uint32_t)(1)) << ((v_table_entry >> 4) & 15)) - 1);
         while (true) {
           if ((v_redir_top + (v_bits & v_redir_mask)) >= 1234) {
-            status =
-                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+            status = WUFFS_BASE__MAKE_STATUS(
+                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
             goto exit;
           }
           v_table_entry =
@@ -6272,7 +6307,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           {
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
             if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-              status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+              status =
+                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
               goto suspend;
             }
             uint8_t t_1 = *iop_a_src++;
@@ -6284,7 +6320,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         if ((v_table_entry >> 31) != 0) {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(4);
           if (iop_a_dst == io1_a_dst) {
-            status = WUFFS_BASE__SUSPENSION_SHORT_WRITE;
+            status =
+                WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
             goto suspend;
           }
           *iop_a_dst++ = ((uint8_t)(((v_table_entry >> 8) & 255)));
@@ -6294,23 +6331,24 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           self->private_impl.f_end_of_block = true;
           goto label_0_break;
         } else if ((v_table_entry >> 28) != 0) {
-          status =
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+          status = WUFFS_BASE__MAKE_STATUS(
+              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
           goto exit;
         } else if ((v_table_entry >> 27) != 0) {
-          status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE;
+          status =
+              WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
           goto exit;
         } else {
-          status =
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+          status = WUFFS_BASE__MAKE_STATUS(
+              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
           goto exit;
         }
       } else if ((v_table_entry >> 27) != 0) {
-        status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
         goto exit;
       } else {
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
       v_length = ((v_table_entry >> 8) & 32767);
@@ -6320,7 +6358,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           {
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(5);
             if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-              status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+              status =
+                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
               goto suspend;
             }
             uint8_t t_2 = *iop_a_src++;
@@ -6345,7 +6384,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(6);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
             goto suspend;
           }
           uint8_t t_3 = *iop_a_src++;
@@ -6359,8 +6398,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         v_redir_mask = ((((uint32_t)(1)) << ((v_table_entry >> 4) & 15)) - 1);
         while (true) {
           if ((v_redir_top + (v_bits & v_redir_mask)) >= 1234) {
-            status =
-                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+            status = WUFFS_BASE__MAKE_STATUS(
+                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
             goto exit;
           }
           v_table_entry =
@@ -6375,7 +6414,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           {
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(7);
             if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-              status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+              status =
+                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
               goto suspend;
             }
             uint8_t t_4 = *iop_a_src++;
@@ -6387,11 +6427,12 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
       }
       if ((v_table_entry >> 24) != 64) {
         if ((v_table_entry >> 24) == 8) {
-          status = WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE;
+          status =
+              WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
           goto exit;
         }
-        status =
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE;
+        status = WUFFS_BASE__MAKE_STATUS(
+            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
         goto exit;
       }
       v_dist_minus_1 = ((v_table_entry >> 8) & 32767);
@@ -6401,7 +6442,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           {
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(8);
             if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-              status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+              status =
+                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
               goto suspend;
             }
             uint8_t t_5 = *iop_a_src++;
@@ -6441,7 +6483,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
             v_length = 0;
           }
           if (self->private_impl.f_history_index < v_hdist) {
-            status = WUFFS_DEFLATE__ERROR_BAD_DISTANCE;
+            status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_DISTANCE);
             goto exit;
           }
           v_hdist = (self->private_impl.f_history_index - v_hdist);
@@ -6463,7 +6505,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
                 goto label_5_break;
               }
             }
-            status = WUFFS_BASE__SUSPENSION_SHORT_WRITE;
+            status =
+                WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(9);
           }
         label_5_break:;
@@ -6481,7 +6524,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
               }
               v_hlen -= v_n_copied;
               v_hdist += v_n_copied;
-              status = WUFFS_BASE__SUSPENSION_SHORT_WRITE;
+              status =
+                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
               WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(10);
             }
           label_6_break:;
@@ -6498,7 +6542,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           goto label_7_break;
         }
         v_length -= v_n_copied;
-        status = WUFFS_BASE__SUSPENSION_SHORT_WRITE;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(11);
       }
     label_7_break:;
@@ -6508,7 +6552,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
     self->private_impl.f_n_bits = v_n_bits;
     if ((self->private_impl.f_n_bits >= 8) ||
         ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-      status = WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS;
+      status = WUFFS_BASE__MAKE_STATUS(
+          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
       goto exit;
     }
 
@@ -6607,19 +6652,19 @@ static const uint16_t wuffs_gif__status__string_offsets[] = {
     0x0074, 0x0084, 0x009D, 0x00B6,
 };
 
-const char* wuffs_gif__status__string(wuffs_base__status s) {
+const char* wuffs_gif__status__string(int32_t status_code) {
   uint16_t o;
-  switch (s & 0x1FFFFF) {
+  switch (status_code & 0x1FFFFF) {
     case 0:
-      return wuffs_base__status__string(s);
+      return wuffs_base__status__string(status_code);
     case wuffs_gif__packageid:
-      o = wuffs_gif__status__string_offsets[(uint8_t)(s >> 24)];
+      o = wuffs_gif__status__string_offsets[(uint8_t)(status_code >> 24)];
       if (o) {
         return wuffs_gif__status__string_data + o;
       }
       break;
     case wuffs_lzw__packageid:
-      return wuffs_lzw__status__string(s);
+      return wuffs_lzw__status__string(status_code);
   }
   return "unknown status";
 }
@@ -6698,28 +6743,29 @@ wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
                                         size_t sizeof_star_self,
                                         uint64_t wuffs_version) {
   if (!self) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   if (sizeof(*self) != sizeof_star_self) {
-    return WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER);
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    return WUFFS_BASE__ERROR_BAD_WUFFS_VERSION;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_WUFFS_VERSION);
   }
   if (self->private_impl.magic != 0) {
-    return WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
+    return WUFFS_BASE__MAKE_STATUS(
+        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE);
   }
   {
     wuffs_base__status z = wuffs_lzw__decoder__check_wuffs_version(
         &self->private_impl.f_lzw, sizeof(self->private_impl.f_lzw),
         WUFFS_VERSION);
-    if (z) {
+    if (z.code) {
       return z;
     }
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  return WUFFS_BASE__STATUS_OK;
+  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 }
 
 // ---------------- Function Implementations
@@ -6731,15 +6777,16 @@ wuffs_gif__decoder__decode_image_config(wuffs_gif__decoder* self,
                                         wuffs_base__image_config* a_dst,
                                         wuffs_base__io_reader a_src) {
   if (!self) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return self->private_impl.status;
   }
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t v_num_loops;
   bool v_ffio;
@@ -6756,22 +6803,22 @@ wuffs_gif__decoder__decode_image_config(wuffs_gif__decoder* self,
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT_0;
 
     if (self->private_impl.f_call_sequence >= 1) {
-      status = WUFFS_BASE__ERROR_INVALID_CALL_SEQUENCE;
+      status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_INVALID_CALL_SEQUENCE);
       goto exit;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
     status = wuffs_gif__decoder__decode_header(self, a_src);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
     status = wuffs_gif__decoder__decode_lsd(self, a_src);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
     status = wuffs_gif__decoder__decode_up_to_id_part1(self, a_src);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     v_num_loops = 1;
@@ -6818,9 +6865,10 @@ wuffs_gif__decoder__num_decoded_frame_configs(wuffs_gif__decoder* self) {
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return 0;
   }
 
@@ -6835,9 +6883,10 @@ wuffs_gif__decoder__num_decoded_frames(wuffs_gif__decoder* self) {
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return 0;
   }
 
@@ -6852,9 +6901,10 @@ wuffs_gif__decoder__work_buffer_size(wuffs_gif__decoder* self) {
     return ((wuffs_base__range_ii_u64){});
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return ((wuffs_base__range_ii_u64){});
   }
 
@@ -6869,15 +6919,16 @@ wuffs_gif__decoder__decode_frame_config(wuffs_gif__decoder* self,
                                         wuffs_base__frame_config* a_dst,
                                         wuffs_base__io_reader a_src) {
   if (!self) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return self->private_impl.status;
   }
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t coro_susp_point =
       self->private_impl.c_decode_frame_config[0].coro_susp_point;
@@ -6891,27 +6942,27 @@ wuffs_gif__decoder__decode_frame_config(wuffs_gif__decoder* self,
       if (self->private_impl.f_call_sequence == 0) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
         status = wuffs_gif__decoder__decode_image_config(self, NULL, a_src);
-        if (status) {
+        if (status.code) {
           goto suspend;
         }
       } else if (self->private_impl.f_call_sequence != 1) {
         if (self->private_impl.f_call_sequence == 2) {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
           status = wuffs_gif__decoder__skip_frame(self, a_src);
-          if (status) {
+          if (status.code) {
             goto suspend;
           }
         }
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
         status = wuffs_gif__decoder__decode_up_to_id_part1(self, a_src);
-        if (status) {
+        if (status.code) {
           goto suspend;
         }
       }
     }
     if (self->private_impl.f_end_of_data) {
       while (true) {
-        status = WUFFS_BASE__SUSPENSION_END_OF_DATA;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_END_OF_DATA);
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(4);
       }
     }
@@ -6963,7 +7014,7 @@ exit:
 static wuffs_base__status  //
 wuffs_gif__decoder__skip_frame(wuffs_gif__decoder* self,
                                wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint8_t v_lw;
 
@@ -6994,7 +7045,7 @@ wuffs_gif__decoder__skip_frame(wuffs_gif__decoder* self,
     {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
       if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-        status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
         goto suspend;
       }
       uint8_t t_0 = *iop_a_src++;
@@ -7008,7 +7059,7 @@ wuffs_gif__decoder__skip_frame(wuffs_gif__decoder* self,
     if (a_src.private_impl.buf) {
       iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
     }
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     self->private_impl.f_seen_graphic_control = false;
@@ -7050,19 +7101,21 @@ wuffs_gif__decoder__decode_frame(wuffs_gif__decoder* self,
                                  wuffs_base__io_reader a_src,
                                  wuffs_base__slice_u8 a_work_buffer) {
   if (!self) {
-    return WUFFS_BASE__ERROR_BAD_RECEIVER;
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status = WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
   }
-  if (self->private_impl.status < 0) {
+  if (self->private_impl.status.code < 0) {
     return self->private_impl.status;
   }
   if (!a_dst) {
-    self->private_impl.status = WUFFS_BASE__ERROR_BAD_ARGUMENT;
-    return WUFFS_BASE__ERROR_BAD_ARGUMENT;
+    self->private_impl.status =
+        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_ARGUMENT);
+    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_ARGUMENT);
   }
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint32_t coro_susp_point =
       self->private_impl.c_decode_frame[0].coro_susp_point;
@@ -7075,13 +7128,13 @@ wuffs_gif__decoder__decode_frame(wuffs_gif__decoder* self,
     if (self->private_impl.f_call_sequence != 2) {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
       status = wuffs_gif__decoder__decode_frame_config(self, NULL, a_src);
-      if (status) {
+      if (status.code) {
         goto suspend;
       }
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
     status = wuffs_gif__decoder__decode_id_part1(self, a_dst, a_src);
-    if (status) {
+    if (status.code) {
       goto suspend;
     }
     self->private_impl.f_seen_graphic_control = false;
@@ -7114,7 +7167,7 @@ exit:
 static wuffs_base__status  //
 wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
                                           wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint8_t v_block_type;
 
@@ -7147,7 +7200,7 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
       {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
         if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-          status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+          status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
           goto suspend;
         }
         uint8_t t_0 = *iop_a_src++;
@@ -7162,7 +7215,7 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
         if (a_src.private_impl.buf) {
           iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
         }
-        if (status) {
+        if (status.code) {
           goto suspend;
         }
       } else if (v_block_type == 44) {
@@ -7174,7 +7227,7 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
         if (a_src.private_impl.buf) {
           iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
         }
-        if (status) {
+        if (status.code) {
           goto suspend;
         }
         goto label_0_break;
@@ -7182,7 +7235,7 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
         self->private_impl.f_end_of_data = true;
         goto label_0_break;
       } else {
-        status = WUFFS_GIF__ERROR_BAD_BLOCK;
+        status = WUFFS_BASE__MAKE_STATUS(WUFFS_GIF__ERROR_BAD_BLOCK);
         goto exit;
       }
     }
@@ -7214,7 +7267,7 @@ exit:
 static wuffs_base__status  //
 wuffs_gif__decoder__decode_header(wuffs_gif__decoder* self,
                                   wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__STATUS_OK;
+  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
 
   uint8_t v_c[6];
   uint32_t v_i;
@@ -7251,7 +7304,7 @@ wuffs_gif__decoder__decode_header(wuffs_gif__decoder* self,
       {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
         if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-          status = WUFFS_BASE__SUSPENSION_SHORT_READ;
+          status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
           goto suspend;
         }
         uint8_t t_0 = *iop_a_src++;
@@ -7261,7 +7314,7 @@ wuffs_gif__decoder__decode_header(wuffs_gif__decoder* self,
     }
     if ((v_c[0] != 71) || (v_c[1] != 73) || (v_c[2] != 70) || (v_c[3] != 56) ||
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
