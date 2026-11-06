# Case ID

C033

## Existing Fuzz Harness H0

### `prog/fuzzing/dewarp_fuzzer.cc`

~~~~cpp
#include "leptfuzz.h"

extern "C" int
LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    if(size<3) return 0;

    PIX *pixs, *pixd;
    L_DEWARPA *dewa1;
    PIXAC *pixac;
    SARRAY *sa;

    leptSetStdNullHandler();

    pixs = pixReadMemSpix(data, size);
    if(pixs==NULL) return 0;
    
    dewarpSinglePage(pixs, 0, 1, 1, 0, &pixd, NULL, 1);
	
    pixac = pixacompReadMem(data, size);
    dewa1 = dewarpaCreateFromPixacomp(pixac, 1, 0, 10, -1);
    
    dewarpaDestroy(&dewa1);
    pixacompDestroy(&pixac);
    pixDestroy(&pixs);
    pixDestroy(&pixd);
    return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/src/sarray1.c b/src/sarray1.c
index f67c14c..76f6690 100644
--- a/src/sarray1.c
+++ b/src/sarray1.c
@@ -1884,7 +1884,7 @@ SARRAY *
 getFilenamesInDirectory(const char  *dirname)
 {
 char            dir[PATH_MAX + 1];
-char           *realdir, *stat_path, *ignore;
+char           *realdir, *stat_path;
 size_t          size;
 SARRAY         *safiles;
 DIR            *pdir;
@@ -1896,12 +1896,26 @@ struct stat     st;
 
     if (!dirname)
         return (SARRAY *)ERROR_PTR("dirname not defined", procName, NULL);
-
-        /* It's nice to ignore directories.  fstatat() works with relative
-           directory paths, but stat() requires using the absolute path.
-           Also, do not pass NULL as the second parameter to realpath();
-           use a buffer of sufficient size. */
-    ignore = realpath(dirname, dir);  /* see note above */
+    if (dirname[0] == '\0')
+        return (SARRAY *)ERROR_PTR("dirname is empty", procName, NULL);
+
+        /* Who would have thought it was this fiddly to open a directory
+           and get the files inside?  fstatat() works with relative
+           directory paths, and stat() requires using the absolute path.
+           realpath works as follows for files and directories:
+            * If the file or directory exists, realpath returns its path;
+              else it returns NULL.
+            * If the second arg to realpath is passed in, the canonical path
+              is returned there.  Use a buffer of sufficient size.  If the
+              second arg is NULL, the path is malloc'd and returned if the
+              file or directory exists.
+           We pass in a buffer for the second arg, and check that the canonical
+           directory path was made.  The existence of the directory is checked
+           later, after its actual path is returned by genPathname().  */
+    dir[0] = '\0';  /* init empty in case realpath() fails to write it */
+    realpath(dirname, dir);
+    if (dir[0] == '\0')
+        return (SARRAY *)ERROR_PTR("dir not made", procName, NULL);
     realdir = genPathname(dir, NULL);
     if ((pdir = opendir(realdir)) == NULL) {
         LEPT_FREE(realdir);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
