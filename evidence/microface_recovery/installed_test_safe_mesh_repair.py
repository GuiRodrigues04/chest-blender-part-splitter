"""Safety regressions for the target-mesh repair operator."""
import sys
import json
import unittest
from pathlib import Path

import bmesh
import bpy

sys.path.insert(0,'C:\\Users\\guiro\\AppData\\Roaming\\Blender Foundation\\Blender\\5.2\\extensions\\user_default')
import chest_part_splitter as src
from chest_part_splitter.src.diagnostic import validate_bmesh_mesh_geometry


class SafeMeshRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.settings = bpy.context.scene.chest_splitter

    def _target(self, mesh):
        obj = bpy.data.objects.new("RepairTarget", mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        self.settings.target_object = obj
        return obj

    @staticmethod
    def _geometry(obj):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        report = validate_bmesh_mesh_geometry(bm, 1000.0)
        result = (len(bm.verts), len(bm.faces), len(report['non_manifold_edges']), report['is_valid'])
        bm.free()
        return result

    def _repair(self):
        return bpy.ops.chest.splitter_repair_target_mesh()

    def test_valid_closed_mesh_is_noop(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        self.settings.target_object = obj
        mesh_before = obj.data
        counts_before = self._geometry(obj)
        result = self._repair()
        self.assertEqual(result, {'CANCELLED'})
        self.assertIs(obj.data, mesh_before)
        self.assertEqual(self._geometry(obj), counts_before)
        self.assertIn("already valid", self.settings.last_status.lower())

    def test_real_arco_keeps_all_fine_details(self):
        fixture = Path('C:\\Users\\guiro\\.gemini\\antigravity\\scratch\\chest-blender-part-splitter\\tests\\fixtures') / 'arco_frame.json'
        data = json.loads(fixture.read_text())
        mesh = bpy.data.meshes.new('Arco')
        mesh.from_pydata(data['vertices'], [], data['faces'])
        mesh.update()
        obj = self._target(mesh)
        original = [tuple(v.co) for v in mesh.vertices]
        self.assertEqual(self._geometry(obj), (1054, 2104, 0, True))
        self.assertEqual(self._repair(), {'CANCELLED'})
        self.assertIs(obj.data, mesh)
        self.assertEqual(original, [tuple(v.co) for v in mesh.vertices])
        self.assertEqual(self._geometry(obj), (1054, 2104, 0, True))

    def test_exact_split_cube_seam_is_repaired(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        face = max(bm.faces, key=lambda f: f.normal.z)
        face_verts = list(face.verts)
        duplicates = {v: bm.verts.new(v.co.copy()) for v in face_verts}
        bmesh.ops.delete(bm, geom=[face], context='FACES_ONLY')
        bm.faces.new([duplicates[v] for v in face_verts])
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        self.settings.target_object = obj
        before = self._geometry(obj)
        self.assertGreater(before[2], 0)
        original_mesh = obj.data

        result = self._repair()

        self.assertEqual(result, {'FINISHED'})
        self.assertIsNot(obj.data, original_mesh)
        after = self._geometry(obj)
        self.assertEqual(after[2], 0)
        self.assertTrue(after[3])

    def test_real_open_hole_is_refused_and_source_preserved(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        face = max(bm.faces, key=lambda f: f.normal.z)
        bmesh.ops.delete(bm, geom=[face], context='FACES')
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        self.settings.target_object = obj
        original_mesh = obj.data
        original_counts = self._geometry(obj)

        result = self._repair()

        self.assertEqual(result, {'CANCELLED'})
        self.assertIs(obj.data, original_mesh)
        self.assertEqual(self._geometry(obj), original_counts)
        self.assertIn("preserved", self.settings.last_status.lower())

    def test_edit_mode_is_restored(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        self.settings.target_object = obj
        bpy.ops.object.mode_set(mode='EDIT')

        result = self._repair()

        self.assertEqual(result, {'CANCELLED'})
        self.assertEqual(obj.mode, 'EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')

    def test_nonactive_edit_target_is_restored(self):
        bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
        target = bpy.context.object
        target.name = "RepairTarget"
        bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
        other = bpy.context.object
        target.select_set(True)
        other.select_set(True)
        bpy.context.view_layer.objects.active = other
        self.settings.target_object = target
        bpy.ops.object.mode_set(mode='EDIT')

        result = self._repair()

        self.assertEqual(result, {'CANCELLED'})
        self.assertEqual(target.mode, 'EDIT')
        self.assertIs(bpy.context.view_layer.objects.active, other)
        bpy.ops.object.mode_set(mode='OBJECT')

    def test_scaled_object_repairs_candidate(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        obj.scale = (0.1, 2.0, 3.0)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        face = max(bm.faces, key=lambda f: f.normal.z)
        face_verts = list(face.verts)
        duplicates = {v: bm.verts.new(v.co.copy()) for v in face_verts}
        bmesh.ops.delete(bm, geom=[face], context='FACES_ONLY')
        bm.faces.new([duplicates[v] for v in face_verts])
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        self.settings.target_object = obj

        result = self._repair()

        self.assertEqual(result, {'FINISHED'})
        self.assertEqual(self._geometry(obj)[2], 0)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
