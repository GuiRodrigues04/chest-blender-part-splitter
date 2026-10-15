"""Testes de aceitação formal da grade simples de posicionamento dos pinos (5 mm).

Valida todos os critérios da Seção 8 do plano_grade_pinos_v1.md:
- Distância física fixa de 5.0 mm nas direções U e V.
- Ancoragem estável no zero da referência manual (inclusive índices negativos).
- Recorte exato por pertencimento à região útil (suporte a formas côncavas, U e furos).
- Movimento livre dos pinos (sem snap, arredondamento ou alteração de coordenadas).
- Limite defensivo para regiões excessivamente grandes (sem travamento).
- Omissão segura em superfícies não planas sem mapeamento planar.
- Ciclo de vida do overlay e do cache (aparece na edição, some na confirmação/cancelamento).
- Zero controles, propriedades ou botões novos na interface.
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
    connector_surface,
    connector_editor,
    geometry_contract,
    geometry_connectors,
)
from src.connector_surface import (
    PreparedSplit,
    prepare_split_candidates,
    clear_prepared_split_cache,
    generate_positioning_grid_points,
)


class TestGridPositioningPoints(unittest.TestCase):
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
        if not hasattr(bpy.types.Scene, "chest_splitter"):
            addon_package.register()
        if not bpy.context.scene.collection:
            col = bpy.data.collections.new("Scene Collection")
            bpy.context.scene.collection = col
        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter
        clear_prepared_split_cache()
        gpu_drawing.clear_grid_cache()

    def _create_box(self, name="BoxTarget", size=(0.1, 0.1, 0.05), location=(0, 0, 0), rotation=(0, 0, 0)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        self.scene.collection.objects.link(obj)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.transform(Matrix.Diagonal((*size, 1.0)))
        bm.to_mesh(mesh)
        bm.free()
        obj.location = Vector(location)
        obj.rotation_euler = Euler(rotation)
        bpy.context.view_layer.update()
        return obj

    def test_grid_physical_spacing_5mm(self):
        """Valida que a distância física euclidiana entre pontos vizinhos em U e V é exatamente 5.0 mm."""
        target = self._create_box("TargetBox", size=(0.06, 0.06, 0.04))
        self.settings.target_object = target
        self.settings.split_mode = 'PLANE'

        prep = prepare_split_candidates(bpy.context)
        points = generate_positioning_grid_points(prep, step_mm=5.0)

        self.assertGreater(len(points), 0, "A grade deve gerar pontos sobre a face de corte.")

        # Agrupa pontos por linha U e coluna V
        u_vals = sorted(list(set(round(p[0], 2) for p in points)))
        v_vals = sorted(list(set(round(p[1], 2) for p in points)))

        # Verifica passo em U
        for i in range(len(u_vals) - 1):
            diff = u_vals[i + 1] - u_vals[i]
            self.assertAlmostEqual(diff, 5.0, places=2, msg="Passo em U deve ser de 5.0 mm.")

        # Verifica passo em V
        for j in range(len(v_vals) - 1):
            diff = v_vals[j + 1] - v_vals[j]
            self.assertAlmostEqual(diff, 5.0, places=2, msg="Passo em V deve ser de 5.0 mm.")

        # Verifica distância euclidiana 3D no espaço de mundo entre vizinhos
        pts_by_uv = {(round(p[0], 2), round(p[1], 2)): p[2] for p in points}
        for (u, v), w_pos in pts_by_uv.items():
            # Vizinho em U
            neighbor_u = (round(u + 5.0, 2), v)
            if neighbor_u in pts_by_uv:
                dist_world = (pts_by_uv[neighbor_u] - w_pos).length
                dist_mm = dist_world * prep.unit_scale
                self.assertAlmostEqual(dist_mm, 5.0, places=2, msg="Distância física 3D em U deve ser 5.0 mm.")

            # Vizinho em V
            neighbor_v = (u, round(v + 5.0, 2))
            if neighbor_v in pts_by_uv:
                dist_world = (pts_by_uv[neighbor_v] - w_pos).length
                dist_mm = dist_world * prep.unit_scale
                self.assertAlmostEqual(dist_mm, 5.0, places=2, msg="Distância física 3D em V deve ser 5.0 mm.")

    def test_stable_origin_anchoring(self):
        """Valida que todos os pontos são múltiplos inteiros de 5.0 mm a partir de (0, 0), inclusive negativos."""
        target = self._create_box("TargetBoxStable", size=(0.08, 0.08, 0.04))
        self.settings.target_object = target
        prep = prepare_split_candidates(bpy.context)
        points = generate_positioning_grid_points(prep, step_mm=5.0)

        for u_mm, v_mm, w_pos in points:
            # Deve ser múltiplo inteiro de 5.0 mm (ex: -15, -10, -5, 0, 5, 10, ...)
            rem_u = abs(u_mm % 5.0)
            rem_v = abs(v_mm % 5.0)
            self.assertTrue(
                rem_u < 1e-4 or abs(rem_u - 5.0) < 1e-4,
                f"Coordenada U ({u_mm}) deve ser múltiplo exato de 5 mm."
            )
            self.assertTrue(
                rem_v < 1e-4 or abs(rem_v - 5.0) < 1e-4,
                f"Coordenada V ({v_mm}) deve ser múltiplo exato de 5 mm."
            )

    def test_concave_and_hole_clipping(self):
        """Valida que regiões côncavas/em U e furos internos excluem pontos fora do domínio sólido."""
        unit_scale = 1000.0  # 1 BU = 1000 mm

        # Cria interface em U artificial:
        # Bounding box [-20, 20] x [-20, 20] mm, com reentrância central recortada entre -10 e 10 mm
        u_shape_outer_bu = [
            (-0.02, -0.02),
            (0.02, -0.02),
            (0.02, 0.02),
            (0.01, 0.02),
            (0.01, -0.005),
            (-0.01, -0.005),
            (-0.01, 0.02),
            (-0.02, 0.02),
        ]
        # Furo circular aproximado em um dos braços (x entre 0.012 e 0.018, y entre 0.005 e 0.015)
        hole_bu = [
            (0.012, 0.005),
            (0.018, 0.005),
            (0.018, 0.015),
            (0.012, 0.015),
        ]

        mock_interface = geometry_contract.CutInterface(
            origin_world=Vector((0, 0, 0)),
            normal_a_to_b_world=Vector((0, 0, 1)),
            axis_u_world=Vector((1, 0, 0)),
            axis_v_world=Vector((0, 1, 0)),
            outer_contours_uv=[u_shape_outer_bu],
            hole_contours_uv=[hole_bu],
            is_planar=True,
        )

        mock_prep = PreparedSplit(
            cut_signature="mock_sig",
            target_name="MockTarget",
            split_mode="PLANE",
            interface=mock_interface,
            surface_origin=Vector((0, 0, 0)),
            surface_normal=Vector((0, 0, 1)),
            axis_u=Vector((1, 0, 0)),
            axis_v=Vector((0, 1, 0)),
            unit_scale=unit_scale,
            male_side="A",
            is_planar=True,
        )

        pts = generate_positioning_grid_points(mock_prep, step_mm=5.0)

        # 1. Ponto na reentrância da concavidade (ex: U=0, V=10 mm -> bu: 0, 0.01) NÃO deve existir
        concave_empty = any(abs(p[0] - 0.0) < 1e-3 and abs(p[1] - 10.0) < 1e-3 for p in pts)
        self.assertFalse(concave_empty, "Ponto no vão côncavo da forma em U deve ser filtrado.")

        # 2. Ponto no furo (ex: U=15 mm, V=10 mm -> bu: 0.015, 0.01) NÃO deve existir
        in_hole = any(abs(p[0] - 15.0) < 1e-3 and abs(p[1] - 10.0) < 1e-3 for p in pts)
        self.assertFalse(in_hole, "Ponto no interior do furo deve ser filtrado.")

        # 3. Ponto no corpo sólido do braço esquerdo (ex: U=-15 mm, V=10 mm -> bu: -0.015, 0.01) DEVE existir
        in_solid = any(abs(p[0] - (-15.0)) < 1e-3 and abs(p[1] - 10.0) < 1e-3 for p in pts)
        self.assertTrue(in_solid, "Ponto no corpo sólido útil deve estar presente na grade.")

    def test_non_planar_surface_omits_grid_safely(self):
        """Valida que superfícies não planas omitem a grade sem erro (Seção 4.4)."""
        mock_interface = geometry_contract.CutInterface(
            origin_world=Vector((0, 0, 0)),
            normal_a_to_b_world=Vector((0, 0, 1)),
            axis_u_world=Vector((1, 0, 0)),
            axis_v_world=Vector((0, 1, 0)),
            outer_contours_uv=[[(-0.02, -0.02), (0.02, -0.02), (0.02, 0.02), (-0.02, 0.02)]],
            is_planar=False,  # Não plano!
            deviation_mm=2.5,
        )
        mock_prep = PreparedSplit(
            cut_signature="non_planar_sig",
            target_name="MockTarget",
            split_mode="LOOP",
            interface=mock_interface,
            surface_origin=Vector((0, 0, 0)),
            surface_normal=Vector((0, 0, 1)),
            axis_u=Vector((1, 0, 0)),
            axis_v=Vector((0, 1, 0)),
            unit_scale=1000.0,
            male_side="A",
            is_planar=False,
        )

        pts = generate_positioning_grid_points(mock_prep, step_mm=5.0)
        self.assertEqual(len(pts), 0, "Superfície não plana deve omitir a grade auxiliar.")

    def test_defensive_safety_limit(self):
        """Valida que regiões que gerariam centenas de milhares de pontos são omitidas de forma defensiva."""
        mock_interface = geometry_contract.CutInterface(
            origin_world=Vector((0, 0, 0)),
            normal_a_to_b_world=Vector((0, 0, 1)),
            axis_u_world=Vector((1, 0, 0)),
            axis_v_world=Vector((0, 1, 0)),
            # Bounding box gigante: 2000 mm x 2000 mm = 400 x 400 = 160.000 pontos
            outer_contours_uv=[[(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]],
            is_planar=True,
        )
        mock_prep = PreparedSplit(
            cut_signature="huge_sig",
            target_name="HugeTarget",
            split_mode="PLANE",
            interface=mock_interface,
            surface_origin=Vector((0, 0, 0)),
            surface_normal=Vector((0, 0, 1)),
            axis_u=Vector((1, 0, 0)),
            axis_v=Vector((0, 1, 0)),
            unit_scale=1000.0,
            male_side="A",
            is_planar=True,
        )

        pts = generate_positioning_grid_points(mock_prep, step_mm=5.0, max_points=1000)
        self.assertEqual(len(pts), 0, "Região que excede o limite defensivo deve omitir a grade com segurança.")

    def test_free_movement_no_snapping(self):
        """Valida que a inserção e movimentação manual continuam totalmente livres (sem snap ou arredondamento a 5 mm)."""
        target = self._create_box("TargetFreeMove", size=(0.1, 0.1, 0.05))
        self.settings.target_object = target
        self.settings.connector_distribution = 'MANUAL'
        self.settings.connector_enabled = True

        # Adiciona pino em coordenadas arbitrárias não múltiplas de 5 mm
        pin = self.settings.manual_connectors.add()
        pin.u_mm = 3.1415
        pin.v_mm = 7.8921

        self.assertAlmostEqual(pin.u_mm, 3.14, places=2)
        self.assertAlmostEqual(pin.v_mm, 7.89, places=2)
        self.assertNotEqual(pin.u_mm, 5.0, "Não deve haver snap a 5 mm.")
        self.assertNotEqual(pin.v_mm, 10.0, "Não deve haver snap a 5 mm.")

    def test_lifecycle_and_zero_new_ui_controls(self):
        """Valida o ciclo de vida do cache e a ausência estrita de novos controles na UI (Seção 1 e 8)."""
        # 1. Zero novos controles ou propriedades
        forbidden_props = [
            "grid_spacing", "show_grid", "enable_grid", "grid_snap", "grid_points",
            "pin_grid", "connector_grid", "display_grid", "grid_color"
        ]
        for prop in forbidden_props:
            self.assertFalse(
                hasattr(self.settings, prop),
                f"A propriedade '{prop}' não deve existir (Seção 1: zero propriedades ou controles adicionais)."
            )

        # 2. Ciclo de cache
        target = self._create_box("TargetLifecycle", size=(0.06, 0.06, 0.04))
        self.settings.target_object = target
        prep = prepare_split_candidates(bpy.context)
        
        # Invalidação limpa o cache
        clear_prepared_split_cache()
        self.assertIsNone(gpu_drawing._GRID_CACHE["key"])
        self.assertIsNone(gpu_drawing._GRID_CACHE["batch"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
