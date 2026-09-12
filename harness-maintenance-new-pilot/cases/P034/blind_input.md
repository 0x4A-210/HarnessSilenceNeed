# Case ID

P034

## Existing Fuzz Harness H0

### `tests/spng_read_fuzzer.cc`

~~~~cpp
#define SPNG_UNTESTED
#include "../spng.h"

#include <string.h>

struct buf_state
{
    const uint8_t *data;
    size_t bytes_left;
};

static int buffer_read_fn(spng_ctx *ctx, void *user, void *dest, size_t length)
{
    struct buf_state *state = (struct buf_state*)user;

    if(length > state->bytes_left) return SPNG_IO_EOF;

    memcpy(dest, state->data, length);

    state->bytes_left -= length;
    state->data += length;

    return 0;
}

#ifdef __cplusplus
extern "C"
#endif
int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
    if(size < 4) return 0;

    int flags = data[size - 1];
    int fmt = data[size - 3] | (data[size - 2] << 8);
    int stream = data[size - 4] & 1;
    int progressive = data[size - 4] & 2;

    size -= 4;

    int ret;
    unsigned char *out = NULL;

    spng_ctx *ctx = spng_ctx_new(SPNG_CTX_IGNORE_ADLER32);
    if(ctx == NULL) return 0;

    struct spng_ihdr ihdr;
    struct spng_plte plte;
    struct spng_trns trns;
    struct spng_chrm chrm;
    struct spng_chrm_int chrm_int;
    double gamma;
    struct spng_iccp iccp;
    struct spng_sbit sbit;
    uint8_t srgb_rendering_intent;
    struct spng_text text[4];
    struct spng_bkgd bkgd;
    struct spng_hist hist;
    struct spng_phys phys;
    struct spng_splt splt[4];
    struct spng_time time;
    uint32_t n_text = 4, n_splt = 4;

    struct buf_state state;
    state.data = data;
    state.bytes_left = size;

    if(stream) ret = spng_set_png_stream(ctx, buffer_read_fn, &state);
    else ret = spng_set_png_buffer(ctx, (void*)data, size);

    if(ret) goto err;

    spng_set_image_limits(ctx, 200000, 200000);

    spng_set_chunk_limits(ctx, 4 * 1000 * 1000, 8 * 1000 * 1000);

    spng_set_crc_action(ctx, SPNG_CRC_USE, SPNG_CRC_USE);

    size_t out_size;
    if(spng_decoded_image_size(ctx, fmt, &out_size)) goto err;

    if(out_size > 80000000) goto err;

    out = (unsigned char*)malloc(out_size);
    if(out == NULL) goto err;

    spng_get_ihdr(ctx, &ihdr);
    spng_get_plte(ctx, &plte);
    spng_get_trns(ctx, &trns);
    spng_get_chrm(ctx, &chrm);
    spng_get_chrm_int(ctx, &chrm_int);
    spng_get_gama(ctx, &gamma);
    spng_get_iccp(ctx, &iccp);
    spng_get_sbit(ctx, &sbit);
    spng_get_srgb(ctx, &srgb_rendering_intent);

    if(!spng_get_text(ctx, text, &n_text))
    {/* Up to 4 entries were read, get the actual count */
        spng_get_text(ctx, NULL, &n_text);

        uint32_t i;
        for(i=0; i < n_text; i++)
        {/* All strings should be non-NULL */
            if(text[i].text == NULL || text[i].language_tag == NULL || text[i].translated_keyword == NULL)
            {
                spng_ctx_free(ctx);
                if(out != NULL) free(out);
                return 1;
            }
            /* This shouldn't cause issues either */
            text[i].length = strlen(text[i].text);
        }
    }

    spng_get_bkgd(ctx, &bkgd);
    spng_get_hist(ctx, &hist);
    spng_get_phys(ctx, &phys);
    spng_get_splt(ctx, splt, &n_splt);
    spng_get_time(ctx, &time);

    if(progressive)
    {
        if(spng_decode_image(ctx, NULL, 0, fmt, flags | SPNG_DECODE_PROGRESSIVE)) goto err;

        size_t ioffset, out_width = out_size / ihdr.height;
        struct spng_row_info ri;

        do
        {
            if(spng_get_row_info(ctx, &ri)) break;

            ioffset = ri.row_num * out_width;

        }while(!spng_decode_row(ctx, out + ioffset, out_size));
    }
    else if(spng_decode_image(ctx, out, out_size, fmt, flags)) goto err;

err:
    spng_ctx_free(ctx);
    if(out != NULL) free(out);

    return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is a deterministic H0-identifier-anchored excerpt capped at 70,000 characters.

~~~~diff
... [unselected diff lines omitted by frozen H0-anchored rule] ...
diff --git a/spng/spng.c b/spng/spng.c
new file mode 100644
index 0000000..897d540
--- /dev/null
+++ b/spng/spng.c
@@ -0,0 +1,4818 @@
+/* SPDX-License-Identifier: (BSD-2-Clause AND libpng-2.0) */
+#include "spng.h"
+
+#include <limits.h>
+#include <string.h>
+#include <stdio.h>
+#include <math.h>
+
+#define ZLIB_CONST
+
+#ifdef __FRAMAC__
+    #define SPNG_DISABLE_OPT
+    #include "tests/framac_stubs.h"
+#else
+    #ifdef SPNG_USE_MINIZ
+        #include <miniz.h>
+    #else
+        #include <zlib.h>
+    #endif
+#endif
+
+#ifdef SPNG_MULTITHREADING
+    #include <pthread.h>
+#endif
+
+#if defined(_MSC_VER)
+
+    #if _MSC_VER >= 1900
+        #define restrict __restrict
+    #else
+        #define restrict
+    #endif
+
+    #pragma warning(push)
+    #pragma warning(disable: 4244)
+#endif
+
+#define SPNG_READ_SIZE 8192
+
+#define SPNG_TARGET_CLONES(x)
+
+#ifndef SPNG_DISABLE_OPT
+
+    #if defined(__i386__) || defined(__x86_64__) || defined(_M_IX86) || defined(_M_X64)
+        #define SPNG_X86
+
+        #if defined(__x86_64__) || defined(_M_X64)
+            #define SPNG_X86_64
+        #endif
+
+    #elif defined(__aarch64__) || defined(_M_ARM64) || defined(__ARM_NEON)
+        /* #define SPNG_ARM */ /* buffer overflow for rgb8 images */
+        #define SPNG_DISABLE_OPT
+    #else
+        #warning "disabling optimizations for unknown platform"
+        #define SPNG_DISABLE_OPT
+    #endif
+
+    #if defined(SPNG_X86_64) && defined(SPNG_ENABLE_TARGET_CLONES)
+        #undef SPNG_TARGET_CLONES
+        #define SPNG_TARGET_CLONES(x) __attribute__((target_clones(x)))
+    #else
+        #define SPNG_TARGET_CLONES(x)
+    #endif
+
+    #ifndef SPNG_DISABLE_OPT
+        static void defilter_sub3(size_t rowbytes, unsigned char *row);
+        static void defilter_sub4(size_t rowbytes, unsigned char *row);
+        static void defilter_avg3(size_t rowbytes, unsigned char *restrict row, const unsigned char *prev);
+        static void defilter_avg4(size_t rowbytes, unsigned char *restrict row, const unsigned char *prev);
+        static void defilter_paeth3(size_t rowbytes, unsigned char *restrict row, const unsigned char *prev);
+        static void defilter_paeth4(size_t rowbytes, unsigned char *restrict row, const unsigned char *prev);
+    #endif
+#endif
+
+#if (defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__) || defined(__BIG_ENDIAN__)
+    #define SPNG_BIG_ENDIAN
+#else
+    #define SPNG_LITTLE_ENDIAN
+#endif
+
+enum spng_state
+{
+    SPNG_STATE_INVALID = 0,
+    SPNG_STATE_INIT = 1, /* No PNG buffer/stream is set */
+    SPNG_STATE_INPUT, /* Input PNG was set */
+    SPNG_STATE_IHDR, /* IHDR was read */
+    SPNG_STATE_FIRST_IDAT,  /* Reached first IDAT */
+    SPNG_STATE_DECODE_INIT, /* Decoder is ready for progressive reads */
+    SPNG_STATE_EOI, /* Reached the last scanline/row */
+    SPNG_STATE_LAST_IDAT, /* Reached last IDAT, set at end of decode_image() */
+    SPNG_STATE_AFTER_IDAT, /*  */
+    SPNG_STATE_IEND, /* Reached IEND */
+};
+
+#define SPNG_STR(x) _SPNG_STR(x)
+#define _SPNG_STR(x) #x
+
+#define SPNG_VERSION_STRING SPNG_STR(SPNG_VERSION_MAJOR) "." \
+                            SPNG_STR(SPNG_VERSION_MINOR) "." \
+                            SPNG_STR(SPNG_VERSION_PATCH)
+
+#define SPNG_GET_CHUNK_BOILERPLATE(chunk) \
+    if(ctx == NULL || chunk == NULL) return 1; \
+    int ret = read_chunks(ctx, 0); \
+    if(ret) return ret;
+
+#define SPNG_SET_CHUNK_BOILERPLATE(chunk) \
+    if(ctx == NULL || chunk == NULL) return 1; \
+    if(ctx->data == NULL) ctx->encode_only = 1; \
+    int ret = read_chunks(ctx, 0); \
+    if(ret) return ret;
+
+struct spng_subimage
+{
+    uint32_t width;
+    uint32_t height;
+    size_t out_width; /* byte width based on output format */
+    size_t scanline_width;
+};
+
+struct spng_plte_entry16
+{
+    uint16_t red;
+    uint16_t green;
+    uint16_t blue;
+    uint16_t alpha;
+};
+
+struct spng_text2
+{
+    int type;
+    char *keyword;
+    char *text;
+
+    size_t text_length;
+
+    uint8_t compression_flag; /* iTXt only */
+    char *language_tag; /* iTXt only */
+    char *translated_keyword; /* iTXt only */
+};
+
+struct decode_flags
+{
+    unsigned apply_trns:  1;
+    unsigned apply_gamma: 1;
+    unsigned use_sbit:    1;
+    unsigned indexed:     1;
+    unsigned do_scaling:  1;
+    unsigned interlaced:  1;
+    unsigned same_layout: 1;
+    unsigned zerocopy:    1;
+    unsigned unpack:      1;
+};
+
+struct spng_chunk_bitfield
+{
+    unsigned ihdr: 1;
+    unsigned plte: 1;
+    unsigned chrm: 1;
+    unsigned iccp: 1;
+    unsigned gama: 1;
+    unsigned sbit: 1;
+    unsigned srgb: 1;
+    unsigned text: 1;
+    unsigned bkgd: 1;
+    unsigned hist: 1;
+    unsigned trns: 1;
+    unsigned phys: 1;
+    unsigned splt: 1;
+    unsigned time: 1;
+    unsigned offs: 1;
+    unsigned exif: 1;
+};
+
+/* Packed sample iterator */
+struct spng__iter
+{
+    const uint8_t mask;
+    const unsigned initial_shift;
+    unsigned shift_amount, bit_depth;
+    const unsigned char *samples;
+};
+
+struct spng_ctx
+{
+    size_t data_size;
+    size_t bytes_read;
+    unsigned char *stream_buf;
+    const unsigned char *data;
+
+    /* User-defined pointers for streaming */
+    spng_read_fn *read_fn;
+    void *read_user_ptr;
+
+    /* Used for buffer reads */
+    const unsigned char *png_buf; /* base pointer for the buffer */
+    size_t bytes_left;
+    size_t last_read_size;
+
+    /* These are updated by read_header()/read_chunk_bytes() */
+    struct spng_chunk current_chunk;
+    uint32_t cur_chunk_bytes_left;
+    uint32_t cur_actual_crc;
+
+    struct spng_alloc alloc;
+
+    int flags; /* context flags */
+    int fmt;
+
+    unsigned state: 4;
+    unsigned streaming: 1;
+
+    unsigned encode_only: 1;
+
+    /* input file contains this chunk */
+    struct spng_chunk_bitfield file;
+
+    /* chunk was stored with spng_set_*() */
+    struct spng_chunk_bitfield user;
+
+    /* chunk was stored by reading or with spng_set_*() */
+    struct spng_chunk_bitfield stored;
+
+    struct spng_chunk first_idat, last_idat;
+
+    uint32_t max_width, max_height;
+
+    uint32_t max_chunk_size;
+    size_t chunk_cache_limit;
+    size_t chunk_cache_usage;
+
+    int crc_action_critical;
+    int crc_action_ancillary;
+
+    struct spng_ihdr ihdr;
+
+    struct spng_plte plte;
+
+    struct spng_chrm_int chrm_int;
+    struct spng_iccp iccp;
+
+    uint32_t gama;
+
+    struct spng_sbit sbit;
+
+    uint8_t srgb_rendering_intent;
+
+    uint32_t n_text;
+    struct spng_text2 *text_list;
+
+    struct spng_bkgd bkgd;
+    struct spng_hist hist;
+    struct spng_trns trns;
+    struct spng_phys phys;
+
+    uint32_t n_splt;
+    struct spng_splt *splt_list;
+
+    struct spng_time time;
+    struct spng_offs offs;
+    struct spng_exif exif;
+
+    struct spng_subimage subimage[7];
+
+    z_stream zstream;
+    unsigned char *scanline_buf, *prev_scanline_buf, *row_buf;
+    unsigned char *scanline, *prev_scanline, *row;
+
+    size_t total_out_size;
+    size_t out_width; /* total_out_size / ihdr.height */
+
+    unsigned channels;
+    unsigned bytes_per_pixel; /* input PNG */
+    unsigned pixel_size; /* output format */
+    int widest_pass;
+    int last_pass; /* last non-empty pass */
+
+    uint16_t *gamma_lut; /* points to either _lut8 or _lut16 */
+    uint16_t *gamma_lut16;
+    uint16_t gamma_lut8[256];
+    unsigned char trns_px[8];
+    struct spng_plte_entry16 decode_plte[256];
+    struct spng_sbit decode_sb;
+    struct decode_flags decode_flags;
+    struct spng_row_info row_info;
+};
+
+static const uint32_t png_u32max = 2147483647;
+
+static const uint8_t png_signature[8] = { 137, 80, 78, 71, 13, 10, 26, 10 };
+
+static const unsigned int adam7_x_start[7] = { 0, 4, 0, 2, 0, 1, 0 };
+static const unsigned int adam7_y_start[7] = { 0, 0, 4, 0, 2, 0, 1 };
+static const unsigned int adam7_x_delta[7] = { 8, 8, 4, 4, 2, 2, 1 };
+static const unsigned int adam7_y_delta[7] = { 8, 8, 8, 4, 4, 2, 2 };
+
+static const uint8_t type_ihdr[4] = { 73, 72, 68, 82 };
+static const uint8_t type_plte[4] = { 80, 76, 84, 69 };
+static const uint8_t type_idat[4] = { 73, 68, 65, 84 };
+static const uint8_t type_iend[4] = { 73, 69, 78, 68 };
+
+static const uint8_t type_trns[4] = { 116, 82, 78, 83 };
+static const uint8_t type_chrm[4] = { 99,  72, 82, 77 };
+static const uint8_t type_gama[4] = { 103, 65, 77, 65 };
+static const uint8_t type_iccp[4] = { 105, 67, 67, 80 };
+static const uint8_t type_sbit[4] = { 115, 66, 73, 84 };
+static const uint8_t type_srgb[4] = { 115, 82, 71, 66 };
+static const uint8_t type_text[4] = { 116, 69, 88, 116 };
+static const uint8_t type_ztxt[4] = { 122, 84, 88, 116 };
+static const uint8_t type_itxt[4] = { 105, 84, 88, 116 };
+static const uint8_t type_bkgd[4] = { 98,  75, 71, 68 };
+static const uint8_t type_hist[4] = { 104, 73, 83, 84 };
+static const uint8_t type_phys[4] = { 112, 72, 89, 115 };
+static const uint8_t type_splt[4] = { 115, 80, 76, 84 };
+static const uint8_t type_time[4] = { 116, 73, 77, 69 };
+
+static const uint8_t type_offs[4] = { 111, 70, 70, 115 };
+static const uint8_t type_exif[4] = { 101, 88, 73, 102 };
+
+static inline void *spng__malloc(spng_ctx *ctx,  size_t size)
+{
+    return ctx->alloc.malloc_fn(size);
+}
+
+static inline void *spng__calloc(spng_ctx *ctx, size_t nmemb, size_t size)
+{
+    return ctx->alloc.calloc_fn(nmemb, size);
+}
+
+static inline void *spng__realloc(spng_ctx *ctx, void *ptr, size_t size)
+{
+    return ctx->alloc.realloc_fn(ptr, size);
+}
+
+static inline void spng__free(spng_ctx *ctx, void *ptr)
+{
+    ctx->alloc.free_fn(ptr);
+}
+
+#if defined(SPNG_USE_MINIZ)
+static void *spng__zalloc(void *opaque, long unsigned items, long unsigned size)
+#else
+static void *spng__zalloc(void *opaque, unsigned items, unsigned size)
+#endif
+{
+    spng_ctx *ctx = opaque;
+
+    if(size > SIZE_MAX / items) return NULL;
+
+    size_t len = (size_t)items * size;
+
+    return spng__malloc(ctx, len);
+}
+
+static void spng__zfree(void *opqaue, void *ptr)
+{
+    spng_ctx *ctx = opqaue;
+    spng__free(ctx, ptr);
+}
+
+static int spng__inflate_init(spng_ctx *ctx)
+{
+    if(ctx->zstream.state) inflateEnd(&ctx->zstream);
+
+    ctx->zstream.zalloc = spng__zalloc;
+    ctx->zstream.zfree = spng__zfree;
+    ctx->zstream.opaque = ctx;
+
+    if(inflateInit(&ctx->zstream) != Z_OK) return SPNG_EZLIB;
+
+#if ZLIB_VERNUM >= 0x1290 && !defined(SPNG_USE_MINIZ)
+    if(inflateValidate(&ctx->zstream, ctx->flags & SPNG_CTX_IGNORE_ADLER32)) return SPNG_EZLIB;
+#else /* This requires zlib >= 1.2.11 */
+    #warning "inflateValidate() not available, SPNG_CTX_IGNORE_ADLER32 will be ignored"
+#endif
+
+    return 0;
+}
+
+static inline uint16_t read_u16(const void *_data)
+{
+    const unsigned char *data = _data;
+
+    return (data[0] & 0xFFU) << 8 | (data[1] & 0xFFU);
+}
+
+static inline uint32_t read_u32(const void *_data)
+{
+    const unsigned char *data = _data;
+
+    return (data[0] & 0xFFUL) << 24 | (data[1] & 0xFFUL) << 16 |
+           (data[2] & 0xFFUL) << 8  | (data[3] & 0xFFUL);
+}
+
+static inline int32_t read_s32(const void *_data)
+{
+    const unsigned char *data = _data;
+
+    int32_t ret;
+    uint32_t val = (data[0] & 0xFFUL) << 24 | (data[1] & 0xFFUL) << 16 |
+                   (data[2] & 0xFFUL) << 8  | (data[3] & 0xFFUL);
+
+    memcpy(&ret, &val, 4);
+
+    return ret;
+}
+
+/* Returns an iterator for 1,2,4,8-bit samples */
+static struct spng__iter spng__iter_init(unsigned bit_depth, const unsigned char *samples)
+{
+    struct spng__iter iter =
+    {
+        .mask = (uint16_t)(1 << bit_depth) - 1,
+        .shift_amount = 8 - bit_depth,
+        .initial_shift = 8 - bit_depth,
+        .bit_depth = bit_depth,
+        .samples = samples
+    };
+
+    return iter;
+}
+
+/* Returns the current sample unpacked, iterates to the next one */
+static inline uint8_t get_sample(struct spng__iter *iter)
+{
+    uint8_t x = (iter->samples[0] >> iter->shift_amount) & iter->mask;
+
+    iter->shift_amount -= iter->bit_depth;
+
+    if(iter->shift_amount > 7)
+    {
+        iter->shift_amount = iter->initial_shift;
+        iter->samples++;
+    }
+
+    return x;
+}
+
+static void u16_row_to_host(void *row, size_t size)
+{
+    uint16_t *px = row;
+    size_t i, n = size / 2;
+    for(i=0; i < n; i++)
+    {
+        px[i] = read_u16(&px[i]);
+    }
+}
+
+static void rgb8_row_to_rgba8(const unsigned char *row, unsigned char *restrict out, uint32_t n)
+{
+    uint32_t i;
+    for(i=0; i < n; i++)
+    {
+        memcpy(out + i * 4, row + i * 3, 3);
+        out[i*4+3] = 255;
+    }
+}
+
+/* Calculate scanline width in bits, round up to the nearest byte */
+static int calculate_scanline_width(struct spng_ctx *ctx, uint32_t width, size_t *scanline_width)
+{
+    if(!width) return 1;
+
+    size_t res = ctx->channels * ctx->ihdr.bit_depth;
+
+    if(res > SIZE_MAX / width) return SPNG_EOVERFLOW;
+    res = res * width;
+
+    res += 15; /* Filter byte + 7 for rounding */
+
+    if(res < 15) return SPNG_EOVERFLOW;
+
+    res /= 8;
+
+    if(res > UINT32_MAX) return SPNG_EOVERFLOW;
+
+    *scanline_width = res;
+
+    return 0;
+}
+
+static int calculate_subimages(struct spng_ctx *ctx)
+{
+    if(ctx == NULL) return 1;
+
+    struct spng_ihdr *ihdr = &ctx->ihdr;
+    struct spng_subimage *sub = ctx->subimage;
+
+    if(ihdr->interlace_method == 1)
+    {
+        sub[0].width = (ihdr->width + 7) >> 3;
+        sub[0].height = (ihdr->height + 7) >> 3;
+        sub[1].width = (ihdr->width + 3) >> 3;
+        sub[1].height = (ihdr->height + 7) >> 3;
+        sub[2].width = (ihdr->width + 3) >> 2;
+        sub[2].height = (ihdr->height + 3) >> 3;
+        sub[3].width = (ihdr->width + 1) >> 2;
+        sub[3].height = (ihdr->height + 3) >> 2;
+        sub[4].width = (ihdr->width + 1) >> 1;
+        sub[4].height = (ihdr->height + 1) >> 2;
+        sub[5].width = ihdr->width >> 1;
+        sub[5].height = (ihdr->height + 1) >> 1;
+        sub[6].width = ihdr->width;
+        sub[6].height = ihdr->height >> 1;
+    }
+    else
+    {
+        sub[0].width = ihdr->width;
+        sub[0].height = ihdr->height;
+    }
+
+    int i;
+    for(i=0; i < 7; i++)
+    {
+        if(sub[i].width == 0 || sub[i].height == 0) continue;
+
+        int ret = calculate_scanline_width(ctx, sub[i].width, &sub[i].scanline_width);
+        if(ret) return ret;
+
+        if(sub[ctx->widest_pass].scanline_width < sub[i].scanline_width) ctx->widest_pass = i;
+
+        ctx->last_pass = i;
+    }
+
+    return 0;
+}
+
+
+static int increase_cache_usage(spng_ctx *ctx, size_t bytes)
+{
+    if(ctx == NULL || !bytes) return 1;
+
+    size_t new_usage = ctx->chunk_cache_usage + bytes;
+
+    /* Overflow, treat it as a normal error though */
+    if(new_usage < ctx->chunk_cache_usage) return 1;
+
+    if(new_usage > ctx->chunk_cache_limit) return 1;
+
+    ctx->chunk_cache_usage = new_usage;
+
+    return 0;
+}
+
+static int decrease_cache_usage(spng_ctx *ctx, size_t usage)
+{
+    if(ctx == NULL || !usage) return 1;
+    if(usage > ctx->chunk_cache_usage) return 1;
+
+    ctx->chunk_cache_usage -= usage;
+
+    return 0;
+}
+
+static int is_critical_chunk(struct spng_chunk *chunk)
+{
+    if(chunk == NULL) return 0;
+    if((chunk->type[0] & (1 << 5)) == 0) return 1;
+
+    return 0;
+}
+
+static inline int read_data(spng_ctx *ctx, size_t bytes)
+{
+    if(ctx == NULL) return 1;
+    if(!bytes) return 0;
+
+    if(ctx->streaming && (bytes > SPNG_READ_SIZE)) return 1;
+
+    int ret;
+    ret = ctx->read_fn(ctx, ctx->read_user_ptr, ctx->stream_buf, bytes);
+    if(ret) return ret;
+
+    ctx->bytes_read += bytes;
+    if(ctx->bytes_read < bytes) return SPNG_EOVERFLOW;
+
+    return 0;
+}
+
+/* Read and check the current chunk's crc,
+   returns -SPNG_CRC_DISCARD if the chunk should be discarded */
+static inline int read_and_check_crc(spng_ctx *ctx)
+{
+    if(ctx == NULL) return 1;
+
+    int ret;
+    ret = read_data(ctx, 4);
+    if(ret) return ret;
+
+    ctx->current_chunk.crc = read_u32(ctx->data);
+
+    if(ctx->cur_actual_crc != ctx->current_chunk.crc)
+    {
+        if(is_critical_chunk(&ctx->current_chunk))
+        {
+            if(ctx->crc_action_critical == SPNG_CRC_USE) return 0;
+        }
+        else
+        {
+            if(ctx->crc_action_ancillary == SPNG_CRC_USE) return 0;
+            if(ctx->crc_action_ancillary == SPNG_CRC_DISCARD) return -SPNG_CRC_DISCARD;
+        }
+
+        return SPNG_ECHUNK_CRC;
+    }
+
+    return 0;
+}
+
+/* Read and validate the current chunk's crc and the next chunk header */
+static inline int read_header(spng_ctx *ctx, int *discard)
+{
+    if(ctx == NULL) return 1;
+
+    int ret;
+    struct spng_chunk chunk = { 0 };
+
+    ret = read_and_check_crc(ctx);
+    if(ret)
+    {
+        if(ret == -SPNG_CRC_DISCARD)
+        {
+            if(discard != NULL) *discard = 1;
+        }
+        else return ret;
+    }
+
+    ret = read_data(ctx, 8);
+    if(ret) return ret;
+
+    chunk.offset = ctx->bytes_read - 8;
+
+    chunk.length = read_u32(ctx->data);
+
+    memcpy(&chunk.type, ctx->data + 4, 4);
+
+    if(chunk.length > png_u32max) return SPNG_ECHUNK_SIZE;
+
+    ctx->cur_chunk_bytes_left = chunk.length;
+
+    ctx->cur_actual_crc = crc32(0, NULL, 0);
+    ctx->cur_actual_crc = crc32(ctx->cur_actual_crc, chunk.type, 4);
+
+    memcpy(&ctx->current_chunk, &chunk, sizeof(struct spng_chunk));
+
+    return 0;
+}
+
+/* Read chunk bytes and update crc */
+static int read_chunk_bytes(spng_ctx *ctx, uint32_t bytes)
+{
+    if(ctx == NULL) return 1;
+    if(!ctx->cur_chunk_bytes_left || !bytes) return 1;
+    if(bytes > ctx->cur_chunk_bytes_left) return 1; /* XXX: more specific error? */
+
+    int ret;
+
+    ret = read_data(ctx, bytes);
+    if(ret) return ret;
+
+    if(is_critical_chunk(&ctx->current_chunk) &&
+       ctx->crc_action_critical == SPNG_CRC_USE) goto skip_crc;
+    else if(ctx->crc_action_ancillary == SPNG_CRC_USE) goto skip_crc;
+
+    ctx->cur_actual_crc = crc32(ctx->cur_actual_crc, ctx->data, bytes);
+
+skip_crc:
+    ctx->cur_chunk_bytes_left -= bytes;
+
+    return ret;
+}
+
+/* read_chunk_bytes() + read_data() with custom output buffer */
+static int read_chunk_bytes2(spng_ctx *ctx, void *out, uint32_t bytes)
+{
+    if(ctx == NULL) return 1;
+    if(!ctx->cur_chunk_bytes_left || !bytes) return 1;
+    if(bytes > ctx->cur_chunk_bytes_left) return 1; /* XXX: more specific error? */
+
+    int ret;
+    uint32_t len = bytes;
+
+    if(ctx->streaming && len > SPNG_READ_SIZE) len = SPNG_READ_SIZE;
+
+    while(bytes)
+    {
+        if(len > bytes) len = bytes;
+
+        ret = ctx->read_fn(ctx, ctx->read_user_ptr, out, len);
+        if(ret) return ret;
+
+        if(!ctx->streaming) memcpy(out, ctx->data, len);
+
+        ctx->bytes_read += len;
+        if(ctx->bytes_read < len) return SPNG_EOVERFLOW;
+
+        if(is_critical_chunk(&ctx->current_chunk) &&
+           ctx->crc_action_critical == SPNG_CRC_USE) goto skip_crc;
+        else if(ctx->crc_action_ancillary == SPNG_CRC_USE) goto skip_crc;
+
+        ctx->cur_actual_crc = crc32(ctx->cur_actual_crc, out, len);
+
+skip_crc:
+        ctx->cur_chunk_bytes_left -= len;
+
+        out = (char*)out + len;
+        bytes -= len;
+        len = SPNG_READ_SIZE;
+    }
+
+    return 0;
+}
+
+static int discard_chunk_bytes(spng_ctx *ctx, uint32_t bytes)
+{
+    if(ctx == NULL) return 1;
+    if(!bytes) return 0;
+
+    int ret;
+
+    if(ctx->streaming) /* Do small, consecutive reads */
+    {
+        while(bytes)
+        {
+            uint32_t len = SPNG_READ_SIZE;
+
+            if(len > bytes) len = bytes;
+
+            ret = read_chunk_bytes(ctx, len);
+            if(ret) return ret;
+
+            bytes -= len;
+        }
+    }
+    else
+    {
+        ret = read_chunk_bytes(ctx, bytes);
+        if(ret) return ret;
+    }
+
+    return 0;
+}
+
+/* Inflate a zlib stream starting with start_buf if non-NULL,
+   continuing from the datastream till an end marker,
+   allocating and writing the inflated stream to *out,
+   leaving "extra" bytes at the end, final buffer length is *len.
+
+   Takes into account the chunk size and cache limits.
+*/
+static int spng__inflate_stream(spng_ctx *ctx, char **out, size_t *len, int extra, const void *start_buf, size_t start_len)
+{
+    int ret = spng__inflate_init(ctx);
+    if(ret) return ret;
+
+    size_t max = ctx->chunk_cache_limit - ctx->chunk_cache_usage;
+
+    if(ctx->max_chunk_size < max) max = ctx->max_chunk_size;
+
+    if(extra > max) return SPNG_EMEM;
+    max -= extra;
+
+    uint32_t read_size;
+    size_t size = 8 * 1024;
+    void *t, *buf = spng__malloc(ctx, size);
+
+    if(buf == NULL) return SPNG_EMEM;
+
+    z_stream *stream = &ctx->zstream;
+
+    if(start_buf != NULL && start_len)
+    {
+        stream->avail_in = start_len;
+        stream->next_in = start_buf;
+    }
+    else
+    {
+        stream->avail_in = 0;
+        stream->next_in = NULL;
+    }
+
+    stream->avail_out = size;
+    stream->next_out = buf;
+
+    while(ret != Z_STREAM_END)
+    {
+        ret = inflate(stream, 0);
+
+        if(ret == Z_OK) continue;
+
+        if(ret == Z_STREAM_END) break;
+
+        if(ret == Z_BUF_ERROR)
+        {
+            if(!stream->avail_out) /* Resize buffer */
+            {
+                /* overflow or reached chunk/cache limit */
+                if( (2 > SIZE_MAX / size) || (size > max / 2) ) goto mem;
+
+                size *= 2;
+
+                t = spng__realloc(ctx, buf, size);
+                if(t == NULL) goto mem;
+
+                buf = t;
+
+                stream->avail_out = size / 2;
+                stream->next_out = (unsigned char*)buf + size / 2;
+            }
+
+            if(!stream->avail_in) /* Read more chunk bytes */
+            {
+                read_size = ctx->cur_chunk_bytes_left;
+                if(ctx->streaming && read_size > SPNG_READ_SIZE) read_size = SPNG_READ_SIZE;
+
+                ret = read_chunk_bytes(ctx, read_size);
+                if(ret)
+                {
+                    spng__free(ctx, buf);
+                    return ret;
+                }
+
+                stream->avail_in = read_size;
+                stream->next_in = ctx->data;
+            }
+        }
+        else
+        {
+            spng__free(ctx, buf);
+            return SPNG_EZLIB;
+        }
+    }
+
+    size = stream->total_out;
+
+    if(!size)
+    {
+        spng__free(ctx, buf);
+        return SPNG_EZLIB;
+    }
+
+    size += extra;
+    if(size < extra) goto mem;
+
+    t = spng__realloc(ctx, buf, size);
+    if(t == NULL) goto mem;
+
+    buf = t;
+
+    increase_cache_usage(ctx, size);
+
+    *out = buf;
+    *len = size;
+
+    return 0;
+
+mem:
+    spng__free(ctx, buf);
+    return SPNG_EMEM;
+}
+
+/* Read at least one byte from the IDAT stream */
+static int read_idat_bytes(spng_ctx *ctx, uint32_t *bytes_read)
+{
+    if(ctx == NULL || bytes_read == NULL) return 1;
+    if(memcmp(ctx->current_chunk.type, type_idat, 4)) return SPNG_EIDAT_TOO_SHORT;
+
+    int ret;
+    uint32_t len;
+
+    while(!ctx->cur_chunk_bytes_left)
+    {
+        ret = read_header(ctx, NULL);
+        if(ret) return ret;
+
+        if(memcmp(ctx->current_chunk.type, type_idat, 4)) return SPNG_EIDAT_TOO_SHORT;
+    }
+
+    if(ctx->streaming)
+    {/* TODO: estimate bytes to read for progressive reads */
+        len = SPNG_READ_SIZE;
+        if(len > ctx->cur_chunk_bytes_left) len = ctx->cur_chunk_bytes_left;
+    }
+    else len = ctx->current_chunk.length;
+
+    ret = read_chunk_bytes(ctx, len);
+
+    *bytes_read = len;
+
+    return ret;
+}
+
+static int read_scanline_bytes(spng_ctx *ctx, unsigned char *dest, size_t len)
+{
+    if(ctx == NULL || dest == NULL) return 1;
+
+    int ret = Z_OK;
+    uint32_t bytes_read;
+
+    z_stream *zstream = &ctx->zstream;
+
+    zstream->avail_out = len;
+    zstream->next_out = dest;
+
+    while(zstream->avail_out != 0)
+    {
+        ret = inflate(&ctx->zstream, 0);
+
+        if(ret == Z_OK) continue;
+
+        if(ret == Z_STREAM_END) /* Reached an end-marker */
+        {
+            if(zstream->avail_out != 0) return SPNG_EIDAT_TOO_SHORT;
+        }
+        else if(ret == Z_BUF_ERROR) /* Read more IDAT bytes */
+        {
+            ret = read_idat_bytes(ctx, &bytes_read);
+            if(ret) return ret;
+
+            zstream->avail_in = bytes_read;
+            zstream->next_in = ctx->data;
+        }
+        else return SPNG_EIDAT_STREAM;
+    }
+
+    return 0;
+}
+
+static uint8_t paeth(uint8_t a, uint8_t b, uint8_t c)
+{
+    int16_t p = (int16_t)a + (int16_t)b - (int16_t)c;
+    int16_t pa = abs(p - (int16_t)a);
+    int16_t pb = abs(p - (int16_t)b);
+    int16_t pc = abs(p - (int16_t)c);
+
+    if(pa <= pb && pa <= pc) return a;
+    else if(pb <= pc) return b;
+
+    return c;
+}
+
+SPNG_TARGET_CLONES("default,avx2")
+static void defilter_up(size_t bytes, unsigned char *restrict row, const unsigned char *prev)
+{
+    size_t i;
+    for(i=0; i < bytes; i++)
+    {
+        row[i] += prev[i];
+    }
+}
+
+/* Defilter *scanline in-place.
+   *prev_scanline and *scanline should point to the first pixel,
+   scanline_width is the width of the scanline including the filter byte.
+*/
+static int defilter_scanline(const unsigned char *prev_scanline,
+                             unsigned char *restrict scanline,
+                             size_t scanline_width,
+                             unsigned bytes_per_pixel,
+                             unsigned filter)
+{
+    if(prev_scanline == NULL || scanline == NULL || !scanline_width) return 1;
+
+    size_t i;
+    scanline_width--;
+
+    if(filter == 0) return 0;
+
+#ifndef SPNG_DISABLE_OPT
+    if(filter == SPNG_FILTER_UP) goto no_opt;
+
+    if(bytes_per_pixel == 4)
+    {
+        if(filter == SPNG_FILTER_SUB)
+            defilter_sub4(scanline_width, scanline);
+        else if(filter == SPNG_FILTER_AVERAGE)
+            defilter_avg4(scanline_width, scanline, prev_scanline);
+        else if(filter == SPNG_FILTER_PAETH)
+            defilter_paeth4(scanline_width, scanline, prev_scanline);
+        else return SPNG_EFILTER;
+
+        return 0;
+    }
+    else if(bytes_per_pixel == 3)
+    {
+        if(filter == SPNG_FILTER_SUB)
+            defilter_sub3(scanline_width, scanline);
+        else if(filter == SPNG_FILTER_AVERAGE)
+            defilter_avg3(scanline_width, scanline, prev_scanline);
+        else if(filter == SPNG_FILTER_PAETH)
+            defilter_paeth3(scanline_width, scanline, prev_scanline);
+        else return SPNG_EFILTER;
+
+        return 0;
+    }
+no_opt:
+#endif
+
+    if(filter == SPNG_FILTER_UP)
+    {
+        defilter_up(scanline_width, scanline, prev_scanline);
+        return 0;
+    }
+
+    for(i=0; i < scanline_width; i++)
+    {
+        uint8_t x, a, b, c;
+
+        if(i >= bytes_per_pixel)
+        {
+            memcpy(&a, scanline + i - bytes_per_pixel, 1);
+            memcpy(&b, prev_scanline + i, 1);
+            memcpy(&c, prev_scanline + i - bytes_per_pixel, 1);
+        }
+        else /* First pixel in row */
+        {
+            a = 0;
+            memcpy(&b, prev_scanline + i, 1);
+            c = 0;
+        }
+
+        memcpy(&x, scanline + i, 1);
+
+        switch(filter)
+        {
+            case SPNG_FILTER_SUB:
+            {
+                x = x + a;
+                break;
+            }
+            case SPNG_FILTER_AVERAGE:
+            {
+                uint16_t avg = (a + b) / 2;
+                x = x + avg;
+                break;
+            }
+            case SPNG_FILTER_PAETH:
+            {
+                x = x + paeth(a,b,c);
+                break;
+            }
+        }
+
+        memcpy(scanline + i, &x, 1);
+    }
+
+    return 0;
+}
+
+/* Scale "sbits" significant bits in "sample" from "bit_depth" to "target"
+
+   "bit_depth" must be a valid PNG depth
+   "sbits" must be less than or equal to "bit_depth"
+   "target" must be between 1 and 16
+*/
+static uint16_t sample_to_target(uint16_t sample, unsigned bit_depth, unsigned sbits, unsigned target)
+{
+    if(bit_depth == sbits)
+    {
+        if(target == sbits) return sample; /* No scaling */
+    }/* bit_depth > sbits */
+    else sample = sample >> (bit_depth - sbits); /* Shift significant bits to bottom */
+
+    /* Downscale */
+    if(target < sbits) return sample >> (sbits - target);
+
+    /* Upscale using left bit replication */
+    int8_t shift_amount = target - sbits;
+    uint16_t sample_bits = sample;
+    sample = 0;
+
+    while(shift_amount >= 0)
+    {
+        sample = sample | (sample_bits << shift_amount);
+        shift_amount -= sbits;
+    }
+
+    int8_t partial = shift_amount + (int8_t)sbits;
+
+    if(partial != 0) sample = sample | (sample_bits >> abs(shift_amount));
+
+    return sample;
+}
+
+static inline void gamma_correct_row(unsigned char *row, uint32_t pixels, int fmt, const uint16_t *gamma_lut)
+{
+    uint32_t i;
+
+    if(fmt == SPNG_FMT_RGBA8)
+    {
+        unsigned char *px;
+        for(i=0; i < pixels; i++)
+        {
+            px = row + i * 4;
+
+            px[0] = gamma_lut[px[0]];
+            px[1] = gamma_lut[px[1]];
+            px[2] = gamma_lut[px[2]];
+        }
+    }
+    else if(fmt == SPNG_FMT_RGBA16)
+    {
+        for(i=0; i < pixels; i++)
+        {
+            uint16_t px[4];
+            memcpy(px, row + i * 8, 8);
+
+            px[0] = gamma_lut[px[0]];
+            px[1] = gamma_lut[px[1]];
+            px[2] = gamma_lut[px[2]];
+
+            memcpy(row + i * 8, px, 8);
+        }
+    }
+    else if(fmt == SPNG_FMT_RGB8)
+    {
+        unsigned char *px;
+        for(i=0; i < pixels; i++)
+        {
+            px = row + i * 3;
+
+            px[0] = gamma_lut[px[0]];
+            px[1] = gamma_lut[px[1]];
+            px[2] = gamma_lut[px[2]];
+        }
+    }
+}
+
+/* Apply transparency to output row */
+static inline void trns_row(unsigned char *restrict row,
+                            const unsigned char *scanline,
+                            const unsigned char *trns,
+                            unsigned scanline_stride,
+                            struct spng_ihdr *ihdr,
+                            uint32_t pixels,
+                            int fmt)
+{
+    uint32_t i;
+    unsigned row_stride;
+    unsigned depth = ihdr->bit_depth;
+
+    if(fmt == SPNG_FMT_RGBA8)
+    {
+        if(ihdr->color_type == SPNG_COLOR_TYPE_GRAYSCALE) return; /* already applied in the decoding loop */
+
+        row_stride = 4;
+        for(i=0; i < pixels; i++, scanline+=scanline_stride, row+=row_stride)
+        {
+            if(!memcmp(scanline, trns, scanline_stride)) row[3] = 0;
+        }
+    }
+    else if(fmt == SPNG_FMT_RGBA16)
+    {
+        if(ihdr->color_type == SPNG_COLOR_TYPE_GRAYSCALE) return; /* already applied in the decoding loop */
+
+        row_stride = 8;
+        for(i=0; i < pixels; i++, scanline+=scanline_stride, row+=row_stride)
+        {
+            if(!memcmp(scanline, trns, scanline_stride)) memset(row + 6, 0, 2);
+        }
+    }
+    else if(fmt == SPNG_FMT_GA8)
+    {
+        row_stride = 2;
+
+        if(depth == 16)
+        {
+            for(i=0; i < pixels; i++, scanline+=scanline_stride, row+=row_stride)
+            {
+                if(!memcmp(scanline, trns, scanline_stride)) memset(row + 1, 0, 1);
+            }
+        }
+        else /* depth <= 8 */
+        {
+            struct spng__iter iter = spng__iter_init(depth, scanline);
+
+            for(i=0; i < pixels; i++, row+=row_stride)
+            {
+                if(trns[0] == get_sample(&iter)) row[1] = 0;
+            }
+        }
+    }
+    else if(fmt == SPNG_FMT_GA16)
+    {
+        row_stride = 4;
+
+        if(depth == 16)
+        {
+            for(i=0; i< pixels; i++, scanline+=scanline_stride, row+=row_stride)
+            {
+                if(!memcmp(scanline, trns, 2)) memset(row + 2, 0, 2);
+            }
+        }
+        else
+        {
+            struct spng__iter iter = spng__iter_init(depth, scanline);
+
+            for(i=0; i< pixels; i++, row+=row_stride)
+            {
+                if(trns[0] == get_sample(&iter)) memset(row + 2, 0, 2);
+            }
+        }
+    }
+    else return;
+}
+
+static inline void scale_row(unsigned char *row, uint32_t pixels, int fmt, unsigned depth, struct spng_sbit *sbit)
+{
+    uint32_t i;
+
+    if(fmt == SPNG_FMT_RGBA8)
+    {
+        unsigned char px[4];
+        for(i=0; i < pixels; i++)
+        {
+            memcpy(px, row + i * 4, 4);
+
+            px[0] = sample_to_target(px[0], depth, sbit->red_bits, 8);
+            px[1] = sample_to_target(px[1], depth, sbit->green_bits, 8);
+            px[2] = sample_to_target(px[2], depth, sbit->blue_bits, 8);
+            px[3] = sample_to_target(px[3], depth, sbit->alpha_bits, 8);
+
+            memcpy(row + i * 4, px, 4);
+        }
+    }
+    else if(fmt == SPNG_FMT_RGBA16)
+    {
+        uint16_t px[4];
+        for(i=0; i < pixels; i++)
+        {
+            memcpy(px, row + i * 8, 8);
+
+            px[0] = sample_to_target(px[0], depth, sbit->red_bits, 16);
+            px[1] = sample_to_target(px[1], depth, sbit->green_bits, 16);
+            px[2] = sample_to_target(px[2], depth, sbit->blue_bits, 16);
+            px[3] = sample_to_target(px[3], depth, sbit->alpha_bits, 16);
+
+            memcpy(row + i * 8, px, 8);
+        }
+    }
+    else if(fmt == SPNG_FMT_RGB8)
+    {
+        unsigned char px[4];
+        for(i=0; i < pixels; i++)
+        {
+            memcpy(px, row + i * 3, 3);
+
+            px[0] = sample_to_target(px[0], depth, sbit->red_bits, 8);
+            px[1] = sample_to_target(px[1], depth, sbit->green_bits, 8);
+            px[2] = sample_to_target(px[2], depth, sbit->blue_bits, 8);
+
+            memcpy(row + i * 3, px, 3);
+        }
+    }
+    else if(fmt == SPNG_FMT_G8)
+    {
+        for(i=0; i < pixels; i++)
+        {
+            row[i] = sample_to_target(row[i], depth, sbit->grayscale_bits, 8);
+        }
+    }
+    else if(fmt == SPNG_FMT_GA8)
+    {
+        for(i=0; i < pixels; i++)
+        {
+            row[i*2] = sample_to_target(row[i*2], depth, sbit->grayscale_bits, 8);
+        }
+    }
+}
+
+/* Expand to *row using 8-bit palette indices from *scanline */
+void expand_row(unsigned char *row,
+                const unsigned char *restrict scanline,
+                struct spng_plte_entry16 *plte,
+                uint32_t width,
+                int fmt)
+{
+    uint32_t i;
+    unsigned char *px;
+    unsigned char entry;
+    if(fmt == SPNG_FMT_RGBA8)
+    {
+        for(i=0; i < width; i++)
+        {
+            px = row + i * 4;
+            entry = scanline[i];
+            px[0] = plte[entry].red;
+            px[1] = plte[entry].green;
+            px[2] = plte[entry].blue;
+            px[3] = plte[entry].alpha;
+        }
+    }
+    else if(fmt == SPNG_FMT_RGB8)
+    {
+        for(i=0; i < width; i++)
+        {
+            px = row + i * 3;
+            entry = scanline[i];
+            px[0] = plte[entry].red;
+            px[1] = plte[entry].green;
+            px[2] = plte[entry].blue;
+        }
+    }
+}
+
+/* Unpack 1/2/4/8-bit samples to G8/GA8/GA16 or G16 -> GA16 */
+static void unpack_scanline(unsigned char *restrict out,
+                            const unsigned char *scanline,
+                            uint32_t width,
+                            unsigned bit_depth,
+                            int fmt)
+{
+    struct spng__iter iter = spng__iter_init(bit_depth, scanline);
+    uint32_t i;
+    uint16_t sample, alpha = 65535;
+
+
+    if(fmt == SPNG_FMT_GA8) goto ga8;
+    else if(fmt == SPNG_FMT_GA16) goto ga16;
+
+    /* 1/2/4-bit -> 8-bit */
+    for(i=0; i < width; i++) out[i] = get_sample(&iter);
+
+    return;
+
+ga8:
+    /* 1/2/4/8-bit -> GA8 */
+    for(i=0; i < width; i++)
+    {
+        out[i*2] = get_sample(&iter);
+        out[i*2 + 1] = 255;
+    }
+
+    return;
+
+ga16:
+
+    /* 16 -> GA16 */
+    if(bit_depth == 16)
+    {
+        for(i=0; i < width; i++)
+        {
+            memcpy(out + i * 4, scanline + i * 2, 2);
+            memcpy(out + i * 4 + 2, &alpha, 2);
+        }
+        return;
+    }
+
+     /* 1/2/4/8-bit -> GA16 */
+    for(i=0; i < width; i++)
+    {
+        sample = get_sample(&iter);
+        memcpy(out + i * 4, &sample, 2);
+        memcpy(out + i * 4 + 2, &alpha, 2);
+    }
+}
+
+static int check_ihdr(const struct spng_ihdr *ihdr, uint32_t max_width, uint32_t max_height)
+{
+    if(ihdr->width > png_u32max || ihdr->width > max_width || !ihdr->width) return SPNG_EWIDTH;
+    if(ihdr->height > png_u32max || ihdr->height > max_height || !ihdr->height) return SPNG_EHEIGHT;
+
+    switch(ihdr->color_type)
+    {
+        case SPNG_COLOR_TYPE_GRAYSCALE:
+        {
+            if( !(ihdr->bit_depth == 1 || ihdr->bit_depth == 2 ||
+                  ihdr->bit_depth == 4 || ihdr->bit_depth == 8 ||
+                  ihdr->bit_depth == 16) )
+                  return SPNG_EBIT_DEPTH;
+
+            break;
+        }
+        case SPNG_COLOR_TYPE_TRUECOLOR:
+        case SPNG_COLOR_TYPE_GRAYSCALE_ALPHA:
+        case SPNG_COLOR_TYPE_TRUECOLOR_ALPHA:
+        {
+            if( !(ihdr->bit_depth == 8 || ihdr->bit_depth == 16) )
+                return SPNG_EBIT_DEPTH;
+
+            break;
+        }
+        case SPNG_COLOR_TYPE_INDEXED:
+        {
+            if( !(ihdr->bit_depth == 1 || ihdr->bit_depth == 2 ||
+                  ihdr->bit_depth == 4 || ihdr->bit_depth == 8) )
+                return SPNG_EBIT_DEPTH;
+
+            break;
+        }
+        default: return SPNG_ECOLOR_TYPE;
+    }
+
+    if(ihdr->compression_method) return SPNG_ECOMPRESSION_METHOD;
+    if(ihdr->filter_method) return SPNG_EFILTER_METHOD;
+
+    if(ihdr->interlace_method > 1) return SPNG_EINTERLACE_METHOD;
+
+    return 0;
+}
+
+static int check_plte(const struct spng_plte *plte, const struct spng_ihdr *ihdr)
+{
+    if(plte == NULL || ihdr == NULL) return 1;
+
+    if(plte->n_entries == 0) return 1;
+    if(plte->n_entries > 256) return 1;
+
+    if(ihdr->color_type == SPNG_COLOR_TYPE_INDEXED)
+    {
+        if(plte->n_entries > (1U << ihdr->bit_depth)) return 1;
+    }
+
+    return 0;
+}
+
+static int check_sbit(const struct spng_sbit *sbit, const struct spng_ihdr *ihdr)
+{
+    if(sbit == NULL || ihdr == NULL) return 1;
+
+    if(ihdr->color_type == 0)
+    {
+        if(sbit->grayscale_bits == 0) return SPNG_ESBIT;
+        if(sbit->grayscale_bits > ihdr->bit_depth) return SPNG_ESBIT;
+    }
+    else if(ihdr->color_type == 2 || ihdr->color_type == 3)
+    {
+        if(sbit->red_bits == 0) return SPNG_ESBIT;
+        if(sbit->green_bits == 0) return SPNG_ESBIT;
+        if(sbit->blue_bits == 0) return SPNG_ESBIT;
+
+        uint8_t bit_depth;
+        if(ihdr->color_type == 3) bit_depth = 8;
+        else bit_depth = ihdr->bit_depth;
+
+        if(sbit->red_bits > bit_depth) return SPNG_ESBIT;
+        if(sbit->green_bits > bit_depth) return SPNG_ESBIT;
+        if(sbit->blue_bits > bit_depth) return SPNG_ESBIT;
+    }
+    else if(ihdr->color_type == 4)
+    {
+        if(sbit->grayscale_bits == 0) return SPNG_ESBIT;
+        if(sbit->alpha_bits == 0) return SPNG_ESBIT;
+
+        if(sbit->grayscale_bits > ihdr->bit_depth) return SPNG_ESBIT;
+        if(sbit->alpha_bits > ihdr->bit_depth) return SPNG_ESBIT;
+    }
+    else if(ihdr->color_type == 6)
+    {
+        if(sbit->red_bits == 0) return SPNG_ESBIT;
+        if(sbit->green_bits == 0) return SPNG_ESBIT;
+        if(sbit->blue_bits == 0) return SPNG_ESBIT;
+        if(sbit->alpha_bits == 0) return SPNG_ESBIT;
+
+        if(sbit->red_bits > ihdr->bit_depth) return SPNG_ESBIT;
+        if(sbit->green_bits > ihdr->bit_depth) return SPNG_ESBIT;
+        if(sbit->blue_bits > ihdr->bit_depth) return SPNG_ESBIT;
+        if(sbit->alpha_bits > ihdr->bit_depth) return SPNG_ESBIT;
+    }
+
+    return 0;
+}
+
+static int check_chrm_int(const struct spng_chrm_int *chrm_int)
+{
+    if(chrm_int == NULL) return 1;
+
+    if(chrm_int->white_point_x > png_u32max ||
+       chrm_int->white_point_y > png_u32max ||
+       chrm_int->red_x > png_u32max ||
+       chrm_int->red_y > png_u32max ||
+       chrm_int->green_x  > png_u32max ||
+       chrm_int->green_y  > png_u32max ||
+       chrm_int->blue_x > png_u32max ||
+       chrm_int->blue_y > png_u32max) return SPNG_ECHRM;
+
+    return 0;
+}
+
+static int check_phys(const struct spng_phys *phys)
+{
+    if(phys == NULL) return 1;
+
+    if(phys->unit_specifier > 1) return SPNG_EPHYS;
+
+    if(phys->ppu_x > png_u32max) return SPNG_EPHYS;
+    if(phys->ppu_y > png_u32max) return SPNG_EPHYS;
+
+    return 0;
+}
+
+static int check_time(const struct spng_time *time)
+{
+    if(time == NULL) return 1;
+
+    if(time->month == 0 || time->month > 12) return 1;
+    if(time->day == 0 || time->day > 31) return 1;
+    if(time->hour > 23) return 1;
+    if(time->minute > 59) return 1;
+    if(time->second > 60) return 1;
+
+    return 0;
+}
+
+static int check_offs(const struct spng_offs *offs)
+{
+    if(offs == NULL) return 1;
+
+    if(offs->unit_specifier > 1) return 1;
+
+    return 0;
+}
+
+static int check_exif(const struct spng_exif *exif)
+{
+    if(exif == NULL) return 1;
+    if(exif->data == NULL) return 1;
+
+    if(exif->length < 4) return SPNG_ECHUNK_SIZE;
+    if(exif->length > png_u32max) return SPNG_ECHUNK_SIZE;
+
+    const uint8_t exif_le[4] = { 73, 73, 42, 0 };
+    const uint8_t exif_be[4] = { 77, 77, 0, 42 };
+
+    if(memcmp(exif->data, exif_le, 4) && memcmp(exif->data, exif_be, 4)) return 1;
+
+    return 0;
+}
+
+/* Validate PNG keyword *str, *str must be 80 bytes */
+static int check_png_keyword(const char str[80])
+{
+    if(str == NULL) return 1;
+    char *end = memchr(str, '\0', 80);
+
+    if(end == NULL) return 1; /* Unterminated string */
+    if(end == str) return 1; /* Zero-length string */
+    if(str[0] == ' ') return 1; /* Leading space */
+    if(end[-1] == ' ') return 1; /* Trailing space */
+    if(strstr(str, "  ") != NULL) return 1; /* Consecutive spaces */
+
+    uint8_t c;
+    while(str != end)
+    {
+        memcpy(&c, str, 1);
+
+        if( (c >= 32 && c <= 126) || (c >= 161) ) str++;
+        else return 1; /* Invalid character */
+    }
+
+    return 0;
+}
+
+/* Validate PNG text *str up to 'len' bytes */
+static int check_png_text(const char *str, size_t len)
+{/* XXX: are consecutive newlines permitted? */
+    if(str == NULL || len == 0) return 1;
+
+    uint8_t c;
+    size_t i = 0;
+    while(i < len)
+    {
+        memcpy(&c, str + i, 1);
+
+        if( (c >= 32 && c <= 126) || (c >= 161) || c == 10) i++;
+        else return 1; /* Invalid character */
+    }
+
+    return 0;
+}
+
+/* Returns non-zero for standard chunks which are stored without allocating memory */
+static int is_small_chunk(uint8_t type[4])
+{
+    if(!memcmp(type, type_plte, 4)) return 1;
+    else if(!memcmp(type, type_chrm, 4)) return 1;
+    else if(!memcmp(type, type_gama, 4)) return 1;
+    else if(!memcmp(type, type_sbit, 4)) return 1;
+    else if(!memcmp(type, type_srgb, 4)) return 1;
+    else if(!memcmp(type, type_bkgd, 4)) return 1;
+    else if(!memcmp(type, type_trns, 4)) return 1;
+    else if(!memcmp(type, type_hist, 4)) return 1;
+    else if(!memcmp(type, type_phys, 4)) return 1;
+    else if(!memcmp(type, type_time, 4)) return 1;
+    else if(!memcmp(type, type_offs, 4)) return 1;
+    else return 0;
+}
+
+static int read_ihdr(spng_ctx *ctx)
+{
+    int ret;
+    struct spng_chunk chunk;
+    const unsigned char *data;
+
+    chunk.offset = 8;
+    chunk.length = 13;
+    size_t sizeof_sig_ihdr = 29;
+
+    ret = read_data(ctx, sizeof_sig_ihdr);
+    if(ret) return ret;
+
+    data = ctx->data;
+
+    if(memcmp(data, png_signature, sizeof(png_signature))) return SPNG_ESIGNATURE;
+
+    chunk.length = read_u32(data + 8);
+    memcpy(&chunk.type, data + 12, 4);
+
+    if(chunk.length != 13) return SPNG_EIHDR_SIZE;
+    if(memcmp(chunk.type, type_ihdr, 4)) return SPNG_ENOIHDR;
+
+    ctx->cur_actual_crc = crc32(0, NULL, 0);
+    ctx->cur_actual_crc = crc32(ctx->cur_actual_crc, data + 12, 17);
+
+    ctx->ihdr.width = read_u32(data + 16);
+    ctx->ihdr.height = read_u32(data + 20);
+    memcpy(&ctx->ihdr.bit_depth, data + 24, 1);
+    memcpy(&ctx->ihdr.color_type, data + 25, 1);
+    memcpy(&ctx->ihdr.compression_method, data + 26, 1);
+    memcpy(&ctx->ihdr.filter_method, data + 27, 1);
+    memcpy(&ctx->ihdr.interlace_method, data + 28, 1);
+
+    if(!ctx->max_width) ctx->max_width = png_u32max;
+    if(!ctx->max_height) ctx->max_height = png_u32max;
+
+    ret = check_ihdr(&ctx->ihdr, ctx->max_width, ctx->max_height);
+    if(ret) return ret;
+
+    ctx->file.ihdr = 1;
+    ctx->stored.ihdr = 1;
+
+    ctx->channels = 1; /* grayscale or indexed color */
+
+    if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_TRUECOLOR) ctx->channels = 3;
+    else if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_GRAYSCALE_ALPHA) ctx->channels = 2;
+    else if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_TRUECOLOR_ALPHA) ctx->channels = 4;
+
+    if(ctx->ihdr.bit_depth < 8) ctx->bytes_per_pixel = 1;
+    else ctx->bytes_per_pixel = ctx->channels * (ctx->ihdr.bit_depth / 8);
+
+    ret = calculate_subimages(ctx);
+    if(ret) return ret;
+
+    return 0;
+}
+
+static int read_non_idat_chunks(spng_ctx *ctx)
+{
+    int ret, discard = 0;
+    int prev_was_idat = ctx->state == SPNG_STATE_AFTER_IDAT ? 1 : 0;
+    struct spng_chunk chunk;
+    const unsigned char *data;
+
+    struct spng_chunk_bitfield stored;
+    memcpy(&stored, &ctx->stored, sizeof(struct spng_chunk_bitfield));
+
+    while( !(ret = read_header(ctx, &discard)))
+    {
+        if(discard)
+        {
+            memcpy(&ctx->stored, &stored, sizeof(struct spng_chunk_bitfield));
+        }
+
+        memcpy(&stored, &ctx->stored, sizeof(struct spng_chunk_bitfield));
+
+        memcpy(&chunk, &ctx->current_chunk, sizeof(struct spng_chunk));
+
+        if(!memcmp(chunk.type, type_idat, 4))
+        {
+            if(ctx->state < SPNG_STATE_FIRST_IDAT)
+            {
+                if(ctx->ihdr.color_type == 3 && !ctx->stored.plte) return SPNG_ENOPLTE;
+
+                memcpy(&ctx->first_idat, &chunk, sizeof(struct spng_chunk));
+                return 0;
+            }
+
+            if(prev_was_idat)
+            {
+                /* Ignore extra IDAT's */
+                ret = discard_chunk_bytes(ctx, chunk.length);
+                if(ret) return ret;
+
+                continue;
+            }
+            else return SPNG_ECHUNK_POS; /* IDAT chunk not at the end of the IDAT sequence */
+        }
+
+        prev_was_idat = 0;
+
+        if(is_small_chunk(chunk.type))
+        {/* The largest of these chunks is PLTE with 256 entries */
+            ret = read_chunk_bytes(ctx, chunk.length > 768 ? 768 : chunk.length);
+            if(ret) return ret;
+        }
+
+        data = ctx->data;
+
+        if(is_critical_chunk(&chunk))
+        {
+            if(!memcmp(chunk.type, type_plte, 4))
+            {
+                if(ctx->file.trns || ctx->file.hist || ctx->file.bkgd) return SPNG_ECHUNK_POS;
+                if(chunk.length % 3 != 0) return SPNG_ECHUNK_SIZE;
+
+                ctx->plte.n_entries = chunk.length / 3;
+
+                if(check_plte(&ctx->plte, &ctx->ihdr)) return SPNG_ECHUNK_SIZE; /* XXX: EPLTE? */
+
+                size_t i;
+                for(i=0; i < ctx->plte.n_entries; i++)
+                {
+                    memcpy(&ctx->plte.entries[i].red,   data + i * 3, 1);
+                    memcpy(&ctx->plte.entries[i].green, data + i * 3 + 1, 1);
+                    memcpy(&ctx->plte.entries[i].blue,  data + i * 3 + 2, 1);
+                }
+
+                ctx->file.plte = 1;
+                ctx->stored.plte = 1;
+            }
+            else if(!memcmp(chunk.type, type_iend, 4))
+            {
+                if(ctx->state == SPNG_STATE_AFTER_IDAT)
+                {
+                    if(chunk.length) return SPNG_ECHUNK_SIZE;
+
+                    ret = read_and_check_crc(ctx);
+                    if(ret == -SPNG_CRC_DISCARD) ret = 0;
+
+                    return ret;
+                }
+                else return SPNG_ECHUNK_POS;
+            }
+            else if(!memcmp(chunk.type, type_ihdr, 4)) return SPNG_ECHUNK_POS;
+            else return SPNG_ECHUNK_UNKNOWN_CRITICAL;
+        }
+        else if(!memcmp(chunk.type, type_chrm, 4)) /* Ancillary chunks */
+        {
+            if(ctx->file.plte) return SPNG_ECHUNK_POS;
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.chrm) return SPNG_EDUP_CHRM;
+
+            if(chunk.length != 32) return SPNG_ECHUNK_SIZE;
+
+            ctx->chrm_int.white_point_x = read_u32(data);
+            ctx->chrm_int.white_point_y = read_u32(data + 4);
+            ctx->chrm_int.red_x = read_u32(data + 8);
+            ctx->chrm_int.red_y = read_u32(data + 12);
+            ctx->chrm_int.green_x = read_u32(data + 16);
+            ctx->chrm_int.green_y = read_u32(data + 20);
+            ctx->chrm_int.blue_x = read_u32(data + 24);
+            ctx->chrm_int.blue_y = read_u32(data + 28);
+
+            if(check_chrm_int(&ctx->chrm_int)) return SPNG_ECHRM;
+
+            ctx->file.chrm = 1;
+            ctx->stored.chrm = 1;
+        }
+        else if(!memcmp(chunk.type, type_gama, 4))
+        {
+            if(ctx->file.plte) return SPNG_ECHUNK_POS;
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.gama) return SPNG_EDUP_GAMA;
+
+            if(chunk.length != 4) return SPNG_ECHUNK_SIZE;
+
+            ctx->gama = read_u32(data);
+
+            if(!ctx->gama) return SPNG_EGAMA;
+            if(ctx->gama > png_u32max) return SPNG_EGAMA;
+
+            ctx->file.gama = 1;
+            ctx->stored.gama = 1;
+        }
+        else if(!memcmp(chunk.type, type_sbit, 4))
+        {
+            if(ctx->file.plte) return SPNG_ECHUNK_POS;
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.sbit) return SPNG_EDUP_SBIT;
+
+            if(ctx->ihdr.color_type == 0)
+            {
+                if(chunk.length != 1) return SPNG_ECHUNK_SIZE;
+
+                memcpy(&ctx->sbit.grayscale_bits, data, 1);
+            }
+            else if(ctx->ihdr.color_type == 2 || ctx->ihdr.color_type == 3)
+            {
+                if(chunk.length != 3) return SPNG_ECHUNK_SIZE;
+
+                memcpy(&ctx->sbit.red_bits, data, 1);
+                memcpy(&ctx->sbit.green_bits, data + 1 , 1);
+                memcpy(&ctx->sbit.blue_bits, data + 2, 1);
+            }
+            else if(ctx->ihdr.color_type == 4)
+            {
+                if(chunk.length != 2) return SPNG_ECHUNK_SIZE;
+
+                memcpy(&ctx->sbit.grayscale_bits, data, 1);
+                memcpy(&ctx->sbit.alpha_bits, data + 1, 1);
+            }
+            else if(ctx->ihdr.color_type == 6)
+            {
+                if(chunk.length != 4) return SPNG_ECHUNK_SIZE;
+
+                memcpy(&ctx->sbit.red_bits, data, 1);
+                memcpy(&ctx->sbit.green_bits, data + 1, 1);
+                memcpy(&ctx->sbit.blue_bits, data + 2, 1);
+                memcpy(&ctx->sbit.alpha_bits, data + 3, 1);
+            }
+
+            if(check_sbit(&ctx->sbit, &ctx->ihdr)) return SPNG_ESBIT;
+
+            ctx->file.sbit = 1;
+            ctx->stored.sbit = 1;
+        }
+        else if(!memcmp(chunk.type, type_srgb, 4))
+        {
+            if(ctx->file.plte) return SPNG_ECHUNK_POS;
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.srgb) return SPNG_EDUP_SRGB;
+
+            if(chunk.length != 1) return SPNG_ECHUNK_SIZE;
+
+            memcpy(&ctx->srgb_rendering_intent, data, 1);
+
+            if(ctx->srgb_rendering_intent > 3) return SPNG_ESRGB;
+
+            ctx->file.srgb = 1;
+            ctx->stored.srgb = 1;
+        }
+        else if(!memcmp(chunk.type, type_bkgd, 4))
+        {
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.bkgd) return SPNG_EDUP_BKGD;
+
+            uint16_t mask = ~0;
+            if(ctx->ihdr.bit_depth < 16) mask = (1 << ctx->ihdr.bit_depth) - 1;
+
+            if(ctx->ihdr.color_type == 0 || ctx->ihdr.color_type == 4)
+            {
+                if(chunk.length != 2) return SPNG_ECHUNK_SIZE;
+
+                ctx->bkgd.gray = read_u16(data) & mask;
+            }
+            else if(ctx->ihdr.color_type == 2 || ctx->ihdr.color_type == 6)
+            {
+                if(chunk.length != 6) return SPNG_ECHUNK_SIZE;
+
+                ctx->bkgd.red = read_u16(data) & mask;
+                ctx->bkgd.green = read_u16(data + 2) & mask;
+                ctx->bkgd.blue = read_u16(data + 4) & mask;
+            }
+            else if(ctx->ihdr.color_type == 3)
+            {
+                if(chunk.length != 1) return SPNG_ECHUNK_SIZE;
+                if(!ctx->file.plte) return SPNG_EBKGD_NO_PLTE;
+
+                ctx->bkgd.plte_index = data[0];
+                if(ctx->bkgd.plte_index >= ctx->plte.n_entries) return SPNG_EBKGD_PLTE_IDX;
+            }
+
+            ctx->file.bkgd = 1;
+            ctx->stored.bkgd = 1;
+        }
+        else if(!memcmp(chunk.type, type_trns, 4))
+        {
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.trns) return SPNG_EDUP_TRNS;
+            if(!chunk.length) return SPNG_ECHUNK_SIZE;
+
+            uint16_t mask = ~0;
+            if(ctx->ihdr.bit_depth < 16) mask = (1 << ctx->ihdr.bit_depth) - 1;
+
+            if(ctx->ihdr.color_type == 0)
+            {
+                if(chunk.length != 2) return SPNG_ECHUNK_SIZE;
+
+                ctx->trns.gray = read_u16(data) & mask;
+            }
+            else if(ctx->ihdr.color_type == 2)
+            {
+                if(chunk.length != 6) return SPNG_ECHUNK_SIZE;
+
+                ctx->trns.red = read_u16(data) & mask;
+                ctx->trns.green = read_u16(data + 2) & mask;
+                ctx->trns.blue = read_u16(data + 4) & mask;
+            }
+            else if(ctx->ihdr.color_type == 3)
+            {
+                if(chunk.length > ctx->plte.n_entries) return SPNG_ECHUNK_SIZE;
+                if(!ctx->file.plte) return SPNG_ETRNS_NO_PLTE;
+
+                size_t k;
+                for(k=0; k < chunk.length; k++)
+                {
+                    memcpy(&ctx->trns.type3_alpha[k], data + k, 1);
+                }
+                ctx->trns.n_type3_entries = chunk.length;
+            }
+            else return SPNG_ETRNS_COLOR_TYPE;
+
+            ctx->file.trns = 1;
+            ctx->stored.trns = 1;
+        }
+        else if(!memcmp(chunk.type, type_hist, 4))
+        {
+            if(!ctx->file.plte) return SPNG_EHIST_NO_PLTE;
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.hist) return SPNG_EDUP_HIST;
+
+            if( (chunk.length / 2) != (ctx->plte.n_entries) ) return SPNG_ECHUNK_SIZE;
+
+            size_t k;
+            for(k=0; k < (chunk.length / 2); k++)
+            {
+                ctx->hist.frequency[k] = read_u16(data + k*2);
+            }
+
+            ctx->file.hist = 1;
+            ctx->stored.hist = 1;
+        }
+        else if(!memcmp(chunk.type, type_phys, 4))
+        {
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.phys) return SPNG_EDUP_PHYS;
+
+            if(chunk.length != 9) return SPNG_ECHUNK_SIZE;
+
+            ctx->phys.ppu_x = read_u32(data);
+            ctx->phys.ppu_y = read_u32(data + 4);
+            memcpy(&ctx->phys.unit_specifier, data + 8, 1);
+
+            if(check_phys(&ctx->phys)) return SPNG_EPHYS;
+
+            ctx->file.phys = 1;
+            ctx->stored.phys = 1;
+        }
+        else if(!memcmp(chunk.type, type_time, 4))
+        {
+            if(ctx->file.time) return SPNG_EDUP_TIME;
+
+            if(chunk.length != 7) return SPNG_ECHUNK_SIZE;
+
+            struct spng_time time;
+
+            time.year = read_u16(data);
+            memcpy(&time.month, data + 2, 1);
+            memcpy(&time.day, data + 3, 1);
+            memcpy(&time.hour, data + 4, 1);
+            memcpy(&time.minute, data + 5, 1);
+            memcpy(&time.second, data + 6, 1);
+
+            if(check_time(&time)) return SPNG_ETIME;
+
+            ctx->file.time = 1;
+
+            if(!ctx->user.time) memcpy(&ctx->time, &time, sizeof(struct spng_time));
+
+            ctx->stored.time = 1;
+        }
+        else if(!memcmp(chunk.type, type_offs, 4))
+        {
+            if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+            if(ctx->file.offs) return SPNG_EDUP_OFFS;
+
+            if(chunk.length != 9) return SPNG_ECHUNK_SIZE;
+
+            ctx->offs.x = read_s32(data);
+            ctx->offs.y = read_s32(data + 4);
+            memcpy(&ctx->offs.unit_specifier, data + 8, 1);
+
+            if(check_offs(&ctx->offs)) return SPNG_EOFFS;
+
+            ctx->file.offs = 1;
+            ctx->stored.offs = 1;
+        }
+        else /* Arbitrary-length chunk */
+        {
+
+            if(!memcmp(chunk.type, type_exif, 4))
+            {
+                if(ctx->file.exif) return SPNG_EDUP_EXIF;
+
+                ctx->file.exif = 1;
+
+                if(ctx->user.exif) goto discard;
+
+                if(increase_cache_usage(ctx, chunk.length)) return SPNG_EMEM;
+
+                struct spng_exif exif;
+
+                exif.length = chunk.length;
+
+                exif.data = spng__malloc(ctx, chunk.length);
+                if(exif.data == NULL) return SPNG_EMEM;
+
+                ret = read_chunk_bytes2(ctx, exif.data, chunk.length);
+                if(ret)
+                {
+                    spng__free(ctx, exif.data);
+                    return ret;
+                }
+
+                if(check_exif(&exif))
+                {
+                    spng__free(ctx, exif.data);
+                    return SPNG_EEXIF;
+                }
+
+                memcpy(&ctx->exif, &exif, sizeof(struct spng_exif));
+
+                ctx->stored.exif = 1;
+            }
+            else if(!memcmp(chunk.type, type_iccp, 4))
+            {/* TODO: add test file with color profile */
+                if(ctx->file.plte) return SPNG_ECHUNK_POS;
+                if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+                if(ctx->file.iccp) return SPNG_EDUP_ICCP;
+                if(!chunk.length) return SPNG_ECHUNK_SIZE;
+
+                ctx->file.iccp = 1;
+
+                uint32_t peek_bytes =  81 > chunk.length ? chunk.length : 81;
+
+                ret = read_chunk_bytes(ctx, peek_bytes);
+                if(ret) return ret;
+
+                unsigned char *keyword_nul = memchr(ctx->data, '\0', peek_bytes);
+                if(keyword_nul == NULL) return SPNG_EICCP_NAME;
+
+                uint32_t keyword_len = keyword_nul - ctx->data;
+
+                if(keyword_len > 79) return SPNG_EICCP_NAME;
+
+                memcpy(ctx->iccp.profile_name, ctx->data, keyword_len);
+
+                if(check_png_keyword(ctx->iccp.profile_name)) return SPNG_EICCP_NAME;
+
+                if(chunk.length < (keyword_len + 2)) return SPNG_ECHUNK_SIZE;
+
+                if(ctx->data[keyword_len + 1] != 0) return SPNG_EICCP_COMPRESSION_METHOD;
+
+                ret = spng__inflate_stream(ctx, &ctx->iccp.profile, &ctx->iccp.profile_len, 0, ctx->data + keyword_len + 2, peek_bytes - (keyword_len + 2));
+                if(ret) return ret;
+
+                ctx->stored.iccp = 1;
+            }
+             else if(!memcmp(chunk.type, type_text, 4) ||
+                     !memcmp(chunk.type, type_ztxt, 4) ||
+                     !memcmp(chunk.type, type_itxt, 4))
+            {
+                if(!chunk.length) return SPNG_ECHUNK_SIZE;
+
+                ctx->file.text = 1;
+
+                if(ctx->user.text) goto discard;
+
+                if(increase_cache_usage(ctx, sizeof(struct spng_text2))) return SPNG_EMEM;
+
+                if(!ctx->stored.text)
+                {
+                    ctx->n_text = 1;
+                    ctx->text_list = spng__calloc(ctx, 1, sizeof(struct spng_text2));
+                    if(ctx->text_list == NULL) return SPNG_EMEM;
+                }
+                else
+                {
+                    ctx->n_text++;
+                    if(ctx->n_text < 1) return SPNG_EOVERFLOW;
+                    if(sizeof(struct spng_text2) > SIZE_MAX / ctx->n_text) return SPNG_EOVERFLOW;
+
+                    void *buf = spng__realloc(ctx, ctx->text_list, ctx->n_text * sizeof(struct spng_text2));
+                    if(buf == NULL) return SPNG_EMEM;
+                    ctx->text_list = buf;
+                }
+
+                struct spng_text2 *text = &ctx->text_list[ctx->n_text - 1];
+                memset(text, 0, sizeof(struct spng_text2));
+
+                uint32_t text_offset = 0, language_tag_offset = 0, translated_keyword_offset = 0;
+                uint32_t peek_bytes = 256; /* enough for 3 80-byte keywords and some text bytes */
+                uint32_t keyword_len;
+
+                if(peek_bytes > chunk.length) peek_bytes = chunk.length;
+
+                ret = read_chunk_bytes(ctx, peek_bytes);
+                if(ret) return ret;
+
+                data = ctx->data;
+
+                const unsigned char *zlib_stream = NULL;
+                const unsigned char *peek_end = data + peek_bytes;
+                const unsigned char *keyword_nul = memchr(data, 0, chunk.length > 80 ? 80 : chunk.length);
+
+                if(keyword_nul == NULL) return SPNG_ETEXT_KEYWORD;
+
+                keyword_len = keyword_nul - data;
+
+                if(!memcmp(chunk.type, type_text, 4))
+                {
+                    text->type = SPNG_TEXT;
+
+                    text->text_length = chunk.length - keyword_len - 1;
+
+                    text_offset = keyword_len;
+
+                    /* increment past nul if there is a text field */
+                    if(text->text_length) text_offset++;
+                }
+                else if(!memcmp(chunk.type, type_ztxt, 4))
+                {
+                    text->type = SPNG_ZTXT;
+
+                    if((peek_bytes - keyword_len) <= 2) return SPNG_EZTXT;
+
+                    if(keyword_nul[1]) return SPNG_EZTXT_COMPRESSION_METHOD;
+
+                    text->compression_flag = 1;
+
+                    text_offset = keyword_len + 2;
+                }
+                else if(!memcmp(chunk.type, type_itxt, 4))
+                {
+                    text->type = SPNG_ITXT;
+
+                    /* at least two 1-byte fields, two >=0 length strings, and one byte of (compressed) text */
+                    if((peek_bytes - keyword_len) < 5) return SPNG_EITXT;
+
+                    memcpy(&text->compression_flag, keyword_nul + 1, 1);
+
+                    if(text->compression_flag > 1) return SPNG_EITXT_COMPRESSION_FLAG;
+
+                    if(keyword_nul[2]) return SPNG_EITXT_COMPRESSION_METHOD;
+
+                    language_tag_offset = keyword_len + 3;
+
+                    const unsigned char *term;
+                    term = memchr(data + language_tag_offset, 0, peek_bytes - language_tag_offset);
+                    if(term == NULL) return SPNG_EITXT_LANG_TAG;
+
+                    if((peek_end - term) < 2) return SPNG_EITXT;
+
+                    translated_keyword_offset = term - data + 1;
+
+                    const unsigned char *zlib_stream = memchr(data + translated_keyword_offset, 0, peek_bytes - translated_keyword_offset);
+                    if(zlib_stream == NULL) return SPNG_EITXT;
+                    if(zlib_stream == peek_end) return SPNG_EITXT;
+
+                    text_offset = zlib_stream - data + 1;
+                    text->text_length = chunk.length - text_offset;
+                }
+                else return 1;
+
+
+                if(text->compression_flag)
+                {
+                    /* cache usage = peek_bytes + decompressed text size + nul */
+                    if(increase_cache_usage(ctx, peek_bytes)) return SPNG_EMEM;
+
+                    text->keyword = spng__calloc(ctx, 1, peek_bytes);
+                    if(text->keyword == NULL) return SPNG_EMEM;
+
+                    memcpy(text->keyword, data, peek_bytes);
+
+                    zlib_stream = ctx->data + text_offset;
+
+                    ret = spng__inflate_stream(ctx, &text->text, &text->text_length, 1, zlib_stream, peek_bytes - text_offset);
+                    if(ret) return ret;
+
+                    text->text[text->text_length - 1] = '\0';
+                }
+                else
+                {
+                    if(increase_cache_usage(ctx, chunk.length + 1)) return SPNG_EMEM;
+
+                    text->keyword = spng__malloc(ctx, chunk.length + 1);
+                    if(text->keyword == NULL) return SPNG_EMEM;
+
+                    memcpy(text->keyword, data, peek_bytes);
+
+                    if(chunk.length > peek_bytes)
+                    {
+                        ret = read_chunk_bytes2(ctx, text->keyword + peek_bytes, chunk.length - peek_bytes);
+                        if(ret) return ret;
+                    }
+
+                    text->text = text->keyword + text_offset;
+
+                    text->text_length = chunk.length - text_offset;
+
+                    text->text[text->text_length] = '\0';
+                }
+
+                if(check_png_keyword(text->keyword)) return SPNG_ETEXT_KEYWORD;
+
+                text->text_length = strlen(text->text);
+
+                if(text->type != SPNG_ITXT)
+                {
+                    language_tag_offset = keyword_len;
+                    translated_keyword_offset = keyword_len;
+
+                    if(check_png_text(text->text, text->text_length)) return SPNG_ETEXT;
+                }
+
+                text->language_tag = text->keyword + language_tag_offset;
+                text->translated_keyword = text->keyword + translated_keyword_offset;
+
+                ctx->stored.text = 1;
+            }
+            else if(!memcmp(chunk.type, type_splt, 4))
+            {
+                if(ctx->state == SPNG_STATE_AFTER_IDAT) return SPNG_ECHUNK_POS;
+                if(ctx->user.splt) goto discard; /* XXX: could check profile names for uniqueness */
+                if(!chunk.length) return SPNG_ECHUNK_SIZE;
+
+                ctx->file.splt = 1;
+
+                /* chunk.length + sizeof(struct spng_splt) + splt->n_entries * sizeof(struct spnt_splt_entry) */
+                if(increase_cache_usage(ctx, chunk.length + sizeof(struct spng_splt))) return SPNG_EMEM;
+
+                if(!ctx->stored.splt)
+                {
+                    ctx->n_splt = 1;
+                    ctx->splt_list = spng__calloc(ctx, 1, sizeof(struct spng_splt));
+                    if(ctx->splt_list == NULL) return SPNG_EMEM;
+                }
+                else
+                {
+                    ctx->n_splt++;
+                    if(ctx->n_splt < 1) return SPNG_EOVERFLOW;
+                    if(sizeof(struct spng_splt) > SIZE_MAX / ctx->n_splt) return SPNG_EOVERFLOW;
+
+                    void *buf = spng__realloc(ctx, ctx->splt_list, ctx->n_splt * sizeof(struct spng_splt));
+                    if(buf == NULL) return SPNG_EMEM;
+                    ctx->splt_list = buf;
+                }
+
+                struct spng_splt *splt = &ctx->splt_list[ctx->n_splt - 1];
+
+                memset(splt, 0, sizeof(struct spng_splt));
+
+                void *t = spng__malloc(ctx, chunk.length);
+                if(t == NULL) return SPNG_EMEM;
+
+                splt->entries = t; /* simplifies error handling */
+                data = t;
+
+                ret = read_chunk_bytes2(ctx, t, chunk.length);
+                if(ret) return ret;
+
+                uint32_t keyword_len = chunk.length < 80 ? chunk.length : 80;
+
+                const unsigned char *keyword_nul = memchr(data, 0, keyword_len);
+                if(keyword_nul == NULL) return SPNG_ESPLT_NAME;
+
+                keyword_len = keyword_nul - data;
+
+                memcpy(splt->name, data, keyword_len);
+
+                if(check_png_keyword(splt->name)) return SPNG_ESPLT_NAME;
+
+                uint32_t j;
+                for(j=0; j < (ctx->n_splt - 1); j++)
+                {
+                    if(!strcmp(ctx->splt_list[j].name, splt->name)) return SPNG_ESPLT_DUP_NAME;
+                }
+
+                if( (chunk.length - keyword_len) <= 2) return SPNG_ECHUNK_SIZE;
+
+                memcpy(&splt->sample_depth, data + keyword_len + 1, 1);
+
+                uint32_t entries_len = chunk.length - keyword_len - 2;
+                if(!entries_len) return SPNG_ECHUNK_SIZE;
+
+                if(splt->sample_depth == 16)
+                {
+                    if(entries_len % 10 != 0) return SPNG_ECHUNK_SIZE;
+                    splt->n_entries = entries_len / 10;
+                }
+                else if(splt->sample_depth == 8)
+                {
+                    if(entries_len % 6 != 0) return SPNG_ECHUNK_SIZE;
+                    splt->n_entries = entries_len / 6;
+                }
+                else return SPNG_ESPLT_DEPTH;
+
+                if(!splt->n_entries) return SPNG_ECHUNK_SIZE;
+
+                size_t list_size = splt->n_entries;
+
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
