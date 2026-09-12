# Case ID

C034

## Existing Fuzz Harness H0

### `prog/fuzzing/enhance_fuzzer.cc`

~~~~cpp
#include "leptfuzz.h"

extern "C" int
LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) { 
	if(size<3) return 0;
 
	leptSetStdNullHandler();


	PIX *pixs_payload = pixReadMemSpix(data, size);
	if(pixs_payload == NULL) return 0;

	PIX *pix_pointer_payload, *return_pix, *pix2;
	L_KERNEL *kel;
	NUMA *na1, *na2, *na3;

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixContrastTRCMasked(NULL, pix_pointer_payload, NULL, 0.5);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);


	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixDarkenGray(NULL, pix_pointer_payload,  220,  10);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);


	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixEqualizeTRC(NULL, pix_pointer_payload,  220,  10);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);


	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixGammaTRCMasked(NULL, pix_pointer_payload, NULL,  1.0,  100,  175);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);


	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixGammaTRCWithAlpha(NULL, pix_pointer_payload, 0.5,  1.0,  100);
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
	return_pix = pixModifySaturation(NULL, pix_pointer_payload, -0.9 + 0.1 * 1);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);


	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixMosaicColorShiftRGB(pix_pointer_payload, -0.1, 0.0, 0.0, 0.0999, 1);
	pixDestroy(&pix_pointer_payload);
	pixDestroy(&return_pix);
	

	pix_pointer_payload = pixCopy(NULL, pixs_payload);
	return_pix = pixMultConstantColor(pix_pointer_payload,  0.7,  0.4,  1.3);
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
diff --git a/prog/string_reg.c b/prog/string_reg.c
index c20ed76..acfbd03 100644
--- a/prog/string_reg.c
+++ b/prog/string_reg.c
@@ -32,6 +32,7 @@
  *      * sarray generation and flattening
  *      * sarray serialization
  *      * file splitting
+ *      * sarray splitting
  */
 
 #ifdef HAVE_CONFIG_H
@@ -54,7 +55,7 @@ char         *str0, *str1, *str2, *str3, *str4, *str5, *str6;
 char          fname[128];
 l_uint8      *data1, *data2;
 L_DNA        *da;
-SARRAY       *sa1, *sa2, *sa3;
+SARRAY       *sa1, *sa2, *sa3, *sa4, *sa5;
 L_REGPARAMS  *rp;
 
     if (regTestSetup(argc, argv, &rp))
@@ -198,6 +199,31 @@ L_REGPARAMS  *rp;
     lept_free(str1);
     lept_free(str2);
 
+        /* Sarray splitting by lines */
+    str1 = (char *)l_binaryRead("kernel_reg.c", &size1);
+    sa1 = sarrayCreateLinesFromString(str1, 0);
+    sa2 = sarrayConcatUniformly(sa1, 6, 0);  /* into 6 strings */
+    sa3 = sarrayCreate(0);
+    for (i = 0; i < 6; i++) {
+        str2 = sarrayGetString(sa2, i, L_NOCOPY);
+        sa4 = sarrayCreateLinesFromString(str2, 0);
+        sarrayJoin(sa3, sa4);
+        sarrayDestroy(&sa4);
+    }
+    sa5 = sarrayConcatUniformly(sa3, 6, 0);  /* same as sa2 ? */
+    sarrayWriteMem((l_uint8 **)&str3, &size1, sa2);
+    sarrayWriteMem((l_uint8 **)&str4, &size2, sa5);
+    regTestWriteDataAndCheck(rp, str3, size1, ".sa");  /* 24 */
+    regTestWriteDataAndCheck(rp, str4, size2, ".sa");  /* 25 */
+    regTestCompareFiles(rp, 24, 25);  /* 26 */
+    sarrayDestroy(&sa1);
+    sarrayDestroy(&sa2);
+    sarrayDestroy(&sa3);
+    sarrayDestroy(&sa4);
+    sarrayDestroy(&sa5);
+    lept_free(str1);
+    lept_free(str3);
+    lept_free(str4);
+
     return regTestCleanup(rp);
 }
-
diff --git a/src/allheaders.h b/src/allheaders.h
index 04a43ae..d960292 100644
--- a/src/allheaders.h
+++ b/src/allheaders.h
@@ -2379,6 +2379,7 @@ LEPT_DLL extern l_int32 sarrayGetRefcount ( SARRAY *sa );
 LEPT_DLL extern l_ok sarrayChangeRefcount ( SARRAY *sa, l_int32 delta );
 LEPT_DLL extern char * sarrayToString ( SARRAY *sa, l_int32 addnlflag );
 LEPT_DLL extern char * sarrayToStringRange ( SARRAY *sa, l_int32 first, l_int32 nstrings, l_int32 addnlflag );
+LEPT_DLL extern SARRAY * sarrayConcatUniformly ( SARRAY *sa, l_int32 n, l_int32 addnlflag );
 LEPT_DLL extern l_ok sarrayJoin ( SARRAY *sa1, SARRAY *sa2 );
 LEPT_DLL extern l_ok sarrayAppendRange ( SARRAY *sa1, SARRAY *sa2, l_int32 start, l_int32 end );
 LEPT_DLL extern l_ok sarrayPadToSameSize ( SARRAY *sa1, SARRAY *sa2, const char *padstring );
diff --git a/src/sarray1.c b/src/sarray1.c
index 8aa5d77..15952df 100644
--- a/src/sarray1.c
+++ b/src/sarray1.c
@@ -55,6 +55,9 @@
  *          char      *sarrayToString()
  *          char      *sarrayToStringRange()
  *
+ *      Concatenate strings uniformly within the sarray
+ *          SARRAY    *sarrayConcatUniformly()
+ *
  *      Join 2 sarrays
  *          l_int32    sarrayJoin()
  *          l_int32    sarrayAppendRange()
@@ -802,7 +805,7 @@ sarrayToString(SARRAY  *sa,
  *
  * <pre>
  * Notes:
- *      (1) Concatenates the specified strings inthe sarray, preserving
+ *      (1) Concatenates the specified strings in the sarray, preserving
  *          all white space.
  *      (2) If addnlflag != 0, adds either a '\n' or a ' ' after
  *          each substring.
@@ -877,6 +880,65 @@ l_int32  n, i, last, size, index, len;
 }
 
 
+/*----------------------------------------------------------------------*
+ *           Concatenate strings uniformly within the sarray            *
+ *----------------------------------------------------------------------*/
+/*!
+ * \brief   sarrayConcatUniformly()
+ *
+ * \param[in]    sa          string array
+ * \param[in]    n           number of strings in output sarray
+ * \param[in]    addnlflag   flag: 0 adds nothing to each substring
+ *                                 1 adds '\n' to each substring
+ *                                 2 adds ' ' to each substring
+ * \return  dest sarray, or NULL on error
+ *
+ * <pre>
+ * Notes:
+ *      (1) Divides the sarray into %n essentially equal sets of strings,
+ *          concatenates each set individually, and makes an output
+ *          sarray with the %n concatenations.
+ *      (2) If addnlflag != 0, adds either a '\n' or a ' ' after
+ *          each substring.
+ * </pre>
+ */
+SARRAY *
+sarrayConcatUniformly(SARRAY  *sa,
+                      l_int32  n,
+                      l_int32  addnlflag)
+{
+l_int32  i, first, ntot, nstr;
+char    *str;
+NUMA    *na;
+SARRAY  *saout;
+
+    PROCNAME("sarrayConcatUniformly");
+
+    if (!sa)
+        return (SARRAY *)ERROR_PTR("sa not defined", procName, NULL);
+    ntot = sarrayGetCount(sa);
+    if (n < 1)
+        return (SARRAY *)ERROR_PTR("n must be >= 1", procName, NULL);
+    if (n > ntot) {
+        L_ERROR("n = %d > ntot = %d\n", procName, n, ntot);
+        return NULL;
+    }
+    if (addnlflag != 0 && addnlflag != 1 && addnlflag != 2)
+        return (SARRAY *)ERROR_PTR("invalid addnlflag", procName, NULL);
+
+    saout = sarrayCreate(0);
+    na = numaGetUniformBinSizes(ntot, n);
+    for (i = 0, first = 0; i < n; i++) {
+        numaGetIValue(na, i, &nstr);
+        str = sarrayToStringRange(sa, first, nstr, addnlflag);
+        sarrayAddString(saout, str, L_INSERT);
+        first += nstr;
+    }
+    numaDestroy(&na);
+    return saout;
+}
+
+
 /*----------------------------------------------------------------------*
  *                           Join 2 sarrays                             *
  *----------------------------------------------------------------------*/
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
