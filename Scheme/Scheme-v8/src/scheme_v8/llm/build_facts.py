"""Deterministic build-configuration facts (evidence classes A and B).

A. Compile-time configuration
   A1 preprocessor conditions that enclose each selected change (after source),
      plus conditional directives added inside the change;
   A2 where the macros used by those conditions are defined or set
      (#define/#undef, -D/-U, AC_DEFINE, CMake option/definitions, meson);
   A3 configuration settings in the build recipe (-D/-U, configure/CMake
      options, *FLAGS assignments, build-time edits of source files).
B. Build paths
   Every repository path the build recipe refers to is checked against the
   supplied source tree; for a missing path the deepest existing ancestor and
   the first missing component are reported, with same-named directories found
   elsewhere as hints. Build outputs (.libs, .o, .a, ...) are checked through
   their source directory only.

The facts are navigation aids. The underlying lines are added to the packet as
ordinary evidence units so that conclusions cite real text.
"""
from __future__ import annotations

import fnmatch
import posixpath
import re
import shutil
import subprocess
from pathlib import PurePosixPath

DIRECTIVE = re.compile(r'^\s*#\s*(if|ifdef|ifndef|elif|elifdef|elifndef|else|endif)\b(.*)$')
MACRO = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]{2,})\b')
NOT_MACROS = {'defined', 'if', 'ifdef', 'ifndef', 'elif', 'else', 'endif', 'and', 'or', 'not', '__has_include',
              '__has_attribute', '__has_builtin', '__has_feature', '__GNUC__', '__clang__', '__cplusplus',
              '__STDC_VERSION__', '_WIN32', '_MSC_VER', '__APPLE__', '__linux__', '__unix__', 'TRUE', 'FALSE'}
DEFINITION = (r'#\s*(define|undef|cmakedefine01|cmakedefine)\s+{m}\b', r'-[DU]\s*{m}\b', r'AC_DEFINE(_UNQUOTED)?\s*\(\s*\[?{m}\b',
              r'option\s*\(\s*{m}\b', r'add_(compile_)?definitions\s*\(.*\b{m}\b', r'\b{m}\b\s*[:?]?=', r"option\s*\(\s*'{m}'")
CONFIG_SUFFIXES = {'.h', '.hh', '.hpp', '.hxx', '.inc', '.in', '.cmake', '.ac', '.am', '.mk', '.m4', '.txt', '.build',
                   '.options', '.dfa', '.sh', '.py', '.cfg', '.def'}
CONFIG_NAMES = {'Makefile', 'GNUmakefile', 'configure', 'CMakeLists.txt', 'meson.build', 'meson_options.txt',
                'meson.options', 'BUILD', 'BUILD.gn', 'SConstruct', 'Dockerfile', 'build.sh'}
FLAG = re.compile(r'(?<![\w-])(-[DU]\s*[A-Za-z_]\w*(?:=\S*)?|--(?:enable|disable|with|without)-[\w-]+(?:=\S+)?'
                  r'|-D\s*CMAKE_\w+=\S+)')
FLAGS_ASSIGN = re.compile(r'\b(?:export\s+)?((?:C|CXX|CPP|LD)FLAGS|LIBS|CMAKE_\w+)\s*\+?=')
EDIT = re.compile(r'\bsed\b.*\s-i\b|\bsed\b.*>\s*\S|\bpatch\b|\bgit\s+apply\b|>>?\s*[\w./-]+\.(?:h|c|dfa|in|cmake|txt)\b')
PATH_TOKEN = re.compile(r'(?:(?<=\s)|^|(?<=[="\']))(-[IL])?((?:\$\{?SRC\}?/|\./|\.\./)?[\w.+*?-]+(?:/[\w.+*?$\{\}-]*)+|(?:\$\{?SRC\}?/)?[\w.+*?-]+\.(?:a|la|so|o|c|cc|cpp|h|dfa|in|py|dict|options|zip))(?=[\s"\';)]|$)')
GENERATED = re.compile(r'^(\.libs|\.deps|_build|build|out|obj|lib)$|\.(a|la|so|o|lo|obj|dylib)(\.\d+)*$')
MAX_MACROS, MAX_DEFS = 16, 6
C_LIKE = {'.c', '.h', '.cc', '.cpp', '.cxx', '.hpp', '.hxx', '.hh', '.inc', '.ipp', '.tcc'}


def _lines(data):
    return data.decode('utf-8', errors='replace').split('\n')


def condition_stack(lines, target):
    """Directives enclosing 1-based line `target`; continuation lines are joined."""
    stack, n = ([], 0)
    while n < min(target - 1, len(lines)):
        start = n + 1
        text = lines[n]
        while text.endswith('\\') and n + 1 < len(lines):
            n += 1
            text = text[:-1] + ' ' + lines[n].strip()
        n += 1
        m = DIRECTIVE.match(text)
        if not m:
            continue
        kind, rest = (m.group(1), m.group(2).strip())
        if kind in ('if', 'ifdef', 'ifndef'):
            guard = kind == 'ifndef' and n < len(lines) and re.match(r'^\s*#\s*define\s+' + re.escape(rest.split()[0] if rest else '#') + r'\b', lines[n])
            stack.append({'line': start, 'directive': f'#{kind} {rest}'.strip(), 'include_guard': bool(guard)})
        elif stack and kind == 'endif':
            stack.pop()
        elif stack:
            stack[-1]['active_branch'] = f'#{kind} {rest}'.strip()
            stack[-1]['branch_line'] = start
    return stack


def macros_of(directive):
    text = re.sub(r'/\*.*?\*/', ' ', directive)
    text = re.sub(r'//.*|/\*.*', ' ', text)
    text = re.sub(r'^\s*#\s*\w+', ' ', text)
    return [m for m in MACRO.findall(text) if m not in NOT_MACROS and not m.isdigit()]


def _config_file(rel):
    p = PurePosixPath(rel)
    return p.name in CONFIG_NAMES or p.suffix.lower() in CONFIG_SUFFIXES or p.name.startswith('Makefile')


RG_GLOBS = ['*.h', '*.hh', '*.hpp', '*.hxx', '*.inc', '*.in', '*.cmake', '*.ac', '*.am', '*.mk', '*.m4', '*.dfa',
            '*.sh', 'CMakeLists.txt', 'Makefile*', 'GNUmakefile', 'configure', 'meson.build', 'meson_options.txt',
            'meson.options', 'Dockerfile', 'BUILD*', 'SConstruct']


def _rg_lines(root, macros):
    rg = shutil.which('rg')
    if not rg or not macros:
        return None if not rg else []
    args = [rg, '-n', '--no-heading', '-w', '--max-columns', '400']
    for g in RG_GLOBS:
        args += ['-g', g]
    for m in macros:
        args += ['-e', m]
    proc = subprocess.run(args + ['--', str(root / 'input')], capture_output=True, text=True, timeout=300)
    if proc.returncode not in (0, 1):
        return None
    out = []
    for line in proc.stdout.splitlines():
        path, _, rest = line.partition(':')
        number, _, text = rest.partition(':')
        if number.isdigit():
            out.append((path, int(number), text))
    return out


def macro_definitions(builder, macro, hits=None):
    reader = builder.reader
    root = reader.case.root
    patterns = [re.compile(p.format(m=re.escape(macro))) for p in DEFINITION]
    if hits is not None:
        hits = [h for h in hits if re.search(r'\b' + re.escape(macro) + r'\b', h[2])]
    if hits is None:
        hits = []
        for rel in reader.case.manifest['files']:
            if rel.startswith('input/') and _config_file(rel):
                for i, text in enumerate(_lines(reader.index(rel)), 1):
                    if re.search(r'\b' + re.escape(macro) + r'\b', text):
                        hits.append((str(root / rel), i, text))
    found = []
    for path, number, text in hits:
        rel = PurePosixPath(path).relative_to(PurePosixPath(str(root))).as_posix() if path.startswith(str(root)) else path
        if rel not in reader.case.manifest['files'] or not _config_file(rel):
            continue
        if any(p.search(text) for p in patterns):
            found.append({'path': rel, 'line': number, 'text': text.strip()[:240]})
    # Headers and build files before tests and docs; at most MAX_DEFS.
    rank = lambda f: ('/test' in f['path'] or '/doc' in f['path'], not f['path'].endswith(('.h', '.in', '.ac', 'CMakeLists.txt', '.cmake')), f['path'], f['line'])
    return sorted(found, key=rank)[:MAX_DEFS]


def build_scripts(case, read=None):
    """Harness-side build files, plus source-tree scripts they invoke (one level)."""
    files = [p for p in case.manifest['files'] if p.startswith('input/harness/')]
    chosen = [case.build_script] if case.build_script else []
    chosen += [p for p in files if PurePosixPath(p).name in CONFIG_NAMES or PurePosixPath(p).suffix in ('.sh', '.mk', '.cmake')]
    chosen = [p for p in dict.fromkeys(chosen) if p in case.manifest['files']]
    if read is not None:
        for rel in list(chosen):
            for token in re.findall(r'(?:\$\{?SRC\}?/[^/\s]+/|\./)?([\w./-]+\.sh)\b', read(rel)):
                candidate = 'input/source/' + posixpath.normpath(token)
                if candidate in case.manifest['files'] and candidate not in chosen:
                    chosen.append(candidate)
    return chosen


def recipe_settings(builder):
    settings = []
    for rel in build_scripts(builder.reader.case, lambda r: builder.reader.index(r).decode('utf-8', 'replace')):
        for i, text in enumerate(_lines(builder.reader.index(rel)), 1):
            stripped = text.strip()
            if not stripped or stripped.startswith('#'):
                continue
            kinds = []
            if FLAG.search(stripped):
                kinds.append('flags:' + ' '.join(dict.fromkeys(f.replace(' ', '') for f in FLAG.findall(stripped)))[:200])
            if FLAGS_ASSIGN.search(stripped):
                kinds.append('flags_assignment')
            if EDIT.search(stripped):
                kinds.append('build_time_source_edit')
            if kinds:
                settings.append({'path': rel, 'line': i, 'text': stripped[:240], 'kind': kinds})
    return settings


def _source_dirs(manifest):
    dirs = set()
    for rel in manifest:
        if rel.startswith('input/source/'):
            parts = rel[len('input/source/'):].split('/')[:-1]
            for k in range(1, len(parts) + 1):
                dirs.add('/'.join(parts[:k]))
    return dirs


SKIP_LINE = re.compile(r'^\s*(FROM|LABEL|MAINTAINER)\b|\b(wget|curl|git\s+clone|apt(-get)?|pip3?\s+install|echo)\b')
SKIP_TOKEN = re.compile(r'^s[/|#]|://|\.(deb|rpm|zip|tar|gz|tgz|xz|bz2|whl|patch|diff)$|^[\w.-]+\.(io|com|org|net)/')


def path_checks(builder):
    case = builder.reader.case
    files = {p[len('input/source/'):] for p in case.manifest['files'] if p.startswith('input/source/')}
    harness = {p[len('input/harness/'):] for p in case.manifest['files'] if p.startswith('input/harness/')}
    harness_names = {PurePosixPath(h).name for h in harness}
    dirs = _source_dirs(case.manifest['files'])
    tree = files | dirs
    by_name = {}
    for d in dirs:
        by_name.setdefault(d.rsplit('/', 1)[-1], []).append(d)

    def resolve(path):
        """Return how the path maps onto the supplied tree, or None."""
        if path in tree:
            return path
        tail = [x for x in tree if x.endswith('/' + path)]
        if len(tail) == 1:
            return tail[0]
        parts = path.split('/')
        if len(parts) > 1 and '/'.join(parts[1:]) in tree:
            return '/'.join(parts[1:])
        return None

    checks, seen, created = ([], set(), set())
    for rel in build_scripts(case, lambda r: builder.reader.index(r).decode('utf-8', 'replace')):
        cwd = ''
        for i, text in enumerate(_lines(builder.reader.index(rel)), 1):
            stripped = text.strip()
            if not stripped or stripped.startswith('#') or SKIP_LINE.search(stripped):
                continue
            mk = re.match(r'^mkdir\s+(?:-p\s+)?(.+)$', stripped)
            if mk:
                for d in mk.group(1).split():
                    created.add(posixpath.normpath(re.sub(r'^\$\{?SRC\}?/[^/]+/?', '', d.strip('"\'')) or '.'))
                continue
            cd = re.match(r'^cd\s+(\S+)', stripped)
            if cd:
                target = cd.group(1).strip('"\'')
                if target.startswith('$') and not re.match(r'^\$\{?SRC\}?/', target):
                    cwd = ''
                else:
                    target = re.sub(r'^\$\{?SRC\}?/[^/]+/?', '', target)
                    cwd = posixpath.normpath(posixpath.join(cwd, target)) if target else ''
                    cwd = '' if cwd == '.' else cwd
                continue
            copy = re.match(r'^(cp|mv|ln|install)\b(.*)$', stripped)
            if copy:
                # The last operand is a destination that the recipe itself creates.
                operands = [w for w in copy.group(2).split() if not w.startswith('-')]
                stripped = copy.group(1) + ' ' + ' '.join(operands[:-1])
            if 'sed ' in stripped:
                stripped = re.sub(r"(['\"])s[/|#].*?\1", ' ', stripped)
            for flag, token in PATH_TOKEN.findall(stripped):
                token = token.strip('"\'')
                if SKIP_TOKEN.search(token) or token.startswith(('/', '_')) or '{' in token or '}' in token:
                    continue
                if '$' in re.sub(r'\$\{?SRC\}?', '', token):
                    continue
                single = re.match(r'^\$\{?SRC\}?/([^/]+)$', token)
                if single:
                    # Files directly in $SRC come from the fuzzing project's own directory (the harness side).
                    name = single.group(1)
                    if token in seen:
                        continue
                    seen.add(token)
                    hits = sorted(h for h in harness if fnmatch.fnmatch(PurePosixPath(h).name, name))
                    checks.append({'path': token, 'build_file': rel, 'line': i, 'status': 'harness_file' if hits else 'missing',
                                   **({'matches': hits[:5]} if hits and hits != [name] else {})})
                    continue
                from_src = bool(re.match(r'^\$\{?SRC\}?/', token))
                path = re.sub(r'^\$\{?SRC\}?/[^/]+/?', '', token)
                path = posixpath.normpath(path if from_src or not cwd else posixpath.join(cwd, path))
                if path in ('.', '') or path.startswith('..') or path in seen:
                    continue
                seen.add(path)
                parts = path.split('/')
                keep = list(parts)
                while keep and GENERATED.search(keep[-1]):
                    keep.pop()
                source_path = '/'.join(keep)
                generated = len(keep) < len(parts)
                record = {'path': path, 'build_file': rel, 'line': i, 'flag': flag or None, 'generated_output': generated,
                          'source_path_checked': source_path or '.'}
                if any(ch in source_path for ch in '*?'):
                    hits = sorted(x for x in tree if fnmatch.fnmatch(x, source_path))
                    hits += sorted(h for h in harness if fnmatch.fnmatch(h, source_path) or fnmatch.fnmatch(PurePosixPath(h).name, source_path))
                    record['status'] = 'exists' if hits else 'missing'
                    record['glob_matches'] = len(hits)
                elif not source_path or any(source_path == c or source_path.startswith(c + '/') for c in created):
                    record['status'] = 'build_directory_created_by_recipe'
                elif resolve(source_path):
                    record['status'] = 'exists'
                    if resolve(source_path) != source_path:
                        record['resolved_as'] = resolve(source_path)
                elif source_path in harness or PurePosixPath(source_path).name in harness_names:
                    record['status'] = 'harness_file'
                elif any((source_path + ext) in files for ext in ('.ac', '.in', '.am')):
                    record['status'] = 'generated_from_template'
                else:
                    record['status'] = 'missing'
                    k = 0
                    while k < len(keep) and '/'.join(keep[:k + 1]) in dirs:
                        k += 1
                    record['deepest_existing'] = '/'.join(keep[:k]) or '.'
                    record['first_missing'] = keep[k] if k < len(keep) else None
                    hint_names = [p for p in keep[k:] if p not in ('src', 'include', 'lib', 'build')]
                    record['same_name_elsewhere'] = sorted({d for n in hint_names[:2] for d in by_name.get(n, [])})[:5]
                checks.append(record)
    # Every referenced path is reported with its status, so existence can be affirmed as
    # well as refuted; detail fields are kept only where they carry information.
    compact = []
    for c in checks:
        item = {k: c[k] for k in ('path', 'status', 'build_file', 'line') if k in c}
        for k in ('flag', 'resolved_as', 'glob_matches', 'matches', 'deepest_existing', 'first_missing', 'same_name_elsewhere'):
            if c.get(k):
                item[k] = c[k]
        if c.get('status') == 'missing' and c.get('flag') in ('-I', '-L'):
            item['note'] = 'a nonexistent -I/-L directory is ignored by the compiler; it matters only if a required header or library is found nowhere else'
        if c.get('generated_output'):
            item['generated_output'] = True
            item['source_path_checked'] = c['source_path_checked']
        compact.append(item)
    return compact[:120]


def compile_context(builder):
    reader = builder.reader
    context, macros = ([], [])
    for g in builder.groups:
        if g.id not in builder.selected_groups:
            continue
        rel = 'input/source/' + g.path
        # Preprocessor conditions only exist in C/C++ sources ('#if' in a shell script is a comment).
        if rel not in reader.case.manifest['files'] or PurePosixPath(g.path).suffix.lower() not in C_LIKE:
            continue
        lines = _lines(reader.index(rel))
        stack = [s for s in condition_stack(lines, g.new_start) if not s.pop('include_guard')]
        inner = []
        for n in range(g.new_start, min(g.new_start + max(g.new_count, 1), len(lines) + 1)):
            m = DIRECTIVE.match(lines[n - 1])
            if m and m.group(1) not in ('else', 'endif'):
                inner.append({'line': n, 'directive': lines[n - 1].strip()[:240]})
        if stack or inner:
            context.append({'change_id': g.id, 'path': rel, 'change_line': g.new_start,
                            'enclosing_conditions': [{k: v for k, v in s.items()} for s in stack], 'directives_inside_change': inner})
            for s in stack:
                macros.extend(macros_of(s['directive']))
                macros.extend(macros_of(s.get('active_branch', '')))
            for d in inner:
                macros.extend(macros_of(d['directive']))
    return context, list(dict.fromkeys(macros))[:MAX_MACROS]


def collect(builder):
    """Return program_facts and add the supporting lines as evidence units."""
    facts = {'note': ('Extracted by the program from the supplied files; navigation only. Cite the underlying '
                      'evidence units. A path absent from the supplied source tree may still be generated by the build.')}
    issues = []

    def window(path, line, kind, reason, radius=1):
        try:
            builder.unit(path, max(1, line - radius), line + radius, reason, kind, 'non_function_context')
        except (ValueError, OSError, RuntimeError, KeyError) as exc:
            issues.append(f'{path}:{line}:{exc}')

    try:
        context, macros = compile_context(builder)
        facts['compile_time_context'] = context
        for item in context:
            for cond in item['enclosing_conditions']:
                window(item['path'], cond['line'], 'source', 'enclosing preprocessor condition', 0)
                if 'branch_line' in cond:
                    window(item['path'], cond['branch_line'], 'source', 'active preprocessor branch', 0)
            for d in item['directives_inside_change']:
                window(item['path'], d['line'], 'source', 'preprocessor directive in change', 0)
        definitions = {}
        all_hits = _rg_lines(builder.reader.case.root, macros)
        for macro in macros:
            defs = macro_definitions(builder, macro, all_hits)
            definitions[macro] = defs
            for d in defs:
                kind = 'harness' if d['path'].startswith('input/harness/') else 'source'
                window(d['path'], d['line'], kind, f'definition or setting of {macro}')
        facts['macro_definitions'] = definitions
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        issues.append('compile_context:' + str(exc))
    try:
        facts['build_recipe_settings'] = recipe_settings(builder)
    except (ValueError, OSError, RuntimeError) as exc:
        issues.append('recipe_settings:' + str(exc))
    try:
        facts['build_path_checks'] = path_checks(builder)
    except (ValueError, OSError, RuntimeError) as exc:
        issues.append('path_checks:' + str(exc))
    if issues:
        facts['extraction_issues'] = issues[:20]
    return facts
