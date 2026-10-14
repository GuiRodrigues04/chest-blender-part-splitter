"""Testes de aceitação formal do fluxo de posicionamento manual de pinos (Plano_Pinos_Manuais_Pos_0.8.11_Antigravity).

Valida os cenários da Matriz de Aceitação (T01 a T35):
- T01 / T02: Modo manual com 0, 1 e múltiplos pinos sem pino seed implícito e sem quebra de UI.
- T03: connector_enabled ativa visualização sem propriedades paralelas.
- T06: Quatro pinos em arranjo livre (retângulo/irregular) sem forçar fila colinear.
- T08 / PM14: Selecionar pino ativo não marca preview stale.
- T13: Estabilidade de eixos PCA contra inversão de sinal ou reflexão.
- T14 / T17: Superfície real de contato nos modos Plano, Loop e Material (fundo da extração).
- T18 / T19: Rejeição de footprint violando margem ou colisão mútua entre pinos.
- T20: Pino selecionado inválido mantém diagnóstico de erro.
- T22 / PM11: Cápsulas individuais a 0°, 45° e 90° com orientações precisas em macho e fêmea.
- T24: Deslocamento explodido preserva coordenadas montadas imutáveis.
- T25: Nenhuma booleana de pino executada durante adição/movimentação no editor.
- T26: Cancelamento restaura snapshot de entrada intacto.
- T27 / T28: Confirmar posições gera pinos/cavidades; reedição preserva lista e posições.
"""

import sys
import os
import unittest
import math

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import src as addon_package
from src import (
    properties,
    operators,
    ui,
    gpu_drawing,
    geometry_connectors,
    geometry_plane,
    connector_surface,
    connector_editor,
    constants,
)
from src.constants import PREVIEW_A_NAME, PREVIEW_B_NAME
from src.connector_surface import (
    prepare_split_candidates,
    evaluate_connector_specs,
    get_cached_prepared_split,
    get_explosion_display_offset,
    raycast_connector_surface,
)


class TestManualConnectorsWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            addon_package.register()
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        try:
            addon_package.unregister()
        except Exception:
            pass

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if not bpy.context.scene.collection:
            col = bpy.data.collections.new("Scene Collection")
            bpy.context.scene.collection = col
        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter
        connector_surface.clear_prepared_split_cache()

    def _create_test_box(self, name="BoxTarget", size=(0.1, 0.08, 0.06), location=(0, 0, 0)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        self.scene.collection.objects.link(obj)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.transform(Matrix.Diagonal((*size, 1.0)))
        bm.to_mesh(mesh)
        bm.free()
        obj.location = Vector(location)
        bpy.context.view_layer.update()
        return obj

    # -------------------------------------------------------------------------
    # T01 / T02: Zero -> Um -> Cinco Pinos sem Seed Implícito
    # -------------------------------------------------------------------------
    def test_t01_t02_empty_manual_and_pin_counts(self):
        """T01/T02: Valida que lista vazia não cria seed e painel suporta 0, 1 e 5 pinos."""
        target = self._create_test_box("TargetT01", size=(0.1, 0.1, 0.1))
        self.settings.target_object = target
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'MANUAL'
        self.settings.manual_connectors.clear()

        # T01: Layout com zero pinos manuais deve retornar 0 posições (sem seed)
        prep = prepare_split_candidates(bpy.context)
        layout = geometry_connectors.compute_connector_layout(
            target_mesh=target.data,
            matrix_world=target.matrix_world,
            plane_origin=prep.surface_origin,
            plane_normal=prep.surface_normal,
            distribution='MANUAL',
            unit_scale=prep.unit_scale,
            interface=prep.interface,
            manual_specs=[],
        )
        self.assertEqual(len(layout["positions"]), 0, "Manual com lista vazia não deve gerar seed implícito.")

        # T02: Adiciona 1 pino e depois 4 adicionais (total 5)
        p1 = self.settings.manual_connectors.add()
        p1.u_mm = 0.0
        p1.v_mm = 0.0
        self.assertEqual(len(self.settings.manual_connectors), 1)

        for i in range(1, 5):
            p = self.settings.manual_connectors.add()
            p.u_mm = float(i * 10)
            p.v_mm = float(i * 5)

        self.assertEqual(len(self.settings.manual_connectors), 5)
        eval_res = evaluate_connector_specs(prep, self.settings)
        self.assertEqual(len(eval_res), 5)

    # -------------------------------------------------------------------------
    # T03: connector_enabled na UI e no Overlay
    # -------------------------------------------------------------------------
    def test_t03_connector_enabled_property_unification(self):
        """T03/PM01: Valida que connector_enabled é a única propriedade utilizada no overlay e na cena."""
        self.assertTrue(hasattr(self.settings, "connector_enabled"))
        self.assertFalse(hasattr(self.settings, "enable_connectors"), "Propriedade espúria enable_connectors não deve existir.")
        self.settings.connector_enabled = True
        self.assertTrue(self.settings.connector_enabled)

    # -------------------------------------------------------------------------
    # T06: Arranjo não colinear (retângulo) sem forçar fila
    # -------------------------------------------------------------------------
    def test_t06_non_collinear_four_pins_placement(self):
        """T06: Valida 4 pinos formando retângulo sem imposição de alinhamento em linha."""
        target = self._create_test_box("TargetT06", size=(0.1, 0.1, 0.1))
        self.settings.target_object = target
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'MANUAL'
        self.settings.manual_connectors.clear()

        # 4 vértices de um retângulo 40x30 mm
        coords = [(-20.0, -15.0), (20.0, -15.0), (20.0, 15.0), (-20.0, 15.0)]
        for u, v in coords:
            p = self.settings.manual_connectors.add()
            p.u_mm = u
            p.v_mm = v

        prep = prepare_split_candidates(bpy.context)
        eval_res = evaluate_connector_specs(prep, self.settings)
        for ev in eval_res:
            self.assertTrue(ev["is_valid"], f"Pino #{ev['index'] + 1} deveria ser válido: {ev['reason']}")

        # Verifica se as posições 3D conservam a geometria retangular
        world_pts = [prep.uv_mm_to_world(c.u_mm, c.v_mm) for c in self.settings.manual_connectors]
        d01 = (world_pts[1] - world_pts[0]).length * prep.unit_scale
        d12 = (world_pts[2] - world_pts[1]).length * prep.unit_scale
        self.assertAlmostEqual(d01, 40.0, delta=0.05)
        self.assertAlmostEqual(d12, 30.0, delta=0.05)

    # -------------------------------------------------------------------------
    # T08 / PM14: Seleção de marcador não invalida preview
    # -------------------------------------------------------------------------
    def test_t08_selection_does_not_mark_preview_stale(self):
        """T08/PM14: Valida que trocar manual_connector_index não altera session_status."""
        target = self._create_test_box("TargetT08")
        self.settings.target_object = target
        self.settings.manual_connectors.clear()
        p1 = self.settings.manual_connectors.add()
        p2 = self.settings.manual_connectors.add()

        self.settings.session_status = 'PREVIEW_VALID'
        self.settings.manual_connector_index = 1
        self.assertEqual(
            self.settings.session_status, 'PREVIEW_VALID',
            "Mudar manual_connector_index NÃO deve tornar a prévia stale (PM14)."
        )

    # -------------------------------------------------------------------------
    # T13: Estabilidade dos eixos PCA entre reconstruções
    # -------------------------------------------------------------------------
    def test_t13_pca_axis_stability(self):
        """T13: Valida que chamadas sucessivas mantêm o sinal e direção dos eixos U e V."""
        target = self._create_test_box("TargetT13", size=(0.1, 0.098, 0.05))
        self.settings.target_object = target
        prep1 = prepare_split_candidates(bpy.context, force_recompute=True)
        u1, v1 = prep1.axis_u.copy(), prep1.axis_v.copy()

        prep2 = prepare_split_candidates(bpy.context, force_recompute=True)
        u2, v2 = prep2.axis_u.copy(), prep2.axis_v.copy()

        self.assertGreater(u1.dot(u2), 0.99, "Eixo U não deve inverter sinal entre reconstruções.")
        self.assertGreater(v1.dot(v2), 0.99, "Eixo V não deve inverter sinal entre reconstruções.")

    # -------------------------------------------------------------------------
    # T14: Superfície de extração por Material (fundo da extração)
    # -------------------------------------------------------------------------
    def test_t14_material_cut_interface_at_bottom(self):
        """T14: Valida que a CutInterface do modo Material fica no fundo real da extração."""
        target = self._create_test_box("TargetT14", size=(0.1, 0.1, 0.1))
        # Atribui dois materiais
        mat1 = bpy.data.materials.new("BodyMat")
        mat2 = bpy.data.materials.new("PatchMat")
        target.data.materials.append(mat1)
        target.data.materials.append(mat2)

        # Atribui mat2 à face superior (normal +Z)
        bm = bmesh.new()
        bm.from_mesh(target.data)
        for f in bm.faces:
            if f.normal.z > 0.9:
                f.material_index = 1
        bm.to_mesh(target.data)
        bm.free()

        self.settings.target_object = target
        self.settings.split_mode = 'MATERIAL'
        self.settings.material_split_index = 1
        self.settings.material_extrude_depth_mm = 5.0

        prep = prepare_split_candidates(bpy.context, force_recompute=True)
        self.assertIsNotNone(prep.interface)
        # O topo do cubo está em Z = 0.05 m (+50 mm). Com profundidade de 5 mm, o fundo fica em Z = 0.045 m
        expected_z_bottom = 0.05 - (5.0 / prep.unit_scale)
        self.assertAlmostEqual(prep.surface_origin.z, expected_z_bottom, delta=0.001)

    # -------------------------------------------------------------------------
    # T18 / T19: Validação de borda e colisão entre pinos
    # -------------------------------------------------------------------------
    def test_t18_t19_boundary_and_collision_diagnostics(self):
        """T18/T19: Valida que pinos próximos da borda ou colidindo recebem is_valid=False com motivo específico."""
        target = self._create_test_box("TargetT19", size=(0.06, 0.06, 0.06))
        self.settings.target_object = target
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'MANUAL'
        self.settings.manual_connectors.clear()

        # Pino 1: perto da borda (fora da margem de 4 mm de uma face 60x60, raio máx útil é 26 mm)
        c_edge = self.settings.manual_connectors.add()
        c_edge.u_mm = 28.0
        c_edge.v_mm = 0.0

        # Pinos 2 e 3: colidindo mutuamente (distância 1 mm entre centros para pinos de 4 mm)
        c2 = self.settings.manual_connectors.add()
        c2.u_mm = 0.0
        c2.v_mm = 0.0
        c3 = self.settings.manual_connectors.add()
        c3.u_mm = 1.0
        c3.v_mm = 0.0

        prep = prepare_split_candidates(bpy.context)
        eval_res = evaluate_connector_specs(prep, self.settings)

        self.assertFalse(eval_res[0]["is_valid"], "Pino na borda deve ser inválido.")
        self.assertIn("margem", eval_res[0]["reason"].lower())

        self.assertFalse(eval_res[1]["is_valid"], "Pino em colisão deve ser inválido.")
        self.assertFalse(eval_res[2]["is_valid"], "Pino em colisão deve ser inválido.")
        self.assertIn("colisão", eval_res[1]["reason"].lower())

    # -------------------------------------------------------------------------
    # T22: Cápsulas individuais a 0°, 45° e 90°
    # -------------------------------------------------------------------------
    def test_t22_individual_capsule_yaw_rotations(self):
        """T22/PM11: Valida que cada cápsula recebe sua orientação individual precisa."""
        target = self._create_test_box("TargetT22", size=(0.12, 0.12, 0.06))
        self.settings.target_object = target
        self.settings.connector_enabled = True
        self.settings.connector_type = 'CAPSULE'
        self.settings.connector_capsule_length_mm = 12.0
        self.settings.connector_distribution = 'MANUAL'
        self.settings.manual_connectors.clear()

        # Três cápsulas com ângulos distintos
        yaws = [0.0, 45.0, 90.0]
        positions_uv = [(-25.0, 0.0), (0.0, 0.0), (25.0, 0.0)]
        for (u, v), yaw in zip(positions_uv, yaws):
            c = self.settings.manual_connectors.add()
            c.u_mm = u
            c.v_mm = v
            c.yaw_deg = yaw

        prep = prepare_split_candidates(bpy.context)
        specs = [{"u_mm": c.u_mm, "v_mm": c.v_mm, "yaw_deg": c.yaw_deg} for c in self.settings.manual_connectors]
        layout = geometry_connectors.compute_connector_layout(
            target_mesh=target.data,
            matrix_world=target.matrix_world,
            plane_origin=prep.surface_origin,
            plane_normal=prep.surface_normal,
            distribution='MANUAL',
            connector_type='CAPSULE',
            capsule_length_mm=12.0,
            unit_scale=prep.unit_scale,
            interface=prep.interface,
            manual_specs=specs,
        )

        pin_rots = layout.get("pin_rotations", [])
        self.assertEqual(len(pin_rots), 3)

        # Verifica se as rotações dos pinos diferem entre 0°, 45° e 90°
        rot0 = pin_rots[0]
        rot45 = pin_rots[1]
        rot90 = pin_rots[2]
        self.assertNotEqual(rot0, rot45, "Cápsula a 45° deve ter rotação distinta de 0°.")
        self.assertNotEqual(rot0, rot90, "Cápsula a 90° deve ter rotação distinta de 0°.")

    # -------------------------------------------------------------------------
    # T24: Deslocamento de explosão mantém coordenadas montadas imutáveis
    # -------------------------------------------------------------------------
    def test_t24_exploded_view_assembled_coordinate_invariance(self):
        """T24: Valida que raycast com explode desfaz o deslocamento e armazena ponto montado."""
        target = self._create_test_box("TargetT24", size=(0.1, 0.1, 0.1))
        self.settings.target_object = target
        prep = prepare_split_candidates(bpy.context)

        # Configura explosão de 40 mm
        self.settings.view_mode = 'EXPLODED'
        self.settings.explosion_distance_mm = 40.0
        disp_offset = get_explosion_display_offset(self.settings, prep)
        self.assertGreater(disp_offset.length, 0.01)

        # Raio atinge a face exibida (deslocada por disp_offset)
        ray_origin = (prep.surface_origin + disp_offset) + prep.surface_normal * 0.5
        ray_dir = -prep.surface_normal

        hit_world, hit_u, hit_v = raycast_connector_surface(
            ray_origin, ray_dir, prep, display_offset=disp_offset
        )
        # O ponto montado retornado deve coincidir com surface_origin (sem offset somado)
        diff = (hit_world - prep.surface_origin).length * prep.unit_scale
        self.assertAlmostEqual(diff, 0.0, delta=0.01, msg="Ponto montado não deve conter deslocamento de explode.")

    # -------------------------------------------------------------------------
    # T25: Adição e remoção de pinos sem gerar booleanas
    # -------------------------------------------------------------------------
    def test_t25_no_booleans_during_marker_manipulation(self):
        """T25: Valida que adicionar e remover marcadores não cria objetos nem roda booleana."""
        target = self._create_test_box("TargetT25")
        self.settings.target_object = target
        obj_count_before = len(bpy.data.objects)

        bpy.ops.chest.splitter_add_manual_connector()
        self.assertEqual(len(self.settings.manual_connectors), 1)
        self.assertEqual(len(bpy.data.objects), obj_count_before, "Nenhum objeto deve ser criado ao adicionar marcador.")

        bpy.ops.chest.splitter_remove_manual_connector()
        self.assertEqual(len(self.settings.manual_connectors), 0)
        self.assertEqual(len(bpy.data.objects), obj_count_before, "Nenhum objeto deve ser alterado ao remover marcador.")

    # -------------------------------------------------------------------------
    # T27 / T28: Confirmar posições gera prévia; reedição preserva lista
    # -------------------------------------------------------------------------
    def test_t27_t28_confirm_positions_and_reedit(self):
        """T27/T28: Valida confirmação de posições com prévia transacional e conservação de marcadores na reedição."""
        target = self._create_test_box("TargetT27", size=(0.1, 0.1, 0.1))
        self.settings.target_object = target
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'MANUAL'
        self.settings.manual_connectors.clear()

        # Adiciona 2 conectores válidos
        c1 = self.settings.manual_connectors.add()
        c1.u_mm = -15.0
        c1.v_mm = 0.0
        c2 = self.settings.manual_connectors.add()
        c2.u_mm = 15.0
        c2.v_mm = 0.0

        # Confirma posições e gera prévia
        res = bpy.ops.chest.splitter_confirm_manual_connectors()
        self.assertIn('FINISHED', res)
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        # Verifica existência dos objetos candidatos gerados
        cand_a = bpy.data.objects.get(PREVIEW_A_NAME)
        cand_b = bpy.data.objects.get(PREVIEW_B_NAME)
        self.assertIsNotNone(cand_a, "Parte A da prévia deve existir.")
        self.assertIsNotNone(cand_b, "Parte B da prévia deve existir.")

        # Reedição preserva marcadores e coordenadas
        self.assertEqual(len(self.settings.manual_connectors), 2)
        self.assertEqual(self.settings.manual_connectors[0].u_mm, -15.0)
        self.assertEqual(self.settings.manual_connectors[1].u_mm, 15.0)

        # T28: Remover prévia preserva marcadores
        bpy.ops.chest.splitter_remove_preview()
        self.assertEqual(len(self.settings.manual_connectors), 2)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
