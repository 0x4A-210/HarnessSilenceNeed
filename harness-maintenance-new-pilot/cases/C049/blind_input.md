# Case ID

C049

## Existing Fuzz Harness H0

### `tests/spng_read_fuzzer.cc`

~~~~cpp
#include "../src/spng.h"

int spng_set_chunk_limits(spng_ctx *ctx, size_t chunk_size, size_t cache_size);
int spng_get_chunk_limits(spng_ctx *ctx, size_t *chunk_size, size_t *cache_size);

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

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/src/spng.h b/src/spng.h
index 0fc5937..7084692 100644
--- a/src/spng.h
+++ b/src/spng.h
@@ -315,6 +315,11 @@ int spng_set_png_stream(spng_ctx *ctx, spng_read_fn *read_fn, void *user);
 int spng_set_image_limits(spng_ctx *ctx, uint32_t width, uint32_t height);
 int spng_get_image_limits(spng_ctx *ctx, uint32_t *width, uint32_t *height);
 
+#if defined(SPNG_UNTESTED)
+int spng_set_chunk_limits(spng_ctx *ctx, size_t chunk_size, size_t cache_size);
+int spng_get_chunk_limits(spng_ctx *ctx, size_t *chunk_size, size_t *cache_size);
+#endif
+
 int spng_set_crc_action(spng_ctx *ctx, int critical, int ancillary);
 
 int spng_decoded_image_size(spng_ctx *ctx, int fmt, size_t *out);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
