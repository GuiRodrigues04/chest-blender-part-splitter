"""Load the actual installed extension and exercise its five preview routes."""
import bpy,addon_utils,os,sys,zipfile,importlib,importlib.util
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
folder=Path(os.environ['APPDATA'])/'Blender Foundation/Blender/5.2/extensions/user_default/chest_part_splitter'
with zipfile.ZipFile(repo/'dist/chest_part_splitter-0.9.6.zip') as archive:
    for name in archive.namelist():
        if not name.endswith('/'):
            assert archive.read(name)==(folder/name).read_bytes(),name
addon=addon_utils.enable('bl_ext.user_default.chest_part_splitter',default_set=False)
assert addon is not None
assert importlib.import_module(addon.__name__+'.src.constants').ADDON_VERSION==(0,9,6)
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
print('INSTALLED_096_OK: exact ZIP bytes, real namespace, five preview routes, standard pin-free gap and safe fallback',flush=True)
