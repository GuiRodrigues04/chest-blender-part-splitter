"""Suíte de testes automatizados headless para a Fase 2 — Encaixes em Cortes Planos.

Executado diretamente no Blender 5.2 LTS via:
blender --background --python tests/test_smoke_phase2.py
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

import src
from src.constants import (
    COLLECTION_GUIDES_NAME,
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    PART_A_SUFFIX,
    PART_B_SUFFIX,
    CLEARANCE_PRESETS,
)
from src.geometry_connectors import (
    create_pin_mesh_data,
    compute_connector_positions,
    validate_connectors,
    apply_connectors_boolean,
    ConnectorValidationError,
)
from src.geometry_plane import slice_mesh_by_plane, evaluate_bmesh_metrics


def run_tests():
    print("\n===========================================================")
    print("=== EXECUTANDO TESTES DE FASE 2: ENCAIXES & FOLGAS (FDM) ===")
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
    # Teste 1: Aferição Dimensional Rigorosa (Convenção de Folga)
    # -------------------------------------------------------------
    print("--- Teste 1: Aferição Dimensional Rigorosa do Macho e da Cavidade ---")
    nom_diam = 6.0
    nom_len = 8.0
    clearance = 0.15
    end_clearance = 0.5

    # 1. Macho Cilíndrico
    pin_mesh = create_pin_mesh_data(
        name="test_pin",
        connector_type='CYLINDER',
        diameter=nom_diam,
        length=nom_len,
        chamfer=0.8,
        is_cavity=False,
    )
    bm_pin = bmesh.new()
    bm_pin.from_mesh(pin_mesh)
    # O diâmetro do pino na região cilíndrica deve ser exatamente nom_diam (raio 3.0)
    measured_pin_diam = max(math.sqrt(v.co.x**2 + v.co.y**2) for v in bm_pin.verts) * 2.0
    assert_test(abs(measured_pin_diam - nom_diam) < 1e-4,
                f"Diâmetro nominal do macho é exatamente {nom_diam:.2f} mm (medido: {measured_pin_diam:.4f})")
    assert_test(all(e.is_manifold for e in bm_pin.edges), "Malha do pino macho é 100% manifold")
    bm_pin.free()
    bpy.data.meshes.remove(pin_mesh, do_unlink=True)

    # 2. Cavidade Fêmea Cilíndrica
    cavity_mesh = create_pin_mesh_data(
        name="test_cavity",
        connector_type='CYLINDER',
        diameter=nom_diam,
        length=nom_len,
        chamfer=0.0,
        is_cavity=True,
        clearance_side=clearance,
        clearance_end=end_clearance,
    )
    bm_cav = bmesh.new()
    bm_cav.from_mesh(cavity_mesh)
    expected_cav_diam = nom_diam + 2.0 * clearance  # 6.30 mm
    measured_cav_diam = max(math.sqrt(v.co.x**2 + v.co.y**2) for v in bm_cav.verts) * 2.0
    assert_test(abs(measured_cav_diam - expected_cav_diam) < 1e-4,
                f"Diâmetro da cavidade fêmea = {expected_cav_diam:.2f} mm (D_nom + 2*folga; medido: {measured_cav_diam:.4f})")
    assert_test(all(e.is_manifold for e in bm_cav.edges), "Malha da cavidade fêmea é 100% manifold")
    bm_cav.free()
    bpy.data.meshes.remove(cavity_mesh, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 2: Todos os 4 Presets de Folga de Montagem
    # -------------------------------------------------------------
    print("\n--- Teste 2: Validação dos 4 Presets de Folga ---")
    for preset_name, expected_clearance in CLEARANCE_PRESETS.items():
        cav_m = create_pin_mesh_data(
            name=f"test_cav_{preset_name}",
            connector_type='CYLINDER',
            diameter=10.0,
            length=10.0,
            is_cavity=True,
            clearance_side=expected_clearance,
            clearance_end=0.5,
        )
        bm_c = bmesh.new()
        bm_c.from_mesh(cav_m)
        meas_d = max(math.sqrt(v.co.x**2 + v.co.y**2) for v in bm_c.verts) * 2.0
        exp_d = 10.0 + 2.0 * expected_clearance
        assert_test(abs(meas_d - exp_d) < 1e-4,
                    f"Preset {preset_name} (folga={expected_clearance:.2f} mm): diâmetro={meas_d:.2f} mm")
        bm_c.free()
        bpy.data.meshes.remove(cav_m, do_unlink=True)


    # -------------------------------------------------------------
    # Teste 3: Chave Tipo Cápsula (Anti-Rotação)
    # -------------------------------------------------------------
    print("\n--- Teste 3: Chave Tipo Cápsula (Anti-Rotação) ---")
    capsule_pin = create_pin_mesh_data(
        name="test_capsule_pin",
        connector_type='CAPSULE',
        diameter=8.0,
        length=10.0,
        chamfer=0.8,
        is_cavity=False,
    )
    bm_caps = bmesh.new()
    bm_caps.from_mesh(capsule_pin)
    assert_test(all(e.is_manifold for e in bm_caps.edges), "Chave cápsula macho é 100% manifold")
    # Bounds em X (largura) e Y (comprimento)
    xs = [v.co.x for v in bm_caps.verts]
    ys = [v.co.y for v in bm_caps.verts]
    width = max(xs) - min(xs)
    length_y = max(ys) - min(ys)
    assert_test(abs(width - 8.0) < 0.1, f"Largura da chave cápsula é 8.0 mm (medido: {width:.2f})")
    assert_test(length_y > width * 1.5, f"Formato oblongo anti-rotação confirmado (comprimento Y={length_y:.2f} > 1.5x largura)")
    bm_caps.free()
    bpy.data.meshes.remove(capsule_pin, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 4: Cálculo de Posições (Centro, Linha 2, Linha 3, Grade 4)
    # -------------------------------------------------------------
    print("\n--- Teste 4: Distribuições Automáticas no Plano ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()

    # Cria cubo 100x100x100 mm (0.100 m)
    bpy.ops.mesh.primitive_cube_add(size=0.100, location=(0, 0, 0))
    cube = bpy.context.active_object

    plane_origin = Vector((0, 0, 0))
    plane_normal = Vector((0, 0, 1))

    # Centro: deve retornar 1 ponto
    pts_center = compute_connector_positions(
        cube.data, cube.matrix_world, plane_origin, plane_normal, distribution='CENTER', edge_margin_mm=5.0, unit_scale=1000.0
    )
    assert_test(len(pts_center) == 1, "Distribuição CENTER produz exatamente 1 ponto")
    assert_test((pts_center[0] - plane_origin).length < 1e-4, "Ponto CENTER coincide com o centro")

    # Linear 2: deve retornar 2 pontos simétricos
    pts_lin2 = compute_connector_positions(
        cube.data, cube.matrix_world, plane_origin, plane_normal, distribution='LINEAR_2', edge_margin_mm=5.0, unit_scale=1000.0
    )
    assert_test(len(pts_lin2) == 2, "Distribuição LINEAR_2 produz exatamente 2 pontos")
    dist_lin2 = (pts_lin2[0] - pts_lin2[1]).length * 1000.0
    assert_test(dist_lin2 > 20.0, f"Distância entre pinos em LINEAR_2 é significativa ({dist_lin2:.1f} mm)")

    # Grid 4: deve retornar 4 pontos
    pts_grid4 = compute_connector_positions(
        cube.data, cube.matrix_world, plane_origin, plane_normal, distribution='GRID_4', edge_margin_mm=5.0, unit_scale=1000.0
    )
    assert_test(len(pts_grid4) == 4, "Distribuição GRID_4 produz exatamente 4 pontos")


    # -------------------------------------------------------------
    # Teste 5: Validação de Sobreposição (Rejeição de Conectores Colidentes)
    # -------------------------------------------------------------
    print("\n--- Teste 5: Detecção e Bloqueio de Sobreposição ---")
    overlapping_pts = [Vector((0, 0, 0)), Vector((2.0, 0, 0))]  # distância = 2mm
    blocked = False
    try:
        validate_connectors(overlapping_pts, diameter_mm=6.0, clearance_per_side_mm=0.15, unit_scale=1.0)
    except ConnectorValidationError:
        blocked = True
    assert_test(blocked, "Sobreposição entre encaixes detectada e bloqueada com ConnectorValidationError")

    # -------------------------------------------------------------
    # Teste 6: Fluxo Completo de Corte com Encaixe (Boolean Union / Difference)
    # -------------------------------------------------------------
    print("\n--- Teste 6: Corte Completo com Encaixe (Parte A Macho, Parte B Cavidade) ---")
    settings = bpy.context.scene.chest_splitter
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)
    bpy.ops.chest.splitter_set_target()

    # Ativa encaixes com preset Normal
    settings.connector_enabled = True
    settings.connector_type = 'CYLINDER'
    settings.connector_male_part = 'A'
    settings.connector_diameter_mm = 8.0
    settings.connector_length_mm = 10.0
    settings.connector_chamfer_mm = 0.8
    settings.clearance_preset = 'NORMAL'
    settings.clearance_per_side_mm = 0.15
    settings.connector_distribution = 'CENTER'

    # Gera preview
    bpy.ops.chest.splitter_generate_preview()

    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com encaixes gerado com sucesso")
    assert_test(settings.part_a_is_manifold, "Parte A (com pino macho unido) é 100% manifold")
    assert_test(settings.part_b_is_manifold, "Parte B (com cavidade subtraída) é 100% manifold")
    assert_test(settings.part_a_non_manifold_edges == 0, "Parte A tem 0 arestas não-manifold")
    assert_test(settings.part_b_non_manifold_edges == 0, "Parte B tem 0 arestas não-manifold")

    # -------------------------------------------------------------
    # Teste 7: Inversão Macho / Fêmea
    # -------------------------------------------------------------
    print("\n--- Teste 7: Inversão Macho / Fêmea ---")
    vol_a_male = settings.part_a_volume_mm3
    vol_b_female = settings.part_b_volume_mm3

    # Inverte para macho na Parte B
    bpy.ops.chest.splitter_invert_male_female()
    assert_test(settings.connector_male_part == 'B', "connector_male_part alterado para 'B'")

    vol_a_female = settings.part_a_volume_mm3
    vol_b_male = settings.part_b_volume_mm3

    # Parte B (agora macho) deve ter volume maior do que quando era fêmea
    assert_test(vol_b_male > vol_b_female,
                f"Parte B com macho ({vol_b_male:,.0f} mm³) tem volume maior que com cavidade ({vol_b_female:,.0f} mm³)")
    assert_test(vol_a_female < vol_a_male,
                f"Parte A com cavidade ({vol_a_female:,.0f} mm³) tem volume menor que com macho ({vol_a_male:,.0f} mm³)")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold,
                "Ambas as partes continuam 100% manifold após inversão de macho/fêmea")

    # -------------------------------------------------------------
    # Teste 8: Multi-Encaixes (2 Pinos e 4 Pinos)
    # -------------------------------------------------------------
    print("\n--- Teste 8: Múltiplos Encaixes (LINEAR_2 e GRID_4) ---")
    settings.connector_distribution = 'LINEAR_2'
    bpy.ops.chest.splitter_generate_preview()
    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com 2 pinos lineares gerado com sucesso")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Partes com 2 pinos são manifold")

    settings.connector_distribution = 'GRID_4'
    bpy.ops.chest.splitter_generate_preview()
    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com 4 pinos em grade gerado com sucesso")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Partes com 4 pinos são manifold")

    # -------------------------------------------------------------
    # Teste 9: Confirmação Definitiva (Commit) com Encaixes
    # -------------------------------------------------------------
    print("\n--- Teste 9: Confirmação Definitiva com Encaixes ---")
    bpy.ops.chest.splitter_commit_parts()
    assert_test(settings.session_status == 'COMMITTED', "Status avançou para COMMITTED com encaixes")

    parts_col = next((c for c in bpy.context.scene.collection.children_recursive if c.name == COLLECTION_PARTS_NAME), None)
    assert_test(parts_col is not None, "Coleção de partes finais existe")
    obj_final_a = parts_col.objects.get(f"{cube.name}{PART_A_SUFFIX}")
    obj_final_b = parts_col.objects.get(f"{cube.name}{PART_B_SUFFIX}")
    assert_test(obj_final_a is not None and obj_final_b is not None, "Objetos finais A e B criados com encaixes")

    # -------------------------------------------------------------
    # Teste 10: Regressão — Chave Cápsula em Cubo 97.2 mm (Aferição Dimensional Exata)
    # -------------------------------------------------------------
    print("\n--- Teste 10: Regressão do Conector Cápsula no Cubo 97.2 mm ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()

    bpy.ops.mesh.primitive_cube_add(size=0.0972, location=(0, 0, 0))
    cube_user = bpy.context.active_object
    cube_user.name = "Cube_97mm"
    bpy.context.view_layer.objects.active = cube_user
    cube_user.select_set(True)
    bpy.ops.chest.splitter_set_target()

    settings = bpy.context.scene.chest_splitter
    settings.connector_enabled = True
    settings.connector_type = 'CAPSULE'
    settings.connector_male_part = 'A'
    settings.connector_diameter_mm = 10.0
    settings.connector_length_mm = 10.0
    settings.connector_chamfer_mm = 0.8
    settings.clearance_per_side_mm = 0.10
    settings.end_clearance_mm = 0.50
    settings.connector_distribution = 'CENTER'

    bpy.ops.chest.splitter_generate_preview()

    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview com conector Cápsula gerado com sucesso")
    assert_test(settings.part_a_is_manifold, "Parte A (Cápsula macho) é 100% manifold")
    assert_test(settings.part_b_is_manifold, "Parte B (Cápsula cavidade) é 100% manifold")
    assert_test(settings.part_a_non_manifold_edges == 0, "Parte A tem exatamente 0 arestas não-manifold")
    assert_test(settings.part_b_non_manifold_edges == 0, "Parte B tem exatamente 0 arestas não-manifold")

    # Aferição dimensional: Part A deve ter 97.2 x 97.2 x 58.6 mm (48.6 + 10.0)
    dims_a = settings.part_a_dims_mm
    assert_test(abs(dims_a[0] - 97.2) < 0.2, f"Largura X da Parte A = {dims_a[0]:.1f} mm (~97.2 mm)")
    assert_test(abs(dims_a[1] - 97.2) < 0.2, f"Profundidade Y da Parte A = {dims_a[1]:.1f} mm (~97.2 mm)")
    assert_test(abs(dims_a[2] - 58.6) < 0.2, f"Altura Z da Parte A = {dims_a[2]:.1f} mm (~58.6 mm com pino)")

    # Part B deve ter 97.2 x 97.2 x 48.6 mm
    dims_b = settings.part_b_dims_mm
    assert_test(abs(dims_b[0] - 97.2) < 0.2, f"Largura X da Parte B = {dims_b[0]:.1f} mm (~97.2 mm)")
    assert_test(abs(dims_b[1] - 97.2) < 0.2, f"Profundidade Y da Parte B = {dims_b[1]:.1f} mm (~97.2 mm)")
    assert_test(abs(dims_b[2] - 48.6) < 0.2, f"Altura Z da Parte B = {dims_b[2]:.1f} mm (~48.6 mm)")

    print(f"\n>>> TODOS OS {passed}/{total} TESTES DA FASE 2 PASSARAM COM SUCESSO! <<<\n")


if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\nERRO FATAL NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
