# Compiling tcpdump on Haiku

## AMD64 R1/beta6

* Both HaikuPorts and local libpcap are suitable.
* Autoconf 2.72 works.
* CMake 4.1.6 works.
* GCC 13.3.0 works.
* Clang 22.1.8 works.

The following command will install respective non-default packages:
```
pkgman install libpcap_devel cmake llvm22_clang
```

For reference, the tests were done using a system installed from
`haiku-r1beta6-x86_64-anyboot.iso`.
