"""Bateria de testes de aceitação formal para as Etapas 1 e 2 do Part Splitter.

Valida os critérios obrigatórios definidos no plano técnico:
- P1: Bloco 60x40x30 cortado por plano central Z (duas peças fechadas, volumes positivos, soma conservada).
- L1: Base 60x60x20 com saliência 24x18x15 e paredes inclinadas (destaque da saliência, interface 24x18, sem afetar o resto da base).
- L3: Inversão da ordem dos vértices/arestas do loop (normal e orientação física estritamente invariantes).
- G1: Objeto sob transformações complexas (translação arbitrária, rotação, escala não uniforme e escala negativa) com alinhamento em mundo.
- G2: Invariância de unidades em escalas de cena distintas (scale_length = 1.0, 0.01 e 0.001) mantendo dimensões reais idênticas em mm.
"""

import sys
import os
import math
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src
from src.geometry_plane import slice_mesh_by_plane, evaluate_bmesh_metrics
from src.geometry_loop import slice_mesh_by_loop, capture_edge_loop
from src.diagnostic import analyze_target_mesh, get_scene_scale_to_mm


def assert_test(cond, msg):
    if not cond:
        print(f"  [FALHA] {msg}")
        raise AssertionError(msg)
    print(f"  [OK] {msg}")


def build_protrusion_bmesh():
    """Constrói malha contínua manifold: Base 60x60x20 e saliência 24x18x15 (parede inclinada)."""
    bm = bmesh.new()

    # Vértices da base inferior (Z=0)
    b0 = bm.verts.new((-30.0, -30.0, 0.0))
    b1 = bm.verts.new((30.0, -30.0, 0.0))
    b2 = bm.verts.new((30.0, 30.0, 0.0))
    b3 = bm.verts.new((-30.0, 30.0, 0.0))

    # Vértices da base superior externa (Z=20)
    b4 = bm.verts.new((-30.0, -30.0, 20.0))
    b5 = bm.verts.new((30.0, -30.0, 20.0))
    b6 = bm.verts.new((30.0, 30.0, 20.0))
    b7 = bm.verts.new((-30.0, 30.0, 20.0))

    # Vértices da base da saliência (Z=20) - 24x18 mm
    p0 = bm.verts.new((-12.0, -9.0, 20.0))
    p1 = bm.verts.new((12.0, -9.0, 20.0))
    p2 = bm.verts.new((12.0, 9.0, 20.0))
    p3 = bm.verts.new((-12.0, 9.0, 20.0))

    # Vértices do topo da saliência (Z=35) - 20x14 mm (paredes inclinadas)
    t0 = bm.verts.new((-10.0, -7.0, 35.0))
    t1 = bm.verts.new((10.0, -7.0, 35.0))
    t2 = bm.verts.new((10.0, 7.0, 35.0))
    t3 = bm.verts.new((-10.0, 7.0, 35.0))

    bm.verts.ensure_lookup_table()

    # Fundo da base
    bm.faces.new((b3, b2, b1, b0))

    # Laterais da base
    bm.faces.new((b0, b1, b5, b4))
    bm.faces.new((b1, b2, b6, b5))
    bm.faces.new((b2, b3, b7, b6))
    bm.faces.new((b3, b0, b4, b7))

    # Topo da base ao redor da saliência (4 quadriláteros conectando b4..b7 a p0..p3)
    bm.faces.new((b4, b5, p1, p0))
    bm.faces.new((b5, b6, p2, p1))
    bm.faces.new((b6, b7, p3, p2))
    bm.faces.new((b7, b4, p0, p3))

    # Paredes inclinadas da saliência
    bm.faces.new((p0, p1, t1, t0))
    bm.faces.new((p1, p2, t2, t1))
    bm.faces.new((p2, p3, t3, t2))
    bm.faces.new((p3, p0, t0, t3))

    # Topo da saliência
    bm.faces.new((t0, t1, t2, t3))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def test_p1():
    print("\n--- Teste P1: Bloco 60x40x30 cortado por plano central Z ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene

    # Cria bloco 60x40x30
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((60.0, 40.0, 30.0)), verts=bm.verts[:])
    mesh = bpy.data.meshes.new("Block_60x40x30")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("Block", mesh)
    scene.collection.objects.link(obj)
    orig_vol = 60.0 * 40.0 * 30.0  # 72,000 mm³

    mesh_a = bpy.data.meshes.new("P1_A")
    mesh_b = bpy.data.meshes.new("P1_B")

    # Corta pelo plano central Z=0 com unit_scale=1.0
    report = slice_mesh_by_plane(
        source_mesh=obj.data,
        matrix_world=obj.matrix_world,
        plane_origin=Vector((0, 0, 0)),
        plane_normal=Vector((0, 0, 1)),
        target_mesh_a=mesh_a,
        target_mesh_b=mesh_b,
        invert_sides=False,
        unit_scale=1.0,
    )

    assert_test(report["A"]["is_manifold"], "Parte A é 100% manifold")
    assert_test(report["B"]["is_manifold"], "Parte B é 100% manifold")
    assert_test(report["A"]["volume_mm3"] > 0, "Volume Parte A é positivo")
    assert_test(report["B"]["volume_mm3"] > 0, "Volume Parte B é positivo")

    sum_vol = report["sum_volume_mm3"]
    vol_diff = abs(sum_vol - orig_vol) / orig_vol
    assert_test(vol_diff < 0.005, f"Conservação de volume estrita (< 0.5%): soma={sum_vol:.1f} vs orig={orig_vol:.1f} (diff={vol_diff*100:.3f}%)")

    # Interface formal
    iface = report.get("interface")
    assert_test(iface is not None, "CutInterface formal gerada no corte por plano")
    assert_test(abs(iface.width_mm - 60.0) < 0.1, f"Largura da interface plana é 60 mm (obtido {iface.width_mm:.2f})")
    assert_test(abs(iface.height_mm - 40.0) < 0.1, f"Altura da interface plana é 40 mm (obtido {iface.height_mm:.2f})")
    assert_test(iface.is_planar, "Interface do plano é 100% planar")


def test_l1_and_l3():
    print("\n--- Testes L1 e L3: Saliência com parede inclinada e invariância de orientação ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001  # 1 BU = 1 mm para geometrias modeladas diretamente em milímetros

    bm = build_protrusion_bmesh()
    mesh = bpy.data.meshes.new("Protrusion_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    # Posiciona o modelo fora da origem com rotação para testar alinhamento
    obj = bpy.data.objects.new("Protrusion_Model", mesh)
    scene.collection.objects.link(obj)
    obj.location = Vector((100.0, 50.0, 25.0))
    bpy.context.view_layer.update()

    # Identifica o contorno de 4 arestas da base da saliência em Z=20 local
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    loop_edges = [
        e for e in bm.edges
        if abs(e.verts[0].co.z - 20.0) < 1e-4 and abs(e.verts[1].co.z - 20.0) < 1e-4
        and abs(e.verts[0].co.x) <= 12.01 and abs(e.verts[0].co.y) <= 9.01
        and abs(e.verts[1].co.x) <= 12.01 and abs(e.verts[1].co.y) <= 9.01
    ]
    assert_test(len(loop_edges) == 4, f"4 arestas encontradas na base da saliência: {len(loop_edges)}")

    # Ordena vértices do ciclo
    v_order = [loop_edges[0].verts[0], loop_edges[0].verts[1]]
    curr_e = loop_edges[0]
    while len(v_order) < 4:
        last_v = v_order[-1]
        next_e = [e for e in loop_edges if e != curr_e and last_v in e.verts][0]
        next_v = next_e.verts[0] if next_e.verts[1] == last_v else next_e.verts[1]
        v_order.append(next_v)
        curr_e = next_e

    indices_order1 = [v.index for v in v_order]
    indices_order2 = list(reversed(indices_order1))

    # Face semente no topo da saliência (Z > 30)
    seed_face = [f for f in bm.faces if f.calc_center_median().z > 30.0][0]
    seed_idx = seed_face.index
    bm.free()

    # Executa corte com ordem 1
    res1 = slice_mesh_by_loop(obj, obj.name, indices_order1, seed_idx, scene)
    bm_a1, bm_b1 = res1[0], res1[1]

    # Verifica manifoldness e métricas
    m_a1 = evaluate_bmesh_metrics(bm_a1, unit_scale=1.0)
    m_b1 = evaluate_bmesh_metrics(bm_b1, unit_scale=1.0)
    assert_test(m_a1["is_manifold"], "Parte A (saliência destacada) é 100% manifold")
    assert_test(m_b1["is_manifold"], "Parte B (base preservada) é 100% manifold")
    assert_test(m_a1["non_manifold_edges"] == 0, "Parte A possui 0 arestas não-manifold")
    assert_test(m_b1["non_manifold_edges"] == 0, "Parte B possui 0 arestas não-manifold")

    # Dimensões da interface local: deve ser exatamente 24x18 mm (NÃO 60x60!)
    iface1 = res1.interface
    assert_test(iface1 is not None, "CutInterface formal gerada para corte por loop")
    assert_test(abs(iface1.width_mm - 24.0) < 0.1, f"Largura da interface do loop é 24 mm (obtido {iface1.width_mm:.2f})")
    assert_test(abs(iface1.height_mm - 18.0) < 0.1, f"Altura da interface do loop é 18 mm (obtido {iface1.height_mm:.2f})")

    # Alinhamento em World Space: centroide de Parte A deve estar próximo da localização do objeto (X~100, Y~50)
    xs_a = [v.co.x for v in bm_a1.verts]
    center_x = sum(xs_a) / len(xs_a)
    assert_test(abs(center_x - 100.0) < 15.0, f"Parte A está em coordenadas de mundo alinhada ao objeto (centro X={center_x:.1f})")

    # --- Teste L3: Inversão da ordem dos vértices do loop ---
    res2 = slice_mesh_by_loop(obj, obj.name, indices_order2, seed_idx, scene)
    bm_a2, bm_b2 = res2[0], res2[1]
    iface2 = res2.interface

    # A normal gerada deve apontar exatamente na mesma direção
    dot_normals = iface1.normal_a_to_b_world.dot(iface2.normal_a_to_b_world)
    assert_test(dot_normals > 0.999, f"L3: Normal da interface é invariante à ordem de seleção das arestas (dot={dot_normals:.4f})")
    assert_test(abs(iface1.width_mm - iface2.width_mm) < 0.01, "L3: Largura idêntica sob inversão do loop")
    assert_test(abs(iface1.height_mm - iface2.height_mm) < 0.01, "L3: Altura idêntica sob inversão do loop")

    bm_a1.free()
    bm_b1.free()
    bm_a2.free()
    bm_b2.free()


def test_g1():
    print("\n--- Teste G1: Transformações arbitrárias, escala não uniforme e negativa ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001  # 1 BU = 1 mm

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((40.0, 30.0, 20.0)), verts=bm.verts[:])
    mesh = bpy.data.meshes.new("G1_Cube")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("G1_Obj", mesh)
    scene.collection.objects.link(obj)

    # Translação, rotação arbitrária e escala não uniforme
    obj.location = Vector((25.0, -40.0, 60.0))
    obj.rotation_euler = Euler((math.radians(35), math.radians(-20), math.radians(45)))
    obj.scale = Vector((1.5, 0.8, 1.2))
    bpy.context.view_layer.update()

    diag = analyze_target_mesh(obj, scene)
    assert_test(diag["valid"], "Diagnóstico aceita malha com transformações")
    assert_test(diag["is_manifold"], "Malha avaliada continua manifold")
    # Volume nominal no mundo = (40*1.5) * (30*0.8) * (20*1.2) = 60 * 24 * 24 = 34,560 mm³
    expected_vol = (40.0 * 1.5) * (30.0 * 0.8) * (20.0 * 1.2)
    assert_test(abs(diag["volume_mm3"] - expected_vol) < 1.0, f"Volume avaliado em World Space fidedigno: {diag['volume_mm3']:.1f} vs {expected_vol:.1f}")

    # Escala com determinante negativo (inversão)
    obj.scale = Vector((-1.0, 1.0, 1.0))
    bpy.context.view_layer.update()
    diag_neg = analyze_target_mesh(obj, scene)
    assert_test(diag_neg["is_manifold"], "Malha com escala negativa recalcula normais e mantém manifold")
    assert_test(diag_neg["volume_mm3"] > 0, f"Volume sob escala negativa é positivo: {diag_neg['volume_mm3']:.1f}")


def test_g2():
    print("\n--- Teste G2: Invariância métrica em escalas de cena distintas ---")
    scales_to_test = [1.0, 0.01, 0.001]

    for scale in scales_to_test:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        src.register()
        scene = bpy.context.scene
        scene.unit_settings.system = 'METRIC'
        scene.unit_settings.scale_length = scale

        unit_scale = get_scene_scale_to_mm(scene)
        # 1 BU = (scale * 1000) mm -> 50 mm = 50 / unit_scale BU
        cube_bu = 50.0 / unit_scale

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((cube_bu, cube_bu, cube_bu)), verts=bm.verts[:])
        mesh = bpy.data.meshes.new(f"G2_Cube_{scale}")
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new(f"G2_Obj_{scale}", mesh)
        scene.collection.objects.link(obj)
        bpy.context.view_layer.update()

        diag = analyze_target_mesh(obj, scene)
        expected_vol = 50.0 ** 3  # 125,000 mm³
        assert_test(abs(diag["volume_mm3"] - expected_vol) < 2.0, f"Escala={scale}: Volume de cubo 50mm é 125,000 mm³ (obtido {diag['volume_mm3']:.1f})")
        assert_test(abs(diag["dims_mm"][0] - 50.0) < 0.1, f"Escala={scale}: Dimensão X é 50 mm (obtido {diag['dims_mm'][0]:.2f})")


def run_all():
    print("\n" + "=" * 70)
    print("SUÍTE DE TESTES DE ACEITAÇÃO DAS ETAPAS 1 E 2 (P1, L1, L3, G1, G2)")
    print("=" * 70)
    test_p1()
    test_l1_and_l3()
    test_g1()
    test_g2()
    print("\n" + "=" * 70)
    print("TODOS OS TESTES DE ACEITAÇÃO DAS ETAPAS 1 E 2 PASSARAM COM SUCESSO! [100% OK]")
    print("=" * 70)


if __name__ == "__main__":
    run_all()
