"""Actual Chest regression: retry an invalid EXACT connector result safely."""
from pathlib import Path
import sys
import unittest

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import src
import src.operators as operators
from src.diagnostic import validate_bmesh_mesh_geometry
from src.geometry_material import get_material_regions
from src.operators import get_current_session_parts, verify_preview_current

CHEST_BLEND = Path(
    r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_Chest_Inteira.blend"
)


class ChestConnectorSolverRetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def setUp(self):
        if not CHEST_BLEND.is_file():
            self.skipTest("Chest source BLEND is unavailable")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 1
        with bpy.data.libraries.load(str(CHEST_BLEND), link=False) as (source, target):
            object_name = next(name for name in source.objects if name == "Placa_Chest_Inteira")
            target.objects = [object_name]
        self.target = target.objects[0]
        bpy.context.scene.collection.objects.link(self.target)
        bpy.context.view_layer.objects.active = self.target
        self.target.select_set(True)
        self.settings = bpy.context.scene.chest_splitter
        self.settings.target_object = self.target

    @staticmethod
    def signature(obj):
        return (
            tuple(tuple(vertex.co) for vertex in obj.data.vertices),
            tuple(tuple(poly.vertices) for poly in obj.data.polygons),
            tuple(poly.material_index for poly in obj.data.polygons),
        )

    def capture_material_zero_loop(self):
        bm = bmesh.new()
        bm.from_mesh(self.target.data)
        try:
            region = set(get_material_regions(bm, 0)[0])
        finally:
            bm.free()
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        self.settings.split_mode = 'LOOP'
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bm = bmesh.from_edit_mesh(self.target.data)
        edit_bm.faces.ensure_lookup_table()
        for face in edit_bm.faces:
            face.select_set(face.index in region)
        edit_bm.faces.active = next(face for face in edit_bm.faces if face.select)
        edit_bm.select_flush_mode()
        bmesh.update_edit_mesh(self.target.data)
        self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(), {'FINISHED'})
        self.assertTrue(self.settings.loop_is_captured)
        bpy.ops.object.mode_set(mode='OBJECT')

    def assert_closed_parts(self, parts):
        self.assertEqual(len(parts), 2)
        measured = []
        for part in parts:
            bm = bmesh.new()
            bm.from_mesh(part.data)
            bm.transform(part.matrix_world)
            try:
                report = validate_bmesh_mesh_geometry(bm, 1000)
                self.assertTrue(report['is_valid'], str(report))
                self.assertTrue(report['is_manifold'], str(report))
                self.assertFalse(report['degenerate_faces'], str(report))
                self.assertGreater(abs(bm.calc_volume(signed=True)), 0)
                measured.append(report['volume_mm3'])
            finally:
                bm.free()
        return measured

    def test_material_fdm_auto_shape_retries_exact_as_manifold(self):
        self.capture_material_zero_loop()
        self.settings.split_mode = 'MATERIAL'
        self.settings.material_split_index = 0
        self.settings.material_region_index = 0
        self.settings.material_extraction_mode = 'EXTRUDE'
        self.settings.material_extrude_depth_mm = 2.0
        self.settings.material_interface_mat_mode = 'EXTRACTED'
        self.settings.assembly_clearance_preset = 'FDM'
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'AUTO_SHAPE'
        self.settings.connector_diameter_mm = 1.2
        self.settings.connector_length_mm = 1.5  # Blender clamps this property to its 2 mm minimum.
        self.settings.connector_chamfer_mm = 0.1
        self.settings.connector_edge_margin_mm = 0.4
        self.settings.commit_next_target = 'NONE'
        self.assertAlmostEqual(self.settings.part_clearance_mm, 0.1, places=5)
        # FDM's documented connector-side allowance is 0.15 mm; the part gap
        # itself remains 0.1 mm. Record and assert both effective values.
        self.assertAlmostEqual(self.settings.clearance_per_side_mm, 0.15, places=5)
        self.assertAlmostEqual(self.settings.connector_length_mm, 2.0, places=5)
        self.assertTrue(self.settings.loop_is_captured)
        source_before = self.signature(self.target)

        selected_solvers = []
        original_apply = operators.apply_connectors_boolean

        def observe_solver(*args, **kwargs):
            solver = original_apply(*args, **kwargs)
            selected_solvers.append(solver)
            return solver

        operators.apply_connectors_boolean = observe_solver
        try:
            self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'},
                             self.settings.get_localized_status())
        finally:
            operators.apply_connectors_boolean = original_apply

        self.assertEqual(selected_solvers, ['MANIFOLD'])
        self.assertTrue(self.settings.loop_is_captured)
        self.assertTrue(verify_preview_current(bpy.context)[0])
        preview_parts = get_current_session_parts(bpy.context.scene)
        preview_volumes = self.assert_closed_parts(preview_parts)
        self.assertEqual(self.signature(self.target), source_before)

        self.assertEqual(bpy.ops.chest.splitter_commit_parts(), {'FINISHED'})
        committed_parts = get_current_session_parts(bpy.context.scene)
        committed_volumes = self.assert_closed_parts(committed_parts)
        self.assertEqual(preview_volumes, committed_volumes)
        self.assertEqual(self.signature(self.target), source_before)
        operation_id = self.settings.active_operation_id or self.settings.session_id
        self.assertEqual(bpy.ops.chest.splitter_revert_cut(operation_id=operation_id), {'FINISHED'})
        self.assertEqual(self.signature(self.target), source_before)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
