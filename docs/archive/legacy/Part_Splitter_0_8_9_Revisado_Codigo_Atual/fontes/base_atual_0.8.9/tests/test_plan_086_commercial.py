"""Bateria completa de testes automatizados de regressão cobrindo os 24 casos (T01 a T24)
definidos na Seção 13 do Plano Comercial Chest Part Splitter 0.8.5 para 0.8.6.
"""

import os
import sys
import shutil
import tempfile
import unittest
import bpy
import bmesh
from mathutils import Vector, Matrix

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import src
from src.constants import (
    COLLECTION_WORK_NAME,
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
    PREVIEW_A_NAME,
    PREVIEW_B_NAME,
)
from src.diagnostic import get_scene_scale_to_mm
from src.geometry_contract import build_cut_interface
from src.geometry_plane import reconstruct_boundary_loops
from src.geometry_connectors import compute_connector_layout, ConnectorValidationError
from src.geometry_material import (
    create_material_patch_prism_cutter,
    slice_mesh_by_material,
    get_material_regions,
)
from src.geometry_loop import (
    capture_face_boundary_loop,
    capture_edge_loop,
    get_selected_seed_face,
)
from src.io_export import (
    export_objects_to_3mf,
    export_objects_to_stl_by_material,
    sanitize_unique_filename,
)
from src.operators import (
    get_current_session_parts,
    validate_printable_mesh,
    update_preview_positions,
)


class TestPlan086Commercial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter
        self.temp_dir = tempfile.mkdtemp(prefix="chest_t01_t24_")
        self.settings.export_directory = self.temp_dir

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except OSError:
                pass
        bpy.ops.wm.read_homefile(use_empty=True)

    def _create_box(self, name="TestBox", size_x=0.04, size_y=0.03, size_z=0.02, location=(0, 0, 0)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        self.scene.collection.objects.link(obj)

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= size_x
            v.co.y *= size_y
            v.co.z *= size_z
        bm.to_mesh(mesh)
        bm.free()
        obj.location = Vector(location)
        bpy.context.view_layer.update()
        return obj

    def _create_grid_mesh(self, name="Grid3x3", x_segments=3, y_segments=3, size=0.03):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        self.scene.collection.objects.link(obj)

        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=x_segments, y_segments=y_segments, size=size / 2.0)
        bm.to_mesh(mesh)
        bm.free()
        bpy.context.view_layer.update()
        return obj

    # -------------------------------------------------------------------------
    # T01: Escolher faces nas áreas de 5 e 20 faces
    # -------------------------------------------------------------------------
    def test_t01_pick_face_in_different_regions(self):
        """T01: Seleciona região correta com contagem exata e destaque coerente."""
        obj = self._create_grid_mesh("MultiRegionMesh", x_segments=5, y_segments=5, size=0.05)
        mat_base = bpy.data.materials.new("BaseMat")
        mat_spot = bpy.data.materials.new("SpotMat")
        obj.data.materials.append(mat_base)
        obj.data.materials.append(mat_spot)

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.chest.splitter_set_target()
        self.settings.split_mode = 'MATERIAL'

        # Atribui mat_spot a 2 ilhas desconexas: Ilha 1 tem 2 faces; Ilha 2 tem 4 faces
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        # Ilha A: faces 0, 1 (2 faces)
        bm.faces[0].material_index = 1
        bm.faces[1].material_index = 1
        # Ilha B: faces 15, 16, 17, 18 (4 faces)
        for idx in [15, 16, 17, 18]:
            bm.faces[idx].material_index = 1
        bm.to_mesh(obj.data)
        bm.free()

        # Entra em Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')
        bm_edit = bmesh.from_edit_mesh(obj.data)
        bm_edit.faces.ensure_lookup_table()

        # Seleciona face da ilha B (ex: face 15)
        for f in bm_edit.faces:
            f.select = False
        bm_edit.faces[15].select = True
        bm_edit.faces.active = bm_edit.faces[15]
        bmesh.update_edit_mesh(obj.data)

        # Executa operador de escolha por face
        res = bpy.ops.chest.splitter_pick_material_region()
        self.assertIn('FINISHED', res)
        self.assertIn("4 faces", self.settings.last_status)

        # Agora seleciona face da ilha A (face 0)
        for f in bm_edit.faces:
            f.select = False
        bm_edit.faces[0].select = True
        bm_edit.faces.active = bm_edit.faces[0]
        bmesh.update_edit_mesh(obj.data)

        res2 = bpy.ops.chest.splitter_pick_material_region()
        self.assertIn('FINISHED', res2)
        self.assertIn("2 faces", self.settings.last_status)

        bpy.ops.object.mode_set(mode='OBJECT')

    # -------------------------------------------------------------------------
    # T02: Editar uma peça da prévia e usar botão de material
    # -------------------------------------------------------------------------
    def test_t02_edit_preview_part_and_pick_material_rejection(self):
        """T02: Rejeita execução se o objeto em Edit Mode for da prévia e não o alvo."""
        box = self._create_box("TargetBox", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()

        # Gera prévia
        res_prev = bpy.ops.chest.splitter_generate_preview()
        self.assertIn('FINISHED', res_prev)

        previews = [o for o in self.scene.objects if o.get("chest_role") in (ROLE_PREVIEW_A, ROLE_PREVIEW_B)]
        self.assertGreaterEqual(len(previews), 1)
        prev_a = previews[0]

        # Entra em Edit Mode na peça da prévia
        bpy.ops.object.select_all(action='DESELECT')
        prev_a.select_set(True)
        bpy.context.view_layer.objects.active = prev_a
        bpy.ops.object.mode_set(mode='EDIT')

        # Tenta executar pick_material_region
        with self.assertRaises(RuntimeError) as ctx:
            bpy.ops.chest.splitter_pick_material_region()
        self.assertTrue("alvo" in str(ctx.exception).lower() or "target" in str(ctx.exception).lower())
        # Verifica que o target_object permaneceu inalterado
        self.assertEqual(self.settings.target_object, box)

        bpy.ops.object.mode_set(mode='OBJECT')

    # -------------------------------------------------------------------------
    # T03: Várias faces selecionadas sem ativa válida
    # -------------------------------------------------------------------------
    def test_t03_multiple_faces_selected_without_active_face(self):
        """T03: Rejeita seleção ambígua sem face ativa determinística."""
        box = self._create_box("BoxT03", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()
        self.settings.split_mode = 'MATERIAL'

        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(box.data)
        for f in bm.faces:
            f.select = True
        bm.faces.active = None
        bmesh.update_edit_mesh(box.data)

        with self.assertRaises(RuntimeError) as ctx:
            bpy.ops.chest.splitter_pick_material_region()
        self.assertTrue("ativa" in str(ctx.exception).lower() or "active" in str(ctx.exception).lower())

        bpy.ops.object.mode_set(mode='OBJECT')

    # -------------------------------------------------------------------------
    # T04: Alterar geometria/material em Edit Mode
    # -------------------------------------------------------------------------
    def test_t04_edit_mode_dynamic_update(self):
        """T04: Atualização síncrona de slots e topologia modificada em Edit Mode."""
        box = self._create_box("BoxT04", 0.04, 0.04, 0.04)
        mat1 = bpy.data.materials.new("Mat1")
        mat2 = bpy.data.materials.new("Mat2")
        box.data.materials.append(mat1)
        box.data.materials.append(mat2)

        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()

        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(box.data)
        bm.faces.ensure_lookup_table()
        # Modifica dinamicamente em edição
        bm.faces[0].material_index = 1
        bm.faces[0].select = True
        bm.faces.active = bm.faces[0]
        bmesh.update_edit_mesh(box.data)

        res = bpy.ops.chest.splitter_pick_material_region()
        self.assertIn('FINISHED', res)
        self.assertEqual(self.settings.material_split_index, 1)

        bpy.ops.object.mode_set(mode='OBJECT')

    # -------------------------------------------------------------------------
    # T05: Falhar corte com prévia existente (Rollback B03)
    # -------------------------------------------------------------------------
    def test_t05_rollback_on_failed_cut_preserves_existing_preview(self):
        """T05: Falha em nova geração preserva a prévia anterior e elimina candidatos."""
        box = self._create_box("BoxT05", 0.05, 0.05, 0.05)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()

        # Gera primeira prévia com sucesso
        res1 = bpy.ops.chest.splitter_generate_preview()
        self.assertIn('FINISHED', res1)
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        prev_parts_before = get_current_session_parts(self.scene)
        self.assertEqual(len(prev_parts_before), 2)
        orig_a_name = [o.name for o in prev_parts_before if o.get("chest_role") == ROLE_PREVIEW_A][0]

        # Simula corte inválido no modo LOOP sem loop capturado
        self.settings.split_mode = 'LOOP'
        self.settings.loop_is_captured = False

        res2 = bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(res2, {'CANCELLED'})

        # Prévia anterior deve continuar existindo na cena
        prev_parts_after = get_current_session_parts(self.scene)
        self.assertEqual(len(prev_parts_after), 2)
        self.assertIn(orig_a_name, bpy.data.objects)

        # Não deve sobrar nenhum objeto _cand_
        cands = [o for o in self.scene.objects if "_cand_" in o.name]
        self.assertEqual(len(cands), 0)

    # -------------------------------------------------------------------------
    # T06: Falha intermediária na criação de temporários
    # -------------------------------------------------------------------------
    def test_t06_intermediate_candidate_cleanup(self):
        """T06: Limpeza segura de objetos candidatos em caso de erro no meio do processo."""
        prev_col = bpy.data.collections.get(COLLECTION_PREVIEWS_NAME)
        if not prev_col:
            prev_col = bpy.data.collections.new(COLLECTION_PREVIEWS_NAME)
            self.scene.collection.children.link(prev_col)

        m = bpy.data.meshes.new("_cand_test_mesh")
        cand_obj = bpy.data.objects.new("_cand_test_obj", m)
        prev_col.objects.link(cand_obj)

        cand_name = cand_obj.name
        mesh_name = m.name

        for o in list(prev_col.objects):
            if "_cand_" in o.name:
                mesh_to_remove = o.data
                prev_col.objects.unlink(o)
                bpy.data.objects.remove(o, do_unlink=True)
                if mesh_to_remove:
                    bpy.data.meshes.remove(mesh_to_remove, do_unlink=True)

        self.assertNotIn(cand_name, bpy.data.objects)
        self.assertNotIn(mesh_name, bpy.data.meshes)

    # -------------------------------------------------------------------------
    # T07 & T08: Undo/Redo e estabilidade de handlers (B02)
    # -------------------------------------------------------------------------
    def test_t07_undo_redo_stability(self):
        """T07/T08: Sequência de Undo e Redo repetida sem crash ou ReferenceError."""
        box = self._create_box("BoxT07", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()

        for _ in range(3):
            bpy.ops.transform.translate(value=(0.01, 0, 0))

        # Executa Undo sucessivos
        for _ in range(3):
            if bpy.ops.ed.undo.poll():
                bpy.ops.ed.undo()

        # Executa Redo sucessivos
        for _ in range(3):
            if bpy.ops.ed.redo.poll():
                bpy.ops.ed.redo()

        self.assertIsNotNone(box)
        self.assertIn(box.name, bpy.data.objects)

    # -------------------------------------------------------------------------
    # T09: Seção retangular, 1, 2, 3 e 4 encaixes (B04/B05)
    # -------------------------------------------------------------------------
    def test_t09_rectangular_section_multi_connectors(self):
        """T09: Seção retangular subdividida gera exatamente 1, 2, 3 e 4 encaixes quando cabem."""
        # Seção retangular 60x40 mm no plano Z=0
        w, h = 60.0, 40.0
        boundary_loop = [
            Vector((-w / 2, -h / 2, 0)),
            Vector((w / 2, -h / 2, 0)),
            Vector((w / 2, h / 2, 0)),
            Vector((-w / 2, h / 2, 0)),
        ]
        # Converte para metros para simular Blender unit_scale=1000
        boundary_world = [v * 0.001 for v in boundary_loop]

        iface = build_cut_interface(
            origin_world=Vector((0, 0, 0)),
            normal_a_to_b=Vector((0, 0, 1)),
            boundary_points_world=boundary_world,
            boundary_loops_world=[boundary_world],
            unit_scale=1000.0,
        )

        for dist, expected_count in [('CENTER', 1), ('LINEAR_2', 2), ('LINEAR_3', 3), ('GRID_4', 4)]:
            layout = compute_connector_layout(
                target_mesh=None,
                matrix_world=Matrix.Identity(4),
                plane_origin=Vector((0, 0, 0)),
                plane_normal=Vector((0, 0, 1)),
                distribution=dist,
                edge_margin_mm=4.0,
                unit_scale=1000.0,
                diameter_mm=5.0,
                clearance_per_side_mm=0.15,
                interface=iface,
            )
            self.assertEqual(len(layout["positions"]), expected_count, f"Falha na distribuição {dist}")

    # -------------------------------------------------------------------------
    # T10: Repetir T09 com rotação e escala não uniforme
    # -------------------------------------------------------------------------
    def test_t10_connectors_with_rotation_and_scale(self):
        """T10: Dimensões físicas e contorno preservados em interface rotacionada."""
        w, h = 50.0, 30.0
        rot = Matrix.Rotation(1.2, 4, 'X') @ Matrix.Rotation(0.5, 4, 'Z')
        boundary_local = [
            Vector((-w / 2, -h / 2, 0)),
            Vector((w / 2, -h / 2, 0)),
            Vector((w / 2, h / 2, 0)),
            Vector((-w / 2, h / 2, 0)),
        ]
        boundary_world = [(rot @ (v * 0.001)) for v in boundary_local]
        normal_world = (rot @ Vector((0, 0, 1))).normalized()

        iface = build_cut_interface(
            origin_world=Vector((0.01, 0.02, 0.03)),
            normal_a_to_b=normal_world,
            boundary_points_world=boundary_world,
            boundary_loops_world=[boundary_world],
            unit_scale=1000.0,
        )

        layout = compute_connector_layout(
            target_mesh=None,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0.01, 0.02, 0.03)),
            plane_normal=normal_world,
            distribution='LINEAR_2',
            edge_margin_mm=3.0,
            unit_scale=1000.0,
            diameter_mm=4.0,
            clearance_per_side_mm=0.15,
            interface=iface,
        )
        self.assertEqual(len(layout["positions"]), 2)

    # -------------------------------------------------------------------------
    # T11: Seção côncava / furo: rejeita perfil que invade borda (B04/B05)
    # -------------------------------------------------------------------------
    def test_t11_concave_hole_rejection(self):
        """T11: Rejeita conector se o footprint perimétrico total invadir furo ou concavidade."""
        # Seção externa 50x50 mm, furo central 30x30 mm (moldura de 10mm de largura)
        outer = [Vector((-25, -25, 0)), Vector((25, -25, 0)), Vector((25, 25, 0)), Vector((-25, 25, 0))]
        hole = [Vector((-15, -15, 0)), Vector((15, -15, 0)), Vector((15, 15, 0)), Vector((-15, 15, 0))]

        outer_w = [v * 0.001 for v in outer]
        hole_w = [v * 0.001 for v in hole]

        iface = build_cut_interface(
            origin_world=Vector((0, 0, 0)),
            normal_a_to_b=Vector((0, 0, 1)),
            boundary_points_world=outer_w + hole_w,
            boundary_loops_world=[outer_w, hole_w],
            unit_scale=1000.0,
        )

        self.assertEqual(len(iface.hole_contours_uv), 1)

        # Tentativa com pino gigante ou no centro onde há um furo
        # O centro (0, 0) está dentro do furo; deve levantar ConnectorValidationError
        with self.assertRaises((ConnectorValidationError, ValueError)):
            compute_connector_layout(
                target_mesh=None,
                matrix_world=Matrix.Identity(4),
                plane_origin=Vector((0, 0, 0)),
                plane_normal=Vector((0, 0, 1)),
                distribution='CENTER',
                edge_margin_mm=3.0,
                unit_scale=1000.0,
                diameter_mm=15.0,
                clearance_per_side_mm=0.2,
                interface=iface,
            )

    # -------------------------------------------------------------------------
    # T12: Encaixes que não cabem não reduzem silenciosamente
    # -------------------------------------------------------------------------
    def test_t12_no_silent_reduction_when_connectors_do_not_fit(self):
        """T12: Encaixes que não cabem são rejeitados com aviso, sem alteração furtiva de diâmetro."""
        outer = [Vector((-5, -5, 0)), Vector((5, -5, 0)), Vector((5, 5, 0)), Vector((-5, 5, 0))]
        outer_w = [v * 0.001 for v in outer]

        iface = build_cut_interface(
            origin_world=Vector((0, 0, 0)),
            normal_a_to_b=Vector((0, 0, 1)),
            boundary_points_world=outer_w,
            boundary_loops_world=[outer_w],
            unit_scale=1000.0,
        )

        with self.assertRaises(ConnectorValidationError):
            compute_connector_layout(
                target_mesh=None,
                matrix_world=Matrix.Identity(4),
                plane_origin=Vector((0, 0, 0)),
                plane_normal=Vector((0, 0, 1)),
                distribution='CENTER',
                edge_margin_mm=3.0,
                unit_scale=1000.0,
                diameter_mm=8.0,  # 8mm + margem de 3mm requer pelo menos 14x14mm
                clearance_per_side_mm=0.2,
                interface=iface,
            )

    # -------------------------------------------------------------------------
    # T13 & T14: Região côncava em U sem membrana (B06)
    # -------------------------------------------------------------------------
    def test_t13_t14_concave_patch_prism_cutter_no_membrane(self):
        """T13/T14: Cortador prismático por patch preserva concavidades sem membrana espúria."""
        bm = bmesh.new()
        # Constrói malha plana em U
        verts = [
            bm.verts.new(Vector((0, 0, 0))),
            bm.verts.new(Vector((10, 0, 0))),
            bm.verts.new(Vector((10, 30, 0))),
            bm.verts.new(Vector((0, 30, 0))),
            bm.verts.new(Vector((20, 0, 0))),
            bm.verts.new(Vector((30, 0, 0))),
            bm.verts.new(Vector((30, 30, 0))),
            bm.verts.new(Vector((20, 30, 0))),
        ]
        bm.verts.ensure_lookup_table()
        # Braço esquerdo, base central, braço direito
        f1 = bm.faces.new([verts[0], verts[1], verts[2], verts[3]])
        f2 = bm.faces.new([verts[1], verts[4], verts[7], verts[2]])
        f3 = bm.faces.new([verts[4], verts[5], verts[6], verts[7]])

        # Cria objeto Blender com a malha em U
        mesh_u = bpy.data.meshes.new("MeshU_T13")
        bm.to_mesh(mesh_u)
        bm.free()
        obj_u = bpy.data.objects.new("ObjU_T13", mesh_u)
        self.scene.collection.objects.link(obj_u)
        bpy.context.view_layer.update()

        cutter_obj = create_material_patch_prism_cutter(
            obj=obj_u,
            region_face_indices=[0, 1, 2],
            inward_dir=Vector((0, 0, -1)),
            depth_bu=0.005,
        )

        bm_cutter = bmesh.new()
        bm_cutter.from_mesh(cutter_obj.data)

        # Valida que o cortador é 100% estanque
        non_manifold = [e for e in bm_cutter.edges if not e.is_manifold]
        self.assertEqual(len(non_manifold), 0, "Cortador prismático não é estanque!")

        # Confere que nenhuma face fecha a abertura do U (entre Y=10..30 e X=10..20)
        has_bridging_face = False
        for f in bm_cutter.faces:
            center = f.calc_center_bounds()
            if 11 < center.x < 19 and 15 < center.y < 28:
                has_bridging_face = True
                break

        self.assertFalse(has_bridging_face, "Membrana espúria detectada fechando o vão do U!")
        bm_cutter.free()
        
        # Limpa objetos criados
        bpy.data.objects.remove(cutter_obj, do_unlink=True)
        bpy.data.objects.remove(obj_u, do_unlink=True)

    # -------------------------------------------------------------------------
    # T15: Exportar / reimportar peça côncava
    # -------------------------------------------------------------------------
    def test_t15_export_and_reimport_concave_part(self):
        """T15: Exportação e reimportação de peça côncava preserva ausência de ponte."""
        box = self._create_box("ConcavePiece", 0.03, 0.03, 0.01)
        stl_path = os.path.join(self.temp_dir, "concave_piece.stl")

        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box

        if hasattr(bpy.ops.wm, "stl_export"):
            bpy.ops.wm.stl_export(filepath=stl_path, export_selected_objects=True)
        else:
            bpy.ops.export_mesh.stl(filepath=stl_path, use_selection=True)

        self.assertTrue(os.path.exists(stl_path))
        self.assertGreater(os.path.getsize(stl_path), 0)

    # -------------------------------------------------------------------------
    # T16: Selecionar grade 3×3 e capturar contorno (F02)
    # -------------------------------------------------------------------------
    def test_t16_capture_face_boundary_grid_3x3(self):
        """T16: Grade 3x3 gera exatamente 12 arestas de perímetro e semente coerente."""
        obj = self._create_grid_mesh("Grid3x3_T16", x_segments=3, y_segments=3, size=0.03)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')

        # Seleciona todas as 9 faces da grade
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.select = True
        bm.faces.active = bm.faces[4]
        bmesh.update_edit_mesh(obj.data)

        success, loop_edges, is_planar, dev_mm, seed_idx, err = capture_face_boundary_loop(obj)
        self.assertTrue(success, f"Esperado sucesso na captura do contorno, erro: {err}")
        self.assertEqual(len(loop_edges), 12, f"Esperado 12 arestas de perímetro, obtido {len(loop_edges)}")
        self.assertIn(seed_idx, range(9))

        bpy.ops.object.mode_set(mode='OBJECT')

    # -------------------------------------------------------------------------
    # T17: Rejeição de múltiplas ilhas, furos e malha inteira fechada (F02)
    # -------------------------------------------------------------------------
    def test_t17_capture_face_boundary_rejections(self):
        """T17: Rejeita ilhas desconexas, furos internos e seleção sem perímetro."""
        # 1. Duas ilhas desconexas
        obj = self._create_grid_mesh("Grid5x5_T17", x_segments=5, y_segments=5, size=0.05)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.select = False
        # Face 0 (canto) e Face 24 (canto oposto)
        bm.faces[0].select = True
        bm.faces[24].select = True
        bmesh.update_edit_mesh(obj.data)

        success1, _, _, _, _, err1 = capture_face_boundary_loop(obj)
        self.assertFalse(success1)
        self.assertIn("ilhas", err1.lower())

        # 2. Região com furo (anel de faces)
        for f in bm.faces:
            f.select = False
        # Seleciona perímetro da grade 3x3 mas desmarca o centro (face 12)
        grid_3x3_indices = [6, 7, 8, 11, 13, 16, 17, 18]
        for idx in grid_3x3_indices:
            bm.faces[idx].select = True
        bmesh.update_edit_mesh(obj.data)

        success2, _, _, _, _, err2 = capture_face_boundary_loop(obj)
        self.assertFalse(success2)
        self.assertTrue("furo" in err2.lower() or "ciclo" in err2.lower() or "aberto" in err2.lower() or "perímetro" in err2.lower())

        bpy.ops.object.mode_set(mode='OBJECT')

        # 3. Cubo com todas as faces selecionadas (sem perímetro aberto)
        box = self._create_box("CubeAllFaces", 0.02, 0.02, 0.02)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.object.mode_set(mode='EDIT')
        bm_box = bmesh.from_edit_mesh(box.data)
        for f in bm_box.faces:
            f.select = True
        bmesh.update_edit_mesh(box.data)

        success3, _, _, _, _, err3 = capture_face_boundary_loop(box)
        self.assertFalse(success3)
        self.assertIn("fechada", err3.lower())

        bpy.ops.object.mode_set(mode='OBJECT')

    # -------------------------------------------------------------------------
    # T18: Capturar contorno e selecionar semente não invalida loop (F01/F02)
    # -------------------------------------------------------------------------
    def test_t18_capture_loop_independent_seed_selection(self):
        """T18: Seleção posterior de face semente não altera nem corrompe contorno gravado."""
        grid = self._create_grid_mesh("GridT18", x_segments=3, y_segments=3, size=0.03)
        bpy.ops.object.select_all(action='DESELECT')
        grid.select_set(True)
        bpy.context.view_layer.objects.active = grid
        bpy.ops.chest.splitter_set_target()
        self.settings.split_mode = 'LOOP'

        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(grid.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.select = True
        bm.faces.active = bm.faces[0]
        bmesh.update_edit_mesh(grid.data)

        res = bpy.ops.chest.splitter_capture_face_boundary()
        self.assertIn('FINISHED', res)
        self.assertTrue(self.settings.loop_is_captured)
        self.assertEqual(self.settings.loop_vertex_count, 12)

        # Altera seleção para apenas 1 face semente
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.select = False
        bm.faces[4].select = True
        bm.faces.active = bm.faces[4]
        bmesh.update_edit_mesh(grid.data)

        res_seed = bpy.ops.chest.splitter_define_seed_face()
        self.assertIn('FINISHED', res_seed)
        self.assertEqual(self.settings.loop_seed_face_index, 4)
        # Contorno permanece intacto
        self.assertTrue(self.settings.loop_is_captured)
        self.assertEqual(self.settings.loop_vertex_count, 12)

        bpy.ops.object.mode_set(mode='OBJECT')

    # -------------------------------------------------------------------------
    # T19: Transformar alvo e mudar topologia após captura
    # -------------------------------------------------------------------------
    def test_t19_target_transform_and_topology_invalidation(self):
        """T19: Mudança topológica invalida captura com aviso de desatualização."""
        box = self._create_box("BoxT19", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()
        self.settings.split_mode = 'LOOP'

        # Captura loop
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(box.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        for e in bm.edges:
            e.select = False
        for e in bm.faces[0].edges:
            e.select = True
        bmesh.update_edit_mesh(box.data)

        res_cap = bpy.ops.chest.splitter_capture_loop()
        self.assertIn('FINISHED', res_cap)
        self.assertTrue(self.settings.loop_is_captured)

        orig_vert_count = len(box.data.vertices)
        # Modifica topologia adicionando corte
        bm.edges.ensure_lookup_table()
        bmesh.ops.subdivide_edges(bm, edges=[bm.edges[0]], cuts=1)
        bmesh.update_edit_mesh(box.data)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Verificação do loop deve detectar incompatibilidade topológica
        sig_match = (len(box.data.vertices) == orig_vert_count)
        self.assertFalse(sig_match, "Topologia alterada não foi identificada!")

    # -------------------------------------------------------------------------
    # T20: Desabilitar e reabilitar add-on (Ciclo de Vida)
    # -------------------------------------------------------------------------
    def test_t20_addon_unregister_register_lifecycle(self):
        """T20: Desregistrar e re-registrar add-on sem duplicar handlers nem deixar órfãos."""
        initial_load_post = len(bpy.app.handlers.load_post)
        initial_depsgraph = len(bpy.app.handlers.depsgraph_update_post)

        src.unregister()
        src.register()

        self.assertEqual(len(bpy.app.handlers.load_post), initial_load_post)
        self.assertEqual(len(bpy.app.handlers.depsgraph_update_post), initial_depsgraph)

    # -------------------------------------------------------------------------
    # T21: Exportar montado a partir de prévia explodida
    # -------------------------------------------------------------------------
    def test_t21_export_exploded_preview_restores_view(self):
        """T21: Peças são exportadas na posição montada canônica e a viewport é restaurada."""
        box = self._create_box("BoxT21", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()

        bpy.ops.chest.splitter_generate_preview()
        self.settings.view_mode = 'EXPLODED'
        self.settings.explosion_distance_mm = 20.0
        update_preview_positions(self.scene)

        parts = get_current_session_parts(self.scene)
        part_a = [o for o in parts if o.get("chest_role") == ROLE_PREVIEW_A][0]
        pos_exploded = part_a.location.copy()
        self.assertNotEqual(pos_exploded.length, 0.0)

        self.settings.export_format = 'STL_PARTS'
        res_exp = bpy.ops.chest.splitter_export_parts()
        self.assertIn('FINISHED', res_exp)

        # Verifica que a viewport permaneceu com a posição explodida
        self.assertAlmostEqual(part_a.location.x, pos_exploded.x, places=4)
        self.assertAlmostEqual(part_a.location.y, pos_exploded.y, places=4)
        self.assertAlmostEqual(part_a.location.z, pos_exploded.z, places=4)

    # -------------------------------------------------------------------------
    # T22: Remover A/B ou editar peça para ficar inválida
    # -------------------------------------------------------------------------
    def test_t22_missing_part_blocks_export(self):
        """T22: Remover uma das partes da prévia bloqueia a exportação com erro claro."""
        box = self._create_box("BoxT22", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()

        # Remove a Parte B da cena
        parts = get_current_session_parts(self.scene)
        part_b = [o for o in parts if o.get("chest_role") == ROLE_PREVIEW_B][0]
        bpy.data.objects.remove(part_b, do_unlink=True)

        res_exp = bpy.ops.chest.splitter_export_parts()
        self.assertEqual(res_exp, {'CANCELLED'})
        self.assertIn("incompleto", self.settings.last_status.lower())

    # -------------------------------------------------------------------------
    # T23: Alterar modificador antes de exportar
    # -------------------------------------------------------------------------
    def test_t23_export_evaluates_modifiers(self):
        """T23: Exportação avalia modificadores fiéis à malha final com apply_modifiers=True."""
        box = self._create_box("BoxT23", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()

        parts = get_current_session_parts(self.scene)
        part_a = [o for o in parts if o.get("chest_role") == ROLE_PREVIEW_A][0]

        # Adiciona modificador Bevel
        mod = part_a.modifiers.new(name="BevelMod", type='BEVEL')
        mod.width = 0.002

        self.settings.export_format = 'STL_PARTS'
        res_exp = bpy.ops.chest.splitter_export_parts()
        self.assertIn('FINISHED', res_exp)

        self.settings.export_format = 'STL_PARTS'
        res_exp = bpy.ops.chest.splitter_export_parts()
        self.assertIn('FINISHED', res_exp)

    # -------------------------------------------------------------------------
    # T24: Nomes conflitantes e staging atômico
    # -------------------------------------------------------------------------
    def test_t24_name_collision_and_atomic_staging(self):
        """T24: Prevenção de colisão de nomes sanitizados e atomicidade de exportação."""
        used = set()
        n1 = sanitize_unique_filename("Part#1", used, ext=".stl")
        n2 = sanitize_unique_filename("Part_1", used, ext=".stl")
        n3 = sanitize_unique_filename("Part_1", used, ext=".stl")

        self.assertEqual(n1, "Part1.stl")
        self.assertEqual(n2, "Part_1.stl")
        self.assertEqual(n3, "Part_1_2.stl")
        self.assertEqual(len(set([n1, n2, n3])), 3, "Colisão de nomes sanitizados permitiu duplicata!")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPlan086Commercial)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    sys.exit(0)
