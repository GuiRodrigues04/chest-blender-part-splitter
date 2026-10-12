"""Build a clean extension package with the Blender command line."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('__init__.py', 'blender_manifest.toml', 'LICENSE', 'README.md', 'CHANGELOG.md')

def prepare_stage(stage):
    for name in REQUIRED:
        source = ROOT / name
        if not source.is_file():
            raise FileNotFoundError(f'Missing required file: {name}')
        shutil.copy2(source, stage / name)
    shutil.copytree(ROOT / 'src', stage / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
    return tomllib.loads((stage / 'blender_manifest.toml').read_text(encoding='utf-8'))

def inspect_package(path):
    with zipfile.ZipFile(path) as package:
        names = set(package.namelist())
        if not set(REQUIRED).issubset(names):
            raise ValueError('Package is missing required root files')
        for name in names:
            member = Path(name)
            if member.is_absolute() or '..' in member.parts:
                raise ValueError(f'Invalid package path: {name}')
            if name not in REQUIRED and not name.startswith('src/'):
                raise ValueError(f'Unexpected package member: {name}')
            if '__pycache__' in member.parts or member.suffix in ('.pyc', '.pyo'):
                raise ValueError(f'Cache in package: {name}')
        if package.testzip() is not None:
            raise ValueError('Corrupted package')

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
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='stage_', dir=dist) as temporary:
        work = Path(temporary)
        stage = work / 'source'
        stage.mkdir()
        manifest = prepare_stage(stage)
        candidate = work / f"{manifest['id']}-{manifest['version']}.zip"
        subprocess.run([args.blender, '--command', 'extension', 'validate', str(stage)], check=True)
        subprocess.run([args.blender, '--command', 'extension', 'build', '--source-dir', str(stage), '--output-filepath', str(candidate)], check=True)
        inspect_package(candidate)
        subprocess.run([args.blender, '--command', 'extension', 'validate', str(candidate)], check=True)
        destination = dist / candidate.name
        os.replace(candidate, destination)
        print(f'Package: {destination}')

if __name__ == '__main__':
    main()
