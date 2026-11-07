import sys,unittest
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
class ConnectorsState092(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def test_target_change_and_saved_values(self):
  bpy.ops.wm.read_factory_settings(use_empty=True)
  s=bpy.context.scene.chest_splitter
  self.assertAlmostEqual(s.connector_edge_margin_mm,.4)
  s.split_mode='MATERIAL';s.material_extraction_mode='WHOLE'
  bpy.ops.mesh.primitive_cube_add();a=bpy.context.object
  bpy.ops.mesh.primitive_cube_add();b=bpy.context.object
  s.target_object=a;s.contact_patch_index=0;s.connector_enabled=True
  s.target_object=a
  self.assertTrue(s.connector_enabled)
  s.connector_edge_margin_mm=.8;s.target_object=b
  self.assertFalse(s.connector_enabled);self.assertEqual(s.contact_patch_index,-1)
  self.assertAlmostEqual(s.connector_edge_margin_mm,.8)
  s.split_mode='PLANE';s.connector_enabled=True;s.target_object=a
  self.assertTrue(s.connector_enabled)
if __name__=='__main__':
 r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ConnectorsState092))
 if not r.wasSuccessful():raise RuntimeError('Regression failed')
