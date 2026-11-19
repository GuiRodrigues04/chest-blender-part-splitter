"""Release checks for topological depth routing and material cap assignment."""
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import geometry_loop as gl
from src import geometry_material as gm
from src.geometry_clearance import trim_depth_contact
from src.localized_errors import LocalizedGeometryError

FIXTURE = Path(__file__).parent / "fixtures" / "horn_region_private.json"


def make_horn_object(data):
    mesh = bpy.data.meshes.new(data['name'])
    mesh.from_pydata(data['vertices'], [], data['faces'])
    mesh.update()
    for slot in data['material_slots']:
        material = bpy.data.materials.new(slot['name'] or 'Material')
        if slot['color']:
            material.diffuse_color = slot['color']
        mesh.materials.append(material)
    for face, material_index in zip(mesh.polygons, data['materials']):
        face.material_index = material_index
    obj = bpy.data.objects.new(data['name'], mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = Matrix(data['matrix'])
    bpy.context.view_layer.update()
    return obj


def mesh_snapshot(obj):
    return (
        tuple(tuple(v.co) for v in obj.data.vertices),
        tuple(tuple(p.vertices) for p in obj.data.polygons),
        tuple(p.material_index for p in obj.data.polygons),
    )


def face_signature(face):
    return tuple(sorted(tuple(round(float(c), 7) for c in v.co) for v in face.verts))


class ReleaseDepthGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding='utf-8'))
        cls.region = set(cls.data['region_face_indices'])

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 1.0

    def test_depth_clearance_cuts_through_piecewise_exterior_relief(self):
        bm = bmesh.new()
        self.addCleanup(bm.free)

        def square_ring(radius, height):
            return [bm.verts.new((x * radius, y * radius, height))
                    for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

        floor, rim, flat, slope, center = (
            square_ring(radius, height) for radius, height in
            ((4, -2), (4, 0), (3.9, 0), (3.7, .02), (2, .02))
        )
        contacts = [bm.faces.new(floor[::-1])]
        for i in range(4):
            j = (i + 1) % 4
            contacts.append(bm.faces.new((floor[i], floor[j], rim[j], rim[i])))
            for outside, inside in ((rim, flat), (flat, slope), (slope, center)):
                bm.faces.new((outside[i], outside[j], inside[j], inside[i]))
        bm.faces.new(center)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bmesh.ops.triangulate(bm, faces=[face for face in bm.faces if face not in contacts])

        inward = Vector((0, 0, -1))
        for lateral, bottom in ((.5, .5), (.5, 0), (0, .5)):
            with self.subTest(lateral=lateral, bottom=bottom):
                result = trim_depth_contact(
                    bm, contacts, inward, lateral, bottom, 1., Vector(), through_exterior=True)
                try:
                    self.assertTrue(all(edge.is_manifold for edge in result.edges))
                    tree = BVHTree.FromBMesh(result)
                    strip = tree.ray_cast(Vector((3.8, 0, 1)), inward)[0]
                    if lateral:
                        self.assertIsNone(strip, 'The axial ray must miss the entire trimmed strip')
                    else:
                        self.assertAlmostEqual(strip.z, .01, places=5)
                    top = tree.ray_cast(Vector((3.4, 0, 1)), inward)[0]
                    base = tree.ray_cast(Vector((3.4, 0, -3)), -inward)[0]
                    self.assertAlmostEqual(top.z, .02, places=5)
                    self.assertAlmostEqual(base.z, -2 + bottom, places=5)
                finally:
                    result.free()

    def test_auto_retries_collapsed_base_at_configured_finite_depth(self):
        scene = bpy.context.scene
        target = SimpleNamespace(name='Thin relief')
        indices = [0, 1, 2]
        settings = SimpleNamespace(
            loop_seed_face_index=3, loop_behavior='AUTO', loop_detach_add_base=False,
            loop_detach_base_depth_mm=2.0, loop_extrude_depth_mm=5.0, loop_through_cut=True,
            part_clearance_mm=0.1, part_clearance_apply_to='PART',
            part_clearance_bottom_mm=0.15, part_clearance_bottom_enable=True,
        )
        collapsed = LocalizedGeometryError('geometry.loop_closure_collapsed', part='A')
        analysis = {'detected_mode': 'DETACH', 'reason': 'protrusion'}
        with mock.patch.object(gl, 'analyze_loop_region', return_value=analysis), \
             mock.patch.object(gl, 'slice_mesh_by_loop', side_effect=collapsed), \
             mock.patch.object(gl, 'slice_mesh_by_loop_extrude') as depth:
            result = gl.slice_loop_from_settings(target, indices, settings, scene)
            self.assertIs(result, depth.return_value)
            depth.assert_called_once_with(
                target, target.name, indices, settings.loop_seed_face_index, depth_mm=5.0,
                through_cut=False, scene=scene, part_clearance_mm=0.1,
                part_clearance_apply_to='PART', part_clearance_bottom_mm=0.15,
            )
            self.assertEqual(settings.loop_detected_mode, 'EXTRUDE')
            self.assertTrue(gl.loop_prefers_finite_depth(settings.loop_auto_reason))

            depth.reset_mock()
            for behavior, add_base in (('DETACH', False), ('AUTO', True)):
                with self.subTest(behavior=behavior, add_base=add_base):
                    settings.loop_behavior = behavior
                    settings.loop_detach_add_base = add_base
                    with self.assertRaises(LocalizedGeometryError) as error:
                        gl.slice_loop_from_settings(target, indices, settings, scene)
                    self.assertIs(error.exception, collapsed)
            depth.assert_not_called()

            settings.loop_detach_add_base = False
            settings.loop_detected_mode = 'DETACH'
            settings.loop_auto_reason = 'previous result'
            depth.side_effect = LocalizedGeometryError('geometry.wall_thickness', depth=5.0, available=3.0)
            with self.assertRaises(LocalizedGeometryError) as error:
                gl.slice_loop_from_settings(target, indices, settings, scene)
            self.assertIs(error.exception, depth.side_effect)
            self.assertEqual(settings.loop_detected_mode, 'DETACH')
            self.assertEqual(settings.loop_auto_reason, 'previous result')

    def test_projected_edges_cannot_cross_a_narrow_concavity(self):
        mesh = bpy.data.meshes.new('AcrossNotch')
        mesh.from_pydata([(-2, 2, 1), (2, 2, 1), (0, -2, 1)], [], [(0, 1, 2)])
        mesh.update()
        obj = bpy.data.objects.new('AcrossNotch', mesh)
        bpy.context.scene.collection.objects.link(obj)
        outline = [(-3,-3), (3,-3), (3,3), (.1,3), (.1,0), (-.1,0), (-.1,3), (-3,3)]
        analysis = dict(coords_world=[Vector((x,y,0)) for x,y in outline],
                        centroid_world=Vector(), inward_dir_world=Vector((0,0,-1)),
                        region_face_indices=[0])
        self.assertTrue(gl._selected_region_overhangs_footprint(obj, analysis, 1))
        # A convex footprint covers the same complete source triangle.
        analysis['coords_world'] = [Vector((x,y,0)) for x,y in [(-3,-3),(3,-3),(3,3),(-3,3)]]
        self.assertFalse(gl._selected_region_overhangs_footprint(obj, analysis, 1))

    def test_overhang_refuses_prism_after_topological_failure(self):
        obj = make_horn_object(self.data)
        indices = self.data['loop_vertex_indices']
        seed = self.data['seed_face_index']
        analysis = gl.analyze_loop_region(obj, indices, seed)
        self.assertTrue(gl._selected_region_overhangs_footprint(
            obj, analysis, gl.get_scene_scale_to_mm(bpy.context.scene)))

        original_mesh = mesh_snapshot(obj)
        objects_before = {item.as_pointer() for item in bpy.data.objects}
        meshes_before = {item.as_pointer() for item in bpy.data.meshes}
        real_slice = gl.slice_mesh_by_loop
        forced_depth_failures = []

        def force_only_the_depth_cut_to_fail(*args, **kwargs):
            if kwargs.get('detach_add_base') and kwargs.get('detach_base_depth_mm', 0.0) > 0.0:
                forced_depth_failures.append(kwargs['detach_base_depth_mm'])
                raise LocalizedGeometryError(
                    'geometry.closing_intersection', part='A', count=1)
            # The nominal analysis probe must remain real; it establishes the
            # actual source geometry and may independently report a crossing.
            return real_slice(*args, **kwargs)

        # A silhouette reconstruction is now allowed, but an incomplete
        # reconstruction must still be refused before publishing any parts.
        from src import geometry_projection
        with mock.patch.object(geometry_projection, 'projected_region_outline', return_value=analysis['coords_world']), \
             mock.patch.object(gl, 'slice_mesh_by_loop', side_effect=force_only_the_depth_cut_to_fail), \
             mock.patch.object(gl, 'create_loop_prism_cutter') as prism_cutter:
            with self.assertRaises(LocalizedGeometryError) as error:
                gl.slice_mesh_by_loop_extrude(
                    obj, obj.name, indices, seed, depth_mm=5.0)

        self.assertEqual(error.exception.payload['__splitter_message__'],
                         'geometry.depth_region_overhang')
        self.assertEqual(forced_depth_failures, [5.0])
        prism_cutter.assert_not_called()
        self.assertEqual(mesh_snapshot(obj), original_mesh)
        self.assertEqual({item.as_pointer() for item in bpy.data.objects}, objects_before)
        self.assertEqual({item.as_pointer() for item in bpy.data.meshes}, meshes_before)

    def test_visible_diagonal_splits_preserve_face_and_corner_custom_data(self):
        mesh = bpy.data.meshes.new('WarpedNgon')
        mesh.from_pydata(
            [(0, 0, 0), (2, 0, 0), (3, 1, .1), (2, 2, .2), (0, 2, 0)],
            [], [(0, 1, 2, 3, 4)],
        )
        mesh.update()
        mesh.materials.append(bpy.data.materials.new('NgonMaterial'))
        mesh.polygons[0].material_index = 0
        uv_layer = mesh.uv_layers.new(name='UVMap')
        for loop in mesh.loops:
            vertex_index = loop.vertex_index
            uv_layer.data[loop.index].uv = (float(vertex_index), float(vertex_index * 2))
        obj = bpy.data.objects.new('WarpedNgon', mesh)
        bpy.context.scene.collection.objects.link(obj)
        bpy.context.view_layer.update()
        mesh.calc_loop_triangles()
        uv_by_coord = {
            tuple(round(float(c), 7) for c in vertex.co): (float(index), float(index * 2))
            for index, vertex in enumerate(mesh.vertices)
        }
        expected_triangles = {
            frozenset(tuple(round(float(c), 7) for c in mesh.vertices[index].co)
                      for index in triangle.vertices)
            for triangle in mesh.loop_triangles
        }

        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            face_id = bm.faces.layers.int.new('release_test_face_id')
            face_label = bm.faces.layers.string.new('release_test_face_label')
            bm.faces[0][face_id] = 73
            bm.faces[0][face_label] = b'warped-source'

            changed = gl._triangulate_retained_source_faces(bm, obj, [0])

            actual_triangles = {
                frozenset(tuple(round(float(c), 7) for c in vertex.co)
                          for vertex in face.verts)
                for face in bm.faces
            }
            self.assertGreater(changed, 0)
            self.assertEqual(actual_triangles, expected_triangles)
            self.assertTrue(all(face[face_id] == 73 for face in bm.faces))
            self.assertTrue(all(face[face_label] == b'warped-source' for face in bm.faces))

            uv_bm = bm.loops.layers.uv.get('UVMap')
            self.assertIsNotNone(uv_bm)
            for face in bm.faces:
                for loop in face.loops:
                    vertex_key = tuple(round(float(c), 7) for c in loop.vert.co)
                    expected_uv = uv_by_coord[vertex_key]
                    self.assertEqual(tuple(round(float(value), 6) for value in loop[uv_bm].uv),
                                     expected_uv)
        finally:
            bm.free()

    def test_material_relief_uses_shared_depth_and_assigns_contact_materials(self):
        for interface_mode in ('SOURCE', 'EXTRACTED'):
            with self.subTest(interface_mode=interface_mode):
                bpy.ops.wm.read_factory_settings(use_empty=True)
                bpy.context.scene.unit_settings.scale_length = 1.0
                obj = make_horn_object(self.data)
                original_mesh = mesh_snapshot(obj)
                selected_faces = {
                    tuple(sorted(tuple(round(float(c), 7) for c in
                                        obj.matrix_world @ obj.data.vertices[index].co)
                                 for index in obj.data.polygons[face_index].vertices))
                    for face_index in self.region
                }
                source_material = self.data['material_index']
                analysis = gm.analyze_material_structure(
                    obj, source_material, self.data['region_index'])
                self.assertEqual(analysis['face_count'], len(self.region))
                body_material = analysis['body_mat_index']

                result = gm.slice_mesh_by_material(
                    obj,
                    material_index=source_material,
                    depth_mm=5.0,
                    region_index=self.data['region_index'],
                    extraction_mode='EXTRUDE',
                    interface_mat_mode=interface_mode,
                )
                try:
                    self.assertEqual(result.interface.source_mode, 'MATERIAL')
                    marker_a = result.bm_a.faces.layers.int.get('splitter_contact_surface')
                    marker_b = result.bm_b.faces.layers.int.get('splitter_contact_surface')
                    self.assertIsNotNone(marker_a)
                    self.assertIsNotNone(marker_b)
                    contact_a = [f for f in result.bm_a.faces if f[marker_a]]
                    contact_b = [f for f in result.bm_b.faces if f[marker_b]]
                    self.assertTrue(contact_a)
                    self.assertTrue(contact_b)
                    expected_a = source_material if interface_mode == 'EXTRACTED' else body_material
                    self.assertEqual({f.material_index for f in contact_a}, {expected_a})
                    self.assertEqual({f.material_index for f in contact_b}, {body_material})

                    # The shared topological depth route must retain the full
                    # painted surface, not just its projected footprint.
                    retained_selected = {
                        face_signature(f) for f in result.bm_a.faces
                        if f.material_index == source_material
                    }
                    self.assertTrue(selected_faces <= retained_selected)
                    self.assertEqual(mesh_snapshot(obj), original_mesh)
                finally:
                    for bm_part in result:
                        bm_part.free()

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseDepthGuard)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
