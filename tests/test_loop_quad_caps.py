"""Editable cap topology, safe fallback and physical gap on a closed fixture."""
import math
import sys
import unittest
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.geometry_loop import slice_mesh_by_loop
from src.geometry_quad_cap import contact_triangles, validate_grid_gap


def cylinder(segments):
    vertices = [(0.01*math.cos(i*2*math.pi/segments),
                 0.01*math.sin(i*2*math.pi/segments), z)
                for z in (-.02,0,.02) for i in range(segments)]
    faces = [tuple(reversed(range(segments)))]
    for level in range(2):
        for i in range(segments):
            j=(i+1)%segments
            faces.append((level*segments+i,level*segments+j,(level+1)*segments+j,(level+1)*segments+i))
    faces.append(tuple(range(2*segments,3*segments)))
    mesh=bpy.data.meshes.new('Quad cap fixture');mesh.from_pydata(vertices,[],faces)
    obj=bpy.data.objects.new('Quad cap fixture',mesh);bpy.context.scene.collection.objects.link(obj)
    return obj,list(range(segments,2*segments)),len(faces)-1


class QuadCaps(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_closed_quad_pair_preserves_source_and_volume(self):
        obj,indices,seed=cylinder(16)
        before=[tuple(v.co) for v in obj.data.vertices]
        parts=slice_mesh_by_loop(obj,obj.name,indices,seed)
        try:
            self.assertFalse(parts.interface.topology_fallback)
            for mesh in parts:
                marker=mesh.faces.layers.int.get('splitter_contact_surface')
                cap=[f for f in mesh.faces if f[marker]]
                self.assertEqual(len(cap),16)
                self.assertTrue(all(len(f.verts)==4 for f in cap))
                previous=mesh.faces.layers.int.get('splitter_previous_interface')
                if previous:
                    self.assertTrue(all(f[previous]==0 for f in cap))
                self.assertTrue(all(e.is_manifold for e in mesh.edges))
            self.assertEqual(before,[tuple(v.co) for v in obj.data.vertices])
            expected=16*.5*.01**2*math.sin(2*math.pi/16)*.04
            self.assertAlmostEqual(sum(p.calc_volume() for p in parts),expected,delta=1e-10)
            validate_grid_gap(*parts,0.,1000.)
        finally:
            for mesh in parts:mesh.free()

    def test_odd_boundary_uses_closed_fallback(self):
        obj,indices,seed=cylinder(15)
        parts=slice_mesh_by_loop(obj,obj.name,indices,seed)
        try:
            self.assertTrue(parts.interface.topology_fallback)
            self.assertTrue(all(e.is_manifold for p in parts for e in p.edges))
        finally:
            for mesh in parts:mesh.free()

    def test_planar_gap_remains_physical_for_each_destination(self):
        obj,indices,seed=cylinder(16)
        for destination in ('PART','CAVITY','BOTH'):
            with self.subTest(destination=destination):
                parts=slice_mesh_by_loop(obj,obj.name,indices,seed,part_clearance_mm=.1,
                                         part_clearance_apply_to=destination)
                try:
                    validate_grid_gap(*parts,.1,1000.)
                    self.assertTrue(all(e.is_manifold for p in parts for e in p.edges))
                finally:
                    for mesh in parts:mesh.free()

    def test_gap_validation_rejects_coincident_surfaces(self):
        obj,indices,seed=cylinder(16)
        parts=slice_mesh_by_loop(obj,obj.name,indices,seed)
        try:
            with self.assertRaises(ValueError):
                validate_grid_gap(*parts,.1,1000.)
        finally:
            for mesh in parts:mesh.free()


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(QuadCaps))
    if not result.wasSuccessful():raise SystemExit(1)
