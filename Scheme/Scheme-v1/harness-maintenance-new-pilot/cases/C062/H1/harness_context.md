The following target source and OSS-Fuzz build wiring are from before the source commit.

### `fuzz/bplist_fuzzer.cc`

~~~~cpp
/*
 * bplist_fuzzer.cc
 * binary plist fuzz target for libFuzzer
 *
 * Copyright (c) 2017 Nikias Bassen All Rights Reserved.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

#include <plist/plist.h>
#include <stdio.h>

extern "C" int LLVMFuzzerTestOneInput(const unsigned char* data, size_t size)
{
	plist_t root_node = NULL;
	plist_from_bin(reinterpret_cast<const char*>(data), size, &root_node);
	plist_free(root_node);

	return 0;
}
~~~~

### `fuzz/xplist_fuzzer.cc`

~~~~cpp
/*
 * xplist_fuzzer.cc
 * XML plist fuzz target for libFuzzer
 *
 * Copyright (c) 2017 Nikias Bassen All Rights Reserved.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

#include <plist/plist.h>
#include <stdio.h>

extern "C" int LLVMFuzzerTestOneInput(const unsigned char* data, size_t size)
{
	plist_t root_node = NULL;
	plist_from_xml(reinterpret_cast<const char*>(data), size, &root_node);
	plist_free(root_node);

	return 0;
}
~~~~

### `historical OSS-Fuzz:projects/libplist/build.sh`

~~~~text
#!/bin/bash -eu
#
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

./autogen.sh --without-cython --enable-debug
make -j$(nproc) clean
make -j$(nproc) all

for fuzzer in bplist_fuzzer xplist_fuzzer jplist_fuzzer; do
  $CXX $CXXFLAGS -std=c++11 -Iinclude/ \
      fuzz/$fuzzer.cc -o $OUT/$fuzzer \
      $LIB_FUZZING_ENGINE src/.libs/libplist-2.0.a
done

zip -j $OUT/bplist_fuzzer_seed_corpus.zip test/data/*.bplist
zip -j $OUT/xplist_fuzzer_seed_corpus.zip test/data/*.plist
zip -j $OUT/jplist_fuzzer_seed_corpus.zip test/data/*.json

cp fuzz/*.dict fuzz/*.options $OUT/
~~~~
