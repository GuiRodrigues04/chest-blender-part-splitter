import sys
import os
import unittest
import bpy
import bmesh
from mathutils import Vector, Matrix

# Ensure src can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import src.properties as properties
import src.operators as operators
from src.geometry_material import analyze_material_structure, slice_mesh_by_material
from src.io_export import separate_object_by_material


class TestAcceptanceEtapa6Material(unittest.TestCase):
    def setUp(self):
        properties.register()
        operators.register()
        bpy.ops.wm.read_homefile(use_empty=True)
        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter

    def tearDown(self):
        bpy.ops.wm.read_homefile(use_empty=True)

    def test_01_scene_part_splitter_alias(self):
        """Valida que scene.part_splitter é um alias direto e funcional para scene.chest_splitter (Seção 8)."""
        self.assertTrue(hasattr(self.scene, "part_splitter"))
        self.assertEqual(self.scene.part_splitter, self.scene.chest_splitter)
        
        # Testar mutação via alias
        self.scene.part_splitter.clearance_preset = 'LOOSE'
        self.assertEqual(self.scene.chest_splitter.clearance_preset, 'LOOSE')
        self.scene.chest_splitter.clearance_preset = 'TIGHT'
        self.assertEqual(self.scene.part_splitter.clearance_preset, 'TIGHT')

    def test_02_closed_component_separation_manifold(self):
        """Valida que componentes fechados isolados atribuídos a materiais diferentes geram sólidos 100% manifold."""
        # 1. Cria cubo principal (20x20x20 mm)
        bpy.ops.mesh.primitive_cube_add(size=20.0, location=(0, 0, 0))
        main_cube = bpy.context.active_object
        mat_body = bpy.data.materials.new("Mat_Body")
        mat_body.diffuse_color = (0.2, 0.2, 0.8, 1.0)
        main_cube.data.materials.append(mat_body)

        # 2. Cria esfera acessório (olho / detalhe desconexo)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=4.0, location=(0, 0, 18))
        eye = bpy.context.active_object
        mat_eye = bpy.data.materials.new("Mat_Eye")
        mat_eye.diffuse_color = (0.9, 0.1, 0.1, 1.0)
        eye.data.materials.append(mat_eye)

        # 3. Junta ambos em um único objeto multipartes
        bpy.ops.object.select_all(action='DESELECT')
        main_cube.select_set(True)
        eye.select_set(True)
        bpy.context.view_layer.objects.active = main_cube
        bpy.ops.object.join()
        combined_obj = main_cube

        # 4. Análise de material
        analysis = analyze_material_structure(combined_obj, material_index=1)
        self.assertTrue(analysis["valid"])
        self.assertEqual(analysis["type"], "CLOSED_COMPONENT")
        self.assertTrue(analysis["is_manifold"])

        # 5. Executa corte por material
        vol_orig = 20.0**3 + (4.0/3.0 * 3.1415926535 * (4.0**3))
        res = slice_mesh_by_material(combined_obj, material_index=1, scene=self.scene)
        self.assertIsNotNone(res)
        bm_a, bm_b = res[0], res[1]

        # 6. Validação estrita de manifold (sem arestas abertas)
        open_edges_a = [e for e in bm_a.edges if not e.is_manifold]
        open_edges_b = [e for e in bm_b.edges if not e.is_manifold]
        self.assertEqual(len(open_edges_a), 0, f"Parte A tem {len(open_edges_a)} arestas abertas!")
        self.assertEqual(len(open_edges_b), 0, f"Parte B tem {len(open_edges_b)} arestas abertas!")

        vol_a = bm_a.calc_volume() * 1000.0**3 # scale default
        vol_b = bm_b.calc_volume() * 1000.0**3
        bm_a.free()
        bm_b.free()

    def test_03_surface_patch_extrusion_depth_manifold(self):
        """Valida que uma superfície contínua pintada com material diferente gera sólido com profundidade e encaixe cavidade."""
        # Cria cubo 30x30x30 mm
        bpy.ops.mesh.primitive_cube_add(size=30.0, location=(0, 0, 0))
        cube = bpy.context.active_object
        mat_base = bpy.data.materials.new("Mat_Base")
        mat_insert = bpy.data.materials.new("Mat_Insert")
        cube.data.materials.append(mat_base)
        cube.data.materials.append(mat_insert)

        # Pinta a face do topo (+Z) com o material 1
        bm = bmesh.new()
        bm.from_mesh(cube.data)
        top_face = max(bm.faces, key=lambda f: f.calc_center_median().z)
        top_face.material_index = 1
        bm.to_mesh(cube.data)
        cube.data.update()
        bm.free()

        # Análise
        analysis = analyze_material_structure(cube, material_index=1)
        self.assertTrue(analysis["valid"])
        self.assertEqual(analysis["type"], "SURFACE_PATCH")

        # Corta com 5 mm de profundidade
        res = slice_mesh_by_material(cube, material_index=1, depth_mm=5.0, scene=self.scene)
        self.assertIsNotNone(res)
        bm_a, bm_b = res[0], res[1]

        # Ambas as partes devem ser sólidos 100% estanques (manifold)
        open_edges_a = [e for e in bm_a.edges if not e.is_manifold]
        open_edges_b = [e for e in bm_b.edges if not e.is_manifold]
        self.assertEqual(len(open_edges_a), 0, f"Parte A tem arestas abertas: {len(open_edges_a)}")
        self.assertEqual(len(open_edges_b), 0, f"Parte B tem arestas abertas: {len(open_edges_b)}")

        vol_a = bm_a.calc_volume()
        vol_b = bm_b.calc_volume()
        bm_cube = bmesh.new()
        bm_cube.from_mesh(cube.data)
        vol_orig = bm_cube.calc_volume()
        bm_cube.free()

        # Conservação de volume
        self.assertAlmostEqual(vol_a + vol_b, vol_orig, delta=vol_orig * 0.01)
        bm_a.free()
        bm_b.free()

    def test_04_criterion_m1_material_slots_preservation(self):
        """Critério M1: Garante que os slots de materiais e índices de faces sejam estritamente preservados na prévia."""
        bpy.ops.mesh.primitive_cube_add(size=20.0, location=(0, 0, 0))
        cube = bpy.context.active_object
        mat1 = bpy.data.materials.new("Mat_Red")
        mat2 = bpy.data.materials.new("Mat_Blue")
        cube.data.materials.append(mat1)
        cube.data.materials.append(mat2)

        # Pinta face superior com mat2
        bm = bmesh.new()
        bm.from_mesh(cube.data)
        top_face = max(bm.faces, key=lambda f: f.calc_center_median().z)
        top_face.material_index = 1
        bm.to_mesh(cube.data)
        cube.data.update()
        bm.free()

        # Configura sessão
        self.settings.target_object = cube
        self.settings.split_mode = 'MATERIAL'
        self.settings.material_split_index = 1
        self.settings.material_extrude_depth_mm = 4.0

        # Executa preview
        res = bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(res, {'FINISHED'})
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        # Verifica preview objects e seus slots de materiais
        from src.constants import COLLECTION_PREVIEWS_NAME, PREVIEW_A_NAME, PREVIEW_B_NAME
        preview_col = bpy.data.collections.get(COLLECTION_PREVIEWS_NAME)
        self.assertIsNotNone(preview_col)
        obj_a = preview_col.objects.get(PREVIEW_A_NAME)
        obj_b = preview_col.objects.get(PREVIEW_B_NAME)
        self.assertIsNotNone(obj_a)
        self.assertIsNotNone(obj_b)

        # Critério M1: Ambos os objetos devem reter os materiais originais
        self.assertEqual(len(obj_a.data.materials), 2)
        self.assertEqual(len(obj_b.data.materials), 2)
        self.assertEqual(obj_a.data.materials[0].name, "Mat_Red")
        self.assertEqual(obj_a.data.materials[1].name, "Mat_Blue")

    def test_05_separate_by_material_open_edges_detection(self):
        """Valida que separate_object_by_material detecta cascas abertas e alerta usuário."""
        # Cria cubo com face pintada
        bpy.ops.mesh.primitive_cube_add(size=20.0, location=(0, 0, 0))
        cube = bpy.context.active_object
        m1 = bpy.data.materials.new("M1")
        m2 = bpy.data.materials.new("M2")
        cube.data.materials.append(m1)
        cube.data.materials.append(m2)

        bm = bmesh.new()
        bm.from_mesh(cube.data)
        bm.faces.ensure_lookup_table()
        bm.faces[0].material_index = 1
        bm.to_mesh(cube.data)
        cube.data.update()
        bm.free()

        target_col = self.scene.collection
        sub_objs = separate_object_by_material(cube, target_col)
        self.assertEqual(len(sub_objs), 2)

        # Como é uma superfície contínua cortada ingenuamente por deleção de faces, ambas ficam abertas!
        self.assertFalse(sub_objs[0]["is_manifold"])
        self.assertGreater(sub_objs[0]["open_edges"], 0)
        self.assertFalse(sub_objs[0]["is_solid_for_printing"])

    def test_06_operator_separate_by_material_warning(self):
        """Valida que o operador chest.splitter_separate_by_material alerta sobre cascas abertas."""
        bpy.ops.mesh.primitive_cube_add(size=20.0, location=(0, 0, 0))
        cube = bpy.context.active_object
        m1 = bpy.data.materials.new("M1_Op")
        m2 = bpy.data.materials.new("M2_Op")
        cube.data.materials.append(m1)
        cube.data.materials.append(m2)

        bm = bmesh.new()
        bm.from_mesh(cube.data)
        bm.faces.ensure_lookup_table()
        bm.faces[0].material_index = 1
        bm.to_mesh(cube.data)
        cube.data.update()
        bm.free()

        self.settings.target_object = cube
        self.settings.split_mode = 'PLANE'
        # Gera preview planar primeiro para ter status PREVIEW_VALID
        bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        bpy.ops.chest.splitter_commit_parts()
        self.assertEqual(self.settings.session_status, 'COMMITTED')

        # Executa separação por material
        res = bpy.ops.chest.splitter_separate_by_material()
        self.assertEqual(res, {'FINISHED'})
        self.assertEqual(self.settings.last_status_level, 'WARNING')
        self.assertIn("casca superficial aberta", self.settings.last_status)
        self.assertIn("Profundidade", self.settings.last_status)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAcceptanceEtapa6Material)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
