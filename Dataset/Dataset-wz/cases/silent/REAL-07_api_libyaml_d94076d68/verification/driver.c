/* 驱动：读入若干 YAML 文件，逐个调用 LLVMFuzzerTestOneInput，最后输出 gap 统计 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

extern int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
extern void gap_report(void);

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "用法: %s <yaml文件>...\n", argv[0]);
        return 2;
    }
    int nfiles = 0;
    for (int i = 1; i < argc; i++) {
        FILE *f = fopen(argv[i], "rb");
        if (!f) { fprintf(stderr, "跳过 %s\n", argv[i]); continue; }
        fseek(f, 0, SEEK_END);
        long n = ftell(f);
        fseek(f, 0, SEEK_SET);
        if (n <= 0) { fclose(f); continue; }
        unsigned char *buf = malloc((size_t)n);
        if (!buf) { fclose(f); continue; }
        if (fread(buf, 1, (size_t)n, f) != (size_t)n) { fclose(f); free(buf); continue; }
        fclose(f);
        LLVMFuzzerTestOneInput(buf, (size_t)n);
        free(buf);
        nfiles++;
    }
    fprintf(stderr, "处理了 %d 个输入\n", nfiles);
    gap_report();
    return 0;
}
