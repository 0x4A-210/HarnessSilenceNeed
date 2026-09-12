# Case ID

C032

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
    if (z.code) {
      return wuffs_gif__status__string(z.code);
    }

    wuffs_base__image_config ic = ((wuffs_base__image_config){});
    z = wuffs_gif__decoder__decode_image_config(&dec, &ic, src_reader);
    if (z.code) {
      ret = wuffs_gif__status__string(z.code);
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
    if (z.code) {
      ret = wuffs_gif__status__string(z.code);
      goto exit;
    }

    bool seen_ok = false;
    while (true) {
      z = wuffs_gif__decoder__decode_frame(&dec, &pb, 0, 0, src_reader,
                                           ((wuffs_base__slice_u8){}));
      if (z.code) {
        if ((z.code == WUFFS_BASE__SUSPENSION_END_OF_DATA) && seen_ok) {
          z.code = WUFFS_BASE__STATUS_OK;
        }
        ret = wuffs_gif__status__string(z.code);
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
  if (z.code) {
    return wuffs_zlib__status__string(z.code);
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
    if (z.code != WUFFS_BASE__SUSPENSION_SHORT_WRITE) {
      ret = wuffs_zlib__status__string(z.code);
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
diff --git a/cmd/wuffs-c/internal/cgen/base/base-private.h b/cmd/wuffs-c/internal/cgen/base/base-private.h
index 70dd26ed..0cfbbe48 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-private.h
+++ b/cmd/wuffs-c/internal/cgen/base/base-private.h
@@ -56,10 +56,10 @@ static inline void wuffs_base__ignore_check_wuffs_version_status(
   case n:;
 
 #define WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(n) \
-  if (status.code < 0) {                                        \
-    goto exit;                                                  \
-  } else if (status.code == 0) {                                \
+  if (!status) {                                                \
     goto ok;                                                    \
+  } else if (*status != '$') {                                  \
+    goto exit;                                                  \
   }                                                             \
   coro_susp_point = n;                                          \
   goto suspend;                                                 \
diff --git a/cmd/wuffs-c/internal/cgen/base/base-public.h b/cmd/wuffs-c/internal/cgen/base/base-public.h
index 459253ee..eba0c2d1 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-public.h
+++ b/cmd/wuffs-c/internal/cgen/base/base-public.h
@@ -99,45 +99,29 @@ typedef struct {
 
 // --------
 
-// A status code is either zero (OK), positive (a recoverable suspension or
-// pause in processing) or negative (a non-recoverable error). Its bits:
-//  - bit        31 (the sign bit) indicates unrecoverable-ness: an error.
-//  - bits 30 .. 24 are a package-namespaced numeric code
-//  - bits 23 .. 21 are reserved.
-//  - bits 20 ..  0 are the packageid (a namespace) as a base38 value.
+// A status is either NULL (meaning OK or no error) or string message. That
+// message is human-readable, for programmers, but it is not for end users. It
+// is not localized, and does not contain additional contextual information
+// such as a source filename.
 //
-// Do not manipulate these bits directly; they are private implementation
-// details. Use methods such as wuffs_base__status__is_error instead.
-typedef struct {
-  int32_t code;
-  const char* msg;
-} wuffs_base__status;
+// Status strings are statically allocated and should never be free'd.
+typedef const char* wuffs_base__status;
 
 // !! INSERT wuffs_base__status names.
 
-// TODO: turn WUFFS_BASE__MAKE_STATUS into a macro, and add a msg field.
-
-static inline wuffs_base__status  //
-WUFFS_BASE__MAKE_STATUS(int32_t code) {
-  return ((wuffs_base__status){
-      .code = code,
-      .msg = NULL,
-  });
-}
-
 static inline bool  //
-wuffs_base__status__is_error(wuffs_base__status s) {
-  return s.code < 0;
+wuffs_base__status__is_error(wuffs_base__status z) {
+  return z && (*z != '$');
 }
 
 static inline bool  //
-wuffs_base__status__is_ok(wuffs_base__status s) {
-  return s.code == 0;
+wuffs_base__status__is_ok(wuffs_base__status z) {
+  return z == NULL;
 }
 
 static inline bool  //
-wuffs_base__status__is_suspension(wuffs_base__status s) {
-  return s.code > 0;
+wuffs_base__status__is_suspension(wuffs_base__status z) {
+  return z && (*z == '$');
 }
 
 const char*  //
diff --git a/cmd/wuffs-c/internal/cgen/base/image-public.h b/cmd/wuffs-c/internal/cgen/base/image-public.h
index 3b844cde..06b628c3 100644
--- a/cmd/wuffs-c/internal/cgen/base/image-public.h
+++ b/cmd/wuffs-c/internal/cgen/base/image-public.h
@@ -809,18 +809,17 @@ wuffs_base__pixel_buffer__set_from_slice(wuffs_base__pixel_buffer* b,
                                          wuffs_base__pixel_config* pixcfg,
                                          wuffs_base__slice_u8 pixbuf_memory) {
   if (!b) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   *b = ((wuffs_base__pixel_buffer){});
   if (!pixcfg) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_ARGUMENT);
+    return wuffs_base__error__bad_argument;
   }
   // TODO: don't assume 1 byte per pixel. Don't assume packed.
   uint64_t wh = ((uint64_t)pixcfg->private_impl.width) *
                 ((uint64_t)pixcfg->private_impl.height);
   if (wh > pixbuf_memory.len) {
-    return WUFFS_BASE__MAKE_STATUS(
-        WUFFS_BASE__ERROR_BAD_ARGUMENT_LENGTH_TOO_SHORT);
+    return wuffs_base__error__bad_argument_length_too_short;
   }
   b->private_impl.pixcfg = *pixcfg;
   wuffs_base__table_u8* tab = &b->private_impl.planes[0];
@@ -828,7 +827,7 @@ wuffs_base__pixel_buffer__set_from_slice(wuffs_base__pixel_buffer* b,
   tab->width = pixcfg->private_impl.width;
   tab->height = pixcfg->private_impl.height;
   tab->stride = pixcfg->private_impl.width;
-  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  return NULL;
 }
 
 // The palette argument is ignored unless its length is exactly 1024.
diff --git a/release/c/wuffs-unsupported-snapshot.h b/release/c/wuffs-unsupported-snapshot.h
index 891ca333..a665f79a 100644
--- a/release/c/wuffs-unsupported-snapshot.h
+++ b/release/c/wuffs-unsupported-snapshot.h
@@ -123,19 +123,13 @@ typedef struct {
 
 // --------
 
-// A status code is either zero (OK), positive (a recoverable suspension or
-// pause in processing) or negative (a non-recoverable error). Its bits:
-//  - bit        31 (the sign bit) indicates unrecoverable-ness: an error.
-//  - bits 30 .. 24 are a package-namespaced numeric code
-//  - bits 23 .. 21 are reserved.
-//  - bits 20 ..  0 are the packageid (a namespace) as a base38 value.
+// A status is either NULL (meaning OK or no error) or string message. That
+// message is human-readable, for programmers, but it is not for end users. It
+// is not localized, and does not contain additional contextual information
+// such as a source filename.
 //
-// Do not manipulate these bits directly; they are private implementation
-// details. Use methods such as wuffs_base__status__is_error instead.
-typedef struct {
-  int32_t code;
-  const char* msg;
-} wuffs_base__status;
+// Status strings are statically allocated and should never be free'd.
+typedef const char* wuffs_base__status;
 
 #define WUFFS_BASE__STATUS_OK 0                                    // 0x00000000
 #define WUFFS_BASE__ERROR_BAD_WUFFS_VERSION -16777216              // 0xFF000000
@@ -165,29 +159,19 @@ extern const char* wuffs_base__suspension__end_of_data;
 extern const char* wuffs_base__suspension__short_read;
 extern const char* wuffs_base__suspension__short_write;
 
-// TODO: turn WUFFS_BASE__MAKE_STATUS into a macro, and add a msg field.
-
-static inline wuffs_base__status  //
-WUFFS_BASE__MAKE_STATUS(int32_t code) {
-  return ((wuffs_base__status){
-      .code = code,
-      .msg = NULL,
-  });
-}
-
 static inline bool  //
-wuffs_base__status__is_error(wuffs_base__status s) {
-  return s.code < 0;
+wuffs_base__status__is_error(wuffs_base__status z) {
+  return z && (*z != '$');
 }
 
 static inline bool  //
-wuffs_base__status__is_ok(wuffs_base__status s) {
-  return s.code == 0;
+wuffs_base__status__is_ok(wuffs_base__status z) {
+  return z == NULL;
 }
 
 static inline bool  //
-wuffs_base__status__is_suspension(wuffs_base__status s) {
-  return s.code > 0;
+wuffs_base__status__is_suspension(wuffs_base__status z) {
+  return z && (*z == '$');
 }
 
 const char*  //
@@ -1935,18 +1919,17 @@ wuffs_base__pixel_buffer__set_from_slice(wuffs_base__pixel_buffer* b,
                                          wuffs_base__pixel_config* pixcfg,
                                          wuffs_base__slice_u8 pixbuf_memory) {
   if (!b) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   *b = ((wuffs_base__pixel_buffer){});
   if (!pixcfg) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_ARGUMENT);
+    return wuffs_base__error__bad_argument;
   }
   // TODO: don't assume 1 byte per pixel. Don't assume packed.
   uint64_t wh = ((uint64_t)pixcfg->private_impl.width) *
                 ((uint64_t)pixcfg->private_impl.height);
   if (wh > pixbuf_memory.len) {
-    return WUFFS_BASE__MAKE_STATUS(
-        WUFFS_BASE__ERROR_BAD_ARGUMENT_LENGTH_TOO_SHORT);
+    return wuffs_base__error__bad_argument_length_too_short;
   }
   b->private_impl.pixcfg = *pixcfg;
   wuffs_base__table_u8* tab = &b->private_impl.planes[0];
@@ -1954,7 +1937,7 @@ wuffs_base__pixel_buffer__set_from_slice(wuffs_base__pixel_buffer* b,
   tab->width = pixcfg->private_impl.width;
   tab->height = pixcfg->private_impl.height;
   tab->stride = pixcfg->private_impl.width;
-  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  return NULL;
 }
 
 // The palette argument is ignored unless its length is exactly 1024.
@@ -3101,10 +3084,10 @@ static inline void wuffs_base__ignore_check_wuffs_version_status(
   case n:;
 
 #define WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(n) \
-  if (status.code < 0) {                                        \
-    goto exit;                                                  \
-  } else if (status.code == 0) {                                \
+  if (!status) {                                                \
     goto ok;                                                    \
+  } else if (*status != '$') {                                  \
+    goto exit;                                                  \
   }                                                             \
   coro_susp_point = n;                                          \
   goto suspend;                                                 \
@@ -3937,21 +3920,20 @@ wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
                                            size_t sizeof_star_self,
                                            uint64_t wuffs_version) {
   if (!self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER);
+    return wuffs_base__error__bad_sizeof_receiver;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_WUFFS_VERSION);
+    return wuffs_base__error__bad_wuffs_version;
   }
   if (self->private_impl.magic != 0) {
-    return WUFFS_BASE__MAKE_STATUS(
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE);
+    return wuffs_base__error__check_wuffs_version_called_twice;
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  return NULL;
 }
 
 // ---------------- Function Implementations
@@ -3965,10 +3947,9 @@ wuffs_adler32__hasher__update(wuffs_adler32__hasher* self,
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return 0;
   }
 
@@ -4469,21 +4450,20 @@ wuffs_crc32__ieee_hasher__check_wuffs_version(wuffs_crc32__ieee_hasher* self,
                                               size_t sizeof_star_self,
                                               uint64_t wuffs_version) {
   if (!self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER);
+    return wuffs_base__error__bad_sizeof_receiver;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_WUFFS_VERSION);
+    return wuffs_base__error__bad_wuffs_version;
   }
   if (self->private_impl.magic != 0) {
-    return WUFFS_BASE__MAKE_STATUS(
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE);
+    return wuffs_base__error__check_wuffs_version_called_twice;
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  return NULL;
 }
 
 // ---------------- Function Implementations
@@ -4497,10 +4477,9 @@ wuffs_crc32__ieee_hasher__update(wuffs_crc32__ieee_hasher* self,
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return 0;
   }
 
@@ -4882,21 +4861,20 @@ wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
                                             size_t sizeof_star_self,
                                             uint64_t wuffs_version) {
   if (!self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER);
+    return wuffs_base__error__bad_sizeof_receiver;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_WUFFS_VERSION);
+    return wuffs_base__error__bad_wuffs_version;
   }
   if (self->private_impl.magic != 0) {
-    return WUFFS_BASE__MAKE_STATUS(
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE);
+    return wuffs_base__error__check_wuffs_version_called_twice;
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  return NULL;
 }
 
 // ---------------- Function Implementations
@@ -4908,16 +4886,15 @@ wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
                                wuffs_base__io_writer a_dst,
                                wuffs_base__io_reader a_src) {
   if (!self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return self->private_impl.status;
   }
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   wuffs_base__status v_z;
   wuffs_base__slice_u8 v_written;
@@ -4970,11 +4947,10 @@ wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
       }
       if (!wuffs_base__status__is_suspension(v_z)) {
         status = v_z;
-        if (status.code == 0) {
+        if (!status) {
           goto ok;
-        } else if (status.code > 0) {
-          status = WUFFS_BASE__MAKE_STATUS(
-              WUFFS_BASE__ERROR_CANNOT_RETURN_A_SUSPENSION);
+        } else if (wuffs_base__status__is_suspension(status)) {
+          status = wuffs_base__error__cannot_return_a_suspension;
         }
         goto exit;
       }
@@ -5047,7 +5023,7 @@ static wuffs_base__status  //
 wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
                                       wuffs_base__io_writer a_dst,
                                       wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t v_final;
   uint32_t v_type;
@@ -5085,7 +5061,7 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint8_t t_0 = *iop_a_src++;
@@ -5108,14 +5084,14 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
         if (a_src.private_impl.buf) {
           iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
         }
-        if (status.code) {
+        if (status) {
           goto suspend;
         }
         goto label_0_continue;
       } else if (v_type == 1) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
         status = wuffs_deflate__decoder__init_fixed_huffman(self);
-        if (status.code) {
+        if (status) {
           goto suspend;
         }
       } else if (v_type == 2) {
@@ -5127,11 +5103,11 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
         if (a_src.private_impl.buf) {
           iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
         }
-        if (status.code) {
+        if (status) {
           goto suspend;
... [unselected diff lines omitted by frozen H0-anchored rule] ...
@@ -5157,14 +5133,14 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
       if (a_src.private_impl.buf) {
         iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
       }
-      if (status.code) {
+      if (status) {
         goto suspend;
       }
       if (self->private_impl.f_end_of_block) {
         goto label_0_continue;
       }
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_END_OF_BLOCK);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_end_of_block;
       goto exit;
     }
 
@@ -5195,7 +5171,7 @@ static wuffs_base__status  //
 wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
                                             wuffs_base__io_writer a_dst,
                                             wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t v_length;
   uint32_t v_n_copied;
@@ -5246,8 +5222,7 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
 
     if ((self->private_impl.f_n_bits >= 8) ||
         ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
+      status = wuffs_deflate__error__internal_error_inconsistent_n_bits;
       goto exit;
     }
     self->private_impl.f_n_bits = 0;
@@ -5263,7 +5238,7 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
         while (true) {
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint64_t* scratch =
@@ -5284,8 +5259,7 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
     }
     if ((((v_length) & ((1 << (16)) - 1)) + ((v_length) >> (32 - (16)))) !=
         65535) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INCONSISTENT_STORED_BLOCK_LENGTH);
+      status = wuffs_deflate__error__inconsistent_stored_block_length;
       goto exit;
     }
     v_length = ((v_length) & ((1 << (16)) - 1));
@@ -5293,15 +5267,15 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
       v_n_copied = wuffs_base__io_writer__copy_n_from_reader(
           &iop_a_dst, io1_a_dst, v_length, &iop_a_src, io1_a_src);
       if (v_length <= v_n_copied) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+        status = NULL;
         goto ok;
       }
       v_length -= v_n_copied;
       if (((uint64_t)(io1_a_dst - iop_a_dst)) == 0) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
+        status = wuffs_base__suspension__short_write;
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(3);
       } else {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+        status = wuffs_base__suspension__short_read;
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(4);
       }
     }
@@ -5334,7 +5308,7 @@ exit:
 
 static wuffs_base__status  //
 wuffs_deflate__decoder__init_fixed_huffman(wuffs_deflate__decoder* self) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t v_i;
 
@@ -5370,12 +5344,12 @@ wuffs_deflate__decoder__init_fixed_huffman(wuffs_deflate__decoder* self) {
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
     status = wuffs_deflate__decoder__init_huff(self, 0, 0, 288, 257);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
     status = wuffs_deflate__decoder__init_huff(self, 1, 288, 320, 0);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
 
@@ -5400,7 +5374,7 @@ exit:
 static wuffs_base__status  //
 wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
                                              wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t v_bits;
   uint32_t v_n_bits;
@@ -5459,7 +5433,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
         if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-          status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+          status = wuffs_base__suspension__short_read;
           goto suspend;
         }
         uint8_t t_0 = *iop_a_src++;
@@ -5469,15 +5443,13 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
     }
     v_n_lit = (((v_bits) & ((1 << (5)) - 1)) + 257);
     if (v_n_lit > 286) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_BAD_LITERAL_LENGTH_CODE_COUNT);
+      status = wuffs_deflate__error__bad_literal_length_code_count;
       goto exit;
     }
     v_bits >>= 5;
     v_n_dist = (((v_bits) & ((1 << (5)) - 1)) + 1);
     if (v_n_dist > 30) {
-      status =
-          WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_DISTANCE_CODE_COUNT);
+      status = wuffs_deflate__error__bad_distance_code_count;
       goto exit;
     }
     v_bits >>= 5;
@@ -5490,7 +5462,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint8_t t_1 = *iop_a_src++;
@@ -5510,7 +5482,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
     status = wuffs_deflate__decoder__init_huff(self, 0, 0, 19, 4095);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     v_mask = ((((uint32_t)(1)) << self->private_impl.f_n_huffs_bits[0]) - 1);
@@ -5529,7 +5501,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(4);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint8_t t_2 = *iop_a_src++;
@@ -5539,8 +5511,8 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       }
     label_1_break:;
       if ((v_table_entry >> 24) != 128) {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
       v_table_entry = ((v_table_entry >> 8) & 255);
@@ -5555,8 +5527,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       if (v_table_entry == 16) {
         v_n_extra_bits = 2;
         if (v_i <= 0) {
-          status = WUFFS_BASE__MAKE_STATUS(
-              WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_REPETITION);
+          status = wuffs_deflate__error__bad_huffman_code_length_repetition;
           goto exit;
         }
         v_rep_symbol = self->private_impl.f_code_lengths[(v_i - 1)];
@@ -5570,15 +5541,15 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
         v_rep_symbol = 0;
         v_rep_count = 11;
       } else {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
       while (v_n_bits < v_n_extra_bits) {
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(5);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint8_t t_3 = *iop_a_src++;
@@ -5591,8 +5562,7 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       v_n_bits -= v_n_extra_bits;
       while (v_rep_count > 0) {
         if (v_i >= (v_n_lit + v_n_dist)) {
-          status = WUFFS_BASE__MAKE_STATUS(
-              WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_COUNT);
+          status = wuffs_deflate__error__bad_huffman_code_length_count;
           goto exit;
         }
         self->private_impl.f_code_lengths[v_i] = v_rep_symbol;
@@ -5601,24 +5571,22 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
       }
     }
     if (v_i != (v_n_lit + v_n_dist)) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_LENGTH_COUNT);
+      status = wuffs_deflate__error__bad_huffman_code_length_count;
       goto exit;
     }
     if (self->private_impl.f_code_lengths[256] == 0) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_MISSING_END_OF_BLOCK_CODE);
+      status = wuffs_deflate__error__missing_end_of_block_code;
       goto exit;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(6);
     status = wuffs_deflate__decoder__init_huff(self, 0, 0, v_n_lit, 257);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(7);
     status = wuffs_deflate__decoder__init_huff(self, 1, v_n_lit,
                                                (v_n_lit + v_n_dist), 0);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     self->private_impl.f_bits = v_bits;
@@ -5665,7 +5633,7 @@ wuffs_deflate__decoder__init_huff(wuffs_deflate__decoder* self,
                                   uint32_t a_n_codes0,
                                   uint32_t a_n_codes1,
                                   uint32_t a_base_symbol) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint16_t v_counts[16];
   uint32_t v_i;
@@ -5697,37 +5665,35 @@ wuffs_deflate__decoder__init_huff(wuffs_deflate__decoder* self,
   v_i = a_n_codes0;
   while (v_i < a_n_codes1) {
     if (v_counts[self->private_impl.f_code_lengths[v_i]] >= 320) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     v_counts[self->private_impl.f_code_lengths[v_i]] += 1;
     v_i += 1;
   }
   if ((((uint32_t)(v_counts[0])) + a_n_codes0) == a_n_codes1) {
-    status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_NO_HUFFMAN_CODES);
+    status = wuffs_deflate__error__no_huffman_codes;
     goto exit;
   }
   v_remaining = 1;
   v_i = 1;
   while (v_i <= 15) {
     if (v_remaining > 1073741824) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     v_remaining <<= 1;
     if (v_remaining < ((uint32_t)(v_counts[v_i]))) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_OVER_SUBSCRIBED);
+      status = wuffs_deflate__error__bad_huffman_code_over_subscribed;
       goto exit;
     }
     v_remaining -= ((uint32_t)(v_counts[v_i]));
     v_i += 1;
   }
   if (v_remaining != 0) {
-    status = WUFFS_BASE__MAKE_STATUS(
-        WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE_UNDER_SUBSCRIBED);
+    status = wuffs_deflate__error__bad_huffman_code_under_subscribed;
     goto exit;
   }
   memset(v_offsets, 0, sizeof(v_offsets));
@@ -5737,30 +5703,30 @@ wuffs_deflate__decoder__init_huff(wuffs_deflate__decoder* self,
     v_offsets[v_i] = ((uint16_t)(v_n_symbols));
     v_count = ((uint32_t)(v_counts[v_i]));
     if (v_n_symbols > (320 - v_count)) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     v_n_symbols = (v_n_symbols + v_count);
     v_i += 1;
   }
   if (v_n_symbols > 288) {
-    status = WUFFS_BASE__MAKE_STATUS(
-        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+    status =
+        wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
     goto exit;
   }
   memset(v_symbols, 0, sizeof(v_symbols));
   v_i = a_n_codes0;
   while (v_i < a_n_codes1) {
     if (v_i < a_n_codes0) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     if (self->private_impl.f_code_lengths[v_i] != 0) {
       if (v_offsets[self->private_impl.f_code_lengths[v_i]] >= 320) {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
       v_symbols[v_offsets[self->private_impl.f_code_lengths[v_i]]] =
@@ -5775,8 +5741,7 @@ wuffs_deflate__decoder__init_huff(wuffs_deflate__decoder* self,
       goto label_0_break;
     }
     if (v_min_cl >= 9) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_MINIMUM_CODE_LENGTH);
+      status = wuffs_deflate__error__bad_huffman_minimum_code_length;
       goto exit;
     }
     v_min_cl += 1;
@@ -5788,7 +5753,7 @@ label_0_break:;
       goto label_1_break;
     }
     if (v_max_cl <= 1) {
-      status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_NO_HUFFMAN_CODES);
+      status = wuffs_deflate__error__no_huffman_codes;
       goto exit;
     }
     v_max_cl -= 1;
@@ -5802,13 +5767,13 @@ label_1_break:;
   v_i = 0;
   if ((v_n_symbols != ((uint32_t)(v_offsets[v_max_cl]))) ||
       (v_n_symbols != ((uint32_t)(v_offsets[15])))) {
-    status = WUFFS_BASE__MAKE_STATUS(
-        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+    status =
+        wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
     goto exit;
   }
   if ((a_n_codes0 + ((uint32_t)(v_symbols[0]))) >= 320) {
-    status = WUFFS_BASE__MAKE_STATUS(
-        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+    status =
+        wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
     goto exit;
   }
   v_initial_high_bits = 512;
@@ -5825,8 +5790,8 @@ label_1_break:;
   v_value = 0;
   while (true) {
     if ((a_n_codes0 + ((uint32_t)(v_symbols[v_i]))) >= 320) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     v_cl = ((uint32_t)(self->private_impl.f_code_lengths[(
@@ -5834,8 +5799,8 @@ label_1_break:;
     if (v_cl > v_prev_cl) {
       v_code <<= (v_cl - v_prev_cl);
       if (v_code >= 32768) {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
     }
@@ -5856,8 +5821,8 @@ label_1_break:;
           }
           v_remaining -= ((uint32_t)(v_counts[v_j]));
           if (v_remaining > 1073741824) {
-            status = WUFFS_BASE__MAKE_STATUS(
-                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+            status =
+                wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
             goto exit;
           }
           v_remaining <<= 1;
@@ -5865,16 +5830,16 @@ label_1_break:;
         }
       label_2_break:;
         if ((v_j <= 9) || (15 < v_j)) {
-          status = WUFFS_BASE__MAKE_STATUS(
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+          status =
+              wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
           goto exit;
         }
         v_tmp = (v_j - 9);
         v_initial_high_bits = (((uint32_t)(1)) << v_tmp);
         v_top = v_next_top;
         if ((v_top + (((uint32_t)(1)) << v_tmp)) > 1234) {
-          status = WUFFS_BASE__MAKE_STATUS(
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+          status =
+              wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
           goto exit;
         }
         v_next_top = (v_top + (((uint32_t)(1)) << v_tmp));
@@ -5886,8 +5851,8 @@ label_1_break:;
       }
     }
     if ((v_key >= 512) || (v_counts[v_prev_cl] <= 0)) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     v_counts[v_prev_cl] -= 1;
@@ -5907,8 +5872,8 @@ label_1_break:;
         v_value = (wuffs_deflate__dcode_magic_numbers[(v_symbol & 31)] | v_cl);
       }
     } else {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     v_high_bits = v_initial_high_bits;
@@ -5916,8 +5881,8 @@ label_1_break:;
     while (v_high_bits >= v_delta) {
... [unselected diff lines omitted by frozen H0-anchored rule] ...
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
       self->private_impl
@@ -5930,8 +5895,8 @@ label_1_break:;
     }
     v_code += 1;
     if (v_code >= 32768) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
   }
@@ -5947,7 +5912,7 @@ static wuffs_base__status  //
 wuffs_deflate__decoder__decode_huffman_fast(wuffs_deflate__decoder* self,
                                             wuffs_base__io_writer a_dst,
                                             wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t v_bits;
   uint32_t v_n_bits;
@@ -5999,8 +5964,7 @@ wuffs_deflate__decoder__decode_huffman_fast(wuffs_deflate__decoder* self,
 
   if ((self->private_impl.f_n_bits >= 8) ||
       ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-    status = WUFFS_BASE__MAKE_STATUS(
-        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
+    status = wuffs_deflate__error__internal_error_inconsistent_n_bits;
     goto exit;
   }
   v_bits = self->private_impl.f_bits;
@@ -6047,8 +6011,8 @@ label_0_continue:;
       v_redir_top = ((v_table_entry >> 8) & 65535);
       v_redir_mask = ((((uint32_t)(1)) << ((v_table_entry >> 4) & 15)) - 1);
       if ((v_redir_top + (v_bits & v_redir_mask)) >= 1234) {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
       v_table_entry = self->private_impl
@@ -6066,23 +6030,23 @@ label_0_continue:;
         self->private_impl.f_end_of_block = true;
         goto label_0_break;
       } else if ((v_table_entry >> 28) != 0) {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       } else if ((v_table_entry >> 27) != 0) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
+        status = wuffs_deflate__error__bad_huffman_code;
         goto exit;
       } else {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     v_length = ((v_table_entry >> 8) & 32767);
@@ -6105,8 +6069,8 @@ label_0_continue:;
     } else {
     }
     if (v_length > 258) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     if (v_n_bits < 15) {
@@ -6135,8 +6099,8 @@ label_0_continue:;
       v_redir_top = ((v_table_entry >> 8) & 65535);
       v_redir_mask = ((((uint32_t)(1)) << ((v_table_entry >> 4) & 15)) - 1);
       if ((v_redir_top + (v_bits & v_redir_mask)) >= 1234) {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
       v_table_entry = self->private_impl
@@ -6148,11 +6112,11 @@ label_0_continue:;
     }
     if ((v_table_entry >> 24) != 64) {
       if ((v_table_entry >> 24) == 8) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
+        status = wuffs_deflate__error__bad_huffman_code;
         goto exit;
       }
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+      status =
+          wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
       goto exit;
     }
     v_dist_minus_1 = ((v_table_entry >> 8) & 32767);
@@ -6194,8 +6158,8 @@ label_0_continue:;
... [unselected diff lines omitted by frozen H0-anchored rule] ...
           if (v_length > 258) {
-            status = WUFFS_BASE__MAKE_STATUS(
-                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+            status =
+                wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
             goto exit;
           }
         } else {
@@ -6203,7 +6167,7 @@ label_0_continue:;
           v_length = 0;
         }
         if (self->private_impl.f_history_index < v_hdist) {
-          status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_DISTANCE);
+          status = wuffs_deflate__error__bad_distance;
           goto exit;
         }
         v_hdist = (self->private_impl.f_history_index - v_hdist);
@@ -6235,8 +6199,7 @@ label_0_continue:;
                      .len = (size_t)(iop_a_dst - a_dst.private_impl.bounds[0]),
                  })
                     .len))) {
-          status = WUFFS_BASE__MAKE_STATUS(
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_DISTANCE);
+          status = wuffs_deflate__error__internal_error_inconsistent_distance;
           goto exit;
         }
       }
@@ -6253,8 +6216,7 @@ label_0_break:;
     if (iop_a_src > io0_a_src) {
       (iop_a_src--, wuffs_base__return_empty_struct());
     } else {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_I_O);
+      status = wuffs_deflate__error__internal_error_inconsistent_i_o;
       goto exit;
     }
   }
@@ -6262,8 +6224,7 @@ label_0_break:;
   self->private_impl.f_n_bits = v_n_bits;
   if ((self->private_impl.f_n_bits >= 8) ||
       ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-    status = WUFFS_BASE__MAKE_STATUS(
-        WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
+    status = wuffs_deflate__error__internal_error_inconsistent_n_bits;
     goto exit;
   }
   goto exit;
@@ -6284,7 +6245,7 @@ static wuffs_base__status  //
 wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
                                             wuffs_base__io_writer a_dst,
                                             wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t v_bits;
   uint32_t v_n_bits;
@@ -6358,8 +6319,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
 
     if ((self->private_impl.f_n_bits >= 8) ||
         ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
+      status = wuffs_deflate__error__internal_error_inconsistent_n_bits;
       goto exit;
     }
     v_bits = self->private_impl.f_bits;
@@ -6381,7 +6341,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint8_t t_0 = *iop_a_src++;
@@ -6393,7 +6353,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
       if ((v_table_entry >> 31) != 0) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
         if (iop_a_dst == io1_a_dst) {
-          status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
+          status = wuffs_base__suspension__short_write;
           goto suspend;
         }
         *iop_a_dst++ = ((uint8_t)(((v_table_entry >> 8) & 255)));
@@ -6407,8 +6367,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         v_redir_mask = ((((uint32_t)(1)) << ((v_table_entry >> 4) & 15)) - 1);
         while (true) {
           if ((v_redir_top + (v_bits & v_redir_mask)) >= 1234) {
-            status = WUFFS_BASE__MAKE_STATUS(
-                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+            status =
+                wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
             goto exit;
           }
           v_table_entry =
@@ -6423,8 +6383,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           {
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
             if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-              status =
-                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+              status = wuffs_base__suspension__short_read;
               goto suspend;
             }
             uint8_t t_1 = *iop_a_src++;
@@ -6436,8 +6395,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         if ((v_table_entry >> 31) != 0) {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(4);
           if (iop_a_dst == io1_a_dst) {
-            status =
-                WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
+            status = wuffs_base__suspension__short_write;
             goto suspend;
           }
           *iop_a_dst++ = ((uint8_t)(((v_table_entry >> 8) & 255)));
@@ -6447,24 +6405,23 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           self->private_impl.f_end_of_block = true;
           goto label_0_break;
         } else if ((v_table_entry >> 28) != 0) {
-          status = WUFFS_BASE__MAKE_STATUS(
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+          status =
+              wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
           goto exit;
         } else if ((v_table_entry >> 27) != 0) {
-          status =
-              WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
+          status = wuffs_deflate__error__bad_huffman_code;
           goto exit;
         } else {
-          status = WUFFS_BASE__MAKE_STATUS(
-              WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+          status =
+              wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
           goto exit;
         }
       } else if ((v_table_entry >> 27) != 0) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
+        status = wuffs_deflate__error__bad_huffman_code;
         goto exit;
       } else {
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
       v_length = ((v_table_entry >> 8) & 32767);
@@ -6474,8 +6431,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           {
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(5);
             if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-              status =
-                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+              status = wuffs_base__suspension__short_read;
               goto suspend;
             }
             uint8_t t_2 = *iop_a_src++;
@@ -6500,7 +6456,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(6);
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint8_t t_3 = *iop_a_src++;
@@ -6514,8 +6470,8 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
         v_redir_mask = ((((uint32_t)(1)) << ((v_table_entry >> 4) & 15)) - 1);
         while (true) {
           if ((v_redir_top + (v_bits & v_redir_mask)) >= 1234) {
-            status = WUFFS_BASE__MAKE_STATUS(
-                WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+            status =
+                wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
             goto exit;
           }
           v_table_entry =
@@ -6530,8 +6486,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           {
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(7);
             if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-              status =
-                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+              status = wuffs_base__suspension__short_read;
               goto suspend;
             }
             uint8_t t_4 = *iop_a_src++;
@@ -6543,12 +6498,11 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
       }
       if ((v_table_entry >> 24) != 64) {
         if ((v_table_entry >> 24) == 8) {
-          status =
-              WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_HUFFMAN_CODE);
+          status = wuffs_deflate__error__bad_huffman_code;
           goto exit;
         }
-        status = WUFFS_BASE__MAKE_STATUS(
-            WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_HUFFMAN_DECODER_STATE);
+        status =
+            wuffs_deflate__error__internal_error_inconsistent_huffman_decoder_state;
         goto exit;
       }
       v_dist_minus_1 = ((v_table_entry >> 8) & 32767);
@@ -6558,8 +6512,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           {
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(8);
             if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-              status =
-                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+              status = wuffs_base__suspension__short_read;
               goto suspend;
             }
             uint8_t t_5 = *iop_a_src++;
@@ -6599,7 +6552,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
             v_length = 0;
           }
           if (self->private_impl.f_history_index < v_hdist) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_DEFLATE__ERROR_BAD_DISTANCE);
+            status = wuffs_deflate__error__bad_distance;
             goto exit;
           }
           v_hdist = (self->private_impl.f_history_index - v_hdist);
@@ -6621,8 +6574,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
                 goto label_5_break;
               }
             }
-            status =
-                WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
+            status = wuffs_base__suspension__short_write;
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(9);
           }
         label_5_break:;
@@ -6640,8 +6592,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
               }
               v_hlen -= v_n_copied;
               v_hdist += v_n_copied;
-              status =
-                  WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
+              status = wuffs_base__suspension__short_write;
               WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(10);
             }
           label_6_break:;
@@ -6658,7 +6609,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
           goto label_7_break;
         }
         v_length -= v_n_copied;
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_WRITE);
+        status = wuffs_base__suspension__short_write;
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(11);
       }
     label_7_break:;
@@ -6668,8 +6619,7 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
     self->private_impl.f_n_bits = v_n_bits;
     if ((self->private_impl.f_n_bits >= 8) ||
         ((self->private_impl.f_bits >> self->private_impl.f_n_bits) != 0)) {
-      status = WUFFS_BASE__MAKE_STATUS(
-          WUFFS_DEFLATE__ERROR_INTERNAL_ERROR_INCONSISTENT_N_BITS);
+      status = wuffs_deflate__error__internal_error_inconsistent_n_bits;
       goto exit;
     }
 
@@ -6871,29 +6821,28 @@ wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
                                         size_t sizeof_star_self,
                                         uint64_t wuffs_version) {
   if (!self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   if (sizeof(*self) != sizeof_star_self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_SIZEOF_RECEIVER);
+    return wuffs_base__error__bad_sizeof_receiver;
   }
   if (((wuffs_version >> 32) != WUFFS_VERSION_MAJOR) ||
       (((wuffs_version >> 16) & 0xFFFF) > WUFFS_VERSION_MINOR)) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_WUFFS_VERSION);
+    return wuffs_base__error__bad_wuffs_version;
   }
   if (self->private_impl.magic != 0) {
-    return WUFFS_BASE__MAKE_STATUS(
-        WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE);
+    return wuffs_base__error__check_wuffs_version_called_twice;
   }
   {
     wuffs_base__status z = wuffs_lzw__decoder__check_wuffs_version(
         &self->private_impl.f_lzw, sizeof(self->private_impl.f_lzw),
         WUFFS_VERSION);
-    if (z.code) {
+    if (z) {
       return z;
     }
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
-  return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  return NULL;
 }
 
 // ---------------- Function Implementations
@@ -6905,16 +6854,15 @@ wuffs_gif__decoder__decode_image_config(wuffs_gif__decoder* self,
                                         wuffs_base__image_config* a_dst,
                                         wuffs_base__io_reader a_src) {
   if (!self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return self->private_impl.status;
   }
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t v_num_loops;
   bool v_ffio;
@@ -6931,22 +6879,22 @@ wuffs_gif__decoder__decode_image_config(wuffs_gif__decoder* self,
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT_0;
 
     if (self->private_impl.f_call_sequence >= 1) {
-      status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_INVALID_CALL_SEQUENCE);
+      status = wuffs_base__error__invalid_call_sequence;
       goto exit;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
     status = wuffs_gif__decoder__decode_header(self, a_src);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
     status = wuffs_gif__decoder__decode_lsd(self, a_src);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
     status = wuffs_gif__decoder__decode_up_to_id_part1(self, a_src);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     v_num_loops = 1;
@@ -6993,10 +6941,9 @@ wuffs_gif__decoder__num_decoded_frame_configs(wuffs_gif__decoder* self) {
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return 0;
   }
 
@@ -7011,10 +6958,9 @@ wuffs_gif__decoder__num_decoded_frames(wuffs_gif__decoder* self) {
     return 0;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return 0;
   }
 
@@ -7029,10 +6975,9 @@ wuffs_gif__decoder__work_buffer_size(wuffs_gif__decoder* self) {
     return ((wuffs_base__range_ii_u64){});
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return ((wuffs_base__range_ii_u64){});
   }
 
@@ -7047,16 +6992,15 @@ wuffs_gif__decoder__decode_frame_config(wuffs_gif__decoder* self,
                                         wuffs_base__frame_config* a_dst,
                                         wuffs_base__io_reader a_src) {
   if (!self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return self->private_impl.status;
   }
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t coro_susp_point =
       self->private_impl.c_decode_frame_config[0].coro_susp_point;
@@ -7070,27 +7014,27 @@ wuffs_gif__decoder__decode_frame_config(wuffs_gif__decoder* self,
       if (self->private_impl.f_call_sequence == 0) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
         status = wuffs_gif__decoder__decode_image_config(self, NULL, a_src);
-        if (status.code) {
+        if (status) {
           goto suspend;
         }
       } else if (self->private_impl.f_call_sequence != 1) {
         if (self->private_impl.f_call_sequence == 2) {
           WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
           status = wuffs_gif__decoder__skip_frame(self, a_src);
-          if (status.code) {
+          if (status) {
             goto suspend;
           }
         }
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
         status = wuffs_gif__decoder__decode_up_to_id_part1(self, a_src);
-        if (status.code) {
+        if (status) {
           goto suspend;
         }
       }
     }
     if (self->private_impl.f_end_of_data) {
       while (true) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_END_OF_DATA);
+        status = wuffs_base__suspension__end_of_data;
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT_MAYBE_SUSPEND(4);
       }
     }
@@ -7142,7 +7086,7 @@ exit:
 static wuffs_base__status  //
 wuffs_gif__decoder__skip_frame(wuffs_gif__decoder* self,
                                wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint8_t v_lw;
 
@@ -7173,7 +7117,7 @@ wuffs_gif__decoder__skip_frame(wuffs_gif__decoder* self,
     {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
       if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+        status = wuffs_base__suspension__short_read;
         goto suspend;
       }
       uint8_t t_0 = *iop_a_src++;
@@ -7187,7 +7131,7 @@ wuffs_gif__decoder__skip_frame(wuffs_gif__decoder* self,
     if (a_src.private_impl.buf) {
       iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
     }
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     self->private_impl.f_seen_graphic_control = false;
@@ -7229,21 +7173,19 @@ wuffs_gif__decoder__decode_frame(wuffs_gif__decoder* self,
                                  wuffs_base__io_reader a_src,
                                  wuffs_base__slice_u8 a_work_buffer) {
   if (!self) {
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_RECEIVER);
+    return wuffs_base__error__bad_receiver;
   }
   if (self->private_impl.magic != WUFFS_BASE__MAGIC) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_CHECK_WUFFS_VERSION_MISSING);
+    self->private_impl.status = wuffs_base__error__check_wuffs_version_missing;
   }
-  if (self->private_impl.status.code < 0) {
+  if (wuffs_base__status__is_error(self->private_impl.status)) {
     return self->private_impl.status;
   }
   if (!a_dst) {
-    self->private_impl.status =
-        WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_ARGUMENT);
-    return WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__ERROR_BAD_ARGUMENT);
+    self->private_impl.status = wuffs_base__error__bad_argument;
+    return wuffs_base__error__bad_argument;
   }
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint32_t coro_susp_point =
       self->private_impl.c_decode_frame[0].coro_susp_point;
@@ -7256,13 +7198,13 @@ wuffs_gif__decoder__decode_frame(wuffs_gif__decoder* self,
     if (self->private_impl.f_call_sequence != 2) {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
       status = wuffs_gif__decoder__decode_frame_config(self, NULL, a_src);
-      if (status.code) {
+      if (status) {
         goto suspend;
       }
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
     status = wuffs_gif__decoder__decode_id_part1(self, a_dst, a_src);
-    if (status.code) {
+    if (status) {
       goto suspend;
     }
     self->private_impl.f_seen_graphic_control = false;
@@ -7295,7 +7237,7 @@ exit:
 static wuffs_base__status  //
 wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
                                           wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint8_t v_block_type;
 
@@ -7328,7 +7270,7 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
       {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
         if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-          status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+          status = wuffs_base__suspension__short_read;
           goto suspend;
         }
         uint8_t t_0 = *iop_a_src++;
@@ -7343,7 +7285,7 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
         if (a_src.private_impl.buf) {
           iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
         }
-        if (status.code) {
+        if (status) {
           goto suspend;
         }
       } else if (v_block_type == 44) {
@@ -7355,7 +7297,7 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
         if (a_src.private_impl.buf) {
           iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
         }
-        if (status.code) {
+        if (status) {
           goto suspend;
         }
         goto label_0_break;
@@ -7363,7 +7305,7 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
         self->private_impl.f_end_of_data = true;
         goto label_0_break;
       } else {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_GIF__ERROR_BAD_BLOCK);
+        status = wuffs_gif__error__bad_block;
         goto exit;
       }
     }
@@ -7395,7 +7337,7 @@ exit:
 static wuffs_base__status  //
 wuffs_gif__decoder__decode_header(wuffs_gif__decoder* self,
                                   wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint8_t v_c[6];
   uint32_t v_i;
@@ -7432,7 +7374,7 @@ wuffs_gif__decoder__decode_header(wuffs_gif__decoder* self,
       {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
         if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-          status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+          status = wuffs_base__suspension__short_read;
           goto suspend;
         }
         uint8_t t_0 = *iop_a_src++;
@@ -7442,7 +7384,7 @@ wuffs_gif__decoder__decode_header(wuffs_gif__decoder* self,
     }
     if ((v_c[0] != 71) || (v_c[1] != 73) || (v_c[2] != 70) || (v_c[3] != 56) ||
         ((v_c[4] != 55) && (v_c[4] != 57)) || (v_c[5] != 97)) {
-      status = WUFFS_BASE__MAKE_STATUS(WUFFS_GIF__ERROR_BAD_HEADER);
+      status = wuffs_gif__error__bad_header;
       goto exit;
     }
 
@@ -7472,7 +7414,7 @@ exit:
 static wuffs_base__status  //
 wuffs_gif__decoder__decode_lsd(wuffs_gif__decoder* self,
                                wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint8_t v_flags;
   uint32_t v_num_palette_entries;
@@ -7518,7 +7460,7 @@ wuffs_gif__decoder__decode_lsd(wuffs_gif__decoder* self,
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
         while (true) {
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint64_t* scratch = &self->private_impl.c_decode_lsd[0].scratch;
@@ -7547,7 +7489,7 @@ wuffs_gif__decoder__decode_lsd(wuffs_gif__decoder* self,
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(4);
         while (true) {
           if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-            status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+            status = wuffs_base__suspension__short_read;
             goto suspend;
           }
           uint64_t* scratch = &self->private_impl.c_decode_lsd[0].scratch;
@@ -7568,7 +7510,7 @@ wuffs_gif__decoder__decode_lsd(wuffs_gif__decoder* self,
     {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(5);
       if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+        status = wuffs_base__suspension__short_read;
         goto suspend;
       }
       uint8_t t_4 = *iop_a_src++;
@@ -7581,7 +7523,7 @@ wuffs_gif__decoder__decode_lsd(wuffs_gif__decoder* self,
         ((uint64_t)(io1_a_src - iop_a_src))) {
       self->private_impl.c_decode_lsd[0].scratch -= io1_a_src - iop_a_src;
       iop_a_src = io1_a_src;
-      status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+      status = wuffs_base__suspension__short_read;
       goto suspend;
     }
     iop_a_src += self->private_impl.c_decode_lsd[0].scratch;
@@ -7600,8 +7542,7 @@ wuffs_gif__decoder__decode_lsd(wuffs_gif__decoder* self,
             WUFFS_BASE__COROUTINE_SUSPENSION_POINT(9);
             while (true) {
               if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-                status =
-                    WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+                status = wuffs_base__suspension__short_read;
                 goto suspend;
               }
               uint64_t* scratch = &self->private_impl.c_decode_lsd[0].scratch;
@@ -7668,7 +7609,7 @@ exit:
 static wuffs_base__status  //
 wuffs_gif__decoder__decode_extension(wuffs_gif__decoder* self,
                                      wuffs_base__io_reader a_src) {
-  wuffs_base__status status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+  wuffs_base__status status = NULL;
 
   uint8_t v_label;
 
@@ -7700,7 +7641,7 @@ wuffs_gif__decoder__decode_extension(wuffs_gif__decoder* self,
     {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(1);
       if (WUFFS_BASE__UNLIKELY(iop_a_src == io1_a_src)) {
-        status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__SUSPENSION_SHORT_READ);
+        status = wuffs_base__suspension__short_read;
         goto suspend;
       }
       uint8_t t_0 = *iop_a_src++;
@@ -7715,10 +7656,10 @@ wuffs_gif__decoder__decode_extension(wuffs_gif__decoder* self,
       if (a_src.private_impl.buf) {
         iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
       }
-      if (status.code) {
+      if (status) {
         goto suspend;
       }
-      status = WUFFS_BASE__MAKE_STATUS(WUFFS_BASE__STATUS_OK);
+      status = NULL;
       goto ok;
     } else if (v_label == 255) {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
@@ -7729,10 +7670,10 @@ wuffs_gif__decoder__decode_extension(wuffs_gif__decoder* self,
       if (a_src.private_impl.buf) {
         iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
       }
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
