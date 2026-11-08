"""Curved closure and measured blades on a portable, closed wavy cylinder."""
import math
import sys
import unittest
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.geometry_loop import slice_mesh_by_loop, _slice_mesh_by_loop_impl
from src.geometry_material import slice_mesh_by_material
from src.geometry_clearance_blade import apply_blade_pair, measure_gap


def fixture(amplitude=.0004):
    count = 16
    vertices = []
    for level in range(3):
        for i in range(count):
            angle = 2 * math.pi * i / count
            z = (-.02 if level == 0 else .02 if level == 2
                 else amplitude * math.sin(2 * angle) + amplitude/3 * math.sin(3 * angle))
            vertices.append((.01 * math.cos(angle), .01 * math.sin(angle), z))
    faces = [tuple(reversed(range(count)))]
    for level in range(2):
        for i in range(count):
            j = (i + 1) % count
            faces.append((level*count+i, level*count+j, (level+1)*count+j, (level+1)*count+i))
    faces.append(tuple(range(2*count, 3*count)))
    mesh = bpy.data.meshes.new('Wavy cylinder')
    mesh.from_pydata(vertices, [], faces)
    for name in ('Body', 'Selected'):
        mesh.materials.append(bpy.data.materials.new(name))
    for face in mesh.polygons:
        face.material_index = int(face.index >= 17)
    obj = bpy.data.objects.new('Wavy cylinder', mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj, list(range(count, 2*count)), len(faces)-1


class NaturalClearance(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 1

    def test_natural_cut_and_material_share_surface_without_steps(self):
        obj, ring, seed = fixture(.0015)
        original = tuple(tuple(v.co) for v in obj.data.vertices)
        loop = slice_mesh_by_loop(obj, obj.name, ring, seed)
        material = slice_mesh_by_material(obj, 1, extraction_mode='BASE')
        try:
            for result in (loop, material):
                self.assertEqual(result.interface.closure_strategy, 'NATURAL')
                self.assertTrue(all(e.is_manifold for part in result for e in part.edges))
            self.assertAlmostEqual(loop[0].calc_volume(), material[0].calc_volume(), delta=1e-10)
            self.assertEqual(original, tuple(tuple(v.co) for v in obj.data.vertices))
        finally:
            for result in (loop, material):
                for part in result:
                    part.free()

    def test_blades_all_destinations_preserve_source_and_clean_temporaries(self):
        obj, ring, seed = fixture()
        original = tuple(tuple(v.co) for v in obj.data.vertices)
        # A blade operates on the accepted triangular safety surface. Curved
        # editable quads may tessellate differently and must be retried first.
        base = _slice_mesh_by_loop_impl(obj, obj.name, ring, seed, _prefer_quads=False)
        object_names = set(bpy.data.objects.keys())
        mesh_names = set(bpy.data.meshes.keys())
        try:
            for gap in (.1, .2, 1.):
                for side in ('PART', 'CAVITY', 'BOTH'):
                    with self.subTest(gap=gap, side=side):
                        a, b, measured = apply_blade_pair(*base, obj, gap, side, 1000.)
                        try:
                            self.assertTrue(all(e.is_manifold for p in (a, b) for e in p.edges))
                            self.assertLess(sum(abs(p.calc_volume()) for p in (a, b)),
                                            sum(abs(p.calc_volume()) for p in base))
                            self.assertGreater(measured['interior_samples'], 0)
                            self.assertLessEqual(abs(measured['normal_minimum_mm']-gap), measured['tolerance_mm'])
                            self.assertLessEqual(abs(measured['normal_maximum_mm']-gap), measured['tolerance_mm'])
                        finally:
                            a.free(); b.free()
                        self.assertEqual(object_names, set(bpy.data.objects.keys()))
                        self.assertEqual(mesh_names, set(bpy.data.meshes.keys()))
            self.assertEqual(original, tuple(tuple(v.co) for v in obj.data.vertices))
            with self.assertRaises(ValueError):
                measure_gap(*base, base[0], .1, 1000.)
        finally:
            for part in base:
                part.free()

    def test_public_cut_measures_visible_curved_gap(self):
        obj, ring, seed = fixture()
        for gap in (.1, .2, 1.):
            for side in ('PART', 'CAVITY', 'BOTH'):
                with self.subTest(gap=gap, side=side):
                    result = slice_mesh_by_loop(obj, obj.name, ring, seed,
                        part_clearance_mm=gap, part_clearance_apply_to=side)
                    try:
                        self.assertEqual(result.interface.closure_strategy, 'NATURAL')
                        measured = result.interface.clearance_measurements
                        self.assertGreater(measured['normal_samples'], 0)
                        self.assertLessEqual(abs(measured['normal_minimum_mm']-gap), measured['tolerance_mm'])
                        self.assertTrue(all(e.is_manifold for part in result for e in part.edges))
                    finally:
                        for part in result:
                            part.free()


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NaturalClearance)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise RuntimeError('Natural clearance tests failed')
