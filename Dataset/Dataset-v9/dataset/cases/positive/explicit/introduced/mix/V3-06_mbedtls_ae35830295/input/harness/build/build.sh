# custom recipe: mbedtls in-tree fuzz programs (programs/fuzz) as OSS-Fuzz builds them, plus the
# step OSS-Fuzz's build.sh of that period lacked: generated sources (error.c, version_features.c,
# query_config.c, ...) were removed from git in 2021-05 and CMake could not yet regenerate them,
# so they are produced with the project's own `make generated_files` first. The boringssl/openssl
# corpora that the Dockerfile cloned (openssl/boringssl, mostly DER keys and certificates) are not
# available offline; as a stand-in the project's own DER test files are added to the PEM/key seeds.
cd $SRC/mbedtls
perl scripts/config.pl set MBEDTLS_PLATFORM_TIME_ALT || python3 scripts/config.py set MBEDTLS_PLATFORM_TIME_ALT
make generated_files >/dev/null 2>&1 || { make -C library generated_files; make -C programs generated_files; }
mkdir -p build && cd build
cmake .. -DENABLE_TESTING=Off -DCMAKE_C_COMPILER=$CC -DCMAKE_CXX_COMPILER=$CXX >/dev/null
make -k -j2 -C programs/fuzz || make -k -j2
cp programs/fuzz/fuzz_* $OUT/ 2>/dev/null
cd ../programs
zip -q -r $OUT/fuzz_privkey_seed_corpus.zip ../tests/data_files/*.key ../tests/data_files/*.pem ../tests/data_files/*.der
zip -q -r $OUT/fuzz_pubkey_seed_corpus.zip ../tests/data_files/*.pub ../tests/data_files/*.pubkey
zip -q -r $OUT/fuzz_x509crt_seed_corpus.zip ../tests/data_files/*.crt ../tests/data_files/*.der
for d in client server dtlsclient dtlsserver; do [ -d fuzz/corpuses/$d ] && zip -q -r $OUT/fuzz_${d}_seed_corpus.zip fuzz/corpuses/$d; done
cp fuzz/*.options $OUT/ 2>/dev/null
true
