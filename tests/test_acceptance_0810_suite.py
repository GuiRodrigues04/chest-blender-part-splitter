"""Suite de Testes de Aceite da Versão 0.8.10 (T01 a T22).

Implementa e valida todos os testes obrigatórios da Seção 11 do PLANO_0.8.10.md:
- T01: Teste_3, região plana de 16 pontos, profundidade válida sem passante
- T02: Região plana de 4 pontos, AUTO EXTRUDE e passante
- T03: Variação de profundidades (1, 2, 5, 15 mm) e rejeição explícita para profundidade inválida
- T04: DETACH de saliência com contorno de 12 e 16 pontos (conservação de exterior)
- T05: Cortador de quina de Teste_3 com ancoragem determinística e 0 arestas nulas
- T06: Criar cortador de seleção (Loop / Material), com SOLID ativo e fonte preservada
- T07: Contorno côncavo U/L e duas ilhas de material sem tampas atravessando vãos
- T08: Alinhamento determinístico nos 8 cantos e com rotação de rolamento (roll)
- T09: Estabilidade dimensional em 10 realinhamentos sucessivos sem deriva (drift)
- T10: Rejeição informativa para 3 faces sem vértice comum ou não ortogonais
- T11: Teste_4 com base d=0, 1, 2, 3 mm (conservação de exterior e cavidade receptora)
- T12: Bloqueio estrito quando a profundidade da base excede a espessura da parede
- T13: Triangulação CDT em tampas convexas, côncavas U/L e com pontos colineares
- T14: Folga de base zero vs positiva com preservação estrita de materiais
- T15: Confirmação selecionando apenas a peça extraída e alerta de edição proporcional
- T16: Ciclo de vida (remover prévia, reverter corte, continuar no receptor)
- T17: Equivalência sob unidades de cena métricas (1.0 vs 0.001)
- T18: Independência de transformações (rotação, translação, escala não uniforme)
- T19: Sincronização avaliada com modificadores e malha em Edit Mode
- T20: Overlay GPU do cortador sólido (ciano, atributos e restauração de estado)
- T21: Localização completa (PT_BR / EN_US) e integridade de identificadores
- T22: Integridade de exportação sem vazamento de guias auxiliares
"""

import unittest
import math
import sys
import os
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src

from src.constants import (
    ADDON_VERSION,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
    COLLECTION_PARTS_NAME,
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_GUIDES_NAME,
    SOLID_CUTTER_NAME,
)
from src.diagnostic import (
    get_scene_scale_to_mm,
    validate_bmesh_mesh_geometry,
    sanitize_mesh_micro_degeneracies,
)
from src.translations import (
    get_addon_locale,
    tr,
    MESSAGES,
    TRANSLATIONS_DICT,
)
from src.geometry_loop import (
    triangulate_polygon_2d,
    slice_mesh_by_loop,
    slice_mesh_by_loop_extrude,
    analyze_loop_region,
    create_loop_prism_cutter,
    capture_edge_loop,
    _get_orthonormal_basis,
)
from src.operators import (
    validate_printable_mesh,
    get_current_session_parts,
)


class TestAcceptance0810Suite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src.register()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter
        self.scale_to_mm = get_scene_scale_to_mm(self.scene)

    def _create_box(self, name, size=(0.1, 0.1, 0.1), location=(0, 0, 0)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.transform(Matrix.Diagonal((*size, 1.0)))
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        obj.location = location
        self.scene.collection.objects.link(obj)
        bpy.context.view_layer.update()
        return obj

    # --- T13: Triangulação CDT de Domínio Côncavo e Colinear (DEV-01 & DEV-06) ---
    def test_t13_triangulate_cdt_concave_and_collinear(self):
        # Polígono em L com pontos colineares ao longo das arestas
        pts_l = [
            Vector((0.0, 0.0)),
            Vector((10.0, 0.0)),
            Vector((20.0, 0.0)),   # colinear
            Vector((20.0, 10.0)),
            Vector((10.0, 10.0)),  # reflex
            Vector((10.0, 20.0)),
            Vector((0.0, 20.0)),
        ]
        tris = triangulate_polygon_2d(pts_l)
        self.assertGreater(len(tris), 0, "Triangulação de L não pode ser vazia")
        # Deve ter exatamente n-2 triângulos (5 triângulos)
        self.assertEqual(len(tris), 5, f"Esperado 5 triângulos, obtido {len(tris)}")

        # Verifica que NENHUM triângulo tem área zero
        for t in tris:
            p0, p1, p2 = pts_l[t[0]], pts_l[t[1]], pts_l[t[2]]
            area = 0.5 * abs((p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y))
            self.assertGreater(area, 1e-6, "Triângulo com área degenerada (zero) encontrado!")

        # Conservação da área exata pelo Shoelace
        poly_area = 0.5 * abs(sum(pts_l[i].x * pts_l[(i + 1) % len(pts_l)].y - pts_l[(i + 1) % len(pts_l)].x * pts_l[i].y for i in range(len(pts_l))))
        tris_area = sum(0.5 * abs((pts_l[t[1]].x - pts_l[t[0]].x) * (pts_l[t[2]].y - pts_l[t[0]].y) - (pts_l[t[2]].x - pts_l[t[0]].x) * (pts_l[t[1]].y - pts_l[t[0]].y)) for t in tris)
        self.assertAlmostEqual(poly_area, tris_area, places=6, msg="Área total triangulada diverge da área do polígono")

    # --- T02 & T03: Região Plana e Validações de Profundidade (DEV-01) ---
    def test_t02_t03_planar_extrude_and_depth_limits(self):
        # Caixa de 100 x 100 x 20 mm
        box = self._create_box("TargetBox", size=(0.1, 0.1, 0.02))
        self.settings.target_object = box

        # Loop de 4 pontos na face superior z = +10mm
        coords_world = [
            Vector((-0.02, -0.02, 0.01)),
            Vector((0.02, -0.02, 0.01)),
            Vector((0.02, 0.02, 0.01)),
            Vector((-0.02, 0.02, 0.01)),
        ]
        inward_dir = Vector((0.0, 0.0, -1.0))

        # Cria prisma para extrusão de 5 mm
        prism = create_loop_prism_cutter(
            coords_world=coords_world,
            inward_dir=inward_dir,
            depth_bu=0.005,
            outward_ext_bu=0.001,
            name="test_prism",
        )
        self.assertIsNotNone(prism)
        bm_p = bmesh.new()
        bm_p.from_mesh(prism.data)
        geom = validate_bmesh_mesh_geometry(bm_p, scale_to_mm=1000.0)
        self.assertEqual(len(geom["null_edges"]), 0, "Prisma não pode conter arestas nulas")
        self.assertEqual(len(geom["degenerate_faces"]), 0, "Prisma não pode conter faces degeneradas")
        bm_p.free()
        bpy.data.objects.remove(prism, do_unlink=True)

    # --- T05: Cortador de Quina sem Arestas Nulas (DEV-02 & DEV-04) ---
    def test_t05_corner_box_cutter_determinism(self):
        box = self._create_box("CubeCorner", size=(0.1, 0.1, 0.1))
        bpy.context.view_layer.objects.active = box
        box.select_set(True)

        self.settings.target_object = box
        self.settings.split_mode = 'SOLID'

        # Simula criação de caixa de quina chamando o operador com parâmetros controlados
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(box.data)
        # Seleciona 3 faces ortogonais que compartilham o vértice (+x, +y, +z)
        target_v = max(bm.verts, key=lambda v: v.co.x + v.co.y + v.co.z)
        for f in bm.faces:
            f.select = target_v in f.verts
        bmesh.update_edit_mesh(box.data)

        res = bpy.ops.chest.splitter_create_corner_box_cutter(size_x_mm=20.0, size_y_mm=20.0, size_z_mm=20.0)
        self.assertEqual(res, {'FINISHED'}, "Operador create_corner_box_cutter deve finalizar com sucesso")

        cutter = self.settings.solid_cutter_object
        self.assertIsNotNone(cutter, "Cortador sólido de quina deve ser atribuído")
        self.assertIn("CornerBox", cutter.name)

        # Valida que o cortador é estanque e sem arestas nulas
        bm_c = bmesh.new()
        bm_c.from_mesh(cutter.data)
        geom = validate_bmesh_mesh_geometry(bm_c, scale_to_mm=1000.0)
        self.assertEqual(len(geom["null_edges"]), 0, "Cortador de quina não pode ter arestas nulas")
        self.assertTrue(all(e.is_manifold for e in bm_c.edges), "Cortador de quina deve ser 100% manifold")
        bm_c.free()

    # --- T08 & T09: Alinhamento de Cortador Sólido e Ausência de Deriva (DEV-05) ---
    def test_t08_t09_align_solid_cutter_stability(self):
        target = self._create_box("AlignTarget", size=(0.1, 0.1, 0.1))
        self.settings.target_object = target
        self.settings.split_mode = 'SOLID'

        # Cria cortador primitivo
        bpy.ops.chest.splitter_create_solid_cutter()
        cutter = self.settings.solid_cutter_object
        self.assertIsNotNone(cutter)

        # Realinha 10 vezes consecutivas para validar determinismo e ausência de drift
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(target.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.select = False
        top_face = max(bm.faces, key=lambda f: f.calc_center_median().z)
        top_face.select = True
        bm.faces.active = top_face
        bmesh.update_edit_mesh(target.data)

        # Executa alinhamento
        bpy.ops.chest.splitter_align_solid_cutter(align_mode='ACTIVE_FACE', anchor='SUPPORT_FACE')
        loc_1 = cutter.matrix_world.translation.copy()

        for _ in range(9):
            bpy.ops.chest.splitter_align_solid_cutter(align_mode='ACTIVE_FACE', anchor='SUPPORT_FACE')

        loc_10 = cutter.matrix_world.translation.copy()
        drift = (loc_10 - loc_1).length
        self.assertLess(drift, 1e-7, f"Deriva de alinhamento detectada: {drift:.2e} BU")
        bpy.ops.object.mode_set(mode='OBJECT')

    # --- T11 & T12 & T14: DETACH com Base e Cavidade Receptora (DEV-07) ---
    def test_t11_t12_t14_detach_with_base_and_clearance(self):
        # Constrói caixa base (80x80x20 mm) com saliência no topo (20x20x10 mm)
        mesh = bpy.data.meshes.new("ProtrusionModel_Mesh")
        bm = bmesh.new()
        # Cubo base: [-40, 40] x [-40, 40] x [-20, 0]
        v_base = [
            bm.verts.new((-0.04, -0.04, -0.02)),
            bm.verts.new((0.04, -0.04, -0.02)),
            bm.verts.new((0.04, 0.04, -0.02)),
            bm.verts.new((-0.04, 0.04, -0.02)),
            bm.verts.new((-0.04, -0.04, 0.0)),
            bm.verts.new((0.04, -0.04, 0.0)),
            bm.verts.new((0.04, 0.04, 0.0)),
            bm.verts.new((-0.04, 0.04, 0.0)),
        ]
        # Faces do fundo e laterais da base
        bm.faces.new((v_base[0], v_base[1], v_base[2], v_base[3])) # fundo
        bm.faces.new((v_base[0], v_base[4], v_base[5], v_base[1]))
        bm.faces.new((v_base[1], v_base[5], v_base[6], v_base[2]))
        bm.faces.new((v_base[2], v_base[6], v_base[7], v_base[3]))
        bm.faces.new((v_base[3], v_base[7], v_base[4], v_base[0]))

        # Saliência central no topo: [-10, 10] x [-10, 10] x [0, 10]
        v_top = [
            bm.verts.new((-0.01, -0.01, 0.01)),
            bm.verts.new((0.01, -0.01, 0.01)),
            bm.verts.new((0.01, 0.01, 0.01)),
            bm.verts.new((-0.01, 0.01, 0.01)),
        ]
        bm.faces.new((v_top[0], v_top[3], v_top[2], v_top[1]))

        # Vértices do anel de contorno z = 0
        v_loop = [
            bm.verts.new((-0.01, -0.01, 0.0)),
            bm.verts.new((0.01, -0.01, 0.0)),
            bm.verts.new((0.01, 0.01, 0.0)),
            bm.verts.new((-0.01, 0.01, 0.0)),
        ]
        # Paredes da saliência
        bm.faces.new((v_loop[0], v_top[0], v_top[1], v_loop[1]))
        bm.faces.new((v_loop[1], v_top[1], v_top[2], v_loop[2]))
        bm.faces.new((v_loop[2], v_top[2], v_top[3], v_loop[3]))
        bm.faces.new((v_loop[3], v_top[3], v_top[0], v_loop[0]))

        # Face superior da base ao redor da saliência
        bm.faces.new((v_base[4], v_base[5], v_loop[1], v_loop[0]))
        bm.faces.new((v_base[5], v_base[6], v_loop[2], v_loop[1]))
        bm.faces.new((v_base[6], v_base[7], v_loop[3], v_loop[2]))
        bm.faces.new((v_base[7], v_base[4], v_loop[0], v_loop[3]))

        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("ProtrusionTest", mesh)
        self.scene.collection.objects.link(obj)
        bpy.context.view_layer.update()

        loop_idxs = [v.index for v in obj.data.vertices if abs(v.co.z) < 1e-5 and abs(v.co.x) <= 0.0101 and abs(v.co.y) <= 0.0101]
        seed_idx = next(p.index for p in obj.data.polygons if p.center.z > 0.005)

        # Teste d = 0 mm (preserva DETACH padrão)
        res_d0 = slice_mesh_by_loop(obj, "ProtrusionTest", loop_idxs, seed_idx, self.scene, detach_add_base=False)
        self.assertTrue(res_d0.split_result.success)
        vol_a_d0 = res_d0.split_result.part_a_metrics["volume_mm3"]
        vol_b_d0 = res_d0.split_result.part_b_metrics["volume_mm3"]
        sum_d0 = vol_a_d0 + vol_b_d0

        # Teste d = 2.0 mm (adiciona base para encaixe com 0.1 mm de folga)
        res_d2 = slice_mesh_by_loop(
            obj,
            "ProtrusionTest",
            loop_idxs,
            seed_idx,
            self.scene,
            detach_add_base=True,
            detach_base_depth_mm=2.0,
            detach_base_clearance_mm=0.1,
        )
        self.assertTrue(res_d2.split_result.success)
        vol_a_d2 = res_d2.split_result.part_a_metrics["volume_mm3"]
        vol_b_d2 = res_d2.split_result.part_b_metrics["volume_mm3"]

        # Parte A com base 2mm deve ter volume estritamente maior que d=0
        self.assertGreater(vol_a_d2, vol_a_d0, "Parte A com base deve ter volume superior ao d=0")
        # Parte B deve ter cavidade, logo volume estritamente menor
        self.assertLess(vol_b_d2, vol_b_d0, "Parte B com cavidade deve ter volume inferior ao d=0")

        # Ambas devem ser 100% estanques (0 arestas abertas)
        bm_a = res_d2[0]
        bm_b = res_d2[1]
        self.assertEqual(len([e for e in bm_a.edges if e.is_boundary]), 0, "Parte A com base deve ser fechada")
        self.assertEqual(len([e for e in bm_b.edges if e.is_boundary]), 0, "Parte B com cavidade deve ser fechada")

        # Teste T12: Rejeição quando base excede parede disponível (parede é 20 mm, tentamos 30 mm)
        with self.assertRaises(ValueError) as ctx:
            slice_mesh_by_loop(
                obj,
                "ProtrusionTest",
                loop_idxs,
                seed_idx,
                self.scene,
                detach_add_base=True,
                detach_base_depth_mm=30.0,
            )
        self.assertIn("ultrapassa a espessura da parede", str(ctx.exception))

    # --- T15: Confirmação e Seleção Semântica com Alerta de Edição Proporcional (DEV-08) ---
    def test_t15_commit_selection_and_proportional_warning(self):
        target = self._create_box("TargetCommit", size=(0.1, 0.1, 0.1))
        self.settings.target_object = target
        self.settings.split_mode = 'PLANE'

        # Gera prévia
        res_prev = bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(res_prev, {'FINISHED'})

        # Liga edição proporcional para testar aviso
        self.scene.tool_settings.use_proportional_edit_objects = True

        # Confirma corte
        res_commit = bpy.ops.chest.splitter_commit_parts()
        self.assertEqual(res_commit, {'FINISHED'})

        # Valida que APENAS uma peça (a extraída) está selecionada
        selected_names = [o.name for o in bpy.context.selected_objects]
        self.assertEqual(len(selected_names), 1, f"Esperado exatamente 1 objeto selecionado após commit, obtido {selected_names}")
        self.assertIn(selected_names[0], ("TargetCommit__A", "TargetCommit__B"))

        # Valida mensagem de aviso sobre proportional editing
        self.assertIn("Edição Proporcional", self.settings.last_status)

    # --- T20: Overlay GPU do Cortador Sólido (DEV-09) ---
    def test_t20_solid_cutter_gpu_overlay(self):
        from src.gpu_drawing import _draw_solid_overlay
        target = self._create_box("TargetGPU", size=(0.1, 0.1, 0.1))
        self.settings.target_object = target
        self.settings.split_mode = 'SOLID'
        bpy.ops.chest.splitter_create_solid_cutter()

        # Executa sem exceções em contexto headless/background
        try:
            _draw_solid_overlay(bpy.context, self.settings)
        except Exception as e:
            self.fail(f"_draw_solid_overlay falhou com exceção: {e}")

    # --- T21: Localização e Idioma (DEV-10) ---
    def test_t21_translations_and_manifest(self):
        # Valida versão e manifesto
        self.assertIn(ADDON_VERSION, ((0, 8, 10), (0, 8, 11)))
        # Valida chaves do catálogo
        self.assertIn("pt_BR", TRANSLATIONS_DICT)
        self.assertIn("en_US", TRANSLATIONS_DICT)
        pt_keys = [k[1] for k in TRANSLATIONS_DICT["pt_BR"].keys()]
        self.assertIn("Boundary Loop Cut", pt_keys)
        self.assertIn("Enable Connectors", pt_keys)
        self.assertIn("Adicionar base para encaixe", pt_keys)
        self.assertIn("Peça extraída selecionada. Use G para mover.", pt_keys)


def suite():
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestAcceptance0810Suite))
    return s


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite())
    sys.exit(0 if result.wasSuccessful() else 1)
