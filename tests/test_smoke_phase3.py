"""Suíte de testes automatizados headless para a Fase 3 — Cortador Sólido Personalizado.

Executado diretamente no Blender 5.2 LTS via:
blender --background --python tests/test_smoke_phase3.py
"""

import sys
import os
import math
import bpy
import bmesh
from mathutils import Vector, Euler, Matrix

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src
from src.constants import (
    COLLECTION_GUIDES_NAME,
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    PART_A_SUFFIX,
    PART_B_SUFFIX,
    SOLID_CUTTER_NAME,
)
from src.geometry_solid import (
    create_primitive_cutter_mesh,
    validate_solid_cutter,
    slice_mesh_by_solid,
    compute_solid_explosion_offsets,
    SolidCutterValidationError,
)


def run_tests():
    print("\n===========================================================")
    print("=== EXECUTANDO TESTES DE FASE 3: CORTADOR SÓLIDO (3D) =====")
    print("===========================================================\n")

    passed = 0
    total = 0

    def assert_test(cond, msg):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f"  [PASS] {msg}")
        else:
            print(f"  [FAIL] {msg}")
            raise AssertionError(msg)

    # -------------------------------------------------------------
    # Teste 1: Ciclo de Registro e Desregistro
    # -------------------------------------------------------------
    print("--- Teste 1: Registro e Propriedades da Fase 3 ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()

    settings = bpy.context.scene.chest_splitter
    assert_test(hasattr(settings, "split_mode"), "Propriedade split_mode registrada")
    assert_test(hasattr(settings, "solid_source"), "Propriedade solid_source registrada")
    assert_test(hasattr(settings, "solid_primitive_type"), "Propriedade solid_primitive_type registrada")
    assert_test(hasattr(settings, "solid_cutter_object"), "Propriedade solid_cutter_object registrada")
    assert_test(hasattr(settings, "solid_cutter_is_manifold"), "Propriedade solid_cutter_is_manifold registrada")

    src.unregister()
    assert_test(not hasattr(bpy.types.Scene, "chest_splitter"), "Propriedade chest_splitter desregistrada")
    src.register()
    assert_test(hasattr(bpy.context.scene, "chest_splitter"), "Re-registro idempotente com sucesso")

    # -------------------------------------------------------------
    # Teste 2: Geração das 4 Primitivas de Cortador Sólido
    # -------------------------------------------------------------
    print("\n--- Teste 2: Geração e Manifoldness das 4 Primitivas ---")
    primitives = ['BOX', 'CYLINDER', 'SPHERE', 'CAPSULE']
    for p_type in primitives:
        m = create_primitive_cutter_mesh(
            name=f"test_prim_{p_type}",
            primitive_type=p_type,
            dims=Vector((0.040, 0.040, 0.060)),
        )
        bm = bmesh.new()
        bm.from_mesh(m)
        is_mani = all(e.is_manifold for e in bm.edges)
        vol = abs(bm.calc_volume())
        verts_cnt = len(bm.verts)
        faces_cnt = len(bm.faces)
        bm.free()
        bpy.data.meshes.remove(m, do_unlink=True)

        assert_test(is_mani, f"Primitiva '{p_type}' é 100% manifold (0 arestas abertas)")
        assert_test(vol > 1e-7, f"Primitiva '{p_type}' possui volume positivo ({vol:.6f} BU³)")
        assert_test(verts_cnt >= 8 and faces_cnt >= 6, f"Primitiva '{p_type}' possui topologia válida ({verts_cnt} verts, {faces_cnt} faces)")

    # -------------------------------------------------------------
    # Teste 3: Corte Sólido por Caixa (Cubo 100 mm cortado por Caixa 50 mm)
    # -------------------------------------------------------------
    print("\n--- Teste 3: Corte Sólido por Caixa (Cálculo de Volume e Manifold) ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()

    # Cria cubo 100x100x100 mm (0.100 m)
    bpy.ops.mesh.primitive_cube_add(size=0.100, location=(0, 0, 0))
    cube = bpy.context.active_object
    cube.name = "Target_Cube"
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)
    bpy.ops.chest.splitter_set_target()

    settings = bpy.context.scene.chest_splitter
    settings.split_mode = 'SOLID'
    settings.solid_source = 'PRIMITIVE'
    settings.solid_primitive_type = 'BOX'

    # Cria cortador paramétrico
    bpy.ops.chest.splitter_create_or_focus_solid_cutter()
    cutter_obj = settings.solid_cutter_object
    assert_test(cutter_obj is not None, "Objeto cortador criado na coleção de guias")

    # Redimensiona cortador para 50x50x50 mm (0.050 m)
    cutter_obj.scale = Vector((50.0 / 60.0, 50.0 / 60.0, 50.0 / 60.0))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Gera preview sólido
    bpy.ops.chest.splitter_generate_preview()
    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com cortador sólido gerado com sucesso")

    # Volume esperado: Alvo = 1.000.000 mm³, Cortador = 125.000 mm³
    # Parte A (Interseção) = 125.000 mm³
    # Parte B (Diferença) = 875.000 mm³
    vol_a = settings.part_a_volume_mm3
    vol_b = settings.part_b_volume_mm3
    assert_test(abs(vol_a - 125000.0) < 500.0, f"Volume Parte A (Interseção) = {vol_a:,.1f} mm³ (~125.000 mm³)")
    assert_test(abs(vol_b - 875000.0) < 500.0, f"Volume Parte B (Diferença) = {vol_b:,.1f} mm³ (~875.000 mm³)")
    assert_test(abs(vol_a + vol_b - 1000000.0) < 500.0, f"Conservação de volume: soma = {vol_a + vol_b:,.1f} mm³ (orig: 1.000.000 mm³)")
    assert_test(settings.part_a_is_manifold, "Parte A é 100% manifold")
    assert_test(settings.part_b_is_manifold, "Parte B é 100% manifold")
    assert_test(settings.part_a_non_manifold_edges == 0, "Parte A tem 0 arestas não-manifold")
    assert_test(settings.part_b_non_manifold_edges == 0, "Parte B tem 0 arestas não-manifold")

    # -------------------------------------------------------------
    # Teste 4: Corte Sólido por Cilindro (Plug Central Cilíndrico)
    # -------------------------------------------------------------
    print("\n--- Teste 4: Corte Sólido por Cilindro ---")
    settings.solid_primitive_type = 'CYLINDER'
    bpy.ops.chest.splitter_create_or_focus_solid_cutter()
    bpy.ops.chest.splitter_generate_preview()

    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com cilindro gerado com sucesso")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Ambas as partes com cilindro são manifold")
    assert_test(settings.part_a_non_manifold_edges == 0 and settings.part_b_non_manifold_edges == 0, "0 arestas abertas com cilindro")
    assert_test(settings.volume_diff_pct < 0.2, f"Balanço de volume conservado (dif: {settings.volume_diff_pct:.3f}%)")

    # -------------------------------------------------------------
    # Teste 5: Corte Sólido por Esfera
    # -------------------------------------------------------------
    print("\n--- Teste 5: Corte Sólido por Esfera ---")
    settings.solid_primitive_type = 'SPHERE'
    bpy.ops.chest.splitter_create_or_focus_solid_cutter()
    bpy.ops.chest.splitter_generate_preview()

    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com esfera gerado com sucesso")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Partes geradas por esfera são 100% manifold")
    assert_test(settings.volume_diff_pct < 0.2, "Volume conservado com corte esférico")

    # -------------------------------------------------------------
    # Teste 6: Corte Sólido por Cápsula
    # -------------------------------------------------------------
    print("\n--- Teste 6: Corte Sólido por Cápsula ---")
    settings.solid_primitive_type = 'CAPSULE'
    bpy.ops.chest.splitter_create_or_focus_solid_cutter()
    bpy.ops.chest.splitter_generate_preview()

    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com cápsula gerado com sucesso")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Partes geradas por cápsula são 100% manifold")
    assert_test(settings.part_a_non_manifold_edges == 0 and settings.part_b_non_manifold_edges == 0, "0 arestas abertas com cápsula")

    # -------------------------------------------------------------
    # Teste 7: Inversão de Lados A/B no Modo Sólido
    # -------------------------------------------------------------
    print("\n--- Teste 7: Inversão de Lados A/B (Interseção <-> Diferença) ---")
    vol_a_norm = settings.part_a_volume_mm3
    vol_b_norm = settings.part_b_volume_mm3

    bpy.ops.chest.splitter_invert_sides()
    assert_test(settings.invert_sides is True, "invert_sides ativado")

    vol_a_inv = settings.part_a_volume_mm3
    vol_b_inv = settings.part_b_volume_mm3

    # Com inversão, Parte A recebe a Diferença (volume maior) e Parte B recebe a Interseção (volume menor)
    assert_test(abs(vol_a_inv - vol_b_norm) < 100.0, f"Volume A invertido ({vol_a_inv:,.0f}) é igual ao Volume B normal ({vol_b_norm:,.0f})")
    assert_test(abs(vol_b_inv - vol_a_norm) < 100.0, f"Volume B invertido ({vol_b_inv:,.0f}) é igual ao Volume A normal ({vol_a_norm:,.0f})")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Partes invertidas continuam 100% manifold")

    # Restaura invert_sides
    bpy.ops.chest.splitter_invert_sides()

    # -------------------------------------------------------------
    # Teste 8: Rejeição de Cortador Aberto / Não-Manifold
    # -------------------------------------------------------------
    print("\n--- Teste 8: Bloqueio Seguro de Cortador Aberto ---")
    # Cria um plano 2D aberto na cena
    bpy.ops.mesh.primitive_plane_add(size=0.080, location=(0, 0, 0))
    open_plane = bpy.context.active_object
    open_plane.name = "Open_Plane_Cutter"

    blocked = False
    try:
        validate_solid_cutter(open_plane, cube, unit_scale=1000.0)
    except SolidCutterValidationError as e:
        blocked = True
        print(f"  [INFO] Erro capturado com sucesso: {e}")

    assert_test(blocked, "Cortador aberto (não-manifold) detectado e bloqueado com SolidCutterValidationError")
    bpy.data.objects.remove(open_plane, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 9: Cortador Fora do Alvo (Sem Interseção)
    # -------------------------------------------------------------
    print("\n--- Teste 9: Detecção de Cortador Fora do Alvo ---")
    cutter_obj = settings.solid_cutter_object
    cutter_obj.location = Vector((0.500, 0.500, 0.500))  # 500 mm longe do alvo

    outside_blocked = False
    try:
        validate_solid_cutter(cutter_obj, cube, unit_scale=1000.0)
    except SolidCutterValidationError as e:
        outside_blocked = True
        print(f"  [INFO] Aviso capturado: {e}")

    assert_test(outside_blocked, "Cortador fora da bounding box do alvo bloqueado com aviso")

    # Reposiciona o cortador no centro do alvo
    cutter_obj.location = Vector((0.0, 0.0, 0.0))

    # -------------------------------------------------------------
    # Teste 10: Cortador Rotacionado em Ângulo Arbitrário
    # -------------------------------------------------------------
    print("\n--- Teste 10: Cortador com Rotação Arbitrária no Espaço Global ---")
    cutter_obj.rotation_euler = Euler((math.radians(35.0), math.radians(45.0), math.radians(20.0)))
    bpy.ops.chest.splitter_generate_preview()

    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com cortador rotacionado gerado com sucesso")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Partes de cortador rotacionado são 100% manifold")
    assert_test(settings.volume_diff_pct < 0.3, f"Volume conservado com cortador rotacionado (dif: {settings.volume_diff_pct:.3f}%)")

    # -------------------------------------------------------------
    # Teste 11: Visão Explodida no Modo Sólido
    # -------------------------------------------------------------
    print("\n--- Teste 11: Visão Explodida entre Centróides ---")
    settings.view_mode = 'EXPLODED'
    settings.explosion_distance_mm = 40.0

    col = bpy.context.scene.collection.children_recursive
    prev_col = next((c for c in col if c.name == COLLECTION_PREVIEWS_NAME), None)
    obj_a = prev_col.objects.get("CHEST_SPLITTER_PREVIEW_A")
    obj_b = prev_col.objects.get("CHEST_SPLITTER_PREVIEW_B")

    dist_between = (obj_a.location - obj_b.location).length * 1000.0
    assert_test(abs(dist_between - 40.0) < 1.0, f"Distância explodida entre partes = {dist_between:.2f} mm (~40.0 mm)")

    # -------------------------------------------------------------
    # Teste 12: Confirmação Definitiva (Commit) e Restauração
    # -------------------------------------------------------------
    print("\n--- Teste 12: Confirmação Definitiva e Restauração em Modo Sólido ---")
    bpy.ops.chest.splitter_commit_parts()
    assert_test(settings.session_status == 'COMMITTED', "Status avançou para COMMITTED")

    parts_col = next((c for c in bpy.context.scene.collection.children_recursive if c.name == COLLECTION_PARTS_NAME), None)
    assert_test(parts_col is not None, "Coleção CHEST_SPLITTER_PARTS existe")
    final_a = parts_col.objects.get(f"{cube.name}{PART_A_SUFFIX}")
    final_b = parts_col.objects.get(f"{cube.name}{PART_B_SUFFIX}")
    assert_test(final_a is not None and final_b is not None, "Peças finais criadas com sucesso")

    # Cortador na coleção de guias deve ter sido ocultado
    assert_test(cutter_obj.hide_viewport is True, "Cortador sólido na coleção de guias foi ocultado")

    # Restaura original
    bpy.ops.chest.splitter_restore_original()
    assert_test(not cube.hide_viewport, "Objeto alvo original restaurado na Viewport")

    # -------------------------------------------------------------
    # Teste 13: 20 Ciclos de Preview Sólido (Sem Vazamento de Memória)
    # -------------------------------------------------------------
    print("\n--- Teste 13: 20 Ciclos de Preview Sólido (Sem Vazamento) ---")
    cube.hide_viewport = False
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)
    bpy.ops.chest.splitter_set_target()
    settings.split_mode = 'SOLID'
    cutter_obj.hide_viewport = False

    objs_before = len(bpy.data.objects)
    meshes_before = len(bpy.data.meshes)

    for i in range(20):
        bpy.ops.chest.splitter_generate_preview()

    objs_after = len(bpy.data.objects)
    meshes_after = len(bpy.data.meshes)

    # Devem existir exatamente os 2 objetos e 2 malhas de preview ativos do último ciclo
    assert_test(objs_after - objs_before <= 2, f"Apenas os previews ativos foram criados em objetos ({objs_after} vs {objs_before})")
    assert_test(meshes_after - meshes_before <= 2, f"Apenas as malhas de preview ativas existem ({meshes_after} vs {meshes_before})")

    print(f"\n>>> TODOS OS {passed}/{total} TESTES DA FASE 3 PASSARAM COM SUCESSO! <<<\n")


if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\nERRO FATAL NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
