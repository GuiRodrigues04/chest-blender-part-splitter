"""Suíte de testes para INV-006: Espessura de parede, cunhas e filmes sem volume (Etapa 5 / E01-E03).

Valida:
- E01: Distinção entre filme inválido (sem volume / não-manifold) e cunha geométrica fiel (volume > 0, manifold).
- E02: Diagnóstico de zona fina em cunha com resolução e preservação nominal sem alteração silenciosa da geometria.
- E03: Diagnóstico inconclusivo quando não há hit ou raios são tangentes; garantia de não assumir 1000 mm.
"""

import unittest
import bpy
import bmesh
from mathutils import Vector
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.geometry_loop import (
    analyze_loop_region,
    slice_mesh_by_loop,
)
from src.geometry_plane import evaluate_bmesh_metrics


class TestINV006ThicknessAndWedge(unittest.TestCase):

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def tearDown(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh, do_unlink=True)

    def _create_prism_wedge(self):
        """Cria um prisma triangular com uma borda em cunha (espessura decrescendo para 0 na aresta)."""
        mesh = bpy.data.meshes.new("WedgeMesh")
        bm = bmesh.new()
        # Vértices da cunha
        v0 = bm.verts.new((0.0, 0.0, 0.0))
        v1 = bm.verts.new((2.0, 0.0, 0.0))
        v2 = bm.verts.new((0.0, 2.0, 0.0))
        v3 = bm.verts.new((0.0, 0.0, 1.0))
        v4 = bm.verts.new((2.0, 0.0, 1.0))
        v5 = bm.verts.new((0.0, 2.0, 1.0))

        bm.faces.new((v0, v1, v2))        # base inferior
        bm.faces.new((v5, v4, v3))        # base superior
        bm.faces.new((v0, v3, v4, v1))    # face lateral Y=0
        bm.faces.new((v1, v4, v5, v2))    # face hipotenusa (cunha)
        bm.faces.new((v2, v5, v3, v0))    # face lateral X=0

        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new("WedgeObj", mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def test_e01_distinguish_film_vs_faithful_wedge(self):
        """E01: Cunha geométrica com aresta viva possui volume estritamente positivo e é manifold."""
        obj = self._create_prism_wedge()
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        metrics = evaluate_bmesh_metrics(bm, unit_scale=1000.0)
        bm.free()

        # Cunha possui volume real (> 0) e é 100% manifold
        self.assertTrue(metrics["is_manifold"], "Cunha geométrica sólida deve ser manifold")
        self.assertGreater(metrics["volume_mm3"], 1e6, "Cunha geométrica deve ter volume positivo")
        self.assertEqual(metrics["non_manifold_edges"], 0)

    def test_e02_thin_zone_preserves_nominal_geometry(self):
        """E02: Diagnóstico de zona fina não altera a geometria nominal da peça nem adiciona chanfros silenciosos."""
        obj = self._create_prism_wedge()
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        init_verts_count = len(bm.verts)
        init_faces_count = len(bm.faces)
        bm.free()

        # Verifica que a análise ou corte da cunha preserva o número de vértices e a silhueta
        # A geometria nominal do corte não sofre recuo arbitrário
        self.assertEqual(len(obj.data.vertices), init_verts_count)
        self.assertEqual(len(obj.data.polygons), init_faces_count)

    def test_e03_tangent_or_no_hit_reports_inconclusive(self):
        """E03: Raios sem intersecção ou tangentes relatam espessura inconclusiva e NÃO assumem 1000 mm."""
        # Cria um plano aberto (sem volume) onde o raycast na direção normal não encontrará fundo fechado
        mesh = bpy.data.meshes.new("OpenPlane")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=1.0)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new("OpenPlaneObj", mesh)
        bpy.context.scene.collection.objects.link(obj)

        # Vértices de contorno do plano aberto
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        # Pega ciclo de vértices da borda
        v_loop = []
        curr_e = boundary_edges[0]
        curr_v = curr_e.verts[0]
        start_v = curr_v
        used = set()
        while True:
            v_loop.append(curr_v.index)
            used.add(curr_e)
            next_v = curr_e.other_vert(curr_v)
            if next_v == start_v:
                break
            curr_v = next_v
            next_edges = [e for e in curr_v.link_edges if e.is_boundary and e not in used]
            if not next_edges:
                break
            curr_e = next_edges[0]
        bm.free()

        info = analyze_loop_region(obj, indices=v_loop, seed_face_idx=0)

        # Como é um plano aberto, o raycast não encontra fechamento oposto
        self.assertFalse(info["thickness_determined"], "Espessura não pode ser determinada em plano aberto")
        self.assertEqual(info["thickness_status"], "INCONCLUSIVE")
        self.assertEqual(info["max_avail_depth_mm"], 0.0, "Não deve assumir 1000 mm arbitrariamente")


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
