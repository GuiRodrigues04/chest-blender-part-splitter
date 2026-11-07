"""Regressions found by the all-plate commercial audit."""
from pathlib import Path
import sys,unittest
from unittest.mock import patch
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
from src.diagnostic import validate_bmesh_mesh_geometry,stable_signed_volume_mm3
from src.geometry_loop import captured_region_faces

class CommercialAuditFixes(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def setUp(self):bpy.ops.wm.read_factory_settings(use_empty=True)
 def chest(self):
  path=Path(r'C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_Chest_Inteira.blend')
  if not path.exists():self.skipTest('Private Chest fixture unavailable')
  with bpy.data.libraries.load(str(path)) as (a,b):b.objects=['Placa_Chest_Inteira']
  obj=b.objects[0];bpy.context.scene.collection.objects.link(obj);obj.select_set(True);bpy.context.view_layer.objects.active=obj
  bpy.context.scene.chest_splitter.target_object=obj
  return obj
 def valid_mesh(self,mesh):
  bm=bmesh.new();bm.from_mesh(mesh)
  try:
   report=validate_bmesh_mesh_geometry(bm,1000)
   self.assertTrue(report['is_valid'],str(report));self.assertTrue(report['is_manifold'],str(report))
   self.assertGreater(report['volume_mm3'],0)
  finally:bm.free()
 def test_stale_loop_capture_is_ignored_in_material_mode(self):
  bpy.ops.mesh.primitive_cube_add()
  obj=bpy.context.object;s=bpy.context.scene.chest_splitter;s.target_object=obj
  s.loop_is_captured=True;s.loop_vertex_indices='0,1,2';s.loop_region_face_indices='[999]'
  s.split_mode='MATERIAL'
  self.assertIsNone(captured_region_faces(obj,[0,1,2],0,bpy.context.scene))
  s.split_mode='LOOP'
  with self.assertRaisesRegex(ValueError,'face escolhida'):captured_region_faces(obj,[0,1,2],0,bpy.context.scene)
 def test_double_volume_is_invariant_to_planar_triangulation(self):
  bpy.ops.mesh.primitive_cube_add(size=.04,location=(.075,.028,.115))
  before=bmesh.new();before.from_mesh(bpy.context.object.data);before.transform(bpy.context.object.matrix_world)
  after=before.copy()
  try:
   bmesh.ops.triangulate(after,faces=after.faces[:])
   self.assertAlmostEqual(stable_signed_volume_mm3(before,1000),stable_signed_volume_mm3(after,1000),delta=1e-8)
  finally:before.free();after.free()
 def test_chest_planar_gap_keeps_valid_closed_geometry(self):
  from src.geometry_plane import slice_mesh_by_plane
  obj=self.chest();snapshot=[tuple(v.co) for v in obj.data.vertices]
  vertices=[obj.matrix_world@v.co for v in obj.data.vertices]
  origin=Vector(tuple((min(v[i] for v in vertices)+max(v[i] for v in vertices))/2 for i in range(3)))
  meshes=[bpy.data.meshes.new('A'),bpy.data.meshes.new('B')]
  slice_mesh_by_plane(obj.data,obj.matrix_world,origin,Vector((1,0,0)),meshes[0],meshes[1],unit_scale=1000,part_clearance_mm=.1)
  planes=[]
  for mesh in meshes:
   self.valid_mesh(mesh)
   bm=bmesh.new();bm.from_mesh(mesh)
   caps=[(f.calc_area(),sum(v.co.x for v in f.verts)/len(f.verts)) for f in bm.faces if abs(f.normal.x)>.9999 and max(abs(v.co.x-origin.x)*1000 for v in f.verts)<.102]
   self.assertTrue(caps);planes.append(max(caps)[1]);bm.free()
  self.assertAlmostEqual(abs(planes[0]-planes[1])*1000,.1,delta=.002)
  self.assertEqual(snapshot,[tuple(v.co) for v in obj.data.vertices])
 def test_chest_solid_retries_invalid_exact_result_and_preserves_volume(self):
  import src.geometry_solid as solid
  obj=self.chest();vertices=[obj.matrix_world@v.co for v in obj.data.vertices]
  lo=Vector(tuple(min(v[i] for v in vertices) for i in range(3)));hi=Vector(tuple(max(v[i] for v in vertices) for i in range(3)));span=hi-lo;center=(lo+hi)/2
  center.x=lo.x+.82*span.x
  bpy.ops.mesh.primitive_cube_add(size=1.,location=center);cutter=bpy.context.object;cutter.dimensions=Vector((span.x*.72,span.y*1.6,span.z*1.6));bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
  meshes=[bpy.data.meshes.new('A'),bpy.data.meshes.new('B')]
  with patch.object(solid,'_slice_mesh_by_solid',wraps=solid._slice_mesh_by_solid) as calls:
   result=solid.slice_mesh_by_solid(obj.data,obj.matrix_world,cutter,meshes[0],meshes[1],unit_scale=1000)
   self.assertEqual(calls.call_count,2)
   self.assertEqual(calls.call_args.kwargs['_solver'],'MANIFOLD')
  for mesh in meshes:self.valid_mesh(mesh)
  before=bmesh.new();before.from_mesh(obj.data)
  try:self.assertAlmostEqual(result['sum_volume_mm3'],abs(before.calc_volume())*1e9,delta=.01)
  finally:before.free()
 def test_chest_material_prisms_and_empty_boolean_fallback(self):
  from src.geometry_material import slice_mesh_by_material
  obj=self.chest();snapshot=[tuple(v.co) for v in obj.data.vertices]
  for material,gap in ((0,0),(0,.1),(1,.1)):
   with self.subTest(material=material,gap=gap):
    parts=slice_mesh_by_material(obj,material,region_index=0,extraction_mode='EXTRUDE',depth_mm=2,part_clearance_mm=gap)
    try:
     for bm in parts:
      report=validate_bmesh_mesh_geometry(bm,1000)
      self.assertTrue(report['is_valid'],str(report));self.assertTrue(report['is_manifold'],str(report))
      self.assertGreater(report['volume_mm3'],0)
    finally:
     for bm in parts:bm.free()
  self.assertEqual(snapshot,[tuple(v.co) for v in obj.data.vertices])

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
