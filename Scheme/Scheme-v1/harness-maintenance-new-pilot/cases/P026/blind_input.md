# Case ID

P026

## Existing Fuzz Harness H0

### `prog/fuzzing/pix_rotate_shear_fuzzer.cc`

~~~~cpp
// The fuzzer takes as input a buffer of bytes. The buffer is read in as:
// <angle>, <x_center>, <y_center>, and the remaining bytes will be read
// in as a <pix>. The image is then rotated by angle around the center. All
// inputs should not result in undefined behavior.
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include "leptfuzz.h"

// Set to true only for debugging; always false for production
static const bool DebugOutput = false;

namespace {

// Reads the front bytes of a data buffer containing `size` bytes as an int16_t,
// and advances the buffer forward [if there is sufficient capacity]. If there
// is insufficient capacity, this returns 0 and does not modify size or data.
int16_t ReadInt16(const uint8_t** data, size_t* size) {
  int16_t result = 0;
  if (*size >= sizeof(result)) {
    memcpy(&result, *data, sizeof(result));
    *data += sizeof(result);
    *size -= sizeof(result);
  }
  return result;
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  const int16_t angle = ReadInt16(&data, &size);
  const int16_t x_center = ReadInt16(&data, &size);
  const int16_t y_center = ReadInt16(&data, &size);

  leptSetStdNullHandler();

  // Don't do pnm format (which can cause timeouts) or
  // jpeg format (which can have uninitialized variables.
  // The format checker requires at least 12 bytes.
  if (size < 12) return EXIT_SUCCESS;
  int format;
  findFileFormatBuffer(data, &format);
  if (format == IFF_PNM || format == IFF_JFIF_JPEG) return EXIT_SUCCESS;

  Pix* pix = pixReadMem(reinterpret_cast<const unsigned char*>(data), size);
  if (pix == nullptr) {
    return EXIT_SUCCESS;
  }

  // Never in production
  if (DebugOutput) {
    L_INFO("w = %d, h = %d, d = %d\n", "fuzzer",
           pixGetWidth(pix), pixGetHeight(pix), pixGetDepth(pix));
  }

  constexpr float deg2rad = M_PI / 180.;
  Pix* pix_rotated = pixRotateShear(pix, x_center, y_center, deg2rad * angle,
                                    L_BRING_IN_WHITE);
  if (pix_rotated) {
    pixDestroy(&pix_rotated);
  }

  pixDestroy(&pix);
  return EXIT_SUCCESS;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/prog/cleanpdf.c b/prog/cleanpdf.c
index 0ed2e5e..ba8e8e5 100644
--- a/prog/cleanpdf.c
+++ b/prog/cleanpdf.c
@@ -99,7 +99,7 @@
 # endif  /* _MSC_VER || __MINGW32__ */
 #endif  /* _WIN32 */
 
-    /* Set to 1 to use pdftoppm; 0 for pdfimages */
+    /* Set to 1 to use pdftoppm (recommended); 0 for pdfimages */
 #define   USE_PDFTOPPM     1
 
 #include "string.h"
@@ -153,13 +153,11 @@ static char  mainName[] = "cleanpdf";
     }
     setLeptDebugOK(1);
 
-#if 1
         /* Get the names of the pdf files */
     if ((sa = getSortedPathnamesInDirectory(basedir, "pdf", 0, 0)) == NULL)
         return ERROR_INT("files not found", mainName, 1);
     sarrayWriteStderr(sa);
     n = sarrayGetCount(sa);
-#endif
 
         /* Rasterize: use either
          *     pdftoppm -r 300 fname outroot  (-r 300 renders output at 300 ppi)
@@ -177,12 +175,11 @@ static char  mainName[] = "cleanpdf";
          *    In some cases, it scrambles the order of the output pages
          *    and inserts extra images. */
     imagedir = stringJoin(basedir, "/image");
-#if 1
-#ifndef _WIN32
+  #ifndef _WIN32
     mkdir(imagedir, 0777);
-#else
+  #else
     _mkdir(imagedir);
-#endif  /* _WIN32 */
+  #endif  /* _WIN32 */
     for (i = 0; i < n; i++) {
         fname = sarrayGetString(sa, i, L_NOCOPY);
         splitPathAtDirectory(fname, NULL, &tail);
@@ -200,9 +197,7 @@ static char  mainName[] = "cleanpdf";
         ret = system(buf);   /* pdfimages or pdftoppm */
     }
     sarrayDestroy(&sa);
-#endif
 
-#if 1
         /* Clean, deskew and compress */
     sa = getSortedPathnamesInDirectory(imagedir, NULL, 0, 0);
     sarrayWriteStderr(sa);
@@ -240,9 +235,7 @@ static char  mainName[] = "cleanpdf";
         lept_free(basename);
     }
     sarrayDestroy(&sa);
-#endif
 
-#if 1
         /* Generate the pdf.  Compute the actual input resolution from
          * the pixel dimensions of the first image.  This will cause each
          * page to be printed to cover an 8.5 x 11 inch sheet of paper. */
@@ -255,8 +248,6 @@ static char  mainName[] = "cleanpdf";
         title = NULL;
     convertFilesToPdf(imagedir, "tif", res, 1.0, L_G4_ENCODE,
                       0, title, outfile);
-#endif
-
     return 0;
 }
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
