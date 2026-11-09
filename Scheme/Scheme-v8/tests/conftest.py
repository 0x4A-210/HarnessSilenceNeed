import difflib
import pytest
from scheme_v8.util import digest, write_json

@pytest.fixture
def make_input(tmp_path):
    counter = 0

    def create(before, after, harness=None, filename='lib.c', extra=None):
        nonlocal counter
        counter += 1
        root = tmp_path / f'input-{counter}'
        files = {'input/source/' + filename: after, 'input/harness/fuzz.c': harness or 'int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size) {\n    feature();\n    return 0;\n}\n', 'input/change.diff': ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/' + filename, tofile='b/' + filename, n=0))}
        files.update(extra or {})
        for name, content in files.items():
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
        data = {'id': f'case-test-{counter}', 'project': 'artificial', 'harness_target': 'fuzz', 'harness_files': ['input/harness/fuzz.c'], 'build_script': None}
        write_json(root / 'case.json', data)
        manifest = {'files': {name: {'sha256': digest((root / name).read_bytes())} for name in files}, 'case_hash': digest((root / 'case.json').read_bytes()), 'input_hash': 'fixture'}
        write_json(root / 'manifest.json', manifest)
        return root
    return create
