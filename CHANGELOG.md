# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.4.0] - 2026-09-06

### Adicionado
- **Fase 3 — Cortador Sólido Personalizado**:
  - Módulo de geometria volumétrica (`src/geometry_solid.py`) para corte tridimensional usando cortadores fechados e manifold.
  - Quatro primitivas paramétricas integradas: Caixa (`BOX`), Cilindro (`CYLINDER`), Esfera (`SPHERE`) e Cápsula (`CAPSULE`), geradas diretamente na coleção de guias (`CHEST_SPLITTER_GUIDES`).
  - Suporte a Cortador Existente da cena: selecione qualquer malha fechada para atuar como ferramenta de corte volumétrico.
  - Validação estrita e bloqueante do cortador (`validate_solid_cutter`):
    - Rejeição imediata com feedback amigável para malhas não-manifold (arestas abertas, normais invertidas).
    - Verificação de volume nulo ou degenerado.
    - Teste de colisão por bounding box com o modelo alvo antes de qualquer computação booleana pesada.
  - Fatiamento volumétrico com solver EXACT booleano no espaço de mundo (`slice_mesh_by_solid`):
    - Parte A = Interseção ($Alvo \cap Cortador$).
    - Parte B = Diferença ($Alvo \setminus Cortador$).
    - Suporte nativo à inversão rápida de papéis ($A \leftrightarrow B$) via `invert_sides`.
  - Visualização explodida volumétrica interativa calculada ao longo do vetor entre os baricentros (centróides) das Partes A e B.
  - Atualização completa da Seção 2 da interface na Sidebar N com alternador de modo (Plano / Sólido), seleção de fonte, parâmetros do cortador e métricas de diagnóstico em tempo real (manifold, triângulos, volume e dimensões).
  - Suíte de 55 testes automatizados na Fase 3 (`tests/test_smoke_phase3.py`), totalizando 144 testes no projeto com 100% de aprovação no Blender 5.2 LTS.

## [0.3.1] - 2026-09-06

### Corrigido
- **Correção Crítica de Escala e Topologia de Encaixes**:
  - Eliminado bug onde `base_offset` (0.5) e `tip_r` (0.2) em `create_pin_mesh_data` eram interpretados diretamente em Blender Units (metros), gerando pinos e cavidades gigantes de 400 mm a 500 mm em cenas milimétricas/métricas.
  - O cálculo de `base_offset` e raio de chanfro `tip_r` agora é estritamente proporcional e invariante à escala da geometria (`min(eff_length * 0.05, eff_radius * 0.1)`).
  - Corrigido o traçado paramétrico da chave cápsula (`create_capsule_2d_profile`), eliminando auto-interseções em formato bowtie e garantindo malhas 100% manifold com normais consistentes para o solver EXACT booleano.
  - Padronização de `get_scene_scale_to_mm(scene)` em todo o ciclo de vida dos operadores para suporte transparente tanto a cenas em metros quanto em milímetros.
  - Adicionado teste automatizado de regressão no cubo de 97,2 mm do usuário (`test_smoke_phase2.py` Teste 10), garantindo dimensões exatas de 97,2 x 97,2 x 58,6 mm (macho) e 97,2 x 97,2 x 48,6 mm (fêmea) com 0 arestas não-manifold.

## [0.3.0] - 2026-09-06

### Adicionado
- **Fase 2 — Encaixes em Cortes Planos**:
  - Módulo paramétrico de conectores (`src/geometry_connectors.py`) para pinos cilíndricos com chanfro de entrada e chaves cápsula anti-rotação.
  - Convenção rigorosa de folga física: dimensão nominal exata no macho, expansão radial por lado na cavidade fêmea ($D + 2c$) e folga de fundo ($L + c_{fundo}$).
  - Quatro presets de calibração FDM para PLA e bico 0,4 mm: Justo (0,10 mm), Normal (0,15 mm), Fácil (0,20 mm) e Solto (0,25 mm), além de valor livre.
  - Distribuições automáticas no plano de corte: 1 pino (Centro), 2 pinos (Linha), 3 pinos (Linha) e 4 pinos (Grade 2x2), com margem de segurança configurável da borda externa.
  - Validações bloqueantes contra sobreposição entre encaixes e violação de margem de borda (`ConnectorValidationError`).
  - Operações booleanas robustas com solver EXACT no BMesh (`UNION` do macho e `DIFFERENCE` da cavidade).
  - Operador de inversão rápida de macho/fêmea (`chest.splitter_invert_male_female`) e seleção de presets (`chest.splitter_apply_connector_preset`).
  - Atualização completa da Seção 3 da interface na Sidebar N (`Viewport 3D -> Chest -> Part Splitter`).
  - Suíte de 34 testes automatizados na Fase 2 (`tests/test_smoke_phase2.py`) cobrindo aferição micrométrica, validação de todos os 4 presets, múltiplos pinos, chave cápsula e conservação de integridade manifold.

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
