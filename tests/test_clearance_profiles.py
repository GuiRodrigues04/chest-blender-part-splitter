"""Clearance profile behavior, compatibility and Blender persistence."""
import sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import src
src.register()

class ClearanceProfiles(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.s = bpy.context.scene.chest_splitter

    def values(self):
        s=self.s
        return (s.part_clearance_mm, s.part_clearance_bottom_mm,
                s.clearance_per_side_mm, s.end_clearance_mm)

    def assert_values(self, expected):
        for a,b in zip(self.values(),expected):self.assertAlmostEqual(a,b,places=6)

    def test_profiles_preserve_pin_configuration_and_invalidate_preview(self):
        s=self.s
        s.connector_diameter_mm=7.;s.connector_length_mm=4.
        s.connector_distribution='MANUAL';s.connector_male_part='B'
        s.part_clearance_apply_to='BOTH'
        frozen=(s.connector_diameter_mm,s.connector_length_mm,s.connector_distribution,s.connector_male_part,s.part_clearance_apply_to)
        for profile,values in [('NONE',(0.,0.,0.,0.)),('FDM',(.1,.1,.15,.2))]:
            s.session_status='PREVIEW_VALID'
            s.assembly_clearance_preset=profile
            self.assertEqual(s.assembly_clearance_preset,profile)
            self.assert_values(values)
            self.assertFalse(s.part_clearance_bottom_enable)
            self.assertEqual(s.session_status,'PREVIEW_STALE')
            self.assertEqual(frozen,(s.connector_diameter_mm,s.connector_length_mm,s.connector_distribution,s.connector_male_part,s.part_clearance_apply_to))

    def test_manual_edit_preserves_other_values(self):
        s=self.s
        for field,value in [('part_clearance_mm',.23),('part_clearance_bottom_mm',.31),('clearance_per_side_mm',.27),('end_clearance_mm',.35),('part_clearance_bottom_enable',True)]:
            s.assembly_clearance_preset='FDM'
            previous=self.values()
            setattr(s,field,value)
            self.assertEqual(s.assembly_clearance_preset,'CUSTOM')
            for name,old in zip(('part_clearance_mm','part_clearance_bottom_mm','clearance_per_side_mm','end_clearance_mm'),previous):
                if name!=field:self.assertAlmostEqual(getattr(s,name),old)
        previous=self.values();s.assembly_clearance_preset='CUSTOM';self.assertEqual(previous,self.values())

    def test_legacy_values_not_rewritten(self):
        s=self.s
        s.part_clearance_mm=.38;s.end_clearance_mm=.41
        if 'assembly_clearance_preset' in s:del s['assembly_clearance_preset']
        before=self.values()
        self.assertEqual(s.assembly_clearance_preset,'CUSTOM')
        self.assertEqual(before,self.values())

    def test_operator_preview_and_commit(self):
        import src.operators as ops
        import bmesh
        for profile in ('FDM','NONE','CUSTOM'):
            with self.subTest(profile=profile):
                bpy.ops.wm.read_factory_settings(use_empty=True)
                bpy.ops.mesh.primitive_cube_add(size=.04)
                target=bpy.context.object
                self.s=bpy.context.scene.chest_splitter
                s=self.s;s.target_object=target;s.split_mode='PLANE'
                s.connector_enabled=True;s.connector_diameter_mm=4.;s.connector_length_mm=3.
                s.connector_chamfer_mm=.2;s.connector_distribution='CENTER'
                s.commit_next_target='NONE'
                s.assembly_clearance_preset=profile
                if profile=='CUSTOM':s.clearance_per_side_mm=.22
                self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'},s.get_localized_status())
                self.assertTrue(ops.verify_preview_current(bpy.context)[0])
                parts=ops.get_current_session_parts(bpy.context.scene)
                self.assertEqual(len(parts),2)
                before=[]
                for part in parts:
                    bm=bmesh.new();bm.from_mesh(part.data)
                    self.assertTrue(all(e.is_manifold for e in bm.edges))
                    before.append(abs(bm.calc_volume()));bm.free()
                self.assertEqual(bpy.ops.chest.splitter_commit_parts(),{'FINISHED'},s.get_localized_status())
                parts=ops.get_current_session_parts(bpy.context.scene)
                after=[]
                for part in parts:
                    bm=bmesh.new();bm.from_mesh(part.data)
                    self.assertTrue(all(e.is_manifold for e in bm.edges))
                    after.append(abs(bm.calc_volume()));bm.free()
                self.assertEqual(sorted(before),sorted(after))

    def test_panel_has_one_profile_and_no_slicer_export(self):
        from types import SimpleNamespace
        from src.ui import VIEW3D_PT_chest_part_splitter
        class Layout:
            def __init__(self):self.calls=[]
            def __getattr__(self, name):
                def call(*args, **kwargs):
                    self.calls.append((name,args,kwargs))
                    return SimpleNamespace() if name=='operator' else self
                return call
        bpy.ops.mesh.primitive_cube_add(size=.04)
        self.s.target_object=bpy.context.object
        self.s.connector_enabled=True
        layout=Layout()
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=layout),bpy.context)
        props=[args[1] for name,args,kw in layout.calls if name=='prop']
        operators=[args[0] for name,args,kw in layout.calls if name=='operator']
        self.assertEqual(props.count('assembly_clearance_preset'),1)
        self.assertNotIn('export_format',props)
        self.assertNotIn('export_directory',props)
        self.assertNotIn('chest.splitter_apply_connector_preset',operators)
        self.assertNotIn('chest.splitter_export_parts',operators)

    def test_save_reload_profiles_and_custom(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'profiles.blend')
            for profile in ('NONE','FDM','CUSTOM'):
                self.s=bpy.context.scene.chest_splitter
                self.s.assembly_clearance_preset=profile
                if profile=='CUSTOM':self.s.end_clearance_mm=.43
                before=self.values()
                bpy.ops.wm.save_as_mainfile(filepath=path)
                bpy.ops.wm.open_mainfile(filepath=path)
                self.s=bpy.context.scene.chest_splitter
                self.assertEqual(self.s.assembly_clearance_preset,profile)
                self.assertEqual(before,self.values())

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClearanceProfiles))
    sys.exit(not result.wasSuccessful())
