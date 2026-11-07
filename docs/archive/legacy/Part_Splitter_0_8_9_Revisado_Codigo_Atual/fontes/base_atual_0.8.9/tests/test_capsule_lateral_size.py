"""Suíte de Testes Automatizados: Controle Lateral de Encaixes Tipo Cápsula (Anti-Colisão).

Valida:
1. Criação de malha do pino cápsula macho e fêmea com comprimento lateral personalizado.
2. Folga radial uniforme em toda a periferia (X e Y).
3. Cálculo matemático de limites seguros anti-colisão (distância entre centros e margem da borda).
4. Bloqueio por validação quando o limite de colisão é violado.
5. Corte completo de peça com encaixes cápsula alargados (100% manifold).
6. Ajuste protetor automático (clamping) com aviso ao usuário quando o valor excede o limite.
"""

import sys
import os
import unittest
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bpy
import bmesh
import src
from src.geometry_connectors import (
    create_pin_mesh_data,
    compute_connector_layout,
    validate_connectors,
    ConnectorValidationError,
)


def assert_test(cond, msg):
    if not cond:
        raise AssertionError(f"FALHA NO TESTE: {msg}")
    print(f"  [OK] {msg}")


def run_tests():
    print("\n" + "=" * 70)
    print("TESTES: CONTROLE LATERAL DE ENCAIXES TIPO CÁPSULA E LIMITES ANTI-COLISÃO")
    print("=" * 70)

    # -------------------------------------------------------------
    # Teste 1: Geometria de Cápsula com Comprimento Lateral Personalizado
    # -------------------------------------------------------------
    print("\n--- Teste 1: Dimensões Exatas de Macho e Fêmea ---")
    diameter = 6.0
    length_z = 8.0
    lat_len = 22.0
    clearance_side = 0.20
    clearance_end = 0.50

    male_mesh = create_pin_mesh_data(
        name="test_male_capsule",
        connector_type='CAPSULE',
        diameter=diameter,
        length=length_z,
        chamfer=0.8,
        is_cavity=False,
        capsule_length=lat_len,
    )
    bm_m = bmesh.new()
    bm_m.from_mesh(male_mesh)
    assert_test(all(e.is_manifold for e in bm_m.edges), "Macho cápsula alargado é 100% manifold")
    xs_m = [v.co.x for v in bm_m.verts]
    ys_m = [v.co.y for v in bm_m.verts]
    zs_m = [v.co.z for v in bm_m.verts]
    width_m = max(xs_m) - min(xs_m)
    length_m = max(ys_m) - min(ys_m)
    assert_test(abs(width_m - diameter) < 1e-3, f"Espessura do macho = {diameter} mm (medido: {width_m:.2f})")
    assert_test(abs(length_m - lat_len) < 1e-3, f"Comprimento lateral do macho = {lat_len} mm (medido: {length_m:.2f})")
    bm_m.free()
    bpy.data.meshes.remove(male_mesh, do_unlink=True)

    fem_mesh = create_pin_mesh_data(
        name="test_female_capsule",
        connector_type='CAPSULE',
        diameter=diameter,
        length=length_z,
        chamfer=0.0,
        is_cavity=True,
        clearance_side=clearance_side,
        clearance_end=clearance_end,
        capsule_length=lat_len,
    )
    bm_f = bmesh.new()
    bm_f.from_mesh(fem_mesh)
    assert_test(all(e.is_manifold for e in bm_f.edges), "Cavidade fêmea cápsula é 100% manifold")
    xs_f = [v.co.x for v in bm_f.verts]
    ys_f = [v.co.y for v in bm_f.verts]
    width_f = max(xs_f) - min(xs_f)
    length_f = max(ys_f) - min(ys_f)
    exp_w = diameter + 2.0 * clearance_side
    exp_l = lat_len + 2.0 * clearance_side
    assert_test(abs(width_f - exp_w) < 1e-3, f"Espessura da cavidade = {exp_w:.2f} mm (medido: {width_f:.2f})")
    assert_test(abs(length_f - exp_l) < 1e-3, f"Comprimento lateral da cavidade = {exp_l:.2f} mm (medido: {length_f:.2f})")
    bm_f.free()
    bpy.data.meshes.remove(fem_mesh, do_unlink=True)

    # -------------------------------------------------------------
    # Teste 2: Cálculo Matemático de Limites Anti-Colisão
    # -------------------------------------------------------------
    print("\n--- Teste 2: Cálculo dos Limites Seguros ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()

    # Cria bloco 120 x 40 x 30 mm (0.120 x 0.040 x 0.030 m)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cube = bpy.context.active_object
    cube.scale = (0.060, 0.020, 0.015)  # half sizes -> total 120x40x30 mm
    bpy.ops.object.transform_apply(scale=True)

    layout_3 = compute_connector_layout(
        target_mesh=cube.data,
        matrix_world=cube.matrix_world,
        plane_origin=Vector((0, 0, 0)),
        plane_normal=Vector((0, 0, 1)),
        distribution='LINEAR_3',
        edge_margin_mm=4.0,
        unit_scale=1000.0,
        diameter_mm=6.0,
        clearance_per_side_mm=0.15,
    )

    positions = layout_3["positions"]
    assert_test(len(positions) == 3, "LINEAR_3 retornou 3 posições")
    min_pitch = layout_3["min_pitch_mm"]
    pitch_limit = layout_3["pitch_limit_mm"]
    max_safe = layout_3["max_safe_lateral_mm"]
    assert_test(min_pitch > 15.0, f"Espaçamento entre centros = {min_pitch:.1f} mm")
    assert_test(pitch_limit < min_pitch, "pitch_limit deixa parede de segurança entre furos vizinhos")
    assert_test(max_safe <= pitch_limit, f"max_safe_lateral_mm ({max_safe:.1f} mm) respeita pitch_limit")

    # -------------------------------------------------------------
    # Teste 3: Validação de Sobreposição (Bloqueio)
    # -------------------------------------------------------------
    print("\n--- Teste 3: Detecção e Bloqueio de Sobreposição ---")
    # Força um comprimento maior do que a distância entre os centros
    violating_len = min_pitch + 5.0
    blocked = False
    try:
        validate_connectors(
            positions=positions,
            diameter_mm=6.0,
            clearance_per_side_mm=0.15,
            unit_scale=1000.0,
            connector_type='CAPSULE',
            capsule_length_mm=violating_len,
        )
    except ConnectorValidationError as e:
        blocked = True
        print(f"  Mensagem de bloqueio capturada: {e}")
    assert_test(blocked, "Sobreposição entre cápsulas vizinhas foi detectada e bloqueada")

    # -------------------------------------------------------------
    # Teste 4: Corte Completo com Encaixes Cápsula Alargados
    # -------------------------------------------------------------
    print("\n--- Teste 4: Corte Completo com Cápsulas Alargadas (Manifold) ---")
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)
    bpy.ops.chest.splitter_set_target()

    settings = bpy.context.scene.chest_splitter
    settings.connector_enabled = True
    settings.connector_type = 'CAPSULE'
    settings.connector_distribution = 'LINEAR_3'
    settings.connector_diameter_mm = 6.0
    settings.connector_capsule_length_mm = 20.0
    settings.connector_length_mm = 6.0

    bpy.ops.chest.splitter_generate_preview()
    assert_test(settings.session_status == 'PREVIEW_VALID', "Preview gerado com sucesso")
    assert_test(settings.part_a_is_manifold, "Parte A (macho cápsula 20mm) é 100% manifold")
    assert_test(settings.part_b_is_manifold, "Parte B (fêmea cápsula 20mm) é 100% manifold")
    assert_test(settings.part_a_non_manifold_edges == 0, "Parte A tem 0 arestas abertas")
    assert_test(settings.part_b_non_manifold_edges == 0, "Parte B tem 0 arestas abertas")

    # -------------------------------------------------------------
    # Teste 5: Ajuste Protetor Automático (Clamping)
    # -------------------------------------------------------------
    print("\n--- Teste 5: Clamping Protetor com Valor Excessivo ---")
    settings.connector_capsule_length_mm = 60.0  # valor excessivo que causaria colisão
    bpy.ops.chest.splitter_generate_preview()
    assert_test(settings.connector_capsule_length_mm < 60.0,
                f"Valor excessivo foi automaticamente limitado para {settings.connector_capsule_length_mm:.1f} mm")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold,
                "Malhas geradas com clamping continuam 100% manifold e livres de defeitos")

    print("\n" + "=" * 70)
    print("TODOS OS TESTES DE CONTROLE LATERAL DE ENCAIXES PASSARAM COM SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
