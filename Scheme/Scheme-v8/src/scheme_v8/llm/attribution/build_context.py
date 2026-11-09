from __future__ import annotations
from pathlib import Path

def _build_paths(case):
    candidates = []
    for p in case.manifest['files']:
        if not p.startswith('input/source/'):
            continue
        relative = p.removeprefix('input/source/')
        name = Path(relative).name
        if name in ('CMakeLists.txt', 'Makefile.am', 'build.sh') and (any((x in Path(relative).parts for x in ('fuzz', 'fuzzing', 'oss-fuzz', 'ossfuzz'))) or relative in ('CMakeLists.txt', 'Makefile.am')) or relative in ('Makefile', 'GNUmakefile', 'meson.build'):
            candidates.append(p)
    return sorted(candidates, key=lambda p: (not any((x in p for x in ('fuzz', 'oss-fuzz', 'ossfuzz'))), len(Path(p).parts), p))[:6]
