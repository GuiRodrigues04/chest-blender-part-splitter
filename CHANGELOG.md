# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

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
