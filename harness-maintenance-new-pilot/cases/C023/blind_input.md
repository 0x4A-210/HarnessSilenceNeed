# Case ID

C023

## Existing Fuzz Harness H0

### `fuzz/c/fuzzlib/fuzzlib.c`

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

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef WUFFS_INCLUDE_GUARD
#error "Wuffs' .h files need to be included before this file"
#endif

volatile int* intentional_segfault_ptr = NULL;

void intentional_segfault() {
  *intentional_segfault_ptr = 0;
}

const char* fuzz(wuffs_base__io_reader src_reader, uint32_t hash);

static const char* llvmFuzzerTestOneInput(const uint8_t* data, size_t size) {
  // Hash input as per https://en.wikipedia.org/wiki/Jenkins_hash_function
  size_t i = 0;
  uint32_t hash = 0;
  while (i != size) {
    hash += data[i++];
    hash += hash << 10;
    hash ^= hash >> 6;
  }
  hash += hash << 3;
  hash ^= hash >> 11;
  hash += hash << 15;

  wuffs_base__io_buffer src = {.ptr = (uint8_t*)(data),
                               .len = size,
                               .wi = size,
                               .ri = 0,
                               .closed = true};
  return fuzz(wuffs_base__io_buffer__reader(&src), hash);
}

#ifdef __cplusplus
extern "C" {
#endif

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  llvmFuzzerTestOneInput(data, size);
  return 0;
}

#ifdef __cplusplus
}  // extern "C"
#endif

#ifdef WUFFS_CONFIG__FUZZLIB_MAIN

#include <errno.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

int main(int argc, char** argv) {
  int i;
  for (i = 1; i < argc; i++) {
    printf("%-50s", argv[i]);

    struct stat z;
    int fd = open(argv[i], O_RDONLY, 0);
    if (fd == -1) {
      printf("\n");
      fprintf(stderr, "FAIL: open: %s\n", strerror(errno));
      return 1;
    }
    if (fstat(fd, &z)) {
      printf("\n");
      fprintf(stderr, "FAIL: fstat: %s\n", strerror(errno));
      return 1;
    }
    if ((z.st_size < 0) || (0x7FFFFFFF < z.st_size)) {
      printf("\n");
      fprintf(stderr, "FAIL: file size out of bounds");
      return 1;
    }
    size_t n = z.st_size;
    void* data = mmap(NULL, n, PROT_READ, MAP_SHARED, fd, 0);
    if (data == MAP_FAILED) {
      printf("\n");
      fprintf(stderr, "FAIL: mmap: %s\n", strerror(errno));
      return 1;
    }

    const char* msg = llvmFuzzerTestOneInput((const uint8_t*)(data), n);
    if (!msg) {
      msg = "(null)";
    }
    printf(" %s\n", msg);

    if (munmap(data, n)) {
      fprintf(stderr, "FAIL: mmap: %s\n", strerror(errno));
      return 1;
    }
    if (close(fd)) {
      fprintf(stderr, "FAIL: close: %s\n", strerror(errno));
      return 1;
    }
  }
  printf("PASS: %d files processed\n", argc > 1 ? argc - 1 : 0);
  return 0;
}

#endif  // WUFFS_CONFIG__FUZZLIB_MAIN
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
  wuffs_zlib__decoder dec = ((wuffs_zlib__decoder){});
  wuffs_base__status z =
      wuffs_zlib__decoder__check_wuffs_version(&dec, sizeof dec, WUFFS_VERSION);
  if (z) {
    return z;
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
    if (z != wuffs_base__suspension__short_write) {
      break;
    }
    if (dst.wi == 0) {
      fprintf(stderr, "wuffs_zlib__decoder__decode made no progress\n");
      intentional_segfault();
    }
  }
  return z;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/cmd/wuffs-c/internal/cgen/base/base-private.h b/cmd/wuffs-c/internal/cgen/base/base-private.h
index c10f97c5..a72f18f1 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-private.h
+++ b/cmd/wuffs-c/internal/cgen/base/base-private.h
@@ -494,8 +494,8 @@ wuffs_base__utility__make_rect_ie_u32(wuffs_base__utility* ignored,
 
 static inline bool  //
 wuffs_base__io_buffer__is_valid(wuffs_base__io_buffer buf) {
-  return (buf.ptr || (buf.len == 0)) && (buf.len >= buf.wi) &&
-         (buf.wi >= buf.ri);
+  return (buf.data.ptr || (buf.data.len == 0)) &&
+         (buf.data.len >= buf.meta.wi) && (buf.meta.wi >= buf.meta.ri);
 }
 
 // TODO: wuffs_base__io_reader__is_eof is no longer used by Wuffs per se, but
@@ -508,7 +508,8 @@ wuffs_base__io_buffer__is_valid(wuffs_base__io_buffer buf) {
 static inline bool  //
 wuffs_base__io_reader__is_eof(wuffs_base__io_reader o) {
   wuffs_base__io_buffer* buf = o.private_impl.buf;
-  return buf && buf->closed && (buf->ptr + buf->wi == o.private_impl.limit);
+  return buf && buf->meta.closed &&
+         (buf->data.ptr + buf->meta.wi == o.private_impl.limit);
 }
 
 static inline bool  //
@@ -516,9 +517,9 @@ wuffs_base__io_reader__is_valid(wuffs_base__io_reader o) {
   wuffs_base__io_buffer* buf = o.private_impl.buf;
   // Note: if making this function public (i.e. moving it to base-header.h), it
   // also needs to allow NULL (i.e. implicit, callee-calculated) mark/limit.
-  return buf ? ((buf->ptr <= o.private_impl.mark) &&
+  return buf ? ((buf->data.ptr <= o.private_impl.mark) &&
                 (o.private_impl.mark <= o.private_impl.limit) &&
-                (o.private_impl.limit <= buf->ptr + buf->len))
+                (o.private_impl.limit <= buf->data.ptr + buf->data.len))
              : ((o.private_impl.mark == NULL) &&
                 (o.private_impl.limit == NULL));
 }
@@ -528,9 +529,9 @@ wuffs_base__io_writer__is_valid(wuffs_base__io_writer o) {
   wuffs_base__io_buffer* buf = o.private_impl.buf;
   // Note: if making this function public (i.e. moving it to base-header.h), it
   // also needs to allow NULL (i.e. implicit, callee-calculated) mark/limit.
-  return buf ? ((buf->ptr <= o.private_impl.mark) &&
+  return buf ? ((buf->data.ptr <= o.private_impl.mark) &&
                 (o.private_impl.mark <= o.private_impl.limit) &&
-                (o.private_impl.limit <= buf->ptr + buf->len))
+                (o.private_impl.limit <= buf->data.ptr + buf->data.len))
              : ((o.private_impl.mark == NULL) &&
                 (o.private_impl.limit == NULL));
 }
@@ -685,11 +686,12 @@ wuffs_base__io_writer__set(wuffs_base__io_writer* o,
                            uint8_t** ioptr1_ptr,
                            uint8_t** ioptr2_ptr,
                            wuffs_base__slice_u8 s) {
-  b->ptr = s.ptr;
-  b->len = s.len;
-  b->wi = 0;
-  b->ri = 0;
-  b->closed = false;
+  b->data.ptr = s.ptr;
+  b->data.len = s.len;
+  b->meta.wi = 0;
+  b->meta.ri = 0;
+  // TODO: set b->meta.pos.
+  b->meta.closed = false;
   o->private_impl.buf = b;
   o->private_impl.mark = s.ptr;
   o->private_impl.limit = s.ptr + s.len;
diff --git a/cmd/wuffs-c/internal/cgen/base/base-public.h b/cmd/wuffs-c/internal/cgen/base/base-public.h
index 1c2fbc92..71646461 100644
--- a/cmd/wuffs-c/internal/cgen/base/base-public.h
+++ b/cmd/wuffs-c/internal/cgen/base/base-public.h
@@ -1043,18 +1043,22 @@ typedef struct {
   } private_impl;
 } wuffs_base__io_writer;
 
-// wuffs_base__io_buffer is a 1-dimensional buffer (a pointer and length), plus
-// additional indexes into that buffer, plus a buffer position and an opened /
-// closed flag.
-//
-// A value with all fields NULL or zero is a valid, empty buffer.
-typedef struct wuffs_base__io_buffer__struct {
-  uint8_t* ptr;  // Pointer.
-  size_t len;    // Length.
+// wuffs_base__io_buffer_meta is the metadata for a wuffs_base__io_buffer's
+// data.
+typedef struct {
   size_t wi;     // Write index. Invariant: wi <= len.
   size_t ri;     // Read  index. Invariant: ri <= wi.
   uint64_t pos;  // Position of the buffer start relative to the stream start.
   bool closed;   // No further writes are expected.
+} wuffs_base__io_buffer_meta;
+
+// wuffs_base__io_buffer is a 1-dimensional buffer (a pointer and length) plus
+// additional metadata.
+//
+// A value with all fields zero is a valid, empty buffer.
+typedef struct wuffs_base__io_buffer__struct {
+  wuffs_base__slice_u8 data;
+  wuffs_base__io_buffer_meta meta;
 
 #ifdef __cplusplus
   inline void compact();
@@ -1070,26 +1074,26 @@ typedef struct wuffs_base__io_buffer__struct {
 // start of the buffer.
 static inline void  //
 wuffs_base__io_buffer__compact(wuffs_base__io_buffer* buf) {
-  if (!buf || (buf->ri == 0)) {
+  if (!buf || (buf->meta.ri == 0)) {
     return;
   }
-  buf->pos = wuffs_base__u64__sat_add(buf->pos, buf->ri);
-  size_t n = buf->wi - buf->ri;
+  buf->meta.pos = wuffs_base__u64__sat_add(buf->meta.pos, buf->meta.ri);
+  size_t n = buf->meta.wi - buf->meta.ri;
   if (n != 0) {
-    memmove(buf->ptr, buf->ptr + buf->ri, n);
+    memmove(buf->data.ptr, buf->data.ptr + buf->meta.ri, n);
   }
-  buf->wi = n;
-  buf->ri = 0;
+  buf->meta.wi = n;
+  buf->meta.ri = 0;
 }
 
 static inline uint64_t  //
 wuffs_base__io_buffer__io_position_reader(wuffs_base__io_buffer* buf) {
-  return buf ? wuffs_base__u64__sat_add(buf->pos, buf->ri) : 0;
+  return buf ? wuffs_base__u64__sat_add(buf->meta.pos, buf->meta.ri) : 0;
 }
 
 static inline uint64_t  //
 wuffs_base__io_buffer__io_position_writer(wuffs_base__io_buffer* buf) {
-  return buf ? wuffs_base__u64__sat_add(buf->pos, buf->wi) : 0;
+  return buf ? wuffs_base__u64__sat_add(buf->meta.pos, buf->meta.wi) : 0;
 }
 
 static inline wuffs_base__io_reader  //
@@ -1156,7 +1160,7 @@ wuffs_base__malloc_slice_u8(void* (*malloc_func)(size_t), uint64_t num_u8) {
     void* p = (*malloc_func)(num_u8 * sizeof(uint8_t));
     if (p) {
       return ((wuffs_base__slice_u8){
-          .ptr = p,
+          .ptr = (uint8_t*)(p),
           .len = num_u8,
       });
     }
@@ -1170,7 +1174,7 @@ wuffs_base__malloc_slice_u16(void* (*malloc_func)(size_t), uint64_t num_u16) {
     void* p = (*malloc_func)(num_u16 * sizeof(uint16_t));
     if (p) {
       return ((wuffs_base__slice_u16){
-          .ptr = p,
+          .ptr = (uint16_t*)(p),
           .len = num_u16,
       });
     }
@@ -1184,7 +1188,7 @@ wuffs_base__malloc_slice_u32(void* (*malloc_func)(size_t), uint64_t num_u32) {
     void* p = (*malloc_func)(num_u32 * sizeof(uint32_t));
     if (p) {
       return ((wuffs_base__slice_u32){
-          .ptr = p,
+          .ptr = (uint32_t*)(p),
           .len = num_u32,
       });
     }
@@ -1198,7 +1202,7 @@ wuffs_base__malloc_slice_u64(void* (*malloc_func)(size_t), uint64_t num_u64) {
     void* p = (*malloc_func)(num_u64 * sizeof(uint64_t));
     if (p) {
       return ((wuffs_base__slice_u64){
-          .ptr = p,
+          .ptr = (uint64_t*)(p),
           .len = num_u64,
       });
     }
diff --git a/release/c/wuffs-unsupported-snapshot.h b/release/c/wuffs-unsupported-snapshot.h
index 4ba35be1..47b97e83 100644
--- a/release/c/wuffs-unsupported-snapshot.h
+++ b/release/c/wuffs-unsupported-snapshot.h
@@ -1081,18 +1081,22 @@ typedef struct {
   } private_impl;
 } wuffs_base__io_writer;
 
-// wuffs_base__io_buffer is a 1-dimensional buffer (a pointer and length), plus
-// additional indexes into that buffer, plus a buffer position and an opened /
-// closed flag.
-//
-// A value with all fields NULL or zero is a valid, empty buffer.
-typedef struct wuffs_base__io_buffer__struct {
-  uint8_t* ptr;  // Pointer.
-  size_t len;    // Length.
+// wuffs_base__io_buffer_meta is the metadata for a wuffs_base__io_buffer's
+// data.
+typedef struct {
   size_t wi;     // Write index. Invariant: wi <= len.
   size_t ri;     // Read  index. Invariant: ri <= wi.
   uint64_t pos;  // Position of the buffer start relative to the stream start.
   bool closed;   // No further writes are expected.
+} wuffs_base__io_buffer_meta;
+
+// wuffs_base__io_buffer is a 1-dimensional buffer (a pointer and length) plus
+// additional metadata.
+//
+// A value with all fields zero is a valid, empty buffer.
+typedef struct wuffs_base__io_buffer__struct {
+  wuffs_base__slice_u8 data;
+  wuffs_base__io_buffer_meta meta;
 
 #ifdef __cplusplus
   inline void compact();
@@ -1108,26 +1112,26 @@ typedef struct wuffs_base__io_buffer__struct {
 // start of the buffer.
 static inline void  //
 wuffs_base__io_buffer__compact(wuffs_base__io_buffer* buf) {
-  if (!buf || (buf->ri == 0)) {
+  if (!buf || (buf->meta.ri == 0)) {
     return;
   }
-  buf->pos = wuffs_base__u64__sat_add(buf->pos, buf->ri);
-  size_t n = buf->wi - buf->ri;
+  buf->meta.pos = wuffs_base__u64__sat_add(buf->meta.pos, buf->meta.ri);
+  size_t n = buf->meta.wi - buf->meta.ri;
   if (n != 0) {
-    memmove(buf->ptr, buf->ptr + buf->ri, n);
+    memmove(buf->data.ptr, buf->data.ptr + buf->meta.ri, n);
   }
-  buf->wi = n;
-  buf->ri = 0;
+  buf->meta.wi = n;
+  buf->meta.ri = 0;
 }
 
 static inline uint64_t  //
 wuffs_base__io_buffer__io_position_reader(wuffs_base__io_buffer* buf) {
-  return buf ? wuffs_base__u64__sat_add(buf->pos, buf->ri) : 0;
+  return buf ? wuffs_base__u64__sat_add(buf->meta.pos, buf->meta.ri) : 0;
 }
 
 static inline uint64_t  //
 wuffs_base__io_buffer__io_position_writer(wuffs_base__io_buffer* buf) {
-  return buf ? wuffs_base__u64__sat_add(buf->pos, buf->wi) : 0;
+  return buf ? wuffs_base__u64__sat_add(buf->meta.pos, buf->meta.wi) : 0;
 }
 
 static inline wuffs_base__io_reader  //
@@ -1194,7 +1198,7 @@ wuffs_base__malloc_slice_u8(void* (*malloc_func)(size_t), uint64_t num_u8) {
     void* p = (*malloc_func)(num_u8 * sizeof(uint8_t));
     if (p) {
       return ((wuffs_base__slice_u8){
-          .ptr = p,
+          .ptr = (uint8_t*)(p),
           .len = num_u8,
       });
     }
@@ -1208,7 +1212,7 @@ wuffs_base__malloc_slice_u16(void* (*malloc_func)(size_t), uint64_t num_u16) {
     void* p = (*malloc_func)(num_u16 * sizeof(uint16_t));
     if (p) {
       return ((wuffs_base__slice_u16){
-          .ptr = p,
+          .ptr = (uint16_t*)(p),
           .len = num_u16,
       });
     }
@@ -1222,7 +1226,7 @@ wuffs_base__malloc_slice_u32(void* (*malloc_func)(size_t), uint64_t num_u32) {
     void* p = (*malloc_func)(num_u32 * sizeof(uint32_t));
     if (p) {
       return ((wuffs_base__slice_u32){
-          .ptr = p,
+          .ptr = (uint32_t*)(p),
           .len = num_u32,
       });
     }
@@ -1236,7 +1240,7 @@ wuffs_base__malloc_slice_u64(void* (*malloc_func)(size_t), uint64_t num_u64) {
     void* p = (*malloc_func)(num_u64 * sizeof(uint64_t));
     if (p) {
       return ((wuffs_base__slice_u64){
-          .ptr = p,
+          .ptr = (uint64_t*)(p),
           .len = num_u64,
       });
     }
@@ -3573,8 +3577,8 @@ wuffs_base__utility__make_rect_ie_u32(wuffs_base__utility* ignored,
 
 static inline bool  //
 wuffs_base__io_buffer__is_valid(wuffs_base__io_buffer buf) {
-  return (buf.ptr || (buf.len == 0)) && (buf.len >= buf.wi) &&
-         (buf.wi >= buf.ri);
+  return (buf.data.ptr || (buf.data.len == 0)) &&
+         (buf.data.len >= buf.meta.wi) && (buf.meta.wi >= buf.meta.ri);
 }
 
 // TODO: wuffs_base__io_reader__is_eof is no longer used by Wuffs per se, but
@@ -3587,7 +3591,8 @@ wuffs_base__io_buffer__is_valid(wuffs_base__io_buffer buf) {
 static inline bool  //
 wuffs_base__io_reader__is_eof(wuffs_base__io_reader o) {
   wuffs_base__io_buffer* buf = o.private_impl.buf;
-  return buf && buf->closed && (buf->ptr + buf->wi == o.private_impl.limit);
+  return buf && buf->meta.closed &&
+         (buf->data.ptr + buf->meta.wi == o.private_impl.limit);
 }
 
 static inline bool  //
@@ -3595,9 +3600,9 @@ wuffs_base__io_reader__is_valid(wuffs_base__io_reader o) {
   wuffs_base__io_buffer* buf = o.private_impl.buf;
   // Note: if making this function public (i.e. moving it to base-header.h), it
   // also needs to allow NULL (i.e. implicit, callee-calculated) mark/limit.
-  return buf ? ((buf->ptr <= o.private_impl.mark) &&
+  return buf ? ((buf->data.ptr <= o.private_impl.mark) &&
                 (o.private_impl.mark <= o.private_impl.limit) &&
-                (o.private_impl.limit <= buf->ptr + buf->len))
+                (o.private_impl.limit <= buf->data.ptr + buf->data.len))
              : ((o.private_impl.mark == NULL) &&
                 (o.private_impl.limit == NULL));
 }
@@ -3607,9 +3612,9 @@ wuffs_base__io_writer__is_valid(wuffs_base__io_writer o) {
   wuffs_base__io_buffer* buf = o.private_impl.buf;
   // Note: if making this function public (i.e. moving it to base-header.h), it
   // also needs to allow NULL (i.e. implicit, callee-calculated) mark/limit.
-  return buf ? ((buf->ptr <= o.private_impl.mark) &&
+  return buf ? ((buf->data.ptr <= o.private_impl.mark) &&
                 (o.private_impl.mark <= o.private_impl.limit) &&
-                (o.private_impl.limit <= buf->ptr + buf->len))
+                (o.private_impl.limit <= buf->data.ptr + buf->data.len))
              : ((o.private_impl.mark == NULL) &&
                 (o.private_impl.limit == NULL));
 }
@@ -3764,11 +3769,12 @@ wuffs_base__io_writer__set(wuffs_base__io_writer* o,
                            uint8_t** ioptr1_ptr,
                            uint8_t** ioptr2_ptr,
                            wuffs_base__slice_u8 s) {
-  b->ptr = s.ptr;
-  b->len = s.len;
-  b->wi = 0;
-  b->ri = 0;
-  b->closed = false;
+  b->data.ptr = s.ptr;
+  b->data.len = s.len;
+  b->meta.wi = 0;
+  b->meta.ri = 0;
+  // TODO: set b->meta.pos.
+  b->meta.closed = false;
   o->private_impl.buf = b;
   o->private_impl.mark = s.ptr;
   o->private_impl.limit = s.ptr + s.len;
@@ -4649,13 +4655,14 @@ wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_dst);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_dst);
   if (a_dst.private_impl.buf) {
-    iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+    iop_a_dst =
+        a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->meta.wi;
     if (!a_dst.private_impl.mark) {
       a_dst.private_impl.mark = iop_a_dst;
       a_dst.private_impl.limit =
-          a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->len;
+          a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->data.len;
     }
-    if (a_dst.private_impl.buf->closed) {
+    if (a_dst.private_impl.buf->meta.closed) {
       a_dst.private_impl.limit = iop_a_dst;
     }
     io0_a_dst = a_dst.private_impl.mark;
@@ -4678,12 +4685,14 @@ wuffs_deflate__decoder__decode(wuffs_deflate__decoder* self,
       wuffs_base__io_writer__set_mark(&a_dst, iop_a_dst);
       {
         if (a_dst.private_impl.buf) {
-          a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+          a_dst.private_impl.buf->meta.wi =
+              iop_a_dst - a_dst.private_impl.buf->data.ptr;
         }
         wuffs_base__status t_0 =
             wuffs_deflate__decoder__decode_blocks(self, a_dst, a_src);
         if (a_dst.private_impl.buf) {
-          iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+          iop_a_dst = a_dst.private_impl.buf->data.ptr +
+                      a_dst.private_impl.buf->meta.wi;
         }
         v_z = t_0;
       }
@@ -4759,7 +4768,8 @@ suspend:
   goto exit;
 exit:
   if (a_dst.private_impl.buf) {
-    a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+    a_dst.private_impl.buf->meta.wi =
+        iop_a_dst - a_dst.private_impl.buf->data.ptr;
   }
 
   if (wuffs_base__status__is_error(status)) {
@@ -4785,11 +4795,12 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -4828,12 +4839,14 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
       if (v_type == 0) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
         if (a_src.private_impl.buf) {
-          a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+          a_src.private_impl.buf->meta.ri =
+              iop_a_src - a_src.private_impl.buf->data.ptr;
         }
         status =
             wuffs_deflate__decoder__decode_uncompressed(self, a_dst, a_src);
         if (a_src.private_impl.buf) {
-          iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+          iop_a_src = a_src.private_impl.buf->data.ptr +
+                      a_src.private_impl.buf->meta.ri;
         }
         if (status) {
           goto suspend;
@@ -4848,11 +4861,13 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
       } else if (v_type == 2) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(4);
         if (a_src.private_impl.buf) {
-          a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+          a_src.private_impl.buf->meta.ri =
+              iop_a_src - a_src.private_impl.buf->data.ptr;
         }
         status = wuffs_deflate__decoder__init_dynamic_huffman(self, a_src);
         if (a_src.private_impl.buf) {
-          iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+          iop_a_src = a_src.private_impl.buf->data.ptr +
+                      a_src.private_impl.buf->meta.ri;
         }
         if (status) {
           goto suspend;
@@ -4864,11 +4879,13 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
       self->private_impl.f_end_of_block = false;
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(5);
       if (a_src.private_impl.buf) {
-        a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+        a_src.private_impl.buf->meta.ri =
+            iop_a_src - a_src.private_impl.buf->data.ptr;
       }
       status = wuffs_deflate__decoder__decode_huffman_fast(self, a_dst, a_src);
       if (a_src.private_impl.buf) {
-        iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+        iop_a_src =
+            a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
       }
       if (status) {
         goto suspend;
@@ -4878,11 +4895,13 @@ wuffs_deflate__decoder__decode_blocks(wuffs_deflate__decoder* self,
       }
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(6);
       if (a_src.private_impl.buf) {
-        a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+        a_src.private_impl.buf->meta.ri =
+            iop_a_src - a_src.private_impl.buf->data.ptr;
       }
       status = wuffs_deflate__decoder__decode_huffman_slow(self, a_dst, a_src);
       if (a_src.private_impl.buf) {
-        iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+        iop_a_src =
+            a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
       }
       if (status) {
         goto suspend;
@@ -4910,7 +4929,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -4933,13 +4953,14 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_dst);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_dst);
   if (a_dst.private_impl.buf) {
-    iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+    iop_a_dst =
+        a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->meta.wi;
     if (!a_dst.private_impl.mark) {
       a_dst.private_impl.mark = iop_a_dst;
       a_dst.private_impl.limit =
-          a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->len;
+          a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->data.len;
     }
-    if (a_dst.private_impl.buf->closed) {
+    if (a_dst.private_impl.buf->meta.closed) {
       a_dst.private_impl.limit = iop_a_dst;
     }
     io0_a_dst = a_dst.private_impl.mark;
@@ -4951,11 +4972,12 @@ wuffs_deflate__decoder__decode_uncompressed(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -5046,10 +5068,12 @@ suspend:
   goto exit;
 exit:
   if (a_dst.private_impl.buf) {
-    a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+    a_dst.private_impl.buf->meta.wi =
+        iop_a_dst - a_dst.private_impl.buf->data.ptr;
   }
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -5146,11 +5170,12 @@ wuffs_deflate__decoder__init_dynamic_huffman(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -5370,7 +5395,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -5685,13 +5711,14 @@ wuffs_deflate__decoder__decode_huffman_fast(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_dst);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_dst);
   if (a_dst.private_impl.buf) {
-    iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+    iop_a_dst =
+        a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->meta.wi;
     if (!a_dst.private_impl.mark) {
       a_dst.private_impl.mark = iop_a_dst;
       a_dst.private_impl.limit =
-          a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->len;
+          a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->data.len;
     }
-    if (a_dst.private_impl.buf->closed) {
+    if (a_dst.private_impl.buf->meta.closed) {
       a_dst.private_impl.limit = iop_a_dst;
     }
     io0_a_dst = a_dst.private_impl.mark;
@@ -5703,11 +5730,12 @@ wuffs_deflate__decoder__decode_huffman_fast(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -5984,10 +6012,12 @@ label_0_break:;
   goto exit;
 exit:
   if (a_dst.private_impl.buf) {
-    a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+    a_dst.private_impl.buf->meta.wi =
+        iop_a_dst - a_dst.private_impl.buf->data.ptr;
   }
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -6021,13 +6051,14 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_dst);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_dst);
   if (a_dst.private_impl.buf) {
-    iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+    iop_a_dst =
+        a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->meta.wi;
     if (!a_dst.private_impl.mark) {
       a_dst.private_impl.mark = iop_a_dst;
       a_dst.private_impl.limit =
-          a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->len;
+          a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->data.len;
     }
-    if (a_dst.private_impl.buf->closed) {
+    if (a_dst.private_impl.buf->meta.closed) {
       a_dst.private_impl.limit = iop_a_dst;
     }
     io0_a_dst = a_dst.private_impl.mark;
@@ -6039,11 +6070,12 @@ wuffs_deflate__decoder__decode_huffman_slow(wuffs_deflate__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -6408,10 +6440,12 @@ suspend:
   goto exit;
 exit:
   if (a_dst.private_impl.buf) {
-    a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+    a_dst.private_impl.buf->meta.wi =
+        iop_a_dst - a_dst.private_impl.buf->data.ptr;
   }
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -6817,11 +6851,12 @@ wuffs_gif__decoder__skip_frame(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -6870,11 +6905,13 @@ wuffs_gif__decoder__skip_frame(wuffs_gif__decoder* self,
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(5);
     if (a_src.private_impl.buf) {
-      a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+      a_src.private_impl.buf->meta.ri =
+          iop_a_src - a_src.private_impl.buf->data.ptr;
     }
     status = wuffs_gif__decoder__skip_blocks(self, a_src);
     if (a_src.private_impl.buf) {
-      iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+      iop_a_src =
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     }
     if (status) {
       goto suspend;
@@ -6898,7 +6935,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -7000,11 +7038,12 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -7021,15 +7060,16 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
 
     if (!self->private_impl.f_restarted) {
       self->private_impl.f_frame_config_io_position =
-          (a_src.private_impl.buf ? wuffs_base__u64__sat_add(
-                                        a_src.private_impl.buf->pos,
-                                        iop_a_src - a_src.private_impl.buf->ptr)
-                                  : 0);
+          (a_src.private_impl.buf
+               ? wuffs_base__u64__sat_add(
+                     a_src.private_impl.buf->meta.pos,
+                     iop_a_src - a_src.private_impl.buf->data.ptr)
+               : 0);
     } else if (self->private_impl.f_frame_config_io_position !=
                (a_src.private_impl.buf
                     ? wuffs_base__u64__sat_add(
-                          a_src.private_impl.buf->pos,
-                          iop_a_src - a_src.private_impl.buf->ptr)
+                          a_src.private_impl.buf->meta.pos,
+                          iop_a_src - a_src.private_impl.buf->data.ptr)
                     : 0)) {
       status = wuffs_base__error__bad_restart;
       goto exit;
@@ -7049,11 +7089,13 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
       if (v_block_type == 33) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
         if (a_src.private_impl.buf) {
-          a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+          a_src.private_impl.buf->meta.ri =
+              iop_a_src - a_src.private_impl.buf->data.ptr;
         }
         status = wuffs_gif__decoder__decode_extension(self, a_src);
         if (a_src.private_impl.buf) {
-          iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+          iop_a_src = a_src.private_impl.buf->data.ptr +
+                      a_src.private_impl.buf->meta.ri;
         }
         if (status) {
           goto suspend;
@@ -7061,11 +7103,13 @@ wuffs_gif__decoder__decode_up_to_id_part1(wuffs_gif__decoder* self,
       } else if (v_block_type == 44) {
         WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
         if (a_src.private_impl.buf) {
-          a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+          a_src.private_impl.buf->meta.ri =
+              iop_a_src - a_src.private_impl.buf->data.ptr;
         }
         status = wuffs_gif__decoder__decode_id_part0(self, a_src);
         if (a_src.private_impl.buf) {
-          iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+          iop_a_src = a_src.private_impl.buf->data.ptr +
+                      a_src.private_impl.buf->meta.ri;
         }
         if (status) {
           goto suspend;
@@ -7096,7 +7140,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -7118,11 +7163,12 @@ wuffs_gif__decoder__decode_header(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -7173,7 +7219,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -7197,11 +7244,12 @@ wuffs_gif__decoder__decode_lsd(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -7367,7 +7415,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -7388,11 +7437,12 @@ wuffs_gif__decoder__decode_extension(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -7419,11 +7469,13 @@ wuffs_gif__decoder__decode_extension(wuffs_gif__decoder* self,
     if (v_label == 249) {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(2);
       if (a_src.private_impl.buf) {
-        a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+        a_src.private_impl.buf->meta.ri =
+            iop_a_src - a_src.private_impl.buf->data.ptr;
       }
       status = wuffs_gif__decoder__decode_gc(self, a_src);
       if (a_src.private_impl.buf) {
-        iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+        iop_a_src =
+            a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
       }
       if (status) {
         goto suspend;
@@ -7433,11 +7485,13 @@ wuffs_gif__decoder__decode_extension(wuffs_gif__decoder* self,
     } else if (v_label == 255) {
       WUFFS_BASE__COROUTINE_SUSPENSION_POINT(3);
       if (a_src.private_impl.buf) {
-        a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+        a_src.private_impl.buf->meta.ri =
+            iop_a_src - a_src.private_impl.buf->data.ptr;
       }
       status = wuffs_gif__decoder__decode_ae(self, a_src);
       if (a_src.private_impl.buf) {
-        iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+        iop_a_src =
+            a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
       }
       if (status) {
         goto suspend;
@@ -7447,11 +7501,13 @@ wuffs_gif__decoder__decode_extension(wuffs_gif__decoder* self,
     }
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(4);
     if (a_src.private_impl.buf) {
-      a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+      a_src.private_impl.buf->meta.ri =
+          iop_a_src - a_src.private_impl.buf->data.ptr;
     }
     status = wuffs_gif__decoder__skip_blocks(self, a_src);
     if (a_src.private_impl.buf) {
-      iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+      iop_a_src =
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     }
     if (status) {
       goto suspend;
@@ -7471,7 +7527,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -7492,11 +7549,12 @@ wuffs_gif__decoder__skip_blocks(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -7552,7 +7610,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -7576,11 +7635,12 @@ wuffs_gif__decoder__decode_ae(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -7735,11 +7795,13 @@ wuffs_gif__decoder__decode_ae(wuffs_gif__decoder* self,
   label_0_break:;
     WUFFS_BASE__COROUTINE_SUSPENSION_POINT(13);
     if (a_src.private_impl.buf) {
-      a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+      a_src.private_impl.buf->meta.ri =
+          iop_a_src - a_src.private_impl.buf->data.ptr;
     }
     status = wuffs_gif__decoder__skip_blocks(self, a_src);
     if (a_src.private_impl.buf) {
-      iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+      iop_a_src =
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     }
     if (status) {
       goto suspend;
@@ -7762,7 +7824,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -7784,11 +7847,12 @@ wuffs_gif__decoder__decode_gc(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -7906,7 +7970,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -7925,11 +7990,12 @@ wuffs_gif__decoder__decode_id_part0(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -8083,7 +8149,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -8118,11 +8185,12 @@ wuffs_gif__decoder__decode_id_part1(wuffs_gif__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -8303,17 +8371,17 @@ wuffs_gif__decoder__decode_id_part1(wuffs_gif__decoder* self,
           wuffs_base__io_reader__set_limit(&a_src, iop_a_src, v_block_size);
           wuffs_base__io_reader__set_mark(&a_src, iop_a_src);
           {
-            u_w.wi = iop_v_w - u_w.ptr;
+            u_w.meta.wi = iop_v_w - u_w.data.ptr;
             if (a_src.private_impl.buf) {
-              a_src.private_impl.buf->ri =
-                  iop_a_src - a_src.private_impl.buf->ptr;
+              a_src.private_impl.buf->meta.ri =
+                  iop_a_src - a_src.private_impl.buf->data.ptr;
             }
             wuffs_base__status t_5 = wuffs_lzw__decoder__decode(
                 &self->private_impl.f_lzw, v_w, a_src);
-            iop_v_w = u_w.ptr + u_w.wi;
+            iop_v_w = u_w.data.ptr + u_w.meta.wi;
             if (a_src.private_impl.buf) {
-              iop_a_src =
-                  a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+              iop_a_src = a_src.private_impl.buf->data.ptr +
+                          a_src.private_impl.buf->meta.ri;
             }
             v_z = t_5;
           }
@@ -8386,7 +8454,8 @@ suspend:
   goto exit;
 exit:
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   return status;
@@ -8611,13 +8680,14 @@ wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_dst);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_dst);
   if (a_dst.private_impl.buf) {
-    iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+    iop_a_dst =
+        a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->meta.wi;
     if (!a_dst.private_impl.mark) {
       a_dst.private_impl.mark = iop_a_dst;
       a_dst.private_impl.limit =
-          a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->len;
+          a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->data.len;
     }
-    if (a_dst.private_impl.buf->closed) {
+    if (a_dst.private_impl.buf->meta.closed) {
       a_dst.private_impl.limit = iop_a_dst;
     }
     io0_a_dst = a_dst.private_impl.mark;
@@ -8629,11 +8699,12 @@ wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -8813,18 +8884,22 @@ wuffs_gzip__decoder__decode(wuffs_gzip__decoder* self,
       wuffs_base__io_writer__set_mark(&a_dst, iop_a_dst);
       {
         if (a_dst.private_impl.buf) {
-          a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+          a_dst.private_impl.buf->meta.wi =
+              iop_a_dst - a_dst.private_impl.buf->data.ptr;
         }
         if (a_src.private_impl.buf) {
-          a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+          a_src.private_impl.buf->meta.ri =
+              iop_a_src - a_src.private_impl.buf->data.ptr;
         }
         wuffs_base__status t_8 = wuffs_deflate__decoder__decode(
             &self->private_impl.f_flate, a_dst, a_src);
         if (a_dst.private_impl.buf) {
-          iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+          iop_a_dst = a_dst.private_impl.buf->data.ptr +
+                      a_dst.private_impl.buf->meta.wi;
         }
         if (a_src.private_impl.buf) {
-          iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+          iop_a_src = a_src.private_impl.buf->data.ptr +
+                      a_src.private_impl.buf->meta.ri;
         }
         v_z = t_8;
       }
@@ -8937,10 +9012,12 @@ suspend:
   goto exit;
 exit:
   if (a_dst.private_impl.buf) {
-    a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+    a_dst.private_impl.buf->meta.wi =
+        iop_a_dst - a_dst.private_impl.buf->data.ptr;
   }
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   if (wuffs_base__status__is_error(status)) {
@@ -9045,13 +9122,14 @@ wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_dst);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_dst);
   if (a_dst.private_impl.buf) {
-    iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+    iop_a_dst =
+        a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->meta.wi;
     if (!a_dst.private_impl.mark) {
       a_dst.private_impl.mark = iop_a_dst;
       a_dst.private_impl.limit =
-          a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->len;
+          a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->data.len;
     }
-    if (a_dst.private_impl.buf->closed) {
+    if (a_dst.private_impl.buf->meta.closed) {
       a_dst.private_impl.limit = iop_a_dst;
     }
     io0_a_dst = a_dst.private_impl.mark;
@@ -9063,11 +9141,12 @@ wuffs_lzw__decoder__decode(wuffs_lzw__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -9224,10 +9303,12 @@ suspend:
   goto exit;
 exit:
   if (a_dst.private_impl.buf) {
-    a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+    a_dst.private_impl.buf->meta.wi =
+        iop_a_dst - a_dst.private_impl.buf->data.ptr;
   }
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   if (wuffs_base__status__is_error(status)) {
@@ -9339,13 +9420,14 @@ wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_dst);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_dst);
   if (a_dst.private_impl.buf) {
-    iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+    iop_a_dst =
+        a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->meta.wi;
     if (!a_dst.private_impl.mark) {
       a_dst.private_impl.mark = iop_a_dst;
       a_dst.private_impl.limit =
-          a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->len;
+          a_dst.private_impl.buf->data.ptr + a_dst.private_impl.buf->data.len;
     }
-    if (a_dst.private_impl.buf->closed) {
+    if (a_dst.private_impl.buf->meta.closed) {
       a_dst.private_impl.limit = iop_a_dst;
     }
     io0_a_dst = a_dst.private_impl.mark;
@@ -9357,11 +9439,12 @@ wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io0_a_src);
   WUFFS_BASE__IGNORE_POTENTIALLY_UNUSED_VARIABLE(io1_a_src);
   if (a_src.private_impl.buf) {
-    iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+    iop_a_src =
+        a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.ri;
     if (!a_src.private_impl.mark) {
       a_src.private_impl.mark = iop_a_src;
       a_src.private_impl.limit =
-          a_src.private_impl.buf->ptr + a_src.private_impl.buf->wi;
+          a_src.private_impl.buf->data.ptr + a_src.private_impl.buf->meta.wi;
     }
     io0_a_src = a_src.private_impl.mark;
     io1_a_src = a_src.private_impl.limit;
@@ -9428,18 +9511,22 @@ wuffs_zlib__decoder__decode(wuffs_zlib__decoder* self,
       wuffs_base__io_writer__set_mark(&a_dst, iop_a_dst);
       {
         if (a_dst.private_impl.buf) {
-          a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+          a_dst.private_impl.buf->meta.wi =
+              iop_a_dst - a_dst.private_impl.buf->data.ptr;
         }
         if (a_src.private_impl.buf) {
-          a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+          a_src.private_impl.buf->meta.ri =
+              iop_a_src - a_src.private_impl.buf->data.ptr;
         }
         wuffs_base__status t_2 = wuffs_deflate__decoder__decode(
             &self->private_impl.f_flate, a_dst, a_src);
         if (a_dst.private_impl.buf) {
-          iop_a_dst = a_dst.private_impl.buf->ptr + a_dst.private_impl.buf->wi;
+          iop_a_dst = a_dst.private_impl.buf->data.ptr +
+                      a_dst.private_impl.buf->meta.wi;
         }
         if (a_src.private_impl.buf) {
-          iop_a_src = a_src.private_impl.buf->ptr + a_src.private_impl.buf->ri;
+          iop_a_src = a_src.private_impl.buf->data.ptr +
+                      a_src.private_impl.buf->meta.ri;
         }
         v_z = t_2;
       }
@@ -9510,10 +9597,12 @@ suspend:
   goto exit;
 exit:
   if (a_dst.private_impl.buf) {
-    a_dst.private_impl.buf->wi = iop_a_dst - a_dst.private_impl.buf->ptr;
+    a_dst.private_impl.buf->meta.wi =
+        iop_a_dst - a_dst.private_impl.buf->data.ptr;
   }
   if (a_src.private_impl.buf) {
-    a_src.private_impl.buf->ri = iop_a_src - a_src.private_impl.buf->ptr;
+    a_src.private_impl.buf->meta.ri =
+        iop_a_src - a_src.private_impl.buf->data.ptr;
   }
 
   if (wuffs_base__status__is_error(status)) {
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
