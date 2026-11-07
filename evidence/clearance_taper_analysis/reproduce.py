"""Measure depth-cut taper on an attached 20 mm square relief, without editing source."""
import json
import sys
from pathlib import Path

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.geometry_material import slice_mesh_by_material

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.scale_length = 1.0
vertices = []
for half, z in ((15, -5), (15, 0), (10, 0), (10, 3)):
    vertices.extend((x / 1000, y / 1000, z / 1000)
                    for x, y in ((-half, -half), (half, -half), (half, half), (-half, half)))
faces = [(3, 2, 1, 0)]
for ring in range(3):
    for i in range(4):
        j = (i + 1) % 4
        faces.append((ring * 4 + i, ring * 4 + j, (ring + 1) * 4 + j, (ring + 1) * 4 + i))
faces.append((12, 13, 14, 15))
mesh = bpy.data.meshes.new('SquareRelief')
mesh.from_pydata(vertices, [], faces)
for name in ('Body', 'Relief'):
    mesh.materials.append(bpy.data.materials.new(name))
for face in mesh.polygons:
    face.material_index = int(face.index >= 9)
bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new('SquareRelief', mesh)
bpy.context.scene.collection.objects.link(obj)
bpy.context.view_layer.update()

results = []
for apply_to in ('PART', 'CAVITY', 'BOTH'):
    for gap in (0., .1, 1.):
        result = slice_mesh_by_material(obj, 1, depth_mm=2., scene=bpy.context.scene,
                                       part_clearance_mm=gap, part_clearance_apply_to=apply_to)
        row = dict(apply_to=apply_to, clearance_mm=gap, sections=[])
        for side, part in zip(('A', 'B'), result):
            levels = {}
            for v in part.verts:
                # Exclude outside of receiver; measure the cavity square only.
                if max(abs(v.co.x), abs(v.co.y)) * 1000 > 11:
                    continue
                z = round(v.co.z * 1000, 4)
                levels.setdefault(z, []).append(v.co.x * 1000)
            row['sections'].append(dict(side=side, widths_mm={z: round(max(xs) - min(xs), 5) for z, xs in sorted(levels.items())},
                                        manifold=all(e.is_manifold for e in part.edges)))
            part.free()
        results.append(row)
print('TAPER_MEASUREMENTS=' + json.dumps(results))
Path(__file__).with_name('measurements.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
