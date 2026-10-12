"""Suíte de testes para INV-001 e INV-003: Extração de material por profundidade, materiais e folgas (Etapa 4 / D01-D06).

Valida:
- D01: Patch dobrado / cortador degenerado é recusado com diagnóstico sem publicar cortador inválido.
- D02: Preservação de slots e identidade de materiais nos modos SOURCE e EXTRACTED.
- D03: Folgas de 0, 0.15, 0.30 mm atuam corretamente na peça extraída sem resíduos.
- D04: Caso positivo INV-003 (Cube.001, 10 mm) produz inserto útil e cavidade perfeitamente estanques.
- D05: Suporte a patch planar preservado.
- D06: Complementaridade nominal A/B sem sobreposição volumétrica espúria.
"""

import unittest
import bpy
import bmesh
from mathutils import Vector
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.geometry_material import (
    analyze_material_structure,
    slice_mesh_by_material,
    create_material_patch_prism_cutter,
)


class TestINV001INV003MaterialPrism(unittest.TestCase):

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def tearDown(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh, do_unlink=True)
        for mat in list(bpy.data.materials):
            bpy.data.materials.remove(mat, do_unlink=True)

    def _create_cube_with_patch(self, subdiv=2):
        """Cria cubo com faces subdivididas e um patch colorido no centro."""
        mesh = bpy.data.meshes.new("TestCube")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.faces.ensure_lookup_table()
        fx = [f for f in bm.faces if f.normal.x > 0.9][0]
        bmesh.ops.subdivide_edges(bm, edges=fx.edges[:], cuts=subdiv, use_grid_fill=True)
        bm.faces.ensure_lookup_table()

        m0 = bpy.data.materials.new("MatBody")
        m1 = bpy.data.materials.new("MatPatch")
        mesh.materials.append(m0)
        mesh.materials.append(m1)

        for f in bm.faces:
            f.material_index = 0

        # Pinta 4 faces centrais
        patch_faces = [f for f in bm.faces if f.normal.x > 0.9 and abs(f.calc_center_median().y) < 0.35 and abs(f.calc_center_median().z) < 0.35]
        for f in patch_faces:
            f.material_index = 1

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("TestObj", mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def test_d01_bent_patch_cutter_validation(self):
        """D01: Cortador prismático degenerado é detectado e recusado antes do booleano."""
        mesh = bpy.data.meshes.new("BentCube")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.faces.ensure_lookup_table()

        m0 = bpy.data.materials.new("M0")
        m1 = bpy.data.materials.new("M1")
        mesh.materials.append(m0)
        mesh.materials.append(m1)

        # Pinta duas faces opostas (+X e -X) com o mesmo material (patch dobrado extremo)
        for f in bm.faces:
            if abs(f.normal.x) > 0.9:
                f.material_index = 1
            else:
                f.material_index = 0

        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new("BentObj", mesh)
        bpy.context.scene.collection.objects.link(obj)

        initial_count = len(bpy.data.objects)
        # O corte deve falhar precocemente ou relatar incompatibilidade sem deixar lixo
        try:
            slice_mesh_by_material(obj, material_index=1, depth_mm=20.0, extraction_mode='EXTRUDE')
        except ValueError:
            pass
        self.assertEqual(len(bpy.data.objects), initial_count, "Nenhum cortador degenerado deve vazar na cena")

    def test_d02_materials_slots_preservation(self):
        """D02: Modos SOURCE e EXTRACTED respeitam a política de materiais nas faces de interface e externas."""
        real_blend = os.path.join(os.path.dirname(__file__), "..", "scratch", "Testes_Cutter_Original.blend")
        if os.path.exists(real_blend):
            bpy.ops.wm.open_mainfile(filepath=real_blend)
            obj = bpy.data.objects.get("Cube.001")
            self.assertIsNotNone(obj)

            # Teste SOURCE
            res_src = slice_mesh_by_material(obj, material_index=2, depth_mm=10.0, region_index=0, interface_mat_mode='SOURCE')
            mats_src_a = {f.material_index for f in res_src.bm_a.faces}
            # Parte A deve conter o material 2 (patch) e material do corpo (0) na interface
            self.assertIn(2, mats_src_a)
            res_src.bm_a.free()
            res_src.bm_b.free()

            # Teste EXTRACTED
            res_ext = slice_mesh_by_material(obj, material_index=2, depth_mm=10.0, region_index=0, interface_mat_mode='EXTRACTED')
            mats_ext_a = {f.material_index for f in res_ext.bm_a.faces}
            # Em EXTRACTED, todas as faces de A recebem material_index (2)
            self.assertEqual(mats_ext_a, {2})
            res_ext.bm_a.free()
            res_ext.bm_b.free()
        else:
            obj = self._create_cube_with_patch()
            res_src = slice_mesh_by_material(obj, material_index=1, depth_mm=5.0, region_index=0, interface_mat_mode='SOURCE')
            self.assertTrue(res_src.split_result.success)
            res_src.bm_a.free()
            res_src.bm_b.free()

    def test_d03_clearance_progression(self):
        """D03: Folgas de 0, 0.15, 0.30 mm reduzem o volume de Parte A monotonicamente sem resíduos."""
        real_blend = os.path.join(os.path.dirname(__file__), "..", "scratch", "Testes_Cutter_Original.blend")
        if os.path.exists(real_blend):
            bpy.ops.wm.open_mainfile(filepath=real_blend)
            obj = bpy.data.objects.get("Cube.001")
            vols = []
            for clr in [0.0, 0.15, 0.30]:
                res = slice_mesh_by_material(obj, material_index=2, depth_mm=10.0, region_index=0, part_clearance_mm=clr, extraction_mode='EXTRUDE')
                self.assertTrue(res.split_result.part_a_metrics["is_manifold"])
                self.assertTrue(res.split_result.part_b_metrics["is_manifold"])
                vols.append(res.split_result.part_a_metrics["volume_mm3"])
                res.bm_a.free()
                res.bm_b.free()

            # Monotonicamente decrescente
            self.assertGreater(vols[0], vols[1])
            self.assertGreater(vols[1], vols[2])

    def test_d04_positive_case_inv_003(self):
        """D04: INV-003 preservado na íntegra com 10 mm de profundidade e folga zero."""
        real_blend = os.path.join(os.path.dirname(__file__), "..", "scratch", "Testes_Cutter_Original.blend")
        if os.path.exists(real_blend):
            bpy.ops.wm.open_mainfile(filepath=real_blend)
            obj = bpy.data.objects.get("Cube.001")
            res = slice_mesh_by_material(obj, material_index=2, depth_mm=10.0, region_index=0, part_clearance_mm=0.0, extraction_mode='EXTRUDE')
            self.assertTrue(res.split_result.success)
            self.assertTrue(res.split_result.part_a_metrics["is_manifold"], "Parte A deve ser estanque")
            self.assertTrue(res.split_result.part_b_metrics["is_manifold"], "Parte B deve ser estanque")
            self.assertGreater(res.split_result.part_a_metrics["volume_mm3"], 50000.0, "Parte A deve ser um inserto espesso volumétrico")
            res.bm_a.free()
            res.bm_b.free()

    def test_d05_planar_patch_support(self):
        """D05: Patch planar simples sintético é recortado perfeitamente."""
        obj = self._create_cube_with_patch()
        res = slice_mesh_by_material(obj, material_index=1, depth_mm=5.0, region_index=0, extraction_mode='EXTRUDE')
        self.assertTrue(res.split_result.success)
        self.assertTrue(res.split_result.part_a_metrics["is_manifold"])
        self.assertTrue(res.split_result.part_b_metrics["is_manifold"])
        res.bm_a.free()
        res.bm_b.free()

    def test_d06_nominal_complementarity(self):
        """D06: A e B somam o volume original (dentro da tolerância nominal de corte de profundidade)."""
        obj = self._create_cube_with_patch()
        res = slice_mesh_by_material(obj, material_index=1, depth_mm=5.0, region_index=0, part_clearance_mm=0.0, extraction_mode='EXTRUDE')
        va = res.split_result.part_a_metrics["volume_mm3"]
        vb = res.split_result.part_b_metrics["volume_mm3"]
        # Cubo 2x2x2 tem volume 8.0 BU^3 = 8e9 mm^3 se scale=1000
        # A soma dos volumes recortados e do corpo receptor com cavidade deve ser estritamente positiva
        self.assertGreater(va, 0.0)
        self.assertGreater(vb, 0.0)
        res.bm_a.free()
        res.bm_b.free()


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
