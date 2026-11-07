"""A01–A03 regressions. Run with Blender --background --factory-startup --python this_file."""
import importlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
addon = importlib.import_module(ROOT.name)
ops = importlib.import_module(ROOT.name + '.src.operators')
cs = importlib.import_module(ROOT.name + '.src.connector_surface')
state = importlib.import_module(ROOT.name + '.src.input_state')
life = importlib.import_module(ROOT.name + '.src.lifecycle')
translations = importlib.import_module(ROOT.name + '.src.translations')
errors = importlib.import_module(ROOT.name + '.src.localized_errors')
addon.register()


def box(name='body'):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=40)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    return obj


class ReleaseStateTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        self.s = bpy.context.scene.chest_splitter
        self.s.connector_enabled = False
        self.s.split_mode = 'PLANE'
        bpy.context.scene.unit_settings.scale_length = .001
        self.target = box()
        self.s.target_object = self.target
        cs.clear_prepared_split_cache()
        self.reporter = SimpleNamespace(report=lambda *_: None)

    def preview(self):
        self.assertEqual(ops.CHEST_OT_splitter_generate_preview.execute(self.reporter, bpy.context), {'FINISHED'})

    def assert_validation_failure_releases_resources(self, execute):
        original_new = bmesh.new
        tracked = []

        class TrackedBMesh:
            def __init__(self, bm):
                self.bm = bm
                self.freed = False
                self.source_mesh = None

            def from_mesh(self, mesh):
                self.source_mesh = mesh
                self.bm.from_mesh(mesh)

            def free(self):
                self.freed = True
                self.bm.free()

            def __getattr__(self, name):
                return getattr(self.bm, name)

        def tracked_new():
            bm = TrackedBMesh(original_new())
            tracked.append(bm)
            return bm

        with patch.object(ops.bmesh, 'new', side_effect=tracked_new), \
                patch.object(ops, 'validate_printable_mesh', side_effect=RuntimeError('injected validation failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected validation failure'):
                execute()

        self.assertEqual(len(tracked), 1)
        self.assertTrue(tracked[0].freed)
        evaluated_mesh = tracked[0].source_mesh
        with self.assertRaises(ReferenceError):
            len(evaluated_mesh.vertices)

    def test_commit_validation_failure_releases_evaluated_mesh_and_bmesh(self):
        self.preview()
        self.assert_validation_failure_releases_resources(
            lambda: ops.CHEST_OT_splitter_commit_parts.execute(self.reporter, bpy.context))

    def test_export_validation_failure_releases_evaluated_mesh_and_bmesh(self):
        self.preview()
        self.assertEqual(ops.CHEST_OT_splitter_commit_parts.execute(self.reporter, bpy.context), {'FINISHED'})
        for part in ops.get_current_session_parts(bpy.context.scene):
            part.modifiers.new('evaluated export fixture', 'DISPLACE')
        bpy.context.view_layer.update()
        self.s.export_format = 'STL_PARTS'
        with tempfile.TemporaryDirectory() as directory:
            self.s.export_directory = directory
            self.assert_validation_failure_releases_resources(
                lambda: ops.CHEST_OT_splitter_export_parts.execute(self.reporter, bpy.context))

    def test_stale_invalid_and_missing_signature_rejected_before_writing(self):
        self.preview()
        self.s.plane_offset_mm = 3
        self.assertEqual(self.s.session_status, 'PREVIEW_STALE')
        with tempfile.TemporaryDirectory() as directory:
            self.s.export_directory = directory
            for status in ('PREVIEW_STALE', 'PREVIEW_INVALID', 'PREVIEW_VALID'):
                with self.subTest(status=status):
                    self.s.session_status = status
                    self.assertFalse(ops.can_export_current_parts(bpy.context))
                    self.assertFalse(bpy.ops.chest.splitter_export_parts.poll())
                    self.assertEqual(ops.CHEST_OT_splitter_export_parts.execute(self.reporter, bpy.context), {'CANCELLED'})
                    self.assertEqual(list(Path(directory).iterdir()), [])
            self.s.plane_offset_mm = 0
            self.s.session_status = 'PREVIEW_VALID'
            self.s.session_input_signature = ''
            self.assertFalse(ops.can_export_current_parts(bpy.context))

    def test_current_and_committed_export_remain_available(self):
        self.preview()
        self.assertTrue(ops.can_export_current_parts(bpy.context))
        # Repainting the panel must reuse its verified gate; execution still
        # performs a fresh verifier and full integrity checks.
        with patch.object(ops, 'compute_session_input_signature', wraps=ops.compute_session_input_signature) as fingerprint:
            for _ in range(5):
                self.assertTrue(ops.can_export_current_parts(bpy.context))
            self.assertEqual(fingerprint.call_count, 0)
            with tempfile.TemporaryDirectory() as directory:
                self.s.export_directory = directory
                self.s.export_format = 'STL_PARTS'
                self.assertEqual(ops.CHEST_OT_splitter_export_parts.execute(self.reporter, bpy.context), {'FINISHED'})
                self.assertGreater(fingerprint.call_count, 0)
        # A same-count geometry edit invalidates the warm gate on the natural
        # Blender update path, regardless of unchanged raw topology counts.
        self.target.data.vertices[0].co.x -= .1
        self.target.data.update()
        bpy.context.view_layer.update()
        self.assertFalse(ops.can_export_current_parts(bpy.context))
        self.preview()
        self.assertEqual(bpy.ops.chest.splitter_commit_parts(), {'FINISHED'})
        self.assertTrue(ops.can_export_current_parts(bpy.context))
        with tempfile.TemporaryDirectory() as directory:
            self.s.export_directory = directory
            self.s.export_format = 'STL_PARTS'
            self.assertEqual(bpy.ops.chest.splitter_export_parts(), {'FINISHED'})
            self.assertEqual(len(list(Path(directory).glob('*.stl'))), 2)

    def check_rollback(self, stage):
        self.preview()
        previous = ops.get_current_session_parts(bpy.context.scene)
        snapshot = [(o, o.name, o.data, o.matrix_world.copy(), [tuple(v.co) for v in o.data.vertices]) for o in previous]
        metrics = (self.s.part_a_volume_mm3, self.s.part_b_volume_mm3, self.s.session_input_signature)
        rec = life.find_operation_record(bpy.context.scene, self.s.session_id)
        records = [(i.obj, i.name, i.role) for i in rec.created_objects]
        self.s.plane_offset_mm = 3

        if stage == 'cut':
            failure = patch.object(ops, 'slice_mesh_by_plane', side_effect=RuntimeError('injected cut failure'))
        elif stage == 'registration':
            original = ops.record_created_object
            def partial_register(*args):
                original(*args)
                raise RuntimeError('injected registration failure')
            failure = patch.object(ops, 'record_created_object', side_effect=partial_register)
        else:
            original = ops.update_preview_positions
            def partial_position(*args):
                original(*args)
                raise RuntimeError('injected positioning failure')
            failure = patch.object(ops, 'update_preview_positions', side_effect=partial_position)
        with failure:
            self.assertEqual(ops.CHEST_OT_splitter_generate_preview.execute(self.reporter, bpy.context), {'CANCELLED'})
        self.assertEqual(self.s.session_status, 'PREVIEW_INVALID')
        self.assertEqual(set(ops.get_current_session_parts(bpy.context.scene)), set(previous))
        for obj, name, mesh, matrix, coords in snapshot:
            self.assertEqual(obj.name, name)
            self.assertEqual(obj.data, mesh)
            self.assertEqual(obj.matrix_world, matrix)
            self.assertEqual([tuple(v.co) for v in obj.data.vertices], coords)
        self.assertEqual([(i.obj, i.name, i.role) for i in rec.created_objects], records)
        self.assertEqual((self.s.part_a_volume_mm3, self.s.part_b_volume_mm3, self.s.session_input_signature), metrics)
        self.assertTrue(self.target.hide_get())
        self.assertFalse(ops.can_export_current_parts(bpy.context))
        self.assertFalse(any(o.name.startswith('_cand') for o in bpy.data.objects))
        self.assertFalse(any(m.name.startswith('_cand') for m in bpy.data.meshes))
        # Recovery must really work, not only leave plausible names in the scene.
        self.assertEqual(bpy.ops.chest.splitter_remove_preview(), {'FINISHED'})
        self.assertFalse(self.target.hide_viewport)
        self.assertFalse(self.target.hide_get())
        self.preview()
        self.assertTrue(ops.can_export_current_parts(bpy.context))

    def test_failure_before_promotion(self):
        self.check_rollback('cut')

    def test_failure_during_registration(self):
        self.check_rollback('registration')

    def test_failure_after_promotion_during_positioning(self):
        self.check_rollback('positioning')

    def test_first_preview_failure_reveals_original(self):
        with patch.object(ops, 'update_preview_positions', side_effect=RuntimeError('injected placement failure')):
            self.assertEqual(ops.CHEST_OT_splitter_generate_preview.execute(self.reporter, bpy.context), {'CANCELLED'})
        self.assertFalse(self.target.hide_viewport)
        self.assertFalse(self.target.hide_get())
        self.assertEqual(ops.get_current_session_parts(bpy.context.scene), [])
        rec = life.find_operation_record(bpy.context.scene, self.s.session_id)
        self.assertEqual(len(rec.created_objects), 0)
        # The stored nested reason must follow a later language switch too.
        failure = errors.LocalizedGeometryError('geometry.degenerate_faces', part='Parte A', count=3)
        with patch.object(ops, 'slice_mesh_by_plane', side_effect=failure):
            self.assertEqual(ops.CHEST_OT_splitter_generate_preview.execute(self.reporter, bpy.context), {'CANCELLED'})
        with patch.object(translations, 'get_addon_locale', return_value='en_US'):
            english = self.s.get_localized_status()
            self.assertIn('3 face(s)', english)
            self.assertIn('Part A', english)
            self.assertNotIn('possui', english)
        with patch.object(translations, 'get_addon_locale', return_value='pt_BR'):
            self.assertIn('possui 3', self.s.get_localized_status())
        self.preview()

    def test_evaluated_cutter_change_invalidates_prepared_split(self):
        cutter = box('cutter')
        cutter.scale = (.6, .6, 1)
        cutter.location.z = 18
        self.s.solid_cutter_object = cutter
        self.s.split_mode = 'SOLID'
        modifier = cutter.modifiers.new('displacement', 'DISPLACE')
        modifier.mid_level, modifier.strength = 0, 0
        bpy.context.view_layer.update()
        before = cs.prepare_split_candidates(bpy.context, force_recompute=True)
        sig_before = state.cut_signature(self.s, self.target, bpy.context.scene)
        modifier.strength = 2
        bpy.context.view_layer.update()
        sig_after = state.cut_signature(self.s, self.target, bpy.context.scene)
        self.assertNotEqual(sig_before, sig_after)
        after = cs.prepare_split_candidates(bpy.context)
        self.assertIsNot(before, after)

    def test_evaluation_failure_never_silently_accepts_raw_fingerprint(self):
        modifier = self.target.modifiers.new('displacement', 'DISPLACE')
        modifier.strength = 1
        self.preview()
        self.assertFalse(self.target.hide_viewport)
        self.assertTrue(self.target.hide_get())
        self.assertTrue(ops.verify_preview_current(bpy.context)[0])
        self.assertTrue(ops.can_export_current_parts(bpy.context))
        self.assertTrue(bpy.ops.chest.splitter_export_parts.poll())
        # An unchanged second generation must evaluate the same modified source.
        volume = self.s.part_sum_volume_mm3
        self.preview()
        self.assertAlmostEqual(self.s.part_sum_volume_mm3, volume, places=5)
        self.assertTrue(ops.verify_preview_current(bpy.context)[0])
        # Saved previews made by the old visibility policy migrate on rebuild.
        self.target.hide_viewport = True
        bpy.context.view_layer.update()
        self.preview()
        self.assertFalse(self.target.hide_viewport)
        self.assertTrue(self.target.hide_get())
        self.assertAlmostEqual(self.s.part_sum_volume_mm3, volume, places=5)
        self.assertTrue(ops.can_export_current_parts(bpy.context))
        with patch.object(state, 'update_evaluated_mesh_hash', side_effect=RuntimeError('evaluation unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'evaluation unavailable'):
                state.cut_signature(self.s, self.target, bpy.context.scene)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseStateTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
