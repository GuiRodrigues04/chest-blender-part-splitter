import sys
import bpy
import bmesh
from mathutils import Vector

# Import local src
sys.path.insert(0, ".")
from src.geometry_loop import slice_mesh_by_loop_extrude, analyze_loop_region

def test_reproduce():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0 # 1 BU = 1 m = 1000 mm

    # Create cube of 211 mm = 0.211 m
    size_bu = 0.211
    bpy.ops.mesh.primitive_cube_add(size=size_bu, location=(0, 0, 0))
    cube = bpy.context.active_object
    cube.name = "TestCube"

    # Let's inspect cube faces and vertices
    bm = bmesh.new()
    bm.from_mesh(cube.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Pick top face (normal = 0, 0, 1)
    top_face = None
    for f in bm.faces:
        if f.normal.z > 0.9:
            top_face = f
            break
    
    loop_verts = [v.index for v in top_face.verts]
    seed_face_idx = top_face.index
    print(f"Selected loop verts: {loop_verts}, seed face: {seed_face_idx}")

    analysis = analyze_loop_region(cube, loop_verts, seed_face_idx, scene=scene)
    print("Analysis result:")
    for k, v in analysis.items():
        print(f"  {k}: {v}")

    # Try extrude with 1.04 mm
    print("\n--- Running slice_mesh_by_loop_extrude (depth = 1.04 mm) ---")
    try:
        res = slice_mesh_by_loop_extrude(
            obj=cube,
            target_name="TestCube",
            indices=loop_verts,
            seed_face_idx=seed_face_idx,
            depth_mm=1.04,
            through_cut=False,
            scene=scene,
        )
        sr = res.split_result
        print(f"Result A metrics: {sr.part_a_metrics}")
        print(f"Result B metrics: {sr.part_b_metrics}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_reproduce()
