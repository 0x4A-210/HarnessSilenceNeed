# Case ID

C050

## Existing Fuzz Harness H0

### `tests/spng_read_fuzzer.c`

~~~~c
#define SPNG_UNTESTED
#include "../spng/spng.h"

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
    int file_stream = data[size - 4] & 4;

    size -= 4;

    int ret;
    unsigned char *out = NULL;
    FILE *file = NULL;

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
    struct spng_text text[4] = {0};
    struct spng_bkgd bkgd;
    struct spng_hist hist;
    struct spng_phys phys;
    struct spng_splt splt[4] = {0};
    struct spng_time time;
    uint32_t n_text = 4, n_splt = 4;

    struct buf_state state;
    state.data = data;
    state.bytes_left = size;

    if(stream)
    {
        if(file_stream)
        {
#if defined(SPNGT_HAVE_FMEMOPEN)
            file = fmemopen((void*)data, size, "rb");

            if(file == NULL) goto err;
#endif
            ret = spng_set_png_file(ctx, file);
        }
        else ret = spng_set_png_stream(ctx, buffer_read_fn, &state);
    }
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
            if(text[i].text == NULL ||
               text[i].keyword[0] == '\0' ||
               text[i].language_tag == NULL ||
               text[i].translated_keyword == NULL ||
               memchr(text[i].keyword, 0, 80) == NULL)
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

    if(spng_get_splt(ctx, splt, &n_splt))
    {/* Up to 4 entries were read, get the actual count */
        spng_get_splt(ctx, NULL, &n_splt);

        uint32_t i;
        for(i=0; i < n_splt; i++)
        {
            if(splt[i].name[0] == '\0' ||
               splt[i].entries == NULL ||
               memchr(splt[i].name, 0, 80) == NULL)
            {
                spng_ctx_free(ctx);
                if(out != NULL) free(out);
                return 1;
            }
        }
    }

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

    spng_get_time(ctx, &time);

err:
    spng_ctx_free(ctx);
    if(out != NULL) free(out);
    if(file != NULL) fclose(file);

    return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/spng/spng.c b/spng/spng.c
index 688cc34..144d38b 100644
--- a/spng/spng.c
+++ b/spng/spng.c
@@ -1635,12 +1635,39 @@ static int read_ihdr(spng_ctx *ctx)
     return 0;
 }
 
+static void splt_undo(spng_ctx *ctx)
+{
+    struct spng_splt *splt = &ctx->splt_list[ctx->n_splt - 1];
+
+    spng__free(ctx, splt->entries);
+
+    splt->entries = NULL;
+
+    ctx->n_splt--;
+}
+
+static void text_undo(spng_ctx *ctx)
+{
+    struct spng_text2 *text = &ctx->text_list[ctx->n_text - 1];
+
+    spng__free(ctx, text->keyword);
+    if(text->compression_flag) spng__free(ctx, text->text);
+
+    text->keyword = NULL;
+    text->text = NULL;
+
+    ctx->n_text--;
+}
+
+typedef void spng__undo(spng_ctx *ctx);
+
 static int read_non_idat_chunks(spng_ctx *ctx)
 {
     int ret, discard = 0;
     int prev_was_idat = ctx->state == SPNG_STATE_AFTER_IDAT ? 1 : 0;
     struct spng_chunk chunk;
     const unsigned char *data;
+    spng__undo *undo = NULL;
 
     struct spng_chunk_bitfield stored;
     memcpy(&stored, &ctx->stored, sizeof(struct spng_chunk_bitfield));
@@ -1649,10 +1676,14 @@ static int read_non_idat_chunks(spng_ctx *ctx)
     {
         if(discard)
         {
+            if(undo) undo(ctx);
+
             memcpy(&ctx->stored, &stored, sizeof(struct spng_chunk_bitfield));
-            discard = 0;
         }
 
+        discard = 0;
+        undo = NULL;
+
         memcpy(&stored, &ctx->stored, sizeof(struct spng_chunk_bitfield));
 
         memcpy(&chunk, &ctx->current_chunk, sizeof(struct spng_chunk));
@@ -2056,27 +2087,19 @@ static int read_non_idat_chunks(spng_ctx *ctx)
                 if(!chunk.length) return SPNG_ECHUNK_SIZE;
 
                 ctx->file.text = 1;
+                undo = text_undo;
 
                 if(ctx->user.text) goto discard;
 
                 if(increase_cache_usage(ctx, sizeof(struct spng_text2))) return SPNG_EMEM;
 
-                if(!ctx->stored.text)
-                {
-                    ctx->n_text = 1;
-                    ctx->text_list = spng__calloc(ctx, 1, sizeof(struct spng_text2));
-                    if(ctx->text_list == NULL) return SPNG_EMEM;
-                }
-                else
-                {
-                    ctx->n_text++;
-                    if(ctx->n_text < 1) return SPNG_EOVERFLOW;
-                    if(sizeof(struct spng_text2) > SIZE_MAX / ctx->n_text) return SPNG_EOVERFLOW;
+                ctx->n_text++;
+                if(ctx->n_text < 1) return SPNG_EOVERFLOW;
+                if(sizeof(struct spng_text2) > SIZE_MAX / ctx->n_text) return SPNG_EOVERFLOW;
 
-                    void *buf = spng__realloc(ctx, ctx->text_list, ctx->n_text * sizeof(struct spng_text2));
-                    if(buf == NULL) return SPNG_EMEM;
-                    ctx->text_list = buf;
-                }
+                void *buf = spng__realloc(ctx, ctx->text_list, ctx->n_text * sizeof(struct spng_text2));
+                if(buf == NULL) return SPNG_EMEM;
+                ctx->text_list = buf;
 
                 struct spng_text2 *text = &ctx->text_list[ctx->n_text - 1];
                 memset(text, 0, sizeof(struct spng_text2));
@@ -2223,26 +2246,18 @@ static int read_non_idat_chunks(spng_ctx *ctx)
                 if(!chunk.length) return SPNG_ECHUNK_SIZE;
 
                 ctx->file.splt = 1;
+                undo = splt_undo;
 
                 /* chunk.length + sizeof(struct spng_splt) + splt->n_entries * sizeof(struct spnt_splt_entry) */
                 if(increase_cache_usage(ctx, chunk.length + sizeof(struct spng_splt))) return SPNG_EMEM;
 
-                if(!ctx->stored.splt)
-                {
-                    ctx->n_splt = 1;
-                    ctx->splt_list = spng__calloc(ctx, 1, sizeof(struct spng_splt));
-                    if(ctx->splt_list == NULL) return SPNG_EMEM;
-                }
-                else
-                {
-                    ctx->n_splt++;
-                    if(ctx->n_splt < 1) return SPNG_EOVERFLOW;
-                    if(sizeof(struct spng_splt) > SIZE_MAX / ctx->n_splt) return SPNG_EOVERFLOW;
+                ctx->n_splt++;
+                if(ctx->n_splt < 1) return SPNG_EOVERFLOW;
+                if(sizeof(struct spng_splt) > SIZE_MAX / ctx->n_splt) return SPNG_EOVERFLOW;
 
-                    void *buf = spng__realloc(ctx, ctx->splt_list, ctx->n_splt * sizeof(struct spng_splt));
-                    if(buf == NULL) return SPNG_EMEM;
-                    ctx->splt_list = buf;
-                }
+                void *buf = spng__realloc(ctx, ctx->splt_list, ctx->n_splt * sizeof(struct spng_splt));
+                if(buf == NULL) return SPNG_EMEM;
+                ctx->splt_list = buf;
 
                 struct spng_splt *splt = &ctx->splt_list[ctx->n_splt - 1];
 
@@ -3171,6 +3186,9 @@ spng_ctx *spng_ctx_new2(struct spng_alloc *alloc, int flags)
 
     ctx->state = SPNG_STATE_INIT;
 
+    ctx->crc_action_critical = SPNG_CRC_ERROR;
+    ctx->crc_action_ancillary = SPNG_CRC_DISCARD;
+
     ctx->flags = flags;
 
     return ctx;
diff --git a/spng/spng.h b/spng/spng.h
index 70ea494..3471b10 100644
--- a/spng/spng.h
+++ b/spng/spng.h
@@ -173,9 +173,15 @@ enum spng_decode_flags
 
 enum spng_crc_action
 {
-    SPNG_CRC_ERROR = 0, /* Default */
-    SPNG_CRC_DISCARD = 1, /* Discard chunk, invalid for critical chunks */
-    SPNG_CRC_USE = 2 /* Ignore and don't calculate checksum */
+    /* Default for critical chunks */
+    SPNG_CRC_ERROR = 0,
+
+    /* Discard chunk, invalid for critical chunks,
+       since v0.6.2: default for ancillary chunks */
+    SPNG_CRC_DISCARD = 1,
+
+    /* Ignore and don't calculate checksum */
+    SPNG_CRC_USE = 2
 };
 
 struct spng_ihdr
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
