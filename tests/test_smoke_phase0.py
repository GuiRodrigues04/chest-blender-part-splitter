"""Suíte de smoke tests para Chest Part Splitter — Fase 0 (Fundação).

Executa os 7 testes mínimos exigidos pelo documento de arquitetura usando o Blender em modo headless (--background).
"""

import sys
import os
import tempfile
import bpy
import bmesh
from mathutils import Vector

# Adiciona a raiz do repositório ao path para importação direta
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src
from src.constants import (
    COLLECTION_GUIDES_NAME,
    COLLECTION_PREVIEWS_NAME,
    WORK_COPY_SUFFIX,
)
from src.diagnostic import analyze_target_mesh


def log_test(name, status="PASS", details=""):
    badge = "[PASS]" if status == "PASS" else "[FAIL]"
    print(f"{badge} {name} {details}")
    if status != "PASS":
        raise AssertionError(f"Teste falhou: {name} - {details}")


def run_all_tests():
    print("=" * 70)
    print("INICIANDO SMOKE TESTS - CHEST PART SPLITTER (FASE 0)")
    print(f"Blender Version: {bpy.app.version_string}")
    print(f"Python Version: {sys.version.split()[0]}")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # TESTE 1: Registrar, desregistrar e registrar novamente sem erros
    # -------------------------------------------------------------------------
    print("\n--- Teste 1: Ciclo de Registro e Idempotência ---")
    try:
        src.register()
        assert hasattr(bpy.types.Scene, "chest_splitter"), "Scene.chest_splitter não registrado"
        assert hasattr(bpy.ops.chest, "splitter_set_target"), "Operador splitter_set_target não registrado"
        assert hasattr(bpy.ops.chest, "splitter_clear_target"), "Operador splitter_clear_target não registrado"
        assert hasattr(bpy.ops.chest, "splitter_create_work_copy"), "Operador splitter_create_work_copy não registrado"

        src.unregister()
        assert not hasattr(bpy.types.Scene, "chest_splitter"), "Scene.chest_splitter não desregistrado"

        # Registra novamente
        src.register()
        log_test("1. Ciclo de vida e registro limpo da extensão", "PASS")
    except Exception as e:
        log_test("1. Ciclo de vida e registro", "FAIL", str(e))

    # -------------------------------------------------------------------------
    # TESTE 2: Diagnóstico de Cubo de 130 mm
    # -------------------------------------------------------------------------
    print("\n--- Teste 2: Medição Física e Diagnóstico de Cubo 130 mm ---")
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        src.register()

        scene = bpy.context.scene
        scene.unit_settings.system = 'METRIC'
        scene.unit_settings.scale_length = 0.001
        scene.unit_settings.length_unit = 'MILLIMETERS'

        # Cria cubo de 130 mm com transformações aplicadas
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=130.0)
        cube_mesh = bpy.data.meshes.new("Cube_130mm_Mesh")
        bm.to_mesh(cube_mesh)
        bm.free()

        cube_obj = bpy.data.objects.new("Cube_130mm", cube_mesh)
        scene.collection.objects.link(cube_obj)
        bpy.context.view_layer.objects.active = cube_obj
        cube_obj.select_set(True)

        bpy.ops.chest.splitter_set_target()
        settings = scene.chest_splitter

        assert settings.target_object == cube_obj, "Objeto alvo não atribuído"
        assert abs(settings.diag_dims_mm[0] - 130.0) < 0.1, f"Dimensão X incorreta: {settings.diag_dims_mm[0]}"
        assert abs(settings.diag_dims_mm[1] - 130.0) < 0.1, f"Dimensão Y incorreta: {settings.diag_dims_mm[1]}"
        assert abs(settings.diag_dims_mm[2] - 130.0) < 0.1, f"Dimensão Z incorreta: {settings.diag_dims_mm[2]}"
        assert settings.diag_triangles == 12, f"Contagem de triângulos esperada 12, obtido {settings.diag_triangles}"
        assert settings.diag_is_manifold, "Cubo fechado deve ser manifold"
        assert not settings.diag_has_unapplied_scale, "Escala 1.0 não deve acusar escala não aplicada"

        # Confirma existência das coleções dedicadas
        assert any(c.name == COLLECTION_GUIDES_NAME for c in scene.collection.children_recursive), "Coleção de guias ausente"
        assert any(c.name == COLLECTION_PREVIEWS_NAME for c in scene.collection.children_recursive), "Coleção de previews ausente"

        log_test("2. Cubo de 130 mm diagnosticado e aferido com precisão", "PASS")
    except Exception as e:
        log_test("2. Cubo 130 mm", "FAIL", str(e))

    # -------------------------------------------------------------------------
    # TESTE 3: Detecção de Escala Não Aplicada e Cópia de Trabalho Segura
    # -------------------------------------------------------------------------
    print("\n--- Teste 3: Detecção de Escala e Cópia Não Destrutiva ---")
    try:
        # Altera escala do cubo
        cube_obj.scale = Vector((2.0, 1.0, 0.5))
        bpy.context.view_layer.update()

        bpy.ops.chest.splitter_set_target()
        settings = bpy.context.scene.chest_splitter

        assert settings.diag_has_unapplied_scale, "Deveria detectar escala não aplicada"
        assert settings.diag_is_non_uniform_scale, "Deveria detectar escala não uniforme"

        # Cria cópia de trabalho com transformações aplicadas
        orig_name = cube_obj.name
        orig_scale = cube_obj.scale.copy()

        bpy.ops.chest.splitter_create_work_copy()

        # O alvo agora deve ser a cópia de trabalho
        work_copy = settings.target_object
        assert work_copy != cube_obj, "Alvo deveria ser a nova cópia de trabalho"
        assert work_copy.name.endswith(WORK_COPY_SUFFIX), "Nome da cópia deve ter sufixo de trabalho"
        assert abs(work_copy.scale.x - 1.0) < 1e-4, "Cópia deve ter escala aplicada (1.0)"
        assert abs(work_copy.scale.y - 1.0) < 1e-4, "Cópia deve ter escala aplicada (1.0)"
        assert abs(work_copy.scale.z - 1.0) < 1e-4, "Cópia deve ter escala aplicada (1.0)"
        assert not settings.diag_has_unapplied_scale, "Cópia de trabalho não deve ter aviso de escala"

        # Garante que o original permaneceu com a escala intacta e apenas oculto
        assert abs(cube_obj.scale.x - orig_scale.x) < 1e-4, "Original teve sua escala alterada indevidamente!"
        assert cube_obj.hide_viewport, "Original deveria estar oculto para evitar colisão visual"

        log_test("3. Detecção de escala não aplicada e geração de cópia segura", "PASS")
    except Exception as e:
        log_test("3. Escala e cópia de trabalho", "FAIL", str(e))

    # -------------------------------------------------------------------------
    # TESTE 4: Detecção de Malha Aberta / Não-Manifold
    # -------------------------------------------------------------------------
    print("\n--- Teste 4: Detecção de Arestas Abertas (Não-Manifold) ---")
    try:
        # Cria malha de plano aberto (4 arestas de contorno abertas)
        bm_open = bmesh.new()
        bmesh.ops.create_grid(bm_open, x_segments=2, y_segments=2, size=50.0)
        open_mesh = bpy.data.meshes.new("OpenPlaneMesh")
        bm_open.to_mesh(open_mesh)
        bm_open.free()

        open_obj = bpy.data.objects.new("OpenPlane", open_mesh)
        bpy.context.scene.collection.objects.link(open_obj)
        bpy.context.view_layer.objects.active = open_obj
        open_obj.select_set(True)

        bpy.ops.chest.splitter_set_target()
        settings = bpy.context.scene.chest_splitter

        assert not settings.diag_is_manifold, "Plano aberto não deve ser manifold"
        assert settings.diag_non_manifold_edges > 0, "Deve reportar arestas não-manifold"

        log_test("4. Detecção precisa de malha não-manifold e arestas abertas", "PASS")
    except Exception as e:
        log_test("4. Malha não-manifold", "FAIL", str(e))

    # -------------------------------------------------------------------------
    # TESTE 5: Persistência de Sessão no .blend
    # -------------------------------------------------------------------------
    print("\n--- Teste 5: Persistência no .blend ---")
    try:
        settings = bpy.context.scene.chest_splitter
        settings.session_id = "phase0_persist_test"
        settings.split_mode = 'SOLID'

        with tempfile.TemporaryDirectory() as tmp_dir:
            blend_path = os.path.join(tmp_dir, "phase0_session.blend")
            bpy.ops.wm.save_as_mainfile(filepath=blend_path)

            bpy.ops.wm.read_factory_settings(use_empty=True)
            src.register()
            bpy.ops.wm.open_mainfile(filepath=blend_path)

            reloaded = bpy.context.scene.chest_splitter
            assert reloaded.session_id == "phase0_persist_test", "session_id não persistiu"
            assert reloaded.split_mode == 'SOLID', "split_mode não persistiu"
            assert reloaded.target_object is not None, "target_object não persistiu"
            assert reloaded.target_object.name == "OpenPlane", "Ponteiro do alvo incorreto após reload"

        log_test("5. Persistência completa do estado e ponteiros no .blend", "PASS")
    except Exception as e:
        log_test("5. Persistência .blend", "FAIL", str(e))

    # -------------------------------------------------------------------------
    # TESTE 6: Robustez a Alvo Apagado ou Renomeado
    # -------------------------------------------------------------------------
    print("\n--- Teste 6: Robustez a Objeto Apagado ou Renomeado ---")
    try:
        target = bpy.context.scene.chest_splitter.target_object
        assert target is not None

        # 1. Renomeia o alvo
        target.name = "RenamedTarget"
        bpy.context.view_layer.update()
        settings = bpy.context.scene.chest_splitter
        assert settings.target_object.name == "RenamedTarget", "Ponteiro deve acompanhar renomeação"

        # 2. Apaga o alvo da cena
        bpy.data.objects.remove(target, do_unlink=True)
        bpy.context.view_layer.update()

        # Verifica se as operações de limpeza ou redefinição funcionam sem exceção
        bpy.ops.chest.splitter_clear_target()
        assert settings.target_object is None
        assert settings.session_status == 'EMPTY'

        log_test("6. Comportamento resiliente a objetos renomeados ou apagados", "PASS")
    except Exception as e:
        log_test("6. Objeto apagado/renomeado", "FAIL", str(e))

    # -------------------------------------------------------------------------
    # TESTE 7: 20 Ciclos de Criar/Limpar Estruturas sem Acúmulo de Dados
    # -------------------------------------------------------------------------
    print("\n--- Teste 7: 20 Ciclos de Criar/Limpar Estruturas ---")
    try:
        scene = bpy.context.scene
        initial_mesh_count = len(bpy.data.meshes)

        for i in range(20):
            # Cria cubo temporário
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=10.0)
            m = bpy.data.meshes.new(f"TempMesh_{i}")
            bm.to_mesh(m)
            bm.free()

            obj = bpy.data.objects.new(f"TempObj_{i}", m)
            scene.collection.objects.link(obj)
            bpy.context.view_layer.objects.active = obj

            # Define como alvo
            bpy.ops.chest.splitter_set_target()

            # Limpa alvo e remove objeto temporário
            bpy.ops.chest.splitter_clear_target()
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(m)

        final_mesh_count = len(bpy.data.meshes)
        assert final_mesh_count == initial_mesh_count, (
            f"Vazamento de malhas detectado: inicial {initial_mesh_count}, final {final_mesh_count}"
        )

        log_test("7. 20 ciclos de criação e limpeza concluídos sem vazamentos", "PASS")
    except Exception as e:
        log_test("7. Ciclos de limpeza", "FAIL", str(e))

    print("\n" + "=" * 70)
    print("TODOS OS TESTES DA FASE 0 PASSARAM COM SUCESSO! [100% OK]")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
