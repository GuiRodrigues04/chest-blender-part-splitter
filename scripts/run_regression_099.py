"""Run focused Blender regressions with separate immutable source and evidence target."""
import argparse, concurrent.futures, json, os, re, subprocess, sys, time
from pathlib import Path
BLENDER = r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
BASE_SUITES = ['test_release_depth_guard.py','test_release_depth_region.py','test_clearance_uniformity.py','test_natural_clearance.py','test_connector_domain_sizing.py','test_all_cut_topology.py','test_release_geometry.py','test_release_connector_frames.py','test_manual_connectors_workflow.py','test_interface_history.py','test_region_release.py','test_whole_region_material.py']
CURRENT_SUITES = BASE_SUITES + ['test_trim_depth_contact_band.py']
CAT = r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\02_Personagens_e_Criaturas\Gato_Cinza\Teste Gato.blend'
def run(suite, source, logs, timeout):
 env=os.environ.copy(); env['SPLITTER_CAT_FIXTURE']=CAT; started=time.monotonic()
 try:
  proc=subprocess.run([BLENDER,'--background','--factory-startup','--threads','2','--python-exit-code','1','--python',str(source/'tests'/suite)],cwd=source,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
  raw=proc.stdout.decode('utf-8','replace'); code,timed_out=proc.returncode,False
 except subprocess.TimeoutExpired as exc:
  output=exc.stdout or b''; raw=(output.decode('utf-8','replace') if isinstance(output,bytes) else output)+f'\nTIMEOUT after {timeout} seconds\n'; code,timed_out=124,True
 (logs/(Path(suite).stem+'.log')).write_text(raw,encoding='utf-8')
 summaries=re.findall(r'Ran (\d+) tests? in ([\d.]+)s',raw)
 counts={'tests':int(summaries[-1][0]) if summaries else None,'unittest_seconds':float(summaries[-1][1]) if summaries else None}
 for key,pattern in [('failures',r'failures=(\d+)'),('errors',r'errors=(\d+)'),('skipped',r'skipped=(\d+)')]:
  found=re.findall(pattern,raw); counts[key]=int(found[-1]) if found else 0
 counts['skip_lines']=re.findall(r'^\s*skipped\s+.+$',raw,re.M); counts['fail_lines']=re.findall(r'^FAIL:\s+.+$',raw,re.M)+re.findall(r'^ERROR:\s+.+$',raw,re.M)
 valid=bool(summaries) and 'OK' in raw
 return {'suite':suite,'exit_code':code,'passed':code==0 and valid and not counts['failures'] and not counts['errors'],'timeout':timed_out,'wall_seconds':round(time.monotonic()-started,2),**counts}
def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('--phase',choices=('baseline','current'),required=True); p.add_argument('--sourcedir',type=Path,required=True); p.add_argument('--targetdir',type=Path,required=True); p.add_argument('--timeout',type=int,default=600)
 argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]; a=p.parse_args(argv); source=a.sourcedir.resolve(); target=a.targetdir.resolve()
 for folder in ('src','tests'):
  if not (source/folder).is_dir(): p.error(f'--sourcedir must contain {folder}/: {source}')
 suites=BASE_SUITES if a.phase=='baseline' else CURRENT_SUITES; missing=[s for s in suites if not (source/'tests'/s).is_file()]
 if missing:p.error(f'missing suites in {source}: {missing}')
 out=target/'evidence'/'0.9.9'; logs=out/f'{a.phase}_logs'; logs.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda s:run(s,source,logs,a.timeout),suites))
 totals={'suites':len(results),'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results),'tests':sum(r['tests'] or 0 for r in results),'failures':sum(r['failures'] for r in results),'errors':sum(r['errors'] for r in results),'skipped':sum(r['skipped'] for r in results)}
 report={'phase':a.phase,'sourcedir':str(source),'targetdir':str(target),'blender':BLENDER,'fixture':CAT,'max_parallel_blender_processes':2,'suites':results,'totals':totals}; path=out/f'{a.phase}.json';path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(report,indent=2,ensure_ascii=False))
 if totals['failed']:raise SystemExit(1)
if __name__=='__main__':main()
