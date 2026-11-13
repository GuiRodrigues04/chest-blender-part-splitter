"""Regression tests for depth-clearance bands along relieved contact walls."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src
from src.geometry_clearance import trim_depth_contact
from src.localized_errors import LocalizedGeometryError


def prism_with_contact_band():
    """20 mm square body with a tilted z=0..0.4 relief and lower contacts."""
    bm = bmesh.new()
    corners = ((-10, -10), (10, -10), (10, 10), (-10, 10))
    floor = [bm.verts.new((x, y, -0.4)) for x, y in corners]
    top = [bm.verts.new((x, y, z)) for (x, y), z in zip(corners, (0.0, 0.2, 0.4, 0.2))]
    bottom = bm.faces.new(tuple(reversed(floor)))
    sides = []
    for i in range(4):
        j = (i + 1) % 4
        sides.append(bm.faces.new((floor[i], floor[j], top[j], top[i])))
    bm.faces.new(tuple(top))
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    return bm, set(sides) | {bottom}


def volume_and_manifold(bm):
    return abs(bm.calc_volume()), all(edge.is_manifold for edge in bm.edges)


class TrimDepthContactBand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def run_band(self, lateral, bottom):
        source, contacts = prism_with_contact_band()
        source_volume = abs(source.calc_volume())
        try:
            result = trim_depth_contact(source, contacts, Vector((0, 0, -1)),
                                        lateral, bottom, 1.0, Vector((0, 0, 0)))
            output_volume, manifold = volume_and_manifold(result)
            result.free()
            return source_volume, output_volume, manifold
        finally:
            source.free()

    def test_full_relief_contact_band_has_clearance(self):
        before, after, manifold = self.run_band(0.1, 0.1)
        self.assertTrue(manifold)
        self.assertGreater(after, 0)
        # Lower core loss is 42.388 mm³. Above the support plane the inset
        # removes 0.1 × 16 mm² of perimeter height, minus 0.008 mm³ of
        # overlapping corner strips: 1.592 mm³ more.
        self.assertAlmostEqual(before-after, 43.980, delta=0.02)

    def test_minimum_lateral_clearance_is_present_across_all_walls(self):
        source, contacts = prism_with_contact_band()
        try:
            result = trim_depth_contact(source, contacts, Vector((0, 0, -1)),
                                        0.1, 0.1, 1.0, Vector((0, 0, 0)))
            try:
                tree = BVHTree.FromBMesh(result)
                probes = ((10, 0, -0.05), (-10, 0, -0.05),
                          (0, 10, -0.05), (0, -10, -0.05),
                          (10, 0, 0.05), (-10, 0, 0.05),
                          (0, 10, 0.05), (0, -10, 0.05))
                distances = [tree.find_nearest(Vector(point))[3] for point in probes]
                self.assertEqual(len(distances), 8)
                self.assertGreater(min(distances), 0.095)
                self.assertLess(max(distances), 0.105)
            finally:
                result.free()
        finally:
            source.free()

    def test_lateral_and_bottom_clearance_remain_independent(self):
        source, floor_only, floor_manifold = self.run_band(0.0, 0.1)
        _, sides_only, sides_manifold = self.run_band(0.1, 0.0)
        self.assertTrue(floor_manifold and sides_manifold)
        self.assertAlmostEqual(source-floor_only, 40.0, delta=0.1)
        self.assertAlmostEqual(source-sides_only, 4.776, delta=0.02)

    def test_real_contact_collapse_remains_excessive(self):
        source, contacts = prism_with_contact_band()
        try:
            with self.assertRaises(LocalizedGeometryError) as caught:
                trim_depth_contact(source, contacts, Vector((0, 0, -1)),
                                   10.1, 0.1, 1.0, Vector((0, 0, 0)))
            self.assertEqual(caught.exception.payload['__splitter_message__'],
                             'geometry.clearance_excessive')
        finally:
            source.free()

    def test_noncutting_boolean_result_reports_unresolved(self):
        source, contacts = prism_with_contact_band()
        try:
            with patch('src.geometry_clearance.subtract_closed_region',
                       side_effect=lambda bm, cutter, scale: bm.copy()):
                with self.assertRaises(LocalizedGeometryError) as caught:
                    trim_depth_contact(source, contacts, Vector((0, 0, -1)),
                                       0.1, 0.1, 1.0, Vector((0, 0, 0)))
            self.assertEqual(caught.exception.payload['__splitter_message__'],
                             'geometry.clearance_unresolved')
        finally:
            source.free()


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
