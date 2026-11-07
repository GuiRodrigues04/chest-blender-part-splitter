"""Annular Material/Loop cuts, inner clearances, centre preservation and pins."""
import json
from pathlib import Path
import sys
import unittest
import tempfile
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import src
from src.geometry_material import slice_mesh_by_material,analyze_material_structure
from src.geometry_regions import region_support,ring_prism
from src.diagnostic import validate_bmesh_mesh_geometry
from src.geometry_connectors import validate_connector_footprint,compute_connector_layout


class FrameRegions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()
    def setUp(self):
        if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.context.scene.unit_settings.scale_length=1
        self.s=bpy.context.scene.chest_splitter
        self.s.connector_enabled=False;self.s.part_clearance_mm=0
        self.s.part_clearance_apply_to='PART';self.s.part_clearance_bottom_enable=False
    def tearDown(self):
        if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    def object(self,vertices,faces,materials):
        mesh=bpy.data.meshes.new('Frame');mesh.from_pydata(vertices,[],faces);mesh.update()
        for i in range(2):mesh.materials.append(bpy.data.materials.new('FrameColor'+str(i)))
        for p,m in zip(mesh.polygons,materials):p.material_index=m
        obj=bpy.data.objects.new('Frame',mesh);bpy.context.scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active=obj;obj.select_set(True);self.s.target_object=obj
        bpy.context.view_layer.update();return obj
    def arco(self):
        data=json.loads((ROOT/'tests/fixtures/arco_frame.json').read_text())
        return self.object(data['vertices'],data['faces'],data['materials'])
    def two_holes(self):
        xs=[-.03,-.025,-.01,0,.01,.025,.03];ys=[-.02,-.015,.015,.02]
        vertices=[(x,y,z) for z in (0,.012) for y in ys for x in xs]
        nx=len(xs);ny=len(ys);count=nx*ny;faces=[];mats=[]
        for j in range(ny-1):
            for i in range(nx-1):
                a=j*nx+i;b=a+1;c=b+nx;d=a+nx
                faces.extend(((d,c,b,a),(a+count,b+count,c+count,d+count)))
                mats.extend((0,0 if j==1 and i in (1,4) else 1))
        boundary=[i for i in range(nx)]+[j*nx+nx-1 for j in range(1,ny)]+[(ny-1)*nx+i for i in range(nx-2,-1,-1)]+[j*nx for j in range(ny-2,0,-1)]
        for a,b in zip(boundary,boundary[1:]+boundary[:1]):faces.append((a,b,b+count,a+count));mats.append(0)
        return self.object(vertices,faces,mats)
    def valid(self,bm):
        report=validate_bmesh_mesh_geometry(bm,1000)
        self.assertTrue(report['is_valid'],str(report));self.assertTrue(report['is_manifold'],str(report))
        self.assertGreater(report['volume_mm3'],0)
    def inside(self,bm,point):
        hit=BVHTree.FromBMesh(bm).find_nearest(Vector(point))
        return hit[0] is not None and (Vector(point)-hit[0]).dot(hit[1])<0
    def test_real_arco_base_and_depth_preserve_centre_and_volume(self):
        obj=self.arco();original=[tuple(v.co) for v in obj.data.vertices]
        source=bmesh.new();source.from_mesh(obj.data);volume=source.calc_volume()*1e9;source.free()
        analysis=analyze_material_structure(obj,0)
        self.assertTrue(analysis['valid']);self.assertTrue(analysis['has_holes'])
        for mode in ('BASE','EXTRUDE'):
            for gap in (0,.1):
                with self.subTest(mode=mode,gap=gap):
                    result=slice_mesh_by_material(obj,0,depth_mm=3,extraction_mode=mode,part_clearance_mm=gap)
                    try:
                        for bm in result:self.valid(bm)
                        self.assertFalse(self.inside(result[0],(0,0,.08)))
                        self.assertTrue(self.inside(result[1],(0,0,.08)))
                        self.assertFalse(any(f.material_index==0 for f in result[1].faces))
                        self.assertEqual(len(result.interface.hole_contours_uv),1)
                        self.assertIsNotNone(result.interface.final_contact_a)
                        # Boolean reconstruction uses float coordinates; allow
                        # one part per million, matching the production guard.
                        if not gap:self.assertAlmostEqual(sum(b.calc_volume()*1e9 for b in result),volume,delta=max(.05,volume*1e-6))
                    finally:
                        for bm in result:bm.free()
        self.assertEqual(original,[tuple(v.co) for v in obj.data.vertices])
    def test_two_holes_clearances_and_connector_domains(self):
        obj=self.two_holes()
        for apply_to in ('PART','CAVITY','BOTH'):
            result=slice_mesh_by_material(obj,1,depth_mm=2,part_clearance_mm=.2,part_clearance_apply_to=apply_to)
            try:
                for bm in result:self.valid(bm)
                iface=result.interface
                self.assertEqual(len(iface.hole_contours_uv),2)
                for x in (-.0175,.0175):
                    self.assertFalse(self.inside(result[0],(x,0,.011)))
                    self.assertTrue(self.inside(result[1],(x,0,.011)))
                    uv=iface.world_to_uv(Vector((x,0,.01)))
                    self.assertFalse(validate_connector_footprint(*uv,.001,iface.outer_contours_uv,iface.hole_contours_uv)[0])
                gap_x={'PART':-.0099,'CAVITY':-.0101,'BOTH':-.01}[apply_to]
                self.assertFalse(self.inside(result[0],(gap_x,0,.011)))
                self.assertFalse(self.inside(result[1],(gap_x,0,.011)))
                layout=compute_connector_layout(obj.data,obj.matrix_world,iface.origin_world,iface.normal_a_to_b_world,
                                                 distribution='AUTO_SHAPE',edge_margin_mm=1,diameter_mm=2,unit_scale=1000,interface=iface)
                self.assertGreater(len(layout['positions']),0)
                for position in layout['positions']:
                    self.assertTrue(validate_connector_footprint(*iface.world_to_uv(position),.0011,iface.outer_contours_uv,iface.hole_contours_uv)[0])
            finally:
                for bm in result:bm.free()

    def test_bottom_clearance_is_independent_of_lateral_clearance(self):
        obj=self.two_holes()
        result=slice_mesh_by_material(obj,1,depth_mm=2,part_clearance_mm=.1,part_clearance_bottom_mm=.4)
        try:
            a=result.interface.final_contact_a;b=result.interface.final_contact_b
            self.assertIsNotNone(a);self.assertIsNotNone(b)
            self.assertAlmostEqual(abs(a['origin'].z-b['origin'].z)*1000,.4,delta=.001)
        finally:
            for bm in result:bm.free()
    def test_collapsed_clearance_is_rejected_without_changes(self):
        obj=self.arco();faces=[f.index for f in obj.data.polygons if f.material_index==0]
        support=region_support(obj,faces,1000);counts=(len(bpy.data.objects),len(bpy.data.meshes))
        with self.assertRaises(ValueError):ring_prism(support,3,3,10,1000,'invalid')
        self.assertEqual(counts,(len(bpy.data.objects),len(bpy.data.meshes)))
    def test_loop_captures_both_rings_and_uses_region_not_centre(self):
        obj=self.arco();self.s.split_mode='LOOP'
        bpy.context.tool_settings.mesh_select_mode=(False,False,True);bpy.ops.object.mode_set(mode='EDIT')
        bm=bmesh.from_edit_mesh(obj.data)
        for el in list(bm.faces)+list(bm.edges)+list(bm.verts):el.select_set(False)
        for face in bm.faces:
            if face.material_index==0:face.select_set(True)
        bm.select_flush_mode();bmesh.update_edit_mesh(obj.data)
        self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(),{'FINISHED'})
        self.assertEqual(len(json.loads(self.s.loop_boundary_loops)),2)
        self.assertEqual(self.s.loop_vertex_count,262)
        self.assertEqual(sum(e.select for e in bm.edges),262)
        bpy.ops.object.mode_set(mode='OBJECT')
        from src.input_state import cut_signature
        fingerprint=cut_signature(self.s,obj,bpy.context.scene)
        captured=self.s.loop_region_face_indices
        self.s.loop_region_face_indices='[]'
        self.assertNotEqual(fingerprint,cut_signature(self.s,obj,bpy.context.scene))
        self.s.loop_region_face_indices=captured
        self.s.loop_behavior='AUTO';self.s.part_clearance_mm=.1
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        self.assertTrue(self.s.part_a_is_manifold);self.assertTrue(self.s.part_b_is_manifold)
    def test_material_preview_with_pins_respects_two_holes(self):
        self.two_holes();s=self.s;s.split_mode='MATERIAL';s.material_split_index=1;s.material_extraction_mode='EXTRUDE'
        s.material_extrude_depth_mm=2;s.part_clearance_mm=.1;s.connector_enabled=True
        s.connector_distribution='CENTER';s.connector_diameter_mm=2;s.connector_length_mm=2;s.connector_chamfer_mm=.2
        s.clearance_per_side_mm=.1;s.end_clearance_mm=.1;s.connector_edge_margin_mm=1
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        self.assertTrue(s.part_a_is_manifold);self.assertTrue(s.part_b_is_manifold)

    def test_real_arco_auto_pins_form_closed_solids(self):
        self.arco();s=self.s;s.split_mode='MATERIAL';s.material_split_index=0
        s.material_extraction_mode='BASE';s.part_clearance_mm=.1;s.connector_enabled=True
        s.connector_distribution='AUTO_SHAPE';s.connector_diameter_mm=1.5
        s.connector_length_mm=1.;s.connector_chamfer_mm=.1;s.connector_edge_margin_mm=.3
        s.clearance_per_side_mm=.1;s.end_clearance_mm=.1
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        self.assertTrue(s.part_a_is_manifold);self.assertTrue(s.part_b_is_manifold)

    def test_transformed_and_millimetre_scene_sources(self):
        for mirrored in (False,True):
            with self.subTest(mirrored=mirrored):
                obj=self.two_holes()
                obj.rotation_euler=(.2,.3,.1)
                obj.scale=(-1. if mirrored else 1.,1.1,.9)
                bpy.context.view_layer.update()
                result=slice_mesh_by_material(obj,1,depth_mm=2,part_clearance_mm=.1)
                try:
                    for bm in result:self.valid(bm)
                    self.assertEqual(len(result.interface.hole_contours_uv),2)
                finally:
                    for bm in result:bm.free()
        obj=self.two_holes()
        for v in obj.data.vertices:v.co*=1000
        obj.data.update();bpy.context.scene.unit_settings.scale_length=.001
        result=slice_mesh_by_material(obj,1,depth_mm=2)
        try:
            for bm in result:
                check=validate_bmesh_mesh_geometry(bm,1)
                self.assertTrue(check['is_valid']);self.assertTrue(check['is_manifold'])
            self.assertAlmostEqual(sum(bm.calc_volume() for bm in result),28800,delta=.1)
        finally:
            for bm in result:bm.free()

    def test_explicit_through_depth_keeps_holes_and_has_no_false_pin_surface(self):
        obj=self.two_holes()
        result=slice_mesh_by_material(obj,1,depth_mm=20,through_cut=True)
        try:
            for bm in result:self.valid(bm)
            self.assertTrue(self.inside(result[1],(-.0175,0,.006)))
            self.assertFalse(result.interface.outer_contours_uv)
        finally:
            for bm in result:bm.free()

    def test_arco_export_commit_and_revert(self):
        obj=self.arco();s=self.s;s.split_mode='MATERIAL';s.material_split_index=0
        s.material_extraction_mode='BASE';s.part_clearance_mm=.1;s.connector_enabled=False
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        with tempfile.TemporaryDirectory(prefix='frame_export_') as directory:
            s.export_directory=directory;s.export_format='STL_PARTS'
            self.assertEqual(bpy.ops.chest.splitter_export_parts(),{'FINISHED'})
            self.assertEqual(len(list(Path(directory).glob('*.stl'))),2)
        self.assertEqual(bpy.ops.chest.splitter_commit_parts(),{'FINISHED'})
        self.assertEqual(bpy.ops.chest.splitter_revert_cut(),{'FINISHED'})
        self.assertEqual(len(obj.data.polygons),2104)


if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
