"""Blender regressions for material patch-prism cutter tessellation."""
import sys
import unittest
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.geometry_material import create_material_patch_prism_cutter
from src.diagnostic import get_scene_scale_to_mm


class MaterialPatchPrism(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 1.0

    def test_warped_quad_uses_visible_triangles_at_requested_depths(self):
        vertices = [(-.02, -.02, 0.0), (.02, -.02, 0.0),
                    (.02, .02, .004), (-.02, .02, 0.0)]
        mesh = bpy.data.meshes.new("WarpedSource")
        mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
        mesh.update()
        mesh.calc_loop_triangles()
        source_triangles = {tuple(sorted(tri.vertices)) for tri in mesh.loop_triangles}
        obj = bpy.data.objects.new("WarpedSource", mesh)
        bpy.context.scene.collection.objects.link(obj)
        scale_to_mm = get_scene_scale_to_mm(bpy.context.scene)
        inward = Vector((0.0, 0.0, -1.0))
        outward_ext = .001
        source = [Vector(co) for co in vertices]

        for depth_mm in (1, 2, 5, 10, 15):
            cutter = create_material_patch_prism_cutter(
                obj=obj,
                region_face_indices=[0],
                inward_dir=inward,
                depth_bu=depth_mm / scale_to_mm,
                outward_ext_bu=outward_ext,
                name=f"WarpedCutter_{depth_mm}",
            )
            try:
                top_lookup = {
                    tuple(round(float(c), 8) for c in p - outward_ext * inward): i
                    for i, p in enumerate(source)
                }
                bottom_lookup = {
                    tuple(round(float(c), 8) for c in p + (depth_mm / scale_to_mm) * inward): i
                    for i, p in enumerate(source)
                }
                top_triangles = set()
                bottom_triangles = set()
                for poly in cutter.data.polygons:
                    coords = [cutter.data.vertices[i].co for i in poly.vertices]
                    top_keys = [tuple(round(float(c), 8) for c in p) for p in coords]
                    if all(key in top_lookup for key in top_keys):
                        top_triangles.add(tuple(sorted(top_lookup[key] for key in top_keys)))
                    bottom_keys = [tuple(round(float(c), 8) for c in p) for p in coords]
                    if all(key in bottom_lookup for key in bottom_keys):
                        bottom_triangles.add(tuple(sorted(bottom_lookup[key] for key in bottom_keys)))
                self.assertEqual(top_triangles, source_triangles)
                self.assertEqual(bottom_triangles, source_triangles)
                for i, p in enumerate(source):
                    bottom = p + depth_mm / scale_to_mm * inward
                    self.assertAlmostEqual((bottom - p).dot(inward) * scale_to_mm, depth_mm, delta=.01)
            finally:
                mesh_cutter = cutter.data
                bpy.data.objects.remove(cutter, do_unlink=True)
                bpy.data.meshes.remove(mesh_cutter)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(MaterialPatchPrism))
    if not result.wasSuccessful():
        raise SystemExit(1)
