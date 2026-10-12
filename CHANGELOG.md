# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.8.8] - 2026-10-12

### Corrigido (Auditoria 0.8.7 e Plano 0.8.8)
- **C01, C02, C03 & V01-V04: Triangulação Ear Clipping 2D Robusta e Saliência por Base (BASE)**:
  - Eliminação de pontes e membranas em contornos côncavos (L/U) e polígonos colineares (4, 12, 20, 40 vértices) com preservação de todas as arestas de borda na triangulação.
  - No modo BASE ("Destacar saliência pela base"), remoção de lâminas coplanares e faces degeneradas: tanto a saliência destacada quanto o corpo receptor são gerados como sólidos 100% estanques (manifold) com tampas planas fechadas e conservação estrita de volume (\(\Sigma V_{\text{partes}} = V_{\text{original}}\)).
  - Rejeição e cancelamento controlado de polígonos de borda degenerados sem travamento do operador.
- **C04, C09, C10 & V06-V07: Vetores de Explosão Orientados e Invariância sem Deriva (Drift)**:
  - Sentido de explosão calculado estritamente para fora da interface em todos os modos (PLANE, LOOP, MATERIAL), garantindo afastamento mútuo das peças A e B em qualquer orientação espacial e rotação.
  - Cálculo de explosão baseado na matriz mundial montada original, eliminando realimentação cumulativa e deriva posicional (drift) mesmo após dezenas de ciclos alternados entre montado e explodido.
- **C05, C06, C07, C08 & V08-V12: Contrato e Calibração Fiel de Folga entre Peças**:
  - Folga axial na interface suportada exclusivamente nos modos PLANE e MATERIAL com validação contra espessura útil e volume remanescente (rejeição segura de folgas excessivas).
  - Em modos não suportados (LOOP, SOLID), os controles de folga são desabilitados com aviso informativo claro na interface de usuário.
  - Distinção exata entre aplicação unilateral (deslocamento $g$ na peça selecionada) e bilateral ($g/2$ em cada peça).
- **C11, C12, C13, C14, C15 & V13-V16: Fechamento de Corte e Linhas de Contorno**:
  - `cap_open_cut_boundaries` restrito às arestas geradas no plano de corte da operação atual, evitando fechamento indevido de orifícios pré-existentes do modelo original de entrada.
  - Deduplicação de segmentos coplanares e tangentes sem traçado de diagonais internas ou arestas nulas em faces côncavas.
  - Na visualização explodida, os contornos de corte são projetados sobre as coordenadas transformadas das peças associadas aos papéis `ROLE_PREVIEW_A` e `ROLE_PREVIEW_B`.
- **C16, C17, C18 & V17-V20: Encaixes, Grade OMBB e Herança Fiel de Materiais**:
  - Grade de pinos GRID_4 alinhada aos eixos principais da interface via Oriented Minimum Bounding Box (OMBB) com fator de escala seguro para retenção dos 4 conectores em domínios sólidos.
  - Pinos de encaixe herdam fielmente os materiais dos polígonos de contato por análise de área em World Space; em interfaces multimateriais, cada conector é avaliado individualmente.
  - Verificação de limites e footprint para conectores do tipo Cápsula evitando perfuração de cantos e paredes adjacentes.
- **C19, C20, C21, C22, C23, C24 & V21-V27: Atomicidade de Sessão, Ciclo de Vida e Assinatura**:
  - Resolução de ambiguidade com cancelamento estrito e sem fallback se objetos de sessões ou operações distintas forem selecionados simultaneamente.
  - Operador `splitter_restore_original` bloqueado em operações confirmadas (COMMITTED), exigindo o uso explícito de `splitter_revert_cut`.
  - Swap atômico de prévia: substituição e descarte da prévia anterior apenas após sucesso pleno de todos os cálculos geométricos e validações, restaurando estado íntegro em caso de exceção.
  - Assinatura de sessão completa cobrindo transformações, matrizes mundiais, materiais, modificadores e parâmetros de conectores (chanfro, folga axial e ajuste à área válida).
  - Avaliação fiel de modificadores em `compute_session_input_signature` preservando a visibilidade temporária do alvo oculto.
- **C25, C26, C27 & V28-V32: Exportação Atômica e Tratamento de Modificadores**:
  - Cancelamento explícito da exportação caso a avaliação de modificadores de qualquer peça falhe, prevenindo divergência entre a prévia e os arquivos finais em disco.
  - Publicação atômica em disco com diretório de staging, backup de arquivos existentes e rollback automático integral em caso de falha de I/O.
  - Exportação 3MF coleta recursos de cores e materiais da geometria avaliada com modificadores.
  - Exportação a partir de vista explodida restaura internamente as matrizes montadas de cada componente.
- **C28, C29, C30 & V33-V36: CLI, Testes de Estresse e Suíte 0.8.8**:
  - Tratamento unificado de argumentos CLI nos scripts `scripts/build.py` e `tests/run_all_tests.py` com e sem separador `--`.
  - Nova suíte oficial `tests/test_plan_088.py` com 36 testes cobrindo 100% da matriz de aceitação V01–V36.
  - Aprovação de 100% (23/23 suítes de testes) no Blender 5.2.0 LTS.

## [0.8.7] - 2026-10-11

### Corrigido (Pós-Testes 0.8.7)
- **C01 & C02: Modo BASE de Extração por Material e Conservação Estrita de Volume**:
  - Implementação do modo `BASE` ("Destacar saliência pela base") em `slice_mesh_by_material`: destaca o ressalto sólido íntegro com tampa plana fechada na base (ex: Z=100 mm), enquanto o corpo receptor mantém sua parede exterior plana restaurada com o material original adjacente, eliminando o núcleo interno oco e lâminas espúrias.
  - Conservação de volume total garantida (\(\Sigma V_{\text{partes}} = V_{\text{original}}\)) sem resíduos ou fragmentos desconexos na cena.
  - Modo `EXTRUDE` preservado para corte de cavidades e regiões planas (M03).
- **C03: Calibração de Folga entre Peças (part_clearance_mm) e Assinatura de Sessão**:
  - Alívio dimensional calibrado aplicado axialmente na interface de contato montada (`PART`, `CAVITY` ou `BOTH`), com validação prévia da espessura útil do sólido (rejeitando folgas \(\ge \text{espessura} - 0.1\text{ mm}\)).
  - Parâmetros `part_clearance_mm`, `part_clearance_apply_to`, `material_extraction_mode` e `material_interface_mat_mode` integrados à assinatura de sessão (`compute_session_input_signature`).
- **C04: Linhas de Corte Face a Face e Vista Explodida**:
  - Interseção calculada estritamente face a face via `_compute_cut_line_segments`, eliminando conexões espúrias ou diagonais que cruzavam o vazio entre ilhas desconexas.
  - Na visualização explodida (`EXPLODED`), o plano flutuante no vácuo é ocultado e os contornos de corte são desenhados diretamente sobre as interfaces deslocadas das peças A e B.
- **C05: Grade GRID_4 em Seções Rotacionadas (OMBB) e Escala Segura**:
  - Algoritmo de Oriented Minimum Bounding Box (OMBB) para alinhamento automático da grade de 4 pinos aos lados reais do quadrado/retângulo, mesmo com rotação de 45° ou eixos arbitrários no plano da interface (`Demonstracao_Grade_4.py`).
  - Busca determinística de escala segura (passos de 0.55 a 0.15) acomodando todos os 4 pinos com margem de segurança dentro do domínio sólido.
- **C06: Herança Fiel de Material nos Pinos por Área em World Space**:
  - Pinos machos herdam fielmente o material da peça dona (ex: peça amarela gera pinos amarelos). Em interfaces multicoloridas ou ambíguas, o material é selecionado pela maior soma de área de faces em World Space (não por contagem de polígonos).
- **C07: Resiliência em Falha de Atualização de Prévia e Bloqueio de Ações**:
  - Quando uma atualização de parâmetros falha e a prévia anterior é preservada, um aviso persistente em destaque de alerta é exibido no painel ("Aviso: A última atualização falhou..."), bloqueando as operações de confirmação (`commit_parts`) e exportação (`export_parts`) até que a configuração seja válida.

### Corrigido (Fase Inicial 0.8.7)
- **B11 & P02/P03: Eliminação de Lâmina Coplanar no Alinhamento por Face**:
  - Classificação física pré-corte de faces coplanares e remoção seletiva da película e faces degeneradas da outra metade na peça retida. Em alinhamentos pela face de apoio, a saliência é gerada com contorno fiel e tampa fechada de base (ex: 30x30x20 mm), sem duplicar a face exterior da base (100x100 mm) nem produzir película de espessura zero.
  - Operador `CHEST_OT_splitter_align_plane` com validação estrita de Edit Mode e face ativa única no alvo, emitindo cancelamento controlado sem falso sucesso.
- **B05 & L01/L02: Triangulação Ear Clipping 2D em Contornos Côncavos (U/L)**:
  - Algoritmo de triangulação por Ear Clipping 2D implementado para as tampas do prisma cortador de loop, garantindo que 100% dos triângulos permaneçam estritamente dentro do domínio sólido sem gerar pontes ou membranas que atravessavam o vazio.
  - Diagnóstico fiel de espessura (`thickness_determined`) sem recurso ao fallback arbitrário de 1000 mm quando a região aberta não encontra parede oposta.
- **B06 & D2: Encaixes em Domínios Côncavos e Ajuste à Área Válida**:
  - Implementada função de amostragem determinística da área sólida útil (polo de inacessibilidade) ativada por `adjust_to_valid_area`. Quando a distribuição `CENTER` cairia no vazio ou furos de formatos em U ou anéis, reposiciona o conector na região com maior margem física útil das bordas.
  - Correção na função `build_cut_interface` para aceitar explicitamente origem `Vector((0,0,0))` válida sem sobrescrever pelo centroide.
- **B03: Desalocação Estrita de Recursos e Limpeza de Memória**:
  - Blocos `finally` sistemáticos com `eval_obj.to_mesh_clear()` aplicados ao mesmo objeto avaliado gerador em todas as rotinas de corte por loop e material, evitando vazamento de malhas em depurações sucessivas.
- **B04 & T23: Rastreamento Completo de Cortador no Depsgraph**:
  - O manipulador `depsgraph_update_post` monitora transformações e topologia tanto do alvo quanto do cortador (`cutter.matrix_world`), marcando `PREVIEW_STALE` quando o cortador é movido individualmente.
- **B12, B13, B14 & B15: Atomicidade e Isolamento do Ciclo de Vida**:
  - `capture_target_snapshot`: Procedimento transacional criando um candidato validado antes de substituir snapshots legados.
  - `discard_target_snapshot`: Checagem rigorosa de propriedade (`chest_role` e `chest_operation_id`), rejeitando objetos do usuário com mesmo nome.
  - `resolve_operation`: Detecção de seleção ambígua quando objetos de operações distintas são selecionados simultaneamente, retornando `None`.
  - `check_child_operations`: Bloqueio de reversão de operação pai se houver operações filhas confirmadas OU prévias de filhas ativas.
  - `revert_committed_operation`: Restauração fiel de alvos deletados clonando o snapshot com modificadores preservados.

### Adicionado
- **Etapa E (E01) — Folga Física entre Peças**:
  - Propriedades `part_clearance_mm` e `part_clearance_apply_to` ('PART', 'CAVITY', 'BOTH') permitindo alívio dimensional calibrado entre as peças cortadas para montagem física justa pós-impressão 3D.
- **Etapa C (C01-C03) — Modos de Extração por Material**:
  - Propriedades `material_extraction_mode` ('EXTRUDE' vs 'BASE') e `material_interface_mat_mode` ('SOURCE' vs 'EXTRACTED') permitindo destacar a saliência inteira pela base ou extrair com profundidade nominal.
- **Etapa F (F01-F02) — Visualização GPU Aprimorada e Isolada**:
  - Prévia visual do corte planar com preenchimento translúcido e linha de corte contrastante no contorno do modelo alvo.
  - Salvamento e restauração estrita do estado gráfico do Blender (`gpu.state`) em bloco `finally`, prevenindo interferências no renderizador da viewport.
  - Separação estrita de visualizadores por modo (`LOOP` vs `PLANE`) com leitura de BMesh em tempo real no Modo de Edição.

## [0.8.6] - 2026-10-10

### Corrigido
- **B01: Seleção por Face Confiável no Objeto Correto**:
  - Restrição estrita do operador `pick_material_region` ao objeto alvo em Modo de Edição (`context.edit_object == target`), impedindo interferência de objetos de prévia ou outros elementos na cena.
  - Rejeição determinística e amigável quando múltiplos objetos estão em edição ou quando não há face ativa válida identificável.
  - Atualização automática dos slots e regiões de material diretamente a partir da topologia atual em edição.
- **B02: Estabilidade e Prevenção de Crash em Undo/Redo**:
  - Remoção de alocação de malhas avaliadas (`eval_obj.to_mesh()`) de dentro do handler `depsgraph_update_post`, eliminando a causa raiz de falhas de segmentação e referências mortas em operações de desfazer/refazer.
  - Handlers dedicados `on_undo_post` e `on_redo_post` registrados com verificação leve e proteção contra `ReferenceError`.
  - Guard global de execução `_is_generating_preview` prevenindo reentrâncias descontroladas durante o pipeline booleano.
- **B03: Geração de Prévia Segura e Transacional com Rollback**:
  - Criação de malhas e objetos em namespace isolado de candidatos (`_cand_{exec_id}_...`).
  - Em falhas intermediárias do corte, da topologia ou dos pinos, a prévia existente é preservada intacta (sinalizada como `PREVIEW_STALE`) e os candidatos transitórios são purgados sem deixar resíduos na cena.
  - Swap e limpeza da prévia anterior executados unicamente após 100% de sucesso.
- **B04 & B05: Reconstrução Ordenada do Contorno no Corte Planar e Múltiplos Encaixes**:
  - Função `reconstruct_boundary_loops` ordenando arestas de corte em loops cíclicos fechados orientados pela conectividade real do BMesh.
  - Classificação robusta em contornos externos e furos (`outer_contours_uv` e `hole_contours_uv`) via inclusão 2D ponto-em-polígono.
  - Eliminação de falsos negativos de encaixes: teste de footprint com amostragem perimétrica multiponto garantindo posicionamento exato de 2 ou mais pinos sem colisões espúrias.
- **B06: Eliminação Definitiva da Película na Extração por Material**:
  - Nova geração de cortador prismático `create_material_patch_prism_cutter` duplicando a topologia exata das faces da região para compor as tampas e extrudando paredes exclusivamente no perímetro de fronteira.
  - Eliminação total de n-gons planos que atravessavam concavidades abertas, preservando o rebaixo complementar na Parte B e gerando a Parte A como sólido estanque (0 arestas não-manifold).
- **Integridade e Confiabilidade de Exportação**:
  - Transação atômica em diretório de staging temporário para exportações STL por material e STL por peças: arquivos só são publicados na pasta de destino após validação de 100% dos itens gerados.
  - Função `sanitize_unique_filename` prevenindo sobrescrita silenciosa de arquivos quando nomes de peças geram nomes de arquivos idênticos.
  - Avaliação fiel de modificadores (`apply_modifiers=True`) durante a checagem prévia de solidez imprimível.

### Adicionado
- **F01: Destaque Persistente do Contorno no Viewport (GPU Overlay)**:
  - Módulo `src/gpu_drawing.py` renderizando o anel de arestas capturado em ciano dinâmico via callback de viewport do Blender (`SpaceView3D.draw_handler_add`).
  - Suporte completo a transformações e posições do objeto alvo na viewport.
  - Propriedade e controle na interface `show_loop_highlight` para alternar a exibição.
- **F02: Captura do Contorno Perimetral a partir de Seleção de Faces**:
  - Função `capture_face_boundary_loop` em `src/geometry_loop.py` e operador `chest.splitter_capture_face_boundary` ("Capturar das Faces").
  - Identificação de arestas de fronteira com incidência de exatamente uma face selecionada, validação de ciclo simples conexo e rejeição de ilhas, furos ou seleção total da malha.
  - Definição automática da semente para a Parte A a partir de face válida da seleção.
- **F03: Remoção de Prévia e Reversão Segura de Cortes**:
  - Operador `chest.splitter_remove_preview` ("Remover Prévia") permitindo descarte imediato da geometria de prévia sem perder a cópia de trabalho nem edições do usuário no alvo, com reativação e seleção do alvo na viewport.
  - Operador `chest.splitter_revert_cut` ("Reverter este corte") com diálogo nativo de confirmação exibindo o modelo alvo e a contagem de peças afetadas, desfazendo o corte confirmado, removendo as peças geradas/subpeças e restaurando o modelo alvo ao seu estado pré-corte.
  - Modelo persistente com `ChestOperationRecord` e `ChestObjectRef` vinculado a `Scene.chest_operations` e `active_operation_id` para rastreamento por UUID e estados de ciclo de vida (`PREVIEW`, `COMMITTED`, `REVERTED`, `BROKEN`).
  - Coleção interna oculta `CHEST_SPLITTER_BACKUPS` para snapshots intactos de malha base, permitindo restauração mesmo se o usuário tiver apagado acidentalmente o objeto alvo após a confirmação.
  - Bloqueio hierárquico determinístico (`check_child_operations`): proteção contra reversão de corte pai quando existem cortes filhos confirmados ativos, com mensagem explicativa ao usuário.
  - Proteção de duplicatas manuais feitas pelo usuário e rastreamento de peças renomeadas ou movidas para outras coleções.
- **Suíte de Testes Comercial & Reversão (20 Suítes / 100% OK)**:
  - Bateria completa de 20 suítes de testes automatizados cobrindo os 24 casos comerciais e os 12 casos do plano de reversão (`tests/test_reversion_086.py`), incluindo teste de estresse de 10 ciclos consecutivos com zero vazamento de malhas ou snapshots.

## [0.8.5] - 2026-10-09

### Corrigido
- **Isolamento e Preservação de Cópias de Trabalho (Seção 2 / R01-R02)**:
  - Criação da coleção dedicada `CHEST_SPLITTER_WORK` para cópias de trabalho e atribuição de metadados `chest_role="WORK_COPY"`.
  - Reformulação de `cleanup_collection_objects`: garantia de tolerância zero à remoção do objeto alvo, cópias de trabalho ou malhas do usuário durante atualizações sucessivas de prévia. Migração automática de cópias legadas.
  - Implementação de restauração segura em `CHEST_OT_splitter_restore_original` reativando a visibilidade do modelo base original (`hide_set(False)` e `hide_viewport=False`), reatribuindo `target_object` e limpando a cópia de trabalho sem deixar datablocks órfãos.
- **Contrato Físico em Milímetros & Retornos do Operador (Seção 3 / R03-R04)**:
  - Adição de retorno explícito `{'FINISHED'}` e caminhos determinísticos de cancelamento `{'CANCELLED'}` em `CHEST_OT_splitter_export_parts`.
  - Padronização física em milímetros para STL (`global_scale=unit_scale`, `use_scene_unit=False`, `apply_modifiers=True`), garantindo que modelos exportados mantenham dimensões idênticas ao 3MF em qualquer escala de cena (`scale_length = 1.0`, `0.01` ou `0.001`).
  - Padronização em milímetros para exportação Wavefront OBJ (`global_scale=unit_scale`, 1 unidade = 1 mm).
  - Remoção de diretórios Windows/OneDrive fixos; fallback inteligente para diretório da cena salva, Desktop do usuário ou pasta temporária do sistema.
  - Alinhamento canônico na exportação de prévias: objetos na visualização explodida são temporariamente exportados na posição original montada `(0, 0, 0)` com restauração transparente da visualização na viewport em bloco `finally:`.
  - Escaping XML com `html.escape` em `build_3mf_xml` para suporte total a nomes de objetos com aspas, e-comercial (`&`) e colchetes angulares (`<`, `>`).
  - Gravação atômica de arquivos 3MF via arquivo temporário `.tmp` e `os.replace` para evitar corrupção ou perda de arquivos pré-existentes em falhas de escrita.
- **Isolamento de Sessões & Invalidação de Prévias (Seções 4 e 5 / R05-R08)**:
  - Geração de identificadores únicos UUID para cada sessão de corte.
  - Assinatura determinística SHA-256 (`session_input_signature`) rastreando transformações, posições, rotações, escalas, contagens e amostras geométricas do alvo e cortadores, além de escala de cena e parâmetros de corte.
  - Invalidação automática (`PREVIEW_STALE`) e bloqueio preventivo de confirmação/exportação quando o alvo ou cortador forem movidos ou alterados na viewport.
  - Handler de depsgraph (`on_depsgraph_update_post`) monitorando alterações em tempo real sem loops de redesenho.
  - Independência da vista explodida e modos de cor em relação à assinatura geométrica do corte.
  - Função centralizada `get_current_session_parts` garantindo que exportações e separações por material processem exclusivamente peças da sessão ativa, preservando cortes anteriores na mesma cena.
- **Validação Geométrica e Tolerâncias de Encaixe (Seção 6 / R11-R12)**:
  - Auto-ajuste de comprimento de conectores cápsula (`adjusted_capsule_length_mm` e `max_safe_lateral_mm`) para interfaces estreitas sem falha prematura da operação.
  - Amostragem perimétrica multiponto em `check_receiving_wall_thickness` para detecção de perfurações em paredes inclinadas e diagnóstico de ausência de corpo receptor (`hit_loc is None`).
  - Verificação de malhas válidas e imprimíveis antes de confirmar ou exportar peças, bloqueando a exportação de cascas abertas como sólidos individuais.
- **Internacionalização & Correção de Localização (Seção 8 / R16)**:
  - Correção de `_get_current_locale()` para retornar `pt_BR` apenas quando o locale do Blender iniciar com `pt`, adotando `en_US` como padrão internacional nos demais casos.
  - Correção de caracteres UTF-8 no manifesto e `__init__.py`.

### Adicionado
- Nova suíte de testes de regressão automatizada cobrindo os 18 requisitos de aceite (`tests/test_final_plan_corrections.py`).

## [0.8.4] - 2026-10-09

### Corrigido
- **Corte por Material com várias áreas da mesma cor**: cada área separada (ilha) agora é uma região independente, com contorno e direção próprios. Antes, duas áreas da mesma cor eram misturadas num único contorno inválido, gerando peças deformadas.
- **Seleção da cor base**: escolher o material do corpo (que envolve as outras áreas) agora mostra um aviso claro em vez de gerar um corte quebrado.
- **Vista explodida no modo Material**: as peças se afastam na direção real da extração (peça sai, corpo recua), e a distância é ajustada automaticamente para a peça sair totalmente da cavidade.
- **Prisma de extração**: pontos colineares do contorno são removidos, corrigindo malhas não-manifold e volume errado em áreas com mais de uma face (afeta também o Loop com profundidade).

### Adicionado
- Lista de "Áreas" quando uma cor aparece em vários lugares e botão **Usar Face Selecionada (Edit Mode)**.

## [0.8.3] - 2026-10-08

### Adicionado
- **Corte por Material com Contrato Estrito de Sólidos Estanques (Etapa 6 / Seção 9)**:
  - Criação do módulo `src/geometry_material.py` com análise topológica estrutural (`analyze_material_structure`) e corte determinístico (`slice_mesh_by_material`).
  - Distinção automática entre **Componentes Fechados** (`CLOSED_COMPONENT`, ex: corpos desconexos com materiais dedicados) e **Regiões Superficiais** (`SURFACE_PATCH`, ex: decalques ou faces pintadas em superfície contínua).
  - Componentes isolados são separados diretamente preservando manifoldness estrita (0 arestas abertas).
  - Superfícies contínuas com materiais diferentes são extraídas através de projeção prismática com profundidade física ajustável (`material_extrude_depth_mm`), gerando uma peça sólida inserível e a cavidade receptora correspondente no corpo principal.
  - Preservação estrita de slots de materiais e índices de faces em ambas as partes (Critério M1).
- **Diagnóstico e Alerta contra Cascas Abertas em `separate_object_by_material`**:
  - Detecção e registro de `open_edges`, `is_manifold` e `is_solid_for_printing` em sub-peças geradas por simples separação de faces.
  - Aviso explicativo na interface e no operador indicando quando cascas abertas não-imprimíveis foram geradas, orientando o usuário a utilizar o corte por Material com Profundidade.
- **Identidade e Coexistência de Estado (Seção 8)**:
  - Adição do alias `scene.part_splitter` apontando diretamente para `scene.chest_splitter`, permitindo interoperabilidade com novas APIs e migração progressiva.
- **Bateria de Testes Automatizados (Etapa 6)**:
  - Adição da suíte `tests/test_acceptance_etapa6_material.py` cobrindo separação manifold de componentes fechados, extração volumétrica de superfícies contínuas com conservação de volume, Critério M1, detecção de cascas e alias de cena (14/14 suítes aprovadas com 100% de sucesso).

## [0.8.2] - 2026-10-08

### Adicionado
- **Reorganização Didática da Interface e Fluxo Linear (Etapa 5 / Seção 7.1)**:
  - Estruturação do painel em 6 seções lógicas: (1) Objeto Alvo, (2) Método de Corte, (3) Encaixes & Folgas, (4) Prévia do Corte, (5) Criar Peças e (6) Exportação.
  - A Seção 3 (Encaixes) foi posicionada antes do botão de geração da Prévia, respeitando o fluxo natural de que os encaixes alteram a geometria gerada.
  - Remoção de todos os jargões técnicos confusos (ex: "Fase 3A", "Modo D", "Face Semente: 19").
  - Adição de instruções claras no modo Contorno: *"Dica: Selecione apenas 1 face dentro da região desejada (o contorno delimita a seleção automaticamente)"*.
- **Sistema de Ajuda Contextual e Popups Didáticos (`src/translations.py` & `CHEST_OT_splitter_help`)**:
  - Implementação de botões de ajuda compactos com ícone `INFO` em cada seção e recurso principal.
  - Ao passar o mouse, exibe tooltips explicativos detalhados para iniciantes.
  - Ao clicar no botão `INFO`, abre um popup menu legível (`popup_menu`) detalhando o funcionamento, recomendações práticas e exemplos de uso em milímetros.
  - Catálogo nativo de tradução bilíngue (`pt_BR` e `en_US`) registrado via `bpy.app.translations`.
- **Proteção Transacional de Estado Desatualizado (`PREVIEW_STALE` / Critério U2)**:
  - Alterações em qualquer parâmetro de corte ou de encaixe após um preview válido marcam a sessão automaticamente como `PREVIEW_STALE`.
  - Exibição de aviso claro em destaque: *"Os ajustes mudaram. Atualize a prévia antes de criar as peças."*
  - Bloqueio preventivo do botão de confirmação (`commit_parts.poll() == False`) até que o usuário clique em "Gerar / Atualizar Preview", prevenindo inconsistências.
- **Auto-Ajuste Inteligente da Distância de Explosão para Pinos Longos**:
  - Ao gerar a prévia com encaixes ativados, a extensão calcula dinamicamente a distância mínima necessária para que o pino e a cavidade se desacoplem totalmente ($\text{Inserção} + \text{Folga de fundo} + 15\text{ mm}$).
  - Caso o slider de explosão esteja menor que essa medida, ele é elevado automaticamente para garantir visualização perfeita do pino 100% fora do furo na vista explodida.
- **Bateria de Testes U1/U2 (`tests/test_acceptance_etapa5_ui.py`)**:
  - Testes cobrindo integridade do catálogo de ajuda, execução do operador, transição de `PREVIEW_STALE` com bloqueio de commit, e auto-ajuste da visão explodida (13/13 testes aprovados).

## [0.8.1] - 2026-10-08

### Corrigido
- **Correção da Avaliação do Depsgraph Booleano em Atualização de Preview (`geometry_loop` & `geometry_solid`)**:
  - Correção de bug crítico onde `temp_obj_a`, `temp_obj_b`, `cutter_obj` e objetos de trabalho herdavam `hide_viewport = True` do objeto original ocultado após a primeira geração de preview.
  - No Blender 4.x/5.x, o Dependency Graph (`evaluated_depsgraph_get()`) ignora silenciosamente a avaliação de modificadores booleanos para economizar recursos caso o objeto esteja oculto na viewport (`hide_viewport = True`).
  - Como consequência, ao ajustar parâmetros (ex: profundidade do corte ou corte passante) e atualizar o preview, as operações booleanas retornavam a malha original inteira para ambas as partes (duplicando o bloco sem corte e causando Z-fighting).
  - Todos os objetos de trabalho temporários agora forçam explicitamente `hide_viewport = False` e `hide_render = False` antes da resolução booleana, garantindo corte perfeito e determinístico em qualquer reexecução de preview.
  - Adicionado teste de aceitação automatizado de regressão (`tests/test_verify_bug_and_fix.py`) integrado à suíte de testes.

## [0.8.0] - 2026-10-08

### Adicionado
- **Extração Plana com Profundidade (Modo Loop `EXTRUDE`)**:
  - Projeção prismática fechada e manifold do contorno capturado para dentro do modelo até a profundidade física $d$.
  - Preservação estrita de concavidades e relevos superficiais com extensão externa de segurança anti-coplanaridade.
  - Verificação automática de espessura de parede via `BVHTree.ray_cast` para prevenção de perfuração acidental.
  - Opção explícita de **Corte Passante** (`loop_through_cut`) para furos passantes limpos e contínuos.
- **Decisão Automática Inteligente (Modo Loop `AUTO`)**:
  - Análise geométrica em tempo real do relevo da região selecionada em relação ao plano médio.
  - Seleção automática entre **Destacar Saliência** (`DETACH`) e **Extrair com Profundidade** (`EXTRUDE`) acompanhada de justificativa didática em texto na interface.
- **Contrato Formal de Geometria (`CutInterface` & `SplitResult`)**:
  - Padronização em World Space de todas as operações de corte, eixos principais (U/V) via PCA, dimensões reais da interface e normais de contato.
  - Invariância topológica estrita à ordem dos vértices no contorno fechado.
- **Encaixes Transacionais Robustos e Tolerâncias Perfeitas**:
  - Perfil de cápsula com tangentes fechadas e folga perimetral estritamente uniforme em toda a periferia.
  - Validação de espessura de parede na peça receptora (`check_receiving_wall_thickness`) antes de qualquer alteração na malha.
  - Validação de inclusão em polígonos côncavos e detecção de furos internos para evitar encaixes no vazio.
  - Rollback atômico em caso de falha booleana, impedindo estados parciais e protegendo a integridade da cena.
  - Proteção de estado contra operações pós-confirmação (`COMMITTED`).
- **Bateria Completa de Testes de Aceitação Formal**:
  - 11 suítes de testes automatizados integradas cobrindo P1-P2, L1-L5, G1-G2, C1-C5 e E1-E3 com 100% de aprovação no Blender 5.2.0 LTS.

## [0.7.0] - 2026-09-28

### Adicionado
- **Controle de Comprimento Lateral de Encaixes Tipo Cápsula (`connector_capsule_length_mm`)**:
  - Nova opção na Seção 3 para expandir a largura lateral dos pinos oblongos/cápsula ao longo do plano de corte.
  - Folga física uniforme (offset radial) em toda a periferia do encaixe fêmea (tanto na espessura quanto no comprimento lateral alargado).
  - Chanfro perimetral proporcional com offset uniforme nas extremidades.
  - Alinhamento de orientação determinístico: o eixo maior da cápsula acompanha a direção longitudinal da interface de corte e a linha de pinos.
- **Sistema de Limites Coerentes Anti-Colisão (`compute_connector_layout` & `connector_max_safe_lateral_mm`)**:
  - Cálculo automático em tempo real da distância entre centros de encaixes vizinhos, deduzindo folgas e garantindo uma parede sólida mínima de segurança entre cavidades adjacentes.
  - Cálculo da margem segura em relação à borda externa da peça (`edge_margin_mm`).
  - Exibição do limite seguro máximo diretamente na interface do Blender.
  - Ajuste protetor automático (clamping) com aviso amigável quando o valor inserido ultrapassar o limite seguro, prevenindo erros booleanos ou contato indevido.
- **Nova Suíte de Testes Automatizados**:
  - Adicionado `tests/test_capsule_lateral_size.py` cobrindo geometria, folgas uniformes, limites matemáticos, detecção de colisão e corte completo (8/8 suítes aprovadas).

## [0.6.1] - 2026-09-28

### Corrigido & Aprimorado
- **Orientação e Inversão de Encaixes (Macho / Fêmea)**:
  - Corrigido cálculo do vetor normal dos encaixes quando `invert_sides` está ativo (`effective_normal_a`), evitando que pinos fossem gerados voltados para o interior do modelo.
  - Adicionada detecção geométrica automática de qual parte é Superior e qual é Inferior com base na coordenada Z de mundo.
  - Adicionado botão direto de inversão de encaixes na Seção 2 (`Inverter Pinos: Macho na Parte Superior / Inferior`).
  - Adicionado seletor visual e botão de inversão detalhado na Seção 3 com indicação textual imediata de status.

## [0.6.0] - 2026-09-28

### Adicionado
- **Suporte Completo a Modelos Multicores e Materiais**:
  - Preservação estrita de todos os slots de materiais e índices de faces originais durante cortes nos modos Plano (`PLANE`), Cortador Sólido (`SOLID`) e Loop Fechado (`LOOP`).
  - Atribuição inteligente de materiais nas tampas de interface de corte (capping faces), herdando automaticamente o material predominante das faces vizinhas imediatas.
  - Sincronização de materiais em pinos e cavidades de encaixe, prevenindo a criação de slots nulos (`None`) após operações booleanas.
- **Alternador de Modo de Exibição de Cores na Viewport (`preview_color_mode`)**:
  - Modo `Cores Originais (Materiais)`: exibe fielmente as cores, materiais e shaders originais do modelo.
  - Modo `Cores A / B (Contraste)`: destaca Parte A (Azul) e Parte B (Laranja) para inspeção geométrica rápida.
- **Operador "Separar Peças por Cores / Materiais" (`chest.splitter_separate_by_material`)**:
  - Divide qualquer peça multicolor em sub-objetos individuais por material/cor, mantendo o alinhamento espacial perfeito para impressão multicolor em sistemas tipo AMS / MMU.
- **Módulo de Exportação Direta para Fatiadores (`src/io_export.py` e `chest.splitter_export_parts`)**:
  - Exportação nativa em **3MF Multimaterial (.3mf)** com `<m:colorgroup>` compatível com Bambu Studio, OrcaSlicer e PrusaSlicer.
  - Exportação em **STLs por Material / Cor (.stl)** com coordenadas globais alinhadas para importação como objeto multipartes.
  - Exportação em **Wavefront OBJ (.obj + .mtl)**.
- **Correção de Interface**:
  - Botão de Gerar Preview, visualização e confirmação de divisão habilitados também para o Modo Loop Fechado (`LOOP`).
- **Suíte de Testes Automatizados**:
  - Adicionado `tests/test_multicolor_support.py` cobrindo cortes planares, sólidos, encaixes com materiais, separação por material e exportação para 3MF e STL. Total de 7 suítes com 100% de aprovação no Blender 5.2 LTS.

## [0.5.0] - 2026-09-08

### Adicionado
- **Fase 3A — Modo Loop Fechado de Arestas**:
  - Captura e validação de loop de arestas em Edit Mode (`capture_edge_loop`).
  - Separação direta da geometria (Caminho D1) por região e face-semente (`slice_mesh_by_loop`).
  - Fechamento manifold de tampas internas compartilhadas.

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
