"""Integration regressions for 0.8.12, using real Blender mesh/boolean operators.
Run: blender -b --factory-startup --python-exit-code 1 --python tests/test_regressions_0812.py
Set PART_SPLITTER_ROOT to reproduce the same regressions against an older source tree.
"""
import os
import sys
from pathlib import Path
import unittest
import math
import tempfile
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, os.environ.get('PART_SPLITTER_ROOT', str(Path(__file__).resolve().parents[1])))
import src
from src import connector_surface as surface, connector_editor as editor
from src import geometry_connectors as connectors, geometry_loop, operators, lifecycle
from src.geometry_contract import build_cut_interface


class Regressions0812(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    @classmethod
    def tearDownClass(cls):
        src.unregister()

    def setUp(self):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.s = self.scene.chest_splitter
        surface.clear_prepared_split_cache()
        editor.stop_connector_editor(self.scene)
        editor.CHEST_OT_splitter_edit_manual_connectors._last_snapshot = None
        self.scene.unit_settings.system = 'METRIC'
        self.scene.unit_settings.scale_length = 1.0

    def fixture(self, raised=True):
        verts=[]
        def ring(r,z):
            return [(x*r,y*r,z) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        verts=ring(.05,-.05)+ring(.05,0)+ring(.02,0)
        faces=[(3,2,1,0)]
        for i in range(4):
            j=(i+1)%4; faces.append((i,j,4+j,4+i))
        for i in range(4):
            j=(i+1)%4; faces.append((4+i,4+j,8+j,8+i))
        if raised:
            verts += ring(.02,.01)
            for i in range(4):
                j=(i+1)%4; faces.append((8+i,8+j,12+j,12+i))
            faces.append((12,13,14,15))
        else:
            faces.append((8,9,10,11))
        mesh=bpy.data.meshes.new('RegressionMesh');mesh.from_pydata(verts,[],faces);mesh.update()
        obj=bpy.data.objects.new('RegressionTarget',mesh);self.scene.collection.objects.link(obj)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:]);bm.to_mesh(mesh);bm.free()
        mesh.materials.append(bpy.data.materials.new('Body'))
        mesh.materials.append(bpy.data.materials.new('Insert'))
        for f in mesh.polygons:
            if f.index>=9:f.material_index=1
        self.s.target_object=obj;self.s.plane_origin=(0,0,-.025)
        self.s.plane_normal=(0,0,1)
        obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.context.view_layer.update()
        return obj

    def capture(self, obj, faces=True):
        self.s.split_mode='LOOP'
        bpy.ops.object.mode_set(mode='EDIT')
        bm=bmesh.from_edit_mesh(obj.data);bm.faces.ensure_lookup_table()
        for f in bm.faces:f.select_set(f.index>=9)
        bm.faces.active=bm.faces[-1]
        bmesh.update_edit_mesh(obj.data)
        if faces:
            self.assertEqual(bpy.ops.chest.splitter_capture_face_boundary(), {'FINISHED'})
        else:
            for f in bm.faces:f.select=False
            for e in bm.edges:e.select_set(all(8<=v.index<12 for v in e.verts))
            bmesh.update_edit_mesh(obj.data)
            self.assertEqual(bpy.ops.chest.splitter_capture_loop(),{'FINISHED'})
            self.s.loop_seed_face_index=len(bm.faces)-1
        bpy.ops.object.mode_set(mode='OBJECT')

    def pin(self,u=0,v=0,yaw=0):
        c=self.s.manual_connectors.add();c.connector_id=f'id_{len(self.s.manual_connectors)}'
        c.u_mm=u;c.v_mm=v;c.yaw_deg=yaw
        return c

    def test_loop_capture_survives_editor_entry(self):
        obj=self.fixture();self.capture(obj)
        indices=self.s.loop_vertex_indices;seed=self.s.loop_seed_face_index
        self.assertEqual(bpy.ops.chest.splitter_edit_manual_connectors(),{'FINISHED'})
        self.assertEqual(self.s.loop_vertex_indices,indices)
        self.assertEqual(self.s.loop_seed_face_index,seed)
        self.assertTrue(self.s.is_editing_connectors)

    def test_loop_reedit_after_preview_twice(self):
        obj=self.fixture();self.capture(obj)
        self.s.loop_behavior='DETACH';self.s.loop_detach_add_base=True
        self.s.loop_detach_base_depth_mm=5
        self.s.connector_distribution='MANUAL';self.s.connector_enabled=True
        self.pin()
        for _ in range(2):
            self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
            self.assertEqual(bpy.ops.chest.splitter_edit_manual_connectors(),{'FINISHED'})
            self.assertTrue(self.s.loop_is_captured)
            self.assertEqual(len(self.s.manual_connectors),1)
            editor.stop_connector_editor(self.scene)

    def test_same_target_assignment_keeps_capture(self):
        obj=self.fixture();self.capture(obj);self.s.target_object=obj
        self.assertTrue(self.s.loop_is_captured)

    def test_new_target_invalidates_capture_and_cache(self):
        obj=self.fixture();self.capture(obj);surface.prepare_split_candidates(bpy.context)
        new=obj.copy();new.data=obj.data.copy();self.scene.collection.objects.link(new)
        self.s.target_object=new
        self.assertFalse(self.s.loop_is_captured)
        self.assertIsNone(surface.get_cached_prepared_split())

    def test_empty_snapshot_cancel_button_restores_empty_list(self):
        self.fixture();bpy.ops.chest.splitter_edit_manual_connectors();self.pin(5,6)
        bpy.ops.chest.splitter_cancel_manual_connectors()
        self.assertEqual(len(self.s.manual_connectors),0)

    def test_cancel_snapshot_restores_positions_and_ids(self):
        self.fixture();self.pin(5,6,30);bpy.ops.chest.splitter_edit_manual_connectors()
        self.s.manual_connectors[0].u_mm=19;self.pin()
        bpy.ops.chest.splitter_cancel_manual_connectors()
        self.assertEqual(len(self.s.manual_connectors),1)
        self.assertEqual(self.s.manual_connectors[0].u_mm,5)
        self.assertEqual(self.s.manual_connectors[0].connector_id,'id_1')

    def test_failed_editor_preparation_is_not_success(self):
        self.fixture();self.s.split_mode='LOOP'
        with self.assertRaises(RuntimeError):bpy.ops.chest.splitter_edit_manual_connectors()
        self.assertFalse(self.s.is_editing_connectors)

    def test_cache_changes_after_same_count_vertex_move(self):
        obj=self.fixture();p=surface.prepare_split_candidates(bpy.context)
        obj.data.vertices[0].co.x-=.002;obj.data.update()
        q=surface.prepare_split_candidates(bpy.context)
        self.assertNotEqual(p.cut_signature,q.cut_signature)

    def test_cache_changes_after_guide_moved(self):
        self.fixture();guide=operators.ensure_plane_guide(bpy.context)
        bpy.context.view_layer.update()
        p=surface.prepare_split_candidates(bpy.context)
        guide.location.z+=.002;bpy.context.view_layer.update()
        q=surface.prepare_split_candidates(bpy.context)
        self.assertNotEqual(p.cut_signature,q.cut_signature)
        self.assertAlmostEqual(q.surface_origin.z-p.surface_origin.z,.002,places=6)

    def test_scene_scale_invalidates_cache(self):
        self.fixture();p=surface.prepare_split_candidates(bpy.context)
        self.scene.unit_settings.scale_length=.001
        q=surface.prepare_split_candidates(bpy.context)
        self.assertNotEqual(p.cut_signature,q.cut_signature)
        self.assertAlmostEqual(q.unit_scale,1,places=6)

    def test_male_side_invalidates_normal(self):
        self.fixture();p=surface.prepare_split_candidates(bpy.context)
        self.s.connector_male_part='B';q=surface.prepare_split_candidates(bpy.context)
        self.assertLess(p.surface_normal.dot(q.surface_normal),-.999)

    def test_loop_base_clearance_invalidates_cache_and_preview(self):
        obj=self.fixture();self.capture(obj);self.s.loop_detach_add_base=True
        self.s.loop_detach_base_depth_mm=5
        p=surface.prepare_split_candidates(bpy.context)
        sig=operators.compute_session_input_signature(bpy.context)
        self.s.loop_detach_base_clearance_mm=.2
        q=surface.prepare_split_candidates(bpy.context)
        self.assertNotEqual(p.cut_signature,q.cut_signature)
        self.assertNotEqual(sig,operators.compute_session_input_signature(bpy.context))

    def test_footprint_detects_enclosed_tiny_hole(self):
        outer=[[(-10,-10),(10,-10),(10,10),(-10,10)]]
        holes=[[(.5,.5),(.7,.5),(.7,.7),(.5,.7)]]
        valid,_=connectors.validate_connector_footprint(0,0,2,outer,holes)
        self.assertFalse(valid)

    def test_planar_raycast_rejects_hole(self):
        self.fixture();p=surface.prepare_split_candidates(bpy.context)
        p.bvh_tree=None;p.interface.hole_contours_uv=[[(-.005,-.005),(.005,-.005),(.005,.005),(-.005,.005)]]
        hit=surface.raycast_connector_surface(p.surface_origin+Vector((0,0,.1)),Vector((0,0,-1)),p)
        self.assertIsNone(hit)

    def test_capsule_parallel_pair_is_valid(self):
        self.fixture();self.s.connector_type='CAPSULE';self.s.connector_capsule_length_mm=20
        self.s.connector_diameter_mm=4
        self.pin(0,-5);self.pin(0,5)
        p=surface.prepare_split_candidates(bpy.context)
        self.assertTrue(all(e['is_valid'] for e in surface.evaluate_connector_specs(p,self.s)))

    def test_crossing_capsules_are_invalid(self):
        self.fixture();self.s.connector_type='CAPSULE';self.s.connector_capsule_length_mm=20
        self.pin(0,0,45);self.pin(0,0,-45)
        p=surface.prepare_split_candidates(bpy.context)
        self.assertTrue(all(not e['is_valid'] for e in surface.evaluate_connector_specs(p,self.s)))

    def test_male_B_pin_rotation_matches_insertion(self):
        obj=self.fixture();p=surface.prepare_split_candidates(bpy.context)
        layout=connectors.compute_connector_layout(obj.data,obj.matrix_world,p.surface_origin,
            -p.interface.normal_a_to_b_world,distribution='MANUAL',interface=p.interface,
            manual_specs=[dict(u_mm=0,v_mm=0,yaw_deg=0)])
        z=layout['pin_rotations'][0].to_matrix() @ Vector((0,0,1))
        self.assertLess(z.dot(p.interface.normal_a_to_b_world),-.999)

    def test_plane_pin_patterns_A_and_B_manifold(self):
        self.fixture();self.s.connector_enabled=True
        for male in ['A','B']:
            for dist in ['CENTER','LINEAR_2','LINEAR_3','GRID_4','AUTO_SHAPE']:
                with self.subTest(male=male,pattern=dist):
                    self.s.connector_male_part=male;self.s.connector_distribution=dist
                    self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
                    self.assertTrue(self.s.part_a_is_manifold and self.s.part_b_is_manifold)

    def test_loop_pin_patterns_manifold(self):
        obj=self.fixture();self.capture(obj);self.s.loop_detach_add_base=True
        self.s.loop_detach_base_depth_mm=5;self.s.connector_enabled=True
        for dist in ['CENTER','LINEAR_2','LINEAR_3','GRID_4','AUTO_SHAPE']:
            with self.subTest(pattern=dist):
                self.s.connector_distribution=dist
                self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
                self.assertTrue(self.s.part_a_is_manifold and self.s.part_b_is_manifold)

    def test_material_pin_patterns_manifold(self):
        self.fixture();self.s.split_mode='MATERIAL';self.s.material_split_index=1
        self.s.material_extrude_depth_mm=5;self.s.connector_enabled=True
        for dist in ['CENTER','LINEAR_2','LINEAR_3','GRID_4','AUTO_SHAPE']:
            with self.subTest(pattern=dist):
                self.s.connector_distribution=dist
                self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
                self.assertTrue(self.s.part_a_is_manifold and self.s.part_b_is_manifold)

    def test_flat_loop_depth_solid(self):
        obj=self.fixture(False);self.capture(obj);self.s.loop_behavior='EXTRUDE'
        self.s.loop_extrude_depth_mm=5
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(),{'FINISHED'})
        self.assertAlmostEqual(self.s.part_a_volume_mm3,8000,delta=1)

    def test_nonplanar_depth_rejected_without_leaking_objects(self):
        obj=self.fixture();obj.data.vertices[8].co.z-=.003;obj.data.update()
        self.capture(obj);self.s.loop_behavior='EXTRUDE'
        before=(len(bpy.data.objects),len(bpy.data.meshes))
        with self.assertRaises(RuntimeError):bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(self.s.session_status,'PREVIEW_INVALID')
        # One persistent restoration snapshot is expected; no boolean candidates.
        self.assertFalse(any(o.name.startswith('_cand') for o in bpy.data.objects))
        self.assertFalse(any('loop_prism' in o.name for o in bpy.data.objects))

    def test_guide_rotation_drives_explosion_normal(self):
        self.fixture();g=operators.ensure_plane_guide(bpy.context)
        g.rotation_euler=(math.pi/2,0,0);bpy.context.view_layer.update()
        bpy.ops.chest.splitter_generate_preview()
        self.assertAlmostEqual(abs(self.s.preview_explosion_normal[1]),1,places=5)

    def test_grid_spacing_no_snap_and_lifecycle(self):
        self.fixture();self.s.connector_distribution='MANUAL'
        bpy.ops.chest.splitter_edit_manual_connectors();self.pin(1.23,4.56)
        p=surface.prepare_split_candidates(bpy.context)
        grid=surface.generate_positioning_grid_points(p)
        self.assertGreater(len(grid),1)
        self.assertTrue(all(abs(u/5-round(u/5))<1e-8 and abs(v/5-round(v/5))<1e-8 for u,v,_ in grid))
        self.assertAlmostEqual(self.s.manual_connectors[0].u_mm,1.23,places=5)
        bpy.ops.chest.splitter_cancel_manual_connectors()
        self.assertFalse(self.s.is_editing_connectors)

    def test_modifiers_used_in_plane_preparation(self):
        obj=self.fixture();m=obj.modifiers.new('ScaleCut','DISPLACE');m.strength=.002
        p=surface.prepare_split_candidates(bpy.context)
        self.assertGreater(p.interface.width_mm,100)

    def test_save_reopen_capture_and_manual_positions(self):
        obj=self.fixture();self.capture(obj);self.pin(6,7,10)
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'regression.blend');bpy.ops.wm.save_as_mainfile(filepath=path)
            bpy.ops.wm.open_mainfile(filepath=path)
        self.s=bpy.context.scene.chest_splitter
        self.assertTrue(self.s.loop_is_captured)
        self.assertEqual(self.s.manual_connectors[0].v_mm,7)
        surface.clear_prepared_split_cache()
        self.assertIsNotNone(surface.prepare_split_candidates(bpy.context))

    def test_anchored_solid_dimension_callback_keeps_anchor(self):
        obj=self.fixture();self.s.split_mode='SOLID'
        cutter=operators.ensure_solid_cutter(bpy.context)
        self.s.solid_cutter_object=cutter
        cutter['chest_align_anchor_local']=(.5,.5,.5)
        bpy.context.view_layer.update()
        anchor=cutter.matrix_world @ Vector((.5,.5,.5))
        self.s.solid_cutter_width_mm=35
        bpy.context.view_layer.update()
        new_anchor=cutter.matrix_world @ Vector((.5,.5,.5))
        self.assertLess((anchor-new_anchor).length,1e-6)
        xs=[v.co.x for v in cutter.data.vertices]
        self.assertAlmostEqual((max(xs)-min(xs))*cutter.scale.x*1000,35,places=3)

    def test_direct_error_replaces_previous_localized_status(self):
        self.s.set_localized_status('target.edit')
        self.s.last_status='Regression error'
        self.assertEqual(self.s.get_localized_status(),'Regression error')

    def test_live_capture_valid_without_leaving_edit_mode(self):
        obj=self.fixture();self.capture(obj)
        bpy.ops.object.mode_set(mode='EDIT')
        valid,reason=geometry_loop.validate_capture(obj,self.s,bpy.context)
        self.assertTrue(valid,reason)
        bm=bmesh.from_edit_mesh(obj.data)
        bmesh.ops.subdivide_edges(bm,edges=[next(iter(bm.edges))],cuts=1)
        bmesh.update_edit_mesh(obj.data)
        valid,_=geometry_loop.validate_capture(obj,self.s,bpy.context)
        self.assertFalse(valid)
        bpy.ops.object.mode_set(mode='OBJECT')

    def test_old_modal_cannot_stop_reopened_editor(self):
        from types import SimpleNamespace
        self.fixture()
        state=editor.get_editor_interaction_state()
        dummy=SimpleNamespace(_generation=state['generation'])
        editor.stop_connector_editor(self.scene)
        state['is_active']=True
        result=editor.CHEST_OT_splitter_edit_manual_connectors._modal_impl(
            dummy,bpy.context,SimpleNamespace())
        self.assertEqual(result,{'FINISHED','PASS_THROUGH'})
        self.assertTrue(state['is_active'])

    def test_drag_release_outside_viewport_finishes_drag(self):
        from types import SimpleNamespace
        from src.input_state import editor_configuration
        obj=self.fixture();self.pin()
        self.s.connector_enabled=True;self.s.connector_distribution='MANUAL'
        self.s.is_editing_connectors=True
        prep=surface.prepare_split_candidates(bpy.context)
        state=editor.get_editor_interaction_state()
        state.update(is_active=True,is_dragging=True,drag_idx=0)
        area=SimpleNamespace(type='VIEW_3D',x=0,y=0,width=100,height=100,
            regions=[],tag_redraw=lambda:None)
        dummy=SimpleNamespace(_generation=state['generation'],_prepared=prep,
            _target=obj,_area=area,_configuration=editor_configuration(self.s,self.scene))
        event=SimpleNamespace(type='LEFTMOUSE',value='RELEASE',mouse_x=-1000,mouse_y=-1000,alt=False)
        result=editor.CHEST_OT_splitter_edit_manual_connectors._modal_impl(dummy,bpy.context,event)
        self.assertEqual(result,{'RUNNING_MODAL'})
        self.assertFalse(state['is_dragging'])
        self.assertEqual(state['drag_idx'],-1)

if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]],verbosity=2)
