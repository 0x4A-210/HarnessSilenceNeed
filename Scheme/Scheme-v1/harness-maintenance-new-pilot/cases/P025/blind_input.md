# Case ID

P025

## Existing Fuzz Harness H0

### `prog/fuzzing/boxfunc5_fuzzer.cc`

~~~~cpp
#include "leptfuzz.h"

extern "C" int
LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) { 
	if(size<3) return 0;
 
	leptSetStdNullHandler();

	BOXA *boxa_payload, *boxa1;
	boxa_payload = boxaReadMem(data, size);
	if(boxa_payload == NULL) return 0;

	l_float32  fvarp, fvarm, devw, devh;
	l_float32  del_evenodd, rms_even, rms_odd, rms_all;
	l_int32    isame;

	boxa1 = boxaConstrainSize(boxa_payload, 0,
				  L_ADJUST_LEFT_AND_RIGHT, 
				  0, L_ADJUST_TOP_AND_BOT);
	boxaDestroy(&boxa1);
	
	boxa1 = boxaReconcileAllByMedian(boxa_payload,
					 L_ADJUST_LEFT_AND_RIGHT,
					 L_ADJUST_TOP_AND_BOT, 50,
					 0, NULL);
	boxaDestroy(&boxa1);
	
	boxa1 = boxaReconcileEvenOddHeight(boxa_payload, L_ADJUST_TOP, 80,
					   L_ADJUST_CHOOSE_MIN, 1.05, 1);
	boxaDestroy(&boxa1);

	boxa1 = boxaReconcilePairWidth(boxa_payload, 2,
				       L_ADJUST_CHOOSE_MIN,
				       0.5, NULL);
	boxaDestroy(&boxa1);

	boxaSizeConsistency1(boxa_payload, L_CHECK_HEIGHT,
			     0.0, 0.0, &fvarp, &fvarm, &isame);

	boxaSizeConsistency2(boxa_payload, &devw, &devh, 0);

	boxaSizeVariation(boxa_payload, L_SELECT_WIDTH, &del_evenodd,
                  	  &rms_even, &rms_odd, &rms_all);

	boxa1 = boxaSmoothSequenceMedian(boxa_payload, 10,
					 L_SUB_ON_LOC_DIFF,
					 80, 20, 1);
	boxaDestroy(&boxa1);
	boxaDestroy(&boxa_payload);
	return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/src/tiffio.c b/src/tiffio.c
index a2a32d3..2b0c60f 100644
--- a/src/tiffio.c
+++ b/src/tiffio.c
@@ -77,13 +77,24 @@
  *      static TIFF      *openTiff()
  *
  *     Memory I/O: reading memory --> pix and writing pix --> memory
- *             [10 static helper functions]
- *             PIX       *pixReadMemTiff();
- *             PIX       *pixReadMemFromMultipageTiff();
- *             PIXA      *pixaReadMemMultipageTiff()    [ special top level ]
- *             l_int32    pixaWriteMemMultipageTiff()   [ special top level ]
- *             l_int32    pixWriteMemTiff();
- *             l_int32    pixWriteMemTiffCustom();
+ *        Ten static low-level memstream functions
+ *           static L_MEMSTREAM  *memstreamCreateForRead()
+ *           static L_MEMSTREAM  *memstreamCreateForWrite()
+ *           static tsize_t       tiffReadCallback()
+ *           static tsize_t       tiffWriteCallback()
+ *           static toff_t        tiffSeekCallback()
+ *           static l_int32       tiffCloseCallback()
+ *           static toff_t        tiffSizeCallback()
+ *           static l_int32       tiffMapCallback()
+ *           static void          tiffUnmapCallback()
+ *           static TIFF         *fopenTiffMemstream()
+ *
+ *           PIX       *pixReadMemTiff();
+ *           PIX       *pixReadMemFromMultipageTiff();
+ *           PIXA      *pixaReadMemMultipageTiff()    [ special top level ]
+ *           l_int32    pixaWriteMemMultipageTiff()   [ special top level ]
+ *           l_int32    pixWriteMemTiff();
+ *           l_int32    pixWriteMemTiffCustom();
  *
  *  Note 1: To include all necessary functions, use libtiff version 3.7.4
  *          (from 2005) or later.
@@ -2582,6 +2593,8 @@ TIFF         *tif;
         mstream = memstreamCreateForRead(*pdata, *pdatasize);
     else
         mstream = memstreamCreateForWrite(pdata, pdatasize);
+    if (!mstream)
+        return (TIFF *)ERROR_PTR("mstream not made", procName, NULL);
 
     TIFFSetWarningHandler(NULL);  /* disable warnings */
     TIFFSetErrorHandler(NULL);  /* disable error messages */
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
