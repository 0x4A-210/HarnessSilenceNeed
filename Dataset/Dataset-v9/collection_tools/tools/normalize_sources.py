#!/usr/bin/env python3
"""Make input/source byte-identical to the git blobs of M (checkout-index applies eol/ident
filters from .gitattributes, e.g. CRLF for Visual Studio files) and rewrite
verification/source_blobs.json.  Harness overlay files (taken from M^1) are left alone."""
import json, os, subprocess, hashlib, glob, sys

HD = '/home/claude/hd'
ROOT = sys.argv[1] if len(sys.argv) > 1 else f'{HD}/dataset'
PROJ = json.load(open(f'{HD}/tools/projects.json'))


def blob_sha(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


for lab in glob.glob(f'{ROOT}/cases/**/label.json', recursive=True):
    sd = os.path.dirname(lab)
    meta = json.load(open(f'{sd}/meta.json'))
    if meta['project'] not in PROJ or (meta.get('provenance') or {}).get('dataset'):
        continue
    repo = f"{HD}/repos/{PROJ[meta['project']]['repo']}"
    h = meta['harness']
    hf = set(h['files'] + h.get('aux_files', [])) if h['kind'] == 'intree' else set()
    out = subprocess.run(['git', '-C', repo, 'ls-tree', '-r', '-z', meta['M']], capture_output=True).stdout
    fixed = 0
    for ent in out.split(b'\0'):
        if not ent:
            continue
        m, p = ent.split(b'\t', 1)
        mode, typ, sha = m.decode().split()
        p = p.decode('utf-8', 'surrogateescape')
        if typ != 'blob' or mode == '120000' or p in hf:
            continue
        dst = f'{sd}/input/source/{p}'
        cur = open(dst, 'rb').read() if os.path.isfile(dst) and not os.path.islink(dst) else None
        if cur is None or blob_sha(cur) != sha:
            data = subprocess.run(['git', '-C', repo, 'cat-file', 'blob', sha], capture_output=True).stdout
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(data)
            os.chmod(dst, 0o755 if mode == '100755' else 0o644)
            fixed += 1
    got = {}
    for dp, dn, fn in os.walk(f'{sd}/input/source'):
        for fl in fn:
            pth = os.path.join(dp, fl)
            if os.path.islink(pth):
                continue
            got[os.path.relpath(pth, f'{sd}/input/source')] = blob_sha(open(pth, 'rb').read())
    json.dump(got, open(f'{sd}/verification/source_blobs.json', 'w'), indent=0, sort_keys=True, ensure_ascii=False)
    print(f"{os.path.basename(sd)}: rewrote {fixed} files")
