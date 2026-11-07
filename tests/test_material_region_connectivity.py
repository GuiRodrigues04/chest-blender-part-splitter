"""Coincidence grouping may merge topological islands, never fragment them."""
import sys,unittest
from pathlib import Path
import bpy,bmesh
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
from src.geometry_material import get_material_regions,analyze_material_structure
from src.diagnostic import validate_bmesh_mesh_geometry
class RegionConnectivity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def test_collapsed_spatial_cluster_retains_topological_links(self):
  bm=bmesh.new()
  try:
   verts=[bm.verts.new(co) for co in ((0,0,0),(.00001,0,0),(0,.00001,0),(0,-.01,0),(1,0,0),(2,0,0),(1,1,0))]
   for ids in ((0,1,2),(1,0,3),(4,5,6)):bm.faces.new([verts[i] for i in ids])
   bm.verts.index_update();bm.faces.index_update()
   self.assertEqual(get_material_regions(bm,0,tol=0.),[[0,1],[2]])
   self.assertEqual(get_material_regions(bm,0),[[0,1],[2]])
  finally:bm.free()
 def test_qr_real_regions_do_not_fragment_and_source_issues_remain_visible(self):
  filename=Path(r'C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_QR_Inclinada_Chest_Inteira.blend')
  if not filename.exists():
   filename=Path(r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_QR_Inclinada_Chest_Inteira.blend')
  if not filename.exists():self.skipTest('Private QR fixture missing')
  with bpy.data.libraries.load(str(filename)) as (a,b):b.objects=['Placa_QR_Inclinada_Chest_Inteira']
  obj=b.objects[0];bpy.context.scene.collection.objects.link(obj)
  original=[tuple(v.co) for v in obj.data.vertices]
  bm=bmesh.new();bm.from_mesh(obj.data)
  try:
   for mat in (0,1):self.assertEqual(get_material_regions(bm,mat),get_material_regions(bm,mat,tol=0.))
   self.assertEqual([len(g) for g in get_material_regions(bm,0)],[443,2,4])
   report=validate_bmesh_mesh_geometry(bm,1000)
   self.assertTrue(report['is_manifold']);self.assertFalse(report['is_valid']);self.assertEqual(len(report['degenerate_faces']),2)
  finally:bm.free()
  analysis=analyze_material_structure(obj,0)
  self.assertTrue(analysis['valid'],str(analysis.get('error')))
  self.assertEqual(analysis['region_count'],3)
  self.assertEqual(original,[tuple(v.co) for v in obj.data.vertices])
if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
