# Case ID

P032

## Existing Fuzz Harness H0

### `tests/spng_read_fuzzer.cc`

~~~~cpp
#define SPNG_UNTESTED
#include "../src/spng.h"

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
    unsigned char *out = NULL;

    spng_ctx *ctx = spng_ctx_new(0);
    if(ctx == NULL) return 0;

    if(spng_set_png_buffer(ctx, (void*)data, size)) goto err;

    spng_set_image_limits(ctx, 200000, 200000);
    
    spng_set_chunk_limits(ctx, 4 * 1000 * 1000, 8 * 1000 * 1000);

    spng_set_crc_action(ctx, SPNG_CRC_USE, SPNG_CRC_USE);

    size_t out_size;
    if(spng_decoded_image_size(ctx, SPNG_FMT_RGBA8, &out_size)) goto err;

    if(out_size > 80000000) goto err;

    out = (unsigned char*)malloc(out_size);
    if(out == NULL) goto err;

    if(spng_decode_image(ctx, out, out_size, SPNG_FMT_RGBA8, SPNG_DECODE_USE_TRNS | SPNG_DECODE_USE_GAMA)) goto err;

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
diff --git a/spng.c b/spng.c
new file mode 100644
index 0000000..70628b9
--- /dev/null
+++ b/spng.c
@@ -0,0 +1,3335 @@
+#include "spng.h"
+
+#include <limits.h>
+#include <string.h>
+#include <math.h>
+
+#include <zlib.h>
+
+#define SPNG_READ_SIZE 8192
+
+#if defined(SPNG_OPTIMIZE_FILTER)
+    #if defined(__i386__) || defined(__x86_64__) || defined(_M_IX86) || defined(_M_X64)
+        #define SPNG_X86
+    #else
+        #undef SPNG_OPTIMIZE_FILTER
+    #endif
+
+    void png_read_filter_row_sub3(size_t rowbytes, unsigned char* row);
+    void png_read_filter_row_sub4(size_t rowbytes, unsigned char* row);
+    void png_read_filter_row_avg3(size_t rowbytes, unsigned char* row, const unsigned char* prev);
+    void png_read_filter_row_avg4(size_t rowbytes, unsigned char* row, const unsigned char* prev);
+    void png_read_filter_row_paeth3(size_t rowbytes, unsigned char* row, const unsigned char* prev);
+    void png_read_filter_row_paeth4(size_t rowbytes, unsigned char* row, const unsigned char* prev);
+#endif
+
+#define SPNG_FILTER_TYPE_NONE 0
+#define SPNG_FILTER_TYPE_SUB 1
+#define SPNG_FILTER_TYPE_UP 2
+#define SPNG_FILTER_TYPE_AVERAGE 3
+#define SPNG_FILTER_TYPE_PAETH 4
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
+    int ret = get_ancillary(ctx); \
+    if(ret) return ret;
+
+#define SPNG_SET_CHUNK_BOILERPLATE(chunk) \
+    if(ctx == NULL || chunk == NULL) return 1; \
+    int ret = get_ancillary2(ctx); \
+    if(ret) return ret;
+
+struct spng_ctx
+{
+    size_t data_size;
+    size_t bytes_read;
+    unsigned char *data;
+
+    /* User-defined pointers for streaming */
+    spng_read_fn *read_fn;
+    void *read_user_ptr;
+
+    /* Used for buffer reads */
+    unsigned char *png_buf; /* base pointer for the buffer */
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
+    unsigned valid_state: 1;
+    unsigned streaming: 1;
+
+    unsigned encode_only: 1;
+
+/* input file contains this chunk */
+    unsigned file_ihdr: 1;
+    unsigned file_plte: 1;
+    unsigned file_chrm: 1;
+    unsigned file_iccp: 1;
+    unsigned file_gama: 1;
+    unsigned file_sbit: 1;
+    unsigned file_srgb: 1;
+    unsigned file_text: 1;
+    unsigned file_bkgd: 1;
+    unsigned file_hist: 1;
+    unsigned file_trns: 1;
+    unsigned file_phys: 1;
+    unsigned file_splt: 1;
+    unsigned file_time: 1;
+    unsigned file_offs: 1;
+    unsigned file_exif: 1;
+
+/* chunk was stored with spng_set_*() */
+    unsigned user_ihdr: 1;
+    unsigned user_plte: 1;
+    unsigned user_chrm: 1;
+    unsigned user_iccp: 1;
+    unsigned user_gama: 1;
+    unsigned user_sbit: 1;
+    unsigned user_srgb: 1;
+    unsigned user_text: 1;
+    unsigned user_bkgd: 1;
+    unsigned user_hist: 1;
+    unsigned user_trns: 1;
+    unsigned user_phys: 1;
+    unsigned user_splt: 1;
+    unsigned user_time: 1;
+    unsigned user_offs: 1;
+    unsigned user_exif: 1;
+
+/* chunk was stored by reading or with spng_set_*() */
+    unsigned stored_ihdr: 1;
+    unsigned stored_plte: 1;
+    unsigned stored_chrm: 1;
+    unsigned stored_iccp: 1;
+    unsigned stored_gama: 1;
+    unsigned stored_sbit: 1;
+    unsigned stored_srgb: 1;
+    unsigned stored_text: 1;
+    unsigned stored_bkgd: 1;
+    unsigned stored_hist: 1;
+    unsigned stored_trns: 1;
+    unsigned stored_phys: 1;
+    unsigned stored_splt: 1;
+    unsigned stored_time: 1;
+    unsigned stored_offs: 1;
+    unsigned stored_exif: 1;
+
+    unsigned have_first_idat: 1;
+    unsigned have_last_idat: 1;
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
+    size_t plte_offset;
+    struct spng_plte plte;
+
+    struct spng_chrm_int chrm_int;
+    struct spng_iccp iccp;
+
+    uint32_t gama;
+    uint16_t *gamma_lut;
+
+    struct spng_sbit sbit;
+
+    uint8_t srgb_rendering_intent;
+
+    uint32_t n_text;
+    struct spng_text *text_list;
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
+};
+
+
+struct spng_subimage
+{
+    uint32_t width;
+    uint32_t height;
+    size_t scanline_width;
+};
+
+void *spng__malloc(spng_ctx *ctx,  size_t size);
+void *spng__calloc(spng_ctx *ctx, size_t nmemb, size_t size);
+void *spng__realloc(spng_ctx *ctx, void *ptr, size_t size);
+void spng__free(spng_ctx *ctx, void *ptr);
+
+int get_ancillary(spng_ctx *ctx);
+int get_ancillary2(spng_ctx *ctx);
+
+int calculate_subimages(struct spng_subimage sub[7], size_t *widest_scanline, struct spng_ihdr *ihdr, unsigned channels);
+
+int check_ihdr(struct spng_ihdr *ihdr, uint32_t max_width, uint32_t max_height);
+int check_sbit(struct spng_sbit *sbit, struct spng_ihdr *ihdr);
+int check_chrm_int(struct spng_chrm_int *chrm_int);
+int check_phys(struct spng_phys *phys);
+int check_time(struct spng_time *time);
+int check_offs(struct spng_offs *offs);
+int check_exif(struct spng_exif *exif);
+
+int check_png_keyword(const char str[80]);
+int check_png_text(const char *str, size_t len);
+
+const uint32_t png_u32max = 2147483647;
+const int32_t png_s32min = -2147483647;
+
+const uint8_t type_ihdr[4] = { 73, 72, 68, 82 };
+const uint8_t type_plte[4] = { 80, 76, 84, 69 };
+const uint8_t type_idat[4] = { 73, 68, 65, 84 };
+const uint8_t type_iend[4] = { 73, 69, 78, 68 };
+
+const uint8_t type_trns[4] = { 116, 82, 78, 83 };
+const uint8_t type_chrm[4] = { 99,  72, 82, 77 };
+const uint8_t type_gama[4] = { 103, 65, 77, 65 };
+const uint8_t type_iccp[4] = { 105, 67, 67, 80 };
+const uint8_t type_sbit[4] = { 115, 66, 73, 84 };
+const uint8_t type_srgb[4] = { 115, 82, 71, 66 };
+const uint8_t type_text[4] = { 116, 69, 88, 116 };
+const uint8_t type_ztxt[4] = { 122, 84, 88, 116 };
+const uint8_t type_itxt[4] = { 105, 84, 88, 116 };
+const uint8_t type_bkgd[4] = { 98,  75, 71, 68 };
+const uint8_t type_hist[4] = { 104, 73, 83, 84 };
+const uint8_t type_phys[4] = { 112, 72, 89, 115 };
+const uint8_t type_splt[4] = { 115, 80, 76, 84 };
+const uint8_t type_time[4] = { 116, 73, 77, 69 };
+
+const uint8_t type_offs[4] = { 111, 70, 70, 115 };
+const uint8_t type_exif[4] = { 101, 88, 73, 102 };
+
+static inline uint16_t read_u16(const void *_data)
+{
+    const unsigned char *data = _data;
+
+    return (data[0] & 0xffU) << 8 | (data[1] & 0xffU);
+}
+
+static inline uint32_t read_u32(const void *_data)
+{
+    const unsigned char *data = _data;
+
+    return (data[0] & 0xffUL) << 24 | (data[1] & 0xffUL) << 16 |
+           (data[2] & 0xffUL) << 8  | (data[3] & 0xffUL);
+}
+
+static inline int32_t read_s32(const void *_data)
+{
+    const unsigned char *data = _data;
+
+    int32_t ret;
+    uint32_t val = (data[0] & 0xffUL) << 24 | (data[1] & 0xffUL) << 16 |
+                   (data[2] & 0xffUL) << 8  | (data[3] & 0xffUL);
+
+    memcpy(&ret, &val, 4);
+
+    return ret;
+}
+
+int is_critical_chunk(struct spng_chunk *chunk)
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
+    if(ctx->streaming && (bytes > ctx->data_size))
+    {
+        void *buf = spng__realloc(ctx, ctx->data, bytes);
+        if(buf == NULL) return SPNG_EMEM;
+
+        ctx->data = buf;
+        ctx->data_size = bytes;
+    }
+
+    int ret;
+    ret = ctx->read_fn(ctx, ctx->read_user_ptr, ctx->data, bytes);
+    if(ret) return ret;
+
+    ctx->bytes_read += bytes;
+    if(ctx->bytes_read < bytes) return SPNG_EOVERFLOW;
+
+    return 0;
+}
+
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
+    if(is_critical_chunk(&ctx->current_chunk) && ctx->crc_action_critical == SPNG_CRC_USE)
+        goto skip_crc;
+    else if(ctx->crc_action_ancillary == SPNG_CRC_USE)
+        goto skip_crc;
+
+    if(ctx->cur_actual_crc != ctx->current_chunk.crc) return SPNG_ECHUNK_CRC;
+
+skip_crc:
+
+    return 0;
+}
+
+/* Read and validate the current chunk's crc and the next chunk header */
+static inline int read_header(spng_ctx *ctx)
+{
+    if(ctx == NULL) return 1;
+
+    int ret;
+    struct spng_chunk chunk = { 0 };
+
+    ret = read_and_check_crc(ctx);
+    if(ret) return ret;
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
+    if(!bytes) return 0;
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
+static int discard_chunk_bytes(spng_ctx *ctx, uint32_t bytes)
+{
+    if(ctx == NULL) return 1;
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
+/* Read at least one byte from the IDAT stream */
+static int get_idat_bytes(spng_ctx *ctx, uint32_t *bytes_read)
+{
+    if(ctx == NULL || bytes_read == NULL) return 1;
+    if(memcmp(ctx->current_chunk.type, type_idat, 4)) return SPNG_EIDAT_TOO_SHORT;
+
+    int ret;
+    uint32_t len;
+
+    while(!ctx->cur_chunk_bytes_left)
+    {
+        ret = read_header(ctx);
+        if(ret) return ret;
+
+        if(memcmp(ctx->current_chunk.type, type_idat, 4)) return SPNG_EIDAT_TOO_SHORT;
+    }
+
+    if(ctx->streaming)
+    {/* TODO: calculate bytes to read for progressive reads */
+        len = SPNG_READ_SIZE;
+        if(len > ctx->current_chunk.length) len = ctx->current_chunk.length;
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
+/* Defilter *scanline in-place.
+   *prev_scanline and *scanline should point to the first pixel,
+   scanline_width is the width of the scanline without the filter byte.
+   */
+static int defilter_scanline(const unsigned char *prev_scanline, unsigned char *scanline,
+                             size_t scanline_width, unsigned bytes_per_pixel, unsigned filter)
+{
+    if(prev_scanline == NULL || scanline == NULL || !scanline_width) return 1;
+
+    size_t i;
+
+    if(filter > 4) return SPNG_EFILTER;
+    if(filter == 0) return 0;
+
+#if defined(SPNG_OPTIMIZE_FILTER)
+    if(filter == SPNG_FILTER_TYPE_UP) goto no_opt;
+
+    if(bytes_per_pixel == 4)
+    {
+        if(filter == SPNG_FILTER_TYPE_SUB)
+            png_read_filter_row_sub4(scanline_width, scanline);
+        else if(filter == SPNG_FILTER_TYPE_AVERAGE)
+            png_read_filter_row_avg4(scanline_width, scanline, prev_scanline);
+        else if(filter == SPNG_FILTER_TYPE_PAETH)
+            png_read_filter_row_paeth4(scanline_width, scanline, prev_scanline);
+
+        return 0;
+    }
+    else if(bytes_per_pixel == 3)
+    {
+        if(filter == SPNG_FILTER_TYPE_SUB)
+            png_read_filter_row_sub3(scanline_width, scanline);
+        else if(filter == SPNG_FILTER_TYPE_AVERAGE)
+            png_read_filter_row_avg3(scanline_width, scanline, prev_scanline);
+        else if(filter == SPNG_FILTER_TYPE_PAETH)
+            png_read_filter_row_paeth3(scanline_width, scanline, prev_scanline);
+
+        return 0;
+    }
+no_opt:
+#endif
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
+        else /* first pixel in row */
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
+            case SPNG_FILTER_TYPE_SUB:
+            {
+                x = x + a;
+                break;
+            }
+            case SPNG_FILTER_TYPE_UP:
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+                break;
+            }
+            case SPNG_FILTER_TYPE_AVERAGE:
+            {
+                uint16_t avg = (a + b) / 2;
+                x = x + avg;
+                break;
+            }
+            case SPNG_FILTER_TYPE_PAETH:
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
+static int chunk_fits_in_cache(spng_ctx *ctx, size_t *new_usage)
+{
+    if(ctx == NULL || new_usage == NULL) return 0;
+   
+    size_t usage = ctx->chunk_cache_usage + (size_t)ctx->current_chunk.length;
+
+    if(usage < ctx->chunk_cache_usage) return 0; /* overflow */
+
+    if(usage > ctx->chunk_cache_limit) return 0;
+
+    *new_usage = usage;
+
+    return 1;
+}
+
+/*
+    Read and validate all critical and relevant ancillary chunks up to the first IDAT
+    Returns zero and sets ctx->first_idat on success
+*/
+static int get_ancillary_data_first_idat(spng_ctx *ctx)
+{
+    if(ctx == NULL) return 1;
+    if(ctx->data == NULL) return 1;
+    if(!ctx->valid_state) return SPNG_EBADSTATE;
+
+    int ret;
+    unsigned char *data;
+    struct spng_chunk chunk;
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
+    uint8_t signature[8] = { 137, 80, 78, 71, 13, 10, 26, 10 };
+    if(memcmp(data, signature, sizeof(signature))) return SPNG_ESIGNATURE;
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
+    ctx->file_ihdr = 1;
+    ctx->stored_ihdr = 1;
+
+    while( !(ret = read_header(ctx)))
+    {
+        memcpy(&chunk, &ctx->current_chunk, sizeof(struct spng_chunk));
+
+        if(!memcmp(chunk.type, type_idat, 4))
+        {
+            memcpy(&ctx->first_idat, &chunk, sizeof(struct spng_chunk));
+            return 0;
+        }
+
+        if(!chunk_fits_in_cache(ctx, &ctx->chunk_cache_usage)) continue;
+
+        ret = read_chunk_bytes(ctx, chunk.length);
+        if(ret) return ret;
+
+        data = ctx->data;
+
+        /* Reserved bit must be zero */
+        if( (chunk.type[2] & (1 << 5)) != 0) return SPNG_ECHUNK_TYPE;
+        /* Ignore private chunks */
+        if( (chunk.type[1] & (1 << 5)) != 0) continue;
+
+        if(is_critical_chunk(&chunk)) /* Critical chunk */
+        {
+            if(!memcmp(chunk.type, type_plte, 4))
+            {
+                if(chunk.length == 0) return SPNG_ECHUNK_SIZE;
+                if(chunk.length % 3 != 0) return SPNG_ECHUNK_SIZE;
+                if( (chunk.length / 3) > 256 ) return SPNG_ECHUNK_SIZE;
+
+                if(ctx->ihdr.color_type == 3)
+                {
+                    if(chunk.length / 3 > (1 << ctx->ihdr.bit_depth) ) return SPNG_ECHUNK_SIZE;
+                }
+
+                ctx->plte.n_entries = chunk.length / 3;
+
+                size_t i;
+                for(i=0; i < ctx->plte.n_entries; i++)
+                {
+                    memcpy(&ctx->plte.entries[i].red,   data + i * 3, 1);
+                    memcpy(&ctx->plte.entries[i].green, data + i * 3 + 1, 1);
+                    memcpy(&ctx->plte.entries[i].blue,  data + i * 3 + 2, 1);
+                }
+
+                ctx->plte_offset = chunk.offset;
+
+                ctx->file_plte = 1;
+            }
+            else if(!memcmp(chunk.type, type_iend, 4)) return SPNG_ECHUNK_POS;
+            else if(!memcmp(chunk.type, type_ihdr, 4)) return SPNG_ECHUNK_POS;
+            else return SPNG_ECHUNK_UNKNOWN_CRITICAL;
+        }
+        else if(!memcmp(chunk.type, type_chrm, 4)) /* Ancillary chunks */
+        {
+            if(ctx->file_plte && chunk.offset > ctx->plte_offset) return SPNG_ECHUNK_POS;
+            if(ctx->file_chrm) return SPNG_EDUP_CHRM;
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
+            ctx->file_chrm = 1;
+            ctx->stored_chrm = 1;
+        }
+        else if(!memcmp(chunk.type, type_gama, 4))
+        {
+            if(ctx->file_plte && chunk.offset > ctx->plte_offset) return SPNG_ECHUNK_POS;
+            if(ctx->file_gama) return SPNG_EDUP_GAMA;
+
+            if(chunk.length != 4) return SPNG_ECHUNK_SIZE;
+
+            ctx->gama = read_u32(data);
+
+            if(!ctx->gama) return SPNG_EGAMA;
+            if(ctx->gama > png_u32max) return SPNG_EGAMA;
+
+            ctx->file_gama = 1;
+            ctx->stored_gama = 1;
+        }
+        else if(!memcmp(chunk.type, type_iccp, 4))
+        {
+            if(ctx->file_plte && chunk.offset > ctx->plte_offset) return SPNG_ECHUNK_POS;
+            if(ctx->file_iccp) return SPNG_EDUP_ICCP;
+            if(!chunk.length) return SPNG_ECHUNK_SIZE;
+
+            continue; /* XXX: https://gitlab.com/randy408/libspng/issues/31 */
+        }
+        else if(!memcmp(chunk.type, type_sbit, 4))
+        {
+            if(ctx->file_plte && chunk.offset > ctx->plte_offset) return SPNG_ECHUNK_POS;
+            if(ctx->file_sbit) return SPNG_EDUP_SBIT;
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
+            ctx->file_sbit = 1;
+            ctx->stored_sbit = 1;
+        }
+        else if(!memcmp(chunk.type, type_srgb, 4))
+        {
+            if(ctx->file_plte && chunk.offset > ctx->plte_offset) return SPNG_ECHUNK_POS;
+            if(ctx->file_srgb) return SPNG_EDUP_SRGB;
+
+            if(chunk.length != 1) return SPNG_ECHUNK_SIZE;
+
+            memcpy(&ctx->srgb_rendering_intent, data, 1);
+
+            if(ctx->srgb_rendering_intent > 3) return SPNG_ESRGB;
+
+            ctx->file_srgb = 1;
+            ctx->stored_srgb = 1;
+        }
+        else if(!memcmp(chunk.type, type_bkgd, 4))
+        {
+            if(ctx->file_plte && chunk.offset < ctx->plte_offset) return SPNG_ECHUNK_POS;
+            if(ctx->file_bkgd) return SPNG_EDUP_BKGD;
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
+                if(!ctx->file_plte) return SPNG_EBKGD_NO_PLTE;
+
+                memcpy(&ctx->bkgd.plte_index, data, 1);
+                if(ctx->bkgd.plte_index >= ctx->plte.n_entries) return SPNG_EBKGD_PLTE_IDX;
+            }
+
+            ctx->file_bkgd = 1;
+            ctx->stored_bkgd = 1;
+        }
+        else if(!memcmp(chunk.type, type_trns, 4))
+        {
+            if(ctx->file_plte && chunk.offset < ctx->plte_offset) return SPNG_ECHUNK_POS;
+            if(ctx->file_trns) return SPNG_EDUP_TRNS;
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
+                if(!ctx->file_plte) return SPNG_ETRNS_NO_PLTE;
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
+            ctx->file_trns = 1;
+            ctx->stored_trns = 1;
+        }
+        else if(!memcmp(chunk.type, type_hist, 4))
+        {
+            if(!ctx->file_plte) return SPNG_EHIST_NO_PLTE;
+            if(chunk.offset < ctx->plte_offset) return SPNG_ECHUNK_POS;
+            if(ctx->file_hist) return SPNG_EDUP_HIST;
+
+            if( (chunk.length / 2) != (ctx->plte.n_entries) ) return SPNG_ECHUNK_SIZE;
+
+            size_t k;
+            for(k=0; k < (chunk.length / 2); k++)
+            {
+                ctx->hist.frequency[k] = read_u16(data + k*2);
+            }
+
+            ctx->file_hist = 1;
+            ctx->stored_hist = 1;
+        }
+        else if(!memcmp(chunk.type, type_phys, 4))
+        {
+            if(ctx->file_phys) return SPNG_EDUP_PHYS;
+
+            if(chunk.length != 9) return SPNG_ECHUNK_SIZE;
+
+            ctx->phys.ppu_x = read_u32(data);
+            ctx->phys.ppu_y = read_u32(data + 4);
+            memcpy(&ctx->phys.unit_specifier, data + 8, 1);
+
+            if(check_phys(&ctx->phys)) return SPNG_EPHYS;
+
+            ctx->file_phys = 1;
+            ctx->stored_phys = 1;
+        }
+        else if(!memcmp(chunk.type, type_splt, 4))
+        {
+            if(ctx->user_splt) continue; /* XXX: should check profile names for uniqueness */
+            if(!chunk.length) return SPNG_ECHUNK_SIZE;
+
+            ctx->file_splt = 1;
+
+            if(!ctx->stored_splt)
+            {
+                ctx->n_splt = 1;
+                ctx->splt_list = spng__calloc(ctx, 1, sizeof(struct spng_splt));
+                if(ctx->splt_list == NULL) return SPNG_EMEM;
+            }
+            else
+            {
+                ctx->n_splt++;
+                if(ctx->n_splt < 1) return SPNG_EOVERFLOW;
+                if(sizeof(struct spng_splt) > SIZE_MAX / ctx->n_splt) return SPNG_EOVERFLOW;
+
+                void *buf = spng__realloc(ctx, ctx->splt_list, ctx->n_splt * sizeof(struct spng_splt));
+                if(buf == NULL) return SPNG_EMEM;
+                ctx->splt_list = buf;
+                memset(&ctx->splt_list[ctx->n_splt - 1], 0, sizeof(struct spng_splt));
+            }
+
+            uint32_t i = ctx->n_splt - 1;
+
+            size_t keyword_len = chunk.length > 80 ? 80 : chunk.length;
+            char *keyword_nul = memchr(data, '\0', keyword_len);
+            if(keyword_nul == NULL) return SPNG_ESPLT_NAME;
+
+            memcpy(&ctx->splt_list[i].name, data, keyword_len);
+
+            if(check_png_keyword(ctx->splt_list[i].name)) return SPNG_ESPLT_NAME;
+
+            keyword_len = strlen(ctx->splt_list[i].name);
+
+            if( (chunk.length - keyword_len - 1) ==  0) return SPNG_ECHUNK_SIZE;
+
+            memcpy(&ctx->splt_list[i].sample_depth, data + keyword_len + 1, 1);
+
+            if(ctx->n_splt > 1)
+            {
+                uint32_t j;
+                for(j=0; j < i; j++)
+                {
+                    if(!strcmp(ctx->splt_list[j].name, ctx->splt_list[i].name)) return SPNG_ESPLT_DUP_NAME;
+                }
+            }
+
+            if(ctx->splt_list[i].sample_depth == 16)
+            {
+                if( (chunk.length - keyword_len - 2) % 10 != 0) return SPNG_ECHUNK_SIZE;
+                ctx->splt_list[i].n_entries = (chunk.length - keyword_len - 2) / 10;
+            }
+            else if(ctx->splt_list[i].sample_depth == 8)
+            {
+                if( (chunk.length - keyword_len - 2) % 6 != 0) return SPNG_ECHUNK_SIZE;
+                ctx->splt_list[i].n_entries = (chunk.length - keyword_len - 2) / 6;
+            }
+            else return SPNG_ESPLT_DEPTH;
+
+            if(ctx->splt_list[i].n_entries == 0) return SPNG_ECHUNK_SIZE;
+            if(sizeof(struct spng_splt_entry) > SIZE_MAX / ctx->splt_list[i].n_entries) return SPNG_EOVERFLOW;
+
+            ctx->splt_list[i].entries = spng__malloc(ctx, sizeof(struct spng_splt_entry) * ctx->splt_list[i].n_entries);
+            if(ctx->splt_list[i].entries == NULL) return SPNG_EMEM;
+
+            const unsigned char *splt = data + keyword_len + 2;
+
+            size_t k;
+            if(ctx->splt_list[i].sample_depth == 16)
+            {
+                for(k=0; k < ctx->splt_list[i].n_entries; k++)
+                {
+                    ctx->splt_list[i].entries[k].red = read_u16(splt + k * 10);
+                    ctx->splt_list[i].entries[k].green = read_u16(splt + k * 10 + 2);
+                    ctx->splt_list[i].entries[k].blue = read_u16(splt + k * 10 + 4);
+                    ctx->splt_list[i].entries[k].alpha = read_u16(splt + k * 10 + 6);
+                    ctx->splt_list[i].entries[k].frequency = read_u16(splt + k * 10 + 8);
+                }
+            }
+            else if(ctx->splt_list[i].sample_depth == 8)
+            {
+                for(k=0; k < ctx->splt_list[i].n_entries; k++)
+                {
+                    uint8_t red, green, blue, alpha;
+                    memcpy(&red,   splt + k * 6, 1);
+                    memcpy(&green, splt + k * 6 + 1, 1);
+                    memcpy(&blue,  splt + k * 6 + 2, 1);
+                    memcpy(&alpha, splt + k * 6 + 3, 1);
+                    ctx->splt_list[i].entries[k].frequency = read_u16(splt + k * 6 + 4);
+
+                    ctx->splt_list[i].entries[k].red = red;
+                    ctx->splt_list[i].entries[k].green = green;
+                    ctx->splt_list[i].entries[k].blue = blue;
+                    ctx->splt_list[i].entries[k].alpha = alpha;
+                }
+            }
+
+            ctx->stored_splt = 1;
+        }
+        else if(!memcmp(chunk.type, type_time, 4))
+        {
+            if(ctx->file_time) return SPNG_EDUP_TIME;
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
+            ctx->file_time = 1;
+
+            if(!ctx->user_time) memcpy(&ctx->time, &time, sizeof(struct spng_time));
+
+            ctx->stored_time = 1;
+        }
+        else if(!memcmp(chunk.type, type_text, 4) ||
+                !memcmp(chunk.type, type_ztxt, 4) ||
+                !memcmp(chunk.type, type_itxt, 4))
+        {
+            ctx->file_text = 1;
+
+            continue; /* XXX: https://gitlab.com/randy408/libspng/issues/31 */
+        }
+        else if(!memcmp(chunk.type, type_offs, 4))
+        {
+            if(ctx->file_offs) return SPNG_EDUP_OFFS;
+
+            if(chunk.length != 9) return SPNG_ECHUNK_SIZE;
+
+            ctx->offs.x = read_s32(data);
+            ctx->offs.y = read_s32(data + 4);
+            memcpy(&ctx->offs.unit_specifier, data + 8, 1);
+
+            if(check_offs(&ctx->offs)) return SPNG_EOFFS;
+
+            ctx->file_offs = 1;
+            ctx->stored_offs = 1;
+        }
+        else if(!memcmp(chunk.type, type_exif, 4))
+        {
+            if(ctx->file_exif) return SPNG_EDUP_EXIF;
+
+            ctx->file_exif = 1;
+
+            struct spng_exif exif;
+
+            exif.data = spng__malloc(ctx, chunk.length);
+            if(exif.data == NULL) return SPNG_EMEM;
+
+            memcpy(exif.data, data, chunk.length);
+            exif.length = chunk.length;
+
+            if(check_exif(&exif))
+            {
+                spng__free(ctx, exif.data);
+                return SPNG_EEXIF;
+            }
+
+            if(!ctx->user_exif) memcpy(&ctx->exif, &exif, sizeof(struct spng_exif));
+            else spng__free(ctx, exif.data);
+
+            ctx->stored_exif = 1;
+        }
+    }
+
+    return ret;
+}
+
+static int validate_past_idat(spng_ctx *ctx)
+{
+    if(ctx == NULL) return 1;
+
+    int ret;
+    int prev_was_idat = 1;
+    struct spng_chunk chunk;
+    unsigned char *data;
+
+    memcpy(&chunk, &ctx->last_idat, sizeof(struct spng_chunk));
+
+    while( !(ret = read_header(ctx)))
+    {
+        memcpy(&chunk, &ctx->current_chunk, sizeof(struct spng_chunk));
+
+        ret = read_chunk_bytes(ctx, chunk.length);
+        if(ret) return ret;
+
+        data = ctx->data;
+
+        /* Reserved bit must be zero */
+        if( (chunk.type[2] & (1 << 5)) != 0) return SPNG_ECHUNK_TYPE;
+         /* Ignore private chunks */
+        if( (chunk.type[1] & (1 << 5)) != 0) continue;
+
+        /* Critical chunk */
+        if(is_critical_chunk(&chunk))
+        {
+            if(!memcmp(chunk.type, type_iend, 4)) return 0;
+            else if(!memcmp(chunk.type, type_idat, 4) && prev_was_idat) continue; /* ignore extra IDATs */
+            else return SPNG_ECHUNK_POS; /* critical chunk after last IDAT that isn't IEND */
+        }
+
+        prev_was_idat = 0;
+
+        if(!memcmp(chunk.type, type_chrm, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_gama, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_iccp, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_sbit, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_srgb, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_bkgd, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_hist, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_trns, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_phys, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_splt, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_offs, 4)) return SPNG_ECHUNK_POS;
+        else if(!memcmp(chunk.type, type_time, 4))
+        {
+           if(ctx->file_time) return SPNG_EDUP_TIME;
+
+           if(chunk.length != 7) return SPNG_ECHUNK_SIZE;
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
+            ctx->file_time = 1;
+
+            if(!ctx->user_time) memcpy(&ctx->time, &time, sizeof(struct spng_time));
+
+            ctx->stored_time = 1;
+        }
+        else if(!memcmp(chunk.type, type_exif, 4))
+        {
+            if(ctx->file_exif) return SPNG_EDUP_EXIF;
+
+            ctx->file_exif = 1;
+
+            struct spng_exif exif;
+
+            exif.data = spng__malloc(ctx, chunk.length);
+            if(exif.data == NULL) return SPNG_EMEM;
+
+            memcpy(exif.data, data, chunk.length);
+            exif.length = chunk.length;
+
+            if(check_exif(&exif))
+            {
+                spng__free(ctx, exif.data);
+                return SPNG_EEXIF;
+            }
+
+            if(!ctx->user_exif) memcpy(&ctx->exif, &exif, sizeof(struct spng_exif));
+            else spng__free(ctx, exif.data);
+
+            ctx->stored_exif = 1;
+        }
+        else if(!memcmp(chunk.type, type_text, 4) ||
+                !memcmp(chunk.type, type_ztxt, 4) ||
+                !memcmp(chunk.type, type_itxt, 4))
+        {
+            ctx->file_text = 1;
+
+            continue; /* XXX: https://gitlab.com/randy408/libspng/issues/31 */
+        }
+    }
+
+    return ret;
+}
+
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
+        if(target == sbits) return sample; /* no scaling */
+    }/* bit_depth > sbits */
+    else sample = sample >> (bit_depth - sbits); /* shift significant bits to bottom */
+
+    /* downscale */
+    if(target < sbits) return sample >> (sbits - target);
+
+    /* upscale using left bit replication */
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
+int get_ancillary(spng_ctx *ctx)
+{
+    if(ctx == NULL) return 1;
+    if(ctx->data == NULL) return 1;
+    if(!ctx->valid_state) return SPNG_EBADSTATE;
+
+    int ret;
+    if(!ctx->first_idat.offset)
+    {
+        ret = get_ancillary_data_first_idat(ctx);
+        if(ret)
+        {
+            ctx->valid_state = 0;
+            return ret;
+        }
+    }
+
+    return 0;
+}
+
+/* Same as above except it returns 0 if no buffer is set */
+int get_ancillary2(spng_ctx *ctx)
+{
+    if(ctx == NULL) return 1;
+    if(!ctx->valid_state) return SPNG_EBADSTATE;
+
+    if(ctx->data == NULL) return 0;
+
+    int ret;
+    if(!ctx->first_idat.offset)
+    {
+        ret = get_ancillary_data_first_idat(ctx);
+        if(ret)
+        {
+            ctx->valid_state = 0;
+            return ret;
+        }
+    }
+
+    return 0;
+}
+
+int spng_decode_image(spng_ctx *ctx, void *out, size_t out_size, int fmt, int flags)
+{
+    if(ctx == NULL) return 1;
+    if(out == NULL) return 1;
+    if(!ctx->valid_state) return SPNG_EBADSTATE;
+    if(ctx->encode_only) return SPNG_ENCODE_ONLY;
+
+    int ret;
+    size_t out_size_required;
+
+    ret = spng_decoded_image_size(ctx, fmt, &out_size_required);
+    if(ret) return ret;
+    if(out_size < out_size_required) return SPNG_EBUFSIZ;
+
+    ret = get_ancillary(ctx);
+    if(ret) return ret;
+
+    uint8_t channels = 1; /* grayscale or indexed_color */
+
+    if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_TRUECOLOR) channels = 3;
+    else if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_GRAYSCALE_ALPHA) channels = 2;
+    else if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_TRUECOLOR_ALPHA) channels = 4;
+
+    uint8_t bytes_per_pixel;
+
+    if(ctx->ihdr.bit_depth < 8) bytes_per_pixel = 1;
+    else bytes_per_pixel = channels * (ctx->ihdr.bit_depth / 8);
+
+    z_stream stream;
+    stream.zalloc = Z_NULL;
+    stream.zfree = Z_NULL;
+    stream.opaque = Z_NULL;
+
+    if(inflateInit(&stream) != Z_OK) return SPNG_EZLIB;
+
+    struct spng_subimage sub[7];
+    memset(sub, 0, sizeof(struct spng_subimage) * 7);
+
+    size_t scanline_width;
+
+    ret = calculate_subimages(sub, &scanline_width, &ctx->ihdr, channels);
+    if(ret) return ret;
+
+    unsigned char *scanline = NULL, *prev_scanline = NULL;
+
+    scanline = spng__malloc(ctx, scanline_width);
+    prev_scanline = spng__malloc(ctx, scanline_width);
+
+    if(scanline == NULL || prev_scanline == NULL)
+    {
+        ret = SPNG_EMEM;
+        goto decode_err;
+    }
+
+    int i;
+    for(i=0; i < 7; i++)
+    {
+        /* Skip empty passes */
+        if(sub[i].width != 0 && sub[i].height != 0)
+        {
+            scanline_width = sub[i].scanline_width;
+            break;
+        }
+    }
+
+    uint16_t *gamma_lut = NULL;
+    uint16_t gamma_lut8[256];
+
+    if(flags & SPNG_DECODE_USE_GAMA && ctx->stored_gama)
+    {
+        float file_gamma = (float)ctx->gama / 100000.0f;
+        float max;
+
+        uint32_t i, lut_entries;
+
+        if(fmt == SPNG_FMT_RGBA8)
+        {
+            lut_entries = 256;
+            max = 255.0f;
+            
+            gamma_lut = gamma_lut8;
+        }
+        else /* SPNG_FMT_RGBA16 */
+        {
+            lut_entries = 65536;
+            max = 65535.0f;
+
+            ctx->gamma_lut = spng__malloc(ctx, lut_entries * sizeof(uint16_t));
+            if(ctx->gamma_lut == NULL)
+            {
+                ret = SPNG_EMEM;
+                goto decode_err;
+            }
+            gamma_lut = ctx->gamma_lut;
+        }
+        
+        float screen_gamma = 2.2f;
+        float exponent = file_gamma * screen_gamma;
+
+        if(FP_ZERO == fpclassify(exponent))
+        {
+            ret = SPNG_EGAMA;
+            goto decode_err;
+        }
+
+        exponent = 1.0f / exponent;
+        
+        for(i=0; i < lut_entries; i++)
+        {
+            float c = pow((float)i / max, exponent) * max;
+            c = fmin(c, max);
+
+            gamma_lut[i] = c;
+        }
+    }
+
+    unsigned red_sbits, green_sbits, blue_sbits, alpha_sbits, grayscale_sbits;
+
+    red_sbits = ctx->ihdr.bit_depth;
+    green_sbits = ctx->ihdr.bit_depth;
+    blue_sbits = ctx->ihdr.bit_depth;
+    alpha_sbits = ctx->ihdr.bit_depth;
+    grayscale_sbits = ctx->ihdr.bit_depth;
+
+    if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_INDEXED)
+    {
+        red_sbits = 8;
+        green_sbits = 8;
+        blue_sbits = 8;
+        alpha_sbits = 8;
+    }
+
+    if(ctx->stored_sbit)
+    {
+        if(flags & SPNG_DECODE_USE_SBIT)
+        {
+            if(ctx->ihdr.color_type == 0)
+            {
+                grayscale_sbits = ctx->sbit.grayscale_bits;
+                alpha_sbits = ctx->ihdr.bit_depth;
+            }
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+                grayscale_sbits = ctx->sbit.grayscale_bits;
+                alpha_sbits = ctx->sbit.alpha_bits;
+            }
+            else /* == 6 */
+            {
+                red_sbits = ctx->sbit.red_bits;
+                green_sbits = ctx->sbit.green_bits;
+                blue_sbits = ctx->sbit.blue_bits;
+                alpha_sbits = ctx->sbit.alpha_bits;
+            }
+        }
+    }
+
+    /* Calculate the palette's alpha channel ahead of time */
+    if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_INDEXED)
+    {
+        for(i=0; i < ctx->plte.n_entries; i++)
+        {
+            if(flags & SPNG_DECODE_USE_TRNS && ctx->stored_trns && i < ctx->trns.n_type3_entries)
+                ctx->plte.entries[i].alpha = ctx->trns.type3_alpha[i];
+            else
+                ctx->plte.entries[i].alpha = 255;
+        }
+    }
+
+    unsigned depth_target = 8; /* FMT_RGBA8 */
+    if(fmt == SPNG_FMT_RGBA16) depth_target = 16;
+
+    uint32_t bytes_read;
+
+    ret = get_idat_bytes(ctx, &bytes_read);
+    if(ret) goto decode_err;
+
+    stream.avail_in = bytes_read;
+    stream.next_in = ctx->data;
+
+    int pass;
+    uint8_t filter = 0, next_filter = 0;
+    uint32_t scanline_idx;
+
+    uint32_t k;
+    uint8_t r_8, g_8, b_8, a_8, gray_8;
+    uint16_t r_16, g_16, b_16, a_16, gray_16;
+    uint16_t r, g, b, a, gray;
+    unsigned char pixel[8] = {0};
+    size_t pixel_offset = 0;
+    size_t pixel_size = 4; /* SPNG_FMT_RGBA8 */
+    unsigned processing_depth = ctx->ihdr.bit_depth;
+                
+    if(fmt == SPNG_FMT_RGBA16) pixel_size = 8;
+
+    if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_INDEXED) processing_depth = 8;
+
+    for(pass=0; pass < 7; pass++)
+    {
+        /* Skip empty passes */
+        if(sub[pass].width == 0 || sub[pass].height == 0) continue;
+
+        scanline_width = sub[pass].scanline_width;
+
+        /* prev_scanline is all zeros for the first scanline */
+        memset(prev_scanline, 0, scanline_width);
+
+        /* Read the first filter byte, offsetting all reads by 1 byte.
+           The scanlines will be aligned with the start of the array with
+           the next scanline's filter byte at the end,
+           the last scanline will end up being 1 byte "shorter". */
+        stream.avail_out = 1;
+        stream.next_out = &filter;
+
+        do
+        {
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+            r=0; g=0; b=0; a=0; gray=0;
+            r_8=0; g_8=0; b_8=0; a_8=0; gray_8=0;
+            r_16=0; g_16=0; b_16=0; a_16=0; gray_16=0;
+
+            /* Process a scanline per-pixel and write to *out */
+            for(k=0; k < sub[pass].width; k++)
+            {
+                /* Extract a pixel from the scanline,
+                   *_16/8 variables are used for memcpy'ing depending on bit_depth,
+                   r, g, b, a, gray (all 16bits) are used for processing */
+                switch(ctx->ihdr.color_type)
+                {
+                    case SPNG_COLOR_TYPE_GRAYSCALE:
+                    {
+                        if(ctx->ihdr.bit_depth == 16)
+                        {
+                            gray_16 = read_u16(scanline + (k * 2));
+
+                            if(flags & SPNG_DECODE_USE_TRNS && ctx->stored_trns &&
+                               ctx->trns.gray == gray_16) a_16 = 0;
+                            else a_16 = 65535;
+                        }
+                        else /* <= 8 */
+                        {
+                            memcpy(&gray_8, scanline + k / (8 / ctx->ihdr.bit_depth), 1);
+
+                            uint16_t mask16 = (1 << ctx->ihdr.bit_depth) - 1;
+                            uint8_t mask = mask16; /* avoid shift by width */
+                            uint8_t samples_per_byte = 8 / ctx->ihdr.bit_depth;
+                            uint8_t max_shift_amount = 8 - ctx->ihdr.bit_depth;
+                            uint8_t shift_amount = max_shift_amount - ((k % samples_per_byte) * ctx->ihdr.bit_depth);
+
+                            gray_8 = gray_8 & (mask << shift_amount);
+                            gray_8 = gray_8 >> shift_amount;
+
+                            if(flags & SPNG_DECODE_USE_TRNS && ctx->stored_trns &&
+                               ctx->trns.gray == gray_8) a_8 = 0;
+                            else a_8 = 255;
+                        }
+
+                        break;
+                    }
+                    case SPNG_COLOR_TYPE_TRUECOLOR:
+                    {
+                        if(ctx->ihdr.bit_depth == 16)
+                        {
+                            r_16 = read_u16(scanline + (k * 6));
+                            g_16 = read_u16(scanline + (k * 6) + 2);
+                            b_16 = read_u16(scanline + (k * 6) + 4);
+
+                            if(flags & SPNG_DECODE_USE_TRNS && ctx->stored_trns &&
+                               ctx->trns.red == r_16 &&
+                               ctx->trns.green == g_16 &&
+                               ctx->trns.blue == b_16) a_16 = 0;
+                            else a_16 = 65535;
+                        }
+                        else /* == 8 */
+                        {
+                            memcpy(&r_8, scanline + (k * 3), 1);
+                            memcpy(&g_8, scanline + (k * 3) + 1, 1);
+                            memcpy(&b_8, scanline + (k * 3) + 2, 1);
+
+                            if(flags & SPNG_DECODE_USE_TRNS && ctx->stored_trns &&
+                               ctx->trns.red == r_8 &&
+                               ctx->trns.green == g_8 &&
+                               ctx->trns.blue == b_8) a_8 = 0;
+                            else a_8 = 255;
+                        }
+
+                        break;
+                    }
+                    case SPNG_COLOR_TYPE_INDEXED:
+                    {
+                        uint8_t entry = 0;
+
+                        if(ctx->ihdr.bit_depth == 8)
+                        {
+                            memcpy(&entry, scanline + k, 1);
+                        }
+                        else
+                        {
+                            memcpy(&entry, scanline + k / (8 / ctx->ihdr.bit_depth), 1);
+
+                            uint8_t mask = (1 << ctx->ihdr.bit_depth) - 1;
+                            uint8_t samples_per_byte = 8 / ctx->ihdr.bit_depth;
+                            uint8_t max_shift_amount = 8 - ctx->ihdr.bit_depth;
+                            uint8_t shift_amount = max_shift_amount - ((k % samples_per_byte) * ctx->ihdr.bit_depth);
+
+                            entry = entry & (mask << shift_amount);
+                            entry = entry >> shift_amount;
+                        }
+
+                        if(entry >= ctx->plte.n_entries)
+                        {
+                            ret = SPNG_EPLTE_IDX;
+                            goto decode_err;
+                        }
+                      
+                        r_8 = ctx->plte.entries[entry].red;
+                        g_8 = ctx->plte.entries[entry].green;
+                        b_8 = ctx->plte.entries[entry].blue;
+                        a_8 = ctx->plte.entries[entry].alpha;
+                
+                        break;
+                    }
+                    case SPNG_COLOR_TYPE_GRAYSCALE_ALPHA:
+                    {
+                        if(ctx->ihdr.bit_depth == 16)
+                        {
+                            gray_16 = read_u16(scanline + (k * 4));
+                            a_16 = read_u16(scanline + (k * 4) + 2);
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+                else
+                {
+                    r = sample_to_target(r, processing_depth, red_sbits, depth_target);
+                    g = sample_to_target(g, processing_depth, green_sbits, depth_target);
+                    b = sample_to_target(b, processing_depth, blue_sbits, depth_target);
+                    a = sample_to_target(a, processing_depth, alpha_sbits, depth_target);
+                }
+
+
+                if(ctx->ihdr.color_type == SPNG_COLOR_TYPE_GRAYSCALE ||
+                   ctx->ihdr.color_type == SPNG_COLOR_TYPE_GRAYSCALE_ALPHA)
+                {
+                    r = gray;
+                    g = gray;
+                    b = gray;
+                }
+
+
+                if(flags & SPNG_DECODE_USE_GAMA && ctx->stored_gama)
+                {
+                    r = gamma_lut[r];
+                    g = gamma_lut[g];
+                    b = gamma_lut[b];
+                }
+
+                /* only use *_8/16 for memcpy */
+                r_8 = r; g_8 = g; b_8 = b; a_8 = a;
+                r_16 = r; g_16 = g; b_16 = b; a_16 = a;
+                gray_8 = gray;
+                gray_16 = gray;
+
+                if(fmt == SPNG_FMT_RGBA8)
+                {
+                    memcpy(pixel, &r_8, 1);
+                    memcpy(pixel + 1, &g_8, 1);
+                    memcpy(pixel + 2, &b_8, 1);
+                    memcpy(pixel + 3, &a_8, 1);
+                }
+                else if(fmt == SPNG_FMT_RGBA16)
+                {
+                    memcpy(pixel, &r_16, 2);
+                    memcpy(pixel + 2, &g_16, 2);
+                    memcpy(pixel + 4, &b_16, 2);
+                    memcpy(pixel + 6, &a_16, 2);
+                }
+
+                if(!ctx->ihdr.interlace_method)
+                {
+                    memcpy((char*)out + pixel_offset, pixel, pixel_size);
+
+                    pixel_offset = pixel_offset + pixel_size;
+                }
+                else
+                {
+                    const unsigned int adam7_x_start[7] = { 0, 4, 0, 2, 0, 1, 0 };
+                    const unsigned int adam7_y_start[7] = { 0, 0, 4, 0, 2, 0, 1 };
+                    const unsigned int adam7_x_delta[7] = { 8, 8, 4, 4, 2, 2, 1 };
+                    const unsigned int adam7_y_delta[7] = { 8, 8, 8, 4, 4, 2, 2 };
+
+                    pixel_offset = ((adam7_y_start[pass] + scanline_idx * adam7_y_delta[pass]) *
+                                     ctx->ihdr.width + adam7_x_start[pass] + k * adam7_x_delta[pass]) * pixel_size;
+
+                    memcpy((char*)out + pixel_offset, pixel, pixel_size);
+                }
+                
+            }/* for(k=0; k < sub[pass].width; k++) */
+
+            /* NOTE: prev_scanline is always defiltered */
+            memcpy(prev_scanline, scanline, scanline_width);
+
+        }/* for(scanline_idx=0; scanline_idx < sub[pass].height; scanline_idx++) */
+    }/* for(pass=0; pass < 7; pass++) */
+
+    if(ctx->cur_chunk_bytes_left) /* zlib stream ended before an IDAT chunk boundary */
+    {/* discard the rest of the chunk */
+        ret = discard_chunk_bytes(ctx, ctx->cur_chunk_bytes_left);
+    }
+
+decode_err:
+
+    inflateEnd(&stream);
+    spng__free(ctx, scanline);
+    spng__free(ctx, prev_scanline);
+
+    if(ret)
+    {
+        ctx->valid_state = 0;
+        return ret;
+    }
+
+    memcpy(&ctx->last_idat, &ctx->current_chunk, sizeof(struct spng_chunk));
+
+    ret = validate_past_idat(ctx);
+
+    if(ret) ctx->valid_state = 0;
+
+    return ret;
+}
+
+inline void *spng__malloc(spng_ctx *ctx,  size_t size)
+{
+    return ctx->alloc.malloc_fn(size);
+}
+
+inline void *spng__calloc(spng_ctx *ctx, size_t nmemb, size_t size)
+{
+    return ctx->alloc.calloc_fn(nmemb, size);
+}
+
+inline void *spng__realloc(spng_ctx *ctx, void *ptr, size_t size)
+{
+    return ctx->alloc.realloc_fn(ptr, size);
+}
+
+inline void spng__free(spng_ctx *ctx, void *ptr)
+{
+    ctx->alloc.free_fn(ptr);
+}
+
+
+spng_ctx *spng_ctx_new(int flags)
+{
+    if(flags) return NULL;
+
+    struct spng_alloc alloc = {0};
+
+    alloc.malloc_fn = malloc;
+    alloc.realloc_fn = realloc;
+    alloc.calloc_fn = calloc;
+    alloc.free_fn = free;
+
+    return spng_ctx_new2(&alloc, flags);
+}
+
+spng_ctx *spng_ctx_new2(struct spng_alloc *alloc, int flags)
+{
+    if(alloc == NULL) return NULL;
+    if(flags) return NULL;
+
+    if(alloc->malloc_fn == NULL) return NULL;
+    if(alloc->realloc_fn == NULL) return NULL;
+    if(alloc->calloc_fn == NULL) return NULL;
+    if(alloc->free_fn == NULL) return NULL;
+
+    spng_ctx *ctx = alloc->calloc_fn(1, sizeof(spng_ctx));
+    if(ctx == NULL) return NULL;
+    
+    memcpy(&ctx->alloc, alloc, sizeof(struct spng_alloc));
+
+    ctx->max_chunk_size = png_u32max;
+    ctx->chunk_cache_limit = SIZE_MAX;
+
+    ctx->valid_state = 1;
+
+    return ctx;
+}
+
+void spng_ctx_free(spng_ctx *ctx)
+{
+    if(ctx == NULL) return;
+
+    if(ctx->streaming && ctx->data != NULL) spng__free(ctx, ctx->data);
+
+    if(ctx->exif.data != NULL && !ctx->user_exif) spng__free(ctx, ctx->exif.data);
+
+    if(ctx->iccp.profile != NULL && !ctx->user_iccp) spng__free(ctx, ctx->iccp.profile);
+
+    if(ctx->gamma_lut != NULL) spng__free(ctx, ctx->gamma_lut);
+
+    if(ctx->splt_list != NULL && !ctx->user_splt)
+    {
+        uint32_t i;
+        for(i=0; i < ctx->n_splt; i++)
+        {
+            if(ctx->splt_list[i].entries != NULL) spng__free(ctx, ctx->splt_list[i].entries);
+        }
+        spng__free(ctx, ctx->splt_list);
+    }
+
+    if(ctx->text_list != NULL && !ctx->user_text)
+    {
+        uint32_t i;
+        for(i=0; i< ctx->n_text; i++)
+        {
+            if(ctx->text_list[i].text != NULL) spng__free(ctx, ctx->text_list[i].text);
+            if(ctx->text_list[i].language_tag != NULL) spng__free(ctx, ctx->text_list[i].language_tag);
+            if(ctx->text_list[i].translated_keyword != NULL) spng__free(ctx, ctx->text_list[i].translated_keyword);
+        }
+        spng__free(ctx, ctx->text_list);
+    }
+
+    spng_free_fn *free_func = ctx->alloc.free_fn;
+
+    memset(ctx, 0, sizeof(spng_ctx));
+
+    free_func(ctx);
+}
+
+static int buffer_read_fn(spng_ctx *ctx, void *user, void *data, size_t n)
+{
+    if(n > ctx->bytes_left) return SPNG_IO_EOF;
+
+    ctx->data = ctx->data + ctx->last_read_size;
+
+    ctx->last_read_size = n;
+    ctx->bytes_left -= n;
+
+    return 0;
+}
+
+int spng_set_png_buffer(spng_ctx *ctx, void *buf, size_t size)
+{
+    if(ctx == NULL || buf == NULL) return 1;
+    if(!ctx->valid_state) return SPNG_EBADSTATE;
+
+    if(ctx->data != NULL) return SPNG_EBUF_SET;
+
+    ctx->data = buf;
+    ctx->png_buf = buf;
+    ctx->data_size = size;
+    ctx->bytes_left = size;
+
+    ctx->read_fn = buffer_read_fn;
+
+    return 0;
+}
+
+int spng_set_png_stream(spng_ctx *ctx, spng_read_fn read_func, void *user)
+{
+    if(ctx == NULL || read_func == NULL) return 1;
+    if(!ctx->valid_state) return SPNG_EBADSTATE;
+
+    if(ctx->data != NULL) return SPNG_EBUF_SET;
+
+    ctx->data = spng__malloc(ctx, 8192);
+    if(ctx->data == NULL) return SPNG_EMEM;
+    ctx->data_size = 8192;
+
+    ctx->read_fn = read_func;
+    ctx->read_user_ptr = user;
+
+    ctx->streaming = 1;
+
+    return 0;
+}
+
+int spng_set_image_limits(spng_ctx *ctx, uint32_t width, uint32_t height)
+{
+    if(ctx == NULL) return 1;
+
+    if(width > png_u32max || height > png_u32max) return 1;
+
+    ctx->max_width = width;
+    ctx->max_height = height;
+
+    return 0;
+}
+
+int spng_get_image_limits(spng_ctx *ctx, uint32_t *width, uint32_t *height)
+{
+    if(ctx == NULL || width == NULL || height == NULL) return 1;
+
+    *width = ctx->max_width;
+    *height = ctx->max_height;
+
+    return 0;
+}
+
+int spng_set_chunk_limits(spng_ctx *ctx, size_t chunk_size, size_t cache_limit)
+{
+    if(ctx == NULL || chunk_size > png_u32max) return 1;
+
+    ctx->max_chunk_size = chunk_size;
+
+    ctx->chunk_cache_limit = cache_limit;
+
+    return 0;
+}
+
+int spng_get_chunk_limits(spng_ctx *ctx, size_t *chunk_size, size_t *cache_limit)
+{
+    if(ctx == NULL || chunk_size == NULL) return 1;
+
+    *chunk_size = ctx->max_chunk_size;
+
+    *cache_limit = ctx->chunk_cache_limit;
+
+    return 0;
+}
+
+int spng_set_crc_action(spng_ctx *ctx, int critical, int ancillary)
+{
+    if(ctx == NULL) return 1;
+
+    if(critical > 2 || critical < 0) return 1;
+    if(ancillary > 2 || ancillary < 0) return 1;
+
+    if(critical == SPNG_CRC_DISCARD) return 1;
+
+    ctx->crc_action_critical = critical;
+    ctx->crc_action_ancillary = ancillary;
+
+    return 0;
+}
+
+int spng_decoded_image_size(spng_ctx *ctx, int fmt, size_t *out)
+{
+    if(ctx == NULL || out == NULL) return 1;
+
+    int ret = get_ancillary(ctx);
+    if(ret) return ret;
+
+    size_t res;
+    if(fmt == SPNG_FMT_RGBA8)
+    {
+        if(4 > SIZE_MAX / ctx->ihdr.width) return SPNG_EOVERFLOW;
+        res = 4 * ctx->ihdr.width;
+
+        if(res > SIZE_MAX / ctx->ihdr.height) return SPNG_EOVERFLOW;
+        res = res * ctx->ihdr.height;
+    }
+    else if(fmt == SPNG_FMT_RGBA16)
+    {
+        if(8 > SIZE_MAX / ctx->ihdr.width) return SPNG_EOVERFLOW;
+        res = 8 * ctx->ihdr.width;
+
+        if(res > SIZE_MAX / ctx->ihdr.height) return SPNG_EOVERFLOW;
+        res = res * ctx->ihdr.height;
+    }
+    else return SPNG_EFMT;
+
+    *out = res;
+
+    return 0;
+}
+
+int calculate_subimages(struct spng_subimage sub[7], size_t *widest_scanline, struct spng_ihdr *ihdr, unsigned channels)
+{
+    if(sub == NULL || ihdr == NULL) return 1;
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
+    size_t scanline_width, widest = 0;
+
+    int i;
+    for(i=0; i < 7; i++)
+    {/* Calculate scanline width in bits, round up to the nearest byte */
+        if(sub[i].width == 0 || sub[i].height == 0) continue;
+
+        scanline_width = channels * ihdr->bit_depth;
+
+        if(scanline_width > SIZE_MAX / ihdr->width) return SPNG_EOVERFLOW;
+        scanline_width = scanline_width * sub[i].width;
+
+        scanline_width += 8; /* Filter byte */
+
+        if(scanline_width < 8) return SPNG_EOVERFLOW;
+
+        /* Round up */
+        if(scanline_width % 8 != 0)
+        {
+            scanline_width = scanline_width + 8;
+            if(scanline_width < 8) return SPNG_EOVERFLOW;
+
+            scanline_width -= (scanline_width % 8);
+        }
+
+        scanline_width /= 8;
+
+        sub[i].scanline_width = scanline_width;
+
+        if(widest < scanline_width) widest = scanline_width;
+    }
+
+    *widest_scanline = widest;
+
+    return 0;
+}
+
+int check_ihdr(struct spng_ihdr *ihdr, uint32_t max_width, uint32_t max_height)
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
+        case SPNG_COLOR_TYPE_GRAYSCALE_ALPHA:
+        {
+            if( !(ihdr->bit_depth == 8 || ihdr->bit_depth == 16) )
+                return SPNG_EBIT_DEPTH;
+
+            break;
+        }
+        case SPNG_COLOR_TYPE_TRUECOLOR_ALPHA:
+        {
+            if( !(ihdr->bit_depth == 8 || ihdr->bit_depth == 16) )
+                return SPNG_EBIT_DEPTH;
+
+            break;
+        }
+    default: return SPNG_ECOLOR_TYPE;
+    }
+
+    if(ihdr->compression_method || ihdr->filter_method)
+        return SPNG_ECOMPRESSION_METHOD;
+
+    if( !(ihdr->interlace_method == 0 || ihdr->interlace_method == 1) )
+        return SPNG_EINTERLACE_METHOD;
+
+    return 0;
+}
+
+int check_sbit(struct spng_sbit *sbit, struct spng_ihdr *ihdr)
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
+        if(sbit->grayscale_bits > ihdr->bit_depth) return SPNG_ESBIT;
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
+int check_chrm_int(struct spng_chrm_int *chrm_int)
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
+int check_phys(struct spng_phys *phys)
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
+int check_time(struct spng_time *time)
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
+int check_offs(struct spng_offs *offs)
+{
+    if(offs == NULL) return 1;
+
+    if(offs->x < png_s32min || offs->y < png_s32min) return 1;
+    if(offs->unit_specifier > 1) return 1;
+
+    return 0;
+}
+
+int check_exif(struct spng_exif *exif)
+{
+    if(exif == NULL) return 1;
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
+int check_png_keyword(const char str[80])
+{
+    if(str == NULL) return 1;
+    char *end = memchr(str, '\0', 80);
+
+    if(end == NULL) return 1; /* unterminated string */
+    if(end == str) return 1; /* zero-length string */
+    if(str[0] == ' ') return 1; /* leading space */
+    if(end[-1] == ' ') return 1; /* trailing space */
+    if(strstr(str, "  ") != NULL) return 1; /* consecutive spaces */
+
+    uint8_t c;
+    while(str != end)
+    {
+        memcpy(&c, str, 1);
+
+        if( (c >= 32 && c <= 126) || (c >= 161) ) str++;
+        else return 1; /* invalid character */
+    }
+
+    return 0;
+}
+
+/* Validate PNG text *str up to 'len' bytes */
+int check_png_text(const char *str, size_t len)
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
+        else return 1; /* invalid character */
+    }
+
+    return 0;
+}
+
+int spng_get_ihdr(spng_ctx *ctx, struct spng_ihdr *ihdr)
+{
+    SPNG_GET_CHUNK_BOILERPLATE(ihdr);
+
+    memcpy(ihdr, &ctx->ihdr, sizeof(struct spng_ihdr));
+
+    return 0;
+}
+
+int spng_get_plte(spng_ctx *ctx, struct spng_plte *plte)
+{
+    SPNG_GET_CHUNK_BOILERPLATE(plte);
+
+    if(!ctx->stored_plte) return SPNG_ECHUNKAVAIL;
+
+    memcpy(plte, &ctx->plte, sizeof(struct spng_plte));
+
+    return 0;
+}
+
+int spng_get_trns(spng_ctx *ctx, struct spng_trns *trns)
+{
+    SPNG_GET_CHUNK_BOILERPLATE(trns);
+
+    if(!ctx->stored_trns) return SPNG_ECHUNKAVAIL;
+
+    memcpy(trns, &ctx->trns, sizeof(struct spng_trns));
+
+    return 0;
+}
+
+int spng_get_chrm(spng_ctx *ctx, struct spng_chrm *chrm)
+{
+    SPNG_GET_CHUNK_BOILERPLATE(chrm);
+
+    if(!ctx->stored_chrm) return SPNG_ECHUNKAVAIL;
+
+    chrm->white_point_x = (double)ctx->chrm_int.white_point_x / 100000.0;
+    chrm->white_point_y = (double)ctx->chrm_int.white_point_y / 100000.0;
+    chrm->red_x = (double)ctx->chrm_int.red_x / 100000.0;
+    chrm->red_y = (double)ctx->chrm_int.red_y / 100000.0;
+    chrm->blue_y = (double)ctx->chrm_int.blue_y / 100000.0;
+    chrm->blue_x = (double)ctx->chrm_int.blue_x / 100000.0;
+    chrm->green_x = (double)ctx->chrm_int.green_x / 100000.0;
+    chrm->green_y = (double)ctx->chrm_int.green_y / 100000.0;
+
+    return 0;
+}
+
+int spng_get_chrm_int(spng_ctx *ctx, struct spng_chrm_int *chrm)
+{
+    SPNG_GET_CHUNK_BOILERPLATE(chrm);
+
+    if(!ctx->stored_chrm) return SPNG_ECHUNKAVAIL;
+
+    memcpy(chrm, &ctx->chrm_int, sizeof(struct spng_chrm_int));
+
+    return 0;
+}
+
+int spng_get_gama(spng_ctx *ctx, double *gamma)
+{
+    SPNG_GET_CHUNK_BOILERPLATE(gamma);
+
+    if(!ctx->stored_gama) return SPNG_ECHUNKAVAIL;
+
+    *gamma = (double)ctx->gama / 100000.0;
+
+    return 0;
+}
+
+int spng_get_iccp(spng_ctx *ctx, struct spng_iccp *iccp)
+{
+    SPNG_GET_CHUNK_BOILERPLATE(iccp);
+
+    if(!ctx->stored_iccp) return SPNG_ECHUNKAVAIL;
+
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
