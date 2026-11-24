/* REAL-09 minimal repro, corrected to match readelf's actual behavior:
 *
 * - The decoder (readelf via process_file) allocates dump_ctf_* globals
 *   ONLY for inputs that contain a CTF section (rare).
 * - The harness frees those globals at the end of EVERY iteration,
 *   unconditionally.
 *
 * With the OLD (buggy) harness the globals are not nulled after free,
 * so on the next non-CTF iteration free() is called AGAIN on the same
 * (already freed) pointer -> double free -> crash. That is exactly
 * issue 27734 ("Abrt with empty stacktrace").
 *
 * With the FIX, the globals are set to NULL after free, so the next
 * free(NULL) is a no-op.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *dump_ctf_symtab_name;
static char *dump_ctf_strtab_name;
static char *dump_ctf_parent_name;

static void decoder_maybe_allocate(int has_ctf) {
    if (has_ctf) {
        dump_ctf_symtab_name = strdup("symtab");
        dump_ctf_strtab_name = strdup("strtab");
        dump_ctf_parent_name = strdup("parent");
    }
    /* else: decoder does NOT touch the globals */
}

static void harness_cleanup(int fix_nulls) {
    free(dump_ctf_symtab_name);
    if (fix_nulls) dump_ctf_symtab_name = NULL;
    free(dump_ctf_strtab_name);
    if (fix_nulls) dump_ctf_strtab_name = NULL;
    free(dump_ctf_parent_name);
    if (fix_nulls) dump_ctf_parent_name = NULL;
}

int main(int argc, char **argv) {
    int fix_nulls = (argc > 1 && strcmp(argv[1], "fix") == 0);
    /* iteration 0: CTF input -> decoder allocates; cleanup frees (dangling) */
    printf("iteration 0 (CTF input): decoder allocates\n");
    decoder_maybe_allocate(1);
    harness_cleanup(fix_nulls);
    /* iteration 1: non-CTF input -> decoder allocates NOTHING;
       cleanup frees the SAME dangling pointers again -> double free */
    printf("iteration 1 (non-CTF input): decoder allocates nothing, harness frees again\n");
    fflush(stdout);
    decoder_maybe_allocate(0);
    harness_cleanup(fix_nulls);
    printf("survived (no crash)\n");
    return 0;
}
