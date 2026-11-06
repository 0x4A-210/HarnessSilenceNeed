# Case ID

C044

## Existing Fuzz Harness H0

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

// ----------------

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
#include "../../../release/c/wuffs-unsupported-snapshot.c"
#include "../fuzzlib/fuzzlib.c"

const char* fuzz(wuffs_base__io_reader src_reader, uint32_t hash) {
  wuffs_zlib__decoder dec = ((wuffs_zlib__decoder){});
  const char* status =
      wuffs_zlib__decoder__check_wuffs_version(&dec, sizeof dec, WUFFS_VERSION);
  if (status) {
    return status;
  }

  // Ignore the checksum for 99.99%-ish of all input. When fuzzers generate
  // random input, the checkum is very unlikely to match. Still, it's useful to
  // verify that checksumming does not lead to e.g. buffer overflows.
  wuffs_zlib__decoder__set_ignore_checksum(&dec, hash & 0xFFFF);

  const size_t dstbuf_size = 65536;
  uint8_t dstbuf[dstbuf_size];
  wuffs_base__io_buffer dst = ((wuffs_base__io_buffer){
      .data = ((wuffs_base__slice_u8){
          .ptr = dstbuf,
          .len = dstbuf_size,
      }),
  });
  wuffs_base__io_writer dst_writer = wuffs_base__io_buffer__writer(&dst);

  while (true) {
    dst.meta.wi = 0;
    status =
        wuffs_zlib__decoder__decode_io_writer(&dec, dst_writer, src_reader);
    if (status != wuffs_base__suspension__short_write) {
      break;
    }
    if (dst.meta.wi == 0) {
      fprintf(stderr,
              "wuffs_zlib__decoder__decode_io_writer made no progress\n");
      intentional_segfault();
    }
  }
  return status;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/cmd/wuffs-c/internal/cgen/base/core-public.h b/cmd/wuffs-c/internal/cgen/base/core-public.h
index 20f11a50..fe5753e2 100644
--- a/cmd/wuffs-c/internal/cgen/base/core-public.h
+++ b/cmd/wuffs-c/internal/cgen/base/core-public.h
@@ -342,6 +342,13 @@ wuffs_base__slice_u8__subslice_ij(wuffs_base__slice_u8 s,
   return ((wuffs_base__slice_u8){});
 }
 
+// ---------------- Slices and Tables (Utility)
+
+static inline wuffs_base__slice_u8  //
+wuffs_base__utility__null_slice_u8(const wuffs_base__utility* ignored) {
+  return ((wuffs_base__slice_u8){});
+}
+
 // ---------------- Bureaucracy re -Wunused-function
 
 static inline void
@@ -374,4 +381,5 @@ wuffs_base__acknowledge_potentially_unused_functions__core_public() {
   (void)(wuffs_base__u8__min);
   (void)(wuffs_base__u8__sat_add);
   (void)(wuffs_base__u8__sat_sub);
+  (void)(wuffs_base__utility__null_slice_u8);
 }
diff --git a/release/c/wuffs-unsupported-snapshot.c b/release/c/wuffs-unsupported-snapshot.c
index 1ce9bbb3..ba0478fe 100644
--- a/release/c/wuffs-unsupported-snapshot.c
+++ b/release/c/wuffs-unsupported-snapshot.c
@@ -373,6 +373,13 @@ wuffs_base__slice_u8__subslice_ij(wuffs_base__slice_u8 s,
   return ((wuffs_base__slice_u8){});
 }
 
+// ---------------- Slices and Tables (Utility)
+
+static inline wuffs_base__slice_u8  //
+wuffs_base__utility__null_slice_u8(const wuffs_base__utility* ignored) {
+  return ((wuffs_base__slice_u8){});
+}
+
 // ---------------- Bureaucracy re -Wunused-function
 
 static inline void
@@ -405,6 +412,7 @@ wuffs_base__acknowledge_potentially_unused_functions__core_public() {
   (void)(wuffs_base__u8__min);
   (void)(wuffs_base__u8__sat_add);
   (void)(wuffs_base__u8__sat_sub);
+  (void)(wuffs_base__utility__null_slice_u8);
 }
 
 // ---------------- Ranges and Rects
@@ -2663,7 +2671,8 @@ sizeof__wuffs_deflate__decoder();
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_deflate__decoder__decode_io_writer(wuffs_deflate__decoder* self,
                                          wuffs_base__io_writer a_dst,
-                                         wuffs_base__io_reader a_src);
+                                         wuffs_base__io_reader a_src,
+                                         wuffs_base__slice_u8 a_workbuf);
 
 // ---------------- Struct Definitions
 
@@ -2770,8 +2779,11 @@ struct wuffs_deflate__decoder__struct {
   }
 
   inline wuffs_base__status  //
-  decode_io_writer(wuffs_base__io_writer a_dst, wuffs_base__io_reader a_src) {
-    return wuffs_deflate__decoder__decode_io_writer(this, a_dst, a_src);
+  decode_io_writer(wuffs_base__io_writer a_dst,
+                   wuffs_base__io_reader a_src,
+                   wuffs_base__slice_u8 a_workbuf) {
+    return wuffs_deflate__decoder__decode_io_writer(this, a_dst, a_src,
+                                                    a_workbuf);
   }
 
 #if (__cplusplus >= 201103L) && !defined(WUFFS_IMPLEMENTATION)
@@ -2829,7 +2841,8 @@ wuffs_lzw__decoder__set_literal_width(wuffs_lzw__decoder* self, uint32_t a_lw);
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_lzw__decoder__decode_io_writer(wuffs_lzw__decoder* self,
                                      wuffs_base__io_writer a_dst,
-                                     wuffs_base__io_reader a_src);
+                                     wuffs_base__io_reader a_src,
+                                     wuffs_base__slice_u8 a_workbuf);
 
 WUFFS_BASE__MAYBE_STATIC wuffs_base__slice_u8  //
 wuffs_lzw__decoder__flush(wuffs_lzw__decoder* self);
@@ -2917,8 +2930,10 @@ struct wuffs_lzw__decoder__struct {
   }
 
   inline wuffs_base__status  //
-  decode_io_writer(wuffs_base__io_writer a_dst, wuffs_base__io_reader a_src) {
-    return wuffs_lzw__decoder__decode_io_writer(this, a_dst, a_src);
+  decode_io_writer(wuffs_base__io_writer a_dst,
+                   wuffs_base__io_reader a_src,
+                   wuffs_base__slice_u8 a_workbuf) {
+    return wuffs_lzw__decoder__decode_io_writer(this, a_dst, a_src, a_workbuf);
   }
 
   inline wuffs_base__slice_u8  //
@@ -3276,7 +3291,8 @@ wuffs_gzip__decoder__set_ignore_checksum(wuffs_gzip__decoder* self, bool a_ic);
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_gzip__decoder__decode_io_writer(wuffs_gzip__decoder* self,
                                       wuffs_base__io_writer a_dst,
-                                      wuffs_base__io_reader a_src);
+                                      wuffs_base__io_reader a_src,
+                                      wuffs_base__slice_u8 a_workbuf);
 
 // ---------------- Struct Definitions
 
@@ -3350,8 +3366,10 @@ struct wuffs_gzip__decoder__struct {
   }
 
   inline wuffs_base__status  //
-  decode_io_writer(wuffs_base__io_writer a_dst, wuffs_base__io_reader a_src) {
-    return wuffs_gzip__decoder__decode_io_writer(this, a_dst, a_src);
+  decode_io_writer(wuffs_base__io_writer a_dst,
+                   wuffs_base__io_reader a_src,
+                   wuffs_base__slice_u8 a_workbuf) {
+    return wuffs_gzip__decoder__decode_io_writer(this, a_dst, a_src, a_workbuf);
   }
 
 #if (__cplusplus >= 201103L) && !defined(WUFFS_IMPLEMENTATION)
@@ -3411,7 +3429,8 @@ wuffs_zlib__decoder__set_ignore_checksum(wuffs_zlib__decoder* self, bool a_ic);
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_zlib__decoder__decode_io_writer(wuffs_zlib__decoder* self,
                                       wuffs_base__io_writer a_dst,
-                                      wuffs_base__io_reader a_src);
+                                      wuffs_base__io_reader a_src,
+                                      wuffs_base__slice_u8 a_workbuf);
 
 // ---------------- Struct Definitions
 
@@ -3482,8 +3501,10 @@ struct wuffs_zlib__decoder__struct {
   }
 
   inline wuffs_base__status  //
-  decode_io_writer(wuffs_base__io_writer a_dst, wuffs_base__io_reader a_src) {
-    return wuffs_zlib__decoder__decode_io_writer(this, a_dst, a_src);
+  decode_io_writer(wuffs_base__io_writer a_dst,
+                   wuffs_base__io_reader a_src,
+                   wuffs_base__slice_u8 a_workbuf) {
+    return wuffs_zlib__decoder__decode_io_writer(this, a_dst, a_src, a_workbuf);
   }
 
 #if (__cplusplus >= 201103L) && !defined(WUFFS_IMPLEMENTATION)
@@ -5922,7 +5943,8 @@ sizeof__wuffs_deflate__decoder() {
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_deflate__decoder__decode_io_writer(wuffs_deflate__decoder* self,
                                          wuffs_base__io_writer a_dst,
-                                         wuffs_base__io_reader a_src) {
+                                         wuffs_base__io_reader a_src,
+                                         wuffs_base__slice_u8 a_workbuf) {
   if (!self) {
     return wuffs_base__error__bad_receiver;
   }
@@ -7705,7 +7727,8 @@ wuffs_lzw__decoder__set_literal_width(wuffs_lzw__decoder* self, uint32_t a_lw) {
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_lzw__decoder__decode_io_writer(wuffs_lzw__decoder* self,
                                      wuffs_base__io_writer a_dst,
-                                     wuffs_base__io_reader a_src) {
+                                     wuffs_base__io_reader a_src,
+                                     wuffs_base__slice_u8 a_workbuf) {
   if (!self) {
     return wuffs_base__error__bad_receiver;
   }
@@ -10138,7 +10161,8 @@ wuffs_gif__decoder__decode_id_part2(wuffs_gif__decoder* self,
             wuffs_base__status t_1 = wuffs_lzw__decoder__decode_io_writer(
                 &self->private_impl.f_lzw,
                 wuffs_base__utility__null_io_writer(&self->private_impl.f_util),
-                v_r);
+                v_r,
+                wuffs_base__utility__null_slice_u8(&self->private_impl.f_util));
             iop_v_r = u_r.data.ptr + u_r.meta.ri;
             v_lzw_status = t_1;
           }
@@ -10423,7 +10447,8 @@ wuffs_gzip__decoder__set_ignore_checksum(wuffs_gzip__decoder* self, bool a_ic) {
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_gzip__decoder__decode_io_writer(wuffs_gzip__decoder* self,
                                       wuffs_base__io_writer a_dst,
-                                      wuffs_base__io_reader a_src) {
+                                      wuffs_base__io_reader a_src,
+                                      wuffs_base__slice_u8 a_workbuf) {
   if (!self) {
     return wuffs_base__error__bad_receiver;
   }
@@ -10657,7 +10682,7 @@ wuffs_gzip__decoder__decode_io_writer(wuffs_gzip__decoder* self,
               iop_a_src - a_src.private_impl.buf->data.ptr;
         }
         wuffs_base__status t_7 = wuffs_deflate__decoder__decode_io_writer(
-            &self->private_impl.f_flate, a_dst, a_src);
+            &self->private_impl.f_flate, a_dst, a_src, a_workbuf);
         if (a_dst.private_impl.buf) {
           iop_a_dst = a_dst.private_impl.buf->data.ptr +
                       a_dst.private_impl.buf->meta.wi;
@@ -10871,7 +10896,8 @@ wuffs_zlib__decoder__set_ignore_checksum(wuffs_zlib__decoder* self, bool a_ic) {
 WUFFS_BASE__MAYBE_STATIC wuffs_base__status  //
 wuffs_zlib__decoder__decode_io_writer(wuffs_zlib__decoder* self,
                                       wuffs_base__io_writer a_dst,
-                                      wuffs_base__io_reader a_src) {
+                                      wuffs_base__io_reader a_src,
+                                      wuffs_base__slice_u8 a_workbuf) {
   if (!self) {
     return wuffs_base__error__bad_receiver;
   }
@@ -10990,7 +11016,7 @@ wuffs_zlib__decoder__decode_io_writer(wuffs_zlib__decoder* self,
               iop_a_src - a_src.private_impl.buf->data.ptr;
         }
         wuffs_base__status t_1 = wuffs_deflate__decoder__decode_io_writer(
-            &self->private_impl.f_flate, a_dst, a_src);
+            &self->private_impl.f_flate, a_dst, a_src, a_workbuf);
         if (a_dst.private_impl.buf) {
           iop_a_dst = a_dst.private_impl.buf->data.ptr +
                       a_dst.private_impl.buf->meta.wi;
diff --git a/std/deflate/decode_deflate.wuffs b/std/deflate/decode_deflate.wuffs
index 017dc49f..b40a27dc 100644
--- a/std/deflate/decode_deflate.wuffs
+++ b/std/deflate/decode_deflate.wuffs
@@ -121,7 +121,7 @@ pub struct decoder?(
 	end_of_block base.bool,
 )
 
-pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader) {
+pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader, workbuf slice base.u8) {
 	var status       base.status
 	var written      slice base.u8
 	var n_copied     base.u64
diff --git a/std/gif/decode_gif.wuffs b/std/gif/decode_gif.wuffs
index 8e2812c2..5bdee2a3 100644
--- a/std/gif/decode_gif.wuffs
+++ b/std/gif/decode_gif.wuffs
@@ -715,7 +715,8 @@ pri func decoder.decode_id_part2?(dst ptr base.pixel_buffer, src base.io_reader,
 				return "?internal error: inconsistent ri/wi"
 			}
 			io_bind (io:r, data:this.compressed[this.compressed_ri:this.compressed_wi]) {
-				lzw_status =? this.lzw.decode_io_writer?(dst:this.util.null_io_writer(), src:r)
+				lzw_status =? this.lzw.decode_io_writer?(
+					dst:this.util.null_io_writer(), src:r, workbuf:this.util.null_slice_u8())
 				this.compressed_ri ~sat+= r.since_mark().length()
 			}
 
diff --git a/std/gzip/decode_gzip.wuffs b/std/gzip/decode_gzip.wuffs
index 7c44b5ca..747f1d4f 100644
--- a/std/gzip/decode_gzip.wuffs
+++ b/std/gzip/decode_gzip.wuffs
@@ -30,7 +30,7 @@ pub func decoder.set_ignore_checksum!(ic base.bool) {
 	this.ignore_checksum = args.ic
 }
 
-pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader) {
+pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader, workbuf slice base.u8) {
 	var c                   base.u8
 	var flags               base.u8
 	var xlen                base.u16
@@ -100,7 +100,7 @@ pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader) {
 	// Decode and checksum the DEFLATE-encoded payload.
 	while true {
 		args.dst.set_mark!()
-		status =? this.flate.decode_io_writer?(dst:args.dst, src:args.src)
+		status =? this.flate.decode_io_writer?(dst:args.dst, src:args.src, workbuf:args.workbuf)
 		if not this.ignore_checksum {
 			checksum_got = this.checksum.update!(x:args.dst.since_mark())
 			decoded_length_got ~mod+= ((args.dst.since_mark().length() & 0xFFFFFFFF) as base.u32)
diff --git a/std/lzw/decode_lzw.wuffs b/std/lzw/decode_lzw.wuffs
index 1543ef0d..b0f65645 100644
--- a/std/lzw/decode_lzw.wuffs
+++ b/std/lzw/decode_lzw.wuffs
@@ -58,7 +58,7 @@ pub func decoder.set_literal_width!(lw base.u32[2..8]) {
 	this.lw = args.lw
 }
 
-pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader) {
+pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader, workbuf slice base.u8) {
 	var i base.u32[..8191]
 
 	// Initialize read_from state.
diff --git a/std/zlib/decode_zlib.wuffs b/std/zlib/decode_zlib.wuffs
index f6d09e06..0520b06e 100644
--- a/std/zlib/decode_zlib.wuffs
+++ b/std/zlib/decode_zlib.wuffs
@@ -32,7 +32,7 @@ pub func decoder.set_ignore_checksum!(ic base.bool) {
 	this.ignore_checksum = args.ic
 }
 
-pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader) {
+pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader, workbuf slice base.u8) {
 	var x             base.u16
 	var checksum_got  base.u32
 	var status        base.status
@@ -55,7 +55,7 @@ pub func decoder.decode_io_writer?(dst base.io_writer, src base.io_reader) {
 	// Decode and checksum the DEFLATE-encoded payload.
 	while true {
 		args.dst.set_mark!()
-		status =? this.flate.decode_io_writer?(dst:args.dst, src:args.src)
+		status =? this.flate.decode_io_writer?(dst:args.dst, src:args.src, workbuf:args.workbuf)
 		if not this.ignore_checksum {
 			checksum_got = this.checksum.update!(x:args.dst.since_mark())
 		}
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
