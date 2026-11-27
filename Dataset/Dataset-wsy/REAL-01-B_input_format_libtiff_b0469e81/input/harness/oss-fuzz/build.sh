#!/bin/bash -eu
# Copyright 2016 Google Inc.
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
./configure --disable-shared
make -j$(nproc)

$CXX $CXXFLAGS -std=c++11 -I. \
    $SRC/libtiff/contrib/oss-fuzz/tiff_read_rgba_fuzzer.cc \
    -o $OUT/tiff_read_rgba_fuzzer \
    $LIB_FUZZING_ENGINE libtiff/.libs/libtiff.a -lz -ljpeg -llzma -lzstd -lwebp

find $SRC/libtiff/test/images -name "*.tiff" -o -name "*.tif" | \
     xargs zip -j $OUT/tiff_read_rgba_fuzzer_seed_corpus.zip
