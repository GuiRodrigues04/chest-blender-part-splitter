"""Regression for the real Spot horn's tapered rim at 1 mm clearance.

Uses the optional user supplied Vaquinha.blend fixture when present. The test
is skipped on machines that do not have that external model.
"""
import sys
import os
import unittest
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.geometry_loop import slice_mesh_by_loop

MODEL = Path(os.environ.get(
    'SPLITTER_SPOT_FIXTURE',
    Path.home() / 'OneDrive' / 'Desktop' / 'Modelos 3D e testes extensao' /
    '02_Personagens_e_Criaturas' / 'spot' / 'spot' / 'Vaquinha.blend'))
LOOP = [424,1648,425,1641,423,1659,427,1653,426,1669,429,1663,428,1677,430,1672]


class RealSpotHornClearance(unittest.TestCase):
    def test_one_mm_clearance_at_tapered_horn_rim(self):
        if not MODEL.is_file():
            self.skipTest(f"Optional Spot fixture not available: {MODEL}")
        bpy.ops.wm.open_mainfile(filepath=str(MODEL), use_scripts=False)
        obj = bpy.data.objects['spot_quadrangulated']
        obj.matrix_world = Matrix.Scale(.4, 4) @ obj.matrix_world
        bpy.context.view_layer.update()
        result = slice_mesh_by_loop(obj, obj.name, LOOP, 958,
            scene=bpy.context.scene, part_clearance_mm=1.,
            part_clearance_apply_to='PART')
        try:
            measured = result.interface.clearance_measurements
            self.assertAlmostEqual(measured['requested_mm'], 1.)
            self.assertLessEqual(abs(measured['interior_minimum_mm']-1.), measured['tolerance_mm'])
            self.assertLessEqual(abs(measured['interior_maximum_mm']-1.), measured['tolerance_mm'])
            self.assertGreater(measured['waived_exterior_misses'], 0)
            for part in result:
                self.assertTrue(all(edge.is_manifold for edge in part.edges))
        finally:
            for part in result:
                part.free()


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RealSpotHornClearance)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise RuntimeError('Real Spot horn clearance test failed')
