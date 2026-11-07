"""Run the selected Blender regression suites in separate processes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

TESTS = [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'tests').glob('test_*.py'))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    is_in_blender = 'bpy' in sys.modules
    default_bin = os.environ.get('BLENDER_BIN') or shutil.which('blender')
    if not default_bin:
        if is_in_blender:
            import bpy
            default_bin = bpy.app.binary_path
        else:
            win_blender = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
            if os.path.exists(win_blender):
                default_bin = win_blender

    parser.add_argument('--blender', default=default_bin)
    parser.add_argument('--suite', action='append', help='Test filename; repeat to select suites')
    parser.add_argument('--report-dir', type=Path, help='Save each process log and summary.json')
    parser.add_argument('--timeout', type=float, default=180, help='Seconds allowed per suite')
    if '--' in sys.argv:
        argv = sys.argv[sys.argv.index('--') + 1:]
    elif is_in_blender:
        argv = []
    else:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    if not args.blender:
        parser.error('Set --blender, BLENDER_BIN or add blender to PATH')
    tests = [str(Path('tests') / name) for name in args.suite] if args.suite else TESTS
    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for test in tests:
        path = ROOT / test
        if not path.is_file() or path.resolve().parent != (ROOT / 'tests').resolve():
            raise FileNotFoundError(path)
        print(f'Running: {test}', flush=True)
        start = time.monotonic()
        try:
            result = subprocess.run(
                [args.blender, '--background', '--factory-startup', '--threads', '2',
                 '--python-exit-code', '1', '--python', str(path)], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=args.timeout)
            output, code = result.stdout, result.returncode
        except subprocess.TimeoutExpired as exc:
            output, code = (exc.stdout or b'') + b'\nTIMEOUT\n', 124
        log = output.decode('utf-8', errors='replace')
        if args.report_dir:
            (args.report_dir / (path.stem + '.log')).write_text(log, encoding='utf-8')
        else:
            print(log)
        results.append(dict(suite=path.name, exit_code=code, seconds=round(time.monotonic()-start, 2)))
        print(f'{path.name}: exit {code}', flush=True)
    if args.report_dir:
        (args.report_dir / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    passed = sum(r['exit_code'] == 0 for r in results)
    print(f'Passed: {passed}/{len(results)} suites')
    if passed != len(results):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
