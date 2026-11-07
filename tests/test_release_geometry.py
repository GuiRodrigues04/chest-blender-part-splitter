"""Portable release geometry regressions. Run with Blender --background --factory-startup.
Private real-source fixture is derived from the supplied scene; do not redistribute it.
"""
import sys,json,unittest,math
from pathlib import Path
import bpy,bmesh
from mathutils import Vector,Matrix,Euler
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src import geometry_loop as gl, geometry_material as gm
from src.geometry_clearance import offset_contact_surface,weld_boolean_roundoff
from src.diagnostic import validate_bmesh_mesh_geometry
from src.localized_errors import LocalizedGeometryError


def boundary(obj, material=3):
    bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
    region={f for f in bm.faces if f.material_index==material}
    edges=[e for e in bm.edges if sum(f in region for f in e.link_faces)==1]
    loops=gm._order_boundary_loops(edges)
    indices=[v.index for v in loops[0]];seed=min(f.index for f in region);bm.free()
    return indices,seed


def real_fixture(item):
    mesh=bpy.data.meshes.new(item['name']);mesh.from_pydata(item['vertices'],[],item['faces']);mesh.update()
    for i in range(4):mesh.materials.append(bpy.data.materials.new('Source'+str(i)))
    for f,mat in zip(mesh.polygons,item['materials']):f.material_index=mat
    obj=bpy.data.objects.new(item['name'],mesh);bpy.context.scene.collection.objects.link(obj);obj.matrix_world=Matrix(item['matrix']);bpy.context.view_layer.update()
    return obj


def stepped_fixture(triangles=False):
    bm=bmesh.new();bmesh.ops.create_cube(bm,size=164.5);bmesh.ops.subdivide_edges(bm,edges=bm.edges[:],cuts=7,use_grid_fill=True)
    if triangles:bmesh.ops.triangulate(bm,faces=bm.faces[:])
    bm.normal_update();bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
    # Provenance survives copies and splitting; generated faces have default zero.
    provenance=bm.faces.layers.int.new('release_source')
    for f in bm.faces:f[provenance]=f.index+1
    originals={f.index+1:(f.normal.copy(),f.verts[0].co.copy()) for f in bm.faces}
    h=82.25;step=164.5/8;eps=1e-3
    selected=[]
    for e in bm.edges:
        a,b=[v.co for v in e.verts]
        front=abs(a.y+h)<eps and abs(b.y+h)<eps
        chosen=False
        if front:
            if abs(a.z-2*step)<eps and abs(b.z-2*step)<eps and -3*step-eps<=min(a.x,b.x) and max(a.x,b.x)<=3*step+eps:chosen=True
            elif abs(a.z)<eps and abs(b.z)<eps and (max(a.x,b.x)<=-3*step+eps or min(a.x,b.x)>=3*step-eps):chosen=True
            elif (abs(a.x+3*step)<eps and abs(b.x+3*step)<eps) or (abs(a.x-3*step)<eps and abs(b.x-3*step)<eps):
                if min(a.z,b.z)>=-eps and max(a.z,b.z)<=2*step+eps:chosen=True
        elif ((abs(a.x-h)<eps and abs(b.x-h)<eps) or (abs(a.x+h)<eps and abs(b.x+h)<eps) or (abs(a.y-h)<eps and abs(b.y-h)<eps)) and abs(a.z)<eps and abs(b.z)<eps:chosen=True
        if chosen:selected.append(e)
    loops=gm._order_boundary_loops(selected);indices=[v.index for v in loops[0]]
    seed=next(f.index for f in bm.faces if abs(f.calc_center_median().z-h)<eps)
    mesh=bpy.data.meshes.new('Stepped');bm.to_mesh(mesh);bm.free();obj=bpy.data.objects.new('Stepped',mesh);bpy.context.scene.collection.objects.link(obj)
    return obj,indices,seed,originals


class ReleaseGeometry(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.scale_length=.001
    def valid(self,bm,scale):
        report=validate_bmesh_mesh_geometry(bm,scale)
        self.assertTrue(report['is_valid'],str(report));self.assertFalse(report['non_manifold_edges']);self.assertGreater(bm.calc_volume(),0)

    def test_real_region_detach_material_and_depth(self):
        items=json.loads((Path(__file__).parent/'fixtures/red_region_private.json').read_text())
        bpy.context.scene.unit_settings.scale_length=1
        for item in items:
            obj=real_fixture(item);indices,seed=boundary(obj)
            self.assertEqual(sum(f.material_index==3 for f in obj.data.polygons),14)
            self.assertEqual(len(indices),22)
            source=[tuple(v.co) for v in obj.data.vertices]
            with self.assertRaises(LocalizedGeometryError) as nominal_error:
                gl.slice_mesh_by_loop(obj,obj.name,indices,seed)
            self.assertEqual(nominal_error.exception.payload['__splitter_message__'],'geometry.closing_intersection')
            self.assertIn(nominal_error.exception.payload['params']['part'],('A','B'))
            self.assertGreater(nominal_error.exception.payload['params']['count'],0)
            with self.assertRaises(LocalizedGeometryError) as material_error:
                gm.slice_mesh_by_material(obj,3,extraction_mode='BASE')

            analysis=gl.analyze_loop_region(obj,indices,seed)
            self.assertEqual(analysis['detected_mode'],'EXTRUDE')
            self.assertTrue(analysis['closure_crosses_source'])
            self.assertEqual(analysis['reason_message']['__splitter_message__'],'diagnostic.closure_uses_depth')
            for depth_mm in (5,10):
                depth=gl.slice_mesh_by_loop_extrude(obj,obj.name,indices,seed,depth_mm)
                try:
                    self.valid(depth.bm_a,1000);self.valid(depth.bm_b,1000)
                    self.assertEqual(source,[tuple(v.co) for v in obj.data.vertices])
                    bm=bmesh.new();bm.from_mesh(obj.data);bm.transform(obj.matrix_world)
                    volume=bm.calc_volume();bm.free()
                    self.assertAlmostEqual(sum(b.calc_volume() for b in depth),volume,delta=1e-8)
                    inward=analysis['inward_dir_world']
                    center=analysis['centroid_world']
                    n_out=-inward
                    support=center+n_out*min((p-center).dot(n_out) for p in analysis['coords_world'])
                    max_depth=max((obj.matrix_world@v.co-support).dot(inward) for v in depth.bm_a.verts)*1000
                    self.assertAlmostEqual(max_depth,depth_mm,delta=.01)
                finally:
                    for bm in depth:bm.free()
            self.assertEqual(material_error.exception.payload['__splitter_message__'],'geometry.non_planar')
    def test_corner_clearance_preserves_supports_and_patch_distances(self):
        item=json.loads((Path(__file__).parent/'fixtures/corner_region_private.json').read_text())
        bpy.context.scene.unit_settings.scale_length=1
        obj=real_fixture(item)
        bm=bmesh.new();bm.from_mesh(obj.data);bm.faces.index_update();bm.normal_update()
        layer=bm.faces.layers.int.new('release_source')
        originals={}
        for f in bm.faces:
            f[layer]=f.index+1;originals[f.index+1]=(f.normal.copy(),f.verts[0].co.copy())
        bm.to_mesh(obj.data);bm.free()
        initial=Matrix(item['matrix'])
        transforms=[initial,Matrix.Translation((.017,.023,-.009))@Euler((.4,-.2,.7)).to_matrix().to_4x4()@initial,
                    Matrix.Translation((.017,.023,-.009))@Euler((.4,-.2,.7)).to_matrix().to_4x4()@Matrix.Diagonal((1.2,.8,1.1,1))@initial]
        for transform in transforms:
            obj.matrix_world=transform;bpy.context.view_layer.update();inverse=transform.inverted()
            nominal=gl.slice_mesh_by_loop(obj,obj.name,item['indices'],item['seed'])
            reference_origin=nominal.interface.reference_origin_world.copy()
            reference_axis=nominal.interface.reference_axis_u_world.copy()
            marker=nominal.bm_a.faces.layers.int['splitter_contact_surface']
            planes=[(f.normal.copy(),f.verts[0].co.copy()) for f in nominal.bm_a.faces if f[marker]]
            for bm in nominal:bm.free()
            for target in ('PART','CAVITY','BOTH'):
                for gap in (0,.15,.3,1,3,5):
                    with self.subTest(target=target,gap=gap,transform=transform):
                        result=gl.slice_mesh_by_loop(obj,obj.name,item['indices'],item['seed'],part_clearance_mm=gap,part_clearance_apply_to=target)
                        try:
                            self.assertLess((result.interface.reference_origin_world-reference_origin).length,1e-7)
                            self.assertLess((result.interface.reference_axis_u_world-reference_axis).length,1e-7)
                            for side,bm in zip(('A','B'),result):
                                self.valid(bm,1000)
                                layer=bm.faces.layers.int.get('release_source');self.assertIsNotNone(layer)
                                protected=[f for f in bm.faces if f[layer]];self.assertTrue(protected)
                                for face in protected:
                                    normal,origin=originals[face[layer]]
                                    self.assertLess(max(abs((inverse@v.co-origin).dot(normal))*1000 for v in face.verts),.01)
                                if gap:
                                    final=getattr(result.interface,'final_contact_'+side.lower());self.assertIsNotNone(final)
                                    self.assertTrue(final['triangles']);self.assertTrue(final['loops'])
                                    # Every nominal contact patch remains at its independently
                                    # prescribed normal distance; exterior planes are stationary.
                                    marker=bm.faces.layers.int['splitter_contact_surface']
                                    factor=(.5 if target=='BOTH' else 1) if target==('PART' if side=='A' else 'CAVITY') or target=='BOTH' else 0
                                    expected=(1 if side=='B' else -1)*gap*factor
                                    for normal,origin in planes:
                                        matches=[f for f in bm.faces if f[marker] and abs(f.normal.dot(normal))>.9999]
                                        self.assertTrue(matches)
                                        error=min(abs((f.verts[0].co-origin).dot(normal)*1000-expected) for f in matches)
                                        self.assertLess(error,.01)
                        finally:
                            for bm in result:bm.free()

    def test_planar_bottom_clearance_independent_of_lateral(self):
        bpy.context.scene.unit_settings.scale_length=1
        vertices=[(x,y,z) for z in (-.05,0,.05) for x,y in ((-.05,-.05),(.05,-.05),(.05,.05),(-.05,.05))]
        faces=[(3,2,1,0),(8,9,10,11)]
        for ring in (0,4):
            for i in range(4):faces.append((ring+i,ring+(i+1)%4,ring+4+(i+1)%4,ring+4+i))
        obj=real_fixture(dict(name='Planar',vertices=vertices,faces=faces,materials=[0]*len(faces),matrix=[list(r) for r in Matrix.Identity(4)]))
        for lateral,bottom,target in ((1,0,'PART'),(0,1,'PART'),(0,1,'CAVITY'),(0,1,'BOTH')):
            result=gl.slice_mesh_by_loop(obj,obj.name,[4,5,6,7],1,part_clearance_mm=lateral,part_clearance_bottom_mm=bottom,part_clearance_apply_to=target)
            try:
                for bm in result:self.valid(bm,1000)
                a=result.interface.final_contact_a;b=result.interface.final_contact_b
                self.assertIsNotNone(a);self.assertIsNotNone(b)
                self.assertAlmostEqual(abs(a['origin'].z-b['origin'].z)*1000,bottom,delta=.01)
                self.assertAlmostEqual(result.interface.origin_world.z,a['origin'].z,delta=.00001)
            finally:
                for bm in result:bm.free()

    def test_weld_does_not_join_unrelated_surfaces(self):
        bm=bmesh.new()
        for z in (0,.00000005):
            vertices=[bm.verts.new((x,0,z)) for x in (0,.00000005,1)]
            bm.faces.new(vertices)
        weld_boolean_roundoff(bm,1)
        self.assertEqual({round(v.co.z,12) for v in bm.verts},{0,round(.00000005,12)});bm.free()

    def test_overhanging_protrusion_with_nonplanar_loop_preserves_upper_geometry(self):
        bpy.context.scene.unit_settings.scale_length=.001
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=100)
        bmesh.ops.subdivide_edges(bm,edges=bm.edges[:],cuts=3,use_grid_fill=True)
        bm.faces.ensure_lookup_table()
        top_faces=[f for f in bm.faces if f.normal.z>.9 and abs(f.calc_center_median().x)<26 and abs(f.calc_center_median().y)<26]
        res_ext=bmesh.ops.extrude_face_region(bm,geom=top_faces)
        ext_verts=[v for v in res_ext['geom'] if isinstance(v,bmesh.types.BMVert)]
        for v in ext_verts:
            v.co.x+=35.0;v.co.z+=60.0
        bmesh.ops.delete(bm,geom=top_faces,context='FACES')
        bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
        ext_faces=[f for f in bm.faces if any(v.co.z>51.0 for v in f.verts)]
        for f in ext_faces:f.material_index=1
        boundary_edges=[e for e in bm.edges if sum(f in ext_faces for f in e.link_faces)==1]
        b_verts={v for e in boundary_edges for v in e.verts}
        max(b_verts,key=lambda v:v.co.x).co.z+=0.20
        loops=gm._order_boundary_loops(boundary_edges)
        indices=[v.index for v in loops[0]]
        seed=next(f.index for f in ext_faces if all(v.co.z>90.0 for v in f.verts))
        mesh=bpy.data.meshes.new('OverhangHorn');bm.to_mesh(mesh)
        for i in range(2):mesh.materials.append(bpy.data.materials.new(f'M{i}'))
        obj=bpy.data.objects.new('OverhangHorn',mesh);bpy.context.scene.collection.objects.link(obj)
        for depth_mm,through in ((5.0,False),(5.0,True),(120.0,True)):
            res=gl.slice_mesh_by_loop_extrude(obj,obj.name,indices,seed,depth_mm=depth_mm,through_cut=through)
            try:
                self.valid(res.bm_a,1);self.valid(res.bm_b,1)
                self.assertAlmostEqual(max(v.co.z for v in res.bm_a.verts),110.0,delta=0.1)
                self.assertAlmostEqual(max(v.co.x for v in res.bm_a.verts),60.0,delta=0.1)
                self.assertLessEqual(max(v.co.z for v in res.bm_b.verts),50.25)
            finally:
                for b in res:b.free()
        bm.free()

    def test_stepped_clearance_preserves_exterior_supports(self):
        for triangles in (False,True):
            obj,indices,seed,originals=stepped_fixture(triangles)
            for transform in (Matrix.Identity(4),Matrix.Translation((17,23,-9))@Euler((.4,-.2,.7)).to_matrix().to_4x4()@Matrix.Diagonal((1.2,.8,1.1,1))):
                obj.matrix_world=transform;bpy.context.view_layer.update()
                inverse=transform.inverted()
                nominal=gl.slice_mesh_by_loop(obj,obj.name,indices,seed)
                nominal_planes=[]
                for bm in nominal:
                    bm.faces.index_update();marker=bm.faces.layers.int['splitter_contact_surface']
                    nominal_planes.append({f.index:(f.normal.copy(),f.verts[0].co.copy()) for f in bm.faces if f[marker]})
                for bm in nominal:bm.free()
                for target in ('PART','CAVITY','BOTH'):
                    for gap in (0,.15,.3,1,3,5):
                        with self.subTest(triangles=triangles,target=target,gap=gap,transform=transform):
                            result=gl.slice_mesh_by_loop(obj,obj.name,indices,seed,part_clearance_mm=gap,part_clearance_apply_to=target)
                            try:
                                for side,bm,planes in zip(('A','B'),result,nominal_planes):
                                    self.valid(bm,1)
                                    bm.faces.index_update();marker=bm.faces.layers.int['splitter_contact_surface']
                                    actual={f.index:f for f in bm.faces if f[marker]}
                                    self.assertEqual(set(actual),set(planes))
                                    factor=(.5 if target=='BOTH' else 1) if target==('PART' if side=='A' else 'CAVITY') or target=='BOTH' else 0
                                    for index,(normal,origin) in planes.items():
                                        face=actual[index]
                                        self.assertLess(max(abs((v.co-origin).dot(normal)+gap*factor) for v in face.verts),.01)
                                        self.assertLess(math.degrees(face.normal.angle(normal)),.1)
                                    layer=bm.faces.layers.int.get('release_source');self.assertIsNotNone(layer)
                                    for face in bm.faces:
                                        if layer and face[layer]:
                                            normal,origin=originals[face[layer]]
                                            self.assertLess(max(abs((inverse@v.co-origin).dot(normal)) for v in face.verts),.01)
                            finally:
                                for bm in result:bm.free()

if __name__=='__main__':
    import os
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseGeometry)
    if os.environ.get('PART_SPLITTER_GEOMETRY_SCOPE')=='reports':
        suite=unittest.TestSuite(test for test in suite if 'stepped_clearance' not in test.id())
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
