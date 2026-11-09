#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *, size_t);
int main(int argc, char **argv) {
  for (int i=1;i<argc;i++) {
    std::ifstream f(argv[i], std::ios::binary);
    if (!f) { std::perror(argv[i]); return 2; }
    std::string b((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    std::fprintf(stderr, "CALL %d %s size=%zu\n", i, argv[i], b.size());
    int rc=LLVMFuzzerTestOneInput(reinterpret_cast<const uint8_t *>(b.data()), b.size());
    std::fprintf(stderr, "RET %d=%d\n", i, rc);
  }
  return 0;
}
