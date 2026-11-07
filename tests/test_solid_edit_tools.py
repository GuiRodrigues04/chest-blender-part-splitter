"""Cutter lifecycle, editable selections and every exposed alignment mode."""
import sys, unittest
from unittest.mock import patch
from types import MethodType
from pathlib import Path
from types import SimpleNamespace
import bpy, bmesh
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src
from src.geometry_solid import create_primitive_cutter_mesh, align_vertices, validate_solid_cutter
from src.ui import VIEW3D_PT_chest_part_splitter
from src.solid_tools import CHEST_OT_splitter_align_solid_vertices

def mesh_coords(obj):
    if obj.mode == 'EDIT':
        return [tuple(v.co) for v in bmesh.from_edit_mesh(obj.data).verts]
    return [tuple(v.co) for v in obj.data.vertices]

def cube(name, center=(0,0,0)):
    obj=bpy.data.objects.new(name,create_primitive_cutter_mesh(name,'BOX',Vector((.1,.12,.08))))
    bpy.context.scene.collection.objects.link(obj);obj.location=center
    bpy.context.view_layer.update();return obj

class SolidTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()
    def setUp(self):
        if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.t=cube('Target');self.s=bpy.context.scene.chest_splitter
        self.s.target_object=self.t;self.s.split_mode='SOLID'
    def cutter(self):
        self.assertEqual(bpy.ops.chest.splitter_create_solid_cutter(),{'FINISHED'})
        return self.s.solid_cutter_object
    def edit(self,obj):
        if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
        bpy.context.view_layer.objects.active=obj;bpy.ops.object.mode_set(mode='EDIT')
    def test_create_hidden_preserves_edited_mesh_transform_and_count(self):
        c=self.cutter();c.data.vertices[0].co.z-=.007;c.location=(.004,.008,.009)
        bpy.context.view_layer.update()
        before=mesh_coords(c);matrix=c.matrix_world.copy();count=len(bpy.data.objects)
        c.hide_set(True);c.hide_viewport=True
        for _ in range(3):self.cutter()
        self.assertEqual(c,self.s.solid_cutter_object)
        self.assertEqual(mesh_coords(c),before);self.assertEqual(c.matrix_world,matrix)
        self.assertEqual(len(bpy.data.objects),count);self.assertTrue(c.visible_get())
        self.assertEqual(bpy.context.active_object,c);self.assertTrue(c.select_get())
    def test_create_after_object_delete_and_after_delete_all_vertices(self):
        c=self.cutter();bpy.data.objects.remove(c,do_unlink=True)
        c=self.cutter();self.assertEqual(len(c.data.polygons),6)
        self.edit(c);bm=bmesh.from_edit_mesh(c.data)
        bmesh.ops.delete(bm,geom=bm.verts[:],context='VERTS');bmesh.update_edit_mesh(c.data)
        count=len(bpy.data.objects);self.cutter()
        self.assertEqual(len(bpy.data.objects),count)
        self.assertEqual(len(c.data.polygons),6);self.assertTrue(c.visible_get())
        self.assertTrue(validate_solid_cutter(c,None)['is_manifold'])
    def test_reveal_hidden_collection_and_focus(self):
        c=self.cutter();col=c.users_collection[0]
        col.hide_viewport=True
        def find(layer):
            if layer.collection==col:return layer
            for child in layer.children:
                result=find(child)
                if result:return result
        layer=find(bpy.context.view_layer.layer_collection);layer.exclude=True
        self.cutter();self.assertFalse(layer.exclude);self.assertTrue(c.visible_get())
        c.hide_set(True);self.assertEqual(bpy.ops.chest.splitter_focus_solid_cutter(),{'FINISHED'})
        self.assertTrue(c.visible_get())
    def test_reset_active_duplicate_resets_scale_and_keeps_original(self):
        original=self.cutter();shape=mesh_coords(original)
        bpy.ops.chest.splitter_duplicate_solid_cutter();c=self.s.solid_cutter_object
        c.scale=(.2,.4,.8);c.rotation_euler=(.3,.4,.5)
        self.assertEqual(bpy.ops.chest.splitter_reset_solid_cutter(),{'FINISHED'})
        self.assertEqual(tuple(c.scale),(1.,1.,1.));self.assertEqual(mesh_coords(original),shape)
        self.assertTrue(c.visible_get())
    def test_every_alignment_anchor_direction_with_offset_mesh_and_scale(self):
        c=self.cutter()
        for v in c.data.vertices:v.co+=Vector((.02,-.03,.04))
        self.t.matrix_world=Matrix.LocRotScale(Vector((.08,.02,-.04)),Euler((.2,.4,.6)).to_quaternion(),Vector((1.2,.8,1.7)))
        bpy.context.scene.cursor.location=(.2,.3,.4);bpy.context.scene.cursor.rotation_euler=(.1,.7,.2)
        target_shape=mesh_coords(self.t);cutter_shape=mesh_coords(c)
        self.edit(self.t);bm=bmesh.from_edit_mesh(self.t.data);bm.faces.ensure_lookup_table()
        for v in bm.verts:v.select_set(False)
        f=max(bm.faces,key=lambda f:f.normal.z);f.select_set(True);bm.faces.active=f
        ref_face=self.t.matrix_world@f.calc_center_median()
        n=(self.t.matrix_world.to_3x3().inverted().transposed()@f.normal).normalized()
        bmesh.update_edit_mesh(self.t.data)
        for mode in ('ACTIVE_FACE','TARGET_AXES','CURSOR_3D','AXIS_X','AXIS_Y','AXIS_Z','SELECTION_CENTER'):
            for anchor in ('CENTER','SUPPORT_FACE'):
                for invert in (False,True):
                    with self.subTest(mode=mode,anchor=anchor,invert=invert):
                        c.matrix_world=Matrix.LocRotScale(Vector((.03,.04,.05)),Euler((.6,.2,.1)).to_quaternion(),Vector((.7,1.3,.9)))
                        bpy.context.view_layer.update();rotation=c.matrix_world.to_quaternion()
                        args=dict(align_mode=mode,anchor=anchor,invert_direction=invert)
                        self.assertEqual(bpy.ops.chest.splitter_align_solid_cutter(**args),{'FINISHED'})
                        ref=ref_face if mode in ('ACTIVE_FACE','SELECTION_CENTER') else (bpy.context.scene.cursor.location if mode=='CURSOR_3D' else self.t.matrix_world.translation)
                        xs,ys,zs=zip(*cutter_shape)
                        local=Vector(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,min(zs) if anchor=='SUPPORT_FACE' and mode!='SELECTION_CENTER' else (min(zs)+max(zs))/2))
                        self.assertLess((c.matrix_world@local-ref).length,1e-6)
                        if mode=='SELECTION_CENTER':
                            self.assertLess(c.matrix_world.to_quaternion().rotation_difference(rotation).angle,1e-5)
                        else:
                            expected=n if mode=='ACTIVE_FACE' else ((self.t.matrix_world.to_quaternion().to_matrix()@Vector((0,0,1))) if mode=='TARGET_AXES' else (bpy.context.scene.cursor.rotation_euler.to_matrix()@Vector((0,0,1)) if mode=='CURSOR_3D' else Vector({'AXIS_X':(1,0,0),'AXIS_Y':(0,1,0),'AXIS_Z':(0,0,1)}[mode])))
                            if invert:expected=-expected
                            self.assertGreater((c.matrix_world.to_3x3()@Vector((0,0,1))).normalized().dot(expected),.99999)
                        first=c.matrix_world.copy();bpy.ops.chest.splitter_align_solid_cutter(**args)
                        self.assertLess(max(abs(c.matrix_world[i][j]-first[i][j]) for i in range(4) for j in range(4)),1e-6)
                        self.assertEqual(mesh_coords(c),cutter_shape)
        self.assertEqual(mesh_coords(self.t),target_shape)
    def test_empty_selection_alignment_does_not_move_cutter(self):
        c=self.cutter();matrix=c.matrix_world.copy();self.edit(self.t)
        bm=bmesh.from_edit_mesh(self.t.data)
        for v in bm.verts:v.select_set(False)
        for f in bm.faces:f.select_set(False)
        bm.faces.active=None;bmesh.update_edit_mesh(self.t.data)
        for mode in ('ACTIVE_FACE','SELECTION_CENTER'):
            self.assertEqual(bpy.ops.chest.splitter_align_solid_cutter(align_mode=mode),{'CANCELLED'})
            self.assertEqual(c.matrix_world,matrix)
    def test_single_vertex_alignment_preserves_other_vertices_and_world_transform(self):
        c=self.cutter();c.matrix_world=Matrix.LocRotScale(Vector((.2,.3,.1)),Euler((.2,.5,.7)).to_quaternion(),Vector((.8,1.3,.5)))
        self.t.matrix_world=Matrix.LocRotScale(Vector((.1,.1,.2)),Euler((.2,.8,.1)).to_quaternion(),Vector((1.2,.4,1.1)))
        bpy.context.view_layer.update();target_before=mesh_coords(self.t);before=mesh_coords(c);matrix=c.matrix_world.copy()
        self.edit(c)
        self.assertEqual(bpy.ops.chest.splitter_align_solid_vertices(move_mode='VERTEX',cutter_vertex=0,target_vertex=3),{'FINISHED'})
        bm=bmesh.from_edit_mesh(c.data);bm.verts.ensure_lookup_table()
        self.assertLess((c.matrix_world@bm.verts[0].co-self.t.matrix_world@self.t.data.vertices[3].co).length,1e-6)
        self.assertEqual(mesh_coords(c)[1:],before[1:]);self.assertEqual(c.matrix_world,matrix)
        self.assertEqual(mesh_coords(self.t),target_before);self.assertEqual(c.mode,'EDIT')
    def test_whole_vertex_alignment_and_pending_target_edit(self):
        c=self.cutter();self.edit(self.t)
        bm=bmesh.from_edit_mesh(self.t.data);bm.verts.ensure_lookup_table();bm.verts[3].co.z+=.011
        destination=self.t.matrix_world@bm.verts[3].co;before=mesh_coords(c)
        align_vertices(c,self.t,0,3)
        self.assertLess((c.matrix_world@c.data.vertices[0].co-destination).length,1e-6)
        self.assertEqual(mesh_coords(c),before)
    def test_faces_create_closed_editable_cutter_without_changing_target(self):
        old=self.cutter();old_mesh=old.data
        self.edit(self.t);bm=bmesh.from_edit_mesh(self.t.data)
        for v in bm.verts:v.select_set(False)
        top=max(bm.faces,key=lambda f:f.normal.z);top.select_set(True);bm.faces.active=top
        bmesh.update_edit_mesh(self.t.data);before=mesh_coords(self.t)
        self.assertEqual(bpy.ops.chest.splitter_create_cutter_from_selection(selection_kind='FACES',depth_mm=20,outer_extension_mm=1),{'FINISHED'})
        c=self.s.solid_cutter_object
        self.assertNotEqual(c,old);self.assertEqual(old.data,old_mesh)
        self.assertTrue(validate_solid_cutter(c,None)['is_manifold'])
        self.assertEqual(mesh_coords(self.t),before);self.assertTrue(c.visible_get())
        z=[v.co.z for v in c.data.vertices]
        self.assertAlmostEqual(max(z)-min(z),.021,places=6)
    def test_faces_invalid_preserves_previous_cutter(self):
        c=self.cutter();matrix=c.matrix_world.copy();self.edit(self.t)
        # The whole closed surface has no single extrusion direction.
        bm=bmesh.from_edit_mesh(self.t.data)
        for f in bm.faces:f.select_set(True)
        bmesh.update_edit_mesh(self.t.data)
        self.assertEqual(bpy.ops.chest.splitter_create_cutter_from_selection(selection_kind='FACES'),{'CANCELLED'})
        self.assertEqual(self.s.solid_cutter_object,c);self.assertEqual(c.matrix_world,matrix)
    def test_faces_button_enters_target_edit_before_creating(self):
        c=self.cutter();count=len(bpy.data.objects)
        self.assertEqual(bpy.ops.chest.splitter_create_cutter_from_selection(selection_kind='FACES'),{'FINISHED'})
        self.assertEqual(self.t.mode,'EDIT');self.assertEqual(self.s.solid_cutter_object,c)
        self.assertEqual(len(bpy.data.objects),count)
    def test_ui_exposes_all_alignments_and_both_vertex_behaviors(self):
        self.cutter();ops=[]
        class Layout:
            def row(self,*a,**k):return self
            column=box=split=grid_flow=row
            def label(self,*a,**k):pass
            def separator(self,*a,**k):pass
            def prop(self,*a,**k):pass
            def template_list(self,*a,**k):pass
            def operator(self,name,*a,**k):
                op=SimpleNamespace(name=name);ops.append(op);return op
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=Layout()),bpy.context)
        self.assertEqual({o.align_mode for o in ops if o.name=='chest.splitter_align_solid_cutter'}, {'ACTIVE_FACE','SELECTION_CENTER','CURSOR_3D','TARGET_AXES','AXIS_X','AXIS_Y','AXIS_Z'})
        self.assertEqual({o.move_mode for o in ops if o.name=='chest.splitter_align_solid_vertices'},{'OBJECT','VERTEX'})
        self.assertFalse(any(o.name=='chest.splitter_create_cutter_from_selection' for o in ops))

    def test_cursor_quaternion_rotation_and_edit_cutter_button(self):
        c=self.cutter();cursor=bpy.context.scene.cursor
        cursor.rotation_mode='QUATERNION';cursor.rotation_quaternion=Euler((.3,.4,.8)).to_quaternion()
        self.assertEqual(bpy.ops.chest.splitter_align_solid_cutter(align_mode='CURSOR_3D',anchor='CENTER'),{'FINISHED'})
        self.assertGreater((c.matrix_world.to_3x3()@Vector((0,0,1))).normalized().dot(cursor.rotation_quaternion@Vector((0,0,1))),.99999)
        self.assertEqual(bpy.ops.chest.splitter_edit_solid_cutter(),{'FINISHED'})
        self.assertEqual(bpy.context.edit_object,c)

    def modal_harness(self,c):
        # Exercise click/escape transitions using the real operator methods,
        # while deterministic projection makes vertex picking independent of GPU.
        area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
        region=next(r for r in area.regions if r.type=='WINDOW')
        harness=SimpleNamespace(move_mode='VERTEX',cutter_vertex=-1,target_vertex=-1,
            _cutter_obj=c,_target_obj=self.t,_stage=0,_hover=None,_handle=None,
            _area=area,_orig_active=c,_orig_mode='EDIT_MESH',_orig_selected=[c],
            report=lambda *args:None)
        for method in ('modal','_cleanup','execute'):
            setattr(harness,method,MethodType(getattr(CHEST_OT_splitter_align_solid_vertices,method),harness))
        return harness,region

    def test_vertex_two_click_flow_keeps_cutter_edit_and_changes_only_one_vertex(self):
        c=self.cutter();self.edit(c)
        bm=bmesh.from_edit_mesh(c.data)
        bmesh.ops.subdivide_edges(bm,edges=bm.edges[:],cuts=1,use_grid_fill=True)
        bmesh.update_edit_mesh(c.data)
        before=mesh_coords(c);picked=len(before)-1;target_before=mesh_coords(self.t)
        matrix=c.matrix_world.copy();h,r=self.modal_harness(c)
        event=SimpleNamespace(type='LEFTMOUSE',value='PRESS',mouse_x=r.x+30,mouse_y=r.y+30,alt=False)
        def projection(region,rv3d,point):
            obj=h._cutter_obj if h._stage==0 else h._target_obj
            coords=mesh_coords(obj);wanted=picked if h._stage==0 else 3
            location=obj.matrix_world@Vector(coords[wanted])
            return Vector((30,30)) if (point-location).length<1e-7 else Vector((5000,5000))
        with patch('src.connector_editor.get_view3d_canvas_region',return_value=r),patch('src.solid_tools.view3d_utils.location_3d_to_region_2d',side_effect=projection):
            self.assertEqual(h.modal(bpy.context,event),{'RUNNING_MODAL'})
            self.assertEqual(mesh_coords(c),before);self.assertEqual(bpy.context.edit_object,c)
            self.assertEqual(h.modal(bpy.context,event),{'FINISHED'})
        self.assertEqual(h.cutter_vertex,picked);self.assertEqual(h.target_vertex,3)
        self.assertEqual(mesh_coords(c)[:picked],before[:picked]);self.assertEqual(c.matrix_world,matrix)
        self.assertEqual(mesh_coords(self.t),target_before);self.assertEqual(bpy.context.edit_object,c)

    def test_cancel_vertex_pick_does_not_move_mesh_or_object(self):
        c=self.cutter();self.edit(c);before=mesh_coords(c);matrix=c.matrix_world.copy()
        h,r=self.modal_harness(c);h._stage=1;h.cutter_vertex=0
        event=SimpleNamespace(type='ESC',value='PRESS')
        self.assertEqual(h.modal(bpy.context,event),{'CANCELLED'})
        self.assertEqual(mesh_coords(c),before);self.assertEqual(c.matrix_world,matrix)
        self.assertEqual(bpy.context.edit_object,c)

    def test_single_vertex_operator_copies_shared_mesh_only_on_commit(self):
        c=self.cutter();other=bpy.data.objects.new('Linked',c.data)
        bpy.context.scene.collection.objects.link(other);before=mesh_coords(other)
        self.edit(c)
        self.assertEqual(bpy.ops.chest.splitter_align_solid_vertices(move_mode='VERTEX',cutter_vertex=0,target_vertex=3),{'FINISHED'})
        self.assertNotEqual(c.data,other.data);self.assertEqual(mesh_coords(other),before)

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
