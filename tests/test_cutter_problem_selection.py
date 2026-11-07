"""Locate cutter topology defects independently from the main target."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
import bpy,bmesh
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import src
from src.problem_selection import publish_cutter_diagnostics
from src.ui import VIEW3D_PT_chest_part_splitter

def snapshot(obj):
    if obj.mode=='EDIT':
        bm=bmesh.from_edit_mesh(obj.data);bm.verts.index_update()
        return ([tuple(v.co) for v in bm.verts],sorted(tuple(v.index for v in e.verts) for e in bm.edges),sorted(tuple(v.index for v in f.verts) for f in bm.faces))
    return ([tuple(v.co) for v in obj.data.vertices],sorted(tuple(e.vertices) for e in obj.data.edges),sorted(tuple(f.vertices) for f in obj.data.polygons))

class CutterProblems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()
    def setUp(self):
        if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=.04);self.target=bpy.context.object
        self.s=bpy.context.scene.chest_splitter;self.s.target_object=self.target;self.s.split_mode='SOLID'
    def cutter(self,bm):
        mesh=bpy.data.meshes.new('Cutter');bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new('Cutter',mesh);bpy.context.scene.collection.objects.link(obj)
        self.s.solid_cutter_object=obj;return obj
    def locate(self,mode='ALL'):
        return bpy.ops.chest.splitter_locate_problems(subject='CUTTER',mode=mode)
    def test_single_wire_edge_matches_screenshot_without_touching_target(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.03)
        a=bm.verts.new((.1,0,0));b=bm.verts.new((.12,0,0));bm.edges.new((a,b));c=self.cutter(bm)
        source=snapshot(self.target);original=snapshot(c)
        self.s.diag_volume_mm3=1234.;self.s.diag_non_manifold_edges=777
        self.assertEqual(self.s.solid_cutter_non_manifold_edges,1)
        self.assertIn('1',self.s.solid_cutter_problem_summary)
        self.assertTrue('wire edges' in self.s.solid_cutter_problem_summary or 'arestas soltas' in self.s.solid_cutter_problem_summary)
        c.hide_set(True)
        self.assertEqual(self.locate(),{'FINISHED'})
        self.assertEqual(bpy.context.edit_object,c)
        edit=bmesh.from_edit_mesh(c.data)
        self.assertEqual(sum(e.select for e in edit.edges),1)
        self.assertTrue(all(e.is_wire for e in edit.edges if e.select))
        self.assertEqual(snapshot(c),original);self.assertEqual(snapshot(self.target),source)
        self.assertEqual(self.s.target_object,self.target);self.assertEqual(self.s.diag_volume_mm3,1234.)
        self.assertEqual(self.s.diag_non_manifold_edges,777)
    def test_two_holes_next_and_refresh_after_manual_repair(self):
        bm=bmesh.new()
        for x in (0,.1):
            vs=bmesh.ops.create_cube(bm,size=.03)['verts'];bmesh.ops.translate(bm,verts=vs,vec=(x,0,0))
        bm.normal_update();bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.normal.z>.9],context='FACES')
        c=self.cutter(bm);before=snapshot(c);self.locate()
        self.assertEqual(self.s.solid_cutter_non_manifold_edges,8)
        self.locate('NEXT');edit=bmesh.from_edit_mesh(c.data);first={tuple(v.co) for v in edit.verts if v.select}
        self.locate('NEXT');second={tuple(v.co) for v in edit.verts if v.select}
        self.assertEqual(len(first),4);self.assertTrue(first.isdisjoint(second));self.assertEqual(snapshot(c),before)
        bmesh.ops.holes_fill(edit,edges=[e for e in edit.edges if e.is_boundary],sides=0)
        bmesh.update_edit_mesh(c.data);selected={v.index for v in edit.verts if v.select}
        self.locate('CHECK')
        self.assertTrue(self.s.solid_cutter_is_manifold);self.assertFalse(self.s.solid_cutter_has_problems)
        self.assertEqual(self.s.solid_cutter_non_manifold_edges,0)
        self.assertEqual(selected,{v.index for v in edit.verts if v.select});self.assertEqual(bpy.context.edit_object,c)
    def test_flipped_winding_is_selected(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.03);bm.faces.ensure_lookup_table();bm.faces[0].normal_flip()
        c=self.cutter(bm);self.locate();edit=bmesh.from_edit_mesh(c.data)
        self.assertEqual(sum(e.select for e in edit.edges),4)
        self.assertTrue(self.s.solid_cutter_has_problems)
        self.assertTrue(self.s.solid_cutter_is_manifold)
    def test_singular_vertex_between_closed_shells(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.03)
        vs=bmesh.ops.create_cube(bm,size=.03)['verts'];bmesh.ops.translate(bm,verts=vs,vec=(.03,.03,.03))
        bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
        c=self.cutter(bm);original=snapshot(c);self.locate()
        edit=bmesh.from_edit_mesh(c.data)
        self.assertEqual(sum(v.select for v in edit.verts),1)
        self.assertEqual(self.s.solid_cutter_non_manifold_edges,0)
        self.assertTrue(self.s.solid_cutter_has_problems);self.assertEqual(snapshot(c),original)
    def test_degenerate_face_and_zero_edge_are_located_without_repair(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.03)
        bm.verts.ensure_lookup_table();edge=next(iter(bm.edges));edge.verts[0].co=edge.verts[1].co
        c=self.cutter(bm);original=snapshot(c);self.locate()
        edit=bmesh.from_edit_mesh(c.data)
        self.assertTrue(any(e.select and e.calc_length()==0 for e in edit.edges))
        self.assertTrue(self.s.solid_cutter_has_problems);self.assertEqual(snapshot(c),original)
    def test_empty_cutter_no_false_clean_status(self):
        c=self.cutter(bmesh.new());self.locate('CHECK')
        self.assertFalse(self.s.solid_cutter_is_manifold);self.assertTrue(self.s.solid_cutter_has_problems)
        self.assertEqual(bpy.context.active_object,self.target)
    def test_modifier_defect_does_not_select_false_base_indices(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.03);c=self.cutter(bm)
        group=c.vertex_groups.new(name='Keep');group.add([0,1,2,3,4],1.,'REPLACE')
        modifier=c.modifiers.new('Open output','MASK');modifier.vertex_group=group.name
        modifier.show_in_editmode=True
        self.locate();edit=bmesh.from_edit_mesh(c.data)
        self.assertFalse(any(v.select for v in edit.verts))
        self.assertTrue(self.s.solid_cutter_diag_evaluated)
        self.assertTrue(self.s.solid_cutter_has_problems)
        self.assertIn('modifier',self.s.last_status.lower())
    def test_target_locator_still_uses_target(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.03);c=self.cutter(bm)
        self.locate();bpy.ops.chest.splitter_locate_problems()
        self.assertEqual(bpy.context.edit_object,self.target)
        self.assertEqual(c.mode,'OBJECT')
    def test_cutter_buttons_use_cutter_subject_and_three_modes(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.03);self.cutter(bm);ops=[]
        class Layout:
            def row(self,*a,**k):return self
            box=column=split=grid_flow=row
            def label(self,*a,**k):pass
            def prop(self,*a,**k):pass
            def separator(self,*a,**k):pass
            def template_list(self,*a,**k):pass
            def operator(self,name,*a,**k):
                op=SimpleNamespace(name=name);ops.append(op);return op
        VIEW3D_PT_chest_part_splitter.draw(SimpleNamespace(layout=Layout()),bpy.context)
        self.assertEqual({o.mode for o in ops if o.name=='chest.splitter_locate_problems' and getattr(o,'subject',None)=='CUTTER'},{'ALL','NEXT','CHECK'})

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
