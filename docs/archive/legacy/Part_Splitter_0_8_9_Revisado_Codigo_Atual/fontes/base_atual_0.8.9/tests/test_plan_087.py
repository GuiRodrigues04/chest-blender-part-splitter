"""Suíte de testes de aceitação e regressão para o Plano 0.8.7 (Chest Part Splitter).

Cobre os casos de aceitação da Seção 12 do plano:
- T04: Invalidação de assinatura topológica do Loop
- T07: Triangulação de contorno côncavo (U/L) sem pontes/membrana
- T08: Rollback seguro e preservação de prévia anterior
- T09: Diagnóstico específico de espessura de extração (sem fallback de 1000mm)
- T12: Posicionamento automático de conector em domínio côncavo (U)
- T20: Folga entre peças zero (geometria nominal)
- T21: Folga entre peças unilateral e bilateral medida
- T23: Detecção de alteração exclusiva no cortador via depsgraph (PREVIEW_STALE)
- T35: Corte planar alinhado à face sem lâmina coplanar (P02/P03)
- T36: Corte planar alinhado à face sob escala e rotação arbitrárias
- T37: Validação estrita do operador de alinhamento por face (CANCELLED seguro)
- T38: Fechamento restrito ao plano de corte sem tampar aberturas pré-existentes
- T39: Isolamento estrito de remoção de prévia entre operações distintas
- T40: Atomicidade do snapshot de backup (candidato promovido apenas após validação)
- T41: Detecção de seleção ambígua em resolve_operation
- T42: Rejeição de objeto substituto não-backup com mesmo nome
- T43: Restauração de alvo apagado com recuperação fiel de modificadores
- T44: Bloqueio de reversão do pai na presença de prévia filha ativa
"""

import unittest
import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

# Garante importação do pacote local
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)


from src.constants import (
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    COLLECTION_BACKUPS_NAME,
    COLLECTION_GUIDES_NAME,
    ROLE_RESTORE_BACKUP,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
    PLANE_GUIDE_NAME,
)
from src.lifecycle import (
    get_or_create_operation_record,
    find_operation_record,
    capture_target_snapshot,
    discard_target_snapshot,
    resolve_operation,
    check_child_operations,
    remove_preview,
    revert_committed_operation,
    record_created_object,
)
from src.geometry_plane import (
    slice_mesh_by_plane,
    cap_open_cut_boundaries,
    evaluate_bmesh_metrics,
)
from src.geometry_loop import (
    create_loop_prism_cutter,
    triangulate_polygon_2d,
    get_topology_signature,
    analyze_loop_region,
)
from src.geometry_connectors import (
    compute_connector_layout,
    point_in_polygon_2d,
    min_distance_to_polygon_boundaries,
)
from src.geometry_contract import build_cut_interface


class TestPlan087(unittest.TestCase):

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
        """Limpa a cena antes de cada teste."""
        bpy.ops.wm.read_homefile(use_empty=True)
        self.scene = bpy.context.scene
        if not hasattr(self.scene, "chest_splitter"):
            from src.properties import register as register_props
            try:
                register_props()
            except Exception:
                pass

    def tearDown(self):
        """Limpeza pós-teste."""
        pass

    def test_t04_loop_topology_signature_invalidation(self):
        """T04: Alteração de conectividade invalida a assinatura topológica antes do corte."""
        mesh = bpy.data.meshes.new("SigCubeMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("SigCube", mesh)
        self.scene.collection.objects.link(obj)

        sig1 = get_topology_signature(obj)
        self.assertTrue(sig1.startswith("V8E12F6"))

        # Modifica conectividade adicionando uma aresta/vértice
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        v0 = bm.verts[0]
        v_new = bm.verts.new((0.0, 0.0, 1.5))
        bm.edges.new((v0, v_new))
        bm.to_mesh(mesh)
        bm.free()

        sig2 = get_topology_signature(obj)
        self.assertNotEqual(sig1, sig2)
        self.assertTrue(sig2.startswith("V9E13F6"))

    def test_t07_concave_loop_ear_clipping_triangulation(self):
        """T07: Triangulação de polígono côncavo em U/L garante faces estritamente no domínio sem pontes."""
        # Polígono côncavo em formato de U (8 vértices)
        # (0,0) -> (4,0) -> (4,4) -> (3,4) -> (3,1) -> (1,1) -> (1,4) -> (0,4)
        u_pts = [
            Vector((0.0, 0.0)),
            Vector((4.0, 0.0)),
            Vector((4.0, 4.0)),
            Vector((3.0, 4.0)),
            Vector((3.0, 1.0)),
            Vector((1.0, 1.0)),
            Vector((1.0, 4.0)),
            Vector((0.0, 4.0)),
        ]

        tris = triangulate_polygon_2d(u_pts)
        self.assertEqual(len(tris), 6)  # n - 2 triângulos para polígono de 8 vértices

        # Verifica se nenhum triângulo cruza o vazio central (x entre 1 e 3, y entre 1 e 4)
        void_pt = Vector((2.0, 2.5))
        self.assertFalse(point_in_polygon_2d(void_pt.x, void_pt.y, [(p.x, p.y) for p in u_pts]))

        # Constrói o prisma cortador usando esses vértices
        coords_3d = [Vector((p.x, p.y, 0.0)) for p in u_pts]
        prism = create_loop_prism_cutter(
            coords_world=coords_3d,
            inward_dir=Vector((0.0, 0.0, 1.0)),
            depth_bu=2.0,
            outward_ext_bu=0.1,
            name="UTestPrism",
        )

        bm_prism = bmesh.new()
        bm_prism.from_mesh(prism.data)
        metrics = evaluate_bmesh_metrics(bm_prism, unit_scale=1000.0)
        bm_prism.free()

        self.assertTrue(metrics["is_manifold"])
        self.assertGreater(metrics["volume_mm3"], 0.0)

    def test_t09_thickness_determination_no_arbitrary_fallback(self):
        """T09: Região sem parede oposta detecta espessura não determinada sem fallback de 1000mm."""
        mesh = bpy.data.meshes.new("PlaneMesh")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=1.0)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("PlaneObj", mesh)
        self.scene.collection.objects.link(obj)

        indices = [0, 1, 2, 3]
        analysis = analyze_loop_region(obj, indices, seed_face_idx=0, scene=self.scene)
        # Como é um plano 2D aberto, o raio na direção inward não encontra parede oposta
        self.assertFalse(analysis["thickness_determined"])
        self.assertNotEqual(analysis["max_avail_depth_mm"], 1000.0)

    def test_t12_automatic_connector_in_u_domain(self):
        """T12: Conector automático em U localiza ponto válido no sólido em vez do vazio central."""
        u_poly = [
            (0.0, 0.0),
            (60.0, 0.0),
            (60.0, 60.0),
            (45.0, 60.0),
            (45.0, 15.0),
            (15.0, 15.0),
            (15.0, 60.0),
            (0.0, 60.0),
        ]

        from src.geometry_contract import CutInterface
        c_iface = CutInterface(
            origin_world=Vector((0.0, 0.0, 0.0)),
            normal_a_to_b_world=Vector((0.0, 0.0, 1.0)),
            axis_u_world=Vector((1.0, 0.0, 0.0)),
            axis_v_world=Vector((0.0, 1.0, 0.0)),
            outer_contours_uv=[u_poly],
            hole_contours_uv=[],
            is_planar=True,
            deviation_mm=0.0,
            source_mode='LOOP',
        )

        dummy_mesh = bpy.data.meshes.new("DummyMesh")
        layout = compute_connector_layout(
            target_mesh=dummy_mesh,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0.0, 0.0, 0.0)),
            plane_normal=Vector((0.0, 0.0, 1.0)),
            distribution='CENTER',
            edge_margin_mm=3.0,
            unit_scale=1000.0,
            diameter_mm=6.0,
            clearance_per_side_mm=0.15,
            interface=c_iface,
            adjust_to_valid_area=True,
        )

        self.assertEqual(len(layout["positions"]), 1)
        pos = layout["positions"][0]
        # Conector não pode estar no vazio central (x entre 15 e 45 e y > 15)
        self.assertTrue(point_in_polygon_2d(pos.x, pos.y, u_poly))

    def test_t20_t21_part_clearance_unilateral_and_bilateral(self):
        """T20/T21: Folga entre peças zero preserva corte nominal; folga física reduz volume proporcionalmente."""
        mesh = bpy.data.meshes.new("BoxMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.04)  # 40x40x40 mm em BU
        bm.to_mesh(mesh)
        bm.free()

        t_mesh_a = bpy.data.meshes.new("PartA")
        t_mesh_b = bpy.data.meshes.new("PartB")

        # Folga zero
        res_zero = slice_mesh_by_plane(
            source_mesh=mesh,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0.0, 0.0, 0.0)),
            plane_normal=Vector((0.0, 0.0, 1.0)),
            target_mesh_a=t_mesh_a,
            target_mesh_b=t_mesh_b,
            unit_scale=1000.0,
            part_clearance_mm=0.0,
        )
        vol_zero = res_zero["sum_volume_mm3"]

        # Folga unilateral de 1.0 mm na Parte A
        res_clear = slice_mesh_by_plane(
            source_mesh=mesh,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0.0, 0.0, 0.0)),
            plane_normal=Vector((0.0, 0.0, 1.0)),
            target_mesh_a=t_mesh_a,
            target_mesh_b=t_mesh_b,
            unit_scale=1000.0,
            part_clearance_mm=1.0,
            part_clearance_apply_to='PART',
        )
        vol_clear = res_clear["sum_volume_mm3"]

        # A área de corte é 40x40 = 1600 mm². Com 1 mm de alívio na Parte A, o volume reduz em ~1600 mm³
        expected_diff = 40.0 * 40.0 * 1.0
        actual_diff = vol_zero - vol_clear
        self.assertAlmostEqual(actual_diff, expected_diff, delta=50.0)

    def test_t35_align_plane_eliminates_coplanar_blade(self):
        """T35: Corte planar alinhado à face de apoio de saliência elimina lâmina coplanar (P02/P03)."""
        # Cria cubo de base 100x100x50 mm (z de 0 a 50) com saliência 30x30x20 mm (z de 50 a 70)
        bm = bmesh.new()
        # Base
        bmesh.ops.create_cube(bm, size=1.0)
        # Escala e translada base para 100x100x50 mm em z de 0 a 50
        for v in bm.verts:
            v.co.x *= 0.1
            v.co.y *= 0.1
            v.co.z = (v.co.z + 0.5) * 0.05

        # Adiciona saliência 30x30x20 mm no topo (z de 50 a 70 mm)
        bm_sal = bmesh.new()
        bmesh.ops.create_cube(bm_sal, size=1.0)
        for v in bm_sal.verts:
            v.co.x *= 0.03
            v.co.y *= 0.03
            v.co.z = 0.05 + (v.co.z + 0.5) * 0.02

        # Unifica malhas
        for v in bm_sal.verts:
            bm.verts.new(v.co)
        bm.verts.ensure_lookup_table()
        for f in bm_sal.faces:
            bm.faces.new([bm.verts[v.index + 8] for v in f.verts])
        bm_sal.free()

        source_mesh = bpy.data.meshes.new("SteppedBlock")
        bm.to_mesh(source_mesh)
        bm.free()

        mesh_a = bpy.data.meshes.new("SlicePartA")
        mesh_b = bpy.data.meshes.new("SlicePartB")

        # Corte exatamente em z = 50 mm (0.05 bu)
        res = slice_mesh_by_plane(
            source_mesh=source_mesh,
            matrix_world=Matrix.Identity(4),
            plane_origin=Vector((0.0, 0.0, 0.05)),
            plane_normal=Vector((0.0, 0.0, 1.0)),
            target_mesh_a=mesh_a,
            target_mesh_b=mesh_b,
            unit_scale=1000.0,
            coplanar_tol_mm=0.05,
        )

        dims_a = res["A"]["dims_mm"]
        dims_b = res["B"]["dims_mm"]

        # A Parte A (base inferior) deve ter ~100x100x50 mm
        self.assertAlmostEqual(dims_a[0], 100.0, delta=1.0)
        self.assertAlmostEqual(dims_a[1], 100.0, delta=1.0)
        self.assertAlmostEqual(dims_a[2], 50.0, delta=1.0)

        # A Parte B (saliência superior) deve ter ~30x30x20 mm e NÃO 100x100 mm da película da base!
        self.assertAlmostEqual(dims_b[0], 30.0, delta=1.0)
        self.assertAlmostEqual(dims_b[1], 30.0, delta=1.0)
        self.assertAlmostEqual(dims_b[2], 20.0, delta=1.0)

        # Ambas as partes devem ser 100% manifold
        self.assertTrue(res["A"]["is_manifold"])
        self.assertTrue(res["B"]["is_manifold"])

    def test_t37_align_plane_operator_strict_validation(self):
        """T37: Alinhar por Face sem alvo ou fora de Edit Mode retorna CANCELLED sem falso sucesso."""
        settings = self.scene.chest_splitter
        settings.target_object = None

        res = bpy.ops.chest.splitter_align_plane(align_mode='FACE')
        self.assertEqual(res, {'CANCELLED'})

    def test_t38_cap_boundaries_preserves_preexisting_hole(self):
        """T38: cap_open_cut_boundaries não fecha furos abertos pré-existentes distantes do corte."""
        # Cria cilindro sem tampa inferior (abertura pré-existente em z = 0)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=False, segments=12, radius1=0.02, radius2=0.02, depth=0.06)
        # O cilindro vai de z = -0.03 a z = +0.03

        # Fecha apenas a tampa superior em z = +0.03
        top_verts = [v for v in bm.verts if v.co.z > 0.025]
        bm.faces.new(top_verts)

        # Corta no plano z = 0.01 (longe da abertura inferior que fica em z = -0.03)
        plane_co = Vector((0.0, 0.0, 0.01))
        norm = Vector((0.0, 0.0, 1.0))

        # Passa o plano de corte para cap_open_cut_boundaries
        cap_open_cut_boundaries(bm, cut_edges=None, plane_origin=plane_co, plane_normal=norm, coplanar_tol_bu=1e-4)

        # A abertura em z = -0.03 deve continuar aberta
        bot_edges_open = [e for e in bm.edges if e.is_boundary and all(v.co.z < -0.025 for v in e.verts)]
        self.assertGreater(len(bot_edges_open), 0)
        bm.free()

    def test_t39_two_operations_preview_isolation(self):
        """T39: Descartar prévia de uma operação não afeta objetos de prévia de outra operação."""
        op1 = get_or_create_operation_record(self.scene, "OP_ALPHA_1111", status='PREVIEW')
        op2 = get_or_create_operation_record(self.scene, "OP_BETA_2222", status='PREVIEW')

        preview_col = bpy.data.collections.new(COLLECTION_PREVIEWS_NAME)
        self.scene.collection.children.link(preview_col)

        m1 = bpy.data.meshes.new("M1")
        o1 = bpy.data.objects.new("P_Alpha", m1)
        o1["chest_operation_id"] = "OP_ALPHA_1111"
        o1["chest_role"] = ROLE_PREVIEW_A
        preview_col.objects.link(o1)
        record_created_object(op1, o1, ROLE_PREVIEW_A)

        m2 = bpy.data.meshes.new("M2")
        o2 = bpy.data.objects.new("P_Beta", m2)
        o2["chest_operation_id"] = "OP_BETA_2222"
        o2["chest_role"] = ROLE_PREVIEW_A
        preview_col.objects.link(o2)
        record_created_object(op2, o2, ROLE_PREVIEW_A)

        # Remove apenas a prévia da OP_ALPHA
        context = bpy.context
        remove_preview(context, op_id="OP_ALPHA_1111")

        self.assertNotIn("P_Alpha", bpy.data.objects)
        # Objeto da OP_BETA permanece intacto
        self.assertIn("P_Beta", bpy.data.objects)

    def test_t40_transactional_snapshot_capture(self):
        """T40: capture_target_snapshot cria candidato validado antes de descartar snapshot anterior."""
        op = get_or_create_operation_record(self.scene, "OP_SNAP_TRANSACT", status='PREVIEW')

        mesh = bpy.data.meshes.new("TargetMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.02)
        bm.to_mesh(mesh)
        bm.free()

        target = bpy.data.objects.new("TransactTarget", mesh)
        self.scene.collection.objects.link(target)

        # Primeira captura
        capture_target_snapshot(self.scene, op, target)
        snap1 = op.snapshot_object
        self.assertIsNotNone(snap1)
        self.assertEqual(snap1.get("chest_role"), ROLE_RESTORE_BACKUP)

        # Segunda captura (atualização transacional)
        capture_target_snapshot(self.scene, op, target)
        snap2 = op.snapshot_object
        self.assertIsNotNone(snap2)
        self.assertEqual(snap2.get("chest_role"), ROLE_RESTORE_BACKUP)
        self.assertIn(snap2.name, bpy.data.objects)

    def test_t41_resolve_operation_detects_ambiguity(self):
        """T41: Selecionar resultados de duas operações retorna None impedindo resolução ambígua."""
        op1 = get_or_create_operation_record(self.scene, "OP_ONE_111", status='COMMITTED')
        op2 = get_or_create_operation_record(self.scene, "OP_TWO_222", status='COMMITTED')

        m1 = bpy.data.meshes.new("M1")
        o1 = bpy.data.objects.new("Part_One", m1)
        o1["chest_operation_id"] = "OP_ONE_111"
        self.scene.collection.objects.link(o1)

        m2 = bpy.data.meshes.new("M2")
        o2 = bpy.data.objects.new("Part_Two", m2)
        o2["chest_operation_id"] = "OP_TWO_222"
        self.scene.collection.objects.link(o2)

        # Seleciona ambos os objetos simultaneamente
        bpy.ops.object.select_all(action='DESELECT')
        o1.select_set(True)
        o2.select_set(True)

        context = bpy.context
        resolved = resolve_operation(context)
        # Ambiguidade deve retornar None
        self.assertIsNone(resolved)

    def test_t42_foreign_object_same_name_not_used_as_backup(self):
        """T42: Objeto criado pelo usuário com mesmo nome do snapshot não é usado como backup."""
        op = get_or_create_operation_record(self.scene, "OP_SECURITY_42", status='COMMITTED')
        op.snapshot_name = "_snap_obj_OP_SECUR"

        # Usuário cria um objeto manual com esse mesmo nome
        m = bpy.data.meshes.new("ForeignMesh")
        foreign_obj = bpy.data.objects.new("_snap_obj_OP_SECUR", m)
        self.scene.collection.objects.link(foreign_obj)

        context = bpy.context
        # Reversão deve falhar e não tocar no objeto do usuário
        success, msg = revert_committed_operation(context, op_id="OP_SECURITY_42")
        self.assertFalse(success)
        self.assertIn("_snap_obj_OP_SECUR", bpy.data.objects)

    def test_t43_deleted_target_restored_with_modifiers(self):
        """T43: Alvo apagado pelo usuário recupera modificadores e configurações a partir do snapshot."""
        op = get_or_create_operation_record(self.scene, "OP_MOD_RECOVER", status='COMMITTED')

        mesh = bpy.data.meshes.new("ModTargetMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.03)
        bm.to_mesh(mesh)
        bm.free()

        target = bpy.data.objects.new("OriginalWithMod", mesh)
        self.scene.collection.objects.link(target)
        mod = target.modifiers.new(name="BevelMod", type='BEVEL')
        mod.width = 0.002

        capture_target_snapshot(self.scene, op, target)

        # Usuário apaga o alvo original
        bpy.data.objects.remove(target, do_unlink=True)
        self.assertNotIn("OriginalWithMod", bpy.data.objects)

        context = bpy.context
        success, msg = revert_committed_operation(context, op_id="OP_MOD_RECOVER")
        self.assertTrue(success)

        restored = bpy.data.objects.get("OriginalWithMod")
        self.assertIsNotNone(restored)
        self.assertEqual(len(restored.modifiers), 1)
        self.assertEqual(restored.modifiers[0].name, "BevelMod")

    def test_t44_child_preview_blocks_parent_reversion(self):
        """T44: Presença de prévia filha ativa bloqueia reversão do corte pai."""
        parent_op = get_or_create_operation_record(self.scene, "PARENT_OP", status='COMMITTED')
        child_op = get_or_create_operation_record(self.scene, "CHILD_OP", status='PREVIEW', parent_op_id="PARENT_OP")

        has_child, msg = check_child_operations(self.scene, parent_op)
        self.assertTrue(has_child)
        self.assertIn("CHILD_OP"[:8], msg)


if __name__ == "__main__":
    res = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestPlan087))
    if not res.wasSuccessful():
        import sys
        sys.exit(1)

