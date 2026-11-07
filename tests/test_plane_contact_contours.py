"""Focused planar contact regressions; optional SPLITTER_PLATE_FIXTURE .blend."""
import importlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(os.environ.get('SPLITTER_TEST_ROOT', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT.parent))
addon = importlib.import_module(ROOT.name)
addon.register()
gp = importlib.import_module(ROOT.name + '.src.geometry_plane')
gc = importlib.import_module(ROOT.name + '.src.geometry_contract')
cs = importlib.import_module(ROOT.name + '.src.connector_surface')
diag = importlib.import_module(ROOT.name + '.src.diagnostic')


class PlaneContactContours(unittest.TestCase):
    def plate_settings(self):
        bpy.ops.wm.open_mainfile(filepath=os.environ['SPLITTER_PLATE_FIXTURE'])
        s = bpy.context.scene.chest_splitter
        s.target_object = bpy.data.objects['Placa_Chest_Inteira']
        constants = importlib.import_module(ROOT.name + '.src.constants')
        guide = bpy.data.objects.get(constants.PLANE_GUIDE_NAME)
        guide.matrix_world = Matrix.Translation((-.025, -.0095, .008))
        bpy.context.view_layer.update()
        s.split_mode = 'PLANE'
        s.plane_extent_mode = 'FULL'
        s.plane_offset_mm = .51
        s.part_clearance_mm = .1
        s.part_clearance_apply_to = 'PART'
        s.invert_sides = False
        s.connector_male_part = 'A'
        s.connector_distribution = 'MANUAL'
        s.connector_enabled = True
        s.connector_type = 'CYLINDER'
        s.connector_diameter_mm = 2.5
        s.connector_length_mm = 4
        s.connector_edge_margin_mm = .4
        s.clearance_per_side_mm = .1
        return s

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        cs.clear_prepared_split_cache()

    def cube(self, center=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(size=.02, location=center)
        return bpy.context.object

    def cut(self, obj, **kwargs):
        a = bpy.data.meshes.new('contact_test_a')
        b = bpy.data.meshes.new('contact_test_b')
        try:
            report = gp.slice_mesh_by_plane(obj.data, obj.matrix_world,
                Vector((0, 0, 0)), Vector((0, 0, 1)), a, b, **kwargs)
            self.assertTrue(report['A']['is_manifold'])
            self.assertTrue(report['B']['is_manifold'])
            return report['interface']
        finally:
            bpy.data.meshes.remove(a)
            bpy.data.meshes.remove(b)

    def test_repaired_perimeter_uses_new_edges(self):
        obj = self.cube()
        original = diag.sanitize_mesh_micro_degeneracies
        def repair(bm, scale):
            original(bm, scale)
            edges = [e for e in bm.edges
                     if all(abs(v.co.z) < 1e-8 for v in e.verts)]
            # A topology edit after bisect makes its original edge list stale.
            bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=False)
        with patch.object(diag, 'sanitize_mesh_micro_degeneracies', repair):
            interface = self.cut(obj)
        self.assertAlmostEqual(interface.area_mm2, 400, delta=.001)
        self.assertEqual(len(interface.outer_contours_uv), 1)

    def test_inverted_and_clearance_destinations(self):
        obj = self.cube()
        for inverted in (False, True):
            for destination in ('PART', 'CAVITY', 'BOTH'):
                with self.subTest(inverted=inverted, destination=destination):
                    f = self.cut(obj, invert_sides=inverted,
                                 part_clearance_mm=.1,
                                 part_clearance_apply_to=destination)
                    self.assertAlmostEqual(f.area_mm2, 400, delta=.001)
                    self.assertEqual(len(f.outer_contours_uv), 1)
                    self.assertEqual(len(f.hole_contours_uv), 0)

    def test_disconnected_contact_islands(self):
        left = self.cube((-.03, 0, 0))
        right = self.cube((.03, 0, 0))
        left.select_set(True)
        right.select_set(True)
        bpy.context.view_layer.objects.active = left
        bpy.ops.object.join()
        f = self.cut(left)
        self.assertEqual(len(f.outer_contours_uv), 2)
        self.assertAlmostEqual(f.area_mm2, 800, delta=.002)

    def test_rotated_translated_nonuniform_target(self):
        obj = self.cube()
        transform = (Matrix.Translation((.2, -.1, .05))
                     @ Matrix.Rotation(.45, 4, 'Y')
                     @ Matrix.Diagonal((2, 1, .5, 1)))
        origin = transform @ Vector()
        normal = (transform.to_3x3().inverted().transposed()
                  @ Vector((0, 0, 1))).normalized()
        a = bpy.data.meshes.new('rotated_a')
        b = bpy.data.meshes.new('rotated_b')
        try:
            r = gp.slice_mesh_by_plane(obj.data, transform, origin, normal, a, b)
            self.assertTrue(r['A']['is_manifold'])
            self.assertTrue(r['B']['is_manifold'])
            self.assertAlmostEqual(r['interface'].area_mm2, 800, delta=.01)
        finally:
            bpy.data.meshes.remove(a)
            bpy.data.meshes.remove(b)

    def test_triangulated_contact_preserves_hole(self):
        bm = bmesh.new()
        try:
            outer = [bm.verts.new((x, y, 0)) for x, y in
                     ((-.02, -.02), (.02, -.02), (.02, .02), (-.02, .02))]
            inner = [bm.verts.new((x, y, 0)) for x, y in
                     ((-.01, -.01), (.01, -.01), (.01, .01), (-.01, .01))]
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new((outer[i], outer[j], inner[j], inner[i]))
            bmesh.ops.triangulate(bm, faces=list(bm.faces))
            loops = gp.final_planar_contact_loops(bm, Vector(), Vector((0, 0, 1)), 1000)
            f = gc.build_cut_interface(Vector(), Vector((0, 0, 1)), [],
                                      boundary_loops_world=loops)
            self.assertEqual(len(f.outer_contours_uv), 1)
            self.assertEqual(len(f.hole_contours_uv), 1)
            self.assertAlmostEqual(f.area_mm2, 1200, delta=.002)
        finally:
            bm.free()

    def test_invalid_contact_does_not_fabricate_polygon(self):
        bm = bmesh.new()
        try:
            # Two caps touching at one vertex have a branching perimeter.
            shared = bm.verts.new((0, 0, 0))
            for points in (((.01, 0, 0), (0, .01, 0)),
                           ((-.01, 0, 0), (0, -.01, 0))):
                bm.faces.new((shared, *(bm.verts.new(p) for p in points)))
            with self.assertRaises(gp.PlaneSliceError):
                gp.final_planar_contact_loops(bm, Vector(), Vector((0, 0, 1)), 1000)
        finally:
            bm.free()

    def test_common_domain_intersects_crossing_rectangles_and_holes(self):
        def rect(x0, x1, y0, y1, z):
            return [Vector((x/1000, y/1000, z/1000))
                    for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
        a = [rect(-10, 5, -10, 10, 0), rect(-2, 2, -2, 2, 0)]
        b = [rect(-5, 10, -5, 5, .1)]
        f = gp.common_planar_interface(a, b, Vector(), Vector((0,0,1)), 1000)
        self.assertAlmostEqual(f.area_mm2, 84, delta=.002)
        self.assertEqual(len(f.outer_contours_uv), 1)
        self.assertEqual(len(f.hole_contours_uv), 1)
        # Intersection, not simply the smaller polygon (B has area 150).

    def test_common_domain_preserves_islands_and_empty_overlap(self):
        def square(x):
            return [Vector((x+u, v, 0)) for u,v in
                    ((-.01,-.01),(.01,-.01),(.01,.01),(-.01,.01))]
        loops = [square(-.03), square(.03)]
        f = gp.common_planar_interface(loops, loops, Vector(), Vector((0,0,1)), 1000)
        self.assertEqual(len(f.outer_contours_uv), 2)
        self.assertAlmostEqual(f.area_mm2, 800, delta=.002)
        empty = gp.common_planar_interface([square(-.03)], [square(.03)],
                                           Vector(), Vector((0,0,1)), 1000)
        self.assertEqual(empty.outer_contours_uv, [])
        self.assertEqual(empty.area_mm2, 0)

    @unittest.skipUnless(os.environ.get('SPLITTER_PLATE_FIXTURE'), 'private plate fixture')
    def test_actual_plate_small_offsets_and_pedestal_clearance(self):
        s = self.plate_settings()
        for offset, gap in ((.03,0),(.03,.1),(.06,.1),(.11,.1)):
            for inverted in (False, True):
                for destination in ('PART','CAVITY','BOTH'):
                    with self.subTest(offset=offset,gap=gap,inverted=inverted,destination=destination):
                        s.plane_offset_mm = offset
                        s.part_clearance_mm = gap
                        s.invert_sides = inverted
                        s.part_clearance_apply_to = destination
                        p = cs.prepare_split_candidates(bpy.context, True)
                        self.assertGreater(p.interface.area_mm2, 780)
                        self.assertLess(p.interface.area_mm2, 810)
                        points = [p.interface.uv_to_world(*uv)
                                  for loop in p.interface.outer_contours_uv for uv in loop]
                        self.assertLessEqual(max(abs(w.y) for w in points)*1000, 3.001)
                        s.connector_distribution = 'GRID_4'
                        with self.assertRaises(Exception) as failure:
                            cs.prepared_connector_layout(p, s, s.target_object)
                        self.assertIn('GRID_4', str(failure.exception))
                        s.connector_distribution = 'MANUAL'
                        s.manual_connectors.clear()
                        for x,y in ((-40,0),(0,0),(40,0),(40,15)):
                            c=s.manual_connectors.add()
                            c.u_mm,c.v_mm=p.world_to_uv_mm(Vector((x/1000,y/1000,p.surface_origin.z)))
                        validity=[r['is_valid'] for r in cs.evaluate_connector_specs(p,s)]
                        self.assertEqual(validity,[True,True,True,False])

    @unittest.skipUnless(os.environ.get('SPLITTER_PLATE_FIXTURE'), 'private plate fixture')
    def test_actual_plate_manual_pins_both_sides(self):
        s = self.plate_settings()
        obj = s.target_object
        before = [(tuple(v.co)) for v in obj.data.vertices]
        for inverted in (False, True):
            for destination in ('PART', 'CAVITY', 'BOTH'):
                for male in ('A', 'B'):
                    with self.subTest(inverted=inverted, destination=destination, male=male):
                        s.invert_sides = inverted
                        s.part_clearance_apply_to = destination
                        s.connector_male_part = male
                        p = cs.prepare_split_candidates(bpy.context, True)
                        self.assertAlmostEqual(p.interface.area_mm2, 799 if inverted else 798,
                                               delta=2)
                        points = cs.generate_positioning_grid_points(p)
                        self.assertLess(min(w.x for _, _, w in points), -.06)
                        self.assertGreater(max(w.x for _, _, w in points), .06)
                        s.manual_connectors.clear()
                        for x in (-40, 0, 40):
                            c = s.manual_connectors.add()
                            c.u_mm, c.v_mm = p.world_to_uv_mm(
                                Vector((x / 1000, 0, p.surface_origin.z)))
                        result = cs.evaluate_connector_specs(p, s)
                        self.assertEqual(len(result), 3)
                        self.assertTrue(all(r['is_valid'] for r in result), result)
        self.assertEqual(before, [tuple(v.co) for v in obj.data.vertices])

    @unittest.skipUnless(os.environ.get('SPLITTER_PLATE_FIXTURE'), 'private plate fixture')
    def test_actual_plate_three_pin_preview(self):
        s = self.plate_settings()
        s.plane_offset_mm = .03
        before = [tuple(v.co) for v in s.target_object.data.vertices]
        p = cs.prepare_split_candidates(bpy.context, True)
        s.manual_connectors.clear()
        for x in (-40, 0, 40):
            c = s.manual_connectors.add()
            c.u_mm, c.v_mm = p.world_to_uv_mm(
                Vector((x / 1000, 0, p.surface_origin.z)))
        result = bpy.ops.chest.splitter_confirm_manual_connectors()
        self.assertIn('FINISHED', result)
        self.assertEqual(s.session_status, 'PREVIEW_VALID')
        constants = importlib.import_module(ROOT.name + '.src.constants')
        for name in (constants.PREVIEW_A_NAME, constants.PREVIEW_B_NAME):
            obj = bpy.data.objects.get(name)
            self.assertIsNotNone(obj)
            bm = bmesh.new()
            try:
                bm.from_mesh(obj.data)
                self.assertTrue(all(e.is_manifold for e in bm.edges))
                self.assertGreater(abs(bm.calc_volume()), 0)
            finally:
                bm.free()
        self.assertEqual(before, [tuple(v.co) for v in s.target_object.data.vertices])


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
