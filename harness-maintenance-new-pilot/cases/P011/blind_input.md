# Case ID

P011

## Existing Fuzz Harness H0

### `test/ares-test-fuzz.c`

~~~~c
/* MIT License
 *
 * Copyright (c) The c-ares project and its contributors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice (including the next
 * paragraph) shall be included in all copies or substantial portions of the
 * Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 * SPDX-License-Identifier: MIT
 */
#include <stddef.h>
#include <stdio.h>
#include "ares.h"
#include "include/ares__buf.h"
#include "include/ares_mem.h"

int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size);

#ifdef USE_LEGACY_PARSERS

/* This implementation calls the legacy c-ares parsers, which historically
 * all used different logic and parsing.  As of c-ares 1.21.0 these are
 * simply wrappers around a single parser, and simply convert the parsed
 * DNS response into the data structures the legacy parsers used which is a
 * small amount of code and not likely going to vary based on the input data.
 *
 * Instead, these days, it makes more sense to test the new parser directly
 * instead of calling it 10 or 11 times with the same input data to speed up
 * the number of iterations per second the fuzzer can perform.
 *
 * We are keeping this legacy fuzzer test for historic reasons or if someone
 * finds them of use.
 */

int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size)
{
  /* Feed the data into each of the ares_parse_*_reply functions. */
  struct hostent          *host = NULL;
  struct ares_addrttl      info[5];
  struct ares_addr6ttl     info6[5];
  unsigned char            addrv4[4] = { 0x10, 0x20, 0x30, 0x40 };
  struct ares_srv_reply   *srv       = NULL;
  struct ares_mx_reply    *mx        = NULL;
  struct ares_txt_reply   *txt       = NULL;
  struct ares_soa_reply   *soa       = NULL;
  struct ares_naptr_reply *naptr     = NULL;
  struct ares_caa_reply   *caa       = NULL;
  struct ares_uri_reply   *uri       = NULL;
  int                      count     = 5;
  ares_parse_a_reply(data, (int)size, &host, info, &count);
  if (host) {
    ares_free_hostent(host);
  }

  host  = NULL;
  count = 5;
  ares_parse_aaaa_reply(data, (int)size, &host, info6, &count);
  if (host) {
    ares_free_hostent(host);
  }

  host = NULL;
  ares_parse_ptr_reply(data, (int)size, addrv4, sizeof(addrv4), AF_INET, &host);
  if (host) {
    ares_free_hostent(host);
  }

  host = NULL;
  ares_parse_ns_reply(data, (int)size, &host);
  if (host) {
    ares_free_hostent(host);
  }

  ares_parse_srv_reply(data, (int)size, &srv);
  if (srv) {
    ares_free_data(srv);
  }

  ares_parse_mx_reply(data, (int)size, &mx);
  if (mx) {
    ares_free_data(mx);
  }

  ares_parse_txt_reply(data, (int)size, &txt);
  if (txt) {
    ares_free_data(txt);
  }

  ares_parse_soa_reply(data, (int)size, &soa);
  if (soa) {
    ares_free_data(soa);
  }

  ares_parse_naptr_reply(data, (int)size, &naptr);
  if (naptr) {
    ares_free_data(naptr);
  }

  ares_parse_caa_reply(data, (int)size, &caa);
  if (caa) {
    ares_free_data(caa);
  }

  ares_parse_uri_reply(data, (int)size, &uri);
  if (uri) {
    ares_free_data(uri);
  }

  return 0;
}

#else

int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size)
{
  ares_dns_record_t *dnsrec      = NULL;
  char              *printdata   = NULL;
  ares__buf_t       *printmsg    = NULL;
  size_t             i;
  unsigned char     *datadup     = NULL;
  size_t             datadup_len = 0;

  /* There is never a reason to have a size > 65535, it is immediately
   * rejected by the parser */
  if (size > 65535) {
    return -1;
  }

  if (ares_dns_parse(data, size, 0, &dnsrec) != ARES_SUCCESS) {
    goto done;
  }

  /* Lets test the message fetchers */
  printmsg = ares__buf_create();
  if (printmsg == NULL) {
    goto done;
  }

  ares__buf_append_str(printmsg, ";; ->>HEADER<<- opcode: ");
  ares__buf_append_str(printmsg, ares_dns_opcode_tostr(ares_dns_record_get_opcode(dnsrec)));
  ares__buf_append_str(printmsg, ", status: ");
  ares__buf_append_str(printmsg, ares_dns_rcode_tostr(ares_dns_record_get_rcode(dnsrec)));
  ares__buf_append_str(printmsg, ", id: ");
  ares__buf_append_num_dec(printmsg, (size_t)ares_dns_record_get_id(dnsrec), 0);
  ares__buf_append_str(printmsg, "\n;; flags: ");
  ares__buf_append_num_hex(printmsg, (size_t)ares_dns_record_get_flags(dnsrec), 0);
  ares__buf_append_str(printmsg, "; QUERY: ");
  ares__buf_append_num_dec(printmsg, ares_dns_record_query_cnt(dnsrec), 0);
  ares__buf_append_str(printmsg, ", ANSWER: ");
  ares__buf_append_num_dec(printmsg, ares_dns_record_rr_cnt(dnsrec, ARES_SECTION_ANSWER), 0);
  ares__buf_append_str(printmsg, ", AUTHORITY: ");
  ares__buf_append_num_dec(printmsg, ares_dns_record_rr_cnt(dnsrec, ARES_SECTION_AUTHORITY), 0);
  ares__buf_append_str(printmsg, ", ADDITIONAL: ");
  ares__buf_append_num_dec(printmsg, ares_dns_record_rr_cnt(dnsrec, ARES_SECTION_ADDITIONAL), 0);
  ares__buf_append_str(printmsg, "\n\n");
  ares__buf_append_str(printmsg, ";; QUESTION SECTION:\n");
  for (i = 0; i < ares_dns_record_query_cnt(dnsrec); i++) {
    const char         *name;
    ares_dns_rec_type_t qtype;
    ares_dns_class_t    qclass;

    if (ares_dns_record_query_get(dnsrec, i, &name, &qtype, &qclass) != ARES_SUCCESS) {
      goto done;
    }

    ares__buf_append_str(printmsg, ";");
    ares__buf_append_str(printmsg, name);
    ares__buf_append_str(printmsg, ".\t\t\t");
    ares__buf_append_str(printmsg, ares_dns_class_tostr(qclass));
    ares__buf_append_str(printmsg, "\t");
    ares__buf_append_str(printmsg, ares_dns_rec_type_tostr(qtype));
    ares__buf_append_str(printmsg, "\n");
  }
  ares__buf_append_str(printmsg, "\n");
  for (i = ARES_SECTION_ANSWER; i < ARES_SECTION_ADDITIONAL + 1; i++) {
    size_t j;

    ares__buf_append_str(printmsg, ";; ");
    ares__buf_append_str(printmsg, ares_dns_section_tostr((ares_dns_section_t)i));
    ares__buf_append_str(printmsg, " SECTION:\n");
    for (j = 0; j < ares_dns_record_rr_cnt(dnsrec, (ares_dns_section_t)i); j++) {
      size_t                   keys_cnt = 0;
      const ares_dns_rr_key_t *keys     = NULL;
      ares_dns_rr_t           *rr       = NULL;
      size_t                   k;

      rr = ares_dns_record_rr_get(dnsrec, (ares_dns_section_t)i, j);
      ares__buf_append_str(printmsg, ares_dns_rr_get_name(rr));
      ares__buf_append_str(printmsg, ".\t\t\t");
      ares__buf_append_str(printmsg, ares_dns_class_tostr(ares_dns_rr_get_class(rr)));
      ares__buf_append_str(printmsg, "\t");
      ares__buf_append_str(printmsg, ares_dns_rec_type_tostr(ares_dns_rr_get_type(rr)));
      ares__buf_append_str(printmsg, "\t");
      ares__buf_append_num_dec(printmsg, ares_dns_rr_get_ttl(rr), 0);
      ares__buf_append_str(printmsg, "\t");

      keys = ares_dns_rr_get_keys(ares_dns_rr_get_type(rr), &keys_cnt);
      for (k = 0; k<keys_cnt; k++) {
        char buf[256] = "";

        ares__buf_append_str(printmsg, ares_dns_rr_key_tostr(keys[k]));
        ares__buf_append_str(printmsg, "=");
        switch (ares_dns_rr_key_datatype(keys[k])) {
          case ARES_DATATYPE_INADDR:
            ares_inet_ntop(AF_INET, ares_dns_rr_get_addr(rr, keys[k]), buf, sizeof(buf));
            ares__buf_append_str(printmsg, buf);
            break;
          case ARES_DATATYPE_INADDR6:
            ares_inet_ntop(AF_INET6, ares_dns_rr_get_addr6(rr, keys[k]), buf, sizeof(buf));
            ares__buf_append_str(printmsg, buf);
            break;
          case ARES_DATATYPE_U8:
            ares__buf_append_num_dec(printmsg, ares_dns_rr_get_u8(rr, keys[k]), 0);
            break;
          case ARES_DATATYPE_U16:
            ares__buf_append_num_dec(printmsg, ares_dns_rr_get_u16(rr, keys[k]), 0);
            break;
          case ARES_DATATYPE_U32:
            ares__buf_append_num_dec(printmsg, ares_dns_rr_get_u32(rr, keys[k]), 0);
            break;
          case ARES_DATATYPE_NAME:
          case ARES_DATATYPE_STR:
            ares__buf_append_byte(printmsg, '"');
            ares__buf_append_str(printmsg, ares_dns_rr_get_str(rr, keys[k]));
            ares__buf_append_byte(printmsg, '"');
            break;
          case ARES_DATATYPE_BIN:
            /* TODO */
            break;
          case ARES_DATATYPE_BINP:
            {
              size_t templen;
              ares__buf_append_byte(printmsg, '"');
              ares__buf_append_str(printmsg, (const char *)ares_dns_rr_get_bin(rr, keys[k], &templen));
              ares__buf_append_byte(printmsg, '"');
            }
            break;
          case ARES_DATATYPE_ABINP:
            {
              size_t a;
              for (a=0; a<ares_dns_rr_get_abin_cnt(rr, keys[k]); a++) {
                size_t templen;

                if (a != 0) {
                  ares__buf_append_byte(printmsg, ' ');
                }
                ares__buf_append_byte(printmsg, '"');
                ares__buf_append_str(printmsg, (const char *)ares_dns_rr_get_abin(rr, keys[k], a, &templen));
                ares__buf_append_byte(printmsg, '"');
              }
            }
            break;
          case ARES_DATATYPE_OPT:
            /* TODO */
            break;
        }
        ares__buf_append_str(printmsg, " ");
      }
      ares__buf_append_str(printmsg, "\n");
    }
  }
  ares__buf_append_str(printmsg, ";; SIZE: ");
  ares__buf_append_num_dec(printmsg, size, 0);
  ares__buf_append_str(printmsg, "\n\n");

  printdata = ares__buf_finish_str(printmsg, NULL);
  printmsg  = NULL;

  /* Write it back out as a dns message to test writer */
  if (ares_dns_write(dnsrec, &datadup, &datadup_len) != ARES_SUCCESS) {
    goto done;
  }

done:
  ares_dns_record_destroy(dnsrec);
  ares__buf_destroy(printmsg);
  ares_free(printdata);
  ares_free(datadup);
  return 0;
}

#endif
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is a deterministic H0-identifier-anchored excerpt capped at 70,000 characters.

~~~~diff
... [unselected diff lines omitted by frozen H0-anchored rule] ...
diff --git a/src/lib/Makefile.inc b/src/lib/Makefile.inc
index f4c084c..5da4d11 100644
--- a/src/lib/Makefile.inc
+++ b/src/lib/Makefile.inc
@@ -1,13 +1,13 @@
 # Copyright (C) The c-ares project and its contributors
 # SPDX-License-Identifier: MIT
 
-CSOURCES = ares__addrinfo2hostent.c	\
-  ares__addrinfo_localhost.c		\
-  ares__close_sockets.c			\
-  ares__hosts_file.c			\
-  ares__parse_into_addrinfo.c		\
-  ares__socket.c			\
-  ares__sortaddrinfo.c			\
+CSOURCES = ares_addrinfo2hostent.c	\
+  ares_addrinfo_localhost.c		\
+  ares_close_sockets.c			\
+  ares_hosts_file.c			\
+  ares_parse_into_addrinfo.c		\
+  ares_socket.c			\
+  ares_sortaddrinfo.c			\
   ares_android.c			\
   ares_cancel.c				\
   ares_cookie.c				\
@@ -42,14 +42,14 @@ CSOURCES = ares__addrinfo2hostent.c	\
   inet_net_pton.c			\
   inet_ntop.c				\
   windows_port.c			\
-  dsa/ares__array.c			\
-  dsa/ares__htable.c			\
-  dsa/ares__htable_asvp.c		\
-  dsa/ares__htable_strvp.c		\
-  dsa/ares__htable_szvp.c		\
-  dsa/ares__htable_vpvp.c		\
-  dsa/ares__llist.c			\
-  dsa/ares__slist.c			\
+  dsa/ares_array.c			\
+  dsa/ares_htable.c			\
+  dsa/ares_htable_asvp.c		\
+  dsa/ares_htable_strvp.c		\
+  dsa/ares_htable_szvp.c		\
+  dsa/ares_htable_vpvp.c		\
+  dsa/ares_llist.c			\
+  dsa/ares_slist.c			\
   event/ares_event_configchg.c		\
   event/ares_event_epoll.c		\
   event/ares_event_kqueue.c		\
@@ -80,12 +80,12 @@ CSOURCES = ares__addrinfo2hostent.c	\
   record/ares_dns_parse.c		\
   record/ares_dns_record.c		\
   record/ares_dns_write.c		\
-  str/ares__buf.c			\
+  str/ares_buf.c			\
   str/ares_str.c			\
   str/ares_strsplit.c			\
-  util/ares__iface_ips.c		\
-  util/ares__threads.c			\
-  util/ares__timeval.c			\
+  util/ares_iface_ips.c		\
+  util/ares_threads.c			\
+  util/ares_timeval.c			\
   util/ares_math.c			\
   util/ares_rand.c
 
@@ -98,23 +98,23 @@ HHEADERS = ares_android.h			\
   ares_platform.h			\
   ares_private.h			\
   ares_setup.h				\
-  dsa/ares__htable.h			\
-  dsa/ares__slist.h			\
+  dsa/ares_htable.h			\
+  dsa/ares_slist.h			\
   event/ares_event.h			\
   event/ares_event_win32.h		\
-  include/ares__array.h			\
-  include/ares__buf.h			\
-  include/ares__htable_asvp.h		\
-  include/ares__htable_strvp.h		\
-  include/ares__htable_szvp.h		\
-  include/ares__htable_vpvp.h		\
-  include/ares__llist.h			\
+  include/ares_array.h			\
+  include/ares_buf.h			\
+  include/ares_htable_asvp.h		\
+  include/ares_htable_strvp.h		\
+  include/ares_htable_szvp.h		\
+  include/ares_htable_vpvp.h		\
+  include/ares_llist.h			\
   include/ares_str.h			\
   record/ares_dns_multistring.h		\
   record/ares_dns_private.h		\
   str/ares_strsplit.h			\
-  util/ares__iface_ips.h		\
-  util/ares__threads.h			\
+  util/ares_iface_ips.h		\
+  util/ares_threads.h			\
   util/ares_math.h			\
   util/ares_rand.h			\
   util/ares_time.h			\
diff --git a/src/lib/ares_addrinfo2hostent.c b/src/lib/ares_addrinfo2hostent.c
new file mode 100644
index 0000000..2bbc791
--- /dev/null
+++ b/src/lib/ares_addrinfo2hostent.c
@@ -0,0 +1,274 @@
+/* MIT License
+ *
+ * Copyright (c) 1998 Massachusetts Institute of Technology
+ * Copyright (c) 2005 Dominick Meglio
+ * Copyright (c) 2019 Andrew Selivanov
+ * Copyright (c) 2021 Brad House
+ *
+ * Permission is hereby granted, free of charge, to any person obtaining a copy
+ * of this software and associated documentation files (the "Software"), to deal
+ * in the Software without restriction, including without limitation the rights
+ * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
+ * copies of the Software, and to permit persons to whom the Software is
+ * furnished to do so, subject to the following conditions:
+ *
+ * The above copyright notice and this permission notice (including the next
+ * paragraph) shall be included in all copies or substantial portions of the
+ * Software.
+ *
+ * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
+ * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
+ * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
+ * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
+ * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
+ * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
+ * SOFTWARE.
+ *
+ * SPDX-License-Identifier: MIT
+ */
+
+#include "ares_private.h"
+
+#ifdef HAVE_NETINET_IN_H
+#  include <netinet/in.h>
+#endif
+#ifdef HAVE_NETDB_H
+#  include <netdb.h>
+#endif
+#ifdef HAVE_ARPA_INET_H
+#  include <arpa/inet.h>
+#endif
+
+#ifdef HAVE_STRINGS_H
+#  include <strings.h>
+#endif
+
+#ifdef HAVE_LIMITS_H
+#  include <limits.h>
+#endif
+
+
+ares_status_t ares_addrinfo2hostent(const struct ares_addrinfo *ai, int family,
+                                    struct hostent **host)
+{
+  struct ares_addrinfo_node  *next;
+  struct ares_addrinfo_cname *next_cname;
+  char                      **aliases  = NULL;
+  char                       *addrs    = NULL;
+  size_t                      naliases = 0;
+  size_t                      naddrs   = 0;
+  size_t                      alias    = 0;
+  size_t                      i;
+
+  if (ai == NULL || host == NULL) {
+    return ARES_EBADQUERY; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  /* Use the first node of the response as the family, since hostent can only
+   * represent one family.  We assume getaddrinfo() returned a sorted list if
+   * the user requested AF_UNSPEC. */
+  if (family == AF_UNSPEC && ai->nodes) {
+    family = ai->nodes->ai_family;
+  }
+
+  if (family != AF_INET && family != AF_INET6) {
+    return ARES_EBADQUERY; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  *host = ares_malloc(sizeof(**host));
+  if (!(*host)) {
+    goto enomem; /* LCOV_EXCL_LINE: OutOfMemory */
+  }
+  memset(*host, 0, sizeof(**host));
+
+  next = ai->nodes;
+  while (next) {
+    if (next->ai_family == family) {
+      ++naddrs;
+    }
+    next = next->ai_next;
+  }
+
+  next_cname = ai->cnames;
+  while (next_cname) {
+    if (next_cname->alias) {
+      ++naliases;
+    }
+    next_cname = next_cname->next;
+  }
+
+  aliases = ares_malloc((naliases + 1) * sizeof(char *));
+  if (!aliases) {
+    goto enomem; /* LCOV_EXCL_LINE: OutOfMemory */
+  }
+  (*host)->h_aliases = aliases;
+  memset(aliases, 0, (naliases + 1) * sizeof(char *));
+
+  if (naliases) {
+    for (next_cname = ai->cnames; next_cname != NULL;
+         next_cname = next_cname->next) {
+      if (next_cname->alias == NULL) {
+        continue;
+      }
+      aliases[alias] = ares_strdup(next_cname->alias);
+      if (!aliases[alias]) {
+        goto enomem; /* LCOV_EXCL_LINE: OutOfMemory */
+      }
+      alias++;
+    }
+  }
+
+
+  (*host)->h_addr_list = ares_malloc((naddrs + 1) * sizeof(char *));
+  if (!(*host)->h_addr_list) {
+    goto enomem; /* LCOV_EXCL_LINE: OutOfMemory */
+  }
+
+  memset((*host)->h_addr_list, 0, (naddrs + 1) * sizeof(char *));
+
+  if (ai->cnames) {
+    (*host)->h_name = ares_strdup(ai->cnames->name);
+    if ((*host)->h_name == NULL && ai->cnames->name) {
+      goto enomem; /* LCOV_EXCL_LINE: OutOfMemory */
+    }
+  } else {
+    (*host)->h_name = ares_strdup(ai->name);
+    if ((*host)->h_name == NULL && ai->name) {
+      goto enomem; /* LCOV_EXCL_LINE: OutOfMemory */
+    }
+  }
+
+  (*host)->h_addrtype = (HOSTENT_ADDRTYPE_TYPE)family;
+
+  if (family == AF_INET) {
+    (*host)->h_length = sizeof(struct in_addr);
+  }
+
+  if (family == AF_INET6) {
+    (*host)->h_length = sizeof(struct ares_in6_addr);
+  }
+
+  if (naddrs) {
+    addrs = ares_malloc(naddrs * (size_t)(*host)->h_length);
+    if (!addrs) {
+      goto enomem; /* LCOV_EXCL_LINE: OutOfMemory */
+    }
+
+    i = 0;
+    for (next = ai->nodes; next != NULL; next = next->ai_next) {
+      if (next->ai_family != family) {
+        continue;
+      }
+      (*host)->h_addr_list[i] = addrs + (i * (size_t)(*host)->h_length);
+      if (family == AF_INET6) {
+        memcpy((*host)->h_addr_list[i],
+               &(CARES_INADDR_CAST(const struct sockaddr_in6 *, next->ai_addr)
+                   ->sin6_addr),
+               (size_t)(*host)->h_length);
+      }
+      if (family == AF_INET) {
+        memcpy((*host)->h_addr_list[i],
+               &(CARES_INADDR_CAST(const struct sockaddr_in *, next->ai_addr)
+                   ->sin_addr),
+               (size_t)(*host)->h_length);
+      }
+      ++i;
+    }
+
+    if (i == 0) {
+      ares_free(addrs);
+    }
+  }
+
+  if (naddrs == 0 && naliases == 0) {
+    ares_free_hostent(*host);
+    *host = NULL;
+    return ARES_ENODATA;
+  }
+
+  return ARES_SUCCESS;
+
+/* LCOV_EXCL_START: OutOfMemory */
+enomem:
+  ares_free_hostent(*host);
+  *host = NULL;
+  return ARES_ENOMEM;
+  /* LCOV_EXCL_STOP */
+}
+
+ares_status_t ares_addrinfo2addrttl(const struct ares_addrinfo *ai, int family,
+                                    size_t                req_naddrttls,
+                                    struct ares_addrttl  *addrttls,
+                                    struct ares_addr6ttl *addr6ttls,
+                                    size_t               *naddrttls)
+{
+  struct ares_addrinfo_node  *next;
+  struct ares_addrinfo_cname *next_cname;
+  int                         cname_ttl = INT_MAX;
+
+  if (family != AF_INET && family != AF_INET6) {
+    return ARES_EBADQUERY; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  if (ai == NULL || naddrttls == NULL) {
+    return ARES_EBADQUERY; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  if (family == AF_INET && addrttls == NULL) {
+    return ARES_EBADQUERY; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  if (family == AF_INET6 && addr6ttls == NULL) {
+    return ARES_EBADQUERY; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  if (req_naddrttls == 0) {
+    return ARES_EBADQUERY; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  *naddrttls = 0;
+
+  next_cname = ai->cnames;
+  while (next_cname) {
+    if (next_cname->ttl < cname_ttl) {
+      cname_ttl = next_cname->ttl;
+    }
+    next_cname = next_cname->next;
+  }
+
+  for (next = ai->nodes; next != NULL; next = next->ai_next) {
+    if (next->ai_family != family) {
+      continue;
+    }
+
+    if (*naddrttls >= req_naddrttls) {
+      break;
+    }
+
+    if (family == AF_INET6) {
+      if (next->ai_ttl > cname_ttl) {
+        addr6ttls[*naddrttls].ttl = cname_ttl;
+      } else {
+        addr6ttls[*naddrttls].ttl = next->ai_ttl;
+      }
+
+      memcpy(&addr6ttls[*naddrttls].ip6addr,
+             &(CARES_INADDR_CAST(const struct sockaddr_in6 *, next->ai_addr)
+                 ->sin6_addr),
+             sizeof(struct ares_in6_addr));
+    } else {
+      if (next->ai_ttl > cname_ttl) {
+        addrttls[*naddrttls].ttl = cname_ttl;
+      } else {
+        addrttls[*naddrttls].ttl = next->ai_ttl;
+      }
+      memcpy(&addrttls[*naddrttls].ipaddr,
+             &(CARES_INADDR_CAST(const struct sockaddr_in *, next->ai_addr)
+                 ->sin_addr),
+             sizeof(struct in_addr));
+    }
+    (*naddrttls)++;
+  }
+
+  return ARES_SUCCESS;
+}
diff --git a/src/lib/ares_addrinfo_localhost.c b/src/lib/ares_addrinfo_localhost.c
new file mode 100644
index 0000000..6f4f2a3
--- /dev/null
+++ b/src/lib/ares_addrinfo_localhost.c
@@ -0,0 +1,233 @@
+/* MIT License
+ *
+ * Copyright (c) Massachusetts Institute of Technology
+ * Copyright (c) Daniel Stenberg
+ *
+ * Permission is hereby granted, free of charge, to any person obtaining a copy
+ * of this software and associated documentation files (the "Software"), to deal
+ * in the Software without restriction, including without limitation the rights
+ * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
+ * copies of the Software, and to permit persons to whom the Software is
+ * furnished to do so, subject to the following conditions:
+ *
+ * The above copyright notice and this permission notice (including the next
+ * paragraph) shall be included in all copies or substantial portions of the
+ * Software.
+ *
+ * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
+ * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
+ * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
+ * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
+ * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
+ * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
+ * SOFTWARE.
+ *
+ * SPDX-License-Identifier: MIT
+ */
+
+#include "ares_private.h"
+
+#ifdef HAVE_NETINET_IN_H
+#  include <netinet/in.h>
+#endif
+#ifdef HAVE_NETDB_H
+#  include <netdb.h>
+#endif
+#ifdef HAVE_ARPA_INET_H
+#  include <arpa/inet.h>
+#endif
+
+#if defined(USE_WINSOCK)
+#  if defined(_WIN32_WINNT) && _WIN32_WINNT >= 0x0600
+#    include <ws2ipdef.h>
+#  endif
+#  if defined(HAVE_IPHLPAPI_H)
+#    include <iphlpapi.h>
+#  endif
+#  if defined(HAVE_NETIOAPI_H)
+#    include <netioapi.h>
+#  endif
+#endif
+
+ares_status_t ares_append_ai_node(int aftype, unsigned short port,
+                                  unsigned int ttl, const void *adata,
+                                  struct ares_addrinfo_node **nodes)
+{
+  struct ares_addrinfo_node *node;
+
+  node = ares_append_addrinfo_node(nodes);
+  if (!node) {
+    return ARES_ENOMEM; /* LCOV_EXCL_LINE: OutOfMemory */
+  }
+
+  memset(node, 0, sizeof(*node));
+
+  if (aftype == AF_INET) {
+    struct sockaddr_in *sin = ares_malloc(sizeof(*sin));
+    if (!sin) {
+      return ARES_ENOMEM; /* LCOV_EXCL_LINE: OutOfMemory */
+    }
+
+    memset(sin, 0, sizeof(*sin));
+    memcpy(&sin->sin_addr.s_addr, adata, sizeof(sin->sin_addr.s_addr));
+    sin->sin_family = AF_INET;
+    sin->sin_port   = htons(port);
+
+    node->ai_addr    = (struct sockaddr *)sin;
+    node->ai_family  = AF_INET;
+    node->ai_addrlen = sizeof(*sin);
+    node->ai_addr    = (struct sockaddr *)sin;
+    node->ai_ttl     = (int)ttl;
+  }
+
+  if (aftype == AF_INET6) {
+    struct sockaddr_in6 *sin6 = ares_malloc(sizeof(*sin6));
+    if (!sin6) {
+      return ARES_ENOMEM; /* LCOV_EXCL_LINE: OutOfMemory */
+    }
+
+    memset(sin6, 0, sizeof(*sin6));
+    memcpy(&sin6->sin6_addr.s6_addr, adata, sizeof(sin6->sin6_addr.s6_addr));
+    sin6->sin6_family = AF_INET6;
+    sin6->sin6_port   = htons(port);
+
+    node->ai_addr    = (struct sockaddr *)sin6;
+    node->ai_family  = AF_INET6;
+    node->ai_addrlen = sizeof(*sin6);
+    node->ai_addr    = (struct sockaddr *)sin6;
+    node->ai_ttl     = (int)ttl;
+  }
+
+  return ARES_SUCCESS;
+}
+
+static ares_status_t
+  ares_default_loopback_addrs(int aftype, unsigned short port,
+                              struct ares_addrinfo_node **nodes)
+{
+  ares_status_t status = ARES_SUCCESS;
+
+  if (aftype == AF_UNSPEC || aftype == AF_INET6) {
+    struct ares_in6_addr addr6;
+    ares_inet_pton(AF_INET6, "::1", &addr6);
+    status = ares_append_ai_node(AF_INET6, port, 0, &addr6, nodes);
+    if (status != ARES_SUCCESS) {
+      return status; /* LCOV_EXCL_LINE: OutOfMemory */
+    }
+  }
+
+  if (aftype == AF_UNSPEC || aftype == AF_INET) {
+    struct in_addr addr4;
+    ares_inet_pton(AF_INET, "127.0.0.1", &addr4);
+    status = ares_append_ai_node(AF_INET, port, 0, &addr4, nodes);
+    if (status != ARES_SUCCESS) {
+      return status; /* LCOV_EXCL_LINE: OutOfMemory */
+    }
+  }
+
+  return status;
+}
+
+static ares_status_t
+  ares_system_loopback_addrs(int aftype, unsigned short port,
+                             struct ares_addrinfo_node **nodes)
+{
+#if defined(USE_WINSOCK) && defined(_WIN32_WINNT) && _WIN32_WINNT >= 0x0600 && \
+  !defined(__WATCOMC__)
+  PMIB_UNICASTIPADDRESS_TABLE table;
+  unsigned int                i;
+  ares_status_t               status = ARES_ENOTFOUND;
+
+  *nodes = NULL;
+
+  if (GetUnicastIpAddressTable((ADDRESS_FAMILY)aftype, &table) != NO_ERROR) {
+    return ARES_ENOTFOUND;
+  }
+
+  for (i = 0; i < table->NumEntries; i++) {
+    if (table->Table[i].InterfaceLuid.Info.IfType !=
+        IF_TYPE_SOFTWARE_LOOPBACK) {
+      continue;
+    }
+
+    if (table->Table[i].Address.si_family == AF_INET) {
+      status =
+        ares_append_ai_node(table->Table[i].Address.si_family, port, 0,
+                            &table->Table[i].Address.Ipv4.sin_addr, nodes);
+    } else if (table->Table[i].Address.si_family == AF_INET6) {
+      status =
+        ares_append_ai_node(table->Table[i].Address.si_family, port, 0,
+                            &table->Table[i].Address.Ipv6.sin6_addr, nodes);
+    } else {
+      /* Ignore any others */
+      continue;
+    }
+
+    if (status != ARES_SUCCESS) {
+      goto fail;
+    }
+  }
+
+  if (*nodes == NULL) {
+    status = ARES_ENOTFOUND;
+  }
+
+fail:
+  FreeMibTable(table);
+
+  if (status != ARES_SUCCESS) {
+    ares_freeaddrinfo_nodes(*nodes);
+    *nodes = NULL;
+  }
+
+  return status;
+
+#else
+  (void)aftype;
+  (void)port;
+  (void)nodes;
+  /* Not supported on any other OS at this time */
+  return ARES_ENOTFOUND;
+#endif
+}
+
+ares_status_t ares_addrinfo_localhost(const char *name, unsigned short port,
+                                      const struct ares_addrinfo_hints *hints,
+                                      struct ares_addrinfo             *ai)
+{
+  struct ares_addrinfo_node *nodes = NULL;
+  ares_status_t              status;
+
+  /* Validate family */
+  switch (hints->ai_family) {
+    case AF_INET:
+    case AF_INET6:
+    case AF_UNSPEC:
+      break;
+    default:                  /* LCOV_EXCL_LINE: DefensiveCoding */
+      return ARES_EBADFAMILY; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  ai->name = ares_strdup(name);
+  if (!ai->name) {
+    goto enomem; /* LCOV_EXCL_LINE: OutOfMemory */
+  }
+
+  status = ares_system_loopback_addrs(hints->ai_family, port, &nodes);
+
+  if (status == ARES_ENOTFOUND) {
+    status = ares_default_loopback_addrs(hints->ai_family, port, &nodes);
+  }
+
+  ares_addrinfo_cat_nodes(&ai->nodes, nodes);
+
+  return status;
+
+/* LCOV_EXCL_START: OutOfMemory */
+enomem:
+  ares_freeaddrinfo_nodes(nodes);
+  ares_free(ai->name);
+  ai->name = NULL;
+  return ARES_ENOMEM;
+  /* LCOV_EXCL_STOP */
+}
diff --git a/src/lib/ares_cancel.c b/src/lib/ares_cancel.c
index c29d8ef..75600de 100644
--- a/src/lib/ares_cancel.c
+++ b/src/lib/ares_cancel.c
@@ -37,18 +37,18 @@ void ares_cancel(ares_channel_t *channel)
     return;
   }
 
-  ares__channel_lock(channel);
+  ares_channel_lock(channel);
 
-  if (ares__llist_len(channel->all_queries) > 0) {
-    ares__llist_node_t *node = NULL;
-    ares__llist_node_t *next = NULL;
+  if (ares_llist_len(channel->all_queries) > 0) {
+    ares_llist_node_t *node = NULL;
+    ares_llist_node_t *next = NULL;
 
     /* Swap list heads, so that only those queries which were present on entry
      * into this function are cancelled. New queries added by callbacks of
      * queries being cancelled will not be cancelled themselves.
      */
-    ares__llist_t      *list_copy = channel->all_queries;
-    channel->all_queries          = ares__llist_create(NULL);
+    ares_llist_t      *list_copy = channel->all_queries;
+    channel->all_queries         = ares_llist_create(NULL);
 
     /* Out of memory, this function doesn't return a result code though so we
      * can't report to caller */
@@ -57,31 +57,31 @@ void ares_cancel(ares_channel_t *channel)
       goto done;                        /* LCOV_EXCL_LINE: OutOfMemory */
     }
 
-    node = ares__llist_node_first(list_copy);
+    node = ares_llist_node_first(list_copy);
     while (node != NULL) {
       ares_query_t *query;
 
       /* Cache next since this node is being deleted */
-      next = ares__llist_node_next(node);
+      next = ares_llist_node_next(node);
 
-      query                   = ares__llist_node_claim(node);
+      query                   = ares_llist_node_claim(node);
       query->node_all_queries = NULL;
 
       /* NOTE: its possible this may enqueue new queries */
       query->callback(query->arg, ARES_ECANCELLED, 0, NULL);
-      ares__free_query(query);
+      ares_free_query(query);
 
       node = next;
     }
 
-    ares__llist_destroy(list_copy);
+    ares_llist_destroy(list_copy);
   }
 
   /* See if the connections should be cleaned up */
-  ares__check_cleanup_conns(channel);
+  ares_check_cleanup_conns(channel);
 
   ares_queue_notify_empty(channel);
 
 done:
-  ares__channel_unlock(channel);
+  ares_channel_unlock(channel);
 }
diff --git a/src/lib/ares_close_sockets.c b/src/lib/ares_close_sockets.c
new file mode 100644
index 0000000..d1fdf28
--- /dev/null
+++ b/src/lib/ares_close_sockets.c
@@ -0,0 +1,137 @@
+/* MIT License
+ *
+ * Copyright (c) 1998 Massachusetts Institute of Technology
+ * Copyright (c) The c-ares project and its contributors
+ *
+ * Permission is hereby granted, free of charge, to any person obtaining a copy
+ * of this software and associated documentation files (the "Software"), to deal
+ * in the Software without restriction, including without limitation the rights
+ * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
+ * copies of the Software, and to permit persons to whom the Software is
+ * furnished to do so, subject to the following conditions:
+ *
+ * The above copyright notice and this permission notice (including the next
+ * paragraph) shall be included in all copies or substantial portions of the
+ * Software.
+ *
+ * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
+ * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
+ * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
+ * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
+ * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
+ * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
+ * SOFTWARE.
+ *
+ * SPDX-License-Identifier: MIT
+ */
+
+#include "ares_private.h"
+#include <assert.h>
+
+static void ares_requeue_queries(ares_conn_t  *conn,
+                                 ares_status_t requeue_status)
+{
+  ares_query_t  *query;
+  ares_timeval_t now;
+
+  ares_tvnow(&now);
+
+  while ((query = ares_llist_first_val(conn->queries_to_conn)) != NULL) {
+    ares_requeue_query(query, &now, requeue_status, ARES_TRUE, NULL);
+  }
+}
+
+void ares_close_connection(ares_conn_t *conn, ares_status_t requeue_status)
+{
+  ares_server_t  *server  = conn->server;
+  ares_channel_t *channel = server->channel;
+
+  /* Unlink */
+  ares_llist_node_claim(
+    ares_htable_asvp_get_direct(channel->connnode_by_socket, conn->fd));
+  ares_htable_asvp_remove(channel->connnode_by_socket, conn->fd);
+
+  if (conn->flags & ARES_CONN_FLAG_TCP) {
+    server->tcp_conn = NULL;
+  }
+
+  ares_buf_destroy(conn->in_buf);
+  ares_buf_destroy(conn->out_buf);
+
+  /* Requeue queries to other connections */
+  ares_requeue_queries(conn, requeue_status);
+
+  ares_llist_destroy(conn->queries_to_conn);
+
+  ares_conn_sock_state_cb_update(conn, ARES_CONN_STATE_NONE);
+
+  ares_close_socket(channel, conn->fd);
+
+  ares_free(conn);
+}
+
+void ares_close_sockets(ares_server_t *server)
+{
+  ares_llist_node_t *node;
+
+  while ((node = ares_llist_node_first(server->connections)) != NULL) {
+    ares_conn_t *conn = ares_llist_node_val(node);
+    ares_close_connection(conn, ARES_SUCCESS);
+  }
+}
+
+void ares_check_cleanup_conns(const ares_channel_t *channel)
+{
+  ares_slist_node_t *snode;
+
+  if (channel == NULL) {
+    return; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  /* Iterate across each server */
+  for (snode = ares_slist_node_first(channel->servers); snode != NULL;
+       snode = ares_slist_node_next(snode)) {
+    ares_server_t     *server = ares_slist_node_val(snode);
+    ares_llist_node_t *cnode;
+
+    /* Iterate across each connection */
+    cnode = ares_llist_node_first(server->connections);
+    while (cnode != NULL) {
+      ares_llist_node_t *next       = ares_llist_node_next(cnode);
+      ares_conn_t       *conn       = ares_llist_node_val(cnode);
+      ares_bool_t        do_cleanup = ARES_FALSE;
+      cnode                         = next;
+
+      /* Has connections, not eligible */
+      if (ares_llist_len(conn->queries_to_conn)) {
+        continue;
+      }
+
+      /* If we are configured not to stay open, close it out */
+      if (!(channel->flags & ARES_FLAG_STAYOPEN)) {
+        do_cleanup = ARES_TRUE;
+      }
+
+      /* If the associated server has failures, close it out. Resetting the
+       * connection (and specifically the source port number) can help resolve
+       * situations where packets are being dropped.
+       */
+      if (conn->server->consec_failures > 0) {
+        do_cleanup = ARES_TRUE;
+      }
+
+      /* If the udp connection hit its max queries, always close it */
+      if (!(conn->flags & ARES_CONN_FLAG_TCP) && channel->udp_max_queries > 0 &&
+          conn->total_queries >= channel->udp_max_queries) {
+        do_cleanup = ARES_TRUE;
+      }
+
+      if (!do_cleanup) {
+        continue;
+      }
+
+      /* Clean it up */
+      ares_close_connection(conn, ARES_SUCCESS);
+    }
+  }
+}
diff --git a/src/lib/ares_conn.h b/src/lib/ares_conn.h
index 47ace9a..f5c7569 100644
--- a/src/lib/ares_conn.h
+++ b/src/lib/ares_conn.h
@@ -63,19 +63,19 @@ struct ares_conn {
    *  stream in TCP format (big endian 16bit length prefix followed by DNS
    *  wire-format message).  For TCP this can be sent as-is, UDP this must
    *  be sent per-packet (stripping the length prefix) */
-  ares__buf_t            *out_buf;
+  ares_buf_t             *out_buf;
 
   /*! Inbound buffered data that is not yet parsed.  Exists as one contiguous
    *  stream in TCP format (big endian 16bit length prefix followed by DNS
    *  wire-format message).  TCP may have partial data and this needs to be
    *  handled gracefully, but UDP will always have a full message */
-  ares__buf_t            *in_buf;
+  ares_buf_t             *in_buf;
 
   /* total number of queries run on this connection since it was established */
   size_t                  total_queries;
 
   /* list of outstanding queries to this connection */
-  ares__llist_t          *queries_to_conn;
+  ares_llist_t           *queries_to_conn;
 };
 
 /*! Various buckets for grouping history */
@@ -144,7 +144,7 @@ struct ares_server {
   size_t                consec_failures; /* Consecutive query failure count
                                           * can be hard errors or timeouts
                                           */
-  ares__llist_t        *connections;
+  ares_llist_t         *connections;
   ares_conn_t          *tcp_conn;
 
   /* The next time when we will retry this server if it has hit failures */
@@ -160,14 +160,14 @@ struct ares_server {
   ares_channel_t       *channel;
 };
 
-void ares__close_connection(ares_conn_t *conn, ares_status_t requeue_status);
-void ares__close_sockets(ares_server_t *server);
-void ares__check_cleanup_conns(const ares_channel_t *channel);
+void ares_close_connection(ares_conn_t *conn, ares_status_t requeue_status);
+void ares_close_sockets(ares_server_t *server);
+void ares_check_cleanup_conns(const ares_channel_t *channel);
 
-void ares__destroy_servers_state(ares_channel_t *channel);
-ares_status_t ares__open_connection(ares_conn_t   **conn_out,
-                                    ares_channel_t *channel,
-                                    ares_server_t *server, ares_bool_t is_tcp);
+void ares_destroy_servers_state(ares_channel_t *channel);
+ares_status_t ares_open_connection(ares_conn_t   **conn_out,
+                                   ares_channel_t *channel,
+                                   ares_server_t *server, ares_bool_t is_tcp);
 ares_bool_t   ares_sockaddr_to_ares_addr(struct ares_addr      *ares_addr,
                                          unsigned short        *port,
                                          const struct sockaddr *sockaddr);
@@ -193,30 +193,29 @@ typedef enum {
   ARES_CONN_ERR_FAILURE      = 99  /*!< Generic failure */
 } ares_conn_err_t;
 
-ares_conn_err_t ares__open_socket(ares_socket_t *sock, ares_channel_t *channel,
-                                  int af, int type, int protocol);
-ares_bool_t     ares__socket_try_again(int errnum);
-ares_conn_err_t ares__conn_write(ares_conn_t *conn, const void *data,
-                                 size_t len, size_t *written);
-ares_status_t   ares__conn_flush(ares_conn_t *conn);
-ares_conn_err_t ares__conn_read(ares_conn_t *conn, void *data, size_t len,
-                                size_t *read_bytes);
-void            ares__conn_sock_state_cb_update(ares_conn_t            *conn,
-                                                ares_conn_state_flags_t flags);
-ares_conn_err_t ares__socket_recv(ares_channel_t *channel, ares_socket_t s,
-                                  ares_bool_t is_tcp, void *data,
-                                  size_t data_len, size_t *read_bytes);
-ares_conn_err_t ares__socket_recvfrom(ares_channel_t *channel, ares_socket_t s,
-                                      ares_bool_t is_tcp, void *data,
-                                      size_t data_len, int flags,
-                                      struct sockaddr *from,
-                                      ares_socklen_t  *from_len,
-                                      size_t          *read_bytes);
-void            ares__close_socket(ares_channel_t *channel, ares_socket_t s);
-ares_status_t   ares__connect_socket(ares_channel_t        *channel,
-                                     ares_socket_t          sockfd,
-                                     const struct sockaddr *addr,
-                                     ares_socklen_t         addrlen);
-void            ares__destroy_server(ares_server_t *server);
+ares_conn_err_t ares_open_socket(ares_socket_t *sock, ares_channel_t *channel,
+                                 int af, int type, int protocol);
+ares_bool_t     ares_socket_try_again(int errnum);
+ares_conn_err_t ares_conn_write(ares_conn_t *conn, const void *data, size_t len,
+                                size_t *written);
+ares_status_t   ares_conn_flush(ares_conn_t *conn);
+ares_conn_err_t ares_conn_read(ares_conn_t *conn, void *data, size_t len,
+                               size_t *read_bytes);
+void            ares_conn_sock_state_cb_update(ares_conn_t            *conn,
+                                               ares_conn_state_flags_t flags);
+ares_conn_err_t ares_socket_recv(ares_channel_t *channel, ares_socket_t s,
+                                 ares_bool_t is_tcp, void *data,
+                                 size_t data_len, size_t *read_bytes);
+ares_conn_err_t ares_socket_recvfrom(ares_channel_t *channel, ares_socket_t s,
+                                     ares_bool_t is_tcp, void *data,
+                                     size_t data_len, int flags,
+                                     struct sockaddr *from,
+                                     ares_socklen_t  *from_len,
+                                     size_t          *read_bytes);
+void            ares_close_socket(ares_channel_t *channel, ares_socket_t s);
+ares_status_t ares_connect_socket(ares_channel_t *channel, ares_socket_t sockfd,
+                                  const struct sockaddr *addr,
+                                  ares_socklen_t         addrlen);
+void          ares_destroy_server(ares_server_t *server);
 
 #endif
diff --git a/src/lib/ares_cookie.c b/src/lib/ares_cookie.c
index 3f429a7..f31c74e 100644
--- a/src/lib/ares_cookie.c
+++ b/src/lib/ares_cookie.c
@@ -229,7 +229,7 @@ static ares_bool_t timeval_expired(const ares_timeval_t *tv,
 {
   ares_int64_t   tvdiff_ms;
   ares_timeval_t tvdiff;
-  ares__timeval_diff(&tvdiff, tv, now);
+  ares_timeval_diff(&tvdiff, tv, now);
 
   tvdiff_ms = tvdiff.sec * 1000 + tvdiff.usec / 1000;
   if (tvdiff_ms >= (ares_int64_t)millsecs) {
@@ -249,7 +249,7 @@ static void ares_cookie_generate(ares_cookie_t *cookie, ares_conn_t *conn,
 {
   ares_channel_t *channel = conn->server->channel;
 
-  ares__rand_bytes(channel->rand_state, cookie->client, sizeof(cookie->client));
+  ares_rand_bytes(channel->rand_state, cookie->client, sizeof(cookie->client));
   memcpy(&cookie->client_ts, now, sizeof(cookie->client_ts));
   memcpy(&cookie->client_ip, &conn->self_ip, sizeof(cookie->client_ip));
 }
@@ -426,8 +426,8 @@ ares_status_t ares_cookie_validate(ares_query_t            *query,
 
     /* Resend the request, hopefully it will work the next time as we should
      * have recorded a server cookie */
-    ares__requeue_query(query, now, ARES_SUCCESS,
-                        ARES_FALSE /* Don't increment try count */, NULL);
+    ares_requeue_query(query, now, ARES_SUCCESS,
+                       ARES_FALSE /* Don't increment try count */, NULL);
 
     /* Parent needs to drop this response */
     return ARES_EBADRESP;
diff --git a/src/lib/ares_destroy.c b/src/lib/ares_destroy.c
index 2d333b3..1e5706e 100644
--- a/src/lib/ares_destroy.c
+++ b/src/lib/ares_destroy.c
@@ -31,17 +31,17 @@
 
 void ares_destroy(ares_channel_t *channel)
 {
-  size_t              i;
-  ares__llist_node_t *node = NULL;
+  size_t             i;
+  ares_llist_node_t *node = NULL;
 
   if (channel == NULL) {
     return;
   }
 
   /* Mark as being shutdown */
-  ares__channel_lock(channel);
+  ares_channel_lock(channel);
   channel->sys_up = ARES_FALSE;
-  ares__channel_unlock(channel);
+  ares_channel_unlock(channel);
 
   /* Disable configuration change monitoring.  We can't hold a lock because
    * some cleanup routines, such as on Windows, are synchronous operations.
@@ -61,23 +61,23 @@ void ares_destroy(ares_channel_t *channel)
    * holding a lock as the thread may take locks. */
   if (channel->reinit_thread != NULL) {
     void *rv;
-    ares__thread_join(channel->reinit_thread, &rv);
+    ares_thread_join(channel->reinit_thread, &rv);
     channel->reinit_thread = NULL;
   }
 
   /* Lock because callbacks will be triggered, and any system-generated
    * callbacks need to hold a channel lock. */
-  ares__channel_lock(channel);
+  ares_channel_lock(channel);
 
   /* Destroy all queries */
-  node = ares__llist_node_first(channel->all_queries);
+  node = ares_llist_node_first(channel->all_queries);
   while (node != NULL) {
-    ares__llist_node_t *next  = ares__llist_node_next(node);
-    ares_query_t       *query = ares__llist_node_claim(node);
+    ares_llist_node_t *next  = ares_llist_node_next(node);
+    ares_query_t      *query = ares_llist_node_claim(node);
 
     query->node_all_queries = NULL;
     query->callback(query->arg, ARES_EDESTRUCTION, 0, NULL);
-    ares__free_query(query);
+    ares_free_query(query);
 
     node = next;
   }
@@ -88,19 +88,19 @@ void ares_destroy(ares_channel_t *channel)
   /* Freeing the query should remove it from all the lists in which it sits,
    * so all query lists should be empty now.
    */
-  assert(ares__llist_len(channel->all_queries) == 0);
-  assert(ares__htable_szvp_num_keys(channel->queries_by_qid) == 0);
-  assert(ares__slist_len(channel->queries_by_timeout) == 0);
+  assert(ares_llist_len(channel->all_queries) == 0);
+  assert(ares_htable_szvp_num_keys(channel->queries_by_qid) == 0);
+  assert(ares_slist_len(channel->queries_by_timeout) == 0);
 #endif
 
-  ares__destroy_servers_state(channel);
+  ares_destroy_servers_state(channel);
 
 #ifndef NDEBUG
-  assert(ares__htable_asvp_num_keys(channel->connnode_by_socket) == 0);
+  assert(ares_htable_asvp_num_keys(channel->connnode_by_socket) == 0);
 #endif
 
   /* No more callbacks will be triggered after this point, unlock */
-  ares__channel_unlock(channel);
+  ares_channel_unlock(channel);
 
   /* Shut down the event thread */
   if (channel->optmask & ARES_OPT_EVENT_THREAD) {
@@ -114,46 +114,46 @@ void ares_destroy(ares_channel_t *channel)
     ares_free(channel->domains);
   }
 
-  ares__llist_destroy(channel->all_queries);
-  ares__slist_destroy(channel->queries_by_timeout);
-  ares__htable_szvp_destroy(channel->queries_by_qid);
-  ares__htable_asvp_destroy(channel->connnode_by_socket);
+  ares_llist_destroy(channel->all_queries);
+  ares_slist_destroy(channel->queries_by_timeout);
+  ares_htable_szvp_destroy(channel->queries_by_qid);
+  ares_htable_asvp_destroy(channel->connnode_by_socket);
 
   ares_free(channel->sortlist);
   ares_free(channel->lookups);
   ares_free(channel->resolvconf_path);
   ares_free(channel->hosts_path);
-  ares__destroy_rand_state(channel->rand_state);
+  ares_destroy_rand_state(channel->rand_state);
 
-  ares__hosts_file_destroy(channel->hf);
+  ares_hosts_file_destroy(channel->hf);
 
-  ares__qcache_destroy(channel->qcache);
+  ares_qcache_destroy(channel->qcache);
 
-  ares__channel_threading_destroy(channel);
+  ares_channel_threading_destroy(channel);
 
   ares_free(channel);
 }
 
-void ares__destroy_server(ares_server_t *server)
+void ares_destroy_server(ares_server_t *server)
 {
   if (server == NULL) {
     return; /* LCOV_EXCL_LINE: DefensiveCoding */
   }
 
-  ares__close_sockets(server);
-  ares__llist_destroy(server->connections);
+  ares_close_sockets(server);
+  ares_llist_destroy(server->connections);
   ares_free(server);
 }
 
-void ares__destroy_servers_state(ares_channel_t *channel)
+void ares_destroy_servers_state(ares_channel_t *channel)
 {
-  ares__slist_node_t *node;
+  ares_slist_node_t *node;
 
-  while ((node = ares__slist_node_first(channel->servers)) != NULL) {
-    ares_server_t *server = ares__slist_node_claim(node);
-    ares__destroy_server(server);
+  while ((node = ares_slist_node_first(channel->servers)) != NULL) {
+    ares_server_t *server = ares_slist_node_claim(node);
+    ares_destroy_server(server);
   }
 
-  ares__slist_destroy(channel->servers);
+  ares_slist_destroy(channel->servers);
   channel->servers = NULL;
 }
diff --git a/src/lib/ares_freeaddrinfo.c b/src/lib/ares_freeaddrinfo.c
index 2a49f57..c996df9 100644
--- a/src/lib/ares_freeaddrinfo.c
+++ b/src/lib/ares_freeaddrinfo.c
@@ -31,7 +31,7 @@
 #  include <netdb.h>
 #endif
 
-void ares__freeaddrinfo_cnames(struct ares_addrinfo_cname *head)
+void ares_freeaddrinfo_cnames(struct ares_addrinfo_cname *head)
 {
   struct ares_addrinfo_cname *current;
   while (head) {
@@ -43,7 +43,7 @@ void ares__freeaddrinfo_cnames(struct ares_addrinfo_cname *head)
   }
 }
 
-void ares__freeaddrinfo_nodes(struct ares_addrinfo_node *head)
+void ares_freeaddrinfo_nodes(struct ares_addrinfo_node *head)
 {
   struct ares_addrinfo_node *current;
   while (head) {
@@ -59,8 +59,8 @@ void ares_freeaddrinfo(struct ares_addrinfo *ai)
   if (ai == NULL) {
     return;
   }
-  ares__freeaddrinfo_cnames(ai->cnames);
-  ares__freeaddrinfo_nodes(ai->nodes);
+  ares_freeaddrinfo_cnames(ai->cnames);
+  ares_freeaddrinfo_nodes(ai->nodes);
 
   ares_free(ai->name);
   ares_free(ai);
diff --git a/src/lib/ares_getaddrinfo.c b/src/lib/ares_getaddrinfo.c
index e71249a..f40ba66 100644
--- a/src/lib/ares_getaddrinfo.c
+++ b/src/lib/ares_getaddrinfo.c
@@ -101,7 +101,7 @@ static const struct ares_addrinfo_hints default_hints = {
 static ares_bool_t next_dns_lookup(struct host_query *hquery);
 
 struct ares_addrinfo_cname *
-  ares__append_addrinfo_cname(struct ares_addrinfo_cname **head)
+  ares_append_addrinfo_cname(struct ares_addrinfo_cname **head)
 {
   struct ares_addrinfo_cname *tail = ares_malloc_zero(sizeof(*tail));
   struct ares_addrinfo_cname *last = *head;
@@ -123,8 +123,8 @@ struct ares_addrinfo_cname *
   return tail;
 }
 
-void ares__addrinfo_cat_cnames(struct ares_addrinfo_cname **head,
-                               struct ares_addrinfo_cname  *tail)
+void ares_addrinfo_cat_cnames(struct ares_addrinfo_cname **head,
+                              struct ares_addrinfo_cname  *tail)
 {
   struct ares_addrinfo_cname *last = *head;
   if (!last) {
@@ -141,7 +141,7 @@ void ares__addrinfo_cat_cnames(struct ares_addrinfo_cname **head,
 
 /* Allocate new addrinfo and append to the tail. */
 struct ares_addrinfo_node *
-  ares__append_addrinfo_node(struct ares_addrinfo_node **head)
+  ares_append_addrinfo_node(struct ares_addrinfo_node **head)
 {
   struct ares_addrinfo_node *tail = ares_malloc_zero(sizeof(*tail));
   struct ares_addrinfo_node *last = *head;
@@ -163,8 +163,8 @@ struct ares_addrinfo_node *
   return tail;
 }
 
-void ares__addrinfo_cat_nodes(struct ares_addrinfo_node **head,
-                              struct ares_addrinfo_node  *tail)
+void ares_addrinfo_cat_nodes(struct ares_addrinfo_node **head,
+                             struct ares_addrinfo_node  *tail)
 {
   struct ares_addrinfo_node *last = *head;
   if (!last) {
@@ -252,7 +252,7 @@ static ares_bool_t fake_addrinfo(const char *name, unsigned short port,
     ares_bool_t valid   = ARES_TRUE;
     const char *p;
     for (p = name; *p; p++) {
-      if (!ares__isdigit(*p) && *p != '.') {
+      if (!ares_isdigit(*p) && *p != '.') {
         valid = ARES_FALSE;
         break;
       } else if (*p == '.') {
@@ -297,7 +297,7 @@ static ares_bool_t fake_addrinfo(const char *name, unsigned short port,
   }
 
   if (hints->ai_flags & ARES_AI_CANONNAME) {
-    cname = ares__append_addrinfo_cname(&ai->cnames);
+    cname = ares_append_addrinfo_cname(&ai->cnames);
     if (!cname) {
       /* LCOV_EXCL_START: OutOfMemory */
       ares_freeaddrinfo(ai);
@@ -327,7 +327,7 @@ static void hquery_free(struct host_query *hquery, ares_bool_t cleanup_ai)
   if (cleanup_ai) {
     ares_freeaddrinfo(hquery->ai);
   }
-  ares__strsplit_free(hquery->names, hquery->names_cnt);
+  ares_strsplit_free(hquery->names, hquery->names_cnt);
   ares_free(hquery->name);
   ares_free(hquery->lookups);
   ares_free(hquery);
@@ -341,7 +341,7 @@ static void end_hquery(struct host_query *hquery, ares_status_t status)
   if (status == ARES_SUCCESS) {
     if (!(hquery->hints.ai_flags & ARES_AI_NOSORT) && hquery->ai->nodes) {
       sentinel.ai_next = hquery->ai->nodes;
-      ares__sortaddrinfo(hquery->channel, &sentinel);
+      ares_sortaddrinfo(hquery->channel, &sentinel);
       hquery->ai->nodes = sentinel.ai_next;
     }
     next = hquery->ai->nodes;
@@ -361,7 +361,7 @@ static void end_hquery(struct host_query *hquery, ares_status_t status)
   hquery_free(hquery, ARES_FALSE);
 }
 
-ares_bool_t ares__is_localhost(const char *name)
+ares_bool_t ares_is_localhost(const char *name)
 {
   /* RFC6761 6.3 says : The domain "localhost." and any names falling within
    * ".localhost." */
@@ -394,11 +394,11 @@ static ares_status_t file_lookup(struct host_query *hquery)
   ares_status_t             status;
 
   /* Per RFC 7686, reject queries for ".onion" domain names with NXDOMAIN. */
-  if (ares__is_onion_domain(hquery->name)) {
+  if (ares_is_onion_domain(hquery->name)) {
     return ARES_ENOTFOUND;
   }
 
-  status = ares__hosts_search_host(
+  status = ares_hosts_search_host(
     hquery->channel,
     (hquery->hints.ai_flags & ARES_AI_ENVHOSTS) ? ARES_TRUE : ARES_FALSE,
     hquery->name, &entry);
@@ -407,7 +407,7 @@ static ares_status_t file_lookup(struct host_query *hquery)
     goto done;
   }
 
-  status = ares__hosts_entry_to_addrinfo(
+  status = ares_hosts_entry_to_addrinfo(
     entry, hquery->name, hquery->hints.ai_family, hquery->port,
     (hquery->hints.ai_flags & ARES_AI_CANONNAME) ? ARES_TRUE : ARES_FALSE,
     hquery->ai);
@@ -424,9 +424,9 @@ done:
    * We will also ignore ALL errors when trying to resolve localhost, such
    * as permissions errors reading /etc/hosts or a malformed /etc/hosts */
   if (status != ARES_SUCCESS && status != ARES_ENOMEM &&
-      ares__is_localhost(hquery->name)) {
-    return ares__addrinfo_localhost(hquery->name, hquery->port, &hquery->hints,
-                                    hquery->ai);
+      ares_is_localhost(hquery->name)) {
+    return ares_addrinfo_localhost(hquery->name, hquery->port, &hquery->hints,
+                                   hquery->ai);
   }
 
   return status;
@@ -440,7 +440,7 @@ static void next_lookup(struct host_query *hquery, ares_status_t status)
        * queries for localhost names to their configured caching DNS
        * server(s)."
        * Otherwise, DNS lookup. */
-      if (!ares__is_localhost(hquery->name) && next_dns_lookup(hquery)) {
+      if (!ares_is_localhost(hquery->name) && next_dns_lookup(hquery)) {
         break;
       }
 
@@ -477,7 +477,7 @@ static void terminate_retries(const struct host_query *hquery,
     return;
   }
 
-  query = ares__htable_szvp_get_direct(channel->queries_by_qid, term_qid);
+  query = ares_htable_szvp_get_direct(channel->queries_by_qid, term_qid);
   if (query == NULL) {
     return;
   }
@@ -498,7 +498,7 @@ static void host_callback(void *arg, ares_status_t status, size_t timeouts,
       addinfostatus = ARES_EBADRESP; /* LCOV_EXCL_LINE: DefensiveCoding */
     } else {
       addinfostatus =
-        ares__parse_into_addrinfo(dnsrec, ARES_TRUE, hquery->port, hquery->ai);
+        ares_parse_into_addrinfo(dnsrec, ARES_TRUE, hquery->port, hquery->ai);
     }
     if (addinfostatus == ARES_SUCCESS) {
       terminate_retries(hquery, ares_dns_record_get_id(dnsrec));
@@ -530,7 +530,7 @@ static void host_callback(void *arg, ares_status_t status, size_t timeouts,
       }
       next_lookup(hquery, hquery->nodata_cnt ? ARES_ENODATA : status);
     } else if ((status == ARES_ESERVFAIL || status == ARES_EREFUSED) &&
-               ares__name_label_cnt(hquery->names[hquery->next_name_idx - 1]) ==
+               ares_name_label_cnt(hquery->names[hquery->next_name_idx - 1]) ==
                  1) {
       /* Issue #852, systemd-resolved may return SERVFAIL or REFUSED on a
        * single label domain name. */
@@ -567,7 +567,7 @@ static void ares_getaddrinfo_int(ares_channel_t *channel, const char *name,
     return;
   }
 
-  if (ares__is_onion_domain(name)) {
+  if (ares_is_onion_domain(name)) {
     callback(arg, ARES_ENOTFOUND, 0, NULL);
     return;
   }
@@ -630,7 +630,7 @@ static void ares_getaddrinfo_int(ares_channel_t *channel, const char *name,
   }
 
   status =
-    ares__search_name_list(channel, name, &hquery->names, &hquery->names_cnt);
+    ares_search_name_list(channel, name, &hquery->names, &hquery->names_cnt);
   if (status != ARES_SUCCESS) {
     hquery_free(hquery, ARES_TRUE);
     callback(arg, (int)status, 0, NULL);
@@ -659,9 +659,9 @@ void ares_getaddrinfo(ares_channel_t *channel, const char *name,
   if (channel == NULL) {
     return;
   }
-  ares__channel_lock(channel);
+  ares_channel_lock(channel);
   ares_getaddrinfo_int(channel, name, service, hints, callback, arg);
-  ares__channel_unlock(channel);
+  ares_channel_unlock(channel);
 }
 
 static ares_bool_t next_dns_lookup(struct host_query *hquery)
diff --git a/src/lib/ares_gethostbyaddr.c b/src/lib/ares_gethostbyaddr.c
index 1db81ec..1b02c94 100644
--- a/src/lib/ares_gethostbyaddr.c
+++ b/src/lib/ares_gethostbyaddr.c
@@ -112,9 +112,9 @@ void ares_gethostbyaddr(ares_channel_t *channel, const void *addr, int addrlen,
   if (channel == NULL) {
     return;
   }
-  ares__channel_lock(channel);
+  ares_channel_lock(channel);
   ares_gethostbyaddr_nolock(channel, addr, addrlen, family, callback, arg);
-  ares__channel_unlock(channel);
+  ares_channel_unlock(channel);
 }
 
 static void next_lookup(struct addr_query *aquery)
@@ -216,12 +216,12 @@ static ares_status_t file_lookup(ares_channel_t         *channel,
     return ARES_ENOTFOUND;
   }
 
-  status = ares__hosts_search_ipaddr(channel, ARES_FALSE, ipaddr, &entry);
+  status = ares_hosts_search_ipaddr(channel, ARES_FALSE, ipaddr, &entry);
   if (status != ARES_SUCCESS) {
     return status;
   }
 
-  status = ares__hosts_entry_to_hostent(entry, addr->family, host);
+  status = ares_hosts_entry_to_hostent(entry, addr->family, host);
   if (status != ARES_SUCCESS) {
     return status; /* LCOV_EXCL_LINE: OutOfMemory */
   }
diff --git a/src/lib/ares_gethostbyname.c b/src/lib/ares_gethostbyname.c
index 6db86e0..e917d91 100644
--- a/src/lib/ares_gethostbyname.c
+++ b/src/lib/ares_gethostbyname.c
@@ -68,7 +68,7 @@ static void ares_gethostbyname_callback(void *arg, int status, int timeouts,
   struct host_query *ghbn_arg = arg;
 
   if (status == ARES_SUCCESS) {
-    status = (int)ares__addrinfo2hostent(result, AF_UNSPEC, &hostent);
+    status = (int)ares_addrinfo2hostent(result, AF_UNSPEC, &hostent);
   }
 
   /* addrinfo2hostent will only return ENODATA if there are no addresses _and_
@@ -175,7 +175,7 @@ static size_t get_address_index(const struct in_addr  *addr,
       continue;
     }
 
-    if (ares__subnet_match(&aaddr, &sortlist[i].addr, sortlist[i].mask)) {
+    if (ares_subnet_match(&aaddr, &sortlist[i].addr, sortlist[i].mask)) {
       break;
     }
   }
@@ -231,15 +231,15 @@ static size_t get6_address_index(const struct ares_in6_addr *addr,
       continue;
     }
 
-    if (ares__subnet_match(&aaddr, &sortlist[i].addr, sortlist[i].mask)) {
+    if (ares_subnet_match(&aaddr, &sortlist[i].addr, sortlist[i].mask)) {
       break;
     }
   }
   return i;
 }
 
-static ares_status_t ares__hostent_localhost(const char *name, int family,
-                                             struct hostent **host_out)
+static ares_status_t ares_hostent_localhost(const char *name, int family,
+                                            struct hostent **host_out)
 {
   ares_status_t              status;
   struct ares_addrinfo      *ai = NULL;
@@ -254,12 +254,12 @@ static ares_status_t ares__hostent_localhost(const char *name, int family,
     goto done;            /* LCOV_EXCL_LINE: OutOfMemory */
   }
 
-  status = ares__addrinfo_localhost(name, 0, &hints, ai);
+  status = ares_addrinfo_localhost(name, 0, &hints, ai);
   if (status != ARES_SUCCESS) {
     goto done; /* LCOV_EXCL_LINE: OutOfMemory */
   }
 
-  status = ares__addrinfo2hostent(ai, family, host_out);
+  status = ares_addrinfo2hostent(ai, family, host_out);
   if (status != ARES_SUCCESS) {
     goto done; /* LCOV_EXCL_LINE: OutOfMemory */
   }
@@ -289,16 +289,16 @@ static ares_status_t ares_gethostbyname_file_int(ares_channel_t *channel,
   }
 
   /* Per RFC 7686, reject queries for ".onion" domain names with NXDOMAIN. */
-  if (ares__is_onion_domain(name)) {
+  if (ares_is_onion_domain(name)) {
     return ARES_ENOTFOUND;
   }
 
-  status = ares__hosts_search_host(channel, ARES_FALSE, name, &entry);
+  status = ares_hosts_search_host(channel, ARES_FALSE, name, &entry);
   if (status != ARES_SUCCESS) {
     goto done;
   }
 
-  status = ares__hosts_entry_to_hostent(entry, family, host);
+  status = ares_hosts_entry_to_hostent(entry, family, host);
   if (status != ARES_SUCCESS) {
     goto done; /* LCOV_EXCL_LINE: OutOfMemory */
   }
@@ -310,8 +310,8 @@ done:
    * We will also ignore ALL errors when trying to resolve localhost, such
    * as permissions errors reading /etc/hosts or a malformed /etc/hosts */
   if (status != ARES_SUCCESS && status != ARES_ENOMEM &&
-      ares__is_localhost(name)) {
-    return ares__hostent_localhost(name, family, host);
+      ares_is_localhost(name)) {
+    return ares_hostent_localhost(name, family, host);
   }
 
   return status;
@@ -325,8 +325,8 @@ int ares_gethostbyname_file(ares_channel_t *channel, const char *name,
     return ARES_ENOTFOUND;
   }
 
-  ares__channel_lock(channel);
+  ares_channel_lock(channel);
   status = ares_gethostbyname_file_int(channel, name, family, host);
-  ares__channel_unlock(channel);
+  ares_channel_unlock(channel);
   return (int)status;
 }
diff --git a/src/lib/ares_getnameinfo.c b/src/lib/ares_getnameinfo.c
index 622c1ad..0159354 100644
--- a/src/lib/ares_getnameinfo.c
+++ b/src/lib/ares_getnameinfo.c
@@ -193,9 +193,9 @@ void ares_getnameinfo(ares_channel_t *channel, const struct sockaddr *sa,
     return;
   }
 
-  ares__channel_lock(channel);
+  ares_channel_lock(channel);
   ares_getnameinfo_int(channel, sa, salen, flags_int, callback, arg);
-  ares__channel_unlock(channel);
+  ares_channel_unlock(channel);
 }
 
 static void nameinfo_callback(void *arg, int status, int timeouts,
@@ -410,8 +410,8 @@ static char *ares_striendstr(const char *s1, const char *s2)
   c1       = c1_begin;
   c2       = s2;
   while (c2 < s2 + s2_len) {
-    lo1 = ares__tolower((unsigned char)*c1);
-    lo2 = ares__tolower((unsigned char)*c2);
+    lo1 = ares_tolower((unsigned char)*c1);
+    lo2 = ares_tolower((unsigned char)*c2);
     if (lo1 != lo2) {
       return NULL;
     } else {
@@ -423,7 +423,7 @@ static char *ares_striendstr(const char *s1, const char *s2)
   return (char *)((size_t)c1_begin);
 }
 
-ares_bool_t ares__is_onion_domain(const char *name)
+ares_bool_t ares_is_onion_domain(const char *name)
 {
   if (ares_striendstr(name, ".onion")) {
     return ARES_TRUE;
diff --git a/src/lib/ares_hosts_file.c b/src/lib/ares_hosts_file.c
new file mode 100644
index 0000000..039ebb0
--- /dev/null
+++ b/src/lib/ares_hosts_file.c
@@ -0,0 +1,947 @@
+/* MIT License
+ *
+ * Copyright (c) 2023 Brad House
+ *
+ * Permission is hereby granted, free of charge, to any person obtaining a copy
+ * of this software and associated documentation files (the "Software"), to deal
+ * in the Software without restriction, including without limitation the rights
+ * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
+ * copies of the Software, and to permit persons to whom the Software is
+ * furnished to do so, subject to the following conditions:
+ *
+ * The above copyright notice and this permission notice (including the next
+ * paragraph) shall be included in all copies or substantial portions of the
+ * Software.
+ *
+ * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
+ * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
+ * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
+ * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
+ * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
+ * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
+ * SOFTWARE.
+ *
+ * SPDX-License-Identifier: MIT
+ */
+#include "ares_private.h"
+#ifdef HAVE_SYS_TYPES_H
+#  include <sys/types.h>
+#endif
+#ifdef HAVE_SYS_STAT_H
+#  include <sys/stat.h>
+#endif
+#ifdef HAVE_NETINET_IN_H
+#  include <netinet/in.h>
+#endif
+#ifdef HAVE_NETDB_H
+#  include <netdb.h>
+#endif
+#ifdef HAVE_ARPA_INET_H
+#  include <arpa/inet.h>
+#endif
+#include <time.h>
+#include "ares_platform.h"
+
+/* HOSTS FILE PROCESSING OVERVIEW
+ * ==============================
+ * The hosts file on the system contains static entries to be processed locally
+ * rather than querying the nameserver.  Each row is an IP address followed by
+ * a list of space delimited hostnames that match the ip address.  This is used
+ * for both forward and reverse lookups.
+ *
+ * We are caching the entire parsed hosts file for performance reasons.  Some
+ * files may be quite sizable and as per Issue #458 can approach 1/2MB in size,
+ * and the parse overhead on a rapid succession of queries can be quite large.
+ * The entries are stored in forwards and backwards hashtables so we can get
+ * O(1) performance on lookup.  The file is cached until the file modification
+ * timestamp changes.
+ *
+ * The hosts file processing is quite unique. It has to merge all related hosts
+ * and ips into a single entry due to file formatting requirements.  For
+ * instance take the below:
+ *
+ * 127.0.0.1    localhost.localdomain localhost
+ * ::1          localhost.localdomain localhost
+ * 192.168.1.1  host.example.com host
+ * 192.168.1.5  host.example.com host
+ * 2620:1234::1 host.example.com host6.example.com host6 host
+ *
+ * This will yield 2 entries.
+ *  1) ips: 127.0.0.1,::1
+ *     hosts: localhost.localdomain,localhost
+ *  2) ips: 192.168.1.1,192.168.1.5,2620:1234::1
+ *     hosts: host.example.com,host,host6.example.com,host6
+ *
+ * It could be argued that if searching for 192.168.1.1 that the 'host6'
+ * hostnames should not be returned, but this implementation will return them
+ * since they are related.  It is unlikely this will matter in the real world.
+ */
+
+struct ares_hosts_file {
+  time_t               ts;
+  /*! cache the filename so we know if the filename changes it automatically
+   *  invalidates the cache */
+  char                *filename;
+  /*! iphash is the owner of the 'entry' object as there is only ever a single
+   *  match to the object. */
+  ares_htable_strvp_t *iphash;
+  /*! hosthash does not own the entry so won't free on destruction */
+  ares_htable_strvp_t *hosthash;
+};
+
+struct ares_hosts_entry {
+  size_t        refcnt; /*! If the entry is stored multiple times in the
+                         *  ip address hash, we have to reference count it */
+  ares_llist_t *ips;
+  ares_llist_t *hosts;
+};
+
+const void *ares_dns_pton(const char *ipaddr, struct ares_addr *addr,
+                          size_t *out_len)
+{
+  const void *ptr     = NULL;
+  size_t      ptr_len = 0;
+
+  if (ipaddr == NULL || addr == NULL || out_len == NULL) {
+    return NULL; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  *out_len = 0;
+
+  if (addr->family == AF_INET &&
+      ares_inet_pton(AF_INET, ipaddr, &addr->addr.addr4) > 0) {
+    ptr     = &addr->addr.addr4;
+    ptr_len = sizeof(addr->addr.addr4);
+  } else if (addr->family == AF_INET6 &&
+             ares_inet_pton(AF_INET6, ipaddr, &addr->addr.addr6) > 0) {
+    ptr     = &addr->addr.addr6;
+    ptr_len = sizeof(addr->addr.addr6);
+  } else if (addr->family == AF_UNSPEC) {
+    if (ares_inet_pton(AF_INET, ipaddr, &addr->addr.addr4) > 0) {
+      addr->family = AF_INET;
+      ptr          = &addr->addr.addr4;
+      ptr_len      = sizeof(addr->addr.addr4);
+    } else if (ares_inet_pton(AF_INET6, ipaddr, &addr->addr.addr6) > 0) {
+      addr->family = AF_INET6;
+      ptr          = &addr->addr.addr6;
+      ptr_len      = sizeof(addr->addr.addr6);
+    }
+  }
+
+  *out_len = ptr_len;
+  return ptr;
+}
+
+static ares_bool_t ares_normalize_ipaddr(const char *ipaddr, char *out,
+                                         size_t out_len)
+{
+  struct ares_addr data;
+  const void      *addr;
+  size_t           addr_len = 0;
+
+  memset(&data, 0, sizeof(data));
+  data.family = AF_UNSPEC;
+
+  addr = ares_dns_pton(ipaddr, &data, &addr_len);
+  if (addr == NULL) {
+    return ARES_FALSE;
+  }
+
+  if (!ares_inet_ntop(data.family, addr, out, (ares_socklen_t)out_len)) {
+    return ARES_FALSE; /* LCOV_EXCL_LINE: DefensiveCoding */
+  }
+
+  return ARES_TRUE;
+}
+
+static void ares_hosts_entry_destroy(ares_hosts_entry_t *entry)
+{
+  if (entry == NULL) {
+    return;
+  }
+
+  /* Honor reference counting */
+  if (entry->refcnt != 0) {
+    entry->refcnt--;
+  }
+
+  if (entry->refcnt > 0) {
+    return;
+  }
+
+  ares_llist_destroy(entry->hosts);
+  ares_llist_destroy(entry->ips);
+  ares_free(entry);
+}
+
+static void ares_hosts_entry_destroy_cb(void *entry)
+{
+  ares_hosts_entry_destroy(entry);
+}
+
+void ares_hosts_file_destroy(ares_hosts_file_t *hf)
+{
+  if (hf == NULL) {
+    return;
+  }
+
+  ares_free(hf->filename);
+  ares_htable_strvp_destroy(hf->hosthash);
+  ares_htable_strvp_destroy(hf->iphash);
+  ares_free(hf);
+}
+
+static ares_hosts_file_t *ares_hosts_file_create(const char *filename)
+{
+  ares_hosts_file_t *hf = ares_malloc_zero(sizeof(*hf));
+  if (hf == NULL) {
+    goto fail;
+  }
+
+  hf->ts = time(NULL);
+
+  hf->filename = ares_strdup(filename);
+  if (hf->filename == NULL) {
+    goto fail;
+  }
+
+  hf->iphash = ares_htable_strvp_create(ares_hosts_entry_destroy_cb);
+  if (hf->iphash == NULL) {
+    goto fail;
+  }
+
+  hf->hosthash = ares_htable_strvp_create(NULL);
+  if (hf->hosthash == NULL) {
+    goto fail;
+  }
+
+  return hf;
+
+fail:
+  ares_hosts_file_destroy(hf);
+  return NULL;
+}
+
+typedef enum {
+  ARES_MATCH_NONE   = 0,
+  ARES_MATCH_IPADDR = 1,
+  ARES_MATCH_HOST   = 2
+} ares_hosts_file_match_t;
+
+static ares_status_t ares_hosts_file_merge_entry(
+  const ares_hosts_file_t *hf, ares_hosts_entry_t *existing,
+  ares_hosts_entry_t *entry, ares_hosts_file_match_t matchtype)
+{
+  ares_llist_node_t *node;
+
+  /* If we matched on IP address, we know there can only be 1, so there's no
+   * reason to do anything */
+  if (matchtype != ARES_MATCH_IPADDR) {
+    while ((node = ares_llist_node_first(entry->ips)) != NULL) {
+      const char *ipaddr = ares_llist_node_val(node);
+
+      if (ares_htable_strvp_get_direct(hf->iphash, ipaddr) != NULL) {
+        ares_llist_node_destroy(node);
+        continue;
+      }
+
+      ares_llist_node_mvparent_last(node, existing->ips);
+    }
+  }
+
+
+  while ((node = ares_llist_node_first(entry->hosts)) != NULL) {
+    const char *hostname = ares_llist_node_val(node);
+
+    if (ares_htable_strvp_get_direct(hf->hosthash, hostname) != NULL) {
+      ares_llist_node_destroy(node);
+      continue;
+    }
+
+    ares_llist_node_mvparent_last(node, existing->hosts);
+  }
+
+  ares_hosts_entry_destroy(entry);
+  return ARES_SUCCESS;
+}
+
+static ares_hosts_file_match_t
+  ares_hosts_file_match(const ares_hosts_file_t *hf, ares_hosts_entry_t *entry,
+                        ares_hosts_entry_t **match)
+{
+  ares_llist_node_t *node;
+  *match = NULL;
+
+  for (node = ares_llist_node_first(entry->ips); node != NULL;
+       node = ares_llist_node_next(node)) {
+    const char *ipaddr = ares_llist_node_val(node);
+    *match             = ares_htable_strvp_get_direct(hf->iphash, ipaddr);
+    if (*match != NULL) {
+      return ARES_MATCH_IPADDR;
+    }
+  }
+
+  for (node = ares_llist_node_first(entry->hosts); node != NULL;
+       node = ares_llist_node_next(node)) {
+    const char *host = ares_llist_node_val(node);
+    *match           = ares_htable_strvp_get_direct(hf->hosthash, host);
+    if (*match != NULL) {
+      return ARES_MATCH_HOST;
+    }
+  }
+
+  return ARES_MATCH_NONE;
+}
+
+/*! entry is invalidated upon calling this function, always, even on error */
+static ares_status_t ares_hosts_file_add(ares_hosts_file_t  *hosts,
+                                         ares_hosts_entry_t *entry)
+{
+  ares_hosts_entry_t     *match  = NULL;
+  ares_status_t           status = ARES_SUCCESS;
+  ares_llist_node_t      *node;
+  ares_hosts_file_match_t matchtype;
+  size_t                  num_hostnames;
+
+  /* Record the number of hostnames in this entry file.  If we merge into an
+   * existing record, these will be *appended* to the entry, so we'll count
+   * backwards when adding to the hosts hashtable */
+  num_hostnames = ares_llist_len(entry->hosts);
+
+  matchtype = ares_hosts_file_match(hosts, entry, &match);
+
+  if (matchtype != ARES_MATCH_NONE) {
+    status = ares_hosts_file_merge_entry(hosts, match, entry, matchtype);
+    if (status != ARES_SUCCESS) {
+      ares_hosts_entry_destroy(entry); /* LCOV_EXCL_LINE: DefensiveCoding */
+      return status;                   /* LCOV_EXCL_LINE: DefensiveCoding */
+    }
+    /* entry was invalidated above by merging */
+    entry = match;
+  }
+
+  if (matchtype != ARES_MATCH_IPADDR) {
+    const char *ipaddr = ares_llist_last_val(entry->ips);
+
+    if (!ares_htable_strvp_get(hosts->iphash, ipaddr, NULL)) {
+      if (!ares_htable_strvp_insert(hosts->iphash, ipaddr, entry)) {
+        ares_hosts_entry_destroy(entry);
+        return ARES_ENOMEM;
+      }
+      entry->refcnt++;
+    }
+  }
+
+  /* Go backwards, on a merge, hostnames are appended.  Breakout once we've
+   * consumed all the hosts that we appended */
+  for (node = ares_llist_node_last(entry->hosts); node != NULL;
+       node = ares_llist_node_prev(node)) {
+    const char *val = ares_llist_node_val(node);
+
+    if (num_hostnames == 0) {
+      break;
+    }
+
+    num_hostnames--;
+
+    /* first hostname match wins.  If we detect a duplicate hostname for another
+     * ip it will automatically be added to the same entry */
+    if (ares_htable_strvp_get(hosts->hosthash, val, NULL)) {
+      continue;
+    }
+
+    if (!ares_htable_strvp_insert(hosts->hosthash, val, entry)) {
+      return ARES_ENOMEM;
+    }
+  }
+
+  return ARES_SUCCESS;
+}
+
+static ares_bool_t ares_hosts_entry_isdup(ares_hosts_entry_t *entry,
+                                          const char         *host)
+{
+  ares_llist_node_t *node;
+
+  for (node = ares_llist_node_first(entry->ips); node != NULL;
+       node = ares_llist_node_next(node)) {
+    const char *myhost = ares_llist_node_val(node);
+    if (ares_strcaseeq(myhost, host)) {
+      return ARES_TRUE;
+    }
+  }
+
+  return ARES_FALSE;
+}
+
+static ares_status_t ares_parse_hosts_hostnames(ares_buf_t         *buf,
+                                                ares_hosts_entry_t *entry)
+{
+  entry->hosts = ares_llist_create(ares_free);
+  if (entry->hosts == NULL) {
+    return ARES_ENOMEM;
+  }
+
+  /* Parse hostnames and aliases */
+  while (ares_buf_len(buf)) {
+    char          hostname[256];
+    char         *temp;
+    ares_status_t status;
+    unsigned char comment = '#';
+
+    ares_buf_consume_whitespace(buf, ARES_FALSE);
+
+    if (ares_buf_len(buf) == 0) {
+      break;
+    }
+
+    /* See if it is a comment, if so stop processing */
+    if (ares_buf_begins_with(buf, &comment, 1)) {
+      break;
+    }
+
+    ares_buf_tag(buf);
+
+    /* Must be at end of line */
+    if (ares_buf_consume_nonwhitespace(buf) == 0) {
+      break;
+    }
+
+    status = ares_buf_tag_fetch_string(buf, hostname, sizeof(hostname));
+    if (status != ARES_SUCCESS) {
+      /* Bad entry, just ignore as long as its not the first.  If its the first,
+       * it must be valid */
+      if (ares_llist_len(entry->hosts) == 0) {
+        return ARES_EBADSTR;
+      }
+
+      continue;
+    }
+
+    /* Validate it is a valid hostname characterset */
+    if (!ares_is_hostname(hostname)) {
+      continue;
+    }
+
+    /* Don't add a duplicate to the same entry */
+    if (ares_hosts_entry_isdup(entry, hostname)) {
+      continue;
+    }
+
+    /* Add to list */
+    temp = ares_strdup(hostname);
+    if (temp == NULL) {
+      return ARES_ENOMEM;
+    }
+
+    if (ares_llist_insert_last(entry->hosts, temp) == NULL) {
+      ares_free(temp);
+      return ARES_ENOMEM;
+    }
+  }
+
+  /* Must have at least 1 entry */
+  if (ares_llist_len(entry->hosts) == 0) {
+    return ARES_EBADSTR;
+  }
+
+  return ARES_SUCCESS;
+}
+
+static ares_status_t ares_parse_hosts_ipaddr(ares_buf_t          *buf,
+                                             ares_hosts_entry_t **entry_out)
+{
+  char                addr[INET6_ADDRSTRLEN];
+  char               *temp;
+  ares_hosts_entry_t *entry = NULL;
+  ares_status_t       status;
+
+  *entry_out = NULL;
+
+  ares_buf_tag(buf);
+  ares_buf_consume_nonwhitespace(buf);
+  status = ares_buf_tag_fetch_string(buf, addr, sizeof(addr));
+  if (status != ARES_SUCCESS) {
+    return status;
+  }
+
+  /* Validate and normalize the ip address format */
+  if (!ares_normalize_ipaddr(addr, addr, sizeof(addr))) {
+    return ARES_EBADSTR;
+  }
+
+  entry = ares_malloc_zero(sizeof(*entry));
+  if (entry == NULL) {
+    return ARES_ENOMEM;
+  }
+
+  entry->ips = ares_llist_create(ares_free);
+  if (entry->ips == NULL) {
+    ares_hosts_entry_destroy(entry);
+    return ARES_ENOMEM;
+  }
+
+  temp = ares_strdup(addr);
+  if (temp == NULL) {
+    ares_hosts_entry_destroy(entry);
+    return ARES_ENOMEM;
+  }
+
+  if (ares_llist_insert_first(entry->ips, temp) == NULL) {
+    ares_free(temp);
+    ares_hosts_entry_destroy(entry);
+    return ARES_ENOMEM;
+  }
+
+  *entry_out = entry;
+
+  return ARES_SUCCESS;
+}
+
+static ares_status_t ares_parse_hosts(const char         *filename,
+                                      ares_hosts_file_t **out)
+{
+  ares_buf_t         *buf    = NULL;
+  ares_status_t       status = ARES_EBADRESP;
+  ares_hosts_file_t  *hf     = NULL;
+  ares_hosts_entry_t *entry  = NULL;
+
+  *out = NULL;
+
+  buf = ares_buf_create();
+  if (buf == NULL) {
+    status = ARES_ENOMEM;
+    goto done;
+  }
+
+  status = ares_buf_load_file(filename, buf);
+  if (status != ARES_SUCCESS) {
+    goto done;
+  }
+
+  hf = ares_hosts_file_create(filename);
+  if (hf == NULL) {
+    status = ARES_ENOMEM;
+    goto done;
+  }
+
+  while (ares_buf_len(buf)) {
+    unsigned char comment = '#';
+
+    /* -- Start of new line here -- */
+
+    /* Consume any leading whitespace */
+    ares_buf_consume_whitespace(buf, ARES_FALSE);
+
+    if (ares_buf_len(buf) == 0) {
+      break;
+    }
+
+    /* See if it is a comment, if so, consume remaining line */
+    if (ares_buf_begins_with(buf, &comment, 1)) {
+      ares_buf_consume_line(buf, ARES_TRUE);
+      continue;
+    }
+
+    /* Pull off ip address */
+    status = ares_parse_hosts_ipaddr(buf, &entry);
+    if (status == ARES_ENOMEM) {
+      goto done;
+    }
+    if (status != ARES_SUCCESS) {
+      /* Bad line, consume and go onto next */
+      ares_buf_consume_line(buf, ARES_TRUE);
+      continue;
+    }
+
+    /* Parse of the hostnames */
+    status = ares_parse_hosts_hostnames(buf, entry);
+    if (status == ARES_ENOMEM) {
+      goto done;
+    } else if (status != ARES_SUCCESS) {
+      /* Bad line, consume and go onto next */
+      ares_hosts_entry_destroy(entry);
+      entry = NULL;
+      ares_buf_consume_line(buf, ARES_TRUE);
+      continue;
+    }
+
+    /* Append the successful entry to the hosts file */
+    status = ares_hosts_file_add(hf, entry);
+    entry  = NULL; /* is always invalidated by this function, even on error */
+    if (status != ARES_SUCCESS) {
+      goto done;
+    }
+
+    /* Go to next line */
+    ares_buf_consume_line(buf, ARES_TRUE);
+  }
+
+  status = ARES_SUCCESS;
+
+done:
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
