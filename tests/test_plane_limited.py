"""Finite planar section selection and full preview/commit regression (Blender)."""
import os, sys, unittest, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy, bmesh
from mathutils import Vector, Matrix, Euler
import src
from src.geometry_plane import slice_mesh_by_plane, PlaneSliceError
from src.plane_region import PlaneRegion, resolve_plane_region, guide_region


def fixture():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    cubes=[]
    for center, dims in [((0,0,.03),(.02,.02,.06)),
                          ((-.03,0,.025),(.02,.02,.05)),
                          ((.03,0,.025),(.02,.02,.05)),
                          ((0,0,.05),(.08,.02,.02))]:
        bpy.ops.mesh.primitive_cube_add(size=1,location=center)
        o=bpy.context.object;o.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);cubes.append(o)
    obj=cubes[0]
    for other in cubes[1:]:
        bpy.context.view_layer.objects.active=obj
        mod=obj.modifiers.new('Union','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=other
        bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(other,do_unlink=True)
    settings=bpy.context.scene.chest_splitter;settings.target_object=obj;settings.split_mode='PLANE';settings.plane_extent_mode='FULL'
    settings.invert_sides=False;settings.part_clearance_mm=0;settings.connector_enabled=False
    bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    return obj,settings


def region(x0=-.045,x1=-.015,y0=-.015,y1=.015,z=.02):
    return PlaneRegion(tuple(Vector(p) for p in ((x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z))))


class LimitedPlane(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()
    def setUp(self):self.obj,self.settings=fixture()

    def cut(self,reg=None,**kw):
        a=bpy.data.meshes.new('out_a');b=bpy.data.meshes.new('out_b')
        try:
            report=slice_mesh_by_plane(self.obj.data,self.obj.matrix_world,Vector((0,0,.02)),Vector((0,0,1)),a,b,unit_scale=1000,plane_region=reg,**kw)
            for mesh in (a,b):
                bm=bmesh.new();bm.from_mesh(mesh);self.assertTrue(all(e.is_manifold for e in bm.edges));bm.free()
            return report,a,b
        except Exception:
            bpy.data.meshes.remove(a);bpy.data.meshes.remove(b);raise

    def test_only_left_arm_and_interface(self):
        full,_,_=self.cut()
        r,a,b=self.cut(region())
        self.assertAlmostEqual(r['A']['volume_mm3'],8000,delta=.02)
        self.assertGreater(full['A']['volume_mm3'],r['A']['volume_mm3']*2)
        self.assertAlmostEqual(r['sum_volume_mm3'],full['sum_volume_mm3'],delta=.1)
        self.assertTrue(all(v.co.x<-.019 for v in a.vertices))
        self.assertTrue(any(v.co.x>.019 and v.co.z<.001 for v in b.vertices))
        iface=r['interface'];self.assertTrue(iface.outer_contours_uv)
        for loop in iface.outer_contours_uv:
            for uv in loop:self.assertTrue(region().contains(iface.uv_to_world(*uv)))

    def test_partial_rectangle_does_not_write_destinations(self):
        a=bpy.data.meshes.new('sentinel_a');b=bpy.data.meshes.new('sentinel_b')
        a.from_pydata([(1,2,3)],[],[])
        with self.assertRaises(PlaneSliceError):
            slice_mesh_by_plane(self.obj.data,self.obj.matrix_world,Vector((0,0,.02)),Vector((0,0,1)),a,b,
                                plane_region=region(y0=-.005,y1=.005))
        self.assertEqual(len(a.vertices),1);self.assertEqual(tuple(a.vertices[0].co),(1,2,3))

    def test_no_section_and_rectangle_inside_solid_are_rejected(self):
        for reg in (region(x0=.1,x1=.2),region(x0=-.035,x1=-.025,y0=-.005,y1=.005)):
            with self.assertRaises(PlaneSliceError):self.cut(reg)

    def test_clearance_stays_local(self):
        original,_,_=self.cut(region())
        for dest in ('PART','CAVITY','BOTH'):
            r,a,b=self.cut(region(),part_clearance_mm=.2,part_clearance_apply_to=dest)
            self.assertAlmostEqual(original['sum_volume_mm3']-r['sum_volume_mm3'],80,delta=.1)
            # The bottom of the unrelated right arm must remain in the receiver.
            self.assertTrue(any(v.co.x>.019 and v.co.z<.001 for v in b.vertices))

    def test_inversion_swaps_parts(self):
        r,_,_=self.cut(region());s,_,_=self.cut(region(),invert_sides=True)
        self.assertAlmostEqual(r['A']['volume_mm3'],s['B']['volume_mm3'],delta=.01)
        self.assertAlmostEqual(r['B']['volume_mm3'],s['A']['volume_mm3'],delta=.01)

    def test_region_clip_and_nonuniform_transform(self):
        m=Matrix.Translation(Vector((.3,-.2,.1)))@Euler((.35,.4,.6)).to_matrix().to_4x4()@Matrix.Diagonal((1.2,.7,1.5,1))
        reg=region();transformed=PlaneRegion(tuple(m@p for p in reg.corners))
        n=m.to_3x3().inverted().transposed()@Vector((0,0,1))
        a=bpy.data.meshes.new('rot_a');b=bpy.data.meshes.new('rot_b')
        r=slice_mesh_by_plane(self.obj.data,m@self.obj.matrix_world,m@Vector((0,0,.02)),n,a,b,plane_region=transformed)
        self.assertAlmostEqual(r['A']['volume_mm3'],8000*1.2*.7*1.5,delta=.2)
        segment=transformed.clip_segment(m@Vector((-.1,0,.02)),m@Vector((.1,0,.02)))
        self.assertIsNotNone(segment);self.assertTrue(all(transformed.contains(p) for p in segment))

    def test_guide_dimensions_fingerprints_and_connector_surface(self):
        from src.operators import ensure_plane_guide,compute_session_input_signature
        from src.input_state import cut_signature,editor_configuration
        from src.connector_surface import prepare_split_candidates
        guide=ensure_plane_guide(bpy.context);guide.location=(-.03,0,.02)
        guide.rotation_euler=(0,0,0);bpy.context.view_layer.update()
        self.settings.plane_extent_mode='LIMITED'
        self.settings.plane_width_mm=30;self.settings.plane_height_mm=30;bpy.context.view_layer.update()
        self.assertAlmostEqual(self.settings.plane_width_mm,30,places=3)
        self.assertAlmostEqual(self.settings.plane_height_mm,30,places=3)
        sig=compute_session_input_signature(bpy.context);cut=cut_signature(self.settings,self.obj,bpy.context.scene);cfg=editor_configuration(self.settings,bpy.context.scene)
        self.settings.plane_width_mm=32;bpy.context.view_layer.update()
        self.assertNotEqual(sig,compute_session_input_signature(bpy.context))
        self.assertNotEqual(cut,cut_signature(self.settings,self.obj,bpy.context.scene))
        self.assertNotEqual(cfg,editor_configuration(self.settings,bpy.context.scene))
        prep=prepare_split_candidates(bpy.context)
        reg=resolve_plane_region(bpy.context.scene,self.settings)
        for contour in prep.interface.outer_contours_uv:
            for uv in contour:self.assertTrue(reg.contains(prep.interface.uv_to_world(*uv)))
        # An in-plane rotation changes a nonsquare footprint even though origin/normal do not.
        sig=compute_session_input_signature(bpy.context);guide.rotation_euler.z=.3;bpy.context.view_layer.update()
        self.assertNotEqual(sig,compute_session_input_signature(bpy.context))

    def test_preview_confirm_and_stale_resize(self):
        from src.operators import ensure_plane_guide
        guide=ensure_plane_guide(bpy.context);guide.location=(-.03,0,.02);bpy.context.view_layer.update()
        self.settings.plane_extent_mode='LIMITED';self.settings.plane_width_mm=30;self.settings.plane_height_mm=30;bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        self.assertEqual(self.settings.session_status,'PREVIEW_VALID')
        self.settings.plane_width_mm=31;bpy.context.view_layer.update()
        self.assertEqual(self.settings.session_status,'PREVIEW_STALE')
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        self.assertEqual(bpy.ops.chest.splitter_commit_parts(),{'FINISHED'})

    def test_connector_preview_is_local_and_failed_update_preserves_preview(self):
        from src.operators import ensure_plane_guide,get_current_session_parts
        guide=ensure_plane_guide(bpy.context);guide.location=(-.03,0,.02);bpy.context.view_layer.update()
        s=self.settings;s.plane_extent_mode='LIMITED';s.plane_width_mm=30;s.plane_height_mm=30
        s.connector_enabled=True;s.connector_type='CYLINDER';s.connector_distribution='CENTER'
        s.connector_diameter_mm=4;s.connector_length_mm=4;s.connector_edge_margin_mm=2
        s.part_clearance_apply_to='PART';s.part_clearance_mm=.1
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        parts=get_current_session_parts(bpy.context.scene)
        self.assertEqual(len(parts),2)
        volumes=[]
        for obj in parts:
            bm=bmesh.new();bm.from_mesh(obj.data);self.assertTrue(all(e.is_manifold for e in bm.edges));volumes.append(bm.calc_volume());bm.free()
        before=[(o.as_pointer(),len(o.data.polygons)) for o in parts]
        s.plane_width_mm=10;bpy.context.view_layer.update()
        try:result=bpy.ops.chest.splitter_generate_preview()
        except RuntimeError:result={'CANCELLED'}
        self.assertEqual(result,{'CANCELLED'})
        self.assertEqual(before,[(o.as_pointer(),len(o.data.polygons)) for o in get_current_session_parts(bpy.context.scene)])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LimitedPlane))
    sys.exit(0 if result.wasSuccessful() else 1)
