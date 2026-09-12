# Case ID

C030

## Existing Fuzz Harness H0

### `tests/spng_read_fuzzer.cc`

~~~~cpp
#include "../spng.h"

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
    struct spng_ctx *ctx = spng_ctx_new();
    if(ctx == NULL) return 0;

    if(spng_set_png_buffer(ctx, (void*)data, size)) return 0;

    spng_set_image_limits(ctx, 200000, 200000);

    size_t out_size;
    if(spng_decoded_image_size(ctx, SPNG_FMT_RGBA8, &out_size)) return 0;

    unsigned char *out = (unsigned char*)malloc(out_size);
    if(out == NULL) return 0;

    if(spng_decode_image(ctx, out, out_size, SPNG_FMT_RGBA8, 0)) return 0;

    spng_ctx_free(ctx);
    free(out);

    return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/example.c b/example.c
index f03cfc0..fcdb0b8 100644
--- a/example.c
+++ b/example.c
@@ -41,7 +41,7 @@ int main(int argc, char **argv)
         return 1;
     }
 
-    struct spng_ctx *ctx = spng_ctx_new(0);
+    spng_ctx *ctx = spng_ctx_new(0);
     if(ctx == NULL)
     {
         printf("spng_ctx_new() failed\n");
diff --git a/spng.h b/spng.h
index 3bd53ae..2d66d2a 100644
--- a/spng.h
+++ b/spng.h
@@ -360,56 +360,57 @@ struct spng_ctx
     struct spng_exif exif;
 };
 
-
-struct spng_ctx *spng_ctx_new(int flags);
-void spng_ctx_free(struct spng_ctx *ctx);
-
-int spng_set_png_buffer(struct spng_ctx *ctx, void *buf, size_t size);
-int spng_set_png_stream(struct spng_ctx *ctx, spng_read_fn *read_fn, void *user);
-
-int spng_set_image_limits(struct spng_ctx *ctx, uint32_t width, uint32_t height);
-int spng_get_image_limits(struct spng_ctx *ctx, uint32_t *width, uint32_t *height);
-
-int spng_decoded_image_size(struct spng_ctx *ctx, int fmt, size_t *out);
-
-int spng_decode_image(struct spng_ctx *ctx, void *out, size_t out_size, int fmt, int flags);
-
-int spng_get_ihdr(struct spng_ctx *ctx, struct spng_ihdr *ihdr);
-int spng_get_plte(struct spng_ctx *ctx, struct spng_plte *plte);
-int spng_get_trns(struct spng_ctx *ctx, struct spng_trns *trns);
-int spng_get_chrm(struct spng_ctx *ctx, struct spng_chrm *chrm);
-int spng_get_gama(struct spng_ctx *ctx, double *gamma);
-int spng_get_iccp(struct spng_ctx *ctx, struct spng_iccp *iccp);
-int spng_get_sbit(struct spng_ctx *ctx, struct spng_sbit *sbit);
-int spng_get_srgb(struct spng_ctx *ctx, uint8_t *rendering_intent);
-int spng_get_text(struct spng_ctx *ctx, struct spng_text *text, uint32_t *n_text);
-int spng_get_bkgd(struct spng_ctx *ctx, struct spng_bkgd *bkgd);
-int spng_get_hist(struct spng_ctx *ctx, struct spng_hist *hist);
-int spng_get_phys(struct spng_ctx *ctx, struct spng_phys *phys);
-int spng_get_splt(struct spng_ctx *ctx, struct spng_splt *splt, uint32_t *n_splt);
-int spng_get_time(struct spng_ctx *ctx, struct spng_time *time);
-
-int spng_get_offs(struct spng_ctx *ctx, struct spng_offs *offs);
-int spng_get_exif(struct spng_ctx *ctx, struct spng_exif *exif);
-
-
-int spng_set_ihdr(struct spng_ctx *ctx, struct spng_ihdr *ihdr);
-int spng_set_plte(struct spng_ctx *ctx, struct spng_plte *plte);
-int spng_set_trns(struct spng_ctx *ctx, struct spng_trns *trns);
-int spng_set_chrm(struct spng_ctx *ctx, struct spng_chrm *chrm);
-int spng_set_gama(struct spng_ctx *ctx, double gamma);
-int spng_set_iccp(struct spng_ctx *ctx, struct spng_iccp *iccp);
-int spng_set_sbit(struct spng_ctx *ctx, struct spng_sbit *sbit);
-int spng_set_srgb(struct spng_ctx *ctx, uint8_t rendering_intent);
-int spng_set_text(struct spng_ctx *ctx, struct spng_text *text, uint32_t n_text);
-int spng_set_bkgd(struct spng_ctx *ctx, struct spng_bkgd *bkgd);
-int spng_set_hist(struct spng_ctx *ctx, struct spng_hist *hist);
-int spng_set_phys(struct spng_ctx *ctx, struct spng_phys *phys);
-int spng_set_splt(struct spng_ctx *ctx, struct spng_splt *splt, uint32_t n_splt);
-int spng_set_time(struct spng_ctx *ctx, struct spng_time *time);
-
-int spng_set_offs(struct spng_ctx *ctx, struct spng_offs *offs);
-int spng_set_exif(struct spng_ctx *ctx, struct spng_exif *exif);
+typedef struct spng_ctx spng_ctx;
+
+spng_ctx *spng_ctx_new(int flags);
+void spng_ctx_free(spng_ctx *ctx);
+
+int spng_set_png_buffer(spng_ctx *ctx, void *buf, size_t size);
+int spng_set_png_stream(spng_ctx *ctx, spng_read_fn *read_fn, void *user);
+
+int spng_set_image_limits(spng_ctx *ctx, uint32_t width, uint32_t height);
+int spng_get_image_limits(spng_ctx *ctx, uint32_t *width, uint32_t *height);
+
+int spng_decoded_image_size(spng_ctx *ctx, int fmt, size_t *out);
+
+int spng_decode_image(spng_ctx *ctx, void *out, size_t out_size, int fmt, int flags);
+
+int spng_get_ihdr(spng_ctx *ctx, struct spng_ihdr *ihdr);
+int spng_get_plte(spng_ctx *ctx, struct spng_plte *plte);
+int spng_get_trns(spng_ctx *ctx, struct spng_trns *trns);
+int spng_get_chrm(spng_ctx *ctx, struct spng_chrm *chrm);
+int spng_get_gama(spng_ctx *ctx, double *gamma);
+int spng_get_iccp(spng_ctx *ctx, struct spng_iccp *iccp);
+int spng_get_sbit(spng_ctx *ctx, struct spng_sbit *sbit);
+int spng_get_srgb(spng_ctx *ctx, uint8_t *rendering_intent);
+int spng_get_text(spng_ctx *ctx, struct spng_text *text, uint32_t *n_text);
+int spng_get_bkgd(spng_ctx *ctx, struct spng_bkgd *bkgd);
+int spng_get_hist(spng_ctx *ctx, struct spng_hist *hist);
+int spng_get_phys(spng_ctx *ctx, struct spng_phys *phys);
+int spng_get_splt(spng_ctx *ctx, struct spng_splt *splt, uint32_t *n_splt);
+int spng_get_time(spng_ctx *ctx, struct spng_time *time);
+
+int spng_get_offs(spng_ctx *ctx, struct spng_offs *offs);
+int spng_get_exif(spng_ctx *ctx, struct spng_exif *exif);
+
+
+int spng_set_ihdr(spng_ctx *ctx, struct spng_ihdr *ihdr);
+int spng_set_plte(spng_ctx *ctx, struct spng_plte *plte);
+int spng_set_trns(spng_ctx *ctx, struct spng_trns *trns);
+int spng_set_chrm(spng_ctx *ctx, struct spng_chrm *chrm);
+int spng_set_gama(spng_ctx *ctx, double gamma);
+int spng_set_iccp(spng_ctx *ctx, struct spng_iccp *iccp);
+int spng_set_sbit(spng_ctx *ctx, struct spng_sbit *sbit);
+int spng_set_srgb(spng_ctx *ctx, uint8_t rendering_intent);
+int spng_set_text(spng_ctx *ctx, struct spng_text *text, uint32_t n_text);
+int spng_set_bkgd(spng_ctx *ctx, struct spng_bkgd *bkgd);
+int spng_set_hist(spng_ctx *ctx, struct spng_hist *hist);
+int spng_set_phys(spng_ctx *ctx, struct spng_phys *phys);
+int spng_set_splt(spng_ctx *ctx, struct spng_splt *splt, uint32_t n_splt);
+int spng_set_time(spng_ctx *ctx, struct spng_time *time);
+
+int spng_set_offs(spng_ctx *ctx, struct spng_offs *offs);
+int spng_set_exif(spng_ctx *ctx, struct spng_exif *exif);
 
 const char *spng_strerror(int err);
 const char *spng_version_string(void);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
