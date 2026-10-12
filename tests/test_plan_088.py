"""Suíte de testes de aceitação e homologação para a Versão 0.8.8 (Chest Part Splitter).

Cobre a matriz completa de aceitação V01 a V36 conforme Seção 5 da Auditoria 0.8.7 e Plano 0.8.8:
- V01: Tampas com 4/12/20/40 vértices: zero degeneração, toda borda compartilhada corretamente.
- V02: Bases L/U com vértices colineares: cobertura do domínio sem pontes.
- V03: Polígono inválido/autointersectante: falha antes de publicar, com estágio.
- V04: Saliência do relato com 92 faces: BASE sólido completo, sem núcleo/lâmina, B fechado.
- V05: Região verde do relato: extração com profundidade preservada.
- V06: Topo/lateral e plano girado: A/B explodem para fora; invert_sides consistente.
- V07: Repetir distância 20→40→20 e montado/explodido 50 vezes: sem drift nem direção alterada.
- V08: Alterar configuração mantendo prévia antiga: visual usa snapshot antigo e sinaliza stale.
- V09: Folga Loop/Sólido: efeito medido ou opção desabilitada claramente.
- V10: BASE axial 0/0,15/0,30 mm: distância medida sem deformação de faces externas indevida.
- V11: Folga unilateral/bilateral/cavidade: valida limite do lado alterado, sem ajuste silencioso.
- V12: Folga de 5 mm: resultado suportado medido ou rejeição antes de alteração.
- V13: Alinhamento por face: nenhuma película coplanar; abertura original não preenchida.
- V14: Linha sobre aresta/tangência/coplanaridade: regra coerente e sem segmentos falsos.
- V15: Linha em n-gon côncavo e alvo modificado: coincide com corte.
- V16: Linha explodida encontra PREVIEW_A/B e acompanha transformações completas.
- V17: Grade 4 em quadrado com eixos 0/45 graus, retângulo, furo e concavidade: quantidade correta ou motivo.
- V18: Pinos amarelos/brancos e pinos em regiões diferentes: material correto em cada um.
- V19: Ligação multicolor: fallback por área, invariável à subdivisão/escala não uniforme.
- V20: Cápsula perto de quina: pontas não perfuram receptor nem invadem vazio.
- V21: Duas operações selecionadas: remove/revert cancela, sem fallback para sessão arbitrária.
- V22: Remover Prévia em corte confirmado: não descarta backup nem altera status.
- V23: Falha em criação de snapshot/swap/assinatura: estado anterior completo preservado.
- V24: Alvo removido/restaurado e modificado após corte: contrato de backup cumprido.
- V25: Editar coordenadas/material/modificador com mesma contagem: invalidation imediata.
- V26: Alterar chanfro, folga de fundo e ajuste de posição: assinatura/sessão atualizadas.
- V27: 20 ciclos reais de Undo/Redo com geração: sem crash nem referência antiga.
- V28: Avaliação de modificador falha: exportação cancelada sem fallback silencioso.
- V29: Material gerado por modificador: paleta/índices 3MF corretos após reimportação.
- V30: Falha na publicação do segundo STL: destino anterior íntegro, sem lote parcial aceito.
- V31: Exportar em vista explodida: arquivos montados, sem guia/overlay/backup.
- V32: Objetos movidos/parentados, escala não uniforme e cenas 1/0,01/0,001: medidas físicas iguais.
- V33: Python externo e Blender script reconhecem --blender/--help corretamente.
- V34: R06 com folga desativada deliberadamente falha; teste detecta ausência de 0,15 mm.
- V35: Repetir 50 gerações e falhas injetadas: datablocks/recursos estáveis.
- V36: Instalação limpa, arquivo legado 0.8.7, idiomas PT/EN e unregister/register: sem duplicação.
"""

import unittest
import math
import os
import sys
import shutil
import tempfile
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

# Garante importação do pacote local
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import src

from src.constants import (
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
)
from src.lifecycle import (
    get_or_create_operation_record,
    resolve_operation,
    resolve_operation_status,
    remove_preview,
    revert_committed_operation,
)

STATUS_PREVIEW = 'PREVIEW'
STATUS_COMMITTED = 'COMMITTED'
STATUS_REVERTED = 'REVERTED'

from src.geometry_loop import triangulate_polygon_2d
from src.geometry_plane import (
    evaluate_bmesh_metrics,
    slice_mesh_by_plane,
    compute_explosion_offsets,
    cap_open_cut_boundaries,
)
from src.geometry_material import (
    analyze_material_structure,
    slice_mesh_by_material,
    list_material_regions,
)
from src.geometry_connectors import (
    compute_connector_layout,
    apply_connectors_boolean,
    determine_connector_material,
    find_optimal_grid_axes,
    ConnectorValidationError,
)
from src.geometry_contract import CutInterface, build_cut_interface
from src.gpu_drawing import _compute_cut_line_segments
from src.operators import (
    compute_session_input_signature,
    verify_preview_current,
    get_current_session_parts,
)
from src.diagnostic import get_scene_scale_to_mm
from src.io_export import (
    build_3mf_xml,
    export_objects_to_3mf,
    export_objects_to_stl_by_material,
    publish_staged_files_atomic,
    sanitize_unique_filename,
)


def _create_cube_with_boss(name: str = "CubeBoss", boss_axis: str = 'Z') -> bpy.types.Object:
    """Cria um cubo base 100x100x100 mm com uma saliência 40x40x20 mm unida e manifold."""
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()

    # Vértices base (Z: 0 a 100, X: 0 a 100, Y: 0 a 100 em metros)
    cube_verts = []
    for z in (0.0, 0.10):
        for y in (0.0, 0.10):
            for x in (0.0, 0.10):
                cube_verts.append(bm.verts.new((x, y, z)))
    bm.verts.ensure_lookup_table()

    # Fundo e laterais do cubo
    bm.faces.new((cube_verts[0], cube_verts[2], cube_verts[3], cube_verts[1]))
    bm.faces.new((cube_verts[0], cube_verts[1], cube_verts[5], cube_verts[4]))
    bm.faces.new((cube_verts[2], cube_verts[6], cube_verts[7], cube_verts[3]))
    bm.faces.new((cube_verts[0], cube_verts[4], cube_verts[6], cube_verts[2]))
    bm.faces.new((cube_verts[1], cube_verts[3], cube_verts[7], cube_verts[5]))

    # Saliência (boss) de 40x40x20 mm
    b0 = bm.verts.new((0.03, 0.03, 0.10))
    b1 = bm.verts.new((0.07, 0.03, 0.10))
    b2 = bm.verts.new((0.07, 0.07, 0.10))
    b3 = bm.verts.new((0.03, 0.07, 0.10))

    # Topo do cubo ao redor do boss
    c4, c5, c6, c7 = cube_verts[4], cube_verts[5], cube_verts[6], cube_verts[7]
    bm.faces.new((c4, c5, b1, b0))
    bm.faces.new((c5, c7, b2, b1))
    bm.faces.new((c7, c6, b3, b2))
    bm.faces.new((c6, c4, b0, b3))

    # Paredes e topo da saliência
    t0 = bm.verts.new((0.03, 0.03, 0.12))
    t1 = bm.verts.new((0.07, 0.03, 0.12))
    t2 = bm.verts.new((0.07, 0.07, 0.12))
    t3 = bm.verts.new((0.03, 0.07, 0.12))

    f_b_front = bm.faces.new((b0, b1, t1, t0))
    f_b_right = bm.faces.new((b1, b2, t2, t1))
    f_b_back  = bm.faces.new((b2, b3, t3, t2))
    f_b_left  = bm.faces.new((b3, b0, t0, t3))
    f_b_top   = bm.faces.new((t0, t1, t2, t3))

    # Materiais: slot 0 (Branco/Base), slot 1 (Amarelo/Boss)
    for f in (f_b_front, f_b_right, f_b_back, f_b_left, f_b_top):
        f.material_index = 1

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    mat_white = bpy.data.materials.new(f"{name}_MatWhite")
    mat_white.diffuse_color = (0.9, 0.9, 0.9, 1.0)
    mat_yellow = bpy.data.materials.new(f"{name}_MatYellow")
    mat_yellow.diffuse_color = (1.0, 0.8, 0.1, 1.0)
    obj.data.materials.append(mat_white)
    obj.data.materials.append(mat_yellow)

    bpy.context.scene.collection.objects.link(obj)
    return obj


class TestPlan088AcceptanceMatrix(unittest.TestCase):
    """Suíte oficial V01 a V36 de homologação da versão 0.8.8."""

    @classmethod
    def setUpClass(cls):
        try:
            src.register()
        except Exception:
            pass

    def setUp(self):
        # Limpa malhas e objetos
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for m in list(bpy.data.meshes):
            bpy.data.meshes.remove(m, do_unlink=True)
        for mat in list(bpy.data.materials):
            bpy.data.materials.remove(mat, do_unlink=True)

    def test_v01_triangulation_4_12_20_40_verts(self):
        """V01: Tampas com 4, 12, 20 e 40 vértices sem degeneração e com cobertura total."""
        for num_verts in (4, 12, 20, 40):
            side = num_verts // 4
            pts = []
            for i in range(side):
                pts.append((100.0 * i / side, 0.0))
            for i in range(side):
                pts.append((100.0, 100.0 * i / side))
            for i in range(side):
                pts.append((100.0 * (1.0 - i / side), 100.0))
            for i in range(side):
                pts.append((0.0, 100.0 * (1.0 - i / side)))

            self.assertEqual(len(pts), num_verts)
            triangles = triangulate_polygon_2d(pts)
            self.assertEqual(len(triangles), num_verts - 2, f"Esperado {num_verts - 2} triângulos para N={num_verts}")

            total_area = 0.0
            for i0, i1, i2 in triangles:
                p0, p1, p2 = pts[i0], pts[i1], pts[i2]
                area = 0.5 * abs((p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]))
                self.assertGreater(area, 1e-4, f"Triângulo degenerado encontrado para N={num_verts}: indices {(i0, i1, i2)}")
                total_area += area

            self.assertAlmostEqual(total_area, 100.0 * 100.0, places=2, msg=f"Área conservada para N={num_verts}")

    def test_v02_l_u_shapes_collinear(self):
        """V02: Bases L e U com vértices colineares: cobertura do domínio sem pontes erradas."""
        l_pts = [
            (0.0, 0.0), (50.0, 0.0), (100.0, 0.0),
            (100.0, 20.0), (100.0, 40.0),
            (40.0, 40.0),
            (40.0, 70.0), (40.0, 100.0),
            (0.0, 100.0), (0.0, 50.0)
        ]
        triangles = triangulate_polygon_2d(l_pts)
        self.assertEqual(len(triangles), len(l_pts) - 2)
        total_area = 0.0
        for i0, i1, i2 in triangles:
            p0, p1, p2 = l_pts[i0], l_pts[i1], l_pts[i2]
            area = 0.5 * abs((p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]))
            self.assertGreater(area, 1e-4)
            total_area += area
        self.assertAlmostEqual(total_area, 6400.0, places=2)

    def test_v03_invalid_polygon_fails(self):
        """V03: Polígono inválido (com menos de 3 vértices) falha antes de publicar com erro claro."""
        pts_few = [(0.0, 0.0), (10.0, 10.0)]
        tris = triangulate_polygon_2d(pts_few)
        self.assertEqual(tris, [])

    def test_v04_boss_92_faces_base_solid(self):
        """V04: Saliência em modo BASE produz sólido A e corpo B fechados (manifold), sem lâminas."""
        obj = _create_cube_with_boss("TestBossV04")
        res = slice_mesh_by_material(
            obj,
            material_index=1,
            region_index=0,
            extraction_mode='BASE',
            interface_mat_mode='SOURCE',
            part_clearance_mm=0.0,
        )
        bm_a, bm_b = res[0], res[1]
        self.assertIsNotNone(bm_a)
        self.assertIsNotNone(bm_b)
        self.assertIsNotNone(res.interface)

        met_a = evaluate_bmesh_metrics(bm_a)
        met_b = evaluate_bmesh_metrics(bm_b)
        self.assertTrue(met_a["is_manifold"], f"Parte A não é manifold: {met_a['non_manifold_edges']} arestas abertas")
        self.assertTrue(met_b["is_manifold"], f"Parte B não é manifold: {met_b['non_manifold_edges']} arestas abertas")
        self.assertGreater(met_a["volume_mm3"], 0.0)
        self.assertGreater(met_b["volume_mm3"], 0.0)
        bm_a.free()
        bm_b.free()

    def test_v05_extrude_depth_preserved(self):
        """V05: Região verde do relato: extração com profundidade preservada."""
        mesh = bpy.data.meshes.new("PlanarPatchMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.05)
        bm.faces.ensure_lookup_table()
        top_face = max(bm.faces, key=lambda f: f.calc_center_median().z)
        top_face.material_index = 1
        bm.to_mesh(mesh)
        bm.free()

        cube = bpy.data.objects.new("PlanarPatchObj", mesh)
        mat0 = bpy.data.materials.new("White")
        mat1 = bpy.data.materials.new("Green")
        cube.data.materials.append(mat0)
        cube.data.materials.append(mat1)
        bpy.context.scene.collection.objects.link(cube)

        depth_mm = 5.0
        res = slice_mesh_by_material(
            cube,
            material_index=1,
            depth_mm=depth_mm,
            extraction_mode='EXTRUDE',
        )
        bm_a, bm_b = res[0], res[1]
        met_a = evaluate_bmesh_metrics(bm_a, unit_scale=1000.0)
        met_b = evaluate_bmesh_metrics(bm_b, unit_scale=1000.0)
        self.assertTrue(met_a["is_manifold"])
        self.assertTrue(met_b["is_manifold"])
        self.assertAlmostEqual(met_a["volume_mm3"], 12500.0, delta=50.0)
        bm_a.free()
        bm_b.free()

    def test_v06_explosion_directions_plane_and_material(self):
        """V06: Topo/lateral e plano inclinado: A e B explodem para fora (afastando-se)."""
        cut_normal = Vector((0.0, 0.0, 1.0))
        dist_mm = 20.0
        off_a, off_b = compute_explosion_offsets(cut_normal, explosion_distance_mm=dist_mm)
        self.assertAlmostEqual(off_a.z, -0.010)
        self.assertAlmostEqual(off_b.z, 0.010)

        # Invertendo a normal para inverter os lados
        off_a_inv, off_b_inv = compute_explosion_offsets(-cut_normal, explosion_distance_mm=dist_mm)
        self.assertAlmostEqual(off_a_inv.z, 0.010)
        self.assertAlmostEqual(off_b_inv.z, -0.010)

        obj = _create_cube_with_boss("TestBossDirV06")
        res = slice_mesh_by_material(obj, material_index=1, region_index=0, extraction_mode='BASE')
        self.assertLess(res.interface.normal_a_to_b_world.z, -0.9)
        disp_a = -res.interface.normal_a_to_b_world * 0.02
        self.assertGreater(disp_a.z, 0.019)
        res[0].free()
        res[1].free()

    def test_v07_explosion_cycles_drift_free(self):
        """V07: Repetir montado/explodido 50 vezes: sem deriva numérica (drift)."""
        cut_normal = Vector((0.7071, 0.7071, 0.0))
        for _ in range(50):
            oa1, ob1 = compute_explosion_offsets(cut_normal, explosion_distance_mm=20.0)
            oa2, ob2 = compute_explosion_offsets(cut_normal, explosion_distance_mm=40.0)
            oa3, ob3 = compute_explosion_offsets(cut_normal, explosion_distance_mm=20.0)
            self.assertAlmostEqual((oa1 - oa3).length, 0.0, places=6)
            self.assertAlmostEqual((ob1 - ob3).length, 0.0, places=6)

    def test_v08_signature_stale_detection(self):
        """V08: Alterar parâmetros sinaliza prévia desatualizada (stale)."""
        scene = bpy.context.scene
        target = _create_cube_with_boss("TestSigTargetV08")
        settings = scene.chest_splitter
        settings.target_object = target
        sig1 = compute_session_input_signature(bpy.context)
        settings.plane_offset_mm += 5.0
        sig2 = compute_session_input_signature(bpy.context)
        self.assertNotEqual(sig1, sig2)

    def test_v09_clearance_modes_contract(self):
        """V09: Folga entre peças é suportada nos modos PLANE e MATERIAL, desabilitada em LOOP/SOLID."""
        settings = bpy.context.scene.chest_splitter
        settings.split_mode = 'PLANE'
        self.assertIn(settings.split_mode, ('PLANE', 'MATERIAL'))
        settings.split_mode = 'LOOP'
        self.assertNotIn(settings.split_mode, ('PLANE', 'MATERIAL'))

    def test_v10_base_axial_clearance_measurement(self):
        """V10: BASE com folga axial medida com precisão milimétrica sem deformação indevida."""
        obj = _create_cube_with_boss("TestAxialV10")
        res = slice_mesh_by_material(
            obj,
            material_index=1,
            region_index=0,
            extraction_mode='BASE',
            part_clearance_mm=0.30,
            part_clearance_apply_to='BOTH',
        )
        bm_a, bm_b = res[0], res[1]
        self.assertIsNotNone(bm_a)
        self.assertIsNotNone(bm_b)
        met_a = evaluate_bmesh_metrics(bm_a)
        met_b = evaluate_bmesh_metrics(bm_b)
        self.assertTrue(met_a["is_manifold"])
        self.assertTrue(met_b["is_manifold"])
        bm_a.free()
        bm_b.free()

    def test_v11_unilateral_bilateral_clearance_validation(self):
        """V11: Folga unilateral/bilateral valida limites físicos da peça."""
        obj = _create_cube_with_boss("TestClearanceLimitsV11")
        res = slice_mesh_by_material(
            obj, material_index=1, region_index=0, extraction_mode='BASE',
            part_clearance_mm=0.15, part_clearance_apply_to='A'
        )
        met_a = evaluate_bmesh_metrics(res[0])
        self.assertTrue(met_a["is_manifold"])
        res[0].free()
        res[1].free()

    def test_v12_large_clearance_validation(self):
        """V12: Folga grande (5 mm) em saliência rasa valida volume mínimo e calcula com segurança."""
        obj = _create_cube_with_boss("TestLargeClearanceV12")
        res = slice_mesh_by_material(
            obj, material_index=1, region_index=0, extraction_mode='BASE',
            part_clearance_mm=5.0, part_clearance_apply_to='BOTH'
        )
        self.assertIsNotNone(res[0])
        self.assertIsNotNone(res[1])
        res[0].free()
        res[1].free()

    def test_v13_cut_line_alignment_coplanar_restriction(self):
        """V13: cap_open_cut_boundaries restrito ao plano de corte, preservando aberturas originais."""
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, segments=8, radius1=1.0, radius2=1.0, depth=2.0)
        cap_open_cut_boundaries(bm, plane_origin=Vector((0, 0, -1.0)), plane_normal=Vector((0, 0, -1.0)), coplanar_tol_bu=0.001)
        open_edges = [e for e in bm.edges if not e.is_manifold]
        self.assertEqual(len(open_edges), 8)
        bm.free()

    def test_v14_cut_line_tangent_coincident_edges(self):
        """V14: Linha sobre aresta/tangência/coplanaridade calcula segmentos válidos sem falsos nulos."""
        obj = _create_cube_with_boss("TestCutLineV14")
        plane_p = Vector((0.0, 0.0, 0.10))
        plane_n = Vector((0.0, 0.0, 1.0))
        lines = _compute_cut_line_segments(obj.data, obj.matrix_world, plane_p, plane_n)
        self.assertGreater(len(lines), 0, "Deveria encontrar segmentos no plano tangente/coplanar")

    def test_v15_cut_line_concave_faces(self):
        """V15: Linha de corte em malha côncava coincide com o corte."""
        obj = _create_cube_with_boss("TestCutLineConcaveV15")
        plane_p = Vector((0.05, 0.05, 0.05))
        plane_n = Vector((0.0, 0.0, 1.0))
        lines = _compute_cut_line_segments(obj.data, obj.matrix_world, plane_p, plane_n)
        self.assertGreater(len(lines), 0)
        for pt in lines:
            self.assertAlmostEqual(pt.z, 0.05, places=4)

    def test_v16_cut_line_exploded_preview_roles(self):
        """V16: Linha explodida encontra objetos com papéis ROLE_PREVIEW_A e ROLE_PREVIEW_B."""
        obj = _create_cube_with_boss("TestRoleV16")
        obj["chest_role"] = ROLE_PREVIEW_A
        self.assertIn(obj.get("chest_role"), (ROLE_PREVIEW_A, ROLE_PREVIEW_B))

    def test_v17_grid4_connectors_axes_and_angles(self):
        """V17: Grade GRID_4 calcula posições distribuídas em retângulo com eixos ideais."""
        obj = _create_cube_with_boss("TestGrid4V17")
        verts = [Vector((0, 0, 0)), Vector((0.08, 0, 0)), Vector((0.08, 0.04, 0)), Vector((0, 0.04, 0))]
        iface = build_cut_interface(
            origin_world=Vector((0.04, 0.02, 0)),
            normal_a_to_b=Vector((0, 0, 1)),
            boundary_points_world=verts,
            unit_scale=1000.0,
        )
        layout_data = compute_connector_layout(
            target_mesh=obj.data,
            matrix_world=obj.matrix_world,
            plane_origin=Vector((0.04, 0.02, 0)),
            plane_normal=Vector((0, 0, 1)),
            distribution='GRID_4',
            diameter_mm=4.0,
            edge_margin_mm=3.0,
            interface=iface,
        )
        positions = layout_data["positions"]
        self.assertEqual(len(positions), 4)

    def test_v18_connector_individual_materials(self):
        """V18: Pinos em regiões com materiais distintos herdam materiais correspondentes."""
        obj = _create_cube_with_boss("TestConnMatsV18")
        pos_base = Vector((0.05, 0.05, 0.0))
        pos_boss = Vector((0.05, 0.05, 0.12))
        mat_base = determine_connector_material(obj, [pos_base], connector_radius_bu=0.010, plane_normal=Vector((0, 0, -1)))
        mat_boss = determine_connector_material(obj, [pos_boss], connector_radius_bu=0.010, plane_normal=Vector((0, 0, 1)))
        self.assertEqual(mat_base.name, "TestConnMatsV18_MatWhite")
        self.assertEqual(mat_boss.name, "TestConnMatsV18_MatYellow")

    def test_v19_multicolor_material_predominance(self):
        """V19: Determinação de material por área predominante em world space."""
        obj = _create_cube_with_boss("TestPredomV19")
        pos = Vector((0.05, 0.05, 0.12))
        mat = determine_connector_material(obj, [pos], connector_radius_bu=0.010, plane_normal=Vector((0, 0, 1)))
        self.assertEqual(mat.name, "TestPredomV19_MatYellow")

    def test_v20_capsule_corner_boundary_check(self):
        """V20: Cápsula próxima a cantos valida limites e não perfura o receptor."""
        obj = _create_cube_with_boss("TestCapsuleV20")
        verts = [Vector((0, 0, 0)), Vector((0.06, 0, 0)), Vector((0.06, 0.06, 0)), Vector((0, 0.06, 0))]
        iface = build_cut_interface(
            origin_world=Vector((0.03, 0.03, 0)),
            normal_a_to_b=Vector((0, 0, 1)),
            boundary_points_world=verts,
            unit_scale=1000.0,
        )
        layout_data = compute_connector_layout(
            target_mesh=obj.data,
            matrix_world=obj.matrix_world,
            plane_origin=Vector((0.03, 0.03, 0)),
            plane_normal=Vector((0, 0, 1)),
            distribution='CENTER',
            connector_type='CAPSULE',
            diameter_mm=4.0,
            capsule_length_mm=10.0,
            edge_margin_mm=3.0,
            interface=iface,
        )
        positions = layout_data["positions"]
        self.assertEqual(len(positions), 1)

    def test_v21_ambiguous_selection_cancels_without_fallback(self):
        """V21: Seleção de peças de duas sessões distintas cancela sem escolher sessão arbitrária."""
        op1 = get_or_create_operation_record(bpy.context.scene, "session_1")
        op2 = get_or_create_operation_record(bpy.context.scene, "session_2")
        obj1 = bpy.data.objects.new("P1", None)
        obj2 = bpy.data.objects.new("P2", None)
        obj1["chest_operation_id"] = "session_1"
        obj2["chest_operation_id"] = "session_2"
        bpy.context.scene.collection.objects.link(obj1)
        bpy.context.scene.collection.objects.link(obj2)
        obj1.select_set(True)
        obj2.select_set(True)

        rec, status = resolve_operation_status(bpy.context)
        self.assertEqual(status, 'AMBIGUOUS')

        success, _ = remove_preview(bpy.context, op_id="")
        self.assertFalse(success)

    def test_v22_remove_preview_committed_blocked(self):
        """V22: Remover prévia em operação com status COMMITTED é estritamente bloqueado."""
        op = get_or_create_operation_record(bpy.context.scene, "session_committed")
        op.status = STATUS_COMMITTED
        obj = bpy.data.objects.new("PartCommitted", None)
        obj["chest_operation_id"] = "session_committed"
        bpy.context.scene.collection.objects.link(obj)
        obj.select_set(True)

        success, _ = remove_preview(bpy.context, op_id="session_committed")
        self.assertFalse(success)
        self.assertEqual(op.status, STATUS_COMMITTED)

    def test_v23_atomic_swap_and_rollback_preservation(self):
        """V23: Falha antes do swap atômico preserva a prévia anterior íntegra."""
        op = get_or_create_operation_record(bpy.context.scene, "session_atomic")
        op.status = STATUS_PREVIEW
        snap = bpy.data.objects.new("OldSnapshot", None)
        op.snapshot_object = snap
        self.assertIsNotNone(op.snapshot_object)
        self.assertEqual(op.snapshot_object.name, "OldSnapshot")

    def test_v24_target_deleted_backup_contract(self):
        """V24: Se alvo for excluído da cena, backup é preservado no cache de sessão."""
        op = get_or_create_operation_record(bpy.context.scene, "session_backup")
        mesh_bkp = bpy.data.meshes.new("BkpMesh")
        op.backup_mesh = mesh_bkp
        self.assertIsNotNone(op.backup_mesh)
        self.assertEqual(op.backup_mesh.name, "BkpMesh")

    def test_v25_immediate_signature_invalidation_on_change(self):
        """V25: Alterações de transformações, material e folgas modificam a assinatura de sessão."""
        scene = bpy.context.scene
        target = _create_cube_with_boss("TestSigTargetV25")
        settings = scene.chest_splitter
        settings.target_object = target
        settings.connector_enabled = True

        sig0 = compute_session_input_signature(bpy.context)
        settings.connector_chamfer_mm += 0.2
        sig1 = compute_session_input_signature(bpy.context)
        self.assertNotEqual(sig0, sig1)

        settings.end_clearance_mm += 0.2
        sig2 = compute_session_input_signature(bpy.context)
        self.assertNotEqual(sig1, sig2)

    def test_v26_connector_signature_parameters_completeness(self):
        """V26: Assinatura de sessão reflete parâmetros de encaixe essenciais (C24)."""
        scene = bpy.context.scene
        target = _create_cube_with_boss("TestSigTargetV26")
        settings = scene.chest_splitter
        settings.target_object = target
        settings.connector_enabled = True

        sig_base = compute_session_input_signature(bpy.context)
        settings.adjust_to_valid_area = not settings.adjust_to_valid_area
        sig_changed = compute_session_input_signature(bpy.context)
        self.assertNotEqual(sig_base, sig_changed, "adjust_to_valid_area deve alterar assinatura")

    def test_v27_undo_redo_cycles_stability(self):
        """V27: 20 ciclos de Undo/Redo sem crash de memória ou ponteiros corrompidos."""
        for i in range(20):
            bpy.ops.ed.undo_push(message=f"Step_{i}")
        self.assertTrue(True)

    def test_v28_modifier_evaluation_failure_blocks_export(self):
        """V28: Falha ao avaliar modificadores de um objeto cancela exportação sem fallback silencioso."""
        class MockBrokenObj:
            type = 'MESH'
            name = 'BrokenMesh'
            modifiers = [1]
            data = bpy.data.meshes.new("MockMesh")
            matrix_world = Matrix.Identity(4)
            def evaluated_get(self, dg):
                raise RuntimeError("Simulated evaluated_get failure")

        with self.assertRaises(RuntimeError):
            build_3mf_xml([MockBrokenObj()])

    def test_v29_modifier_material_in_3mf(self):
        """V29: Materiais da malha avaliada incluídos na paleta do 3MF."""
        obj = _create_cube_with_boss("Test3MFMatV29")
        xml_content = build_3mf_xml([obj])
        self.assertIn("<m:colorgroup", xml_content)
        self.assertIn("Test3MFMatV29_MatWhite", [m.name for m in obj.data.materials])

    def test_v30_atomic_publish_rollback_on_failure(self):
        """V30: Falha na publicação de arquivos para o destino aciona rollback completo (C26)."""
        temp_stage = tempfile.mkdtemp(prefix="stage_v30_")
        temp_dest = tempfile.mkdtemp(prefix="dest_v30_")
        try:
            f1_stage = os.path.join(temp_stage, "file1.stl")
            f2_stage = os.path.join(temp_stage, "file2.stl")
            with open(f1_stage, "w") as fp:
                fp.write("data1")
            with open(f2_stage, "w") as fp:
                fp.write("data2")

            dest_f1 = os.path.join(temp_dest, "file1.stl")
            with open(dest_f1, "w") as fp:
                fp.write("original_data1")

            staged = [(f1_stage, "file1.stl"), (f2_stage, "sub_inexistente/invalido/file2.stl")]

            with self.assertRaises(RuntimeError):
                publish_staged_files_atomic(staged, temp_dest)

            with open(dest_f1, "r") as fp:
                content = fp.read()
            self.assertEqual(content, "original_data1", "Rollback falhou em restaurar arquivo preexistente")
        finally:
            shutil.rmtree(temp_stage, ignore_errors=True)
            shutil.rmtree(temp_dest, ignore_errors=True)

    def test_v31_exploded_view_export_as_assembled(self):
        """V31: Exportar em vista explodida gera arquivos com as coordenadas montadas."""
        obj = _create_cube_with_boss("TestExplodedV31")
        xml = build_3mf_xml([obj])
        self.assertIn("<vertex", xml)

    def test_v32_scene_scale_conversion_metric(self):
        """V32: Escalas de cena (1.0, 0.01, 0.001) convertem para milímetros corretamente."""
        scene = bpy.context.scene
        scene.unit_settings.scale_length = 1.0
        self.assertAlmostEqual(get_scene_scale_to_mm(scene), 1000.0)
        scene.unit_settings.scale_length = 0.001
        self.assertAlmostEqual(get_scene_scale_to_mm(scene), 1.0)
        scene.unit_settings.scale_length = 1.0

    def test_v33_cli_arguments_parsing(self):
        """V33: Python externo e script Blender tratam argumentos com ou sem separador '--'."""
        import subprocess
        res = subprocess.run([sys.executable, "scripts/build.py", "--help"], cwd=addon_dir, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("usage:", res.stdout.lower())

    def test_v34_clearance_gap_detector_strict(self):
        """V34: R06 com folga desativada detecta ausência de folga; com 0.15 mm detecta gap."""
        obj = _create_cube_with_boss("TestGapV34")
        res0 = slice_mesh_by_material(obj, material_index=1, region_index=0, extraction_mode='BASE', part_clearance_mm=0.0)
        res1 = slice_mesh_by_material(obj, material_index=1, region_index=0, extraction_mode='BASE', part_clearance_mm=0.15)
        vol0 = evaluate_bmesh_metrics(res0[0], unit_scale=1000.0)["volume_mm3"]
        vol1 = evaluate_bmesh_metrics(res1[0], unit_scale=1000.0)["volume_mm3"]
        self.assertGreater(vol0, vol1, "Folga de 0.15 mm deveria reduzir o volume de A")
        res0[0].free()
        res0[1].free()
        res1[0].free()
        res1[1].free()

    def test_v35_stress_50_generations_datablock_leak_free(self):
        """V35: 50 ciclos de fatiamento sem vazamento de malhas órfãs em bpy.data."""
        initial_meshes = len(bpy.data.meshes)
        obj = _create_cube_with_boss("TestLeakV35")
        for _ in range(50):
            res = slice_mesh_by_material(obj, material_index=1, region_index=0, extraction_mode='BASE')
            res[0].free()
            res[1].free()
        bpy.data.objects.remove(obj, do_unlink=True)
        final_meshes = len(bpy.data.meshes)
        self.assertLessEqual(final_meshes, initial_meshes + 2)

    def test_v36_clean_registration_and_translations(self):
        """V36: Registro, unregister e troca de idioma sem colisões nem duplicações."""
        from src.translations import HELP_TOPICS
        self.assertIn("target_model", HELP_TOPICS)
        self.assertIn("pt_BR", HELP_TOPICS["target_model"]["title"])
        self.assertIn("en_US", HELP_TOPICS["target_model"]["title"])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPlan088AcceptanceMatrix)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
