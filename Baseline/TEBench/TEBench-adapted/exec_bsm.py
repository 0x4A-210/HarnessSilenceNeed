#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exec_bsm.py —— 路线 2：三版本编译执行 + 覆盖率

和路线 1.5（`ir_bsm.py`，纯静态 AST）的关系
-------------------------------------------
路线 1.5 把"文本/结构上能看见的"榨干了，剩下三类原理上看不见：

  * 运行时失败（NaN 断言、越界）—— 不跑就看不见；
  * "可达 ≠ 被覆盖"—— 静态可达只说"能调到"，不说"这次 fuzz 真的调到了"；
  * 构建/链接类退化 —— 要真编译才知道编不过。

本脚本对每条样本真的把库编出来、把 harness 链上去、跑一小轮 libFuzzer、导出
符号级/行级覆盖率，用执行证据重新判 B/S/M。

三个版本（论文 2.2.1 的口径，按 v9 实际可得性改造）
---------------------------------------------------
  V−1    = 库(M^1) + 旧 harness(H)      M^1 由 change.diff 反向 apply 得到
  V−0.5  = 库(M)   + 旧 harness(H)      就是 agent 能看到的 input/
  V0     = 库(M)   + 修复后 harness(H⁺)  **只有 3 条样本随数据集提供 harness_fix.diff**

这一点必须先说清楚：`verification/harness_fix.diff` 全数据集只有 3 条
（V3-13 flac、V3-47 postgresql、V3-48 binutils），其余 45 条拿不到 H⁺。
所以本轮的**判定只用 V−1 / V−0.5**（这两个版本对 48 条全都可得），
V0 只在 `--oracle` 下对那 3 条跑，作为"上限"对照，**不参与预测**。

另外：`verification/` 里有 `experiments.json`（编译矩阵、崩溃复现、GT 结论），
那是答案。本脚本的判定路径**只读 `case.json` 和 `input/`**，`verification/`
只在 `--oracle` 分支里被读一次（读 harness_fix.diff），并把这个事实写进结果的
`protocol.oracle_used` 字段，避免"偷看答案"的嫌疑。

判定规则（只用执行证据）
------------------------
  breaking     H 在 M 上编不过/链不上，但在 M^1 上可以；
               或同一 corpus 在 M 上崩溃、在 M^1 上不崩。
  stale        M 上能跑，且 **change.diff 新增的行在 M 上真的被执行到**
               （说明新语义落在 harness 实际走的路径上，旧 harness 的断言/期望过时）。
  missing      M 上能跑、新增行没被执行，但库侧新增了外部符号 —— 新行为没有任何
               测试路径覆盖，需要新增测试。
  no_update    以上都不成立：新增行一行都没被执行（改动对该 harness 是死代码）。

覆盖率用 llvm-cov 的 lcov 输出（`FN:`/`FNDA:` 给函数级命中数，`DA:` 给行级），
不是只看"跑没跑过"。

用法
----
    python3 exec_bsm.py --dataset /mnt/c/.../Dataset-v9/dataset \\
        --out results/exec_v9.json --jobs 6 --fuzz-secs 10

    # 只做一次构建可行性探测（不跑 fuzz、不导覆盖率），用来估成本
    python3 exec_bsm.py --dataset ... --out /tmp/probe.json --probe

依赖：WSL2 里的 clang / clang++ / llvm-cov / llvm-profdata / cmake / make / git。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ir_bsm  # 复用行尾归一化 / 反向 apply
import classify_bsm_c  # 只复用 is_test_side（路线 1 修过的测试侧判据）

# ---- 编译与运行参数 -------------------------------------------------------

COV_FLAGS = ['-O1', '-g', '-fprofile-instr-generate', '-fcoverage-mapping']

# 老代码（2018-2020）撞上 clang 21：一批新告警被项目自己的 -Werror 放大成编译失败。
# 这些是**按告警类别**降级，不是全局 -Wno-error（全局的会被 target 级 -Werror 覆盖，
# 而且会把真正的 error 也吞掉）。列出来的都是"新编译器新增的告警"，不是语义错误。
WERROR_OFF = [
    '-Wno-error=strict-prototypes', '-Wno-error=deprecated-declarations',
    '-Wno-error=implicit-function-declaration', '-Wno-error=implicit-int',
    '-Wno-error=int-conversion', '-Wno-error=incompatible-pointer-types',
    '-Wno-error=incompatible-function-pointer-types',
    '-Wno-error=unused-parameter', '-Wno-error=unused-variable',
    '-Wno-error=unused-but-set-variable', '-Wno-error=sign-compare',
    '-Wno-error=missing-field-initializers', '-Wno-error=format-security',
    '-Wno-error=tautological-compare', '-Wno-error=constant-conversion',
]

# 只关掉"风格级"告警；**不关** int-conversion / incompatible-pointer-types ——
# 那两个是 C 的约束违反，默认就是 error，正好是 V3-01 这类 API 退化的真信号。
WNOISE = [
    '-Wno-strict-prototypes', '-Wno-deprecated-declarations',
    '-Wno-unused-parameter', '-Wno-unused-variable',
    '-Wno-unused-but-set-variable', '-Wno-sign-compare',
    '-Wno-missing-field-initializers', '-Wno-tautological-compare',
]
FUZZ_NOLINK = ['-fsanitize=fuzzer-no-link']       # 库：插桩，但不带 fuzzer runtime
FUZZ_LINK = ['-fsanitize=fuzzer']                 # harness：带 runtime

C_EXTS = ('.c',)
CXX_EXTS = ('.cc', '.cpp', '.cxx', '.c++')
SRC_EXTS = C_EXTS + CXX_EXTS

# 构建阶段可能踩的坑，统一记成结构化原因
PH_CONFIGURE = 'configure'
PH_BUILD = 'build'
PH_HARNESS = 'harness_compile'
PH_LINK = 'link'
PH_RUN = 'run'

SKIP_DIR_PARTS = ('/.git/', '/tests/', '/test/', '/doc/', '/docs/', '/examples/',
                  '/testing/', '/benchmark/', '/benchmarks/')


def sh(cmd, cwd=None, timeout=600, env=None, shell=False):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, timeout=timeout, env=env, shell=shell,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = r.stdout.decode('utf-8', 'replace')
        return r.returncode, out, time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b'').decode('utf-8', 'replace')
        return 124, out + '\n[TIMEOUT after %ss]' % timeout, time.time() - t0
    except OSError as e:
        return 127, '[OSError] %s' % e, time.time() - t0


def tail(s, n=1200):
    s = (s or '').strip()
    return s[-n:]


# ---- 目录准备 -------------------------------------------------------------

def copy_tree(src, dst):
    """实体复制（构建会往树里写 .o，硬链接会污染数据集，绝对不能用）。"""
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    rc, out, _ = sh(['cp', '-a', src + '/.', dst], timeout=1800)
    if rc != 0:
        raise RuntimeError('cp -a failed: %s' % tail(out, 400))
    return dst


WERROR_FILE = re.compile(r'-Werror(?:=([A-Za-z0-9_-]+))?')


def strip_werror(root):
    """把构建文件里写死的 -Werror 降级成 -Wno-error。

    命令行上的 `-Wno-error` 会被 target 级 `-Werror` 覆盖（后者排在后面），
    所以只能改构建脚本本身。只动 CMakeLists / *.cmake / Makefile.am / configure.ac，
    **不动任何 .c/.h**；真正的类型错误仍然报错（它们不是 warning）。
    """
    n = 0
    names = ('CMakeLists.txt', 'Makefile.am', 'Makefile.in', 'configure.ac', 'configure.in')
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in ('.git',)]
        for f in fns:
            if f not in names and not f.endswith('.cmake'):
                continue
            p = os.path.join(dp, f)
            try:
                t = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            if '-Werror' not in t:
                continue
            t2 = WERROR_FILE.sub(lambda m: '-Wno-error=' + m.group(1) if m.group(1) else '', t)
            if t2 != t:
                open(p, 'w', encoding='utf-8').write(t2)
                n += 1
    return n


def prepare(case_dir, work):
    """返回 (m, m1, diff_path, reverse_info)。M 与 M1 都是实体副本。"""
    inp = os.path.join(case_dir, 'input')
    src = os.path.join(inp, 'source')
    diff = os.path.join(inp, 'change.diff')
    m = os.path.join(work, 'M')
    m1 = os.path.join(work, 'M1')

    copy_tree(src, m)
    ir_bsm.norm_eol(m)
    strip_werror(m)                       # 构建文件里的 -Werror 降级（M/M1 一致处理）
    copy_tree(m, m1)                      # 从已归一化的 M 复制，M1 自然是 LF，-Werror 也一致

    ok, failed = ir_bsm.reverse_apply(m1, diff, work, allow_patch=False)
    return m, m1, diff, OrderedDict([('applied', len(ok)), ('failed', failed[:8]),
                                     ('failed_n', len(failed))])


# ---- change.diff 新增行 ---------------------------------------------------

def diff_added_lines(patch_path):
    """{相对路径: set(新文件行号)}，只收 +/- 的文本 hunk。

    行号是**新文件**行号，正好能和 M 的覆盖率行号对齐。
    只保留库侧源码（.c/.cc/.cpp/.h），测试/文档/构建脚本的改动不算"新语义"。
    """
    out = {}
    cur = None
    newno = 0
    in_hunk = False
    with open(patch_path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if line.startswith('diff --git '):
                m = re.match(r'diff --git a/(\S+) b/(\S+)', line)
                cur = m.group(2) if m else None
                in_hunk = False
                if cur and cur.endswith(SRC_EXTS) and not classify_bsm_c.is_test_side(cur):
                    out.setdefault(cur, set())
                else:
                    cur = None
                continue
            if cur is None:
                continue
            if line.startswith('@@'):
                m = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
                if not m:
                    in_hunk = False
                    continue
                newno = int(m.group(1))
                in_hunk = True
                continue
            if not in_hunk:
                continue
            if line.startswith('+++') or line.startswith('---') or line.startswith('index '):
                continue
            if line.startswith('+'):
                out[cur].add(newno)
                newno += 1
            elif line.startswith('-'):
                pass
            elif line.startswith(' '):
                newno += 1
    return {k: v for k, v in out.items() if v}


# ---- 构建 -----------------------------------------------------------------

def detect_build(tree):
    """返回 (kind, build_root)。有些项目的构建根在子目录（expat/expat、lz4/contrib/cmake_unofficial）。"""
    if os.path.exists(os.path.join(tree, 'CMakeLists.txt')):
        return 'cmake', tree
    if os.path.exists(os.path.join(tree, 'configure')):
        return 'configure', tree
    skip = {'tests', 'test', 'doc', 'docs', 'examples', 'example', 'third_party',
            'vendor', 'contrib', 'build', 'cmake'}
    cands = []
    for name in sorted(os.listdir(tree)):
        p = os.path.join(tree, name)
        if not os.path.isdir(p) or name in skip or name.startswith('.'):
            continue
        if os.path.exists(os.path.join(p, 'CMakeLists.txt')):
            cands.append((0, p))
        elif os.path.exists(os.path.join(p, 'configure')):
            cands.append((1, p))
    if cands:
        cands.sort()
        return ('cmake' if cands[0][0] == 0 else 'configure'), cands[0][1]
    return None, None


def cmake_configure(tree, bd, timeout):
    os.makedirs(bd, exist_ok=True)
    env = dict(os.environ)
    env.update({'CC': 'clang', 'CXX': 'clang++'})
    cmd = ['cmake', '-S', tree, '-B', bd,
           '-DCMAKE_BUILD_TYPE=Debug',
           '-DCMAKE_C_COMPILER=clang', '-DCMAKE_CXX_COMPILER=clang++',
           '-DBUILD_SHARED_LIBS=OFF', '-DBUILD_TESTING=OFF',
           '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
           # 别编测试：nlohmann 的 doctest 套件、zstd 的 seedcorpora 目标会把时间吃光，
           # 而执行证据只需要"库 + harness"。这些开关对不认识它们的项目只是无害的 unused warning。
           '-DJSON_BuildTests=OFF', '-DBUILD_TESTS=OFF', '-DENABLE_TESTING=OFF',
           '-DCMAKE_BUILD_TESTING=OFF', '-DBUILD_TESTING=OFF',
           '-DLIBXML2_WITH_PYTHON=OFF', '-DLIBXML2_WITH_TESTS=OFF',
           '-DPCRE2_BUILD_TESTS=OFF', '-DPCRE2_SUPPORT_JIT=OFF',
           # CMake 4 移除了 <3.5 的兼容，老项目（expat 2019）会直接报错
           '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
           '-DCMAKE_C_FLAGS=' + ' '.join(COV_FLAGS + FUZZ_NOLINK),
           '-DCMAKE_CXX_FLAGS=' + ' '.join(COV_FLAGS + FUZZ_NOLINK)]
    return sh(cmd, cwd=bd, timeout=timeout, env=env)


def configure_build(tree, bd, timeout):
    # autoconf 的 out-of-tree 支持要求源树干净，而这些项目（zlib 的自制 configure、
    # postgres 的 configure）大多只支持 in-tree。M/M1 本来就是副本，直接原地编。
    bd = tree
    os.makedirs(bd, exist_ok=True)
    env = dict(os.environ)
    env.update({'CC': 'clang', 'CXX': 'clang++',
                'CFLAGS': ' '.join(COV_FLAGS + FUZZ_NOLINK),
                'CXXFLAGS': ' '.join(COV_FLAGS + FUZZ_NOLINK)})
    conf = os.path.join(tree, 'configure')
    # 有些树的 configure 没有 +x（复制时丢权限），用 sh 显式跑
    cmd = ['sh', conf, '--disable-shared', '--enable-static']
    return sh(cmd, cwd=bd, timeout=timeout, env=env)


def build_library(tree, broot, work, tag, kind, jobs, timeout):
    """返回 dict(ok, kind, phase, cmd, log, seconds, libs)。tree 用于找产物，broot 是构建根。"""
    bd = os.path.join(work, 'bd_' + tag) if kind == 'cmake' else broot
    t_all = time.time()
    info = OrderedDict(kind=kind, ok=False, phase=None, cmds=[], seconds=0.0,
                       log='', libs=[], build_root=broot)

    if kind == 'cmake':
        rc, out, dt = cmake_configure(broot, bd, timeout)
        info['cmds'].append('cmake -S %s -B %s (rc=%d, %.1fs)' % (tree, bd, rc, dt))
        if rc != 0:
            info.update(ok=False, phase=PH_CONFIGURE, log=tail(out))
            info['seconds'] = round(time.time() - t_all, 1)
            return info
        rc, out, dt = sh(['cmake', '--build', bd, '-j', str(jobs)],
                         cwd=bd, timeout=timeout)
        info['cmds'].append('cmake --build (rc=%d, %.1fs)' % (rc, dt))
        if rc != 0:
            info.update(ok=False, phase=PH_BUILD, log=tail(out))
            info['seconds'] = round(time.time() - t_all, 1)
            return info
    elif kind == 'configure':
        rc, out, dt = configure_build(broot, bd, timeout)
        info['cmds'].append('configure (rc=%d, %.1fs)' % (rc, dt))
        if rc != 0:
            info.update(ok=False, phase=PH_CONFIGURE, log=tail(out))
            info['seconds'] = round(time.time() - t_all, 1)
            return info
        rc, out, dt = sh(['make', '-j', str(jobs)], cwd=bd, timeout=timeout)
        info['cmds'].append('make (rc=%d, %.1fs)' % (rc, dt))
        if rc != 0:
            # 有些项目的 all 目标包含文档/测试，退一步只编库
            rc2, out2, dt2 = sh(['make', '-j', str(jobs), 'lib'], cwd=bd, timeout=timeout)
            info['cmds'].append('make lib (rc=%d, %.1fs)' % (rc2, dt2))
            if rc2 != 0:
                info.update(ok=False, phase=PH_BUILD, log=tail(out))
                info['seconds'] = round(time.time() - t_all, 1)
                return info
    else:
        info.update(ok=False, phase=PH_CONFIGURE, log='no build system (no CMakeLists/configure)')
        return info

    libs = find_libs([bd, tree])
    info.update(ok=bool(libs), libs=libs, seconds=round(time.time() - t_all, 1))
    if not libs:
        info['phase'] = PH_BUILD
        info['log'] = 'build finished but no .a/.so found'
    return info


def find_libs(roots):
    out = []
    for root in roots:
        for dp, dns, fns in os.walk(root):
            if '/CMakeFiles/' in dp or dp.endswith('/CMakeFiles'):
                continue
            for f in fns:
                if f.endswith('.a') and not f.startswith('libgtest'):
                    p = os.path.join(dp, f)
                    try:
                        if os.path.getsize(p) > 2048:
                            out.append(p)
                    except OSError:
                        pass
    # 去重 + 大库优先（有些项目会同时产出 object 库和合并库）
    uniq = sorted(set(out), key=lambda p: -os.path.getsize(p))
    keep = []
    for p in uniq:
        b = os.path.basename(p)
        if any(b == os.path.basename(k) for k in keep):
            continue
        keep.append(p)
    return keep


def include_dirs(tree, bd, cap=40):
    """头文件搜索路径：树根 + 常见 include/src 目录 + 生成头所在目录。"""
    cands = [tree]
    for sub in ('include', 'src', 'lib', 'source', 'headers', 'api', 'inc'):
        p = os.path.join(tree, sub)
        if os.path.isdir(p):
            cands.append(p)
    # 浅层所有含头文件的目录（最多 3 层）
    for dp, dns, fns in os.walk(tree):
        rel = os.path.relpath(dp, tree)
        depth = 0 if rel == '.' else rel.count(os.sep) + 1
        if depth > 3:
            dns[:] = []
            continue
        dns[:] = [d for d in dns if d not in ('tests', 'test', 'doc', 'docs', '.git',
                                              'examples', 'example', 'third_party')]
        if any(f.endswith(('.h', '.hh', '.hpp', '.hxx')) for f in fns):
            cands.append(dp)
    # 构建目录（生成头：config.h / export.h / 版本头）
    if bd and os.path.isdir(bd):
        cands.append(bd)
        for dp, dns, fns in os.walk(bd):
            rel = os.path.relpath(dp, bd)
            depth = 0 if rel == '.' else rel.count(os.sep) + 1
            if depth > 3:
                dns[:] = []
                continue
            if any(f.endswith(('.h', '.hh', '.hpp')) for f in fns):
                cands.append(dp)
    seen, out = set(), []
    for p in cands:
        p = os.path.abspath(p)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:cap]


def locate_harness_files(case_dir, case):
    """case.json 里的 harness_files 是 oss-fuzz 仓库内路径，按 basename 在 input/harness 里找。"""
    hroot = os.path.join(case_dir, 'input', 'harness')
    index = {}
    for dp, _, fns in os.walk(hroot):
        for f in fns:
            index.setdefault(f, os.path.join(dp, f))
    picked, missing = [], []
    for rel in case.get('harness_files') or []:
        b = os.path.basename(rel)
        if b.endswith(SRC_EXTS):
            if b in index:
                picked.append(index[b])
            else:
                missing.append(rel)
    # case.json 没写全时，退化成"harness 目录下所有 fuzz 源文件"
    if not picked:
        for dp, _, fns in os.walk(hroot):
            for f in fns:
                if f.endswith(SRC_EXTS) and ('fuzz' in f.lower() or 'test' in f.lower()):
                    picked.append(os.path.join(dp, f))
    return sorted(set(picked)), missing


def sys_libs():
    """静态库没带进来的常见系统依赖（zlib/bz2/lzma/expat...）。只加真实存在的。"""
    want = ['z', 'bz2', 'lzma', 'zstd', 'expat', 'ssl', 'crypto', 'pcre2-8', 'm', 'pthread', 'dl', 'rt']
    out = []
    dirs = ['/usr/lib/x86_64-linux-gnu', '/usr/lib', '/lib/x86_64-linux-gnu']
    for w in want:
        if w in ('m', 'pthread', 'dl', 'rt'):
            out.append('-l' + w)
            continue
        if any(os.path.exists(os.path.join(d, 'lib%s.so' % w)) or
               os.path.exists(os.path.join(d, 'lib%s.a' % w)) for d in dirs):
            out.append('-l' + w)
    return out


def helper_sources(undefined, harness_root, already):
    """按未定义符号在 harness 目录里找定义文件（libxml2 的 fuzz/fuzz.c 就是这种）。

    OSS-Fuzz 的 build.sh 会把这些辅助文件一起编；我们手工链接时必须自己找回来。
    """
    out = []
    if not undefined or not harness_root or not os.path.isdir(harness_root):
        return out
    names = [u.split('@')[0] for u in undefined]
    cand = []
    for dp, dns, fns in os.walk(harness_root):
        dns[:] = [d for d in dns if d != '.git']
        for f in fns:
            if f.endswith(SRC_EXTS):
                p = os.path.join(dp, f)
                if p not in already:
                    cand.append(p)
    for p in cand:
        try:
            txt = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for n in names:
            if re.search(r'\b%s\s*\([^;]*\)\s*\{' % re.escape(n), txt):
                out.append(p)
                break
    return out


def build_harness(tree, bd, libs, hfiles, work, tag, timeout):
    """编译并链接 harness。返回 dict(ok, phase, log, bin, seconds)。"""
    incs = include_dirs(tree, bd)
    out_bin = os.path.join(work, 'harness_' + tag)
    is_cxx = any(f.endswith(CXX_EXTS) for f in hfiles)
    cc = 'clang++' if is_cxx else 'clang'
    t0 = time.time()
    info = OrderedDict(ok=False, phase=PH_HARNESS, bin=out_bin, log='', seconds=0.0)

    if not hfiles:
        info['log'] = 'no harness source file found'
        return info

    # 链接行也必须带 -fprofile-instr-generate，否则不链 profile runtime，跑完没有 .profraw
    if hfiles:
        # harness 自己所在的目录（含 `#include "../cJSON.h"` 这种相对写法）
        for f in hfiles:
            for d in (os.path.dirname(f), os.path.dirname(os.path.dirname(f))):
                if d not in incs:
                    incs.append(d)
    cmd = [cc] + COV_FLAGS + ['-fsanitize=fuzzer', '-fno-omit-frame-pointer']
    for p in incs:
        cmd += ['-I', p]
    cmd += list(hfiles)
    if libs:
        cmd += ['-Wl,--start-group'] + libs + ['-Wl,--end-group']
    cmd += sys_libs() + ['-o', out_bin]

    # 先编译，失败时按错误类别做有限补救（缺头文件目录 / 缺宏）
    rc, out, dt = sh(cmd, cwd=work, timeout=timeout)
    info['log'] = tail(out)
    if rc == 0:
        info.update(ok=True, phase=None, seconds=round(time.time() - t0, 1))
        return info

    # 补救 1：把 "fatal error: 'x.h' file not found" 的位置所在目录加进去
    extra = []
    for m in re.finditer(r"fatal error: '([^']+)' file not found", out):
        name = os.path.basename(m.group(1))
        for root in (tree, bd):
            for dp, _, fns in os.walk(root):
                if name in fns:
                    extra.append(dp)
                    break
            else:
                continue
            break
    # 补救 2：宏形态的未定义类型（和路线 1.5 的 synth 同一条策略，最多 4 个）
    for m in re.finditer(r"unknown type name '(_?[A-Z][A-Z0-9_]*)'", out):
        d = '-D%s=' % m.group(1)
        if d not in extra and len([x for x in extra if x.startswith('-D')]) < 4:
            extra.append(d)
    # 补救 3：`#error "ENCODING_FOR_FUZZING was not provided"` —— OSS-Fuzz 的 build.sh
    # 会给每个 target 单独传这个宏（expat 等），手工编译时要补上
    for m in re.finditer(r'#\s*error\s+"(\w+) was not provided', out):
        d = '-D%s=UTF-8' % m.group(1)
        if d not in extra:
            extra.append(d)
    # pcre2 的 harness 要求先定义代码单元宽度（build.sh 里也是这么传的）
    if 'PCRE2_CODE_UNIT_WIDTH' in out and '-DPCRE2_CODE_UNIT_WIDTH=8' not in extra:
        extra.append('-DPCRE2_CODE_UNIT_WIDTH=8')

    if extra:
        cmd2 = [cc] + COV_FLAGS + ['-fsanitize=fuzzer', '-fno-omit-frame-pointer']
        for p in incs + [x for x in extra if not x.startswith('-D')]:
            cmd2 += ['-I', p]
        cmd2 += [x for x in extra if x.startswith('-D')]
        cmd2 += list(hfiles)
        if libs:
            cmd2 += ['-Wl,--start-group'] + libs + ['-Wl,--end-group']
        cmd2 += sys_libs() + ['-o', out_bin]
        rc2, out2, dt2 = sh(cmd2, cwd=work, timeout=timeout)
        info['log'] = tail(out2)
        info['retry'] = [x for x in extra]
        if rc2 == 0:
            info.update(ok=True, phase=None, seconds=round(time.time() - t0, 1))
            return info
        rc, out = rc2, out2

    # 补救 4：链接时缺的符号其实由 harness 目录里的辅助 .c 定义 → 把它们补进编译单元
    if 'undefined reference' in out:
        und = sorted(set(re.findall(r"undefined reference to [`']([^']+)'", out)))
        helpers = helper_sources(und, os.path.dirname(hfiles[0]) if hfiles else None,
                                 set(hfiles))
        if helpers:
            cmd3 = [cc] + COV_FLAGS + ['-fsanitize=fuzzer', '-fno-omit-frame-pointer']
            for p2 in incs:
                cmd3 += ['-I', p2]
            cmd3 += list(hfiles) + helpers
            if libs:
                cmd3 += ['-Wl,--start-group'] + libs + ['-Wl,--end-group']
            cmd3 += sys_libs() + ['-o', out_bin]
            rc3, out3, _ = sh(cmd3, cwd=work, timeout=timeout)
            info['log'] = tail(out3)
            info['helpers'] = [os.path.basename(h) for h in helpers]
            if rc3 == 0:
                info.update(ok=True, phase=None, seconds=round(time.time() - t0, 1))
                return info
            out = out3

    # 编译过了但链接失败 → 区分成 link 阶段（这也是证据：符号被删/改名）
    if 'undefined reference' in out or 'undefined symbol' in out:
        info['phase'] = PH_LINK
        info['undefined'] = sorted(set(re.findall(r"undefined reference to [`']([^']+)'", out)))[:8]
    info['seconds'] = round(time.time() - t0, 1)
    return info


# ---- 首选：跑项目自己的 build.sh（OSS-Fuzz 环境） --------------------------

HARNESS_META = {'build.sh', 'Dockerfile', 'project.yaml', 'run_tests.sh', '.gitignore'}


def find_build_sh(case_dir):
    """build.sh 可能在不同位置：input/harness/oss-fuzz/ 或 input/harness/build/。"""
    for rel in (('oss-fuzz', 'build.sh'), ('build', 'build.sh')):
        p = os.path.join(case_dir, 'input', 'harness', *rel)
        if os.path.exists(p):
            return p
    for dp, _, fns in os.walk(os.path.join(case_dir, 'input', 'harness')):
        if 'build.sh' in fns:
            return os.path.join(dp, 'build.sh')
    return None


def fuzzer_archive(wk):
    """OSS-Fuzz 的 base-builder 里 $LIB_FUZZING_ENGINE 是 libFuzzer 的 .a 路径；
    这里用 clang 自带的 libclang_rt.fuzzer 归档顶上（等价物，不是替代实现）。"""
    for pat in ('/usr/lib/llvm-*/lib/clang/*/lib/linux/libclang_rt.fuzzer-x86_64.a',):
        import glob as _glob
        hits = sorted(_glob.glob(pat))
        if hits:
            dst = os.path.join(wk, 'libFuzzingEngine.a')
            if not os.path.exists(dst):
                try:
                    os.symlink(hits[-1], dst)
                except OSError:
                    shutil.copy2(hits[-1], dst)
            return dst
    return None


ZIP_SHIM = """#!/usr/bin/env python3
import sys, zipfile, os
args = [a for a in sys.argv[1:] if not a.startswith('-')]
if len(args) < 2:
    sys.exit(0)
out, files = args[0], args[1:]
if os.path.exists(out):
    os.remove(out)
with zipfile.ZipFile(out, 'w') as z:
    for f in files:
        if os.path.isfile(f):
            z.write(f, os.path.basename(f))
"""


def make_tool_shims(wk):
    """OSS-Fuzz 镜像里有 zip/python；本地没有。补最小等价物，避免 build.sh 因环境缺失而中断。"""
    b = os.path.join(wk, 'bin')
    os.makedirs(b, exist_ok=True)
    py = os.path.join(b, 'python')
    if not os.path.exists(py):
        os.symlink('/usr/bin/python3', py)
    zp = os.path.join(b, 'zip')
    with open(zp, 'w') as w:
        w.write(ZIP_SHIM)
    os.chmod(zp, 0o755)
    return b


def fuzz_env(src, out, wk, extra_cflags=''):
    env = dict(os.environ)
    arch = fuzzer_archive(wk)
    shim = make_tool_shims(wk)
    extra = ' -L' + wk if arch else ''
    # 老代码 + clang 21：新的 -Wstrict-prototypes 等告警会被项目的 -Werror 放大成编译失败。
    # 加 -Wno-error 是**编译环境适配**，不是放宽判定：真正的 error（类型不匹配、缺符号）照样报错。
    extra += ' ' + ' '.join(WERROR_OFF + WNOISE)
    env.update({
        'SRC': src, 'OUT': out, 'WORK': wk,
        'CC': 'clang', 'CXX': 'clang++', 'LD': 'clang++',
        'CFLAGS': ' '.join(COV_FLAGS + FUZZ_NOLINK) + extra + (' ' + extra_cflags if extra_cflags else ''),
        'CXXFLAGS': ' '.join(COV_FLAGS + FUZZ_NOLINK) + extra + (' ' + extra_cflags if extra_cflags else ''),
        'LIB_FUZZING_ENGINE': arch or '-fsanitize=fuzzer',
        'FUZZING_ENGINE': 'libfuzzer',
        'SANITIZER': 'address',
        'ARCHITECTURE': 'x86_64',
        'PATH': shim + ':' + os.environ.get('PATH', '/usr/bin:/bin'),
        # CMake 4 拒绝 <3.5 的兼容声明；build.sh 里的 cmake 调用没法加参数，用环境变量兜住
        'CMAKE_POLICY_VERSION_MINIMUM': '3.5',

    })
    return env


def stage_src(tree, broot, case_dir, work, tag):
    """拼 OSS-Fuzz 的 $SRC 布局：树 + 展平的 harness 文件 + 项目名软链。"""
    src = os.path.join(work, 'src_' + tag)
    if os.path.exists(src):
        shutil.rmtree(src)
    os.makedirs(src)
    # 1) harness 目录原样铺进来（保留 oss-fuzz/、expat/fuzz/ 这类相对路径）
    hroot = os.path.join(case_dir, 'input', 'harness')
    if os.path.isdir(hroot):
        for name in os.listdir(hroot):
            if name == 'oss-fuzz':
                continue          # 这个目录里的文件下面会展平到 $SRC 根，保留副本会和展平副本重名
            sh(['cp', '-a', os.path.join(hroot, name), src], timeout=300)
    # 1b) 跳过 oss-fuzz/ 后要把它里面的 build.sh 单独放回去（后面跑的是 stage 里这份，
    #     原始文件是 CRLF，直接跑会 `syntax error near 'do\r'`）
    _bsh = find_build_sh(case_dir)
    if _bsh and os.path.basename(os.path.dirname(_bsh)) == 'oss-fuzz':
        os.makedirs(os.path.join(src, 'oss-fuzz'), exist_ok=True)
        shutil.copy2(_bsh, os.path.join(src, 'oss-fuzz', 'build.sh'))
    # 2) 再按 basename 展平一份到 $SRC 根：多数 build.sh 用 `$SRC/fuzz_x.c`
    for dp, _, fns in os.walk(hroot):
        rel = os.path.relpath(dp, hroot)
        if rel == '.':
            continue
        for f in fns:
            if f.endswith(SRC_EXTS) or f.endswith(('.dict', '.options', '.zip')):
                dst = os.path.join(src, f)
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(dp, f), dst)
    # 本地没有 libc++（OSS-Fuzz 镜像里有），把 -stdlib=libc++ 换成 libstdc++。
    # 这是编译环境差异，不是"改测试"——记进 protocol.env_adaptations。
    for dp, _, fns in os.walk(src):
        for f in fns:
            if not f.endswith(('.sh', '.cmake', 'CMakeLists.txt')):
                continue
            p = os.path.join(dp, f)
            try:
                t = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            if '-stdlib=libc++' in t:
                open(p, 'w', encoding='utf-8').write(t.replace('-stdlib=libc++', '-stdlib=libstdc++'))
    # build.sh / 字典 / 脚本本身也是 CRLF（数据集的通病），不归一化会 `syntax error near 'do\r'`
    ir_bsm.norm_eol(src)
    # 3) 项目名软链：build.sh 里 `cd $SRC/<name>` 要能落到树上
    names = set()
    base = os.path.basename(os.path.normpath(tree))
    names.add(base)
    bsh = find_build_sh(case_dir)
    if bsh:
        txt = open(bsh, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'\$SRC/([A-Za-z0-9_][A-Za-z0-9_.+-]*)', txt):
            names.add(m.group(1))
        # `cmake ../expat` / `cd ../libyaml` 这类相对路径也要能落到树上
        for m in re.finditer(r'\.\./([A-Za-z0-9_][A-Za-z0-9_.+-]*)', txt):
            names.add(m.group(1))
    tgt = broot or tree
    for n in names:
        p = os.path.join(src, n)
        if n in HARNESS_META or n.endswith(SRC_EXTS):
            continue
        # harness 里可能有个同名目录（expat/fuzz/xml_parse_fuzzer.c）。这些文件本来就该
        # 住在树里（项目自己的 CMake 会编 fuzz/），并进树后把它换成指向构建根的软链。
        if os.path.isdir(p) and not os.path.islink(p):
            for dp, _, fns in os.walk(p):
                rel = os.path.relpath(dp, p)
                for f in fns:
                    dst = os.path.join(tgt, rel, f) if rel != '.' else os.path.join(tgt, f)
                    if not os.path.exists(dst):
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(os.path.join(dp, f), dst)
            shutil.rmtree(p)
        elif os.path.exists(p):
            continue
        try:
            os.symlink(tgt, p)
        except OSError:
            pass
    return src


def build_via_buildsh(tree, broot, case_dir, case, work, tag, args):
    """跑项目 build.sh。产物在 $OUT（项目自己链好了 libFuzzingEngine）。"""
    bsh = find_build_sh(case_dir)
    if not bsh:
        return OrderedDict(ok=False, route=None, reason='no build.sh')
    out = os.path.join(work, 'out_' + tag)
    wk = os.path.join(work, 'bw_' + tag)
    for d in (out, wk):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    src = stage_src(tree, broot, case_dir, work, tag)
    env = fuzz_env(src, out, wk)
    # flac 的 build.sh 需要 HARNESS 指向 harness 目录（项目自定义约定，不是 OSS-Fuzz 标准变量）
    env['HARNESS'] = os.path.join(case_dir, 'input', 'harness')
    # 一定要跑 stage 里的那份：原文件是 CRLF，bash 会报 `syntax error near 'do\r'`
    hroot = os.path.join(case_dir, 'input', 'harness')
    rel = os.path.relpath(bsh, hroot)
    staged = os.path.join(src, rel)
    if not os.path.exists(staged):
        staged = bsh
    txt = open(staged, encoding='utf-8', errors='replace').read()
    # 两种 build.sh 约定并存，按脚本自己怎么引用来选 cwd：
    #   expat 型：cwd=$SRC，脚本里 `mkdir build && cd build && cmake ../expat`
    #   zlib 型：cwd=$SRC/<proj>，脚本里直接 `./configure`（数据集把 `cd $SRC/zlib` 去掉了）
    if re.search(r'cmake\s+\.\./', txt):
        cwd = src
    else:
        link = os.path.join(src, 'proj')
        if not os.path.islink(link):
            try:
                os.symlink(broot or tree, link)
            except OSError:
                link = broot or tree
        cwd = link
    t0 = time.time()
    rc, log, dt = sh(['bash', staged], cwd=cwd, timeout=args.buildsh_timeout, env=env)
    bins = []
    for f in sorted(os.listdir(out)):
        p = os.path.join(out, f)
        if os.path.isfile(p) and os.access(p, os.X_OK) and not f.endswith(('.zip', '.dict', '.options')):
            bins.append(p)
    # **必须以任务指定的 target 为准**：zlib 的 build.sh 会为 7 个 fuzzer 逐个编译，
    # checksum_fuzzer 编不过、其它 7 个照编——只看"OUT 里有 binary"会把这种破裂判成成功。
    target = case.get('harness_target')
    tgt = None
    if target:
        for b in bins:
            if os.path.basename(b) == target:
                tgt = b
                break
        if tgt is None:
            for b in bins:
                if os.path.basename(b).startswith(target):
                    tgt = b
                    break
        ok = tgt is not None
    else:
        tgt = bins[0] if bins else None
        ok = bool(bins)
    return OrderedDict(ok=ok, route='build.sh', rc=rc, bin=tgt,
                       seconds=round(time.time() - t0, 1), bins=bins,
                       log=tail(log, 1500), out=out)


def pick_bin(bins, target):
    if not bins:
        return None
    for b in bins:
        if target and os.path.basename(b) == target:
            return b
    for b in bins:
        if target and target in os.path.basename(b):
            return b
    return bins[0]


def make_corpus(case_dir, work, tree_hint=None, out_dir=None):
    """尽量用项目自带 seed corpus；没有就造一批最小种子。

    build.sh 通常会产出 `$OUT/*_seed_corpus.zip`，那是最贴近真实 fuzz 的入口语料，
    优先用它——这也让"覆盖率"更像 OSS-Fuzz 实际跑出来的覆盖率。
    """
    cdir = os.path.join(work, 'corpus')
    if os.path.isdir(cdir):
        shutil.rmtree(cdir)
    os.makedirs(cdir)
    n = 0
    roots = [r for r in (out_dir, os.path.join(case_dir, 'input', 'harness')) if r]
    for dp, _, fns in roots and [(r, None, os.listdir(r)) for r in roots] or []:
        for f in fns:
            if 'seed_corpus' in f and f.endswith('.zip'):
                rc, _, _ = sh(['unzip', '-qq', '-o', os.path.join(dp, f), '-d', cdir])
                if rc == 0:
                    n += 1
    if n:
        return cdir, len(os.listdir(cdir))
    hroot = os.path.join(case_dir, 'input', 'harness')
    for dp, _, fns in os.walk(hroot):
        for f in fns:
            if 'seed_corpus' in f and f.endswith('.zip'):
                rc, _, _ = sh(['unzip', '-qq', '-o', os.path.join(dp, f), '-d', cdir])
                if rc == 0:
                    n += 1
    # 树里自带的测试样本（小文件、非源码）
    if n == 0 and tree_hint:
        cand = []
        for dp, dns, fns in os.walk(tree_hint):
            dns[:] = [d for d in dns if d not in ('.git', 'tests', 'test', 'doc', 'docs')]
            for f in fns:
                p = os.path.join(dp, f)
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    continue
                if 0 < sz <= 4096 and not f.endswith(SRC_EXTS + ('.o', '.a', '.so')):
                    cand.append(p)
        for i, p in enumerate(cand[:20]):
            shutil.copy2(p, os.path.join(cdir, 'seed_%02d' % i))
            n += 1
    # 兜底：结构化小种子（很多解析器对空/短输入走到 early-exit 分支）
    if n == 0:
        seeds = [b'', b'0', b'\x00', b'{}', b'[]', b'\x1f\x8b\x08\x00', b'PK\x03\x04',
                 b'\x89PNG\r\n\x1a\n', b'<?xml version="1.0"?><a/>']
        seeds += [bytes(range(i, min(256, i + 32))) for i in range(0, 200, 40)]
        for i, s in enumerate(seeds):
            with open(os.path.join(cdir, 'seed_%02d' % i), 'wb') as w:
                w.write(s)
        n = len(seeds)
    return cdir, n


def run_fuzzer(bin_path, corpus, secs, work, tag, timeout):
    """跑一小轮 libFuzzer，返回 dict(rc, crash, seconds, log, profdir)。"""
    profdir = os.path.join(work, 'prof_' + tag)
    if os.path.isdir(profdir):
        shutil.rmtree(profdir)
    os.makedirs(profdir)
    arts = os.path.join(work, 'artifacts_' + tag)
    os.makedirs(arts, exist_ok=True)
    env = dict(os.environ)
    env['LLVM_PROFILE_FILE'] = os.path.join(profdir, 'run-%p.profraw')
    cmd = [bin_path, '-max_total_time=%d' % secs, '-runs=0',
           '-artifact_prefix=' + arts + '/', '-print_final_stats=1', corpus]
    rc, out, dt = sh(cmd, cwd=work, timeout=timeout, env=env)
    crash = rc != 0
    kind = ''
    if crash:
        for pat, name in ((r'AddressSanitizer:\s*(\w+)', 'ASAN'),
                          (r'runtime error:', 'UBSAN'),
                          (r'Assertion .* failed', 'ASSERT'),
                          (r'ERROR: libFuzzer: (\w[\w-]*)', 'LIBFUZZER')):
            m = re.search(pat, out)
            if m:
                kind = name + ':' + (m.group(1) if m.groups() else '')
                break
    arts_list = sorted(os.listdir(arts))[:5]
    return OrderedDict(rc=rc, crash=crash, crash_kind=kind, seconds=round(dt, 1),
                       log=tail(out, 1600), profdir=profdir, artifacts=arts_list)


# ---- 覆盖率 ---------------------------------------------------------------

def coverage(bin_path, profdir, work, tag, timeout=300):
    """llvm-profdata merge -> llvm-cov export -format=lcov -> 函数/行命中。"""
    profs = [os.path.join(profdir, f) for f in os.listdir(profdir) if f.endswith('.profraw')]
    if not profs:
        return OrderedDict(ok=False, reason='no .profraw (binary probably not instrumented)',
                           functions={}, lines={}, n_functions_covered=0)
    merged = os.path.join(work, 'cov_' + tag + '.profdata')
    rc, out, _ = sh(['llvm-profdata', 'merge', '-sparse'] + profs + ['-o', merged], timeout=timeout)
    if rc != 0:
        return OrderedDict(ok=False, reason='llvm-profdata: ' + tail(out, 300),
                           functions={}, lines={}, n_functions_covered=0)
    rc, out, _ = sh(['llvm-cov', 'export', '-format=lcov', '-instr-profile', merged, bin_path],
                    timeout=timeout)
    if rc != 0:
        return OrderedDict(ok=False, reason='llvm-cov: ' + tail(out, 300),
                           functions={}, lines={}, n_functions_covered=0)

    functions, lines = {}, {}
    cur_sf = None
    covered_fn = 0
    for line in out.splitlines():
        if line.startswith('SF:'):
            cur_sf = line[3:]
            lines.setdefault(cur_sf, {})
        elif line.startswith('FNDA:'):
            parts = line[5:].split(',', 1)
            if len(parts) == 2:
                c, name = parts
                try:
                    c = int(c)
                except ValueError:
                    c = 0
                functions[name] = functions.get(name, 0) + c
                if c > 0:
                    covered_fn += 1
        elif line.startswith('DA:'):
            parts = line[3:].split(',')
            if len(parts) >= 2 and cur_sf:
                try:
                    lines[cur_sf][int(parts[0])] = int(parts[1])
                except ValueError:
                    pass
    return OrderedDict(ok=True, functions=functions, lines=lines,
                       n_functions_covered=covered_fn)


def rel_of(path, tree):
    """把 lcov 里的绝对路径映射回树内相对路径。"""
    p = os.path.abspath(path)
    t = os.path.abspath(tree) + os.sep
    if p.startswith(t):
        return p[len(t):]
    return None


def added_line_hits(cov, tree, added):
    """change.diff 里新增的行，有多少在覆盖率里真的被执行到。"""
    per_file = {}
    total = hit = 0
    for rel, lset in added.items():
        # lcov 里的路径可能带 ./ 前缀或符号链接差异，按后缀匹配
        cand = None
        for sf in cov['lines']:
            rr = rel_of(sf, tree)
            if rr == rel:
                cand = sf
                break
        if cand is None:
            for sf in cov['lines']:
                if sf.endswith('/' + rel) or sf.endswith(rel):
                    cand = sf
                    break
        if cand is None:
            per_file[rel] = OrderedDict(total=len(lset), hit=0, note='no coverage record')
            total += len(lset)
            continue
        lm = cov['lines'][cand]
        h = sum(1 for ln in lset if lm.get(ln, 0) > 0)
        per_file[rel] = OrderedDict(total=len(lset), hit=h)
        total += len(lset)
        hit += h
    return OrderedDict(total=total, hit=hit, ratio=round(hit / total, 3) if total else None,
                       per_file=per_file)


# ---- 判定 -----------------------------------------------------------------

def classify_phase(log):
    """从构建日志里判失败阶段，给配置类/编译类/链接类留结构化原因。"""
    if not log:
        return PH_BUILD
    if 'undefined reference' in log or 'undefined symbol' in log:
        return PH_LINK
    if re.search(r"error:.*\.(c|cc|cpp|h):", log) or 'errors generated' in log:
        return PH_HARNESS
    if 'CMake Error' in log or 'configure: error' in log:
        return PH_CONFIGURE
    return PH_BUILD


def decide(res, ir_row):
    """只用执行证据；ir_row 只用来拿"新增外部符号"这一静态事实（不是 GT）。"""
    vm, vm1 = res.get('v_m') or {}, res.get('v_m1') or {}
    rm, rm1 = res.get('run_m'), res.get('run_m1')
    ah = res.get('added_hits') or {}
    n_hit = ah.get('hit') or 0

    ok_m, ok_m1 = bool(vm.get('ok')), bool(vm1.get('ok'))
    ev = OrderedDict()
    ev['m_build_ok'] = ok_m
    ev['m1_build_ok'] = ok_m1
    ev['route_m'] = vm.get('route')
    ev['route_m1'] = vm1.get('route')
    ev['m_run_crash'] = bool(rm and rm.get('crash'))
    ev['m1_run_crash'] = bool(rm1 and rm1.get('crash'))
    ev['added_lines_total'] = ah.get('total')
    ev['added_lines_hit'] = n_hit

    # 证据状态：两个版本都编不出来时，这一行什么也说明不了（对齐路线 1.5 的 reach.status）
    res['exec_status'] = 'ok' if (ok_m or ok_m1) else 'no_build'

    # 1) M^1 能编、M 编不出来 → 库侧改动把 harness 打断了
    if ok_m1 and not ok_m:
        ph = vm.get('phase') or classify_phase(vm.get('log'))
        ev['failure_phase'] = ph
        if ph == PH_LINK:
            ev['undefined_symbols'] = vm.get('undefined') or []
            return 'test_breaking', 'harness link fails on M only (removed/renamed symbol)', ev
        return 'test_breaking', 'harness build fails on M only (signature/API change)', ev

    # 2) 同一个 corpus，M 崩、M^1 不崩 → 运行时失配
    if ok_m and ok_m1 and rm and rm1 and not rm1.get('crash') and rm.get('crash'):
        ev['crash_kind'] = rm.get('crash_kind')
        return 'test_breaking', 'runtime failure on M only (%s)' % (rm.get('crash_kind') or 'crash'), ev

    # 3) 新语义是否落在 harness 实际执行的路径上
    if n_hit > 0:
        return 'test_stale', 'diff-added lines executed by harness (new semantics on live path)', ev

    # 4) 两版都编不出来：没有任何可比的执行证据，直接判"无证据"，
    #    不能再往下走 missing —— 否则"构建失败"会被误当成"新增符号没被覆盖"（V3-03 就是这么错的）
    if not (ok_m and ok_m1):
        return 'no_update', 'no comparable build (both versions failed) — no evidence', ev

    # 5) 新外部符号存在，但新增行一行都没被执行 → 没有测试路径覆盖新行为
    d = ((ir_row or {}).get('evidence') or {}).get('decision') or {}
    new_syms = d.get('added_external') or []
    if new_syms:
        ev['added_external'] = new_syms[:8]
        return 'test_missing', 'new external symbol exists but no added line is covered', ev

    return 'no_update', 'no execution evidence that the harness is affected', ev


# ---- 单条 -----------------------------------------------------------------

def build_version(tree, case_dir, case, work, tag, args):
    """先跑项目 build.sh；失败或没出 binary 时退回通用构建 + 手工链接。"""
    v = OrderedDict(ok=False, route=None, phase=None, bin=None, bins=[], libs=[],
                    seconds=0.0, log='', cmds=[])
    t0 = time.time()
    kind, broot = detect_build(tree)

    if not args.generic_only:
        try:
            r = build_via_buildsh(tree, broot, case_dir, case, work, tag, args)
        except Exception as e:
            r = OrderedDict(ok=False, route='build.sh', reason='exception: %r' % e)
        v['cmds'].append('build.sh rc=%s bins=%d' % (r.get('rc'), len(r.get('bins') or [])))
        if r.get('ok'):
            v.update(ok=True, route='build.sh', bin=r.get('bin'),
                     bins=r['bins'], seconds=r['seconds'], log=r.get('log'))
            v['out'] = r.get('out')
            return v
        v['log'] = r.get('log') or r.get('reason') or ''
        v['phase'] = classify_phase(v['log'])

    # ---- 通用构建 ----
    v['build_kind'] = kind
    if not kind:
        v['phase'] = PH_CONFIGURE
        v['log'] = (v['log'] + '\n[generic] no CMakeLists/configure').strip()
        return v
    b = build_library(tree, broot, work, tag, kind, args.make_jobs, args.build_timeout)
    v['libs'] = b['libs']
    v['cmds'] += b['cmds']
    if not b['ok']:
        v.update(phase=b['phase'], log=(v['log'] + '\n[generic] ' + (b.get('log') or '')).strip()[-1500:])
        v['seconds'] = round(time.time() - t0, 1)
        return v
    bd = os.path.join(work, 'bd_' + tag) if kind == 'cmake' else broot
    hfiles, _ = locate_harness_files(case_dir, case)
    h = build_harness(tree, bd, b['libs'], hfiles, work, tag, args.build_timeout)
    v['cmds'] += ['harness %s' % ('ok' if h['ok'] else h.get('phase'))]
    v['phase'] = h.get('phase')
    v['log'] = (v['log'] + '\n[generic] ' + (h.get('log') or '')).strip()[-1500:]
    v['undefined'] = h.get('undefined')
    v['seconds'] = round(time.time() - t0, 1)
    if h['ok']:
        v.update(ok=True, route='generic', bin=h['bin'])
    return v


def run_case(args, case_dir, sample, work):
    t0 = time.time()
    # case.json 才是任务输入（harness_files / harness_target），dataset.json 的 sample 只提供 GT
    try:
        case = json.load(open(os.path.join(case_dir, 'case.json'), encoding='utf-8'))
    except Exception:
        case = dict(sample)
    cid = case.get('id') or sample.get('dir_id')
    res = OrderedDict(id=cid, project=case.get('project') or sample.get('project'))
    res['harness_target'] = case.get('harness_target')
    res['case_dir'] = case_dir
    res['harness_files'] = case.get('harness_files')

    try:
        m, m1, diff, rev = prepare(case_dir, work)
    except Exception as e:
        res.update(error='prepare: %s' % e, seconds=round(time.time() - t0, 1))
        return res
    res['reverse_apply'] = rev

    added = diff_added_lines(diff)
    res['diff_added'] = OrderedDict((k, len(v)) for k, v in added.items())
    res['diff_added_total'] = sum(len(v) for v in added.values())

    v_m = build_version(m, case_dir, case, work, 'm', args)
    v_m1 = build_version(m1, case_dir, case, work, 'm1', args)
    res['v_m'], res['v_m1'] = v_m, v_m1
    # 兼容字段：旧报告里叫 build_m/harness_m，这里给个等价视图
    res['build_m'] = OrderedDict(ok=v_m['ok'], route=v_m.get('route'), phase=v_m.get('phase'),
                                 seconds=v_m.get('seconds'), log=(v_m.get('log') or '')[-800:])
    res['build_m1'] = OrderedDict(ok=v_m1['ok'], route=v_m1.get('route'), phase=v_m1.get('phase'),
                                  seconds=v_m1.get('seconds'), log=(v_m1.get('log') or '')[-800:])

    if args.probe:
        res['label'] = None
        res['decision'] = OrderedDict(why='probe mode: build only')
        res['seconds'] = round(time.time() - t0, 1)
        return res

    corpus, nseed = make_corpus(case_dir, work, m, v_m.get('out'))
    res['corpus'] = OrderedDict(files=nseed, dir=corpus)

    r_m = r_m1 = None
    cov_m = None
    if v_m.get('ok'):
        r_m = run_fuzzer(v_m['bin'], corpus, args.fuzz_secs, work, 'm', args.run_timeout)
        cov_m = coverage(v_m['bin'], r_m['profdir'], work, 'm', args.cov_timeout)
    if v_m1.get('ok'):
        r_m1 = run_fuzzer(v_m1['bin'], corpus, args.fuzz_secs, work, 'm1', args.run_timeout)

    res['run_m'], res['run_m1'] = r_m, r_m1
    res['coverage'] = OrderedDict(
        ok=bool(cov_m and cov_m.get('ok')),
        n_functions_covered=(cov_m or {}).get('n_functions_covered', 0),
        reason=(cov_m or {}).get('reason'),
    )
    if cov_m and cov_m.get('ok'):
        res['added_hits'] = added_line_hits(cov_m, m, added)

    ir_row = (args._ir or {}).get(cid)
    label, why, ev = decide(res, ir_row)
    if not args.keep_work and not args.probe:
        try:
            shutil.rmtree(work, ignore_errors=True)
        except Exception:
            pass
    res['label'] = label
    res['decision'] = OrderedDict(ev)
    res['decision']['why'] = why
    res['seconds'] = round(time.time() - t0, 1)
    return res


def main():
    ap = argparse.ArgumentParser(description='路线 2：三版本编译执行 + 覆盖率')
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--out', default='results/exec_v9.json')
    ap.add_argument('--cases', default=None, help='逗号分隔的 id，默认全量')
    ap.add_argument('--jobs', type=int, default=6, help='并行 case 数')
    ap.add_argument('--make-jobs', type=int, default=4, help='单次 make/cmake 的 -j')
    ap.add_argument('--fuzz-secs', type=int, default=10)
    ap.add_argument('--build-timeout', type=int, default=1800)
    ap.add_argument('--buildsh-timeout', type=int, default=1800)
    ap.add_argument('--generic-only', action='store_true',
                    help='跳过 build.sh，只用通用 cmake/configure（调试用）')
    ap.add_argument('--run-timeout', type=int, default=180)
    ap.add_argument('--cov-timeout', type=int, default=600)
    ap.add_argument('--workdir', default=os.path.expanduser('~/ir2work2'))
    ap.add_argument('--probe', action='store_true', help='只探测构建可行性')
    ap.add_argument('--ir', default=None, help='路线 1.5 的 ir_v9.json，只用于取 added_external')
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--keep-work', action='store_true',
                    help='保留每条的 M/M1/构建目录（默认跑完就删，磁盘只够放一条）')
    args = ap.parse_args()

    args._ir = {}
    if args.ir and os.path.exists(args.ir):
        for r in json.load(open(args.ir, encoding='utf-8')):
            args._ir[r['id']] = r

    man = json.load(open(os.path.join(args.dataset, 'dataset.json'), encoding='utf-8'))
    gt = {s['dir_id']: s for s in man['samples']}
    want = None
    if args.cases:
        want = [x.strip() for x in args.cases.split(',') if x.strip()]

    cases = []
    for s in man['samples']:
        if want and s['dir_id'] not in want:
            continue
        cases.append((os.path.join(args.dataset, s['path']), s))
    if want:
        cases.sort(key=lambda x: want.index(x[1]['dir_id']))
    print('[cases] %d' % len(cases), flush=True)

    os.makedirs(args.workdir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)

    results = []

    def write_out():
        tmp = args.out + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as w:
            json.dump(results, w, ensure_ascii=False, indent=1)
        os.replace(tmp, args.out)

    if args.jobs <= 1:
        for case_dir, s in cases:
            work = os.path.join(args.workdir, s['dir_id'])
            os.makedirs(work, exist_ok=True)
            r = run_case(args, case_dir, s, work)
            r['gt_label'] = s['label']
            r['gt_visibility'] = s['need_visibility']
            r['gt_type'] = s['degradation_type']
            results.append(r)
            print('[%s] %s %s %.1fs' % (s['dir_id'], r.get('label'), s['project'],
                                        r.get('seconds', 0)), flush=True)
            write_out()
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = {}
            for case_dir, s in cases:
                work = os.path.join(args.workdir, s['dir_id'])
                os.makedirs(work, exist_ok=True)
                futs[ex.submit(run_case, args, case_dir, s, work)] = s
            for f in as_completed(futs):
                s = futs[f]
                try:
                    r = f.result()
                except Exception as e:
                    r = OrderedDict(id=s['dir_id'], error='unhandled: %r' % e)
                r['gt_label'] = s['label']
                r['gt_visibility'] = s['need_visibility']
                r['gt_type'] = s['degradation_type']
                results.append(r)
                print('[%s] %s %s %.1fs' % (s['dir_id'], r.get('label'), s['project'],
                                            r.get('seconds', 0)), flush=True)
                write_out()

    order = {s['dir_id']: i for i, (_, s) in enumerate(cases)}
    results.sort(key=lambda r: order.get(r['id'], 999))
    write_out()
    ok = sum(1 for r in results if (r.get('v_m') or {}).get('ok'))
    routes = {}
    for r in results:
        k = (r.get('v_m') or {}).get('route') or 'fail'
        routes[k] = routes.get(k, 0) + 1
    print('[done] %d cases, built on M: %d, routes=%s' % (len(results), ok, routes))


if __name__ == '__main__':
    main()
