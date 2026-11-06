# Case ID

P040

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
#include "../../../gen/c/std/gif.c"
#include "../fuzzlib/fuzzlib.c"

const char* fuzz(wuffs_base__io_reader src_reader, uint32_t hash) {
  const char* ret = NULL;
  void* pixbuf = NULL;

  // Use a {} code block so that "goto exit" doesn't trigger "jump bypasses
  // variable initialization" warnings.
  {
    wuffs_gif__status s = 0;
    wuffs_gif__decoder dec = ((wuffs_gif__decoder){});
    wuffs_gif__decoder__check_wuffs_version(&dec, WUFFS_VERSION, sizeof dec);

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
#include "../../../gen/c/std/adler32.c"
#include "../../../gen/c/std/deflate.c"
#include "../../../gen/c/std/zlib.c"
#include "../fuzzlib/fuzzlib.c"

const char* fuzz(wuffs_base__io_reader src_reader, uint32_t hash) {
  const char* ret = NULL;
  wuffs_zlib__status s = 0;
  wuffs_zlib__decoder dec = ((wuffs_zlib__decoder){});
  wuffs_zlib__decoder__check_wuffs_version(&dec, WUFFS_VERSION, sizeof dec);

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
index ed56226d..52ba9eca 100644
--- a/gen/c/std/adler32.c
+++ b/gen/c/std/adler32.c
@@ -1219,10 +1219,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_adler32__hasher__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
-                                                uint32_t wuffs_version,
-                                                size_t sizeof_star_self);
+                                                size_t sizeof_star_self,
+                                                uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1796,19 +1796,19 @@ const char* wuffs_adler32__status__string(wuffs_adler32__status s) {
 // ---------------- Initializer Implementations
 
 void wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
-                                                uint32_t wuffs_version,
-                                                size_t sizeof_star_self) {
+                                                size_t sizeof_star_self,
+                                                uint32_t wuffs_version) {
   if (!self) {
     return;
   }
-  if (wuffs_version != WUFFS_VERSION) {
-    self->private_impl.status = WUFFS_ADLER32__ERROR_BAD_WUFFS_VERSION;
-    return;
-  }
   if (sizeof(*self) != sizeof_star_self) {
     self->private_impl.status = WUFFS_ADLER32__ERROR_BAD_SIZEOF_RECEIVER;
     return;
   }
+  if (wuffs_version != WUFFS_VERSION) {
+    self->private_impl.status = WUFFS_ADLER32__ERROR_BAD_WUFFS_VERSION;
+    return;
+  }
   if (self->private_impl.magic != 0) {
     self->private_impl.status =
         WUFFS_ADLER32__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
diff --git a/gen/c/std/crc32.c b/gen/c/std/crc32.c
index ac6ae4fe..cde854a0 100644
--- a/gen/c/std/crc32.c
+++ b/gen/c/std/crc32.c
@@ -1217,11 +1217,11 @@ typedef struct {
 //
 // It should be called before any other wuffs_crc32__ieee_hasher__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_crc32__ieee_hasher__check_wuffs_version(
     wuffs_crc32__ieee_hasher* self,
-    uint32_t wuffs_version,
-    size_t sizeof_star_self);
+    size_t sizeof_star_self,
+    uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2159,19 +2159,19 @@ static const uint32_t wuffs_crc32__ieee_table[8][256] = {
 
 void wuffs_crc32__ieee_hasher__check_wuffs_version(
     wuffs_crc32__ieee_hasher* self,
-    uint32_t wuffs_version,
-    size_t sizeof_star_self) {
+    size_t sizeof_star_self,
+    uint32_t wuffs_version) {
   if (!self) {
     return;
   }
-  if (wuffs_version != WUFFS_VERSION) {
-    self->private_impl.status = WUFFS_CRC32__ERROR_BAD_WUFFS_VERSION;
-    return;
-  }
   if (sizeof(*self) != sizeof_star_self) {
     self->private_impl.status = WUFFS_CRC32__ERROR_BAD_SIZEOF_RECEIVER;
     return;
   }
+  if (wuffs_version != WUFFS_VERSION) {
+    self->private_impl.status = WUFFS_CRC32__ERROR_BAD_WUFFS_VERSION;
+    return;
+  }
   if (self->private_impl.magic != 0) {
     self->private_impl.status =
         WUFFS_CRC32__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
diff --git a/gen/c/std/deflate.c b/gen/c/std/deflate.c
index bebf7bcb..217c7331 100644
--- a/gen/c/std/deflate.c
+++ b/gen/c/std/deflate.c
@@ -1307,10 +1307,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_deflate__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self);
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1979,19 +1979,19 @@ static wuffs_deflate__status wuffs_deflate__decoder__decode_huffman_slow(
 // ---------------- Initializer Implementations
 
 void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self) {
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version) {
   if (!self) {
     return;
   }
-  if (wuffs_version != WUFFS_VERSION) {
-    self->private_impl.status = WUFFS_DEFLATE__ERROR_BAD_WUFFS_VERSION;
-    return;
-  }
   if (sizeof(*self) != sizeof_star_self) {
     self->private_impl.status = WUFFS_DEFLATE__ERROR_BAD_SIZEOF_RECEIVER;
     return;
   }
+  if (wuffs_version != WUFFS_VERSION) {
+    self->private_impl.status = WUFFS_DEFLATE__ERROR_BAD_WUFFS_VERSION;
+    return;
+  }
   if (self->private_impl.magic != 0) {
     self->private_impl.status =
         WUFFS_DEFLATE__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
diff --git a/gen/c/std/gif.c b/gen/c/std/gif.c
index cb268c9b..58dd998f 100644
--- a/gen/c/std/gif.c
+++ b/gen/c/std/gif.c
@@ -1351,10 +1351,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_gif__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
-                                             uint32_t wuffs_version,
-                                             size_t sizeof_star_self);
+                                             size_t sizeof_star_self,
+                                             uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1955,13 +1955,13 @@ static const uint8_t wuffs_gif__netscape2dot0[11] = {
 // ---------------- Private Initializer Prototypes
 
 void wuffs_gif__lzw_decoder__check_wuffs_version(wuffs_gif__lzw_decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self);
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version);
 
 static inline void wuffs_gif__lzw_decoder__reset(wuffs_gif__lzw_decoder* self) {
   memset(self, 0, sizeof *self);
-  wuffs_gif__lzw_decoder__check_wuffs_version(self, WUFFS_VERSION,
-                                              sizeof *self);
+  wuffs_gif__lzw_decoder__check_wuffs_version(self, sizeof *self,
+                                              WUFFS_VERSION);
 }
 
 // ---------------- Private Function Prototypes
@@ -2015,19 +2015,19 @@ static wuffs_gif__status wuffs_gif__lzw_decoder__decode(
 // ---------------- Initializer Implementations
 
 void wuffs_gif__lzw_decoder__check_wuffs_version(wuffs_gif__lzw_decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self) {
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version) {
   if (!self) {
     return;
   }
-  if (wuffs_version != WUFFS_VERSION) {
-    self->private_impl.status = WUFFS_GIF__ERROR_BAD_WUFFS_VERSION;
-    return;
-  }
   if (sizeof(*self) != sizeof_star_self) {
     self->private_impl.status = WUFFS_GIF__ERROR_BAD_SIZEOF_RECEIVER;
     return;
   }
+  if (wuffs_version != WUFFS_VERSION) {
+    self->private_impl.status = WUFFS_GIF__ERROR_BAD_WUFFS_VERSION;
+    return;
+  }
   if (self->private_impl.magic != 0) {
     self->private_impl.status =
         WUFFS_GIF__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
@@ -2037,19 +2037,19 @@ void wuffs_gif__lzw_decoder__check_wuffs_version(wuffs_gif__lzw_decoder* self,
 }
 
 void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
-                                             uint32_t wuffs_version,
-                                             size_t sizeof_star_self) {
+                                             size_t sizeof_star_self,
+                                             uint32_t wuffs_version) {
   if (!self) {
     return;
   }
-  if (wuffs_version != WUFFS_VERSION) {
-    self->private_impl.status = WUFFS_GIF__ERROR_BAD_WUFFS_VERSION;
-    return;
-  }
   if (sizeof(*self) != sizeof_star_self) {
     self->private_impl.status = WUFFS_GIF__ERROR_BAD_SIZEOF_RECEIVER;
     return;
   }
+  if (wuffs_version != WUFFS_VERSION) {
+    self->private_impl.status = WUFFS_GIF__ERROR_BAD_WUFFS_VERSION;
+    return;
+  }
   if (self->private_impl.magic != 0) {
     self->private_impl.status =
         WUFFS_GIF__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
@@ -2057,8 +2057,8 @@ void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
   wuffs_gif__lzw_decoder__check_wuffs_version(&self->private_impl.f_lzw,
-                                              WUFFS_VERSION,
-                                              sizeof(self->private_impl.f_lzw));
+                                              sizeof(self->private_impl.f_lzw),
+                                              WUFFS_VERSION);
 }
 
 // ---------------- Function Implementations
diff --git a/gen/c/std/gzip.c b/gen/c/std/gzip.c
index 9bd3b4fd..0f3d471d 100644
--- a/gen/c/std/gzip.c
+++ b/gen/c/std/gzip.c
@@ -1226,11 +1226,11 @@ typedef struct {
 //
 // It should be called before any other wuffs_crc32__ieee_hasher__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_crc32__ieee_hasher__check_wuffs_version(
     wuffs_crc32__ieee_hasher* self,
-    uint32_t wuffs_version,
-    size_t sizeof_star_self);
+    size_t sizeof_star_self,
+    uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1411,10 +1411,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_deflate__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self);
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1517,10 +1517,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_gzip__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
-                                              uint32_t wuffs_version,
-                                              size_t sizeof_star_self);
+                                              size_t sizeof_star_self,
+                                              uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2107,19 +2107,19 @@ const char* wuffs_gzip__status__string(wuffs_gzip__status s) {
 // ---------------- Initializer Implementations
 
 void wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
-                                              uint32_t wuffs_version,
-                                              size_t sizeof_star_self) {
+                                              size_t sizeof_star_self,
+                                              uint32_t wuffs_version) {
   if (!self) {
     return;
   }
-  if (wuffs_version != WUFFS_VERSION) {
-    self->private_impl.status = WUFFS_GZIP__ERROR_BAD_WUFFS_VERSION;
-    return;
-  }
   if (sizeof(*self) != sizeof_star_self) {
     self->private_impl.status = WUFFS_GZIP__ERROR_BAD_SIZEOF_RECEIVER;
     return;
   }
+  if (wuffs_version != WUFFS_VERSION) {
+    self->private_impl.status = WUFFS_GZIP__ERROR_BAD_WUFFS_VERSION;
+    return;
+  }
   if (self->private_impl.magic != 0) {
     self->private_impl.status =
         WUFFS_GZIP__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
@@ -2127,11 +2127,11 @@ void wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
   wuffs_deflate__decoder__check_wuffs_version(
-      &self->private_impl.f_flate, WUFFS_VERSION,
-      sizeof(self->private_impl.f_flate));
+      &self->private_impl.f_flate, sizeof(self->private_impl.f_flate),
+      WUFFS_VERSION);
   wuffs_crc32__ieee_hasher__check_wuffs_version(
-      &self->private_impl.f_checksum, WUFFS_VERSION,
-      sizeof(self->private_impl.f_checksum));
+      &self->private_impl.f_checksum, sizeof(self->private_impl.f_checksum),
+      WUFFS_VERSION);
 }
 
 // ---------------- Function Implementations
diff --git a/gen/c/std/zlib.c b/gen/c/std/zlib.c
index 95f43d9d..3e5403fe 100644
--- a/gen/c/std/zlib.c
+++ b/gen/c/std/zlib.c
@@ -1228,10 +1228,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_adler32__hasher__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
-                                                uint32_t wuffs_version,
-                                                size_t sizeof_star_self);
+                                                size_t sizeof_star_self,
+                                                uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1412,10 +1412,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_deflate__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self);
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1517,10 +1517,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_zlib__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
-                                              uint32_t wuffs_version,
-                                              size_t sizeof_star_self);
+                                              size_t sizeof_star_self,
+                                              uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -2108,19 +2108,19 @@ const char* wuffs_zlib__status__string(wuffs_zlib__status s) {
 // ---------------- Initializer Implementations
 
 void wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
-                                              uint32_t wuffs_version,
-                                              size_t sizeof_star_self) {
+                                              size_t sizeof_star_self,
+                                              uint32_t wuffs_version) {
   if (!self) {
     return;
   }
-  if (wuffs_version != WUFFS_VERSION) {
-    self->private_impl.status = WUFFS_ZLIB__ERROR_BAD_WUFFS_VERSION;
-    return;
-  }
   if (sizeof(*self) != sizeof_star_self) {
     self->private_impl.status = WUFFS_ZLIB__ERROR_BAD_SIZEOF_RECEIVER;
     return;
   }
+  if (wuffs_version != WUFFS_VERSION) {
+    self->private_impl.status = WUFFS_ZLIB__ERROR_BAD_WUFFS_VERSION;
+    return;
+  }
   if (self->private_impl.magic != 0) {
     self->private_impl.status =
         WUFFS_ZLIB__ERROR_CHECK_WUFFS_VERSION_CALLED_TWICE;
@@ -2128,11 +2128,11 @@ void wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
   }
   self->private_impl.magic = WUFFS_BASE__MAGIC;
   wuffs_deflate__decoder__check_wuffs_version(
-      &self->private_impl.f_flate, WUFFS_VERSION,
-      sizeof(self->private_impl.f_flate));
+      &self->private_impl.f_flate, sizeof(self->private_impl.f_flate),
+      WUFFS_VERSION);
   wuffs_adler32__hasher__check_wuffs_version(
-      &self->private_impl.f_checksum, WUFFS_VERSION,
-      sizeof(self->private_impl.f_checksum));
+      &self->private_impl.f_checksum, sizeof(self->private_impl.f_checksum),
+      WUFFS_VERSION);
 }
 
 // ---------------- Function Implementations
diff --git a/gen/h/std/adler32.h b/gen/h/std/adler32.h
index 225f984b..a27b2caf 100644
--- a/gen/h/std/adler32.h
+++ b/gen/h/std/adler32.h
@@ -1219,10 +1219,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_adler32__hasher__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
-                                                uint32_t wuffs_version,
-                                                size_t sizeof_star_self);
+                                                size_t sizeof_star_self,
+                                                uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
diff --git a/gen/h/std/crc32.h b/gen/h/std/crc32.h
index a01ac68f..feae69e3 100644
--- a/gen/h/std/crc32.h
+++ b/gen/h/std/crc32.h
@@ -1217,11 +1217,11 @@ typedef struct {
 //
 // It should be called before any other wuffs_crc32__ieee_hasher__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_crc32__ieee_hasher__check_wuffs_version(
     wuffs_crc32__ieee_hasher* self,
-    uint32_t wuffs_version,
-    size_t sizeof_star_self);
+    size_t sizeof_star_self,
+    uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
diff --git a/gen/h/std/deflate.h b/gen/h/std/deflate.h
index acc659d6..4292568f 100644
--- a/gen/h/std/deflate.h
+++ b/gen/h/std/deflate.h
@@ -1307,10 +1307,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_deflate__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self);
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
diff --git a/gen/h/std/gif.h b/gen/h/std/gif.h
index a0e774d3..c504bdc1 100644
--- a/gen/h/std/gif.h
+++ b/gen/h/std/gif.h
@@ -1351,10 +1351,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_gif__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_gif__decoder__check_wuffs_version(wuffs_gif__decoder* self,
-                                             uint32_t wuffs_version,
-                                             size_t sizeof_star_self);
+                                             size_t sizeof_star_self,
+                                             uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
diff --git a/gen/h/std/gzip.h b/gen/h/std/gzip.h
index 1ba58ce3..a447eba3 100644
--- a/gen/h/std/gzip.h
+++ b/gen/h/std/gzip.h
@@ -1226,11 +1226,11 @@ typedef struct {
 //
 // It should be called before any other wuffs_crc32__ieee_hasher__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_crc32__ieee_hasher__check_wuffs_version(
     wuffs_crc32__ieee_hasher* self,
-    uint32_t wuffs_version,
-    size_t sizeof_star_self);
+    size_t sizeof_star_self,
+    uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1411,10 +1411,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_deflate__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self);
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1517,10 +1517,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_gzip__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_gzip__decoder__check_wuffs_version(wuffs_gzip__decoder* self,
-                                              uint32_t wuffs_version,
-                                              size_t sizeof_star_self);
+                                              size_t sizeof_star_self,
+                                              uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
diff --git a/gen/h/std/zlib.h b/gen/h/std/zlib.h
index ed35d7d8..6f55d847 100644
--- a/gen/h/std/zlib.h
+++ b/gen/h/std/zlib.h
@@ -1228,10 +1228,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_adler32__hasher__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_adler32__hasher__check_wuffs_version(wuffs_adler32__hasher* self,
-                                                uint32_t wuffs_version,
-                                                size_t sizeof_star_self);
+                                                size_t sizeof_star_self,
+                                                uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1412,10 +1412,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_deflate__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_deflate__decoder__check_wuffs_version(wuffs_deflate__decoder* self,
-                                                 uint32_t wuffs_version,
-                                                 size_t sizeof_star_self);
+                                                 size_t sizeof_star_self,
+                                                 uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
 
@@ -1517,10 +1517,10 @@ typedef struct {
 //
 // It should be called before any other wuffs_zlib__decoder__* function.
 //
-// Pass WUFFS_VERSION and sizeof(*self) for wuffs_version and sizeof_star_self.
+// Pass sizeof(*self) and WUFFS_VERSION for sizeof_star_self and wuffs_version.
 void wuffs_zlib__decoder__check_wuffs_version(wuffs_zlib__decoder* self,
-                                              uint32_t wuffs_version,
-                                              size_t sizeof_star_self);
+                                              size_t sizeof_star_self,
+                                              uint32_t wuffs_version);
 
 // ---------------- Public Function Prototypes
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
