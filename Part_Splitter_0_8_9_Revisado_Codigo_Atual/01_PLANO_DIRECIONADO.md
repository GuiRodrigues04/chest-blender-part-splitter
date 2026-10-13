# Auditoria atual e plano dirigido de implementação

## 1. Identidade da base

Manifesto recebido: version 0.8.9, mínimo Blender 4.2.0. Changelog 0.8.9 descreve INV-001–006 e afirma28/28 suítes Blender 5.2. Não executamos essa suíte neste ambiente e essa afirmação não demonstra cobertura de INV-008–014.

Análise: fontes src, lifecycle, testes relacionados e runner; comparação com requisitos e cenas já lidas. Referências de função/linha atuais em04_MAPA_CODIGO_ATUAL.md. Não editar por números de linha de planos antigos.

Esta revisão deve completar a 0.8.9 pedida, preservando o que já existe. Não sugerir migração para 0.8.6 ou recriar módulos resolvidos.

## 2. Estado por requisito

| Requisito | Estado observado no código atual | Próximo passo |
|---|---|---|
| INV-008 | Folga implementada só na profundidade, inclusive BASE com shift axial | Acrescentar offset lateral no domínio de contato e semântica por lado |
| INV-009 | Cortador usa translação única de patch; não há proposta caixa de quina | Diagnóstico de cunhas + caixa revisável restrita + ferramentas SOL |
| INV-010 | Validação final não inclui calc_area/degeneração; cortador só manifold+volume | Expandir validação e localizar geração de faces colineares |
| INV-011 | lifecycle pai/filho já existe; commit ativa A, sem continuação no receptor | Novo comando de continuidade usando registros atuais |
| INV-012 | EXTRACTED compartilhado por cortadorA/B; A inteira recolorida | Política independente das interfaces e material receptor em B |
| INV-013 | CENTER tem busca opcional25×25; LINEAR_2/3 fixos; flag não exposta na UI | Expor capacidade existente e ampliar para propostas pela forma |
| INV-014 | Geração já compara assinatura; overlay/set_target não validam/invalida captura | Unificar validade desde UI/desenho até geração |
| SOL | Primitivas e usar objeto existem; foco destrutivo e alinhamentos ausentes | Separar operações e acrescentarSOL-01–06 |
| LANG |25 chavesPT/26EN, locale-only, catálogos/strings misturados | Preferência addon e catálogo unificado |

Status observado significa análise estática, não falha reproduzida em Blender na versão recebida.

## 3. Recursos atuais a preservar

- operators.update_preview_positions usa invert_explosion e propriedades de posição/normal congeladas; commit/exportação usam posições montadas. Manter testesINV-004.
- geometry_loop usa interface de fechamento compartilhada/triangulação e rejeita entradas abertas. Não voltar a holes_fill indiscriminado nem remover contrato da superfície.
- analyze_material_structure passou a transformar BMesh para mundo e ponderar normais por áreas mundiais. Não reaplicar correção antiga de área local.
- lifecycle.py já possui captura de snapshot, registro criado, parent_operation_id, remoção de prévia, reversão e bloqueio de pai com filhos. Reusar, não introduzir outro banco de sessões.
- geometry_connectors contém min_distance_to_polygon_boundaries, buscaCENTER opcional, eixos de grade e validação de parede/material base. Reusar, sem chamar método amostrado de prova geral.

## 4. Etapa A — segurança de captura e continuação

### INV-014: modificar pontos exatos

Em operators.CHEST_OT_splitter_generate_preview, o ramoLOOP já chama get_topology_signature e recusa incompatibilidade. Isso protege geração tardia; não protege o desenho.

Em gpu_drawing._draw_loop_overlay, a lista de pontos usa “if0<=i<v_len”: índices inválidos são descartados e os restantes são conectados como se ainda fossem um ciclo. Mesmo índices válidos podem pertencer a outra topologia.

Criar helper único validate_capture(target,settings,context) com origem de objeto/mesh, assinatura, coordenadas/transforms e arestas consecutivas. Usar no painel, overlay e geração. No draw callback, não alterar a cena de forma recorrente; apenas não desenhar captura inválida e solicitar invalidação pelo fluxo/handler seguro.

Criar invalidation helper que limpa loop_is_captured, índices, contagem, seed, planicidade/razãoAUTO e interface/sugestão vinculadas à captura. Chamar no set_target, transições lifecycle e troca real do mesh. Caso mesma topologia deformada, recalcular planicidade/capacidades; hash atual só conta conectividade.

Testes2: assinatura antiga doCube, alvoCube__B e59/62 arestas ausentes. Confirmar nativamente. Padrão da revisão: recaptura em novo corpo; remapeamento automático só quando provenance permitir, não por posição dos IDs.

### INV-011: integrar lifecycle existente

commit_parts seleciona A/B e torna A ativa; mantém alvo anterior. Novo comando “Continuar no corpo remanescente” deve:

1. Resolver operação confirmada atual via lifecycle.resolve_operation e record.
2. Identificar receptor pelo papel/resultado, sem assumir sempreB em SOLID com invert_sides.
3. Selecionar apenas receptor, promover a novo alvo e invalidar captura/seed.
4. Iniciar configuração da próxima sessão, conservando chest_operation_id do corpo para parent_op_id em generate_preview.
5. Recalcular regiões/materiais e diagnóstico; habilitar Editar alvo/capturar no objeto correto.

Não atribuir session_id da operação anterior como ID da nova; não apagar registros. A geração atual já obtém parent_op_id=target.get('chest_operation_id',''); preservar esse elo.

Reverter filho depois pai: usar check_child_operations e mecanismo existente, com testes das transições. Bloqueio de escolher face da prévia continua correto; oferecer “Editar alvo” em vez de relaxá-lo.

## 5. Etapa B — INV-010 e honestidade dos diagnósticos

operators.validate_printable_mesh verifica elementos, coordenadas finitas, abs(volume), arestas não-manifold e métricas. Não testa área zero. geometry_material.create_material_patch_prism_cutter afirma validar ausência de degeneração/auto-interseção, mas seu if só verifica is_manifold e volume.

Adicionar serviço geométrico compartilhado para:

- Área poligonal/triângulos em mm² e segmentos nulos.
- Vértices com IDs distintos coincidentes no mesmo polígono.
- Incidência/orientação e duplicação topológica.
- Volume orientado, componentes e coordenadas finitas.
- Interseção/espessura somente quando método implementado; caso ausente reportar não medido.

Usar no cortador, candidatos antes/depois dos encaixes/folga, confirmação e exportação. analyze_target_mesh já mede degeneração, mas em epsilonBU fixo e como aviso; unificar unidades/capacidade com validação de resultados.

Testes1: faces66,68,69,147,150 do segundo receptor são colineares apesar de incidência2. Confirmar no Blender e registrar em qual estágio surgem; não apenas remover as faces e abrir sólido. Não pintar para esconder resíduos.

Mensagem atual do cortador afirma “auto-interseção por faces dobradas”; a condição não prova essa causa. Substituir por diagnóstico específico de falha medida; traceback técnico pode existir no log.

Cleanup: EXTRUDE tem temporários None e finally mais robusto do que versões antigas. Preservar; auditar liberação de bm_a/bm_b se validação lança antes de retornar, to_mesh e dados avaliados. Não reintroduzir uso de variáveis não inicializadas.

## 6. Etapa C — INV-012, corrigir caminho específico de material

create_material_patch_prism_cutter calcula target_iface_mat=material_index seEXTRACTED, senão body_mat_index. Usa esse material no fundo/laterais.

slice_mesh_by_material EXTRUDE cria prism_obj_a e prism_obj_b com o MESMO interface_mat_mode. Portanto, EXTRACTED colore também o cortador usado emDIFFERENCE; o receptor recebe essa política no booleano. Além disso, loop final recolore todas as facesA para material_index.

Mudança mínima recomendada:

1. Separar argumentos/política de interface por operando. A recebe material do inserto; B recebe material do receptor para superfícies novas.
2. Não passarEXTRACTED ao prisma B para pintar suas interfaces como inserto. SOURCE/body no cortadorB é primeiro passo, mas confirmar identidade no resultado avaliado.
3. body_mat_index já é inferido por faces vizinhas fora da região com maioria de índices. Tornar empates/ambiguidade determinísticos e permitir escolha explícita; não assumir slot0 universal.
4. Preserve exterior original deA/B. A recoloração total só deve existir como opção explícita de impressão monocromática do inserto, não como definição ambígua de “interface”.
5. BASE tem sua própria atribuição de tampas: usar mesma política independente. Folga e encaixes seguem material da peça à qual pertencem.
6. Alternar políticas não muda coordenadas/volume/tesselação nominal. Testar isso.

3MF deve mostrar cavidade branco/cor do corpo e inserto roxo neste exemplo. Restantes regiões externas pintadas continuam para futuras seleções. Não recolorir todo B.

## 7. Etapa D — INV-008, folga lateral por lado

Local exato: ramoEXTRUDE em slice_mesh_by_material. depth_a_bu/depth_b_bu são alterados por clearance_bu; os contornos/region_face_indices dos dois prismas permanecem idênticos. BASE desloca tampas nas direções normais por shift_a/b, também sem offset lateral do domínio.

Não descrever implementação atual como redução de “paredes” em geral. Atualizar tooltips da propriedade depois de corrigir.

Implementar:

- Folga lateralg por parede, separado da folga de fundo ou ligação explicitamente declarada.
- PART erode domínio de contato do inserto por g; CAVITY dilata cavidade por g; BOTH divide g/2 por operando.
- Superfície exterior livre permanece na posição original. Sem scale global.
- Contorno exterior/vazios/concavidades corretos. Definir junção de cantos e limites.

Para patch planar, construir domínio 2D válido, offset robusto e prisma correspondente. Reutilizar tesselação/provenance quando viável. ParaBASE e quina geral, não projetar silenciosamente tudo para plano2D: suportar domínio explicitamente e usar cortador editável nos demais.

Não usar clamp de profundidade como aceite de geometria colapsada: tratar g excessivo com diagnóstico. Validação atual g>=depth-0.1 não detecta estreitamento lateral; ampliar após medir dimensão útil.

Fixture40×30×20 comg0.30 aplicado inserto:39.40×29.40, fundo ligado19.70, receptor nominal. Testar g0/0.15/0.30 e5 quando viável na seleção verde. Verificar cada parede e reentrância, não só volume monotônico.

## 8. Etapa E — INV-013, estender busca existente

adjust_to_valid_area existe emproperties, defaultFalse, entra na assinatura e é passado pelo operador. Não há prop correspondente desenhado emui.py. Usuário não consegue ativar normalmente a busca existente pelo painel.

compute_connector_layout:

- CENTER verifica inclusão/distância e, se flagTrue, faz busca25×25 pelo ponto mais distante das bordas.
- LINEAR_2/3 permanecem candidatos fixos60%/70% da meia-extensão.
- GRID_4 possui busca/eixos próprios; não remover melhorias existentes.
- Validação final testa perfil; buscaCENTER de círculo não basta para cápsula.

A revisão deve expor a capacidade existente de modo claro e criar AUTO_SHAPE separado deCENTER/LINEAR/GRID. Para modoCentro preservar escolha estrita ou oferecer “ajustar”, não mover silenciosamente por padrão.

Separar candidate generation, footprint/domain validation,3D validation e scoring. Quantidade/medidas não mudam automaticamente. Preview e movimento/fixar por pino integram proposta; sugestão de quantidade é comando separado.

CENTRO: maior distância segura dentro do domínio, não centro vazio da caixa. MULTIPLOS: separação e cobertura entre candidatos válidos. LINHA: colinearidade mantida. CÁPSULA: perfil completo+orientação+chanfro. Profundidade/fundo/parede/união verificados em 3D.

Busca adaptativa refina grid quando não encontra candidato; declarar limite/resolução. Nenhum sucesso amostrado é garantia global e nenhum fracasso isolado prova falta absoluta de espaço.

Fluxo atual ignora encaixes emSOLID/MATERIAL, com aviso explícito. A criação de cortador por Material/Loop muda o modo paraSOLID; não prometer pinos automáticos nesse caminho sem implementar interface extraída real.

Nesta revisão, suporte novo de pinos emSOLID deve ser condicionado a interface planar efetivamente construída e validada. Para sólidos gerais, manter bloqueio e explicar. Não ativar pela simples troca de enum ou reutilizar interface velha.

## 9. Etapa F — SOL-01–06 e INV-009

Seguir02_FERRAMENTAS_SOLIDO.md, agora referente ao código recebido:

- ensure_solid_cutter ainda recria dados noelse; foco deve ser puro.
- geometry_solid já ofereceBOX/CYLINDER/SPHERE/CAPSULE e usar objeto existente; estender, não reescrever booleano.
- Criar cópia independente, focar, reiniciar explícito; alinhar face/alvo/cursor/eixos; dimensões/offsets locaismm.
- Prisma deMaterial/Loop planar validado e caixa de quina regular; preview revisável antes do corte.
- Novas ferramentas respeitam operações e ownership do lifecycle; não apagar objetos externos na reversão.

slice_mesh_by_solid devolve métricas, mas não retornaCutInterface; só remapeia material_index fora dos slots para0. Logo, genericamente não fornece domínio para folga/pinos nem proveniência de interface. Acrescentar contrato para métodos suportados antes de integrar recursos.

Receber sólidos gerais não significa geração automática geral. Quinas/capas com espessura variável exigem decisão explícita de volume interno; não espessar sem mostrar alteração. Preservar silhouette externa, cavidade material receptor e proposta de montagem.

## 10. Etapa G — idioma e versão

translations.py atual:25 chavesPT/26EN. Chave adicionalEN é “Inverter Sentido da Explosão”; ausência de entradaPT idêntica à fonte não causa sozinha falta de tradução, mas revela catálogos assimétricos.

Problema maior: fontesPT emRNA/layout + tradução parcialEN + mensagens bifurcadas por locale + exceptionsPT cruas. Preferência AUTO/PT/EN não existe. Implementar catálogo/resolver único conforme03_IDIOMAS.md e auditar lifecycle também.

Na base atual existe entrada literal “Part Splitter 0.8.8” no catálogo, enquanto manifesto já 0.8.9 e UI usa versão dinâmica. Não manter rótulos versionados como msgids repetidos; compor nome e versão a partir da fonte de versão comum.

Manter IDs de propriedades/operadores; alterar somente textos renderizados/diagnósticos. LocPT forçada em BlenderEN deve evitar tradução dupla; cobrir enums/tooltips nativos além de labels.

## 11. Testes existentes: lacunas verificadas

tests/run_all_tests.py lista28 suítes; existem33 arquivostest*.py. Conferir inclusão e runner, não usar total de arquivos como total executado.

test_inv_001_003_material.py:

- D01 capturaValueError opcionalmente mas não exige que erro ocorra; usa duas faces opostas desconectadas, não patch dobrado conectado real. Resultado pode passar sem validar hipótese.
- D02 fallback sintético testa sucesso, não compara faces novasA/B nem material da cavidade.
- D03 só entra nas asserções quando scratch/Testes_Cutter_Original.blend existe. Essa pasta/cena não está no ZIP recebido; sem else/skip, o teste pode concluir sem verificar folga.
- D06 chamado complementaridade apenas assertGreater(va,0) e assertGreater(vb,0); não compara soma original, cobertura ou interseção.

Corrigir testes, não apenas código. Testes sem fixture devem SKIP explícito ou criar fixture determinística; nunca passar vazios. Manifold+volume não é espessura, complementaridade nem material correto.

Adicionar testes novos reais paraINV-008–014/SOL/LANG. A matriz preserva67 casos anteriores e acrescenta6 específicos desta auditoria. Executar em subprocessos limpos com --python-exit-code1. Não rodar suítes que limpam a cena na sessão do usuário.

## 12. Entrega e critérios

Fonte-base recebida imutável; changes em checkout separado. Atualizar changelog com testes realmente executados, correções adicionais e limitações; não herdar afirmação100% sem rerun.

ZIP instalável não inclui.git, caches, dumps, cenas ou históricos internos. Arquivo de fonte/evidências deste plano é pacote de desenvolvimento, não instalar na UI do Blender.

Verificar Blender 4.2 anunciada e5.2 das cenas; cenas5.2 podem não ser compatíveis com4.2, usarfixtures apropriadas. Instalar em perfil limpo e conferir versão módulo/UI/manifesto.

Sem P0 pendente silenciosamente; tools dos domínios suportados demonstradas; matriz e relatório porINV/SOL/LANG preenchidos. Não prometer impressão física/montagem resistente sem ensaio.
