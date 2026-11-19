"""General clearance preserves individual settings and invalidates previews."""
import sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import src
from src.clearance import bottom_clearance, radial_clearance, end_clearance
from src.input_state import editor_configuration
from src.operators import compute_session_input_signature
src.register()

class GeneralClearance(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=.04)
        self.s = bpy.context.scene.chest_splitter
        self.s.target_object = bpy.context.object

    def test_toggle_preserves_values_and_invalidates(self):
        s=self.s
        self.assertFalse(s.clearance_use_general)
        s.part_clearance_mm=.3; s.part_clearance_bottom_enable=True
        s.part_clearance_bottom_mm=.4; s.clearance_per_side_mm=.2; s.end_clearance_mm=.5
        original=(s.part_clearance_bottom_mm,s.clearance_per_side_mm,s.end_clearance_mm)
        self.assertAlmostEqual(bottom_clearance(s),.4)
        before=editor_configuration(s,bpy.context.scene)
        signature=compute_session_input_signature(bpy.context)
        s.session_status='PREVIEW_VALID'; s.clearance_use_general=True
        self.assertEqual(s.session_status,'PREVIEW_STALE')
        self.assertNotEqual(before,editor_configuration(s,bpy.context.scene))
        self.assertNotEqual(signature,compute_session_input_signature(bpy.context))
        self.assertIsNone(bottom_clearance(s))
        self.assertAlmostEqual(radial_clearance(s),.3)
        self.assertAlmostEqual(end_clearance(s),.3)
        self.assertEqual(original,(s.part_clearance_bottom_mm,s.clearance_per_side_mm,s.end_clearance_mm))
        s.clearance_use_general=False
        self.assertAlmostEqual(bottom_clearance(s),.4)
        self.assertAlmostEqual(radial_clearance(s),.2)
        self.assertAlmostEqual(end_clearance(s),.5)

    def test_pin_geometry_matches_equivalent_individual_settings(self):
        import bmesh
        from src.operators import get_current_session_parts
        s=self.s; s.split_mode='PLANE'; s.connector_enabled=True
        s.connector_diameter_mm=4.; s.connector_length_mm=3.; s.connector_chamfer_mm=.2
        s.part_clearance_mm=.3; s.clearance_per_side_mm=.05; s.end_clearance_mm=.05
        s.clearance_use_general=True
        def volumes():
            self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'}, s.get_localized_status())
            result=[]
            for part in get_current_session_parts(bpy.context.scene):
                bm=bmesh.new(); bm.from_mesh(part.data)
                result.append(abs(bm.calc_volume())); bm.free()
            return result
        general=volumes()
        s.clearance_use_general=False; s.clearance_per_side_mm=.3; s.end_clearance_mm=.3
        individual=volumes()
        self.assertEqual(len(general),2)
        for a,b in zip(general,individual): self.assertAlmostEqual(a,b,places=10)

    def test_save_and_profile(self):
        s=self.s; s.clearance_per_side_mm=.27; s.clearance_use_general=True
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'settings.blend')
            bpy.ops.wm.save_as_mainfile(filepath=path); bpy.ops.wm.open_mainfile(filepath=path)
            s=bpy.context.scene.chest_splitter
            self.assertTrue(s.clearance_use_general)
            self.assertAlmostEqual(s.clearance_per_side_mm,.27)
            s.assembly_clearance_preset='FDM'
            self.assertFalse(s.clearance_use_general)
            self.assertAlmostEqual(radial_clearance(s),.15)
            self.assertAlmostEqual(end_clearance(s),.2)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GeneralClearance))
    sys.exit(not result.wasSuccessful())
