#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ir_bsm.py —— 路线 1.5：把纯 diff 正则换成 clang AST 统一 IR，判定 B/S/M + 弃权

和路线 1（classify_bsm_c.py）的区别
------------------------------------
路线 1 在 change.diff 的**文本行**上跑正则，因此：
  - 只看得到"列 0 的函数名行"，多行参数（V3-06）、宏修饰返回类型（V3-43）都漏；
  - 宏名会混进符号表（zlib 的 `OF`）；
  - 无法知道 harness 到底引用了哪个符号，于是 24 条阴性全判"需要更新"。

路线 1.5 把四个对象投影到同一套 clang AST IR，再做集合差：
    M^1（库·改前，由 change.diff 反推）   —— 符号表 + 函数体指纹
    M  （库·改后，input/source）          —— 同上
    H  （旧 harness，input/harness）      —— 调用图，根 = LLVMFuzzerTestOneInput

IR 分四层，本轮实现前三层的静态部分：
  1. 符号表层：FunctionDecl 的 name / storageClass / desugared 返回类型 / 参数类型；
     同时用 `-detailed-preprocessing-record` 登记 MacroDefinitionRecord，
     宏名单独成表、**不进**函数符号表（`OF`、`XMLPARSEAPI` 因此不会再被当成函数）。
  2. 调用图层：从 LLVMFuzzerTestOneInput 出发 BFS。边的来源是 DeclRefExpr
     （不止 CallExpr）——这样"按名注册回调"也能连上，正是阴性误报的主因。
  3. 行为层：对可达函数做 body 级结构指纹（语句种类、运算符、非字符串字面量、被调名），
     给 stale 一个正向证据；只改字符串常量（错误文案）不算行为变化。
  4. 执行/覆盖层：本轮不做，只留 `COVERAGE_LAYER` 占位，供路线 2 接。

判定规则（优先级 breaking > missing > stale > no_update）
    breaking  : 可达符号的签名/链接性变化，或可达符号被删除
    missing   : 新增外部（非 static）符号，且不在可达集内（新行为无覆盖）
    stale     : 可达符号签名没变、但 body 指纹变了
    no_update : 以上都不成立 —— 库侧 delta 与 harness 可达集无交集，判定"不需要更新"

注意：`no_update` 是本轮**新增**的第四个标签，对应 §7 第 6 条"无弃权出口"。

工程约束
--------
- 只在 WSL/Linux 里跑（需要 clang）。Windows 侧用 `wsl -e python3 ...` 调。
- 不修改 `Baseline/TEBench/`；每个 case 的 M/M1 副本落在 `--workdir`，跑完即删。
- 编译 flags：优先从 `input/harness/build/build.sh` 抽 `-I`/`-D`，其余用 include 目录启发式；
  缺生成头（config.h / expat_config.h 等）时自动补空 stub 并记录，AST 不完整的文件单独标记。

用法
----
    python3 ir_bsm.py --dataset <Dataset-v9/dataset> --out results/ir_v9.json
    python3 ir_bsm.py --dataset <ds> --cases V3-06,V3-43 --keep-work --verbose
"""

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, OrderedDict, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify_bsm_c  # 只复用它的 is_test_side（路线 1 修过的路径判据）

C_EXTS = {'.c', '.h', '.cc', '.cpp', '.cxx', '.hh', '.hpp', '.hxx'}
CU_EXTS = {'.c', '.cc', '.cpp', '.cxx'}          # 编译单元

LABEL_BREAKING = 'test_breaking'
LABEL_STALE = 'test_stale'
LABEL_MISSING = 'test_missing'
LABEL_NO_UPDATE = 'no_update'

AST_TIMEOUT = 300
MAX_DUMP_BYTES = 400 * 1024 * 1024

# 每个项目需要的额外 -D：都是"生成头缺失 / 配置宏必须定义"的补丁，
# 不是给分类器开后门（它们只影响预处理分支，不影响判定规则）。
PROJECT_DEFINES = {
    'expat': ['-DXML_GE=1', '-DXML_DTD=1', '-DXML_CONTEXT_BYTES=1024', '-DHAVE_MEMMOVE=1',
              '-DHAVE_GETRANDOM=1', '-DHAVE_SYSCALL_GETRANDOM=1'],
    'mbedtls': ['-DMBEDTLS_CONFIG_FILE="mbedtls/config.h"'],
    'zstd': ['-DZSTD_MULTITHREAD=1', '-DXXH_NAMESPACE=ZSTD_'],
    'nghttp2': ['-DHAVE_CONFIG_H=0'],
    'pcre2': ['-DPCRE2_CODE_UNIT_WIDTH=8'],
    'libxml2': ['-DHAVE_CONFIG_H=0'],
}


# ── 通用工具 ────────────────────────────────────────────────────────────────────
def sh(cmd, cwd=None, timeout=AST_TIMEOUT):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, errors='replace')


def sha1(s):
    return hashlib.sha1(s.encode('utf-8', 'replace')).hexdigest()[:16]


def walk(node):
    """clang JSON 是树，这里做先序遍历（不递归太深时性能可接受）。"""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        inner = n.get('inner')
        if inner:
            stack.extend(reversed(inner))


def norm_eol(root):
    """把文本文件的 CRLF 归一成 LF —— 数据集里的工作树是 CRLF，diff 是 LF。"""
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                b = open(p, 'rb').read()
            except OSError:
                continue
            if b'\0' in b or len(b) > 4_000_000:
                continue
            if b'\r' in b:
                open(p, 'wb').write(b.replace(b'\r\n', b'\n'))


def _strip_crlf(path):
    try:
        b = open(path, 'rb').read()
    except OSError:
        return
    if b'\0' in b or b'\r' not in b:
        return
    open(path, 'wb').write(b.replace(b'\r\n', b'\n'))


def _link_or_copy(src, dst):
    """M1 农场用硬链接；跨设备（数据集在 /mnt/c、workdir 在 tmpfs）时退化成实体复制。"""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def split_patch(text):
    """把 change.diff 切成 per-file 的文本 hunk，丢掉二进制段（pdf 之类没法反向应用）。"""
    chunks, cur = [], None
    for line in text.splitlines(keepends=True):
        if line.startswith('diff --git '):
            if cur:
                chunks.append(''.join(cur))
            cur = [line]
        elif cur is not None:
            cur.append(line)
    if cur:
        chunks.append(''.join(cur))

    keep = []
    for c in chunks:
        if 'GIT binary patch' in c or c.startswith('Binary files'):
            continue
        if '\n--- a/' not in c or '\n+++ b/' not in c:
            continue
        m = re.match(r'diff --git a/(\S+) b/', c)
        if not m:
            continue
        keep.append((m.group(1), c))
    return keep


def reverse_apply(m1_root, patch_path, workdir, allow_patch=True):
    """逐文件反向应用，返回 (ok_files, failed_files)。一个文件失败不影响其它文件。

    M1 是 M 的硬链接副本时禁用 GNU patch：patch 可能原地改写，会把 M 一起改掉。
    """
    ok, failed = [], []
    with open(patch_path, encoding='utf-8', errors='replace') as fh:
        for path, chunk in split_patch(fh.read()):
            single = os.path.join(workdir, '.one.patch')
            with open(single, 'w', encoding='utf-8') as w:
                w.write(chunk)
            r = sh(['git', 'apply', '-R', '--ignore-whitespace', single], cwd=m1_root)
            if r.returncode == 0:
                ok.append(path)
            elif allow_patch:
                # 退一步：GNU patch，能容忍更多上下文抖动
                r2 = sh(['patch', '-p1', '-R', '--batch', '--forward', '-i', single], cwd=m1_root)
                (ok if r2.returncode == 0 else failed).append(path)
            else:
                failed.append(path)
    return ok, failed


# ── AST 提取 ────────────────────────────────────────────────────────────────────
def make_flags(case, tree, harness_root, build_sh):
    """收集 include / define。返回 (flags, notes)。"""
    inc, defines, notes = [], [], []
    seen = set()

    def add(d):
        """加入目录本身以及它到树根的所有祖先：`#include "mbedtls/config.h"`
        需要的是 -I <tree>/include，只加 include/mbedtls 是不够的。"""
        d = os.path.normpath(d)
        if not os.path.isdir(d):
            return
        t = os.path.normpath(tree)
        chain, cur = [d], d
        while cur != t:
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            chain.append(parent)
            cur = parent
        for x in reversed(chain):
            if x not in seen:
                seen.add(x)
                inc.append(x)

    add(tree)
    # 启发式：深度 3 内所有含头文件的目录（跳过测试/文档）
    for dp, dns, fs in os.walk(tree):
        rel = os.path.relpath(dp, tree)
        depth = 0 if rel == '.' else rel.count(os.sep) + 1
        if depth > 3:
            dns[:] = []
            continue
        dns[:] = [d for d in dns if not d.startswith('.') and
                  os.path.basename(d).lower() not in ('test', 'tests', 'doc', 'docs', 'html')]
        if any(f.lower().endswith(('.h', '.hpp', '.hh')) for f in fs):
            add(dp)

    # build.sh 里的真实 flags（相对路径按 build 目录 / harness 根 / 树根 依次解析）
    if build_sh and os.path.exists(build_sh):
        txt = open(build_sh, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'(?<![\w-])-I\s*("?)([^"\s]+)\1', txt):
            raw = m.group(2)
            if '$' in raw:
                continue
            for base in (os.path.dirname(build_sh), harness_root, tree):
                cand = os.path.normpath(os.path.join(base, raw))
                if os.path.isdir(cand):
                    add(cand)
                    break
        for m in re.finditer(r'(?<![\w-])-D\s*([A-Za-z_]\w*(?:=[^\s"\']*)?)', txt):
            d = m.group(1)
            if '$' in d:
                continue
            name, _, val = d.partition('=')
            # build.sh 里还混着 CMake 变量（-DCMAKE_C_FLAGS=、-DENABLE_TESTING=Off），不是给编译器的
            if name.startswith('CMAKE') or name.endswith('_FLAGS') or val in ('Off', 'OFF', 'ON', 'True'):
                continue
            defines.append('-D' + d)
        notes.append('build.sh flags: -I×%d -D×%d' % (len(inc), len(defines)))

    for d in PROJECT_DEFINES.get(case.get('project', ''), []):
        defines.append(d)
        notes.append('project define: ' + d)

    if len(inc) > 40:            # 只保留离树根最近的一批
        inc = sorted(inc, key=lambda d: d.count(os.sep))[:40]
    return ['-I' + p for p in inc] + defines, notes


_TEMPLATES = {}


def template_index(tree):
    """生成头模板索引：cbor/configuration.h 缺了就找 configuration.h.in。"""
    key = os.path.normpath(tree)
    if key in _TEMPLATES:
        return _TEMPLATES[key]
    idx = {}
    for dp, dns, fs in os.walk(tree):
        dns[:] = [d for d in dns if not d.startswith('.')]
        for f in fs:
            if f.endswith(('.h.in', '.h.cmake.in', '.h.in.cmake')):
                base = f.split('.h.')[0] + '.h'
                idx.setdefault(base, os.path.join(dp, f))
    _TEMPLATES[key] = idx
    return idx


# 这些宏是"语法修饰符"（restrict / inline / 可见性），填 0 会变成语法错误，只能填空
_EMPTY_HINTS = ('SPECIFIER', 'ATTRIBUTE', 'RESTRICT', 'INLINE', 'EXPORT', 'DECL',
                'NODISCARD', 'DEPRECATED', 'VISIBILITY', 'FORMAT', 'API')


def render_template(tree, name):
    """用 CMake/autoconf 模板渲染一个最小可用的配置头。

    只求"能过预处理、分支走向合理"，不追求和真实构建一致：
    版本号/尺寸类填 0，语法修饰类填空，feature 开关按"关闭"处理。
    """
    path = template_index(tree).get(os.path.basename(name))
    if not path:
        return None
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return None

    def var(m):
        v = m.group(1) or m.group(2)
        if v is None:
            return ''
        return '' if any(h in v.upper() for h in _EMPTY_HINTS) else '0'

    txt = re.sub(r'\$\{([A-Za-z_]\w*)\}|@([A-Za-z_]\w*)@', var, txt)
    txt = re.sub(r'(?m)^\s*#cmakedefine01\s+(\w+)', r'#define \1 0', txt)
    txt = re.sub(r'(?m)^\s*#cmakedefine\s+(\w+).*$', r'/* #undef \1 */', txt)
    txt = re.sub(r'(?m)^\s*#undef\s+(\w+)', r'/* #undef \1 */', txt)
    return '/* rendered from %s by ir_bsm.py */\n%s\n' % (os.path.basename(path), txt)


def dump_ast(path, flags, stub_dir, cxx=False, verbose=False, tree=None, synth=None):
    """跑 clang -ast-dump=json；缺生成头时自动补空 stub（最多 4 轮）。"""
    cc = 'clang++' if cxx else 'clang'
    stubs = []
    base = [cc, '-Xclang', '-ast-dump=json', '-fsyntax-only', '-ferror-limit=0', '-w',
            '-Xclang', '-detailed-preprocessing-record']
    if cxx:
        base += ['-x', 'c++', '-std=gnu++17']
    else:
        base += ['-std=gnu11']

    synth = synth if synth is not None else []
    last = None
    for _ in range(6):
        # 单文件 90 s 上限：binutils/gas 那种大 TU 失败重试 6 次会很贵
        last = sh(base + flags + synth + ['-I', stub_dir, path], timeout=90)
        if len(last.stdout) > MAX_DUMP_BYTES:
            return None, 'ast-dump too large (%d MB)' % (len(last.stdout) // 1048576), stubs
        m = re.search(r"fatal error: '([^']+)' file not found", last.stderr)
        if m:
            name = m.group(1)
            tgt = os.path.join(stub_dir, name)
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            if not os.path.exists(tgt):
                body = render_template(tree, name) if tree else None
                open(tgt, 'w').write(body or '/* stub generated by ir_bsm.py: %s */\n' % name)
                stubs.append(name + ('' if body else ' (empty stub)'))
                if verbose:
                    print('    [stub]', name, file=sys.stderr)
                continue
        # 空 stub 会导致 "unknown type name" / "undeclared identifier"：
        # 这类符号通常是可见性宏，补一个空的 -D 定义即可让 AST 继续往下走
        # 只对"宏形态"的名字兜底（CBOR_EXPORT / _CBOR_NODISCARD）；cbor_item_t 这类真类型名
        # 说明头文件没 include 进来，强行定义只会把 AST 改坏
        m = re.search(r"unknown type name '(_?[A-Z][A-Z0-9_]*)'", last.stderr)
        if m and len(synth) < 6 and ('-D%s=' % m.group(1)) not in synth:
            synth.append('-D%s=' % m.group(1))
            if verbose:
                print('    [synth] -D%s=' % m.group(1), file=sys.stderr)
            continue
        m = re.search(r"use of undeclared identifier '([A-Z_][A-Z0-9_]*)'", last.stderr)
        if m and len(synth) < 6 and ('-D%s=0' % m.group(1)) not in synth:
            synth.append('-D%s=0' % m.group(1))
            if verbose:
                print('    [synth] -D%s=0' % m.group(1), file=sys.stderr)
            continue
        break

    if not last.stdout.strip():
        return None, (last.stderr.strip().splitlines() or ['empty ast'])[0][:200], stubs
    try:
        data = json.loads(last.stdout)
    except Exception:
        return None, 'ast json parse failed (truncated?)', stubs

    err = None
    if last.returncode != 0:
        first = next((l for l in last.stderr.splitlines() if ' error:' in l), '')
        err = ('partial: ' + first.strip()[:160]) if first else 'rc=%d' % last.returncode
    return data, err, stubs


def desugar(t, tmap, depth=0):
    """把类型串里的 typedef 名就地展开（clang JSON 只在部分节点给 desugaredQualType）。"""
    if not t or depth > 3:
        return t
    out = []
    for tok in re.findall(r'[A-Za-z_]\w*|[^A-Za-z_]+', t):
        sub = tmap.get(tok)
        # 自引用（typedef struct X X）与无变化的情况直接保留原名，避免无限展开
        if sub and tok not in ('void',) and not re.search(r'\b%s\b' % re.escape(tok), sub):
            out.append(desugar(sub, tmap, depth + 1))
        else:
            out.append(tok)
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


def norm_type(t):
    t = re.sub(r'\s+', ' ', t or '').strip()
    t = t.replace(' *', '*').replace('* ', '*')
    t = re.sub(r'\b(const|volatile|restrict)\b', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def callee_name(call):
    """CallExpr -> 被调函数名（直接调用与函数指针都尽量取）。"""
    for c in call.get('inner') or []:
        if c.get('kind') == 'ImplicitCastExpr':
            for g in c.get('inner') or []:
                if g.get('kind') == 'DeclRefExpr':
                    d = g.get('referencedDecl') or {}
                    if d.get('kind') in ('FunctionDecl', 'FunctionTemplateDecl'):
                        return d.get('name')
        if c.get('kind') == 'DeclRefExpr':
            d = c.get('referencedDecl') or {}
            if d.get('kind') in ('FunctionDecl', 'FunctionTemplateDecl'):
                return d.get('name')
    return None


def body_fingerprint(fn_node):
    """两个指纹：struct 忽略字符串常量内容（错误文案不算行为变化），text 全量。"""
    kinds, ops, calls, lits, slits = Counter(), Counter(), set(), [], []
    refs = set()

    for n in walk(fn_node):
        if not isinstance(n, dict):
            continue
        k = n.get('kind') or 'unknown'
        if k in ('FunctionDecl', 'ParmVarDecl'):
            continue
        if k == 'StringLiteral':
            # 字符串常量（错误文案）完全不进结构指纹：改文案、拆长字符串都不算行为变化
            slits.append(str(n.get('value') or ''))
            for x in n.get('inner') or []:
                if isinstance(x, dict) and x.get('kind') == 'StringLiteral':
                    slits.append(str(x.get('value') or ''))
            continue
        kinds[k] += 1
        if k in ('BinaryOperator', 'UnaryOperator', 'CompoundAssignOperator'):
            ops[str(n.get('opcode') or '')] += 1
        elif k == 'CallExpr':
            c = callee_name(n)
            if c:
                calls.add(c)
        elif k in ('IntegerLiteral', 'FloatingLiteral', 'CharacterLiteral'):
            lits.append(str(n.get('value') if n.get('value') is not None else ''))
        elif k == 'DeclRefExpr':
            d = n.get('referencedDecl') or {}
            if d.get('kind') == 'FunctionDecl' and d.get('name'):
                refs.add(d['name'])

    s_tokens = (['K:%s=%d' % (k, v) for k, v in sorted(kinds.items())] +
                ['O:%s=%d' % (k, v) for k, v in sorted(ops.items())] +
                ['C:' + c for c in sorted(calls)] +
                ['L:' + x for x in sorted(lits)])
    t_tokens = s_tokens + ['T:' + x for x in slits]
    return {
        'hash': sha1('\n'.join(s_tokens)),
        'text_hash': sha1('\n'.join(t_tokens)),
        'calls': sorted(calls),
        'refs': sorted(refs),
        'n_nodes': sum(kinds.values()),
        'n_strings': len(slits),
    }


def collect(data, roots, harness_root=None, default_file=None):
    """从一个 TU 的 AST 里抽函数符号表 + 宏名表 + typedef 表。

    roots 可以是单个目录，也可以是目录元组：harness 的 TU 会同时看到 H 和 M 里的符号
    （前者是 harness 自己，后者是它 include 的库头），需要分别判定归属。
    """
    roots = (roots,) if isinstance(roots, str) else tuple(roots)
    tmap, macros, funcs = {}, set(), {}
    hroot = os.path.normpath(harness_root) if harness_root else None

    def owner(path):
        p = os.path.normpath(path)
        if '/usr/' in p:
            return None
        for r in roots:
            r = os.path.normpath(r)
            if p.startswith(r + os.sep):
                return r
        return None

    def visit(node, cur_file):
        if not isinstance(node, dict):
            return
        kind = node.get('kind')
        loc = node.get('loc') or {}
        # clang 的 JSON 会省略"和上一个节点同一个文件"的 file 字段，必须沿树继承；
        # 顶层节点没有 file 时用 TU 的输入路径兜底，否则主文件里的函数会被整片丢掉。
        f = loc.get('file') or cur_file or default_file
        if kind == 'MacroDefinitionRecord':
            if node.get('name'):
                macros.add(node['name'])
        elif kind == 'TypedefDecl' and node.get('name'):
            t = (node.get('type') or {}).get('qualType')
            if t:
                tmap[node['name']] = t

        if kind == 'FunctionDecl' and node.get('name') and f:
            root = owner(f)
            if root:
                name = node['name']
                t = (node.get('type') or {})
                has_body = any(c.get('kind') == 'CompoundStmt' for c in node.get('inner') or [])
                params = [(p.get('type') or {}).get('qualType', '')
                          for p in node.get('inner') or [] if p.get('kind') == 'ParmVarDecl']
                rec = {
                    'name': name,
                    'file': os.path.relpath(f, root).replace('\\', '/'),
                    'in_harness': bool(hroot and root == hroot),
                    'static': node.get('storageClass') == 'static' or bool(node.get('inline')),
                    'is_def': has_body,
                    'ret': (t.get('desugaredQualType') or t.get('qualType') or ''),
                    'params': params,
                    'variadic': bool(node.get('variadic')),
                    'body': body_fingerprint(node) if has_body else None,
                }
                old = funcs.get(name)
                if old is None or (rec['is_def'] and not old['is_def']):
                    funcs[name] = rec
                elif rec['is_def'] and old['is_def'] and rec['body']['hash'] != old['body']['hash']:
                    # 同名 static 函数在不同 TU 里各有一份：保留节点更多的那个
                    if rec['body']['n_nodes'] > old['body']['n_nodes']:
                        funcs[name] = rec

        for c in node.get('inner') or []:
            visit(c, f)

    visit(data, None)
    # 类型展开：把 typedef 名换成底层类型，避免 "uLong" vs "unsigned long" 这类假差异
    for f in funcs.values():
        f['ret_n'] = norm_type(desugar(f['ret'], tmap))
        f['params_n'] = [norm_type(desugar(p, tmap)) for p in f['params']]
    return funcs, macros, tmap


def is_in_tree(path, tree):
    p = os.path.normpath(path)
    t = os.path.normpath(tree)
    return p.startswith(t + os.sep) and '/usr/' not in p


def merge_into(dst, src):
    """跨 TU 合并符号表：定义优先于声明；同名多定义时保留节点更多的那个。"""
    for k, v in src.items():
        old = dst.get(k)
        if old is None:
            dst[k] = v
        elif v.get('is_def') and not old.get('is_def'):
            dst[k] = v
        elif v.get('is_def') and old.get('is_def') and v.get('body') and old.get('body'):
            if v['body']['hash'] != old['body']['hash'] and \
                    v['body']['n_nodes'] > old['body']['n_nodes']:
                dst[k] = v
    return dst


def is_reserved(name):
    """C 保留标识符（`__x`、`_X`）不可能是库的公开 API；它们通常是 libc 宏展开出来的。"""
    return name.startswith('__') or (len(name) > 1 and name[0] == '_' and name[1].isupper())


def sig_of(f):
    return (f['ret_n'], tuple(f['params_n']), f.get('variadic'), f['static'])


# ── 单个 case 的处理 ────────────────────────────────────────────────────────────
def prep_case(case_dir, work, hardlink=True):
    """准备 M 与 M1 两棵树，并把 change.diff 反向应用到 M1。

    M 直接读数据集里的 `input/source`（只读，不拷贝）——binutils 那种 400 MB / 3.7 万文件的树，
    实体拷贝一次就要十几分钟，而 AST 只需要读。
    M1 用**硬链接农场**：每个文件是 M 里同名文件的另一个硬链接（同一 inode，几乎零成本）；
    只有 diff 改到的文件先 unlink 再实体复制（改副本不影响 M），所以
    `git apply -R`（写临时文件再 rename，不原地改）在 M1 上是安全的。

    为什么不用软链：clang 会把软链解析成真实路径，M1/include/*.h 全被报成 M 的路径，
    `collect(roots=(m1,))` 的归属判定直接落空，M1 侧成片丢声明 → 冒出一堆假"新增符号"
    （libyaml 的 `yaml_get_version_string`、libxml2 的 `xmlBufCreate` 就是这么来的）。
    硬链接报的仍是 M1 自己的路径，没有这个问题。
    """
    inp = os.path.join(case_dir, 'input')
    src = os.path.join(inp, 'source')
    m = os.path.normpath(src)
    m1 = os.path.join(work, 'M1')

    if not hardlink:
        m = os.path.join(work, 'M')
        shutil.copytree(src, m, symlinks=True)
        norm_eol(m)
        shutil.copytree(src, m1, symlinks=True)
        norm_eol(m1)
        ok, failed = reverse_apply(m1, os.path.join(inp, 'change.diff'), work)
        return m, m1, ok, failed

    if os.path.exists(m1):
        shutil.rmtree(m1)
    shutil.copytree(m, m1, symlinks=True, copy_function=_link_or_copy)

    # diff 涉及的文件先断开硬链接、再实体复制，并归一化行尾（patch 是 LF，数据集工作树是 CRLF）
    touched = [p for p, _ in split_patch(open(os.path.join(inp, 'change.diff'),
                                              encoding='utf-8', errors='replace').read())]
    for rel in touched:
        tgt = os.path.join(m1, rel)
        if os.path.lexists(tgt):
            os.unlink(tgt)          # 只删目录项，M 的 inode 不受影响
        if os.path.exists(os.path.join(m, rel)):
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            shutil.copy2(os.path.join(m, rel), tgt)
            _strip_crlf(tgt)
    ok, failed = reverse_apply(m1, os.path.join(inp, 'change.diff'), work, allow_patch=False)
    return m, m1, ok, failed


def changed_cu(m, patch_files):
    """改动里的 C/C++ 文件，排除测试侧（测试代码不是库 API，还会拖慢/污染 AST）。

    优先用编译单元（.c/.cc/.cpp）；只改了头文件时退回头文件本身。
    """
    cus, hdrs = [], []
    for p in patch_files:
        ext = os.path.splitext(p)[1].lower()
        if ext not in C_EXTS:
            continue
        if classify_bsm_c.is_test_side(p):
            continue
        full = os.path.join(m, p)
        if not os.path.exists(full):
            continue
        (cus if ext in CU_EXTS else hdrs).append(p)
    return cus or hdrs


def harness_files(case, case_dir, work):
    """返回 (harness 根, 需要 dump 的 harness 文件列表)。intree 的 harness 在 source 里。"""
    root = os.path.join(work, 'H')
    shutil.copytree(os.path.join(case_dir, 'input', 'harness'), root, symlinks=True)
    norm_eol(root)
    files = []
    for rel in case.get('harness_files') or []:
        p = os.path.join(root, rel)
        if os.path.exists(p):
            files.append(p)
    if not files:  # 兜底：harness 目录里所有编译单元
        for dp, _, fs in os.walk(root):
            for f in fs:
                if os.path.splitext(f)[1].lower() in CU_EXTS:
                    files.append(os.path.join(dp, f))
    # harness 依赖的本地 .c（common.c 之类）一并 dump，但不作为入口
    deps = []
    seen = {os.path.normpath(f) for f in files}
    for f in list(files):
        for inc in re.findall(r'^\s*#\s*include\s+"([^"]+)"', open(f, encoding='utf-8', errors='replace').read(), re.M):
            cand = os.path.normpath(os.path.join(os.path.dirname(f), inc))
            if cand in seen:
                continue
            base = os.path.splitext(cand)[0]
            for ext in ('.c', '.cc', '.cpp'):
                if os.path.exists(base + ext):
                    deps.append(base + ext)
                    seen.add(os.path.normpath(base + ext))
    return root, files + deps


_DEF_INDEX = {}
_INDEX_CAP = [1500]        # 单棵树最多索引多少个编译单元（由 --max-index-files 设置）


def def_index(tree):
    """一次遍历建"函数名 -> 定义所在文件"索引。

    起初是每个待扩展符号都 walk 一遍整棵树，nghttp2/libxml2 这种几千文件的树会卡几十秒；
    改成建一次索引后按名查，单 case 的扩展开销从 O(名字数 × 文件数) 降到 O(文件数)。
    """
    key = os.path.normpath(tree)
    if key in _DEF_INDEX:
        return _DEF_INDEX[key]
    idx, n_files = {}, 0
    pat = re.compile(rb'(?m)^[A-Za-z_][\w \t\*]*?\b([A-Za-z_]\w*)\s*\(')
    for dp, dns, fs in os.walk(tree):
        dns[:] = [d for d in dns if not d.startswith('.')]
        for f in fs:
            if os.path.splitext(f)[1].lower() not in CU_EXTS:
                continue
            p = os.path.join(dp, f)
            n_files += 1
            if n_files > _INDEX_CAP[0]:
                return idx
            try:
                if os.path.getsize(p) > 2_000_000:
                    continue
                data = open(p, 'rb').read()
            except OSError:
                continue
            for m in pat.finditer(data):
                n = m.group(1).decode('latin-1')
                lst = idx.setdefault(n, [])
                if len(lst) < 2 and p not in lst:
                    lst.append(p)
    _DEF_INDEX[key] = idx
    return idx


def run_case(case, ds, args):
    case_dir = os.path.join(ds, case['path'])
    t0 = time.time()
    work = tempfile.mkdtemp(prefix='ir15_', dir=args.workdir)
    rec = OrderedDict(id=case['dir_id'], dir=case['dir'], project=case.get('project'),
                      gt_label=case['label'], gt_visibility=case['need_visibility'],
                      gt_type=case['degradation_type'], gt_introduced=case.get('introduced_by_this_change'))
    ev = OrderedDict()
    rec['evidence'] = ev
    try:
        m, m1, ok, failed = prep_case(case_dir, work, hardlink=not args.no_hardlink)
        ev['m1'] = OrderedDict(reverted=len(ok), failed=failed[:5], failed_n=len(failed))

        hroot, hfiles = harness_files(case, case_dir, work)
        build_sh = None
        for cand in (case.get('build_script'), 'harness/build/build.sh'):
            if not cand:
                continue
            p = os.path.join(case_dir, 'input', cand) if not cand.startswith('input/') else os.path.join(case_dir, cand)
            p = os.path.normpath(p)
            if os.path.exists(p):
                build_sh = p
                break
        flags, notes = make_flags(case, m, hroot, build_sh)
        ev['flags'] = OrderedDict(include_n=sum(1 for f in flags if f.startswith('-I')),
                                  defines=[f for f in flags if f.startswith('-D')],
                                  notes=notes)

        stub = os.path.join(work, 'stub')
        os.makedirs(stub, exist_ok=True)

        cu = changed_cu(m, ok + failed)
        ev['changed_cu'] = cu
        if not cu:
            rec['label'] = LABEL_NO_UPDATE
            ev['reason'] = 'no C/C++ file changed'
            rec['changed_code_files'] = 0
            return rec

        ast_fail, stubs_used, synth = [], set(), []

        def expired():
            return (time.time() - t0) > args.case_timeout

        def dump_collect(path, roots, tag, harness_root=None):
            if expired():          # 大项目（binutils）单个 TU 就能跑几分钟，超时就收缩
                ev['timeout'] = True
                return {}
            cxx = os.path.splitext(path)[1].lower() in ('.cc', '.cpp', '.cxx')
            data, err, st = dump_ast(path, flags, stub, cxx=cxx, verbose=args.verbose,
                                     tree=m, synth=synth)
            stubs_used.update(st)
            if data is None:
                ast_fail.append('%s: %s' % (tag, err))
                return {}
            if err:
                ast_fail.append('%s: %s' % (tag, err))
            funcs, _macros, _tmap = collect(data, roots, harness_root=harness_root,
                                           default_file=os.path.abspath(path))
            return funcs

        f_m, f_m1 = {}, {}
        # roots 同时给 M 和 M1：两棵树的目录结构一致，谁匹配上都说明是"库侧文件"，
        # 归属只影响 relpath 的基准，不会把两侧混起来（符号表各存各的）。
        both = (m, m1)
        for rel in cu:
            merge_into(f_m, dump_collect(os.path.join(m, rel), both, 'M/' + rel))
        for rel in cu:
            merge_into(f_m1, dump_collect(os.path.join(m1, rel), both, 'M1/' + rel))

        # 符号表：只保留"库侧 API"（非 static）参与 delta
        api_m = {k: v for k, v in f_m.items() if not v['static'] and not is_reserved(k)}
        api_m1 = {k: v for k, v in f_m1.items() if not v['static'] and not is_reserved(k)}
        # 只在"两版都成功解析"的文件上比符号：某个 TU 在 M 侧部分失败时，
        # 它独有的符号会被误当成新增/删除，这是纯属工具噪声，先按文件屏蔽掉。
        failed_m = {x[2:].split(':')[0] for x in ast_fail if x.startswith('M/')}
        failed_m1 = {x[2:].split(':')[0] for x in ast_fail if x.startswith('M1/')}
        sig_changed = sorted(k for k in api_m.keys() & api_m1.keys()
                             if api_m[k]['file'] not in failed_m
                             and api_m1[k]['file'] not in failed_m1
                             and sig_of(api_m[k]) != sig_of(api_m1[k]))
        removed = sorted(k for k in api_m1.keys() - api_m.keys()
                         if api_m1[k]['file'] not in failed_m)
        added = sorted(k for k in api_m.keys() - api_m1.keys()
                       if api_m[k]['file'] not in failed_m1)
        if args.debug_name:
            ev['debug_symbol'] = {'m': api_m.get(args.debug_name),
                                  'm1': api_m1.get(args.debug_name)}
        ev['symbols'] = OrderedDict(m=len(api_m), m1=len(api_m1),
                                    sig_changed=sig_changed[:20], sig_changed_n=len(sig_changed),
                                    removed=removed[:20], removed_n=len(removed),
                                    added=added[:20], added_n=len(added))

        # ── 调用图：harness 入口出发 ──
        h_funcs = {}
        for p in hfiles:
            merge_into(h_funcs, dump_collect(p, (hroot, m, m1), 'H/' + os.path.relpath(p, hroot),
                                             harness_root=hroot))
        h_nodes = {k: v for k, v in h_funcs.items() if v['in_harness']}
        # harness TU 里看到的库声明：只用来补"该符号被引用过"的证据，不覆盖真实定义
        for k, v in h_funcs.items():
            if not v['in_harness'] and k not in f_m:
                f_m[k] = v

        graph = {}
        for k, v in list(h_nodes.items()) + list(f_m.items()):
            if v.get('body'):
                graph.setdefault(k, set()).update(v['body']['calls'])
                graph.setdefault(k, set()).update(v['body']['refs'])

        roots = [k for k in h_nodes if k == 'LLVMFuzzerTestOneInput'] or \
                [k for k in f_m if k == 'LLVMFuzzerTestOneInput']
        reach = set()
        q = deque(roots)
        while q:
            n = q.popleft()
            if n in reach:
                continue
            reach.add(n)
            for c in graph.get(n, ()):
                if c not in reach:
                    q.append(c)

        # 惰性扩展：可达集里尚未 dump 定义的库函数，找到定义文件再 dump 一层
        extra = 0
        tried = set()
        idx = def_index(m)
        expanded = True
        while expanded and extra < args.max_extra and not expired():
            expanded = False
            for name in sorted(reach):
                if name in f_m and f_m[name].get('body'):
                    continue
                if name in tried:
                    continue
                for p in idx.get(name, []):
                    if extra >= args.max_extra:
                        break
                    tried.add(p)
                    extra += 1
                    data, err, st = dump_ast(p, flags, stub,
                                             cxx=os.path.splitext(p)[1].lower() in ('.cc', '.cpp', '.cxx'),
                                             tree=m, synth=synth)
                    stubs_used.update(st)
                    if data is None:
                        ast_fail.append('X/%s: %s' % (os.path.relpath(p, m), err))
                        continue
                    funcs, _, _ = collect(data, both, default_file=os.path.abspath(p))
                    for k, v in funcs.items():
                        if k not in f_m or (not f_m[k].get('body') and v.get('body')):
                            f_m[k] = v
                    for k, v in funcs.items():
                        if v.get('body'):
                            graph.setdefault(k, set()).update(v['body']['calls'])
                            graph.setdefault(k, set()).update(v['body']['refs'])
                    # 新边可能带出新节点，继续 BFS
                    for k, v in funcs.items():
                        if k in reach and v.get('body'):
                            for c in set(v['body']['calls']) | set(v['body']['refs']):
                                if c not in reach:
                                    reach.add(c)
                                    expanded = True
                    expanded = True
                    break
                tried.add(name)

        # 可达集能不能算出来，和"可达集里什么都没变"是两件事，必须分开记：
        #   reach_status='ok'      → 从 LLVMFuzzerTestOneInput 走到了，可达集有内容，
        #                            此时 no_update 的含义是"库侧 delta 没碰到可达符号"；
        #   reach_status='unknown' → harness 的入口 TU 解析失败（缺头/编译错误），连
        #                            LLVMFuzzerTestOneInput 都没找到，可达集根本算不出来。
        #                            此时 no_update **不是结论**，是"没证据"。
        # 早先这个字段叫 reach_unavailable，措辞把"拿不到证据"说成了"不可达"，容易误读。
        if not roots:
            reach_status, reach_reason = 'unknown', 'no_entry_symbol'
        elif ev.get('timeout'):
            reach_status, reach_reason = 'unknown', 'timeout'
        else:
            reach_status, reach_reason = 'ok', ''
        boundary = sorted(n for n in reach if n in api_m or n in api_m1)
        ev['reach'] = OrderedDict(roots=roots, size=len(reach), boundary=boundary[:25],
                                  boundary_n=len(boundary), expanded_files=extra,
                                  status=reach_status, status_reason=reach_reason)
        ev['ast'] = OrderedDict(stubs=sorted(stubs_used), synth_defines=list(synth),
                                fail=ast_fail[:10], fail_n=len(ast_fail))

        # ── 判定 ──
        reach_api = set(boundary)
        sig_hit = [n for n in sig_changed if n in reach_api]
        removed_hit = [n for n in removed if n in reach_api]
        added_ext = [n for n in added if not api_m[n]['static']]
        missing_hit = [n for n in added_ext if n not in reach_api]

        # body 层：两版都解析出函数体的可达符号，做结构指纹比对。
        # 可达的 static 函数（内部 helper）改了，语义上也算"行为可能变了"，但 harness 无法
        # 直接调用它，判 stale 相当于把"任何内部重构"都当成需要更新。默认**不算**，
        # 由 --body-static 打开；两种口径的证据都记进 evidence，标签可离线复算。
        body_all, trivial = [], []
        for n in sorted(reach):
            a, b = f_m.get(n), f_m1.get(n)
            if not a or not b or not a.get('body') or not b.get('body'):
                continue
            if a['body']['hash'] != b['body']['hash']:
                body_all.append(n)
            elif a['body']['text_hash'] != b['body']['text_hash']:
                trivial.append(n)
        body_pub = [n for n in body_all if not f_m[n]['static']]
        body_sta = [n for n in body_all if f_m[n]['static']]
        body_changed = body_all if args.body_static else body_pub

        if sig_hit or removed_hit:
            label, why = LABEL_BREAKING, 'signature/remove on reachable symbol'
        elif missing_hit:
            label, why = LABEL_MISSING, 'new external symbol unreachable from harness'
        elif body_changed:
            label, why = LABEL_STALE, 'reachable symbol body changed, signature stable'
        elif reach_status != 'ok':
            # 标签仍是 no_update（标签空间只有四种），但理由必须和"触及了但没变"区分开，
            # 否则读文档的人会把这条 no_update 当成"确认不需要更新"。
            label = LABEL_NO_UPDATE
            why = 'no evidence: reachability not computable (%s)' % reach_reason
        else:
            label, why = LABEL_NO_UPDATE, 'no delta touches harness-reachable symbols'

        rec['label'] = label
        rec['changed_code_files'] = len(cu)
        ev['decision'] = OrderedDict(
            label=label, why=why,
            sig_changed_reachable=sig_hit[:15],
            removed_reachable=removed_hit[:15],
            added_external=added_ext[:15],
            missing_unreachable=missing_hit[:15],
            body_changed_reachable=body_pub[:15],
            body_changed_public_n=len(body_pub),
            body_changed_static=body_sta[:15],
            body_changed_static_n=len(body_sta),
            body_static_policy=bool(args.body_static),
            string_only_reachable=trivial[:15],
            reach_size=len(reach), boundary_n=len(reach_api),
            reach_status=reach_status, reach_status_reason=reach_reason,
        )
        if args.verbose:
            print('  %-6s %-12s <- %-60s sig=%d add=%d miss=%d body=%d' %
                  (rec['id'], label, why, len(sig_hit), len(added_ext), len(missing_hit),
                   len(body_changed)), file=sys.stderr)
        return rec
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        if args.verbose:
            print(tb, file=sys.stderr)
        rec['label'] = 'error'
        rec['error'] = '%s: %s' % (type(e).__name__, e)
        rec['traceback'] = tb.strip().splitlines()[-6:]
        return rec
    finally:
        if not args.keep_work:
            shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description='路线 1.5：clang AST IR 版 B/S/M 分类（v9）')
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--out', default='results/ir_v9.json')
    ap.add_argument('--cases', default=None, help='只跑指定 dir_id，逗号分隔')
    ap.add_argument('--workdir', default='/tmp')
    ap.add_argument('--jobs', type=int, default=max(1, min(8, (os.cpu_count() or 2) - 2)))
    ap.add_argument('--max-extra', type=int, default=40, help='可达性扩展最多额外 dump 的文件数')
    ap.add_argument('--keep-work', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--debug-name', default=None, help='把某个符号的两版记录写进 evidence')
    ap.add_argument('--case-timeout', type=float, default=420.0, help='单个 case 的墙钟上限（秒）')
    ap.add_argument('--max-index-files', type=int, default=1500, help='单棵树最多索引的编译单元数')
    ap.add_argument('--body-static', action='store_true',
                    help='行为层把可达的 static 函数也算进来（默认只算公开符号）')
    ap.add_argument('--no-hardlink', action='store_true', help='M1 改成实体拷贝（默认硬链接）')
    args = ap.parse_args()

    _INDEX_CAP[0] = args.max_index_files
    if shutil.which('clang') is None:
        sys.exit('找不到 clang：本脚本需要在 WSL/Linux 里跑（clang 21 已验证）')

    man = json.load(open(os.path.join(args.dataset, 'dataset.json'), encoding='utf-8'))
    samples = man['samples']
    if args.cases:
        want = {c.strip() for c in args.cases.split(',')}
        samples = [s for s in samples if s['dir_id'] in want]

    os.makedirs(args.workdir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    rows = []
    order = {s['dir_id']: i for i, s in enumerate(man['samples'])}

    def write_out():
        """增量落盘：48 条里有 binutils 这种慢样本，不能等全部跑完才写。"""
        rows.sort(key=lambda r: order.get(r.get('id'), 999))
        json.dump(rows, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if args.jobs > 1 and len(samples) > 1:
        with mp.Pool(args.jobs) as pool:
            for i, rec in enumerate(pool.imap_unordered(
                    _run_case_star, [(s, args.dataset, args) for s in samples]), 1):
                rows.append(rec)
                write_out()
                print('[%d/%d] %-6s %s' % (i, len(samples), rec.get('id'), rec.get('label')),
                      file=sys.stderr)
    else:
        for i, s in enumerate(samples, 1):
            rec = run_case(s, args.dataset, args)
            rows.append(rec)
            write_out()
            print('[%d/%d] %-6s %s' % (i, len(samples), rec.get('id'), rec.get('label')),
                  file=sys.stderr)

    write_out()

    print('\n=== 预测分布 ===', file=sys.stderr)
    for k, v in Counter(r.get('label') for r in rows).most_common():
        print('  %-14s %d' % (str(k), v), file=sys.stderr)
    print('[out]', args.out, file=sys.stderr)


def _run_case_star(a):
    return run_case(*a)


if __name__ == '__main__':
    main()
