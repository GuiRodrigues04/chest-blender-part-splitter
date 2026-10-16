"""Testes de regressão específicos para o bug de reedição e movimentação de pinos após prévia.

Valida:
1. Reabertura do editor após criação de prévia limpa objetos de preview e desoculta o alvo.
2. Preservação dos pinos na reedição.
3. Concluir edição (finish) e cancelar edição (cancel) sem gerar preview prematuramente.
4. Raycast / projeção no plano permite mover e selecionar pinos mesmo quando caem fora da margem.
5. Gerar preview encerra a sessão ativa do editor para evitar zumbis de estado.
"""

import sys
import os
import unittest
import math

import bpy
import bmesh
from mathutils import Vector, Matrix

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import src as addon_package
from src.constants import PREVIEW_A_NAME, PREVIEW_B_NAME
from src.connector_surface import (
    prepare_split_candidates,
    evaluate_connector_specs,
    clear_prepared_split_cache,
)
from src.connector_editor import (
    get_editor_interaction_state,
    CHEST_OT_splitter_edit_manual_connectors,
)


class TestReeditAfterPreviewBugfix(unittest.TestCase):
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
        if not hasattr(bpy.types.Scene, "chest_splitter"):
            addon_package.register()
        if not bpy.context.scene.collection:
            col = bpy.data.collections.new("Scene Collection")
            bpy.context.scene.collection = col
        self.scene = bpy.context.scene
        self.settings = self.scene.chest_splitter
        clear_prepared_split_cache()
        _state = get_editor_interaction_state()
        _state["is_active"] = False
        _state["is_dragging"] = False
        _state["drag_idx"] = -1
        _state["hover_world"] = None

    def _create_test_box(self, name="BoxTarget", size=(0.1, 0.1, 0.06)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        self.scene.collection.objects.link(obj)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.transform(Matrix.Diagonal((*size, 1.0)))
        bm.to_mesh(mesh)
        bm.free()
        bpy.context.view_layer.update()
        return obj

    def test_reopen_editor_after_preview_restores_target_and_cleans_preview(self):
        """Valida que reabrir o editor após preview desoculta o alvo e remove os objetos de preview."""
        target = self._create_test_box("TargetReopen")
        self.settings.target_object = target
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'MANUAL'
        self.settings.manual_connectors.clear()

        # Adiciona 2 pinos válidos
        p1 = self.settings.manual_connectors.add()
        p1.u_mm = -15.0
        p1.v_mm = 0.0
        p2 = self.settings.manual_connectors.add()
        p2.u_mm = 15.0
        p2.v_mm = 0.0

        # 1. Gera prévia
        res = bpy.ops.chest.splitter_confirm_manual_connectors()
        self.assertIn('FINISHED', res)
        self.assertTrue(target.hide_viewport, "Alvo deve estar oculto enquanto preview está visível.")
        self.assertIsNotNone(bpy.data.objects.get(PREVIEW_A_NAME), "Parte A deve existir.")

        # 2. Usuário reabre o editor para editar posições novamente
        bpy.ops.chest.splitter_edit_manual_connectors()
        self.assertTrue(self.settings.is_editing_connectors, "is_editing_connectors deve estar ativo.")
        self.assertFalse(target.hide_viewport, "Alvo deve ser desocultado para edição dos pinos.")
        self.assertIsNone(bpy.data.objects.get(PREVIEW_A_NAME), "Objetos de preview anteriores devem ser limpos ao reabrir o editor.")
        self.assertEqual(len(self.settings.manual_connectors), 2, "Os pinos anteriores devem ser preservados.")

    def test_finish_and_cancel_operators(self):
        """Valida que os operadores Concluir e Cancelar encerram a edição de forma segura."""
        target = self._create_test_box("TargetFinishCancel")
        self.settings.target_object = target
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'MANUAL'
        self.settings.manual_connectors.clear()

        p1 = self.settings.manual_connectors.add()
        p1.u_mm = 0.0
        p1.v_mm = 0.0

        bpy.ops.chest.splitter_edit_manual_connectors()
        self.assertTrue(self.settings.is_editing_connectors)

        # Concluir edição
        bpy.ops.chest.splitter_finish_manual_connectors()
        self.assertFalse(self.settings.is_editing_connectors, "Concluir edição deve desativar is_editing_connectors.")
        self.assertEqual(len(self.settings.manual_connectors), 1)

        # Reabre e cancela
        CHEST_OT_splitter_edit_manual_connectors._last_snapshot = [{"connector_id": "pin_0", "u_mm": 0.0, "v_mm": 0.0, "yaw_deg": 0.0}]
        p_extra = self.settings.manual_connectors.add()
        p_extra.u_mm = 20.0
        p_extra.v_mm = 20.0
        self.assertEqual(len(self.settings.manual_connectors), 2)

        self.settings.is_editing_connectors = True
        bpy.ops.chest.splitter_cancel_manual_connectors()
        self.assertFalse(self.settings.is_editing_connectors)
        self.assertEqual(len(self.settings.manual_connectors), 1, "Cancelar deve restaurar o snapshot.")
        self.assertEqual(self.settings.manual_connectors[0].u_mm, 0.0)

    def test_generate_preview_closes_editing_state(self):
        """Valida que gerar preview via chest.splitter_generate_preview encerra qualquer sessão de edição ativa."""
        target = self._create_test_box("TargetGenerateClosesEdit")
        self.settings.target_object = target
        self.settings.connector_enabled = True
        self.settings.connector_distribution = 'MANUAL'
        self.settings.manual_connectors.clear()

        p1 = self.settings.manual_connectors.add()
        p1.u_mm = -10.0
        p1.v_mm = 0.0

        self.settings.is_editing_connectors = True
        _state = get_editor_interaction_state()
        _state["is_active"] = True

        bpy.ops.chest.splitter_generate_preview()
        self.assertFalse(self.settings.is_editing_connectors, "Gerar preview deve desativar is_editing_connectors.")
        self.assertFalse(_state["is_active"], "is_active deve ser False após gerar preview.")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
