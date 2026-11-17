/* REAL-03 复现：add_passphrase 的调用顺序约束
 * 编译：gcc -O1 verify03.c -o verify03 $(pkg-config --cflags --libs libarchive)
 */
#include <archive.h>
#include <archive_entry.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static size_t make_encrypted_zip(unsigned char *buf, size_t cap)
{
    size_t used = 0;
    struct archive *w = archive_write_new();
    archive_write_set_format_zip(w);
    archive_write_add_filter_none(w);
    archive_write_set_options(w, "zip:encryption=aes256");
    archive_write_open_memory(w, buf, cap, &used);

    struct archive_entry *e = archive_entry_new();
    const char *body = "hello passphrase";
    archive_entry_set_pathname(e, "f.txt");
    archive_entry_set_size(e, strlen(body));
    archive_entry_set_filetype(e, AE_IFREG);
    archive_write_header(w, e);
    archive_write_data(w, body, strlen(body));
    archive_entry_free(e);
    archive_write_close(w);
    archive_write_free(w);
    return used;
}

static void run(const char *tag, const unsigned char *zip, size_t len, int fix_order)
{
    struct archive *a = archive_read_new();
    archive_read_support_filter_all(a);
    archive_read_support_format_all(a);

    int r;
    if (fix_order) {
        /* FIX: add_passphrase 在 open 之前 */
        r = archive_read_add_passphrase(a, "secret");
        printf("%-4s add_passphrase = %d", tag, r);
        if (r != ARCHIVE_OK) printf(" [%s]", archive_error_string(a));
        printf("\n");
        r = archive_read_open_memory(a, zip, len);
        printf("%-4s open_memory    = %d\n", tag, r);
    } else {
        /* OLD: open 之后才 add_passphrase（harness 原样） */
        r = archive_read_open_memory(a, zip, len);
        printf("%-4s open_memory    = %d\n", tag, r);
        r = archive_read_add_passphrase(a, "secret");
        printf("%-4s add_passphrase = %d", tag, r);
        if (r != ARCHIVE_OK) printf("  <-- %s", archive_error_string(a));
        printf("\n");
    }

    int entries = 0;
    struct archive_entry *entry;
    int hdr;
    while ((hdr = archive_read_next_header(a, &entry)) == ARCHIVE_OK) entries++;
    printf("%-4s next_header    = %d, entries = %d\n\n", tag, hdr, entries);
    archive_read_free(a);
}

int main(void)
{
    static unsigned char zip[65536];
    size_t len = make_encrypted_zip(zip, sizeof(zip));
    printf("加密 zip 大小 = %zu 字节\n\n", len);

    struct timespec t0, t1;

    clock_gettime(CLOCK_MONOTONIC, &t0);
    run("OLD", zip, len, 0);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double s1 = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;

    clock_gettime(CLOCK_MONOTONIC, &t0);
    run("FIX", zip, len, 1);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double s2 = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;

    printf("耗时: OLD=%.3fs  FIX=%.3fs\n", s1, s2);
    return 0;
}
