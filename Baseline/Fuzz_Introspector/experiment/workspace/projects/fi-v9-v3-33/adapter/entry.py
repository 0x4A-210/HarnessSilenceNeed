#!/usr/bin/env python3
"""Stage an immutable dataset snapshot, then invoke OSS-Fuzz's unmodified compile."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
P=Path
case=json.loads(P('/opt/case.json').read_text())
project=case['project'];target=case['harness_target'];sanitizer=os.environ['SANITIZER']
source_name={'nlohmann-json':'json','binutils-gas':'binutils-gdb'}.get(project,project)
for root in [P('/src'),P('/work')]:
 root.mkdir(exist_ok=True)
 for p in root.iterdir():
  if p.is_symlink() or p.is_file():p.unlink()
  else:shutil.rmtree(p)
P('/tmp/dataset-input').mkdir(exist_ok=True)
subprocess.run(['tar','-xf','/opt/input.tar','-C','/tmp/dataset-input'],check=True)
source=P('/src')/source_name
shutil.move('/tmp/dataset-input/source',source)
h=P('/tmp/dataset-input/harness')
for name in ['oss-fuzz','oss-fuzz-project']:
 if (h/name).is_dir():shutil.copytree(h/name,'/src',dirs_exist_ok=True)
overlays=[]
for p in h.rglob('*'):
 if not p.is_file():continue
 relative=p.relative_to(h)
 if relative.parts[0] in ['oss-fuzz','oss-fuzz-project','build']:continue
 dest=source/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);overlays.append(str(relative))
if case['harness_location']=='intree':
 for relative in case['harness_files']:
  p=h/relative
  if p.is_file():
   dest=source/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
   if relative not in overlays:overlays.append(relative)
 harness=source/case['harness_files'][0]
else:
 parts=P(case['harness_files'][0]).parts
 harness=P('/src')/P(*parts[2:])
 if not harness.is_file():harness=P('/src')/parts[-1]
 if project=='unbound':
  for p in P('/src').glob('*.c'):shutil.copy2(p,source/p.name)
# Windows-mounted dataset files lost POSIX execute bits. Restore executable
# script/binary formats; do not let dictionaries or JSON become fuzz targets.
for p in P('/src').rglob('*'):
 if not p.is_file():continue
 with p.open('rb') as stream:magic=stream.read(4)
 executable=magic.startswith(b'#!') or magic==b'\x7fELF' or p.suffix in ('.sh','.py') or p.name in ('configure','bootstrap','autogen.sh','buildconf')
 p.chmod(0o755 if executable else 0o644)
original=P('/tmp/dataset-input')/P(case['build_script']).relative_to('input')
shutil.copy2(original,'/src/dataset-build.sh')
shutil.copy2('/opt/adapter/build_target.sh','/src/build.sh')
flags=os.environ['CFLAGS']+' -gdwarf-4'
if project=='json-c':flags+=' -D_GNU_SOURCE -Wno-error=strict-prototypes'
if project=='libspng':flags+=' -fcommon'
os.environ.update(PROJECT=project,PROJECT_DIR=str(source),HARNESS_FILE=str(harness),HARNESS=str(h),TARGET=target,CFLAGS=flags,MAKEFLAGS='-j3',MFLAGS='-j3',CMAKE_BUILD_PARALLEL_LEVEL='3',CMAKE_POLICY_VERSION_MINIMUM='3.5')
# The official compile script creates sanitizer and coverage flags, FI setup,
# native light/LTO analyses, correlation, HTML and JSON reports.
old=P('/out')/target
if old.exists():old.unlink()
start=time.monotonic()
try:rc=subprocess.run(['/usr/local/bin/compile'],cwd=source).returncode
except KeyboardInterrupt:raise
record={'case_id':case['id'],'project':project,'target':target,'sanitizer':sanitizer,'compile_returncode':rc,'elapsed_seconds':round(time.monotonic()-start,2),'harness_sha256':hashlib.sha256(harness.read_bytes()).hexdigest(),'harness_path':str(harness),'overlays':overlays,'official_compile_sha256':hashlib.sha256(P('/usr/local/bin/compile').read_bytes()).hexdigest(),'fi_commit':subprocess.check_output(['git','-C','/fuzz-introspector','rev-parse','HEAD'],text=True).strip(),'target_is_elf':old.exists() and old.open('rb').read(4)==b'\x7fELF'}
P('/out/experiment-meta').mkdir(exist_ok=True)
P('/out/experiment-meta/official-build-status-'+sanitizer+'.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(rc)
