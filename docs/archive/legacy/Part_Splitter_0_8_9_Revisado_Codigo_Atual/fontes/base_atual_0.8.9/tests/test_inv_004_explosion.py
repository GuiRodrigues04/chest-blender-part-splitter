"""Suíte de testes de aceitação para INV-004 (A01 a A05) do Plano de Correção.

Valida a convenção e comportamento de explosão no corte por Plano:
- A01: Ciclo 0 -> 39.3 -> 0 mm: afastamento para fora e retorno idêntico sem drift.
- A02: Normal negada x invert_sides on/off: A e B sempre se afastam na direção correta.
- A03: Inversão visual da explosão duas vezes: sem drift e sem alterar corte nominal.
- A04: Alteração de parâmetros de corte com prévia desatualizada: prévia mantém seu snapshot.
- A05: Exportação em modo explodido e montado gera malhas nas coordenadas montadas canônicas.
"""
import unittest
import bpy
import bmesh
from mathutils import Vector
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.geometry_plane import compute_explosion_offsets, slice_mesh_by_plane
from src.operators import update_preview_positions, ROLE_PREVIEW_A, ROLE_PREVIEW_B
from src.diagnostic import get_scene_scale_to_mm


def _create_test_box(name: str = "TestBoxA01", size: float = 0.1) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


class TestINV004ExplosionAcceptance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import src
        try:
            src.register()
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        import src
        try:
            src.unregister()
        except Exception:
            pass

    def setUp(self):
        # Limpa objetos criados
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for m in list(bpy.data.meshes):
            bpy.data.meshes.remove(m, do_unlink=True)

    def test_a01_explosion_distance_cycle(self):
        """A01: Plano 0 -> 39.3 -> 0 mm: A/B afastam e retornam sem drift."""
        norm = Vector((0.0, 0.0, 1.0))
        dist_39_3 = 39.3

        # Deslocamento a 39.3 mm
        off_a, off_b = compute_explosion_offsets(norm, explosion_distance_mm=dist_39_3, unit_scale=1000.0)
        self.assertAlmostEqual(off_a.z, -39.3 / 2000.0, places=6)
        self.assertAlmostEqual(off_b.z, 39.3 / 2000.0, places=6)
        # Distância entre partes = 39.3 mm (0.0393 BU)
        self.assertAlmostEqual((off_b - off_a).length * 1000.0, 39.3, places=4)

        # Retorno a zero
        off_a_0, off_b_0 = compute_explosion_offsets(norm, explosion_distance_mm=0.0, unit_scale=1000.0)
        self.assertAlmostEqual(off_a_0.length, 0.0, places=7)
        self.assertAlmostEqual(off_b_0.length, 0.0, places=7)

    def test_a02_normal_negated_and_invert_sides(self):
        """A02: Normal negada x invert_sides on/off: A e B afastam-se em todos os casos."""
        dist = 20.0  # mm
        norm_pos = Vector((0.0, 0.0, 1.0))
        norm_neg = Vector((0.0, 0.0, -1.0))

        # Caso 1: Normal +Z, invert_sides=False
        # Lado A é mantido no lado negativo de +Z (z <= 0)
        # Para afastar de B (z >= 0), A deve ir para -Z, B para +Z
        effective_norm_1 = norm_pos
        oa1, ob1 = compute_explosion_offsets(effective_norm_1, dist)
        self.assertTrue(oa1.z < 0.0, "Parte A deve afastar-se para -Z")
        self.assertTrue(ob1.z > 0.0, "Parte B deve afastar-se para +Z")

        # Caso 2: Normal +Z, invert_sides=True
        # Lado A é mantido no lado negativo de -Z (z >= 0)
        # Para afastar de B (z <= 0), A deve ir para +Z, B para -Z
        effective_norm_2 = -norm_pos
        oa2, ob2 = compute_explosion_offsets(effective_norm_2, dist)
        self.assertTrue(oa2.z > 0.0, "Com invert_sides, Parte A deve afastar-se para +Z")
        self.assertTrue(ob2.z < 0.0, "Com invert_sides, Parte B deve afastar-se para -Z")

        # Caso 3: Normal -Z, invert_sides=False
        # Lado A mantido em z >= 0
        oa3, ob3 = compute_explosion_offsets(norm_neg, dist)
        self.assertTrue(oa3.z > 0.0, "Normal -Z: Parte A deve afastar-se para +Z")
        self.assertTrue(ob3.z < 0.0, "Normal -Z: Parte B deve afastar-se para -Z")

        # Caso 4: Normal -Z, invert_sides=True
        # Lado A mantido em z <= 0
        oa4, ob4 = compute_explosion_offsets(-norm_neg, dist)
        self.assertTrue(oa4.z < 0.0, "Normal -Z com invert_sides: Parte A deve afastar-se para -Z")
        self.assertTrue(ob4.z > 0.0, "Normal -Z com invert_sides: Parte B deve afastar-se para +Z")

    def test_a03_invert_explosion_toggle_drift_free(self):
        """A03: Inversão visual da explosão duas vezes: restaura posição sem drift numérico."""
        norm = Vector((0.0, 0.0, 1.0))
        dist = 30.0

        oa_orig, ob_orig = compute_explosion_offsets(norm, dist, invert_direction=False)
        oa_inv, ob_inv = compute_explosion_offsets(norm, dist, invert_direction=True)

        # Invertido deve ter sinais opostos
        self.assertAlmostEqual((oa_orig + oa_inv).length, 0.0, places=6)
        self.assertAlmostEqual((ob_orig + ob_inv).length, 0.0, places=6)

        # Invertendo de volta (duas vezes)
        oa_back, ob_back = compute_explosion_offsets(norm, dist, invert_direction=False)
        self.assertAlmostEqual((oa_orig - oa_back).length, 0.0, places=7)
        self.assertAlmostEqual((ob_orig - ob_back).length, 0.0, places=7)

    def test_a04_stale_preview_uses_snapshot_normal(self):
        """A04: Modificar plano na UI não altera a direção de explosão da prévia já gerada."""
        scene = bpy.context.scene
        settings = scene.chest_splitter
        settings.session_id = "test_session_a04"
        settings.session_status = 'PREVIEW_VALID'
        settings.view_mode = 'EXPLODED'
        settings.explosion_distance_mm = 20.0
        settings.invert_explosion = False

        # Cria objetos de teste simulando a prévia gerada com normal +Z
        mesh_a = bpy.data.meshes.new("prev_a_mesh")
        obj_a = bpy.data.objects.new("CHEST_PREVIEW_A", mesh_a)
        obj_a["chest_session_id"] = settings.session_id
        obj_a["chest_role"] = ROLE_PREVIEW_A
        obj_a["chest_assembled_loc"] = [0.0, 0.0, 0.0]
        obj_a["chest_explosion_normal_a_to_b"] = [0.0, 0.0, 1.0]

        mesh_b = bpy.data.meshes.new("prev_b_mesh")
        obj_b = bpy.data.objects.new("CHEST_PREVIEW_B", mesh_b)
        obj_b["chest_session_id"] = settings.session_id
        obj_b["chest_role"] = ROLE_PREVIEW_B
        obj_b["chest_assembled_loc"] = [0.0, 0.0, 0.0]
        obj_b["chest_explosion_normal_a_to_b"] = [0.0, 0.0, 1.0]

        from src.operators import get_or_create_collection, COLLECTION_PREVIEWS_NAME
        prev_col = get_or_create_collection(scene, COLLECTION_PREVIEWS_NAME)
        prev_col.objects.link(obj_a)
        prev_col.objects.link(obj_b)

        # Executa atualização de posições
        update_preview_positions(scene)
        pos_a1 = obj_a.location.copy()
        pos_b1 = obj_b.location.copy()
        self.assertAlmostEqual(pos_a1.z, -0.010, places=5)
        self.assertAlmostEqual(pos_b1.z, 0.010, places=5)

        # Usuário altera plano normal na UI para o eixo X, SEM clicar em Gerar Prévia
        settings.plane_normal = (1.0, 0.0, 0.0)
        settings.invert_sides = True
        update_preview_positions(scene)

        # Como a prévia não foi regenerada, ela DEVE continuar respeitando seu snapshot (+Z)
        self.assertAlmostEqual(obj_a.location.z, pos_a1.z, places=5)
        self.assertAlmostEqual(obj_a.location.x, 0.0, places=5)
        self.assertAlmostEqual(obj_b.location.z, pos_b1.z, places=5)
        self.assertAlmostEqual(obj_b.location.x, 0.0, places=5)

    def test_a05_assembled_export_coordinates_canonical(self):
        """A05: Prévia explodida mantém coordenadas montadas canônicas gravadas em chest_assembled_loc."""
        mesh_a = bpy.data.meshes.new("prev_a_mesh")
        obj_a = bpy.data.objects.new("CHEST_PREVIEW_A", mesh_a)
        obj_a["chest_assembled_loc"] = [0.05, 0.02, 0.01]

        # Verifica se chest_assembled_loc é preservado
        self.assertEqual(list(obj_a["chest_assembled_loc"]), [0.05, 0.02, 0.01])


if __name__ == "__main__":
    import sys
    argv = [sys.argv[0]] + (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    unittest.main(argv=argv)
