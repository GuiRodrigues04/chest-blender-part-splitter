import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from types import SimpleNamespace
from unittest.mock import patch
from src import history
from src.constants import ROLE_COMMITTED_PART, COLLECTION_PARTS_NAME
from src.lifecycle import get_or_create_collection


class HistoryTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene=bpy.context.scene
        self.obj=bpy.data.objects.new('Gato__B__B',bpy.data.meshes.new('Mesh'))
        self.parts=get_or_create_collection(self.scene,COLLECTION_PARTS_NAME)
        self.parts.objects.link(self.obj)
        self.obj['chest_role']=ROLE_COMMITTED_PART

    def test_archive_is_reversible_and_eye_controls_visibility(self):
        ptr=self.obj.as_pointer()
        history.archive_target(self.scene,self.obj)
        self.assertNotIn(self.obj.name,self.parts.objects)
        self.assertTrue(self.obj.hide_get())
        self.assertFalse(self.obj.hide_viewport)
        self.obj.hide_set(False)
        self.assertTrue(self.obj.visible_get())
        history.restore_target(self.scene,self.obj)
        self.assertIn(self.obj.name,self.parts.objects)
        self.assertEqual(self.obj.as_pointer(),ptr)

    def test_user_objects_are_not_archived(self):
        del self.obj['chest_role']
        history.archive_target(self.scene,self.obj)
        self.assertIn(self.obj.name,self.parts.objects)

    def test_registration_defers_scene_access_in_restricted_context(self):
        try:
            with patch.object(history.bpy,'data',SimpleNamespace()), \
                 patch.object(history,'on_load') as organize, \
                 patch.object(history.bpy.app.timers,'is_registered',return_value=False), \
                 patch.object(history.bpy.app.timers,'register') as schedule:
                history.register()
                organize.assert_not_called()
                schedule.assert_called_once_with(history._after_register,first_interval=.1)
                # Remove the mocked handler while its identity is still bound.
                if organize in bpy.app.handlers.load_post:
                    bpy.app.handlers.load_post.remove(organize)
        finally:
            history.unregister()

    def test_short_names_and_manual_rename(self):
        root,number=history.result_names(self.scene,self.obj,'_work_copy')
        self.assertEqual(root,'Gato')
        self.obj.name='Gato — Restante 001'
        self.obj['chest_default_name']=self.obj.name
        self.obj['chest_name_root']='Gato'
        self.assertEqual(history.result_names(self.scene,self.obj,'_work_copy')[0],'Gato')
        self.obj.name='Bigode do gato'
        self.assertEqual(history.result_names(self.scene,self.obj,'_work_copy')[0],'Bigode do gato')


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HistoryTests))
    if not result.wasSuccessful():raise SystemExit(1)
