# Case ID

P019

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

  // Check for pnm format; this can cause timeouts.
  // The format checker requires at least 12 bytes.
  if (size < 12) return EXIT_SUCCESS;
  int format;
  findFileFormatBuffer(data, &format);
  if (format == IFF_PNM) return EXIT_SUCCESS;

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
diff --git a/src/jpegio.c b/src/jpegio.c
index 208cea1..993683d 100644
--- a/src/jpegio.c
+++ b/src/jpegio.c
@@ -103,12 +103,14 @@
  *    can extract just the 8 bpp luminance channel, using pixReadJpeg(),
  *    where you use L_JPEG_READ_LUMINANCE for the %hint arg.
  *
- *    How to fail to read if the data is corrupted
- *    ---------------------------------------------
- *    By default, if the low-level jpeg library functions do not abort,
- *    a pix will be returned, even if the data is corrupted and warnings
- *    are issued.  In order to be most likely to fail to read when there
- *    is data corruption, use L_JPEG_FAIL_ON_BAD_DATA in the %hint arg.
+ *    How to continue to read if the data is corrupted
+ *    ------------------------------------------------
+ *    By default, if data is corrupted we make every effort to fail
+ *    to return a pix.  (Failure is not always possible with bad
+ *    data, because in some situations, such as during arithmetic
+ *    decoding, the low-level jpeg library will not abort or raise
+ *    a warning.)  To attempt to ignore warnings and get a pix when data
+ *    is corrupted, use L_JPEG_CONTINUE_WITH_BAD_DATA in the %hint arg.
  *
  *    Compressing to memory and decompressing from memory
  *    ---------------------------------------------------
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
