"""Material assignment must cover the complete extracted part, including pins."""
import sys, unittest
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_region_release import sphere, upper, configure, CAT
import src
from src.geometry_region import slice_region, CONTACT, mesh_signature


class WholeRegionMaterial(unittest.TestCase):
    @classmethod
    def setUpClass(cls): src.register()
    @classmethod
    def tearDownClass(cls): src.unregister()
    def setUp(self):
        if bpy.context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.wm.read_factory_settings(use_empty=True)
    def setup_piece(self):
        o, _ = sphere()
        for name in ('Body', 'Orange'): o.data.materials.append(bpy.data.materials.new(name))
        ids = upper(o)
        for f in o.data.polygons: f.material_index = int(f.index in ids)
        s = configure(o, ids); s.split_mode = 'MATERIAL'; s.material_extraction_mode = 'WHOLE'; s.material_split_index = 1
        s.material_interface_mat_mode = 'EXTRACTED'; s.connector_enabled = False
        return o, s
    def result(self, o, s):
        a = bpy.data.meshes.new('A'); b = bpy.data.meshes.new('B')
        return a, b, slice_region(o, s, bpy.context.scene, a, b)
    def test_raw_piece_all_material_without_geometry_change(self):
        o, s = self.setup_piece(); before = mesh_signature(o.data)
        s.material_interface_mat_mode = 'SOURCE'; a, b, raw = self.result(o, s)
        s.material_interface_mat_mode = 'EXTRACTED'; c, d, colored = self.result(o, s)
        self.assertEqual({f.material_index for f in c.polygons}, {1})
        self.assertEqual([tuple(v.co) for v in a.vertices], [tuple(v.co) for v in c.vertices])
        self.assertEqual([tuple(f.vertices) for f in a.polygons], [tuple(f.vertices) for f in c.polygons])
        self.assertEqual([f.material_index for f in b.polygons], [f.material_index for f in d.polygons])
        self.assertEqual(raw['sum_volume_mm3'], colored['sum_volume_mm3'])
        self.assertEqual(mesh_signature(o.data), before)
    def test_source_option_keeps_body_interface(self):
        o, s = self.setup_piece(); s.material_interface_mat_mode = 'SOURCE'
        a, b, _ = self.result(o, s)
        self.assertEqual({f.material_index for f in a.polygons}, {0, 1})
        self.assertEqual({f.material_index for f in a.polygons if a.attributes[CONTACT].data[f.index].value}, {0})
    def test_face_selection_cut_keeps_original_materials(self):
        o, s = self.setup_piece(); s = configure(o, upper(o))
        a, b, _ = self.result(o, s)
        self.assertEqual({f.material_index for f in a.polygons}, {0, 1})
    def test_pins_gap_both_male_sides_and_commit_keep_uniform_piece(self):
        o, s = self.setup_piece()
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
        self.assertEqual(bpy.ops.chest.splitter_choose_contact(index=0), {'FINISHED'})
        s.connector_enabled = True; s.connector_distribution = 'LINEAR_2'; s.connector_diameter_mm = 5; s.connector_length_mm = 6; s.part_clearance_mm = .1
        for male in ('A', 'B'):
            s.connector_male_part = male
            self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
            a = bpy.data.objects['SPLITTER_PREVIEW_A']; self.assertEqual({f.material_index for f in a.data.polygons}, {1})
            self.assertTrue(s.part_a_is_manifold and s.part_b_is_manifold)
        self.assertEqual(bpy.ops.chest.splitter_commit_parts(), {'FINISHED'})
        self.assertEqual({f.material_index for f in a.data.polygons}, {1})
    def test_cat_orange_paw_caps_and_pins(self):
        if not CAT.exists(): self.skipTest('Cat fixture unavailable')
        bpy.ops.wm.open_mainfile(filepath=str(CAT), use_scripts=False)
        if bpy.context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        o = bpy.data.objects['Gato Cinza Retopology']; before = mesh_signature(o.data)
        s = bpy.context.scene.chest_splitter; s.target_object = o; s.split_mode = 'MATERIAL'; s.material_extraction_mode = 'WHOLE'; s.material_split_index = 4; s.material_region_index = 0
        s.material_interface_mat_mode = 'EXTRACTED'; s.connector_enabled = False; s.part_clearance_mm = 0; s.contact_patch_index = -1
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
        self.assertEqual(bpy.ops.chest.splitter_choose_contact(index=0), {'FINISHED'})
        s.connector_enabled = True; s.connector_distribution = 'LINEAR_2'; s.connector_diameter_mm = 8; s.connector_length_mm = 12; s.part_clearance_mm = .1
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
        self.assertEqual({f.material_index for f in bpy.data.objects['SPLITTER_PREVIEW_A'].data.polygons}, {4})
        self.assertGreater(len({f.material_index for f in bpy.data.objects['SPLITTER_PREVIEW_B'].data.polygons}), 1)
        self.assertEqual(mesh_signature(o.data), before)


if __name__ == '__main__': unittest.main(argv=[sys.argv[0]], verbosity=2)
