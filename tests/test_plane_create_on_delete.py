"""
Unit and regression test for plane guide recreation when deleted in Planar Cut mode.
Requirement: When the cutting plane is deleted, an option "Criar Plano" becomes available
only when the previous plane was deleted. When the plane exists, "Criar Plano" is disabled
and "Focar Guia 3D" is available.
"""

import unittest
import bpy
from mathutils import Vector, Euler


class TestPlaneCreateOnDelete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Register addon if needed
        import sys
        import os
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if repo_dir not in sys.path:
            sys.path.insert(0, repo_dir)
        import src
        src.register()

    @classmethod
    def tearDownClass(cls):
        import src
        try:
            src.unregister()
        except Exception:
            pass

    def setUp(self):
        # Clean scene
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)

        # Create target cube
        bpy.ops.mesh.primitive_cube_add(size=50.0, location=(0, 0, 0))
        self.target = bpy.context.active_object
        self.target.name = "TestTargetCube"

        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter
        self.settings.target_object = self.target
        self.settings.split_mode = 'PLANE'

    def tearDown(self):
        self.settings.target_object = None
        # Clean all mesh objects
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

    def test_plane_create_poll_and_lifecycle(self):
        from src.operators import (
            PLANE_GUIDE_NAME,
            is_plane_guide_present,
            CHEST_OT_splitter_create_plane,
            CHEST_OT_splitter_create_or_focus_guide,
            ensure_plane_guide,
        )

        # 1. Initially, plane guide does not exist
        if bpy.data.objects.get(PLANE_GUIDE_NAME):
            bpy.data.objects.remove(bpy.data.objects[PLANE_GUIDE_NAME], do_unlink=True)

        self.assertFalse(is_plane_guide_present(bpy.context))
        # "Criar Plano" operator poll must be TRUE (available to create)
        self.assertTrue(CHEST_OT_splitter_create_plane.poll(bpy.context))
        # "Focar Guia 3D" poll must be FALSE (no plane to focus)
        self.assertFalse(CHEST_OT_splitter_create_or_focus_guide.poll(bpy.context))

        # 2. Call operator to create the plane
        res = bpy.ops.chest.splitter_create_plane()
        self.assertEqual(res, {'FINISHED'})

        # Now plane exists
        self.assertTrue(is_plane_guide_present(bpy.context))
        guide_obj = bpy.data.objects.get(PLANE_GUIDE_NAME)
        self.assertIsNotNone(guide_obj)
        self.assertIn(guide_obj.name, self.scene.objects)
        self.assertEqual(bpy.context.view_layer.objects.active, guide_obj)

        # "Criar Plano" operator poll must now be FALSE (disabled because plane already exists)
        self.assertFalse(CHEST_OT_splitter_create_plane.poll(bpy.context))
        # "Focar Guia 3D" poll must now be TRUE
        self.assertTrue(CHEST_OT_splitter_create_or_focus_guide.poll(bpy.context))

        # 3. Simulate user orienting or moving the plane
        self.settings.plane_normal = (0.0, 1.0, 0.0)
        self.settings.plane_origin = (10.0, 5.0, 0.0)

        # 4. User deletes the plane from the scene
        bpy.data.objects.remove(guide_obj, do_unlink=True)
        self.assertFalse(is_plane_guide_present(bpy.context))

        # Immediately, "Criar Plano" must become available again!
        self.assertTrue(CHEST_OT_splitter_create_plane.poll(bpy.context))
        self.assertFalse(CHEST_OT_splitter_create_or_focus_guide.poll(bpy.context))

        # 5. User clicks "Criar Plano" again
        res2 = bpy.ops.chest.splitter_create_plane()
        self.assertEqual(res2, {'FINISHED'})

        # Plane is present again
        self.assertTrue(is_plane_guide_present(bpy.context))
        recreated_obj = bpy.data.objects.get(PLANE_GUIDE_NAME)
        self.assertIsNotNone(recreated_obj)
        self.assertAlmostEqual(recreated_obj.location.x, 10.0, places=3)
        self.assertAlmostEqual(recreated_obj.location.y, 5.0, places=3)

        # "Criar Plano" is again disabled
        self.assertFalse(CHEST_OT_splitter_create_plane.poll(bpy.context))
        self.assertTrue(CHEST_OT_splitter_create_or_focus_guide.poll(bpy.context))

    def test_poll_disabled_when_not_in_plane_mode_or_no_target(self):
        from src.operators import CHEST_OT_splitter_create_plane

        # Without target
        self.settings.target_object = None
        self.assertFalse(CHEST_OT_splitter_create_plane.poll(bpy.context))

        # With target but in MATERIAL mode
        self.settings.target_object = self.target
        self.settings.split_mode = 'MATERIAL'
        self.assertFalse(CHEST_OT_splitter_create_plane.poll(bpy.context))

        # Back to PLANE mode without guide
        self.settings.split_mode = 'PLANE'
        self.assertTrue(CHEST_OT_splitter_create_plane.poll(bpy.context))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPlaneCreateOnDelete)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    import sys
    sys.exit(0 if res.wasSuccessful() else 1)
