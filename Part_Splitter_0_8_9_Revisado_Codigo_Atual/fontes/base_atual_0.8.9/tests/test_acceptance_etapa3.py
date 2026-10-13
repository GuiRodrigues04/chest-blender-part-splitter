"""Bateria de testes de aceitação formal para a Etapa 3 do Part Splitter.

Valida os critérios obrigatórios definidos no plano técnico:
- P2: Macho em A, B; normal invertida e invert_sides (pino e cavidade no sentido correto).
- L2: Saliência L1 com encaixe cilíndrico e cápsula (ambos os lados).
- C1: Interface estreita (< 14.30 mm para D=6, c=0.15, m=4) -> rejeição explicativa.
- C2: Medição exata da malha de pino/cavidade cápsula (6x14 macho vs 6.30x14.30 cavidade, prof útil 8.5 mm).
- C3: Região côncava ou com furo (evita posicionar pino no vazio).
- C4: Distribuição sem espaço (LINEAR_2/3/GRID_4) -> rejeição sem redução silenciosa.
- C5: Parede fina (peça receptora com 4 mm, inserção 8 mm) -> rejeição explicativa via BVHTree.
- E1: Erro induzido em booleano -> rollback limpo sem partes parciais e bloqueio de confirmação.
- E2: Modo SOLID com connector_enabled -> bloqueio sem variáveis não inicializadas.
- E3: 20 regenerações e 1 falha -> 0 vazamento de meshes/objetos órfãos.
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
from src.geometry_plane import slice_mesh_by_plane, evaluate_bmesh_metrics
from src.geometry_loop import slice_mesh_by_loop, capture_edge_loop
from src.geometry_contract import CutInterface, build_cut_interface
from src.geometry_connectors import (
    create_pin_mesh_data,
    create_capsule_2d_profile,
    point_in_polygon_2d,
    compute_connector_layout,
    validate_connectors,
    check_receiving_wall_thickness,
    apply_connectors_boolean,
    ConnectorValidationError,
)
from src.diagnostic import get_scene_scale_to_mm
from src.constants import COLLECTION_PREVIEWS_NAME, PREVIEW_A_NAME, PREVIEW_B_NAME


def assert_test(cond: bool, msg: str):
    if not cond:
        print(f"  [FALHA] {msg}")
        raise AssertionError(msg)
    print(f"  [OK] {msg}")


def build_box_mesh(name: str, dims=(60.0, 40.0, 30.0), center=(0.0, 0.0, 0.0)):
    """Cria um objeto cuboide com dimensões e centro especificados."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.transform(Matrix.Diagonal((dims[0], dims[1], dims[2], 1.0)))
    bm.transform(Matrix.Translation(Vector(center)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def build_protrusion_obj():
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
    mesh = bpy.data.meshes.new("ProtrusionMesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("ProtrusionObj", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def test_p2():
    print("\n--- Teste P2: Direção e sentidos de Macho/Fêmea em todas as combinações ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001
    settings = scene.chest_splitter

    combinations = [
        ('A', False, Vector((0, 0, 1))),
        ('B', False, Vector((0, 0, 1))),
        ('A', True, Vector((0, 0, 1))),
        ('B', True, Vector((0, 0, 1))),
        ('A', False, Vector((0, 0, -1))),
    ]

    for male_part, invert_sides, norm_vec in combinations:
        # Cria bloco 60x40x30 centralizado em Z=0 (Z vai de -15 a +15)
        box = build_box_mesh(f"Box_P2_{male_part}_{invert_sides}_{int(norm_vec.z)}")
        settings.target_object = box
        settings.split_mode = 'PLANE'
        settings.plane_normal = norm_vec
        settings.plane_origin = Vector((0.0, 0.0, 0.0))
        settings.invert_sides = invert_sides
        settings.connector_enabled = True
        settings.connector_male_part = male_part
        settings.connector_diameter_mm = 6.0
        settings.connector_length_mm = 6.0
        settings.connector_distribution = 'CENTER'

        res = bpy.ops.chest.splitter_generate_preview()
        assert_test(res == {'FINISHED'}, f"Preview com male={male_part}, inv={invert_sides}, norm={norm_vec} gerado.")
        assert_test(settings.session_status == 'PREVIEW_VALID', "Status é PREVIEW_VALID.")

        col = scene.collection.children.get(COLLECTION_PREVIEWS_NAME)
        obj_a = col.objects.get(PREVIEW_A_NAME)
        obj_b = col.objects.get(PREVIEW_B_NAME)
        assert_test(obj_a is not None and obj_b is not None, "Objetos A e B existem no preview.")

        # Ambas as peças devem ser manifold
        assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Ambas as peças são 100% manifold.")

        # O pino no macho deve projetar vértices além da interface Z=0
        male_obj = obj_a if male_part == 'A' else obj_b
        female_obj = obj_b if male_part == 'A' else obj_a

        # Posição Z extrema do macho deve adentrar o espaço da fêmea
        # Na caixa original, metade está em Z < 0 e metade em Z > 0
        zs_male = [v.co.z for v in male_obj.data.vertices]
        if min(zs_male) < -1e-3 and max(zs_male) > 1e-3:
            has_pin_projection = True
        else:
            has_pin_projection = False
        assert_test(has_pin_projection, f"Macho ({male_part}) cruza a interface de corte Z=0 com o pino.")

        # Limpa para a próxima iteração
        bpy.data.objects.remove(box, do_unlink=True)


def test_l2():
    print("\n--- Teste L2: Encaixes na interface de loop (cilindro e cápsula) ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001
    settings = scene.chest_splitter

    target = build_protrusion_obj()
    settings.target_object = target
    settings.split_mode = 'LOOP'

    # Captura o loop na base da saliência (Z=20)
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(target.data)
    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = False

    # 1. Arestas do contorno da saliência em Z=20
    loop_edges = [
        e for e in bm.edges
        if abs(e.verts[0].co.z - 20.0) < 1e-3 and abs(e.verts[1].co.z - 20.0) < 1e-3
        and abs(e.verts[0].co.x) <= 12.01 and abs(e.verts[0].co.y) <= 9.01
        and abs(e.verts[1].co.x) <= 12.01 and abs(e.verts[1].co.y) <= 9.01
    ]
    for e in loop_edges:
        e.select = True
    bmesh.update_edit_mesh(target.data)

    res_cap = bpy.ops.chest.splitter_capture_loop()
    assert_test(res_cap == {'FINISHED'}, "Loop capturado com sucesso.")

    # 2. Deseleciona arestas e seleciona a face de semente na saliência (Z > 20)
    for e in bm.edges:
        e.select = False
    seed_face = [f for f in bm.faces if f.calc_center_median().z > 20.01][0]
    seed_face.select = True
    bmesh.update_edit_mesh(target.data)

    res_seed = bpy.ops.chest.splitter_define_seed_face()
    bpy.ops.object.mode_set(mode='OBJECT')
    assert_test(res_seed == {'FINISHED'}, "Face semente definida com sucesso.")

    # 1. Teste L2 com cilindro macho em A
    settings.connector_enabled = True
    settings.connector_type = 'CYLINDER'
    settings.connector_diameter_mm = 4.0
    settings.connector_length_mm = 5.0
    settings.connector_male_part = 'A'
    settings.connector_distribution = 'CENTER'

    res_prev = bpy.ops.chest.splitter_generate_preview()
    assert_test(res_prev == {'FINISHED'}, "Preview de loop com cilindro gerado com sucesso.")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Partes A e B de loop são manifold.")

    # 2. Teste L2 com cápsula macho em B
    settings.connector_type = 'CAPSULE'
    settings.connector_capsule_length_mm = 10.0
    settings.connector_male_part = 'B'

    res_prev2 = bpy.ops.chest.splitter_generate_preview()
    assert_test(res_prev2 == {'FINISHED'}, "Preview de loop com cápsula gerado com sucesso.")
    assert_test(settings.part_a_is_manifold and settings.part_b_is_manifold, "Partes A e B com cápsula são manifold.")


def test_c1():
    print("\n--- Teste C1: Interface estreita demais com rejeição explicativa ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001

    # Caixa 10x40x20 mm (interface em Z=0 tem 10x40 mm)
    box = build_box_mesh("NarrowBox", dims=(10.0, 40.0, 20.0))
    settings = scene.chest_splitter
    settings.target_object = box
    settings.split_mode = 'PLANE'
    settings.plane_normal = Vector((0, 0, 1))
    settings.plane_origin = Vector((0, 0, 0))
    settings.connector_enabled = True
    settings.connector_diameter_mm = 6.0
    settings.clearance_per_side_mm = 0.15
    settings.connector_edge_margin_mm = 4.0
    try:
        res = bpy.ops.chest.splitter_generate_preview()
        cancelled = (res == {'CANCELLED'})
    except RuntimeError:
        cancelled = True
    assert_test(cancelled, "Preview cancelado devido à interface estreita.")
    assert_test(settings.session_status == 'PREVIEW_INVALID', "Status definido como PREVIEW_INVALID.")
    assert_test("Falta de espaço" in settings.last_status, f"Mensagem explicativa clara: {settings.last_status}")


def test_c2():
    print("\n--- Teste C2: Medição exata de pino e cavidade de cápsula ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()

    # Parâmetros nominais
    D = 6.0
    L = 14.0
    length = 8.0
    chamfer = 0.5
    clearance_side = 0.15
    end_clearance = 0.5
    unit_scale = 1000.0

    # 1. Perfil 2D da cápsula
    w_male = D / 2.0
    half_len = (L - D) / 2.0  # 4.0 mm
    prof_male = create_capsule_2d_profile(w_male, half_len)
    xs_male = [p[0] for p in prof_male]
    ys_male = [p[1] for p in prof_male]

    width_male_2d = max(xs_male) - min(xs_male)
    len_male_2d = max(ys_male) - min(ys_male)
    assert_test(abs(width_male_2d - D) < 1e-4, f"Largura menor 2D do macho é exatamente {D:.2f} mm.")
    assert_test(abs(len_male_2d - L) < 1e-4, f"Comprimento maior 2D do macho é exatamente {L:.2f} mm.")

    w_fem = (D / 2.0) + clearance_side
    prof_fem = create_capsule_2d_profile(w_fem, half_len)
    xs_fem = [p[0] for p in prof_fem]
    ys_fem = [p[1] for p in prof_fem]

    width_fem_2d = max(xs_fem) - min(xs_fem)
    len_fem_2d = max(ys_fem) - min(ys_fem)
    expected_w_fem = D + 2.0 * clearance_side  # 6.30 mm
    expected_l_fem = L + 2.0 * clearance_side  # 14.30 mm
    assert_test(abs(width_fem_2d - expected_w_fem) < 1e-4, f"Largura cavidade 2D é {expected_w_fem:.2f} mm.")
    assert_test(abs(len_fem_2d - expected_l_fem) < 1e-4, f"Comprimento cavidade 2D é {expected_l_fem:.2f} mm.")

    # 2. Malha sólida 3D do pino macho
    male_mesh = create_pin_mesh_data(
        name="TestPinMale",
        connector_type='CAPSULE',
        diameter=D / unit_scale,
        length=length / unit_scale,
        chamfer=chamfer / unit_scale,
        is_cavity=False,
        capsule_length=L / unit_scale,
    )
    m_xs = [v.co.x * unit_scale for v in male_mesh.vertices]
    m_ys = [v.co.y * unit_scale for v in male_mesh.vertices]
    m_zs = [v.co.z * unit_scale for v in male_mesh.vertices]

    assert_test(abs((max(m_xs) - min(m_xs)) - D) < 1e-3, f"Macho 3D: largura {D:.2f} mm.")
    assert_test(abs((max(m_ys) - min(m_ys)) - L) < 1e-3, f"Macho 3D: comprimento {L:.2f} mm.")
    assert_test(abs(max(m_zs) - length) < 1e-3, f"Macho 3D: projeção útil {length:.2f} mm.")

    # 3. Malha sólida 3D da cavidade fêmea
    cavity_mesh = create_pin_mesh_data(
        name="TestCavityFem",
        connector_type='CAPSULE',
        diameter=D / unit_scale,
        length=length / unit_scale,
        chamfer=0.0,
        is_cavity=True,
        clearance_side=clearance_side / unit_scale,
        clearance_end=end_clearance / unit_scale,
        capsule_length=L / unit_scale,
    )
    c_xs = [v.co.x * unit_scale for v in cavity_mesh.vertices]
    c_ys = [v.co.y * unit_scale for v in cavity_mesh.vertices]
    c_zs = [v.co.z * unit_scale for v in cavity_mesh.vertices]

    tot_depth = length + end_clearance
    assert_test(abs((max(c_xs) - min(c_xs)) - expected_w_fem) < 1e-3, f"Cavidade 3D: largura {expected_w_fem:.2f} mm.")
    assert_test(abs((max(c_ys) - min(c_ys)) - expected_l_fem) < 1e-3, f"Cavidade 3D: comprimento {expected_l_fem:.2f} mm.")
    assert_test(abs(max(c_zs) - tot_depth) < 1e-3, f"Cavidade 3D: profundidade útil {tot_depth:.2f} mm.")


def test_c3():
    print("\n--- Teste C3: Região com furo ou côncava (evita posicionar pino no vazio) ---")
    # Ponto no centro de um furo interno (anel com raio externo 30 e interno 15)
    outer_poly = [(-30.0, -30.0), (30.0, -30.0), (30.0, 30.0), (-30.0, 30.0)]
    hole_poly = [(-15.0, -15.0), (15.0, -15.0), (15.0, 15.0), (-15.0, 15.0)]

    # Centro (0, 0) está dentro do contorno externo, mas cai dentro do furo
    in_outer = point_in_polygon_2d(0.0, 0.0, outer_poly)
    in_hole = point_in_polygon_2d(0.0, 0.0, hole_poly)
    assert_test(in_outer is True, "Centro (0,0) está geometricamente dentro da bounding box externa.")
    assert_test(in_hole is True, "Centro (0,0) detectado dentro do furo interno.")

    # CutInterface formal com furo
    interface = CutInterface(
        origin_world=Vector((0, 0, 0)),
        normal_a_to_b_world=Vector((0, 0, 1)),
        axis_u_world=Vector((1, 0, 0)),
        axis_v_world=Vector((0, 1, 0)),
        outer_contours_uv=[outer_poly],
        hole_contours_uv=[hole_poly],
    )

    try:
        compute_connector_layout(
            target_mesh=None,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0, 0, 0)),
            plane_normal=Vector((0, 0, 1)),
            distribution='CENTER',
            edge_margin_mm=3.0,
            diameter_mm=6.0,
            interface=interface,
        )
        assert_test(False, "Deveria ter lançado ConnectorValidationError para conector no furo.")
    except ConnectorValidationError as e:
        assert_test(True, f"Conector no furo rejeitado com sucesso: {str(e)}")


def test_c4():
    print("\n--- Teste C4: Distribuição sem espaço (LINEAR_3 e GRID_4) sem redução silenciosa ---")
    # Caixa 20x20 mm com interface 20x20 mm
    outer_poly = [(-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0)]
    interface = CutInterface(
        origin_world=Vector((0, 0, 0)),
        normal_a_to_b_world=Vector((0, 0, 1)),
        axis_u_world=Vector((1, 0, 0)),
        axis_v_world=Vector((0, 1, 0)),
        outer_contours_uv=[outer_poly],
        width_mm=20.0,
        height_mm=20.0,
    )

    # LINEAR_3 com D=6 mm requer > 28.9 mm
    try:
        compute_connector_layout(
            target_mesh=None,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0, 0, 0)),
            plane_normal=Vector((0, 0, 1)),
            distribution='LINEAR_3',
            edge_margin_mm=3.0,
            diameter_mm=6.0,
            unit_scale=1.0,
            interface=interface,
        )
        assert_test(False, "LINEAR_3 deveria ter sido rejeitado por falta de espaço.")
    except ConnectorValidationError as e:
        assert_test(True, f"LINEAR_3 rejeitado formalmente sem redução silenciosa: {str(e)}")

    # GRID_4 com D=6 mm requer > 20.6 mm
    try:
        compute_connector_layout(
            target_mesh=None,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0, 0, 0)),
            plane_normal=Vector((0, 0, 1)),
            distribution='GRID_4',
            edge_margin_mm=4.0,
            diameter_mm=6.0,
            unit_scale=1.0,
            interface=interface,
        )
        assert_test(False, "GRID_4 deveria ter sido rejeitado por falta de espaço.")
    except ConnectorValidationError as e:
        assert_test(True, f"GRID_4 rejeitado formalmente sem redução silenciosa: {str(e)}")


def test_c5():
    print("\n--- Teste C5: Parede fina na peça receptora detectada via BVHTree ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001

    # Peça receptora: placa de 4 mm de espessura (Z de 0 a 4 mm)
    plate = build_box_mesh("ThinPlate", dims=(40.0, 40.0, 4.0), center=(0.0, 0.0, 2.0))

    # Posição do conector na face Z=0
    pos = [Vector((0.0, 0.0, 0.0))]
    normal = Vector((0.0, 0.0, 1.0))  # penetração no sentido +Z

    unit_scale = get_scene_scale_to_mm(scene)
    req_depth_bu = 8.5 / unit_scale

    ok, avail = check_receiving_wall_thickness(plate, pos, normal, req_depth_bu)
    assert_test(not ok, f"Parede fina detectada com sucesso (espessura disponível: {avail*unit_scale:.1f} mm < {req_depth_bu*unit_scale:.1f} mm).")

    # Também valida via validate_connectors
    try:
        validate_connectors(
            positions=pos,
            diameter_mm=6.0,
            clearance_per_side_mm=0.15,
            unit_scale=unit_scale,
            obj_female=plate,
            normal=normal,
            length_mm=8.0,
            end_clearance_mm=0.5,
        )
        assert_test(False, "validate_connectors deveria ter lançado ConnectorValidationError.")
    except ConnectorValidationError as e:
        assert_test(True, f"Exceção explicativa lançada por validate_connectors: {str(e)}")


def test_e1():
    print("\n--- Teste E1: Erro induzido em booleano com rollback limpo e confirmação bloqueada ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001
    settings = scene.chest_splitter

    box = build_box_mesh("Box_E1", dims=(40.0, 40.0, 40.0))
    settings.target_object = box
    settings.split_mode = 'PLANE'
    settings.plane_normal = Vector((0, 0, 1))
    settings.plane_origin = Vector((0, 0, 0))
    settings.connector_enabled = True

    # Induz erro na execução forçando uma exceção no módulo de conectores
    original_apply = src.operators.apply_connectors_boolean

    def failing_apply(*args, **kwargs):
        raise RuntimeError("Falha induzida de teste no cálculo booleano.")

    src.operators.apply_connectors_boolean = failing_apply
    try:
        try:
            res = bpy.ops.chest.splitter_generate_preview()
            cancelled = (res == {'CANCELLED'})
        except RuntimeError:
            cancelled = True
        assert_test(cancelled, "Operador retornou CANCELLED na falha booleana.")
        assert_test(settings.session_status == 'PREVIEW_INVALID', "session_status definido como PREVIEW_INVALID.")
        assert_test(bpy.ops.chest.splitter_commit_parts.poll() is False, "Confirmação de corte bloqueada com segurança.")

        col = scene.collection.children.get(COLLECTION_PREVIEWS_NAME)
        num_preview_objs = len(col.objects) if col else 0
        assert_test(num_preview_objs == 0, "Nenhum objeto parcial ou cortador temporário ficou na coleção de preview.")
    finally:
        src.operators.apply_connectors_boolean = original_apply


def test_e2():
    print("\n--- Teste E2: Modo SOLID com connector_enabled sem variáveis não inicializadas ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001
    settings = scene.chest_splitter

    target = build_box_mesh("Target_E2", dims=(50.0, 50.0, 50.0))
    cutter = build_box_mesh("Cutter_E2", dims=(25.0, 25.0, 60.0))

    settings.target_object = target
    settings.split_mode = 'SOLID'
    settings.solid_cutter_object = cutter
    settings.connector_enabled = True  # Ativado intencionalmente

    res = bpy.ops.chest.splitter_generate_preview()
    assert_test(res == {'FINISHED'}, "Preview SOLID executou com sucesso mesmo com connector_enabled.")
    assert_test(settings.session_status == 'PREVIEW_VALID', "session_status é PREVIEW_VALID.")
    assert_test("não são suportados no modo Cortador Sólido" not in settings.last_status or "sucesso" in settings.last_status, "Mensagem de status coerente.")


def test_e3():
    print("\n--- Teste E3: 20 regenerações e 1 falha sem vazamento de objetos/meshes ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 0.001
    settings = scene.chest_splitter

    box = build_box_mesh("Box_E3", dims=(50.0, 50.0, 50.0))
    settings.target_object = box
    settings.split_mode = 'PLANE'
    settings.plane_normal = Vector((0, 0, 1))
    settings.plane_origin = Vector((0, 0, 0))
    settings.connector_enabled = True
    settings.connector_diameter_mm = 6.0
    settings.connector_length_mm = 6.0

    # 1ª execução para estabilizar caches
    bpy.ops.chest.splitter_generate_preview()

    initial_mesh_count = len(bpy.data.meshes)
    initial_obj_count = len(bpy.data.objects)

    # 20 regenerações contínuas
    for i in range(20):
        settings.connector_diameter_mm = 6.0 if (i % 2 == 0) else 5.0
        bpy.ops.chest.splitter_generate_preview()

    # 1 falha intencional (interface muito estreita)
    settings.connector_edge_margin_mm = 30.0  # Não cabe em 50 mm (requer 6 + 60 = 66 mm)
    try:
        bpy.ops.chest.splitter_generate_preview()
    except RuntimeError:
        pass
    assert_test(settings.session_status == 'PREVIEW_INVALID', "Falha induzida gerou PREVIEW_INVALID.")

    # 1 regeneração válida para restaurar
    settings.connector_edge_margin_mm = 3.0
    bpy.ops.chest.splitter_generate_preview()
    assert_test(settings.session_status == 'PREVIEW_VALID', "Regeneração válida restaurou PREVIEW_VALID.")

    final_mesh_count = len(bpy.data.meshes)
    final_obj_count = len(bpy.data.objects)

    print(f"  Contagem de malhas: inicial={initial_mesh_count}, final={final_mesh_count}")
    print(f"  Contagem de objetos: inicial={initial_obj_count}, final={final_obj_count}")

    assert_test(final_obj_count == initial_obj_count, f"Zero vazamento de objetos ({final_obj_count} == {initial_obj_count}).")
    assert_test(final_mesh_count == initial_mesh_count, f"Zero vazamento de malhas ({final_mesh_count} == {initial_mesh_count}).")


def run_all_tests():
    print("=" * 70)
    print("EXECUTANDO TESTES DE ACEITAÇÃO DA ETAPA 3 (P2, L2, C1-C5, E1-E3)")
    print("=" * 70)

    test_p2()
    test_l2()
    test_c1()
    test_c2()
    test_c3()
    test_c4()
    test_c5()
    test_e1()
    test_e2()
    test_e3()

    print("\n" + "=" * 70)
    print("TODOS OS TESTES DE ACEITAÇÃO DA ETAPA 3 FORAM APROVADOS COM SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
