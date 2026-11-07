import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy,bmesh
from mathutils import Matrix
import src
from src.interface_history import (CONTACT,PREVIOUS,archive_contact_marks,
                                   recover_previous_interfaces,clear_recovery_cache)
from src.geometry_clearance import triangulated_source_mesh
from src.geometry_region import mesh_signature


class InterfaceHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()
    def setUp(self):
        if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.wm.read_factory_settings(use_empty=True);clear_recovery_cache()
    def pair(self,linked=True):
        bpy.ops.mesh.primitive_cube_add(size=.01);ancestor=bpy.context.object
        ancestor.name='Ancestor'
        marker=ancestor.data.attributes.new(CONTACT,'INT','FACE')
        top=next(f.index for f in ancestor.data.polygons if f.normal.z>.9)
        marker.data[top].value=1
        current=bpy.data.objects.new('Current',ancestor.data.copy())
        bpy.context.scene.collection.objects.link(current)
        current.data.attributes.remove(current.data.attributes[CONTACT])
        current['chest_operation_id']='cut01'
        if linked:
            record=bpy.context.scene.chest_operations.add();record.operation_id='cut01'
            record.status='COMMITTED';record.target_object=ancestor
        return ancestor,current,top
    def test_tessellation_remaps_all_interface_face_tags(self):
        ancestor,_,top=self.pair()
        prev=ancestor.data.attributes.new(PREVIOUS,'INT','FACE');prev.data[0].value=1
        patches=ancestor.data.attributes.new('splitter_contact_patch','INT','FACE');patches.data[top].value=7
        mesh=triangulated_source_mesh(ancestor.data)
        try:
            ancestor.data.calc_loop_triangles()
            for name in (CONTACT,PREVIOUS,'splitter_contact_patch'):
                self.assertEqual([d.value for d in mesh.attributes[name].data],
                                 [ancestor.data.attributes[name].data[t.polygon_index].value for t in ancestor.data.loop_triangles])
        finally:bpy.data.meshes.remove(mesh)
    def test_archive_keeps_previous_marks_and_clears_current(self):
        ancestor,_,top=self.pair();bm=bmesh.new();bm.from_mesh(ancestor.data)
        try:
            previous=bm.faces.layers.int.new(PREVIOUS);bm.faces.ensure_lookup_table();bm.faces[(top+1)%6][previous]=1
            patch=bm.faces.layers.int.new('splitter_contact_patch');bm.faces[top][patch]=7
            archive_contact_marks(bm)
            self.assertEqual(sum(f[bm.faces.layers.int[PREVIOUS]]!=0 for f in bm.faces),2)
            self.assertEqual(sum(f[bm.faces.layers.int[CONTACT]] for f in bm.faces),0)
            self.assertEqual(sum(f[patch] for f in bm.faces),0)
        finally:bm.free()
    def test_recovery_uses_recorded_ancestor_and_changes_only_metadata(self):
        ancestor,current,top=self.pair();signature=mesh_signature(current.data)
        self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),1)
        self.assertEqual(current.data.attributes[PREVIOUS].data[top].value,1)
        self.assertEqual(mesh_signature(current.data),signature)
        self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),0)
    def test_unrelated_marked_objects_cannot_authorize_recovery(self):
        _,current,_=self.pair(linked=False)
        self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),0)
        self.assertIsNone(current.data.attributes.get(PREVIOUS))
    def test_real_thin_wall_is_still_rejected(self):
        from src.geometry_loop import slice_mesh_by_loop_extrude
        from src.localized_errors import LocalizedGeometryError
        bpy.ops.mesh.primitive_cube_add(size=1.)
        obj=bpy.context.object;obj.scale=(.01,.01,.00002);bpy.context.view_layer.update()
        top=next(f for f in obj.data.polygons if f.normal.z>.9)
        with self.assertRaises(LocalizedGeometryError) as error:
            slice_mesh_by_loop_extrude(obj,obj.name,list(top.vertices),top.index,depth_mm=1.)
        self.assertEqual(error.exception.payload['__splitter_message__'],'geometry.wall_thickness')
    def test_missing_or_untrusted_snapshot_is_ignored(self):
        ancestor,current,_=self.pair(linked=False)
        record=bpy.context.scene.chest_operations.add();record.operation_id='cut01';record.status='COMMITTED'
        record.snapshot_object=ancestor  # Not tagged as this operation's backup.
        self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),0)
    def test_moved_source_cannot_transfer_marks(self):
        ancestor,current,_=self.pair();ancestor.location.x=1.;bpy.context.view_layer.update()
        self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),0)
    def test_shared_mesh_is_not_changed_for_another_object(self):
        _,current,_=self.pair();other=bpy.data.objects.new('Other',current.data)
        bpy.context.scene.collection.objects.link(other)
        self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),1)
        self.assertIsNot(current.data,other.data)
        self.assertIsNone(other.data.attributes.get(PREVIOUS))
    def test_recovery_preserves_edit_mode_and_selection(self):
        _,current,top=self.pair()
        bpy.ops.object.select_all(action='DESELECT');current.select_set(True)
        bpy.context.view_layer.objects.active=current
        bpy.ops.object.mode_set(mode='EDIT');bm=bmesh.from_edit_mesh(current.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:f.select_set(f.index==top)
        bmesh.update_edit_mesh(current.data)
        before={f.index for f in bm.faces if f.select}
        self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),1)
        self.assertEqual(current.mode,'EDIT')
        bm=bmesh.from_edit_mesh(current.data)
        self.assertEqual({f.index for f in bm.faces if f.select},before)
        self.assertEqual(sum(f[bm.faces.layers.int[PREVIOUS]] for f in bm.faces),1)
        bpy.ops.object.mode_set(mode='OBJECT')

    def test_edit_mode_with_existing_face_attributes(self):
        _,current,top=self.pair()
        current.data.attributes.new(CONTACT,'INT','FACE')
        current.data.attributes.new(PREVIOUS,'INT','FACE')
        bpy.ops.object.select_all(action='DESELECT');current.select_set(True)
        bpy.context.view_layer.objects.active=current
        bpy.ops.object.mode_set(mode='EDIT')
        mesh_count=len(bpy.data.meshes)
        try:
            self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),1)
            bm=bmesh.from_edit_mesh(current.data)
            bm.faces.ensure_lookup_table()
            self.assertEqual(bm.faces[top][bm.faces.layers.int[PREVIOUS]],1)
            self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),0)
            self.assertEqual(len(bpy.data.meshes),mesh_count)
        finally:bpy.ops.object.mode_set(mode='OBJECT')

    def test_edit_mode_existing_marks_are_preserved(self):
        _,current,top=self.pair()
        marker=current.data.attributes.new(PREVIOUS,'INT','FACE')
        other=(top+1)%6;marker.data[other].value=1
        bpy.ops.object.select_all(action='DESELECT');current.select_set(True)
        bpy.context.view_layer.objects.active=current;bpy.ops.object.mode_set(mode='EDIT')
        try:
            self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),1)
            bm=bmesh.from_edit_mesh(current.data);bm.faces.ensure_lookup_table()
            layer=bm.faces.layers.int[PREVIOUS]
            self.assertEqual({f.index for f in bm.faces if f[layer]}, {top,other})
        finally:bpy.ops.object.mode_set(mode='OBJECT')

    def test_ancestor_in_edit_mode_uses_live_face_marks(self):
        ancestor,current,top=self.pair()
        bpy.context.view_layer.objects.active=ancestor;bpy.ops.object.mode_set(mode='EDIT')
        try:
            bm=bmesh.from_edit_mesh(ancestor.data);bm.faces.ensure_lookup_table()
            layer=bm.faces.layers.int[CONTACT]
            other=(top+1)%6
            bm.faces[top][layer]=0;bm.faces[other][layer]=1
            self.assertEqual(recover_previous_interfaces(bpy.context.scene,current),1)
            marker=current.data.attributes[PREVIOUS]
            self.assertEqual({i for i,value in enumerate(marker.data) if value.value}, {other})
            self.assertEqual(ancestor.mode,'EDIT')
        finally:bpy.ops.object.mode_set(mode='OBJECT')

    def test_preview_from_edit_mode_with_previous_cut_attributes(self):
        _,current,_=self.pair()
        current.data.attributes.new(CONTACT,'INT','FACE')
        current.data.attributes.new(PREVIOUS,'INT','FACE')
        settings=bpy.context.scene.chest_splitter
        settings.target_object=current;settings.split_mode='PLANE';settings.connector_enabled=False
        bpy.ops.object.select_all(action='DESELECT');current.select_set(True)
        bpy.context.view_layer.objects.active=current;bpy.ops.object.mode_set(mode='EDIT')
        self.assertEqual(bpy.ops.chest.splitter_generate_preview(), {'FINISHED'})
        self.assertEqual(settings.session_status,'PREVIEW_VALID')


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InterfaceHistory))
    if not result.wasSuccessful():raise SystemExit(1)
