#!/usr/bin/env python3
"""Index upstream reports without producing maintenance labels or local alerts."""
from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
import argparse,csv,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
class Conclusions(HTMLParser):
 def __init__(self):super().__init__();self.level=0;self.parts=[];self.items=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag=='div':
   if self.level:self.level+=1
   elif 'high-level-conclusion' in attrs.get('class','').split():self.level=1;self.parts=[]
 def handle_data(self,data):
  if self.level:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag=='div' and self.level:
   self.level-=1
   if not self.level:self.items.append(' '.join(' '.join(self.parts).split()))
def read(p):return json.loads(p.read_text()) if p.is_file() else None
def relative(p):return str(p.relative_to(ROOT))
def collect(folder):
 if (folder/'superseded.txt').is_file():return None
 launch=read(folder/'launch.json');done=read(folder/'completed.json')
 if not launch or not done:return None
 case=read(ROOT/launch['project_context']/'case.json')
 full=folder/'official-report/introspector-report/inspector'
 fallback=folder/'official-report/introspector-only'
 report=full if (full/'summary.json').is_file() else fallback
 summary=read(report/'summary.json')
 phases={}
 for p in (folder/'build-status').glob('official-build-status-*.json'):
  d=read(p);phases[d['sanitizer']]=d
 data={'run_folder':relative(folder),'case_id':case['id'],'project':case['project'],'harness_target':case['harness_target'],**done,'build_phases':phases,'report_available':bool(summary and (report/'fuzz_report.html').is_file()),'native_report':relative(report/'fuzz_report.html') if (report/'fuzz_report.html').is_file() else None,'native_summary':relative(report/'summary.json') if summary else None,'native_project_stats':(summary or {}).get('MergedProjectProfile',{}).get('stats',{}),'native_profiles':{k:v for k,v in (summary or {}).items() if k not in ['MergedProjectProfile','analyses']},'native_high_level_conclusions':[],'native_blocked_conclusions':[],'runtime_error_summaries':[],'maintenance_prediction':None,'classification_metrics':None}
 if data['report_available']:
  parser=Conclusions();parser.feed((report/'fuzz_report.html').read_text(errors='replace'))
  data['native_high_level_conclusions']=parser.items
  data['native_blocked_conclusions']=[x for x in parser.items if re.search(r'^Fuzzer .+ is blocked:',x)]
  data['report_sha256']=hashlib.sha256((report/'fuzz_report.html').read_bytes()).hexdigest()
  data['summary_sha256']=hashlib.sha256((report/'summary.json').read_bytes()).hexdigest()
  data['native_branch_blockers_file']=relative(report/'branch-blockers.json') if (report/'branch-blockers.json').is_file() else None
 errors=set();compiler_errors=set();source_counts=set()
 pattern=re.compile(r'SUMMARY: AddressSanitizer:|ERROR: libFuzzer: (?:deadly signal|timeout|out-of-memory)')
 for name in ['helper.log','introspector-fallback.log']:
  p=folder/name
  if p.exists():
   with p.open(errors='replace') as stream:
    for line in stream:
     if pattern.search(line):errors.add(line.strip())
     if re.search(r'\b(?:fatal )?error:|undefined reference|cannot stat',line):compiler_errors.add(line.strip())
     count=re.search(r'Found (\d+) files to include in analysis',line)
     if count:source_counts.add(int(count.group(1)))
 data['runtime_error_summaries']=sorted(errors)
 data['compiler_error_messages']=sorted(compiler_errors)
 data['native_source_file_counts']=sorted(source_counts)
 return data

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',default='official-v9-final-20261114');ap.add_argument('--extra-runs',nargs='*',default=[]);args=ap.parse_args()
 folders=[ROOT/'experiment/runs'/x for x in [args.run,*args.extra_runs]]
 by_id={}
 for run in folders:
  for folder in sorted(run.glob('V3-*')):
   item=collect(folder)
   if item:by_id[item['case_id']]=item
 rows=[by_id[k] for k in sorted(by_id)]
 destination=ROOT/'experiment/results';destination.mkdir(exist_ok=True)
 (destination/'native-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 stats={'completed_samples':len(rows),'full_official_pipeline_success':sum(r['helper_exit']==0 for r in rows),'native_report_available':sum(r['report_available'] for r in rows),'successful_lto_introspector_build':sum(r['build_phases'].get('introspector',{}).get('compile_returncode')==0 for r in rows),'native_source_report_without_successful_lto':sum(r['report_available'] and r['build_phases'].get('introspector',{}).get('compile_returncode')!=0 for r in rows),'native_blocked_messages':sum(len(r['native_blocked_conclusions']) for r in rows),'cases_with_runtime_error_summary':sum(bool(r['runtime_error_summaries']) for r in rows),'maintenance_classification_metrics':None,'reason':'Upstream reports are not maintenance labels; no local mapping or classifier is applied.'}
 stats['cases_with_native_blocked_messages']=[r['case_id'] for r in rows if r['native_blocked_conclusions']]
 stats['cases_without_full_pipeline']=[r['case_id'] for r in rows if r['helper_exit']!=0]
 (destination/'run-summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
 fields=['elapsed_seconds','case_id','project','harness_target','full_pipeline_exit','asan_build_exit','coverage_build_exit','introspector_build_exit','native_report','native_profile_count','native_function_reach_percent','native_function_coverage_percent','native_target_cov_reach_percent','native_blocked_message_count']
 table=[]
 for r in rows:
  phases=r['build_phases'];s=r['native_project_stats'];p=r['native_profiles'].get(r['harness_target'],{})
  table.append({'elapsed_seconds':r['elapsed_seconds'],'case_id':r['case_id'],'project':r['project'],'harness_target':r['harness_target'],'full_pipeline_exit':r['helper_exit'],'asan_build_exit':phases.get('address',{}).get('compile_returncode'),'coverage_build_exit':phases.get('coverage',{}).get('compile_returncode'),'introspector_build_exit':phases.get('introspector',{}).get('compile_returncode'),'native_report':r['native_report'],'native_profile_count':s.get('harness-count'),'native_function_reach_percent':s.get('reached-function-percentage'),'native_function_coverage_percent':s.get('code-coverage-function-percentage'),'native_target_cov_reach_percent':p.get('coverage-blocker-stats',{}).get('cov-reach-proportion'),'native_blocked_message_count':len(r['native_blocked_conclusions'])})
 with (destination/'native-results.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(table)
 print(json.dumps(stats,ensure_ascii=False,indent=2))
 if len(rows)!=48:return
 report=['# Dataset-v9：官方 Fuzz Introspector 48 条重测报告','', '本轮运行官方工具原生流程，未使用 R_any、R_all、LLM、义务匹配或其他维护分类规则。主集 48 条逐条重新构建并运行；不纳入 extension。','', '## 官方版本与执行方式','', '官方 FI 源码固定提交 `341ebbd72bc9116733bcfcfab5adfd7f9b633e07`，与现有官方 OSS-Fuzz 镜像内的 LLVM pass 匹配；不是最新 main。官方 OSS-Fuzz helper 的提交及镜像 ID 见 [版本记录](experiment/provenance.json)。两个 upstream 仓库的已跟踪代码未修改。','', '使用官方 `helper.py introspector <project> --seconds=30`，依次执行 ASan 构建、运行 fuzzer、coverage 构建、覆盖率采集、FI 原生分析与报告。完整流程失败的样本另外调用官方 `build_fuzzers --sanitizer=introspector`，其原生源码分析报告单独保留。','', '数据集适配代码仅装载源码和旧 harness、选择构建目标及解决构建环境兼容，位于 `experiment/`，不是官方代码。具体差异和依赖环境见 [执行协议](experiment/PROTOCOL.md)。构建中间文件使用 Linux 临时目录以保留 POSIX 权限；下列报告、JSON 和日志已保存在本文件夹内。','', '## 总体运行结果','', '| 项目 | 数量 | 占 48 条比例 |','|---|---:|---:|']
 for key,title in [('full_official_pipeline_success','官方完整流程返回成功'),('successful_lto_introspector_build','官方 LTO introspector 构建成功'),('native_report_available','生成官方原生报告'),('native_source_report_without_successful_lto','仅有原生源码分析报告，LTO 未成功'),('cases_with_runtime_error_summary','原生日志包含运行错误摘要')]:
  report.append(f'| {title} | {stats[key]} | {stats[key]/48:.2%} |')
 report+=['', '这些比例是流程完成率或报告可用率，**不是维护检测准确率**。完整流程成功也不等于 fuzzer 从未崩溃：官方 helper 的语料准备允许 fuzzer 失败后继续。','', '**维护分类 Precision、Recall、FPR、FNR、F1：不适用（N/A）。** 官方没有直接对应“需要维护/不需要维护”的预测标签；将编译失败、覆盖率、blocked 或某类 blocker 映射到该标签，需要另加规则，本轮未做。','', '## 48 条逐条原生结果','', '构建列中 `0` 表示成功，非零为返回码，`—` 表示流程未运行到该阶段。函数可达率和函数覆盖率直接抄录官方 `MergedProjectProfile.stats`；源码分析报告可能包含多个 profile，不能把它当作指定 harness 的二分类结果。目标覆盖/可达比直接读取声明 target 的 `coverage-blocker-stats.cov-reach-proportion`，缺少该 profile 时标为 —。blocked 数量只计官方 HTML 中原样出现的提示，不进行本地阈值判断。','', '| 样本 | 项目 | 完整流程 | ASan / coverage / FI 构建返回码 | 原生 profile 数 | 原生函数可达率 | 原生函数覆盖率 | 目标覆盖/可达比 | 原生 blocked 提示数 | 官方报告 |','|---|---|---|---|---:|---:|---:|---:|---:|---|']
 fmt=lambda v:'—' if v is None else f'{v:.2f}%'
 for r,t in zip(rows,table):
  exits=' / '.join(str(t[k]) if t[k] is not None else '—' for k in ['asan_build_exit','coverage_build_exit','introspector_build_exit'])
  link=f'[HTML]({r["native_report"]})' if r['native_report'] else '未生成'
  report.append(f'| {r["case_id"]} | {r["project"]} | {"成功" if r["helper_exit"]==0 else "失败"} | {exits} | {t["native_profile_count"] if t["native_profile_count"] is not None else "—"} | {fmt(t["native_function_reach_percent"])} | {fmt(t["native_function_coverage_percent"])} | {fmt(t["native_target_cov_reach_percent"])} | {len(r["native_blocked_conclusions"]) if r["report_available"] else "—"} | {link} |')
 report+=['', '## 原生提示与结果解释','', f'官方 HTML 共包含 {stats["native_blocked_messages"]} 条 “Fuzzer … is blocked” 提示，可能分布于同一样本的多个 profile。原文及逐 profile 的 `coverage-blocker-stats` 已保留在 [原生结果 JSON](experiment/results/native-results.json)。没有出现提示，不代表 harness 被判定为不需要维护；缺少运行覆盖的源码分析报告也不能作此判断。','', '该官方版本用运行覆盖与静态可达范围的对比解释覆盖受阻，并提供 branch blocker 等信息。它分析的是 fuzzing 覆盖和阻塞，不直接证明旧 harness 与本次变更之间存在维护缺口，也不输出本次/非本次归因。','', '每个 fuzzer 按官方命令运行 30 秒；崩溃可能提前终止运行，随机种子保留在原生日志中。覆盖率受时间、随机语料和项目初始化条件影响。源码前端与 LTO 报告的函数范围不同，不能混为同一精度口径。','', '## 可复核文件','', '- [逐条 CSV](experiment/results/native-results.csv)、[逐条原生字段 JSON](experiment/results/native-results.json)、[总体运行统计](experiment/results/run-summary.json)。','- [FI 官方源码](upstream/fuzz-introspector/README.md)、[OSS-Fuzz 集成文档](upstream/oss-fuzz/docs/advanced-topics/fuzz_introspector.md)。','- 每条原始 helper 日志、构建状态和官方报告位于 `experiment/runs/`；完整输入包及 SHA-256 位于 `experiment/workspace/projects/`。','', '官方参考：[FI GitHub](https://github.com/ossf/fuzz-introspector)、[本地构建说明](https://github.com/ossf/fuzz-introspector/blob/341ebbd72bc9116733bcfcfab5adfd7f9b633e07/doc/LocalBuild.md)、[OSS-Fuzz 集成说明](https://github.com/google/oss-fuzz/blob/master/docs/advanced-topics/fuzz_introspector.md)。','']
 report+=['## 失败记录与独立重跑','', '最终逐条结果采用以下运行目录，后列目录仅替换其中实际完成的同编号样本：','', *['- `experiment/runs/'+x+'`' for x in [args.run,*args.extra_runs]], '', '修正构建适配后均重新执行完整官方命令，不复用先前的预测或覆盖率。重跑原因见相应目录的 `reason.txt`。', '', '| 未完成官方完整流程的样本 | 原始错误摘要 | 完整日志 |','|---|---|---|']
 for r in rows:
  if r['helper_exit']==0:continue
  errors='<br>'.join(x.replace('|','\\|') for x in [*r['runtime_error_summaries'],*r['compiler_error_messages']][:3]) or '见原始 helper 日志'
  report.append(f'| {r["case_id"]} | {errors} | [helper.log]({r["run_folder"]}/helper.log) |')
 report+=['', '源码报告中显示的 0% 运行覆盖，在未成功构建和执行的样本上表示没有运行覆盖数据，不能解释为已证实零覆盖。', '', '完整性核验结果见 [validation.json](experiment/results/validation.json)；底层证据及崩溃输入的哈希见 [native-evidence-manifest.json](experiment/results/native-evidence-manifest.json)。', '']
 report+=['## 耗时较长的样本','', '下表为最终采用的各次运行耗时，包含构建、语料生成、分析和报告保存。样本并行执行，不能将这些耗时之和当成本轮总墙钟时间。FI 阶段为官方 compile 的完整 introspector 阶段，也包括其源码分析。','', '| 样本 | 单样本总耗时（分钟） | FI 阶段耗时（分钟） |','|---|---:|---:|']
 for r in sorted(rows,key=lambda x:x['elapsed_seconds'],reverse=True)[:5]:
  fi=r['build_phases'].get('introspector',{}).get('elapsed_seconds')
  fi_text=f'{fi/60:.2f}' if fi is not None else '—'
  report.append(f'| {r["case_id"]} | {r["elapsed_seconds"]/60:.2f} | {fi_text} |')
 report.append('')
 (ROOT/'REPORT.md').write_text('\n'.join(report))
if __name__=='__main__':main()
