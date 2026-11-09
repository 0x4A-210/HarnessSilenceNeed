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

# build project
if [ "$SANITIZER" = undefined ]; then
    export CFLAGS="$CFLAGS -fno-sanitize=unsigned-integer-overflow"
    export CXXFLAGS="$CXXFLAGS -fno-sanitize=unsigned-integer-overflow"
fi
cd binutils-gdb

# Comment out the lines of logging to stderror from elfcomm.c
# This is to make it nicer to read the output of libfuzzer.
cd binutils
sed -i 's/vfprintf (stderr/\/\//' elfcomm.c
sed -i 's/fprintf (stderr/\/\//' elfcomm.c
cd ../

./configure --disable-gdb --disable-gdbserver --disable-gdbsupport \
	    --disable-libdecnumber --disable-readline --disable-sim \
	    --disable-libbacktrace --disable-gas --disable-ld --disable-werror \
      --enable-targets=all
make clean
make -j4 MAKEINFO=true && true
cd /src/binutils-gdb/binutils
# Build GAS fuzzer. Will keep this here in case GAS fuzzer is used in the future.
if [ "$FUZZING_ENGINE" != "afl" ]
then
  cd ../gas
  ./configure
  make -j4
  sed 's/main (int argc/old_main32 (int argc, char **argv);\nint old_main32 (int argc/' as.c > fuzz_as.h
  rm as.o || true
  ar r libar.a *.o

  $CC $CFLAGS -DHAVE_CONFIG_H -I.  -I. -I. -I../bfd -I./config -I./../include -I./.. -I./../bfd \
      -DLOCALEDIR="\"/usr/local/share/locale\"" -I./../zlib -c $SRC/fuzz_as.c -o fuzz_as.o
  $CXX $CXXFLAGS $LIB_FUZZING_ENGINE -I./../zlib -o $OUT/fuzz_as ./fuzz_as.o \
      libar.a config/tc-i386.o config/obj-elf.o config/atof-ieee.o  \
      ../opcodes/.libs/libopcodes.a ../bfd/.libs/libbfd.a \
      -L/src/binutils-gdb/zlib ../libiberty/libiberty.a -lz
fi
