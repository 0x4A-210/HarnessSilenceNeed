# Case ID

P023

## Existing Fuzz Harness H0

### `prog/fuzzing/flipdetect_fuzzer.cc`

~~~~cpp
#include "leptfuzz.h"

extern "C" int
LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) { 
	if(size<3) return 0;
 
	leptSetStdNullHandler();

	PIX *pixs_payload = pixReadMemSpix(data, size);
	if(pixs_payload == NULL) return 0;
	
	l_float32 minupconf, minratio, conf1, conf2, upconf1, leftconf1, &upconf2, &leftconf2;
	PIX *pix_pointer_payload, *return_pix;
	
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixMirrorDetect(pix_pointer_payload, &conf1, 0, 1);
	pixDestroy(&pix_pointer_payload);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixMirrorDetectDwa(pix_pointer_payload, &conf2, 0, 0);
	pixDestroy(&pix_pointer_payload);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixOrientCorrect(pixs, minupconf, minratio, NULL, NULL, NULL, 1);
	pixDestroy(&pix_pointer_payload);	
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixOrientDetect(pix_pointer_payload, &upconf1, &leftconf1, 0, 0);
	pixDestroy(&pix_pointer_payload);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixOrientDetectDwa(pix1, &upconf2, &leftconf2, 0, 0);
	pixDestroy(&pix_pointer_payload);

	pixDestroy(&pixs_payload);
	return 0;
}
~~~~
### `prog/fuzzing/morph_fuzzer.cc`

~~~~cpp
#include "leptfuzz.h"

extern "C" int
LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) { 
    if(size<3) return 0;
 
    leptSetStdNullHandler();

    PIX *pixs_payload = pixReadMemSpix(data, size);
    if(pixs_payload == NULL) return 0;

    PIX *pix, *pix1, *pix_copy1, *pix_copy2, *pix_copy3, *pix_copy4;
    SEL *sel;

    pix = pixRead("../test8.jpg");
    pix1 = pixCreate(size, size, 1);
    sel = selCreateFromPix(pix1, 6, 6, "plus_sign");
    pix_copy1 = pixCopy(NULL, pixs_payload);
    pixCloseGeneralized(pix_copy1, pix, sel);
    pixDestroy(&pix_copy1);
    pixDestroy(&pix);
    pixDestroy(&pix1);
    selDestroy(&sel);

    pix1 = pixCreate(size, size, 1);
    sel = selCreateFromPix(pix1, 6, 6, "plus_sign");
    pix_copy2 = pixCopy(NULL, pixs_payload);
    pixCloseSafe(pix_copy2, pix1, sel);
    pixDestroy(&pix_copy2);
    pixDestroy(&pix1);
    selDestroy(&sel);

    pix = pixRead("../test8.jpg");
    sel = selCreateFromPix(pix, 6, 6, "plus_sign");
    pix_copy3 = pixCopy(NULL, pixs_payload);
    pixOpenGeneralized(pix_copy3, pix, sel);
    pixDestroy(&pix_copy3);
    pixDestroy(&pix);
    selDestroy(&sel);

    for(l_int32 i=0; i<5; i++){
        if ((sel = selCreate (i, i, "sel_5dp")) == NULL)
            continue;
        char *selname = selGetName(sel);
        pix_copy4 = pixCopy(NULL, pixs_payload);
        pixFMorphopGen_1(pix_copy4, pix_copy4,
                     i, selname);
        pixDestroy(&pix_copy4);
        selDestroy(&sel);
    }

    pixDestroy(&pixs_payload);
    return 0;
}
~~~~
### `prog/fuzzing/pix3_fuzzer.cc`

~~~~cpp
#include "leptfuzz.h"

extern "C" int
LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) { 
	if(size<3) return 0;
 
	leptSetStdNullHandler();

	PIX *pixs_payload = pixReadMemSpix(data, size);
	if(pixs_payload == NULL) return 0;

	BOX *box1;
	PIX *pix_pointer_payload, *return_pix, *pix2;
	NUMA *return_numa;
	l_float32 l_f;
	l_int32 l_i, l_i2;
	l_uint32 l_ui;
	BOXA *boxa1;

	box1 = boxCreate(150, 130, 1500, 355);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_numa = pixAbsDiffByColumn(pix_pointer_payload, box1);
	pixDestroy(&pix_pointer_payload);
	boxDestroy(&box1);
        numaDestroy(&return_numa);

	box1 = boxCreate(150, 130, 1500, 355);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_numa = pixAbsDiffByRow(pix_pointer_payload, box1);
	pixDestroy(&pix_pointer_payload);
	boxDestroy(&box1);
        numaDestroy(&return_numa);

	box1 = boxCreate(150, 130, 1500, 355);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixAbsDiffInRect(pix_pointer_payload, box1, 0.5, &l_f);
	pixDestroy(&pix_pointer_payload);
	boxDestroy(&box1);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixAbsDiffOnLine(pix_pointer_payload, 2, 2, 3, 3, &l_f);
	pixDestroy(&pix_pointer_payload);

	box1 = boxCreate(150, 130, 1500, 355);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_numa = pixAverageByColumn(pix_pointer_payload, box1, L_BLACK_IS_MAX);
	boxDestroy(&box1);
	pixDestroy(&pix_pointer_payload);
	numaDestroy(&return_numa);
	
	box1 = boxCreate(150, 130, 1500, 355);
	return_numa = pixAverageByRow(pix_pointer_payload, box1, L_WHITE_IS_MAX);
	boxDestroy(&box1);
	pixDestroy(&pix_pointer_payload);
	numaDestroy(&return_numa);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixAverageInRect(pix_pointer_payload, NULL, NULL, 0, 255, 1, &l_f);
	pixDestroy(&pix_pointer_payload);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixAverageInRectRGB(pix_pointer_payload, NULL, NULL, 10, &l_ui);
	pixDestroy(&pix_pointer_payload);

	boxa1 = boxaCreate(0);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixCopyWithBoxa(pix_pointer_payload, boxa1, L_SET_WHITE);
	pixDestroy(&pix_pointer_payload);
	boxaDestroy(&boxa1);
	pixDestroy(&return_pix);
	
	for(int i=0;i<size;i++){
	box1 = boxCreate(150, 130, 1500, 355);
	    pix_pointer_payload = pixCopy(NULL, pixs_payload);
	    pixCountArbInRect(pix_pointer_payload, box1, L_SET_WHITE, 2, &l_i);
	    pixDestroy(&pix_pointer_payload);
	    boxDestroy(&box1);
	}

	box1 = boxCreate(150, 130, 1500, 355);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_numa = pixCountByRow(pix_pointer_payload, box1);
	pixDestroy(&pix_pointer_payload);
	boxDestroy(&box1);
	numaDestroy(&return_numa);
	
	box1 = boxCreate(150, 130, 1500, 355);
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixCountPixelsInRect(pix_pointer_payload, box1, &l_i, &l_i2);
	boxDestroy(&box1);
	pixDestroy(&pix_pointer_payload);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixMakeArbMaskFromRGB(pix_pointer_payload, -0.5, -0.5, 1.0, 20);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	for (int i = 0; i < size; i++) {
            return_pix = pixMakeMaskFromVal(pix_pointer_payload, i);
	    pixDestroy(&pix_pointer_payload);
	    pixDestroy(&return_pix);
        }
    
	pix2 = pixRead("../test8.jpg");
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	pixPaintSelfThroughMask(pix_pointer_payload, pix2, 0, 0, L_HORIZ, 30, 50, 5, 10);
	pixDestroy(&pix2);
	pixDestroy(&pix_pointer_payload);
	
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixSetUnderTransparency(pix_pointer_payload, 0, 0);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);
	
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_numa = pixVarianceByColumn(pix2, NULL);
	pixDestroy(&pix_pointer_payload);
	numaDestroy(&return_numa);
	
	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_numa = pixVarianceByRow(pix_pointer_payload, NULL);
	pixDestroy(&pix_pointer_payload);
	numaDestroy(&return_numa);

	box1 = boxCreate(150, 130, 1500, 355);
	pixVarianceInRect(pix_pointer_payload, box1, &l_f);
	boxDestroy(&box1);
	pixDestroy(&pix_pointer_payload);

	pixDestroy(&pixs_payload);
	return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/prog/alltests_reg.c b/prog/alltests_reg.c
index 8e88a28..82484ca 100644
--- a/prog/alltests_reg.c
+++ b/prog/alltests_reg.c
@@ -61,6 +61,7 @@ static const char *tests[] = {
                               "binarize_reg",
                               "binmorph1_reg",
                               "binmorph3_reg",
+                              "binmorph6_reg",
                               "blackwhite_reg",
                               "blend1_reg",
                               "blend2_reg",
diff --git a/prog/binmorph6_reg.c b/prog/binmorph6_reg.c
new file mode 100644
index 0000000..f45a3f9
--- /dev/null
+++ b/prog/binmorph6_reg.c
@@ -0,0 +1,89 @@
+/*====================================================================*
+ -  Copyright (C) 2001 Leptonica.  All rights reserved.
+ -
+ -  Redistribution and use in source and binary forms, with or without
+ -  modification, are permitted provided that the following conditions
+ -  are met:
+ -  1. Redistributions of source code must retain the above copyright
+ -     notice, this list of conditions and the following disclaimer.
+ -  2. Redistributions in binary form must reproduce the above
+ -     copyright notice, this list of conditions and the following
+ -     disclaimer in the documentation and/or other materials
+ -     provided with the distribution.
+ -
+ -  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
+ -  ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
+ -  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
+ -  A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL ANY
+ -  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
+ -  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
+ -  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
+ -  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
+ -  OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
+ -  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
+ -  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
+ *====================================================================*/
+
+/*
+ * binmorph6_reg.c
+ *
+ *    Miscellaneous morphological operations.
+ */
+
+#ifdef HAVE_CONFIG_H
+#include <config_auto.h>
+#endif  /* HAVE_CONFIG_H */
+
+#include "allheaders.h"
+
+int main(int    argc,
+         char **argv)
+{
+BOX          *box1;
+PIX          *pix1, *pix2, *pix3, *pix4, *pix5, *pix6, *pix7, *pix8;
+PIXA         *pixa;
+SEL          *sel;
+L_REGPARAMS  *rp;
+
+    if (regTestSetup(argc, argv, &rp))
+        return 1;
+
+        /* Test making sel from a pix */
+    pixa = pixaCreate(10);
+    pix1 = pixRead("feyn-fract.tif");
+    box1 = boxCreate(507, 65, 60, 36);
+    pix2 = pixClipRectangle(pix1, box1, NULL);
+    sel = selCreateFromPix(pix2, 6, 6, "life");  /* 610 hits */
+
+        /* Note how the closing tries to put the negative
+         * of the sel, inverted spatially, in the background.  */
+    pix3 = pixDilate(NULL, pix1, sel);  /* note the small holes */
+    pix4 = pixOpen(NULL, pix1, sel);  /* just the sel */
+    pix5 = pixCloseSafe(NULL, pix1, sel);  /* expands small holes in dilate */
+    pix6 = pixSubtract(NULL, pix3, pix1);
+    pix7 = pixSubtract(NULL, pix1, pix5);  /* no pixels because closing
+                                            * is extensive */
+    regTestWritePixAndCheck(rp, pix2, IFF_PNG);  /* 0 */
+    regTestWritePixAndCheck(rp, pix3, IFF_PNG);  /* 1 */
+    regTestWritePixAndCheck(rp, pix4, IFF_PNG);  /* 2 */
+    regTestWritePixAndCheck(rp, pix5, IFF_PNG);  /* 3 */
+    regTestWritePixAndCheck(rp, pix6, IFF_PNG);  /* 4 */
+    regTestWritePixAndCheck(rp, pix7, IFF_PNG);  /* 5 */
+    pixaAddPix(pixa, pix1, L_INSERT);
+    pixaAddPix(pixa, pix3, L_INSERT);
+    pixaAddPix(pixa, pix4, L_INSERT);
+    pixaAddPix(pixa, pix5, L_INSERT);
+    pixaAddPix(pixa, pix6, L_INSERT);
+    pixaAddPix(pixa, pix7, L_INSERT);
+
+    pix8 = pixaDisplayTiledInColumns(pixa, 2, 0.75, 20, 2);
+    regTestWritePixAndCheck(rp, pix8, IFF_PNG);  /* 6 */
+    pixDisplayWithTitle(pix8, 100, 0, NULL, rp->display);
+    pixDestroy(&pix2);
+    pixDestroy(&pix8);
+    pixaDestroy(&pixa);
+    boxDestroy(&box1);
+    selDestroy(&sel);
+    return regTestCleanup(rp);
+}
+
diff --git a/prog/dwamorph1_reg.c b/prog/dwamorph1_reg.c
index 68eb6b9..bc08f5e 100644
--- a/prog/dwamorph1_reg.c
+++ b/prog/dwamorph1_reg.c
@@ -79,8 +79,9 @@ L_REGPARAMS  *rp;
         pixEqual(pixt1, pixt2, &same);
 
 	if (same == 1) {
-	    lept_stderr("dilations are identical for sel %d (%s)\n",
-                        i, selname);
+            if (rp->display)
+                lept_stderr("dilations are identical for sel %d (%s)\n",
+                            i, selname);
 	} else {
             rp->success = FALSE;
 	    fprintf(rp->fp, "dilations differ for sel %d (%s)\n", i, selname);
@@ -95,14 +96,16 @@ L_REGPARAMS  *rp;
 	    /*  ---------  erosion with asymmetric b.c  ----------*/
 
         resetMorphBoundaryCondition(ASYMMETRIC_MORPH_BC);
-        lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
+        if (rp->display) lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
 
 	pixt1 = pixErode(NULL, pixs, sel);
         pixt2 = pixMorphDwa_3(NULL, pixs, L_MORPH_ERODE, selname);
         pixEqual(pixt1, pixt2, &same);
 
 	if (same == 1) {
-	    lept_stderr("erosions are identical for sel %d (%s)\n", i, selname);
+            if (rp->display)
+                lept_stderr("erosions are identical for sel %d (%s)\n",
+                            i, selname);
 	} else {
             rp->success = FALSE;
 	    fprintf(rp->fp, "erosions differ for sel %d (%s)\n", i, selname);
@@ -117,14 +120,16 @@ L_REGPARAMS  *rp;
 	    /*  ---------  erosion with symmetric b.c  ----------*/
 
         resetMorphBoundaryCondition(SYMMETRIC_MORPH_BC);
-        lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
+        if (rp->display) lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
 
 	pixt1 = pixErode(NULL, pixs, sel);
         pixt2 = pixMorphDwa_3(NULL, pixs, L_MORPH_ERODE, selname);
         pixEqual(pixt1, pixt2, &same);
 
 	if (same == 1) {
-	    lept_stderr("erosions are identical for sel %d (%s)\n", i, selname);
+            if (rp->display)
+                lept_stderr("erosions are identical for sel %d (%s)\n",
+                            i, selname);
 	} else {
             rp->success = FALSE;
 	    fprintf(rp->fp, "erosions differ for sel %d (%s)\n", i, selname);
@@ -139,14 +144,16 @@ L_REGPARAMS  *rp;
 	    /*  ---------  opening with asymmetric b.c  ----------*/
 
         resetMorphBoundaryCondition(ASYMMETRIC_MORPH_BC);
-        lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
+        if (rp->display) lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
 
 	pixt1 = pixOpen(NULL, pixs, sel);
         pixt2 = pixMorphDwa_3(NULL, pixs, L_MORPH_OPEN, selname);
         pixEqual(pixt1, pixt2, &same);
 
 	if (same == 1) {
-	    lept_stderr("openings are identical for sel %d (%s)\n", i, selname);
+            if (rp->display)
+                lept_stderr("openings are identical for sel %d (%s)\n",
+                            i, selname);
 	} else {
             rp->success = FALSE;
 	    fprintf(rp->fp, "openings differ for sel %d (%s)\n", i, selname);
@@ -161,14 +168,16 @@ L_REGPARAMS  *rp;
 	    /*  ---------  opening with symmetric b.c  ----------*/
 
         resetMorphBoundaryCondition(SYMMETRIC_MORPH_BC);
-        lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
+        if (rp->display) lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
 
 	pixt1 = pixOpen(NULL, pixs, sel);
         pixt2 = pixMorphDwa_3(NULL, pixs, L_MORPH_OPEN, selname);
         pixEqual(pixt1, pixt2, &same);
 
 	if (same == 1) {
-	    lept_stderr("openings are identical for sel %d (%s)\n", i, selname);
+            if (rp->display)
+                lept_stderr("openings are identical for sel %d (%s)\n",
+                            i, selname);
 	} else {
             rp->success = FALSE;
 	    fprintf(rp->fp, "openings differ for sel %d (%s)\n", i, selname);
@@ -183,14 +192,16 @@ L_REGPARAMS  *rp;
 	    /*  ---------  safe closing with asymmetric b.c  ----------*/
 
         resetMorphBoundaryCondition(ASYMMETRIC_MORPH_BC);
-        lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
+        if (rp->display) lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
 
 	pixt1 = pixCloseSafe(NULL, pixs, sel);  /* must use safe version */
         pixt2 = pixMorphDwa_3(NULL, pixs, L_MORPH_CLOSE, selname);
         pixEqual(pixt1, pixt2, &same);
 
 	if (same == 1) {
-	    lept_stderr("closings are identical for sel %d (%s)\n", i, selname);
+            if (rp->display)
+                lept_stderr("closings are identical for sel %d (%s)\n",
+                            i, selname);
 	} else {
             rp->success = FALSE;
 	    fprintf(rp->fp, "closings differ for sel %d (%s)\n", i, selname);
@@ -205,14 +216,16 @@ L_REGPARAMS  *rp;
 	    /*  ---------  safe closing with symmetric b.c  ----------*/
 
         resetMorphBoundaryCondition(SYMMETRIC_MORPH_BC);
-        lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
+        if (rp->display) lept_stderr("MORPH_BC = %d ... ", MORPH_BC);
 
 	pixt1 = pixClose(NULL, pixs, sel);  /* safe version not required */
         pixt2 = pixMorphDwa_3(NULL, pixs, L_MORPH_CLOSE, selname);
         pixEqual(pixt1, pixt2, &same);
 
 	if (same == 1) {
-	    lept_stderr("closings are identical for sel %d (%s)\n", i, selname);
+            if (rp->display)
+                lept_stderr("closings are identical for sel %d (%s)\n",
+                i, selname);
 	} else {
             rp->success = FALSE;
 	    fprintf(rp->fp, "closings differ for sel %d (%s)\n", i, selname);
diff --git a/src/fhmtauto.c b/src/fhmtauto.c
index e5c403f..dc1802e 100644
--- a/src/fhmtauto.c
+++ b/src/fhmtauto.c
@@ -68,22 +68,24 @@
  *        Makefile, regnerate the prototypes, and recompile
  *        the libraries.  Look at the Makefile to see how I've
  *        included fhmtgen.1.c and fhmtgenlow.1.c.  These files
- *        provide the high-level interfaces for the hmt, and
- *        the low-level interfaces to do the actual work.
+ *        provide the single high-level interface for the hmt, and
+ *        the lower-level functions to do the actual work.
  *
  *    (4) In an application, you now use this interface.  Again
  *        for the example files generated, using integer "1":
  *
  *           PIX   *pixHMTDwa_1(PIX *pixd, PIX *pixs, const char *selname);
  *
- *              or
- *
- *           PIX   *pixFHMTGen_1(PIX *pixd, PIX *pixs, const char *selname);
- *
  *        where the selname is one of the set that were defined
  *        as the name field of sels.  This set is listed at the
  *        beginning of the file fhmtgen.1.c.
- *        As an example, see the file prog/fmtauto_reg.c, which
+ *
+ *        N.B. Although pixFHMTGen_1() is global, you must NOT
+ *        use it, because it assumes that 32 or 64 border pixels
+ *        have been added to each side, and it will crash without those
+ *        added pixels.
+ 
+ *        As an example, see the file prog/fhmtauto_reg.c, which
  *        verifies the correctness of the implementation by
  *        comparing the dwa result with that of full-image
  *        rasterops.
diff --git a/src/fmorphauto.c b/src/fmorphauto.c
index bd07b00..fb88311 100644
--- a/src/fmorphauto.c
+++ b/src/fmorphauto.c
@@ -51,9 +51,10 @@
  *           (c) reading in a SELA from file, using selaRead() or
  *               various other formats.
  *
- *    (2) You call fmorphautogen1() and fmorphautogen2() on this SELA.
- *        These use the text files morphtemplate1.txt and
- *        morphtemplate2.txt for building up the source code.  See the file
+ *    (2) You call fmorphautogen() on this SELA.  This in turn calls
+ *        fmorphautogen1() and fmorphautogen2(), which use the text
+ *        files morphtemplate1.txt and morphtemplate2.txt, respectively,
+ *        for building up the source code.  See the file
  *        prog/fmorphautogen.c for an example of how this is done.
  *        The output is written to files named fmorphgen.*.c
  *        and fmorphgenlow.*.c, where "*" is an integer that you
@@ -66,11 +67,11 @@
  *
  *    (3) You copy the generated source files back to your src
  *        directory for compilation.  Put their names in the
- *        Makefile, regenerate the prototypes, and recompile
- *        the library.  Look at the Makefile to see how I've
- *        included morphgen.1.c and fmorphgenlow.1.c.  These files
- *        provide the high-level interfaces for erosion, dilation,
- *        opening and closing, and the low-level interfaces to
+ *        Makefile, regenerate the allheaders.h prototype file,
+ *        and recompile the library.  Look at the Makefile to see how
+ *        morphgen.1.c and fmorphgenlow.1.c are included.  These files
+ *        provide the single high-level interface for erosion, dilation,
+ *        opening and closing, and the lower-level functions to
  *        do the actual work, for all 58 SELs in the SEL array.
  *
  *    (4) In an application, you now use this interface.  Again
@@ -79,15 +80,16 @@
  *            PIX   *pixMorphDwa_1(PIX *pixd, PIX, *pixs,
  *                                 l_int32 operation, char *selname);
  *
- *                 or
- *
- *            PIX   *pixFMorphopGen_1(PIX *pixd, PIX *pixs,
- *                                    l_int32 operation, char *selname);
- *
  *        where the operation is one of {L_MORPH_DILATE, L_MORPH_ERODE.
  *        L_MORPH_OPEN, L_MORPH_CLOSE}, and the selname is one
  *        of the set that were defined as the name field of sels.
  *        This set is listed at the beginning of the file fmorphgen.1.c.
+ *
+ *        N.B. Although pixFMorphopGen_1() is global, you must NOT
+ *        use it, because it assumes that 32 or 64 border pixels
+ *        have been added to each side, and it will crash without those
+ *        added pixels.
+ *
  *        For examples of use, see the file prog/binmorph_reg1.c, which
  *        verifies the consistency of the various implementations by
  *        comparing the dwa result with that of full-image rasterops.
diff --git a/src/sel1.c b/src/sel1.c
index 61f076d..492972c 100644
--- a/src/sel1.c
+++ b/src/sel1.c
@@ -153,6 +153,10 @@ static const l_int32 InitialPtrArraySize = 50;      /*!< n'importe quoi */
     /* Bounds on kernel size */
 static const l_uint32  MaxKernelSize = 10000;
 
+    /* Bounds on pix template size */
+static const l_uint32  MaxPixTemplateSize = 100;
+static const l_uint32  MaxPixTemplateHits = 1000;
+
     /* Static functions */
 static l_int32 selaExtendArray(SELA *sela);
 static SEL *selCreateFromSArray(SARRAY *sa, l_int32 first, l_int32 last);
@@ -2014,6 +2018,8 @@ SEL     *sel;
  * <pre>
  * Notes:
  *      (1) The origin must be positive.
+ *      (2) The pix must not exceed MaxPixTemplateSize in either dimension.
+ *          and the total number of hits must not exceed MaxPixTemplateHits.
  * </pre>
  */
 SEL *
@@ -2023,7 +2029,7 @@ selCreateFromPix(PIX         *pix,
                  const char  *name)
 {
 SEL      *sel;
-l_int32   i, j, w, h, d;
+l_int32   i, j, w, h, d, nhits;
 l_uint32  val;
 
     PROCNAME("selCreateFromPix");
@@ -2035,6 +2041,15 @@ l_uint32  val;
     pixGetDimensions(pix, &w, &h, &d);
     if (d != 1)
         return (SEL *)ERROR_PTR("pix not 1 bpp", procName, NULL);
+    if (w > MaxPixTemplateSize || h > MaxPixTemplateSize) {
+        L_ERROR("pix template too large (w = %d, h = %d)\n", procName, w, h);
+        return NULL;
+    }
+    pixCountPixels(pix, &nhits, NULL);
+    if (nhits > MaxPixTemplateHits) {
+        L_ERROR("too many hits (%d) in pix template\n", procName, nhits);
+        return NULL;
+    }
 
     sel = selCreate(h, w, name);
     selSetOrigin(sel, cy, cx);
diff --git a/sw.cpp b/sw.cpp
index 832c7ba..61a201d 100644
--- a/sw.cpp
+++ b/sw.cpp
@@ -84,6 +84,7 @@ void build(Solution &s)
             {"binmorph3_reg", {"binmorph3_reg.c"}},
             {"binmorph4_reg", {"binmorph4_reg.c"}},
             {"binmorph5_reg", {"binmorph5_reg.c"}},
+            {"binmorph6_reg", {"binmorph6_reg.c"}},
             {"blackwhite_reg", {"blackwhite_reg.c"}},
             {"blend1_reg", {"blend1_reg.c"}},
             {"blend2_reg", {"blend2_reg.c"}},
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
