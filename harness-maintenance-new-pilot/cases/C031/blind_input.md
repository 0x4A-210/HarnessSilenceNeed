# Case ID

C031

## Existing Fuzz Harness H0

### `prog/fuzzing/enhance_fuzzer.cc`

~~~~cpp
#include "leptfuzz.h"

extern "C" int
LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) { 
	if (size<3) return 0;
 
	leptSetStdNullHandler();

	PIX *pixs_payload = pixReadMemSpix(data, size);
	if (pixs_payload == NULL) return 0;

	PIX *pix_pointer_payload, *return_pix, *pix2;
	L_KERNEL *kel;
	NUMA *na1, *na2, *na3;

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixContrastTRCMasked(NULL, pix_pointer_payload, NULL, 0.5);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixDarkenGray(NULL, pix_pointer_payload, 220, 10);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixEqualizeTRC(NULL, pix_pointer_payload, 220, 10);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixGammaTRCMasked(NULL, pix_pointer_payload, NULL,
                                       1.0, 100, 175);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixGammaTRCWithAlpha(NULL, pix_pointer_payload,
                                          0.5, 1.0, 100);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixHalfEdgeByBandpass(pix_pointer_payload, 2, 2, 4, 4);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	l_float32 sat;
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixMeasureSaturation(pix_pointer_payload, 1, &sat);
	pixDestroy(&pix_pointer_payload);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixModifyBrightness(NULL, pix_pointer_payload, 0.5);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixModifyHue(NULL, pix_pointer_payload, 0.01 + 0.05 * 1);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixModifySaturation(NULL, pix_pointer_payload,
                                         -0.9 + 0.1 * 1);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixMosaicColorShiftRGB(pix_pointer_payload,
                                            -0.1, 0.0, 0.0, 0.0999, 1);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixMultConstantColor(pix_pointer_payload, 0.7, 0.4, 1.3);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	kel = kernelCreate(3, 3);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixMultMatrixColor( pix_pointer_payload, kel);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);
	kernelDestroy(&kel);

	na1 = numaGammaTRC(1.0, 0, 255);
	na2 = numaGammaTRC(1.0, 0, 255);
	na3 = numaGammaTRC(1.0, 0, 255);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pix2 = pixMakeSymmetricMask(10, 10, 0.5, 0.5, L_USE_INNER);
	return_pix = pixTRCMapGeneral(pix_pointer_payload, pix2, na1, na2, na3);
	pixDestroy(&return_pix);
	numaDestroy(&na1);
	numaDestroy(&na2);
	numaDestroy(&na3);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&pix2);

	pixDestroy(&pixs_payload);
	return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/src/enhance.c b/src/enhance.c
index 32813c4..9d4bf00 100644
--- a/src/enhance.c
+++ b/src/enhance.c
@@ -44,8 +44,8 @@
  *           NUMA    *numaEqualizeTRC()
  *
  *      Generic TRC mapper
- *           PIX     *pixTRCMap()
- *           PIX     *pixTRCMapGeneral()
+ *           l_int32  pixTRCMap()
+ *           l_int32  pixTRCMapGeneral()
  *
  *      Unsharp-masking
  *           PIX     *pixUnsharpMasking()
@@ -765,7 +765,7 @@ NUMA      *nah, *nasum, *nad;
  * \param[in]    pixs    8 grayscale or 32 bpp rgb; not colormapped
  * \param[in]    pixm    [optional] 1 bpp mask
  * \param[in]    na      mapping array
- * \return  pixd, or NULL on error
+ * \return  0 if OK, 1 on error
  *
  * <pre>
  * Notes:
@@ -886,7 +886,7 @@ l_uint32  *data, *datam, *line, *linem, *tab;
  * \param[in]    pixs             32 bpp rgb; not colormapped
  * \param[in]    pixm             [optional] 1 bpp mask
  * \param[in]    nar, nag, nab    mapping arrays
- * \return  pixd, or NULL on error
+ * \return  0 if OK, 1 on error
  *
  * <pre>
  * Notes:
diff --git a/src/finditalic.c b/src/finditalic.c
index be7e4c5..adcd0e7 100644
--- a/src/finditalic.c
+++ b/src/finditalic.c
@@ -127,10 +127,11 @@ SEL     *sel_ital1, *sel_ital2, *sel_ital3;
 
     PROCNAME("pixItalicWords");
 
-    if (!pixs)
-        return ERROR_INT("pixs not defined", procName, 1);
     if (!pboxa)
         return ERROR_INT("&boxa not defined", procName, 1);
+    *pboxa = NULL;
+    if (!pixs)
+        return ERROR_INT("pixs not defined", procName, 1);
     if (boxaw && pixw)
         return ERROR_INT("both boxaw and pixw are defined", procName, 1);
 
diff --git a/src/pdfio2.c b/src/pdfio2.c
index 9ee4126..2f8629d 100644
--- a/src/pdfio2.c
+++ b/src/pdfio2.c
@@ -2412,18 +2412,30 @@ substituteObjectNumbers(L_BYTEA  *bas,
 l_uint8   space = ' ';
 l_uint8  *datas;
 l_uint8   buf[32];  /* only needs to hold one integer in ascii format */
-l_int32   start, nrepl, i, j, objin, objout, found;
+l_int32   start, nrepl, i, j, nobjs, objin, objout, found;
 l_int32  *objs, *matches;
 size_t    size;
 L_BYTEA  *bad;
 L_DNA    *da_match;
 
+    PROCNAME("substituteObjectNumbers");
+    if (!bas)
+        return (L_BYTEA *)ERROR_PTR("bas not defined", procName, NULL);
+    if (!na_objs)
+        return (L_BYTEA *)ERROR_PTR("na_objs not defined", procName, NULL);
+
     datas = l_byteaGetData(bas, &size);
     bad = l_byteaCreate(100);
     objs = numaGetIArray(na_objs);  /* object number mapper */
+    nobjs = numaGetCount(na_objs);  /* use for sanity checking */
 
         /* Substitute the object number on the first line */
     sscanf((char *)datas, "%d", &objin);
+    if (objin < 0 || objin >= nobjs) {
+        L_ERROR("index %d into array of size %d\n", procName, objin, nobjs);
+        LEPT_FREE(objs);
+        return bad;
+    }
     objout = objs[objin];
     snprintf((char *)buf, 32, "%d", objout);
     l_byteaAppendString(bad, (char *)buf);
@@ -2449,6 +2461,13 @@ L_DNA    *da_match;
             /* Copy bytes from 'start' up to the object number */
         l_byteaAppendData(bad, datas + start, j - start + 1);
         sscanf((char *)(datas + j + 1), "%d", &objin);
+        if (objin < 0 || objin >= nobjs) {
+            L_ERROR("index %d into array of size %d\n", procName, objin, nobjs);
+            LEPT_FREE(objs);
+            LEPT_FREE(matches);
+            l_dnaDestroy(&da_match);
+            return bad;
+        }
         objout = objs[objin];
         snprintf((char *)buf, 32, "%d", objout);
         l_byteaAppendString(bad, (char *)buf);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
