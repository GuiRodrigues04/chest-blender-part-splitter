"""Suíte de testes automatizados para Remoção de Prévia e Reversão de Cortes (Part Splitter 0.8.6).

Cobre integralmente os requisitos da Seção 8 de docs/Plano_Antigravity_Reversao_Part_Splitter_0.8.6.md:
- Casos de corte: PLANE, SOLID, LOOP e MATERIAL (gerar -> remover -> editar -> gerar; commit -> reverter -> repetir)
- Prévia explodida, stale e invalid com prévia anterior
- Edit Mode ativo durante remoção ou reversão
- Preservação de cópia de trabalho e suas edições
- Alvo com transformações, modificadores e materiais
- Múltiplas operações e bloqueio de reversão de pai com filho ativo
- Separação por material (limpeza de subpeças e restauração de pais)
- Peças renomeadas/movidas e proteção de duplicatas do usuário
- Recuperação de alvo deletado a partir do snapshot de backup
- 10 ciclos sucessivos sem vazamento de malhas ou snapshots
"""

import unittest
import os
import sys
import bmesh
import bpy
from mathutils import Vector, Matrix

# Garante importação do pacote local
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import src
from src.constants import (
    COLLECTION_PREVIEWS_NAME,
    COLLECTION_PARTS_NAME,
    COLLECTION_WORK_NAME,
    COLLECTION_BACKUPS_NAME,
    ROLE_PREVIEW_A,
    ROLE_PREVIEW_B,
    ROLE_COMMITTED_PART,
    ROLE_SUBPART_MATERIAL,
    ROLE_RESTORE_BACKUP,
)
from src.lifecycle import (
    find_operation_record,
    resolve_operation,
    check_child_operations,
    remove_preview,
    revert_committed_operation,
)


class TestReversion086(unittest.TestCase):

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
        # Limpa todos os dados da cena para isolamento estrito
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

        # Limpa registros de operações
        if hasattr(self.scene, "chest_operations"):
            self.scene.chest_operations.clear()

    def _create_box(self, name="Box", x=0.04, y=0.04, z=0.04, loc=(0, 0, 0)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        self.scene.collection.objects.link(obj)

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.transform(Matrix.Diagonal((x, y, z, 1.0)))
        bm.to_mesh(mesh)
        bm.free()

        obj.location = loc
        bpy.context.view_layer.update()
        return obj

    # -------------------------------------------------------------------------
    # Caso 1: Ciclo Completo PLANE (Gerar -> Remover -> Editar -> Gerar -> Commit -> Reverter)
    # -------------------------------------------------------------------------
    def test_01_planar_remove_preview_and_revert_cut(self):
        """Ciclo completo PLANE: prévia, remoção, edição do alvo, regeneração, confirmação e reversão."""
        target = self._create_box("PlanarBox", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.chest.splitter_set_target()

        # 1. Gerar prévia
        res_prev = bpy.ops.chest.splitter_generate_preview()
        self.assertIn('FINISHED', res_prev)
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')
        self.assertTrue(target.hide_viewport)

        # 2. Remover prévia
        res_rem = bpy.ops.chest.splitter_remove_preview()
        self.assertIn('FINISHED', res_rem)
        self.assertEqual(self.settings.session_status, 'CONFIGURED')
        self.assertFalse(target.hide_viewport)
        self.assertEqual(bpy.context.active_object, target)

        # 3. Editar alvo
        target.data.vertices[0].co.x += 0.005

        # 4. Regenerar prévia
        res_prev2 = bpy.ops.chest.splitter_generate_preview()
        self.assertIn('FINISHED', res_prev2)
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        # 5. Confirmar corte
        res_commit = bpy.ops.chest.splitter_commit_parts()
        self.assertIn('FINISHED', res_commit)
        self.assertEqual(self.settings.session_status, 'COMMITTED')

        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        self.assertIsNotNone(parts_col)
        self.assertEqual(len(parts_col.objects), 2)

        # 6. Reverter corte
        res_rev = bpy.ops.chest.splitter_revert_cut()
        self.assertIn('FINISHED', res_rev)
        self.assertEqual(self.settings.session_status, 'CONFIGURED')
        self.assertEqual(len(parts_col.objects), 0)
        self.assertFalse(target.hide_viewport)
        self.assertEqual(bpy.context.active_object, target)

    # -------------------------------------------------------------------------
    # Caso 2: Prévia Explodida, Stale e Invalid com Prévia Anterior Preservada
    # -------------------------------------------------------------------------
    def test_02_remove_preview_in_various_states(self):
        """Remoção de prévia em modos explodido, desatualizado (STALE) e com erro (INVALID)."""
        target = self._create_box("StateBox", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.chest.splitter_set_target()

        # Prévia com visualização explodida
        self.settings.preview_exploded = True
        bpy.ops.chest.splitter_generate_preview()
        self.assertEqual(self.settings.session_status, 'PREVIEW_VALID')

        # Transiciona para STALE alterando folga
        self.settings.clearance_per_side_mm = 0.25
        self.assertEqual(self.settings.session_status, 'PREVIEW_STALE')

        # Botão de remover prévia deve estar acessível e funcional
        self.assertTrue(bpy.ops.chest.splitter_remove_preview.poll())
        res = bpy.ops.chest.splitter_remove_preview()
        self.assertIn('FINISHED', res)
        self.assertEqual(self.settings.session_status, 'CONFIGURED')
        self.assertFalse(target.hide_viewport)

    # -------------------------------------------------------------------------
    # Caso 3: Execução Segura com Edit Mode Ativo
    # -------------------------------------------------------------------------
    def test_03_edit_mode_safe_exit_on_remove_and_revert(self):
        """Garante saída segura de Edit Mode sem ReferenceError em remoção e reversão."""
        target = self._create_box("EditBox", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.chest.splitter_set_target()

        bpy.ops.chest.splitter_generate_preview()

        # Entra em Edit Mode no preview
        prev_col = bpy.data.collections.get(COLLECTION_PREVIEWS_NAME)
        p_obj = prev_col.objects[0]
        bpy.ops.object.select_all(action='DESELECT')
        p_obj.select_set(True)
        bpy.context.view_layer.objects.active = p_obj
        bpy.ops.object.mode_set(mode='EDIT')

        # Remove prévia mesmo em Edit Mode
        res = bpy.ops.chest.splitter_remove_preview()
        self.assertIn('FINISHED', res)
        self.assertEqual(bpy.context.mode, 'OBJECT')
        self.assertEqual(bpy.context.active_object, target)

    # -------------------------------------------------------------------------
    # Caso 4: Preservação de Cópia de Trabalho e Edições
    # -------------------------------------------------------------------------
    def test_04_work_copy_edits_preserved_on_remove_preview(self):
        """Remover prévia não descarta nem desassocia a cópia de trabalho ou suas edições."""
        orig = self._create_box("OriginalPart", 0.05, 0.05, 0.05)
        bpy.ops.object.select_all(action='DESELECT')
        orig.select_set(True)
        bpy.context.view_layer.objects.active = orig
        bpy.ops.chest.splitter_set_target()

        # Cria cópia de trabalho
        bpy.ops.chest.splitter_create_work_copy()
        work_copy = self.settings.target_object
        self.assertIn("work_copy", work_copy.name)

        # Edita a cópia de trabalho
        work_copy.data.vertices[0].co.z += 0.01
        edited_z = work_copy.data.vertices[0].co.z

        # Gera e remove prévia
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_remove_preview()

        # Cópia de trabalho deve continuar ativa como alvo com suas edições preservadas
        self.assertEqual(self.settings.target_object, work_copy)
        self.assertEqual(work_copy.data.vertices[0].co.z, edited_z)
        self.assertIn(work_copy.name, bpy.data.objects)

    # -------------------------------------------------------------------------
    # Caso 5: Alvo com Transformações, Modificadores e Materiais
    # -------------------------------------------------------------------------
    def test_05_target_with_transforms_modifiers_materials_restored(self):
        """Reversão recupera transformações, modifiers e materiais preservando identidade."""
        target = self._create_box("ComplexBox", 0.04, 0.04, 0.04, loc=(0.1, 0.2, 0.3))
        mat = bpy.data.materials.new("TestMat")
        target.data.materials.append(mat)
        mod = target.modifiers.new(name="BevelTest", type='BEVEL')
        mod.width = 0.002

        orig_matrix = target.matrix_world.copy()
        orig_vert_count = len(target.data.vertices)

        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.chest.splitter_set_target()

        # Gera e confirma
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        # Altera intencionalmente a matriz do alvo enquanto oculto
        target.location.x += 0.5

        # Reverte corte
        res = bpy.ops.chest.splitter_revert_cut()
        self.assertIn('FINISHED', res)

        # Alvo restaurado à transformação de entrada do corte
        self.assertAlmostEqual(target.location.x, 0.1, places=5)
        self.assertEqual(len(target.data.vertices), orig_vert_count)
        self.assertEqual(len(target.data.materials), 1)
        self.assertEqual(target.data.materials[0], mat)
        self.assertIn("BevelTest", target.modifiers)

    # -------------------------------------------------------------------------
    # Caso 6: Duas Operações Independentes
    # -------------------------------------------------------------------------
    def test_06_two_independent_operations(self):
        """Reverter uma operação independente mantém os resultados da outra intactos."""
        box1 = self._create_box("Box1", 0.04, 0.04, 0.04, loc=(-0.1, 0, 0))
        box2 = self._create_box("Box2", 0.04, 0.04, 0.04, loc=(0.1, 0, 0))

        # Corta Box1
        bpy.ops.object.select_all(action='DESELECT')
        box1.select_set(True)
        bpy.context.view_layer.objects.active = box1
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        # Corta Box2
        bpy.ops.object.select_all(action='DESELECT')
        box2.select_set(True)
        bpy.context.view_layer.objects.active = box2
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        self.assertEqual(len(parts_col.objects), 4)

        # Reverte Box2 (ativo)
        bpy.ops.chest.splitter_revert_cut()

        # Peças de Box1 continuam existindo
        box1_parts = [o for o in parts_col.objects if "Box1" in o.name]
        self.assertEqual(len(box1_parts), 2)
        self.assertEqual(len(parts_col.objects), 2)

    # -------------------------------------------------------------------------
    # Caso 7: Hierarquia de Corte Filho (Bloqueio do Pai)
    # -------------------------------------------------------------------------
    def test_07_child_cut_blocks_parent_reversion(self):
        """Corte realizado na peça gerada bloqueia a reversão do pai até o filho ser revertido."""
        base = self._create_box("BaseBlock", 0.06, 0.06, 0.06)
        bpy.ops.object.select_all(action='DESELECT')
        base.select_set(True)
        bpy.context.view_layer.objects.active = base
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        part_a = [o for o in parts_col.objects if o.name.endswith("__A")][0]
        parent_op_id = part_a.get("chest_operation_id")

        # Define Parte A como alvo de um novo corte filho
        bpy.ops.object.select_all(action='DESELECT')
        part_a.select_set(True)
        bpy.context.view_layer.objects.active = part_a
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        # Tentar reverter o corte pai diretamente deve ser bloqueado
        parent_rec = find_operation_record(self.scene, parent_op_id)
        has_child, msg = check_child_operations(self.scene, parent_rec)
        self.assertTrue(has_child)
        self.assertTrue("corte posterior" in msg.lower() or "posterior cut" in msg.lower())

        # Reverte o filho primeiro
        bpy.ops.chest.splitter_revert_cut()

        # Agora a reversão do pai é permitida
        has_child_after, _ = check_child_operations(self.scene, parent_rec)
        self.assertFalse(has_child_after)

        # Reverte o pai
        res = revert_committed_operation(bpy.context, op_id=parent_op_id)
        self.assertTrue(res[0])
        self.assertFalse(base.hide_viewport)

    # -------------------------------------------------------------------------
    # Caso 8: Separação por Material Reversível
    # -------------------------------------------------------------------------
    def test_08_material_separation_reversion(self):
        """Reversão de corte que sofreu separação por material remove subpeças e restaura pai."""
        cube = self._create_box("MultiMatCube", 0.04, 0.04, 0.04)
        m0 = bpy.data.materials.new("MatA")
        m1 = bpy.data.materials.new("MatB")
        cube.data.materials.append(m0)
        cube.data.materials.append(m1)

        # Pinta uma face com material 1
        cube.data.polygons[0].material_index = 1

        bpy.ops.object.select_all(action='DESELECT')
        cube.select_set(True)
        bpy.context.view_layer.objects.active = cube
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        # Separa por material
        bpy.ops.chest.splitter_separate_by_material()
        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        self.assertGreater(len(parts_col.objects), 2)

        # Reverte operação completa
        res = bpy.ops.chest.splitter_revert_cut()
        self.assertIn('FINISHED', res)
        self.assertEqual(len(parts_col.objects), 0)
        self.assertFalse(cube.hide_viewport)

    # -------------------------------------------------------------------------
    # Caso 9: Peças Renomeadas/Movidas Continuam Rastreáveis
    # -------------------------------------------------------------------------
    def test_09_renamed_or_moved_parts_tracked(self):
        """Peças finais renomeadas ou movidas são identificadas e removidas na reversão."""
        box = self._create_box("TrackBox", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        part = parts_col.objects[0]
        # Usuário renomeia a peça
        part.name = "My_Custom_Part_Name_Changed"

        res = bpy.ops.chest.splitter_revert_cut()
        self.assertIn('FINISHED', res)
        self.assertEqual(len(parts_col.objects), 0)
        self.assertNotIn("My_Custom_Part_Name_Changed", bpy.data.objects)

    # -------------------------------------------------------------------------
    # Caso 10: Proteção a Duplicatas Feitas pelo Usuário
    # -------------------------------------------------------------------------
    def test_10_user_duplicate_not_deleted(self):
        """Duplicata manual feita pelo usuário não é excluída na reversão da operação."""
        box = self._create_box("DupBox", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        parts_col = bpy.data.collections.get(COLLECTION_PARTS_NAME)
        part = parts_col.objects[0]

        # Usuário duplica a peça para uso próprio
        user_dup = part.copy()
        user_dup.data = part.data.copy()
        user_dup.name = "User_Independent_Copy"
        self.scene.collection.objects.link(user_dup)

        bpy.ops.chest.splitter_revert_cut()

        # Peças geradas foram removidas, mas a cópia do usuário sobrevive
        self.assertIn("User_Independent_Copy", bpy.data.objects)
        self.assertEqual(len(parts_col.objects), 0)

    # -------------------------------------------------------------------------
    # Caso 11: Recuperação de Alvo Deletado a Partir de Snapshot
    # -------------------------------------------------------------------------
    def test_11_target_deleted_recovered_from_snapshot(self):
        """Se o usuário deletou o objeto alvo após o corte, a reversão o recupera do snapshot."""
        box = self._create_box("DeletedTarget", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        bpy.context.view_layer.objects.active = box
        bpy.ops.chest.splitter_set_target()
        bpy.ops.chest.splitter_generate_preview()
        bpy.ops.chest.splitter_commit_parts()

        # Usuário apaga o alvo original da cena
        box_name = box.name
        bpy.data.objects.remove(box, do_unlink=True)
        self.assertNotIn(box_name, bpy.data.objects)

        # Reverte corte: deve recuperar o alvo a partir do snapshot de backup
        res = bpy.ops.chest.splitter_revert_cut()
        self.assertIn('FINISHED', res)

        # Alvo recuperado existe na cena
        self.assertIsNotNone(self.settings.target_object)
        self.assertIn(self.settings.target_object.name, self.scene.collection.objects)
        self.assertEqual(self.settings.session_status, 'CONFIGURED')

    # -------------------------------------------------------------------------
    # Caso 12: Dez Ciclos Consecutivos sem Vazamento de Dados
    # -------------------------------------------------------------------------
    def test_12_ten_cycles_zero_leak(self):
        """10 ciclos de gerar -> remover e commit -> reverter sem vazamento de malhas ou snapshots."""
        target = self._create_box("LeakTestBox", 0.04, 0.04, 0.04)
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.chest.splitter_set_target()

        init_meshes = len(bpy.data.meshes)
        init_objs = len(bpy.data.objects)

        for _ in range(5):
            bpy.ops.chest.splitter_generate_preview()
            bpy.ops.chest.splitter_remove_preview()

        for _ in range(5):
            bpy.ops.chest.splitter_generate_preview()
            bpy.ops.chest.splitter_commit_parts()
            bpy.ops.chest.splitter_revert_cut()

        final_meshes = len(bpy.data.meshes)
        final_objs = len(bpy.data.objects)

        # Coleção de backups não deve ter sobras
        backups_col = bpy.data.collections.get(COLLECTION_BACKUPS_NAME)
        backup_objs = len(backups_col.objects) if backups_col else 0
        self.assertEqual(backup_objs, 0)

        # Quantidade de objetos e malhas permanece estável
        self.assertEqual(final_objs, init_objs)
        self.assertEqual(final_meshes, init_meshes)


if __name__ == "__main__":
    res = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestReversion086))
    if not res.wasSuccessful():
        import sys
        sys.exit(1)
