"""Teste de Aceitação Formal - Etapa 5: UI Didática, Ajuda, Tradução e Estado Desatualizado (U1, U2)."""

import sys
import os
import bpy
import bmesh
from mathutils import Vector

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src
from src.translations import HELP_TOPICS, get_help_tooltip, get_help_popup_content, register_translations, unregister_translations


def assert_true(condition, message):
    if not condition:
        print(f"  [FALHA] {message}")
        sys.exit(1)
    print(f"  [OK] {message}")


def test_etapa5():
    print("=" * 70)
    print("INICIANDO SUÍTE DE TESTES: ETAPA 5 (UI, AJUDA, TRADUÇÕES E U1/U2)")
    print("=" * 70)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    src.register()

    # --- TESTE 1: U1 - Sistema de Ajuda e Tradução Contextual ---
    print("\n--- Teste 1: Sistema de Ajuda e Catálogo de Traduções (Critério U1) ---")
    topics_to_test = [
        "target_model",
        "split_plane",
        "split_loop",
        "loop_region",
        "loop_extrude",
        "connectors",
        "clearance",
        "explosion",
    ]

    for topic in topics_to_test:
        assert_true(topic in HELP_TOPICS, f"Tópico '{topic}' presente no catálogo HELP_TOPICS")
        tip = get_help_tooltip(topic)
        assert_true(bool(tip) and len(tip) > 10, f"Tooltip do tópico '{topic}' válido: '{tip[:30]}...'")
        title, lines = get_help_popup_content(topic)
        assert_true(bool(title) and len(lines) >= 2, f"Popup do tópico '{topic}' possui título e parágrafos explicativos")

    # Verifica execução do operador de ajuda
    op_res = bpy.ops.chest.splitter_help(topic="loop_region")
    assert_true('FINISHED' in op_res, "Operador chest.splitter_help executou com sucesso")

    # --- TESTE 2: U2 - Ciclo de Estado e Proteção PREVIEW_STALE ---
    print("\n--- Teste 2: Proteção de Estado PREVIEW_STALE e Bloqueio de Confirmação (Critério U2) ---")
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    # Cria cubo de teste 60x40x30
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    cube = bpy.context.active_object
    cube.dimensions = (0.060, 0.040, 0.030)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bpy.ops.chest.splitter_set_target()
    settings = scene.chest_splitter
    settings.split_mode = 'PLANE'
    settings.plane_origin = (0.0, 0.0, 0.0)
    settings.plane_normal = (0.0, 0.0, 1.0)
    settings.connector_enabled = False

    # Gera preview
    bpy.ops.chest.splitter_generate_preview()
    assert_true(settings.session_status == 'PREVIEW_VALID', "Preview gerado com status PREVIEW_VALID")
    assert_true(bpy.ops.chest.splitter_commit_parts.poll(), "commit_parts.poll() é True com PREVIEW_VALID")

    # Altera parâmetro de corte (ex: inverter lados)
    settings.invert_sides = True
    assert_true(settings.session_status == 'PREVIEW_STALE', "Alteração de corte transicionou para PREVIEW_STALE")
    assert_true(not bpy.ops.chest.splitter_commit_parts.poll(), "commit_parts.poll() bloqueia confirmação em PREVIEW_STALE")

    # Regenera preview para validar recuperação
    bpy.ops.chest.splitter_generate_preview()
    assert_true(settings.session_status == 'PREVIEW_VALID', "Novo preview restaurou status para PREVIEW_VALID")
    assert_true(bpy.ops.chest.splitter_commit_parts.poll(), "commit_parts.poll() reabilitado após atualização")

    # Altera parâmetro de encaixe (ex: diâmetro do conector)
    settings.connector_diameter_mm = 8.0
    assert_true(settings.session_status == 'PREVIEW_STALE', "Alteração em connector_diameter_mm transicionou para PREVIEW_STALE")
    assert_true(not bpy.ops.chest.splitter_commit_parts.poll(), "commit_parts bloqueado novamente")

    # --- TESTE 3: Auto-Ajuste Inteligente da Distância de Explosão ---
    print("\n--- Teste 3: Auto-Ajuste Inteligente da Distância de Explosão para Pinos ---")
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    tall_cube = bpy.context.active_object
    tall_cube.name = "TallCube"
    tall_cube.dimensions = (0.080, 0.080, 0.120)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.chest.splitter_set_target()

    settings.split_mode = 'PLANE'
    settings.plane_origin = (0.0, 0.0, 0.0)
    settings.plane_normal = (0.0, 0.0, 1.0)
    settings.connector_enabled = True
    settings.connector_diameter_mm = 6.0
    settings.connector_length_mm = 35.0  # Pino longo de 35 mm (cabe nos 60 mm disponíveis)
    settings.end_clearance_mm = 0.5
    settings.explosion_distance_mm = 30.0  # Menor que o comprimento do pino
    settings.view_mode = 'EXPLODED'

    bpy.ops.chest.splitter_generate_preview()
    assert_true(settings.session_status == 'PREVIEW_VALID', "Preview com encaixes gerado")

    expected_min_explosion = 35.0 + 0.5 + 15.0  # 50.5 mm
    assert_true(
        settings.explosion_distance_mm >= expected_min_explosion,
        f"Distância de explosão auto-ajustada para {settings.explosion_distance_mm:.1f} mm (>= {expected_min_explosion:.1f} mm)"
    )

    preview_a = scene.objects.get("CHEST_SPLITTER_PREVIEW_A")
    preview_b = scene.objects.get("CHEST_SPLITTER_PREVIEW_B")
    assert_true(preview_a is not None and preview_b is not None, "Partes de preview presentes")

    sep_distance = (preview_b.location - preview_a.location).length * 1000.0  # Em mm
    assert_true(
        abs(sep_distance - settings.explosion_distance_mm) < 1.0,
        f"Afastamento real na viewport ({sep_distance:.1f} mm) corresponde à distância de explosão configurada"
    )

    print("\n" + "=" * 70)
    print("TODOS OS TESTES DA ETAPA 5 PASSARAM COM 100% DE SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    test_etapa5()
