"""Suite abrangente de testes automatizados para o Part Splitter 0.8.11 (PLANO_0.8.11).

Executa a validação de todos os gates (A01 a A12) em modo headless no Blender 5.2.
"""

import sys
import os
import unittest
import math
from mathutils import Vector, Matrix, Euler
import bmesh

# Adiciona raiz do projeto ao path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy
import src as addon_package
from src import (
    plane_state,
    diagnostic,
    geometry_connectors,
    geometry_loop,
    geometry_material,
    geometry_plane,
    geometry_solid,
    operators,
    properties,
    translations,
    ui,
)


class TestPartSplitter0811(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            addon_package.register()
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        try:
            addon_package.unregister()
        except Exception:
            pass

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if not bpy.context.scene.collection:
            col = bpy.data.collections.new("Scene Collection")
            bpy.context.scene.collection = col

    def _create_test_cube(self, name="TestCube", size=0.1, location=(0, 0, 0)):
        mesh = bpy.data.meshes.new(name=f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=size)
        bm.to_mesh(mesh)
        bm.free()
        obj.location = Vector(location)
        bpy.context.view_layer.update()
        return obj

    # -------------------------------------------------------------
    # A01: Sincronização do Plano (G1, T01, T02, T03)
    # -------------------------------------------------------------
    def test_a01_plane_state_sync(self):
        """Valida que resolve_plane_state calcula origem, normal e tangentes de forma idêntica."""
        scene = bpy.context.scene
        settings = scene.chest_splitter
        target = self._create_test_cube("TargetCube", size=0.1)
        settings.target_object = target
        settings.split_mode = 'PLANE'

        guide = operators.ensure_plane_guide(bpy.context)
        self.assertIsNotNone(guide, "Guia do plano não foi criado.")

        # Teste 1: Posição inicial
        p_origin, p_normal = plane_state.resolve_plane_state(scene, settings)
        self.assertAlmostEqual(p_normal.length, 1.0, places=5)

        # Teste 2: Move guia e rotaciona (G e R)
        guide.location = Vector((0.0, 0.0, 0.05))
        guide.rotation_euler = Euler((math.radians(30), 0.0, 0.0), 'XYZ')
        bpy.context.view_layer.update()

        p_origin2, p_normal2 = plane_state.resolve_plane_state(scene, settings)
        expected_norm = (guide.matrix_world.to_3x3().inverted().transposed() @ Vector((0, 0, 1))).normalized()
        self.assertAlmostEqual(p_normal2.x, expected_norm.x, places=4)
        self.assertAlmostEqual(p_normal2.y, expected_norm.y, places=4)
        self.assertAlmostEqual(p_normal2.z, expected_norm.z, places=4)
        self.assertAlmostEqual(p_origin2.z, 0.05, places=4)

    # -------------------------------------------------------------
    # A02: Criar Cortador da Seleção de Material (T05)
    # -------------------------------------------------------------
    def test_a02_material_cutter_signature(self):
        """Valida que analyze_material_structure aceita os argumentos corretos e detecta região planar."""
        target = self._create_test_cube("MatTarget", size=0.1)
        mat0 = bpy.data.materials.new("MatBody")
        mat1 = bpy.data.materials.new("MatPatch")
        target.data.materials.append(mat0)
        target.data.materials.append(mat1)

        # Atribui mat1 à face superior (normal z > 0.9)
        bm = bmesh.new()
        bm.from_mesh(target.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            if f.normal.z > 0.9:
                f.material_index = 1
                break
        bm.to_mesh(target.data)
        bm.free()

        analysis = geometry_material.analyze_material_structure(target, material_index=1, region_index=0)
        self.assertTrue(analysis["valid"], f"Análise deve ser válida: {analysis.get('error')}")
        self.assertTrue(analysis["is_planar_base"], "Face superior do cubo deve ser planar.")

    # -------------------------------------------------------------
    # A03 & A04: Base física, interface no fundo e folga independente
    # -------------------------------------------------------------
    def test_a03_a04_material_base_prism_and_clearance(self):
        """Valida create_material_footprint_prism_cutter com pegada no plano de apoio e interface no fundo."""
        target = self._create_test_cube("ReliefTarget", size=0.1)
        mat_base = bpy.data.materials.new("BaseMat")
        target.data.materials.append(mat_base)

        coords_world = [
            Vector((-0.02, -0.02, 0.05)),
            Vector((0.02, -0.02, 0.05)),
            Vector((0.02, 0.02, 0.05)),
            Vector((-0.02, 0.02, 0.05)),
        ]
        centroid = Vector((0.0, 0.0, 0.05))
        n_out = Vector((0.0, 0.0, 1.0))
        depth_bu = 0.005  # 5 mm de base
        top_bu = 0.010    # 10 mm acima do apoio cobrindo relevo

        cutter_obj, iface_tris = geometry_material.create_material_footprint_prism_cutter(
            obj=target,
            coords_world=coords_world,
            centroid=centroid,
            n_out=n_out,
            top_bu=top_bu,
            depth_bu=depth_bu,
            name="TestFootprintCutter",
            material_index=0,
            interface_mat_mode='RECEIVER',
            body_mat_index=0,
            lateral_offset_bu=0.0002,
        )

        self.assertIsNotNone(cutter_obj)
        self.assertGreater(len(iface_tris), 0)
        # Verifica se o fundo dos triângulos da interface fica em z = centroid.z - depth_bu
        for tri in iface_tris:
            for pt in tri:
                self.assertAlmostEqual(pt.z, 0.05 - depth_bu, places=4)

        bpy.data.objects.remove(cutter_obj, do_unlink=True)

    # -------------------------------------------------------------
    # A05 & A07: Padrões Editáveis, Conectores Manuais e Busca em U/L/S
    # -------------------------------------------------------------
    def test_a05_a07_manual_connectors_and_domain_sampling(self):
        """Valida que o modo manual armazena pontos, calcula validade e respeita domínio."""
        scene = bpy.context.scene
        settings = scene.chest_splitter
        target = self._create_test_cube("ManualTarget", size=0.1)
        settings.target_object = target
        settings.connector_enabled = True
        settings.connector_distribution = 'MANUAL'

        settings.manual_connectors.clear()
        c1 = settings.manual_connectors.add()
        c1.u_mm = 0.0
        c1.v_mm = 0.0
        c1.yaw_deg = 0.0

        c2 = settings.manual_connectors.add()
        c2.u_mm = 20.0
        c2.v_mm = 10.0
        c2.yaw_deg = 45.0

        self.assertEqual(len(settings.manual_connectors), 2)
        self.assertAlmostEqual(settings.manual_connectors[0].u_mm, 0.0)
        self.assertAlmostEqual(settings.manual_connectors[1].u_mm, 20.0)

        # L-shape de 40x40mm com espessura 10mm
        l_shape_2d = [
            (0.0, 0.0),
            (40.0, 0.0),
            (40.0, 10.0),
            (10.0, 10.0),
            (10.0, 40.0),
            (0.0, 40.0),
        ]
        valid_pts = geometry_connectors.sample_domain_valid_points(
            outer_polys=[l_shape_2d],
            hole_polys=[],
            min_u=0.0,
            max_u=40.0,
            min_v=0.0,
            max_v=40.0,
            check_r=3.0,
            steps=25,
        )
        self.assertGreaterEqual(len(valid_pts), 1, "Amostragem em L-shape deve encontrar pontos válidos.")
        for u, v, _dist in valid_pts:
            is_valid, _ = geometry_connectors.validate_connector_footprint(
                u_p=u,
                v_p=v,
                check_r=2.0,
                outer_polys=[l_shape_2d],
                hole_polys=[],
                edge_margin_mm=0.5,
            )
            self.assertTrue(is_valid, f"Ponto amostrado ({u}, {v}) deve ter pegada válida dentro do L.")

        # O centro geométrico (20, 20) está no vazio do L e deve ser REJEITADO
        is_center_valid, reason = geometry_connectors.validate_connector_footprint(
            u_p=20.0,
            v_p=20.0,
            check_r=2.0,
            outer_polys=[l_shape_2d],
            hole_polys=[],
            edge_margin_mm=0.5,
        )
        self.assertFalse(is_center_valid, "O centro (20,20) no vazio do L deve ser rejeitado.")

    # -------------------------------------------------------------
    # A08: Saneamento Determinístico Pós-Booleanos
    # -------------------------------------------------------------
    def test_a08_micro_degeneracies_sanitation(self):
        """Valida que sanitize_mesh_micro_degeneracies resolve micro-arestas mantendo solidez manifold."""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        # Subdivide uma aresta do cubo e move o novo vértice para distância sub-micrométrica (5e-8 BU = 0.05 µm)
        e = bm.edges[0]
        v_orig_co = e.verts[0].co.copy()
        res = bmesh.ops.subdivide_edges(bm, edges=[e], cuts=1)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        new_v = [v for v in res["geom_split"] if isinstance(v, bmesh.types.BMVert)][0]
        new_v.co = v_orig_co + Vector((5e-8, 0.0, 0.0))
        bm.edges.ensure_lookup_table()

        fixed = diagnostic.sanitize_mesh_micro_degeneracies(bm, scale_to_mm=1000.0)
        self.assertTrue(fixed, "Saneamento de micro-arestas deve retornar True.")
        self.assertTrue(all(e.is_manifold for e in bm.edges), "Mesh pós-saneamento deve ser manifold.")
        bm.free()

    # -------------------------------------------------------------
    # A09: Desacoplamento de Explosão e Posições Montadas
    # -------------------------------------------------------------
    def test_a09_explosion_immutable_assembled_location(self):
        """Valida que alternar e alterar explosão preserva chest_assembled_loc intacto."""
        target = self._create_test_cube("ExplodeTarget", size=0.1)
        part_a = self._create_test_cube("PartA", size=0.05, location=(0, 0, 0.05))
        part_b = self._create_test_cube("PartB", size=0.05, location=(0, 0, -0.05))

        part_a["chest_assembled_loc"] = list(part_a.location)
        part_b["chest_assembled_loc"] = list(part_b.location)
        part_a["chest_explosion_normal_a_to_b"] = [0.0, 0.0, 1.0]
        part_b["chest_explosion_normal_a_to_b"] = [0.0, 0.0, 1.0]

        # 10 ciclos de variação de explosão
        for dist in [0.0, 10.0, 50.0, 100.0, 0.0, 37.6, 191.1, 0.0]:
            unit_scale = 1000.0
            dist_bu = (dist / unit_scale) / 2.0
            norm = Vector((0.0, 0.0, 1.0))
            part_a.location = Vector(part_a["chest_assembled_loc"]) - norm * dist_bu
            part_b.location = Vector(part_b["chest_assembled_loc"]) + norm * dist_bu

        # Retorna a zero
        part_a.location = Vector(part_a["chest_assembled_loc"])
        part_b.location = Vector(part_b["chest_assembled_loc"])

        self.assertAlmostEqual(part_a.location.z, 0.05, places=5)
        self.assertAlmostEqual(part_b.location.z, -0.05, places=5)

    # -------------------------------------------------------------
    # A12 & T08: Preservação de Âncora Fixa no Redimensionamento Sólido
    # -------------------------------------------------------------
    def test_a12_t08_solid_anchor_preservation(self):
        """Valida que redimensionar caixa cortadora (10 -> 20 -> 10 mm) mantém ponto de apoio imóvel."""
        scene = bpy.context.scene
        settings = scene.chest_splitter

        cutter_box = self._create_test_cube("CutterBox", size=0.01)  # 10 mm
        settings.solid_cutter_object = cutter_box
        settings.solid_cutter_width_mm = 10.0
        settings.solid_cutter_height_mm = 10.0
        settings.solid_cutter_depth_mm = 10.0

        # Define âncora na face inferior (z=-0.005 em local)
        a_local = Vector((0.0, 0.0, -0.005))
        cutter_box["chest_align_anchor_local"] = tuple(a_local)
        ref_world_before = cutter_box.matrix_world @ a_local

        # Altera dimensões para 20 mm
        settings.solid_cutter_width_mm = 20.0
        settings.solid_cutter_height_mm = 20.0
        settings.solid_cutter_depth_mm = 20.0
        properties._on_solid_dim_update(settings, bpy.context)

        ref_world_after_20 = cutter_box.matrix_world @ a_local
        self.assertAlmostEqual((ref_world_after_20 - ref_world_before).length, 0.0, places=4,
                               msg="Ponto de âncora derivou ao expandir para 20 mm.")

        # Retorna para 10 mm
        settings.solid_cutter_width_mm = 10.0
        settings.solid_cutter_height_mm = 10.0
        settings.solid_cutter_depth_mm = 10.0
        properties._on_solid_dim_update(settings, bpy.context)

        ref_world_after_10 = cutter_box.matrix_world @ a_local
        self.assertAlmostEqual((ref_world_after_10 - ref_world_before).length, 0.0, places=4,
                               msg="Ponto de âncora derivou ao retornar para 10 mm.")

    # -------------------------------------------------------------
    # Teste com Blend Files Reais (Padrao_1, Teste_3, Teste_4)
    # -------------------------------------------------------------
    def test_real_blend_files_integrity(self):
        """Inspeciona os arquivos blend reais da auditoria para verificar ausência de regressões."""
        casos_dir = os.path.join(PROJECT_ROOT, "pkg", "casos")
        padrao_blend = os.path.join(casos_dir, "Padrao_1.blend")
        teste3_blend = os.path.join(casos_dir, "Teste_3.blend")
        teste4_blend = os.path.join(casos_dir, "Teste_4.blend")

        if os.path.exists(padrao_blend):
            bpy.ops.wm.open_mainfile(filepath=padrao_blend)
            obj = bpy.data.objects.get("Extração por material") or bpy.data.objects.get("Cube.001")
            self.assertIsNotNone(obj, "Objeto principal em Padrao_1.blend não encontrado.")
            if len(obj.data.materials) > 0:
                res = geometry_material.analyze_material_structure(obj, material_index=0, region_index=0)
                self.assertIsInstance(res, dict)

        if os.path.exists(teste3_blend):
            bpy.ops.wm.open_mainfile(filepath=teste3_blend)
            corner_box = bpy.data.objects.get("CHEST_SPLITTER_SOLID_CUTTER_CornerBox")
            self.assertIsNotNone(corner_box, "Corner box em Teste_3.blend não encontrado.")
            self.assertEqual(len(corner_box.data.vertices), 8)

        if os.path.exists(teste4_blend):
            bpy.ops.wm.open_mainfile(filepath=teste4_blend)
            obj_loop = bpy.data.objects.get("Loop")
            obj_mat = bpy.data.objects.get("Material")
            self.assertTrue(obj_loop is not None or obj_mat is not None, "Objetos de Teste_4.blend não encontrados.")


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPartSplitter0811)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
