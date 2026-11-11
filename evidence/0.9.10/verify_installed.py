"""Load the actual installed extension and exercise its five preview routes."""
import bpy,addon_utils,os,sys,zipfile,importlib,importlib.util
import hashlib
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
folder=Path(os.environ['APPDATA'])/'Blender Foundation/Blender/5.2/extensions/user_default/chest_part_splitter'
zip_path=repo/'dist/chest_part_splitter-0.9.10.zip'
assert hashlib.sha256(zip_path.read_bytes()).hexdigest().upper()=='E5BA22F63AB3C106016FB85CC4151B3878A1D523A80D5B280BCD512812FBAFF5'
with zipfile.ZipFile(zip_path) as archive:
    for name in archive.namelist():
        if not name.endswith('/'):
            assert archive.read(name)==(folder/name).read_bytes(),name
addon=addon_utils.enable('bl_ext.user_default.chest_part_splitter',default_set=False)
assert addon is not None
assert importlib.import_module(addon.__name__+'.src.constants').ADDON_VERSION==(0,9,10)
assert hasattr(bpy.types.Scene,'chest_splitter')
# The fixture resets factory preferences between cases. Register the same
# installed module directly so those resets do not unload its RNA classes.
addon_utils.disable(addon.__name__,default_set=False)
addon.register()
prefix=addon.__name__+'.src'
for name,module in list(sys.modules.items()):
    if name==prefix or name.startswith(prefix+'.'):
        sys.modules['src'+name[len(prefix):]]=module
sys.path.insert(0,str(repo/'tests'))
spec=importlib.util.spec_from_file_location('installed_cut_tests',repo/'tests/test_all_cut_topology.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
case=module.AllCutTopology()
case.test_five_methods_with_and_without_standard_gap()
case.test_odd_boundary_falls_back_for_every_method()
case.test_plane_ignores_inherited_contact_selection()
case.test_ring_hole_survives_fallback()
case.test_subdivided_square_ring_hole_survives_fallback()
print('INSTALLED_010_OK: exact ZIP bytes, real namespace, five preview routes, standard pin-free gap and safe fallback',flush=True)

import types, unittest
path=repo/'tests/test_connector_domain_sizing.py'
checks=types.ModuleType('installed_connector_checks');checks.__file__=str(path)
code=path.read_text(encoding='utf-8').replace('\nsrc.register()\n','\n')
exec(compile(code,str(path),'exec'),checks.__dict__)
result=unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(checks.ConnectorDomainSizing))
assert result.wasSuccessful()
print('INSTALLED_010_CONNECTORS_OK: centered/manual curved domain, sizing, units, holes, UV and custom values',flush=True)
path=repo/'tests/test_preview_uv_material.py'
checks=types.ModuleType('installed_uv_material_checks');checks.__file__=str(path)
code=path.read_text(encoding='utf-8')
exec(compile(code,str(path),'exec'),checks.__dict__)
result=unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(checks.PreviewUVMaterial))
assert result.wasSuccessful()
print('INSTALLED_010_UV_OK: two UV layers, seam corners, active render map, synthetic four-color sampling, surface/pin/bare/restore',flush=True)
