"""Depth regression for the privately captured Cubo Teste 2 horn region.

Run with Blender's background Python and PART_SPLITTER_ROOT pointing to the
integrated add-on. The fixture contains only the original mesh geometry and
the material-region boundary extracted from the provided blend file.
"""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ROOT = Path(os.environ.get('PART_SPLITTER_ROOT') or (arguments[0] if arguments else Path(__file__).resolve().parents[1])).resolve()
FIXTURE = Path(os.environ.get('PART_SPLITTER_HORN_FIXTURE', str(ROOT / 'tests/fixtures/horn_region_private.json')))
sys.path.insert(0, str(ROOT.parent))
addon = importlib.import_module(ROOT.name)
ops = importlib.import_module(ROOT.name + '.src.operators')
geometry_loop = importlib.import_module(ROOT.name + '.src.geometry_loop')
addon.register()


class HornDepthRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding='utf-8'))
        cls.region = set(cls.data['region_face_indices'])

    def setUpCase(self, mode, gap, through=False, depth_mm=5.0):
        data = self.data
        bpy.ops.wm.read_homefile(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 1.0
        mesh = bpy.data.meshes.new(data['name'])
        mesh.from_pydata(data['vertices'], [], data['faces'])
        mesh.update()
        for slot in data['material_slots']:
            material = bpy.data.materials.new(slot['name'] or 'Material')
            if slot['color']:
                material.diffuse_color = slot['color']
            mesh.materials.append(material)
        for poly, mat_index in zip(mesh.polygons, data['materials']):
            poly.material_index = mat_index
        obj = bpy.data.objects.new(data['name'], mesh)
        obj.matrix_world = Matrix(data['matrix'])
        bpy.context.scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.context.view_layer.update()
        self.target = obj
        self.original = (
            tuple(tuple(v.co) for v in mesh.vertices),
            tuple(tuple(p.vertices) for p in mesh.polygons),
            tuple(p.material_index for p in mesh.polygons),
        )
        settings = bpy.context.scene.chest_splitter
        settings.target_object = obj
        settings.split_mode = mode
        settings.connector_enabled = False
        settings.commit_next_target = 'NONE'
        settings.view_mode = 'ASSEMBLED'
        settings.part_clearance_mm = gap
        settings.part_clearance_apply_to = 'PART'
        settings.loop_behavior = 'EXTRUDE'
        settings.loop_extrude_depth_mm = depth_mm
        settings.loop_through_cut = through
        settings.material_split_index = data['material_index']
        settings.material_region_index = data['region_index']
        settings.material_extraction_mode = 'EXTRUDE'
        settings.material_extrude_depth_mm = depth_mm

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            face.select_set(face.index in self.region)
        bm.faces.active = bm.faces[data['seed_face_index']]
        bmesh.update_edit_mesh(mesh)
        if mode == 'MATERIAL':
            # Exercise the product's region selection from the actual active face.
            self.assertEqual(bpy.ops.chest.splitter_pick_material_region(), {'FINISHED'})
            self.assertEqual(settings.material_split_index, data['material_index'])
            self.assertEqual(settings.material_region_index, data['region_index'])
        else:
            self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(), {'FINISHED'})
            self.assertEqual(settings.loop_seed_face_index, data['seed_face_index'])
            self.assertEqual(settings.loop_vertex_count, len(data['loop_vertex_indices']))
        bpy.ops.object.mode_set(mode='OBJECT')
        self.settings = settings

    def _assert_source_unchanged(self):
        mesh = self.target.data
        current = (
            tuple(tuple(v.co) for v in mesh.vertices),
            tuple(tuple(p.vertices) for p in mesh.polygons),
            tuple(p.material_index for p in mesh.polygons),
        )
        self.assertEqual(current, self.original)

    def _parts_and_trees(self):
        parts = ops.get_current_session_parts(bpy.context.scene)
        self.assertEqual(len(parts), 2)
        part_a = next(part for part in parts if part.get('chest_role') == 'PREVIEW_A')
        part_b = next(part for part in parts if part.get('chest_role') == 'PREVIEW_B')
        trees = []
        bmeshes = []
        for part in (part_a, part_b):
            bm = bmesh.new()
            bm.from_mesh(part.data)
            frame = Matrix(part.get('chest_assembled_matrix', part.matrix_world))
            bm.transform(frame)
            bm.normal_update()
            trees.append(BVHTree.FromBMesh(bm))
            bmeshes.append(bm)
        return (part_a, part_b), trees, bmeshes

    def _selected_region_samples(self):
        mesh = self.target.data
        mesh.calc_loop_triangles()
        world = [self.target.matrix_world @ vertex.co for vertex in mesh.vertices]
        samples = []
        for tri in mesh.loop_triangles:
            if tri.polygon_index not in self.region:
                continue
            points = [world[index] for index in tri.vertices]
            # Face-center and three interior points catch partial clipping while
            # avoiding the legitimate shared boundary vertices.
            samples.append(sum(points, Vector()) / 3.0)
            for i in range(3):
                samples.append(points[i] * .6 + points[(i + 1) % 3] * .2 + points[(i + 2) % 3] * .2)
        self.assertGreater(len(samples), 112)
        return samples

    @staticmethod
    def _point_key(point):
        return tuple(round(float(value), 6) for value in point)

    def _source_face_and_vertex_provenance(self, parts):
        mesh = self.target.data
        source_vertices = [self.target.matrix_world @ vertex.co for vertex in mesh.vertices]
        selected_face_keys = []
        selected_vertex_keys = {self._point_key(source_vertices[index])
                                for face_index in self.region
                                for index in mesh.polygons[face_index].vertices}
        for face_index in sorted(self.region):
            face = mesh.polygons[face_index]
            selected_face_keys.append(tuple(sorted(self._point_key(source_vertices[index])
                                                   for index in face.vertices)))
        output = []
        output_vertices = []
        for part in parts:
            transform = Matrix(part.get('chest_assembled_matrix', part.matrix_world))
            vertices = [transform @ vertex.co for vertex in part.data.vertices]
            face_keys = {tuple(sorted(self._point_key(vertices[index]) for index in face.vertices))
                         for face in part.data.polygons}
            vertex_keys = {self._point_key(vertex) for vertex in vertices}
            output.append(face_keys)
            output_vertices.append(vertex_keys)
        retained_a = sum(key in output[0] for key in selected_face_keys)
        retained_b = sum(key in output[1] for key in selected_face_keys)
        missing_a = [index for index, key in zip(sorted(self.region), selected_face_keys) if key not in output[0]]
        present_b = [index for index, key in zip(sorted(self.region), selected_face_keys) if key in output[1]]
        vertices_a = sum(key in output_vertices[0] for key in selected_vertex_keys)
        vertices_b = sum(key in output_vertices[1] for key in selected_vertex_keys)
        return retained_a, retained_b, vertices_a, vertices_b, len(selected_vertex_keys), missing_a, present_b

    def _connected_component_count(self, bm):
        remaining = set(bm.verts)
        count = 0
        while remaining:
            count += 1
            stack = [remaining.pop()]
            while stack:
                vertex = stack.pop()
                for edge in vertex.link_edges:
                    other = edge.other_vert(vertex)
                    if other in remaining:
                        remaining.remove(other)
                        stack.append(other)
        return count

    def _exercise_case(self, mode, gap, through=False, depth_mm=5.0):
        self.setUpCase(mode, gap, through, depth_mm)
        result = bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(result, {'FINISHED'}, self.settings.get_localized_status())
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')
        self._assert_source_unchanged()
        (part_a, part_b), trees, bmeshes = self._parts_and_trees()
        try:
            face_a, face_b, vertices_a, vertices_b, total_vertices, missing_a, present_b = self._source_face_and_vertex_provenance((part_a, part_b))
            samples = self._selected_region_samples()
            on_a = [tree.find_nearest(point)[3] for point in samples for tree in trees[:1]]
            on_b = [tree.find_nearest(point)[3] for point in samples for tree in trees[1:]]
            max_a = max(on_a)
            min_b = min(on_b)
            selected_vertices = {vertex for index in self.region
                                 for vertex in self.target.data.polygons[index].vertices}
            selected_source_max_z = max((self.target.matrix_world @ self.target.data.vertices[i].co).z
                                        for i in selected_vertices)
            part_world_points = []
            for part in (part_a, part_b):
                transform = Matrix(part.get('chest_assembled_matrix', part.matrix_world))
                part_world_points.append([transform @ vertex.co for vertex in part.data.vertices])
            frame_z = [max(point.z for point in points) * 1000 for points in part_world_points]
            region_on_a = sum(distance * 1000 <= .05 for distance in on_a)
            region_on_b = sum(distance * 1000 <= .05 for distance in on_b)
            indices = self.data['loop_vertex_indices']
            loop_analysis = geometry_loop.analyze_loop_region(
                self.target, indices, self.data['seed_face_index'], bpy.context.scene,
            )
            overrun = (mode == 'LOOP' and through and
                       depth_mm >= loop_analysis.get('max_avail_depth_mm', float('inf')))
            print('HORN_REGION_COVERAGE', json.dumps({
                'mode': mode, 'gap_mm': gap, 'through': through,
                'region_faces': len(self.region), 'surface_samples': len(samples),
                'selected_source_max_z_mm': selected_source_max_z * 1000,
                'preview_A_max_z_mm': frame_z[0], 'preview_B_max_z_mm': frame_z[1],
                'selected_surface_samples_on_A': region_on_a,
                'selected_surface_samples_on_B': region_on_b,
                'original_region_faces_on_A': face_a,
                'original_region_faces_on_B': face_b,
                'original_region_vertices_on_A': vertices_a,
                'original_region_vertices_on_B': vertices_b,
                'original_region_vertex_count': total_vertices,
                'missing_source_faces_from_A': missing_a,
                'source_faces_still_in_B': present_b,
                'max_distance_to_A_mm': max_a * 1000,
                'min_distance_to_B_mm': min_b * 1000,
                'A_components': self._connected_component_count(bmeshes[0]),
                'B_components': self._connected_component_count(bmeshes[1]),
            }, sort_keys=True))
            self.assertLessEqual(max_a * 1000, .05,
                                 'Every selected visible horn-triangle interior must remain on extracted Part A')
            if overrun:
                self.assertEqual(selected_source_max_z, max(point.z for point in part_world_points[0]),
                                 'The horn tip must be preserved at the source maximum height')
            self.assertGreater(min_b * 1000, .05,
                               'The selected horn surface must be absent from complementary Part B')
            self.assertEqual(self._connected_component_count(bmeshes[0]), 1,
                             'Extracted horn region must remain connected as one solid, with no floating fragments')
            self.assertEqual(self._connected_component_count(bmeshes[1]), 1,
                             'Complementary main body must remain one connected solid')
            if not overrun:
                self.assertEqual(face_a, len(self.region),
                                 'Every original selected horn face must be preserved exactly in Part A')
                self.assertEqual(face_b, 0,
                                 'No original selected horn face may remain in Part B')
            self.assertEqual(vertices_a, total_vertices,
                             'Every original selected horn vertex must be preserved in Part A')
            analysis = loop_analysis
            inward = Vector(analysis['inward_dir_world']).normalized()
            outward = -inward
            center = Vector(analysis['centroid_world'])
            support = center + outward * min((Vector(point)-center).dot(outward)
                                             for point in analysis['coords_world'])
            u_axis, v_axis = geometry_loop._get_orthonormal_basis(inward)
            coords = [Vector(point) for point in analysis['coords_world']]
            planar = [Vector(((point-support).dot(u_axis), (point-support).dot(v_axis))) for point in coords]
            if overrun:
                self.assertEqual(self.settings.loop_extrude_depth_mm, depth_mm,
                                 'Through-cut must preserve the configured depth without clamping')
                source_bm = bmesh.new()
                source_bm.from_mesh(self.target.data)
                source_bm.transform(self.target.matrix_world)
                source_bm.normal_update()
                source_tree = BVHTree.FromBMesh(source_bm)
                source_bm.free()
                ray_origin = support + inward * ((depth_mm + 1.0) / 1000)
                source_back = source_tree.ray_cast(ray_origin, -inward, .5)
                output_back = trees[0].ray_cast(ray_origin, -inward, .5)
                self.assertIsNotNone(source_back[0], 'Source ray must find the opposite wall before the requested depth')
                self.assertIsNotNone(output_back[0], 'Extracted piece must reach the opposite wall')
                source_back_depth = (source_back[0]-support).dot(inward) * 1000
                output_back_depth = (output_back[0]-support).dot(inward) * 1000
                self.assertLess(source_back_depth, depth_mm,
                                'The configured through-depth must extend beyond the real opposite wall')
                self.assertAlmostEqual(output_back_depth, source_back_depth, delta=.05,
                                       msg='Extracted bbox/floor must stop at the source opposite wall')
                print('HORN_REGION_THROUGH_WALL', json.dumps({
                    'mode': mode, 'configured_depth_mm': depth_mm,
                    'source_opposite_wall_depth_mm': source_back_depth,
                    'extracted_opposite_wall_depth_mm': output_back_depth,
                    'gap_mm': gap, 'through': through,
                }, sort_keys=True))
                return

            interface_b = Vector(self.settings.loop_interface_origin)
            interface_a = interface_b - inward * (gap / 1000)
            triangles = geometry_loop.triangulate_polygon_2d(planar)
            footprint_samples = []
            for tri in triangles:
                q = (planar[tri[0]] + planar[tri[1]] + planar[tri[2]]) / 3.0
                edge_distances = []
                for i, a in enumerate(planar):
                    b = planar[(i + 1) % len(planar)]
                    ab = b-a
                    t = max(0.0, min(1.0, (q-a).dot(ab) / max(ab.length_squared, 1e-20)))
                    edge_distances.append((q-(a+t*ab)).length * 1000)
                footprint_samples.append((q, min(edge_distances)))
            for role, tree, interface_origin, expected_depth in (
                ('A', trees[0], interface_a, 5.0-gap),
                ('B', trees[1], interface_b, depth_mm),
            ):
                actual_depth = (interface_origin-support).dot(inward) * 1000
                self.assertAlmostEqual(actual_depth, expected_depth, delta=.02)
                measured_depths = []
                for q, edge_distance_mm in footprint_samples:
                    if role == 'A' and gap > 0.0 and edge_distance_mm <= gap + .02:
                        continue
                    point = interface_origin + q.x*u_axis + q.y*v_axis
                    if role == 'A':
                        start, direction = point - inward * .0005, inward
                    else:
                        start, direction = point + inward * .0005, -inward
                    hit = tree.ray_cast(start, direction, .001)
                    if hit[0] is not None:
                        measured_depths.append((hit[0]-support).dot(inward) * 1000)
                self.assertGreater(len(measured_depths), 5,
                                   f'{role} needs enough physical interface hits after clearance')
                max_error = max(abs(value-expected_depth) for value in measured_depths)
                print('HORN_REGION_DEPTH', json.dumps({
                    'mode': mode, 'part': role, 'configured_depth_mm': depth_mm,
                    'gap_mm': gap, 'through': through, 'measured_depth_mm': actual_depth,
                    'measured_min_mm': min(measured_depths), 'measured_max_mm': max(measured_depths),
                    'max_error_mm': max_error, 'samples': len(measured_depths),
                }, sort_keys=True))
                self.assertLessEqual(max_error, .05,
                                     f'{role} physical interface must match the selected depth')
        finally:
            for bm in bmeshes:
                bm.free()
        self._assert_source_unchanged()

    def test_material_extrude_preserves_tall_horn_region(self):
        for gap in (0.0, .15):
            with self.subTest(mode='MATERIAL', gap_mm=gap):
                self._exercise_case('MATERIAL', gap)

    def test_loop_extrude_preserves_tall_horn_region(self):
        for gap in (0.0, .15):
            for through in (False, True):
                with self.subTest(mode='LOOP', gap_mm=gap, through=through):
                    self._exercise_case('LOOP', gap, through)

    def test_loop_through_depth_reaches_opposite_wall(self):
        self._exercise_case('LOOP', 0.0, True, depth_mm=200.0)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
