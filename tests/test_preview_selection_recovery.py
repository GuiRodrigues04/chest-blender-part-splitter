"""Preview discard restores target access and retires stale solid pickers."""
import sys,unittest,hashlib,tempfile
from pathlib import Path
from types import SimpleNamespace,MethodType
from unittest.mock import patch
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
import src.solid_tools as st
from src.solid_tools import CHEST_OT_splitter_align_solid_vertices as Picker
from src.geometry_solid import create_primitive_cutter_mesh
from src.lifecycle import remove_preview
from src.scene_state import activate_target_for_selection
from src.connector_editor import get_editor_interaction_state

class SelectionRecovery(unittest.TestCase):
 @classmethod
 def setUpClass(cls):src.register()
 @classmethod
 def tearDownClass(cls):src.unregister()
 def setUp(self):
  st.stop_solid_alignment()
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  bpy.ops.wm.read_factory_settings(use_empty=True)
  self.s=bpy.context.scene.chest_splitter;self.t=self.cube('Target',(.1,.1,.1));self.c=self.cube('Cutter',(.1,.1,.1),(.05,0,0))
  self.s.target_object=self.t;self.s.split_mode='SOLID';self.s.solid_source='EXISTING';self.s.solid_cutter_object=self.c;self.s.part_clearance_mm=0;self.s.connector_enabled=False
  self.area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');self.region=next(r for r in self.area.regions if r.type=='WINDOW')
 def tearDown(self):
  st.stop_solid_alignment()
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
 def cube(self,name,dims,center=(0,0,0)):
  o=bpy.data.objects.new(name,create_primitive_cutter_mesh(name,'BOX',Vector(dims)));bpy.context.scene.collection.objects.link(o);o.location=center;bpy.context.view_layer.update();return o
 def preview(self):self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
 def edit(self,o):
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  for item in bpy.context.view_layer.objects:item.select_set(False)
  o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.mode_set(mode='EDIT')
 def harness(self,mode='VERTEX',stage=1,register=False):
  self.edit(self.t if stage==1 and mode=='OBJECT' else self.c)
  h=SimpleNamespace(move_mode=mode,cutter_vertex=0,target_vertex=-1,_cutter_obj=self.c,_target_obj=self.t,_stage=stage,_hover=None,_handle=None,_area=self.area,_orig_active=self.c,_orig_mode='EDIT_MESH',_orig_selected=[self.c],_generation=st._ALIGNMENT_GENERATION,report=lambda *a:None)
  for method in ('modal','_cleanup','execute'):setattr(h,method,MethodType(getattr(Picker,method),h))
  if register:st._ACTIVE_ALIGNMENT=h
  return h
 def event(self,event_type='LEFTMOUSE'):
  return SimpleNamespace(type=event_type,value='PRESS',mouse_x=self.region.x+30,mouse_y=self.region.y+30,alt=False)
 def old_event(self,h,key='LEFTMOUSE'):
  with patch('src.connector_editor.get_view3d_canvas_region',return_value=self.region),patch('src.solid_tools.view3d_utils.location_3d_to_region_2d',return_value=Vector((5000,5000))):return h.modal(bpy.context,self.event(key))
 def accessible(self):
  self.assertEqual(bpy.context.mode,'OBJECT');self.assertEqual(bpy.context.active_object,self.t);self.assertEqual(self.s.target_object,self.t);self.assertTrue(self.t.select_get());self.assertIn(self.t,bpy.context.selectable_objects);self.assertTrue(self.t.visible_get())
  self.assertEqual(bpy.ops.chest.splitter_edit_target(),{'FINISHED'});self.assertEqual(bpy.context.edit_object,self.t)
 def test_old_alignment_passes_first_click_after_generate_and_discard(self):
  for mode in ('VERTEX','OBJECT'):
   for stage in (0,1):
    with self.subTest(mode=mode,stage=stage):
     h=self.harness(mode,stage,True);before=[tuple(v.co) for v in self.c.data.vertices]
     self.preview();self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'});self.assertIn('PASS_THROUGH',self.old_event(h));self.accessible()
     if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
     self.assertEqual(before,[tuple(v.co) for v in self.c.data.vertices])
 def test_stale_tab_does_not_swallow_edit_shortcut(self):
  h=self.harness();self.preview();bpy.ops.chest.splitter_remove_preview();self.assertIn('PASS_THROUGH',self.old_event(h,'TAB'));self.accessible()
 def test_cancel_on_context_object_mode_change(self):
  h=self.harness();bpy.ops.object.mode_set(mode='OBJECT');self.assertIn('PASS_THROUGH',self.old_event(h));self.assertIsNone(h._hover)
 def test_tab_retires_current_picker_without_restoring_old_mode(self):
  h=self.harness(register=True);self.assertIn('PASS_THROUGH',self.old_event(h,'TAB'));self.assertIsNone(st._ACTIVE_ALIGNMENT)
 def test_older_picker_cannot_clear_new_header_or_active_picker(self):
  old=self.harness();st.stop_solid_alignment();new=SimpleNamespace();st._ACTIVE_ALIGNMENT=new;calls=[]
  old._area=SimpleNamespace(header_text_set=lambda value:calls.append(value),tag_redraw=lambda:None)
  self.assertIn('PASS_THROUGH',self.old_event(old));self.assertEqual(calls,[]);self.assertIs(st._ACTIVE_ALIGNMENT,new);st._ACTIVE_ALIGNMENT=None
 def test_switch_target_retires_without_returning_to_cutter(self):
  h=self.harness(register=True);other=self.cube('Other',(.04,.04,.04));self.s.target_object=other
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  activate_target_for_selection(bpy.context,other);self.assertIn('PASS_THROUGH',self.old_event(h));self.assertEqual(bpy.context.active_object,other)
 def test_switch_cutter_retires_picker(self):
  h=self.harness();self.s.solid_cutter_object=self.cube('Other cutter',(.03,.03,.03));self.assertIn('PASS_THROUGH',self.old_event(h))
 def test_edit_target_ends_alignment_and_pin_editor(self):
  h=self.harness(register=True);self.s.is_editing_connectors=True;get_editor_interaction_state()['is_active']=True
  self.assertEqual(bpy.ops.chest.splitter_edit_target(),{'FINISHED'});self.assertFalse(self.s.is_editing_connectors);self.assertFalse(get_editor_interaction_state()['is_active']);self.assertIn('PASS_THROUGH',self.old_event(h));self.assertEqual(bpy.context.edit_object,self.t)
 def test_discard_direct_api_ends_pin_editor_and_vertex_picker(self):
  self.preview();h=self.harness(register=True);self.s.is_editing_connectors=True;get_editor_interaction_state()['is_active']=True
  ok,msg=remove_preview(bpy.context,op_id=self.s.session_id);self.assertTrue(ok,msg);self.assertFalse(self.s.is_editing_connectors);self.assertIn('PASS_THROUGH',self.old_event(h));self.accessible()
 def test_discard_clears_object_selection_lock(self):
  self.preview();self.t.hide_select=True;self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'});self.assertFalse(self.t.hide_select);self.accessible()
 def target_collection(self):
  parent=bpy.data.collections.new('Target parent');child=bpy.data.collections.new('Target only');bpy.context.scene.collection.children.link(parent);parent.children.link(child)
  for col in tuple(self.t.users_collection):col.objects.unlink(self.t)
  child.objects.link(self.t);bpy.context.view_layer.update()
  return parent,child
 def test_discard_unlocks_nested_collection_without_unlocking_unrelated_collection(self):
  parent,child=self.target_collection();other=bpy.data.collections.new('Untouched locked');bpy.context.scene.collection.children.link(other);other.hide_select=True
  self.preview();parent.hide_select=True;child.hide_select=True
  self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'});self.assertFalse(parent.hide_select);self.assertFalse(child.hide_select);self.assertTrue(other.hide_select);self.accessible()
 def test_discard_reveals_excluded_target_path(self):
  parent,child=self.target_collection();self.preview();layer=bpy.context.view_layer.layer_collection.children[parent.name];layer.exclude=True
  self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'});self.assertFalse(layer.exclude);self.accessible()
 def test_discard_reveals_collection_hide_viewport(self):
  parent,child=self.target_collection();self.preview();parent.hide_viewport=True;child.hide_viewport=True
  self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'});self.assertFalse(parent.hide_viewport);self.assertFalse(child.hide_viewport);self.accessible()
 def test_local_view_target_is_restored_without_leaving_local_view(self):
  self.preview();a=bpy.data.objects['SPLITTER_PREVIEW_A'];bpy.ops.object.select_all(action='DESELECT');a.select_set(True);bpy.context.view_layer.objects.active=a
  with bpy.context.temp_override(area=self.area,region=self.region):
   bpy.ops.view3d.localview(frame_selected=False);self.assertIsNotNone(self.area.spaces.active.local_view);self.assertFalse(self.t.local_view_get(self.area.spaces.active));self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'})
   self.assertIsNotNone(self.area.spaces.active.local_view);self.assertTrue(self.t.local_view_get(self.area.spaces.active));self.accessible();bpy.ops.object.mode_set(mode='OBJECT');bpy.ops.view3d.localview(frame_selected=False)
 def test_edit_target_unlocks_current_target(self):
  self.t.hide_select=True;self.t.hide_set(True)
  self.assertEqual(bpy.ops.chest.splitter_edit_target(),{'FINISHED'});self.assertEqual(bpy.context.edit_object,self.t);self.assertFalse(self.t.hide_select)
 def test_repeated_preview_discard_preserves_target_and_cutter_geometry(self):
  geometry=lambda obj:([tuple(v.co) for v in obj.data.vertices],[tuple(f.vertices) for f in obj.data.polygons],tuple(tuple(row) for row in obj.matrix_world))
  before=(geometry(self.t),geometry(self.c))
  for _ in range(5):self.preview();self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'});self.accessible();bpy.ops.object.mode_set(mode='OBJECT')
  self.assertEqual(before,(geometry(self.t),geometry(self.c)))
 def test_discard_from_preview_edit_mode(self):
  self.preview();self.edit(bpy.data.objects['SPLITTER_PREVIEW_A']);self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'});self.accessible()
 def test_commit_revert_and_editor_shutdown(self):
  self.preview();self.assertEqual(bpy.ops.chest.splitter_commit_parts(),{'FINISHED'});self.assertEqual(bpy.ops.chest.splitter_revert_cut(),{'FINISHED'});self.accessible()
 def test_missing_area_during_cleanup_does_not_trap_modal(self):
  h=self.harness(register=True)
  def gone(*args):raise ReferenceError('Area removed')
  h._area=SimpleNamespace(header_text_set=gone,tag_redraw=gone)
  st.stop_solid_alignment();self.assertIsNone(st._ACTIVE_ALIGNMENT);self.assertIsNone(h._hover)
  self.assertIn('PASS_THROUGH',self.old_event(h))
 def test_restore_failure_reports_failure_instead_of_success(self):
  self.preview()
  with patch('src.scene_state.activate_target_for_selection',side_effect=RuntimeError('blocked test target')):
   ok,msg=remove_preview(bpy.context,op_id=self.s.session_id)
  self.assertFalse(ok);self.assertIn('blocked test target',msg);self.assertEqual(self.s.last_status_level,'WARNING')
 def test_saved_cat_cycle_and_source_unchanged(self):
  source=Path(r'C:/Users/guiro/OneDrive/Documentos/ChatGPT/Extensão Blender/regioes-0.8.24/Gato_pata_regiao_0.8.24.blend')
  if not source.exists():self.skipTest('Private cat example unavailable')
  digest=hashlib.sha256(source.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False);self.s=bpy.context.scene.chest_splitter;self.t=self.s.target_object
  for _ in range(2):
   self.preview();self.assertEqual(bpy.ops.chest.splitter_remove_preview(),{'FINISHED'});self.accessible();bpy.ops.object.mode_set(mode='OBJECT')
  self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),digest)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SelectionRecovery));sys.exit(not result.wasSuccessful())
