# custom recipe: autotools bootstrap needs autopoint (gettext), unavailable offline; build the same
# static liblzma with xz's CMake build, then run the unchanged tests/ossfuzz Makefile as build.sh does
cd $SRC/xz
mkdir -p cmbuild && cd cmbuild
cmake .. -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=None -DCMAKE_C_COMPILER=$CC -DCMAKE_C_FLAGS="$CFLAGS" \
  -DXZ_NLS=OFF -DENABLE_NLS=OFF -DXZ_TOOL_XZ=OFF -DXZ_TOOL_XZDEC=OFF -DXZ_TOOL_LZMADEC=OFF -DXZ_TOOL_LZMAINFO=OFF \
  -DXZ_TOOL_SCRIPTS=OFF -DXZ_DOC=OFF -DBUILD_TESTING=OFF -DXZ_SANDBOX=no >/dev/null
make -j2 liblzma
mkdir -p ../src/liblzma/.libs && cp liblzma.a ../src/liblzma/.libs/liblzma.a
cd ../tests/ossfuzz && make -k
cp fuzz_* $OUT/ 2>/dev/null; rm -f $OUT/*.c $OUT/*.h $OUT/*.o
find $SRC/xz/tests/files -name "*.lzma" -exec zip -ujq $OUT/fuzz_decode_alone_seed_corpus.zip "{}" \;
find $SRC/xz/tests/files -name "*.xz" -exec zip -ujq $OUT/fuzz_decode_stream_seed_corpus.zip "{}" \;
