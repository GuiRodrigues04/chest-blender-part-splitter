import sys,json,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()));sys.path.insert(0,str(Path.cwd()/'tests'))
from test_release_depth_guard import make_horn_object
import bpy
from src import geometry_loop as gl
p=json.loads(Path('tests/fixtures/horn_region_private.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
o=make_horn_object(p)
try:
 r=gl.slice_mesh_by_loop(o,o.name,p['loop_vertex_indices'],p['seed_face_index'],detach_add_base=True,detach_base_depth_mm=5,part_clearance_mm=.15)
 print('DIRECT_OK',len(r[0].faces));[b.free() for b in r]
except Exception:traceback.print_exc()
