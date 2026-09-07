# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.2.0] - 2026-09-06

### Adicionado
- **Fase 1 — Corte por Plano**:
  - Módulo de geometria planar (`src/geometry_plane.py`) com bisect e fechamento manifold automático (*capping*) via `edgenet_fill` e `holes_fill`.
  - Objeto guia visual de plano na Viewport 3D (`CHEST_SPLITTER_PLANE_GUIDE`) redimensionado automaticamente ao tamanho do alvo.
  - Operador de alinhamento rápido do plano (`chest.splitter_align_plane`) por Vista 3D, Cursor 3D, Face selecionada e Eixos X/Y/Z.
  - Operador de geração de preview não destrutivo (`chest.splitter_generate_preview`) com cálculo instantâneo das Partes A e B.
  - Visualização Montada vs Explodida com controle interativo de distância de explosão em milímetros (`explosion_distance_mm`).
  - Alternador de inversão de lados (`chest.splitter_invert_sides`) para alternar papéis de A e B.
  - Diagnóstico em tempo real para as partes divididas (volumes, dimensões, verificação de manifold, número de componentes desconexos e conservação de volume).
  - Operador de confirmação (`chest.splitter_commit_parts`) que gera `<alvo>__A` e `<alvo>__B` na coleção `CHEST_SPLITTER_PARTS`.
  - Operador de restauração do original (`chest.splitter_restore_original`) e refazer sessão (`chest.splitter_redo_session`).
  - Suíte de 38 testes automatizados headless no Blender 5.2 (`tests/test_smoke_phase1.py`), incluindo cortes inclinados, alvo transformado, conservação de volume e prevenção de vazamento de memória em 20 ciclos de preview.

## [0.1.0] - 2026-09-06


### Adicionado
- **Fase 0 — Fundação da Extensão**:
  - Manifesto oficial de extensão para Blender 5.2+ (`blender_manifest.toml`).
  - Painel principal em `Viewport 3D -> Barra lateral (N) -> Chest -> Part Splitter`.
  - Operador para selecionar e registrar o objeto alvo (`chest.splitter_set_target`).
  - Diagnóstico em tempo real da malha: dimensões físicas em mm, contagem de triângulos e faces, volume.
  - Alertas automáticos para escala não aplicada, arestas não-manifold e faces degeneradas.
  - Operador seguro `Criar cópia de trabalho com transformações aplicadas` preservando 100% o modelo original.
  - Coleções dedicadas para isolamento: `CHEST_SPLITTER_GUIDES` e `CHEST_SPLITTER_PREVIEWS`.
  - Registro e ciclo de vida idempotentes.
  - Suíte de smoke tests automatizados em modo headless (`tests/test_smoke_phase0.py`).
