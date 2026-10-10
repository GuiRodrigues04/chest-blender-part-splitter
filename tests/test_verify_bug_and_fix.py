import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, ".")

def test_sequence():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import src
    src.register()

    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    bpy.ops.mesh.primitive_cube_add(size=0.211, location=(0, 0, 0))
    cube = bpy.context.active_object
    cube.name = "Cube211"

    bpy.ops.chest.splitter_set_target()
    settings = scene.chest_splitter

    # Edit mode setup
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(cube.data)
    for e in bm.edges: e.select = False
    for v in bm.verts: v.select = False
    for f in bm.faces: f.select = False

    top_face = [f for f in bm.faces if f.normal.z > 0.9][0]
    for e in top_face.edges: e.select = True
    bmesh.update_edit_mesh(cube.data)

    bpy.ops.chest.splitter_capture_loop()

    for e in bm.edges: e.select = False
    top_face.select = True
    bmesh.update_edit_mesh(cube.data)
    bpy.ops.chest.splitter_define_seed_face()

    bpy.ops.object.mode_set(mode='OBJECT')

    settings.split_mode = 'LOOP'
    settings.loop_behavior = 'EXTRUDE'
    settings.loop_extrude_depth_mm = 50.0 # First test with 50mm
    settings.loop_through_cut = False

    print("\n--- FIRST RUN of generate_preview ---")
    bpy.ops.chest.splitter_generate_preview()
    print("Run 1: Target hide_viewport:", cube.hide_viewport)
    print("Run 1: Parte A vol:", settings.part_a_volume_mm3)
    print("Run 1: Parte B vol:", settings.part_b_volume_mm3)

    print("\n--- SECOND RUN of generate_preview (user changes depth to 1.04 mm) ---")
    settings.loop_extrude_depth_mm = 1.04
    bpy.ops.chest.splitter_generate_preview()
    print("Run 2: Target hide_viewport:", cube.hide_viewport)
    print("Run 2: Parte A vol:", settings.part_a_volume_mm3)
    print("Run 2: Parte B vol:", settings.part_b_volume_mm3)
    print("Run 2: Parte A dims:", settings.part_a_dims_mm)
    print("Run 2: Parte B dims:", settings.part_b_dims_mm)

    assert cube.hide_viewport is True, "Target should be hidden in viewport after preview"
    assert 40000 < settings.part_a_volume_mm3 < 55000, f"Expected Parte A ~46302 mm3, got {settings.part_a_volume_mm3}"
    assert 9300000 < settings.part_b_volume_mm3 < 9400000, f"Expected Parte B ~9347629 mm3, got {settings.part_b_volume_mm3}"
    assert abs((settings.part_a_volume_mm3 + settings.part_b_volume_mm3) - (211.0**3)) < 1000, "Volume sum mismatch"
    print("TEST PASSED: Loop extrude works even when target was hidden in viewport!")

if __name__ == "__main__":
    test_sequence()
