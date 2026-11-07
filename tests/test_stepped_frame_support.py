"""Planar reference with a stepped inner boundary must support annular cuts."""
from pathlib import Path
import sys,unittest,os
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
from src.geometry_regions import region_support
from src.geometry_material import slice_mesh_by_material,analyze_material_structure
from src.diagnostic import validate_bmesh_mesh_geometry

class SteppedFrameSupport(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def setUp(self):
  bpy.ops.wm.read_factory_settings(use_empty=True)
  bpy.context.scene.unit_settings.scale_length=1
 def synthetic(self):
  vertices=[]
  for size,heights in [(20,[0]*4),(20,[5]*4),(18,[5]*4),(19,[7]*4),(10,[7]*4),(11,[5,6,6,5])]:
   vertices.extend([(x/1000,y/1000,z/1000) for (x,y),z in zip([(-size,-size),(size,-size),(size,size),(-size,size)],heights)])
  faces=[(3,2,1,0)];materials=[0]
  for ring in range(5):
   for i in range(4):
    j=(i+1)%4;faces.append((4*ring+i,4*ring+j,4*(ring+1)+j,4*(ring+1)+i));materials.append(1 if ring in (2,3,4) else 0)
  faces.extend([(20,21,22),(20,22,23)]);materials.extend([0,0])
  mesh=bpy.data.meshes.new('Stepped frame');mesh.from_pydata(vertices,[],faces);mesh.update()
  for name in ('Body','Frame'):mesh.materials.append(bpy.data.materials.new(name))
  for f,m in zip(mesh.polygons,materials):f.material_index=m
  obj=bpy.data.objects.new('Stepped frame',mesh);bpy.context.scene.collection.objects.link(obj)
  return obj
 def valid(self,bm):
  check=validate_bmesh_mesh_geometry(bm,1000)
  self.assertTrue(check['is_valid'],str(check));self.assertTrue(check['is_manifold'],str(check))
  self.assertGreater(bm.calc_volume(),0)
 def test_stepped_inner_boundary_base_depth_and_clearances(self):
  obj=self.synthetic();original=[tuple(v.co) for v in obj.data.vertices]
  faces=[f.index for f in obj.data.polygons if f.material_index==1]
  support=region_support(obj,faces,1000);self.assertGreater(support['deviation'],.9)
  for mode in ('BASE','EXTRUDE'):
   for apply_to,gap in [('PART',0.),('PART',.1),('CAVITY',.1),('BOTH',.1)]:
    with self.subTest(mode=mode,apply_to=apply_to,gap=gap):
     result=slice_mesh_by_material(obj,1,depth_mm=2,extraction_mode=mode,part_clearance_mm=gap,part_clearance_apply_to=apply_to)
     try:
      for bm in result:self.valid(bm)
     finally:
      for bm in result:bm.free()
  self.assertEqual(original,[tuple(v.co) for v in obj.data.vertices])
 def test_nonplanar_reference_is_still_rejected(self):
  obj=self.synthetic();obj.data.vertices[8].co.z+=.002;obj.data.update()
  with self.assertRaisesRegex(ValueError,'apoio planar'):
   region_support(obj,[f.index for f in obj.data.polygons if f.material_index==1],1000)
 def test_loop_capture_uses_same_stepped_support(self):
  obj=self.synthetic();bpy.context.view_layer.objects.active=obj;obj.select_set(True)
  s=bpy.context.scene.chest_splitter;s.target_object=obj;s.split_mode='LOOP'
  bpy.ops.object.mode_set(mode='EDIT');bpy.context.tool_settings.mesh_select_mode=(False,False,True)
  bm=bmesh.from_edit_mesh(obj.data)
  for v in bm.verts:v.select_set(False)
  for e in bm.edges:e.select_set(False)
  for f in bm.faces:f.select_set(f.material_index==1)
  bm.faces.active=next(f for f in bm.faces if f.material_index==1)
  bmesh.update_edit_mesh(obj.data)
  self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(),{'FINISHED'})
  bpy.ops.object.mode_set(mode='OBJECT')
  s.loop_behavior='EXTRUDE';s.loop_extrude_depth_mm=2.;s.connector_enabled=False
  s.assembly_clearance_preset='FDM'
  self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'},s.get_localized_status())
  from src.operators import get_current_session_parts
  parts=get_current_session_parts(bpy.context.scene);self.assertEqual(len(parts),2)
  for part in parts:
   bm=bmesh.new();bm.from_mesh(part.data);self.valid(bm);bm.free()

 def test_real_bone_material_preview_commit(self):
  filename=Path(os.environ.get('BONE_BLEND',r'C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_Osso_Chest_Inteira.blend'))
  if not filename.is_file():self.skipTest('Private bone fixture not available')
  with bpy.data.libraries.load(str(filename)) as (a,b):b.objects=['Placa_Osso_Chest_Inteira']
  obj=b.objects[0];bpy.context.scene.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
  original=([tuple(v.co) for v in obj.data.vertices],[tuple(f.vertices) for f in obj.data.polygons])
  s=bpy.context.scene.chest_splitter;s.target_object=obj;s.split_mode='MATERIAL';s.material_split_index=0
  s.material_extraction_mode='EXTRUDE';s.material_extrude_depth_mm=2.;s.connector_enabled=False
  s.assembly_clearance_preset='FDM';s.commit_next_target='NONE'
  analysis=analyze_material_structure(obj,0);self.assertTrue(analysis['valid']);self.assertGreater(analysis['base_deviation_mm'],.9)
  self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'},s.get_localized_status())
  from src.operators import get_current_session_parts,verify_preview_current
  self.assertTrue(verify_preview_current(bpy.context)[0])
  before=[]
  for part in get_current_session_parts(bpy.context.scene):
   bm=bmesh.new();bm.from_mesh(part.data);self.valid(bm);before.append(bm.calc_volume());bm.free()
  self.assertEqual(len(before),2)
  self.assertEqual(bpy.ops.chest.splitter_commit_parts(),{'FINISHED'},s.get_localized_status())
  after=[]
  for part in get_current_session_parts(bpy.context.scene):
   bm=bmesh.new();bm.from_mesh(part.data);self.valid(bm);after.append(bm.calc_volume());bm.free()
  self.assertEqual(sorted(before),sorted(after))
  self.assertEqual(original,([tuple(v.co) for v in obj.data.vertices],[tuple(f.vertices) for f in obj.data.polygons]))

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
