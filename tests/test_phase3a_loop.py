import bpy
import bmesh
import sys
import os
import math
from mathutils import Vector

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src
from src.geometry_loop import capture_edge_loop, get_topology_signature, slice_mesh_by_loop

def assert_true(condition, message):
    if not condition:
        print(f"  [FAIL] {message}")
        sys.exit(1)
    print(f"  [PASS] {message}")

def run_loop_tests():
    print("\n===========================================================")
    print("=== EXECUTANDO SUÍTE COMPLETA DA FASE 3A: MODO LOOP =======")
    print("===========================================================\n")
    try:
        src.unregister()
    except:
        pass
    src.register()

    # --- Teste 1: Pata Sintética Cilíndrica e Separação Completa ---
    print("--- Teste 1: Modelo Cilíndrico Sintético (Corpo / Pata) ---")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.mesh.primitive_cylinder_add(radius=25, depth=100, vertices=16, location=(0, 0, 50))
    paw_model = bpy.context.active_object
    paw_model.name = "Synthetic_Paw_Model"

    # Subdividir apenas as arestas verticais para criar um anel perfeito no centro (Z=50)
    bm = bmesh.new()
    bm.from_mesh(paw_model.data)
    vertical_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 10.0]
    bmesh.ops.subdivide_edges(bm, edges=vertical_edges, cuts=1)
    bm.to_mesh(paw_model.data)
    bm.free()

    # Entrar em Edit Mode para selecionar o anel intermediário em Z=0 (local)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(paw_model.data)
    bpy.ops.mesh.select_all(action='DESELECT')
    mid_edges = [e for e in bm.edges if abs(e.verts[0].co.z) < 0.1 and abs(e.verts[1].co.z) < 0.1]
    for e in mid_edges:
        e.select = True
    bmesh.update_edit_mesh(paw_model.data)

    bpy.context.scene.chest_splitter.target_object = paw_model
    bpy.context.scene.chest_splitter.split_mode = 'LOOP'

    # Capturar Loop via operador
    res = bpy.ops.chest.splitter_capture_loop()
    assert_true('FINISHED' in res, "Loop fechado capturado com sucesso")
    assert_true(bpy.context.scene.chest_splitter.loop_is_captured, "loop_is_captured == True")
    assert_true(bpy.context.scene.chest_splitter.loop_is_planar, "loop_is_planar == True")
    assert_true(bpy.context.scene.chest_splitter.loop_vertex_count == 16, f"Vértices no loop: {bpy.context.scene.chest_splitter.loop_vertex_count}")

    # Definir Face Semente na pata superior (Z > 10 local)
    bm = bmesh.from_edit_mesh(paw_model.data)
    bpy.ops.mesh.select_all(action='DESELECT')
    for f in bm.faces:
        if f.calc_center_median().z > 10.0:
            f.select = True
            bm.faces.active = f
            break
    bmesh.update_edit_mesh(paw_model.data)

    res = bpy.ops.chest.splitter_define_seed_face()
    assert_true('FINISHED' in res, "Face-semente definida para a Parte A")
    assert_true(bpy.context.scene.chest_splitter.loop_seed_face_index >= 0, "loop_seed_face_index válido")

    bpy.ops.object.mode_set(mode='OBJECT')

    # Gerar Preview
    res = bpy.ops.chest.splitter_generate_preview()
    assert_true('FINISHED' in res, "Preview de loop gerado com sucesso")

    part_A = bpy.context.scene.objects.get("CHEST_SPLITTER_PREVIEW_A")
    part_B = bpy.context.scene.objects.get("CHEST_SPLITTER_PREVIEW_B")
    assert_true(part_A is not None and part_B is not None, "Partes de preview criadas")

    # Checagem de Manifoldness e Volume
    bm_a = bmesh.new()
    bm_a.from_mesh(part_A.data)
    non_man_a = sum(1 for e in bm_a.edges if not e.is_manifold)
    vol_a = bm_a.calc_volume()
    bm_a.free()

    bm_b = bmesh.new()
    bm_b.from_mesh(part_B.data)
    non_man_b = sum(1 for e in bm_b.edges if not e.is_manifold)
    vol_b = bm_b.calc_volume()
    bm_b.free()

    assert_true(non_man_a == 0, f"Parte A (Pata) é 100% manifold ({non_man_a} arestas abertas)")
    assert_true(non_man_b == 0, f"Parte B (Corpo) é 100% manifold ({non_man_b} arestas abertas)")
    assert_true(vol_a > 0 and vol_b > 0, f"Volumes válidos e positivos: Pata={vol_a:.1f}, Corpo={vol_b:.1f}")

    # --- Teste 2: Rejeição de Loop Aberto ---
    print("\n--- Teste 2: Validação e Bloqueio de Loop Aberto ---")
    paw_model.hide_viewport = False
    bpy.context.view_layer.objects.active = paw_model
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(paw_model.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bpy.ops.mesh.select_all(action='DESELECT')
    # Seleciona apenas 2 arestas adjacentes
    bm.edges[0].select = True
    bm.edges[1].select = True
    bmesh.update_edit_mesh(paw_model.data)

    blocked_open = False
    try:
        res = bpy.ops.chest.splitter_capture_loop()
        if 'CANCELLED' in res:
            blocked_open = True
    except RuntimeError:
        blocked_open = True

    assert_true(blocked_open, "Loop aberto detectado e rejeitado com segurança")

    # --- Teste 3: Rejeição de Loop com Ramificação (T-Junction / Grau != 2) ---
    print("\n--- Teste 3: Validação e Bloqueio de Loop Ramificado ---")
    bm = bmesh.from_edit_mesh(paw_model.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bpy.ops.mesh.select_all(action='DESELECT')
    v = bm.verts[0]
    for e in v.link_edges[:3]:
        e.select = True
    bmesh.update_edit_mesh(paw_model.data)

    blocked_branch = False
    try:
        res = bpy.ops.chest.splitter_capture_loop()
        if 'CANCELLED' in res:
            blocked_branch = True
    except RuntimeError:
        blocked_branch = True

    assert_true(blocked_branch, "Loop ramificado detectado e bloqueado com segurança")

    # --- Teste 4: Diagnóstico de Loop Não-Planar ---
    print("\n--- Teste 4: Diagnóstico e Aviso de Não-Planicidade ---")
    bm = bmesh.from_edit_mesh(paw_model.data)
    bpy.ops.mesh.select_all(action='DESELECT')
    mid_edges = [e for e in bm.edges if abs(e.verts[0].co.z) < 0.1 and abs(e.verts[1].co.z) < 0.1]
    for e in mid_edges:
        e.select = True
    # Desloca um vértice do loop em Z para simular superfície sinuosa
    if mid_edges:
        mid_edges[0].verts[0].co.z += 10.0
    bmesh.update_edit_mesh(paw_model.data)

    res = bpy.ops.chest.splitter_capture_loop()
    assert_true('FINISHED' in res, "Captura executada com diagnóstico de planicidade")
    assert_true(not bpy.context.scene.chest_splitter.loop_is_planar, "Não-planicidade detectada com sucesso (loop_is_planar == False)")
    assert_true(bpy.context.scene.chest_splitter.loop_planarity_deviation_mm > 0.0, f"Desvio registrado: {bpy.context.scene.chest_splitter.loop_planarity_deviation_mm:.2f}mm")

    bpy.ops.object.mode_set(mode='OBJECT')

    # --- Teste 5: Assinatura Topológica e Detecção de Mudança ---
    print("\n--- Teste 5: Assinatura Topológica ---")
    sig = get_topology_signature(paw_model)
    assert_true(sig.startswith("V") and "E" in sig and "F" in sig, f"Assinatura gerada: {sig}")

    print("\n===========================================================")
    print(">>> TODOS OS TESTES DA FASE 3A PASSARAM COM SUCESSO! [100%]")
    print("===========================================================\n")

if __name__ == "__main__":
    run_loop_tests()
    sys.exit(0)
