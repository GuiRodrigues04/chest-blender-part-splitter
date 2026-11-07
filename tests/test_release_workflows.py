"""Full operator workflows on the private red-region fixture.

Run with Blender --background --factory-startup --python-exit-code 1 --python
this_file -- /path/to/integrated/addon. PART_SPLITTER_ROOT is also supported.
Fixture data remains private. These tests do not claim the screenshot's exact
three-face failure parameters or visual approval of the intended closing shape.
"""
import importlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ROOT = Path(os.environ.get('PART_SPLITTER_ROOT') or (arguments[0] if arguments else Path(__file__).resolve().parents[1])).resolve()
FIXTURE = Path(os.environ.get('PART_SPLITTER_RED_FIXTURE', str(ROOT / 'tests/fixtures/red_region_private.json')))
sys.path.insert(0, str(ROOT.parent))
addon = importlib.import_module(ROOT.name)
ops = importlib.import_module(ROOT.name + '.src.operators')
cs = importlib.import_module(ROOT.name + '.src.connector_surface')
diagnostic = importlib.import_module(ROOT.name + '.src.diagnostic')
geometry_loop = importlib.import_module(ROOT.name + '.src.geometry_loop')
geometry_material = importlib.import_module(ROOT.name + '.src.geometry_material')
addon.register()


def mesh_bmesh(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm


def binary_stl_bounds(path):
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0]
    if len(data) != 84 + count * 50:
        raise AssertionError('Expected a complete binary STL')
    coordinates = []
    for index in range(count):
        values = struct.unpack_from('<12fH', data, 84 + index * 50)
        coordinates.extend((values[3:6], values[6:9], values[9:12]))
    return tuple(max(v[axis] for v in coordinates) - min(v[axis] for v in coordinates) for axis in range(3))


class ReleaseWorkflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FIXTURE.is_file():
            raise FileNotFoundError('Private red-region fixture is required: ' + str(FIXTURE))
        cls.items = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def setup_case(self, item, mode, behavior, gap):
        bpy.ops.wm.read_homefile(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 1
        mesh = bpy.data.meshes.new(item['name'])
        mesh.from_pydata(item['vertices'], [], item['faces'])
        mesh.update()
        for name in ('Body', 'Other1', 'Other2', 'Erro Critico'):
            mesh.materials.append(bpy.data.materials.new(name))
        for polygon, material in zip(mesh.polygons, item['materials']):
            polygon.material_index = material
        target = bpy.data.objects.new(item['name'], mesh)
        target.matrix_world = Matrix(item['matrix'])
        bpy.context.scene.collection.objects.link(target)
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        bpy.context.view_layer.update()
        self.target = target
        self.original = (tuple(tuple(v.co) for v in mesh.vertices),
                         tuple(tuple(p.vertices) for p in mesh.polygons),
                         tuple(p.material_index for p in mesh.polygons))
        self.original_materials = tuple(
            (material.name, tuple(material.diffuse_color)) for material in mesh.materials
        )
        self.s = bpy.context.scene.chest_splitter
        self.s.target_object = target
        self.s.split_mode = mode
        self.s.connector_enabled = False
        self.s.commit_next_target = 'NONE'
        self.s.view_mode = 'ASSEMBLED'
        self.s.part_clearance_mm = gap
        self.s.part_clearance_apply_to = 'PART'
        self.s.loop_behavior = behavior if mode == 'LOOP' else 'DETACH'
        self.s.loop_extrude_depth_mm = 5
        self.s.material_extraction_mode = behavior if mode == 'MATERIAL' else 'BASE'
        self.s.material_extrude_depth_mm = 5
        cs.clear_prepared_split_cache()

        # Exercise the real Edit Mode capture and seed validation.
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        for vertex in bm.verts:
            vertex.select = False
        for edge in bm.edges:
            edge.select = False
        for face in bm.faces:
            face.select_set(face.material_index == 3)
        red = [face for face in bm.faces if face.material_index == 3]
        self.assertEqual(len(red), 14)
        bm.faces.active = red[0]
        bmesh.update_edit_mesh(mesh)
        if mode == 'MATERIAL':
            # Pick the intended island through the product operator too.
            self.assertEqual(bpy.ops.chest.splitter_pick_material_region(), {'FINISHED'})
            self.assertEqual(self.s.material_split_index, 3)
        self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(), {'FINISHED'})
        self.assertTrue(self.s.loop_is_captured)
        self.assertEqual(self.s.loop_vertex_count, 22)
        self.assertGreaterEqual(self.s.loop_seed_face_index, 0)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.update()

    def assert_original(self):
        mesh = self.target.data
        self.assertEqual(self.original, (tuple(tuple(v.co) for v in mesh.vertices),
                                        tuple(tuple(p.vertices) for p in mesh.polygons),
                                        tuple(p.material_index for p in mesh.polygons)))

    def assert_preserved_materials(self, parts):
        expected = self.original_materials
        for part in parts:
            actual = tuple((material.name, tuple(material.diffuse_color)) for material in part.data.materials)
            self.assertEqual(actual, expected)
            self.assertTrue(all(0 <= polygon.material_index < len(expected) for polygon in part.data.polygons))

    def assert_preview_rejected(self, expected_message):
        try:
            result = bpy.ops.chest.splitter_generate_preview()
        except RuntimeError as error:
            self.assertIn(expected_message.lower(), str(error).lower())
        else:
            self.assertEqual(result, {'CANCELLED'})
        self.assertEqual(self.s.session_status, 'PREVIEW_INVALID')
        self.assertIn(expected_message.lower(), self.s.get_localized_status().lower())
        self.assert_original()
        self.assertFalse(ops.get_current_session_parts(bpy.context.scene))

    def generate(self):
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'}, self.s.get_localized_status())
        self.assertEqual(self.s.session_status, 'PREVIEW_VALID')
        self.assertTrue(ops.verify_preview_current(bpy.context)[0])
        self.assertTrue(ops.can_export_current_parts(bpy.context))
        parts = ops.get_current_session_parts(bpy.context.scene)
        self.assertEqual(len(parts), 2)
        for part in parts:
            bm = mesh_bmesh(part)
            try:
                report = diagnostic.validate_bmesh_mesh_geometry(bm, 1000)
                self.assertTrue(report['is_valid'], str(report))
                self.assertFalse(report['non_manifold_edges'])
                self.assertGreater(bm.calc_volume(), 0)
            finally:
                bm.free()
        self.assert_original()
        return parts

    def finish_workflow(self, parts):
        self.assertEqual(bpy.ops.chest.splitter_commit_parts(), {'FINISHED'})
        operation_id = self.s.active_operation_id or self.s.session_id
        self.assertTrue(operation_id)
        self.assertTrue(bpy.ops.chest.splitter_export_parts.poll())
        committed = ops.get_current_session_parts(bpy.context.scene)
        expected = []
        for part in committed:
            points = [part.matrix_world @ vertex.co for vertex in part.data.vertices]
            expected.append(tuple((max(v[a] for v in points) - min(v[a] for v in points)) * 1000 for a in range(3)))
        with tempfile.TemporaryDirectory() as directory:
            self.s.export_directory = directory
            self.s.export_format = 'STL_PARTS'
            self.assertEqual(bpy.ops.chest.splitter_export_parts(), {'FINISHED'})
            files = list(Path(directory).glob('*.stl'))
            self.assertEqual(len(files), 2)
            actual = [binary_stl_bounds(path) for path in files]
            for measured in actual:
                closest = min(expected, key=lambda dimensions: sum(abs(a-b) for a,b in zip(measured, dimensions)))
                for a, b in zip(measured, closest):
                    self.assertAlmostEqual(a, b, delta=.01)
                expected.remove(closest)
        self.assertEqual(bpy.ops.chest.splitter_revert_cut(operation_id=operation_id), {'FINISHED'})
        self.assertFalse(self.target.hide_get())
        self.assertFalse(self.target.hide_viewport)
        self.assert_original()
        self.assertFalse(any(o.get('chest_operation_id') == operation_id and o.get('chest_role') in ('COMMITTED_PART', 'ROLE_COMMITTED_PART') for o in bpy.data.objects))

    def check_family(self, mode, behavior, interface_material='SOURCE'):
        for item in self.items:
            for gap in (0, .15):
                with self.subTest(body=item['name'], mode=mode, behavior=behavior, gap=gap, interface_material=interface_material):
                    self.setup_case(item, mode, behavior, gap)
                    self.s.material_interface_mat_mode = interface_material
                    parts = self.generate()
                    total = self.s.part_sum_volume_mm3
                    bm = mesh_bmesh(self.target)
                    original_volume = abs(bm.calc_volume()) * 1000**3
                    bm.free()
                    self.assertLessEqual(total, original_volume * 1.00002)
                    if gap == 0:
                        self.assertAlmostEqual(total, original_volume, delta=original_volume * .00002)
                    # A repeat update must preserve geometry rather than successively trim it.
                    self.generate()
                    self.assertAlmostEqual(self.s.part_sum_volume_mm3, total, delta=max(1e-3, abs(total)*1e-6))
                    self.finish_workflow(parts)

    def test_loop_auto(self):
        self.check_family('LOOP', 'AUTO')

    def test_loop_detach(self):
        for item in self.items:
            with self.subTest(body=item['name'], mode='LOOP', behavior='DETACH'):
                self.setup_case(item, 'LOOP', 'DETACH', 0)
                self.assert_preview_rejected('closing surface crosses existing geometry')

    def test_loop_extrude(self):
        self.check_family('LOOP', 'EXTRUDE')

    def test_loop_auto_uses_selected_depth(self):
        for item in self.items:
            for gap in (0, .15):
                for depth in (1, 2, 5, 10, 15):
                    with self.subTest(body=item['name'], gap=gap, depth_mm=depth):
                        self.setup_case(item, 'LOOP', 'AUTO', gap)
                        self.s.loop_extrude_depth_mm = depth
                        self.assertEqual(self.original, (tuple(tuple(v.co) for v in self.target.data.vertices),
                                                         tuple(tuple(p.vertices) for p in self.target.data.polygons),
                                                         tuple(p.material_index for p in self.target.data.polygons)))
                        analysis = geometry_loop.analyze_loop_region(
                            self.target,
                            [int(i) for i in self.s.loop_vertex_indices.split(',') if i.strip()],
                            self.s.loop_seed_face_index,
                            bpy.context.scene,
                        )
                        if depth > analysis['max_avail_depth_mm'] + 1e-3:
                            self.assert_preview_rejected('wall thickness')
                            continue

                        parts = self.generate()
                        self.assertEqual(self.s.loop_detected_mode, 'EXTRUDE')
                        self.assertEqual(self.s.loop_extrude_depth_mm, depth)
                        self.assert_preserved_materials(parts)
                        source_before = self.original
                        first_volume = self.s.part_sum_volume_mm3
                        signature = [
                            (tuple(tuple(v.co) for v in part.data.vertices),
                             tuple(tuple(p.vertices) for p in part.data.polygons),
                             tuple(p.material_index for p in part.data.polygons))
                            for part in parts
                        ]
                        bm = mesh_bmesh(self.target)
                        try:
                            source_volume = abs(bm.calc_volume()) * 1000**3
                        finally:
                            bm.free()
                        self.assertLessEqual(first_volume, source_volume * 1.00002)
                        if gap == 0:
                            self.assertAlmostEqual(first_volume, source_volume, delta=source_volume * .00002)

                        # The reference plane must remain at the user-selected depth from
                        # the lowest boundary support, including the nonplanar loop vertices.
                        inward = analysis['inward_dir_world'].normalized()
                        outward = -inward
                        center = analysis['centroid_world']
                        coords = analysis['coords_world']
                        support = center + outward * min((point - center).dot(outward) for point in coords)
                        reference = Vector(self.s.loop_interface_origin)
                        measured_depth = (reference - support).dot(inward) * 1000
                        self.assertAlmostEqual(measured_depth, depth, delta=.02)

                        repeated = self.generate()
                        repeated_signature = [
                            (tuple(tuple(v.co) for v in part.data.vertices),
                             tuple(tuple(p.vertices) for p in part.data.polygons),
                             tuple(p.material_index for p in part.data.polygons))
                            for part in repeated
                        ]
                        self.assertEqual(repeated_signature, signature)
                        self.assertAlmostEqual(self.s.part_sum_volume_mm3, first_volume,
                                               delta=max(1e-3, abs(first_volume) * 1e-6))
                        self.assertEqual(self.original, source_before)
                        self.assert_original()

    def test_material_base(self):
        for item in self.items:
            with self.subTest(body=item['name'], mode='MATERIAL', behavior='BASE'):
                self.setup_case(item, 'MATERIAL', 'BASE', 0)
                self.assert_preview_rejected('protrusion base is non-planar')

    def test_material_extrude(self):
        for interface_material in ('SOURCE', 'EXTRACTED'):
            self.check_family('MATERIAL', 'EXTRUDE', interface_material)

    def test_material_extrude_uses_selected_depth_on_warped_surface(self):
        for item in self.items:
            for depth in (1, 2, 5, 10, 15):
                gaps = (0, .15) if depth in (5, 10) else (0,)
                for gap in gaps:
                    with self.subTest(body=item['name'], depth_mm=depth, gap=gap):
                        self.setup_case(item, 'MATERIAL', 'EXTRUDE', gap)
                        self.s.material_extrude_depth_mm = depth
                        analysis = geometry_material.analyze_material_structure(
                            self.target, self.s.material_split_index, self.s.material_region_index
                        )
                        self.assertTrue(analysis['valid'], str(analysis))
                        inward = Vector(analysis['inward_dir_world']).normalized()
                        outward = -inward
                        region_faces = set(analysis['region_face_indices'])
                        source_mesh = self.target.data
                        source_mesh.calc_loop_triangles()
                        source_vertices = [self.target.matrix_world @ vertex.co for vertex in source_mesh.vertices]
                        source_triangles = [tuple(triangle.vertices) for triangle in source_mesh.loop_triangles
                                            if triangle.polygon_index in region_faces]
                        surface_samples = [sum((source_vertices[index] for index in triangle), Vector()) / 3
                                           for triangle in source_triangles]
                        self.assertTrue(surface_samples, 'The selected material island must have visible source triangles')
                        source_tree = BVHTree.FromPolygons(source_vertices, source_triangles)
                        centroid = Vector(analysis['centroid_world'])
                        boundary = [Vector(point) for point in analysis['coords_world']]
                        support = centroid + outward * min((point-centroid).dot(outward) for point in boundary)
                        support_height_mm = max(
                            (source_vertices[index]-support).dot(outward) * 1000
                            for triangle in source_triangles for index in triangle
                        )
                        footprint_samples = [point - outward*(point-support).dot(outward)
                                             for point in surface_samples]

                        parts = self.generate()
                        self.assertEqual(self.s.material_extrude_depth_mm, depth)
                        self.assert_preserved_materials(parts)
                        part_a = next(part for part in parts if part.get('chest_role') == 'PREVIEW_A')
                        part_b = next(part for part in parts if part.get('chest_role') == 'PREVIEW_B')
                        # Preview positioning separates the objects in the viewport.
                        # Use each part's saved assembled transform, which is the frame
                        # occupied by the source region before that display offset.
                        meshes = []
                        for part in (part_a, part_b):
                            mesh = bmesh.new()
                            mesh.from_mesh(part.data)
                            mesh.transform(Matrix(part['chest_assembled_matrix']))
                            mesh.normal_update()
                            meshes.append(mesh)
                        try:
                            trees = [BVHTree.FromBMesh(mesh) for mesh in meshes]
                            epsilon_mm = .005
                            origin_offset = inward * (epsilon_mm / 1000)
                            # Material EXTRUDE uses a planar support frame anchored at the
                            # lowest boundary support, even though the selected red surface
                            # is warped. Ray through the visible source triangles to recover
                            # each sample's local surface height, then measure the output
                            # bottom against the support plane without assuming a flat source.
                            expected_depths = (max(.05, depth-gap), depth)
                            for part_name, tree, expected_base in zip(('A', 'B'), trees, expected_depths):
                                measured = []
                                for sample in footprint_samples:
                                    source_hit = source_tree.ray_cast(
                                        sample + outward * ((support_height_mm + 1.0) / 1000), inward,
                                        (support_height_mm + 1.5) / 1000)
                                    self.assertIsNotNone(source_hit[0], 'Ray must first locate the selected source surface')
                                    point = source_hit[0]
                                    surface_height_mm = (point-support).dot(outward) * 1000
                                    hit = tree.ray_cast(point + origin_offset, inward,
                                                        (depth + gap + surface_height_mm + .5) / 1000)
                                    self.assertIsNotNone(hit[0], f'{part_name}: missing bottom hit from sample {point}')
                                    measured.append((hit[3] * 1000) + epsilon_mm - surface_height_mm)
                                max_error = max(abs(value-expected_base) for value in measured)
                                print('MATERIAL_DEPTH_MEASURE', json.dumps({
                                    'body': item['name'], 'part': part_name, 'depth_mm': depth,
                                    'gap_mm': gap, 'expected_below_support_mm': expected_base,
                                    'measured_min_mm': min(measured), 'measured_max_mm': max(measured),
                                    'max_error_mm': max_error, 'samples': len(measured),
                                }, sort_keys=True))
                                for value in measured:
                                    self.assertAlmostEqual(value, expected_base, delta=.01,
                                                           msg=f'{part_name}: expected {expected_base} mm below the boundary support')
                        finally:
                            for mesh in meshes:
                                mesh.free()

    def test_real_region_late_failure_keeps_previous_preview(self):
        self.setup_case(self.items[0], 'LOOP', 'EXTRUDE', 0)
        previous = self.generate()
        identities = [(o.as_pointer(), o.data.as_pointer(), o.name) for o in previous]
        reporter = SimpleNamespace(report=lambda *_: None)
        with patch.object(ops, 'update_preview_positions', side_effect=RuntimeError('REAL_REGION_LATE_FAILURE')) as placement:
            self.assertEqual(ops.CHEST_OT_splitter_generate_preview.execute(reporter, bpy.context), {'CANCELLED'})
            self.assertTrue(placement.called, 'The injected failure must reach the late placement stage')
        self.assertEqual(self.s.session_status, 'PREVIEW_INVALID')
        self.assertEqual([(o.as_pointer(), o.data.as_pointer(), o.name) for o in ops.get_current_session_parts(bpy.context.scene)], identities)
        self.assertFalse(ops.can_export_current_parts(bpy.context))
        self.assert_original()
        self.generate()

    def test_manual_connector_when_safe_footprint_fits(self):
        fitted = 0
        for item in self.items:
            self.setup_case(item, 'LOOP', 'EXTRUDE', .15)
            self.generate()
            self.s.connector_enabled = True
            self.s.connector_distribution = 'MANUAL'
            self.s.connector_diameter_mm = 2
            self.s.connector_length_mm = 2
            self.s.connector_edge_margin_mm = .5
            self.s.end_clearance_mm = .15
            prepared = cs.prepare_split_candidates(bpy.context)
            connector = self.s.manual_connectors.add()
            connector.connector_id = 'release_safe_pin'
            candidates = [(0, 0)]
            for triangle in prepared.interface.interface_triangles_world:
                center = sum((Vector(v) for v in triangle), Vector()) / 3
                candidates.append(prepared.world_to_uv_mm(center))
            valid = False
            for u, v in candidates:
                connector.u_mm, connector.v_mm = u, v
                if cs.evaluate_connector_specs(prepared, self.s)[0]['is_valid']:
                    valid = True
                    break
            if not valid:
                print('PIN_NO_SAFE_FOOTPRINT', item['name'])
                continue
            self.generate()
            self.finish_workflow(ops.get_current_session_parts(bpy.context.scene))
            fitted += 1
        if not fitted:
            self.skipTest('Neither real-region interface contains the configured 2 mm pin footprint with margin')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseWorkflows)
    selected = os.environ.get('PART_SPLITTER_TEST_METHOD')
    if selected:
        suite = unittest.TestSuite(test for test in suite if selected in test.id())
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
