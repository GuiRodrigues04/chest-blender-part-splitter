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


def _cyclic_min(sequence):
    sequence = tuple(sequence)
    if not sequence:
        return ()
    return min(sequence[index:] + sequence[:index] for index in range(len(sequence)))


def _point_triangle_distance_mm(point, a, b, c):
    """Double precision closest distance for a 3D point to a triangle."""
    sub = lambda x, y: tuple(x[i] - y[i] for i in range(3))
    add = lambda x, y: tuple(x[i] + y[i] for i in range(3))
    scale = lambda x, factor: tuple(x[i] * factor for i in range(3))
    dot = lambda x, y: sum(x[i] * y[i] for i in range(3))
    def segment_distance(p, x, y):
        edge = sub(y, x)
        denom = dot(edge, edge)
        t = max(0.0, min(1.0, dot(sub(p, x), edge) / denom)) if denom else 0.0
        return sum((p[i] - (x[i] + t * edge[i])) ** 2 for i in range(3))
    ab, ac, ap = sub(b, a), sub(c, a), sub(point, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return (sum(value * value for value in ap)) ** .5
    bp = sub(point, b)
    d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return (sum(value * value for value in bp)) ** .5
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        delta = sub(point, add(a, scale(ab, v)))
        return (dot(delta, delta)) ** .5
    cp = sub(point, c)
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return (dot(cp, cp)) ** .5
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        delta = sub(point, add(a, scale(ac, w)))
        return (dot(delta, delta)) ** .5
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and d4 - d3 >= 0.0 and d5 - d6 >= 0.0:
        edge = sub(c, b)
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        delta = sub(point, add(b, scale(edge, w)))
        return (dot(delta, delta)) ** .5
    denom = va + vb + vc
    if denom == 0.0:
        return min(segment_distance(point, a, b), segment_distance(point, b, c),
                   segment_distance(point, c, a)) ** .5
    inv = 1.0 / denom
    v, w = vb * inv, vc * inv
    q = add(a, add(scale(ab, v), scale(ac, w)))
    delta = sub(point, q)
    return (dot(delta, delta)) ** .5


def _match_vertices_within_tolerance(first, repeated, tolerance_mm):
    """Return a bijection from first vertex indices to repeat indices, or None."""
    if len(first) != len(repeated):
        return None
    candidates = []
    for point in first:
        options = []
        for index, other in enumerate(repeated):
            distance = sum((float(point[axis]) - float(other[axis])) ** 2 for axis in range(3)) ** .5
            if distance <= tolerance_mm:
                options.append((distance, index))
        candidates.append(sorted(options))
    if any(not options for options in candidates):
        return None
    order = sorted(range(len(first)), key=lambda index: len(candidates[index]))
    matched_source = [-1] * len(repeated)
    def assign(source_index, seen):
        for _, repeat_index in candidates[source_index]:
            if repeat_index in seen:
                continue
            seen.add(repeat_index)
            if matched_source[repeat_index] < 0 or assign(matched_source[repeat_index], seen):
                matched_source[repeat_index] = source_index
                return True
        return False
    for source_index in order:
        if not assign(source_index, set()):
            return None
    mapping = [None] * len(first)
    for repeat_index, source_index in enumerate(matched_source):
        mapping[source_index] = repeat_index
    return mapping


def _mapped_face_records_equal(first_faces, repeated_faces, vertex_mapping):
    """Compare cyclic, winding-preserving faces after vertex reindexing."""
    mapped = sorted((material, _cyclic_min(tuple((vertex_mapping[index], uv)
                                                for index, uv in corners)))
                    for material, corners in first_faces)
    normalized_repeat = sorted((material, _cyclic_min(corners)) for material, corners in repeated_faces)
    return mapped == normalized_repeat


def capture_preview_geometry(obj):
    """Capture immutable mesh data and a BVH before a preview regeneration."""
    mesh = obj.data
    mesh.calc_loop_triangles()
    world = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
    world_mm = [tuple(float(component) * 1000.0 for component in point) for point in world]
    face_records = []
    indexed_face_records = []
    for polygon in mesh.polygons:
        coords = [tuple(round(value, 6) for value in world_mm[index]) for index in polygon.vertices]
        uv_layers = tuple(mesh.uv_layers)
        uvs = ([tuple(tuple(round(float(c), 7) for c in layer.data[loop_index].uv)
                      for layer in uv_layers) for loop_index in polygon.loop_indices]
               if uv_layers else [])
        paired = list(zip(coords, uvs)) if uvs else [(coord, ()) for coord in coords]
        face_records.append((polygon.material_index, _cyclic_min(paired)))
        indexed_uvs = uvs if uvs else [()] * len(polygon.vertices)
        indexed_face_records.append((polygon.material_index,
                                     _cyclic_min(tuple((int(vertex_index), uv)
                                                       for vertex_index, uv in zip(polygon.vertices, indexed_uvs)))))
    triangles = [tuple(int(index) for index in tri.vertices) for tri in mesh.loop_triangles]
    triangle_records = sorted((mesh.polygons[tri.polygon_index].material_index,
                               _cyclic_min(tuple(tuple(round(value, 6) for value in world_mm[index])
                                                 for index in tri.vertices)))
                              for tri in mesh.loop_triangles)
    bbox = [[min(point[axis] for point in world_mm) for axis in range(3)],
            [max(point[axis] for point in world_mm) for axis in range(3)]]
    center = tuple((bbox[0][axis] + bbox[1][axis]) * .5 for axis in range(3))
    centered_vertices = [tuple(point[axis] - center[axis] for axis in range(3)) for point in world_mm]
    bvh = BVHTree.FromPolygons(centered_vertices, triangles, all_triangles=True) if triangles else None
    samples = [('vertex', point, None) for point in world_mm]
    for tri_index, tri in enumerate(triangles):
        samples.append(('triangle_centroid', tuple(sum(world_mm[index][axis] for index in tri) / 3.0
                                                    for axis in range(3)), tri_index))
        for offset, index in enumerate(tri):
            other = tri[(offset + 1) % 3]
            samples.append(('triangle_edge_midpoint', tuple((world_mm[index][axis] + world_mm[other][axis]) * .5
                                                             for axis in range(3)), tri_index))
    bm = mesh_bmesh(obj)
    try:
        volume_mm3 = abs(bm.calc_volume()) * 1e9
    finally:
        bm.free()
    return {'world_mm': world_mm, 'vertices': sorted(tuple(round(v, 6) for v in p) for p in world_mm),
            'faces': sorted(face_records), 'indexed_faces': indexed_face_records,
            'triangles': triangles, 'triangle_records': triangle_records,
            'bvh': bvh, 'samples': samples, 'center_mm': center,
            'centered_vertices': centered_vertices,
            'volume_mm3': volume_mm3, 'bbox_mm': bbox,
            'material_slots': tuple((m.name, tuple(m.diffuse_color)) if m else None for m in mesh.materials),
            'uv_layers': tuple(layer.name for layer in mesh.uv_layers)}


def repeated_preview_metrics(a, b):
    """Compare captured previews, independent of mesh indexing and lifecycle."""
    distances = []
    self_distances = []
    distance_by_type = {}
    self_distance_by_type = {}
    cross_worst = (0.0, None)
    self_worst = (0.0, None)
    raw_bvh_distances = []
    self_raw_bvh_distances = []
    brute_force_count = 0
    def bidirectional_vertex_delta():
        maxima = []
        for source, target in ((a, b), (b, a)):
            maxima.extend(min((sum((point[i]-other[i])**2 for i in range(3)) ** .5
                               for other in target['world_mm']), default=float('inf'))
                          for point in source['world_mm'])
        return max(maxima, default=0.0)
    def nearest_surface(point, target, raw_store):
        nonlocal brute_force_count
        local_point = tuple(float(point[i] - target['center_mm'][i]) for i in range(3))
        hit = target['bvh'].find_nearest(local_point) if target['bvh'] else None
        raw_distance = (sum((float(hit[0][i]) - local_point[i]) ** 2 for i in range(3)) ** .5
                        if hit and hit[0] else float('inf'))
        raw_store.append(raw_distance)
        candidate = [int(hit[2])] if hit and hit[2] is not None else []
        def exact_distance(indices):
            return min((_point_triangle_distance_mm(
                local_point, target['centered_vertices'][target['triangles'][index][0]],
                target['centered_vertices'][target['triangles'][index][1]],
                target['centered_vertices'][target['triangles'][index][2]])
                for index in indices), default=float('inf'))
        distance = exact_distance(candidate)
        if distance > .001:
            brute_force_count += 1
            distance = exact_distance(range(len(target['triangles'])))
        return distance
    for source, target in ((a, b), (b, a)):
        if target['bvh'] is None and source['samples']:
            distances.append(float('inf'))
            continue
        for sample_type, point, tri_index in source['samples']:
            distance = nearest_surface(point, target, raw_bvh_distances)
            distances.append(distance)
            distance_by_type[sample_type] = max(distance_by_type.get(sample_type, 0.0), distance)
            if distance > cross_worst[0]:
                cross_worst = (distance, (sample_type, tri_index, point))
    for source in (a, b):
        for sample_type, point, tri_index in source['samples']:
            distance = nearest_surface(point, source, self_raw_bvh_distances)
            self_distances.append(distance)
            self_distance_by_type[sample_type] = max(self_distance_by_type.get(sample_type, 0.0), distance)
            if distance > self_worst[0]:
                self_worst = (distance, (sample_type, tri_index, point))
    def triangle_shape(snapshot, sample):
        if sample is None or sample[1] is None:
            return None
        tri = snapshot['triangles'][sample[1]]
        points = [Vector(snapshot['world_mm'][index]) for index in tri]
        lengths = [(points[(index+1) % 3] - points[index]).length for index in range(3)]
        area = .5 * (points[1]-points[0]).cross(points[2]-points[0]).length
        return {'triangle_index': sample[1], 'side_lengths_mm': lengths, 'area_mm2': area,
                'max_side_min_altitude_ratio': (max(lengths) ** 2 / (2 * area)) if area else float('inf')}
    vertex_mapping = _match_vertices_within_tolerance(a['world_mm'], b['world_mm'], .001)
    semantic_faces_equal = (vertex_mapping is not None and len(a['faces']) == len(b['faces'])
                            and _mapped_face_records_equal(a['indexed_faces'], b['indexed_faces'],
                                                           vertex_mapping))
    return {
        'first_vertex_count': len(a['world_mm']), 'repeat_vertex_count': len(b['world_mm']),
        'vertices_canonical_equal': a['vertices'] == b['vertices'],
        'vertex_bijection_within_0_001mm': vertex_mapping is not None,
        'bidirectional_nearest_vertex_max_mm': bidirectional_vertex_delta(),
        'face_count_first': len(a['faces']), 'face_count_repeat': len(b['faces']),
        'faces_canonical_equal': a['faces'] == b['faces'],
        'faces_semantic_equal_after_reindex': semantic_faces_equal,
        'triangles_canonical_equal': a['triangle_records'] == b['triangle_records'],
        'material_face_counts_first': {str(key): value for key, value in
                                       sorted(__import__('collections').Counter(
                                           material for material, _ in a['faces']).items())},
        'material_face_counts_repeat': {str(key): value for key, value in
                                        sorted(__import__('collections').Counter(
                                            material for material, _ in b['faces']).items())},
        'material_slots_equal': a['material_slots'] == b['material_slots'],
        'uv_layers_equal': a['uv_layers'] == b['uv_layers'],
        'uv_data_present': bool(a['uv_layers'] or b['uv_layers']),
        'volume_first_mm3': a['volume_mm3'], 'volume_repeat_mm3': b['volume_mm3'],
        'volume_delta_mm3': abs(a['volume_mm3'] - b['volume_mm3']),
        'bbox_delta_mm': max(abs(a['bbox_mm'][side][axis] - b['bbox_mm'][side][axis])
                             for side in (0, 1) for axis in range(3)),
        'bidirectional_sample_to_surface_max_mm': max(distances, default=0.0),
        'raw_bvh_bidirectional_max_mm': max(raw_bvh_distances, default=0.0),
        'self_sample_to_surface_max_mm': max(self_distances, default=0.0),
        'raw_bvh_self_max_mm': max(self_raw_bvh_distances, default=0.0),
        'pure_python_bruteforce_refinements': brute_force_count,
        'bidirectional_distance_by_sample_type_mm': distance_by_type,
        'self_distance_by_sample_type_mm': self_distance_by_type,
        'cross_worst_sample': {'distance_mm': cross_worst[0], 'type': cross_worst[1][0] if cross_worst[1] else None,
                               'triangle': triangle_shape(a, cross_worst[1])},
        'self_worst_sample': {'distance_mm': self_worst[0], 'type': self_worst[1][0] if self_worst[1] else None,
                              'triangle': triangle_shape(a, self_worst[1])},
        'sample_count_each_direction': len(a['samples']),
    }


class ReleaseWorkflows(unittest.TestCase):
    def test_point_triangle_distance_helper(self):
        self.assertAlmostEqual(_point_triangle_distance_mm((.25, .25, 1), (0, 0, 0), (1, 0, 0), (0, 1, 0)), 1.0)
        self.assertAlmostEqual(_point_triangle_distance_mm((.25, .25, 0), (0, 0, 0), (1, 0, 0), (0, 1, 0)), 0.0)
        self.assertAlmostEqual(_point_triangle_distance_mm((1, 1, 0), (0, 0, 0), (2, 0, 0), (1, 0, 0)), 1.0)

    def test_tolerant_reindex_helpers_reject_physical_winding_and_material_changes(self):
        first = [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.)]
        repeated = [(0., 1., 0.), (.0002, 0., 0.), (1., 0., 0.)]
        mapping = _match_vertices_within_tolerance(first, repeated, .001)
        self.assertEqual(mapping, [1, 2, 0])
        uv = ((.0, .0),)
        first_faces = [(3, ((0, uv), (1, uv), (2, uv)))]
        repeat_faces = [(3, ((2, uv), (0, uv), (1, uv)))]
        self.assertTrue(_mapped_face_records_equal(first_faces, repeat_faces, mapping))
        self.assertFalse(_mapped_face_records_equal(first_faces, [(3, ((2, uv), (1, uv), (0, uv)))], mapping))
        self.assertFalse(_mapped_face_records_equal(first_faces, [(4, ((2, uv), (0, uv), (1, uv)))], mapping))
        self.assertFalse(_mapped_face_records_equal(first_faces, [(3, ((2, ((.1, .0),)), (0, uv), (1, uv)))], mapping))
        self.assertIsNone(_match_vertices_within_tolerance(first, [(0., 1., 0.), (.002, 0., 0.), (1., 0., 0.)], .001))

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
                        self.assertEqual(len(parts), 2)
                        signature = {part.get('chest_role'): capture_preview_geometry(part) for part in parts}
                        self.assertEqual(len(signature), 2)
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
                        self.assertEqual(len(repeated), 2)
                        repeated_by_role = {part.get('chest_role'): part for part in repeated}
                        self.assertEqual(len(repeated_by_role), 2)
                        self.assertEqual(set(repeated_by_role), set(signature))
                        for role, first_part in signature.items():
                            metrics = repeated_preview_metrics(first_part, capture_preview_geometry(repeated_by_role[role]))
                            self.assertEqual(metrics['face_count_first'], metrics['face_count_repeat'], str(metrics))
                            self.assertTrue(metrics['vertex_bijection_within_0_001mm'], str(metrics))
                            self.assertTrue(metrics['faces_semantic_equal_after_reindex'], str(metrics))
                            self.assertEqual(metrics['material_slots_equal'], True, str(metrics))
                            self.assertEqual(metrics['uv_layers_equal'], True, str(metrics))
                            self.assertLessEqual(metrics['volume_delta_mm3'],
                                                 max(.001, abs(metrics['volume_first_mm3']) * 1e-6), str(metrics))
                            self.assertLessEqual(metrics['bbox_delta_mm'], .001, str(metrics))
                            self.assertLessEqual(metrics['bidirectional_sample_to_surface_max_mm'], .001,
                                                 str(metrics))
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
