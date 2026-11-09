from __future__ import annotations
from pathlib import Path
from scheme_v8.llm.context import PacketBuilder as PreviousPacketBuilder
BUILD_NAMES = {'CMakeLists.txt', 'Makefile', 'Makefile.am', 'Makefile.in', 'configure', 'configure.ac', 'meson.build', 'meson_options.txt', 'build.sh'}

class PacketBuilder(PreviousPacketBuilder):
    """Trusted, allowlisted retrieval; requests describe questions, never executable commands."""

    def __init__(self, reader, config):
        super().__init__(reader, config)
        self.request_keys = set()
        self.request_count = 0
        self.phase = 'source'
        self.limit = config.get('diff_packet_chars', 16000)
        changed_dirs = {str(Path(g.path).parent) for g in self.groups}
        candidates = [p for p in reader.case.manifest['files'] if p.startswith('input/source/') and (Path(p).name in BUILD_NAMES or Path(p).suffix == '.cmake')]
        self.build_candidates = sorted(candidates, key=lambda p: (str(Path(p.removeprefix('input/source/')).parent) not in changed_dirs, len(Path(p).parts), p))[:config.get('max_build_candidates', 24)]

    def add_harness(self):
        build = self.reader.case.build_script
        if build:
            try:
                self.snippet(build, 1, 160, 'target build configuration', 'harness')
            except (ValueError, RuntimeError, OSError) as exc:
                self.issues.append('build_context:' + str(exc))
        used = sum((len(e['text']) + 150 for e in self.blocks.values() if e['kind'] == 'harness' and e['path'] != build))
        remaining = max(0, self.config.get('max_harness_chars', 16000) - used)
        for path in self.reader.case.harness_files:
            if self.harness_complete.get(path):
                continue
            try:
                lines = self.reader.index(path).decode('utf-8', errors='replace').splitlines()
                if not lines:
                    self.harness_complete[path] = False
                    continue
                if len('\n'.join(lines)) + 150 <= remaining and self.snippet(path, 1, len(lines), 'complete old target', 'harness'):
                    self.harness_complete[path] = True
                    remaining -= len('\n'.join(lines)) + 150
                    continue
                self.harness_complete[path] = False
                functions = [f for f in self.syntax.functions(path) if f.definition]
                roots = {'LLVMFuzzerTestOneInput', 'LLVMFuzzerInitialize'}
                for depth in range(self.reader.budget.limits.max_depth + 1):
                    selected = [f for f in functions if f.name in roots]
                    for f in selected:
                        start, end = (f.node.start_point.row + 1, f.node.end_point.row + 1)
                        end = min(end, start + 149)
                        size = len('\n'.join(lines[start - 1:end])) + 150
                        if size <= remaining:
                            before = self.total_chars
                            self.snippet(path, start, end, 'bounded target entry/helper', 'harness', depth)
                            remaining -= self.total_chars - before
                    roots = {n for f in selected for n, _, _ in self.syntax.calls(f.node)}
                size = len('\n'.join(lines[:50])) + 150
                if size <= remaining:
                    before = self.total_chars
                    self.snippet(path, 1, min(50, len(lines)), 'target includes and macros', 'harness')
                    remaining -= self.total_chars - before
            except (ValueError, RuntimeError, OSError) as exc:
                self.issues.append('harness_context:' + str(exc))

    def packet(self):
        packet = super().packet()
        packet.update(phase=getattr(self, 'phase', 'source'), build_candidates=getattr(self, 'build_candidates', []), change_catalog=[{'change_id': g.id, 'path': g.path, 'heading': g.heading, 'selected': g.id in self.selected_groups} for g in self.groups[:300]], change_catalog_truncated=len(self.groups) > 300, remaining_targeted_requests=max(0, self.config.get('max_total_requests', 8) - getattr(self, 'request_count', 0)), foundation_checks=['build', 'input', 'lifecycle', 'control_flow'])
        return packet
