"""Run the selected Blender regression suites in separate processes."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

TESTS = [
    "tests/test_smoke_phase0.py",
    "tests/test_smoke_phase1.py",
    "tests/test_smoke_phase2.py",
    "tests/test_smoke_phase3.py",
    "tests/test_stress_phases0_3.py",
    "tests/test_phase3a_loop.py",
    "tests/test_multicolor_support.py",
    "tests/test_capsule_lateral_size.py",
    "tests/test_acceptance_etapa2.py",
    "tests/test_acceptance_etapa3.py",
    "tests/test_acceptance_etapa4.py",
    "tests/test_verify_bug_and_fix.py",
    "tests/test_acceptance_etapa5_ui.py",
    "tests/test_acceptance_etapa6_material.py",
    "tests/test_material_regions.py",
    "tests/test_acceptance_etapa7_delivery.py",
    "tests/test_final_plan_corrections.py",
    "tests/test_b01_b07.py",
    "tests/test_plan_086_commercial.py",
    "tests/test_reversion_086.py",
    "tests/test_plan_087.py",
    "tests/test_pos_testes_087.py",
    "tests/test_plan_088.py",
]

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
    if '--' in sys.argv:
        argv = sys.argv[sys.argv.index('--') + 1:]
    elif is_in_blender:
        argv = []
    else:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    if not args.blender:
        parser.error('Set --blender, BLENDER_BIN or add blender to PATH')
    for test in TESTS:
        path = ROOT / test
        if not path.is_file():
            raise FileNotFoundError(path)
        print(f'Running: {test}', flush=True)
        result = subprocess.run([args.blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(path)], cwd=ROOT)
        if result.returncode:
            raise SystemExit(result.returncode)
    print(f'Passed: {len(TESTS)}/{len(TESTS)} suites')

if __name__ == '__main__':
    main()
