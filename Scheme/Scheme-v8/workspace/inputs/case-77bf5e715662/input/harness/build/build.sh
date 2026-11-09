# custom recipe: oss-fuzz build.sh needs protobuf (LPM fuzzer) which is unavailable offline;
# we build the plain libFuzzer harnesses exactly as expat's CMake does (ENCODING_FOR_FUZZING per encoding)
cd $SRC/expat/expat
mkdir -p b && cd b
cmake .. -DEXPAT_BUILD_TESTS=OFF -DEXPAT_BUILD_TOOLS=OFF -DEXPAT_BUILD_EXAMPLES=OFF -DEXPAT_BUILD_DOCS=OFF \
  -DEXPAT_SHARED_LIBS=OFF -DCMAKE_C_COMPILER=$CC -DCMAKE_C_FLAGS="$CFLAGS" -DCMAKE_CXX_COMPILER=$CXX >/dev/null
make -j2 expat
LIB=$(find . -name 'libexpat*.a' | head -1)
for f in ../fuzz/xml_parse_fuzzer.c ../fuzz/xml_parsebuffer_fuzzer.c; do
  [ -f $f ] || continue
  b=$(basename $f .c)
  $CC $CFLAGS -DENCODING_FOR_FUZZING=UTF-8 -I../lib -I. -c $f -o $b.o && \
  $CXX $CXXFLAGS $b.o -o $OUT/${b}_UTF-8 $LIB_FUZZING_ENGINE $LIB
done
