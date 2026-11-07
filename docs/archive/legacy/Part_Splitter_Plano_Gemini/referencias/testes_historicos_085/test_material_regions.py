import sys, os
sys.path.insert(0, os.getcwd())
import bpy, bmesh
from mathutils import Vector
import src.properties as properties
import src.operators as operators
properties.register(); operators.register()
bpy.ops.wm.read_homefile(use_empty=True)
scene = bpy.context.scene
s = scene.chest_splitter

# Cubo subdividido 4x4 por face, como na captura do usuário
bpy.ops.mesh.primitive_cube_add(size=0.2936)
cube = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=3)
bpy.ops.object.mode_set(mode='OBJECT')
m0 = bpy.data.materials.new("Material"); m1 = bpy.data.materials.new("Material.001")
cube.data.materials.append(m0); cube.data.materials.append(m1)
bm = bmesh.new(); bm.from_mesh(cube.data); bm.faces.ensure_lookup_table()
h = 0.2936 / 2
# Patch 1: face -Y, uma face próxima ao centro (x>0, z<0)
fy = [f for f in bm.faces if f.normal.y < -0.9]
p1 = min(fy, key=lambda f: (f.calc_center_median() - Vector((0.04, -h, -0.04))).length)
p1.material_index = 1
# Patch 2: face -X, duas faces adjacentes
fx = [f for f in bm.faces if f.normal.x < -0.9]
fx.sort(key=lambda f: (f.calc_center_median() - Vector((-h, -0.07, 0.04))).length)
fx[0].material_index = 1
fx[1].material_index = 1
bm.to_mesh(cube.data); bm.free()

s.target_object = cube
s.split_mode = 'MATERIAL'
bpy.ops.chest.splitter_select_split_material(material_index=1, region_index=0)
print("SEL", s.material_split_index, s.material_region_index)
from src.geometry_material import list_material_regions, analyze_material_structure
print("REGIONS", list_material_regions(cube, 1))
print("BASE", analyze_material_structure(cube, 0).get("error"))

from src.constants import PREVIEW_A_NAME, PREVIEW_B_NAME
ok = True
for r in range(2):
    s.material_region_index = r
    s.view_mode = 'EXPLODED'
    res = bpy.ops.chest.splitter_generate_preview()
    a = bpy.data.objects[PREVIEW_A_NAME]; b = bpy.data.objects[PREVIEW_B_NAME]
    an = analyze_material_structure(cube, 1, r)
    print("REGION", r, res, s.session_status, "type", an["type"], "inward", tuple(round(x, 3) for x in an["inward_dir_world"]))
    print("  A manifold", s.part_a_is_manifold, "B manifold", s.part_b_is_manifold, "volA", round(s.part_a_volume_mm3), "diff%", round(s.volume_diff_pct, 3))
    print("  locA", tuple(round(x*1000, 1) for x in a.location), "locB", tuple(round(x*1000, 1) for x in b.location), "explode", s.explosion_distance_mm)
    sep = (a.location - b.location)
    ok &= s.part_a_is_manifold and s.part_b_is_manifold and sep.dot(an["inward_dir_world"]) < 0 and abs(s.part_a_volume_mm3 - 0) > 1
    cube.hide_viewport = False
print("ALL_OK", ok)
sys.exit(0 if ok else 1)
