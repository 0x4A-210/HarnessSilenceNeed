# Case ID

C042

## Existing Fuzz Harness H0

### `test/ares-fuzz.c`

~~~~c
/*
 * Copyright (C) The c-ares project
 *
 * Permission to use, copy, modify, and distribute this
 * software and its documentation for any purpose and without
 * fee is hereby granted, provided that the above copyright
 * notice appear in all copies and that both that copyright
 * notice and this permission notice appear in supporting
 * documentation, and that the name of M.I.T. not be used in
 * advertising or publicity pertaining to distribution of the
 * software without specific, written prior permission.
 * M.I.T. makes no representations about the suitability of
 * this software for any purpose.  It is provided "as is"
 * without express or implied warranty.
 *
 * SPDX-License-Identifier: MIT
 */
/*
 * General driver to allow command-line fuzzer (i.e. afl) to
 * exercise the libFuzzer entrypoint.
 */

#include <sys/types.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

#include "ares.h"

#define kMaxAflInputSize (1 << 20)
static unsigned char afl_buffer[kMaxAflInputSize];

#ifdef __AFL_LOOP
/* If we are built with afl-clang-fast, use persistent mode */
#define KEEP_FUZZING(count)  __AFL_LOOP(1000)
#else
/* If we are built with afl-clang, execute each input once */
#define KEEP_FUZZING(count) ((count) < 1)
#endif

/* In ares-test-fuzz.c and ares-test-fuzz-name.c: */
int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size);

static void ProcessFile(int fd) {
  ares_ssize_t count = read(fd, afl_buffer, kMaxAflInputSize);
  /*
   * Make a copy of the data so that it's not part of a larger
   * buffer (where buffer overflows would go unnoticed).
   */
  if (count > 0) {
    unsigned char *copied_data = (unsigned char *)malloc((size_t)count);
    memcpy(copied_data, afl_buffer, (size_t)count);
    LLVMFuzzerTestOneInput(copied_data, (size_t)count);
    free(copied_data);
  }
}

int main(int argc, char *argv[]) {
  if (argc == 1) {
    int count = 0;
    while (KEEP_FUZZING(count)) {
      ProcessFile(fileno(stdin));
      count++;
    }
  } else {
    int ii;
    for (ii = 1; ii < argc; ++ii) {
      int fd = open(argv[ii], O_RDONLY);
      if (fd < 0) {
        fprintf(stderr, "Failed to open '%s'\n", argv[ii]);
        continue;
      }
      ProcessFile(fd);
      close(fd);
    }
  }
  return 0;
}
~~~~
### `test/ares-test-fuzz-name.c`

~~~~c
/*
 * Copyright (C) The c-ares project
 *
 * Permission to use, copy, modify, and distribute this
 * software and its documentation for any purpose and without
 * fee is hereby granted, provided that the above copyright
 * notice appear in all copies and that both that copyright
 * notice and this permission notice appear in supporting
 * documentation, and that the name of M.I.T. not be used in
 * advertising or publicity pertaining to distribution of the
 * software without specific, written prior permission.
 * M.I.T. makes no representations about the suitability of
 * this software for any purpose.  It is provided "as is"
 * without express or implied warranty.
 *
 * SPDX-License-Identifier: MIT
 */
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#include "ares.h"
// Include ares internal file for DNS protocol constants
#include "ares_nameser.h"

int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size);

// Entrypoint for Clang's libfuzzer, exercising query creation.
int LLVMFuzzerTestOneInput(const unsigned char *data,
                           unsigned long size) {
  // Null terminate the data.
  char *name = malloc(size + 1);
  unsigned char *buf = NULL;
  int buflen = 0;
  name[size] = '\0';
  memcpy(name, data, size);

  ares_create_query(name, C_IN, T_AAAA, 1234, 0, &buf, &buflen, 1024);
  free(buf);
  free(name);
  return 0;
}
~~~~
### `test/ares-test-fuzz.c`

~~~~c
/*
 * Copyright (C) The c-ares project
 *
 * Permission to use, copy, modify, and distribute this
 * software and its documentation for any purpose and without
 * fee is hereby granted, provided that the above copyright
 * notice appear in all copies and that both that copyright
 * notice and this permission notice appear in supporting
 * documentation, and that the name of M.I.T. not be used in
 * advertising or publicity pertaining to distribution of the
 * software without specific, written prior permission.
 * M.I.T. makes no representations about the suitability of
 * this software for any purpose.  It is provided "as is"
 * without express or implied warranty.
 *
 * SPDX-License-Identifier: MIT
 */
#include <stddef.h>

#include "ares.h"

int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size);


// Entrypoint for Clang's libfuzzer
int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size)
{
  // Feed the data into each of the ares_parse_*_reply functions.
  struct hostent *host = NULL;
  struct ares_addrttl info[5];
  struct ares_addr6ttl info6[5];
  unsigned char addrv4[4] = {0x10, 0x20, 0x30, 0x40};
  struct ares_srv_reply* srv = NULL;
  struct ares_mx_reply* mx = NULL;
  struct ares_txt_reply* txt = NULL;
  struct ares_soa_reply* soa = NULL;
  struct ares_naptr_reply* naptr = NULL;
  struct ares_caa_reply* caa = NULL;
  struct ares_uri_reply* uri = NULL;
  int count = 5;
  ares_parse_a_reply(data, (int)size, &host, info, &count);
  if (host) ares_free_hostent(host);

  host = NULL;
  count = 5;
  ares_parse_aaaa_reply(data, (int)size, &host, info6, &count);
  if (host) ares_free_hostent(host);

  host = NULL;
  ares_parse_ptr_reply(data, (int)size, addrv4, sizeof(addrv4), AF_INET, &host);
  if (host) ares_free_hostent(host);

  host = NULL;
  ares_parse_ns_reply(data, (int)size, &host);
  if (host) ares_free_hostent(host);

  ares_parse_srv_reply(data, (int)size, &srv);
  if (srv) ares_free_data(srv);

  ares_parse_mx_reply(data, (int)size, &mx);
  if (mx) ares_free_data(mx);

  ares_parse_txt_reply(data, (int)size, &txt);
  if (txt) ares_free_data(txt);

  ares_parse_soa_reply(data, (int)size, &soa);
  if (soa) ares_free_data(soa);

  ares_parse_naptr_reply(data, (int)size, &naptr);
  if (naptr) ares_free_data(naptr);

  ares_parse_caa_reply(data, (int)size, &caa);
  if (caa) ares_free_data(caa);

  ares_parse_uri_reply(data, (int)size, &uri);
  if (uri) ares_free_data(uri);

  return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is a deterministic H0-identifier-anchored excerpt capped at 70,000 characters.

~~~~diff
... [unselected diff lines omitted by frozen H0-anchored rule] ...
diff --git a/include/ares.h b/include/ares.h
index 8c45622..49eb6e1 100644
--- a/include/ares.h
+++ b/include/ares.h
@@ -28,16 +28,16 @@
 #ifndef ARES__H
 #define ARES__H
 
-#include "ares_version.h"  /* c-ares version defines   */
-#include "ares_build.h"    /* c-ares build definitions */
-#include "ares_rules.h"    /* c-ares rules enforcement */
+#include "ares_version.h" /* c-ares version defines   */
+#include "ares_build.h"   /* c-ares build definitions */
+#include "ares_rules.h"   /* c-ares rules enforcement */
 
 /*
  * Define WIN32 when build target is Win32 API
  */
 
-#if (defined(_WIN32) || defined(__WIN32__)) && \
-   !defined(WIN32) && !defined(__SYMBIAN32__)
+#if (defined(_WIN32) || defined(__WIN32__)) && !defined(WIN32) && \
+  !defined(__SYMBIAN32__)
 #  define WIN32
 #endif
 
@@ -47,13 +47,13 @@
    libc5-based Linux systems. Only include it on system that are known to
    require it! */
 #if defined(_AIX) || defined(__NOVELL_LIBC__) || defined(__NetBSD__) || \
-    defined(__minix) || defined(__SYMBIAN32__) || defined(__INTEGRITY) || \
-    defined(ANDROID) || defined(__ANDROID__) || defined(__OpenBSD__) || \
-    defined(__QNXNTO__) || defined(__MVS__) || defined(__HAIKU__)
-#include <sys/select.h>
+  defined(__minix) || defined(__SYMBIAN32__) || defined(__INTEGRITY) || \
+  defined(ANDROID) || defined(__ANDROID__) || defined(__OpenBSD__) ||   \
+  defined(__QNXNTO__) || defined(__MVS__) || defined(__HAIKU__)
+#  include <sys/select.h>
 #endif
 #if (defined(NETWARE) && !defined(__NOVELL_LIBC__))
-#include <sys/bsdskt.h>
+#  include <sys/bsdskt.h>
 #endif
 
 #if defined(WATT32)
@@ -86,10 +86,10 @@
 #endif
 
 #if defined(ANDROID) || defined(__ANDROID__)
-#include <jni.h>
+#  include <jni.h>
 #endif
 
-#ifdef  __cplusplus
+#ifdef __cplusplus
 extern "C" {
 #endif
 
@@ -101,9 +101,9 @@ extern "C" {
 #  define CARES_EXTERN
 #elif defined(WIN32) || defined(_WIN32) || defined(__SYMBIAN32__)
 #  if defined(CARES_BUILDING_LIBRARY)
-#    define CARES_EXTERN  __declspec(dllexport)
+#    define CARES_EXTERN __declspec(dllexport)
 #  else
-#    define CARES_EXTERN  __declspec(dllimport)
+#    define CARES_EXTERN __declspec(dllimport)
 #  endif
 #elif defined(CARES_BUILDING_LIBRARY) && defined(CARES_SYMBOL_HIDING)
 #  define CARES_EXTERN CARES_SYMBOL_SCOPE_EXTERN
@@ -113,66 +113,65 @@ extern "C" {
 
 
 typedef enum {
-  ARES_SUCCESS                = 0,
+  ARES_SUCCESS = 0,
 
   /* Server error codes (ARES_ENODATA indicates no relevant answer) */
-  ARES_ENODATA                = 1,
-  ARES_EFORMERR               = 2,
-  ARES_ESERVFAIL              = 3,
-  ARES_ENOTFOUND              = 4,
-  ARES_ENOTIMP                = 5,
-  ARES_EREFUSED               = 6,
+  ARES_ENODATA   = 1,
+  ARES_EFORMERR  = 2,
+  ARES_ESERVFAIL = 3,
+  ARES_ENOTFOUND = 4,
+  ARES_ENOTIMP   = 5,
+  ARES_EREFUSED  = 6,
 
   /* Locally generated error codes */
-  ARES_EBADQUERY              = 7,
-  ARES_EBADNAME               = 8,
-  ARES_EBADFAMILY             = 9,
-  ARES_EBADRESP               = 10,
-  ARES_ECONNREFUSED           = 11,
-  ARES_ETIMEOUT               = 12,
-  ARES_EOF                    = 13,
-  ARES_EFILE                  = 14,
-  ARES_ENOMEM                 = 15,
-  ARES_EDESTRUCTION           = 16,
-  ARES_EBADSTR                = 17,
-
-/* ares_getnameinfo error codes */
-  ARES_EBADFLAGS              = 18,
-
-/* ares_getaddrinfo error codes */
-  ARES_ENONAME                = 19,
-  ARES_EBADHINTS              = 20,
+  ARES_EBADQUERY    = 7,
+  ARES_EBADNAME     = 8,
+  ARES_EBADFAMILY   = 9,
+  ARES_EBADRESP     = 10,
+  ARES_ECONNREFUSED = 11,
+  ARES_ETIMEOUT     = 12,
+  ARES_EOF          = 13,
+  ARES_EFILE        = 14,
+  ARES_ENOMEM       = 15,
+  ARES_EDESTRUCTION = 16,
+  ARES_EBADSTR      = 17,
+
+  /* ares_getnameinfo error codes */
+  ARES_EBADFLAGS = 18,
+
+  /* ares_getaddrinfo error codes */
+  ARES_ENONAME   = 19,
+  ARES_EBADHINTS = 20,
 
   /* Uninitialized library error code */
-  ARES_ENOTINITIALIZED        = 21,          /* introduced in 1.7.0 */
+  ARES_ENOTINITIALIZED = 21, /* introduced in 1.7.0 */
 
   /* ares_library_init error codes */
-  ARES_ELOADIPHLPAPI          = 22,     /* introduced in 1.7.0 */
-  ARES_EADDRGETNETWORKPARAMS  = 23,     /* introduced in 1.7.0 */
+  ARES_ELOADIPHLPAPI         = 22, /* introduced in 1.7.0 */
+  ARES_EADDRGETNETWORKPARAMS = 23, /* introduced in 1.7.0 */
 
   /* More error codes */
-  ARES_ECANCELLED             = 24,          /* introduced in 1.7.0 */
+  ARES_ECANCELLED = 24, /* introduced in 1.7.0 */
 
   /* More ares_getaddrinfo error codes */
-  ARES_ESERVICE               = 25          /* introduced in 1.?.0 */
+  ARES_ESERVICE = 25 /* introduced in 1.?.0 */
 } ares_status_t;
 
-
 typedef enum {
   ARES_FALSE = 0,
   ARES_TRUE  = 1
 } ares_bool_t;
 
 /* Flag values */
-#define ARES_FLAG_USEVC         (1 << 0)
-#define ARES_FLAG_PRIMARY       (1 << 1)
-#define ARES_FLAG_IGNTC         (1 << 2)
-#define ARES_FLAG_NORECURSE     (1 << 3)
-#define ARES_FLAG_STAYOPEN      (1 << 4)
-#define ARES_FLAG_NOSEARCH      (1 << 5)
-#define ARES_FLAG_NOALIASES     (1 << 6)
-#define ARES_FLAG_NOCHECKRESP   (1 << 7)
-#define ARES_FLAG_EDNS          (1 << 8)
+#define ARES_FLAG_USEVC       (1 << 0)
+#define ARES_FLAG_PRIMARY     (1 << 1)
+#define ARES_FLAG_IGNTC       (1 << 2)
+#define ARES_FLAG_NORECURSE   (1 << 3)
+#define ARES_FLAG_STAYOPEN    (1 << 4)
+#define ARES_FLAG_NOSEARCH    (1 << 5)
+#define ARES_FLAG_NOALIASES   (1 << 6)
+#define ARES_FLAG_NOCHECKRESP (1 << 7)
+#define ARES_FLAG_EDNS        (1 << 8)
 
 /* Option mask values */
 #define ARES_OPT_FLAGS           (1 << 0)
@@ -197,52 +196,53 @@ typedef enum {
 #define ARES_OPT_UDP_MAX_QUERIES (1 << 19)
 
 /* Nameinfo flag values */
-#define ARES_NI_NOFQDN                  (1 << 0)
-#define ARES_NI_NUMERICHOST             (1 << 1)
-#define ARES_NI_NAMEREQD                (1 << 2)
-#define ARES_NI_NUMERICSERV             (1 << 3)
-#define ARES_NI_DGRAM                   (1 << 4)
-#define ARES_NI_TCP                     0
-#define ARES_NI_UDP                     ARES_NI_DGRAM
-#define ARES_NI_SCTP                    (1 << 5)
-#define ARES_NI_DCCP                    (1 << 6)
-#define ARES_NI_NUMERICSCOPE            (1 << 7)
-#define ARES_NI_LOOKUPHOST              (1 << 8)
-#define ARES_NI_LOOKUPSERVICE           (1 << 9)
+#define ARES_NI_NOFQDN        (1 << 0)
+#define ARES_NI_NUMERICHOST   (1 << 1)
+#define ARES_NI_NAMEREQD      (1 << 2)
+#define ARES_NI_NUMERICSERV   (1 << 3)
+#define ARES_NI_DGRAM         (1 << 4)
+#define ARES_NI_TCP           0
+#define ARES_NI_UDP           ARES_NI_DGRAM
+#define ARES_NI_SCTP          (1 << 5)
+#define ARES_NI_DCCP          (1 << 6)
+#define ARES_NI_NUMERICSCOPE  (1 << 7)
+#define ARES_NI_LOOKUPHOST    (1 << 8)
+#define ARES_NI_LOOKUPSERVICE (1 << 9)
 /* Reserved for future use */
-#define ARES_NI_IDN                     (1 << 10)
-#define ARES_NI_IDN_ALLOW_UNASSIGNED    (1 << 11)
+#define ARES_NI_IDN                      (1 << 10)
+#define ARES_NI_IDN_ALLOW_UNASSIGNED     (1 << 11)
 #define ARES_NI_IDN_USE_STD3_ASCII_RULES (1 << 12)
 
 /* Addrinfo flag values */
-#define ARES_AI_CANONNAME               (1 << 0)
-#define ARES_AI_NUMERICHOST             (1 << 1)
-#define ARES_AI_PASSIVE                 (1 << 2)
-#define ARES_AI_NUMERICSERV             (1 << 3)
-#define ARES_AI_V4MAPPED                (1 << 4)
-#define ARES_AI_ALL                     (1 << 5)
-#define ARES_AI_ADDRCONFIG              (1 << 6)
-#define ARES_AI_NOSORT                  (1 << 7)
-#define ARES_AI_ENVHOSTS                (1 << 8)
+#define ARES_AI_CANONNAME   (1 << 0)
+#define ARES_AI_NUMERICHOST (1 << 1)
+#define ARES_AI_PASSIVE     (1 << 2)
+#define ARES_AI_NUMERICSERV (1 << 3)
+#define ARES_AI_V4MAPPED    (1 << 4)
+#define ARES_AI_ALL         (1 << 5)
+#define ARES_AI_ADDRCONFIG  (1 << 6)
+#define ARES_AI_NOSORT      (1 << 7)
+#define ARES_AI_ENVHOSTS    (1 << 8)
 /* Reserved for future use */
-#define ARES_AI_IDN                     (1 << 10)
-#define ARES_AI_IDN_ALLOW_UNASSIGNED    (1 << 11)
+#define ARES_AI_IDN                      (1 << 10)
+#define ARES_AI_IDN_ALLOW_UNASSIGNED     (1 << 11)
 #define ARES_AI_IDN_USE_STD3_ASCII_RULES (1 << 12)
-#define ARES_AI_CANONIDN                (1 << 13)
-
-#define ARES_AI_MASK (ARES_AI_CANONNAME|ARES_AI_NUMERICHOST|ARES_AI_PASSIVE| \
-                      ARES_AI_NUMERICSERV|ARES_AI_V4MAPPED|ARES_AI_ALL| \
-                      ARES_AI_ADDRCONFIG)
-#define ARES_GETSOCK_MAXNUM 16 /* ares_getsock() can return info about this
-                                  many sockets */
-#define ARES_GETSOCK_READABLE(bits,num) (bits & (1<< (num)))
-#define ARES_GETSOCK_WRITABLE(bits,num) (bits & (1 << ((num) + \
-                                         ARES_GETSOCK_MAXNUM)))
+#define ARES_AI_CANONIDN                 (1 << 13)
+
+#define ARES_AI_MASK                                           \
+  (ARES_AI_CANONNAME | ARES_AI_NUMERICHOST | ARES_AI_PASSIVE | \
+   ARES_AI_NUMERICSERV | ARES_AI_V4MAPPED | ARES_AI_ALL | ARES_AI_ADDRCONFIG)
+#define ARES_GETSOCK_MAXNUM                       \
+  16 /* ares_getsock() can return info about this \
+        many sockets */
+#define ARES_GETSOCK_READABLE(bits, num) (bits & (1 << (num)))
+#define ARES_GETSOCK_WRITABLE(bits, num) \
+  (bits & (1 << ((num) + ARES_GETSOCK_MAXNUM)))
 
 /* c-ares library initialization flag values */
-#define ARES_LIB_INIT_NONE   (0)
-#define ARES_LIB_INIT_WIN32  (1 << 0)
-#define ARES_LIB_INIT_ALL    (ARES_LIB_INIT_WIN32)
+#define ARES_LIB_INIT_NONE  (0)
+#define ARES_LIB_INIT_WIN32 (1 << 0)
+#define ARES_LIB_INIT_ALL   (ARES_LIB_INIT_WIN32)
 
 
 /*
@@ -250,20 +250,18 @@ typedef enum {
  */
 
 #ifndef ares_socket_typedef
-#ifdef WIN32
+#  ifdef WIN32
 typedef SOCKET ares_socket_t;
-#define ARES_SOCKET_BAD INVALID_SOCKET
-#else
+#    define ARES_SOCKET_BAD INVALID_SOCKET
+#  else
 typedef int ares_socket_t;
-#define ARES_SOCKET_BAD -1
-#endif
-#define ares_socket_typedef
+#    define ARES_SOCKET_BAD -1
+#  endif
+#  define ares_socket_typedef
 #endif /* ares_socket_typedef */
 
-typedef void (*ares_sock_state_cb)(void *data,
-                                   ares_socket_t socket_fd,
-                                   int readable,
-                                   int writable);
+typedef void (*ares_sock_state_cb)(void *data, ares_socket_t socket_fd,
+                                   int readable, int writable);
 
 struct apattern;
 
@@ -285,27 +283,27 @@ struct apattern;
 
  */
 struct ares_options {
-  int flags;
-  int timeout; /* in seconds or milliseconds, depending on options */
-  int tries;
-  int ndots;
+  int            flags;
+  int            timeout; /* in seconds or milliseconds, depending on options */
+  int            tries;
+  int            ndots;
   unsigned short udp_port;
   unsigned short tcp_port;
-  int socket_send_buffer_size;
-  int socket_receive_buffer_size;
-  struct in_addr *servers;
-  int nservers;
-  char **domains;
-  int ndomains;
-  char *lookups;
+  int            socket_send_buffer_size;
+  int            socket_receive_buffer_size;
+  struct in_addr    *servers;
+  int                nservers;
+  char             **domains;
+  int                ndomains;
+  char              *lookups;
   ares_sock_state_cb sock_state_cb;
-  void *sock_state_cb_data;
-  struct apattern *sortlist;
-  int nsort;
-  int ednspsz;
-  char *resolvconf_path;
-  char *hosts_path;
-  int udp_max_queries;
+  void              *sock_state_cb_data;
+  struct apattern   *sortlist;
+  int                nsort;
+  int                ednspsz;
+  char              *resolvconf_path;
+  char              *hosts_path;
+  int                udp_max_queries;
 };
 
 struct hostent;
@@ -317,107 +315,89 @@ struct ares_addrinfo_hints;
 
 typedef struct ares_channeldata *ares_channel;
 
-typedef void (*ares_callback)(void *arg,
-                              int status,
-                              int timeouts,
-                              unsigned char *abuf,
-                              int alen);
+typedef void     (*ares_callback)(void *arg, int status, int timeouts,
+                              unsigned char *abuf, int alen);
 
-typedef void (*ares_host_callback)(void *arg,
-                                   int status,
-                                   int timeouts,
+typedef void     (*ares_host_callback)(void *arg, int status, int timeouts,
                                    struct hostent *hostent);
 
-typedef void (*ares_nameinfo_callback)(void *arg,
-                                       int status,
-                                       int timeouts,
-                                       char *node,
-                                       char *service);
+typedef void     (*ares_nameinfo_callback)(void *arg, int status, int timeouts,
+                                       char *node, char *service);
 
-typedef int  (*ares_sock_create_callback)(ares_socket_t socket_fd,
-                                          int type,
-                                          void *data);
+typedef int      (*ares_sock_create_callback)(ares_socket_t socket_fd, int type,
+                                         void *data);
 
-typedef int  (*ares_sock_config_callback)(ares_socket_t socket_fd,
-                                          int type,
-                                          void *data);
+typedef int      (*ares_sock_config_callback)(ares_socket_t socket_fd, int type,
+                                         void *data);
 
-typedef void (*ares_addrinfo_callback)(void *arg,
-                                   int status,
-                                   int timeouts,
-                                   struct ares_addrinfo *res);
+typedef void     (*ares_addrinfo_callback)(void *arg, int status, int timeouts,
+                                       struct ares_addrinfo *res);
 
 CARES_EXTERN int ares_library_init(int flags);
 
-CARES_EXTERN int ares_library_init_mem(int flags,
-                                       void *(*amalloc)(size_t size),
-                                       void (*afree)(void *ptr),
-                                       void *(*arealloc)(void *ptr, size_t size));
+CARES_EXTERN int ares_library_init_mem(int flags, void *(*amalloc)(size_t size),
+                                       void  (*afree)(void *ptr),
+                                       void *(*arealloc)(void  *ptr,
+                                                         size_t size));
 
 #if defined(ANDROID) || defined(__ANDROID__)
 CARES_EXTERN void ares_library_init_jvm(JavaVM *jvm);
-CARES_EXTERN int ares_library_init_android(jobject connectivity_manager);
-CARES_EXTERN int ares_library_android_initialized(void);
+CARES_EXTERN int  ares_library_init_android(jobject connectivity_manager);
+CARES_EXTERN int  ares_library_android_initialized(void);
 #endif
 
-CARES_EXTERN int ares_library_initialized(void);
+CARES_EXTERN int         ares_library_initialized(void);
 
-CARES_EXTERN void ares_library_cleanup(void);
+CARES_EXTERN void        ares_library_cleanup(void);
 
 CARES_EXTERN const char *ares_version(int *version);
 
-CARES_EXTERN int ares_init(ares_channel *channelptr);
+CARES_EXTERN int         ares_init(ares_channel *channelptr);
 
-CARES_EXTERN int ares_init_options(ares_channel *channelptr,
-                                   struct ares_options *options,
-                                   int optmask);
+CARES_EXTERN int         ares_init_options(ares_channel        *channelptr,
+                                           struct ares_options *options, int optmask);
 
-CARES_EXTERN int ares_save_options(ares_channel channel,
-                                   struct ares_options *options,
-                                   int *optmask);
+CARES_EXTERN int         ares_save_options(ares_channel         channel,
+                                           struct ares_options *options, int *optmask);
 
-CARES_EXTERN void ares_destroy_options(struct ares_options *options);
+CARES_EXTERN void        ares_destroy_options(struct ares_options *options);
 
-CARES_EXTERN int ares_dup(ares_channel *dest,
-                          ares_channel src);
+CARES_EXTERN int         ares_dup(ares_channel *dest, ares_channel src);
 
-CARES_EXTERN void ares_destroy(ares_channel channel);
+CARES_EXTERN void        ares_destroy(ares_channel channel);
 
-CARES_EXTERN void ares_cancel(ares_channel channel);
+CARES_EXTERN void        ares_cancel(ares_channel channel);
 
 /* These next 3 configure local binding for the out-going socket
  * connection.  Use these to specify source IP and/or network device
  * on multi-homed systems.
  */
-CARES_EXTERN void ares_set_local_ip4(ares_channel channel, unsigned int local_ip);
+CARES_EXTERN void        ares_set_local_ip4(ares_channel channel,
+                                            unsigned int local_ip);
 
 /* local_ip6 should be 16 bytes in length */
-CARES_EXTERN void ares_set_local_ip6(ares_channel channel,
-                                     const unsigned char* local_ip6);
+CARES_EXTERN void        ares_set_local_ip6(ares_channel         channel,
+                                            const unsigned char *local_ip6);
 
 /* local_dev_name should be null terminated. */
-CARES_EXTERN void ares_set_local_dev(ares_channel channel,
-                                     const char* local_dev_name);
+CARES_EXTERN void        ares_set_local_dev(ares_channel channel,
+                                            const char  *local_dev_name);
 
-CARES_EXTERN void ares_set_socket_callback(ares_channel channel,
-                                           ares_sock_create_callback callback,
-                                           void *user_data);
+CARES_EXTERN void        ares_set_socket_callback(ares_channel              channel,
+                                                  ares_sock_create_callback callback,
+                                                  void                     *user_data);
 
-CARES_EXTERN void ares_set_socket_configure_callback(ares_channel channel,
-                                                     ares_sock_config_callback callback,
-                                                     void *user_data);
+CARES_EXTERN void        ares_set_socket_configure_callback(
+         ares_channel channel, ares_sock_config_callback callback, void *user_data);
 
-CARES_EXTERN int ares_set_sortlist(ares_channel channel,
-                                   const char *sortstr);
+CARES_EXTERN int  ares_set_sortlist(ares_channel channel, const char *sortstr);
 
-CARES_EXTERN void ares_getaddrinfo(ares_channel channel,
-                                   const char* node,
-                                   const char* service,
-                                   const struct ares_addrinfo_hints* hints,
-                                   ares_addrinfo_callback callback,
-                                   void* arg);
+CARES_EXTERN void ares_getaddrinfo(ares_channel channel, const char *node,
+                                   const char                       *service,
+                                   const struct ares_addrinfo_hints *hints,
+                                   ares_addrinfo_callback callback, void *arg);
 
-CARES_EXTERN void ares_freeaddrinfo(struct ares_addrinfo* ai);
+CARES_EXTERN void ares_freeaddrinfo(struct ares_addrinfo *ai);
 
 /*
  * Virtual function set to have user-managed socket IO.
@@ -428,111 +408,80 @@ CARES_EXTERN void ares_freeaddrinfo(struct ares_addrinfo* ai);
  * ares_sock_config_callback call.
  */
 struct iovec;
+
 struct ares_socket_functions {
-   ares_socket_t(*asocket)(int, int, int, void *);
-   int(*aclose)(ares_socket_t, void *);
-   int(*aconnect)(ares_socket_t, const struct sockaddr *, ares_socklen_t, void *);
-   ares_ssize_t(*arecvfrom)(ares_socket_t, void *, size_t, int, struct sockaddr *, ares_socklen_t *, void *);
-   ares_ssize_t(*asendv)(ares_socket_t, const struct iovec *, int, void *);
+  ares_socket_t (*asocket)(int, int, int, void *);
+  int           (*aclose)(ares_socket_t, void *);
+  int (*aconnect)(ares_socket_t, const struct sockaddr *, ares_socklen_t,
+                  void *);
+  ares_ssize_t (*arecvfrom)(ares_socket_t, void *, size_t, int,
+                            struct sockaddr *, ares_socklen_t *, void *);
+  ares_ssize_t (*asendv)(ares_socket_t, const struct iovec *, int, void *);
 };
 
-CARES_EXTERN void ares_set_socket_functions(ares_channel channel,
-					    const struct ares_socket_functions * funcs,
-					    void *user_data);
-
-CARES_EXTERN void ares_send(ares_channel channel,
-                            const unsigned char *qbuf,
-                            int qlen,
-                            ares_callback callback,
-                            void *arg);
-
-CARES_EXTERN void ares_query(ares_channel channel,
-                             const char *name,
-                             int dnsclass,
-                             int type,
-                             ares_callback callback,
+CARES_EXTERN void
+                  ares_set_socket_functions(ares_channel                        channel,
+                                            const struct ares_socket_functions *funcs,
+                                            void                               *user_data);
+
+CARES_EXTERN void ares_send(ares_channel channel, const unsigned char *qbuf,
+                            int qlen, ares_callback callback, void *arg);
+
+CARES_EXTERN void ares_query(ares_channel channel, const char *name,
+                             int dnsclass, int type, ares_callback callback,
                              void *arg);
 
-CARES_EXTERN void ares_search(ares_channel channel,
-                              const char *name,
-                              int dnsclass,
-                              int type,
-                              ares_callback callback,
+CARES_EXTERN void ares_search(ares_channel channel, const char *name,
+                              int dnsclass, int type, ares_callback callback,
                               void *arg);
 
-CARES_EXTERN void ares_gethostbyname(ares_channel channel,
-                                     const char *name,
-                                     int family,
-                                     ares_host_callback callback,
+CARES_EXTERN void ares_gethostbyname(ares_channel channel, const char *name,
+                                     int family, ares_host_callback callback,
                                      void *arg);
 
-CARES_EXTERN int ares_gethostbyname_file(ares_channel channel,
-                                         const char *name,
-                                         int family,
-                                         struct hostent **host);
+CARES_EXTERN int ares_gethostbyname_file(ares_channel channel, const char *name,
+                                         int family, struct hostent **host);
 
-CARES_EXTERN void ares_gethostbyaddr(ares_channel channel,
-                                     const void *addr,
-                                     int addrlen,
-                                     int family,
-                                     ares_host_callback callback,
-                                     void *arg);
+CARES_EXTERN void ares_gethostbyaddr(ares_channel channel, const void *addr,
+                                     int addrlen, int family,
+                                     ares_host_callback callback, void *arg);
 
-CARES_EXTERN void ares_getnameinfo(ares_channel channel,
+CARES_EXTERN void ares_getnameinfo(ares_channel           channel,
                                    const struct sockaddr *sa,
-                                   ares_socklen_t salen,
-                                   int flags,
-                                   ares_nameinfo_callback callback,
-                                   void *arg);
+                                   ares_socklen_t salen, int flags,
+                                   ares_nameinfo_callback callback, void *arg);
 
-CARES_EXTERN int ares_fds(ares_channel channel,
-                          fd_set *read_fds,
-                          fd_set *write_fds);
+CARES_EXTERN int  ares_fds(ares_channel channel, fd_set *read_fds,
+                           fd_set *write_fds);
 
-CARES_EXTERN int ares_getsock(ares_channel channel,
-                              ares_socket_t *socks,
-                              int numsocks);
+CARES_EXTERN int  ares_getsock(ares_channel channel, ares_socket_t *socks,
+                               int numsocks);
 
-CARES_EXTERN struct timeval *ares_timeout(ares_channel channel,
-                                          struct timeval *maxtv,
-                                          struct timeval *tv);
+CARES_EXTERN struct timeval *
+  ares_timeout(ares_channel channel, struct timeval *maxtv, struct timeval *tv);
 
-CARES_EXTERN void ares_process(ares_channel channel,
-                               fd_set *read_fds,
+CARES_EXTERN void ares_process(ares_channel channel, fd_set *read_fds,
                                fd_set *write_fds);
 
-CARES_EXTERN void ares_process_fd(ares_channel channel,
-                                  ares_socket_t read_fd,
+CARES_EXTERN void ares_process_fd(ares_channel channel, ares_socket_t read_fd,
                                   ares_socket_t write_fd);
 
-CARES_EXTERN int ares_create_query(const char *name,
-                                   int dnsclass,
-                                   int type,
-                                   unsigned short id,
-                                   int rd,
-                                   unsigned char **buf,
-                                   int *buflen,
-                                   int max_udp_size);
-
-CARES_EXTERN int ares_mkquery(const char *name,
-                              int dnsclass,
-                              int type,
-                              unsigned short id,
-                              int rd,
-                              unsigned char **buf,
-                              int *buflen);
-
-CARES_EXTERN int ares_expand_name(const unsigned char *encoded,
-                                  const unsigned char *abuf,
-                                  int alen,
-                                  char **s,
-                                  long *enclen);
-
-CARES_EXTERN int ares_expand_string(const unsigned char *encoded,
-                                    const unsigned char *abuf,
-                                    int alen,
-                                    unsigned char **s,
-                                    long *enclen);
+CARES_EXTERN int  ares_create_query(const char *name, int dnsclass, int type,
+                                    unsigned short id, int rd,
+                                    unsigned char **buf, int *buflen,
+                                    int max_udp_size);
+
+CARES_EXTERN int  ares_mkquery(const char *name, int dnsclass, int type,
+                               unsigned short id, int rd, unsigned char **buf,
+                               int *buflen);
+
+CARES_EXTERN int  ares_expand_name(const unsigned char *encoded,
+                                   const unsigned char *abuf, int alen, char **s,
+                                   long *enclen);
+
+CARES_EXTERN int  ares_expand_string(const unsigned char *encoded,
+                                     const unsigned char *abuf, int alen,
+                                     unsigned char **s, long *enclen);
 
 /*
  * NOTE: before c-ares 1.7.0 we would most often use the system in6_addr
@@ -554,47 +503,47 @@ struct ares_addrttl {
 
 struct ares_addr6ttl {
   struct ares_in6_addr ip6addr;
-  int             ttl;
+  int                  ttl;
 };
 
 struct ares_caa_reply {
-  struct ares_caa_reply  *next;
-  int                     critical;
-  unsigned char          *property;
-  size_t                  plength;  /* plength excludes null termination */
-  unsigned char          *value;
-  size_t                  length;   /* length excludes null termination */
+  struct ares_caa_reply *next;
+  int                    critical;
+  unsigned char         *property;
+  size_t                 plength; /* plength excludes null termination */
+  unsigned char         *value;
+  size_t                 length;  /* length excludes null termination */
 };
 
 struct ares_srv_reply {
-  struct ares_srv_reply  *next;
-  char                   *host;
-  unsigned short          priority;
-  unsigned short          weight;
-  unsigned short          port;
+  struct ares_srv_reply *next;
+  char                  *host;
+  unsigned short         priority;
+  unsigned short         weight;
+  unsigned short         port;
 };
 
 struct ares_mx_reply {
-  struct ares_mx_reply   *next;
-  char                   *host;
-  unsigned short          priority;
+  struct ares_mx_reply *next;
+  char                 *host;
+  unsigned short        priority;
 };
 
 struct ares_txt_reply {
-  struct ares_txt_reply  *next;
-  unsigned char          *txt;
-  size_t                  length;  /* length excludes null termination */
+  struct ares_txt_reply *next;
+  unsigned char         *txt;
+  size_t                 length; /* length excludes null termination */
 };
 
 /* NOTE: This structure is a superset of ares_txt_reply
  */
 struct ares_txt_ext {
-  struct ares_txt_ext      *next;
-  unsigned char            *txt;
-  size_t                   length;
+  struct ares_txt_ext *next;
+  unsigned char       *txt;
+  size_t               length;
   /* 1 - if start of new record
    * 0 - if a chunk in the same record */
-  unsigned char            record_start;
+  unsigned char        record_start;
 };
 
 struct ares_naptr_reply {
@@ -618,11 +567,11 @@ struct ares_soa_reply {
 };
 
 struct ares_uri_reply {
-  struct ares_uri_reply  *next;
-  unsigned short          priority;
-  unsigned short          weight;
-  char                   *uri;
-  int                     ttl;
+  struct ares_uri_reply *next;
+  unsigned short         priority;
+  unsigned short         weight;
+  char                  *uri;
+  int                    ttl;
 };
 
 /*
@@ -672,60 +621,46 @@ struct ares_addrinfo_hints {
 ** so written.
 */
 
-CARES_EXTERN int ares_parse_a_reply(const unsigned char *abuf,
-                                    int alen,
-                                    struct hostent **host,
-                                    struct ares_addrttl *addrttls,
-                                    int *naddrttls);
-
-CARES_EXTERN int ares_parse_aaaa_reply(const unsigned char *abuf,
-                                       int alen,
-                                       struct hostent **host,
-                                       struct ares_addr6ttl *addrttls,
-                                       int *naddrttls);
-
-CARES_EXTERN int ares_parse_caa_reply(const unsigned char* abuf,
-				      int alen,
-				      struct ares_caa_reply** caa_out);
-
-CARES_EXTERN int ares_parse_ptr_reply(const unsigned char *abuf,
-                                      int alen,
-                                      const void *addr,
-                                      int addrlen,
-                                      int family,
-                                      struct hostent **host);
+CARES_EXTERN int  ares_parse_a_reply(const unsigned char *abuf, int alen,
+                                     struct hostent     **host,
+                                     struct ares_addrttl *addrttls,
+                                     int                 *naddrttls);
+
+CARES_EXTERN int  ares_parse_aaaa_reply(const unsigned char *abuf, int alen,
+                                        struct hostent      **host,
+                                        struct ares_addr6ttl *addrttls,
+                                        int                  *naddrttls);
+
+CARES_EXTERN int  ares_parse_caa_reply(const unsigned char *abuf, int alen,
+                                       struct ares_caa_reply **caa_out);
 
-CARES_EXTERN int ares_parse_ns_reply(const unsigned char *abuf,
-                                     int alen,
-                                     struct hostent **host);
+CARES_EXTERN int  ares_parse_ptr_reply(const unsigned char *abuf, int alen,
+                                       const void *addr, int addrlen, int family,
+                                       struct hostent **host);
 
-CARES_EXTERN int ares_parse_srv_reply(const unsigned char* abuf,
-                                      int alen,
-                                      struct ares_srv_reply** srv_out);
+CARES_EXTERN int  ares_parse_ns_reply(const unsigned char *abuf, int alen,
+                                      struct hostent **host);
+
+CARES_EXTERN int  ares_parse_srv_reply(const unsigned char *abuf, int alen,
+                                       struct ares_srv_reply **srv_out);
 
-CARES_EXTERN int ares_parse_mx_reply(const unsigned char* abuf,
-                                      int alen,
-                                      struct ares_mx_reply** mx_out);
+CARES_EXTERN int  ares_parse_mx_reply(const unsigned char *abuf, int alen,
+                                      struct ares_mx_reply **mx_out);
 
-CARES_EXTERN int ares_parse_txt_reply(const unsigned char* abuf,
-                                      int alen,
-                                      struct ares_txt_reply** txt_out);
+CARES_EXTERN int  ares_parse_txt_reply(const unsigned char *abuf, int alen,
+                                       struct ares_txt_reply **txt_out);
 
-CARES_EXTERN int ares_parse_txt_reply_ext(const unsigned char* abuf,
-                                          int alen,
-                                          struct ares_txt_ext** txt_out);
+CARES_EXTERN int  ares_parse_txt_reply_ext(const unsigned char *abuf, int alen,
+                                           struct ares_txt_ext **txt_out);
 
-CARES_EXTERN int ares_parse_naptr_reply(const unsigned char* abuf,
-                                        int alen,
-                                        struct ares_naptr_reply** naptr_out);
+CARES_EXTERN int  ares_parse_naptr_reply(const unsigned char *abuf, int alen,
+                                         struct ares_naptr_reply **naptr_out);
 
-CARES_EXTERN int ares_parse_soa_reply(const unsigned char* abuf,
-				      int alen,
-				      struct ares_soa_reply** soa_out);
+CARES_EXTERN int  ares_parse_soa_reply(const unsigned char *abuf, int alen,
+                                       struct ares_soa_reply **soa_out);
 
-CARES_EXTERN int ares_parse_uri_reply(const unsigned char* abuf,
-                                      int alen,
-                                      struct ares_uri_reply** uri_out);
+CARES_EXTERN int  ares_parse_uri_reply(const unsigned char *abuf, int alen,
+                                       struct ares_uri_reply **uri_out);
 
 CARES_EXTERN void ares_free_string(void *str);
 
@@ -737,7 +672,8 @@ CARES_EXTERN const char *ares_strerror(int code);
 
 struct ares_addr_node {
   struct ares_addr_node *next;
-  int family;
+  int                    family;
+
   union {
     struct in_addr       addr4;
     struct ares_in6_addr addr6;
@@ -746,38 +682,40 @@ struct ares_addr_node {
 
 struct ares_addr_port_node {
   struct ares_addr_port_node *next;
-  int family;
+  int                         family;
+
   union {
     struct in_addr       addr4;
     struct ares_in6_addr addr6;
   } addr;
+
   int udp_port;
   int tcp_port;
 };
 
-CARES_EXTERN int ares_set_servers(ares_channel channel,
-                                  struct ares_addr_node *servers);
-CARES_EXTERN int ares_set_servers_ports(ares_channel channel,
-                                        struct ares_addr_port_node *servers);
+CARES_EXTERN int         ares_set_servers(ares_channel           channel,
+                                          struct ares_addr_node *servers);
+CARES_EXTERN int         ares_set_servers_ports(ares_channel                channel,
+                                                struct ares_addr_port_node *servers);
 
 /* Incomming string format: host[:port][,host[:port]]... */
-CARES_EXTERN int ares_set_servers_csv(ares_channel channel,
-                                      const char* servers);
-CARES_EXTERN int ares_set_servers_ports_csv(ares_channel channel,
-                                            const char* servers);
+CARES_EXTERN int         ares_set_servers_csv(ares_channel channel,
+                                              const char  *servers);
+CARES_EXTERN int         ares_set_servers_ports_csv(ares_channel channel,
+                                                    const char  *servers);
 
-CARES_EXTERN int ares_get_servers(ares_channel channel,
-                                  struct ares_addr_node **servers);
-CARES_EXTERN int ares_get_servers_ports(ares_channel channel,
-                                        struct ares_addr_port_node **servers);
+CARES_EXTERN int         ares_get_servers(ares_channel            channel,
+                                          struct ares_addr_node **servers);
+CARES_EXTERN int         ares_get_servers_ports(ares_channel                 channel,
+                                                struct ares_addr_port_node **servers);
 
 CARES_EXTERN const char *ares_inet_ntop(int af, const void *src, char *dst,
                                         ares_socklen_t size);
 
-CARES_EXTERN int ares_inet_pton(int af, const char *src, void *dst);
+CARES_EXTERN int         ares_inet_pton(int af, const char *src, void *dst);
 
 
-#ifdef  __cplusplus
+#ifdef __cplusplus
 }
 #endif
 
diff --git a/include/ares_dns.h b/include/ares_dns.h
index e49c3d2..46edbbb 100644
--- a/include/ares_dns.h
+++ b/include/ares_dns.h
@@ -40,84 +40,88 @@
  * Macro DNS__16BIT reads a network short (16 bit) given in network
  * byte order, and returns its value as an unsigned short.
  */
-#define DNS__16BIT(p)  ((unsigned short)((unsigned int) 0xffff & \
-                         (((unsigned int)((unsigned char)(p)[0]) << 8U) | \
-                          ((unsigned int)((unsigned char)(p)[1])))))
+#define DNS__16BIT(p)                                                \
+  ((unsigned short)((unsigned int)0xffff &                           \
+                    (((unsigned int)((unsigned char)(p)[0]) << 8U) | \
+                     ((unsigned int)((unsigned char)(p)[1])))))
 
 /*
  * Macro DNS__32BIT reads a network long (32 bit) given in network
  * byte order, and returns its value as an unsigned int.
  */
-#define DNS__32BIT(p)  ((unsigned int) \
-                         (((unsigned int)((unsigned char)(p)[0]) << 24U) | \
-                          ((unsigned int)((unsigned char)(p)[1]) << 16U) | \
-                          ((unsigned int)((unsigned char)(p)[2]) <<  8U) | \
-                          ((unsigned int)((unsigned char)(p)[3]))))
+#define DNS__32BIT(p)                                              \
+  ((unsigned int)(((unsigned int)((unsigned char)(p)[0]) << 24U) | \
+                  ((unsigned int)((unsigned char)(p)[1]) << 16U) | \
+                  ((unsigned int)((unsigned char)(p)[2]) << 8U) |  \
+                  ((unsigned int)((unsigned char)(p)[3]))))
 
-#define DNS__SET16BIT(p, v)  (((p)[0] = (unsigned char)(((v) >> 8) & 0xff)), \
-                              ((p)[1] = (unsigned char)((v) & 0xff)))
-#define DNS__SET32BIT(p, v)  (((p)[0] = (unsigned char)(((v) >> 24) & 0xff)), \
-                              ((p)[1] = (unsigned char)(((v) >> 16) & 0xff)), \
-                              ((p)[2] = (unsigned char)(((v) >> 8) & 0xff)), \
-                              ((p)[3] = (unsigned char)((v) & 0xff)))
+#define DNS__SET16BIT(p, v)                       \
+  (((p)[0] = (unsigned char)(((v) >> 8) & 0xff)), \
+   ((p)[1] = (unsigned char)((v) & 0xff)))
+#define DNS__SET32BIT(p, v)                        \
+  (((p)[0] = (unsigned char)(((v) >> 24) & 0xff)), \
+   ((p)[1] = (unsigned char)(((v) >> 16) & 0xff)), \
+   ((p)[2] = (unsigned char)(((v) >> 8) & 0xff)),  \
+   ((p)[3] = (unsigned char)((v) & 0xff)))
 
 #if 0
 /* we cannot use this approach on systems where we can't access 16/32 bit
    data on un-aligned addresses */
-#define DNS__16BIT(p)                   ntohs(*(unsigned short*)(p))
-#define DNS__32BIT(p)                   ntohl(*(unsigned long*)(p))
-#define DNS__SET16BIT(p, v)             *(unsigned short*)(p) = htons(v)
-#define DNS__SET32BIT(p, v)             *(unsigned long*)(p) = htonl(v)
+#  define DNS__16BIT(p)       ntohs(*(unsigned short *)(p))
+#  define DNS__32BIT(p)       ntohl(*(unsigned long *)(p))
+#  define DNS__SET16BIT(p, v) *(unsigned short *)(p) = htons(v)
+#  define DNS__SET32BIT(p, v) *(unsigned long *)(p) = htonl(v)
 #endif
 
 /* Macros for parsing a DNS header */
-#define DNS_HEADER_QID(h)               DNS__16BIT(h)
-#define DNS_HEADER_QR(h)                (((h)[2] >> 7) & 0x1)
-#define DNS_HEADER_OPCODE(h)            (((h)[2] >> 3) & 0xf)
-#define DNS_HEADER_AA(h)                (((h)[2] >> 2) & 0x1)
-#define DNS_HEADER_TC(h)                (((h)[2] >> 1) & 0x1)
-#define DNS_HEADER_RD(h)                ((h)[2] & 0x1)
-#define DNS_HEADER_RA(h)                (((h)[3] >> 7) & 0x1)
-#define DNS_HEADER_Z(h)                 (((h)[3] >> 4) & 0x7)
-#define DNS_HEADER_RCODE(h)             ((h)[3] & 0xf)
-#define DNS_HEADER_QDCOUNT(h)           DNS__16BIT((h) + 4)
-#define DNS_HEADER_ANCOUNT(h)           DNS__16BIT((h) + 6)
-#define DNS_HEADER_NSCOUNT(h)           DNS__16BIT((h) + 8)
-#define DNS_HEADER_ARCOUNT(h)           DNS__16BIT((h) + 10)
+#define DNS_HEADER_QID(h)     DNS__16BIT(h)
+#define DNS_HEADER_QR(h)      (((h)[2] >> 7) & 0x1)
+#define DNS_HEADER_OPCODE(h)  (((h)[2] >> 3) & 0xf)
+#define DNS_HEADER_AA(h)      (((h)[2] >> 2) & 0x1)
+#define DNS_HEADER_TC(h)      (((h)[2] >> 1) & 0x1)
+#define DNS_HEADER_RD(h)      ((h)[2] & 0x1)
+#define DNS_HEADER_RA(h)      (((h)[3] >> 7) & 0x1)
+#define DNS_HEADER_Z(h)       (((h)[3] >> 4) & 0x7)
+#define DNS_HEADER_RCODE(h)   ((h)[3] & 0xf)
+#define DNS_HEADER_QDCOUNT(h) DNS__16BIT((h) + 4)
+#define DNS_HEADER_ANCOUNT(h) DNS__16BIT((h) + 6)
+#define DNS_HEADER_NSCOUNT(h) DNS__16BIT((h) + 8)
+#define DNS_HEADER_ARCOUNT(h) DNS__16BIT((h) + 10)
 
 /* Macros for constructing a DNS header */
-#define DNS_HEADER_SET_QID(h, v)      DNS__SET16BIT(h, v)
-#define DNS_HEADER_SET_QR(h, v)       ((h)[2] |= (unsigned char)(((v) & 0x1) << 7))
-#define DNS_HEADER_SET_OPCODE(h, v)   ((h)[2] |= (unsigned char)(((v) & 0xf) << 3))
-#define DNS_HEADER_SET_AA(h, v)       ((h)[2] |= (unsigned char)(((v) & 0x1) << 2))
-#define DNS_HEADER_SET_TC(h, v)       ((h)[2] |= (unsigned char)(((v) & 0x1) << 1))
-#define DNS_HEADER_SET_RD(h, v)       ((h)[2] |= (unsigned char)((v) & 0x1))
-#define DNS_HEADER_SET_RA(h, v)       ((h)[3] |= (unsigned char)(((v) & 0x1) << 7))
-#define DNS_HEADER_SET_Z(h, v)        ((h)[3] |= (unsigned char)(((v) & 0x7) << 4))
-#define DNS_HEADER_SET_RCODE(h, v)    ((h)[3] |= (unsigned char)((v) & 0xf))
-#define DNS_HEADER_SET_QDCOUNT(h, v)  DNS__SET16BIT((h) + 4, v)
-#define DNS_HEADER_SET_ANCOUNT(h, v)  DNS__SET16BIT((h) + 6, v)
-#define DNS_HEADER_SET_NSCOUNT(h, v)  DNS__SET16BIT((h) + 8, v)
-#define DNS_HEADER_SET_ARCOUNT(h, v)  DNS__SET16BIT((h) + 10, v)
+#define DNS_HEADER_SET_QID(h, v) DNS__SET16BIT(h, v)
+#define DNS_HEADER_SET_QR(h, v)  ((h)[2] |= (unsigned char)(((v) & 0x1) << 7))
+#define DNS_HEADER_SET_OPCODE(h, v) \
+  ((h)[2] |= (unsigned char)(((v) & 0xf) << 3))
+#define DNS_HEADER_SET_AA(h, v)      ((h)[2] |= (unsigned char)(((v) & 0x1) << 2))
+#define DNS_HEADER_SET_TC(h, v)      ((h)[2] |= (unsigned char)(((v) & 0x1) << 1))
+#define DNS_HEADER_SET_RD(h, v)      ((h)[2] |= (unsigned char)((v) & 0x1))
+#define DNS_HEADER_SET_RA(h, v)      ((h)[3] |= (unsigned char)(((v) & 0x1) << 7))
+#define DNS_HEADER_SET_Z(h, v)       ((h)[3] |= (unsigned char)(((v) & 0x7) << 4))
+#define DNS_HEADER_SET_RCODE(h, v)   ((h)[3] |= (unsigned char)((v) & 0xf))
+#define DNS_HEADER_SET_QDCOUNT(h, v) DNS__SET16BIT((h) + 4, v)
+#define DNS_HEADER_SET_ANCOUNT(h, v) DNS__SET16BIT((h) + 6, v)
+#define DNS_HEADER_SET_NSCOUNT(h, v) DNS__SET16BIT((h) + 8, v)
+#define DNS_HEADER_SET_ARCOUNT(h, v) DNS__SET16BIT((h) + 10, v)
 
 /* Macros for parsing the fixed part of a DNS question */
-#define DNS_QUESTION_TYPE(q)            DNS__16BIT(q)
-#define DNS_QUESTION_CLASS(q)           DNS__16BIT((q) + 2)
+#define DNS_QUESTION_TYPE(q)  DNS__16BIT(q)
+#define DNS_QUESTION_CLASS(q) DNS__16BIT((q) + 2)
 
 /* Macros for constructing the fixed part of a DNS question */
-#define DNS_QUESTION_SET_TYPE(q, v)     DNS__SET16BIT(q, v)
-#define DNS_QUESTION_SET_CLASS(q, v)    DNS__SET16BIT((q) + 2, v)
+#define DNS_QUESTION_SET_TYPE(q, v)  DNS__SET16BIT(q, v)
+#define DNS_QUESTION_SET_CLASS(q, v) DNS__SET16BIT((q) + 2, v)
 
 /* Macros for parsing the fixed part of a DNS resource record */
-#define DNS_RR_TYPE(r)                  DNS__16BIT(r)
-#define DNS_RR_CLASS(r)                 DNS__16BIT((r) + 2)
-#define DNS_RR_TTL(r)                   DNS__32BIT((r) + 4)
-#define DNS_RR_LEN(r)                   DNS__16BIT((r) + 8)
+#define DNS_RR_TYPE(r)  DNS__16BIT(r)
+#define DNS_RR_CLASS(r) DNS__16BIT((r) + 2)
+#define DNS_RR_TTL(r)   DNS__32BIT((r) + 4)
+#define DNS_RR_LEN(r)   DNS__16BIT((r) + 8)
 
 /* Macros for constructing the fixed part of a DNS resource record */
-#define DNS_RR_SET_TYPE(r, v)           DNS__SET16BIT(r, v)
-#define DNS_RR_SET_CLASS(r, v)          DNS__SET16BIT((r) + 2, v)
-#define DNS_RR_SET_TTL(r, v)            DNS__SET32BIT((r) + 4, v)
-#define DNS_RR_SET_LEN(r, v)            DNS__SET16BIT((r) + 8, v)
+#define DNS_RR_SET_TYPE(r, v)  DNS__SET16BIT(r, v)
+#define DNS_RR_SET_CLASS(r, v) DNS__SET16BIT((r) + 2, v)
+#define DNS_RR_SET_TTL(r, v)   DNS__SET32BIT((r) + 4, v)
+#define DNS_RR_SET_LEN(r, v)   DNS__SET16BIT((r) + 8, v)
 
 #endif /* HEADER_CARES_DNS_H */
diff --git a/include/ares_nameser.h b/include/ares_nameser.h
index 3138d89..bdc746b 100644
--- a/include/ares_nameser.h
+++ b/include/ares_nameser.h
@@ -44,51 +44,51 @@
  */
 
 #ifndef NS_PACKETSZ
-#  define NS_PACKETSZ     512   /* maximum packet size */
+#  define NS_PACKETSZ 512 /* maximum packet size */
 #endif
 
 #ifndef NS_MAXDNAME
-#  define NS_MAXDNAME     256   /* maximum domain name */
+#  define NS_MAXDNAME 256 /* maximum domain name */
 #endif
 
 #ifndef NS_MAXCDNAME
-#  define NS_MAXCDNAME    255   /* maximum compressed domain name */
+#  define NS_MAXCDNAME 255 /* maximum compressed domain name */
 #endif
 
 #ifndef NS_MAXLABEL
-#  define NS_MAXLABEL     63
+#  define NS_MAXLABEL 63
 #endif
 
 #ifndef NS_HFIXEDSZ
-#  define NS_HFIXEDSZ     12    /* #/bytes of fixed data in header */
+#  define NS_HFIXEDSZ 12 /* #/bytes of fixed data in header */
 #endif
 
 #ifndef NS_QFIXEDSZ
-#  define NS_QFIXEDSZ     4     /* #/bytes of fixed data in query */
+#  define NS_QFIXEDSZ 4 /* #/bytes of fixed data in query */
 #endif
 
 #ifndef NS_RRFIXEDSZ
-#  define NS_RRFIXEDSZ    10    /* #/bytes of fixed data in r record */
+#  define NS_RRFIXEDSZ 10 /* #/bytes of fixed data in r record */
 #endif
 
 #ifndef NS_INT16SZ
-#  define NS_INT16SZ      2
+#  define NS_INT16SZ 2
 #endif
 
 #ifndef NS_INADDRSZ
-#  define NS_INADDRSZ     4
+#  define NS_INADDRSZ 4
 #endif
 
 #ifndef NS_IN6ADDRSZ
-#  define NS_IN6ADDRSZ    16
+#  define NS_IN6ADDRSZ 16
 #endif
 
 #ifndef NS_CMPRSFLGS
-#  define NS_CMPRSFLGS    0xc0  /* Flag bits indicating name compression. */
+#  define NS_CMPRSFLGS 0xc0 /* Flag bits indicating name compression. */
 #endif
 
 #ifndef NS_DEFAULTPORT
-#  define NS_DEFAULTPORT  53    /* For both TCP and UDP. */
+#  define NS_DEFAULTPORT 53 /* For both TCP and UDP. */
 #endif
 
 /* ============================================================================
@@ -99,106 +99,106 @@
 #ifndef CARES_HAVE_ARPA_NAMESER_H
 
 typedef enum __ns_class {
-    ns_c_invalid = 0,       /* Cookie. */
-    ns_c_in = 1,            /* Internet. */
-    ns_c_2 = 2,             /* unallocated/unsupported. */
-    ns_c_chaos = 3,         /* MIT Chaos-net. */
-    ns_c_hs = 4,            /* MIT Hesiod. */
-    /* Query class values which do not appear in resource records */
-    ns_c_none = 254,        /* for prereq. sections in update requests */
-    ns_c_any = 255,         /* Wildcard match. */
-    ns_c_max = 65536
+  ns_c_invalid = 0, /* Cookie. */
+  ns_c_in      = 1, /* Internet. */
+  ns_c_2       = 2, /* unallocated/unsupported. */
+  ns_c_chaos   = 3, /* MIT Chaos-net. */
+  ns_c_hs      = 4, /* MIT Hesiod. */
+  /* Query class values which do not appear in resource records */
+  ns_c_none = 254, /* for prereq. sections in update requests */
+  ns_c_any  = 255, /* Wildcard match. */
+  ns_c_max  = 65536
 } ns_class;
 
 typedef enum __ns_type {
-    ns_t_invalid = 0,       /* Cookie. */
-    ns_t_a = 1,             /* Host address. */
-    ns_t_ns = 2,            /* Authoritative server. */
-    ns_t_md = 3,            /* Mail destination. */
-    ns_t_mf = 4,            /* Mail forwarder. */
-    ns_t_cname = 5,         /* Canonical name. */
-    ns_t_soa = 6,           /* Start of authority zone. */
-    ns_t_mb = 7,            /* Mailbox domain name. */
-    ns_t_mg = 8,            /* Mail group member. */
-    ns_t_mr = 9,            /* Mail rename name. */
-    ns_t_null = 10,         /* Null resource record. */
-    ns_t_wks = 11,          /* Well known service. */
-    ns_t_ptr = 12,          /* Domain name pointer. */
-    ns_t_hinfo = 13,        /* Host information. */
-    ns_t_minfo = 14,        /* Mailbox information. */
-    ns_t_mx = 15,           /* Mail routing information. */
-    ns_t_txt = 16,          /* Text strings. */
-    ns_t_rp = 17,           /* Responsible person. */
-    ns_t_afsdb = 18,        /* AFS cell database. */
-    ns_t_x25 = 19,          /* X_25 calling address. */
-    ns_t_isdn = 20,         /* ISDN calling address. */
-    ns_t_rt = 21,           /* Router. */
-    ns_t_nsap = 22,         /* NSAP address. */
-    ns_t_nsap_ptr = 23,     /* Reverse NSAP lookup (deprecated). */
-    ns_t_sig = 24,          /* Security signature. */
-    ns_t_key = 25,          /* Security key. */
-    ns_t_px = 26,           /* X.400 mail mapping. */
-    ns_t_gpos = 27,         /* Geographical position (withdrawn). */
-    ns_t_aaaa = 28,         /* Ip6 Address. */
-    ns_t_loc = 29,          /* Location Information. */
-    ns_t_nxt = 30,          /* Next domain (security). */
-    ns_t_eid = 31,          /* Endpoint identifier. */
-    ns_t_nimloc = 32,       /* Nimrod Locator. */
-    ns_t_srv = 33,          /* Server Selection. */
-    ns_t_atma = 34,         /* ATM Address */
-    ns_t_naptr = 35,        /* Naming Authority PoinTeR */
-    ns_t_kx = 36,           /* Key Exchange */
-    ns_t_cert = 37,         /* Certification record */
-    ns_t_a6 = 38,           /* IPv6 address (deprecates AAAA) */
-    ns_t_dname = 39,        /* Non-terminal DNAME (for IPv6) */
-    ns_t_sink = 40,         /* Kitchen sink (experimentatl) */
-    ns_t_opt = 41,          /* EDNS0 option (meta-RR) */
-    ns_t_apl = 42,          /* Address prefix list (RFC3123) */
-    ns_t_ds = 43,           /* Delegation Signer (RFC4034) */
-    ns_t_sshfp = 44,        /* SSH Key Fingerprint (RFC4255) */
-    ns_t_rrsig = 46,        /* Resource Record Signature (RFC4034) */
-    ns_t_nsec = 47,         /* Next Secure (RFC4034) */
-    ns_t_dnskey = 48,       /* DNS Public Key (RFC4034) */
-    ns_t_tkey = 249,        /* Transaction key */
-    ns_t_tsig = 250,        /* Transaction signature. */
-    ns_t_ixfr = 251,        /* Incremental zone transfer. */
-    ns_t_axfr = 252,        /* Transfer zone of authority. */
-    ns_t_mailb = 253,       /* Transfer mailbox records. */
-    ns_t_maila = 254,       /* Transfer mail agent records. */
-    ns_t_any = 255,         /* Wildcard match. */
-    ns_t_uri = 256,         /* Uniform Resource Identifier (RFC7553) */
-    ns_t_caa = 257,         /* Certification Authority Authorization. */
-    ns_t_max = 65536
+  ns_t_invalid  = 0,   /* Cookie. */
+  ns_t_a        = 1,   /* Host address. */
+  ns_t_ns       = 2,   /* Authoritative server. */
+  ns_t_md       = 3,   /* Mail destination. */
+  ns_t_mf       = 4,   /* Mail forwarder. */
+  ns_t_cname    = 5,   /* Canonical name. */
+  ns_t_soa      = 6,   /* Start of authority zone. */
+  ns_t_mb       = 7,   /* Mailbox domain name. */
+  ns_t_mg       = 8,   /* Mail group member. */
+  ns_t_mr       = 9,   /* Mail rename name. */
+  ns_t_null     = 10,  /* Null resource record. */
+  ns_t_wks      = 11,  /* Well known service. */
+  ns_t_ptr      = 12,  /* Domain name pointer. */
+  ns_t_hinfo    = 13,  /* Host information. */
+  ns_t_minfo    = 14,  /* Mailbox information. */
+  ns_t_mx       = 15,  /* Mail routing information. */
+  ns_t_txt      = 16,  /* Text strings. */
+  ns_t_rp       = 17,  /* Responsible person. */
+  ns_t_afsdb    = 18,  /* AFS cell database. */
+  ns_t_x25      = 19,  /* X_25 calling address. */
+  ns_t_isdn     = 20,  /* ISDN calling address. */
+  ns_t_rt       = 21,  /* Router. */
+  ns_t_nsap     = 22,  /* NSAP address. */
+  ns_t_nsap_ptr = 23,  /* Reverse NSAP lookup (deprecated). */
+  ns_t_sig      = 24,  /* Security signature. */
+  ns_t_key      = 25,  /* Security key. */
+  ns_t_px       = 26,  /* X.400 mail mapping. */
+  ns_t_gpos     = 27,  /* Geographical position (withdrawn). */
+  ns_t_aaaa     = 28,  /* Ip6 Address. */
+  ns_t_loc      = 29,  /* Location Information. */
+  ns_t_nxt      = 30,  /* Next domain (security). */
+  ns_t_eid      = 31,  /* Endpoint identifier. */
+  ns_t_nimloc   = 32,  /* Nimrod Locator. */
+  ns_t_srv      = 33,  /* Server Selection. */
+  ns_t_atma     = 34,  /* ATM Address */
+  ns_t_naptr    = 35,  /* Naming Authority PoinTeR */
+  ns_t_kx       = 36,  /* Key Exchange */
+  ns_t_cert     = 37,  /* Certification record */
+  ns_t_a6       = 38,  /* IPv6 address (deprecates AAAA) */
+  ns_t_dname    = 39,  /* Non-terminal DNAME (for IPv6) */
+  ns_t_sink     = 40,  /* Kitchen sink (experimentatl) */
+  ns_t_opt      = 41,  /* EDNS0 option (meta-RR) */
+  ns_t_apl      = 42,  /* Address prefix list (RFC3123) */
+  ns_t_ds       = 43,  /* Delegation Signer (RFC4034) */
+  ns_t_sshfp    = 44,  /* SSH Key Fingerprint (RFC4255) */
+  ns_t_rrsig    = 46,  /* Resource Record Signature (RFC4034) */
+  ns_t_nsec     = 47,  /* Next Secure (RFC4034) */
+  ns_t_dnskey   = 48,  /* DNS Public Key (RFC4034) */
+  ns_t_tkey     = 249, /* Transaction key */
+  ns_t_tsig     = 250, /* Transaction signature. */
+  ns_t_ixfr     = 251, /* Incremental zone transfer. */
+  ns_t_axfr     = 252, /* Transfer zone of authority. */
+  ns_t_mailb    = 253, /* Transfer mailbox records. */
+  ns_t_maila    = 254, /* Transfer mail agent records. */
+  ns_t_any      = 255, /* Wildcard match. */
+  ns_t_uri      = 256, /* Uniform Resource Identifier (RFC7553) */
+  ns_t_caa      = 257, /* Certification Authority Authorization. */
+  ns_t_max      = 65536
 } ns_type;
 
 typedef enum __ns_opcode {
-    ns_o_query = 0,         /* Standard query. */
-    ns_o_iquery = 1,        /* Inverse query (deprecated/unsupported). */
-    ns_o_status = 2,        /* Name server status query (unsupported). */
-                                /* Opcode 3 is undefined/reserved. */
-    ns_o_notify = 4,        /* Zone change notification. */
-    ns_o_update = 5,        /* Zone update message. */
-    ns_o_max = 6
+  ns_o_query  = 0, /* Standard query. */
+  ns_o_iquery = 1, /* Inverse query (deprecated/unsupported). */
+  ns_o_status = 2, /* Name server status query (unsupported). */
+                   /* Opcode 3 is undefined/reserved. */
+  ns_o_notify = 4, /* Zone change notification. */
+  ns_o_update = 5, /* Zone update message. */
+  ns_o_max    = 6
 } ns_opcode;
 
 typedef enum __ns_rcode {
-    ns_r_noerror = 0,       /* No error occurred. */
-    ns_r_formerr = 1,       /* Format error. */
-    ns_r_servfail = 2,      /* Server failure. */
-    ns_r_nxdomain = 3,      /* Name error. */
-    ns_r_notimpl = 4,       /* Unimplemented. */
-    ns_r_refused = 5,       /* Operation refused. */
-    /* these are for BIND_UPDATE */
-    ns_r_yxdomain = 6,      /* Name exists */
-    ns_r_yxrrset = 7,       /* RRset exists */
-    ns_r_nxrrset = 8,       /* RRset does not exist */
-    ns_r_notauth = 9,       /* Not authoritative for zone */
-    ns_r_notzone = 10,      /* Zone of record different from zone section */
-    ns_r_max = 11,
-    /* The following are TSIG extended errors */
-    ns_r_badsig = 16,
-    ns_r_badkey = 17,
-    ns_r_badtime = 18
+  ns_r_noerror  = 0, /* No error occurred. */
... [unselected diff lines omitted by frozen H0-anchored rule] ...
+  /* these are for BIND_UPDATE */
+  ns_r_yxdomain = 6,  /* Name exists */
+  ns_r_yxrrset  = 7,  /* RRset exists */
+  ns_r_nxrrset  = 8,  /* RRset does not exist */
+  ns_r_notauth  = 9,  /* Not authoritative for zone */
+  ns_r_notzone  = 10, /* Zone of record different from zone section */
+  ns_r_max      = 11,
+  /* The following are TSIG extended errors */
+  ns_r_badsig  = 16,
+  ns_r_badkey  = 17,
+  ns_r_badtime = 18
 } ns_rcode;
 
 #endif /* CARES_HAVE_ARPA_NAMESER_H */
@@ -212,45 +212,45 @@ typedef enum __ns_rcode {
  */
 
 #ifndef PACKETSZ
-#  define PACKETSZ         NS_PACKETSZ
+#  define PACKETSZ NS_PACKETSZ
 #endif
 
 #ifndef MAXDNAME
-#  define MAXDNAME         NS_MAXDNAME
+#  define MAXDNAME NS_MAXDNAME
 #endif
 
 #ifndef MAXCDNAME
-#  define MAXCDNAME        NS_MAXCDNAME
+#  define MAXCDNAME NS_MAXCDNAME
 #endif
 
 #ifndef MAXLABEL
-#  define MAXLABEL         NS_MAXLABEL
+#  define MAXLABEL NS_MAXLABEL
 #endif
 
 #ifndef HFIXEDSZ
-#  define HFIXEDSZ         NS_HFIXEDSZ
+#  define HFIXEDSZ NS_HFIXEDSZ
 #endif
 
 #ifndef QFIXEDSZ
-#  define QFIXEDSZ         NS_QFIXEDSZ
+#  define QFIXEDSZ NS_QFIXEDSZ
 #endif
 
 #ifndef RRFIXEDSZ
-#  define RRFIXEDSZ        NS_RRFIXEDSZ
+#  define RRFIXEDSZ NS_RRFIXEDSZ
 #endif
 
 #ifndef INDIR_MASK
-#  define INDIR_MASK       NS_CMPRSFLGS
+#  define INDIR_MASK NS_CMPRSFLGS
 #endif
 
 #ifndef NAMESERVER_PORT
-#  define NAMESERVER_PORT  NS_DEFAULTPORT
+#  define NAMESERVER_PORT NS_DEFAULTPORT
 #endif
 
 
 /* opcodes */
 #ifndef O_QUERY
-#  define O_QUERY 0  /* ns_o_query */
+#  define O_QUERY 0 /* ns_o_query */
 #endif
 #ifndef O_IQUERY
 #  define O_IQUERY 1 /* ns_o_iquery */
@@ -268,242 +268,242 @@ typedef enum __ns_rcode {
 
 /* response codes */
 #ifndef SERVFAIL
-#  define SERVFAIL        ns_r_servfail
+#  define SERVFAIL ns_r_servfail
 #endif
 #ifndef NOTIMP
-#  define NOTIMP          ns_r_notimpl
+#  define NOTIMP ns_r_notimpl
 #endif
 #ifndef REFUSED
-#  define REFUSED         ns_r_refused
+#  define REFUSED ns_r_refused
 #endif
 #if defined(_WIN32) && !defined(HAVE_ARPA_NAMESER_COMPAT_H) && defined(NOERROR)
 #  undef NOERROR /* it seems this is already defined in winerror.h */
 #endif
 #ifndef NOERROR
-#  define NOERROR         ns_r_noerror
+#  define NOERROR ns_r_noerror
 #endif
 #ifndef FORMERR
-#  define FORMERR         ns_r_formerr
+#  define FORMERR ns_r_formerr
 #endif
 #ifndef NXDOMAIN
-#  define NXDOMAIN        ns_r_nxdomain
+#  define NXDOMAIN ns_r_nxdomain
 #endif
 /* Non-standard response codes, use numeric values */
 #ifndef YXDOMAIN
-#  define YXDOMAIN        6 /* ns_r_yxdomain */
+#  define YXDOMAIN 6 /* ns_r_yxdomain */
 #endif
 #ifndef YXRRSET
-#  define YXRRSET         7 /* ns_r_yxrrset */
+#  define YXRRSET 7 /* ns_r_yxrrset */
 #endif
 #ifndef NXRRSET
-#  define NXRRSET         8 /* ns_r_nxrrset */
+#  define NXRRSET 8 /* ns_r_nxrrset */
 #endif
 #ifndef NOTAUTH
-#  define NOTAUTH         9 /* ns_r_notauth */
+#  define NOTAUTH 9 /* ns_r_notauth */
 #endif
 #ifndef NOTZONE
-#  define NOTZONE         10 /* ns_r_notzone */
+#  define NOTZONE 10 /* ns_r_notzone */
 #endif
 #ifndef TSIG_BADSIG
-#  define TSIG_BADSIG     16 /* ns_r_badsig */
+#  define TSIG_BADSIG 16 /* ns_r_badsig */
 #endif
 #ifndef TSIG_BADKEY
-#  define TSIG_BADKEY     17 /* ns_r_badkey */
+#  define TSIG_BADKEY 17 /* ns_r_badkey */
 #endif
 #ifndef TSIG_BADTIME
-#  define TSIG_BADTIME    18 /* ns_r_badtime */
+#  define TSIG_BADTIME 18 /* ns_r_badtime */
 #endif
 
 
 /* classes */
 #ifndef C_IN
-#  define C_IN            1 /* ns_c_in */
+#  define C_IN 1 /* ns_c_in */
 #endif
 #ifndef C_CHAOS
-#  define C_CHAOS         3 /* ns_c_chaos */
+#  define C_CHAOS 3 /* ns_c_chaos */
 #endif
 #ifndef C_HS
-#  define C_HS            4 /* ns_c_hs */
+#  define C_HS 4 /* ns_c_hs */
 #endif
 #ifndef C_NONE
-#  define C_NONE          254 /* ns_c_none */
+#  define C_NONE 254 /* ns_c_none */
 #endif
 #ifndef C_ANY
-#  define C_ANY           255 /*  ns_c_any */
+#  define C_ANY 255 /*  ns_c_any */
 #endif
 
 
 /* types */
 #ifndef T_A
-#  define T_A             1   /* ns_t_a */
+#  define T_A 1 /* ns_t_a */
 #endif
 #ifndef T_NS
-#  define T_NS            2   /* ns_t_ns */
+#  define T_NS 2 /* ns_t_ns */
 #endif
 #ifndef T_MD
-#  define T_MD            3   /* ns_t_md */
+#  define T_MD 3 /* ns_t_md */
 #endif
 #ifndef T_MF
-#  define T_MF            4   /* ns_t_mf */
+#  define T_MF 4 /* ns_t_mf */
 #endif
 #ifndef T_CNAME
-#  define T_CNAME         5   /* ns_t_cname */
+#  define T_CNAME 5 /* ns_t_cname */
 #endif
 #ifndef T_SOA
-#  define T_SOA           6   /* ns_t_soa */
+#  define T_SOA 6 /* ns_t_soa */
 #endif
 #ifndef T_MB
-#  define T_MB            7   /* ns_t_mb */
+#  define T_MB 7 /* ns_t_mb */
 #endif
 #ifndef T_MG
-#  define T_MG            8   /* ns_t_mg */
+#  define T_MG 8 /* ns_t_mg */
 #endif
 #ifndef T_MR
-#  define T_MR            9   /* ns_t_mr */
+#  define T_MR 9 /* ns_t_mr */
 #endif
 #ifndef T_NULL
-#  define T_NULL          10  /* ns_t_null */
+#  define T_NULL 10 /* ns_t_null */
 #endif
 #ifndef T_WKS
-#  define T_WKS           11  /* ns_t_wks */
+#  define T_WKS 11 /* ns_t_wks */
 #endif
 #ifndef T_PTR
-#  define T_PTR           12  /* ns_t_ptr */
+#  define T_PTR 12 /* ns_t_ptr */
 #endif
 #ifndef T_HINFO
-#  define T_HINFO         13  /* ns_t_hinfo */
+#  define T_HINFO 13 /* ns_t_hinfo */
 #endif
 #ifndef T_MINFO
-#  define T_MINFO         14  /* ns_t_minfo */
+#  define T_MINFO 14 /* ns_t_minfo */
 #endif
 #ifndef T_MX
-#  define T_MX            15  /* ns_t_mx */
+#  define T_MX 15 /* ns_t_mx */
 #endif
 #ifndef T_TXT
-#  define T_TXT           16  /* ns_t_txt */
+#  define T_TXT 16 /* ns_t_txt */
 #endif
 #ifndef T_RP
-#  define T_RP            17  /* ns_t_rp */
+#  define T_RP 17 /* ns_t_rp */
 #endif
 #ifndef T_AFSDB
-#  define T_AFSDB         18  /* ns_t_afsdb */
+#  define T_AFSDB 18 /* ns_t_afsdb */
 #endif
 #ifndef T_X25
-#  define T_X25           19  /* ns_t_x25 */
+#  define T_X25 19 /* ns_t_x25 */
 #endif
 #ifndef T_ISDN
-#  define T_ISDN          20  /* ns_t_isdn */
+#  define T_ISDN 20 /* ns_t_isdn */
 #endif
 #ifndef T_RT
-#  define T_RT            21  /* ns_t_rt */
+#  define T_RT 21 /* ns_t_rt */
 #endif
 #ifndef T_NSAP
-#  define T_NSAP          22  /* ns_t_nsap */
+#  define T_NSAP 22 /* ns_t_nsap */
 #endif
 #ifndef T_NSAP_PTR
-#  define T_NSAP_PTR      23  /* ns_t_nsap_ptr */
+#  define T_NSAP_PTR 23 /* ns_t_nsap_ptr */
 #endif
 #ifndef T_SIG
-#  define T_SIG           24  /* ns_t_sig */
+#  define T_SIG 24 /* ns_t_sig */
 #endif
 #ifndef T_KEY
-#  define T_KEY           25  /* ns_t_key */
+#  define T_KEY 25 /* ns_t_key */
 #endif
 #ifndef T_PX
-#  define T_PX            26  /* ns_t_px */
+#  define T_PX 26 /* ns_t_px */
 #endif
 #ifndef T_GPOS
-#  define T_GPOS          27  /* ns_t_gpos */
+#  define T_GPOS 27 /* ns_t_gpos */
 #endif
 #ifndef T_AAAA
-#  define T_AAAA          28  /* ns_t_aaaa */
+#  define T_AAAA 28 /* ns_t_aaaa */
 #endif
 #ifndef T_LOC
-#  define T_LOC           29  /* ns_t_loc */
+#  define T_LOC 29 /* ns_t_loc */
 #endif
 #ifndef T_NXT
-#  define T_NXT           30  /* ns_t_nxt */
+#  define T_NXT 30 /* ns_t_nxt */
 #endif
 #ifndef T_EID
-#  define T_EID           31  /* ns_t_eid */
+#  define T_EID 31 /* ns_t_eid */
 #endif
 #ifndef T_NIMLOC
-#  define T_NIMLOC        32  /* ns_t_nimloc */
+#  define T_NIMLOC 32 /* ns_t_nimloc */
 #endif
 #ifndef T_SRV
-#  define T_SRV           33  /* ns_t_srv */
+#  define T_SRV 33 /* ns_t_srv */
 #endif
 #ifndef T_ATMA
-#  define T_ATMA          34  /* ns_t_atma */
+#  define T_ATMA 34 /* ns_t_atma */
 #endif
 #ifndef T_NAPTR
-#  define T_NAPTR         35  /* ns_t_naptr */
+#  define T_NAPTR 35 /* ns_t_naptr */
 #endif
 #ifndef T_KX
-#  define T_KX            36  /* ns_t_kx */
+#  define T_KX 36 /* ns_t_kx */
 #endif
 #ifndef T_CERT
-#  define T_CERT          37  /* ns_t_cert */
+#  define T_CERT 37 /* ns_t_cert */
 #endif
 #ifndef T_A6
-#  define T_A6            38  /* ns_t_a6 */
+#  define T_A6 38 /* ns_t_a6 */
 #endif
 #ifndef T_DNAME
-#  define T_DNAME         39  /* ns_t_dname */
+#  define T_DNAME 39 /* ns_t_dname */
 #endif
 #ifndef T_SINK
-#  define T_SINK          40  /* ns_t_sink */
+#  define T_SINK 40 /* ns_t_sink */
 #endif
 #ifndef T_OPT
-#  define T_OPT           41  /* ns_t_opt */
+#  define T_OPT 41 /* ns_t_opt */
 #endif
 #ifndef T_APL
-#  define T_APL           42  /* ns_t_apl */
+#  define T_APL 42 /* ns_t_apl */
 #endif
 #ifndef T_DS
-#  define T_DS            43  /* ns_t_ds */
+#  define T_DS 43 /* ns_t_ds */
 #endif
 #ifndef T_SSHFP
-#  define T_SSHFP         44  /* ns_t_sshfp */
+#  define T_SSHFP 44 /* ns_t_sshfp */
 #endif
 #ifndef T_RRSIG
-#  define T_RRSIG         46  /* ns_t_rrsig */
+#  define T_RRSIG 46 /* ns_t_rrsig */
 #endif
 #ifndef T_NSEC
-#  define T_NSEC          47  /* ns_t_nsec */
+#  define T_NSEC 47 /* ns_t_nsec */
 #endif
 #ifndef T_DNSKEY
-#  define T_DNSKEY        48  /* ns_t_dnskey */
+#  define T_DNSKEY 48 /* ns_t_dnskey */
 #endif
 #ifndef T_TKEY
-#  define T_TKEY          249 /* ns_t_tkey */
+#  define T_TKEY 249 /* ns_t_tkey */
 #endif
 #ifndef T_TSIG
-#  define T_TSIG          250 /* ns_t_tsig */
+#  define T_TSIG 250 /* ns_t_tsig */
 #endif
 #ifndef T_IXFR
-#  define T_IXFR          251 /* ns_t_ixfr */
+#  define T_IXFR 251 /* ns_t_ixfr */
 #endif
 #ifndef T_AXFR
-#  define T_AXFR          252 /* ns_t_axfr */
+#  define T_AXFR 252 /* ns_t_axfr */
 #endif
 #ifndef T_MAILB
-#  define T_MAILB         253 /* ns_t_mailb */
+#  define T_MAILB 253 /* ns_t_mailb */
 #endif
 #ifndef T_MAILA
-#  define T_MAILA         254 /* ns_t_maila */
+#  define T_MAILA 254 /* ns_t_maila */
 #endif
 #ifndef T_ANY
-#  define T_ANY           255 /* ns_t_any */
+#  define T_ANY 255 /* ns_t_any */
 #endif
 #ifndef T_URI
-#  define T_URI          256 /* ns_t_uri */
+#  define T_URI 256 /* ns_t_uri */
 #endif
 #ifndef T_CAA
-#  define T_CAA           257 /* ns_t_caa */
+#  define T_CAA 257 /* ns_t_caa */
 #endif
 #ifndef T_MAX
-#  define T_MAX         65536 /* ns_t_max */
+#  define T_MAX 65536 /* ns_t_max */
 #endif
 
 
diff --git a/include/ares_rules.h b/include/ares_rules.h
index f6b1f66..450dc8a 100644
--- a/include/ares_rules.h
+++ b/include/ares_rules.h
@@ -81,7 +81,7 @@
 
 #ifndef CARES_TYPEOF_ARES_SOCKLEN_T
 #  error "CARES_TYPEOF_ARES_SOCKLEN_T definition is missing!"
-   Error Compilation_aborted_CARES_TYPEOF_ARES_SOCKLEN_T_is_missing
+Error Compilation_aborted_CARES_TYPEOF_ARES_SOCKLEN_T_is_missing
 #endif
 
 /*
@@ -92,15 +92,14 @@
 
 #define CareschkszGE(t1, t2) sizeof(t1) >= sizeof(t2) ? 1 : -1
 
-/*
- * Verify that the size previously defined and expected for
- * ares_socklen_t is actually the same as the one reported
- * by sizeof() at compile time.
- */
+  /*
+   * Verify that the size previously defined and expected for
+   * ares_socklen_t is actually the same as the one reported
+   * by sizeof() at compile time.
+   */
 
-typedef char
-  __cares_rule_02__
-    [CareschkszEQ(ares_socklen_t, sizeof(CARES_TYPEOF_ARES_SOCKLEN_T))];
+  typedef char __cares_rule_02__[CareschkszEQ(
+    ares_socklen_t, sizeof(CARES_TYPEOF_ARES_SOCKLEN_T))];
 
 /*
  * Verify at compile time that the size of ares_socklen_t as reported
@@ -108,9 +107,7 @@ typedef char
  * the current compilation.
  */
 
-typedef char
-  __cares_rule_03__
-    [CareschkszGE(ares_socklen_t, int)];
+typedef char   __cares_rule_03__[CareschkszGE(ares_socklen_t, int)];
 
 /* ================================================================ */
 /*          EXTERNALLY AND INTERNALLY VISIBLE DEFINITIONS           */
diff --git a/include/ares_version.h b/include/ares_version.h
index 34784e2..a3437a5 100644
--- a/include/ares_version.h
+++ b/include/ares_version.h
@@ -33,13 +33,13 @@
 #define ARES_VERSION_MAJOR 1
 #define ARES_VERSION_MINOR 20
 #define ARES_VERSION_PATCH 1
-#define ARES_VERSION ((ARES_VERSION_MAJOR<<16)|\
-                       (ARES_VERSION_MINOR<<8)|\
-                       (ARES_VERSION_PATCH))
+#define ARES_VERSION                                        \
+  ((ARES_VERSION_MAJOR << 16) | (ARES_VERSION_MINOR << 8) | \
+   (ARES_VERSION_PATCH))
 #define ARES_VERSION_STR "1.20.1"
 
 #if (ARES_VERSION >= 0x010700)
-#  define CARES_HAVE_ARES_LIBRARY_INIT 1
+#  define CARES_HAVE_ARES_LIBRARY_INIT    1
 #  define CARES_HAVE_ARES_LIBRARY_CLEANUP 1
 #else
 #  undef CARES_HAVE_ARES_LIBRARY_INIT
diff --git a/src/lib/ares__addrinfo2hostent.c b/src/lib/ares__addrinfo2hostent.c
index 081fbea..564020e 100644
--- a/src/lib/ares__addrinfo2hostent.c
+++ b/src/lib/ares__addrinfo2hostent.c
@@ -57,151 +57,138 @@
 ares_status_t ares__addrinfo2hostent(const struct ares_addrinfo *ai, int family,
                                      struct hostent **host)
 {
-  struct ares_addrinfo_node *next;
+  struct ares_addrinfo_node  *next;
   struct ares_addrinfo_cname *next_cname;
-  char **aliases = NULL;
-  char *addrs = NULL;
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
