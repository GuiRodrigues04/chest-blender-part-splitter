"""Boolean wire leftovers must not invalidate otherwise closed output shells."""
from pathlib import Path
import sys,unittest
import bpy,bmesh
sys.path.insert(0,'C:\\Users\\guiro\\AppData\\Roaming\\Blender Foundation\\Blender\\5.2\\extensions\\user_default')
import chest_part_splitter as src
from chest_part_splitter.src.geometry_clearance import remove_boolean_wires
from chest_part_splitter.src.diagnostic import validate_bmesh_mesh_geometry

class BooleanWires(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def setUp(self):bpy.ops.wm.read_factory_settings(use_empty=True)
 def test_only_wires_removed_faces_materials_and_volume_unchanged(self):
  bpy.ops.mesh.primitive_cube_add(size=.04)
  bm=bmesh.new();bm.from_mesh(bpy.context.object.data)
  try:
   bm.faces.ensure_lookup_table();bm.faces[0].material_index=2
   shell=sorted((f.material_index,tuple(sorted(tuple(v.co) for v in f.verts))) for f in bm.faces)
   volume=bm.calc_volume()
   a=bm.verts.new((1,1,1));b=bm.verts.new((2,2,2));bm.edges.new((a,b));bm.verts.new((3,3,3))
   self.assertTrue(remove_boolean_wires(bm))
   self.assertEqual(len(bm.verts),8);self.assertEqual(len(bm.edges),12)
   self.assertEqual(shell,sorted((f.material_index,tuple(sorted(tuple(v.co) for v in f.verts))) for f in bm.faces))
   self.assertEqual(volume,bm.calc_volume());self.assertTrue(all(e.is_manifold for e in bm.edges))
   self.assertFalse(remove_boolean_wires(bm))
  finally:bm.free()
 def test_real_open_boundaries_are_never_removed_or_filled(self):
  bm=bmesh.new()
  try:
   vs=[bm.verts.new(co) for co in ((0,0,0),(1,0,0),(0,1,0))];bm.faces.new(vs)
   self.assertFalse(remove_boolean_wires(bm));self.assertEqual(len(bm.edges),3)
   self.assertTrue(all(len(e.link_faces)==1 for e in bm.edges))
  finally:bm.free()
 def test_qr_screenshot_depth_zero_gap_preview_commit(self):
  filename=Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_QR_Inclinada_Chest_Inteira.blend")
  if not filename.exists():self.skipTest('Private QR fixture unavailable')
  with bpy.data.libraries.load(str(filename)) as (a,b):b.objects=['Placa_QR_Inclinada_Chest_Inteira']
  obj=b.objects[0];bpy.context.scene.collection.objects.link(obj);obj.select_set(True);bpy.context.view_layer.objects.active=obj
  s=bpy.context.scene.chest_splitter;s.target_object=obj
  self.assertEqual(bpy.ops.chest.splitter_repair_target_mesh(),{'FINISHED'})
  original=([tuple(v.co) for v in obj.data.vertices],[tuple(f.vertices) for f in obj.data.polygons])
  bm=bmesh.new();bm.from_mesh(obj.data);source_volume=bm.calc_volume()*1e9;bm.free()
  s.split_mode='MATERIAL';s.material_split_index=0;s.material_region_index=0
  s.material_extraction_mode='EXTRUDE';s.material_extrude_depth_mm=.1
  s.assembly_clearance_preset='NONE';s.connector_enabled=False;s.commit_next_target='NONE'
  s.material_interface_mat_mode='EXTRACTED'
  from chest_part_splitter.src.operators import get_current_session_parts,verify_preview_current
  self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'},s.get_localized_status())
  self.assertTrue(verify_preview_current(bpy.context)[0])
  def volumes():
   parts=get_current_session_parts(bpy.context.scene);self.assertEqual(len(parts),2);result=[]
   for part in parts:
    bm=bmesh.new();bm.from_mesh(part.data)
    try:
     report=validate_bmesh_mesh_geometry(bm,1000)
     self.assertTrue(report['is_valid']);self.assertTrue(report['is_manifold'])
     self.assertGreater(report['volume_mm3'],0);result.append(report['volume_mm3'])
    finally:bm.free()
   return sorted(result)
  preview=volumes();self.assertAlmostEqual(sum(preview),source_volume,delta=.001)
  self.assertEqual(bpy.ops.chest.splitter_commit_parts(),{'FINISHED'},s.get_localized_status())
  self.assertEqual(preview,volumes())
  self.assertEqual(original,([tuple(v.co) for v in obj.data.vertices],[tuple(f.vertices) for f in obj.data.polygons]))

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
