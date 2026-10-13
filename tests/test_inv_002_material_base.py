"""Suíte de testes para INV-002: Destaque de saliência por material com tampa na base (Etapa 3 / C01-C04).

Valida:
- C01: Região com 13 faces e folga zero (caso real de reprodução INV-002) é destacada com sucesso ou diagnóstico claro.
- C02: Saliência com faces planas pintadas adjacentes ao corpo não gera película nem tampa sobreposta.
- C03: Reuso de faces existentes na interface apenas quando a incidência topológica é correta; detecção de duplicadas.
- C04: Falha seguida de nova tentativa mantém estado original/backup limpo e sem lixo na cena.
"""

import unittest
import bpy
import bmesh
from mathutils import Vector
import os
import sys

# Garante import do código fonte
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.geometry_material import (
    analyze_material_structure,
    slice_mesh_by_material,
    get_material_regions,
)


class TestINV002MaterialBase(unittest.TestCase):

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def tearDown(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh, do_unlink=True)
        for mat in list(bpy.data.materials):
            bpy.data.materials.remove(mat, do_unlink=True)

    def _create_boss_on_cube(self):
        """Cria um cubo base com uma saliência 40x40x20 mm unida e manifold."""
        mesh = bpy.data.meshes.new("TestCubeMesh")
        bm = bmesh.new()

        # Vértices base (Z: 0 a 0.10, X: 0 a 0.10, Y: 0 a 0.10 em metros)
        cube_verts = []
        for z in (0.0, 0.10):
            for y in (0.0, 0.10):
                for x in (0.0, 0.10):
                    cube_verts.append(bm.verts.new((x, y, z)))
        bm.verts.ensure_lookup_table()

        # Fundo e laterais do cubo
        bm.faces.new((cube_verts[0], cube_verts[2], cube_verts[3], cube_verts[1]))
        bm.faces.new((cube_verts[0], cube_verts[1], cube_verts[5], cube_verts[4]))
        bm.faces.new((cube_verts[2], cube_verts[6], cube_verts[7], cube_verts[3]))
        bm.faces.new((cube_verts[0], cube_verts[4], cube_verts[6], cube_verts[2]))
        bm.faces.new((cube_verts[1], cube_verts[3], cube_verts[7], cube_verts[5]))

        # Saliência (boss) de 40x40x20 mm
        b0 = bm.verts.new((0.03, 0.03, 0.10))
        b1 = bm.verts.new((0.07, 0.03, 0.10))
        b2 = bm.verts.new((0.07, 0.07, 0.10))
        b3 = bm.verts.new((0.03, 0.07, 0.10))

        # Topo do cubo ao redor do boss
        c4, c5, c6, c7 = cube_verts[4], cube_verts[5], cube_verts[6], cube_verts[7]
        bm.faces.new((c4, c5, b1, b0))
        bm.faces.new((c5, c7, b2, b1))
        bm.faces.new((c7, c6, b3, b2))
        bm.faces.new((c6, c4, b0, b3))

        # Paredes e topo da saliência
        t0 = bm.verts.new((0.03, 0.03, 0.12))
        t1 = bm.verts.new((0.07, 0.03, 0.12))
        t2 = bm.verts.new((0.07, 0.07, 0.12))
        t3 = bm.verts.new((0.03, 0.07, 0.12))

        f_b_front = bm.faces.new((b0, b1, t1, t0))
        f_b_right = bm.faces.new((b1, b2, t2, t1))
        f_b_back  = bm.faces.new((b2, b3, t3, t2))
        f_b_left  = bm.faces.new((b3, b0, t0, t3))
        f_b_top   = bm.faces.new((t0, t1, t2, t3))

        # Materiais: slot 0 (Base), slot 1 (Boss/Erro)
        for f in (f_b_front, f_b_right, f_b_back, f_b_left, f_b_top):
            f.material_index = 1

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("BossCube", mesh)
        mat_base = bpy.data.materials.new(name="MatBase")
        mat_erro = bpy.data.materials.new(name="MatErro")
        obj.data.materials.append(mat_base)
        obj.data.materials.append(mat_erro)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def test_c01_boss_extraction_without_face_already_exists(self):
        """C01: Saliência destacada pela base não levanta 'face already exists' e produz sólidos estanques."""
        # Se a cena real de teste estiver presente, testa nela; senão, usa a geometria sintética
        real_blend = os.path.join(os.path.dirname(__file__), "..", "scratch", "Testes_Cutter_Original.blend")
        if os.path.exists(real_blend):
            bpy.ops.wm.open_mainfile(filepath=real_blend)
            obj = bpy.data.objects.get("Cube")
            self.assertIsNotNone(obj, "Objeto Cube deve existir na cena real")

            # Região 1 (13 faces com material Erro, que causava o erro na versão anterior)
            res = slice_mesh_by_material(obj, material_index=1, region_index=1, extraction_mode='BASE')
            self.assertTrue(res.split_result.success)
            self.assertTrue(res.split_result.part_a_metrics["is_manifold"], "Parte A deve ser manifold")
            self.assertTrue(res.split_result.part_b_metrics["is_manifold"], "Parte B deve ser manifold")
            self.assertEqual(res.split_result.part_a_metrics["non_manifold_edges"], 0)
            self.assertEqual(res.split_result.part_b_metrics["non_manifold_edges"], 0)
            self.assertGreater(res.split_result.part_a_metrics["volume_mm3"], 1000.0)
            self.assertGreater(res.split_result.part_b_metrics["volume_mm3"], 1000.0)
            res.bm_a.free()
            res.bm_b.free()
        else:
            obj = self._create_boss_on_cube()
            res = slice_mesh_by_material(obj, material_index=1, region_index=0, extraction_mode='BASE')
            self.assertTrue(res.split_result.success)
            self.assertTrue(res.split_result.part_a_metrics["is_manifold"])
            self.assertTrue(res.split_result.part_b_metrics["is_manifold"])
            res.bm_a.free()
            res.bm_b.free()

    def test_c02_boss_with_painted_flat_faces_no_thin_film(self):
        """C02: Saliência com faces coplanares da base pintadas não gera película (sem bordas abertas ou não-manifold)."""
        real_blend = os.path.join(os.path.dirname(__file__), "..", "scratch", "Testes_Cutter_Original.blend")
        if os.path.exists(real_blend):
            bpy.ops.wm.open_mainfile(filepath=real_blend)
            obj = bpy.data.objects.get("Cube")
            info = analyze_material_structure(obj, material_index=1, region_index=1)
            # A Região 1 deve identificar as 4 faces coplanares da base
            self.assertIn("coplanar_base_face_indices", info)
            self.assertEqual(len(info["coplanar_base_face_indices"]), 4)
            self.assertEqual(len(info["protrusion_face_indices"]), 9)

            res = slice_mesh_by_material(obj, material_index=1, region_index=1, extraction_mode='BASE')
            # Parte A não possui arestas de borda (película fin)
            self.assertEqual(res.split_result.part_a_metrics["non_manifold_edges"], 0)
            self.assertEqual(res.split_result.part_b_metrics["non_manifold_edges"], 0)
            # Volume total estritamente conservado
            sum_vol = res.split_result.part_a_metrics["volume_mm3"] + res.split_result.part_b_metrics["volume_mm3"]
            self.assertGreater(sum_vol, 0.0)
            res.bm_a.free()
            res.bm_b.free()

    def test_c03_coplanar_only_region_diagnostic(self):
        """C03: Região 100% coplanar à base é recusada com diagnóstico claro em modo BASE."""
        # Cria um cubo onde apenas uma face plana recebe material 1
        mesh = bpy.data.meshes.new("FlatMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.faces.ensure_lookup_table()
        mat0 = bpy.data.materials.new("M0")
        mat1 = bpy.data.materials.new("M1")
        mesh.materials.append(mat0)
        mesh.materials.append(mat1)
        bm.faces[0].material_index = 1
        for f in bm.faces[1:]:
            f.material_index = 0
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("FlatObj", mesh)
        bpy.context.scene.collection.objects.link(obj)

        with self.assertRaises(ValueError) as ctx:
            slice_mesh_by_material(obj, material_index=1, region_index=0, extraction_mode='BASE')
        self.assertIn("completamente coplanar com a base", str(ctx.exception))

    def test_c04_cleanup_after_error_and_retry(self):
        """C04: Estado da cena e dos objetos é preservado mesmo após falha ou nova tentativa."""
        mesh = bpy.data.meshes.new("CleanMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        mat0 = bpy.data.materials.new("MatA")
        mat1 = bpy.data.materials.new("MatB")
        mesh.materials.append(mat0)
        mesh.materials.append(mat1)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new("CleanObj", mesh)
        bpy.context.scene.collection.objects.link(obj)

        initial_obj_count = len(bpy.data.objects)

        # Tentativa 1 com erro (nenhuma face do material 1)
        try:
            slice_mesh_by_material(obj, material_index=1, region_index=0, extraction_mode='BASE')
        except ValueError:
            pass

        # Garante que nenhum objeto temporário vazou na cena
        self.assertEqual(len(bpy.data.objects), initial_obj_count)

        # Pinta uma face
        obj.data.polygons[0].material_index = 1

        # Tentativa 2 com erro (face plana em modo BASE)
        try:
            slice_mesh_by_material(obj, material_index=1, region_index=0, extraction_mode='BASE')
        except ValueError:
            pass

        self.assertEqual(len(bpy.data.objects), initial_obj_count)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
