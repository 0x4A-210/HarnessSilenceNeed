#!/bin/bash -eu
# Copyright 2019 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
################################################################################

./autogen.sh
./configure --enable-static --disable-shared
make -j$(nproc)

$CXX $CXXFLAGS $LIB_FUZZING_ENGINE \
    $SRC/flac/oss-fuzz/fuzzer_decoder.cc \
    -o $OUT/fuzzer_decoder \
    -I$SRC/flac/include \
    $SRC/flac/src/libFLAC/.libs/libFLAC.a \
    -lm

$CXX $CXXFLAGS $LIB_FUZZING_ENGINE \
    $SRC/flac/oss-fuzz/fuzzer_encoder.cc \
    -o $OUT/fuzzer_encoder \
    -I$SRC/flac/include \
    $SRC/flac/src/libFLAC/.libs/libFLAC.a \
    -lm

find $SRC/flac/test/flac-to-flac-metadata-test-files -name "*.flac" | \
     xargs zip -j $OUT/fuzzer_decoder_seed_corpus.zip
