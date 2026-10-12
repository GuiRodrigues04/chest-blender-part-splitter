# Part Splitter — auditoria da 0.8.7 e plano de correção 0.8.8

Data: 11/10/2026. Destino: Antigravity / Gemini Pro. Escopo: estabilização funcional, integridade geométrica, preservação de dados e validação da entrega.

## 1. Conclusão

A 0.8.7 contém avanços reais, mas ainda possui inconsistências entre interface, contrato geométrico, prévia e exportação. Priorizar a correção dos sólidos e a segurança da sessão. Não acrescentar métodos novos antes de validar os recursos existentes.

Os pontos mais urgentes são triangulação degenerada das tampas, direção de explosão, folga ignorada em modos que a exibem, material dos pinos e transações incompletas. O erro de 14 arestas visto pelo usuário não foi reproduzido no Blender: não associar automaticamente esse número a um único defeito encontrado.

Base efetivamente analisada: `chest-blender-part-splitter-0.8.7.zip`, SHA-256 **8e89fe1782639cd13a69c896059f06cff36f6902d26bb3d1691ac404c0f7b7af**. Manifesto identifica 0.8.7. Próxima versão proposta: **0.8.8**. Se a 0.8.7 ainda não foi distribuída, pode-se aplicar os consertos na ramificação em desenvolvimento, mantendo rastreabilidade das compilações.

## 2. Cobertura e limites

Revisão estática transversal dos **16 módulos de produção, totalizando 9.676 linhas**, entrada, manifesto, README, build e runner. Foram analisados sintaticamente **46 arquivos Python**, incluindo **28 scripts de testes**. Nenhum erro sintático encontrado. Revisão de testes concentrou-se nos cenários comerciais, 0.8.7 e pós-testes; o inventário inclui todos os arquivos, mas não afirma execução de cada suíte.

Sem executável Blender neste ambiente. Não houve execução de BMesh, booleanos, GPU, Undo/Redo, exportação nativa ou testes de impressão. Foram executadas reproduções aritméticas da função original de triangulação e cálculo de segmentos, com adaptadores mínimos; isso confirma defeitos nesses cálculos, sem simular a API do Blender.

O pacote inclui inventário com hashes e localização das funções, cópias de referência dos módulos originais, reproduções isoladas e imagens. A auditoria não garante ausência de outros bugs. Uma revisão estática ampla precisa ser complementada pelas fixtures e testes previstos aqui.

| Área | Arquivos | Cobertura |
|---|---|---|
| Registro e parâmetros | __init__, constants, properties, translations | Registro, versões, callbacks, modos, propriedades e textos. |
| Operações e sessão | operators, lifecycle | Assinatura, geração/commit, rollback, recuperação e handlers. |
| Geometria | geometry_contract, plane, loop, material, solid, connectors | Topologia, interfaces, direção, unidades, tolerância, folga, materiais e recursos temporários. |
| Exibição | gpu_drawing, ui | Geometria das linhas, papéis, transformações, comportamento por modo e coerência dos controles. |
| Diagnóstico/exportação | diagnostic, io_export | Malha avaliada, materiais, publicação de arquivos e limpeza. |
| Ferramentas/testes | scripts/build, tests/run_all_tests e suítes selecionadas | Argumentos, subprocessos, métricas de aceite e lacunas de cobertura. |

## 3. Registro de achados

**C**: mecanismo confirmado no código ou em reprodução isolada. O impacto em uma cena específica pode exigir Blender. **R**: risco ou cenário sem reprodução suficiente. Prioridade P0: corrigir antes de novos testes comerciais; P1: corrigir antes do lançamento; P2: manutenção/usabilidade.

| ID | Prioridade | Evidência e consequência |
|---|---|---|
| C01 | P0 | `geometry_loop.triangulate_polygon_2d`: fallback força triângulos e o caso final aceita três pontos colineares. Quadrados com 12/20 vértices geram 1/3 triângulos de área zero. |
| C02 | P0 | `geometry_material`, ramo BASE: exceções na criação de tampas são ignoradas; pode chegar à validação com tampa incompleta sem indicar o estágio responsável. |
| C03 | P0 | Material BASE orienta `n_base` para a saliência e passa esse vetor como A→B. A→B deveria apontar para o corpo; a explosão usa A=-normal e empurra a saliência para dentro. |
| C04 | P0 | Plano: `clear_outer=True` conserva A no lado negativo da normal, mas `compute_explosion_offsets` move A para o positivo e B para o negativo. Revisar também o caminho com invert_sides. |
| C05 | P1 | A interface exibe folga entre peças no Loop/Sólido, mas seus métodos não recebem nem aplicam essa propriedade. No Loop, o ramo do operador passa somente profundidade/through_cut; no Sólido a assinatura da função nem tem parâmetro de folga. |
| C06 | P1 | Material EXTRUDE aplica folga mudando profundidades; não calcula folga lateral do contorno. Pode ser um contrato axial válido, mas o nome genérico sugere algo mais amplo. Definir suporte e explicá-lo. |
| C07 | P1 | Material BASE desloca vértices do perímetro para criar folga. Esses vértices pertencem também às faces externas adjacentes; isso deforma essas faces em vez de recortar por um novo plano. |
| C08 | P1 | Material EXTRUDE transforma novamente `coords_world` por `matrix_world` no fallback da interface; contorno sofre transformação dupla em objetos movidos/escalados. |
| C09 | P1 | Plano chama `cap_open_cut_boundaries(bm, cut_edges=...)` sem origem/normal. O fallback da função percorre todas as bordas abertas, contrariando a restrição de fechar somente o corte. |
| C10 | P1 | `coplanar_tol_mm` é usado na classificação das faces, mas não passado ao parâmetro `dist` do bisect. Duas etapas usam critérios distintos. |
| C11 | P1 | Overlay explodido procura `chest_role == 'A'/'B'`; produção usa `PREVIEW_A/PREVIEW_B`. Não encontra as prévias e usa deslocamentos zero. |
| C12 | P1 | `_compute_cut_line_segments` exige sinais positivos e negativos; ignora arestas coincidentes com o plano quando o terceiro vértice fica de um único lado. Reprodução isolada retorna zero segmentos nesse caso. |
| C13 | P1 | Overlay triangula polígonos em leque a partir do primeiro vértice; em n-gons côncavos isso pode gerar segmentos fora da superfície real. |
| C14 | P1 | Overlay usa `target.data`/BMesh e não o snapshot avaliado usado por Plano/Sólido. Linha pode divergir do corte com modificadores. |
| C15 | P1 | Overlay calcula interseções e constrói batches durante cada desenho, sem cache. Custo cresce com polígonos e viewports; medir o impacto real em Blender. |
| C16 | P1 | Pinos recebem material escolhido em slot zero de uma malha separada, mas booleanos não configuram `material_mode`. Padrão INDEX pode mapear esse zero para o primeiro material do macho, produzindo branco em vez de amarelo. |
| C17 | P1 | `determine_connector_material` amostra centros de faces perto de todas as posições e escolhe um material para todos os pinos. Centro de face não representa a área de ligação; pinos em regiões distintas não recebem decisão individual. |
| C18 | P1 | Predominância por área usa leque sobre n-gons; pode superestimar área de face côncava. A computação inclui tampas recém-criadas, podendo alterar a predominância original. |
| C19 | P0 | `resolve_operation` retorna None para seleção ambígua, mas remove/revert fazem fallback para `settings.session_id`. O cancelamento por ambiguidade pode ser contornado pelo chamador. |
| C20 | P0 | `remove_preview` não exige status PREVIEW; pode descartar snapshot e marcar REVERTED em operação confirmada resolvida pela seleção/sessão. |
| C21 | P0 | Snapshot foi melhorado, mas é substituído antes da conclusão da nova prévia. Registro e alocações ainda ocorrem antes do try principal; rollback da geometria não restaura backup/registro anterior. |
| C22 | P0 | O swap remove a prévia anterior antes de assinatura final, atualização visual e outras operações potencialmente falíveis. Falha após swap não pode manter a prévia que já foi removida. |
| C23 | P1 | Handler reconhece alteração de malha, mas compara contagens/transformações; edição de coordenadas/material com mesmas contagens pode não invalidar. Transformações parentais de rotação/escala também exigem matriz mundial completa. |
| C24 | P1 | Assinatura de encaixes omite chanfro, folga de fundo e ajuste à área válida; folga da interface não aparece em Loop/Sólido. Callbacks podem invalidar alguns casos, mas assinatura completa continua inconsistente. |
| C25 | P1 | Exportadores/operador fazem fallback silencioso para malha base se avaliação de modificadores falha. O arquivo pode diferir do resultado prometido no viewport. |
| C26 | P0 | STL em lote faz staging, mas publica com `shutil.copy2` em sequência. Falha de disco no meio pode deixar saída parcial e sobrescrever arquivos existentes. Não é transação atômica de lote. |
| C27 | P1 | `build_3mf_xml` coleta paleta e slots na malha original, depois exporta faces avaliadas. Modificadores que acrescentam materiais podem perder ou trocar cores. |
| C28 | P1 | Build e runner usam `argv=[]` quando não existe separador literal `--`; ignoram `python script.py --blender caminho`, comando documentado no README. |
| C29 | P1 | Teste R06 compara coordenada em metros com `delta=0.01`, equivalente a 10 mm na cena padrão; pode aprovar folga de 0,15 mm sem aplicá-la. |
| C30 | P1 | `is_manifold`/volume positivo não checam auto-interseções, triângulos degenerados ou união real dos pinos. Texto “arestas abertas” mostra contagem de todas as arestas não-manifold, confundindo diagnósticos. |
| R01 | P1 | Verificar cápsula completa na espessura receptora: a amostragem usa raio e cinco pontos, sem os extremos alongados do perfil. Pode deixar passar perfuração nas pontas. |
| R02 | P1 | Material/Loop usam malha base para seleção/análise enquanto alguns booleanos mantêm modificadores das cópias. Definir contrato de suporte para deformação e mudanças de topologia. |
| R03 | P1 | Validar restauração completa quando o alvo existe: copia malha/matriz, mas não restaura modificadores que o usuário alterou após o snapshot. Definir o que “reverter” preserva. |
| R04 | P1 | Auditar liberação de BMeshes/malhas avaliadas em todas as exceções. Em conectores, a segunda avaliação pode falhar antes do finally que libera a primeira; Material BASE tem saídas sem free dos dois resultados. |
| R05 | P1 | Undo/Redo pressupõe cena válida no argumento; confirmar assinatura real nas versões suportadas e reconciliar caches/registro quando não houver argumento de cena. |
| R06 | P2 | Tolerâncias fixas em BU, área 1e-8/1e-7 e offsets 1e-4 mudam fisicamente com scale_length. Auditar também espessura indeterminada do Loop com fallback permissivo de 1000 mm. |

Não reenviar o plano anterior como se nenhuma mudança tivesse ocorrido: a 0.8.7 já melhora validade da captura, restauração de GPU, identificação de snapshots, grade orientada, recursos temporários no Loop e mensagens de prévia anterior. Preservar essas melhorias e corrigir suas lacunas.

## 4. Plano de implementação

### Fase 1 — identidade da compilação e segurança

Registrar versão da extensão, Blender, localização do módulo instalado e hash do pacote. A mensagem “O corte por material...” vista com BASE pertence ao ramo EXTRUDE deste ZIP; BASE emite “O destaque por base...”. Limpar/atualizar status ao trocar comportamento e incluir modo efetivo e estágio nos diagnósticos. Não concluir que a propriedade BASE está errada: o operador a passa corretamente.

Corrigir C19–C22 antes de ampliar funcionalidades. Resolver operação com retorno estruturado: encontrada, ausente ou ambígua; não usar fallback em caso ambíguo. Remover Prévia só atua em prévia; Reverter Corte só em confirmado. Nenhuma exclusão por papel/nome sem associação inequívoca.

Criar registro, backup, meshes, objetos e métricas como candidatos da mesma transação. Toda alocação deve estar em try/finally. Validar geometria, assinatura e dados visuais antes de descartar o estado anterior. Commit deve promover um conjunto consistente e ter rollback de dados persistentes, não somente dos objetos temporários. Só eliminar o backup anterior depois da promoção. Testar falhas em cada ponto de aquisição e no swap.

### Fase 2 — tampas e volume real

Substituir o fallback da triangulação por triangulação robusta/constrangida com preservação de todos os segmentos da borda. Não remover pontos colineares só da tampa: as paredes continuam usando esses vértices e podem criar junções sem conexão. Pode-se simplificar se a topologia adjacente for atualizada consistentemente; caso contrário reinserir os vértices no contorno triangulado.

Validar área orientada, simplicidade do polígono, cobertura total, zero triângulos degenerados, nenhuma sobreposição e incidência correta nas bordas. Polígono sem solução deve falhar com motivo, nunca forçar triângulo para terminar o laço. Em BASE, criação de face com falha deve cancelar explicitamente e liberar todos os recursos.

Aplicar a mesma correção ao prisma do Loop que reutiliza a função. Reproduzir a saliência com 92 faces e contar/destacar as arestas problemáticas antes da tampa, depois da tampa e depois da folga. Separar borda aberta, aresta com mais de duas faces e aresta solta.

Preservar o requisito: BASE retira a saliência inteira e fecha sua base, deixando a parede do corpo plana; EXTRUDE preserva a extração da região verde com profundidade e cavidade. Região complexa dobrada não deve virar capa por projeção média. Não fechar aberturas preexistentes da entrada indiscriminadamente.

### Fase 3 — interfaces, direção e prévia explodida

Definir normal A→B de modo uniforme. Material BASE: normal voltada para a saliência é a oposta da normal A→B. Plano: conferir lado retido pelo bisect e mover as peças para fora uma da outra, inclusive com inversão de lados. Não usar posição superior no eixo Z como substituto da direção da interface.

Guardar na prévia validada: matrizes montadas A/B, direção de extração, interface nominal/efetiva e configuração usada. Exibir a prévia antiga com seus próprios dados quando parâmetros atuais estiverem desatualizados. A posição explodida é calculada a partir da matriz montada, nunca da posição já explodida. Sólido hoje usa centros das bounding boxes transformadas: medir se repetir atualizações muda sua direção por realimentação.

Para partes que encaixam dentro de cavidades, distinguir distância solicitada de distância necessária para liberar a peça. Medir profundidade e extremos na direção de saída. Usar verificação geométrica quando houver reentrâncias; se não existe trajetória de extração simples, informar limite. Não alterar a geometria ou folga para melhorar a ilustração.

Montado deve restaurar exatamente a posição base. Exportação usa essas matrizes salvas. Ocultar original/backups da sessão sem modificar visibilidade de objetos alheios. Testar repetição da vista, troca de modo, rotação, parent e A/B invertidos.

### Fase 4 — folga honesta e medida

Estabelecer contratos por modo. BASE pode oferecer **folga axial na base**; EXTRUDE planar precisa distinguir fundo de laterais se oferecer ambos. Não rotular redução de profundidade como folga universal. Loop/Sólido: implementar casos suportados ou desabilitar a opção com motivo; nunca mostrar controle sem efeito.

Em BASE, recortar pelo novo plano de interface em vez de mover vértices externos compartilhados. Recalcular contorno/tampa a partir do recorte; preservar exterior fora da faixa removida necessária. Não prometer exterior integral quando a própria base do relevo muda: definir exatamente a região afetada e mostrar a diferença.

Aplicação unilateral g; bilateral g/2 em cada lado. Validar espessura remanescente no lado realmente alterado. Não comparar folga aplicada só à cavidade com altura da saliência, nem usar valor g inteiro quando só g/2 é aplicado a essa peça. Proibir escalonamento global da peça como substituto de offset.

Todos os controles geométricos precisam de assinatura, invalidation e persistência coerentes. Medir 0; 0,15; 0,30 mm em posição montada. 5 mm é ensaio de estresse e pode ser inviável, não recomendação. Com folga, soma de volume deixa de ser igual à original por definição; registrar volume removido intencionalmente.

### Fase 5 — plano, linhas e cache

Passar origem, normal e tolerância ao fechamento; limitar arestas ao corte efetivo, incluindo geração/proveniência, não só coplanaridade. Passar a tolerância física também ao bisect e alinhar classificações. Não eliminar faces próximas de um plano por epsilon grande.

Usar constantes de papel PREVIEW_A/B para os overlays. Uma interface com folga tem dois contornos efetivos: desenhar cada um na sua peça, em vez de duplicar a linha nominal indiscriminadamente. Com vista explodida, aplicar matrizes visuais completas.

Usar tesselação real da malha, não leque em n-gons. Definir regra para coplanaridade, tangência e aresta inteira sobre o plano, deduplicando segmentos sem desenhar diagonais internas. Alvo com modificadores deve compartilhar o snapshot de corte. Edit Mode requer estado vivo coerente; se não puder avaliar sem ambiguidades, explicar o limite.

Cache guarda coordenadas independentes, nunca RNA avaliado/BMesh antigo. Handler apenas marca sujo; atualização limitada fora do draw callback; draw só desenha. Restaurar todos os estados GPU alterados em finally. Medir latência/CPU em malhas reais e em múltiplas viewports.

### Fase 6 — encaixes, materiais e precisão

Preservar a grade orientada nova. Conferir índices de contornos, ilhas/furos, raio efetivo, distância de bordas e espessura. Amostragem e heurística finitas podem rejeitar uma solução existente; apresentar falha específica, não retirar validação nem reduzir a quantidade.

Escolher material por pino. Área de ligação monomaterial determina o pino inteiro; ligação ambígua usa material predominante da peça por área mundial da superfície de referência. Amostrar região/triângulos intersectados pela ligação, não apenas centro de face num raio. Calcular área com tesselação real e manter resultado independente de subdivisão.

Mapear slots por identidade do material. Opções: alinhar índices no cortador ao receptor ou usar TRANSFER explicitamente quando suportado. Verificar faces após booleano e não confiar na cor de objeto. Paredes da cavidade seguem material do receptor. Validar 3MF reimportado.

Para cápsulas, verificar footprint alongado completo, colisão entre pinos, margem e parede em extremos. Amostras do círculo central não garantem espaço nas pontas. Definir epsilons e espessura mínima em unidades físicas. Após união, comprovar conexão do pino, não apenas um componente com volume positivo.

### Fase 7 — exportação e diagnóstico

Não exportar malha base silenciosamente se avaliação falhar. Avaliar uma vez por objeto e usar a mesma geometria/material para validar e exportar. 3MF deve coletar recursos de materiais do snapshot avaliado. Texturas/procedurais não são reduzidos fielmente a uma cor Base Color: descrever suporte real.

STL por material que apenas separa faces coloridas pode gerar cascas; manter rejeição para impressão independente e explicar diferença para 3MF multipartes. Não confundir exportação de superfícies com extração de sólidos por material.

Staging de lote não torna publicação atômica: usar diretório final versionado/renomeado no mesmo filesystem quando apropriado, ou backup e rollback por arquivo. Uma falha de publicação deve preservar o destino anterior e identificar o que foi escrito. Não sobrescrever colisões de nome existentes sem política explícita. 3MF temporário deve ter nome único por execução e limpeza garantida.

Normalizar diagnóstico: boundary_edges, non_manifold_edges, wire_edges, degenerate_faces, components, volume físico, orientação e self_intersection quando verificável. Limites numéricos em mm/mm²/mm³. Avaliação de modificadores e limpeza de recursos precisam estar em finally de todo o caminho.

### Fase 8 — build, testes e documentação

Corrigir argv: Python externo recebe `sys.argv[1:]`; Blender com script usa argumentos após separador `--`. Testar ambos, --help, ambiente e executável ausente. Não inferir que qualquer python com “blender” no path é executável Blender sem verificar.

Corrigir delta de R06: converter unidade antes de comparar ou medir em mm com tolerância compatível, por exemplo 0,01 mm documentado para fixture simples. Não usar 0,01 BU como tolerância de 0,15 mm. Testes de Undo devem gerar/atualizar prévia, executar ciclos efetivos e contabilizar operações; poll falso não equivale a teste aprovado.

Adicionar casos subdivididos, concavidades e contorno colinear; cubo simples com quatro vértices não cobre C01. Fazer testes de falhas durante publicação, promoção e aquisição de recursos. Registrar executados, falhos, omitidos e skip com motivo.

Manter README curto e sem emojis. O termo “homologada” precisa de relatório e geometrias/versões cobertas; manifestar compatibilidade mínima não demonstra testes. Manter src/testes/scripts/docs organizados, sem refatoração geral junto da correção geométrica. Criar módulos pequenos apenas para contrato de interfaces, recursos/transações e snapshots de sessão quando houver benefício concreto.

## 5. Matriz de aceitação da 0.8.8

| Teste | Resultado obrigatório |
|---|---|
| V01 | Tampas com 4/12/20/40 vértices: zero degeneração, toda borda compartilhada corretamente. |
| V02 | Bases L/U com vértices colineares: cobertura do domínio sem pontes. |
| V03 | Polígono inválido/autointersectante: falha antes de publicar, com estágio. |
| V04 | Saliência do relato com 92 faces: BASE sólido completo, sem núcleo/lâmina, B fechado. |
| V05 | Região verde do relato: extração com profundidade preservada. |
| V06 | Topo/lateral e plano girado: A/B explodem para fora; invert_sides consistente. |
| V07 | Repetir distância 20→40→20 e montado/explodido 50 vezes: sem drift nem direção alterada. |
| V08 | Alterar configuração mantendo prévia antiga: visual usa snapshot antigo e sinaliza stale. |
| V09 | Folga Loop/Sólido: efeito medido ou opção desabilitada claramente. |
| V10 | BASE axial 0/0,15/0,30 mm: distância medida sem deformação de faces externas indevida. |
| V11 | Folga unilateral/bilateral/cavidade: valida limite do lado alterado, sem ajuste silencioso. |
| V12 | Folga de 5 mm: resultado suportado medido ou rejeição antes de alteração. |
| V13 | Alinhamento por face: nenhuma película coplanar; abertura original não preenchida. |
| V14 | Linha sobre aresta/tangência/coplanaridade: regra coerente e sem segmentos falsos. |
| V15 | Linha em n-gon côncavo e alvo modificado: coincide com corte. |
| V16 | Linha explodida encontra PREVIEW_A/B e acompanha transformações completas. |
| V17 | Grade 4 em quadrado com eixos 0/45 graus, retângulo, furo e concavidade: quantidade correta ou motivo. |
| V18 | Pinos amarelos/brancos e pinos em regiões diferentes: material correto em cada um. |
| V19 | Ligação multicolor: fallback por área, invariável à subdivisão/escala não uniforme. |
| V20 | Cápsula perto de quina: pontas não perfuram receptor nem invadem vazio. |
| V21 | Duas operações selecionadas: remove/revert cancela, sem fallback para sessão arbitrária. |
| V22 | Remover Prévia em corte confirmado: não descarta backup nem altera status. |
| V23 | Falha em criação de snapshot/swap/assinatura: estado anterior completo preservado. |
| V24 | Alvo removido/restaurado e modificado após corte: contrato de backup cumprido. |
| V25 | Editar coordenadas/material/modificador com mesma contagem: invalidation imediata. |
| V26 | Alterar chanfro, folga de fundo e ajuste de posição: assinatura/sessão atualizadas. |
| V27 | 20 ciclos reais de Undo/Redo com geração: sem crash nem referência antiga. |
| V28 | Avaliação de modificador falha: exportação cancelada sem fallback silencioso. |
| V29 | Material gerado por modificador: paleta/índices 3MF corretos após reimportação. |
| V30 | Falha na publicação do segundo STL: destino anterior íntegro, sem lote parcial aceito. |
| V31 | Exportar em vista explodida: arquivos montados, sem guia/overlay/backup. |
| V32 | Objetos movidos/parentados, escala não uniforme e cenas 1/0,01/0,001: medidas físicas iguais. |
| V33 | Python externo e Blender script reconhecem --blender/--help corretamente. |
| V34 | R06 com folga desativada deliberadamente falha; teste detecta ausência de 0,15 mm. |
| V35 | Repetir 50 gerações e falhas injetadas: datablocks/recursos estáveis. |
| V36 | Instalação limpa, arquivo legado 0.8.7, idiomas PT/EN e unregister/register: sem duplicação. |

## 6. Evidências, referências e entrega

`evidencias/Inventario_e_Verificacao.json`: hashes, linhas e funções. `evidencias/Reproducoes_Estaticas.py`: funções originais por AST, teste numérico reproduzível sem Blender. `evidencias/Resultado_Reproducoes.json`: saída obtida nesta revisão. `fontes_referencia/`: original 0.8.7, não corrigido.

As imagens M/P/E preservam exemplos dos testes anteriores. Acrescentadas X01/X02 da explosão por Loop, X03 com 14 arestas em Material e X04/X05 com BASE selecionado. Inspecionar a cena real antes de associar cada defeito a cada screenshot.

Referências primárias:

- [BMesh Operators](https://docs.blender.org/api/4.2/bmesh.ops.html): bisect, delete, triangulação e preenchimento; clear_outer remove o lado positivo.
- [BMesh](https://docs.blender.org/api/5.0/bmesh.html): propriedade e ciclo de vida do BMesh vivo/criado.
- [GPU State](https://docs.blender.org/api/current/gpu.state.html): leitura e restauração de estado.
- [BooleanModifier](https://docs.blender.org/api/4.5/bpy.types.BooleanModifier.html): material_mode INDEX/TRANSFER; confirmar na versão mínima.
- [Depsgraph](https://docs.blender.org/api/5.0/bpy.types.Depsgraph.html): snapshot avaliado e limpeza pelo proprietário correto.
- [Handlers](https://docs.blender.org/api/5.2/bpy.app.handlers.html): cuidados com alterações de dados e callbacks.
- [CLI de extensões](https://docs.blender.org/manual/en/4.5/advanced/command_line/extension_arguments.html): build/validate oficiais.

Instrução ao Gemini Pro: confirmar checkout e instalação, reproduzir primeiro, implementar por fases e entregar ZIP instalável **0.8.8**, fontes, fixtures, testes e relatório V01–V36. Atualizar versão/metadados de forma consistente. Não remover validações, não aumentar tolerâncias indiscriminadamente e não declarar todos os bugs resolvidos por sintaxe ou por resultado FINISHED. Preservar recursos já funcionais, cenas do usuário e reversão de operações.
