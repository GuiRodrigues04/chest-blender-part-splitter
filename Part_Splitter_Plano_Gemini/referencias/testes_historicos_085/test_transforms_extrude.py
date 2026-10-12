import sys
import bpy
import bmesh
from mathutils import Vector, Euler

sys.path.insert(0, ".")
from src.geometry_loop import slice_mesh_by_loop_extrude

def test_transforms():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    # Test 1: Cube moved to (0.5, 0.5, 0.5) with unapplied location, rotation and scale
    bpy.ops.mesh.primitive_cube_add(size=0.211, location=(0.5, -0.3, 0.2))
    cube = bpy.context.active_object
    cube.rotation_euler = Euler((0.2, 0.4, 0.1))
    cube.scale = Vector((1.2, 0.8, 1.5))
    bpy.context.view_layer.update()

    top_face_idx = 5
    loop_verts = [7, 3, 1, 5]

    print("Testing transformed cube:")
    print("Matrix world:", cube.matrix_world)
    try:
        res = slice_mesh_by_loop_extrude(cube, cube.name, loop_verts, top_face_idx, depth_mm=1.04, through_cut=False, scene=scene)
        sr = res.split_result
        print(f"Transformed: A vol = {sr.part_a_metrics.get('volume_mm3')}, B vol = {sr.part_b_metrics.get('volume_mm3')}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_transforms()
