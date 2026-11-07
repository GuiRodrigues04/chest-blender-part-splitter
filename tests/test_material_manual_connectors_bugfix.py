"""Testes de regressão para posicionamento manual de conectores no modo Material.

Garante:
1. get_explosion_display_offset é estritamente zero durante is_editing_connectors = True.
2. iface_tris_world e bvh_tree são gerados para regiões planas de material.
3. Grade de 5 mm e marcadores mantêm-se coplanares à interface sem deslocamento espúrio.
4. Fluxo completo de adicionar pino manual e confirmar prévia no modo Material.
"""

import unittest
import sys
import os

import bpy
import bmesh
from mathutils import Vector

# Garante import do src
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

from src.connector_surface import (
    prepare_split_candidates,
    generate_positioning_grid_points,
    get_explosion_display_offset,
    raycast_connector_surface,
    clear_prepared_split_cache,
)
from src.geometry_material import analyze_material_structure, slice_mesh_by_material
from src.connector_editor import stop_connector_editor
from src.lifecycle import remove_preview


class TestMaterialManualConnectorsBugfix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import src
        src.register()

    @classmethod
    def tearDownClass(cls):
        import src
        src.unregister()

    def setUp(self):
        clear_prepared_split_cache()
        stop_connector_editor(bpy.context.scene)
        self._clean_scene()
        self.settings = bpy.context.scene.chest_splitter
        self.settings.split_mode = 'MATERIAL'
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'MANUAL'
        self.settings.view_mode = 'EXPLODED'
        self.settings.explosion_distance_mm = 30.0

    def tearDown(self):
        stop_connector_editor(bpy.context.scene)
        clear_prepared_split_cache()
        self._clean_scene()

    def _clean_scene(self):
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for m in list(bpy.data.meshes):
            bpy.data.meshes.remove(m, do_unlink=True)
        for mat in list(bpy.data.materials):
            bpy.data.materials.remove(mat, do_unlink=True)

    def _create_material_cube(self):
        """Cria cubo 40x40x40 mm com material base (cinza) e patch superior (verde)."""
        bpy.ops.mesh.primitive_cube_add(size=0.040, location=(0, 0, 0))
        cube = bpy.context.active_object
        cube.name = "CubeMaterialTest"

        mat_body = bpy.data.materials.new(name="MatBody")
        mat_body.diffuse_color = (0.8, 0.8, 0.8, 1.0)
        cube.data.materials.append(mat_body)

        mat_green = bpy.data.materials.new(name="MatGreen")
        mat_green.diffuse_color = (0.0, 1.0, 0.0, 1.0)
        cube.data.materials.append(mat_green)

        # Subdivide face superior para criar um patch no topo
        bm = bmesh.new()
        bm.from_mesh(cube.data)
        top_faces = [f for f in bm.faces if f.normal.z > 0.9]
        res = bmesh.ops.subdivide_edges(
            bm,
            edges=list({e for f in top_faces for e in f.edges}),
            cuts=2,
            use_grid_fill=True,
        )
        # Atribui material 1 a uma face subdividida do topo
        patch_faces = [f for f in bm.faces if f.normal.z > 0.9 and abs(f.calc_center_median().x) < 0.01 and abs(f.calc_center_median().y) < 0.01]
        for pf in patch_faces:
            pf.material_index = 1
        bm.to_mesh(cube.data)
        bm.free()

        self.settings.target_object = cube
        self.settings.material_split_index = 1
        self.settings.material_region_index = 0
        self.settings.material_extrude_depth_mm = 5.0
        return cube

    def test_explosion_display_offset_zero_during_manual_editing(self):
        """Valida que get_explosion_display_offset retorna estritamente zero durante is_editing_connectors = True."""
        self._create_material_cube()
        prep = prepare_split_candidates(bpy.context, force_recompute=True)

        self.settings.is_editing_connectors = True
        offset = get_explosion_display_offset(self.settings, prep)
        self.assertEqual(
            offset, Vector((0.0, 0.0, 0.0)),
            "O deslocamento explodido deve ser (0,0,0) enquanto o usuário edita pinos."
        )

    def test_planar_region_iface_tris_and_bvh_tree_populated(self):
        """Valida que iface_tris_world e bvh_tree são gerados mesmo quando _material_support_frame é None."""
        self._create_material_cube()
        prep = prepare_split_candidates(bpy.context, force_recompute=True)

        self.assertTrue(prep.is_planar, "A região plana deve ter is_planar = True.")
        self.assertGreater(
            len(prep.contact_triangles_world), 0,
            "A interface deve conter triângulos de contato triangulados."
        )
        self.assertIsNotNone(
            prep.bvh_tree,
            "O BVHTree deve ser criado para permitir raycast físico na superfície."
        )

    def test_grid_points_coplanar_and_no_floating(self):
        """Gera a grade de 5 mm e valida que todos os pontos situam-se sobre o plano da interface."""
        self._create_material_cube()
        self.settings.is_editing_connectors = True
        prep = prepare_split_candidates(bpy.context, force_recompute=True)

        grid_pts = generate_positioning_grid_points(prep)
        self.assertGreater(len(grid_pts), 0, "A grade de 5 mm deve gerar pontos dentro do patch.")

        disp_offset = get_explosion_display_offset(self.settings, prep)
        self.assertEqual(disp_offset, Vector((0.0, 0.0, 0.0)))

        # Valida que todos os pontos têm a mesma coordenada Z da interface
        z_expected = prep.surface_origin.z
        for u_mm, v_mm, world_pos in grid_pts:
            self.assertAlmostEqual(
                world_pos.z, z_expected, delta=1e-4,
                msg="Ponto da grade não está no plano de corte da extração."
            )

    def test_material_manual_add_pin_and_confirm_preview(self):
        """Executa o fluxo completo: entrar em edição, adicionar conector manual e gerar prévia."""
        cube = self._create_material_cube()

        # Inicia edição manual
        bpy.ops.chest.splitter_edit_manual_connectors('EXEC_DEFAULT')
        self.assertTrue(self.settings.is_editing_connectors)
        self.assertFalse(cube.hide_viewport)

        # Adiciona pino no centro (0, 0) com tamanho e margem adequados ao patch de teste
        self.settings.connector_diameter_mm = 2.0
        self.settings.connector_edge_margin_mm = 1.0
        self.settings.manual_connectors.clear()
        conn = self.settings.manual_connectors.add()
        conn.connector_id = "pin_mat_0"
        conn.u_mm = 0.0
        conn.v_mm = 0.0
        conn.yaw_deg = 0.0
        self.settings.manual_connector_index = 0

        # Confirma e gera prévia
        res = bpy.ops.chest.splitter_confirm_manual_connectors('EXEC_DEFAULT')
        self.assertEqual(res, {'FINISHED'})
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        preview_objs = [o.name for o in bpy.data.objects if "PREVIEW" in o.name]
        from src.constants import PREVIEW_A_NAME, PREVIEW_B_NAME
        self.assertTrue(any(PREVIEW_A_NAME in o or 'CHEST_SPLITTER_PREVIEW_A' in o for o in preview_objs))
        self.assertTrue(any(PREVIEW_B_NAME in o or 'CHEST_SPLITTER_PREVIEW_B' in o for o in preview_objs))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
