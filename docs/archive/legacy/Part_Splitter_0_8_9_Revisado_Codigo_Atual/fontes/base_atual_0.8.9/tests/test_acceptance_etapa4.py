"""Bateria de testes de aceitação formal para a Etapa 4 do Part Splitter.

Valida os critérios obrigatórios definidos no plano técnico:
- L4: Cubo 40³, região plana 10×10, profundidade 3 mm (Bloco 10×10×3 = 300 mm³, restante = 63700 mm³).
- L5: Extração com profundidade > espessura (bloqueio sem clamp silencioso vs corte passante explícito).
- Decisão Automática: detecção correta entre DETACH (saliência) e EXTRUDE (região plana) com justificativa.
- Extração com Encaixes: conectores aplicados na interface da peça extraída e cavidade receptora.
"""

import sys
import os
import math
import unittest
import bpy
import bmesh
from mathutils import Vector, Matrix

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src
from src.geometry_loop import (
    capture_edge_loop,
    analyze_loop_region,
    slice_mesh_by_loop,
    slice_mesh_by_loop_extrude,
)
from src.diagnostic import get_scene_scale_to_mm
from src.constants import COLLECTION_PREVIEWS_NAME, PREVIEW_A_NAME, PREVIEW_B_NAME


def assert_test(cond: bool, msg: str):
    if not cond:
        print(f"  [FALHA] {msg}")
        raise AssertionError(msg)
    print(f"  [OK] {msg}")


def build_cube_with_subface(cube_size: float = 40.0, sub_size: float = 10.0, name: str = "CubeSubface"):
    """Constrói um cubo 3D manifold com uma sub-região quadrada no topo (Z = +cube_size/2)."""
    bm = bmesh.new()
    half_c = cube_size / 2.0
    half_s = sub_size / 2.0

    b0 = bm.verts.new((-half_c, -half_c, -half_c))
    b1 = bm.verts.new((half_c, -half_c, -half_c))
    b2 = bm.verts.new((half_c, half_c, -half_c))
    b3 = bm.verts.new((-half_c, half_c, -half_c))

    t0 = bm.verts.new((-half_c, -half_c, half_c))
    t1 = bm.verts.new((half_c, -half_c, half_c))
    t2 = bm.verts.new((half_c, half_c, half_c))
    t3 = bm.verts.new((-half_c, half_c, half_c))

    s0 = bm.verts.new((-half_s, -half_s, half_c))
    s1 = bm.verts.new((half_s, -half_s, half_c))
    s2 = bm.verts.new((half_s, half_s, half_c))
    s3 = bm.verts.new((-half_s, half_s, half_c))

    bm.verts.ensure_lookup_table()

    bm.faces.new((b3, b2, b1, b0))
    bm.faces.new((b0, b1, t1, t0))
    bm.faces.new((b1, b2, t2, t1))
    bm.faces.new((b2, b3, t3, t2))
    bm.faces.new((b3, b0, t0, t3))

    bm.faces.new((t0, t1, s1, s0))
    bm.faces.new((t1, t2, s2, s1))
    bm.faces.new((t2, t3, s3, s2))
    bm.faces.new((t3, t0, s0, s3))
    seed_face = bm.faces.new((s0, s1, s2, s3))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    seed_idx = seed_face.index
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj, seed_idx


def build_protrusion_obj(name: str = "ProtrusionObj"):
    """Constrói objeto com Base 60x60x20 e saliência 24x18x15 (parede inclinada)."""
    bm = bmesh.new()
    b0 = bm.verts.new((-30.0, -30.0, 0.0))
    b1 = bm.verts.new((30.0, -30.0, 0.0))
    b2 = bm.verts.new((30.0, 30.0, 0.0))
    b3 = bm.verts.new((-30.0, 30.0, 0.0))

    b4 = bm.verts.new((-30.0, -30.0, 20.0))
    b5 = bm.verts.new((30.0, -30.0, 20.0))
    b6 = bm.verts.new((30.0, 30.0, 20.0))
    b7 = bm.verts.new((-30.0, 30.0, 20.0))

    p0 = bm.verts.new((-12.0, -9.0, 20.0))
    p1 = bm.verts.new((12.0, -9.0, 20.0))
    p2 = bm.verts.new((12.0, 9.0, 20.0))
    p3 = bm.verts.new((-12.0, 9.0, 20.0))

    t0 = bm.verts.new((-10.0, -7.0, 35.0))
    t1 = bm.verts.new((10.0, -7.0, 35.0))
    t2 = bm.verts.new((10.0, 7.0, 35.0))
    t3 = bm.verts.new((-10.0, 7.0, 35.0))

    bm.verts.ensure_lookup_table()
    bm.faces.new((b3, b2, b1, b0))
    bm.faces.new((b0, b1, b5, b4))
    bm.faces.new((b1, b2, b6, b5))
    bm.faces.new((b2, b3, b7, b6))
    bm.faces.new((b3, b0, b4, b7))

    bm.faces.new((b4, b5, p1, p0))
    bm.faces.new((b5, b6, p2, p1))
    bm.faces.new((b6, b7, p3, p2))
    bm.faces.new((b7, b4, p0, p3))

    bm.faces.new((p0, p1, t1, t0))
    bm.faces.new((p1, p2, t2, t1))
    bm.faces.new((p2, p3, t3, t2))
    bm.faces.new((p3, p0, t0, t3))
    bm.faces.new((t0, t1, t2, t3))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def select_loop_and_seed(obj: bpy.types.Object, loop_filter_func, seed_filter_func):
    """Auxiliar para selecionar arestas do loop e face semente em Edit Mode."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)

    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = False

    loop_edges = [e for e in bm.edges if loop_filter_func(e)]
    for e in loop_edges:
        e.select = True
    bmesh.update_edit_mesh(obj.data)

    res_cap = bpy.ops.chest.splitter_capture_loop()
    assert_test(res_cap == {'FINISHED'}, f"Loop capturado com {len(loop_edges)} arestas.")

    for e in bm.edges:
        e.select = False
    seed_faces = [f for f in bm.faces if seed_filter_func(f)]
    assert_test(len(seed_faces) > 0, "Face semente encontrada.")
    seed_faces[0].select = True
    bmesh.update_edit_mesh(obj.data)

    res_seed = bpy.ops.chest.splitter_define_seed_face()
    bpy.ops.object.mode_set(mode='OBJECT')
    assert_test(res_seed == {'FINISHED'}, "Face semente definida com sucesso.")


def test_l4():
    print("\n--- Teste L4: Cubo 40³, região plana 10×10, profundidade 3 mm ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001  # 1 BU = 1 mm
    settings = scene.chest_splitter

    cube_obj, seed_idx = build_cube_with_subface(cube_size=40.0, sub_size=10.0, name="Cube_L4")
    settings.target_object = cube_obj
    settings.split_mode = 'LOOP'

    # Seleciona o loop do contorno 10x10 em Z=20
    def loop_filter(e):
        return (
            abs(e.verts[0].co.z - 20.0) < 1e-3 and abs(e.verts[1].co.z - 20.0) < 1e-3
            and abs(e.verts[0].co.x) <= 5.01 and abs(e.verts[0].co.y) <= 5.01
            and abs(e.verts[1].co.x) <= 5.01 and abs(e.verts[1].co.y) <= 5.01
        )

    def seed_filter(f):
        c = f.calc_center_median()
        return abs(c.z - 20.0) < 1e-3 and abs(c.x) < 4.0 and abs(c.y) < 4.0

    select_loop_and_seed(cube_obj, loop_filter, seed_filter)

    settings.loop_behavior = 'EXTRUDE'
    settings.loop_extrude_depth_mm = 3.0
    settings.loop_through_cut = False
    settings.connector_enabled = False

    res = bpy.ops.chest.splitter_generate_preview()
    assert_test(res == {'FINISHED'}, "Preview de extração com profundidade gerado.")
    assert_test(settings.session_status == 'PREVIEW_VALID', "Status é PREVIEW_VALID.")

    # Volume do bloco extraído: 10 × 10 × 3 = 300 mm³
    vol_a = settings.part_a_volume_mm3
    vol_b = settings.part_b_volume_mm3
    sum_vol = settings.part_sum_volume_mm3

    print(f"  Volume Parte A (extraído): {vol_a:.2f} mm³ (esperado: 300.0 mm³)")
    print(f"  Volume Parte B (restante): {vol_b:.2f} mm³ (esperado: 63,700.0 mm³)")
    print(f"  Volume Total: {sum_vol:.2f} mm³ (esperado: 64,000.0 mm³)")

    assert_test(abs(vol_a - 300.0) < 1.5, f"Volume da Parte A é ~300 mm³ (diferença: {abs(vol_a - 300.0):.2f} mm³).")
    assert_test(abs(vol_b - 63700.0) < 15.0, f"Volume da Parte B é ~63700 mm³ (diferença: {abs(vol_b - 63700.0):.2f} mm³).")
    assert_test(abs(sum_vol - 64000.0) < 15.0, f"Soma dos volumes conservada (diferença: {abs(sum_vol - 64000.0):.2f} mm³).")

    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Ambas as partes são 100% manifold.")


def test_l5():
    print("\n--- Teste L5: Extração > espessura (bloqueio sem clamp vs corte passante) ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001
    settings = scene.chest_splitter

    cube_obj, seed_idx = build_cube_with_subface(cube_size=40.0, sub_size=10.0, name="Cube_L5")
    settings.target_object = cube_obj
    settings.split_mode = 'LOOP'

    def loop_filter(e):
        return (
            abs(e.verts[0].co.z - 20.0) < 1e-3 and abs(e.verts[1].co.z - 20.0) < 1e-3
            and abs(e.verts[0].co.x) <= 5.01 and abs(e.verts[0].co.y) <= 5.01
            and abs(e.verts[1].co.x) <= 5.01 and abs(e.verts[1].co.y) <= 5.01
        )

    def seed_filter(f):
        c = f.calc_center_median()
        return abs(c.z - 20.0) < 1e-3 and abs(c.x) < 4.0 and abs(c.y) < 4.0

    select_loop_and_seed(cube_obj, loop_filter, seed_filter)

    # 1. Caso sem corte passante: profundidade 50 mm > 40 mm espessura -> DEVE BLOQUEAR COM ERRO
    settings.loop_behavior = 'EXTRUDE'
    settings.loop_extrude_depth_mm = 50.0
    settings.loop_through_cut = False

    try:
        res = bpy.ops.chest.splitter_generate_preview()
        cancelled = (res == {'CANCELLED'})
    except RuntimeError:
        cancelled = True

    assert_test(cancelled, "Preview bloqueado quando profundidade excede espessura.")
    assert_test(settings.session_status == 'PREVIEW_INVALID', "Status definido como PREVIEW_INVALID.")
    assert_test("ultrapassa a espessura da peça" in settings.last_status, f"Erro explicativo com aviso: {settings.last_status}")
    assert_test(bpy.ops.chest.splitter_commit_parts.poll() is False, "Confirmação bloqueada de forma segura.")

    # 2. Caso com corte passante ativado explicitamente
    settings.loop_through_cut = True
    res_through = bpy.ops.chest.splitter_generate_preview()
    assert_test(res_through == {'FINISHED'}, "Corte passante executou com sucesso.")
    assert_test(settings.session_status == 'PREVIEW_VALID', "Status é PREVIEW_VALID com corte passante.")

    vol_col = settings.part_a_volume_mm3  # Coluna passante 10x10x40 = 4000 mm³
    vol_rest = settings.part_b_volume_mm3 # Cubo furado 64000 - 4000 = 60000 mm³

    print(f"  Volume Coluna Passante: {vol_col:.2f} mm³ (esperado: 4000.0 mm³)")
    print(f"  Volume Cubo Furado: {vol_rest:.2f} mm³ (esperado: 60,000.0 mm³)")

    assert_test(abs(vol_col - 4000.0) < 20.0, "Volume da coluna passante ~4000 mm³.")
    assert_test(abs(vol_rest - 60000.0) < 50.0, "Volume do bloco furado ~60000 mm³.")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Ambas as peças com furo passante são manifold.")


def test_auto_decision():
    print("\n--- Teste Decisão Automática (AUTO): Plano vs Saliência ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001
    settings = scene.chest_splitter

    # 1. Região plana no cubo -> Deve detectar EXTRUDE
    cube_obj, seed_idx = build_cube_with_subface(cube_size=40.0, sub_size=10.0, name="Cube_Auto")
    settings.target_object = cube_obj
    settings.split_mode = 'LOOP'

    def loop_filter_cube(e):
        return (
            abs(e.verts[0].co.z - 20.0) < 1e-3 and abs(e.verts[1].co.z - 20.0) < 1e-3
            and abs(e.verts[0].co.x) <= 5.01 and abs(e.verts[0].co.y) <= 5.01
            and abs(e.verts[1].co.x) <= 5.01 and abs(e.verts[1].co.y) <= 5.01
        )

    def seed_filter_cube(f):
        c = f.calc_center_median()
        return abs(c.z - 20.0) < 1e-3 and abs(c.x) < 4.0 and abs(c.y) < 4.0

    select_loop_and_seed(cube_obj, loop_filter_cube, seed_filter_cube)

    settings.loop_behavior = 'AUTO'
    settings.loop_extrude_depth_mm = 4.0
    settings.loop_through_cut = False

    res_cube = bpy.ops.chest.splitter_generate_preview()
    assert_test(res_cube == {'FINISHED'}, "Preview AUTO no cubo plano gerado.")
    assert_test(settings.loop_detected_mode == 'EXTRUDE', f"Modo detectado no cubo plano é EXTRUDE: {settings.loop_detected_mode}")
    assert_test("Região plana" in settings.loop_auto_reason, f"Motivo claro: {settings.loop_auto_reason}")

    # 2. Saliência 3D na base -> Deve detectar DETACH
    prot_obj = build_protrusion_obj("Prot_Auto")
    settings.target_object = prot_obj

    def loop_filter_prot(e):
        return (
            abs(e.verts[0].co.z - 20.0) < 1e-3 and abs(e.verts[1].co.z - 20.0) < 1e-3
            and abs(e.verts[0].co.x) <= 12.01 and abs(e.verts[0].co.y) <= 9.01
            and abs(e.verts[1].co.x) <= 12.01 and abs(e.verts[1].co.y) <= 9.01
        )

    def seed_filter_prot(f):
        return f.calc_center_median().z > 20.01

    select_loop_and_seed(prot_obj, loop_filter_prot, seed_filter_prot)

    settings.loop_behavior = 'AUTO'
    res_prot = bpy.ops.chest.splitter_generate_preview()
    assert_test(res_prot == {'FINISHED'}, "Preview AUTO na saliência 3D gerado.")
    assert_test(settings.loop_detected_mode == 'DETACH', f"Modo detectado na saliência 3D é DETACH: {settings.loop_detected_mode}")
    assert_test("Saliência 3D" in settings.loop_auto_reason, f"Motivo claro: {settings.loop_auto_reason}")


def test_extrude_with_connectors():
    print("\n--- Teste Extração com Encaixes na Interface ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001
    settings = scene.chest_splitter

    # Cubo 60x60x40 com sub-face 24x24 mm
    cube_obj, seed_idx = build_cube_with_subface(cube_size=60.0, sub_size=24.0, name="Cube_Conn")
    settings.target_object = cube_obj
    settings.split_mode = 'LOOP'

    def loop_filter(e):
        return (
            abs(e.verts[0].co.z - 30.0) < 1e-3 and abs(e.verts[1].co.z - 30.0) < 1e-3
            and abs(e.verts[0].co.x) <= 12.01 and abs(e.verts[0].co.y) <= 12.01
            and abs(e.verts[1].co.x) <= 12.01 and abs(e.verts[1].co.y) <= 12.01
        )

    def seed_filter(f):
        c = f.calc_center_median()
        return abs(c.z - 30.0) < 1e-3 and abs(c.x) < 8.0 and abs(c.y) < 8.0

    select_loop_and_seed(cube_obj, loop_filter, seed_filter)

    settings.loop_behavior = 'EXTRUDE'
    settings.loop_extrude_depth_mm = 10.0
    settings.loop_through_cut = False

    # Habilita conectores
    settings.connector_enabled = True
    settings.connector_type = 'CYLINDER'
    settings.connector_diameter_mm = 5.0
    settings.connector_length_mm = 5.0
    settings.connector_male_part = 'A'
    settings.connector_distribution = 'CENTER'

    res = bpy.ops.chest.splitter_generate_preview()
    assert_test(res == {'FINISHED'}, "Preview com extração e conector gerado com sucesso.")
    assert_test(settings.session_status == 'PREVIEW_VALID', "Status é PREVIEW_VALID.")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Ambas as peças com conector são 100% manifold.")


def run_all_tests():
    print("=" * 70)
    print("EXECUTANDO TESTES DE ACEITAÇÃO DA ETAPA 4 (L4, L5, AUTO, ENCAIXES)")
    print("=" * 70)

    test_l4()
    test_l5()
    test_auto_decision()
    test_extrude_with_connectors()

    print("\n" + "=" * 70)
    print("TODOS OS TESTES DE ACEITAÇÃO DA ETAPA 4 FORAM APROVADOS COM SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
