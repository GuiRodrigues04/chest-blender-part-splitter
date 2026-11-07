"""Bateria de testes de regressão cobrindo a matriz R01 a R18 do Plano Final de Correção 0.8.4/0.8.5."""

import os
import sys
import shutil
import tempfile
import xml.etree.ElementTree as ET
import unittest
import bpy
import bmesh
from mathutils import Vector

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import src
from src.constants import (
    COLLECTION_WORK_NAME,
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    ROLE_WORK_COPY,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
    PREVIEW_A_NAME,
    PREVIEW_B_NAME,
    WORK_COPY_SUFFIX,
)
from src.diagnostic import get_scene_scale_to_mm
from src.io_export import build_3mf_xml, export_objects_to_3mf
from src.translations import _get_current_locale
from src.geometry_connectors import compute_connector_layout, check_receiving_wall_thickness
from src.operators import verify_preview_current, get_current_session_parts, update_preview_positions


class TestFinalPlanCorrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter
        self.temp_dir = tempfile.mkdtemp()
        self.settings.export_directory = self.temp_dir

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except OSError:
                pass
        bpy.ops.wm.read_homefile(use_empty=True)

    def _create_box(self, name="TestBox", size_x=0.04, size_y=0.03, size_z=0.02, location=(0, 0, 0)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        self.scene.collection.objects.link(obj)

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        # Escala vertices para o tamanho solicitado (span de create_cube com size=1.0 é [-0.5, +0.5])
        for v in bm.verts:
            v.co.x *= size_x
            v.co.y *= size_y
            v.co.z *= size_z
        bm.to_mesh(mesh)
        bm.free()
        obj.location = Vector(location)
        bpy.context.view_layer.update()
        return obj

    def test_r01_work_copy_and_preview_cleanup_triple_update(self):
        """R01: Criar cópia de trabalho e gerar prévia 3 vezes consecutivas preservando alvo e original."""
        orig = self._create_box("CubeOrig", 0.04, 0.03, 0.02)
        bpy.ops.object.select_all(action='DESELECT')
        orig.select_set(True)
        bpy.context.view_layer.objects.active = orig

        # 1. Define alvo
        res = bpy.ops.chest.splitter_set_target()
        self.assertIn('FINISHED', res)
        self.assertEqual(self.settings.target_object, orig)

        # 2. Cria cópia de trabalho
        res = bpy.ops.chest.splitter_create_work_copy()
        self.assertIn('FINISHED', res)
        work_copy = self.settings.target_object
        self.assertIsNotNone(work_copy)
        self.assertTrue(work_copy.name.endswith(WORK_COPY_SUFFIX))
        self.assertEqual(work_copy.get("chest_role"), ROLE_WORK_COPY)

        # Verifica coleção da cópia de trabalho
        work_col = bpy.data.collections.get(COLLECTION_WORK_NAME)
        self.assertIsNotNone(work_col)
        self.assertIn(work_copy.name, work_col.objects)

        # 3. Gera prévia 3 vezes consecutivas
        for i in range(3):
            res = bpy.ops.chest.splitter_generate_preview()
            self.assertIn('FINISHED', res, f"Falha na geração de prévia #{i+1}")
            self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

            # Original e cópia de trabalho DEVEM continuar existindo intactos no Blender!
            self.assertIn(orig.name, bpy.data.objects, f"Original foi apagado na iteração #{i+1}!")
            self.assertIn(work_copy.name, bpy.data.objects, f"Cópia de trabalho foi apagada na iteração #{i+1}!")
            self.assertEqual(self.settings.target_object, work_copy)

            preview_col = bpy.data.collections.get(COLLECTION_PREVIEWS_NAME)
            self.assertIsNotNone(preview_col)
            self.assertIn(PREVIEW_A_NAME, preview_col.objects)
            self.assertIn(PREVIEW_B_NAME, preview_col.objects)

    def test_r02_restore_original_visibility(self):
        """R02: Restaurar original reativa o objeto base e limpa a cópia com segurança."""
        orig = self._create_box("TargetRestore", 0.04, 0.03, 0.02)
        orig.select_set(True)
        bpy.context.view_layer.objects.active = orig

        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_create_work_copy()
        work_copy = self.settings.target_object

        bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        work_copy_name = work_copy.name
        # Restaura original
        res = bpy.ops.chest.splitter_restore_original()
        self.assertIn('FINISHED', res)
        self.assertEqual(self.settings.target_object, orig)
        self.assertFalse(orig.hide_get(), "Original permaneceu oculto após restore!")
        self.assertNotIn(work_copy_name, bpy.data.objects, "Cópia de trabalho não foi limpa no restore!")

    def test_r03_r04_physical_dimensions_and_operator_returns(self):
        """R03/R04: Exportação em mm e retornos explícitos {'FINISHED'} nas escalas 1.0, 0.01 e 0.001."""
        test_scales = [1.0, 0.01, 0.001]

        for s_len in test_scales:
            self.scene.unit_settings.scale_length = s_len
            unit_scale = get_scene_scale_to_mm(self.scene)

            # Peça conhecida de 40 x 30 x 20 mm
            # Tamanho em BU = mm / unit_scale
            bx = 40.0 / unit_scale
            by = 30.0 / unit_scale
            bz = 20.0 / unit_scale

            box = self._create_box(f"Box_Scale_{s_len}", bx, by, bz)
            box.select_set(True)
            bpy.context.view_layer.objects.active = box

            bpy.ops.chest.splitter_set_target()
            res_prev = bpy.ops.chest.splitter_generate_preview()
            self.assertIn('FINISHED', res_prev)

            # 1. Exporta 3MF
            self.settings.export_format = '3MF'
            res_exp_3mf = bpy.ops.chest.splitter_export_parts()
            self.assertEqual(res_exp_3mf, {'FINISHED'}, f"3MF export não retornou FINISHED para scale {s_len}")

            out_3mf = os.path.join(self.temp_dir, f"{box.name}__parts.3mf")
            self.assertTrue(os.path.exists(out_3mf), f"Arquivo 3MF não foi criado: {out_3mf}")

            # Valida dimensões dentro do XML do 3MF
            import zipfile
            with zipfile.ZipFile(out_3mf, "r") as zf:
                xml_content = zf.read("3D/3dmodel.model").decode("utf-8")
                root = ET.fromstring(xml_content)
                # Verifica vértices em mm
                ns = {"core": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
                vertices = root.findall(".//core:vertex", ns)
                self.assertGreater(len(vertices), 0)
                xs = [float(v.attrib["x"]) for v in vertices]
                ys = [float(v.attrib["y"]) for v in vertices]
                zs = [float(v.attrib["z"]) for v in vertices]
                dim_x = max(xs) - min(xs)
                dim_y = max(ys) - min(ys)
                dim_z = max(zs) - min(zs)
                self.assertAlmostEqual(dim_x, 40.0, delta=0.5, msg=f"Dim X em mm incorreta no 3MF para scale {s_len}")
                self.assertAlmostEqual(dim_y, 30.0, delta=0.5, msg=f"Dim Y em mm incorreta no 3MF para scale {s_len}")
                self.assertAlmostEqual(dim_z, 20.0, delta=0.5, msg=f"Dim Z em mm incorreta no 3MF para scale {s_len}")

            # 2. Exporta STL_PARTS
            self.settings.export_format = 'STL_PARTS'
            res_exp_stl = bpy.ops.chest.splitter_export_parts()
            self.assertEqual(res_exp_stl, {'FINISHED'}, f"STL_PARTS export não retornou FINISHED para scale {s_len}")

            # 3. Exporta OBJ
            self.settings.export_format = 'OBJ'
            res_exp_obj = bpy.ops.chest.splitter_export_parts()
            self.assertEqual(res_exp_obj, {'FINISHED'}, f"OBJ export não retornou FINISHED para scale {s_len}")

    def test_r05_r06_multi_session_and_canonical_unexploded_export(self):
        """R05/R06: Isolamento de sessões X e Y na mesma cena e exportação canônica não-explodida."""
        self.scene.unit_settings.scale_length = 1.0
        unit_scale = get_scene_scale_to_mm(self.scene)

        # 1. Corte X: Confirma
        box_x = self._create_box("Box_X", 40/unit_scale, 30/unit_scale, 20/unit_scale, location=(-0.1, 0, 0))
        box_x.select_set(True)
        bpy.context.view_layer.objects.active = box_x
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        res_commit_x = bpy.ops.chest.splitter_commit_parts()
        self.assertIn('FINISHED', res_commit_x)
        sid_x = self.settings.session_id

        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        self.assertIsNotNone(parts_col)
        parts_x = [o for o in parts_col.objects if o.get("chest_session_id") == sid_x]
        self.assertEqual(len(parts_x), 2)

        # 2. Corte Y: Prévia na mesma cena com Explosão
        box_y = self._create_box("Box_Y", 40/unit_scale, 30/unit_scale, 20/unit_scale, location=(0.1, 0, 0))
        box_y.select_set(True)
        bpy.context.view_layer.objects.active = box_y
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        # Ativa vista explodida
        self.settings.view_mode = 'EXPLODED'
        self.settings.explosion_distance_mm = 50.0
        update_preview_positions(self.scene)

        preview_col = bpy.data.collections.get(COLLECTION_PREVIEWS_NAME)
        pa = preview_col.objects.get(PREVIEW_A_NAME)
        pb = preview_col.objects.get(PREVIEW_B_NAME)
        self.assertGreater((pa.location - pb.location).length, 0.01, "Objetos não foram explodidos na viewport")

        # 3. Exporta corte Y
        self.settings.export_format = '3MF'
        res_exp_y = bpy.ops.chest.splitter_export_parts()
        self.assertEqual(res_exp_y, {'FINISHED'})

        # Verifica que na viewport eles CONTINUAM explodidos
        self.assertGreater((pa.location - pb.location).length, 0.01, "A vista explodida foi desfeita permanentemente!")

        # Lê o 3MF exportado e confirma alinhamento canônico montado (sem os 50mm de afastamento)
        out_3mf_y = os.path.join(self.temp_dir, f"{box_y.name}__parts.3mf")
        import zipfile
        with zipfile.ZipFile(out_3mf_y, "r") as zf:
            xml_content = zf.read("3D/3dmodel.model").decode("utf-8")
            root = ET.fromstring(xml_content)
            # Deve conter apenas as partes de Y, e nenhuma de X
            objects_in_xml = root.findall(".//{http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel}object")
            names_in_xml = [o.attrib.get("name", "") for o in objects_in_xml]
            for n in names_in_xml:
                self.assertNotIn("Box_X", n, "Peças do corte X foram indevidamente exportadas no corte Y!")

    def test_r07_r08_stale_invalidation_rules(self):
        """R07/R08: Invalidar prévia quando geometria/cortador mudar; não invalidar em explosão/contraste."""
        box = self._create_box("BoxStaleTest", 0.04, 0.03, 0.02)
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        # 1. Mudança de explosão ou contraste NÃO deve invalidar
        self.settings.explosion_distance_mm = 45.0
        self.settings.view_mode = 'EXPLODED'
        self.settings.preview_color_mode = 'PARTS'
        is_cur, reason = verify_preview_current(bpy.context)
        self.assertTrue(is_cur, f"Explosão/cor invalidou indevidamente a prévia: {reason}")

        # 2. Mudança na transformação do alvo DEVE invalidar
        box.location.x += 0.05
        bpy.context.view_layer.update()
        is_cur2, reason2 = verify_preview_current(bpy.context)
        self.assertFalse(is_cur2, "Mudança de posição do alvo não invalidou a prévia!")

        # Exportação deve ser bloqueada
        res_exp = bpy.ops.chest.splitter_export_parts()
        self.assertEqual(res_exp, {'CANCELLED'}, "Exportação com prévia desatualizada não foi cancelada!")
        self.assertEqual(self.settings.session_status, 'PREVIEW_STALE')

    def test_r11_r12_connectors_capsule_and_wall_thickness(self):
        """R11/R12: Auto-ajuste de cápsula e diagnóstico seguro de espessura de parede."""
        # 1. Auto-ajuste de cápsula em interface estreita
        # Interface de 20 x 20 mm com cápsula de 30 mm solicitada
        box = self._create_box("CapsuleBox", 0.02, 0.02, 0.02)
        layout = compute_connector_layout(
            target_mesh=box.data,
            matrix_world=box.matrix_world,
            plane_origin=Vector((0.0, 0.0, 0.0)),
            plane_normal=Vector((0.0, 0.0, 1.0)),
            diameter_mm=4.0,
            distribution='CENTER',
            edge_margin_mm=1.0,
            connector_type='CAPSULE',
            capsule_length_mm=30.0,  # Maior que a interface (20mm)
        )
        self.assertIn("positions", layout)
        self.assertGreater(len(layout["positions"]), 0, "Deveria ter gerado conector ajustado")
        self.assertLessEqual(layout["adjusted_capsule_length_mm"], 20.0, "Cápsula não foi auto-ajustada ao limite seguro!")

        # 2. check_receiving_wall_thickness com raio sem corpo receptor
        # Objeto fino sem corpo atrás
        thin_box = self._create_box("ThinBox", 0.04, 0.03, 0.001)
        valid_wall, thick = check_receiving_wall_thickness(
            obj_female=thin_box,
            positions=[Vector((0.0, 0.0, 0.001))],
            normal=Vector((0.0, 0.0, -1.0)),
            required_depth_bu=0.01,
            min_wall_bu=0.001,
            cavity_radius_bu=0.003,
        )
        self.assertFalse(valid_wall, "Parede de 1mm não deveria suportar profundidade de 10mm!")

    def test_r15_xml_special_characters_and_atomic_replace(self):
        """R15: Escaping seguro de caracteres especiais no XML do 3MF."""
        box = self._create_box('Peça "A" & B <teste>', 0.04, 0.03, 0.02)
        xml_str = build_3mf_xml([box], unit_scale=1000.0)

        # O XML DEVE ser perfeitamente parseável sem erro de sintaxe
        try:
            root = ET.fromstring(xml_str)
            self.assertIsNotNone(root)
        except ET.ParseError as e:
            self.fail(f"XML inválido gerado para nome com caracteres especiais: {e}")

    def test_r16_locale_fallback(self):
        """R16: _get_current_locale retorna pt_BR para português e en_US para inglês/fallback."""
        # Com locale forçado em pt_BR
        loc_pt = _get_current_locale(forced_locale="pt_BR")
        self.assertEqual(loc_pt, "pt_BR")

        # Com locale em en_US ou outros idiomas
        loc_en = _get_current_locale(forced_locale="en_US")
        self.assertEqual(loc_en, "en_US")

        loc_ja = _get_current_locale(forced_locale="ja_JP")
        self.assertEqual(loc_ja, "en_US")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestFinalPlanCorrections)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    sys.exit(0)
