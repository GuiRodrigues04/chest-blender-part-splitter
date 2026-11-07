import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy,bmesh
from src.geometry_region import _repair_inherited_slivers,_validate_caps,CONTACT
from src.diagnostic import validate_bmesh_mesh_geometry,stable_signed_volume_mm3
from src.localized_errors import LocalizedGeometryError


def closed_sliver():
    # A triangulated flat polygon with an almost collinear intermediate point.
    mesh=bpy.data.meshes.new('InheritedSliver')
    mesh.from_pydata([(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1),
                     (-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(0,-1+1e-9,0)],[],
                    [(0,1,2,3),(4,8,5),(4,5,6),(4,6,7),
                     (0,4,8,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)])
    bm=bmesh.new();bm.from_mesh(mesh);bpy.data.meshes.remove(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    layer=bm.faces.layers.int.new(CONTACT)
    caps=[f for f in bm.faces if all(v.co.z==1 for v in f.verts)]
    for f in caps:f[layer]=1
    return bm,caps


class InheritedSlivers(unittest.TestCase):
    def setUp(self):bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_local_cleanup_preserves_caps_source_materials_and_volume(self):
        bm,caps=closed_sliver();candidate=None
        try:
            self.assertFalse(validate_bmesh_mesh_geometry(bm,1)['is_valid'])
            before=stable_signed_volume_mm3(bm,1)
            candidate,new_caps=_repair_inherited_slivers(bm,caps,1)
            self.assertIsNot(candidate,bm)
            self.assertTrue(validate_bmesh_mesh_geometry(candidate,1)['is_valid'])
            self.assertFalse(validate_bmesh_mesh_geometry(bm,1)['is_valid'])
            self.assertEqual(len(new_caps),len(caps))
            self.assertAlmostEqual(before,stable_signed_volume_mm3(candidate,1),places=7)
            self.assertTrue(all(f.is_valid for f in caps))
            self.assertTrue(_validate_caps(candidate,new_caps,lambda p:True,1)['is_manifold'])
        finally:
            if candidate is not None and candidate is not bm:candidate.free()
            bm.free()

    def test_failed_repair_keeps_original_references(self):
        bm,caps=closed_sliver()
        try:
            with patch('src.diagnostic.validate_mesh_repair_change',return_value=False):
                candidate,new_caps=_repair_inherited_slivers(bm,caps,1)
            self.assertIs(candidate,bm);self.assertIs(new_caps,caps)
            self.assertTrue(all(f.is_valid for f in caps))
            self.assertFalse(validate_bmesh_mesh_geometry(bm,1)['is_valid'])
        finally:bm.free()

    def test_degenerate_closing_faces_are_not_silently_repaired(self):
        bm,caps=closed_sliver()
        try:
            report=validate_bmesh_mesh_geometry(bm,1)
            bad=bm.faces[report['degenerate_faces'][0]]
            caps.append(bad);bad[bm.faces.layers.int[CONTACT]]=1
            candidate,_=_repair_inherited_slivers(bm,caps,1)
            self.assertIs(candidate,bm)
            with self.assertRaises(LocalizedGeometryError) as error:
                _validate_caps(bm,caps,lambda p:True,1)
            self.assertEqual(error.exception.payload['__splitter_message__'],'geometry.region_degenerate')
        finally:bm.free()


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InheritedSlivers))
    if not result.wasSuccessful():raise SystemExit(1)
