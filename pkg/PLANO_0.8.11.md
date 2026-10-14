# Part Splitter 0.8.11 — plano de implementação para Antigravity

**Base obrigatória:** `base/chest_part_splitter-0.8.10.zip`. **Data:** 14/10/2026, America/Sao_Paulo. **Versão alvo confirmada pelo pedido mais recente:** 0.8.11, substituindo a designação anterior “1.11”. **Agente de destino:** Gemini no Antigravity, conforme preferência do usuário por Flash 3.8; não presumir APIs/capacidades a partir desse nome.

Este pacote contém plano técnico, evidências, código original, trechos com linhas, histórico de requisitos e arquivos Blender. É um plano, não um ZIP de extensão corrigida. O código foi analisado estaticamente; 17 arquivos Python passaram por parsing AST. Não havia Blender nem `bpy` disponíveis: nenhuma reprodução dos `.blend` ou teste geométrico/GPU foi executada nesta análise. Todas as verificações funcionais abaixo são trabalho obrigatório do implementador.

## 1. Prompt de entrada — copiar para o Antigravity

Leia este plano, AUDITORIA_CODIGO.md e as evidências antes de editar. Trabalhe sobre a base 0.8.10 incluída. Primeiro reproduza os casos em cópias de Padrao_1.blend; compare com as capturas, pois o estado salvo pode diferir do estado mostrado. Corrija sincronização do plano antes das alterações maiores. Depois execute os gates deste documento, em sequência, sem implementar tudo num único patch.

Preserve malhas originais, materiais externos, medidas físicas, undo, restauração e isolamento por operação. Não remova verificações para produzir uma prévia aparentemente bem-sucedida. Não altere quantidade/diâmetro/profundidade/folga silenciosamente. Não prometa algoritmo automático sofisticado para todas as formas: o lançamento exige padrões editáveis 1–4, manual funcional e validação correta. Explique limitações e produza evidência de teste.

Para cada tarefa, registre: causa comprovada ou hipótese; função atingida; teste antes/depois; resultado observado; pendências. Não considere comentário ou CHANGELOG prova de correção. Se Blender estiver indisponível, faça somente verificações possíveis e marque execução pendente. Ao final, entregue ZIP instalável 0.8.11, changelog factual e relatório dos gates realmente executados.

## 2. Objetivo comercial e limites

A extensão deve separar peças para impressão 3D por Plano, Loop, Material e Sólido. Região superficial ou relevo com apoio válido deve poder ganhar uma base de profundidade editável, com cavidade complementar, folgas e encaixes. Poucas categorias de corte; o usuário não deve precisar distinguir quatro algoritmos internos para extrair um relevo com base.

**Entrega obrigatória nesta versão:** bugs atuais de geometria/estado/material, plano visual sincronizado, padrões editáveis, posicionamento manual visual, base/profundidade coerente em Loop e Material, suporte a encaixes em Material, folgas independentes e tradução didática.

**Pesquisa com custo limitado:** melhora incremental de sugestões automáticas para U/L/S. Pode entregar algoritmo experimental desativado por padrão ou proposta documentada; não é condição de lançamento encontrar posicionamento ótimo em toda forma. Não incluir suporte irrestrito a base curva/dobrada nem otimização estrutural sem definição de cargas. Interface não planar exige decisão explícita sobre suporte e direção de montagem.

**Restrições de confiança:** prévia antiga preservada em falha continua útil, mas deve ser identificada como antiga e não pode ser confirmada como resultado dos novos parâmetros. Ausência de posição válida no padrão não equivale a impossibilidade física de colocar pinos manualmente.

## 3. O que mudou desde 0.8.9 — não reimplementar às cegas

| Tema | Código 0.8.10 efetivamente lido | Trabalho 0.8.11 |
|---|---|---|
| Cortador criado do Loop | Helper retorna Object, ativação SOLID e inversão existem | Regressão, estado Edit Mode e ownership |
| Cortador criado do Material | Retorno melhorado, mas chamada de análise ainda incompatível | Corrigir contrato: tarefa A02 |
| Origem/apoio de cortador | Fórmula baseada em a_local já existe | Regressão de face/quina, resize e orientação |
| Seleção ao confirmar | Seleciona só extraída e avisa edição proporcional | Não registrar seleção conjunta como bug atual sem reprodução |
| Tolerâncias | Comprimento/coincidência convertidos com scale_to_mm | Rever espaços de coordenadas e pós-encaixes, não desfazer avanço |
| Saneamento micro | Existe e é chamado antes de encaixes | Risco de mutação/sem rollback e ausência de etapa equivalente pós-encaixes |
| Tampas | CDT já tentada antes de ear clipping | Corrigir mapa de origem, fallback e material; não dizer “adicionar CDT” |
| Base adicional Loop | loop_detach_add_base/depth/clearance e cavidade existem | Interface deslocada, folgas e análise de espessura precisam revisão |
| Interface Loop EXTRUDE | Contorno agora deslocado para fundo na extração não passante | Regredir; passante não tem fundo necessariamente |
| Overlay sólido | Desenho ciano já existe | Regressão de visibilidade e estado GPU |
| Overlay plano | Continua lendo settings enquanto corte lê guia | Fonte única em A01 |
| Idioma | Há catálogo/traduções, mas capturas continuam mistas | Auditar caminhos reais e preferências, não confiar no changelog |
| Material + encaixes | Branch ainda exclui MATERIAL em assinatura/geração/status | Implementar após interface válida em A06 |

Linhas e trechos próprios estão em AUDITORIA_CODIGO.md. As referências numéricas são da base, não da futura implementação.

## 4. Catálogo de evidências e classificação

Todas as imagens recebidas estão em imagens/, com nomes seguros e índice na GALERIA.html. A tabela abaixo reúne os grupos que determinam o escopo. Consultar REGISTRO_RELATOS.md para parâmetros e distinções históricas.

| Grupo | Arquivos de imagem — sufixo de horário | O que sabemos |
|---|---|---|
| E01 | 200451, 200613 (14/10) | Plano guia move com G, overlay fica em outra altura; corte segue guia |
| E02 | 192339 | Material, EXTRUDE 5 mm, região com relevo: resultado inadequado; correção do usuário confirma Material, não Loop |
| E03 | 193654, 193724, 193734, 193740, 193750 | Num caso 2 funciona, 1/3/4/Auto falham após encaixes com 2 arestas quase nulas em A; não generalizar para todos os casos |
| E04 | 194115, 194302, 194313, 194322 | S: 1/2 funcionam, distribuição insatisfatória; 3/4 falham por domínio/margem |
| E05 | 194414, 194511 | L por Loop: usuário relata 1–4 falham; Auto rejeita #1; tentativa de diâmetro 2 mm não tem novo resultado visível |
| E06 | 194940 | Zigue-zague concavo: 2 falha por domínio/margem; ajustar ligado |
| E07 | 195129, 195401, 195459 | Loop: AUTO DETACH tem pontas finas/problema de direção relatado; EXTRUDE 5 mm adequado; pedido material da base |
| E08 | 200011, 200157, 200301 | Saliência verde: 1/2/3 funcionam pelo relato; 4 rejeitado é esperado neste caso; tampa com triângulos brancos |
| E09 | 145344, 145428 (13/10) | Quina: falha antiga com 3 arestas quase nulas em B, caso histórico de regressão |
| E10 | 150643, 150649, 150915 (13/10) | Loop plano 16/4 pontos falhava na 0.8.9; testar se reparado na 0.8.10 |
| E11 | 150956, 151200, 151346 (13/10) | DETACH funcionando, tampa em leque e saliência fina; controles históricos |
| E12 | 143251, 143731, 144535, 144555 (13/10) | Dificuldade de alinhar caixa, deformação manual de um vértice; justifica fluxo integrado |

**Não confundir três classes:** (1) contenção/margem rejeitada antes do booleano; (2) degeneração criada após pinos; (3) resultado válido, mas distribuição pouco útil. O modo manual ajuda (1)/(3), mas não conserta automaticamente (2).

**Prévia antiga:** nas falhas com mensagem “The visible preview is the previous valid one”, objetos/pinos desenhados não são resultado parcial da tentativa atual. Preservar isso em testes e relatos. Normal geométrica, normal da tampa, direção de extração e explosão visual são variáveis diferentes.

## 5. A01 — plano guia, overlay e corte: mesma geometria atual (P0)

**Achado confirmado:** gpu_drawing.py::_draw_plane_overlay, linhas 254–265, usa plane_origin/plane_normal armazenados. operators.py::read_plane_geometry, 264–277, lê matrix_world do guia e atualiza settings. Corte/signature usam esse reader em momentos específicos; movimentação não garante overlay atualizado. Evidência visual é consistente com essa divergência, embora a execução ainda precise provar a causa no caso.

**Implementação:** extrair helper puro, por exemplo resolve_plane_state(scene, settings, guide) em módulo neutro. Retornar origem/normal/base tangente mundiais e offset físico aplicado uma única vez. Desenho, linha de interseção, bisect/corte, assinatura e alinhamentos devem usar o mesmo contrato. Callback GPU não cria coleções, não altera settings e não dispara recursão do depsgraph. Preferir referência ao guia da sessão; evitar capturar objeto homônimo errado.

Normal de plano transformado: calcular por inversa transposta ou tangentes transformadas; tratar escala singular e espelhamento. Ler matriz atual durante G/R, redesenhar; undo e cancelar transformação também atualizam. Deslocamento pelo painel deve coincidir com o plano efetivo, sem aplicar offset no guia e depois de novo no corte. Retângulo pode ser centrado na projeção do alvo, mas sempre coplanar; movimento tangencial não exige centro idêntico, movimento normal/rotação exige plano idêntico.

**Gate G1:** mover G normal/tangencial, girar R, alinhar Face/Cursor/Eixos, offset 0/±2 mm, desfazer/cancelar e gerar corte: linha e superfície visual coincidem com a seção real antes de atualizar preview. Conferir montado com explosão zero; explosão posterior não deve alterar geometria física.

## 6. A02 — Criar cortador desta seleção, contrato Material ainda quebrado (P0)

**Achado confirmado:** operators.py, linha 1400, chama `analyze_material_structure(target, scene=context.scene)`. Em geometry_material.py:190 a assinatura é `analyze_material_structure(obj, material_index, region_index=0)`, sem scene. mat_idx/reg_idx foram lidos, mas não enviados. Essa chamada gera erro de keyword antes de construir o prisma.

Correção mínima: enviar obj, material_index, region_index e verificar analysis.valid; se tornar scene explícito, adaptar assinatura e todos os consumidores conscientemente. Não confundir com contrato do helper que retorna Object: essa parte melhorou na 0.8.10. Conferir referência viva em Edit Mode, domínio planar e inversão antes de criar cortador. Não assumir normal default para análise inválida.

Sucesso cria um único objeto, em coordenadas coerentes, ligado à coleção de guias, SOLID ativo, material/região corretos, fonte intacta e seleção exclusiva. Falha/cancel libera recursos. Testar ilhas da mesma cor e região sem apoio. Diálogo editável de profundidade/inversão deve estar acessível sem depender de F9.

## 7. A03 — contrato comum de apoio/base para Loop e Material (P0/P1)

**Decisão de produto:** não acrescentar outro modo de corte. Dentro de Loop e Material, apresentar “Profundidade da base (mm)” quando aplicável; AUTO pode reconhecer apoio e recomendar base, mas deve exibir o valor, sem adquirir espessura silenciosa. Região plana vira inserto; relevo mantém todo o exterior e ganha base retirada do corpo; receptor recebe cavidade complementar.

**Três conceitos geométricos distintos:** plano do contorno, plano de apoio e faces selecionadas do relevo. Não exigir que todas as faces do cone sejam coplanares; exigir uma referência válida para o volume extraído. Sem apoio confiável, bloquear/solicitar referência, sem extrudar por normal média arbitrária. Isso resolve a exigência de Material não gerar resultados inválidos e preserva a intenção cone+quadrado.

**Material atual:** analyze_material_structure encontra contorno e classifica faces coplanares/relevo. EXTRUDE (geometry_material.py:759 em diante) passa todas as faces da região para create_material_patch_prism_cutter e as desloca numa direção média. Não é um prisma definido somente pela base; em relevo pode gerar cascas/volumes inadequados. Extrusão não bloqueia pela mesma exigência usada em BASE. BASE ainda exclui coplanar_base_face_indices quando há relevo: isso não realiza a intenção de extrair todo o quadrado pintado com base grossa. Mais de um loop é rejeitado como corpo/base; distinguir furos válidos de região externa envolvente antes de anunciar suporte.

**Loop atual:** DETACH com base já cria laterais e tampa deslocadas. Ao final, build_cut_interface ainda recebe centroid_world/loop_coords_world/tri_indices originais, mesmo com base deslocada. Isso deixa a referência de encaixes no topo antigo, em vez da interface efetiva da base. Corrigir com dados gerados e validados; não só somar profundidade ao ponto sem atualizar domínio e triângulos.

**Arquitetura recomendada:** análise de referência comum (região selecionada, contornos externos/furos, origem, normal interior, plano, suporte e motivos); gerador de volume de extração/base; split A/B; interface real; materiais; encaixes. Usar wrappers dos modos antigos para migrar cenas, sem expor classes internas na UI.

Para apoio planar: construir volume com footprint exato, abrangendo altura máxima do relevo para fora e d para dentro. Candidato `A = alvo ∩ volume`, `B = alvo − volume`, ou construção topológica validada. Não tornar booleano universal sem medir resultados. Evitar extração de outros detalhes/ilhas alcançados pelo volume. Profundidade começa no apoio, não no topo do relevo. Base não modifica silhueta exterior nem extruda individualmente cada face por sua normal.

**Espessura:** amostras dentro do domínio, incluindo áreas de risco, com raycast físico; centroid pode ficar fora de U/L. eps do ray_start e parede mínima em mm, não `1e-4` BU. Medir footprint do alojamento e material disponível nos dois lados. Se espessura inconclusiva, não tratar como infinita. Não atravessar parede silenciosamente. Corte passante pode não ter fundo de apoio; não fabricar interface plana utilizável para pinos onde não há contato.

**Apoio dobrado/não planar:** o caso verde não prova esse tipo de apoio pelas imagens. Primeiro medir no arquivo. Se realmente não planar, preservar DETACH que funciona; base adicional para contato curvo requer inserção sem undercuts/autointerseção e direção definida. Não exigir solução geral nesta versão: explicar limitação e manter o caso funcionando.

**Gate G2:** cone/relevo+região quadrada por Material e Loop, d=0/1/2/5 mm, parede suficiente/insuficiente, concavidade e furo válido; exterior original, base contínua, cavidade correspondente, materiais preservados. Regressão de verde com 1/2/3 e laranja por profundidade.

## 8. A04 — folgas independentes e físicas (P1)

Separar profundidade nominal da base, folga lateral da base, folga de fundo/base e folgas radial/diametral e de fundo dos pinos. Documentar por lado versus total. Convenção sugerida: UI lateral por lado e pinos por lado, com total diametral mostrado (como já ocorre); fundo axial separado. Não inventar valores padrão aprovados pelo usuário; preservar cenas existentes e oferecer presets rotulados.

**Achado Material:** part_clearance_mm afeta tanto depth_a/depth_b quanto lat_off_a/lat_off_b; revisar propriedades e fluxo para evitar controles distintos apontarem ao mesmo parâmetro. **Achado Loop com base:** vértices originais de boca B não se deslocam lateralmente, mas novos vértices de fundo recebem offset. Isso pode criar cavidade inclinada com folga no fundo e nenhuma na boca. Confirmar geometricamente e gerar envelope que respeite folga por toda a inserção.

Definir lado de aplicação: reduzir base, ampliar cavidade ou repartir. Exterior nominal preservado quando necessário; não retirar relevo colorido visível para aliviar base sem aviso. Validar offsets U/L/furos, colisões de fronteiras, miter em cantos e região que desaparece. Não aumentar epsilon como substituto de folga, nem expandir footprint do corte silenciosamente para evitar booleano degenerado.

Contato de encaixes com peças separadas por folga precisa de duas superfícies reais/transformação de montagem. Um único plano médio pode gerar pino desligado da base ou furo raso. Fixar semântica de projeção útil, penetração de união e profundidade de alojamento.

## 9. A05 — padrões editáveis e manual visual (P1, requisito comercial)

Fluxo: gerar prévia sem pinos → Posicionar encaixes → interface acessível → marcador fantasma circular/cápsula segue cursor → clique adiciona → arrastar move → controle gira cápsula → excluir/desfazer → Aplicar encaixes. Cancelar restaura estado anterior. Sem selecionar centro de triângulo ou editar malha da prévia; posição contínua do clique. Receptor oculto/translúcido e vista perpendicular opcionais.

Padrões 1/2/3/4 geram **os mesmos marcadores** do manual. Ajustar espaçamento/orientação do conjunto; converter para edição individual sem apagar tudo. Não forçar padrão linear no vazio do U/L. Quantidade solicitada ≠ capacidade física; avisar que o padrão não coube, sem declarar ausência absoluta de posições válidas. Não reduzir quantidade silenciosamente. Verde significa validação concluída da posição, vermelho indica motivo; estado pendente não é verde garantido.

**Dados propostos:** coleção de ConnectorSpec com ID estável, u/v físicos ou BU com convenção explícita, perfil, yaw, medidas/folgas, lado macho e estado. Preferir parâmetros globais inicialmente, orientação/posição por pino; overrides só se necessários. Assinar interface/target topology e versões de parâmetros. Não guardar referências frágeis a BMFace para uso após troca de malha.

**Viewport:** converter mouse→raio com bpy_extras.view3d_utils; intersectar superfície de contato real ou plano+domínio de interface. Raycast em face externa do relevo não serve. Não aceitar vazio ou clicar atrás da peça por ausência de hit. Mostrar footprint do pino, alojamento com folga e margem opcional; marker preso à interface. Coordenadas canônicas em montagem; mapear matriz de exibição explodida e sua inversa. Explodir 191,1 mm não muda posição física. Cancelar/finalizar limpa handlers e estado modal; navegação de viewport deve continuar disponível.

Somente desenho/checagem leve durante drag; booleanos ao Aplicar, sobre candidatos reconstruídos de corte sem pinos. Não empilhar pinos em resultados anteriores a cada movimento. IDs internos não exportáveis, não criar auxiliares selecionáveis desnecessários. Foco no Object Mode, com ajuda clara PT/EN.

**Gate G3:** S/U/L/zigue-zague, triangulações diferentes, d/folga mudam após markers, explosão/câmera, cápsula girada, click no vazio, cancel/undo/reopen. Manual em região com espaço deve funcionar mesmo quando padrão falha. Isso não dispensa validação final booleana.

## 10. A06 — encaixes também em Material (P1)

operators.py:403, 1891, 1973, 2062 exclui MATERIAL juntamente com SOLID para assinatura/geração/status. Não basta remover uma condição: Material precisa retornar interface real, regiões/furos e espessura válidos. Reusar o pipeline comum de layout/spec/validação/booleano para Plano, Loop e Material; SOLID arbitrário fica explicitamente sem suporte de interface automática se não definida.

Parte extraída/receptor são papéis semânticos, independentes de A/B e invert_sides. Trocar lado macho altera geometria pino/furo, não direção da explosão. Material: pino da cor apropriada da peça, cavidade da cor do receptor; base pode ter material escolhido. Testar assinatura stale quando parâmetro de pino muda em Material, suporte à folga e export.

## 11. A07 — contenção exata e sugestões automáticas modestas (P0/P1)

**Achados atuais:** layout usa centro de bounds; CENTER tenta malha 25×25 se ajuste ligado; LINEAR_2 varia distância em linha central; LINEAR_3 mantém centro e não faz busca equivalente; GRID_4 contrai grade centrada sobre axes/bounds, olhando outer_polys[0]; AUTO varia uma linha ou busca um ponto. Isso não explora toda área real do L/S. Rejeição final do padrão é correta se inválido, mas não demonstra inviabilidade da região.

A validação final amostra centro + 16 pontos do círculo ou perfil de cápsula de 24 segmentos. Amostragem discreta pode perder passagem de borda/furo entre pontos. Não assumir que “todos os pontos testados estão dentro” prova contenção do polígono/cavidade inteira. Pipeline comum deve verificar domínio externo menos furos, distância às fronteiras e interseções dos segmentos/perfil. Para círculo, centro interno + distância mínima exata às bordas >= raio+cavidade+margem é critério útil num domínio planar simples validado. Para cápsula, usar segmento central, raio e limites/orientação, ou região 2D robusta; tratar ilhas/furos, sem convex hull.

Separação cápsula-cápsula não deve ser só distância de centros ou bounding circle excessivamente conservador. Broad phase pode usar bounds; narrow phase usa perfil orientado e distância física. Amostras de espessura atuais cobrem centro e 4 pontos radiais, não extensão inteira da cápsula: incluir footprint alongado e material de ancoragem macho.

Proposta incremental de Auto: candidatos em domínio real, validação completa, seleção determinística com distância de borda + afastamento + cobertura; fallback para editar marcadores se padrão falha. Limitar tempo/resolução e declarar incerteza. Não reduzir diâmetro/cápsula sem escolha explícita. `adjusted_capsule_length_mm` já pode modificar settings: rever para sugestão confirmável, evitando alteração de parâmetros no meio de geração/assinatura.

**Gate:** nenhum encaixe no vão de U/L/S, sem perfil cortando borda/furo; nenhuma promessa de optimalidade mecânica. Verde com 4 rejeitado por footprint fica controle de rejeição legítima, não bug que precisa ser forçado a passar.

## 12. A08 — degenerações após pinos e cápsulas (P0)

**E03:** um caso 2 funciona, outros padrões falham com arestas quase nulas em A. Não usar modo manual como substituto desta correção. create_pin_mesh_data:163 tem offset de base e chanfro, apply_connectors_boolean:863 cria UNION/DIFFERENCE EXACT. Verificar construção standalone fechada, sobreposição efetiva com macho, orientação, stack de modificadores e cleanup. Não culpar posição antes de inspecionar etapa e elemento defeituoso.

Diagnosticar cada estágio: alvo, corte sem pinos, cada união, cada subtração, conjunto final. Coordenadas/comprimentos em mm e papéis dos objetos. Testar 7 mm/4 mm/0,34 mm/0,1 mm lateral/0,5 mm fundo, com 1/2/3/4/Auto; chanfro zero e perturbação mínima de posição apenas como diagnóstico, não correção silenciosa. Posicionamento coincide com vértice/aresta antiga? registrar e testar.

**Saneamento atual:** diagnostic.py:141 retorna sucesso após weld sem verificar manifold dentro da função, apesar do docstring; caller revalida em outro estágio. Targetmap deve resolver cadeias/conflitos de forma determinística; cópia/rollback obrigatório. Chamadas de saneamento existem nos candidatos antes dos encaixes; a validação após encaixes não tem reparo equivalente. Acrescentar saneamento após booleanos só se medições provarem a necessidade e se preservação de dimensão/domínio/materiais for demonstrada. Não usar merge/dissolve global. R5 documenta que dissolve pode produzir non-manifold.

Sucesso exige A/B sólidos válidos, sem NaN/Inf, faces duplicadas/internas, aberturas ou autointerseções detectadas. Sem folga/conectores, união e diferença devem recuperar alvo, interseção desprezível; soma de volumes não basta. Com pinos e folgas, usar balanço de volume esperado, testar união do conjunto montado e cavidade correta. Candidatos falhos nunca substituem última prévia válida.

## 13. A09 — normal, direção física e explosão separadas (P0)

No DETACH, normal_a_to_b vem de média de normais de tampas recalculadas ou de Newell; média não ponderada e fallback winding podem inverter direção percebida. Não concluir a causa só pela imagem: 195401 também mostra stale. Medir Frame montado, Face Orientation, região escolhida, vetor de inserção e normal persistida da operação. Guardar orientação semântica por geometria/ocupação, não ordem incidental de arestas.

Separar n_geom, inward, lado macho e dir_explosion. Inverter explosão não troca A/B nem material/pinos. A/B semânticos não devem ser reatribuídos pelo sinal da normal. Refazer interface na profundidade real, snapshots montados imutáveis e direção congelada por prévia. Testar loops CW/CCW, seed alternativa válida, rotação/espelho, 10 ciclos explode=0/37,6/191,1 e invert. Sem deriva/corte se mover por visualizar.

## 14. A10 — materiais de tampas/base/pinos (P1)

**Achado claro:** geometry_loop.py:652–665 faz herança de material por adjacência a faces que não foram criadas. Triângulo novo sem vizinho antigo não recebe material explícito e fica no índice inicial. Isso é consistente com triângulos brancos entre verdes. Provar material_index no caso, pois shading/z-fighting também devem ser excluídos.

Antes de criar faces, resolver material semântico da região extraída/receptor. Atribuir a todas as novas faces e mapear slots por identidade de material. Não inferir separadamente cada triângulo, nem repintar toda a malha. Faces inferiores novas de saliência verde devem ficar verdes por padrão. Controle “Material da base” permite material da peça/receptor/material escolhido; cavidade é opção independente com default receptor. Preservar cores externas multicolor. Pinos podem seguir superfície predominante ou escolha explícita; material da base não muda material global compartilhado.

Testar reordenação de slots, múltiplos materiais, triangulação diferente, confirmação, undo e 3MF. STL não carrega materiais. Não mascarar erro de índice só mudando cor de preview.

## 15. A11 — tesselação com fronteira íntegra (P1)

CDT existe em geometry_loop.py:933–965. Usa `orig_v[output_index][0]` ou, se vazio, output_index como índice original. Isso não é contrato seguro quando CDT cria/funde pontos. Aceita número de triângulos >= n-2, sem provar cobertura do domínio ou conservação da cadeia de borda. epsilon 1e-6 em UV/BU não tem política física unificada. O fallback ear clipping ainda precisa revisão de casos sem orelha. Registrar domínio, fronteira, área e maps; não confiar no docstring de garantia.

Escolher contrato que retorna vertices2d/triangles/mapping quando há pontos internos; preserva todos os vértices de borda necessários, incluindo colineares. Criar mesma superfície para ambas as partes, normais opostas. Medir cobertura e overlap; nenhum triângulo externo/T-junction. Não fazer convex hull, global remesh ou n-gon atravessando U. Qualidade é objetivo secundário à validade; comparar ângulos/aspecto com leque observado. Se não suportar furos, falhar explicitamente antes de publicar.

## 16. A12 — estado/undo, alinhamento, idioma e acabamento (P1/P2)

**Estado:** verify_preview_current já existe; inspecionar assinatura por modo incluindo todos os novos parâmetros/markers/materiais/folgas/topology. UI distingue solicitação atual, última configuração aplicada e falha. Confirmar inválido/stale bloqueia; preservar preview antiga com badge visível. Regredir remover prévia, reverter corte, continuar receptor, sessões paralelas, alterações de alvo/guia e Ctrl-Z.

**Alinhamento face/quina:** preservar as correções já presentes; apoio por a_local, referência compartilhada e sem cursor/origem obrigatórios. Verificar anchor fixa ao alterar escala (properties::_on_solid_dim_update ainda só muda scale). Implementar realinhar/desfazer referência com invalidação de topologia. Validar 3 faces/canto único, ordem selecionada, escala negativa e quina rotacionada. Não misturar isso com sincronização de plano.

**Idiomas:** screenshots ainda têm Boundary Loop Cut, Add base for fitting, Enable Connectors, Cut Distribution, Nominal Dimensions, Warning Last update failed e mensagens de preview em inglês. Catálogo não basta: conferir todos os labels/tooltips/enums/status/diálogos no caminho real PT_BR/EN_US/AUTO. Não traduzir IDs usados por dados/lifecycle. Ajuda explica profundidade versus base, folga por lado, incompatibilidade do padrão e prévia antiga. Atualizar README sem alegações de teste que não existiram.

**GPU:** overlay sólido ciano já existe; regredir e mostrar marker/interface/normal. Um handler compartilhado, cache por revisão, restauração de estado em finally; cancelar modal/unregister/reload limpa tudo. Viewport headless não prova cor/espessura. Preservar local view, ocultação e export limpo.

## 17. Matriz de testes e gates

### Regras de harness

Abrir cópias de casos/Padrao_1.blend, Teste_3.blend e Teste_4.blend. Inspecionar nomes, meshes, faces, materials, unit_settings, seleções e propriedades. Captura de face #137 ou #286 não autoriza hardcode no arquivo sem conferir topologia. Fixtures sintéticas devem ter IDs/grupos próprios. Não executar scripts de texto embutidos em `.blend` automaticamente; carregamento de teste sem autoexec externo.

Registrar JSON: versão Blender/addon; hash entrada; alvo/região; parâmetros; domínio/normal; specs de pinos; erros por fase; V/AABB/manifold/degen/interseção; materiais; objetos temporários; assinaturas requested/applied. Screenshots em modo montado e explodido, antes/depois, para os casos UI. Valores físicos com tolerância explícita e justificada.

| ID | Cenário | Aceitação |
|---|---|---|
| T01 | Plano G normal, offset zero | Overlay já coincide antes de gerar |
| T02 | Plano R e alinhamento Face/Cursor/Eixos | Mesma origem/normal do corte |
| T03 | Offset +2/−2 mm, parent/escala | Aplicação única e mm físicos |
| T04 | G cancel, Ctrl-Z, remove preview | Sem visual obsoleto |
| T05 | Criar cortador Material, duas ilhas mesma cor | Sem TypeError; região correta |
| T06 | Criar cortador Loop, invert, target rotacionado | Um objeto, matriz coerente |
| T07 | Quina rotacionada, 8 cantos, origem arbitrária | Apoio/interior corretos |
| T08 | Resize 10→20→10, realinhar repetido | Âncora fixa, sem deriva |
| T09 | 3 faces sem canto comum/chanfro | Rejeição clara |
| T10 | Material relevo laranja + apoio | Base contínua, exterior intacto |
| T11 | Loop mesmo relevo, d=1/2/5 mm | Geometria equivalente e interface real |
| T12 | Material seleção sem apoio válido | Bloqueio/solicitar referência, sem artefato |
| T13 | Verde DETACH 1/2/3 pinos | Sucesso preservado |
| T14 | Verde GRID_4 fora domínio | Rejeição esperada, antiga identificada |
| T15 | Parede insuficiente/inconclusiva | Sem perfuração silenciosa |
| T16 | Base U/L/anel com furo suportado | Domínio íntegro, ou limitação explícita |
| T17 | Folga lateral/fundo isoladas/combinadas | Valores por toda profundidade e boca |
| T18 | Material da base verde e override | Todas faces novas corretas |
| T19 | Slots permutados/multicolor | Exterior/receptor preservados |
| T20 | Loop plano 4/16 pontos, 15,26 mm | Regressão sem arestas quase nulas |
| T21 | Corte passante | Não gerar fundo inexistente para pinos |
| T22 | Caso 2 funciona, 1/3/4/Auto degen | Causa por fase, geometria corrigida |
| T23 | Chanfro zero/0,34, cilindro/cápsula | Fixtures sólidas e booleanos válidos |
| T24 | L 7 mm e 2 mm; ajuste on/off | Distingue padrão/busca/domínio |
| T25 | S e zigue-zague | Padrões inválidos editáveis, sem vazio |
| T26 | U com centro no vão | Centro rejeitado, válidos manuais aceitos |
| T27 | Centro interno mas perfil toca furo/borda | Footprint rejeitado corretamente |
| T28 | Cápsula girada e duas próximas | Orientação/collision exatas |
| T29 | Padrões 1/2/3/4→manual | Markers mantidos e editáveis |
| T30 | Click/drag/delete/undo/cancel | Interação contínua sem Edit Mode |
| T31 | Mesma forma, triangulação diferente | Posição clique invariável |
| T32 | Click no relevo/vazio/objeto estranho | Só contato elegível |
| T33 | Explosão 0/37,6/191,1, câmera muda | Specs físicas invariantes |
| T34 | Alterar profundidade/folga/contorno após markers | Atualiza/invalida sem referências órfãs |
| T35 | Material + 1/2/3 pinos e manual | Assinatura, geometria e materiais corretos |
| T36 | Alterar padrão e geração falha | Fonte/última preview preservadas |
| T37 | Confirmar após falha/stale | Bloqueado para novos parâmetros |
| T38 | Sequência 2→1→3→4→Auto→2 | Sem cache/stacks acumulados |
| T39 | Loop CW/CCW, seeds válidos | Normal/direção semântica estáveis |
| T40 | 10 ciclos explosão/inversão | Sem deriva ou troca de lado macho |
| T41 | CDT convexa/U/L/colineares/densidades | Domínio, mapeamento, borda e material |
| T42 | Remover preview/reverter/recursivo/sessões | Ownership e snapshot íntegros |
| T43 | Unidade 1/0,001, escala não uniforme/espelho | Equivalência física ou erro explícito |
| T44 | Modificadores/Edit Mode | Estado cortado e validado consistente |
| T45 | Pós-confirmar, mover só extraída | Receptor parado com proporcional off |
| T46 | PT_BR/EN_US/AUTO e tooltips | Sem idioma misto inesperado |
| T47 | GPU reload/local view/oculto/modal cancel | Sem leak/handlers duplicados |
| T48 | Export STL/3MF e fatiador | Guias excluídos, materiais 3MF |
| T49 | Blender 4.2 e 5.2 LTS | Compatível com manifesto ou mínimo revisto explicitamente |
| T50 | Amostra impressa base/pinos | Montagem calibrada; não declarar encaixe físico por teste digital |

Comando exemplo Windows, caminhos reais a adaptar:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python '.\tests\run_0811.py'
```

Harness deve registrar a extensão e fixtures/casos, testar artefatos geométricos e liberar recursos, não simplesmente espelhar chamadas da implementação. Headless para geometria/estado; manual gráfico para modal/GPU. Tempo de preview/drag e crescimento de datablocks devem ser medidos no baseline e na versão final, sem impor meta de desempenho inventada.

## 18. Ordem de trabalho e limites para o Gemini

1. **Baseline:** inventário de Padrao_1 e reprodução E01/E02/E03/E04/E05/E08. Guardar resultados antes de corrigir.
2. **Patch pequeno imediato:** A01 + A02; G1/T05/T06. Só então seguir.
3. **Contrato de interface/base:** A03/A04/A09. G2, rejeições físicas e controles positivos.
4. **Materiais/tampas/booleanos:** A08/A10/A11. Geometria sem pinos e pós-pinos válidas; controles preservados.
5. **Manual/padrões/Material:** A05/A06/A07. G3; pesquisa Auto incremental com prazo/limites declarados.
6. **Acabamento/compatibilidade:** A12 e restante da matriz. Instalação limpa 0.8.11, changelog com execução real.

Checkpoint por etapa: arquivos, novos contratos, dados migrados, testes executados, falhas abertas. Evitar mudar helper e deixar consumidores antigos incompatíveis; buscar todos os call sites. Não criar testes triviais só para dizer que passaram. Corrigir incompatibilidade simples de assinatura pode usar AST/inspect como teste auxiliar, mas não substitui reprodução.

**Liberação comercial:** sem perda de fonte, preview confiável, corte válido e manual utilizável com folgas/materiais. Não marcar pronto se BUG-18, falhas booleanas em regiões válidas ou confirmação stale persistirem. Rejeição de GRID_4 em domínio inadequado é resultado correto, não gate que deve passar a qualquer custo.

## 19. Referências oficiais e código aberto

Consultadas/reverificadas em 14/10/2026. Fontes primárias; algumas páginas tiveram erro de fetch, indicado abaixo. Não são dependências obrigatórias. Não copiar código sem verificar licença, atribuições e commit. Projeto declara GPL-2.0-or-later; referências C++/APIs não são código Python pronto.

| Ref | Link | O que aproveitar |
|---|---|---|
| R1 | [PrusaSlicer Cut Tool](https://help.prusa3d.com/article/cut-tool_1779) | Fluxo documentado de conectar por clique, tamanho/profundidade/rotação; proposta de marker/edit de nossa extensão não é atribuída integralmente ao Prusa |
| R2 | [Bool Tool](https://github.com/nickberckley/bool_tool) e [releases](https://github.com/nickberckley/bool_tool/releases) | Gestão canvas/cutter, alinhamento e interação; releases consultadas anteriormente; não alegar que resolve mesmo bug |
| R3 | [Bool Tool histórico](https://github.com/blender/blender-addons/blob/main/object_boolean_tools.py) | Código aberto de booleanos e seleção, arquivado; readaptar contexto à API atual |
| R4 | [3D Print Toolbox histórico](https://github.com/blender/blender-addons/blob/main/object_print3d_utils/operators.py) | Classes check_degenerate/check_solid/check_thick e relatórios selecionáveis; repositório arquivado |
| R5 | [Histórico 3D Print Toolbox](https://extensions.blender.org/add-ons/print3d-toolbox/versions/) | Remoção de dissolve por criar non-manifold em certos casos; resultado primário da busca confirma advertência |
| R6 | [mathutils.geometry](https://docs.blender.org/api/current/mathutils.geometry.html) | CDT, mapas de origem, interseções; usar API versionada 4.2/5.2 no código final |
| R7 | [bmesh.ops](https://docs.blender.org/api/5.0/bmesh.ops.html) | Saneamento e tesselação; thresholds/coordenadas não universais |
| R8 | [view3d_utils](https://docs.blender.org/api/current/bpy_extras.view3d_utils.html) | Mouse/raio/ortho; busca oficial recuperada, open direto bloqueado nesta consulta |
| R9 | [SpaceView3D](https://docs.blender.org/api/current/bpy.types.SpaceView3D.html) | draw handlers; open direto bloqueado, validar documentação na implementação |
| R10 | [GPU shaders](https://docs.blender.org/api/current/gpu.shader.html) | POLYLINE_UNIFORM_COLOR e estado; não depender de bgl antigo |
| R11 | [PrusaSlicer código GLGizmoCut](https://github.com/prusa3d/PrusaSlicer/blob/master/src/slic3r/GUI/Gizmos/GLGizmoCut.cpp) | Ponto de entrada sugerido para estudar picking/validação; conteúdo não recuperado nesta consulta, não auditado |
| R12 | [Boolean Modifier 5.2](https://docs.blender.org/manual/pt/5.2/modeling/modifiers/generate/booleans.html) | Solvers e limitações; EXACT não garante ausência de degeneração |

R3/R4 são exemplos reais de outras extensões; código da base e suas linhas são evidência principal. Não usar código não verificado de forks que imitam nomes oficiais. Fixar commit no relatório se reutilizar uma implementação; consultar atualizações do projeto de destino quando necessário.

## 20. Entregáveis exigidos do Antigravity

- ZIP instalável com manifesto/bl_info/UI/changelog coerentes em 0.8.11.
- Relatório antes/depois por gate e lista do que ficou pendente.
- Screenshots de plano sincronizado, base laranja/verde correta, manual S/L e erro legítimo em 4 que não cabe.
- JSONs de regressão e fixtures/scripts significativos, com comando real de reprodução.
- Política de tolerâncias/folgas e contratos de interface/ownership documentados.
- Migração das propriedades legadas, sem quebrar .blend existente ou apagar preferência.
- Manual/ajuda PT/EN de corte/base/folga/manual e prévia antiga, em escopo proporcional à implementação.

Não entregar só um resumo de intenção. Se um gate falhar, documentar o motivo e manter status de teste; não publicar sucesso baseado em uma captura do último preview válido.
