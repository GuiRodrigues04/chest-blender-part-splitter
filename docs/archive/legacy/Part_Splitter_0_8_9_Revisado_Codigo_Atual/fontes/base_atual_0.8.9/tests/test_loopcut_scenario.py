import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, ".")
from src.geometry_loop import slice_mesh_by_loop_extrude, slice_mesh_by_loop, analyze_loop_region

def test_loopcut():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    # Create cube 211mm
    bpy.ops.mesh.primitive_cube_add(size=0.211, location=(0, 0, 0))
    cube = bpy.context.active_object
    cube.name = "Cube211"

    # Enter edit mode and subdivide
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(cube.data)

    vertical_edges = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-4 and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-4]
    print(f"Vertical edges found: {len(vertical_edges)}")
    
    bmesh.ops.subdivide_edges(bm, edges=vertical_edges, cuts=1, use_grid_fill=True)
    bmesh.update_edit_mesh(cube.data)
    
    print(f"Total faces after subdivide: {len(bm.faces)}")
    for f in bm.faces:
        print(f"Face {f.index}: center={f.calc_center_median()}, normal={f.normal}")

    # Move the new loop vertices near the top face (say z = 0.10446, 1.04mm below top z=0.1055)
    for v in bm.verts:
        if abs(v.co.z) < 1e-4:
            v.co.z = 0.1055 - 0.00104 # 1.04mm below top
            v.select = True
        else:
            v.select = False
    
    bmesh.update_edit_mesh(cube.data)
    
    loop_verts = [v.index for v in bm.verts if v.select]
    print(f"Loop verts (1.04mm below top): {loop_verts}")

    top_faces = [f for f in bm.faces if f.normal.z > 0.9]
    seed_face_idx = top_faces[0].index
    print(f"Seed face index: {seed_face_idx}")

    bpy.ops.object.mode_set(mode='OBJECT')

    analysis = analyze_loop_region(cube, loop_verts, seed_face_idx, scene=scene)
    print("\nAnalysis:")
    for k, v in analysis.items():
        print(f"  {k}: {v}")

    print("\nTrying slice_mesh_by_loop (DETACH):")
    try:
        res = slice_mesh_by_loop(cube, cube.name, loop_verts, seed_face_idx, scene=scene)
        sr = res.split_result
        print(f"DETACH A vol: {sr.part_a_metrics.get('volume_mm3')}")
        print(f"DETACH B vol: {sr.part_b_metrics.get('volume_mm3')}")
    except Exception as e:
        import traceback
        traceback.print_exc()

    print("\nTrying slice_mesh_by_loop_extrude (EXTRUDE depth = 1.04 mm):")
    try:
        res = slice_mesh_by_loop_extrude(cube, cube.name, loop_verts, seed_face_idx, depth_mm=1.04, through_cut=False, scene=scene)
        sr = res.split_result
        print(f"EXTRUDE A vol: {sr.part_a_metrics.get('volume_mm3')}")
        print(f"EXTRUDE B vol: {sr.part_b_metrics.get('volume_mm3')}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_loopcut()
