"""Loop capture on Mesa selection slivers, split imports and real islands."""
import json
from pathlib import Path
import sys
import unittest

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import src
from src.geometry_loop import capture_face_boundary_loop, capture_edge_loop
from src.diagnostic import validate_bmesh_mesh_geometry


class LoopCaptureSelectionGaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def setUp(self):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.scene.unit_settings.scale_length = 1

    def tearDown(self):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

    def edit(self, mesh):
        obj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.context.scene.chest_splitter.target_object = obj
        bpy.context.scene.chest_splitter.split_mode = 'LOOP'
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        bpy.ops.object.mode_set(mode='EDIT')
        return obj, bmesh.from_edit_mesh(mesh)

    def mesa(self, split=False, minimum=0., units=1000):
        data = json.loads((ROOT / 'tests/fixtures/mesa_connector_clearance.json').read_text())
        mesh = bpy.data.meshes.new('Mesa')
        points = [[c * 1000 / units for c in p] for p in data['vertices']]
        if split:
            vertices = [points[i] for f in data['faces'] for i in f]
            faces = [list(range(i, i+3)) for i in range(0, len(vertices), 3)]
        else:
            vertices, faces = points, data['faces']
        mesh.from_pydata(vertices, [], faces)
        for i in range(2):
            mesh.materials.append(bpy.data.materials.new('Mat' + str(i)))
        for face, material in zip(mesh.polygons, data['materials']):
            face.material_index = material
        bpy.context.scene.unit_settings.scale_length = units / 1000
        obj, bm = self.edit(mesh)
        for element in list(bm.faces) + list(bm.edges) + list(bm.verts):
            element.select_set(False)
        for face in bm.faces:
            if face.material_index == 0 and face.calc_area() * units**2 >= minimum:
                face.select_set(True)
        bm.select_flush_mode()
        bmesh.update_edit_mesh(mesh)
        return obj, bm

    @staticmethod
    def signature(bm):
        bm.verts.index_update()
        return ([tuple(v.co) for v in bm.verts],
                [(tuple(v.index for v in f.verts), f.material_index) for f in bm.faces])

    def test_mesa_micro_omission_is_bridged_without_changing_mesh(self):
        obj, bm = self.mesa(minimum=.01)
        self.assertEqual(sum(f.select for f in bm.faces), 80)
        original = self.signature(bm)
        self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(), {'FINISHED'})
        bm = bmesh.from_edit_mesh(obj.data)
        self.assertEqual(original, self.signature(bm))
        self.assertTrue(all(e.is_manifold for e in bm.edges))
        self.assertEqual(sum(e.select for e in bm.edges), 83)
        self.assertEqual(tuple(bpy.context.tool_settings.mesh_select_mode), (False, True, False))
        self.assertFalse(any(f.select for f in bm.faces))
        result = capture_edge_loop(obj)
        self.assertTrue(result[0], str(result))

    def test_full_material_selection_is_a_valid_loop(self):
        obj, bm = self.mesa()
        bm.faces.ensure_lookup_table()
        bm.faces.active = bm.faces[33]
        original = self.signature(bm)
        result = capture_face_boundary_loop(obj)
        self.assertTrue(result[0], str(result))
        self.assertEqual(len(result[1]), 86)
        self.assertEqual(result[4], 33)
        self.assertEqual(original, self.signature(bm))

    def test_captured_region_can_be_cut_with_clearance_and_pins(self):
        obj, bm = self.mesa(minimum=.01)
        self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(), {'FINISHED'})
        bpy.ops.object.mode_set(mode='OBJECT')
        settings = bpy.context.scene.chest_splitter
        settings.loop_behavior = 'EXTRUDE'
        settings.loop_extrude_depth_mm = 5.
        settings.part_clearance_mm = .1
        settings.connector_enabled = True
        settings.connector_distribution = 'CENTER'
        settings.connector_diameter_mm = 5.
        settings.connector_length_mm = 2.
        settings.connector_chamfer_mm = .2
        settings.clearance_per_side_mm = .1
        settings.end_clearance_mm = .1
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
        self.assertTrue(settings.part_a_is_manifold)
        self.assertTrue(settings.part_b_is_manifold)

    def test_split_triangle_import_is_welded_only_after_success(self):
        obj, bm = self.mesa(split=True)
        self.assertGreater(len(bm.verts), 94)
        result = capture_face_boundary_loop(obj)
        self.assertTrue(result[0], str(result))
        bm = bmesh.from_edit_mesh(obj.data)
        self.assertEqual(len(bm.verts), 94)
        report = validate_bmesh_mesh_geometry(bm, 1000)
        self.assertTrue(report['is_valid'], str(report))
        self.assertTrue(report['is_manifold'], str(report))

    def test_physical_units_do_not_change_gap_completion(self):
        obj, bm = self.mesa(minimum=.01, units=1)
        result = capture_face_boundary_loop(obj)
        self.assertTrue(result[0], str(result))
        self.assertEqual(len(result[1]), 83)

    def test_real_islands_are_rejected_without_welding_close_walls(self):
        mesh = bpy.data.meshes.new('SeparateCloseTriangles')
        # A 0.01 mm gap was incorrectly welded by the old 0.05 mm fallback.
        mesh.from_pydata([(0,0,0),(.001,0,0),(0,.001,0),
                          (.00101,0,0),(.00201,0,0),(.00101,.001,0)], [], [(0,1,2),(3,4,5)])
        obj, bm = self.edit(mesh)
        for f in bm.faces:
            f.select_set(True)
        original = self.signature(bm)
        result = capture_face_boundary_loop(obj)
        self.assertFalse(result[0])
        self.assertEqual(original, self.signature(bm))
        self.assertEqual(sum(f.select for f in bm.faces), 2)

    def test_failed_split_import_capture_does_not_mutate_source(self):
        obj, bm = self.mesa(split=True)
        # Select distant triangles only, which remain genuinely disconnected.
        for f in bm.faces:
            f.select = False
        bm.faces.ensure_lookup_table()
        bm.faces[0].select = True
        bm.faces[40].select = True
        original = self.signature(bm)
        result = capture_face_boundary_loop(obj)
        self.assertFalse(result[0], str(result))
        self.assertEqual(original, self.signature(bm))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
