import concurrent.futures, json, os, pathlib, re, subprocess, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
BLENDER = pathlib.Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
SUITES = ['test_clearance_uniformity.py','test_inv_005_loop.py','test_loop_quad_caps.py','test_all_cut_topology.py','test_frame_regions.py','test_material_regions.py','test_whole_region_material.py','test_region_multicontact_091.py','test_plane_limited.py','test_plane_contact_contours.py','test_manual_connectors_workflow.py','test_connector_state_092.py','test_interface_history.py','test_history.py','test_release_geometry.py','test_release_state.py','test_release_interface.py','test_release_depth_region.py','test_release_depth_guard.py','test_release_workflows.py','test_release_connector_frames.py','test_material_region_connectivity.py','test_connector_clearance_slivers.py','test_loop_panel.py','test_plane_limited_pose.py','test_region_release.py','test_natural_clearance.py']
PASS_MARKERS = ('ALL_OK True', 'REAL_POSE_LIMITED_AND_CONNECTOR_PASS')
def main():
    phase = sys.argv[1]
    target = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv)>2 else (ROOT/'scratch'/'baseline097' if phase=='baseline' else ROOT)
    out = ROOT/'evidence'/'0.9.7'
    logs = out/(phase+'_logs')
    logs.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
    def run(name):
        path = target/'tests'/name
        if not path.exists():
            return dict(suite=name,status='missing',exit_code=None,seconds=0,tests_run=0,skips=0,errors=0,failures=0,detail='test file missing')
        started=time.time()
        try:
            p=subprocess.run([str(BLENDER),'--background','--factory-startup','--python-exit-code','1','--python',str(path)],cwd=str(target),env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            output=p.stdout or ''; code=p.returncode
            (logs/(path.stem+'.log')).write_text(output,encoding='utf-8',errors='replace')
            ran=re.findall(r'^Ran (\d+) tests? in ',output,re.M)
            skipped=sum(map(int,re.findall(r'\((\d+) skipped\)',output)))
            skipped+=sum(map(int,re.findall(r'\bskipped=(\d+)\b',output)))
            counts=re.findall(r'^FAILED \((.*?)\)',output,re.M)
            errors=sum(map(int,re.findall(r'errors=(\d+)',counts[-1]))) if counts else 0
            failures=sum(map(int,re.findall(r'failures=(\d+)',counts[-1]))) if counts else 0
            explicit=any(marker in output for marker in PASS_MARKERS)
            is_unittest_success=bool(re.search(r'^OK(?:\s|$)',output,re.M))
            status='passed' if code==0 and (is_unittest_success or explicit) else ('failed' if code!=0 or 'FAILED' in output else 'no_result')
            detail='Explicit standalone success marker observed.' if explicit and not is_unittest_success else ''
            return dict(suite=name,status=status,exit_code=code,seconds=round(time.time()-started,2),tests_run=int(ran[-1]) if ran else 0,skips=skipped,errors=errors,failures=failures,detail=detail)
        except subprocess.TimeoutExpired as e:
            output=(e.stdout or b'').decode(errors='replace') if isinstance(e.stdout,bytes) else (e.stdout or '')
            (logs/(path.stem+'.log')).write_text(output+'\nTIMEOUT after 180 seconds',encoding='utf-8',errors='replace')
            return dict(suite=name,status='timeout',exit_code=124,seconds=180,tests_run=0,skips=0,errors=0,failures=0,detail='180 second timeout')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,SUITES))
    summary=dict(phase=phase,version='0.9.6' if phase=='baseline' else '0.9.7',target=str(target),blender=str(BLENDER),generated_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),suite_count=len(results),passed=sum(x['status']=='passed' for x in results),failed=sum(x['status']=='failed' for x in results),no_result=sum(x['status']=='no_result' for x in results),timeouts=sum(x['status']=='timeout' for x in results),missing=sum(x['status']=='missing' for x in results),test_methods=sum(x['tests_run'] for x in results),skipped=sum(x['skips'] for x in results),subtest_errors=sum(x['errors'] for x in results),subtest_failures=sum(x['failures'] for x in results),results=results)
    (out/f'regression_{phase}.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('phase','suite_count','passed','failed','no_result','timeouts','missing','test_methods','skipped','subtest_errors','subtest_failures')}))
    for r in results: print(f"{r['status']:8} {r['suite']} ({r['seconds']}s, {r['tests_run']} tests, {r['skips']} skips, {r['errors']} errors, {r['failures']} failures)")
if __name__=='__main__': main()
