# Case ID

P015

## Existing Fuzz Harness H0

### `prog/fuzzing/enhance_fuzzer.cc`

~~~~cpp
#include "string.h"
#include "leptfuzz.h"
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>


extern "C" int
LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
        if(size<3) return 0;
        PIX *pix, *pix0, *pix1, *pix2, *pix3, *pix4;

        leptSetStdNullHandler();

        pix = pixReadMem(data, size);
        if(pix==NULL) return 0;
        
        pix0 = pixModifyHue(NULL, pix, 0.01 + 0.05 * 1);
        pix1 = pixModifySaturation(NULL, pix, -0.9 + 0.1 * 1);
        pix2 = pixMosaicColorShiftRGB(pix, -0.1, 0.0, 0.0, 0.0999, 1);
        pix3 = pixMultConstantColor(pix, 0.7, 0.4, 1.3);
        pix4 = pixUnsharpMasking(pix, 3, 0.01 + 0.15 * 1);

        pixDestroy(&pix);
        pixDestroy(&pix0);
        pixDestroy(&pix1);
        pixDestroy(&pix2);
        pixDestroy(&pix3);
        pixDestroy(&pix4);
        return 0;	
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/src/readbarcode.c b/src/readbarcode.c
index 77c6774..71257be 100644
--- a/src/readbarcode.c
+++ b/src/readbarcode.c
@@ -858,7 +858,7 @@ numaQuantizeCrossingsByWidth(NUMA       *nas,
                              NUMA      **pnaohist,
                              l_int32     debugflag)
 {
-l_int32    i, n, ned, nod, iw, width;
+l_int32    i, n, ret, ned, nod, iw, width;
 l_float32  val, minsize, maxsize, factor;
 GPLOT     *gplot;
 NUMA      *naedist, *naodist, *naehist, *naohist, *naecent, *naocent;
@@ -875,7 +875,9 @@ NUMA      *naerange, *naorange, *naelut, *naolut, *nad;
         return (NUMA *)ERROR_PTR("binfract <= 0.0", procName, NULL);
 
         /* Get even and odd crossing distances */
-    numaGetCrossingDistances(nas, &naedist, &naodist, &minsize, &maxsize);
+    ret = numaGetCrossingDistances(nas, &naedist, &naodist, &minsize, &maxsize);
+    if (ret)
+        return (NUMA *)ERROR_PTR("crossing data not found", procName, NULL);
 
         /* Bin the spans in units of binfract * minsize.  These
          * units are convenient because they scale to make at least
diff --git a/src/readfile.c b/src/readfile.c
index f37bf12..51e58bf 100644
--- a/src/readfile.c
+++ b/src/readfile.c
@@ -633,7 +633,7 @@ l_int32  format;
 
     if (fread(&firstbytes, 1, 12, fp) != 12)
         return ERROR_INT("failed to read first 12 bytes of file", procName, 1);
-    firstbytes[12] = '\0';
+    firstbytes[12] = 0;
     rewind(fp);
 
     findFileFormatBuffer(firstbytes, &format);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
