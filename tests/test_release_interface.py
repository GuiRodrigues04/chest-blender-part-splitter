"""Release regressions A04/A05/A06 and structured R18 presentation."""
import importlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import bpy
import bmesh
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
addon = importlib.import_module(root.name)
ui = importlib.import_module(root.name + '.src.ui')
gpu = importlib.import_module(root.name + '.src.gpu_drawing')
gm = importlib.import_module(root.name + '.src.geometry_material')
tr = importlib.import_module(root.name + '.src.translations')
errors = importlib.import_module(root.name + '.src.localized_errors')
fingerprints = importlib.import_module(root.name + '.src.cache_fingerprint')
addon.register()


class InterfaceRegressions(unittest.TestCase):
    def setUp(self):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        self.obj = bpy.context.object
        self.obj.data.polygons[0].material_index = 1
        bpy.context.view_layer.update()
        ui._CACHED_UI_MAT_KEY = None
        gpu.clear_cut_line_cache()

    def test_material_assignment_invalidates(self):
        regions, _ = ui.get_cached_material_ui_analysis(self.obj, 1, 0)
        self.assertEqual(regions[0]['face_count'], 1)
        self.obj.data.polygons[1].material_index = 1
        bpy.context.view_layer.update()
        current, _ = ui.get_cached_material_ui_analysis(self.obj, 1, 0)
        self.assertEqual(sum(r['face_count'] for r in current), 2)
        self.assertIsNot(current, regions)
        for face in self.obj.data.polygons:
            face.material_index = 0
        bpy.context.view_layer.update()
        removed, analysis = ui.get_cached_material_ui_analysis(self.obj, 1, 0)
        self.assertEqual(removed, [])
        self.assertFalse(analysis['valid'])

    def test_material_geometry_transform_and_units_invalidate(self):
        with patch.object(gm, 'analyze_material_structure', wraps=gm.analyze_material_structure) as analyze:
            ui.get_cached_material_ui_analysis(self.obj, 1, 0)
            ui.get_cached_material_ui_analysis(self.obj, 1, 0)
            self.assertEqual(analyze.call_count, 1)
            self.obj.data.vertices[0].co.x += .25
            self.obj.data.update()
            bpy.context.view_layer.update()
            ui.get_cached_material_ui_analysis(self.obj, 1, 0)
            self.obj.matrix_world.translation.x += .5
            ui.get_cached_material_ui_analysis(self.obj, 1, 0)
            previous = bpy.context.scene.unit_settings.scale_length
            try:
                bpy.context.scene.unit_settings.scale_length = previous * .5
                ui.get_cached_material_ui_analysis(self.obj, 1, 0)
            finally:
                bpy.context.scene.unit_settings.scale_length = previous
            self.assertEqual(analyze.call_count, 4)

    def test_cut_contour_changes_after_vertex_edit(self):
        args = (self.obj, self.obj.matrix_world, Vector((0, 0, 0)), Vector((0, 0, 1)))
        with patch.object(gpu, '_compute_cut_line_segments', wraps=gpu._compute_cut_line_segments) as compute:
            before = [tuple(p) for p in gpu._get_cached_cut_line_segments(*args)]
            gpu._get_cached_cut_line_segments(*args)
            self.assertEqual(compute.call_count, 1)
            for v in self.obj.data.vertices:
                v.co.x *= 2
            self.obj.data.update()
            bpy.context.view_layer.update()
            after = [tuple(p) for p in gpu._get_cached_cut_line_segments(*args)]
            self.assertEqual(compute.call_count, 2)
            self.assertNotEqual(before, after)

    def test_unchanged_draws_never_rescan_mesh(self):
        fingerprints.clear_geometry_fingerprints()
        with patch.object(fingerprints, 'mesh_geometry_fingerprint', wraps=fingerprints.mesh_geometry_fingerprint) as scan:
            for _ in range(20):
                ui.get_cached_material_ui_analysis(self.obj, 1, 0)
            self.assertEqual(scan.call_count, 1)
            self.obj.data.polygons[1].material_index = 1
            bpy.context.view_layer.update()
            ui.get_cached_material_ui_analysis(self.obj, 1, 0)
            self.assertEqual(scan.call_count, 2)

    def test_live_edit_analysis_does_not_write_datablocks(self):
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bm = bmesh.from_edit_mesh(self.obj.data)
            bm.faces.ensure_lookup_table()
            regions, _ = ui.get_cached_material_ui_analysis(self.obj, 1, 0)
            self.assertEqual(sum(r['face_count'] for r in regions), 1)
            bm.faces[1].material_index = 1
            bm.verts.ensure_lookup_table()
            bm.verts[0].co.x += .25
            bmesh.update_edit_mesh(self.obj.data)
            bpy.context.view_layer.update()
            def forbidden_write():
                raise AssertionError('draw must not write')
            readonly = SimpleNamespace(data=self.obj.data, mode='EDIT', type='MESH',
                                       matrix_world=self.obj.matrix_world,
                                       as_pointer=self.obj.as_pointer,
                                       update_from_editmode=forbidden_write)
            counts = (len(bpy.data.meshes), len(bpy.data.objects))
            current, analysis = ui.get_cached_material_ui_analysis(readonly, 1, 0)
            self.assertEqual(counts, (len(bpy.data.meshes), len(bpy.data.objects)))
            self.assertEqual(sum(r['face_count'] for r in current), 2)
            self.assertIsNot(regions, current)
            self.assertEqual(bm.faces[1].material_index, 1)
            before = analysis['centroid_world'].copy()
            bm.faces[0].verts[0].co += bm.faces[0].normal * .125
            bmesh.update_edit_mesh(self.obj.data)
            bpy.context.view_layer.update()
            _, edited = ui.get_cached_material_ui_analysis(readonly, 1, 0)
            self.assertGreater((edited['centroid_world'] - before).length, .001)
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

    def test_fingerprint_compact_and_exact_for_connectivity_and_coordinates(self):
        mesh = self.obj.data
        first = fingerprints.mesh_geometry_fingerprint(mesh)
        self.assertIsInstance(first[1], bytes)
        self.assertEqual(len(first[1]), 20)
        mesh.vertices[0].co.x += .000001
        second = fingerprints.mesh_geometry_fingerprint(mesh)
        self.assertNotEqual(first, second)
        vertices = [tuple(v.co) for v in mesh.vertices]
        polygons = [tuple(p.vertices) for p in mesh.polygons]
        polygons[0] = tuple(reversed(polygons[0]))
        counts = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))
        mesh.clear_geometry()
        mesh.from_pydata(vertices, [], polygons)
        self.assertEqual(counts, (len(mesh.vertices), len(mesh.edges), len(mesh.polygons)))
        self.assertNotEqual(second, fingerprints.mesh_geometry_fingerprint(mesh))

    def test_help_topics_passed_to_operator(self):
        for topic in tr.HELP_TOPICS:
            op = SimpleNamespace(topic='')
            layout = SimpleNamespace(row=lambda **kw: SimpleNamespace(operator=lambda *a, **kw: op))
            ui.draw_help_button(layout, topic)
            self.assertEqual(op.topic, topic)
            self.assertTrue(tr.get_help_popup_content(op.topic)[1])

    def test_nested_error_survives_language_switch_and_json(self):
        reason = errors.LocalizedGeometryError('geometry.degenerate_faces', part='Parte A', count=3)
        failure = errors.LocalizedGeometryError('geometry.validation_failed', reason=errors.error_payload(reason))
        settings = bpy.context.scene.chest_splitter
        with patch.object(tr, 'get_addon_locale', return_value='en_US'):
            settings.set_localized_status('preview.failed_preserved', 'ERROR', reason=errors.error_payload(failure))
            text = settings.get_localized_status()
            self.assertIn('zero area', text)
            self.assertNotIn('possui', text)
            self.assertIn('Part A:', text)
            self.assertNotIn('Parte A', text)
            self.assertIn('previous preview was preserved', text)
        with patch.object(tr, 'get_addon_locale', return_value='pt_BR'):
            self.assertIn('área nula', settings.get_localized_status())
        encoded = json.dumps(errors.error_payload(failure))
        with patch.object(tr, 'get_addon_locale', return_value='en_US'):
            self.assertEqual(tr.localize_text(encoded), str(failure))
            for code in ('preview.failed', 'export.failed'):
                settings.set_localized_status(code, 'ERROR', reason=errors.error_payload(failure))
                self.assertIn('zero area', settings.get_localized_status())

    def test_priority_templates_and_diagnostic_are_bilingual(self):
        cases = [
            ('geometry.non_planar', dict(deviation=10.8, limit=.15), '10.80'),
            ('geometry.wall_thickness', dict(depth=5., available=2.), '2.00'),
            ('geometry.clearance_excessive', {}, 'clearance'),
            ('diagnostic.protrusion', dict(height=5.94), '5.94'),
            ('diagnostic.non_planar_protrusion', dict(deviation=5.94), '5.94'),
            ('diagnostic.planar_region', dict(height=.01), '0.01'),
        ]
        for key, params, expected in cases:
            encoded = json.dumps(errors.message_payload(key, **params))
            with patch.object(tr, 'get_addon_locale', return_value='en_US'):
                english = tr.localize_text(encoded)
                self.assertIn(expected, english)
                self.assertNotIn('{', english)
                self.assertNotIn('Saliência', english)
            with patch.object(tr, 'get_addon_locale', return_value='pt_BR'):
                self.assertNotEqual(english, tr.localize_text(encoded))
        with patch.object(tr, 'get_addon_locale', return_value='en_US'):
            self.assertEqual(errors.render_message('Erro Critico'), 'Erro Critico')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InterfaceRegressions)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
