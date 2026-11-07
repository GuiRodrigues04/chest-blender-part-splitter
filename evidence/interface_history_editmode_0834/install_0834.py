"""Back up, install and verify the versioned extension without editing user scenes."""
from pathlib import Path
import hashlib
import importlib.util
import json
import runpy
import sys
import zipfile
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DEST = Path.home() / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/chest_part_splitter'
PACKAGE = ROOT / 'dist/chest_part_splitter-0.8.34.zip'
assert DEST.is_dir() and DEST.name == 'chest_part_splitter'
backup = ROOT / 'evidence/clearance_taper_analysis' / ('installed_before_0834_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.zip')
with zipfile.ZipFile(backup, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in DEST.rglob('*'):
        if path.is_file():
            archive.write(path, path.relative_to(DEST))
with zipfile.ZipFile(PACKAGE) as archive:
    for entry in archive.infolist():
        target = (DEST / entry.filename).resolve()
        assert target.is_relative_to(DEST.resolve())
    archive.extractall(DEST)
    for entry in archive.infolist():
        if not entry.is_dir():
            assert hashlib.sha256(archive.read(entry)).digest() == hashlib.sha256((DEST / entry.filename).read_bytes()).digest()
report = dict(version='0.8.34', package=str(PACKAGE), installation=str(DEST), backup=str(backup), all_package_files_match=True)
(ROOT / 'evidence/clearance_taper_analysis/installation_0834.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
spec = importlib.util.spec_from_file_location('installed_splitter', DEST / '__init__.py', submodule_search_locations=[str(DEST)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
assert addon.bl_info['version'] == (0,8,34)
assert addon.src.ui.PANEL_TITLE == 'Splitter 0.8.34'
sys.modules['src'] = addon.src
print('INSTALLATION_VERIFIED', json.dumps(report))
runpy.run_path(str(ROOT / 'tests/test_interface_history.py'), run_name='__main__')
