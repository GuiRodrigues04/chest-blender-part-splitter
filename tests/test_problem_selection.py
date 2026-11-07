import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy,bmesh
from mathutils import Matrix,Vector
import src
from src.problem_selection import problem_elements


def snapshot(bm):
    bm.verts.index_update()
    return ([tuple(v.co) for v in bm.verts],sorted(tuple(sorted(v.index for v in e.verts)) for e in bm.edges),
            sorted(tuple(sorted(v.index for v in f.verts)) for f in bm.faces))


class ProblemSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):src.register()
    @classmethod
    def tearDownClass(cls):src.unregister()
    def setUp(self):
        if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    def target(self,bm):
        mesh=bpy.data.meshes.new('ProblemMesh');bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new('Target',mesh);bpy.context.scene.collection.objects.link(obj)
        bpy.context.scene.chest_splitter.target_object=obj;bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        return obj

    def test_two_holes_group_navigation_and_geometry_preserved(self):
        bm=bmesh.new()
        for x in (0,4):
            verts=bmesh.ops.create_cube(bm,size=2)['verts'];bmesh.ops.translate(bm,verts=verts,vec=(x,0,0))
        bm.normal_update()
        top=[f for f in bm.faces if f.normal.z>.9]
        bmesh.ops.delete(bm,geom=top,context='FACES')
        original=snapshot(bm);obj=self.target(bm)
        self.assertEqual(bpy.ops.chest.splitter_locate_problems(),{'FINISHED'})
        edit=bmesh.from_edit_mesh(obj.data);self.assertEqual(snapshot(edit),original)
        self.assertEqual(sum(e.select for e in edit.edges),8)
        self.assertTrue(all(not e.is_manifold for e in edit.edges if e.select))
        self.assertEqual(bpy.ops.chest.splitter_locate_problems(mode='NEXT'),{'FINISHED'})
        edit=bmesh.from_edit_mesh(obj.data)
        first={tuple(v.co) for v in edit.verts if v.select};self.assertEqual(len(first),4)
        bpy.ops.chest.splitter_locate_problems(mode='NEXT');edit=bmesh.from_edit_mesh(obj.data)
        second={tuple(v.co) for v in edit.verts if v.select}
        self.assertTrue(first.isdisjoint(second));self.assertEqual(snapshot(edit),original)
        # Repair both holes manually; a fresh scan must clear selection and diagnostic warning.
        bmesh.ops.holes_fill(edit,edges=[e for e in edit.edges if e.is_boundary],sides=0)
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.chest.splitter_locate_problems()
        self.assertFalse(any(v.select for v in edit.verts))
        self.assertTrue(bpy.context.scene.chest_splitter.diag_is_manifold)

    def test_nonmanifold_edge_and_loose_vertex(self):
        bm=bmesh.new();a=bm.verts.new((0,0,0));b=bm.verts.new((1,0,0))
        for co in ((0,1,0),(0,-1,0),(0,0,1)):bm.faces.new((a,b,bm.verts.new(co)))
        loose=bm.verts.new((5,5,5));original=snapshot(bm)
        obj=self.target(bm);bpy.ops.chest.splitter_locate_problems()
        edit=bmesh.from_edit_mesh(obj.data)
        self.assertTrue(any(len(e.link_faces)==3 and e.select for e in edit.edges))
        self.assertTrue(next(v for v in edit.verts if tuple(v.co)==(5,5,5)).select)
        self.assertEqual(snapshot(edit),original)

    def test_singular_vertex_between_closed_shells(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=2)
        verts=bmesh.ops.create_cube(bm,size=2)['verts'];bmesh.ops.translate(bm,verts=verts,vec=(2,2,2))
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
        self.assertTrue(all(e.is_manifold for e in bm.edges))
        bad,edges,faces,groups=problem_elements(bm,Matrix.Identity(4),1000)
        self.assertEqual(len(bad),1);self.assertEqual(len(groups),1)
        obj=self.target(bm);bpy.ops.chest.splitter_locate_problems()
        self.assertEqual(sum(v.select for v in bmesh.from_edit_mesh(obj.data).verts),1)

    def test_flipped_winding_and_live_edit(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.04);obj=self.target(bm)
        bpy.ops.object.mode_set(mode='EDIT');edit=bmesh.from_edit_mesh(obj.data)
        face=next(iter(edit.faces));face.normal_flip()
        original=snapshot(edit)
        bpy.ops.chest.splitter_locate_problems()
        self.assertEqual(sum(e.select for e in edit.edges),4)
        self.assertEqual(snapshot(edit),original)

    def test_clean_mesh_deselects_and_switches_to_target(self):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=.04);obj=self.target(bm)
        bpy.ops.mesh.primitive_cube_add(size=.01);other=bpy.context.object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.chest.splitter_locate_problems()
        self.assertEqual(bpy.context.edit_object,obj)
        self.assertFalse(any(v.select for v in bmesh.from_edit_mesh(obj.data).verts))
        self.assertEqual(other.mode,'OBJECT')


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProblemSelection))
    sys.exit(0 if result.wasSuccessful() else 1)
