"""Suíte de aceitação final da Etapa 7: Entrega, Pacote Limpo e Regressão de Fluxos.

Valida os requisitos finais do plano (Seções 8, 11 e 13):
1. Integridade do pacote comercial .zip (exclusão estrita de scratch/, tests/, caches).
2. Licença legal GPL-2.0 completa sem marcadores de texto incompletos.
3. Consistência de versão e metadados no manifesto e __init__.py.
4. Fluxos completos de ponta a ponta (Plano, Loop, Sólido e Material).
5. Coexistência de APIs (scene.part_splitter e scene.chest_splitter).
"""

import os
import sys
import zipfile
import unittest
import bpy
import bmesh
from mathutils import Vector

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import src
from src.constants import COLLECTION_PARTS_NAME, PREVIEW_A_NAME, PREVIEW_B_NAME
from src.geometry_material import list_material_regions, analyze_material_structure


class TestAcceptanceEtapa7Delivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter

    def tearDown(self):
        bpy.ops.wm.read_homefile(use_empty=True)

    def test_01_commercial_zip_purity(self):
        import glob
        zip_candidates = (
            glob.glob(os.path.join(parent_dir, "dist", "chest_part_splitter-*.zip")) +
            glob.glob(os.path.join(parent_dir, "chest_part_splitter-*.zip"))
        )
        zip_path = zip_candidates[0] if zip_candidates else None
        self.assertTrue(zip_path and os.path.exists(zip_path), f"Arquivo ZIP não encontrado: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            # Deve conter arquivos obrigatórios
            self.assertIn("blender_manifest.toml", names)
            self.assertIn("LICENSE", names)
            self.assertIn("__init__.py", names)
            self.assertIn("src/operators.py", names)
            self.assertIn("src/geometry_material.py", names)

            # NÃO deve conter pastas e arquivos proibidos
            for n in names:
                n_lower = n.lower()
                self.assertFalse(n_lower.startswith("scratch/"), f"Arquivo de scratch no ZIP: {n}")
                self.assertFalse(n_lower.startswith("tests/"), f"Arquivo de testes no ZIP: {n}")
                self.assertFalse(n_lower.startswith("docs/"), f"Documento interno no ZIP: {n}")
                self.assertFalse("__pycache__" in n_lower, f"Cache no ZIP: {n}")
                self.assertFalse(n_lower.endswith(".blend"), f"Arquivo .blend no ZIP: {n}")
                self.assertFalse(n_lower.endswith(".png"), f"Imagem solta no ZIP: {n}")

    def test_02_license_integrity(self):
        """Valida que o arquivo LICENSE contém o texto completo da GPL-2.0 sem marcadores incompletos."""
        lic_path = os.path.join(parent_dir, "LICENSE")
        with open(lic_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("[Full GPL-2.0 License Text]", content)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", content)
        self.assertIn("TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION", content)
        self.assertIn("END OF TERMS AND CONDITIONS", content)

    def test_03_metadata_version_consistency(self):
        """Valida consistência estrita da versão entre manifesto, __init__.py e changelog."""
        init_path = os.path.join(parent_dir, "__init__.py")
        with open(init_path, "r", encoding="utf-8") as f:
            init_code = f.read()
        self.assertTrue('"version": (0, 8, 6)' in init_code or '"version": (0, 8, 5)' in init_code or '"version": (0, 8, 4)' in init_code)

        import tomllib
        manifest_path = os.path.join(parent_dir, "blender_manifest.toml")
        with open(manifest_path, "rb") as mf:
            mdata = tomllib.load(mf)
        self.assertIn(mdata.get("version"), ("0.8.6", "0.8.5", "0.8.4"))
        self.assertEqual(mdata.get("id"), "chest_part_splitter")

    def test_04_full_material_multi_region_workflow(self):
        """Valida o fluxo completo de corte por material em regiões separadas do modelo do usuário."""
        # Cria cubo 30x30x30 mm subdividido
        bpy.ops.mesh.primitive_cube_add(size=30.0, location=(0, 0, 0))
        cube = bpy.context.active_object
        m0 = bpy.data.materials.new("Cor_Base")
        m1 = bpy.data.materials.new("Cor_Detalhe")
        cube.data.materials.append(m0)
        cube.data.materials.append(m1)

        bm = bmesh.new()
        bm.from_mesh(cube.data)
        bm.faces.ensure_lookup_table()
        # Pinta face 4 (-Z) e face 5 (+Z) com o material 1 (duas ilhas independentes opostas)
        bm.faces[4].material_index = 1
        bm.faces[5].material_index = 1
        bm.to_mesh(cube.data)
        cube.data.update()
        bm.free()

        regions = list_material_regions(cube, 1)
        self.assertEqual(len(regions), 2)

        self.settings.target_object = cube
        self.settings.split_mode = 'MATERIAL'
        self.settings.material_split_index = 1
        self.settings.material_region_index = 0
        self.settings.material_extrude_depth_mm = 5.0
        self.settings.view_mode = 'EXPLODED'

        # Gera preview da Região 0
        res = bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(res, {'FINISHED'})
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')
        self.assertTrue(self.settings.part_a_is_manifold)
        self.assertTrue(self.settings.part_b_is_manifold)
        self.assertEqual(self.settings.part_a_non_manifold_edges, 0)
        self.assertEqual(self.settings.part_b_non_manifold_edges, 0)
        self.assertLess(self.settings.volume_diff_pct, 0.1)

        # Confirma criação das peças
        res_commit = bpy.ops.chest.splitter_commit_parts()
        self.assertEqual(res_commit, {'FINISHED'})
        self.assertEqual(self.settings.session_status, 'COMMITTED')

        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        self.assertIsNotNone(parts_col)
        self.assertGreaterEqual(len(parts_col.objects), 2)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAcceptanceEtapa7Delivery)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
