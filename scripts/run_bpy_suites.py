import concurrent.futures, subprocess, pathlib, sys, os, json, time
root=pathlib.Path(sys.argv[1]).resolve(); dest=pathlib.Path(sys.argv[2]); dest.mkdir(exist_ok=True)
wrapper=pathlib.Path(__file__).with_name("bpy_script.py").resolve()
tests=sorted((root/'tests').glob('test_*.py'))
def run(p):
 start=time.time(); env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
 try:
  r=subprocess.run([sys.executable,str(wrapper),str(p)],capture_output=True,text=True,timeout=120,env=env,cwd=root)
  log=r.stdout+r.stderr; code=r.returncode
 except subprocess.TimeoutExpired as e:
  log=(e.stdout or b'').decode()+(e.stderr or b'').decode()+'\nTIMEOUT'; code=124
 (dest/(p.stem+'.log')).write_text(log)
 return {'suite':p.name,'exit_code':code,'seconds':round(time.time()-start,2)}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 results=list(pool.map(run,tests))
(dest/'summary.json').write_text(json.dumps(results,indent=2))
for r in results:print(r,flush=True)
