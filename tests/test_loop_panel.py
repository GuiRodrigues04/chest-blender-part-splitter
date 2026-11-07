"""Keep the Loop method selector fixed and display only applicable inputs."""
import sys, unittest
from pathlib import Path
from types import SimpleNamespace
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src
from src.ui import VIEW3D_PT_chest_part_splitter

class LoopPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls): src.register()
    @classmethod
    def tearDownClass(cls): src.unregister()
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=.1)
        self.settings = bpy.context.scene.chest_splitter
        self.settings.target_object = bpy.context.object
        self.settings.split_mode = 'LOOP'; self.settings.connector_enabled = False
    def draw(self):
        events = []
        class Layout:
            def row(self,*a,**k): return self
            column=box=split=grid_flow=row
            def label(self,*a,**k): events.append(('label',k.get('text','')))
            def separator(self,*a,**k): pass
            def template_list(self,*a,**k): pass
            def prop(self,obj,name,*a,**k): getattr(obj,name);events.append(('prop',name))
            def operator(self,name,*a,**k):
                namespace,op=name.split('.');getattr(getattr(bpy.ops,namespace),op).get_rna_type()
                events.append(('operator',name));return SimpleNamespace()
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=Layout()),bpy.context)
        return events
    def test_selector_position_and_order_stable_in_all_modes(self):
        before = None
        identifiers = [i.identifier for i in self.settings.bl_rna.properties['loop_behavior'].enum_items]
        self.assertEqual(identifiers,['AUTO','DETACH','EXTRUDE','WHOLE'])
        for mode in ('AUTO','WHOLE','DETACH','EXTRUDE','WHOLE','AUTO'):
            with self.subTest(mode=mode):
                self.settings.loop_behavior=mode; events=self.draw()
                self.assertEqual(events.count(('prop','loop_behavior')),1)
                prefix=events[:events.index(('prop','loop_behavior'))+1]
                if before is None: before=prefix
                self.assertEqual(prefix,before)
                captures=[i for i,(kind,name) in enumerate(events) if kind=='operator' and name in ('chest.splitter_capture_region','chest.splitter_capture_loop','chest.splitter_capture_face_boundary')]
                self.assertTrue(captures);self.assertLess(events.index(('prop','loop_behavior')),min(captures))
                self.assertLess(events.index(('operator','chest.splitter_edit_target')),min(captures))
    def test_only_relevant_capture_and_depth_controls(self):
        for mode in ('AUTO','DETACH','EXTRUDE','WHOLE'):
            with self.subTest(mode=mode):
                self.settings.loop_behavior=mode;events=self.draw()
                self.assertEqual(('operator','chest.splitter_capture_region') in events,mode=='WHOLE')
                self.assertEqual(('operator','chest.splitter_capture_loop') in events,mode!='WHOLE')
                self.assertEqual(('operator','chest.splitter_define_seed_face') in events,mode!='WHOLE')
                if mode=='WHOLE':
                    self.assertNotIn(('prop','loop_extrude_depth_mm'),events)
                    self.assertNotIn(('prop','loop_detach_add_base'),events)
                if mode=='EXTRUDE':self.assertIn(('prop','loop_extrude_depth_mm'),events)

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
