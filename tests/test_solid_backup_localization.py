import sys, unittest, ast, runpy
from pathlib import Path
from unittest.mock import patch
import bpy
r=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(r))
import src
from src import translations as tr, properties as props
from src.lifecycle import ensure_backups_collection
from src.operators import CHEST_OT_splitter_select_existing_cutter
src.register()

class Changes(unittest.TestCase):
    def test_backups_and_regular_objects(self):
        s=bpy.context.scene.chest_splitter
        target=bpy.data.objects.new('Target',bpy.data.meshes.new('Target'))
        bpy.context.scene.collection.objects.link(target);s.target_object=target
        normal=bpy.data.objects.new('Normal',bpy.data.meshes.new('Normal'))
        bpy.context.scene.collection.objects.link(normal)
        self.assertTrue(props._poll_mesh_cutter(s,normal))
        self.assertFalse(props._poll_mesh_cutter(s,target))
        # A user object named Backup stays usable; internal tags identify snapshots.
        normal.name='Backup';self.assertTrue(props._poll_mesh_cutter(s,normal))
        normal['chest_role']='RESTORE_BACKUP'
        self.assertFalse(props._poll_mesh_cutter(s,normal))
        bpy.context.view_layer.objects.active=normal
        self.assertFalse(CHEST_OT_splitter_select_existing_cutter.poll(bpy.context))
        del normal['chest_role']
        col=ensure_backups_collection(bpy.context.scene)
        child=bpy.data.collections.new('Nested backups');col.children.link(child)
        child.objects.link(normal)
        self.assertFalse(props._poll_mesh_cutter(s,normal))
        child.objects.unlink(normal)
        self.assertTrue(props._poll_mesh_cutter(s,normal))

    def test_locale_switch_and_new_texts(self):
        for locale in ('en_US','pt_BR','en_US'):
            bpy.context.preferences.view.language=locale
            self.assertEqual(tr.get_addon_locale(),locale)
            for pt,en in tr._RELEASE_0829_PAIRS+tr._REGION_0829_PAIRS:
                self.assertEqual(tr.localize_text(pt),en if locale=='en_US' else pt)
                self.assertEqual(tr.localize_text(en),en if locale=='en_US' else pt)
        self.assertEqual(set(tr.TRANSLATIONS_DICT['pt_BR']),set(tr.TRANSLATIONS_DICT['en_US']))

    def test_full_source_catalog_coverage(self):
        # Reuse the AST extraction used by the maintenance audit and fail on gaps.
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            audit=runpy.run_path(str(r/'scripts/audit_translations.py'))
        self.assertEqual(audit['missing_en'],[])
        for filename,line,text,kind in audit['extracted_strings']:
            if len(text)>1 and not audit['re'].match(r'^[\d\.\s\-_/\\:]+$',text):
                self.assertIn(('*',text),tr.TRANSLATIONS_DICT['pt_BR'],(filename,line,text))

suite=unittest.defaultTestLoader.loadTestsFromTestCase(Changes)
result=unittest.TextTestRunner(verbosity=2).run(suite)
src.unregister()
if not result.wasSuccessful():raise RuntimeError('0.8.29 regression failed')
