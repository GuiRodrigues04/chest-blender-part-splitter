import bpy
import bmesh
import sys
import os
import math
from mathutils import Vector, Matrix

# Add the root directory to sys.path so we can import src as a package
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src

def assert_true(condition, message):
    if not condition:
        print(f"  [FAIL] {message}")
        sys.exit(1)
    print(f"  [PASS] {message}")

def run_stress_tests():
    print("\n===========================================================")
    print("=== EXECUTANDO TESTES DE ESTRESSE: FASES 0 A 3 =========")
    print("===========================================================\n")
    
    try:
        src.unregister()
    except:
        pass
    src.register()
    
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # --- Teste 1: Malha High Poly ---
    print("--- Teste 1: High Poly (125k faces) ---")
    bpy.ops.mesh.primitive_monkey_add(size=200, location=(0, 0, 0))
    monkey = bpy.context.active_object
    subsurf = monkey.modifiers.new(name="Subsurf", type='SUBSURF')
    subsurf.levels = 4
    subsurf.render_levels = 4
    bpy.context.view_layer.objects.active = monkey
    bpy.ops.object.modifier_apply(modifier="Subsurf")
    
    bpy.context.view_layer.update()
    poly_count = len(monkey.data.polygons)
    print(f"Info: Malha com {poly_count} polígonos.")
    
    bpy.context.scene.chest_splitter.target_object = monkey
    bpy.context.scene.chest_splitter.split_mode = 'PLANE'
    bpy.context.scene.chest_splitter.use_connectors = True
    bpy.context.scene.chest_splitter.connector_clearance_preset = 'NORMAL'
    
    bpy.ops.chest.splitter_align_plane(align_mode='Z')
    res = bpy.ops.chest.splitter_generate_preview()
    assert_true('FINISHED' in res, "Preview de alta resolução gerado.")
    
    part_A = bpy.context.scene.objects.get("CHEST_SPLITTER_PREVIEW_A")
    part_B = bpy.context.scene.objects.get("CHEST_SPLITTER_PREVIEW_B")
    
    bm_a = bmesh.new()
    bm_a.from_mesh(part_A.data)
    non_manifold_a = sum(1 for e in bm_a.edges if not e.is_manifold)
    bm_a.free()
    
    assert_true(non_manifold_a == 0, f"Parte A é 100% manifold ({non_manifold_a} abertas).")
    
    # --- Teste 2: Cortador Sólido Extremo ---
    print("\n--- Teste 2: Cortador Sólido (Cápsula Extrema) ---")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    bpy.ops.mesh.primitive_cube_add(size=100, location=(0,0,0))
    bar = bpy.context.active_object
    bar.scale = (1, 1, 5)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    bpy.context.scene.chest_splitter.target_object = bar
    bpy.context.scene.chest_splitter.split_mode = 'SOLID'
    bpy.context.scene.chest_splitter.solid_source = 'PRIMITIVE'
    bpy.context.scene.chest_splitter.solid_primitive_type = 'CAPSULE'
    
    bpy.ops.chest.splitter_create_or_focus_solid_cutter()
    cutter = bpy.context.scene.chest_splitter.solid_cutter_object
    cutter.scale = (0.5, 0.5, 0.5)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    res = bpy.ops.chest.splitter_generate_preview()
    assert_true('FINISHED' in res, "Preview sólido gerado.")
    
    print("\n>>> TODOS OS TESTES DE ESTRESSE PASSARAM COM SUCESSO! <<<\n")

if __name__ == "__main__":
    run_stress_tests()
    sys.exit(0)
