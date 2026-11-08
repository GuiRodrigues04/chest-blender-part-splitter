"""Run the focused Blender regression suites against an explicit checkout."""
import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BLENDER = r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
BASE_SUITES = [
    'test_loop_quad_caps.py', 'test_all_cut_topology.py',
    'test_natural_clearance.py', 'test_clearance_uniformity.py',
    'test_release_geometry.py', 'test_release_interface.py',
    'test_release_connector_frames.py', 'test_manual_connectors_workflow.py',
    'test_interface_history.py', 'test_connector_state_092.py',
    'test_region_release.py', 'test_whole_region_material.py',
]
CURRENT_SUITES = BASE_SUITES + ['test_connector_domain_sizing.py']
CAT = r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\02_Personagens_e_Criaturas\Gato_Cinza\Teste Gato.blend'

def run(suite, target, logs, timeout):
    env = os.environ.copy()
    env['SPLITTER_CAT_FIXTURE'] = CAT
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [BLENDER, '--background', '--factory-startup', '--threads', '2',
             '--python-exit-code', '1', '--python', str(target / 'tests' / suite)],
            cwd=target, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout)
        raw = proc.stdout.decode('utf-8', 'replace')
        code, timed_out = proc.returncode, False
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or b''
        raw = (output.decode('utf-8', 'replace') if isinstance(output, bytes) else output)
        raw += f'\nTIMEOUT after {timeout} seconds\n'
        code, timed_out = 124, True
    (logs / (Path(suite).stem + '.log')).write_text(raw, encoding='utf-8')
    summaries = re.findall(r'Ran (\d+) tests? in ([\d.]+)s', raw)
    counts = {
        'tests': int(summaries[-1][0]) if summaries else None,
        'unittest_seconds': float(summaries[-1][1]) if summaries else None,
    }
    for key, pattern in [('failures', r'failures=(\d+)'),
                         ('errors', r'errors=(\d+)'), ('skipped', r'skipped=(\d+)')]:
        found = re.findall(pattern, raw)
        counts[key] = int(found[-1]) if found else 0
    counts['skip_lines'] = re.findall(r'^\s*skipped\s+.+$', raw, re.M)
    counts['fail_lines'] = (re.findall(r'^FAIL:\s+.+$', raw, re.M)
                            + re.findall(r'^ERROR:\s+.+$', raw, re.M))
    valid_summary = bool(summaries) and 'OK' in raw
    return {
        'suite': suite, 'exit_code': code,
        'passed': code == 0 and valid_summary and not counts['failures'] and not counts['errors'],
        'timeout': timed_out, 'wall_seconds': round(time.monotonic() - started, 2), **counts,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('baseline', 'current'), required=True)
    parser.add_argument('--targetdir', type=Path, required=True,
                        help='Checkout containing src/ and tests/')
    parser.add_argument('--timeout', type=int, default=600)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    target = args.targetdir.resolve()
    if not (target / 'src').is_dir() or not (target / 'tests').is_dir():
        parser.error(f'--targetdir must contain src/ and tests/: {target}')
    suites = BASE_SUITES if args.phase == 'baseline' else CURRENT_SUITES
    missing = [suite for suite in suites if not (target / 'tests' / suite).is_file()]
    if missing:
        parser.error(f'missing suites in {target}: {missing}')
    out = target / 'evidence' / '0.9.8'
    logs = out / f'{args.phase}_logs'
    logs.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda suite: run(suite, target, logs, args.timeout), suites))
    totals = {
        'suites': len(results), 'passed': sum(row['passed'] for row in results),
        'failed': sum(not row['passed'] for row in results),
        'tests': sum(row['tests'] or 0 for row in results),
        'failures': sum(row['failures'] for row in results),
        'errors': sum(row['errors'] for row in results),
        'skipped': sum(row['skipped'] for row in results),
    }
    report = {
        'phase': args.phase, 'targetdir': str(target), 'blender': BLENDER,
        'fixture': CAT, 'max_parallel_blender_processes': 2,
        'suites': results, 'totals': totals,
    }
    report_path = out / f'{args.phase}.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if totals['failed']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
