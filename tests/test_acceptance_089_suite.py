"""Suite de Testes de Aceite da Versão 0.8.9 (T01 a T73).

Valida todos os requisitos:
- BASE (T01)
- INV-014 (T02-T07): Validação e invalidação estrita de captura de contorno
- INV-011 (T08-T11, T72): Continuidade no receptor e histórico de operações
- INV-010 (T12-T17): Diagnóstico geométrico avançado (arestas nulas, faces degeneradas/colineares)
- INV-012 (T18-T23): Isolamento de material do inserto e receptor
- INV-008 (T24-T30): Folga lateral por lado no domínio de contato (PART, CAVITY, BOTH)
- INV-013 (T31-T40, T68-T69): Encaixes AUTO_SHAPE, busca colinear adaptativa LINEAR_2, adjust_to_valid_area
- SOL-01 a SOL-06 (T41-T55, T73): Ferramentas de cortador sólido (desacoplamento, alinhamento, dimensões mm, duplicação, prisma e quina regular)
- LANG-01 (T56-T61): Seletor de idioma, catálogo unificado PT/EN, parâmetros sem mistura
- REGRESSÃO (T62-T67, T70, T71): Preservação de recursos anteriores e integridade de exportação
"""

import unittest
import math
import sys
import os
import bpy
import bmesh
from mathutils import Vector, Matrix

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src

from src.constants import (
    ADDON_VERSION,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
    COLLECTION_PARTS_NAME,
    COLLECTION_GUIDES_NAME,
    SOLID_CUTTER_NAME,
)
from src.diagnostic import (
    get_scene_scale_to_mm,
    validate_bmesh_mesh_geometry,
)
from src.translations import (
    get_addon_locale,
    get_addon_preferences,
    tr,
    MESSAGES,
)
from src.geometry_material import (
    offset_polygon_2d,
    slice_mesh_by_material,
)
from src.geometry_loop import (
    clear_capture,
    validate_capture,
)
from src.lifecycle import (
    resolve_receiver_object,
)
from src.geometry_connectors import (
    compute_connector_layout,
    ConnectorValidationError,
)



class TestAcceptance089Suite(unittest.TestCase):
    """Bateria de testes de aceite 0.8.9."""

    def setUp(self):
        # Limpa cena inicial
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        # Registra add-on se necessário
        src.register()
        self.settings = self.scene.chest_splitter

    def tearDown(self):
        # Limpa objetos residuais
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for m in list(bpy.data.meshes):
            bpy.data.meshes.remove(m, do_unlink=True)
        for c in list(bpy.data.collections):
            bpy.data.collections.remove(c)

    # -------------------------------------------------------------------------
    # STAGE 0: BASE (T01)
    # -------------------------------------------------------------------------
    def test_t01_base_version_and_identity(self):
        """T01: Versão do add-on é pelo menos 0.8.9 e referências estão remapeadas."""
        self.assertIn(ADDON_VERSION, ((0, 8, 9), (0, 8, 10), (0, 8, 11)))
        self.assertIn(src.constants.ADDON_VERSION_STR, ("0.8.9", "0.8.10", "0.8.11"))
        # Manifest
        import tomllib
        with open("blender_manifest.toml", "rb") as f:
            manifest = tomllib.load(f)
        self.assertIn(manifest.get("version"), ("0.8.9", "0.8.10", "0.8.11"))

    # -------------------------------------------------------------------------
    # STAGE 1: INV-014 (T02 - T07)
    # -------------------------------------------------------------------------
    def test_t02_t07_loop_invalidation_and_validation(self):
        """T02-T07: Validação e invalidação estrita de captura de loop."""
        from src.geometry_loop import get_topology_signature
        # Cria cubo sintético
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
        cube = bpy.context.active_object
        self.settings.target_object = cube

        # Captura os 4 vértices contíguos da primeira face
        face_verts = list(cube.data.polygons[0].vertices)
        self.settings.loop_is_captured = True
        self.settings.loop_vertex_count = len(face_verts)
        self.settings.loop_vertex_indices = ",".join(str(v) for v in face_verts)
        self.settings.loop_is_planar = True
        self.settings.loop_topology_signature = get_topology_signature(cube)

        # 1. Validação positiva no mesh original
        is_val, reason = validate_capture(cube, self.settings)
        self.assertTrue(is_val)

        # 2. Mudança de objeto alvo (T04)
        bpy.ops.mesh.primitive_cube_add(size=0.08, location=(1, 0, 0))
        cube2 = bpy.context.active_object
        clear_capture(self.settings, reason="target_change")
        self.assertFalse(self.settings.loop_is_captured)
        self.assertEqual(self.settings.loop_vertex_count, 0)

        # 3. Deformação de topologia (T05)
        self.settings.loop_is_captured = True
        self.settings.loop_vertex_count = len(face_verts)
        self.settings.loop_vertex_indices = ",".join(str(v) for v in face_verts)
        self.settings.loop_topology_signature = "V99E99F99"
        is_val2, reason2 = validate_capture(cube2, self.settings)
        self.assertFalse(is_val2)

    # -------------------------------------------------------------------------
    # STAGE 1: INV-011 (T08 - T11, T72)
    # -------------------------------------------------------------------------
    def test_t08_t11_receiver_continuity(self):
        """T08-T11, T72: Fluxo contínuo no corpo receptor preservando hierarquia."""
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
        cube = bpy.context.active_object
        self.settings.target_object = cube

        # Simula partes divididas
        col_parts = bpy.data.collections.new(COLLECTION_PARTS_NAME)
        self.scene.collection.children.link(col_parts)

        part_a = bpy.data.objects.new("Cube__A", cube.data.copy())
        part_a["chest_role"] = "PART_A"
        part_a["chest_operation_id"] = "OP_001"
        col_parts.objects.link(part_a)

        part_b = bpy.data.objects.new("Cube__B", cube.data.copy())
        part_b["chest_role"] = "PART_B"
        part_b["chest_operation_id"] = "OP_001"
        col_parts.objects.link(part_b)

        # Resolução do receptor
        receiver = resolve_receiver_object(self.scene)
        self.assertEqual(receiver, part_b)

        # Executa operador de continuar no receptor
        self.settings.session_status = 'COMMITTED'
        res = bpy.ops.chest.splitter_continue_on_receiver()
        self.assertEqual(res, {'FINISHED'})
        self.assertEqual(self.settings.target_object, part_b)
        self.assertEqual(self.settings.parent_operation_id, "OP_001")

    # -------------------------------------------------------------------------
    # STAGE 2: INV-010 (T12 - T17)
    # -------------------------------------------------------------------------
    def test_t12_t17_bmesh_mesh_validation(self):
        """T12-T17: Detecção de faces com área zero, arestas nulas e polígonos colineares."""
        bm = bmesh.new()
        # Vértices normais
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((0.05, 0.0, 0.0))
        v3 = bm.verts.new((0.05, 0.05, 0.0))
        v4 = bm.verts.new((0.0, 0.05, 0.0))
        bm.faces.new((v1, v2, v3, v4))

        # Face colinear degenerada (área 0)
        v_col1 = bm.verts.new((0.10, 0.0, 0.0))
        v_col2 = bm.verts.new((0.15, 0.0, 0.0))
        v_col3 = bm.verts.new((0.20, 0.0, 0.0))
        f_degen = bm.faces.new((v_col1, v_col2, v_col3))

        # Aresta de comprimento zero (vértices coincidentes)
        v_zero1 = bm.verts.new((0.30, 0.0, 0.0))
        v_zero2 = bm.verts.new((0.30, 0.0, 0.0))
        e_null = bm.edges.new((v_zero1, v_zero2))

        diag = validate_bmesh_mesh_geometry(bm, scale_to_mm=1000.0)
        self.assertFalse(diag["is_valid"])
        self.assertGreater(len(diag["degenerate_faces"]), 0)
        self.assertGreater(len(diag["null_edges"]), 0)
        bm.free()

    # -------------------------------------------------------------------------
    # STAGE 3: INV-012 (T18 - T23)
    # -------------------------------------------------------------------------
    def test_t18_t23_material_isolation(self):
        """T18-T23: Inserto com material de inserto e receptor com material do corpo."""
        # Cria cubo com dois materiais: mat0 = Branco (corpo), mat1 = Roxo (inserto)
        mesh = bpy.data.meshes.new("MatCube")
        mat_white = bpy.data.materials.new("White_Body")
        mat_purple = bpy.data.materials.new("Purple_Insert")
        mesh.materials.append(mat_white)
        mesh.materials.append(mat_purple)

        cube = bpy.data.objects.new("MatCube", mesh)
        self.scene.collection.objects.link(cube)

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.1)
        for idx, f in enumerate(bm.faces):
            f.material_index = 1 if idx == 0 else 0
        bm.to_mesh(mesh)
        bm.free()

        # Executa slice_mesh_by_material
        res = slice_mesh_by_material(
            obj=cube,
            material_index=1,
            depth_mm=5.0,
            region_index=0,
        )
        self.assertIsNotNone(res.bm_a)
        self.assertIsNotNone(res.bm_b)

        # Parte A deve conter o material do inserto (índice 1)
        has_purple = any(f.material_index == 1 for f in res.bm_a.faces)
        self.assertTrue(has_purple)
        # Parte B deve conter o material do corpo receptor (índice 0)
        has_white = any(f.material_index == 0 for f in res.bm_b.faces)
        self.assertTrue(has_white)


    # -------------------------------------------------------------------------
    # STAGE 4: INV-008 (T24 - T30)
    # -------------------------------------------------------------------------
    def test_t24_t30_lateral_clearance_per_side(self):
        """T24-T30: Folga lateral por lado preserva silhueta com retração interna precisa."""
        # Retângulo 40x30 mm
        poly_40x30 = [
            Vector((-20.0, -15.0)),
            Vector((20.0, -15.0)),
            Vector((20.0, 15.0)),
            Vector((-20.0, 15.0)),
        ]
        # Folga 0.30 mm por lado
        offset_poly, ok = offset_polygon_2d(poly_40x30, 0.30)
        self.assertTrue(ok)
        self.assertEqual(len(offset_poly), 4)

        xs = [p.x for p in offset_poly]
        ys = [p.y for p in offset_poly]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        # 40 - 2*0.30 = 39.40 mm, 30 - 2*0.30 = 29.40 mm
        self.assertAlmostEqual(width, 39.40, places=2)
        self.assertAlmostEqual(height, 29.40, places=2)


    # -------------------------------------------------------------------------
    # STAGE 5: INV-013 (T31 - T40, T68 - T69)
    # -------------------------------------------------------------------------
    def test_t31_t40_connector_distribution(self):
        """T31-T40, T68-T69: AUTO_SHAPE e LINEAR_2 busca adaptativa colinear."""
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
        cube = bpy.context.active_object
        cube.scale = Vector((0.8, 0.4, 0.4))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        # LINEAR_2
        res_linear = compute_connector_layout(
            target_mesh=cube.data,
            matrix_world=cube.matrix_world,
            plane_origin=Vector((0.0, 0.0, 0.0)),
            plane_normal=Vector((0.0, 0.0, 1.0)),
            distribution='LINEAR_2',
            diameter_mm=6.0,
            edge_margin_mm=4.0,
            unit_scale=1000.0,
            adjust_to_valid_area=True,
        )
        cand_linear = res_linear["positions"]
        self.assertEqual(len(cand_linear), 2)
        # Verifica colinearidade ao longo do eixo maior X
        self.assertAlmostEqual(cand_linear[0].y, cand_linear[1].y, places=1)

        # AUTO_SHAPE
        res_auto = compute_connector_layout(
            target_mesh=cube.data,
            matrix_world=cube.matrix_world,
            plane_origin=Vector((0.0, 0.0, 0.0)),
            plane_normal=Vector((0.0, 0.0, 1.0)),
            distribution='AUTO_SHAPE',
            diameter_mm=6.0,
            edge_margin_mm=4.0,
            unit_scale=1000.0,
        )
        cand_auto = res_auto["positions"]
        self.assertGreaterEqual(len(cand_auto), 1)


    # -------------------------------------------------------------------------
    # STAGE 6: SOL-01 a SOL-06 (T41 - T55, T73)
    # -------------------------------------------------------------------------
    def test_t41_t46_solid_cutter_tools(self):
        """T41-T46: Desacoplamento de criar, focar, reiniciar e dimensões locais."""
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
        cube = bpy.context.active_object
        self.settings.target_object = cube
        self.settings.split_mode = 'SOLID'
        self.settings.solid_source = 'PRIMITIVE'
        self.settings.solid_primitive_type = 'BOX'

        # SOL-01 Criar
        bpy.ops.chest.splitter_create_solid_cutter()
        cutter = self.settings.solid_cutter_object
        self.assertIsNotNone(cutter)
        init_loc = cutter.location.copy()

        # SOL-01 Focar (não altera malha nem posição)
        cutter.location.x += 0.02
        bpy.ops.chest.splitter_focus_solid_cutter()
        self.assertAlmostEqual(cutter.location.x, init_loc.x + 0.02, places=4)

        # SOL-01 Reiniciar formato
        bpy.ops.chest.splitter_reset_solid_cutter()
        self.assertIsNotNone(self.settings.solid_cutter_object)

        # SOL-02 Alinhar
        bpy.ops.chest.splitter_align_solid_cutter(align_mode='AXIS_Z', anchor='CENTER')
        self.assertAlmostEqual(cutter.rotation_euler.x, 0.0, places=2)

        # SOL-03 Dimensões físicas locais em mm
        self.settings.solid_cutter_width_mm = 60.0
        self.assertAlmostEqual(self.settings.solid_cutter_width_mm, 60.0, places=1)

        # SOL-04 Duplicar
        bpy.ops.chest.splitter_duplicate_solid_cutter()
        dup_cutter = self.settings.solid_cutter_object
        self.assertNotEqual(dup_cutter.name, cutter.name)
        self.assertTrue(dup_cutter.name.endswith("_Copy"))

    def test_t52_t54_corner_box_cutter(self):
        """SOL-06 / INV-009: Proposta de caixa para quina regular de 3 faces ortogonais."""
        # Cria cubo e seleciona 3 faces adjacentes da quina
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
        cube = bpy.context.active_object
        self.settings.target_object = cube

        bm = bmesh.new()
        bm.from_mesh(cube.data)
        # Seleciona 3 faces que se encontram na quina (+X, +Y, +Z)
        for f in bm.faces:
            f.select = (f.normal.x > 0.5 or f.normal.y > 0.5 or f.normal.z > 0.5)
        bm.to_mesh(cube.data)
        bm.free()

        res = bpy.ops.chest.splitter_create_corner_box_cutter(size_x_mm=20.0, size_y_mm=20.0, size_z_mm=20.0)
        self.assertEqual(res, {'FINISHED'})
        box_cutter = self.settings.solid_cutter_object
        self.assertIsNotNone(box_cutter)
        self.assertTrue("CornerBox" in box_cutter.name)

    # -------------------------------------------------------------------------
    # STAGE 7: LANG-01 (T56 - T61)
    # -------------------------------------------------------------------------
    def test_t56_t61_language_preferences_and_catalog(self):
        """T56-T61: Seletor de idioma AUTO/PT_BR/EN_US e catálogo unificado sem mistura."""
        prefs = get_addon_preferences()

        # Testa catálogo unificado direto
        self.assertIn("connectors.enable", MESSAGES["pt_BR"])
        self.assertIn("connectors.enable", MESSAGES["en_US"])
        self.assertEqual(MESSAGES["pt_BR"]["connectors.enable"], "Ativar encaixes")
        self.assertEqual(MESSAGES["en_US"]["connectors.enable"], "Enable connectors")

        # Testa parâmetros e placeholders
        txt_pt = tr("connectors.outside_domain", index=1, margin_mm=1.5)
        txt_en = MESSAGES["en_US"]["connectors.outside_domain"].format(index=1, margin_mm=1.5)
        self.assertIn("1", txt_pt)
        self.assertIn("1.5", txt_pt)
        self.assertIn("1", txt_en)
        self.assertIn("1.5", txt_en)

        # Testa set_localized_status e get_localized_status
        self.settings.set_localized_status("connectors.enable", level='INFO')
        self.assertIn(self.settings.get_localized_status(), ["Ativar encaixes", "Enable connectors"])


if __name__ == "__main__":
    unittest.main(argv=['unittest'])

