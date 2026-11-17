#!/usr/bin/env python3
"""Dataset orchestration only. Every analysis is performed by upstream helper.py."""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,os,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
DATASET=ROOT.parent/'Dataset-v9/Dataset-v9/dataset'
WORKSPACE=ROOT/'experiment/workspace'
HELPER=ROOT/'upstream/oss-fuzz/infra/helper.py'
def write(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def cases():
 root=DATASET/'cases'
 return sorted([(p,json.loads(p.read_text())) for p in [*root.glob('positive/*/*/*/*/case.json'),*root.glob('negative/*/*/*/case.json')]],key=lambda x:x[1]['id'])
def stage(path,case,prefix):
 name=prefix+'-'+case['id'].lower();folder=WORKSPACE/'projects'/name
 if folder.exists():
  manifest=json.loads((folder/'input-manifest.json').read_text())
  if manifest['case_sha256']!=hashlib.sha256(path.read_bytes()).hexdigest():raise ValueError('existing input context mismatch')
  return name,folder
 folder.mkdir(parents=True,exist_ok=False)
 write(folder/'case.json',case)
 shutil.copytree(ROOT/'experiment/adapter',folder/'adapter',ignore=shutil.ignore_patterns('__pycache__','Dockerfile.environment'))
 with (folder/'input.tar').open('wb') as output:
  subprocess.run(['tar','-cf','-','-C',str(path.parent/'input'),'.'],stdout=output,check=True)
 write(folder/'input-manifest.json',{'case_id':case['id'],'input_tar_sha256':hashlib.sha256((folder/'input.tar').read_bytes()).hexdigest(),'case_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'labels_mounted':False})
 (folder/'project.yaml').write_text('language: c++\nfuzzing_engines:\n  - libfuzzer\nsanitizers:\n  - address\n  - coverage\n  - introspector\n')
 (folder/'Dockerfile').write_text('FROM fi-official-v9-environment:20261114\nCOPY input.tar /opt/input.tar\nCOPY case.json /opt/case.json\nCOPY adapter /opt/adapter\nWORKDIR /src\nCMD ["python3", "/opt/adapter/entry.py"]\n')
 return name,folder
def run_one(item,run,prefix,seconds,no_fallback=False):
 path,case=item;out=run/case['id'];out.mkdir(parents=True,exist_ok=False)
 start=time.monotonic();print('STAGING '+case['id'],flush=True)
 name,folder=stage(path,case,prefix)
 # Native builds use a temporary POSIX filesystem. This preserves executable
 # bits required by upstream fuzzer discovery; final reports are copied back.
 native=Path('/tmp/fi-official-v9-build')/run.name/name
 for sub in ['out','work','corpus']:
  destination=native/sub;destination.mkdir(parents=True,exist_ok=True)
  link=WORKSPACE/'build'/sub/name;link.parent.mkdir(parents=True,exist_ok=True)
  if link.is_symlink() and str(link.resolve()).startswith('/tmp/fi-official-v9-build/'):
   link.unlink()
  elif link.exists():raise ValueError('native build directory already exists: '+str(link))
  link.symlink_to(destination,target_is_directory=True)
 env={**os.environ,'OSS_FUZZ_DIR':str(WORKSPACE),'PYTHONUNBUFFERED':'1'}
 cmd=['python3',str(HELPER),'introspector',name,'--seconds='+str(seconds),'--out',str(out/'official-report')]
 write(out/'launch.json',{'command':cmd,'project_name':name,'case_id':case['id'],'project_context':str(folder.relative_to(ROOT)),'started':time.strftime('%Y-%m-%dT%H:%M:%S%z')})
 with (out/'helper.log').open('w') as log:
  rc=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
 fallback=None
 if rc!=0 and not no_fallback:
  command=['python3',str(HELPER),'build_fuzzers','--sanitizer=introspector',name]
  write(out/'fallback-launch.json',{'command':command,'reason':'Full upstream pipeline failed; separately attempt the official introspector build, preserving its native light/LTO output.'})
  with (out/'introspector-fallback.log').open('w') as log:
   fallback=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
 native_out=WORKSPACE/'build/out'/name
 for source_name,dest_name in [('experiment-meta','build-status'),('logs','coverage-logs'),('textcov_reports','textcov_reports'),('fuzzer_stats','fuzzer_stats')]:
  source=native_out/source_name
  if source.is_dir():shutil.copytree(source,out/dest_name,dirs_exist_ok=True)
 if rc!=0 and (native_out/'inspector').is_dir():
  shutil.copytree(native_out/'inspector',out/'official-report/introspector-only',dirs_exist_ok=True)
 record={'case_id':case['id'],'project_name':name,'helper_exit':rc,'fallback_introspector_exit':fallback,'elapsed_seconds':round(time.monotonic()-start,2),'official_out':str((WORKSPACE/'build/out'/name).relative_to(ROOT))}
 write(out/'completed.json',record);print(json.dumps(record),flush=True)
 return record
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--prefix',required=True);ap.add_argument('--cases',nargs='*');ap.add_argument('--workers',type=int,default=2);ap.add_argument('--seconds',type=int,default=30);ap.add_argument('--no-fallback',action='store_true',help='Preserve a failed full run without automatically rebuilding introspector.');args=ap.parse_args()
 run=ROOT/'experiment/runs'/args.run;run.mkdir(parents=True,exist_ok=False)
 selected=[x for x in cases() if not args.cases or x[1]['id'] in args.cases]
 write(run/'run.json',{'cases':[c['id'] for _,c in selected],'seconds_per_target':args.seconds,'official_fi_commit':subprocess.check_output(['git','-C',str(ROOT/'upstream/fuzz-introspector'),'rev-parse','HEAD'],text=True).strip(),'official_oss_fuzz_commit':subprocess.check_output(['git','-C',str(ROOT/'upstream/oss-fuzz'),'rev-parse','HEAD'],text=True).strip(),'local_classifier':False,'automatic_introspector_fallback':not args.no_fallback})
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
  for result in concurrent.futures.as_completed([pool.submit(run_one,x,run,args.prefix,args.seconds,args.no_fallback) for x in selected]):result.result()
 print('ALL CASES COMPLETED',flush=True)
