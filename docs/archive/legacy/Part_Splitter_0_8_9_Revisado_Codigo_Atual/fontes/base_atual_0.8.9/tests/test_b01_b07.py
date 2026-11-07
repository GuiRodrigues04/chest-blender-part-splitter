import bpy
import bmesh
import unittest
import os
import sys
import tempfile
import unittest
import bpy
import bmesh
from mathutils import Vector

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import src

class TestCorrecoesB01B07(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            src.unregister()
        except:
            pass
        src.register()

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        
    def test_b01_b02_sessoes_distintas(self):
        # T01: Definir X, confirmar; definir Y, confirmar -> IDs distintos; Y exporta só Y
        bpy.ops.mesh.primitive_cube_add(location=(-5, 0, 0))
        cube_x = bpy.context.active_object
        cube_x.name = "Teste_X"
        
        bpy.ops.mesh.primitive_cube_add(location=(5, 0, 0))
        cube_y = bpy.context.active_object
        cube_y.name = "Teste_Y"
        
        # X
        bpy.context.view_layer.objects.active = cube_x
        cube_x.select_set(True)
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()
        
        settings = bpy.context.scene.chest_splitter
        id_x = settings.session_id
        
        # Y
        bpy.context.view_layer.objects.active = cube_y
        cube_y.select_set(True)
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()
        
        id_y = settings.session_id
        
        self.assertNotEqual(id_x, id_y, "IDs devem ser distintos (B01)")
        self.assertTrue(bool(id_x), "ID não pode ser vazio")
        self.assertNotEqual(id_x, "session_01")
        
        # Exportar Y
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings.export_directory = tmp_dir
            settings.export_format = 'STL_PARTS'
            res = bpy.ops.chest.splitter_export_parts()
            self.assertEqual(res, {'FINISHED'})
            
            files = os.listdir(tmp_dir)
            self.assertEqual(len(files), 2, "Devem ser exportadas apenas as 2 partes de Y")
            
    def test_b03_limpeza_segura(self):
        # T07: Objeto do usuário em coleção de prévias -> Sobrevive
        bpy.ops.mesh.primitive_monkey_add(location=(0,0,5))
        user_obj = bpy.context.active_object
        user_obj.name = "Objeto_do_usuario"
        
        from src.operators import get_or_create_collection, COLLECTION_PREVIEWS_NAME
        col = get_or_create_collection(bpy.context.scene, COLLECTION_PREVIEWS_NAME)
        
        for old_col in user_obj.users_collection:
            old_col.objects.unlink(user_obj)
        col.objects.link(user_obj)
        
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        
        self.assertIn("Objeto_do_usuario", bpy.data.objects, "Objeto do usuário não deve ser apagado (B03)")

    def test_b05_validacao_rejeita_faces_apagadas(self):
        # T16: Apagar face de uma prévia -> Confirmar/exportar bloqueados por integridade
        bpy.ops.mesh.primitive_cube_add()
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        
        from src.constants import PREVIEW_A_NAME
        obj_a = bpy.data.objects.get(PREVIEW_A_NAME)
        self.assertIsNotNone(obj_a)
        
        # Apagar uma face (fazendo ser não-manifold)
        bm = bmesh.new()
        bm.from_mesh(obj_a.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES')
        bm.to_mesh(obj_a.data)
        bm.free()
        
        with self.assertRaises(RuntimeError, msg="Deve rejeitar peça editada manualmente com face aberta (B05)"):
            bpy.ops.chest.splitter_commit_parts()

    def test_b06_b07_separacao_material(self):
        # T21: Separar por material antes de confirmar -> Bloqueado
        bpy.ops.mesh.primitive_cube_add()
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        
        with self.assertRaises(RuntimeError, msg="Não deve permitir separar por material na prévia (B07)"):
            bpy.ops.chest.splitter_separate_by_material()
        
        bpy.ops.chest.splitter_commit_parts()
        
        # Adicionar segundo material e face colorida
        parts_col = bpy.data.collections.get("CHEST_SPLITTER_PARTS")
        part_a = parts_col.objects[0]
        
        mat1 = bpy.data.materials.new("Mat1")
        mat2 = bpy.data.materials.new("Mat2")
        part_a.data.materials.append(mat1)
        part_a.data.materials.append(mat2)
        
        part_a.data.polygons[0].material_index = 1
        
        # Separar
        res = bpy.ops.chest.splitter_separate_by_material()
        self.assertEqual(res, {'FINISHED'})
        
        # T19: Exportar STL_PER_MATERIAL -> Deve rejeitar porque é casca superficial
        settings = bpy.context.scene.chest_splitter
        settings.export_format = 'STL_PER_MATERIAL'
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings.export_directory = tmp_dir
            with self.assertRaises(RuntimeError, msg="Deve rejeitar exportação STL de casca superficial (B06)"):
                bpy.ops.chest.splitter_export_parts()

if __name__ == '__main__':
    res = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestCorrecoesB01B07))
    if not res.wasSuccessful():
        import sys
        sys.exit(1)
