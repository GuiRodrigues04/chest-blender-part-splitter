"""Regression with exact coordinates/topology from the user's Padrão 1.blend.
The neutral JSON fixture avoids loading a Blender 5.2 UI layout in older versions.
"""
import unittest,json,sys
from pathlib import Path
import bpy
from mathutils import Matrix
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
from src import geometry_material as gm

class UserMesh0812(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        data=json.loads((Path(__file__).parent/'fixtures/padrao1_mesh.json').read_text())
        mesh=bpy.data.meshes.new('UserMesh');mesh.from_pydata(data['vertices'],[],data['faces']);mesh.update()
        self.obj=bpy.data.objects.new('UserMesh',mesh);bpy.context.scene.collection.objects.link(self.obj)
        self.obj.matrix_world=Matrix(data['matrix_world'])
        for m in data['materials']:
            mat=bpy.data.materials.new(m['name']);mat.diffuse_color=m['color'];mesh.materials.append(mat)
        for p,i in zip(mesh.polygons,data['material_indices']):p.material_index=i
        bpy.context.view_layer.update()
    def test_planar_relief_previously_cracked_by_float_accumulation(self):
        for mode in ['BASE','EXTRUDE']:
            with self.subTest(mode=mode):
                result=gm.slice_mesh_by_material(self.obj,4,3,scene=bpy.context.scene,extraction_mode=mode)
                try:
                    self.assertTrue(result.split_result.part_a_metrics['is_manifold'])
                    self.assertTrue(result.split_result.part_b_metrics['is_manifold'])
                    self.assertGreater(result.split_result.part_a_metrics['volume_mm3'],1)
                finally:result[0].free();result[1].free()
    def test_all_funciona_regions_accept_depth(self):
        for region in range(len(gm.list_material_regions(self.obj,2))):
            with self.subTest(region=region):
                result=gm.slice_mesh_by_material(self.obj,2,3,scene=bpy.context.scene,region_index=region)
                try:
                    self.assertTrue(result.split_result.part_a_metrics['is_manifold'])
                    self.assertTrue(result.split_result.part_b_metrics['is_manifold'])
                finally:result[0].free();result[1].free()
    def test_supported_nonplanar_critical_region_is_closed(self):
        result=gm.slice_mesh_by_material(self.obj,3,3,scene=bpy.context.scene,region_index=0)
        try:
            for metrics in (result.split_result.part_a_metrics, result.split_result.part_b_metrics):
                self.assertTrue(metrics['is_manifold'])
                self.assertGreater(metrics['volume_mm3'], 0)
        finally:
            result[0].free();result[1].free()

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
