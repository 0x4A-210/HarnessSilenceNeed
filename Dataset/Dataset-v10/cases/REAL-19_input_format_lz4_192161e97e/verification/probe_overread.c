/* REAL-12 (lz4 compress_frame_fuzzer) minimal repro.
 *
 * The harness constructs the data producer with:
 *     FUZZ_dataProducer_create(data, LZ4_compressBound(size));
 * The 2nd argument is the producer's "size" field, which
 * FUZZ_dataProducer_retrieve32() later uses to read the last 4 bytes:
 *     return *(data + size - 4);
 * LZ4_compressBound(n) > n, so with the inflated size the read lands past
 * the end of the real input buffer -> heap-buffer-overflow (explicit
 * crash under ASan).  The fix passes `size` itself.
 *
 * This probe demonstrates the mapping error concretely by printing the
 * byte range [size-4, size) that retrieve32 reads:
 *   OLD: read offset exceeds the real buffer length (out of bounds)
 *   FIX: read offset is the last 4 real bytes (in bounds)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* mimics LZ4_compressBound(n): always > n for n > 0 */
static size_t compressBound(size_t n) { return 2 * n + 16; }

int main(int argc, char **argv) {
    int fixed = (argc > 1 && argv[1][0] == 'f');
    size_t real_size = 8;
    unsigned char *data = (unsigned char*)malloc(real_size);
    for (size_t i = 0; i < real_size; i++) data[i] = (unsigned char)('A' + i);

    size_t producer_size = fixed ? real_size : compressBound(real_size);
    size_t read_start = producer_size >= 4 ? producer_size - 4 : 0;
    printf("%s: real buffer = %zu bytes; producer->size = %zu; retrieve32 reads [%zu, %zu)\n",
           fixed ? "FIX" : "OLD", real_size, producer_size, read_start, producer_size);
    printf("    -> %s\n",
           read_start + 4 <= real_size
               ? "in-bounds (last 4 real bytes)"
               : "OUT OF BOUNDS (reads past the real input buffer)");
    free(data);
    return 0;
}
