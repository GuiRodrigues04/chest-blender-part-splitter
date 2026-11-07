"""Planar shared seats, parallel pins, UI simplification, and assembly clearance."""
import sys,json,unittest,hashlib,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import bpy,bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import src
from test_region_release import configure,sphere,upper,CAT
from src.geometry_region import slice_region,mesh_signature,mesh_tree,CONTACT,PATCH
from src.geometry_seat import candidate_groups,assembly_axis,verify_straight_assembly
from src.connector_surface import prepare_split_candidates,prepared_connector_layout

class PlanarSeats(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def setUp(self):
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  bpy.ops.wm.read_factory_settings(use_empty=True)
 def make(self):
  o,_=sphere();s=configure(o,upper(o));s.part_clearance_mm=0;s.connector_diameter_mm=5;s.connector_length_mm=6;s.connector_distribution='LINEAR_2'
  return o,s
 def preview(self):self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
 def seat(self):
  self.preview();self.assertEqual(bpy.ops.chest.splitter_choose_contact(index=0),{'FINISHED'})
  return prepare_split_candidates(bpy.context,True)
 def result(self,o,s):
  a=bpy.data.meshes.new('a');b=bpy.data.meshes.new('b');return a,b,slice_region(o,s,bpy.context.scene,a,b)
 def test_only_four_cut_methods(self):
  self.assertEqual({v.identifier for v in bpy.context.scene.chest_splitter.bl_rna.properties['split_mode'].enum_items},{'PLANE','SOLID','LOOP','MATERIAL'})
 def test_material_and_face_selection_produce_same_partition(self):
  o,s=self.make();w=bpy.data.materials.new('body');m=bpy.data.materials.new('part');o.data.materials.append(w);o.data.materials.append(m)
  for f in o.data.polygons:f.material_index=int(f.index in upper(o))
  s=configure(o,upper(o));a,b,r=self.result(o,s)
  s.split_mode='MATERIAL';s.material_split_index=1;s.material_region_index=0;s.material_extraction_mode='WHOLE'
  c,d,q=self.result(o,s);self.assertAlmostEqual(r['A']['volume_mm3'],q['A']['volume_mm3'],delta=.001);self.assertEqual(len(a.polygons),len(c.polygons))
 def test_material_change_recomputes_region_without_repainting(self):
  o,s=self.make();o.data.materials.append(bpy.data.materials.new('body'));o.data.materials.append(bpy.data.materials.new('top'))
  for f in o.data.polygons:f.material_index=int(sum(o.data.vertices[i].co.z for i in f.vertices)/len(f.vertices)>.02)
  s.split_mode='MATERIAL';s.material_extraction_mode='WHOLE';s.material_split_index=1
  a,b,r=self.result(o,s);self.assertLess(r['A']['volume_mm3'],r['B']['volume_mm3']);self.assertTrue(r['A']['is_manifold'])
 def test_contour_capture_does_not_require_new_material(self):
  o,s=self.make();region={f.index for f in o.data.polygons if sum(o.data.vertices[i].co.z for i in f.vertices)/len(f.vertices)>.02}
  bpy.context.tool_settings.mesh_select_mode=(False,True,False);bpy.ops.object.mode_set(mode='EDIT');bm=bmesh.from_edit_mesh(o.data);bm.faces.index_update()
  for f in bm.faces:f.select_set(False)
  for e in bm.edges:e.select_set(False)
  for v in bm.verts:v.select_set(False)
  for e in bm.edges:
   if sum(f.index in region for f in e.link_faces)==1:e.select_set(True)
  bmesh.update_edit_mesh(o.data)
  self.assertEqual(bpy.ops.chest.splitter_capture_region(),{'FINISHED'});self.assertEqual(set(map(int,s.region_face_indices.split(','))),region);self.preview()
 def test_all_pin_axes_parallel_on_one_real_plane(self):
  o,s=self.make();prepared=self.seat();s.connector_enabled=True;self.preview();prepared=prepare_split_candidates(bpy.context,True);layout=prepared_connector_layout(prepared,s,o)
  self.assertGreaterEqual(len(layout['positions']),2)
  n=prepared.interface.normal_a_to_b_world
  for position in layout['positions']:self.assertLess(abs((position-prepared.interface.origin_world).dot(n))*1000,.001)
  for rotation in layout['pin_rotations']:self.assertGreater(abs((rotation.to_matrix()@Vector((0,0,1))).dot(n)),.999999)
 def test_male_flip_keeps_parallel_axes(self):
  o,s=self.make();self.seat();s.connector_enabled=True;s.connector_male_part='B';self.preview()
  prepared=prepare_split_candidates(bpy.context,True);layout=prepared_connector_layout(prepared,s,o)
  for rotation in layout['pin_rotations']:self.assertGreater(abs((rotation.to_matrix()@Vector((0,0,1))).dot(prepared.surface_normal)),.999999)
 def test_edit_target_hides_previews_instead_of_overlaying_original(self):
  o,s=self.make();self.preview();a=bpy.data.objects['SPLITTER_PREVIEW_A'];b=bpy.data.objects['SPLITTER_PREVIEW_B'];count=len(bpy.data.objects);coords=[tuple(v.co) for v in o.data.vertices]
  self.assertEqual(bpy.ops.chest.splitter_edit_target(),{'FINISHED'});self.assertTrue(a.hide_get() and b.hide_get());self.assertFalse(o.hide_get());self.assertEqual(len(bpy.data.objects),count);self.assertEqual(coords,[tuple(v.co) for v in o.data.vertices])
 def test_multiple_faces_choose_complete_contact(self):
  o,s=self.make();self.preview();a=bpy.data.objects['SPLITTER_PREVIEW_A'];bpy.ops.object.select_all(action='DESELECT');a.select_set(True);bpy.context.view_layer.objects.active=a;bpy.context.tool_settings.mesh_select_mode=(False,False,True);bpy.ops.object.mode_set(mode='EDIT');bm=bmesh.from_edit_mesh(a.data);layer=bm.faces.layers.int[PATCH]
  for f in bm.faces:f.select_set(False)
  selected=[f for f in bm.faces if f[layer]==1]
  self.assertGreater(len(selected),1)
  for f in selected:f.select_set(True)
  bmesh.update_edit_mesh(a.data);self.assertEqual(bpy.ops.chest.splitter_choose_contact(),{'FINISHED'})
  prepared=prepare_split_candidates(bpy.context,True);self.assertTrue(prepared.interface.is_planar);self.assertGreater(prepared.interface.area_mm2,1000)
 def test_closed_plane_is_shared_before_pins(self):
  o,s=self.make();s.contact_patch_index=0;a,b,r=self.result(o,s);self.assertLess(r['interface'].deviation_mm,.001)
  keys=lambda mesh:{tuple(sorted(tuple(mesh.vertices[i].co) for i in f.vertices)) for f in mesh.polygons if mesh.attributes[CONTACT].data[f.index].value}
  self.assertEqual(keys(a),keys(b))
 def test_no_common_assembly_axis_is_rejected(self):
  faces=[SimpleNamespace(index=i,normal=Vector(n)) for i,n in enumerate(((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)))]
  self.assertIsNone(assembly_axis(Vector((0,0,1)),faces))
 def test_distant_body_interference_is_rejected(self):
  bpy.ops.mesh.primitive_cube_add(size=.02,location=(0,0,0));a=bpy.context.object.data.copy();bpy.ops.mesh.primitive_cube_add(size=.03,location=(0,0,-.025));obj=bpy.context.object
  bm=bmesh.new();bm.from_mesh(obj.data);bm.transform(obj.matrix_world);b=bpy.data.meshes.new('obstacle');bm.to_mesh(b);bm.free()
  with self.assertRaisesRegex(ValueError,'colide'):verify_straight_assembly(a,b,Vector((0,0,1)),1000)
 def test_contact_area_is_broad_and_truly_flat_on_cat(self):
  if not CAT.exists():self.skipTest('Cat fixture missing')
  digest=hashlib.sha256(CAT.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(CAT),use_scripts=False)
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  o=bpy.data.objects['Gato Cinza Retopology'];s=bpy.context.scene.chest_splitter;s.target_object=o;s.split_mode='MATERIAL';s.material_extraction_mode='WHOLE';s.material_split_index=4;s.material_region_index=0;s.part_clearance_mm=0;s.connector_enabled=False;s.contact_patch_index=-1
  a,b,raw=self.result(o,s);self.assertLess(len(raw['contact_choices']),5);s.contact_patch_index=0;c,d,flat=self.result(o,s)
  interface=flat['interface'];self.assertGreater(interface.area_mm2,15000);self.assertLess(interface.deviation_mm,.001)
  self.assertAlmostEqual(raw['sum_volume_mm3'],flat['sum_volume_mm3'],delta=.01)
  old=mesh_tree(o.data,o.matrix_world)
  for mesh in (c,d):
   for face in mesh.polygons:
    if not mesh.attributes[CONTACT].data[face.index].value:
     p=sum((mesh.vertices[i].co for i in face.vertices),Vector())/len(face.vertices);self.assertLess(old.find_nearest(p)[3]*1000,.001)
  self.assertEqual(hashlib.sha256(CAT.read_bytes()).hexdigest(),digest)
 def test_interface_gap_and_pin_clearance_independent(self):
  o,s=self.make();self.seat();s.connector_enabled=True;s.part_clearance_mm=.1;self.preview();p=prepare_split_candidates(bpy.context,True)
  self.assertTrue(p.interface.clearance_applied)
  n=p.interface.normal_a_to_b_world
  self.assertAlmostEqual((p.interface.final_contact_b['origin']-p.interface.final_contact_a['origin']).dot(n)*1000,.1,delta=.002)
  a=s.part_a_volume_mm3;b=s.part_b_volume_mm3;s.clearance_per_side_mm=.3;self.preview();self.assertAlmostEqual(s.part_a_volume_mm3,a,delta=.1);self.assertLess(s.part_b_volume_mm3,b)
 def test_cat_gap_on_either_or_both_parts_and_both_pin_sides(self):
  if not CAT.exists():self.skipTest('Cat fixture missing')
  bpy.ops.wm.open_mainfile(filepath=str(CAT),use_scripts=False)
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  o=bpy.data.objects['Gato Cinza Retopology'];s=bpy.context.scene.chest_splitter;s.target_object=o;s.split_mode='MATERIAL';s.material_extraction_mode='WHOLE';s.material_split_index=4;s.material_region_index=0;s.part_clearance_mm=0;s.connector_enabled=False;s.contact_patch_index=-1
  self.seat();s.connector_enabled=True;s.connector_diameter_mm=8;s.connector_length_mm=12;s.connector_distribution='LINEAR_2'
  for gap in (.1,.2):
   for apply in ('PART','CAVITY','BOTH'):
    for male in ('A','B'):
     with self.subTest(gap=gap,apply=apply,male=male):
      s.part_clearance_mm=gap;s.part_clearance_apply_to=apply;s.connector_male_part=male;self.preview()
      p=prepare_split_candidates(bpy.context,True);interface=p.interface;n=interface.normal_a_to_b_world
      self.assertAlmostEqual((interface.final_contact_b['origin']-interface.final_contact_a['origin']).dot(n)*1000,gap,delta=.002)
      self.assertTrue(s.part_a_is_manifold and s.part_b_is_manifold)
      layout=prepared_connector_layout(p,s,o);self.assertEqual(len(layout['positions']),2)
      for rotation in layout['pin_rotations']:self.assertGreater(abs((rotation.to_matrix()@Vector((0,0,1))).dot(n)),.999999)
 def test_old_region_file_migrates_to_loop_whole(self):
  old=Path(r'C:/Users/guiro/OneDrive/Documentos/ChatGPT/Extensão Blender/regioes-0.8.24/Gato_pata_regiao_0.8.24.blend')
  if not old.exists():self.skipTest('Old region fixture missing')
  bpy.ops.wm.open_mainfile(filepath=str(old),use_scripts=False)
  s=bpy.context.scene.chest_splitter
  self.assertEqual(s.split_mode,'LOOP');self.assertEqual(s.loop_behavior,'WHOLE');self.assertEqual(len(s.region_face_indices.split(',')),477)
  self.assertFalse(s.connector_enabled);self.assertEqual(s.contact_patch_index,-1);self.preview()
 def test_ui_solid_has_no_shell_no_pins_no_target_promotion(self):
  from src.ui import VIEW3D_PT_chest_part_splitter
  o,s=self.make();s.split_mode='SOLID';bpy.ops.chest.splitter_create_solid_cutter();ops=[];props=[]
  class Layout:
   def row(self,*a,**k):return self
   column=box=split=grid_flow=row
   def label(self,*a,**k):pass
   def separator(self,*a,**k):pass
   def template_list(self,*a,**k):pass
   def prop(self,obj,name,*a,**k):props.append(name)
   def operator(self,name,*a,**k):ops.append(name);return SimpleNamespace()
  VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=Layout()),bpy.context)
  self.assertNotIn('chest.splitter_create_cutter_from_selection',ops);self.assertNotIn('connector_enabled',props);self.assertNotIn('chest.splitter_set_target',ops);self.assertNotIn('chest.splitter_choose_contact',ops)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PlanarSeats));sys.exit(not result.wasSuccessful())
