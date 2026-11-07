"""All five UI cut routes: actual quad previews and pin-free physical clearance."""
import sys,unittest,json
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import src
from test_loop_quad_caps import cylinder
from src.geometry_loop import get_topology_signature
from src.geometry_region import mesh_signature
from src.geometry_quad_cap import finish_cut_pair
from mathutils.bvhtree import BVHTree
MEASUREMENTS=[]


class AllCutTopology(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()

    def setup_cut(self,method,gap,segments=16):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        obj,indices,seed=cylinder(segments)
        for name in ('Body','Part'):obj.data.materials.append(bpy.data.materials.new(name))
        for face in obj.data.polygons:face.material_index=int(face.index>=segments+1)
        bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        s=bpy.context.scene.chest_splitter
        self.assertAlmostEqual(s.part_clearance_mm,.1,places=6)
        self.assertFalse(s.connector_enabled)
        s.target_object=obj;s.connector_enabled=False
        s.part_clearance_mm=gap;s.part_clearance_apply_to='PART';s.part_clearance_bottom_enable=False
        s.view_mode='ASSEMBLED';s.invert_sides=False
        s.split_mode='MATERIAL' if method=='WHOLE' else method
        s.material_split_index=1;s.material_region_index=0;s.material_extraction_mode='BASE'
        if method=='WHOLE':
            s.material_extraction_mode='WHOLE';s.region_target=obj
            s.region_face_indices=','.join(str(f.index) for f in obj.data.polygons if f.material_index==1)
            s.region_mesh_signature=mesh_signature(obj.data)
        elif method=='LOOP':
            s.loop_behavior='DETACH';s.loop_is_captured=True;s.loop_vertex_indices=','.join(map(str,indices))
            s.loop_vertex_count=len(indices);s.loop_seed_face_index=seed;s.loop_topology_signature=get_topology_signature(obj)
        elif method=='PLANE':s.plane_origin=(0,0,0);s.plane_normal=(0,0,1)
        elif method=='SOLID':
            bpy.ops.mesh.primitive_cube_add(size=.04,location=(0,0,.02))
            s.solid_source='EXISTING';s.solid_cutter_object=bpy.context.object
            bpy.context.view_layer.objects.active=obj
        return obj,s

    def test_five_methods_with_and_without_standard_gap(self):
        for method in ('LOOP','PLANE','WHOLE','SOLID','MATERIAL'):
            for gap in (0.,.1):
                with self.subTest(method=method,gap=gap):
                    obj,s=self.setup_cut(method,gap)
                    before=mesh_signature(obj.data)
                    result=bpy.ops.chest.splitter_generate_preview()
                    self.assertEqual(result,{'FINISHED'},s.get_localized_status())
                    self.assertEqual(before,mesh_signature(obj.data))
                    parts=[o for o in bpy.context.scene.objects if o.get('chest_role') in ('PREVIEW_A','PREVIEW_B')]
                    self.assertEqual(len(parts),2)
                    planes=[];quads=[]
                    for part in parts:
                        bm=bmesh.new();bm.from_mesh(part.data);bm.transform(part.matrix_world);bm.normal_update()
                        try:
                            self.assertTrue(all(e.is_manifold for e in bm.edges))
                            cap=[f for f in bm.faces if abs(f.normal.z)>.9999 and abs(f.calc_center_median().z)<.005]
                            self.assertTrue(cap)
                            if method=='SOLID' and gap>0:
                                # Exact Boolean introduces tiny collinear rim
                                # segments; a regular grid may be unsafe here.
                                self.assertTrue(all(len(f.verts) in (3,4) for f in cap))
                                if any(len(f.verts)==3 for f in cap):self.assertIn('triang',s.get_localized_status())
                            else:self.assertTrue(all(len(f.verts)==4 for f in cap))
                            quads.append(sum(len(f.verts)==4 for f in cap))
                            planes.append(sum(f.calc_center_median().z for f in cap)/len(cap))
                            tree=BVHTree.FromBMesh(bm)
                            hits=[]
                            for x,y in ((0,0),(.003,0),(-.003,0),(0,.003),(0,-.003)):
                                # Upper half and lower half are both sampled from
                                # above the interface; choose the inward direction.
                                start=Vector((x,y,.01)); hit=tree.ray_cast(start,Vector((0,0,-1)))
                                self.assertIsNotNone(hit[0]);hits.append(hit[0].z)
                            planes[-1]=hits
                        finally:bm.free()
                    measured=[abs(a-b)*1000 for a,b in zip(*planes)]
                    for value in measured:self.assertAlmostEqual(value,gap,delta=.002)
                    row=dict(method=method,gap=gap,quads=quads,min_mm=min(measured),max_mm=max(measured))
                    MEASUREMENTS.append(row)
                    print('CUT_TOPOLOGY',json.dumps(row),flush=True)

    def test_odd_boundary_falls_back_for_every_method(self):
        for method in ('LOOP','PLANE','WHOLE','SOLID','MATERIAL'):
            with self.subTest(method=method):
                obj,s=self.setup_cut(method,0,segments=15)
                self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
                self.assertIn('triang',s.get_localized_status())
                self.assertEqual(s.last_status_level,'SUCCESS')

    def test_plane_ignores_inherited_contact_selection(self):
        obj,s=self.setup_cut('PLANE',0.)
        mark=obj.data.attributes.new('splitter_contact_surface','INT','FACE')
        mark.data[0].value=1
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        for part in bpy.context.scene.objects:
            if part.get('chest_role') not in ('PREVIEW_A','PREVIEW_B'):continue
            bm=bmesh.new();bm.from_mesh(part.data)
            try:
                cap=[f for f in bm.faces if abs(f.normal.z)>.9999 and abs(f.calc_center_median().z)<.005]
                self.assertEqual(len(cap),16)
                self.assertTrue(all(len(f.verts)==4 for f in cap))
            finally:bm.free()

    def _assert_ring_hole_survives(self,square=False):
        import math
        from mathutils import Matrix
        from src.geometry_plane import slice_mesh_by_plane
        bpy.ops.wm.read_factory_settings(use_empty=True)
        n=16
        points=[(r*math.cos(i*2*math.pi/n)/(max(abs(math.cos(i*2*math.pi/n)),abs(math.sin(i*2*math.pi/n))) if square else 1),
                 r*math.sin(i*2*math.pi/n)/(max(abs(math.cos(i*2*math.pi/n)),abs(math.sin(i*2*math.pi/n))) if square else 1),z)
                for z,r in ((-.02,.01),(.02,.01),(-.02,.004),(.02,.004)) for i in range(n)]
        faces=[]
        for i in range(n):
            j=(i+1)%n
            faces.extend(((i,j,n+j,n+i),(2*n+j,2*n+i,3*n+i,3*n+j),
                          (n+i,n+j,3*n+j,3*n+i),(j,i,2*n+i,2*n+j)))
        source=bpy.data.meshes.new('Hollow tube');source.from_pydata(points,[],faces)
        outputs=[bpy.data.meshes.new(name) for name in ('A','B')]
        slice_mesh_by_plane(source,Matrix.Identity(4),Vector(),Vector((0,0,1)),*outputs)
        for mesh in outputs:
            before=bmesh.new();before.from_mesh(mesh)
            self.assertIsNone(BVHTree.FromBMesh(before).ray_cast(Vector((0,0,.03)),Vector((0,0,-1)))[0])
            before.free()
        stats=finish_cut_pair(*outputs,source,Matrix.Identity(4),1000.)
        for mesh in outputs:
            bm=bmesh.new();bm.from_mesh(mesh)
            try:
                self.assertTrue(all(e.is_manifold for e in bm.edges))
                self.assertIsNone(BVHTree.FromBMesh(bm).ray_cast(Vector((0,0,.03)),Vector((0,0,-1)))[0])
            finally:bm.free()

    def test_ring_hole_survives_fallback(self):
        self._assert_ring_hole_survives()

    def test_subdivided_square_ring_hole_survives_fallback(self):
        self._assert_ring_hole_survives(square=True)


if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AllCutTopology))
    if not r.wasSuccessful():raise SystemExit(1)
    if '--' in sys.argv:
        Path(sys.argv[sys.argv.index('--')+1]).write_text(json.dumps(MEASUREMENTS,indent=2),encoding='utf-8')
