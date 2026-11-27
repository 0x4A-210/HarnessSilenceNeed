# Compiling tcpdump on Solaris and related OSes

* Autoconf works everywhere.

## OmniOS r151054/AMD64

* Both system and local libpcap are suitable.
* CMake 4.0.1 works.
* GCC 14.2.0 and Clang 20.1.2 work.

## Oracle Solaris CBE 11.4.90.212.0/AMD64
* Both system and local libpcap are suitable.
* CMake 3.24.0 works.
* GCC 15.2.0 and Clang 21.1.0 work.
* Sun C 5.15 works.

For reference, the tests were done using the following packages:
```shell
xargs -L1 pkg install <<ENDOFTEXT
developer/build/autoconf
developer/build/cmake
developer/gcc/gcc-c
developer/llvm/clang
ENDOFTEXT
```

## Solaris 11.3/(SPARC and AMD64)

* Both system and local libpcap are suitable.
* CMake 3.14.3 works.
* Sun C 5.13 and GCC 5.5.0 work.

## Solaris 10/SPARC

* Both system and local libpcap are suitable.
* CMake 3.14.3 works.
* Sun C 5.9 and GCC 5.5.0 work.

## Solaris 9

This version of this OS is not supported because the snprintf(3) implementation
in its libc is not suitable.
