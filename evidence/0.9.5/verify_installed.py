"""Verify the installed ZIP bytes, namespace registration and actual Spot cut."""
import bpy,addon_utils,os,sys,zipfile,importlib
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
folder=Path(os.environ['APPDATA'])/'Blender Foundation/Blender/5.2/extensions/user_default/chest_part_splitter'
with zipfile.ZipFile(repo/'dist/chest_part_splitter-0.9.5.zip') as archive:
    for name in archive.namelist():
        if not name.endswith('/'):
            assert archive.read(name)==(folder/name).read_bytes(),name
addon=addon_utils.enable('bl_ext.user_default.chest_part_splitter',default_set=False)
assert addon is not None
assert importlib.import_module(addon.__name__+'.src.constants').ADDON_VERSION==(0,9,5)
assert hasattr(bpy.types.Scene,'chest_splitter')
geometry=importlib.import_module(addon.__name__+'.src.geometry_loop')
bpy.ops.wm.open_mainfile(filepath=str(Path(os.environ['USERPROFILE'])/'OneDrive/Desktop/Vaquinha.blend'))
if bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
obj=bpy.data.objects['spot_quadrangulated']
indices=[424,1648,425,1641,423,1659,427,1653,426,1669,429,1663,428,1677,430,1672]
parts=geometry.slice_mesh_by_loop(obj,obj.name,indices,958,bpy.context.scene,part_clearance_mm=.1)
try:
    for mesh in parts:
        layer=mesh.faces.layers.int.get('splitter_contact_surface')
        assert sum(len(f.verts)==4 for f in mesh.faces if f[layer])==16
        assert all(e.is_manifold for e in mesh.edges)
finally:
    for mesh in parts:mesh.free()
print('INSTALLED_095_OK: package bytes, extension namespace, registration, Spot 0.1 mm and closed quad caps',flush=True)
