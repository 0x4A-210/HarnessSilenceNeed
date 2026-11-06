# Case ID

C025

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

// If building this program in an environment that doesn't easily accomodate
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
      s = wuffs_gif__decoder__decode_frame(&dec, &pb, src_reader,
                                           ((wuffs_base__slice_u8){}), 0, 0);
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

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/release/c/wuffs-unsupported-snapshot.h b/release/c/wuffs-unsupported-snapshot.h
index 51c67c03..b3839976 100644
--- a/release/c/wuffs-unsupported-snapshot.h
+++ b/release/c/wuffs-unsupported-snapshot.h
@@ -2633,10 +2633,10 @@ typedef struct {
   inline wuffs_base__status decode_frame_config(wuffs_base__frame_config* a_dst,
                                                 wuffs_base__io_reader a_src);
   inline wuffs_base__status decode_frame(wuffs_base__pixel_buffer* a_dst,
-                                         wuffs_base__io_reader a_src,
-                                         wuffs_base__slice_u8 a_work_buffer,
                                          uint32_t a_pixbuf_origin_x,
-                                         uint32_t a_pixbuf_origin_y);
+                                         uint32_t a_pixbuf_origin_y,
+                                         wuffs_base__io_reader a_src,
+                                         wuffs_base__slice_u8 a_work_buffer);
 #endif  // __cplusplus
 
 } wuffs_gif__decoder;
@@ -2676,10 +2676,10 @@ wuffs_gif__decoder__decode_frame_config(wuffs_gif__decoder* self,
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_gif__decoder__decode_frame(wuffs_gif__decoder* self,
                                  wuffs_base__pixel_buffer* a_dst,
-                                 wuffs_base__io_reader a_src,
-                                 wuffs_base__slice_u8 a_work_buffer,
                                  uint32_t a_pixbuf_origin_x,
-                                 uint32_t a_pixbuf_origin_y);
+                                 uint32_t a_pixbuf_origin_y,
+                                 wuffs_base__io_reader a_src,
+                                 wuffs_base__slice_u8 a_work_buffer);
 
 // ---------------- C++ Convenience Methods
 
@@ -2721,12 +2721,12 @@ wuffs_gif__decoder::decode_frame_config(wuffs_base__frame_config* a_dst,
 
 inline wuffs_base__status  //
 wuffs_gif__decoder::decode_frame(wuffs_base__pixel_buffer* a_dst,
-                                 wuffs_base__io_reader a_src,
-                                 wuffs_base__slice_u8 a_work_buffer,
                                  uint32_t a_pixbuf_origin_x,
-                                 uint32_t a_pixbuf_origin_y) {
-  return wuffs_gif__decoder__decode_frame(this, a_dst, a_src, a_work_buffer,
-                                          a_pixbuf_origin_x, a_pixbuf_origin_y);
+                                 uint32_t a_pixbuf_origin_y,
+                                 wuffs_base__io_reader a_src,
+                                 wuffs_base__slice_u8 a_work_buffer) {
+  return wuffs_gif__decoder__decode_frame(
+      this, a_dst, a_pixbuf_origin_x, a_pixbuf_origin_y, a_src, a_work_buffer);
 }
 
 #endif  // __cplusplus
@@ -7070,10 +7070,10 @@ short_read_src:
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_gif__decoder__decode_frame(wuffs_gif__decoder* self,
                                  wuffs_base__pixel_buffer* a_dst,
-                                 wuffs_base__io_reader a_src,
-                                 wuffs_base__slice_u8 a_work_buffer,
                                  uint32_t a_pixbuf_origin_x,
-                                 uint32_t a_pixbuf_origin_y) {
+                                 uint32_t a_pixbuf_origin_y,
+                                 wuffs_base__io_reader a_src,
+                                 wuffs_base__slice_u8 a_work_buffer) {
   if (!self) {
     return WUFFS_BASE__ERROR_BAD_RECEIVER;
   }
diff --git a/std/gif/decode_gif.wuffs b/std/gif/decode_gif.wuffs
index a8229011..896c4d25 100644
--- a/std/gif/decode_gif.wuffs
+++ b/std/gif/decode_gif.wuffs
@@ -232,7 +232,7 @@ pri func decoder.skip_frame?(src base.io_reader)() {
 }
 
 // TODO: honor pixbuf_origin_x and pixbuf_origin_y args.
-pub func decoder.decode_frame?(dst ptr base.pixel_buffer, src base.io_reader, work_buffer slice base.u8, pixbuf_origin_x base.u32, pixbuf_origin_y base.u32)() {
+pub func decoder.decode_frame?(dst ptr base.pixel_buffer, pixbuf_origin_x base.u32, pixbuf_origin_y base.u32, src base.io_reader, work_buffer slice base.u8)() {
 	if this.call_sequence != 2 {
 		this.decode_frame_config?(dst:nullptr, src:in.src)
 	}
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
