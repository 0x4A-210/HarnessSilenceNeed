#!/bin/bash
set -euxo pipefail
jobs="${T6_BUILD_JOBS:-3}"

# This adapter is mounted as /src/build.sh in the pinned OSS-Fuzz builder.
# It deliberately builds only project libraries and the complete in-tree H0
# libFuzzer entrypoints. This avoids unrelated unit-test/toolchain failures.

case "${PROJECT_NAME}" in
  c-ares)
    cmake -S /src/c-ares -B /work/build \
      -DCARES_STATIC=ON -DCARES_SHARED=OFF -DCARES_BUILD_TESTS=OFF \
      -DCARES_BUILD_CONTAINER_TESTS=OFF -DCARES_BUILD_TOOLS=OFF
    cmake --build /work/build --parallel "${jobs}"
    lib="$(find /work/build -type f -name 'libcares.a' -print -quit)"
    test -n "${lib}"
    for spec in \
      "ares_parse_reply_fuzzer:test/ares-test-fuzz.c" \
      "ares_create_query_fuzzer:test/ares-test-fuzz-name.c"; do
      name="${spec%%:*}"
      source="${spec#*:}"
      test -f "/src/c-ares/${source}" || continue
      "${CC}" ${CFLAGS} -I/work/build -I/src/c-ares/include -I/src/c-ares/src/lib \
        -c "/src/c-ares/${source}" -o "/work/${name}.o"
      "${CXX}" ${CXXFLAGS} -std=c++11 "/work/${name}.o" \
        -o "/out/${name}" ${LIB_FUZZING_ENGINE} "${lib}" -pthread
    done
    ;;

  libplist)
    cd /src/libplist
    # git archive intentionally omits .git; provide the version input expected
    # by libplist's release-aware autoconf macro. It has no code semantics.
    printf '%s\n' '0.0.0-t6-archive' > .tarball-version
    autoreconf -fi
    mkdir -p /work/build
    cd /work/build
    /src/libplist/configure --without-cython --without-tests \
      --enable-static --disable-shared
    make -j"${jobs}"
    lib="$(find /work/build -type f -name 'libplist-2.0.a' -print -quit)"
    test -n "${lib}"
    for source in /src/libplist/fuzz/*_fuzzer.cc; do
      test -f "${source}" || continue
      name="$(basename "${source}" .cc)"
      "${CXX}" ${CXXFLAGS} -std=c++11 \
        -I/src/libplist/include -I/work/build/include \
        "${source}" -o "/out/${name}" \
        ${LIB_FUZZING_ENGINE} "${lib}" -pthread
    done
    ;;

  libspng)
    cmake -S /src/zlib -B /work/zlib -DZLIB_BUILD_EXAMPLES=OFF
    cmake --build /work/zlib --target zlibstatic --parallel "${jobs}"
    "${CC}" ${CFLAGS} -I/work/zlib -I/src/zlib -I/src/libspng/spng \
      -c /src/libspng/spng/spng.c -o /work/libspng.o
    zlib="$(find /work/zlib -type f -name 'libz.a' -print -quit)"
    test -n "${zlib}"
    "${CXX}" ${CXXFLAGS} -std=c++11 -DSPNGT_HAVE_FMEMOPEN=1 \
      -I/work/zlib -I/src/zlib -I/src/libspng/spng \
      /src/libspng/tests/spng_read_fuzzer.c -o /out/spng_read_fuzzer \
      ${LIB_FUZZING_ENGINE} /work/libspng.o "${zlib}" -pthread
    ;;

  meshoptimizer)
    mkdir -p /work/objects
    for source in /src/meshoptimizer/src/*.cpp; do
      object="/work/objects/$(basename "${source}" .cpp).o"
      "${CXX}" ${CXXFLAGS} -std=c++11 -I/src/meshoptimizer/src \
        -c "${source}" -o "${object}"
    done
    llvm-ar rcs /work/libmeshoptimizer.a /work/objects/*.o
    for source in /src/meshoptimizer/tools/*fuzz.cpp; do
      test -f "${source}" || continue
      name="$(basename "${source}" .cpp)er"
      "${CXX}" ${CXXFLAGS} -std=c++11 -I/src/meshoptimizer/src \
        "${source}" -o "/out/${name}" \
        ${LIB_FUZZING_ENGINE} /work/libmeshoptimizer.a -pthread
    done
    ;;

  *)
    echo "unsupported project: ${PROJECT_NAME}" >&2
    exit 64
    ;;
esac

find /out -maxdepth 1 -type f -executable -printf '%f\n' | sort
