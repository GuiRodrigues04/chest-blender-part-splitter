"""Measured clearances on joined contacts, concave parts and transformed models."""
import sys,unittest,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy,bmesh,src
from mathutils import Vector
from src.geometry_region import slice_region,mesh_signature,mesh_tree

DIRECTIONS=[((1,0,0),[(1,0,0),(1,1,0),(1,1,1),(1,0,1)]),((-1,0,0),[(0,1,0),(0,0,0),(0,0,1),(0,1,1)]),((0,1,0),[(1,1,0),(0,1,0),(0,1,1),(1,1,1)]),((0,-1,0),[(0,0,0),(1,0,0),(1,0,1),(0,0,1)]),((0,0,1),[(0,0,1),(1,0,1),(1,1,1),(0,1,1)]),((0,0,-1),[(0,1,0),(1,1,0),(1,0,0),(0,0,0)])]

def fixture(count=4,concave=False,joined_concave=False):
    cells={(x,y,z):0 for x in range(-10,10) for y in range(-10,10) for z in range(3)}
    footprint={(x,y) for x in range(-5,5) for y in range(-5,5)
               if not (concave and x>=0 and y>=0)}
    for x,y in footprint:
        for z in range(3,7):cells[x,y,z]=1
    if not concave or joined_concave:
        for side in range(count):
            for a in range(-8,-5):
                for b in range(-3,3):
                    x,y=((a,b),(-a-1,b),(b,-a-1),(b,a))[side]
                    for z in range(3,6):cells[x,y,z]=0
    verts=[];faces=[];mats=[];lookup={}
    def vi(p):
        if p not in lookup:lookup[p]=len(verts);verts.append(tuple(v*.001 for v in p))
        return lookup[p]
    for (x,y,z),mat in cells.items():
        for (dx,dy,dz),corners in DIRECTIONS:
            if (x+dx,y+dy,z+dz) not in cells:
                faces.append([vi((x+a,y+b,z+c)) for a,b,c in corners]);mats.append(mat)
    me=bpy.data.meshes.new('joined_contacts');me.from_pydata(verts,[],faces);me.update()
    for name in ('gray','piece'):me.materials.append(bpy.data.materials.new(name))
    for f,m in zip(me.polygons,mats):f.material_index=m
    ob=bpy.data.objects.new('target',me);bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active=ob;ob.select_set(True)
    return ob

def configure(ob,gap=0,apply='PART',loop=False):
    s=bpy.context.scene.chest_splitter;s.target_object=ob;s.part_clearance_mm=gap;s.part_clearance_apply_to=apply
    s.connector_enabled=False;s.invert_sides=False;s.contact_patch_index=-1
    s.material_split_index=1;s.material_region_index=0;s.material_extraction_mode='WHOLE'
    s.split_mode='LOOP' if loop else 'MATERIAL';s.loop_behavior='WHOLE'
    ids=[f.index for f in ob.data.polygons if f.material_index==1]
    s.region_target=ob;s.region_face_indices=','.join(map(str,ids));s.region_mesh_signature=mesh_signature(ob.data)
    return s

class Multicontact091(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()
    def setUp(self):bpy.ops.wm.read_factory_settings(use_empty=True)
    def cut(self,ob,s):
        before=mesh_signature(ob.data);a=bpy.data.meshes.new('A');b=bpy.data.meshes.new('B')
        result=slice_region(ob,s,bpy.context.scene,a,b)
        self.assertEqual(before,mesh_signature(ob.data))
        for key in ('A','B'):
            self.assertTrue(result[key]['is_manifold']);self.assertEqual(result[key]['components'],1)
        return a,b,result
    def measured_gap(self,mesh,ob,position,outward,towards_piece):
        p=ob.matrix_world@(Vector(position)*.001)
        n=(ob.matrix_world.to_3x3().inverted().transposed()@Vector(outward)).normalized()
        direction=-n if towards_piece else n
        origin=p-direction*.0005
        hit=mesh_tree(mesh).ray_cast(origin,direction)
        self.assertIsNotNone(hit[0])
        return hit[3]*1000-.5
    def test_joined_contacts_close_full_expected_volume(self):
        for count in range(1,5):
            with self.subTest(contacts=count+1):
                ob=fixture(count);_,_,r=self.cut(ob,configure(ob))
                self.assertAlmostEqual(r['A']['volume_mm3'],400,delta=.005)
    def test_gap_on_every_surface_and_no_corner_teeth(self):
        for apply in ('PART','CAVITY','BOTH'):
            with self.subTest(apply=apply):
                ob=fixture();a,b,_=self.cut(ob,configure(ob,.1,apply))
                probes=[((0,0,3),(0,0,-1)),((-5,0,4.5),(-1,0,0)),((5,0,4.5),(1,0,0)),((0,5,4.5),(0,1,0)),((0,-5,4.5),(0,-1,0))]
                for p,n in probes:
                    ga=self.measured_gap(a,ob,p,n,True);gb=self.measured_gap(b,ob,p,n,False)
                    self.assertAlmostEqual(ga+gb,.1,delta=.002)
                    self.assertAlmostEqual(ga,.1 if apply=='PART' else .05 if apply=='BOTH' else 0,delta=.002)
                expected=.003+(.0001 if apply=='PART' else .00005 if apply=='BOTH' else 0)
                self.assertGreaterEqual(min(v.co.z for v in a.vertices),expected-.000001)
    def test_rotation_nonuniform_scale_reflection_and_face_selection(self):
        ob=fixture();ob.rotation_euler=(.25,-.33,.41);ob.scale=(-1.2,.8,1.3);ob.location=(.12,-.23,.07);bpy.context.view_layer.update()
        a,b,r=self.cut(ob,configure(ob,.1,'BOTH',loop=True))
        for p,n in [((0,0,3),(0,0,-1)),((-5,0,4.5),(-1,0,0)),((0,5,4.5),(0,1,0))]:
            gap=self.measured_gap(a,ob,p,n,True)+self.measured_gap(b,ob,p,n,False)
            self.assertAlmostEqual(gap,.1,delta=.002)
    def test_concave_piece_keeps_its_notch(self):
        ob=fixture(0,concave=True);a,_,r=self.cut(ob,configure(ob,.1))
        self.assertAlmostEqual(r['A']['volume_mm3'],75*3.9,delta=.01)
        # A convex hull must never silently fill the missing quadrant.
        tree=mesh_tree(a);self.assertIsNone(tree.ray_cast(Vector((.002,.002,.008)),Vector((0,0,-1)))[0])
    def test_impossible_gap_preserves_input(self):
        ob=fixture();before=mesh_signature(ob.data)
        with self.assertRaises(ValueError):self.cut(ob,configure(ob,10))
        self.assertEqual(before,mesh_signature(ob.data))
    def test_ambiguous_concave_completion_is_not_convexified(self):
        ob=fixture(2,concave=True,joined_concave=True)
        before=mesh_signature(ob.data)
        with self.assertRaises(ValueError):self.cut(ob,configure(ob))
        self.assertEqual(before,mesh_signature(ob.data))
    def test_remainder_keeps_other_materials_and_contact_identity(self):
        ob=fixture();ob.data.materials.append(bpy.data.materials.new('next_piece'))
        far=next(f for f in ob.data.polygons if f.center.x<-.008 and f.normal.z<-.9)
        far.material_index=2
        a,b,r=self.cut(ob,configure(ob))
        self.assertIn(2,{f.material_index for f in b.polygons})
        self.assertEqual({f.material_index for f in a.polygons},{1})
        bottom=next(p for p in r['contact_choices'] if p['normal'][2]<-.99)
        for mesh in (a,b):
            marker=mesh.attributes['splitter_contact_patch']
            area=sum(f.area for f in mesh.polygons if marker.data[f.index].value==bottom['index']+1)*1e6
            self.assertAlmostEqual(area,100,delta=.005)
    def test_polygonal_contact_builds_real_triangles_for_pin_seat(self):
        ob=fixture();s=configure(ob);_,_,raw=self.cut(ob,s)
        chosen=next(p['index'] for p in raw['contact_choices'] if p['normal'][2]<-.99)
        s.contact_patch_index=chosen;s.part_clearance_mm=.1;s.part_clearance_apply_to='BOTH'
        _,_,report=self.cut(ob,s);interface=report['interface']
        self.assertTrue(interface.is_planar)
        self.assertTrue(all(len(t)==3 for t in interface.interface_triangles_world))
        n=interface.normal_a_to_b_world
        gap=(interface.final_contact_b['origin']-interface.final_contact_a['origin']).dot(n)*1000
        self.assertAlmostEqual(gap,.1,delta=.002)
    def test_public_gap_rejects_untrimmed_band_rims_then_offsets_corner(self):
        from src.geometry_contact_gap import shrink_contact
        from unittest.mock import patch
        ob=fixture(1);a,_,_=self.cut(ob,configure(ob))
        signature=mesh_signature(a)
        with patch('src.geometry_contact_gap._offset_contact_vertices',side_effect=ValueError('force trim audit')):
            with self.assertRaises(ValueError):shrink_contact(a,.1,1000)
        self.assertEqual(signature,mesh_signature(a))
        shrink_contact(a,.1,1000)
        self.assertAlmostEqual(self.measured_gap(a,ob,(0,0,3),(0,0,-1),True),.1,delta=.002)
        self.assertAlmostEqual(self.measured_gap(a,ob,(-5,0,4.5),(-1,0,0),True),.1,delta=.002)
        self.assertGreaterEqual(min(v.co.z for v in a.vertices),.003099)

if __name__=='__main__':
    result=unittest.main(argv=[__file__],exit=False)
    if not result.result.wasSuccessful():raise SystemExit(1)
