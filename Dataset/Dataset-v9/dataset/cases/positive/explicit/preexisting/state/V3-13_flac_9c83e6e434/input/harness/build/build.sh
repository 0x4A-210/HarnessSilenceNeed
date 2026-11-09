#!/bin/bash
set -eu
: "${SRC:?set SRC to input/source}"
: "${HARNESS:?set HARNESS to input/harness}"
: "${OUT:?set OUT to an output directory}"
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
WORK="$ROOT/verification/.build"
HARNESS_TOOL="${HARNESS_TOOL:-$HARNESS/oss-fuzz/tool_flac.c}"
RUN_REPLAY="${RUN_REPLAY:-0}"
rm -rf "$WORK"
mkdir -p "$WORK" "$OUT"
SOURCE_HARNESS="$SRC/oss-fuzz/tool_flac.c"
if [ "$HARNESS_TOOL" != "$SOURCE_HARNESS" ]; then
  cp "$SOURCE_HARNESS" "$WORK/source_harness.original.c"
  restore_source() { cp "$WORK/source_harness.original.c" "$SOURCE_HARNESS"; }
  trap restore_source EXIT
  cp "$HARNESS_TOOL" "$SOURCE_HARNESS"
fi
cmake -S "$SRC" -B "$WORK/cmake" -DBUILD_PROGRAMS=ON -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF -DWITH_OGG=OFF -DINSTALL_MANPAGES=OFF -DCMAKE_BUILD_TYPE=Debug
cmake --build "$WORK/cmake" -j$(nproc)
$CC -DHAVE_CONFIG_H -I"$WORK/cmake" -I"$SRC/include" -I"$SRC/src" -I"$SRC/src/share" -I"$SRC/src/share/getopt" -I"$SRC/src/share/grabbag" -I"$SRC/oss-fuzz" -g -c "$SRC/oss-fuzz/tool_flac.c" -o "$WORK/tool_flac.o"
$CXX -std=c++11 -g "$ROOT/verification/replay_driver.cpp" "$WORK/tool_flac.o" \
  "$WORK/cmake/src/flac/CMakeFiles/flacapp.dir/analyze.c.o" "$WORK/cmake/src/flac/CMakeFiles/flacapp.dir/decode.c.o" "$WORK/cmake/src/flac/CMakeFiles/flacapp.dir/encode.c.o" "$WORK/cmake/src/flac/CMakeFiles/flacapp.dir/foreign_metadata.c.o" "$WORK/cmake/src/flac/CMakeFiles/flacapp.dir/local_string_utils.c.o" "$WORK/cmake/src/flac/CMakeFiles/flacapp.dir/utils.c.o" "$WORK/cmake/src/flac/CMakeFiles/flacapp.dir/vorbiscomment.c.o" \
  "$WORK/cmake/src/libFLAC/libFLAC.a" "$WORK/cmake/src/share/getopt/libgetopt.a" "$WORK/cmake/src/share/replaygain_synthesis/libreplaygain_synthesis.a" "$WORK/cmake/src/share/utf8/libutf8.a" "$WORK/cmake/src/share/grabbag/libgrabbag.a" "$WORK/cmake/src/share/replaygain_analysis/libreplaygain_analysis.a" -lm -lz -o "$OUT/replay_tool_flac"
if [ "$RUN_REPLAY" = 1 ]; then
  cp "$ROOT/verification/in.wav" /tmp/in.wav
  cp "$ROOT/verification/in2.wav" /tmp/in2.wav
  "$OUT/replay_tool_flac" "$ROOT/verification/multi2.bin" "$ROOT/verification/plain.bin"
fi
