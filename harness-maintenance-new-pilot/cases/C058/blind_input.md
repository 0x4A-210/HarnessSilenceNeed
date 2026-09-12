# Case ID

C058

## Existing Fuzz Harness H0

### `prog/fuzzing/adaptmap_fuzzer.cc`

~~~~cpp
#include "leptfuzz.h"

extern "C" int
LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) { 
	if(size<3) return 0;

	leptSetStdNullHandler();


	PIX *pixs_payload = pixReadMemSpix(data, size);
	if(pixs_payload == NULL) return 0;

	PIX *pix1, *pix2, *pix3, *pix4, *pix5, *return_pix1, *payload_copy;

	pix1 = pixRead("../test8.jpg");
	payload_copy = pixCopy(NULL, pixs_payload);
	pixBackgroundNormGrayArray(payload_copy, pix1, 10, 10, 10, 10, 256, 10, 10, &pix2);
	pixDestroy(&pix1);
	pixDestroy(&pix2);
	pixDestroy(&payload_copy);



	pix1 = pixRead("../test8.jpg");
	payload_copy = pixCopy(NULL, pixs_payload);
	pixBackgroundNormGrayArrayMorph(payload_copy, pix1, 6, 5, 256, &pix2);
	pixDestroy(&pix1);
	pixDestroy(&pix2);
	pixDestroy(&payload_copy);


	pix1 = pixRead("../test8.jpg");
	payload_copy = pixCopy(NULL, pixs_payload);
	return_pix1 = pixBackgroundNormMorph(payload_copy, pix1, 6, 5, 256);
	pixDestroy(&pix1);
	pixDestroy(&payload_copy);
	if(return_pix1!=NULL){
		pixDestroy(&return_pix1);
	}


	pix1 = pixRead("../test8.jpg");
	pix2 = pixRead("../test8.jpg");
	payload_copy = pixCopy(NULL, pixs_payload);
	pixBackgroundNormRGBArrays(payload_copy, pix1, pix2, 10, 10, 10, 10, 130, 10, 10, &pix3, &pix4, &pix5);
	pixDestroy(&pix1);
	pixDestroy(&pix2);
	pixDestroy(&pix3);
	pixDestroy(&pix4);
	pixDestroy(&pix5);
	pixDestroy(&payload_copy);


	pix1 = pixRead("../test8.jpg");
	payload_copy = pixCopy(NULL, pixs_payload);
	pixBackgroundNormRGBArraysMorph(payload_copy, pix1, 6, 33, 130, &pix2, &pix3, &pix4);
	pixDestroy(&pix1);
	pixDestroy(&pix2);
	pixDestroy(&pix3);
	pixDestroy(&pix4);
	pixDestroy(&payload_copy);


	pix1 = pixRead("../test8.jpg");
	payload_copy = pixCopy(NULL, pixs_payload);
	pixContrastNorm(payload_copy, payload_copy, 10, 10, 3, 0, 0);
	pixDestroy(&pix1);
	pixDestroy(&payload_copy);


	pix1 = pixRead("../test8.jpg");
	payload_copy = pixCopy(NULL, pixs_payload);
	return_pix1 = pixGlobalNormNoSatRGB(payload_copy, pix1, 3, 3, 3, 2, 0.9);
	pixDestroy(&pix1);
	pixDestroy(&payload_copy);
	if(return_pix1!=NULL){
		pixDestroy(&return_pix1);
	}


	payload_copy = pixCopy(NULL, pixs_payload);
	pixThresholdSpreadNorm(payload_copy, L_SOBEL_EDGE, 10, 0, 0, 0.7, -25, 255, 10, &pix1, &pix2, &pix3);
	pixDestroy(&pix1);
	pixDestroy(&pix2);
	pixDestroy(&pix3);
	pixDestroy(&payload_copy);

	pixDestroy(&pixs_payload);


	return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/src/bilateral.c b/src/bilateral.c
index a7fc411..aa1d015 100644
--- a/src/bilateral.c
+++ b/src/bilateral.c
@@ -319,6 +319,10 @@ PIXA         *pixac;
         pixt = pixScaleAreaMap2(pixt2);
         pixDestroy(&pixt2);
     }
+    if (!pixt) {
+        bilateralDestroy(&bil);
+        return (L_BILATERAL *)ERROR_PTR("pixt not made", procName, NULL);
+    }
 
     pixGetExtremeValue(pixt, 1, L_SELECT_MIN, NULL, NULL, NULL, &minval);
     pixGetExtremeValue(pixt, 1, L_SELECT_MAX, NULL, NULL, NULL, &maxval);
@@ -327,8 +331,12 @@ PIXA         *pixac;
 
     border = (l_int32)(2 * sstdev + 1);
     pixsc = pixAddMirroredBorder(pixt, border, border, border, border);
-    bil->pixsc = pixsc;
     pixDestroy(&pixt);
+    if (!pixsc) {
+        bilateralDestroy(&bil);
+        return (L_BILATERAL *)ERROR_PTR("pixsc not made", procName, NULL);
+    }
+    bil->pixsc = pixsc;
     bil->pixs = pixClone(pixs);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
