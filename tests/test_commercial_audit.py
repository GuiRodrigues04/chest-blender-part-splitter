"""Testes de regressão dos critérios comerciais (COM-01 a COM-07) do Part Splitter."""
import sys
import unittest
import importlib
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

args = (
    sys.argv[sys.argv.index("--") + 1 :]
    if "--" in sys.argv
    else sys.argv[1:]
    if "--python" not in sys.argv
    else []
)
root = Path(args[0]).resolve() if args else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
addon = importlib.import_module(root.name)

import bpy
import bmesh
from mathutils import Vector, Matrix

constants = importlib.import_module(root.name + ".src.constants")
ops = importlib.import_module(root.name + ".src.operators")
life = importlib.import_module(root.name + ".src.lifecycle")
cs = importlib.import_module(root.name + ".src.connector_surface")
input_state = importlib.import_module(root.name + ".src.input_state")
io_export = importlib.import_module(root.name + ".src.io_export")
gpu_drawing = importlib.import_module(root.name + ".src.gpu_drawing")
gm = importlib.import_module(root.name + ".src.geometry_material")
addon.register()


def create_test_box(name: str, size=(40, 40, 40), location=(0, 0, 0)) -> bpy.types.Object:
    """Cria um cubo de teste isolado."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    return obj


class TestCommercialAudit(unittest.TestCase):
    def setUp(self):
        # Limpa objetos de teste
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh, do_unlink=True)
        if hasattr(bpy.context.scene, "chest_operations"):
            bpy.context.scene.chest_operations.clear()
        settings = bpy.context.scene.chest_splitter
        settings.session_id = ""
        settings.active_operation_id = ""
        settings.session_status = 'CONFIGURED'
        settings.split_mode = 'PLANE'
        settings.connector_enabled = False
        cs.clear_prepared_split_cache()

    def test_com01_commit_preserves_exportable_operation_receiver_extracted_none(self):
        """COM-01 / F01: Confirmar corte nos 3 modos de próximo alvo mantém partes exportáveis."""
        settings = bpy.context.scene.chest_splitter

        for next_target_choice in ('RECEIVER', 'EXTRACTED', 'NONE'):
            self.setUp()
            target = create_test_box(f'body_{next_target_choice}')
            settings.target_object = target
            settings.split_mode = 'PLANE'
            settings.commit_next_target = next_target_choice

            ret_prev = bpy.ops.chest.splitter_generate_preview()
            self.assertIn('FINISHED', ret_prev)
            orig_sid = settings.session_id
            self.assertTrue(bool(orig_sid))

            # Confirma corte
            ret_commit = bpy.ops.chest.splitter_commit_parts()
            self.assertIn('FINISHED', ret_commit)

            # Exportador deve ter poll True
            can_export = bpy.ops.chest.splitter_export_parts.poll()
            self.assertTrue(can_export, f"Export poll falhou para commit_next_target={next_target_choice}")

            # get_current_session_parts deve retornar as 2 partes confirmadas
            exportable_parts = ops.get_current_session_parts(bpy.context.scene)
            self.assertEqual(len(exportable_parts), 2, f"Partes exportáveis != 2 para {next_target_choice}")

            # Exportar deve rodar sem erros
            with tempfile.TemporaryDirectory() as tmpdir:
                settings.export_directory = tmpdir
                settings.export_format = 'STL_PARTS'
                ret_exp = bpy.ops.chest.splitter_export_parts()
                self.assertIn('FINISHED', ret_exp)
                stls = list(Path(tmpdir).glob("*.stl"))
                self.assertGreaterEqual(len(stls), 2, f"STLs exportados < 2 para {next_target_choice}")


    def test_com02_cutter_modifier_invalidates_preview(self):
        """COM-02 / F02: Modificador no cortador sólido deve invalidar a assinatura e o cache de prévia."""
        settings = bpy.context.scene.chest_splitter
        target = create_test_box('body_com02')
        cutter = create_test_box('cutter_com02', size=(24, 24, 40), location=(0, 0, 18))
        settings.target_object = target
        settings.solid_cutter_object = cutter
        settings.split_mode = 'SOLID'
        settings.connector_enabled = False

        mod = cutter.modifiers.new('deform', 'DISPLACE')
        mod.direction = 'NORMAL'
        mod.mid_level = 0.0
        mod.strength = 0.0
        bpy.context.view_layer.update()

        ret = bpy.ops.chest.splitter_generate_preview()
        self.assertIn('FINISHED', ret)
        sig1 = ops.compute_session_input_signature(bpy.context)
        p1 = cs.get_cached_prepared_split()

        # Altera parâmetro do modificador (a malha bruta não muda, mas a malha avaliada muda)
        mod.strength = 2.0
        bpy.context.view_layer.update()
        sig2 = ops.compute_session_input_signature(bpy.context)
        self.assertNotEqual(sig1, sig2, "Assinatura da sessão não mudou após alterar modificador do cortador!")

        is_current, reason = ops.verify_preview_current(bpy.context)
        self.assertFalse(is_current, "verify_preview_current não deve aceitar prévia com cortador modificado!")

        p2 = cs.prepare_split_candidates(bpy.context)
        self.assertIsNot(p1, p2, "prepare_split_candidates não deve reutilizar o cache de corte antigo!")


    def test_com03_late_preview_failure_rollback(self):
        """COM-03 / F03: Falha injetada durante a geração de prévia deve preservar a prévia anterior intacta."""
        settings = bpy.context.scene.chest_splitter
        target = create_test_box('body_com03')
        settings.target_object = target
        settings.split_mode = 'PLANE'
        settings.connector_enabled = True
        settings.connector_distribution = 'CENTER'

        # 1. Gera prévia inicial válida
        ret1 = bpy.ops.chest.splitter_generate_preview()
        self.assertIn('FINISHED', ret1)
        self.assertEqual(settings.session_status, 'PREVIEW_VALID')

        prev_parts_before = [o.name for o in ops.get_current_session_parts(bpy.context.scene)]
        self.assertEqual(len(prev_parts_before), 2, "Deveria haver 2 partes de prévia inicial")

        # 2. Injeta falha controlada na segunda chamada a cache_prepared_interface (durante atualização)
        original_cache = cs.cache_prepared_interface
        counter = [0]

        def injected_cache_prepared_interface(*args, **kwargs):
            counter[0] += 1
            if counter[0] == 2:
                raise RuntimeError("AUDIT_INJECTED_LATE_FAILURE")
            return original_cache(*args, **kwargs)

        cs.cache_prepared_interface = injected_cache_prepared_interface
        try:
            # Tenta atualizar prévia; deve falhar de forma segura sem exception não tratada
            ret2 = bpy.ops.chest.splitter_generate_preview()
            self.assertEqual(ret2, {'CANCELLED'})
        finally:
            cs.cache_prepared_interface = original_cache

        # 3. Verifica que a prévia anterior foi REALMENTE preservada
        previews_after = [o for o in bpy.context.scene.objects if o.get('chest_role') in ('ROLE_PREVIEW_A', 'ROLE_PREVIEW_B', 'PREVIEW_A', 'PREVIEW_B')]
        self.assertEqual(len(previews_after), 2, f"A prévia anterior foi destruída! Objetos encontrados: {[o.name for o in previews_after]}")
        self.assertTrue(target.hide_get(), "O alvo deve continuar oculto enquanto a prévia anterior estiver ativa")


    def test_com04_export_physical_geometry_singular_scale_and_mirrored_winding(self):
        """COM-04 / F04 e F05: Escala singular deve bloquear exportação; objeto espelhado deve ter orientação positiva no 3MF."""
        settings = bpy.context.scene.chest_splitter
        target = create_test_box('body_com04')
        settings.target_object = target
        settings.split_mode = 'PLANE'

        ret1 = bpy.ops.chest.splitter_generate_preview()
        self.assertIn('FINISHED', ret1)

        # F04: Escala zero / singular deve ser rejeitada pela validação de exportação
        parts = ops.get_current_session_parts(bpy.context.scene)
        parts[0].scale.x = 0.0
        bpy.context.view_layer.update()

        settings.export_format = 'STL_PARTS'
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.export_directory = tmpdir
            try:
                ret_exp = bpy.ops.chest.splitter_export_parts()
                self.assertEqual(ret_exp, {'CANCELLED'}, "Exportação com escala zero deveria retornar CANCELLED!")
            except RuntimeError as exc:
                self.assertIn("singular", str(exc).lower())
            stls = list(Path(tmpdir).glob("*.stl"))
            self.assertEqual(len(stls), 0, "Nenhum arquivo STL deve ser publicado quando a escala for singular/zero!")

        # F05: Objeto com escala negativa / espelhado deve gerar 3MF com winding externo positivo
        mirrored = create_test_box('mirrored_box', size=(20, 20, 20))
        mirrored.scale.x = -1.0
        bpy.context.view_layer.update()

        xml_text = io_export.build_3mf_xml([mirrored], unit_scale=1.0)
        tree = ET.fromstring(xml_text)
        ns = {'c': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
        verts = [Vector(tuple(float(v.attrib[k]) for k in ('x', 'y', 'z'))) for v in tree.findall('.//c:vertex', ns)]
        signed_volume = 0.0
        for tri in tree.findall('.//c:triangle', ns):
            a, b, c = [verts[int(tri.attrib[k])] for k in ('v1', 'v2', 'v3')]
            signed_volume += a.dot(b.cross(c)) / 6.0

        # Para um cubo de 20x20x20 = 8000 mm^3, o volume assinado voltado para fora DEVE ser positivo (+8000)
        self.assertGreater(signed_volume, 0, f"Volume assinado do 3MF espelhado foi negativo ({signed_volume})! Winding invertido.")
        self.assertAlmostEqual(signed_volume, 8000.0, delta=1.0)


    def test_com05_rename_target_preserves_manual_connectors(self):
        """COM-05 / F06: Renomear o objeto alvo não deve apagar o layout de conectores manuais."""
        settings = bpy.context.scene.chest_splitter
        target = create_test_box('piece_com05')
        settings.target_object = target
        settings.split_mode = 'PLANE'

        cs.prepare_split_candidates(bpy.context, force_recompute=True)
        conn = settings.manual_connectors.add()
        conn.u_mm = 5.0
        conn.v_mm = 2.0
        before_count = len(settings.manual_connectors)
        self.assertEqual(before_count, 1)

        # Renomeia o objeto alvo
        target.name = 'piece_com05_renamed'
        cs.prepare_split_candidates(bpy.context, force_recompute=True)

        after_count = len(settings.manual_connectors)
        self.assertEqual(after_count, before_count, "Renomear o alvo apagou os conectores manuais!")

    def test_com06_concave_ngon_overlay_no_spurious_segments(self):
        """COM-06 / F07: N-gon côncavo não deve produzir segmentos de corte espúrios no vão vazio."""
        outline = [(-30, -20), (30, -20), (30, 20), (10, 20), (10, 0), (-10, 0), (-10, 20), (-30, 20)]
        mesh = bpy.data.meshes.new('concave_ngon_com06')
        mesh.from_pydata([(x, y, 0) for x, y in outline], [], [tuple(range(len(outline)))])
        mesh.update()
        obj = bpy.data.objects.new('concave_obj_com06', mesh)
        bpy.context.scene.collection.objects.link(obj)

        segments = gpu_drawing._compute_cut_line_segments(mesh, Matrix.Identity(4), Vector((0, 10, 0)), Vector((0, 1, 0)))
        false_segments = []
        for a, b in zip(segments[::2], segments[1::2]):
            midpoint = (a + b) / 2.0
            if -10.0 + 1e-4 < midpoint.x < 10.0 - 1e-4:
                false_segments.append((a, b))

        self.assertEqual(len(false_segments), 0, f"Segmentos espúrios detectados no vão do n-gon côncavo: {false_segments}")

    def test_com07_draw_and_material_caching_orbit_no_recompute(self):
        """COM-07 / P01: Caching de interseção e análise de material evita recomputação pesada no redraw."""
        ui = importlib.import_module(root.name + ".src.ui")

        target = create_test_box('mat_com07')
        mat1 = bpy.data.materials.new('mat1')
        mat2 = bpy.data.materials.new('mat2')
        target.data.materials.append(mat1)
        target.data.materials.append(mat2)
        target.data.polygons[0].material_index = 1
        bpy.context.view_layer.update()

        # 1. Análise de material cacheada
        r1, a1 = ui.get_cached_material_ui_analysis(target, 1, 0)
        r2, a2 = ui.get_cached_material_ui_analysis(target, 1, 0)
        self.assertIs(r1, r2, "Regiões de material deveriam vir do cache sem recalcular no redraw")
        self.assertIs(a1, a2, "Diagnóstico de material deveria vir do cache sem recalcular no redraw")

        # 2. Linha de corte do plano com tesselação real
        mesh = target.data
        mw = target.matrix_world
        origin = Vector((0, 0, 0))
        norm = Vector((0, 0, 1))

        # Primeiro cálculo
        segs1 = gpu_drawing._compute_cut_line_segments(mesh, mw, origin, norm, is_bmesh=False)
        self.assertGreater(len(segs1), 0)

    def test_com08_stepped_belt_loop_detach_and_extrude(self):
        """COM-08: Loop 3D em degrau envolvendo o bloco inteiro deve gerar corte justo manifold em DETACH e EXTRUDE."""
        gl = importlib.import_module(root.name + ".src.geometry_loop")
        bpy.context.scene.unit_settings.scale_length = 0.001

        for use_tris in (False, True):
            self.setUp()
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=164.5)
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
            if use_tris:
                bmesh.ops.triangulate(bm, faces=bm.faces[:])
            me = bpy.data.meshes.new(f"SteppedCube_{use_tris}")
            bm.to_mesh(me)
            bm.free()
            obj = bpy.data.objects.new(f"SteppedCube_{use_tris}", me)
            bpy.context.scene.collection.objects.link(obj)
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)

            h = 164.5 / 2.0
            step = 164.5 / 8.0
            eps = 1e-3
            z_step = 2 * step
            x_min = -3 * step
            x_max = 3 * step

            bpy.ops.object.mode_set(mode='EDIT')
            bm_edit = bmesh.from_edit_mesh(me)
            bm_edit.verts.ensure_lookup_table()
            bm_edit.edges.ensure_lookup_table()
            bm_edit.faces.ensure_lookup_table()
            for v in bm_edit.verts:
                v.select = False
            for e in bm_edit.edges:
                e.select = False
            for f in bm_edit.faces:
                f.select = False

            for e in bm_edit.edges:
                c1, c2 = e.verts[0].co, e.verts[1].co
                on_front = abs(c1.y - (-h)) < eps and abs(c2.y - (-h)) < eps
                if on_front:
                    if abs(c1.z - z_step) < eps and abs(c2.z - z_step) < eps and x_min - eps <= min(c1.x, c2.x) and max(c1.x, c2.x) <= x_max + eps:
                        e.select = True
                    elif abs(c1.z) < eps and abs(c2.z) < eps and (max(c1.x, c2.x) <= x_min + eps or min(c1.x, c2.x) >= x_max - eps):
                        e.select = True
                    elif (abs(c1.x - x_min) < eps and abs(c2.x - x_min) < eps) or (abs(c1.x - x_max) < eps and abs(c2.x - x_max) < eps):
                        if min(c1.z, c2.z) >= -eps and max(c1.z, c2.z) <= z_step + eps:
                            e.select = True
                else:
                    on_wall = (abs(c1.x - h) < eps and abs(c2.x - h) < eps) or (abs(c1.x + h) < eps and abs(c2.x + h) < eps) or (abs(c1.y - h) < eps and abs(c2.y - h) < eps)
                    if on_wall and abs(c1.z) < eps and abs(c2.z) < eps:
                        e.select = True

            seed_face_idx = next(f.index for f in bm_edit.faces if abs(f.calc_center_median().z - h) < eps)
            ok, indices, is_planar, dev_mm, err = gl.capture_edge_loop(obj)
            self.assertTrue(ok, f"Falha na captura do loop: {err}")
            self.assertFalse(is_planar)
            bpy.ops.object.mode_set(mode='OBJECT')

            total_vol = 164.5 ** 3

            # 1. Teste DETACH (Na Base)
            res_detach = gl.slice_mesh_by_loop(obj, obj.name, indices, seed_face_idx, scene=bpy.context.scene)
            try:
                self.assertTrue(res_detach.split_result.part_a_metrics["is_manifold"])
                self.assertTrue(res_detach.split_result.part_b_metrics["is_manifold"])
                self.assertAlmostEqual(
                    res_detach.split_result.part_a_metrics["volume_mm3"] + res_detach.split_result.part_b_metrics["volume_mm3"],
                    total_vol,
                    delta=total_vol * 1e-4,
                )
            finally:
                res_detach.bm_a.free()
                res_detach.bm_b.free()

            # 2. Teste EXTRUDE (Profundidade = 10.0 mm)
            res_ext = gl.slice_mesh_by_loop_extrude(obj, obj.name, indices, seed_face_idx, 10.0, scene=bpy.context.scene)
            try:
                self.assertTrue(res_ext.split_result.part_a_metrics["is_manifold"])
                self.assertTrue(res_ext.split_result.part_b_metrics["is_manifold"])
                vol_a = res_ext.split_result.part_a_metrics["volume_mm3"]
                vol_b = res_ext.split_result.part_b_metrics["volume_mm3"]
                self.assertAlmostEqual(vol_a + vol_b, total_vol, delta=total_vol * 1e-4)
                expected_step_vol = (6 * step) * (2 * step) * 10.0
                self.assertAlmostEqual(vol_b - vol_a, 2.0 * expected_step_vol, delta=50.0)
            finally:
                res_ext.bm_a.free()
                res_ext.bm_b.free()

            # 3. Teste de Folga Física (part_clearance_mm) no Loop 3D em Degrau (PART, CAVITY, BOTH)
            res_nom = gl.slice_mesh_by_loop(obj, obj.name, indices, seed_face_idx, scene=bpy.context.scene, part_clearance_mm=0.0)
            vol_a_nom = res_nom.split_result.part_a_metrics["volume_mm3"]
            vol_b_nom = res_nom.split_result.part_b_metrics["volume_mm3"]
            res_nom.bm_a.free()
            res_nom.bm_b.free()

            for app_mode in ('PART', 'CAVITY', 'BOTH'):
                res_clr = gl.slice_mesh_by_loop(
                    obj, obj.name, indices, seed_face_idx, scene=bpy.context.scene,
                    part_clearance_mm=0.4, part_clearance_apply_to=app_mode,
                )
                try:
                    self.assertTrue(res_clr.split_result.part_a_metrics["is_manifold"], f"Parte A não-manifold em {app_mode}")
                    self.assertTrue(res_clr.split_result.part_b_metrics["is_manifold"], f"Parte B não-manifold em {app_mode}")
                    va = res_clr.split_result.part_a_metrics["volume_mm3"]
                    vb = res_clr.split_result.part_b_metrics["volume_mm3"]
                    if app_mode == 'PART':
                        self.assertLess(va, vol_a_nom - 100.0)
                        self.assertAlmostEqual(vb, vol_b_nom, delta=10.0)
                    elif app_mode == 'CAVITY':
                        self.assertAlmostEqual(va, vol_a_nom, delta=10.0)
                        self.assertLess(vb, vol_b_nom - 100.0)
                    else:
                        self.assertLess(va, vol_a_nom - 50.0)
                        self.assertLess(vb, vol_b_nom - 50.0)
                finally:
                    res_clr.bm_a.free()
                    res_clr.bm_b.free()

    def test_com09_loop_clearance_extrude_and_solid_capsule_clearance(self):
        """COM-09: Folga de interface no modo LOOP (EXTRUDE lateral + fundo) e no modo SOLID (incluindo CAPSULE)."""
        gl = importlib.import_module(root.name + ".src.geometry_loop")
        gs = importlib.import_module(root.name + ".src.geometry_solid")
        bpy.context.scene.unit_settings.scale_length = 0.001
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=40.0)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
        mesh = bpy.data.meshes.new("LoopExtrudeClearanceCube")
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new("LoopExtrudeClearanceCube", mesh)
        bpy.context.scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bm_edit = bmesh.from_edit_mesh(obj.data)
        bm_edit.faces.ensure_lookup_table()
        for f in bm_edit.faces:
            c = f.calc_center_median()
            f.select = (abs(c.z - 20.0) < 1e-3 and abs(c.x) < 10.0 and abs(c.y) < 10.0)
        ok, indices, is_planar, dev_mm, seed_idx, err = gl.capture_face_boundary_loop(obj)
        self.assertTrue(ok, err)
        bpy.ops.object.mode_set(mode='OBJECT')

        res0 = gl.slice_mesh_by_loop_extrude(obj, obj.name, indices, seed_idx, depth_mm=10.0, part_clearance_mm=0.0)
        va0 = res0.split_result.part_a_metrics["volume_mm3"]
        vb0 = res0.split_result.part_b_metrics["volume_mm3"]
        res0.bm_a.free()
        res0.bm_b.free()

        for app_mode in ('PART', 'CAVITY', 'BOTH'):
            res_c = gl.slice_mesh_by_loop_extrude(
                obj, obj.name, indices, seed_idx, depth_mm=10.0,
                part_clearance_mm=0.3, part_clearance_apply_to=app_mode,
                part_clearance_bottom_mm=0.5,
            )
            try:
                self.assertTrue(res_c.split_result.part_a_metrics["is_manifold"])
                self.assertTrue(res_c.split_result.part_b_metrics["is_manifold"])
                va = res_c.split_result.part_a_metrics["volume_mm3"]
                vb = res_c.split_result.part_b_metrics["volume_mm3"]
                if app_mode == 'PART':
                    self.assertLess(va, va0 - 50.0)
                    self.assertAlmostEqual(vb, vb0, delta=1.0)
                elif app_mode == 'CAVITY':
                    self.assertAlmostEqual(va, va0, delta=1.0)
                    self.assertLess(vb, vb0 - 50.0)
                else:
                    self.assertLess(va, va0 - 25.0)
                    self.assertLess(vb, vb0 - 25.0)
            finally:
                res_c.bm_a.free()
                res_c.bm_b.free()

        # Verifica CAPSULE com folga no modo SOLID
        cutter_mesh = gs.create_primitive_cutter_mesh("CapClearance", 'CAPSULE', Vector((20.0, 20.0, 20.0)), segments=24)
        cutter_obj = bpy.data.objects.new("CapClearance", cutter_mesh)
        cutter_obj.location = Vector((0.0, 0.0, 20.0))
        bpy.context.scene.collection.objects.link(cutter_obj)
        bpy.context.view_layer.update()

        ma = bpy.data.meshes.new("CapOutA")
        mb = bpy.data.meshes.new("CapOutB")
        try:
            rep = gs.slice_mesh_by_solid(
                obj.data, obj.matrix_world, cutter_obj, ma, mb,
                unit_scale=1.0, part_clearance_mm=0.25, part_clearance_apply_to='BOTH',
            )
            self.assertTrue(rep["A"]["is_manifold"])
            self.assertTrue(rep["B"]["is_manifold"])
            self.assertLess(rep["A"]["volume_mm3"] + rep["B"]["volume_mm3"], 64000.0 - 50.0)
        finally:
            bpy.data.meshes.remove(ma)
            bpy.data.meshes.remove(mb)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCommercialAudit)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    addon.unregister()
    sys.exit(0 if result.wasSuccessful() else 1)

