"""Preserve tiny valid facets, repair only sub-tolerance slivers in copies."""
from pathlib import Path
import sys,unittest
import bpy,bmesh
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
from src.diagnostic import validate_bmesh_mesh_geometry,validate_mesh_repair_change,analyze_target_mesh

class MicrofaceRepair(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def setUp(self):bpy.ops.wm.read_factory_settings(use_empty=True)
 def load_qr(self):
  filename=Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_QR_Inclinada_Chest_Inteira.blend")
  if not filename.exists():self.skipTest('Private QR fixture missing')
  with bpy.data.libraries.load(str(filename)) as (a,b):b.objects=['Placa_QR_Inclinada_Chest_Inteira']
  obj=b.objects[0];bpy.context.scene.collection.objects.link(obj);obj.select_set(True);bpy.context.view_layer.objects.active=obj
  bpy.context.scene.chest_splitter.target_object=obj
  return obj
 def test_tiny_well_shaped_face_is_valid_but_collinear_is_not(self):
  for height,expected in [(1e-6,True),(1e-9,False)]:
   bm=bmesh.new()
   try:
    vs=[bm.verts.new(co) for co in [(0,0,0),(1e-6,0,0),(0,height,0)]]
    bm.faces.new(vs)
    self.assertEqual(validate_bmesh_mesh_geometry(bm,1000)['is_valid'],expected)
   finally:bm.free()
 def test_material_swap_is_refused_even_if_area_and_shape_match(self):
  bpy.ops.mesh.primitive_cube_add(size=.04)
  before=bmesh.new();before.from_mesh(bpy.context.object.data);before.faces.ensure_lookup_table()
  before.faces[0].material_index=1;before.faces[1].material_index=2
  after=before.copy();after.faces.ensure_lookup_table()
  after.faces[0].material_index=2;after.faces[1].material_index=1
  try:self.assertFalse(validate_mesh_repair_change(before,after,1000))
  finally:before.free();after.free()
 def test_qr_repair_preserves_source_datablock_and_passes_strict_checks(self):
  obj=self.load_qr();old_mesh=obj.data
  # Another object uses the original datablock: it must remain unchanged.
  shared=obj.copy();bpy.context.scene.collection.objects.link(shared)
  original=[tuple(v.co) for v in old_mesh.vertices]
  before=bmesh.new();before.from_mesh(old_mesh)
  self.assertEqual(len(validate_bmesh_mesh_geometry(before,1000)['degenerate_faces']),2)
  self.assertEqual(analyze_target_mesh(obj,bpy.context.scene)['degenerate_faces'],2)
  bpy.context.scene.chest_splitter.session_status='PREVIEW_VALID'
  self.assertEqual(bpy.ops.chest.splitter_repair_target_mesh(),{'FINISHED'})
  self.assertIs(shared.data,old_mesh);self.assertIsNot(obj.data,old_mesh)
  self.assertEqual(original,[tuple(v.co) for v in old_mesh.vertices])
  self.assertEqual(list(obj.data.materials),list(old_mesh.materials))
  after=bmesh.new();after.from_mesh(obj.data)
  try:
   report=validate_bmesh_mesh_geometry(after,1000)
   self.assertTrue(report['is_valid']);self.assertTrue(report['is_manifold'])
   self.assertTrue(validate_mesh_repair_change(before,after,1000))
  finally:before.free();after.free()
  self.assertEqual(bpy.context.scene.chest_splitter.session_status,'PREVIEW_STALE')
  self.assertEqual(bpy.context.scene.chest_splitter.diag_degenerate_faces,0)
 def test_show_faces_selects_only_strictly_degenerate_faces(self):
  obj=self.load_qr();original=[tuple(v.co) for v in obj.data.vertices]
  self.assertEqual(bpy.ops.chest.splitter_show_problem_faces(),{'FINISHED'})
  self.assertEqual(obj.mode,'EDIT')
  bm=bmesh.from_edit_mesh(obj.data)
  self.assertEqual(sum(f.select for f in bm.faces),2)
  bpy.ops.object.mode_set(mode='OBJECT')
  self.assertEqual(original,[tuple(v.co) for v in obj.data.vertices])
 def test_qr_fdm_clearance_failure_is_actionable_and_not_changed(self):
  obj=self.load_qr();self.assertEqual(bpy.ops.chest.splitter_repair_target_mesh(),{'FINISHED'})
  from src.geometry_material import slice_mesh_by_material
  from src.localized_errors import LocalizedGeometryError
  with self.assertRaises(LocalizedGeometryError) as caught:
   slice_mesh_by_material(obj,0,depth_mm=5,extraction_mode='EXTRUDE',part_clearance_mm=.1)
  self.assertEqual(caught.exception.payload['__splitter_message__'],'geometry.clearance_microfeatures')
  self.assertAlmostEqual(bpy.context.scene.chest_splitter.part_clearance_mm,.1)

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
