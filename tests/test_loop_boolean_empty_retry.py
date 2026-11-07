"""Empty Boolean output must try the alternate LOOP solver, then stay strict."""
import sys
import unittest
from pathlib import Path
from unittest import mock

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import geometry_loop as gl


class LoopBooleanEmptyRetry(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_empty_and_zero_volume_outputs_are_solver_failures(self):
        empty = bmesh.new()
        plane = bmesh.new()
        plane.from_mesh(bpy.data.meshes.new("ZeroVolumePlane"))
        plane.verts.ensure_lookup_table()
        bmesh.ops.create_circle(plane, cap_ends=True, radius=1.0, segments=4)
        plane.normal_update()
        solid = bmesh.new()
        bmesh.ops.create_cube(solid, size=1.0)
        try:
            with self.assertRaises(gl.LoopBooleanError):
                gl._raise_for_empty_loop_boolean_result(empty, solid, 1000.0)
            with self.assertRaises(gl.LoopBooleanError):
                gl._raise_for_empty_loop_boolean_result(plane, solid, 1000.0)
            gl._raise_for_empty_loop_boolean_result(solid, solid, 1000.0)
        finally:
            empty.free()
            plane.free()
            solid.free()

    def test_empty_boolean_error_retries_with_manifold_solver(self):
        solvers = {
            item.identifier
            for item in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items
        }
        if "MANIFOLD" not in solvers:
            self.skipTest("Blender build does not expose the MANIFOLD Boolean solver")
        success = object()
        with mock.patch.object(
            gl,
            "_slice_mesh_by_loop_extrude",
            side_effect=[gl.LoopBooleanError("empty EXACT result"), success],
        ) as backend:
            result = gl.slice_mesh_by_loop_extrude(
                None, "test", [], 0, 1.0
            )
        self.assertIs(result, success)
        self.assertEqual(backend.call_count, 2)
        self.assertEqual(backend.call_args_list[0].kwargs.get("_solver", "EXACT"), "EXACT")
        self.assertEqual(backend.call_args_list[1].kwargs["_solver"], "MANIFOLD")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
