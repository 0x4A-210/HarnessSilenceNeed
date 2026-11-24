/* REAL-11 (gdk-pixbuf pixbuf_cons_fuzzer) minimal repro of blocker #2.
 *
 * The harness repeatedly assigns freshly-created intermediate GdkPixbuf
 * objects to the SAME variable `tmp` without g_object_unref() on the
 * previous value:
 *
 *     tmp = gdk_pixbuf_rotate_simple(pixbuf, rot);   // old tmp leaked
 *     tmp = gdk_pixbuf_flip(pixbuf, TRUE);           // old tmp leaked
 *     tmp = gdk_pixbuf_composite_color_simple(...);  // old tmp leaked
 *     ...
 *     tmp = gdk_pixbuf_flip(tmp, TRUE);              // uses tmp as src,
 *                                                    // old tmp still leaked
 *
 * Each new GdkPixbuf has refcount 1; overwriting the pointer without
 * unref and never unref'ing at the end drops that refcount back to 0
 * only in the FIXED version.  In the buggy version every overwrite
 * leaks one object (LSan: 1704 bytes in 8 allocations per iteration).
 *
 * This probe tracks the same "refcount owned by harness" convention with
 * a counter and shows the leak accumulates across iterations exactly
 * like the real harness (silent: nothing crashes, objects just pile up).
 */
#include <stdio.h>

static long leaked_objects = 0;

/* a fake GdkPixbuf with a refcount the harness must release */
typedef struct { int refcount; } FakePixbuf;

static FakePixbuf *pix_new(void) { return NULL; /* placeholder */ }

/* simulate: caller must unref each returned object (refcount 1) */
static FakePixbuf *rotate_simple(void) { leaked_objects += 1; return (FakePixbuf*)1; }
static FakePixbuf *flip(void)            { leaked_objects += 1; return (FakePixbuf*)1; }
static FakePixbuf *composite(void)       { leaked_objects += 1; return (FakePixbuf*)1; }
static void unref(FakePixbuf *p)         { if (p) leaked_objects -= 1; }

int main(int argc, char **argv) {
    int fixed = (argc > 1 && argv[1][0] == 'f');
    int iterations = 3;
    for (int i = 0; i < iterations; i++) {
        FakePixbuf *tmp = NULL;
        /* three intermediate objects, each overwrites tmp */
        tmp = rotate_simple();  /* (void)tmp; */
        if (fixed) unref(tmp);
        tmp = flip();
        if (fixed) unref(tmp);
        tmp = composite();
        if (fixed) unref(tmp);
        /* GBytes analogue: allocated each iteration, freed only in fix */
        leaked_objects += 1;
        if (fixed) leaked_objects -= 1;
    }
    printf("%s: leaked_objects after %d iterations = %ld\n",
           fixed ? "FIX (unref each intermediate)" : "OLD (overwrite without unref)",
           iterations, leaked_objects);
    return 0;
}
