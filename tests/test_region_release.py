"""Physical invariants, rejected inputs, and complete region/contact workflows."""
import sys,unittest,hashlib,json,tempfile,os
from pathlib import Path
import bpy,bmesh
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
from src.geometry_region import slice_region,mesh_signature,mesh_tree,PATCH,CONTACT,closing_triangles
from src.geometry_solid import slice_mesh_by_solid
from src.diagnostic import stable_signed_volume_mm3
CAT=Path(os.environ.get('SPLITTER_CAT_FIXTURE',r'C:/Users/guiro/OneDrive/Desktop/Modelos 3D e testes extensao/Placas - Modelos 3D/Teste Gato.blend'))

def configure(obj,ids):
 s=bpy.context.scene.chest_splitter;s.target_object=obj;s.split_mode='LOOP';s.loop_behavior='WHOLE';s.region_selection_enabled=True;s.region_target=obj
 s.region_face_indices=','.join(map(str,ids));s.region_mesh_signature=mesh_signature(obj.data)
 s.part_clearance_mm=0;s.connector_enabled=False;s.invert_sides=False;s.contact_patch_index=-1
 return s

def sphere(segments=24,rings=12):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,radius=.05)
 o=bpy.context.object
 return o,[f.index for f in o.data.polygons if f.center.z>0] # polygon centers updated below

def upper(o):
 return [f.index for f in o.data.polygons if sum(o.data.vertices[i].co.z for i in f.vertices)/len(f.vertices)>.00001]

class RegionRelease(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def setUp(self):
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  bpy.ops.wm.read_factory_settings(use_empty=True)
 def result(self,o,s):
  a=bpy.data.meshes.new('test_A');b=bpy.data.meshes.new('test_B')
  try:return a,b,slice_region(o,s,bpy.context.scene,a,b)
  except Exception:
   bpy.data.meshes.remove(a);bpy.data.meshes.remove(b);raise
 def invariant(self,o,a,b,r):
  source=mesh_tree(o.data,o.matrix_world)
  for side,mesh in (('A',a),('B',b)):
   self.assertTrue(r[side]['is_manifold']);self.assertEqual(r[side]['components'],1)
   self.assertGreater(r[side]['volume_mm3'],0)
   bm=bmesh.new();bm.from_mesh(mesh);self.assertTrue(all(v.is_manifold for v in bm.verts));bm.free()
  ca={tuple(sorted(tuple(a.vertices[i].co) for i in f.vertices)) for f in a.polygons if a.attributes[CONTACT].data[f.index].value}
  cb={tuple(sorted(tuple(b.vertices[i].co) for i in f.vertices)) for f in b.polygons if b.attributes[CONTACT].data[f.index].value}
  self.assertEqual(ca,cb)
  o.data.calc_loop_triangles()
  def volume_term(t):
   a,b,c=[tuple(o.matrix_world@o.data.vertices[i].co) for i in t.vertices]
   return a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0])
  total=abs(sum(volume_term(t) for t in o.data.loop_triangles)/6)*(1000*bpy.context.scene.unit_settings.scale_length)**3
  self.assertAlmostEqual(r['sum_volume_mm3'],total,delta=max(.002,total*1e-7))
  # Every retained exterior triangle still lies on the source, never on a scaled copy.
  for mesh in (a,b):
   for f in mesh.polygons:
    if not mesh.attributes[CONTACT].data[f.index].value:
     p=sum((mesh.vertices[i].co for i in f.vertices),Vector())/len(f.vertices)
     self.assertLess(source.find_nearest(p)[3]*1000*bpy.context.scene.unit_settings.scale_length,.001)
  self.assertTrue(r['contact_choices'])
 def test_sphere_and_transforms(self):
  for scale,unit in (((1,1,1),1),((1.2,.7,1.5),1),((-1.2,.7,1.5),1),((1000,1000,1000),.001)):
   with self.subTest(scale=scale,unit=unit):
    o,_=sphere();o.scale=scale;o.location=(.17,-.22,.31);o.rotation_euler=(.13,.23,.37)
    bpy.context.scene.unit_settings.scale_length=unit;bpy.context.view_layer.update()
    s=configure(o,upper(o));a,b,r=self.result(o,s);self.invariant(o,a,b,r)
 def test_cylinder_top(self):
  bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.05,depth=.1)
  o=bpy.context.object;s=configure(o,[f.index for f in o.data.polygons if f.normal.z>.9])
  # A single flat cap would have zero volume: do not emit a false solid.
  with self.assertRaises(ValueError):self.result(o,s)
 def test_empty_and_whole_selection(self):
  o,_=sphere()
  for ids in ([],list(range(len(o.data.polygons))),[-1],[99999]):
   with self.subTest(ids=len(ids)):
    with self.assertRaises(ValueError):self.result(o,configure(o,ids))
 def test_stale_same_count_vertex_change(self):
  o,_=sphere();s=configure(o,upper(o));o.data.vertices[0].co.x+=.001
  with self.assertRaisesRegex(ValueError,'mudou'):self.result(o,s)
 def test_stale_material_change(self):
  o,_=sphere();s=configure(o,upper(o));o.data.polygons[0].material_index=1
  with self.assertRaisesRegex(ValueError,'mudou'):self.result(o,s)
 def test_wrong_target(self):
  o,_=sphere();s=configure(o,upper(o));other,_=sphere();s.region_target=other
  with self.assertRaises(ValueError):self.result(o,s)
 def test_modifier_rejected(self):
  o,_=sphere();s=configure(o,upper(o));o.modifiers.new('sub','SUBSURF')
  with self.assertRaisesRegex(ValueError,'modificadores'):self.result(o,s)
 def test_gap_and_inversion_rejected(self):
  o,_=sphere();s=configure(o,upper(o));a,b,baseline=self.result(o,s);s.part_clearance_mm=.1
  c,d,with_gap=self.result(o,s);self.assertLess(with_gap['sum_volume_mm3'],baseline['sum_volume_mm3'])
  self.assertTrue(with_gap['A']['is_manifold'] and with_gap['B']['is_manifold'])
  s.part_clearance_mm=0;s.invert_sides=True
  with self.assertRaisesRegex(ValueError,'Macho'):self.result(o,s)
 def test_open_source(self):
  o,_=sphere();bm=bmesh.new();bm.from_mesh(o.data);bm.faces.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.faces[0]],context='FACES');bm.to_mesh(o.data);bm.free()
  with self.assertRaisesRegex(ValueError,'topológicos'):self.result(o,configure(o,upper(o)))
 def test_disconnected_selection(self):
  o,_=sphere();ids=[f.index for f in o.data.polygons if abs(sum(o.data.vertices[i].co.z for i in f.vertices)/len(f.vertices))>.035]
  with self.assertRaises(ValueError):self.result(o,configure(o,ids))
 def test_dense_boundary_guard(self):
  o,_=sphere(segments=132,rings=6)
  with self.assertRaisesRegex(ValueError,'128'):self.result(o,configure(o,upper(o)))
 def test_singular_transform(self):
  o,_=sphere();o.scale.x=0;bpy.context.view_layer.update()
  with self.assertRaisesRegex(ValueError,'escala nula'):self.result(o,configure(o,upper(o)))
 def test_material_shortcut_captures_without_planar_requirement(self):
  o,_=sphere();white=bpy.data.materials.new('white');orange=bpy.data.materials.new('orange');o.data.materials.append(white);o.data.materials.append(orange)
  ids=upper(o)
  for f in o.data.polygons:f.material_index=int(f.index in ids)
  s=bpy.context.scene.chest_splitter;s.target_object=o;s.split_mode='MATERIAL';s.material_split_index=1;s.material_region_index=0
  self.assertEqual(bpy.ops.chest.splitter_capture_region(use_material=True),{'FINISHED'})
  self.assertEqual(s.split_mode,'MATERIAL');self.assertEqual(s.material_extraction_mode,'WHOLE');self.assertEqual(set(map(int,s.region_face_indices.split(','))),set(ids));self.preview()
 def test_capture_requires_target_edit(self):
  o,_=sphere();s=configure(o,upper(o))
  with self.assertRaises(RuntimeError):bpy.ops.chest.splitter_capture_region()
 def preview(self):
  self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
 def workflow_setup(self):
  o,_=sphere();s=configure(o,upper(o));s.assembly_clearance_preset='CUSTOM'
  bpy.context.tool_settings.mesh_select_mode=(False,False,True)
  for v in o.data.vertices:v.select=False
  for e in o.data.edges:e.select=False
  for f in o.data.polygons:f.select=f.index in upper(o)
  bpy.ops.object.mode_set(mode='EDIT');self.assertEqual(bpy.ops.chest.splitter_capture_region(),{'FINISHED'});self.assertEqual(bpy.context.mode,'OBJECT')
  self.preview();self.assertEqual(bpy.ops.chest.splitter_choose_contact(index=0),{'FINISHED'})
  s.connector_enabled=True;s.connector_diameter_mm=5;s.connector_length_mm=6;s.connector_distribution='CENTER'
  return o,s
 def test_capture_preview_pins_flip_commit_revert(self):
  o,s=self.workflow_setup();self.preview();self.assertTrue(s.part_a_is_manifold and s.part_b_is_manifold)
  s.connector_male_part='B';self.preview();self.assertTrue(s.part_a_is_manifold and s.part_b_is_manifold)
  self.assertEqual(bpy.ops.chest.splitter_commit_parts(),{'FINISHED'})
  self.assertEqual(bpy.ops.chest.splitter_revert_cut(),{'FINISHED'})
  self.assertIn(o.name,bpy.data.objects)
 def test_contact_rejects_changed_cut_and_keeps_previous_preview(self):
  o,s=self.workflow_setup();self.preview();old=bpy.data.objects['SPLITTER_PREVIEW_A'];pointer=old.as_pointer();mesh=old.data
  s.region_face_indices=','.join(str(i) for i in upper(o)[:-1])
  self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'CANCELLED'})
  self.assertEqual(bpy.data.objects['SPLITTER_PREVIEW_A'].as_pointer(),pointer);self.assertEqual(old.data,mesh)
  with self.assertRaises(RuntimeError):bpy.ops.chest.splitter_choose_contact(index=0)
  bpy.ops.chest.splitter_choose_contact(index=-2);self.assertFalse(s.connector_enabled);self.assertEqual(s.contact_patch_index,-1)
 def test_save_load_selection(self):
  o,s=self.workflow_setup();self.preview();sig=s.region_mesh_signature;indices=s.region_face_indices
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'region.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False)
   s=bpy.context.scene.chest_splitter;self.assertEqual(s.region_mesh_signature,sig);self.assertEqual(s.region_face_indices,indices);self.assertEqual(s.contact_patch_index,0);self.preview()
 def test_pick_preview_face_and_reject_exterior(self):
  o,s=self.workflow_setup();self.preview();p=bpy.data.objects['SPLITTER_PREVIEW_A']
  bpy.ops.object.select_all(action='DESELECT');p.select_set(True);bpy.context.view_layer.objects.active=p
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  for v in p.data.vertices:v.select=False
  for e in p.data.edges:e.select=False
  for face in p.data.polygons:face.select=False
  attr=p.data.attributes[PATCH];idx=next(f.index for f in p.data.polygons if attr.data[f.index].value==1)
  p.data.polygons[idx].select=True;bpy.ops.object.mode_set(mode='EDIT')
  self.assertEqual(bpy.ops.chest.splitter_choose_contact(),{'FINISHED'})
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  # Choosing/preparing a contact may rebuild the preview's custom-data layers.
  # Reacquire RNA after leaving Edit Mode instead of keeping a stale handle.
  attr=p.data.attributes[PATCH]
  for v in p.data.vertices:v.select=False
  for e in p.data.edges:e.select=False
  for face in p.data.polygons:face.select=False
  idx=next(f.index for f in p.data.polygons if attr.data[f.index].value==0);p.data.polygons[idx].select=True
  bpy.ops.object.mode_set(mode='EDIT')
  with self.assertRaises(RuntimeError):bpy.ops.chest.splitter_choose_contact()
 def test_cat_both_paws_and_pins(self):
  if not CAT.exists():self.skipTest('Private cat fixture unavailable')
  digest=hashlib.sha256(CAT.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(CAT),use_scripts=False)
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  o=bpy.data.objects.get('Gato Cinza Retopology');part=bpy.data.objects.get('Gato Cinza Retopology__A')
  if o is None or part is None:self.skipTest('Private cat paw reference objects unavailable')
  tree=mesh_tree(part.data,part.matrix_world)
  positive=[]
  for f in o.data.polygons:
   p=sum((o.matrix_world@o.data.vertices[i].co for i in f.vertices),Vector())/len(f.vertices)
   near=tree.find_nearest(p)
   if f.material_index==0 and near[3]<.00001 and (o.matrix_world.to_3x3()@f.normal).dot(near[1])>.999:positive.append(f.index)
  for label,ids in [('orange',[f.index for f in o.data.polygons if f.material_index==4]),('positive',positive)]:
   with self.subTest(paw=label):
    s=configure(o,ids);a,b,r=self.result(o,s);self.invariant(o,a,b,r)
    self.assertGreater(len(ids),400)
    self.preview();bpy.ops.chest.splitter_choose_contact(index=0);s.connector_enabled=True;s.connector_diameter_mm=8;s.connector_length_mm=12;s.connector_distribution='CENTER';self.preview()
    self.assertTrue(s.part_a_is_manifold and s.part_b_is_manifold)
    bpy.ops.chest.splitter_remove_preview()
  self.assertEqual(hashlib.sha256(CAT.read_bytes()).hexdigest(),digest)
 def test_panel_contains_full_region_workflow(self):
  from types import SimpleNamespace
  from src.ui import VIEW3D_PT_chest_part_splitter
  o,s=self.workflow_setup();self.preview();ops=[]
  class Layout:
   def row(self,*a,**k):return self
   column=box=split=grid_flow=row
   def label(self,*a,**k):pass
   def separator(self,*a,**k):pass
   def prop(self,obj,name,*a,**k):getattr(obj,name)
   def template_list(self,*a,**k):pass
   def operator(self,name,*a,**k):
    ns,op=name.split('.');getattr(getattr(bpy.ops,ns),op).get_rna_type();ops.append(name);return SimpleNamespace()
  VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=Layout()),bpy.context)
  for op in ('capture_region','generate_preview','choose_contact','commit_parts'):
   self.assertIn('chest.splitter_'+op,ops)
 def test_region_manual_editor(self):
  from src.connector_surface import prepare_split_candidates
  o,s=self.workflow_setup();self.preview()
  prepared=prepare_split_candidates(bpy.context,True);self.assertTrue(prepared.interface.is_planar)
  self.assertEqual(bpy.ops.chest.splitter_edit_manual_connectors(),{'FINISHED'})
  self.assertEqual(bpy.ops.chest.splitter_add_manual_connector(),{'FINISHED'})
  self.assertTrue(len(s.manual_connectors)>0)
  self.assertEqual(bpy.ops.chest.splitter_confirm_manual_connectors(),{'FINISHED'})
  self.preview()
 def test_edit_hidden_target_after_preview(self):
  o,s=self.workflow_setup();self.preview();self.assertTrue(o.hide_get())
  self.assertEqual(bpy.ops.chest.splitter_edit_target(),{'FINISHED'});self.assertEqual(bpy.context.edit_object,o);self.assertFalse(o.hide_get())
 def test_contact_indices_deterministic(self):
  o,_=sphere();s=configure(o,upper(o));a,b,r=self.result(o,s)
  c,d,second=self.result(o,s);self.assertEqual(r['contact_choices'],second['contact_choices'])
 def test_torus_band_rejected_without_false_cap(self):
  bpy.ops.mesh.primitive_torus_add(major_radius=.05,minor_radius=.015,major_segments=24,minor_segments=12)
  o=bpy.context.object
  with self.assertRaises(ValueError):self.result(o,configure(o,upper(o)))
 def test_cylinder_with_mid_ring(self):
  import math
  vertices=[(.05*math.cos(i*math.tau/24),.05*math.sin(i*math.tau/24),z) for z in (-.05,0,.05) for i in range(24)]
  faces=[tuple(reversed(range(24))),tuple(range(48,72))]
  faces.extend((ring*24+i,ring*24+(i+1)%24,(ring+1)*24+(i+1)%24,(ring+1)*24+i) for ring in range(2) for i in range(24))
  mesh=bpy.data.meshes.new('ring_cylinder');mesh.from_pydata(vertices,[],faces);mesh.update();o=bpy.data.objects.new('Ring cylinder',mesh);bpy.context.scene.collection.objects.link(o)
  a,b,r=self.result(o,configure(o,upper(o)));self.invariant(o,a,b,r)
 def test_pin_clearance_changes_hole_only(self):
  o,s=self.workflow_setup();s.clearance_per_side_mm=.1;self.preview();a=s.part_a_volume_mm3;b=s.part_b_volume_mm3
  s.clearance_per_side_mm=.3;self.preview();self.assertAlmostEqual(a,s.part_a_volume_mm3,delta=.1);self.assertLess(s.part_b_volume_mm3,b)
 def test_contact_edit_rejects_changed_target(self):
  from src.connector_surface import prepare_split_candidates
  o,s=self.workflow_setup();self.preview();o.data.vertices[0].co.x+=.001
  with self.assertRaisesRegex(ValueError,'corte mudou'):prepare_split_candidates(bpy.context,True)
 def test_solid_remains_a_simple_cut_without_pins(self):
  bpy.ops.mesh.primitive_cube_add(size=.1);o=bpy.context.object;s=bpy.context.scene.chest_splitter;s.target_object=o;s.split_mode='SOLID';s.part_clearance_mm=0;s.connector_enabled=False
  bpy.ops.mesh.primitive_cube_add(size=.1,location=(.05,0,0));s.solid_cutter_object=bpy.context.object;s.solid_source='EXISTING'
  self.preview();self.assertFalse(json.loads(s.contact_choices or '[]'))
  s.connector_enabled=True;self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'CANCELLED'})

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegionRelease));sys.exit(not result.wasSuccessful())
