# custom recipe: fmt's in-tree libFuzzer targets (test/fuzzing) built through fmt's own CMake
# switches, as OSS-Fuzz does (OSS-Fuzz only gained a fmt project in 2020-10)
cd $SRC/fmt
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Debug -DFMT_DOC=Off -DFMT_TEST=Off -DFMT_FUZZ=On -DFMT_FUZZ_LINKMAIN=Off \
  -DFMT_FUZZ_LDFLAGS="$LIB_FUZZING_ENGINE" -DCMAKE_CXX_COMPILER=$CXX -DCMAKE_CXX_FLAGS="$CXXFLAGS" -DCMAKE_C_COMPILER=$CC >/dev/null
make -k -j2
find . -type f -perm -u+x \( -name 'fuzzer_*' -o -name '*-fuzzer' -o -name '*_fuzzer' \) -exec cp {} $OUT/ \;
