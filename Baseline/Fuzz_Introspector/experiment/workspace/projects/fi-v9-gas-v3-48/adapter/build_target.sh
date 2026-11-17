#!/bin/bash
set -euxo pipefail
# Source and target are selected only from the neutral case metadata.
cd "$PROJECT_DIR"
case "$PROJECT" in
zlib)
 ./configure --static; make -j3 libz.a
 $CC $CFLAGS -I. -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o libz.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
json-c)
 if [ -f CMakeLists.txt ]; then
  cmake -S . -B /work/build -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF
  cmake --build /work/build -j3 --target json-c
  archive=/work/build/libjson-c.a; includes=-I/work/build
 else
  autoreconf -fi; ./configure --disable-shared; make -j3
  archive=.libs/libjson-c.a; includes=-I.
 fi
 $CXX $CXXFLAGS -std=c++11 -I. $includes "$HARNESS_FILE" "$archive" $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
libyaml)
 ./bootstrap; ./configure --disable-shared; make -j3
 $CC $CFLAGS -I/src -Iinclude -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o src/.libs/libyaml.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
pugixml)
 $CXX $CXXFLAGS "$HARNESS_FILE" src/pugixml.cpp $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
cjson)
 cmake -S . -B /work/build -DBUILD_SHARED_LIBS=OFF -DENABLE_CJSON_TEST=OFF
 cmake --build /work/build -j3
 $CXX $CXXFLAGS "$HARNESS_FILE" -I/work/build /work/build/libcjson.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
cmark)
 cmake -S . -B /work/build
 cmake --build /work/build -j3 --target cmark_static
 $CC $CFLAGS -Isrc -I/work/build/src -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o /work/build/src/libcmark.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
md4c)
 cmake -S . -B /work/build -DBUILD_SHARED_LIBS=OFF
 cmake --build /work/build -j3
 $CC $CFLAGS -Isrc -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o /work/build/src/libmd4c-html.a /work/build/src/libmd4c.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
tinyxml2)
 $CXX $CXXFLAGS -std=c++11 -I. "$HARNESS_FILE" tinyxml2.cpp $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
tinyobjloader)
 cmake -S . -B /work/build -DBUILD_SHARED_LIBS=OFF
 cmake --build /work/build -j3 --target "$TARGET"
 cp "/work/build/$TARGET" "$OUT/$TARGET";;
utf8proc)
 cmake -S . -B /work/build -DUTF8PROC_ENABLE_TESTING=ON -DLIB_FUZZING_ENGINE="$LIB_FUZZING_ENGINE"
 cmake --build /work/build -j3 --target fuzzer
 cp /work/build/fuzzer "$OUT/$TARGET";;
nlohmann-json)
 if [ -d tests/src ]; then d=tests; else d=test; fi
 make -j3 -C "$d" FUZZER_ENGINE="$LIB_FUZZING_ENGINE" "$TARGET"
 cp "$d/$TARGET" "$OUT/$TARGET";;
zstd)
 cd tests/fuzz
 make -j3 "$TARGET" LIB_FUZZING_ENGINE="$LIB_FUZZING_ENGINE"
 cp "$TARGET" "$OUT/$TARGET";;
lz4)
 make -j3 -C ossfuzz "$TARGET" LIB_FUZZING_ENGINE="$LIB_FUZZING_ENGINE"
 cp "ossfuzz/$TARGET" "$OUT/$TARGET";;
miniz)
 cmake -S . -B /work/build -DAMALGAMATE_SOURCES=ON -DBUILD_SHARED_LIBS=OFF -DBUILD_FUZZERS=ON
 cmake --build /work/build -j3 --target miniz
 $CC $CFLAGS -I/work/build/amalgamation -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o /work/build/libminiz.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
jansson)
 if [ "$SANITIZER" = introspector ]; then sed -i 's/--default-symver/-flto/g' configure.ac; fi
 autoreconf -fi; ./configure --enable-ossfuzzers; make -j3 -C src; make -j3 -C test/ossfuzz "$TARGET"
 cp "test/ossfuzz/$TARGET" "$OUT/$TARGET";;
libucl)
 ./autogen.sh --force; ./configure; make -j3
 $CC $CFLAGS -DHAVE_CONFIG_H -I. -Isrc -Iinclude -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o src/.libs/libucl.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
libcbor)
 cmake -S . -B /work/build -DBUILD_SHARED_LIBS=OFF -DWITH_EXAMPLES=OFF -DWITH_TESTS=OFF
 cmake --build /work/build -j3
 $CXX $CXXFLAGS -Isrc -I/work/build -I/work/build/src "$HARNESS_FILE" /work/build/src/libcbor.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
nghttp2)
 autoreconf -i; ./configure --enable-lib-only; make -j3
 $CXX $CXXFLAGS -std=c++11 -Ilib/includes "$HARNESS_FILE" lib/.libs/libnghttp2.a $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
c-ares)
 export CFLAGS="${CFLAGS/-DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION/}"
 ./buildconf; ./configure --enable-debug
 if [ -f src/lib/Makefile ]; then libdir=src/lib; else libdir=.; fi
 make -j3 -C "$libdir" libcares.la
 $CC $CFLAGS -I. -Iinclude -Isrc/lib -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o "$libdir/.libs/libcares.a" $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
libxml2)
 ./autogen.sh --disable-shared --without-debug --without-http --without-python
 make -j3
 cd fuzz; make fuzz.o "$TARGET.o"
 $CXX $CXXFLAGS "$TARGET.o" fuzz.o ../.libs/libxml2.a -Wl,-Bstatic -lz -llzma -Wl,-Bdynamic $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
libpng)
 sed -i -e 's/option STDIO/option STDIO disabled/' -e 's/option WARNING /option WARNING disabled/' -e 's/option WRITE enables WRITE_INT_FUNCTIONS/option WRITE disabled/' scripts/pnglibconf.dfa
 autoreconf -fi; ./configure; make -j3 libpng16.la
 $CXX $CXXFLAGS -std=c++11 -I. "$HARNESS_FILE" .libs/libpng16.a -lz $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
libspng)
 if [ -f spng/spng.c ]; then
  $CC $CFLAGS -c spng/spng.c -o /work/spng.o
  $CXX $CXXFLAGS -std=c++11 -DSPNGT_HAVE_FMEMOPEN=1 "$HARNESS_FILE" /work/spng.o -lz $LIB_FUZZING_ENGINE -o "$OUT/$TARGET"
 else
  meson --buildtype=plain --default-library static /work/build
  ninja -C /work/build
  $CXX $CXXFLAGS -std=c++11 -I. "$HARNESS_FILE" /work/build/libspng.a -lz $LIB_FUZZING_ENGINE -o "$OUT/$TARGET"
 fi;;
flac)
 cmake -S . -B /work/build -DBUILD_PROGRAMS=ON -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF -DWITH_OGG=OFF -DINSTALL_MANPAGES=OFF -DCMAKE_BUILD_TYPE=Debug
 cmake --build /work/build -j3 --target FLAC getopt replaygain_synthesis utf8 grabbag replaygain_analysis
 for unit in analyze decode encode foreign_metadata local_string_utils utils vorbiscomment; do
  $CC $CFLAGS -DHAVE_CONFIG_H -I/work/build -Iinclude -Isrc -Isrc/flac -c "src/flac/$unit.c" -o "/work/$unit.o"
 done
 $CC $CFLAGS -DHAVE_CONFIG_H -I/work/build -Iinclude -Isrc -Isrc/share -Isrc/share/getopt -Isrc/share/grabbag -Ioss-fuzz -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o /work/{analyze,decode,encode,foreign_metadata,local_string_utils,utils,vorbiscomment}.o /work/build/src/libFLAC/libFLAC.a /work/build/src/share/{getopt/libgetopt,replaygain_synthesis/libreplaygain_synthesis,utf8/libutf8,grabbag/libgrabbag,replaygain_analysis/libreplaygain_analysis}.a -lm -lz $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
jq)
 autoreconf -fi; ./configure --with-oniguruma=builtin; make -j3
 if [ -f vendor/oniguruma/src/.libs/libonig.a ]; then
  onig=vendor/oniguruma/src/.libs/libonig.a
 else
  onig=modules/oniguruma/src/.libs/libonig.a
 fi
 $CXX $CXXFLAGS -I./src "$HARNESS_FILE" .libs/libjq.a "$onig" $LIB_FUZZING_ENGINE -o "$OUT/$TARGET";;
mbedtls)
 perl scripts/config.pl set MBEDTLS_PLATFORM_TIME_ALT || python3 scripts/config.py set MBEDTLS_PLATFORM_TIME_ALT
 make generated_files >/dev/null 2>&1 || { make -C library generated_files; make -C programs generated_files; }
 cmake -S . -B /work/build -DENABLE_TESTING=OFF -DMBEDTLS_FATAL_WARNINGS=OFF
 cmake --build /work/build -j3 --target "$TARGET"
 cp "/work/build/programs/fuzz/$TARGET" "$OUT/$TARGET";;
postgresql)
 cp -r /src/fuzzer src/backend/
 git apply /src/add_fuzzers.diff
 if [ ! -f "$OUT/data/PG_VERSION" ]; then
  useradd fuzzuser
  mkdir -p bootstrap
  chown -R fuzzuser "$PROJECT_DIR"
  cd bootstrap
  CC=clang CXX=clang++ CFLAGS='-O1 -g -Wno-error=implicit-function-declaration' CXXFLAGS='-O1 -g' su fuzzuser -c '../configure'
  su fuzzuser -c 'make -j3 -C src/backend/fuzzer createdb'
  cp -r src/backend/fuzzer/temp/data "$OUT/"
  cp -r tmp_install "$OUT/"
  cd ..
 fi
 mkdir -p bld; cd bld
 ../configure
 make -j3
 make -j3 -C src/backend/fuzzer "$TARGET"
 cp "src/backend/fuzzer/$TARGET" "$OUT/$TARGET";;
binutils-gas)
 ./configure --disable-gdb --disable-gdbserver --disable-gdbsupport --disable-libdecnumber --disable-readline --disable-sim --disable-libbacktrace --disable-gas --disable-ld --disable-werror --enable-targets=all
 make -j3 MAKEINFO=true all-opcodes
 cd gas
 # Match the supplied OSS-Fuzz recipe: GAS has its own native configuration.
 # The top-level --enable-targets=all otherwise adds emulation objects that
 # are not part of the recipe's native-GAS harness link command.
 ./configure --disable-werror
 make -j3 MAKEINFO=true
 sed 's/main (int argc/old_main32 (int argc, char **argv);\nint old_main32 (int argc/' as.c > fuzz_as.h
 rm -f as.o
 ar r libar.a *.o
 $CC $CFLAGS -DHAVE_CONFIG_H -I. -I../bfd -I./config -I../include -I.. -I../zlib -DLOCALEDIR='"/usr/local/share/locale"' -c "$HARNESS_FILE" -o fuzz_as.o
 $CXX $CXXFLAGS $LIB_FUZZING_ENGINE -o "$OUT/$TARGET" fuzz_as.o libar.a config/tc-i386.o config/obj-elf.o config/atof-ieee.o ../opcodes/.libs/libopcodes.a ../bfd/.libs/libbfd.a ../libiberty/libiberty.a -L../zlib -lz;;
pcre2)
 ./autogen.sh
 ./configure --enable-fuzz-support --enable-never-backslash-C --with-match-limit=1000 --with-match-limit-depth=1000 --enable-jit --enable-pcre2-16 --enable-pcre2-32
 make -j3
 $CXX $CXXFLAGS -o "$OUT/$TARGET" $LIB_FUZZING_ENGINE .libs/libpcre2-fuzzsupport.a .libs/libpcre2-8.a
 cp pcre2_fuzzer.dict pcre2_fuzzer.options "$OUT/";;
xz)
 cmake -S . -B /work/build -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=None -DXZ_NLS=OFF -DENABLE_NLS=OFF -DXZ_TOOL_XZ=OFF -DXZ_TOOL_XZDEC=OFF -DXZ_TOOL_LZMADEC=OFF -DXZ_TOOL_LZMAINFO=OFF -DXZ_TOOL_SCRIPTS=OFF -DXZ_DOC=OFF -DBUILD_TESTING=OFF -DXZ_SANDBOX=no
 cmake --build /work/build -j3 --target liblzma
 mkdir -p src/liblzma/.libs; cp /work/build/liblzma.a src/liblzma/.libs/liblzma.a
 make -C tests/ossfuzz "$TARGET"
 test -f "$OUT/$TARGET";;
fmt)
 cmake -S . -B /work/build -DCMAKE_BUILD_TYPE=Debug -DFMT_DOC=OFF -DFMT_TEST=OFF -DFMT_FUZZ=ON -DFMT_FUZZ_LINKMAIN=OFF -DFMT_FUZZ_LDFLAGS="$LIB_FUZZING_ENGINE"
 cmake --build /work/build -j3 --target "$TARGET"
 cp "/work/build/bin/$TARGET" "$OUT/$TARGET";;
expat)
 cd expat
 cmake -S . -B /work/build -DEXPAT_BUILD_TESTS=OFF -DEXPAT_BUILD_TOOLS=OFF -DEXPAT_BUILD_EXAMPLES=OFF -DEXPAT_BUILD_DOCS=OFF -DEXPAT_SHARED_LIBS=OFF
 cmake --build /work/build -j3 --target expat
 $CC $CFLAGS -DENCODING_FOR_FUZZING=UTF-8 -Ilib -I/work/build -c "$HARNESS_FILE" -o /work/harness.o
 $CXX $CXXFLAGS /work/harness.o -o "$OUT/$TARGET" $LIB_FUZZING_ENGINE /work/build/libexpat.a;;
*)
 # Remaining recipes preserve the supplied build configuration verbatim.
 bash -eux /src/dataset-build.sh;;
esac
