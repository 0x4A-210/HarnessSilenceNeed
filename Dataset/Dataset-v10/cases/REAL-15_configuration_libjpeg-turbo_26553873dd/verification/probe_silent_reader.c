/* A compile-level probe demonstrating the silent degradation of the
 * libjpeg-turbo cjpeg fuzzer (REAL-08).
 *
 * This tiny standalone repro simulates what happens in src/cjpeg.c's
 * select_file_type(): each input-format reader is enabled only under a
 * *_SUPPORTED compile-time define.  When the defines are absent (the old
 * harness after M = 7fec5074f), the format-agnostic switch falls into the
 * default branch and rejects the input with a clean "unknown format" error.
 * The program still compiles and still exits 0 — nothing crashes — yet the
 * Targa/BMP/GIF/PPM readers are unreachable.
 *
 * Compile once WITH the defines (fixed config) and once WITHOUT (old
 * config).  Both binaries compile and run; only the WITH build can reach the
 * reader.  This is the source-level mechanism behind H = 26553873dda0's
 * "-DBMP_SUPPORTED -DGIF_SUPPORTED -DPPM_SUPPORTED -DTARGA_SUPPORTED".
 */
#include <stdio.h>

#ifdef TARGA_SUPPORTED
#define ENTER_READER(name) do { \
    printf("reader %s reached\n", name); \
    return 0; \
  } while (0)
#else
#define ENTER_READER(name) do { \
    printf("reader %s UNREACHABLE -> clean reject\n", name); \
    return 0; \
  } while (0)
#endif

int main(void) {
  char probe[4] = {'T', 'G', 'P', 'B'};
  (void)probe;
#ifdef TARGA_SUPPORTED
  ENTER_READER("targa");
#else
  ENTER_READER("targa");
#endif
  return 0;
}
