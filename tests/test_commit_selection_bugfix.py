"""Teste de regressão para seleção no Object Mode após confirmar corte (commit_parts).

Verifica:
1. Encerramento forçado e seguro do modal de edição manual de pinos no commit_parts.
2. Não captura de cliques nem emissão indevida de mensagem de posicionamento de pinos pós-commit.
3. Ambas as peças finais (A e B) desimpedidas, visíveis e selecionáveis em Object Mode.
4. Objeto alvo pré-corte oculto de forma consistente (hide_viewport e hide_set).
5. Pass-through de eventos se _modal_impl for chamado após commit ou em modo não-OBJECT.
"""

import unittest
import os
import sys
import bpy
import bmesh
from mathutils import Vector, Matrix

addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import src
from src.constants import (
    COLLECTION_PARTS_NAME,
    COLLECTION_PREVIEWS_NAME,
    ROLE_COMMITTED_PART,
)
from src.connector_editor import (
    get_editor_interaction_state,
    stop_connector_editor,
    CHEST_OT_splitter_edit_manual_connectors,
)


class TestCommitSelectionBugfix(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            src.register()
        except ValueError:
            pass

    @classmethod
    def tearDownClass(cls):
        try:
            src.unregister()
        except RuntimeError:
            pass

    def setUp(self):
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        for col in list(bpy.data.collections):
            bpy.data.collections.remove(col)

        for block in list(bpy.data.meshes):
            if block.users == 0:
                bpy.data.meshes.remove(block)

        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter
        self.settings.session_id = ""
        self.settings.active_operation_id = ""
        self.settings.target_object = None
        self.settings.session_status = 'EMPTY'

        if hasattr(self.scene, "chest_operations"):
            self.scene.chest_operations.clear()

    def _create_cube(self, name="Cube", size=0.04):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        self.scene.collection.objects.link(obj)

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=size)
        bm.to_mesh(mesh)
        bm.free()
        return obj

    def test_commit_terminates_connector_modal_and_restores_selection(self):
        """Verifica que o commit encerra o editor modal e permite selecionar qualquer peça."""
        target = self._create_cube("TargetBlock", 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.chest.splitter_set_target()

        # Ativa modo manual e simula estado ativo de edição
        self.settings.connector_distribution = 'MANUAL'
        self.settings.connector_enabled = True
        self.settings.is_editing_connectors = True
        ed_state = get_editor_interaction_state()
        ed_state["is_active"] = True

        # Gera preview
        res_prev = bpy.ops.chest.splitter_generate_preview()
        self.assertIn('FINISHED', res_prev)
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        # Simula que o usuário reativou a edição interativa de pinos
        self.settings.is_editing_connectors = True
        ed_state["is_active"] = True

        # Confirma corte (Commit)
        bpy.context.scene.chest_splitter.commit_next_target = 'NONE'
        res_commit = bpy.ops.chest.splitter_commit_parts()
        self.assertIn('FINISHED', res_commit)
        self.assertEqual(self.settings.session_status, 'COMMITTED')

        # 1. O editor de conectores DEVE estar totalmente desativado
        self.assertFalse(self.settings.is_editing_connectors)
        self.assertFalse(ed_state.get("is_active", False))
        self.assertFalse(ed_state.get("is_dragging", False))
        self.assertEqual(ed_state.get("drag_idx", -1), -1)

        # 2. As peças finais devem estar na coleção de peças, visíveis e desimpedidas
        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        self.assertIsNotNone(parts_col)
        self.assertEqual(len(parts_col.objects), 2)
        # Current public names are short and numbered; legacy __A/__B names
        # no longer identify the committed objects.
        part_a = parts_col.objects.get("TargetBlock — Peça 001")
        part_b = parts_col.objects.get("TargetBlock — Restante 001")
        self.assertIsNotNone(part_a)
        self.assertIsNotNone(part_b)
        self.assertEqual(part_a.get("chest_role"), ROLE_COMMITTED_PART)
        self.assertEqual(part_b.get("chest_role"), ROLE_COMMITTED_PART)

        self.assertFalse(part_a.hide_viewport)
        self.assertFalse(part_a.hide_get())
        self.assertFalse(part_b.hide_viewport)
        self.assertFalse(part_b.hide_get())

        # 3. O alvo original pré-corte deve estar oculto no viewport e outliner
        self.assertTrue(target.hide_viewport)
        self.assertTrue(target.hide_get())

        # 4. Deve ser possível selecionar a outra peça (part_b) livremente em Object Mode
        bpy.ops.object.select_all(action='DESELECT')
        part_b.select_set(True)
        bpy.context.view_layer.objects.active = part_b
        self.assertEqual(bpy.context.active_object, part_b)
        self.assertTrue(part_b.select_get())
        self.assertFalse(part_a.select_get())

    def test_modal_guard_exits_on_committed_or_edit_mode_with_pass_through(self):
        """Testa se o _modal_impl encerra graciosamente com pass_through quando acionado em COMMITTED ou Edit Mode."""
        target = self._create_cube("GuardBlock", 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.chest.splitter_set_target()

        class MockOperator:
            _target = target
            _prepared = None
            _area = None
            def _finish_cleanup(self, context, result_state, pass_through=False):
                return CHEST_OT_splitter_edit_manual_connectors._finish_cleanup(self, context, result_state, pass_through=pass_through)

        mock_op = MockOperator()

        class DummyEvent:
            type = 'LEFTMOUSE'
            value = 'PRESS'
            mouse_x = 100
            mouse_y = 100

        # Caso 1: Status COMMITTED -> deve retornar FINISHED e PASS_THROUGH
        self.settings.session_status = 'COMMITTED'
        self.settings.is_editing_connectors = False
        res1 = CHEST_OT_splitter_edit_manual_connectors._modal_impl(mock_op, bpy.context, DummyEvent())
        self.assertIn('FINISHED', res1)
        self.assertIn('PASS_THROUGH', res1)

        # Caso 2: Em EDIT mode -> deve retornar CANCELLED e PASS_THROUGH
        self.settings.session_status = 'CONFIGURED'
        self.settings.is_editing_connectors = True
        bpy.ops.object.mode_set(mode='EDIT')
        res2 = CHEST_OT_splitter_edit_manual_connectors._modal_impl(mock_op, bpy.context, DummyEvent())
        self.assertIn('CANCELLED', res2)
        self.assertIn('PASS_THROUGH', res2)
        bpy.ops.object.mode_set(mode='OBJECT')


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
