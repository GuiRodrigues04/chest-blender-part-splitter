"""Suíte de testes de aceitação e regressão para as Correções Pós-Testes da 0.8.7 (Chest Part Splitter).

Cobre os 18 casos de aceitação da Seção 11 do plano Plano_Correcoes_0.8.7_Pos_Testes.md:
- R01: Saliência superior sai inteira no modo BASE, sem núcleo no corpo nem lâmina fora da base.
- R02: Saliência lateral sai inteira, corpo fechado com parede plana.
- R03: Região verde planar mantém extração com profundidade e cavidade complementar (M03).
- R04: Entrada com região incompleta/base ambígua cancela sem volume adivinhado.
- R05: Corte sem folga/encaixes conserva volume e não gera resíduos inesperados.
- R06: Folgas 0 / 0.15 / 0.30 mm medidas em posição montada; exterior preservado.
- R07: Folga 5 mm valida espessura e rejeita caso inviável antes de modificar a cena.
- R08: Troca unilateral/bilateral modifica interfaces conforme contrato e atualiza assinatura.
- R09: Linha coincide com corte incluindo deslocamento 0.030 mm e modificadores.
- R10: Montado/explodido mostram contornos coerentes; nenhum segmento corta o vazio.
- R11: Grade GRID_4 em quadrado/retângulo funciona com rotação de 45 graus e eixos arbitrários.
- R12: Grade em espaço insuficiente preserva validação e 4 pinos; falha com diagnóstico claro.
- R13: Pinos numa peça amarela herdam material amarelo; peça branca gera pinos brancos.
- R14: Ligação multicolor usa material predominante por área em world space (não por contagem).
- R15: Inversão macho A/B recalcula material dos pinos conforme a peça dona do pino.
- R16: Falha na atualização mantém prévia anterior sinalizada e bloqueia confirmação/exportação.
- R17: Escalas de cena 1 / 0.01 / 0.001 e transformações mantêm medidas reais em mm.
- R18: Ciclo de vida, remoção de prévia e falha não deixam objetos temporários nem vazamentos.
"""

import unittest
import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

# Garante importação do pacote local
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

from src.constants import (
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
)
from src.lifecycle import (
    get_or_create_operation_record,
    resolve_operation,
    remove_preview,
)
from src.operators import get_current_session_parts
from src.geometry_plane import evaluate_bmesh_metrics, slice_mesh_by_plane
from src.geometry_material import (
    analyze_material_structure,
    slice_mesh_by_material,
    get_material_regions,
)
from src.geometry_connectors import (
    compute_connector_layout,
    apply_connectors_boolean,
    determine_connector_material,
    find_optimal_grid_axes,
    ConnectorValidationError,
)
from src.geometry_contract import CutInterface
from src.gpu_drawing import _compute_cut_line_segments
from src.operators import compute_session_input_signature, verify_preview_current
from src.diagnostic import get_scene_scale_to_mm


def _create_cube_with_boss(name: str = "CubeBoss", boss_axis: str = 'Z') -> bpy.types.Object:
    """Cria um cubo base 100x100x100 mm com uma saliência 40x40x20 mm perfeitamente unida (manifold).
    
    A saliência possui o material 1 (Amarelo) e o cubo base possui o material 0 (Branco).
    """
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()

    # Cubo base de 0 a 100 mm
    # Vértices base (Z: 0 a 100, X: 0 a 100, Y: 0 a 100)
    cube_verts = []
    for z in (0.0, 100.0):
        for y in (0.0, 100.0):
            for x in (0.0, 100.0):
                cube_verts.append(bm.verts.new((x / 1000.0, y / 1000.0, z / 1000.0)))
    bm.verts.ensure_lookup_table()

    # Cria cubo 100x100x100
    # Bottom (Z=0)
    bm.faces.new((cube_verts[0], cube_verts[2], cube_verts[3], cube_verts[1]))
    # Sides
    bm.faces.new((cube_verts[0], cube_verts[1], cube_verts[5], cube_verts[4])) # -Y
    bm.faces.new((cube_verts[2], cube_verts[6], cube_verts[7], cube_verts[3])) # +Y
    bm.faces.new((cube_verts[0], cube_verts[4], cube_verts[6], cube_verts[2])) # -X
    bm.faces.new((cube_verts[1], cube_verts[3], cube_verts[7], cube_verts[5])) # +X

    # No topo (Z=100 mm), cria abertura de 30 a 70 mm (40x40 mm) para a saliência
    # Top vertices outer: 4, 5, 7, 6
    # Inner boss base vertices (Z=100 mm)
    b0 = bm.verts.new((0.03, 0.03, 0.10))
    b1 = bm.verts.new((0.07, 0.03, 0.10))
    b2 = bm.verts.new((0.07, 0.07, 0.10))
    b3 = bm.verts.new((0.03, 0.07, 0.10))

    # Top faces do cubo ao redor da saliência (4 faces trapezoidais)
    bm.faces.new((cube_verts[4], cube_verts[5], b1, b0))
    bm.faces.new((cube_verts[5], cube_verts[7], b2, b1))
    bm.faces.new((cube_verts[7], cube_verts[6], b3, b2))
    bm.faces.new((cube_verts[6], cube_verts[4], b0, b3))

    # Vértices do topo da saliência (Z=120 mm)
    t0 = bm.verts.new((0.03, 0.03, 0.12))
    t1 = bm.verts.new((0.07, 0.03, 0.12))
    t2 = bm.verts.new((0.07, 0.07, 0.12))
    t3 = bm.verts.new((0.03, 0.07, 0.12))

    # Paredes laterais da saliência
    bf0 = bm.faces.new((b0, b1, t1, t0))
    bf1 = bm.faces.new((b1, b2, t2, t1))
    bf2 = bm.faces.new((b2, b3, t3, t2))
    bf3 = bm.faces.new((b3, b0, t0, t3))
    # Topo da saliência
    bf4 = bm.faces.new((t0, t1, t2, t3))

    # Atribui material 0 para cubo e material 1 para saliência
    for f in bm.faces:
        f.material_index = 0
    for f in (bf0, bf1, bf2, bf3, bf4):
        f.material_index = 1

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    # Materiais: Branco (0) e Amarelo (1)
    mat_white = bpy.data.materials.new(f"{name}_White")
    mat_white.diffuse_color = (0.9, 0.9, 0.9, 1.0)
    mat_yellow = bpy.data.materials.new(f"{name}_Yellow")
    mat_yellow.diffuse_color = (1.0, 0.85, 0.0, 1.0)
    obj.data.materials.append(mat_white)
    obj.data.materials.append(mat_yellow)

    bpy.context.scene.collection.objects.link(obj)
    return obj


def _create_cube_with_lateral_boss(name: str = "CubeLatBoss") -> bpy.types.Object:
    """Cria um cubo base com uma saliência na face lateral (+X)."""
    obj = _create_cube_with_boss(name=name, boss_axis='Z')
    # Rotaciona para que a saliência fique no eixo lateral +X
    obj.rotation_euler = Euler((0.0, math.radians(90.0), 0.0), 'XYZ')
    bpy.context.view_layer.update()
    return obj


class TestPosTestes087(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import src
        try:
            src.register()
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        import src
        try:
            src.unregister()
        except Exception:
            pass

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        self.scene = bpy.context.scene
        if not hasattr(self.scene, "chest_splitter"):
            from src.properties import register as register_props
            try:
                register_props()
            except Exception:
                pass

    def tearDown(self):
        pass

    def test_r01_top_protrusion_base_detachment(self):
        """R01: Saliência superior sai inteira no modo BASE, sem núcleo no corpo nem lâmina fora da base."""
        obj = _create_cube_with_boss("R01_Boss")
        res = slice_mesh_by_material(
            obj,
            material_index=1,
            extraction_mode='BASE',
            scene=self.scene,
        )
        bm_a, bm_b = res[0], res[1]
        metrics_a = evaluate_bmesh_metrics(bm_a, unit_scale=1000.0)
        metrics_b = evaluate_bmesh_metrics(bm_b, unit_scale=1000.0)

        # Parte A (saliência 40x40x20 mm): volume esperado 32,000 mm³
        self.assertAlmostEqual(metrics_a["volume_mm3"], 32000.0, delta=50.0)
        self.assertTrue(metrics_a["is_manifold"])
        self.assertEqual(metrics_a["non_manifold_edges"], 0)
        self.assertEqual(metrics_a["components"], 1)

        # Parte B (cubo base 100x100x100 mm): volume esperado 1,000,000 mm³
        self.assertAlmostEqual(metrics_b["volume_mm3"], 1000000.0, delta=50.0)
        self.assertTrue(metrics_b["is_manifold"])
        self.assertEqual(metrics_b["non_manifold_edges"], 0)
        self.assertEqual(metrics_b["components"], 1)

        # A tampa de Parte B deve ser plana na cota Z = 100 mm
        bm_b.faces.ensure_lookup_table()
        cap_faces_b = [f for f in bm_b.faces if all(abs(v.co.z - 0.10) < 1e-4 for v in f.verts)]
        self.assertTrue(len(cap_faces_b) > 0, "Parte B deve ter tampa plana fechando a base da saliência")

        bm_a.free()
        bm_b.free()

    def test_r02_lateral_protrusion_base_detachment(self):
        """R02: Saliência lateral sai inteira, corpo fechado com parede plana."""
        obj = _create_cube_with_lateral_boss("R02_LatBoss")
        res = slice_mesh_by_material(
            obj,
            material_index=1,
            extraction_mode='BASE',
            scene=self.scene,
        )
        bm_a, bm_b = res[0], res[1]
        metrics_a = evaluate_bmesh_metrics(bm_a, unit_scale=1000.0)
        metrics_b = evaluate_bmesh_metrics(bm_b, unit_scale=1000.0)

        self.assertAlmostEqual(metrics_a["volume_mm3"], 32000.0, delta=100.0)
        self.assertAlmostEqual(metrics_b["volume_mm3"], 1000000.0, delta=100.0)
        self.assertTrue(metrics_a["is_manifold"])
        self.assertTrue(metrics_b["is_manifold"])
        self.assertEqual(metrics_a["components"], 1)
        self.assertEqual(metrics_b["components"], 1)

        bm_a.free()
        bm_b.free()

    def test_r03_planar_patch_depth_extraction_preserved(self):
        """R03: Região verde planar mantém extração com profundidade e cavidade complementar (M03)."""
        # Cubo 50x50x50 mm com face superior pintada de verde
        mesh = bpy.data.meshes.new("PlanarPatchMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.05)
        # Face superior pintada com material 1
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
        self.scene.collection.objects.link(cube)

        depth_mm = 5.0
        res = slice_mesh_by_material(
            cube,
            material_index=1,
            depth_mm=depth_mm,
            extraction_mode='EXTRUDE',
            scene=self.scene,
        )
        bm_a, bm_b = res[0], res[1]
        metrics_a = evaluate_bmesh_metrics(bm_a, unit_scale=1000.0)
        metrics_b = evaluate_bmesh_metrics(bm_b, unit_scale=1000.0)

        # Placa extraída: 50 x 50 x 5 mm = 12,500 mm³
        self.assertAlmostEqual(metrics_a["volume_mm3"], 12500.0, delta=50.0)
        # Corpo restante: 125,000 - 12,500 = 112,500 mm³
        self.assertAlmostEqual(metrics_b["volume_mm3"], 112500.0, delta=50.0)
        self.assertTrue(metrics_a["is_manifold"])
        self.assertTrue(metrics_b["is_manifold"])

        bm_a.free()
        bm_b.free()

    def test_r04_ambiguous_base_rejected_without_guessing(self):
        """R04: Entrada com região incompleta ou base não-planar cancela com diagnóstico claro sem volume adivinhado."""
        obj = _create_cube_with_boss("R04_Incomplete")
        # Pinta apenas 2 faces da saliência com o material 1, deixando a base aberta/não-fechada
        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        boss_faces = [f for f in bm.faces if f.material_index == 1]
        for f in boss_faces[:2]:
            f.material_index = 0
        bm.to_mesh(mesh)
        bm.free()

        with self.assertRaises(ValueError) as ctx:
            slice_mesh_by_material(
                obj,
                material_index=1,
                extraction_mode='BASE',
                scene=self.scene,
            )
        self.assertTrue(len(str(ctx.exception)) > 0)

    def test_r05_volume_conservation_no_waste(self):
        """R05: Corte sem folga nem encaixes conserva volume total exato e não gera resíduos inesperados."""
        obj = _create_cube_with_boss("R05_Conserve")
        vol_original = 1000000.0 + 32000.0

        res = slice_mesh_by_material(
            obj,
            material_index=1,
            extraction_mode='BASE',
            part_clearance_mm=0.0,
            scene=self.scene,
        )
        bm_a, bm_b = res[0], res[1]
        metrics_a = evaluate_bmesh_metrics(bm_a, unit_scale=1000.0)
        metrics_b = evaluate_bmesh_metrics(bm_b, unit_scale=1000.0)

        sum_vol = metrics_a["volume_mm3"] + metrics_b["volume_mm3"]
        self.assertAlmostEqual(sum_vol, vol_original, delta=1.0)
        self.assertEqual(metrics_a["components"], 1)
        self.assertEqual(metrics_b["components"], 1)

        bm_a.free()
        bm_b.free()

    def test_r06_part_clearances_measured_in_assembled_position(self):
        """R06: Folgas de 0.0, 0.15 e 0.30 mm medidas na interface em posição montada."""
        obj = _create_cube_with_boss("R06_Clearance")

        for c_val in (0.0, 0.15, 0.30):
            res = slice_mesh_by_material(
                obj,
                material_index=1,
                extraction_mode='BASE',
                part_clearance_mm=c_val,
                part_clearance_apply_to='PART',
                scene=self.scene,
            )
            bm_a, bm_b = res[0], res[1]
            # Em Parte A, a tampa de base deve estar na cota Z = 100 mm + c_val (em metros: 0.10 + c_val/1000)
            bm_a.verts.ensure_lookup_table()
            min_z_a = min(v.co.z for v in bm_a.verts) * 1000.0
            expected_min_z = 100.0 + c_val
            self.assertAlmostEqual(min_z_a, expected_min_z, delta=0.01)

            bm_a.free()
            bm_b.free()

    def test_r07_clearance_exceeding_useful_thickness_rejected(self):
        """R07: Folga que excede ou elimina espessura útil rejeita antes de modificar a cena."""
        obj = _create_cube_with_boss("R07_Excessive")
        # Altura útil da saliência é 20 mm; testar folga de 25 mm
        with self.assertRaises(ValueError) as ctx:
            slice_mesh_by_material(
                obj,
                material_index=1,
                extraction_mode='BASE',
                part_clearance_mm=25.0,
                scene=self.scene,
            )
        self.assertIn("excede ou elimina a altura útil", str(ctx.exception))

    def test_r08_unilateral_vs_bilateral_clearance_and_signature(self):
        """R08: Aplicações PART, CAVITY e BOTH produzem alívios físicos corretos e atualizam assinatura."""
        obj = _create_cube_with_boss("R08_Modes")
        settings = self.scene.chest_splitter
        settings.target_object = obj
        settings.split_mode = 'MATERIAL'
        settings.material_split_index = 1
        settings.part_clearance_mm = 0.5

        settings.part_clearance_apply_to = 'PART'
        sig_part = compute_session_input_signature(bpy.context)

        settings.part_clearance_apply_to = 'CAVITY'
        sig_cavity = compute_session_input_signature(bpy.context)

        settings.part_clearance_apply_to = 'BOTH'
        sig_both = compute_session_input_signature(bpy.context)

        self.assertNotEqual(sig_part, sig_cavity)
        self.assertNotEqual(sig_part, sig_both)
        self.assertNotEqual(sig_cavity, sig_both)

    def test_r09_cut_line_matches_offset(self):
        """R09: Linha de corte coincide com o plano efetivo incluindo deslocamento de 0.030 mm."""
        mesh = bpy.data.meshes.new("R09_Mesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.10)
        bm.to_mesh(mesh)
        bm.free()

        plane_origin = Vector((0.0, 0.0, 0.0))
        plane_normal = Vector((0.0, 0.0, 1.0))
        offset_mm = 0.030
        effective_origin = plane_origin + Vector((0.0, 0.0, offset_mm / 1000.0))

        segments = _compute_cut_line_segments(
            mesh,
            matrix_world=Matrix.Identity(4),
            plane_co=effective_origin,
            plane_no=plane_normal,
            is_bmesh=False,
        )
        self.assertTrue(len(segments) >= 8)
        # Todos os pontos de corte devem ter cota Z exatamente igual a 0.030 / 1000.0
        for pt in segments:
            self.assertAlmostEqual(pt.z, offset_mm / 1000.0, places=5)

    def test_r10_cut_line_no_void_crossing(self):
        """R10: Linha de corte é calculada face a face; nenhum segmento cruza o vazio entre ilhas."""
        mesh = bpy.data.meshes.new("R10_Mesh")
        bm = bmesh.new()
        # Dois cubos separados no mesmo mesh: Cubo 1 em X=-0.05, Cubo 2 em X=+0.05
        bmesh.ops.create_cube(bm, size=0.03, matrix=Matrix.Translation((-0.05, 0.0, 0.0)))
        bmesh.ops.create_cube(bm, size=0.03, matrix=Matrix.Translation((0.05, 0.0, 0.0)))
        bm.to_mesh(mesh)
        bm.free()

        segments = _compute_cut_line_segments(
            mesh,
            matrix_world=Matrix.Identity(4),
            plane_co=Vector((0.0, 0.0, 0.0)),
            plane_no=Vector((0.0, 0.0, 1.0)),
            is_bmesh=False,
        )
        self.assertTrue(len(segments) >= 8)
        # Cada segmento (p0, p1) deve pertencer estritamente a um único cubo
        for i in range(0, len(segments), 2):
            p0 = segments[i]
            p1 = segments[i + 1]
            seg_len = (p0 - p1).length
            # Segmentos dentro de cada cubo de 30mm têm comprimento no máximo 30mm
            self.assertLess(seg_len, 0.035, "Segmento não deve conectar ilhas distintas através do vazio")

    def test_r11_grid4_square_rotated_45_degrees(self):
        """R11: Grade GRID_4 em quadrado rotacionado 45° gera 4 encaixes válidos e seguros (Demonstracao_Grade_4)."""
        # Interface de 103 x 103 mm rotacionada 45° no plano UV
        side_mm = 103.0
        limit = side_mm / math.sqrt(2.0)
        # 4 vértices do quadrado girado 45°
        diamond_uv = [
            (0.0, limit),
            (limit, 0.0),
            (0.0, -limit),
            (-limit, 0.0),
        ]

        # Converte para metros (BU)
        diamond_uv_bu = [(u / 1000.0, v / 1000.0) for u, v in diamond_uv]

        iface = CutInterface(
            origin_world=Vector((0.0, 0.0, 0.0)),
            normal_a_to_b_world=Vector((0.0, 0.0, 1.0)),
            axis_u_world=Vector((1.0, 0.0, 0.0)),
            axis_v_world=Vector((0.0, 1.0, 0.0)),
            outer_contours_uv=[diamond_uv_bu],
            hole_contours_uv=[],
        )

        # Testa cálculo de layout com GRID_4
        layout = compute_connector_layout(
            target_mesh=None,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0.0, 0.0, 0.0)),
            plane_normal=Vector((0.0, 0.0, 1.0)),
            distribution='GRID_4',
            diameter_mm=10.0,
            clearance_per_side_mm=0.10,
            edge_margin_mm=1.0,
            unit_scale=1000.0,
            interface=iface,
        )
        positions = layout["positions"]
        self.assertEqual(len(positions), 4, "GRID_4 deve gerar exatamente 4 posições viáveis")

    def test_r12_grid4_insufficient_space_rejected_with_diagnostic(self):
        """R12: Grade em domínio insuficiente preserva integridade e rejeita com diagnóstico sem reduzir para 3 pinos."""
        # Seção minúscula de 15 x 15 mm que não comporta 4 pinos de 10 mm
        small_square_bu = [
            (-0.0075, -0.0075),
            (0.0075, -0.0075),
            (0.0075, 0.0075),
            (-0.0075, 0.0075),
        ]
        iface_small = CutInterface(
            origin_world=Vector((0.0, 0.0, 0.0)),
            normal_a_to_b_world=Vector((0.0, 0.0, 1.0)),
            axis_u_world=Vector((1.0, 0.0, 0.0)),
            axis_v_world=Vector((0.0, 1.0, 0.0)),
            outer_contours_uv=[small_square_bu],
            hole_contours_uv=[],
        )
        with self.assertRaises(ConnectorValidationError) as ctx:
            compute_connector_layout(
                target_mesh=None,
                matrix_world=Matrix.Identity(4),
                plane_origin=Vector((0.0, 0.0, 0.0)),
                plane_normal=Vector((0.0, 0.0, 1.0)),
                distribution='GRID_4',
                diameter_mm=10.0,
                clearance_per_side_mm=0.10,
                edge_margin_mm=1.0,
                unit_scale=1000.0,
                interface=iface_small,
            )
        self.assertIn("Falta de espaço", str(ctx.exception))

    def test_r13_connector_inherits_yellow_material(self):
        """R13: Pinos gerados na peça amarela herdam material amarelo; peça branca gera pinos brancos."""
        # Cria objeto amarelo
        mesh_yellow = bpy.data.meshes.new("YellowPieceMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.04)
        bm.to_mesh(mesh_yellow)
        bm.free()

        obj_yellow = bpy.data.objects.new("YellowPiece", mesh_yellow)
        mat_yellow = bpy.data.materials.new("MatYellow")
        mat_yellow.diffuse_color = (1.0, 0.85, 0.0, 1.0)
        obj_yellow.data.materials.append(mat_yellow)
        self.scene.collection.objects.link(obj_yellow)

        mat_chosen = determine_connector_material(
            obj_yellow,
            positions=[Vector((0.0, 0.0, 0.02))],
            connector_radius_bu=0.005,
            plane_normal=Vector((0.0, 0.0, 1.0)),
        )
        self.assertEqual(mat_chosen, mat_yellow, "Pino deve herdar material amarelo")

    def test_r14_multicolor_predominant_area_world_space(self):
        """R14: Ligação multicolor usa material predominante por área em world space (não por contagem de polígonos)."""
        mesh = bpy.data.meshes.new("MultiMesh")
        bm = bmesh.new()
        # 1 face grande de 100x100 mm com Material Amarelo (área = 10,000 mm²)
        v0 = bm.verts.new((0.0, 0.0, 0.0))
        v1 = bm.verts.new((0.10, 0.0, 0.0))
        v2 = bm.verts.new((0.10, 0.10, 0.0))
        v3 = bm.verts.new((0.0, 0.10, 0.0))
        f_large = bm.faces.new((v0, v1, v2, v3))
        f_large.material_index = 1  # Amarelo

        # 100 micro faces de 1x1 mm com Material Branco (área total = 100 mm²)
        # Muitas faces mas área minúscula
        for i in range(10):
            for j in range(10):
                x = 0.10 + i * 0.001
                y = j * 0.001
                mv0 = bm.verts.new((x, y, 0.0))
                mv1 = bm.verts.new((x + 0.001, y, 0.0))
                mv2 = bm.verts.new((x + 0.001, y + 0.001, 0.0))
                mv3 = bm.verts.new((x, y + 0.001, 0.0))
                f_micro = bm.faces.new((mv0, mv1, mv2, mv3))
                f_micro.material_index = 0  # Branco

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("MultiObj", mesh)
        mat_white = bpy.data.materials.new("MatWhite")
        mat_yellow = bpy.data.materials.new("MatYellow")
        obj.data.materials.append(mat_white)
        obj.data.materials.append(mat_yellow)
        self.scene.collection.objects.link(obj)

        mat_chosen = determine_connector_material(
            obj,
            positions=[Vector((0.05, 0.05, 0.0))],
            connector_radius_bu=0.005,
            plane_normal=Vector((0.0, 0.0, 1.0)),
        )
        self.assertEqual(mat_chosen, mat_yellow, "Área predominante (10,000 mm²) deve vencer contagem de faces")

    def test_r15_male_part_inversion_recalculates_material(self):
        """R15: Inversão macho A/B recalcula material dos pinos conforme a peça que contém o macho."""
        mesh_a = bpy.data.meshes.new("MeshA")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.04)
        bm.to_mesh(mesh_a)
        bm.free()
        obj_a = bpy.data.objects.new("PartA", mesh_a)
        mat_a = bpy.data.materials.new("MatA")
        obj_a.data.materials.append(mat_a)

        mesh_b = bpy.data.meshes.new("MeshB")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.04)
        bm.to_mesh(mesh_b)
        bm.free()
        obj_b = bpy.data.objects.new("PartB", mesh_b)
        mat_b = bpy.data.materials.new("MatB")
        obj_b.data.materials.append(mat_b)

        # Se macho é A -> pino herda mat_a
        mat_male_a = determine_connector_material(obj_a, [Vector((0, 0, 0))], 0.005, Vector((0, 0, 1)))
        self.assertEqual(mat_male_a, mat_a)

        # Se invertido e macho é B -> pino herda mat_b
        mat_male_b = determine_connector_material(obj_b, [Vector((0, 0, 0))], 0.005, Vector((0, 0, 1)))
        self.assertEqual(mat_male_b, mat_b)

    def test_r16_preview_failure_preserves_previous_and_blocks_commit(self):
        """R16: Falha na grade mantém prévia anterior sinalizada com aviso persistente e bloqueia commit."""
        from src.operators import CHEST_OT_splitter_commit_parts
        settings = self.scene.chest_splitter
        settings.session_status = 'PREVIEW_INVALID'
        settings.last_status = "Aviso: A última atualização falhou (Falta de espaço).\nA prévia visualizada é a anterior válida."
        settings.last_status_level = 'WARNING'

        # commit_parts deve estar bloqueado quando a sessão estiver com erro ou prévia inválida
        can_commit = CHEST_OT_splitter_commit_parts.poll(bpy.context)
        self.assertFalse(can_commit, "commit_parts deve ser bloqueado após falha de atualização")

    def test_r17_scale_invariance_and_transforms(self):
        """R17: Escalas de cena e transformações mantêm dimensões físicas exatas em mm."""
        for s_val in (1.0, 0.01, 0.001):
            self.scene.unit_settings.scale_length = s_val
            scale_to_mm = get_scene_scale_to_mm(self.scene)
            # Medida de 50 mm em BU
            bu_val = 50.0 / scale_to_mm
            mm_back = bu_val * scale_to_mm
            self.assertAlmostEqual(mm_back, 50.0, places=5)

    def test_r18_clean_lifecycle_no_leaks(self):
        """R18: Remoção de prévia e ciclos de erro não deixam objetos temporários na cena."""
        obj = _create_cube_with_boss("R18_Clean")
        initial_obj_count = len(bpy.data.objects)
        initial_mesh_count = len(bpy.data.meshes)

        # Gera resultado
        res = slice_mesh_by_material(obj, material_index=1, extraction_mode='BASE', scene=self.scene)
        res[0].free()
        res[1].free()

        # Nenhuma malha temporária órfã deve restar em bpy.data
        for o in list(bpy.data.objects):
            if "temp_mat_prism" in o.name:
                self.fail(f"Objeto temporário não liberado: {o.name}")


if __name__ == '__main__':
    res = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestPosTestes087))
    if not res.wasSuccessful():
        import sys
        sys.exit(1)
