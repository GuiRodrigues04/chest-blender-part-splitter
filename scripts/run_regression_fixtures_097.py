import concurrent.futures, json, os, pathlib, re, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
BLENDER = pathlib.Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
FIXTURES = {
 'test_whole_region_material.py': ('SPLITTER_CAT_FIXTURE', r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\02_Personagens_e_Criaturas\Gato_Cinza\Teste Gato.blend'),
 'test_region_release.py': ('SPLITTER_CAT_FIXTURE', r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\02_Personagens_e_Criaturas\Gato_Cinza\Teste Gato.blend'),
 'test_plane_contact_contours.py': ('SPLITTER_PLATE_FIXTURE', r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\01_Placas_Chest\Placas_Versao_1_Inteiras\Blender\Placa_Chest\Placa Chest.blend'),
 'test_material_region_connectivity.py': ('SPLITTER_QR_FIXTURE', r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\01_Placas_Chest\Placas_Versao_1_Inteiras\Blender\Placa_QR_Inclinada\Placa_QR_Inclinada_Chest_V2_Inteira.blend'),
}
TARGETS = [('baseline', ROOT/'scratch'/'baseline097'), ('final', ROOT)]
def run_one(case):
    phase, target, suite = case
    source = target/'tests'/suite
    actual = source
    env = dict(os.environ, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', **{FIXTURES[suite][0]: FIXTURES[suite][1]})
    if suite == 'test_material_region_connectivity.py':
        env['SPLITTER_QR_OBJECT'] = 'Placa_QR_Inclinada_Chest_V2_Inteira'
        text = source.read_text(encoding='utf-8')
        text = text.replace('import sys,unittest', 'import os,sys,unittest')
        old_path = r"filename=Path(r'C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_QR_Inclinada_Chest_Inteira.blend')"
        new_path = "filename=Path(os.environ.get('SPLITTER_QR_FIXTURE', r'C:\\Users\\guiro\\OneDrive\\Desktop\\Placas - Modelos 3D\\Modelos_Chest\\Modelos Versão 1 - Placas Inteiras\\Blender\\Placa_QR_Inclinada_Chest_Inteira.blend'))"
        if old_path not in text:
            return dict(phase=phase,suite=suite,status='adapter_error',exit_code=None,seconds=0,tests_run=0,skips=0,errors=0,failures=0,detail='could not adapt hard-coded QR fixture path')
        text = text.replace(old_path,new_path)
        old_obj = "b.objects=['Placa_QR_Inclinada_Chest_Inteira']"
        new_obj = "b.objects=[os.environ.get('SPLITTER_QR_OBJECT','Placa_QR_Inclinada_Chest_Inteira')]"
        if old_obj not in text:
            return dict(phase=phase,suite=suite,status='adapter_error',exit_code=None,seconds=0,tests_run=0,skips=0,errors=0,failures=0,detail='could not adapt QR object name')
        text = text.replace(old_obj,new_obj)
        actual = target/'tests'/'_fixture_adapter_qr_connectivity.py'
        actual.write_text(text,encoding='utf-8')
    start=time.time()
    try:
        p=subprocess.run([str(BLENDER),'--background','--factory-startup','--python-exit-code','1','--python',str(actual)],cwd=str(target),env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        output=p.stdout or ''; code=p.returncode
    except subprocess.TimeoutExpired as e:
        output=(e.stdout or b'').decode(errors='replace') if isinstance(e.stdout,bytes) else (e.stdout or '')
        code=124
    finally:
        if actual != source:
            try: actual.unlink()
            except FileNotFoundError: pass
    logdir=ROOT/'evidence'/'0.9.7'/'fixture_logs'; logdir.mkdir(parents=True,exist_ok=True)
    (logdir/f'{phase}_{pathlib.Path(suite).stem}.log').write_text(output,encoding='utf-8',errors='replace')
    ran=re.findall(r'^Ran (\d+) tests? in ',output,re.M)
    skips=sum(map(int,re.findall(r'\((\d+) skipped\)',output)))+sum(map(int,re.findall(r'\bskipped=(\d+)\b',output)))
    failed=re.findall(r'^FAILED \((.*?)\)',output,re.M); errors=sum(map(int,re.findall(r'errors=(\d+)',failed[-1]))) if failed else 0; failures=sum(map(int,re.findall(r'failures=(\d+)',failed[-1]))) if failed else 0
    status='passed' if code==0 and re.search(r'^OK(?:\s|$)',output,re.M) else ('timeout' if code==124 else ('failed' if code!=0 or 'FAILED' in output else 'no_result'))
    return dict(phase=phase,suite=suite,status=status,exit_code=code,seconds=round(time.time()-start,2),tests_run=int(ran[-1]) if ran else 0,skips=skips,errors=errors,failures=failures,detail='')
def main():
    cases=[(phase,target,suite) for phase,target in TARGETS for suite in FIXTURES]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run_one,cases))
    report=dict(generated_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),blender=str(BLENDER),fixtures={k:v[1] for k,v in FIXTURES.items()},suite_runs=len(results),passed=sum(x['status']=='passed' for x in results),failed=sum(x['status']=='failed' for x in results),skipped=sum(x['skips'] for x in results),test_methods=sum(x['tests_run'] for x in results),errors=sum(x['errors'] for x in results),failures=sum(x['failures'] for x in results),results=results)
    out=ROOT/'evidence'/'0.9.7'/'regression_fixtures.json'; out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('suite_runs','passed','failed','skipped','test_methods','errors','failures')}))
    for r in results: print(f"{r['phase']:8} {r['status']:8} {r['suite']} ({r['tests_run']} tests; {r['skips']} skips; {r['errors']} errors; {r['failures']} failures; {r['seconds']}s)")
if __name__=='__main__': main()
