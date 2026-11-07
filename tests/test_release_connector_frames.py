"""Connector frame regressions. Run with Blender --background --python this file."""
import importlib
import sys
import unittest
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
addon = importlib.import_module(ROOT.name)
addon.register()
gl = importlib.import_module(ROOT.name + ".src.geometry_loop")
cs = importlib.import_module(ROOT.name + ".src.connector_surface")
contract = importlib.import_module(ROOT.name + ".src.geometry_contract")


def loop_fixture():
    vertices = [
        (x, y, z)
        for z in (-0.05, 0.0, 0.05)
        for x, y in ((-0.05, -0.05), (0.05, -0.05), (0.05, 0.05), (-0.05, 0.05))
    ]
    faces = [(3, 2, 1, 0), (8, 9, 10, 11)]
    for ring in (0, 4):
        for i in range(4):
            faces.append((ring + i, ring + (i + 1) % 4,
                          ring + 4 + (i + 1) % 4, ring + 4 + i))
    mesh = bpy.data.meshes.new("connector_frame_fixture")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("connector_frame_fixture", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    settings = bpy.context.scene.chest_splitter
    settings.target_object = obj
    settings.split_mode = 'LOOP'
    settings.loop_behavior = 'DETACH'
    settings.loop_vertex_indices = '4,5,6,7'
    settings.loop_seed_face_index = 1
    settings.part_clearance_apply_to = 'PART'
    settings.part_clearance_bottom_enable = False
    settings.connector_distribution = 'MANUAL'
    return obj, settings


class ReleaseConnectorFrames(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 1.0
        addon.register()
        cs.clear_prepared_split_cache()

    def prepare(self, obj, settings, gap, male, bottom=None):
        settings.part_clearance_mm = gap
        settings.connector_male_part = male
        settings.part_clearance_bottom_enable = bottom is not None
        settings.part_clearance_bottom_mm = bottom or 0.0
        result = gl.slice_mesh_by_loop(
            obj, obj.name, [4, 5, 6, 7], 1,
            part_clearance_mm=gap, part_clearance_apply_to='PART',
            part_clearance_bottom_mm=bottom)
        try:
            prepared = cs.cache_prepared_interface(bpy.context, result.interface)
            return prepared, prepared.uv_mm_to_world(5.0, 3.0).copy()
        finally:
            for bm in result:
                bm.free()

    def test_manual_uv_stays_in_place_across_clearance_and_male_flip(self):
        obj, settings = loop_fixture()
        p0, point0 = self.prepare(obj, settings, 0.0, 'A')
        p1, point1 = self.prepare(obj, settings, 1.0, 'A')
        p2, point2 = self.prepare(obj, settings, 1.0, 'B')

        # PART clearance changes only the insertion-axis position; changing the
        # selected male side must also retain the same canonical UV coordinates.
        self.assertLess((point1 - point0).cross(p1.surface_normal).length * 1000.0, 0.01)
        self.assertLess((point2 - point1).cross(p1.surface_normal).length * 1000.0, 0.01)
        self.assertAlmostEqual(abs((point2 - point1).dot(p1.surface_normal)) * 1000.0,
                               1.0, delta=0.02)
        self.assertGreater(p0.interface.axis_u_world.dot(p1.interface.axis_u_world), 0.99999)
        self.assertGreater(p1.interface.axis_u_world.dot(p2.interface.axis_u_world), 0.99999)

    def test_bottom_clearance_does_not_change_manual_uv_anchor(self):
        obj, settings = loop_fixture()
        _, point0 = self.prepare(obj, settings, 1.0, 'A', bottom=0.0)
        prepared, point1 = self.prepare(obj, settings, 1.0, 'A', bottom=0.75)
        self.assertLess((point1 - point0).cross(prepared.surface_normal).length * 1000.0, 0.01)

    def test_selected_contact_patch_keeps_holes_for_both_sides(self):
        outer = [Vector((x, y, 0.0)) for x, y in
                 ((-0.02, -0.02), (0.02, -0.02), (0.02, 0.02), (-0.02, 0.02))]
        inner = [Vector((x, y, 0.0)) for x, y in
                 ((-0.004, -0.004), (0.004, -0.004), (0.004, 0.004), (-0.004, 0.004))]
        triangles = []
        for i in range(4):
            j = (i + 1) % 4
            triangles.extend(((outer[i], outer[j], inner[j]),
                              (outer[i], inner[j], inner[i])))
        iface = contract.build_cut_interface(
            Vector(), Vector((0, 0, 1)), outer, interface_triangles=triangles,
            unit_scale=1000, boundary_loops_world=[outer, inner], source_mode='LOOP')
        patch_a = dict(origin=Vector((0.0, 0.0, 0.001)), normal=Vector((0, 0, 1)),
                       boundary=[p + Vector((0, 0, 0.001)) for p in outer],
                       loops=[[p + Vector((0, 0, 0.001)) for p in ring]
                              for ring in (outer, inner)],
                       triangles=[tuple(p + Vector((0, 0, 0.001)) for p in tri)
                                  for tri in triangles])
        patch_b = dict(origin=Vector((0.0, 0.0, -0.001)), normal=Vector((0, 0, -1)),
                       boundary=[p + Vector((0, 0, -0.001)) for p in outer],
                       loops=[[p + Vector((0, 0, -0.001)) for p in ring]
                              for ring in (outer, inner)],
                       triangles=[tuple(p + Vector((0, 0, -0.001)) for p in tri)
                                  for tri in triangles])
        iface.clearance_applied = True
        iface.final_contact_a = patch_a
        iface.final_contact_b = patch_b
        _, settings = loop_fixture()
        for side in ('A', 'B'):
            settings.connector_male_part = side
            prepared = cs.cache_prepared_interface(bpy.context, iface)
            self.assertEqual(len(prepared.interface.hole_contours_uv), 1)
            hit = cs.raycast_connector_surface(Vector((0, 0, 0.01)),
                                               Vector((0, 0, -1)), prepared)
            self.assertIsNone(hit)
            hit = cs.raycast_connector_surface(Vector((0.01, 0, 0.01)),
                                               Vector((0, 0, -1)), prepared)
            self.assertIsNotNone(hit)

    def test_nonplanar_patch_keeps_nominal_uv_axis(self):
        outer = [Vector((-0.02, -0.01, 0)), Vector((0.02, -0.01, 0)),
                 Vector((0.02, 0.01, 0)), Vector((-0.02, 0.01, 0))]
        triangles = [
            (outer[0], outer[1], Vector((0, 0, 0.001))),
            (outer[1], outer[2], Vector((0, 0, 0.001))),
            (outer[2], outer[3], Vector((0, 0, 0.001))),
            (outer[3], outer[0], Vector((0, 0, 0.001))),
        ]
        iface = contract.build_cut_interface(
            Vector(), Vector((0, 0, 1)), outer, interface_triangles=triangles,
            boundary_loops_world=[outer], unit_scale=1000, source_mode='LOOP')
        iface.is_planar = False
        iface.deviation_mm = 1.0
        iface.clearance_applied = True
        iface.final_contact_a = dict(origin=Vector((0.003, 0, 0.001)),
                                     normal=Vector((0, 0, 1)), boundary=outer,
                                     loops=[outer], triangles=triangles)
        iface.final_contact_b = iface.final_contact_a
        _, settings = loop_fixture()
        settings.connector_male_part = 'A'
        prepared = cs.cache_prepared_interface(bpy.context, iface)
        self.assertGreater(prepared.axis_u.dot(iface.axis_u_world), 0.99999)
        self.assertFalse(prepared.is_planar)
        lifted = prepared.uv_mm_to_world(0.0, 0.0)
        self.assertAlmostEqual(lifted.z, 0.001, delta=1e-6)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseConnectorFrames)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
