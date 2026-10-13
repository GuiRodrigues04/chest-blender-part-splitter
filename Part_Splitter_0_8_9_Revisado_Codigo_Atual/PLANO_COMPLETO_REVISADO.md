# Part Splitter — revisão da 0.8.9 baseada no código recebido

Este pacote SUBSTITUI o plano anterior “Part_Splitter_0_8_9_Plano_Antigravity_Flash_3_8.zip”.

A distribuição recebida “chest-blender-part-splitter(2).zip” declara 0.8.9 no manifesto. Seu changelog descreve correções INV-001 a INV-006; o escopo pedido agora é completar INV-008 a INV-014, idiomas e ferramentas de sólido. Não confundir versão declarada com aprovação de todos esses requisitos.

## Prompt para Antigravity / Gemini Flash 3.8

Trabalhe sobre a base atual deste pacote, não sobre 0.8.5/0.8.6. Confirme que seu checkout coincide com SHA256_Fontes_Atuais.json. Leia 01_PLANO_DIRECIONADO.md e 04_MAPA_CODIGO_ATUAL.md. Depois leia especificações 02/03 e execute 05_TESTES_ACEITE.csv.

Finalize a revisão 0.8.9 corrigindo INV-008 a INV-014 e implementando SOL-01 a SOL-06 e LANG-01. Se a 0.8.9 já foi publicada/distribuída fora deste ambiente, combine numeração de release antes de sobrescrever; este pedido mantém o alvo 0.8.9.

Não duplicar recursos que já existem: invert_explosion e snapshots, lifecycle.py com operações pai/filho e reversão, triangulação compartilhada do Loop, helpers de domínio/espessura em geometry_connectors. Preserve essas proteções e amplie os contratos existentes.

Pontos concretos ainda pendentes:
- Folga Material altera apenas depth_a_bu/depth_b_bu.
- EXTRACTED é passado aos dois prismas e contamina material da cavidade.
- validate_printable_mesh e validação do cortador não checam área zero.
- set_target não invalida loop; overlay não verifica assinatura e ainda filtra índices fora de faixa silenciosamente.
- commit seleciona A/B e ativa A, sem próxima sessão no receptor.
- Ajustar à Área Válida existe, defaultFalse, mas não é desenhado no painel; busca só CENTER, LINEAR_2/3 continuam fixos.
- Criar/Focar Sólido ainda recria malha existente.
- Catálogo parcial e decisões de locale coexistem com textos PT fixos.

Implemente em etapas testáveis. Registre causa, arquivos e evidências; não declarar testes PASSOU sem executá-los. Os dois .blend estão intactos. Não executar scripts internos ao abrir cenas. Reproduza cinco polígonos colineares em Testes1 e loop antigo em receptor novo em Testes2.

Entregue ZIP instalável, changelog corrigido, relatório por INV/SOL/LANG, matriz de testes, antes/depois PT/EN e limites de suporte. Não tratar changelog que afirma28/28 como prova independente de novos requisitos: os testes têm lacunas descritas neste plano.

## Conteúdo

- 01_PLANO_DIRECIONADO.md: achados atuais, funções e ordem de correção.
- 02_FERRAMENTAS_SOLIDO.md: contratos das novas ferramentas.
- 03_IDIOMAS.md: política PT/EN e detalhes de migração.
- 04_MAPA_CODIGO_ATUAL.md: linhas exatas da base recebida.
- 05_TESTES_ACEITE.csv: 73 testes de aceite planejados, inicialmente NÃO EXECUTADO.
- 06_GALERIA.html:17 imagens dos casos.
- 07_RELATORIO_ENTREGA_MODELO.md: modelo de entrega.
- fontes/base_atual_0.8.9/: fonte e 33 arquivos de testes recebidos; sem histórico git.
- referencias/: fontes oficiais, hashes, código numerado e auditoria de strings.
- evidencias/: registros históricos INV-008 em diante e dois .blend.

Os registros históricos citam versões anteriores; prevalece a análise do código atual neste pacote. Não há implementação de correções aqui nem execução Blender.


---

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


---

# Ferramentas novas — contratos exatos para 0.8.9

## SOL-01 — Criar, focar e reiniciar são operações diferentes

Na base atual 0.8.9, ensure_solid_cutter recria a malha e reposiciona ao centro mesmo se o objeto existe; Criar/Focar chama essa função. Separar:

- Criar cortador: cria somente quando não existe; se existe, seleciona e orienta para Focar/Reiniciar.
- Focar/Selecionar: somente seleção/enquadramento; nenhuma alteração de malha, dimensões, posição, rotação ou parent.
- Reiniciar formato: ação explícita, com undo, gera nova malha no cortador pertencente à sessão. Não alterar objeto externo usado como cortador.
- Trocar tipo: definir se preserva dimensões e transformações; padrão preservar dimensões físicas e pose quando possível, mostrando limitações.

Separar factory(create) de resolver/get e focus(context). Não esconder recriação dentro de função ensure chamada em UI, depsgraph ou atualização de preview.

Aceite: ajustar cortador, focar repetidamente, atualizar painel/preview e reabrir cena: mesh e matrizes idênticos.

## SOL-02 — Alinhamento previsível

Comandos mínimos:

1. Alinhar à face ativa: origem no ponto de referência da face; um eixo local explicitamente rotulado como Profundidade acompanha sua normal mundial.
2. Alinhar aos eixos do alvo: usar orientação ortonormal do alvo, sem herdar escala não uniforme como fator físico do cortador.
3. Alinhar ao cursor3D: pose do cursor, com opção posição somente ou posição+orientação.
4. Eixos globais X/Y/Z: normal de profundidade e rotação em torno dela explícitas.
5. Ajustar posição à seleção: centro/âncora da seleção, sem inferir automaticamente volume do recorte.

Preservar tamanho ao alinhar. Normais com inversa-transposta ou geometria já transformada; usar mesmo espaço das posições. Matriz singular deve recusar; reflexão tratada explicitamente.

Construir base ortonormal determinística: normal validada, eixo tangente de aresta de referência ou projeção de eixo do alvo; fallback quando quase paralelo. Evitar giro180° inesperado em faces vizinhas. Não substituir usuário por câmera como convenção principal.

Para alinhar pela face, âncora do cortador pode ser Centro ou Face de apoio. Com Face de apoio, essa face toca o plano selecionado; profundidade positiva entra no alvo. Botão Inverter direção altera o cortador proposto e invalida preview, diferente da inversão só visual da explosão.

Aceite: face inclinada, objeto rotacionado/escalado/refletido, cursor e origem distante: contato/pose corretos sem mudança de dimensões.

## SOL-03 — Dimensões e deslocamentos físicos

Mostrar largura, altura e profundidade em mm na base local ortonormal do cortador, não misturar com bounding box global que muda ao girar.

Deslocamentos em eixos locais, rotação em torno da profundidade e face de apoio. Native gizmos/G/R continuam úteis; painel acompanha suas mudanças sem reconstituir a malha.

Fonte única de geometria/transformação: escolher malha canônica + transformação ou rebuild explícito para edição dimensional; nunca aplicar novo tamanho em callbacks que disparam entre si e acumulam escala.

scale_length altera conversão física: dimensions_mm=BU×scale_to_mm. Sem alvo, default50 mm equivale50/scale_to_mm BU, não50 BU. Auditar default do código atual.

Aceite: girar cortador preserva dimensões locais; editar largura não altera altura/profundidade; repetir ajustes sem drift; callbacks têm proteção contra recursão.

## SOL-04 — Duplicar e copiar como cortador

- Duplicar cortador: objeto e mesh independentes, mesma matriz mundial inicial e parâmetros aplicáveis; selecionar cópia como novo cortador de sessão.
- Copiar selecionado como cortador: não editar/ocultar/reparentear fonte; criar objeto e mesh próprios na coleção de guias, com proveniência.
- Se fonte tem modificadores, oferecer copiar malha base ou malha avaliada; explicar diferença e copiar materiais quando necessário. Liberação de to_mesh obrigatória.
- Usar selecionado como cortador continua disponível como referência externa: ajustes só por ação do usuário, limpeza da sessão nunca apaga esse objeto.
- Garantir propriedades/IDs de sessão próprios; não herdar role de peça final/backup incorretamente.

Aceite: mover/editar cópia não altera fonte; removê-la não elimina objeto do usuário; exportação não inclui guias.

## SOL-05 — Prisma de Material/Loop planar

Comando Criar cortador desta seleção aceita:

- Loop capturado válido e planar.
- Região de material que é patch planar com contorno(s) suportado(s).

Pré-validar conectividade, vazio/furos, concavidade, segmentos e planicidade em mm. Loop planar não determina qual lado/extrusão o usuário deseja; mostrar Profundidade, Direção e extensão para fora como parâmetros.

Prisma preserve domínio exato, incluindo vazios quando suportados. Tampas trianguladas com contorno restrito; triângulos internos não invadem concavidades. Não convex hull. Extensão exterior pequena em mm evita coplanaridade, mas não deve englobar outra área externa: verificar visual e geometricamente.

Gerar objeto cortador editável primeiro; não executar o corte simultaneamente. O usuário vê volume de interseção, pode ajustar e depois gerar preview. Transferir seleção/material como proveniência, não definir cor final automaticamente por todo cortador.

Seleção não planar: oferecer alinhar/propor primitiva com base nela; não chamar extrusão arbitrária de prisma validado. Base com furos não suportados: explicar, nunca fechar buraco silenciosamente.

Aceite: retângulo, U/C, contorno com buraco suportado, segmentos colineares e valores pequenos/grandes; malha fechada e exterior selecionado respeitado.

## SOL-06 — Caixa para quina regular

Identificar pequeno conjunto de planos dominantes aproximadamente ortogonais e região regular. Estimar orientação com geometria de mundo; não assumir eixos globais do cubo.

Propor caixa delimitada pelos planos/contorno, mostrar volume retirado e campos de dimensão/profundidade internos. Validar interseção com exterior:

- Faces pintadas pretendidas incluídas.
- Faces externas não selecionadas não invadidas, salvo ajuste explícito mostrado.
- Superfícies livres externas preservadas.

Três patches quadrados compatíveis podem sugerir bloco. Patch irregular/côncavo não recebe bounding box indiscriminado: requer edição manual ou diagnóstico.

Uma capa de20 mm, extrusão diagonal20 mm e bloco interno são resultados diferentes. A proposta não deve ocultar essa mudança no volume retirado.

Caixa editável permite evitar abas triangulares internas; não garante automaticamente montagem. Indicar direção candidata (diagonal no caso regular) e limitações de teste.

Aceite: quina ortogonal rotacionada, quina com escala não uniforme, seleção irregular recusada corretamente, core retirado mostrado e material/folga por superfície de contato corretos.

## Interface e integração

Fluxo: selecionar referência → criar proposta → alinhar/dimensionar → inspecionar volume → gerar corte → validar → confirmar → continuar no receptor.

Gerar nova ferramenta não deve desfazer automaticamente prévia válida. Mudanças tornam preview desatualizado e exigem regeneração. Não confundir focar com regenerar.

Todos os botões e mensagens em PT/EN. Ajuda explica corpo, inserto, profundidade local, face de apoio e diferença entre direção do cortador e explosão visual.

Limite explícito da 0.8.9: sólidos gerais podem ser usados manualmente, mas geração automática de sólido para toda região curva/não planar está fora da garantia. Esse limite não elimina SOL-05/06 nos casos suportados.


---

# LANG-01 — revisão de idioma

## Achados específicos

Na base atual 0.8.9:

- ui.py e properties.py contêm muitos textos PT fixos.
- translations.TRANSLATIONS_DICT tem 25 entradas pt_BR e 26 en_US, incluindo entradas pt_BR idênticas às fontes e traduções en_US de fontes PT.
- HELP_TOPICS usa catálogo PT/EN próprio.
- _get_current_locale resolve pt quando bpy.app.translations.locale começa com pt; todo restante vira en_US.
- Mensagens de alguns operadores usam loc=='pt_BR'; outras são PT fixas.
- Exceptions geométricas são frases PT; operadores embrulham str(e) com prefixos PT/EN. Pode resultar envelope inglês e causa portuguesa.
- F-strings formatadas antes de tradução não têm msgid estável; catálogo parcial não cobre toda combinação dinâmica.
- Falhas de registro de tradução são capturadas silenciosamente; investigar registro/unregister em reload.

As capturas 0.8.8 exibem mistura: Enable Connectors, Cut Distribution, Nominal Dimensions, Assembly Clearances (FDM), Boundary Loop Cut, Highlight Loop in Viewport, Invert Explosion Direction e mensagens de erro em inglês entre controles portugueses.

O Blender das capturas também tem menus em inglês. Assim, não concluir que o idioma do sistema era PT: a mistura pode decorrer de locale en + fontes PT incompletamente catalogadas. A preferência explícita do addon resolve a expectativa sem exigir mudar toda a interface do Blender.

## Política recomendada

AddonPreferences.language: AUTO / PT_BR / EN_US; padrão AUTO. Preferência do addon, não configuração de cada cena. IDs internos e EnumIdentifiers permanecem estáveis e não são traduzidos.

Um único resolver resolve preferência explícita ou idioma Blender. Fallback EN_US documentado para idiomas não suportados. Alterar idioma deve redesenhar UI sem alterar geometria, sessão, captura ou validade da prévia.

Usar catálogo único com chaves de mensagem estáveis e placeholders nomeados. Todas as mensagens possuem PT/EN. Exemplos:

| Chave | PT | EN |
|---|---|---|
| connectors.enable | Ativar encaixes | Enable connectors |
| connectors.distribution | Distribuição dos encaixes | Connector distribution |
| connectors.suggest_positions | Sugerir posições | Suggest positions |
| connectors.suggest_count | Sugerir quantidade | Suggest count |
| connectors.outside_domain | O encaixe {index} está fora da região útil ou viola a margem de {margin_mm} mm. | Connector {index} is outside the usable region or violates the {margin_mm} mm margin. |
| preview.failed_preserved | A atualização falhou: {reason}. A prévia anterior foi mantida. | Update failed: {reason}. The previous preview was preserved. |
| loop.recapture_target_changed | O corpo mudou após o corte. Capture um novo contorno para continuar. | The body changed after the cut. Capture a new boundary to continue. |
| target.edit | Editar alvo | Edit target |
| target.continue_receiver | Continuar no corpo remanescente | Continue on the remaining body |
| explosion.reverse | Inverter sentido da explosão | Reverse explosion direction |
| cutter.focus | Focar cortador | Focus cutter |
| cutter.from_selection | Criar cortador desta seleção | Create cutter from selection |
| materials.receiver | Material da cavidade | Cavity material |
| materials.insert | Material do inserto | Insert material |

Preferir “Prévia” em PT, sem alternar Preview/Prévia. Manter nomes de marca Part Splitter e de objetos do usuário. “Contorno (Loop)” pode ser termo didático na primeira ocorrência; restante consistente.

## Estratégia de implementação sem tradução dupla

Para atender override do addon independente do Blender, escolher uma camada explícita de resolução de texto. Renderizar texto já resolvido com translate=False nas chamadas que suportam isso; não passar frase PT resolvida de novo pelo catálogo en do Blender.

Verificar a API UILayout da versão mínima. Propriedades e enums podem receber tratamento diferente de rótulos: cobrir nomes, descrição/tooltips e cada enum exibido. Usar callbacks estáveis ou botões explícitos quando necessário; não reinicializar propriedades RNA a cada troca de idioma nem renomear seus identifiers.

Caso opte por integração nativa bpy.app.translations para AUTO, não manter duas estratégias concorrentes por widget. Isolar adaptação para override e testar menus/enum popovers; versões diferentes podem interpretar translate/context de forma diferente. Escolher a solução mais simples que passe nos testes PT/EN e documentar.

Strings retornadas por callbacks de enum devem ter vida útil estável; manter catálogo em memória, evitando construir itens efêmeros sem referência retida. Não adicionar complexidade dinâmica se botões existentes resolvem o requisito.

Formato: primeiro resolver template, depois formatar parâmetros. Não usar f-string final como chave. Validar igualdade de placeholders PT/EN, incluindo índice, unidade, nomes e causa aninhada.

Relatórios persistem code+params+severity+stage. Ao desenhar/mostrar report, resolver idioma atual; mudar idioma depois de uma falha muda texto do diagnóstico sem perder dados.

Exceções de domínio retornam códigos tipados; logs técnicos podem conservar traceback original. Erro não previsto vira mensagem amigável localizada + identificador para log; não despejar inglês técnico como única explicação.

Não substituir globalmente palavras nos fontes: nomes de propriedades, imports, operadores e filenames não são textos de interface.

## Auditoria e migração

scripts/auditar_textos.py extrai candidatos de labels, descriptions, textos de layout, reports e exceções. referencias/Auditoria_Textos_Atual.csv foi produzido na base atual 0.8.9; é inventário de candidatos, não prova de ausência de chaves nem teste de execução.

Auditar checkout atual 0.8.9:

1. ui.py: rótulos fixos e dinâmicos, tooltips de ajuda, status, instruções.
2. properties.py: names/descriptions e enum display.
3. operators.py: bl_label, bl_description, reports, popup/menu e last_status.
4. geometry_* e io_export: erros/avisos convertidos em códigos.
5. translations/help: unificar catálogos e remover fallback PT acidental em EN.
6. Scripts auxiliares destinados ao usuário: linguagem clara; logs técnicos podem ser técnicos.

Corrigir promessas de ajuda como “100% pronto para impressão” e “cavidade perfeita”: fechamento topológico não prova espessura, material ou montagem.

## Testes obrigatórios

- Blender EN + addon PT: nenhum inglês de interface do addon, exceto marca/nome do usuário.
- Blender PT + addon EN: nenhum PT em interface/erros/ajuda.
- AUTO com Blender PT/EN: resultado consistente.
- Tradução de interface/tooltips Blender on/off: override do addon mantém política definida.
- Trocar idioma com prévia válida e com erro salvo: geometria e dados iguais, texto atualizado.
- Painel, enums, tooltip, erro de encaixe, erro de loop, falha com prévia preservada, confirmação, continuidade e exportação.
- Reload/register/unregister repetidos: catálogo e handlers sem duplicações.
- Placeholders e plural/singular: mensagens1/2/5 encaixes/faces; valores não desaparecem ou trocam significado.

Referências oficiais em referencias/Fontes_Oficiais.md. Testar no Blender instalado; catálogo estático sozinho não comprova idioma renderizado.


---

# Mapa do código ATUAL recebido — manifesto 0.8.9

Não são linhas da 0.8.6. Fonte-base no pacote; snapshots numerados em referencias/codigo_atual_numerado. O arquivo-base não foi modificado.

## Pontos exatos para cada correção

| Requisito | Arquivo/função e trecho atual | Achado |
|---|---|---|
| INV-008 | geometry_material.py, slice_mesh_by_material; EXTRUDE662–684; BASE551–555/610–615 | Só profundidade/shift axial; mesmo contorno em A/B. |
| INV-012 | geometry_material.py303–339 e697–718/760–782 | target_iface_mat compartilhado; mesmo modo nos dois prismas. |
| INV-010 | operators.py168–201; geometry_material.py345–354 | Validação não mede calc_area/auto-interseção. |
| INV-014 | operators.py619–679 e1093–1112; gpu_drawing.py30–87 | Geração compara assinatura; troca/desenho não invalidam e draw filtra índices. |
| INV-011 | operators.py1595–1733; lifecycle.py | Commit ativaA;parent_op e reversão já existem. |
| INV-013 | geometry_connectors.py418–462/465–490; properties.py628–633 | CENTER25×25 opcional;LINEAR2/3 fixos; flagFalse. |
| INV-013/UI | ui.py378–383;operators.py1260–1288 | Flag passada ao domínio porém não desenhada na UI. |
| SOL-01 | operators.py503–544 e906–934 | Focar chama factory que recria noelse. |
| SOL/interface | geometry_solid.py270–382 | Retorna métricas sem CutInterface;materiais fallback0. |
| LANG | translations.py239–305; ui/properties/operators/lifecycle |25PT/26EN,locale-only e strings mistas. |

As faixas curtas identificam o bloco; use definição por função abaixo para localizar alterações após edições.

## Definições atuais

| Arquivo | Definição | Linhas |
|---|---|---|
| src/__init__.py | register | 10–15 |
| src/__init__.py | unregister | 18–23 |
| src/diagnostic.py | get_scene_scale_to_mm | 9–15 |
| src/diagnostic.py | analyze_target_mesh | 18–136 |
| src/geometry_connectors.py | ConnectorValidationError | 20–22 |
| src/geometry_connectors.py | point_in_polygon_2d | 25–38 |
| src/geometry_connectors.py | point_to_segment_dist_sq | 41–51 |
| src/geometry_connectors.py | min_distance_to_polygon_boundaries | 54–78 |
| src/geometry_connectors.py | find_optimal_grid_axes | 81–136 |
| src/geometry_connectors.py | create_capsule_2d_profile | 139–160 |
| src/geometry_connectors.py | create_pin_mesh_data | 163–249 |
| src/geometry_connectors.py | check_receiving_wall_thickness | 252–315 |
| src/geometry_connectors.py | compute_connector_layout | 319–651 |
| src/geometry_connectors.py | compute_connector_positions | 654–673 |
| src/geometry_connectors.py | validate_connectors | 676–725 |
| src/geometry_connectors.py | determine_connector_material | 729–794 |
| src/geometry_connectors.py | apply_connectors_boolean | 797–1017 |
| src/geometry_contract.py | CutInterface | 15–45 |
| src/geometry_contract.py | build_cut_interface | 48–191 |
| src/geometry_contract.py | SplitResult | 195–214 |
| src/geometry_loop.py | LoopSliceResult | 21–36 |
| src/geometry_loop.py | get_topology_signature | 42–66 |
| src/geometry_loop.py | capture_edge_loop | 69–153 |
| src/geometry_loop.py | capture_face_boundary_loop | 156–266 |
| src/geometry_loop.py | get_selected_seed_face | 269–283 |
| src/geometry_loop.py | slice_mesh_by_loop | 286–551 |
| src/geometry_loop.py | analyze_loop_region | 554–722 |
| src/geometry_loop.py | _get_orthonormal_basis | 725–733 |
| src/geometry_loop.py | triangulate_polygon_2d | 736–906 |
| src/geometry_loop.py | create_loop_prism_cutter | 909–967 |
| src/geometry_loop.py | slice_mesh_by_loop_extrude | 970–1135 |
| src/geometry_material.py | _get_orthonormal_basis | 22–30 |
| src/geometry_material.py | get_material_regions | 33–57 |
| src/geometry_material.py | _order_boundary_loops | 60–90 |
| src/geometry_material.py | list_material_regions | 93–101 |
| src/geometry_material.py | find_region_of_face | 104–116 |
| src/geometry_material.py | analyze_material_structure | 119–273 |
| src/geometry_material.py | create_material_patch_prism_cutter | 276–367 |
| src/geometry_material.py | slice_mesh_by_material | 370–837 |
| src/geometry_plane.py | PlaneSliceError | 13–15 |
| src/geometry_plane.py | NoIntersectionError | 18–20 |
| src/geometry_plane.py | count_mesh_islands | 23–43 |
| src/geometry_plane.py | cap_open_cut_boundaries | 46–128 |
| src/geometry_plane.py | evaluate_bmesh_metrics | 131–180 |
| src/geometry_plane.py | reconstruct_boundary_loops | 183–238 |
| src/geometry_plane.py | slice_mesh_by_plane | 241–406 |
| src/geometry_plane.py | compute_explosion_offsets | 409–428 |
| src/geometry_solid.py | SolidCutterValidationError | 22–24 |
| src/geometry_solid.py | SolidSliceError | 27–29 |
| src/geometry_solid.py | create_bmesh_capsule | 32–116 |
| src/geometry_solid.py | create_primitive_cutter_mesh | 119–182 |
| src/geometry_solid.py | validate_solid_cutter | 185–267 |
| src/geometry_solid.py | slice_mesh_by_solid | 270–381 |
| src/geometry_solid.py | compute_solid_explosion_offsets | 384–414 |
| src/gpu_drawing.py | _get_orthonormal_basis | 19–27 |
| src/gpu_drawing.py | _draw_loop_overlay | 30–132 |
| src/gpu_drawing.py | _compute_cut_line_segments | 135–236 |
| src/gpu_drawing.py | _draw_plane_overlay | 239–399 |
| src/gpu_drawing.py | _draw_overlay_callback | 402–415 |
| src/gpu_drawing.py | register_overlay | 418–430 |
| src/gpu_drawing.py | unregister_overlay | 433–441 |
| src/io_export.py | sanitize_unique_filename | 23–36 |
| src/io_export.py | get_material_rgba | 41–57 |
| src/io_export.py | rgba_to_hex | 60–66 |
| src/io_export.py | publish_staged_files_atomic | 69–117 |
| src/io_export.py | build_3mf_xml | 120–247 |
| src/io_export.py | export_objects_to_3mf | 250–286 |
| src/io_export.py | separate_object_by_material | 290–354 |
| src/io_export.py | export_objects_to_stl_by_material | 357–491 |
| src/lifecycle.py | get_or_create_collection | 27–34 |
| src/lifecycle.py | find_collection | 37–42 |
| src/lifecycle.py | ensure_backups_collection | 45–50 |
| src/lifecycle.py | find_operation_record | 57–64 |
| src/lifecycle.py | get_or_create_operation_record | 67–95 |
| src/lifecycle.py | record_created_object | 98–115 |
| src/lifecycle.py | record_unlinked_parent | 118–128 |
| src/lifecycle.py | capture_target_snapshot | 135–166 |
| src/lifecycle.py | discard_target_snapshot | 169–192 |
| src/lifecycle.py | resolve_operation_status | 199–245 |
| src/lifecycle.py | resolve_operation | 248–251 |
| src/lifecycle.py | check_child_operations | 254–281 |
| src/lifecycle.py | remove_preview | 288–410 |
| src/lifecycle.py | revert_committed_operation | 417–603 |
| src/operators.py | find_collection | 80–85 |
| src/operators.py | get_or_create_collection | 88–95 |
| src/operators.py | cleanup_collection_objects | 99–165 |
| src/operators.py | validate_printable_mesh | 168–200 |
| src/operators.py | get_target_bounds | 204–215 |
| src/operators.py | ensure_plane_guide | 218–254 |
| src/operators.py | read_plane_geometry | 257–270 |
| src/operators.py | compute_session_input_signature | 273–410 |
| src/operators.py | verify_preview_current | 413–445 |
| src/operators.py | get_current_session_parts | 448–500 |
| src/operators.py | ensure_solid_cutter | 503–544 |
| src/operators.py | update_preview_positions | 547–616 |
| src/operators.py | CHEST_OT_splitter_set_target | 619–678 |
| src/operators.py | CHEST_OT_splitter_clear_target | 681–716 |
| src/operators.py | CHEST_OT_splitter_create_work_copy | 719–774 |
| src/operators.py | CHEST_OT_splitter_create_or_focus_guide | 777–794 |
| src/operators.py | CHEST_OT_splitter_align_plane | 797–903 |
| src/operators.py | CHEST_OT_splitter_create_or_focus_solid_cutter | 906–934 |
| src/operators.py | CHEST_OT_splitter_select_existing_cutter | 937–964 |
| src/operators.py | CHEST_OT_splitter_generate_preview | 970–1505 |
| src/operators.py | CHEST_OT_splitter_invert_sides | 1510–1528 |
| src/operators.py | CHEST_OT_splitter_invert_male_female | 1531–1555 |
| src/operators.py | CHEST_OT_splitter_apply_connector_preset | 1558–1591 |
| src/operators.py | CHEST_OT_splitter_commit_parts | 1595–1733 |
| src/operators.py | CHEST_OT_splitter_remove_preview | 1736–1759 |
| src/operators.py | CHEST_OT_splitter_revert_cut | 1762–1827 |
| src/operators.py | CHEST_OT_splitter_restore_original | 1830–1871 |
| src/operators.py | CHEST_OT_splitter_redo_session | 1874–1899 |
| src/operators.py | CHEST_OT_splitter_capture_loop | 1902–1950 |
| src/operators.py | CHEST_OT_splitter_capture_face_boundary | 1953–2021 |
| src/operators.py | CHEST_OT_splitter_define_seed_face | 2024–2055 |
| src/operators.py | CHEST_OT_splitter_separate_by_material | 2058–2123 |
| src/operators.py | CHEST_OT_splitter_export_parts | 2126–2374 |
| src/operators.py | CHEST_OT_splitter_help | 2377–2411 |
| src/operators.py | CHEST_OT_splitter_select_split_material | 2412–2427 |
| src/operators.py | CHEST_OT_splitter_pick_material_region | 2430–2530 |
| src/operators.py | on_depsgraph_update_post | 2566–2634 |
| src/operators.py | on_undo_post | 2638–2652 |
| src/operators.py | on_redo_post | 2656–2669 |
| src/operators.py | register_handlers | 2672–2679 |
| src/operators.py | unregister_handlers | 2682–2689 |
| src/operators.py | register | 2692–2698 |
| src/operators.py | unregister | 2701–2707 |
| src/properties.py | _on_preview_transform_update | 24–31 |
| src/properties.py | _on_param_change_mark_stale | 34–39 |
| src/properties.py | _on_clearance_preset_update | 42–46 |
| src/properties.py | _poll_mesh_cutter | 49–51 |
| src/properties.py | _on_cutter_object_update | 54–81 |
| src/properties.py | _on_target_object_update | 84–86 |
| src/properties.py | ChestObjectRef | 89–93 |
| src/properties.py | ChestOperationRecord | 96–118 |
| src/properties.py | ChestSplitterSettings | 121–797 |
| src/properties.py | register | 807–816 |
| src/properties.py | unregister | 819–830 |
| src/translations.py | _get_current_locale | 297–305 |
| src/translations.py | get_help_tooltip | 308–315 |
| src/translations.py | get_help_popup_content | 318–327 |
| src/translations.py | register_translations | 333–341 |
| src/translations.py | unregister_translations | 344–352 |
| src/ui.py | draw_help_button | 7–11 |
| src/ui.py | VIEW3D_PT_chest_part_splitter | 14–534 |
| src/ui.py | register | 537–541 |
| src/ui.py | unregister | 544–548 |

## Testes com cobertura insuficiente

| Arquivo | Caso | Lacuna estática |
|---|---|---|
| tests/test_inv_001_003_material.py | test_d01_bent_patch_cutter_validation | Não exige lançamento; faces opostas desconectadas. |
| mesmo | test_d02_materials_slots_preservation | Fallback só verifica success; não cavidade/receptor. |
| mesmo | test_d03_clearance_progression | Sem fixture real não executa asserções;volume monotônico não prova folga lateral. |
| mesmo | test_d06_nominal_complementarity | Só verifica volumes positivos. |
| tests/run_all_tests.py | TESTS |28 suites listadas; novos requisitos exigem adições explícitas. |


---

# Guia de alterações pequenas e revisáveis

Estas são instruções/pseudocódigo, não patches já testados. O mapa atual localiza as funções. Não modificar fontes do pacote-base: implementar em checkout separado.

## 1. Captura — operators + gpu_drawing + lifecycle

Introduzir serviço de estado da captura, com funções distintas:

- clear_capture(settings, reason): limpar índices, seed, flag, contagem, planicidade, razões e propostas dependentes.
- inspect_capture(target,settings,context): resultado válido/inválido com razão, origem, signature, ciclos/arestas.

set_target chama clear_capture quando muda objeto/mesh/sessão; chamar novamente na preparação do receptor confirmado. Overlay consulta validade e não desenha inválidos; não mutar RNA/cena dentro do callback GPU a cada frame.

Geração reutiliza inspect_capture; remover duplicação de checks que possam discordar entre UI e operador. Se modoEdit usaBMesh vivo, assinatura/índices precisam ser do mesmo snapshot; não comparar mesh.data ainda não sincronizado com captura recém-editada.

## 2. Materiais — geometry_material

Esboço do argumento por operando:

```text
insert_policy = chosen_insert_policy
receiver_policy = BODY
prism_a = cutter(..., interface_material=resolved_insert_material)
prism_b = cutter(..., interface_material=resolved_receiver_material)
result_a = intersect(source, prism_a)
result_b = difference(source, prism_b)
assign_new_interface_materials(result_a, result_b, provenance)
preserve_original_exterior_materials(...)
```

Converter politicaSOURCE/EXTRACTED legado para regras novas explicitamente. Se optar por manterAPI existente, passar política BODY/SOURCE apenas ao prisma B é correção inicial, mas teste do resultado continua obrigatório.

Não classificar toda A como “face nova”. Recoloração total deA deve ser opção separada. Exterior deB remanescente não é reparado por pintura única.

## 3. Validação — operators.validate_printable_mesh

Adicionar check de área e colinearidade antes de sucesso, com unidade:

```text
area_mm2 = face.calc_area() * scale_to_mm**2
if numeric_degenerate(face, area_mm2):
    return invalid(code=DEGENERATE_FACE, face_ids, stage)
```

Usar mesma função no cortador/candidato. Incluir limites físicos/tolerância numérica explícitos, sem inventar limite universal de impressão. Os índices deTestes1 ajudam reprodução, não devem ser hardcoded na extensão.

## 4. Folga — separar domínio lateral de profundidade

Substituir apenas depth_a/depth_b por construção que retorna lateral_domain_a/b + bottom_offset_a/b. Inputs: domínio nominal, folga lateral, fundo, alvoPART/CAVITY/BOTH.

Gerar cortadores da geometria offset e preservarposição da abertura exterior. Não usar scale_global emA ou prismas. Devolver diagnóstico de colapso com região afetada.

## 5. Encaixes — reutilizar compute_connector_layout

Extrair helpers já existentes para pipeline:

```text
nominal_candidates = generate_for_requested_layout(...)
safe_candidates = filter_by_complete_footprint_and_domain(...)
proposed = search_or_score_for_count_if_requested(...)
valid3d = verify_receiving_volume_and_attachment(...)
return ConnectorProposal(positions, status, reasons, resolution)
```

Expor adjust_to_valid_area enquantoAUTO_SHAPE é implementado; não chamar grade25×25 de solução exata. Reusar distância às bordas/validadores, ampliando para múltiplos candidatos e cápsula.

Guardar proposta com origem/interface e posiçõesUV/oumundo consistentes. Manual e pinosfixos revalidam; não bypass do domínio.

## 6. Continuação — lifecycle

Novo operador de continuar usa resolve_operation, record de confirmação e created_objects/roles existentes. Não usar active_object como única origem após commit, pois o código atual ativaA.

Criar papel semântico deRECEIVER/INSERT para associação, compatível com legados. Ligação de operação filha usa chest_operation_id do receptor; não limpar esse metadado ao torná-lo alvo. NovoIDgerado pela próxima geração, não no simples foco.

## 7. Cortador — separar factory/resolver/focus

ensure_solid_cutter pode ser dividido em get_session_cutter, create_session_cutter e reset_session_cutter. focus só seleciona/enquadra.

Objeto externo não passa porreset/cleanup de owned_objects. Duplica mesh se criar cópia editável. Novas ferramentas de referência usam snapshot e coordenadas físicas.

## 8. Idioma — preferências, templates e erros

Registrar AddonPreferences uma vez e catálogoPT/EN central. Código de erro não é uma frase traduzida. Relatórios armazenamparams+code; renderer e operator.report traduzem no momento de apresentação.

Idioma não entra na assinatura geométrica nem altera validação da prévia. Testar enums, descriçãoRNA, popup e fallback técnico, não apenas labels do painel.

## 9. Testes e entrega

Adicionar casos assertivos aos testes existentes; registrarSKIP sefixture ausente. D06 deve realmente medir sobreposição/cobertura quando anunciado, não apenasva>0/vb>0.

Encaixes emSOLID/MATERIAL ainda são bloqueados na base. Para prisma planar derivado que suporte novos pinos, adicionarCutInterface real evalidadores; manter recusa para sólidos gerais seminterface. Não reutilizar settings.loop_interface_normal antigo.

Cada patch tem teste da causa e uma regressão associada; só depois ampliar. Nenhum trecho deste guia autoriza apagar malha/caches do usuário fora da operação em foco.


---

# Relatório de implementação — preencher pelo Antigravity

## Identidade

- Checkout/caminho do módulo carregado:
- Versão antes/depois:
- SHA da base e da entrega:
- Blender/Python/OS testados:
- Dependências novas, licenças e empacotamento:

## Por requisito

Para INV-008/009/010/011/012/013/014, SOL-01/02/03/04/05/06 e LANG-01:

- Estado: CORRIGIDO / IMPLEMENTADO / FALHOU / BLOQUEADO / SUPORTE RESTRITO.
- Causa confirmada no código atual, com arquivo/função:
- Mudança e comportamento final:
- Testes CSV executados:
- Evidência antes/depois:
- Riscos/limites:

## Testes

Anexar 05_TESTES_ACEITE.csv preenchido. Resultados permitidos: PASSOU, FALHOU, BLOQUEADO, NÃO EXECUTADO. Não usar PASSOU para plano de teste, análise estática ou sintaxe.

Separar reprodução na cena original, fixture sintética e validação física. Informar quando um caso precisa de cena adicional.

## Entregáveis

- ZIP instalável 0.8.9.
- Changelog final coerente com escopo.
- Cenas corrigidas separadas, originais preservados.
- Screenshots PT e EN dos novos controles e erros.
- Scripts/testes usados e logs relevantes.
- Limitações de offsets, interfaces não planares e sugestão geométrica.

## Condições de aprovação

Nenhum P0 pendente silenciosamente; todas as ferramentas de escopo suportado demonstradas. Recurso incompatível recebe diagnóstico precoce específico. Nenhuma conclusão de resistência/encaixe físico sem ensaio.

Não confundir melhoria de mensagem com correção de geometria. Não chamar a versão de pronta para venda apenas porque os casos visuais parecem melhores.
