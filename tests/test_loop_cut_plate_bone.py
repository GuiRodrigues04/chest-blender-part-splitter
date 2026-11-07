"""Regression test for loop cut partial edge on Placa_Osso_Chest_Inteira and clearance/margin defaults."""
import os
import sys
import unittest
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src
from src.properties import ChestSplitterSettings
from src.diagnostic import validate_bmesh_mesh_geometry


class TestLoopCutPlateBoneAndDefaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def setUp(self):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh, do_unlink=True)

    def test_new_defaults_and_limits(self):
        """Verify the 4 required defaults and limits:
        1. material_interface_mat_mode default is 'EXTRACTED'
        2. part clearance default is 0.10mm (lateral & bottom)
        3. pin clearance default is 0.15mm side, 0.20mm bottom
        4. connector edge margin min is 0.4mm
        """
        settings = bpy.context.scene.chest_splitter
        
        # 1. Interface material default
        prop_mat = ChestSplitterSettings.bl_rna.properties.get("material_interface_mat_mode")
        self.assertIsNotNone(prop_mat)
        self.assertEqual(prop_mat.default, 'EXTRACTED')
        
        # 2. Part clearance defaults (0.10mm)
        prop_part_clearance = ChestSplitterSettings.bl_rna.properties.get("part_clearance_mm")
        self.assertAlmostEqual(prop_part_clearance.default, 0.10, places=4)
        prop_bottom_clearance = ChestSplitterSettings.bl_rna.properties.get("part_clearance_bottom_mm")
        self.assertAlmostEqual(prop_bottom_clearance.default, 0.10, places=4)

        # 3. Pin clearance defaults (0.15mm side, 0.20mm bottom)
        prop_side = ChestSplitterSettings.bl_rna.properties.get("clearance_per_side_mm")
        self.assertAlmostEqual(prop_side.default, 0.15, places=4)
        prop_end = ChestSplitterSettings.bl_rna.properties.get("end_clearance_mm")
        self.assertAlmostEqual(prop_end.default, 0.20, places=4)

        # 4. Connector edge margin min is 0.4mm
        prop_margin = ChestSplitterSettings.bl_rna.properties.get("connector_edge_margin_mm")
        self.assertAlmostEqual(prop_margin.hard_min, 0.4, places=4)

    def test_plate_bone_partial_loop_cut_manifold(self):
        """Reproduce the 21-vertex planar loop cut on Placa_Osso_Chest_Inteira.blend.
        Ensures both Part A and Part B are closed solids (manifold) with 0 open edges.
        """
        blend_path = Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_Osso_Chest_Inteira.blend")
        if not blend_path.is_file():
            self.skipTest(f"Placa_Osso_Chest_Inteira.blend not found at {blend_path}")

        # Load the mesh from the blend file
        with bpy.data.libraries.load(str(blend_path)) as (data_from, data_to):
            data_to.objects = [name for name in data_from.objects if "Placa_Osso" in name or "Placa" in name]
            if not data_to.objects and data_from.objects:
                data_to.objects = [data_from.objects[0]]

        target_obj = None
        for obj in data_to.objects:
            if obj is not None:
                bpy.context.scene.collection.objects.link(obj)
                target_obj = obj
                break

        self.assertIsNotNone(target_obj, "Target object not loaded from blend")
        bpy.context.view_layer.objects.active = target_obj
        target_obj.select_set(True)

        settings = bpy.context.scene.chest_splitter
        settings.target_object = target_obj
        settings.split_mode = 'LOOP'

        # Select the 21-vertex loop containing reference face #1414
        ref_face_idx = 1414
        bm = bmesh.new()
        bm.from_mesh(target_obj.data)
        bm.faces.ensure_lookup_table()
        ref_face = bm.faces[ref_face_idx]
        ref_n = ref_face.normal.copy()
        ref_d = ref_n.dot(ref_face.verts[0].co)

        coplanar_faces = [
            f for f in bm.faces
            if abs(f.normal.dot(ref_n) - 1.0) < 1e-3 and abs(ref_n.dot(f.verts[0].co) - ref_d) < 1e-3
        ]
        coplanar_f_indices = set(f.index for f in coplanar_faces)

        # Boundary edges of coplanar faces
        boundary_edges = []
        for e in bm.edges:
            c = sum(1 for lf in e.link_faces if lf.index in coplanar_f_indices)
            if c == 1:
                boundary_edges.append(e)

        # Reconstruct connected components
        adj = {}
        for e in boundary_edges:
            v0, v1 = e.verts[0].index, e.verts[1].index
            adj.setdefault(v0, []).append(v1)
            adj.setdefault(v1, []).append(v0)

        visited = set()
        loops = []
        for v in adj:
            if v not in visited:
                comp = []
                stack = [v]
                visited.add(v)
                while stack:
                    curr = stack.pop()
                    comp.append(curr)
                    for nbr in adj[curr]:
                        if nbr not in visited:
                            visited.add(nbr)
                            stack.append(nbr)
                loops.append(comp)

        loop_v_indices = [2130, 2128, 2135, 2131, 2132, 2133, 2134, 2138, 2139, 2004, 2003, 2005, 2006, 2007, 2008, 2012, 2013, 2014, 2015, 3466, 2011]
        settings.loop_is_captured = True
        settings.loop_seed_face_index = 1414
        settings.loop_vertex_indices = ','.join(str(i) for i in loop_v_indices)
        settings.loop_vertex_count = len(loop_v_indices)
        settings.loop_planarity_deviation_mm = 0.0
        settings.loop_is_planar = True

        # Configure settings as specified by user:
        # Depth = 5mm, through_cut = False, clearance = 0, connectors = False
        settings.loop_behavior = 'EXTRUDE'
        settings.loop_extrude_depth_mm = 5.0
        settings.loop_through_cut = False
        settings.part_clearance_mm = 0.0
        settings.part_clearance_bottom_enable = False
        settings.part_clearance_bottom_mm = 0.0
        settings.connector_enabled = False

        # Generate Preview
        res_prev = bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(res_prev, {'FINISHED'}, "Preview generation failed")

        from src.constants import PREVIEW_A_NAME, PREVIEW_B_NAME
        part_a = bpy.data.objects.get(PREVIEW_A_NAME)
        part_b = bpy.data.objects.get(PREVIEW_B_NAME)
        self.assertIsNotNone(part_a, "Preview Part A not generated")
        self.assertIsNotNone(part_b, "Preview Part B not generated")

        # Validate Part A and Part B are closed solids
        bm_chk_a = bmesh.new()
        bm_chk_a.from_mesh(part_a.data)
        val_a = validate_bmesh_mesh_geometry(bm_chk_a)
        bm_chk_a.free()

        bm_chk_b = bmesh.new()
        bm_chk_b.from_mesh(part_b.data)
        val_b = validate_bmesh_mesh_geometry(bm_chk_b)
        bm_chk_b.free()

        self.assertTrue(val_a['is_manifold'], f"Preview Part A not manifold: {val_a}")
        self.assertTrue(val_b['is_manifold'], f"Preview Part B not manifold: {val_b}")
        self.assertEqual(len(val_a['non_manifold_edges']), 0)
        self.assertEqual(len(val_b['non_manifold_edges']), 0)

        # Commit cut
        res_commit = bpy.ops.chest.splitter_commit_parts()
        self.assertEqual(res_commit, {'FINISHED'}, "Commit parts failed")

        final_a = bpy.data.objects.get(f"{target_obj.name}__A")
        final_b = bpy.data.objects.get(f"{target_obj.name}__B")
        self.assertIsNotNone(final_a, "Final Part A not generated")
        self.assertIsNotNone(final_b, "Final Part B not generated")

        bm_chk_fa = bmesh.new()
        bm_chk_fa.from_mesh(final_a.data)
        val_fa = validate_bmesh_mesh_geometry(bm_chk_fa)
        bm_chk_fa.free()

        bm_chk_fb = bmesh.new()
        bm_chk_fb.from_mesh(final_b.data)
        val_fb = validate_bmesh_mesh_geometry(bm_chk_fb)
        bm_chk_fb.free()

        self.assertTrue(val_fa['is_manifold'], f"Final Part A not manifold: {val_fa}")
        self.assertTrue(val_fb['is_manifold'], f"Final Part B not manifold: {val_fb}")
        self.assertEqual(len(val_fa['non_manifold_edges']), 0)
        self.assertEqual(len(val_fb['non_manifold_edges']), 0)

        # Volume conservation: Vol(A) + Vol(B) == Vol(Target)
        bm_orig = bmesh.new()
        bm_orig.from_mesh(target_obj.data)
        vol_orig = bm_orig.calc_volume()
        bm_orig.free()

        bm_fa = bmesh.new()
        bm_fa.from_mesh(final_a.data)
        vol_fa = bm_fa.calc_volume()
        bm_fa.free()

        bm_fb = bmesh.new()
        bm_fb.from_mesh(final_b.data)
        vol_fb = bm_fb.calc_volume()
        bm_fb.free()

        self.assertAlmostEqual(vol_fa + vol_fb, vol_orig, delta=vol_orig * 0.001,
                               msg=f"Volume mismatch: {vol_fa + vol_fb} vs {vol_orig}")

        # Depth verification on Part A (depth should be 5mm)
        # Part A was cut by 5mm prism from top face
        bm_fa = bmesh.new()
        bm_fa.from_mesh(final_a.data)
        z_vals = [ref_n.dot(v.co) for v in bm_fa.verts]
        depth_cut = (max(z_vals) - min(z_vals)) * 1000.0  # meters to mm
        bm_fa.free()
        self.assertAlmostEqual(depth_cut, 5.0, delta=0.1,
                               msg=f"Extruded cut depth should be 5.0mm, got {depth_cut}mm")

        bm.free()


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
