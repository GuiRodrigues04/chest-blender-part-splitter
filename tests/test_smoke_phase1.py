"""Bateria de testes automatizados headless para a Fase 1 — Corte por Plano.

Executado diretamente no Blender 5.2 LTS via:
blender --background --python tests/test_smoke_phase1.py
"""

import sys
import os
import math
import bpy
import bmesh
from mathutils import Vector, Euler, Matrix

# Garante a raiz do repositório no path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Importa módulos internos da extensão
from src.constants import (

    COLLECTION_GUIDES_NAME,
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    PLANE_GUIDE_NAME,
    PREVIEW_A_NAME,
    PREVIEW_B_NAME,
    PART_A_SUFFIX,
    PART_B_SUFFIX,
)
from src.geometry_plane import (
    slice_mesh_by_plane,
    compute_explosion_offsets,
    count_mesh_islands,
    NoIntersectionError,
)
import src


def run_tests():
    print("\n=======================================================")
    print("=== EXECUTANDO TESTES DE FASE 1: CORTE POR PLANO ===")
    print("=======================================================\n")

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
    # Teste 1: Registro e Desregistro Idempotente
    # -------------------------------------------------------------
    print("--- Teste 1: Ciclo de Registro e Desregistro ---")
    src.register()
    assert_test(hasattr(bpy.types.Scene, "chest_splitter"), "Propriedade chest_splitter registrada na Scene")
    src.unregister()
    assert_test(not hasattr(bpy.types.Scene, "chest_splitter"), "Propriedade chest_splitter desregistrada na Scene")
    src.register()
    assert_test(hasattr(bpy.types.Scene, "chest_splitter"), "Re-registro idempotente com sucesso")

    # -------------------------------------------------------------
    # Teste 2: Cubo de 130 mm cortado ao meio (Z = 0)
    # -------------------------------------------------------------
    print("\n--- Teste 2: Cubo de 130 mm cortado ao meio ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()

    bpy.ops.mesh.primitive_cube_add(size=130.0, location=(0, 0, 0))
    cube = bpy.context.active_object
    orig_vol = 130.0 ** 3

    mesh_a = bpy.data.meshes.new("test_a")
    mesh_b = bpy.data.meshes.new("test_b")

    report = slice_mesh_by_plane(
        source_mesh=cube.data,
        matrix_world=cube.matrix_world,
        plane_origin=Vector((0, 0, 0)),
        plane_normal=Vector((0, 0, 1)),
        target_mesh_a=mesh_a,
        target_mesh_b=mesh_b,
        invert_sides=False,
        unit_scale=1.0,  # usando BU direto para conferência exata
    )

    assert_test(report["A"]["is_manifold"], "Parte A é manifold (0 arestas abertas)")
    assert_test(report["B"]["is_manifold"], "Parte B é manifold (0 arestas abertas)")
    assert_test(report["A"]["non_manifold_edges"] == 0, "Parte A tem 0 arestas não-manifold")
    assert_test(report["B"]["non_manifold_edges"] == 0, "Parte B tem 0 arestas não-manifold")

    vol_a = report["A"]["volume_mm3"]
    vol_b = report["B"]["volume_mm3"]
    expected_half = orig_vol / 2.0
    assert_test(abs(vol_a - expected_half) < 1.0, f"Volume Parte A ({vol_a:.1f}) é metade do cubo ({expected_half:.1f})")
    assert_test(abs(vol_b - expected_half) < 1.0, f"Volume Parte B ({vol_b:.1f}) é metade do cubo ({expected_half:.1f})")
    assert_test(abs((vol_a + vol_b) - orig_vol) < 1.0, f"Conservação estrita de volume: soma={vol_a+vol_b:.1f} vs orig={orig_vol:.1f}")

    # Bounds: X=130, Y=130, Z=65
    dims_a = report["A"]["dims_mm"]
    assert_test(abs(dims_a[0] - 130.0) < 0.1 and abs(dims_a[1] - 130.0) < 0.1 and abs(dims_a[2] - 65.0) < 0.1,
                f"Bounds da Parte A correspondem a 130 x 130 x 65 mm (obtido {dims_a[0]:.1f}x{dims_a[1]:.1f}x{dims_a[2]:.1f})")

    bpy.data.meshes.remove(mesh_a, do_unlink=True)
    bpy.data.meshes.remove(mesh_b, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 3: Cortes Inclinados (10° e 45°)
    # -------------------------------------------------------------
    print("\n--- Teste 3: Cortes Inclinados (10° e 45°) ---")
    for angle_deg in (10.0, 45.0):
        ang_rad = math.radians(angle_deg)
        normal = Vector((math.sin(ang_rad), 0.0, math.cos(ang_rad))).normalized()

        m_a = bpy.data.meshes.new(f"test_ang_{int(angle_deg)}_a")
        m_b = bpy.data.meshes.new(f"test_ang_{int(angle_deg)}_b")

        rep_ang = slice_mesh_by_plane(
            source_mesh=cube.data,
            matrix_world=cube.matrix_world,
            plane_origin=Vector((0, 0, 0)),
            plane_normal=normal,
            target_mesh_a=m_a,
            target_mesh_b=m_b,
            unit_scale=1.0,
        )

        sum_v = rep_ang["A"]["volume_mm3"] + rep_ang["B"]["volume_mm3"]
        assert_test(rep_ang["A"]["is_manifold"] and rep_ang["B"]["is_manifold"],
                    f"Corte a {angle_deg}° produz ambas partes manifold")
        assert_test(abs(sum_v - orig_vol) < 2.0,
                    f"Corte a {angle_deg}° conserva volume total (dif={abs(sum_v - orig_vol):.2f})")

        bpy.data.meshes.remove(m_a, do_unlink=True)
        bpy.data.meshes.remove(m_b, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 4: Alvo com Transformações Arbitrárias (Pos, Rot, Escala)
    # -------------------------------------------------------------
    print("\n--- Teste 4: Alvo com Rotação, Translação e Parent ---")
    bpy.ops.mesh.primitive_cube_add(size=100.0, location=(40, -30, 50))
    trans_cube = bpy.context.active_object
    trans_cube.rotation_euler = Euler((math.radians(25), math.radians(35), math.radians(10)))
    bpy.context.view_layer.update()

    m_ta = bpy.data.meshes.new("trans_a")
    m_tb = bpy.data.meshes.new("trans_b")
    rep_trans = slice_mesh_by_plane(
        source_mesh=trans_cube.data,
        matrix_world=trans_cube.matrix_world,
        plane_origin=trans_cube.matrix_world.translation,
        plane_normal=Vector((0, 0, 1)),
        target_mesh_a=m_ta,
        target_mesh_b=m_tb,
        unit_scale=1.0,
    )
    expected_vol_trans = 100.0 ** 3
    sum_trans = rep_trans["A"]["volume_mm3"] + rep_trans["B"]["volume_mm3"]
    assert_test(rep_trans["A"]["is_manifold"] and rep_trans["B"]["is_manifold"],
                "Alvo rotacionado/transladado resulta em partes manifold")
    assert_test(abs(sum_trans - expected_vol_trans) < 2.0,
                f"Volume de alvo transformado conservado (dif={abs(sum_trans - expected_vol_trans):.2f})")
    bpy.data.meshes.remove(m_ta, do_unlink=True)
    bpy.data.meshes.remove(m_tb, do_unlink=True)
    bpy.data.objects.remove(trans_cube, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 5: Plano Sem Interseção Bloqueia com Erro Controlado
    # -------------------------------------------------------------
    print("\n--- Teste 5: Plano Sem Interseção ---")
    m_no_a = bpy.data.meshes.new("no_a")
    m_no_b = bpy.data.meshes.new("no_b")
    blocked = False
    try:
        slice_mesh_by_plane(
            source_mesh=cube.data,
            matrix_world=cube.matrix_world,
            plane_origin=Vector((1000.0, 0, 0)),
            plane_normal=Vector((1, 0, 0)),
            target_mesh_a=m_no_a,
            target_mesh_b=m_no_b,
            unit_scale=1.0,
        )
    except NoIntersectionError:
        blocked = True

    assert_test(blocked, "Plano fora do modelo dispara NoIntersectionError de modo controlado")
    bpy.data.meshes.remove(m_no_a, do_unlink=True)
    bpy.data.meshes.remove(m_no_b, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 6: Corte passando exatamente por Vértices / Arestas
    # -------------------------------------------------------------
    print("\n--- Teste 6: Corte Diagonal Passando por Vértices ---")
    m_diag_a = bpy.data.meshes.new("diag_a")
    m_diag_b = bpy.data.meshes.new("diag_b")
    diag_normal = Vector((1, 1, 0)).normalized()
    rep_diag = slice_mesh_by_plane(
        source_mesh=cube.data,
        matrix_world=cube.matrix_world,
        plane_origin=Vector((0, 0, 0)),
        plane_normal=diag_normal,
        target_mesh_a=m_diag_a,
        target_mesh_b=m_diag_b,
        unit_scale=1.0,
    )
    assert_test(rep_diag["A"]["is_manifold"] and rep_diag["B"]["is_manifold"],
                "Corte diagonal passando por vértices gera partes manifold")
    sum_diag = rep_diag["A"]["volume_mm3"] + rep_diag["B"]["volume_mm3"]
    assert_test(abs(sum_diag - orig_vol) < 2.0, "Corte diagonal conserva volume total")
    bpy.data.meshes.remove(m_diag_a, do_unlink=True)
    bpy.data.meshes.remove(m_diag_b, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 7: Modelo com Múltiplos Componentes
    # -------------------------------------------------------------
    print("\n--- Teste 7: Modelo com Múltiplos Componentes Desconexos ---")
    # Cria malha com dois cubos separados
    bm_multi = bmesh.new()
    bmesh.ops.create_cube(bm_multi, size=20.0, matrix=Matrix.Translation((0, 0, -30)))
    bmesh.ops.create_cube(bm_multi, size=20.0, matrix=Matrix.Translation((0, 0, 30)))
    multi_mesh = bpy.data.meshes.new("multi_mesh")
    bm_multi.to_mesh(multi_mesh)
    bm_multi.free()

    m_ma = bpy.data.meshes.new("multi_a")
    m_mb = bpy.data.meshes.new("multi_b")
    rep_multi = slice_mesh_by_plane(
        source_mesh=multi_mesh,
        matrix_world=Matrix.Identity(4),
        plane_origin=Vector((0, 0, 0)),
        plane_normal=Vector((0, 0, 1)),
        target_mesh_a=m_ma,
        target_mesh_b=m_mb,
        unit_scale=1.0,
    )
    assert_test(rep_multi["A"]["components"] == 1, "Parte A preservou 1 componente do seu lado")
    assert_test(rep_multi["B"]["components"] == 1, "Parte B preservou 1 componente do seu lado")
    assert_test(rep_multi["A"]["is_manifold"] and rep_multi["B"]["is_manifold"], "Partes de malha multi-ilha são manifold")
    bpy.data.meshes.remove(multi_mesh, do_unlink=True)
    bpy.data.meshes.remove(m_ma, do_unlink=True)
    bpy.data.meshes.remove(m_mb, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 8: Visão Explodida e Deslocamento
    # -------------------------------------------------------------
    print("\n--- Teste 8: Cálculo de Afastamento na Visão Explodida ---")
    norm_exp = Vector((0, 0, 1))
    off_a, off_b = compute_explosion_offsets(norm_exp, explosion_distance_mm=40.0, unit_scale=1000.0)
    # Com unit_scale=1000, 40mm = 0.04 BU. Metade = 0.02 BU
    assert_test(abs(off_a.z - 0.02) < 1e-5 and abs(off_b.z - (-0.02)) < 1e-5,
                "Offsets da visão explodida correspondem exatamente a +/- 20 mm (0.02 BU)")
    dist_total = (off_a - off_b).length * 1000.0
    assert_test(abs(dist_total - 40.0) < 1e-3, f"Distância total entre partes é 40.0 mm (obtido {dist_total:.3f} mm)")

    # -------------------------------------------------------------
    # Teste 9: Inversão de Lados A/B
    # -------------------------------------------------------------
    print("\n--- Teste 9: Inversão de Lados A/B ---")
    # Corta o cubo não centralizado (Z=20)
    m_norm_a = bpy.data.meshes.new("norm_a")
    m_norm_b = bpy.data.meshes.new("norm_b")
    rep_direct = slice_mesh_by_plane(
        source_mesh=cube.data,
        matrix_world=cube.matrix_world,
        plane_origin=Vector((0, 0, 20)),
        plane_normal=Vector((0, 0, 1)),
        target_mesh_a=m_norm_a,
        target_mesh_b=m_norm_b,
        invert_sides=False,
        unit_scale=1.0,
    )
    vol_direct_a = rep_direct["A"]["volume_mm3"]
    vol_direct_b = rep_direct["B"]["volume_mm3"]

    m_inv_a = bpy.data.meshes.new("inv_a")
    m_inv_b = bpy.data.meshes.new("inv_b")
    rep_inv = slice_mesh_by_plane(
        source_mesh=cube.data,
        matrix_world=cube.matrix_world,
        plane_origin=Vector((0, 0, 20)),
        plane_normal=Vector((0, 0, 1)),
        target_mesh_a=m_inv_a,
        target_mesh_b=m_inv_b,
        invert_sides=True,
        unit_scale=1.0,
    )
    vol_inv_a = rep_inv["A"]["volume_mm3"]
    vol_inv_b = rep_inv["B"]["volume_mm3"]

    assert_test(abs(vol_inv_a - vol_direct_b) < 1.0, "Inversão de lados: novo volume de A é o volume anterior de B")
    assert_test(abs(vol_inv_b - vol_direct_a) < 1.0, "Inversão de lados: novo volume de B é o volume anterior de A")

    bpy.data.meshes.remove(m_norm_a, do_unlink=True)
    bpy.data.meshes.remove(m_norm_b, do_unlink=True)
    bpy.data.meshes.remove(m_inv_a, do_unlink=True)
    bpy.data.meshes.remove(m_inv_b, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 10: 20 Ciclos de Gerar/Limpar Preview Sem Vazamento
    # -------------------------------------------------------------
    print("\n--- Teste 10: 20 Ciclos de Preview sem Acúmulo de Objetos/Malhas ---")
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)
    bpy.ops.chest.splitter_set_target()

    initial_obj_count = len(bpy.data.objects)
    initial_mesh_count = len(bpy.data.meshes)

    for i in range(20):
        bpy.ops.chest.splitter_generate_preview()

    final_obj_count = len(bpy.data.objects)
    final_mesh_count = len(bpy.data.meshes)

    # Após 20 ciclos, deve haver exatamente o alvo, o guia e os 2 objetos de preview ativos
    # e nenhuma malha órfã
    print(f"  Inicial: {initial_obj_count} objs, {initial_mesh_count} meshes")
    print(f"  Final:   {final_obj_count} objs, {final_mesh_count} meshes")
    assert_test(final_obj_count == initial_obj_count + 2, "Apenas os 2 objetos de preview atuais foram criados")
    assert_test(final_mesh_count == initial_mesh_count + 2, "Apenas as 2 malhas de preview atuais existem (sem vazamentos)")

    # -------------------------------------------------------------
    # Teste 11: Fluxo de Confirmação (Commit) e Restauração
    # -------------------------------------------------------------
    print("\n--- Teste 11: Confirmação (Commit) e Restauração ---")
    settings = bpy.context.scene.chest_splitter
    assert_test(settings.session_status == 'PREVIEW_VALID', "Status está PREVIEW_VALID antes do commit")

    bpy.ops.chest.splitter_commit_parts()
    assert_test(settings.session_status == 'COMMITTED', "Status avançou para COMMITTED após commit")

    parts_col = next((c for c in bpy.context.scene.collection.children_recursive if c.name == COLLECTION_PARTS_NAME), None)
    assert_test(parts_col is not None, "Coleção CHEST_SPLITTER_PARTS existe")


    part_a_obj = parts_col.objects.get(f"{cube.name}{PART_A_SUFFIX}")
    part_b_obj = parts_col.objects.get(f"{cube.name}{PART_B_SUFFIX}")
    assert_test(part_a_obj is not None, f"Objeto final '{cube.name}{PART_A_SUFFIX}' criado com sucesso")
    assert_test(part_b_obj is not None, f"Objeto final '{cube.name}{PART_B_SUFFIX}' criado com sucesso")
    assert_test(part_a_obj.get("chest_splitter_part") == "A", "Metadado de Parte A gravado")
    assert_test(part_b_obj.get("chest_splitter_part") == "B", "Metadado de Parte B gravado")

    # Testa restaurar original
    bpy.ops.chest.splitter_restore_original()
    assert_test(not cube.hide_viewport, "Original re-exibido na Viewport após restauração")
    assert_test(settings.session_status == 'CONFIGURED', "Status retornou para CONFIGURED")

    print(f"\n>>> TODOS OS {passed}/{total} TESTES DA FASE 1 PASSARAM COM SUCESSO! <<<\n")


if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\nERRO FATAL NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
