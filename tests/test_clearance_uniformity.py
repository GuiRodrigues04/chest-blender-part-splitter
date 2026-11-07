"""Physical section measurements: constant lateral gap, independent axial gap."""
import sys
import unittest
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.geometry_material import slice_mesh_by_material
from src.geometry_loop import slice_mesh_by_loop, slice_mesh_by_loop_extrude
from src.geometry_plane import slice_mesh_by_plane
from src.geometry_solid import slice_mesh_by_solid


def square(relief=True):
    levels = ((15, -5), (15, 0), (10, 0)) + (((10, 3),) if relief else ())
    vertices = [(x / 1000, y / 1000, z / 1000) for half, z in levels
                for x, y in ((-half, -half), (half, -half), (half, half), (-half, half))]
    faces = [(3, 2, 1, 0)]
    for ring in range(len(levels) - 1):
        for i in range(4):
            j = (i + 1) % 4
            faces.append((ring*4+i, ring*4+j, (ring+1)*4+j, (ring+1)*4+i))
    last = (len(levels) - 1)*4
    faces.append(tuple(range(last, last+4)))
    mesh = bpy.data.meshes.new('Square')
    mesh.from_pydata(vertices, [], faces)
    for name in ('Body', 'Relief'):
        mesh.materials.append(bpy.data.materials.new(name))
    for face in mesh.polygons:
        face.material_index = int(face.index >= 9)
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new('Square', mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    return obj, len(faces)-1


class ClearanceUniformity(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.scale_length = 1

    def valid(self, parts):
        for part in parts:
            self.assertTrue(all(e.is_manifold for e in part.edges))
            self.assertTrue(all(v.is_manifold for v in part.verts))
            self.assertGreater(part.calc_volume(), 0)

    def test_depth_sections_all_destinations_and_independent_bottom(self):
        for route in ('MATERIAL', 'LOOP', 'DIRECT', 'FLAT', 'MATERIAL_FLAT'):
            for destination in ('PART', 'CAVITY', 'BOTH'):
                for lateral, bottom in ((0, 0), (.1, .1), (1, 1), (1, 0), (0, .7), (3, 0)):
                    with self.subTest(route=route, destination=destination, lateral=lateral, bottom=bottom):
                        obj, seed = square(route not in ('FLAT', 'MATERIAL_FLAT'))
                        before = [tuple(v.co) for v in obj.data.vertices]
                        kw = dict(part_clearance_mm=lateral, part_clearance_apply_to=destination,
                                  part_clearance_bottom_mm=bottom)
                        if route in ('MATERIAL', 'MATERIAL_FLAT'):
                            parts = slice_mesh_by_material(obj, 1, depth_mm=2, **kw)
                        elif route == 'DIRECT':
                            parts = slice_mesh_by_loop(obj, obj.name, [8,9,10,11], seed,
                                                      detach_add_base=True, detach_base_depth_mm=2, **kw)
                        else:
                            parts = slice_mesh_by_loop_extrude(obj, obj.name, [8,9,10,11], seed, depth_mm=2, **kw)
                        try:
                            self.valid(parts)
                            fractions = (1,0) if destination == 'PART' else (0,1) if destination == 'CAVITY' else (.5,.5)
                            for side, (part, fraction) in enumerate(zip(parts, fractions)):
                                tree = BVHTree.FromBMesh(part)
                                radius = 10 + (-1 if side == 0 else 1)*lateral*fraction
                                for z in (-.02, -.4, -.9):
                                    for direction in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0)):
                                        hit = tree.ray_cast(Vector((0,0,z/1000)), Vector(direction))
                                        self.assertIsNotNone(hit[0])
                                        self.assertAlmostEqual(hit[3]*1000, radius, delta=.002)
                                floor = min(v.co.z for v in part.verts)*1000 if side == 0 else min(
                                    v.co.z for f in part.faces if abs(f.normal.z) > .99
                                    and f.calc_center_median().z > -.004 for v in f.verts)*1000
                                self.assertAlmostEqual(floor, -2 + (1 if side == 0 else -1)*bottom*fraction, delta=.002)
                            self.assertEqual([tuple(v.co) for v in obj.data.vertices], before)
                        finally:
                            for part in parts: part.free()
                            bpy.data.objects.remove(obj, do_unlink=True)

    def test_material_base_respects_separate_bottom(self):
        obj, _ = square()
        for destination in ('PART', 'CAVITY', 'BOTH'):
            for lateral, bottom in ((1,0), (0,.7)):
                with self.subTest(destination=destination, lateral=lateral, bottom=bottom):
                    parts = slice_mesh_by_material(obj, 1, extraction_mode='BASE',
                        part_clearance_mm=lateral, part_clearance_bottom_mm=bottom,
                        part_clearance_apply_to=destination)
                    try:
                        self.valid(parts)
                        a = min(v.co.z for v in parts[0].verts)*1000
                        b = BVHTree.FromBMesh(parts[1]).ray_cast(Vector((0,0,.002)), Vector((0,0,-1)))[0].z*1000
                        self.assertAlmostEqual(a-b, bottom, delta=.002)
                    finally:
                        for part in parts: part.free()

    def test_through_cut_has_constant_gap_at_top_and_bottom(self):
        obj, seed = square()
        for destination in ('PART', 'CAVITY', 'BOTH'):
            with self.subTest(destination=destination):
                parts = slice_mesh_by_loop_extrude(obj, obj.name, [8,9,10,11], seed,
                    depth_mm=6, through_cut=True, part_clearance_mm=.2,
                    part_clearance_apply_to=destination)
                try:
                    self.valid(parts)
                    for z in (-.05, -2, -4.95):
                        hits = [BVHTree.FromBMesh(p).ray_cast(Vector((0,0,z/1000)), Vector((1,0,0)))[3]*1000 for p in parts]
                        self.assertAlmostEqual(hits[1]-hits[0], .2, delta=.003)
                finally:
                    for part in parts: part.free()

    def test_plane_and_solid_gap_and_parallel_walls(self):
        bpy.ops.mesh.primitive_cube_add(size=.04)
        target = bpy.context.object
        bpy.ops.mesh.primitive_cube_add(size=.02)
        cutter = bpy.context.object
        for mode in ('PLANE','SOLID'):
            for destination in ('PART','CAVITY','BOTH'):
                with self.subTest(mode=mode, destination=destination):
                    outputs = [bpy.data.meshes.new('result') for _ in range(2)]
                    kw = dict(part_clearance_mm=1, part_clearance_apply_to=destination)
                    if mode == 'PLANE':
                        slice_mesh_by_plane(target.data, Matrix.Identity(4), Vector(), Vector((0,0,1)), *outputs, **kw)
                    else:
                        slice_mesh_by_solid(target.data, Matrix.Identity(4), cutter, *outputs, **kw)
                    parts = []
                    try:
                        for mesh in outputs:
                            bm = bmesh.new(); bm.from_mesh(mesh); parts.append(bm)
                        self.valid(parts)
                        trees = [BVHTree.FromBMesh(bm) for bm in parts]
                        if mode == 'SOLID':
                            radii = [trees[i].ray_cast(Vector((0,0,z)), Vector((1,0,0)))[3]*1000
                                     for z in (-.005,0,.005) for i in (0,1)]
                            a = 9 if destination == 'PART' else 9.5 if destination == 'BOTH' else 10
                            b = 11 if destination == 'CAVITY' else 10.5 if destination == 'BOTH' else 10
                            for measured, expected in zip(radii, (a,b)*3):
                                self.assertAlmostEqual(measured, expected, delta=.002)
                        else:
                            faces = [min((abs(v.co.z) for v in bm.verts))*1000 for bm in parts]
                            self.assertAlmostEqual(sum(faces), 1, delta=.002)
                    finally:
                        for bm in parts: bm.free()
                        for mesh in outputs: bpy.data.meshes.remove(mesh)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClearanceUniformity))
    if not result.wasSuccessful(): raise SystemExit(1)
