import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, ".")

def test_operator():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Load addon
    import src
    src.register()
    
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    
    # Create cube 211mm
    bpy.ops.mesh.primitive_cube_add(size=0.211, location=(0, 0, 0))
    cube = bpy.context.active_object
    cube.name = "Cube211"
    
    # Set target
    bpy.ops.chest.splitter_set_target()
    settings = scene.chest_splitter
    print("Target set:", settings.target_object.name)
    print("Target dims:", settings.diag_dims_mm)
    print("Target volume:", settings.diag_volume_mm3)
    
    # Go to edit mode to select loop
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(cube.data)
    # Deselect all
    for e in bm.edges:
        e.select = False
    for v in bm.verts:
        v.select = False
    for f in bm.faces:
        f.select = False
    
    # Pick top face
    top_face = [f for f in bm.faces if f.normal.z > 0.9][0]
    for e in top_face.edges:
        e.select = True
    bmesh.update_edit_mesh(cube.data)
    
    # Capture loop
    bpy.ops.chest.splitter_capture_loop()
    print("Loop captured:", settings.loop_is_captured, settings.loop_vertex_indices)
    
    # Deselect edges and select seed face
    for e in bm.edges:
        e.select = False
    top_face.select = True
    bmesh.update_edit_mesh(cube.data)
    bpy.ops.chest.splitter_define_seed_face()
    print("Seed face set:", settings.loop_seed_face_index)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Configure loop settings
    settings.split_mode = 'LOOP'
    settings.loop_behavior = 'EXTRUDE'
    settings.loop_extrude_depth_mm = 1.04
    settings.loop_through_cut = False
    settings.connector_enabled = True # As in user screenshot where connectors were enabled
    
    # Run generate preview
    print("\n--- Running chest.splitter_generate_preview ---")
    ret = bpy.ops.chest.splitter_generate_preview()
    print("Preview return:", ret)
    print("Status:", settings.last_status)
    print("Parte A volume:", settings.part_a_volume_mm3)
    print("Parte B volume:", settings.part_b_volume_mm3)
    print("Sum volume:", settings.part_sum_volume_mm3)
    print("Diff pct:", settings.volume_diff_pct)

if __name__ == "__main__":
    test_operator()
