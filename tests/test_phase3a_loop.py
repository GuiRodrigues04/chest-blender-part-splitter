import bpy
import bmesh
import sys
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src

def assert_true(condition, message):
    if not condition:
        print(f"  [FAIL] {message}")
        sys.exit(1)
    print(f"  [PASS] {message}")

def run_loop_test():
    print("\n=== TESTANDO FASE 3A: LOOP FECHADO ===\n")
    try:
        src.unregister()
    except:
        pass
    src.register()
    
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # Criar cubo (2x2x2)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    
    bpy.context.scene.chest_splitter.target_object = cube
    bpy.context.scene.chest_splitter.split_mode = 'LOOP'
    
    # Entrar em Edit Mode
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(cube.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    
    # Cortar o cubo ao meio (Loop Cut não tem API direta trivial em python)
    # Em vez disso, vamos subdividir e selecionar o anel central
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=1, use_grid_fill=True)
    bmesh.update_edit_mesh(cube.data)
    
    # Selecionar arestas no plano z=0
    bpy.ops.mesh.select_all(action='DESELECT')
    
    # Achando as arestas que formam um loop em z=0
    for e in bm.edges:
        z1, z2 = e.verts[0].co.z, e.verts[1].co.z
        if abs(z1) < 0.01 and abs(z2) < 0.01:
            e.select = True
            
    bmesh.update_edit_mesh(cube.data)
    
    # Capturar Loop
    res = bpy.ops.chest.splitter_capture_loop()
    assert_true('FINISHED' in res, "Operador capture_loop executado")
    assert_true(bpy.context.scene.chest_splitter.loop_is_captured, "Loop marcado como capturado")
    assert_true(bpy.context.scene.chest_splitter.loop_vertex_count >= 4, f"Vértices no loop: {bpy.context.scene.chest_splitter.loop_vertex_count}")
    
    # Definir Face Semente (face topo, z>0)
    bpy.ops.mesh.select_all(action='DESELECT')
    for f in bm.faces:
        if f.calc_center_median().z > 0.5:
            f.select = True
            bm.faces.active = f
            break
            
    bmesh.update_edit_mesh(cube.data)
    
    res = bpy.ops.chest.splitter_define_seed_face()
    assert_true('FINISHED' in res, "Operador define_seed_face executado")
    assert_true(bpy.context.scene.chest_splitter.loop_seed_face_index >= 0, f"Face Semente: {bpy.context.scene.chest_splitter.loop_seed_face_index}")
    
    # Voltar para Object Mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Gerar Preview COM conectores
    bpy.context.scene.chest_splitter.use_connectors = True
    bpy.context.scene.chest_splitter.connector_type = 'CYLINDER'
    
    res = bpy.ops.chest.splitter_generate_preview()
    assert_true('FINISHED' in res, "Preview de loop gerado")
    
    part_A = bpy.context.scene.objects.get("CHEST_SPLITTER_PREVIEW_A")
    part_B = bpy.context.scene.objects.get("CHEST_SPLITTER_PREVIEW_B")
    
    assert_true(part_A is not None and part_B is not None, "Partes de preview do loop criadas.")
    
    bm_a = bmesh.new()
    bm_a.from_mesh(part_A.data)
    non_manifold_a = sum(1 for e in bm_a.edges if not e.is_manifold)
    bm_a.free()
    
    assert_true(non_manifold_a == 0, f"Parte A é manifold ({non_manifold_a} abertas).")

    print("\n>>> FASE 3A TESTE BÁSICO PASSOU! <<<\n")

if __name__ == "__main__":
    run_loop_test()
    sys.exit(0)
