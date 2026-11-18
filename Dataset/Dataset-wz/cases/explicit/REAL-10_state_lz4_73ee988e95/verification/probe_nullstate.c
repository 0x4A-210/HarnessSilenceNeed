/* REAL-10 (lz4 round_trip_stream_fuzzer) minimal repro.
 *
 * The harness state_create() creates a cross-call state:
 *     state.cstream    = LZ4_createStream();      // succeeds
 *     state.cstreamHC  = LZ4_createStreamHC();    // may fail under OOM
 *     FUZZ_ASSERT(state.cstream);                 // BUG: checks cstream AGAIN
 *     state.dstream    = LZ4_createStreamDecode();
 *     FUZZ_ASSERT(state.dstream);
 * then state_reset() unconditionally calls
 *     LZ4_resetStreamHC_fast(state->cstreamHC, level)
 * which dereferences cstreamHC.  When the injection makes
 * LZ4_createStreamHC() return NULL, the mis-asserted variable means the
 * NULL slips through and state_reset() dereferences NULL -> crash.
 *
 * The FIX asserts state.cstreamHC instead, which catches the NULL
 * (FUZZ_ASSERT aborts with a clear "Assertion failed" message).
 *
 * This probe reproduces the two behaviors:
 *   OLD: NULL pointer dereference -> crash (signal)
 *   FIX: assert catches it -> abort with message -> also non-zero, but the
 *        failure is the assert (correct), not a NULL deref.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { void *cstream; void *cstreamHC; void *dstream; } state_t;

static void *create_ok(void) { return malloc(16); }      /* succeeds        */
static void *create_null(void) { return NULL; }          /* OOM injection  */

/* reset dereferences cstreamHC exactly like LZ4_resetStreamHC_fast(NULL..) */
static void reset_deref(state_t *s, int level) {
    printf("reset: dereferencing cstreamHC=%p level=%d\n", s->cstreamHC, level);
    fflush(stdout);
    if (!s->cstreamHC) {
        /* mimic a library helper that blindly uses the handle */
        int *p = NULL;
        (void)level;
        printf("about to touch...");
        fflush(stdout);
        *p = 0;   /* NULL deref -> crash */
    }
}

#define FUZZ_ASSERT(cond) \
  ((cond) ? (void)0 : (fprintf(stderr, "Assertion `%s' failed\n", #cond), abort()))

int main(int argc, char **argv) {
    int fixed = (argc > 1 && strcmp(argv[1], "fix") == 0);
    state_t s;
    s.cstream   = create_ok();
    FUZZ_ASSERT(s.cstream);
    s.cstreamHC = create_null();          /* OOM: returns NULL */
    if (fixed)
        FUZZ_ASSERT(s.cstreamHC);         /* FIX: abort here (correct) */
    else
        FUZZ_ASSERT(s.cstream);           /* OLD: mis-asserted, always true */
    s.dstream   = create_ok();
    FUZZ_ASSERT(s.dstream);

    reset_deref(&s, 12);
    printf("survived\n");
    return 0;
}
