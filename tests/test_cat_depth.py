"""Private-file regression: explicit depth must move the cat nose interface.

Run in Blender; SPLITTER_CAT_BLEND can point to the user-provided source.
The model is read without scripts and is never saved by this test.
"""
from pathlib import Path
import os, sys, unittest
import bpy, bmesh
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src
from src.geometry_material import slice_mesh_by_material
from src.geometry_plane import evaluate_bmesh_metrics

SOURCE = Path(os.environ.get('SPLITTER_CAT_BLEND', r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\Placas - Modelos 3D\Teste Gato.blend'))

@unittest.skipUnless(SOURCE.is_file(), 'Private cat blend not available')
class CatDepth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        cls.obj = bpy.context.scene.chest_splitter.target_object

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def test_nose_depth_moves_interface_and_preserves_surface_and_volume(self):
        obj = self.obj
        before = obj.data.copy()
        source_bm = bmesh.new(); source_bm.from_mesh(obj.data)
        volume = evaluate_bmesh_metrics(source_bm, 1000)['volume_mm3']
        source_bm.free()
        surface = {tuple(obj.matrix_world @ obj.data.vertices[i].co)
                   for f in obj.data.polygons if f.material_index == 2 for i in f.vertices}
        origins = []
        try:
            for depth in (5., 20.):
                result = slice_mesh_by_material(obj, 2, depth, scene=bpy.context.scene,
                                                region_index=0, interface_mat_mode='EXTRACTED')
                try:
                    metrics = [evaluate_bmesh_metrics(bm, 1000) for bm in result]
                    for m in metrics:
                        self.assertTrue(m['is_manifold'], m)
                        self.assertEqual(m['components'], 1)
                    self.assertAlmostEqual(sum(m['volume_mm3'] for m in metrics), volume, delta=.1)
                    extracted = {tuple(v.co) for v in result[0].verts}
                    # Check the selected nose surface, excluding the separate ears.
                    nose = {co for co in surface if .48 < co[2] < .55}
                    self.assertGreater(len(nose), 50)
                    self.assertTrue(nose.issubset(extracted))
                    origins.append(Vector(result.interface.origin_world))
                finally:
                    for bm in result: bm.free()
            self.assertAlmostEqual((origins[1]-origins[0]).length*1000, 15., delta=.01)
            self.assertEqual([tuple(v.co) for v in obj.data.vertices], [tuple(v.co) for v in before.vertices])
            self.assertEqual([tuple(p.vertices) for p in obj.data.polygons], [tuple(p.vertices) for p in before.polygons])
            self.assertEqual([p.material_index for p in obj.data.polygons], [p.material_index for p in before.polygons])
        finally:
            bpy.data.meshes.remove(before)

if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
