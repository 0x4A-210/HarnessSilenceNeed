# custom recipe (8-bit target only, to save build time): same configure options as the
# date-pinned OSS-Fuzz build.sh for the 8-bit pcre2_fuzzer, without the 16/32-bit and link-size loops
cd $SRC/pcre2
./autogen.sh >/dev/null 2>&1 || autoreconf -fi >/dev/null 2>&1
DEPTH=--with-match-limit-depth=1000
./configure --help | grep -q match-limit-depth || DEPTH=--with-match-limit-recursion=1000
JIT=
./configure --help | grep -q enable-jit && [ -d src/sljit -o -d deps/sljit ] && JIT=--enable-jit
./configure --enable-fuzz-support --enable-never-backslash-C --with-match-limit=1000 $DEPTH $JIT --disable-shared >/dev/null
make -j2 all >/dev/null || make -j2 libpcre2-8.la libpcre2-fuzzsupport.la
$CXX $CXXFLAGS -o $OUT/pcre2_fuzzer $LIB_FUZZING_ENGINE .libs/libpcre2-fuzzsupport.a .libs/libpcre2-8.a
