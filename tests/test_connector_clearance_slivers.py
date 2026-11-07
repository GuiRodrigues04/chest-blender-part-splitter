"""Regression for Mesa's four post-Boolean slivers with 0.1 mm part clearance."""
import json
import math
from pathlib import Path
import sys
import unittest

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import src
from src.diagnostic import sanitize_mesh_micro_degeneracies, validate_bmesh_mesh_geometry


class ConnectorClearanceSlivers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def setUp(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.scene.unit_settings.scale_length = 1
        self.settings = bpy.context.scene.chest_splitter

    def target(self, simple=False):
        if simple:
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=.04)
            bm.normal_update()
            top = [f for f in bm.faces if f.normal.z > .9]
            bmesh.ops.subdivide_edges(bm, edges=list({e for f in top for e in f.edges}),
                                     cuts=2, use_grid_fill=True)
            bm.normal_update()
            for face in bm.faces:
                c = face.calc_center_median()
                face.material_index = int(face.normal.z > .9 and abs(c.x) < .01 and abs(c.y) < .01)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            mesh = bpy.data.meshes.new('TiltedControl')
            bm.to_mesh(mesh)
            bm.free()
        else:
            fixture = json.loads((ROOT / 'tests/fixtures/mesa_connector_clearance.json').read_text())
            mesh = bpy.data.meshes.new('Mesa')
            mesh.from_pydata(fixture['vertices'], [], fixture['faces'])
            for f, mat in zip(mesh.polygons, fixture['materials']):
                f.material_index = mat
        for i in range(2):
            mesh.materials.append(bpy.data.materials.new('Material' + str(i)))
        obj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        if simple:
            obj.rotation_euler.x = math.atan(.25)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.context.view_layer.update()
        s = self.settings
        s.target_object = obj
        for key, val in dict(split_mode='MATERIAL', material_split_index=int(simple),
                             material_region_index=0, material_extraction_mode='EXTRUDE',
                             material_extrude_depth_mm=5., connector_enabled=False,
                             connector_distribution='AUTO_SHAPE', connector_type='CYLINDER',
                             connector_male_part='A', connector_diameter_mm=5.,
                             connector_length_mm=2., connector_chamfer_mm=.2,
                             clearance_per_side_mm=.1, end_clearance_mm=.1,
                             connector_edge_margin_mm=4., part_clearance_mm=.1,
                             part_clearance_apply_to='PART', part_clearance_bottom_enable=False).items():
            setattr(s, key, val)
        return obj

    def assert_valid(self, obj):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        try:
            report = validate_bmesh_mesh_geometry(bm, 1000)
            self.assertTrue(report['is_valid'], str(report))
            self.assertTrue(report['is_manifold'], str(report))
            self.assertGreater(report['volume_mm3'], 0)
        finally:
            bm.free()

    def run_preview(self):
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')
        parts = [o for o in bpy.context.scene.objects if o.get('chest_role') in ('PREVIEW_A', 'PREVIEW_B')]
        self.assertEqual(len(parts), 2)
        for obj in parts:
            self.assert_valid(obj)
        volumes = {}
        for obj in parts:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            volumes[obj.get('chest_role')] = bm.calc_volume(signed=True) * 1e9
            bm.free()
        return volumes

    def test_mesa_clearance_and_connectors(self):
        target = self.target()
        original = ([tuple(v.co) for v in target.data.vertices],
                    [(tuple(f.vertices), f.material_index) for f in target.data.polygons])
        self.assert_valid(target)
        baseline = self.run_preview()
        self.settings.connector_enabled = True
        for distribution, male, chamfer in [('AUTO_SHAPE', 'A', .2), ('CENTER', 'A', .2),
                                             ('AUTO_SHAPE', 'B', .2), ('AUTO_SHAPE', 'A', 0.)]:
            with self.subTest(distribution=distribution, male=male, chamfer=chamfer):
                self.settings.connector_distribution = distribution
                self.settings.connector_male_part = male
                self.settings.connector_chamfer_mm = chamfer
                volumes = self.run_preview()
                # A valid preview alone could silently contain no connectors.
                # Verify the male gained material and the female lost material.
                for side in ('A', 'B'):
                    role = 'PREVIEW_' + side
                    delta = volumes[role] - baseline[role]
                    self.assertGreater(delta if side == male else -delta, 1.)
        self.assertEqual(original, ([tuple(v.co) for v in target.data.vertices],
                                   [(tuple(f.vertices), f.material_index) for f in target.data.polygons]))

    def test_simple_tilted_control(self):
        self.target(simple=True)
        self.settings.connector_distribution = 'CENTER'
        self.settings.connector_edge_margin_mm = 1.
        self.run_preview()
        self.settings.connector_enabled = True
        self.run_preview()

    def test_does_not_erase_small_real_facets(self):
        bm = bmesh.new()
        try:
            bmesh.ops.create_cube(bm, size=1e-6)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            before = (len(bm.verts), len(bm.edges), len(bm.faces), bm.calc_volume(signed=True))
            self.assertFalse(sanitize_mesh_micro_degeneracies(bm, 1000))
            self.assertEqual(before, (len(bm.verts), len(bm.edges), len(bm.faces), bm.calc_volume(signed=True)))
        finally:
            bm.free()

    def test_unsafe_cleanup_rolls_back(self):
        bm = bmesh.new()
        try:
            verts = [bm.verts.new(p) for p in ((0, 0, 0), (.001, 0, 0), (.002, 0, 0))]
            bm.faces.new(verts)
            before = ([tuple(v.co) for v in bm.verts], len(bm.faces))
            self.assertFalse(sanitize_mesh_micro_degeneracies(bm, 1000))
            self.assertEqual(before, ([tuple(v.co) for v in bm.verts], len(bm.faces)))
        finally:
            bm.free()


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
