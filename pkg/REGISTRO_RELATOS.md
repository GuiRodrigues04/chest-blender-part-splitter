# Nota de versão — 14/10/2026

O pedido mais recente define **0.8.11**. As menções históricas a 1.11 abaixo ficam preservadas como histórico, não como versão alvo atual. Consulte PLANO_0.8.11.md e AUDITORIA_CODIGO.md para revisão baseada na 0.8.10. Bugs da 0.8.9 não são automaticamente bugs ativos.

# Part Splitter — registro de desenvolvimento da versão 1.11

Atualizado em 14/10/2026 (America/Sao_Paulo).

Documento vivo de decisões, requisitos, bugs e testes. Usar como fonte ao preparar o plano técnico da próxima versão. Ainda não é uma especificação final nem indica que as mudanças foram implementadas. Novos relatos devem ser acrescentados com evidência e estado, preservando as decisões existentes.

## 1. Versão e base de referência

- Versão desejada pelo usuário: **1.11**. Preservar essa identificação; confirmar a correspondência com o manifesto antes de empacotar, sem convertê-la automaticamente para 0.8.11.
- Última base analisada neste chat: `chest_part_splitter-0.8.9.zip`.
- Plano anterior: `Part_Splitter_Plano_0.8.10.zip`. Ele descreve correções anteriores; a versão 0.8.10 era uma proposta naquele documento, não uma versão cuja implementação foi verificada aqui.
- Ao elaborar o plano da 1.11, obter e analisar o código mais recente. Não pressupor que bugs da 0.8.9 continuem presentes nem que tenham sido corrigidos.
- Não foram executados testes Blender nesta análise. Observações visuais e conclusões estáticas devem permanecer distintas de reprodução funcional.

## 2. Direção do produto e decisões do usuário

O usuário quer poucos modos de corte, controles didáticos e peças realmente adequadas para montagem posterior. Priorizar cortes confiáveis, preservação da geometria externa, folgas explícitas e encaixes que possam ser posicionados pelo usuário.

### Decisões aceitas

1. Material e Loop devem permitir extrair uma região plana ou com relevo **com profundidade de base**, criando uma cavidade complementar no corpo principal.
2. Não criar uma nova categoria de corte apenas para “relevo com base”. A análise automática identifica o caso e a referência geométrica, dentro dos modos já existentes.
3. Ambos os modos devem oferecer **folgas de montagem** e **encaixes/pinos**. Adicionar suporte a pinos em Material é requisito explícito.
4. Primeira versão comercial: padrões editáveis de **1, 2, 3 e 4 encaixes** e posicionamento **manual**.
5. Investigar melhorias na distribuição automática, sem condicionar o lançamento a um algoritmo sofisticado que encontre as melhores posições em qualquer forma.
6. Validar posições e geometria continua obrigatório, mesmo com distribuição simples ou manual.
7. Simplificar alinhamento do cortador à face/quina pela própria extensão e distinguir visualmente as linhas do cortador.

### Propostas a detalhar no plano técnico

- Nome sugerido: “Profundidade da base (mm)”. O algoritmo identifica o apoio; valor de profundidade deve ser visível e editável, sem mudança silenciosa.
- Apresentar controles de folga lateral e folga de fundo/interface com ajuda visual. Sua nomenclatura e lado de aplicação precisam ser definidos de forma consistente.
- Compartilhar a infraestrutura de encaixes entre Material e Loop, respeitando a interface real de cada corte. Não duplicar simplesmente o código do Loop com seus possíveis defeitos.

## 3. REQ-01 — extração de relevo com base, sem novo modo

Exemplo de intenção: cubo com um cone ou outro relevo sobre uma região quadrada colorida. A seleção inclui o relevo e a região de apoio. Separar somente pela superfície de apoio pode deixar áreas em forma de película, frágeis para impressão.

Resultado desejado:

- **Peça extraída:** relevo completo, sem alterar sua superfície externa, mais uma base de espessura X retirada do volume do corpo.
- **Receptor:** cavidade correspondente à base, com as folgas configuradas.
- **Montagem:** recupera a aparência externa original, respeitando o afastamento previsto pelas folgas.

A profundidade deve partir do plano de apoio, e não do topo do cone. O contorno da base segue a região selecionada; não substituir formas U/L ou regiões com furos por bounding box ou convex hull. O exemplo numérico original de quadrado 3×3 e cone de raio 2 descrevia a intenção: geometria de teste precisa usar medidas compatíveis se o círculo tiver que caber no quadrado.

| Situação | Comportamento desejado |
|---|---|
| Região plana superficial | Extrair com a profundidade definida pelo usuário |
| Região com relevo e apoio planar identificável | Preservar relevo e acrescentar base atrás do apoio |
| Sólido já separado | Separar componente; indicar se profundidade de base não se aplica |
| Apoio ambíguo ou contorno não planar | Explicar limitação e solicitar referência quando necessário; não inventar plano silenciosamente |

Detectar espessura disponível, riscos de atravessar parede e interceptar outra região. Base não é conserto automático de faces duplicadas, soltas ou degeneradas: defeitos de malha exigem diagnóstico próprio.

**Estado:** requisito aceito; reconhecimento do apoio e algoritmo a especificar após novos arquivos de referência.

## 4. REQ-02 — folgas em Material e Loop

As duas formas de extração devem possuir controles de folga destinados ao encaixe posterior, inclusive no caso de relevo + base. Não confundir espessura da base com tolerância numérica ou folga de montagem.

### Contrato a definir e verificar

- **Folga lateral:** separação entre o perímetro da base e as paredes da cavidade.
- **Folga de fundo/interface:** espaço na direção de inserção; preservar a posição externa montada desejada. Tornar visível onde o volume é removido.
- **Folga de pinos:** diferença dimensional entre pino e alojamento, independente das folgas da base.
- Deixar claro se o valor lateral é por lado ou total e se a folga cilíndrica é radial ou diametral.
- Definir lado de aplicação (reduzir inserto, ampliar cavidade ou repartir), preservando a silhueta externa quando for requisito.
- Não aplicar duas vezes a mesma folga por caminhos diferentes de corte e geração de encaixe.
- Valores devem estar em milímetros físicos e funcionar sob escala/rotação do objeto.
- Validar offsets em concavidades, furos e faixas estreitas; não apagar partes da base para fazer o offset passar.
- Folga zero deve gerar volumes complementares. Folga positiva deve retirar apenas o volume previsto nas interfaces.

**Estado:** suporte em ambos os modos aceito. Defaults, convenções por lado e implementação precisam ser definidos no próximo plano; não pressupor que o usuário já aprovou valores numéricos.

## 5. REQ-03 — pinos também no corte por Material

Adicionar os encaixes cilíndricos e de cápsula à extração por Material, incluindo relevo com base. Manter opções equivalentes em Loop e extração com profundidade.

Os encaixes devem usar a interface física entre base e receptor, não o topo do relevo nem o plano original quando o fundo foi deslocado pela profundidade. Cada colocação gera um par associado: pino em uma peça e alojamento na outra.

Tratar posições em coordenadas locais da interface; visualização explodida não pode deslocar sua referência geométrica. Recalcular/invalidate ao mudar profundidade, folga, contorno ou referência. Preservar os materiais externos e definir material das novas superfícies internas.

**Estado:** requisito explícito aceito; verificar restrições atuais de Material na versão mais recente.

## 6. REQ-04 — padrões simples e modo manual

### Escopo comercial aceito

- Padrões iniciais editáveis de 1/2/3/4 encaixes.
- Ajuste de espaçamento e orientação do padrão.
- Manual: adicionar, selecionar, mover, girar cápsula e excluir.
- Preview de pino e cavidade correspondente; posições inválidas claramente marcadas.
- Bloquear confirmação de encaixes inválidos, mantendo a possibilidade de corrigir ou remover cada um.

Fluxo sugerido: gerar corte/base → mostrar interface → escolher padrão ou adicionar manualmente → ajustar → validar → confirmar. Não obrigar o usuário a editar malhas auxiliares ou posicionar separadamente pino e furo.

Padrões são sugestões, não garantia de encaixe em qualquer domínio. Em U/L, permitir editar os pontos. Não projetar cegamente para a posição válida mais próxima, reduzir quantidade ou redimensionar pinos sem informar. Se não couberem, explicar e oferecer ajustes.

### Validação compartilhada obrigatória

1. Todo o footprint do pino **e do alojamento com folga** pertence ao domínio válido da interface.
2. Margem de borda respeitada; centro válido sozinho não basta.
3. Profundidade/espessura suficiente nas duas peças.
4. Nenhuma colisão com outros encaixes ou detalhes relevantes.
5. Para cápsula, considerar perfil completo e orientação.
6. Booleanos de união/subtração geram resultados fechados e coerentes.

Modo manual não dispensa esses testes e não resolve defeitos no gerador de cilindros/cápsulas.

## 7. INV-AUTO — investigação do posicionamento automático

Problema relatado: em uma interface U, pinos às vezes caem no vão vazio e/ou se concentram em posições mal distribuídas. A causa específica ainda não foi reproduzida no código mais recente.

Investigar se a distribuição usa centro/bounds da região, domínio incompleto, amostragem apenas do centro do encaixe ou interface no plano errado. Identificar o domínio real, concavidades, furos e componentes conectados.

Pesquisar melhorias incrementais: candidatos válidos, distância de borda, afastamento entre encaixes, cobertura das partes da interface e determinismo. Não prometer “posição mecanicamente ideal” sem definir cargas, material e orientação de impressão.

Exemplo de teste: U com hastes equivalentes → dois encaixes podem ser sugeridos um em cada haste se houver espaço; três podem incluir a faixa inferior se válida. Não transformar isso em regra universal de simetria.

**Entrega de lançamento:** distribuição simples validada e manual utilizável. **Investigação adicional:** proposta de algoritmo melhor, benchmark e custo de implementação; implementação sofisticada pode ficar para versão posterior.

## 8. Registro de bugs e melhorias anteriores

Reavaliar todos na versão mais recente. Os estados abaixo descrevem o que foi observado/analisado na 0.8.9, não o estado atual da implementação.

| ID | Problema | Evidência / estado |
|---|---|---|
| BUG-01 | Extração por Loop em região plana falha | 16 pontos, 15,26 mm, sem passante: 5 arestas consideradas nulas em A; causa pendente |
| BUG-02 | Mesmo tipo de falha com loop mínimo | 4 pontos, AUTO EXTRUDE, passante: 2 arestas consideradas nulas em A |
| BUG-03 | Corte de quina falha | 3 arestas consideradas nulas em B; coincidência de superfícies é hipótese |
| BUG-04 | Criar cortador desta seleção | Contratos de chamada/retorno incompatíveis em Loop/Material confirmados estaticamente na 0.8.9; inversão declarada sem uso |
| BUG-05 | Caixa para quina | Orientação e referência precisam de revisão; três faces sem canto comum são aceitas no código analisado |
| BUG-06 | Alinhar à Face | Supõe origem central e usa dimensão mundial Z para apoio; não conserva orientação completa |
| BUG-07 | Tampa com topologia em leque | Triângulos compridos/estreitos observados; deformação da superfície não comprovada |
| BUG-08 | Películas na saliência amarela | Pode ser afinamento original ou defeito de malha; investigar com Teste 4 e extração com base |
| BUG-09 | Peça extraída e cubo movem juntos | Confirmação seleciona A/B na 0.8.9; edição proporcional é hipótese adicional; testar independência real |
| BUG-10 | Encaixes cilíndricos e cápsula falham | Relato do usuário; separar problema de posição de problema de construção/booleano |
| BUG-11 | Pinos no vazio e distribuição ruim em U | Relato; domínio real e footprint precisam ser validados |
| MEL-01 | Linhas do cortador pouco distinguíveis | Cor própria sugerida: ciano, com espessura ajustável |
| MEL-02 | Alinhamento integrado à face/quina | Seleção guiada, apoio fixo, realinhar e desfazer; sem etapas manuais de cursor/origem |
| MEL-03 | Interface com textos em inglês | Rótulos, tooltips e mensagens ainda não totalmente localizados |
| MEL-04 | Tolerâncias incoerentes | Arestas/coincidência em BU e áreas em mm² no diagnóstico analisado; revisar contrato de unidades |

Observação importante: saliência 3D pode ter **contorno planar**. Casos que funcionaram usaram DETACH; casos planos que falharam usaram EXTRUDE. Não registrar a conclusão ampla “loop planar nunca funciona”.

## 9. Código a inspecionar no próximo plano

Referências da 0.8.9, verificar existência/assinatura na nova base:

- `src/geometry_loop.py`: `analyze_loop_region`, `slice_mesh_by_loop`, `slice_mesh_by_loop_extrude`, `create_loop_prism_cutter`, `triangulate_polygon_2d`.
- `src/geometry_material.py`: análise/seleção de região, prisma e corte por material. Verificar se suporta relevo com apoio planar ou exige faces coplanares.
- `src/geometry_connectors.py`: distribuição, perfil de cápsula/cilindro, contenção e geração de alojamentos. Inspeção completa necessária para os novos relatos.
- `src/geometry_contract.py`: domínio, plano de interface, limites e métricas; preservar furos/concavidades e relação entre base e receptor.
- `src/operators.py`: criação de cortadores, encaminhamento DETACH/EXTRUDE, bloqueio de encaixes Material/Solid, confirmação e seleção.
- `src/diagnostic.py`: validade geométrica, espessura e tolerâncias.
- `src/properties.py`, `src/ui.py`, `src/translations.py`, `src/gpu_drawing.py`: controles, estados, traduções e edição visual de encaixes/cortadores.
- `src/lifecycle.py`: transações, remoção de preview, restauração e operações recursivas.

Não reutilizar índices de faces/vértices após mudança topológica sem validar a referência. Não usar bounds como prova de que ponto ou encaixe inteiro pertence à interface. Não remover validação para fazer testes passarem.

## 10. Arquivos e referências existentes

- `Teste 3.blend`: caso para quina e Loop; seleções reais precisam ser conferidas, pois capturas podem corresponder a estado posterior ao salvamento.
- `Teste 4.blend`: corte confirmado da saliência, películas e movimento conjunto; executar inspeção antes de afirmar causa.
- Capturas 145344/145428: falha de quina; 150643/150649 e 150915: falhas EXTRUDE; 150956: DETACH funcionando; 151200: tampa em leque; 151346: saliência amarela.
- `Part_Splitter_Plano_0.8.10.zip`: plano e referências anteriores, contendo imagens, trechos próprios e casos. Consultar junto deste registro; este registro atualiza o escopo de pinos e unificação da extração.
- Referência de fluxo manual previamente consultada: https://help.prusa3d.com/article/cut-tool_1779 — colocação e remoção de conectores por clique, parâmetros de tamanho/profundidade/rotação. Serve como referência de interação, não prova de solução para nossos bugs.
- Referências técnicas já reunidas no plano anterior: APIs BMesh/mathutils/GPU, Bool Tool e 3D Print Toolbox. Verificar versões, commits e licenças quando adaptar implementações.

## 11. Testes novos para a 1.11

| Teste | Resultado desejado |
|---|---|
| Região Material: cone sobre base quadrada | Relevo inteiro + base X mm; cavidade complementar; nenhuma película espúria |
| Mesmo caso por Loop | Comportamento geométrico equivalente, sem novo modo de corte |
| Profundidade 0 e positiva | Comportamento explicitamente definido; não alterar profundidade silenciosamente |
| Folga lateral/fundo/pino, isoladas e combinadas | Aplicação única, convenções de medida claras e exterior preservado |
| Base U/L ou com furo | Contorno real preservado; nenhuma tampa/encaixe no vazio |
| Material + pinos cilíndricos/cápsula | Pino/alojamento associados e geometria final válida |
| Padrões 1/2/3/4 em interface ampla/estreita | Posições editáveis; inválidas marcadas e confirmação bloqueada |
| Centro do pino válido, perfil atravessa borda | Rejeitar: validação do footprint completo |
| Cápsula com giros diferentes | Validade recalculada para cada orientação |
| Manual: mover/excluir/alterar dimensão | Preview e validação atualizados; undo/cancel funcionam |
| Mudar profundidade/folga após posicionar | Referências atualizadas ou invalidadas claramente; sem encaixes órfãos |
| Preview explodido versus montado | Mesmas posições físicas de encaixe na montagem |
| Parede insuficiente e outros detalhes atrás da região | Aviso/bloqueio coerente; não atravessar ou extrair outro detalhe silenciosamente |
| Restaurar preview/corte e continuar receptor | Fonte preservada, sessões isoladas, materiais e objetos do usuário intactos |
| Impressão de amostras reais | Avaliar montagem e folga física; teste digital sozinho não garante encaixe impresso |

Executar também a matriz do plano anterior após confirmar relevância na base atual. Registrar resultados reais, screenshots antes/depois e parâmetros; não declarar teste funcional com base apenas na compilação Python.

## 12. Pendências e próximos passos

1. Usuário enviará imagens/.blend adicionais do caso relevo + apoio para Material.
2. Obter versão mais recente do código antes do plano definitivo da 1.11.
3. Reproduzir bugs de pinos e distinguir domínio/posição, espessura e construção booleana.
4. Definir interface de profundidade/folgas compartilhada entre Material e Loop, mantendo poucos modos.
5. Traduzir requisitos em tarefas pequenas, com testes e critérios de aceitação.
6. Atualizar este mesmo registro a cada novo relato ou decisão, preservando sua identidade e histórico.

### Formato para acrescentar novos relatos

`ID | data | versão testada | objeto/caso | passos | parâmetros | esperado | observado | imagem/arquivo | certeza | prioridade | estado`.

Estados recomendados: relatado; reproduzido; causa identificada; implementação pendente; implementado; validado; adiado com justificativa. Nunca marcar resolvido somente porque um comportamento alternativo funcionou.

## 13. BUG-12 — Material: profundidade gera resultado inadequado em região não plana

**Data:** 14/10/2026. **Versão visível na captura:** Part Splitter 0.8.10, Blender 5.2.0 LTS. **Prioridade:** alta. **Estado:** relatado com evidência visual; causa e reprodução funcional pendentes. Código da 0.8.10 ainda não analisado neste registro.

**Evidência:** `image(20261014-192339).png` (arquivo de referência: `libfile_dd5f3c066de4819186bfee908b3012ea`). Cena “Padrão Testes”, alvo “Cube”, modo Material, região “4: Erro”, 16 faces e fronteira contínua. Modo “Extrair com Profundidade”, profundidade 5,00 mm, interface “Material da Peça Extraída”. A captura mostra a saliência amarela e superfícies/fragmentos aparentes junto ao receptor. A imagem não comprova a topologia dos fragmentos, mas o usuário relata que a profundidade continua gerando para modelos não planos e solicita correção.

**Problema a investigar:** o caminho de extração pode estar tratando faces do relevo com direções diferentes como uma região plana, identificando o apoio incorretamente ou reconstruindo o volume/interface de forma inadequada. Estas são hipóteses; não concluir a causa sem abrir o caso e conferir o código da 0.8.10.

**Comportamento esperado, compatível com REQ-01:**

- Não proibir todos os objetos ou regiões com relevo: cone sobre base plana continua sendo um caso desejado.
- Distinguir planaridade das faces selecionadas, planaridade do contorno e existência de plano de apoio válido. A planaridade global do objeto alvo não é o critério correto.
- Se houver apoio planar válido, preservar o relevo inteiro e extrair a base com a profundidade medida a partir desse apoio, gerando cavidade complementar e respeitando folgas/pinos.
- Sem referência válida ou num caso ainda não suportado, bloquear a geração com explicação e permitir escolher uma referência quando aplicável. Não extrudar por uma normal média arbitrária nem gerar uma prévia inválida silenciosamente.
- Validar domínio, fechamento, ausência de películas espúrias/faces internas e complementaridade das partes antes de aceitar o resultado.
- Alterar seleção ou referência deve invalidar e recalcular a análise e a prévia; não reutilizar diagnóstico de planaridade antigo.

**Testes a acrescentar:** (a) região plana, controle positivo; (b) relevo não plano com contorno e apoio planar, deve preservar relevo + base; (c) região que atravessa faces de uma quina sem apoio único, deve solicitar referência ou bloquear; (d) região curva/contorno não planar sem estratégia suportada, deve bloquear; (e) mudar de região plana para não plana e atualizar, sem diagnóstico obsoleto; (f) verificar os mesmos critérios por Material e Loop, com folga zero/positiva e pinos desligados/ligados.

**Aceitação:** nenhuma geração inadequada somente porque a opção está disponível. O bloqueio deve depender da referência geométrica necessária à extração, preservando o suporte a relevo sobre base plana que o usuário já solicitou.

## 14. BUG-13 — 2 pinos funcionam; 1/3/4 e Auto falham no mesmo caso

**Data:** 14/10/2026. **Estado:** relato corroborado por capturas; reprodução no Blender e causa pendentes. **Prioridade:** alta, requisito de confiabilidade para os padrões comerciais. A versão não está visível nestes recortes; contexto recente indica 0.8.10, a confirmar com código/arquivo. Blender mostrado: 5.2.0 LTS. Cena: Padrão Testes; alvo ativo Cube.002.

| Configuração | Captura | Resultado observado |
|---|---|---|
| 2 Pinos (Linha), LINEAR_2 | image(20261014-193654).png | Barra de status informa preview gerado com sucesso com LINEAR_2 |
| 1 Pino (Centro) | image(20261014-193724).png | Atualização falhou: após encaixes, Parte A tem 2 arestas consideradas de comprimento nulo |
| 3 Pinos (Linha) | image(20261014-193734).png | Mesmo aviso de atualização inválida após encaixes |
| 4 Pinos (Grade) | image(20261014-193740).png | Mesmo aviso de atualização inválida após encaixes |
| Pela Forma (Auto) | image(20261014-193750).png | Mesmo aviso de atualização inválida após encaixes |

**Parâmetros visíveis:** diâmetro nominal 7,00 mm; profundidade de inserção 4,00 mm; chanfro de entrada 0,34 mm; folga por lado 0,100 mm (0,20 mm total no diâmetro); folga de fundo 0,50 mm; margem da borda 1,0 mm. “Ajustar à Área Válida” está desmarcado. Perfil do encaixe e método de corte não aparecem neste recorte do painel: não deduzir cilindro/cápsula ou Plano/Loop/Material sem conferir o arquivo.

**Interpretação correta das imagens:** nas quatro falhas, a interface informa que a prévia visível é a anterior válida. Os dois pinos ainda desenhados não demonstram que os padrões 1/3/4/Auto criaram dois pinos incorretamente; a extensão conservou o último resultado válido. Preservar essa proteção, mas indicar claramente a configuração aplicada versus a configuração solicitada que falhou. Verificar que Confirmar não consuma a prévia antiga como se tivesse aplicado os novos parâmetros.

**Hipóteses a investigar, não causas confirmadas:**
- Pino central em 1 e 3, ou candidato escolhido pelo Auto, pode coincidir com triangulação/vértices/arestas existentes e produzir degeneração no booleano.
- Perfil completo do pino/alojamento pode ultrapassar domínio/margem/espessura, embora o centro pareça caber.
- Orientação, mapa da interface, tolerâncias ou geometria do gerador podem variar conforme padrão.
- Atualização incremental pode reutilizar malha/cache/referências incorretamente. O mesmo aviso em todas as capturas não prova elementos idênticos nem exclui diagnóstico antigo.

**Investigação e testes obrigatórios:**
1. Reproduzir cada padrão a partir do alvo intacto, também em sessão nova, com parâmetros iguais.
2. Testar sequência 2→1→3→4→Auto→2 e atualizar explicitamente cada vez. Registrar assinatura dos parâmetros, resultado e validade de confirmação.
3. Registrar coordenadas, perfil/orientação e containment de cada candidato antes de gerar. Localizar as 2 arestas problemáticas após a operação, com comprimento em mm e fase exata (união/subtração).
4. Comparar malha sem encaixes, após cada encaixe individual e após combinação. Diferenciar falha de posição, gerador e booleano.
5. Para diagnóstico, variar levemente posição/diâmetro e chanfro zero/0,34; isso é teste de sensibilidade, não correção que altere medidas silenciosamente.
6. Repetir com Ajustar à Área Válida desligado/ligado. A opção desligada não deve permitir encaixes inválidos: apenas pode impedir reposicionamento automático.
7. Repetir cilindro e cápsula explicitamente, testar deslocamento manual dos pontos, folgas e espessura disponível.
8. Verificar que falha não modifica fonte/última prévia válida e não deixa pinos/meshes temporários. Exibir erro em português, marcando candidatos inválidos quando possível.

**Aceitação:** padrões 1/2/3/4 e Auto geram todos os encaixes solicitados quando há espaço válido, ou rejeitam por motivo identificável antes de entregar malha defeituosa. Manual não pode ser usado como justificativa para manter defeitos do gerador. Manter o caso LINEAR_2 como controle positivo.

**Referências anexadas:** 193654 (libfile_59834bd48ec08191bbc67f1810d6a4f4), 193724 (libfile_77c30d29dee081919e96f3a1735cd41f), 193734 (libfile_5297139c65f4819195c64496150a9cc1), 193740 (libfile_d9916e5ab6848191ae9dfbcb357cc163), 193750 (libfile_d21ae871dd308191a70eaa5476ce344b). Os arquivos são referências visuais existentes, não foram duplicados neste Markdown.

## 15. UX-01 / BUG-14 — posicionamento manual visual em interfaces S

**Data:** 14/10/2026. **Evidências:** image(20261014-194115).png (libfile_c2371cb7415c819185d97d898ea03743), 194302 (libfile_b74577f6cc04819195a6b19e4aadfd06), 194313 (libfile_87b9ad8fe42481918c1376282ad4ee01), 194322 (libfile_ede122a686d881919a45e783ed408147). Estado: sucesso/falha visual observado; causa algorítmica não reproduzida.

No S, o usuário relata distribuição pouco adequada. Captura 194115 mostra dois pinos em segmentos superior/inferior. 194302 confirma CENTER com um único pino, reposicionado na faixa superior apesar do rótulo “Centro”; Ajustar à Área Válida está ligado. Não é prova de erro de geometria: pode ser ajuste intencional cuja referência/resultado não é clara. 194313 (4) rejeita encaixe #2; 194322 (3) rejeita encaixe #1 por margem de segurança de 1 mm ou posição fora do domínio sólido. São mensagens de contenção, distintas das arestas quase nulas do BUG-13. A prévia antiga é conservada nas falhas.

**Análise/recomendação de interação (a validar com usuário):**
- Unir clique e marcador: clique define a posição exata na superfície de contato; círculo/cápsula fantasma mostra perfil real, folga e margem antes do clique.
- Não posicionar automaticamente no centro de uma face da triangulação. A localização do clique deve ser contínua, independente de densidade e divisão da malha.
- Gerar prévia sem pinos; botão Posicionar encaixes abre etapa específica com interface isolada, vista perpendicular opcional e receptor translúcido/oculto para acesso.
- Clique em local válido adiciona marcador; arrastar move; cápsula tem giro no plano; selecionar/excluir e desfazer; botões Aplicar encaixes e Cancelar.
- Verde indica validação preliminar aprovada, vermelho indica motivo de rejeição. Antes dos testes de espessura acabarem, não apresentar verde como garantia. Validar pino/alojamento completo, profundidade e colisões; booleano pode ainda falhar e deve ter diagnóstico separado.
- Marcadores não são meshes exportáveis nem alteram faces da prévia. Adiar booleanos caros para Aplicar encaixes; durante movimento, overlay e verificações leves, com validação geométrica final.
- Padrões 1/2/3/4 geram os mesmos marcadores editáveis do manual. Usuário corrige disposição sem trocar toda a ferramenta.
- Referências em coordenadas da interface física montada. Em preview explodido, mapear transformação de visualização; mover explosão/câmera não altera posições físicas. Não permitir raycast no relevo externo ou através do vão do S como se fosse contato.
- Primeiro atender interfaces planas reais de Plano, Loop e Material com base. Não pressupor suporte geral a contato curvo.
- UI distingue número solicitado, marcadores válidos e última configuração aplicada. Não apresentar peças/pinos antigos como resultado atual.

**Alternativa rejeitada como fluxo padrão:** escolher uma face e usar seu centro. Depende da triangulação, limita precisão e leva o usuário para Edit Mode. Pode existir como atalho opcional com ajuste posterior. Mover um objeto círculo livre em 3D também não é o padrão: aumenta passos e risco de desalinhamento; restringir marcador ao plano de contato.

**Testes:** S/U/L com mesma forma e triangulações diferentes → mesmos cliques produzem posições equivalentes; clique no vazio rejeitado; footprint atravessando borda rejeitado; arrastar/girar cápsula; conversão padrão→manual; preview sem pinos acessível; confirmar/cancelar sem temporários; alternar explodido/montado; margem 1 mm e diâmetro 7 mm; 3/4 encaixes válidos posicionados manualmente quando a geometria permitir. Não afirmar que qualquer quantidade sempre cabe.

Referência de interação: PrusaSlicer Cut Tool (https://help.prusa3d.com/article/cut-tool_1779), consultada em 14/10/2026, documenta adicionar/remover conectores por clique. A proposta de ghost marker e fluxo integrado acima é recomendação própria, não funcionalidade atribuída integralmente à referência.

## 16. BUG-15 — Loop em L: padrões 1/2/3/4 falham

**Data:** 14/10/2026. **Prioridade:** alta. **Estado:** relato de falha em todos os padrões, com capturas de Auto e 1 pino; reprodução e causa pendentes. Método Loop confirmado pelo usuário. Alvo ativo Cube.002; Blender 5.2.0 LTS. Versão da extensão não visível neste painel recortado.

**Evidências:** image(20261014-194414).png (libfile_1e6cafa416bc81918065ec4093f06579) e image(20261014-194511).png (libfile_463a4231094c81919355a6af6ac9fb42). Contorno ciano de região L numa superfície subdividida.

- Relato: nenhum padrão de 1 a 4 pinos funciona com as configurações testadas.
- 194414: Auto selecionado, pino cilíndrico, macho em A, diâmetro 7 mm, inserção 4 mm, chanfro 0,34 mm, folga por lado 0,10 mm, fundo 0,50 mm, margem 1 mm, Ajustar à Área Válida ligado. Mensagem: encaixe #1 ultrapassa margem de 1 mm ou cai fora do domínio sólido.
- 194511: 1 Pino (Centro), diâmetro reduzido para 2 mm, demais valores visíveis equivalentes e ajuste ligado. Medições mostradas: 82,2573 mm ao longo do braço superior e 20,5643 mm transversalmente. Não há nova mensagem de resultado visível: não afirmar que essa captura isolada comprova atualização após reduzir diâmetro. Registrar redução como tentativa, confirmar execução e resultado no .blend.

**Interpretação:** centro de bounds/centroide pode cair na concavidade do L; busca de ajuste pode ser incompleta ou usar domínio/interface incorretos. São hipóteses. Não atribuir a falha só ao diâmetro: a faixa medida parece larga em relação a 7 mm, mas isso não comprova espessura ou domínio real válidos. Distinguir “nenhuma posição válida existe” de “o algoritmo não encontrou posição”.

**Reprodução:** gerar o corte sem pinos para confirmar validade; testar 1/2/3/4/Auto individualmente, 7 e 2 mm, ligado/desligado Ajustar à Área Válida, com registros de posições e footprint. Medir domínio e profundidade real em cada braço. Testar candidato manual no interior de cada braço: se válido, distribuição falhou; se também falhar, investigar domínio, transformação, espessura ou geração booleana. Não reduzir margem/validação para forçar sucesso.

**Aceitação:** em L com espaço geométrico suficiente, ao menos o manual deve aceitar posições válidas em ambos os braços; padrões/Auto oferecem candidatos válidos ou aviso que distingue incompatibilidade do padrão de impossibilidade física. Marcar candidato rejeitado e motivo. Não garantir que todas as quantidades sempre cabem. Incorporar este L e o S do BUG-14 à matriz de regressão, inclusive após rotação/escala e mudança de triangulação.

## 17. BUG-15, caso adicional — contorno em zigue-zague/escalonado

**Data:** 14/10/2026. **Evidência:** image(20261014-194940).png, libfile_66106f499e8c8191a9a19a775de6f034. Forma distinta do L, contorno concavo escalonado/zigue-zague; não atribuir um nome exato de letra sem arquivo. Usuário relata o mesmo bug.

Na captura: 2 Pinos (Linha), macho Parte A, diâmetro nominal 7 mm, inserção 4 mm, chanfro 0,34 mm, folga por lado 0,10 mm (total diametral 0,20 mm), folga fundo 0,50 mm, margem borda 1 mm, Ajustar à Área Válida ligado. Falha: encaixe #1 ultrapassa margem de segurança ou cai fora do domínio sólido. Método de corte e versão não aparecem neste recorte; confirmar no .blend em vez de deduzir apenas pelo contexto de Loop.

A peça afastada e um pino visível pertencem à última prévia válida, segundo a própria mensagem. Não concluir que o padrão solicitado de 2 gerou apenas um, nem que a nova tentativa foi parcialmente aplicada. Testar número aplicado versus solicitado e bloqueio de confirmação de estado obsoleto.

Este caso amplia a regressão de distribuição/contenção em formas côncavas, mas não comprova a mesma causa interna do L/S nem impossibilidade de posicionar dois pinos. Testar posições manuais em segmentos diferentes, footprint completo, espessura, domínio e transformação da interface, com preview montado/explodido e ajuste ligado/desligado. Preservar margem; não deslocar silenciosamente encaixes para qualquer ponto válido. Registrar cada candidato rejeitado e diferenciar falha de distribuição de falha booleana.

## 18. BUG-16 / REQ-05 — Loop: DETACH versus profundidade, direção, pontas finas e material da base

**Data:** 14/10/2026. **Prioridade:** alta para direção/espessura/encaixes; controle de material integra acabamento do fluxo. **Estado:** relato e comparação visual; normal e causa dos pinos ainda não reproduzidas. Blender 5.2.0 LTS; versão da extensão não visível no recorte. Cena Padrão Testes, alvo Cube.002.

**Referências:** image(20261014-195129).png (libfile_a7b65c4589a08191acb2b731364cbba9), image(20261014-195401).png (libfile_72bab626f89081919329a5cf46ff3b25), image(20261014-195459).png (libfile_c785efbfbb208191b482661625be60ec).

### Observações e relato

- 195129 mostra Loop/AUTO, decisão Destacar Saliência e checkbox “Add base for fitting” desligado; aviso de prévia descartada. Há uma opção de base já visível nesta implementação: não especificar sua criação do zero sem analisar código recente.
- 195401 mostra contorno de 16 vértices, planar (0,00 mm), face de referência #137, AUTO→Destacar Saliência, base desligada. Usuário relata nova inversão da normal e problema na direção; existe aviso de parâmetros alterados, portanto a captura isolada não comprova geometria/direção regenerada com a configuração atual.
- 195459 mantém contorno/face e usa Extrair com Profundidade de 5,00 mm, passante desligado, prévia explodida 191,1 mm. Peça aparece com base espessa e relevo preservado. Encaixes estão desligados no painel: o sucesso de pinos em profundidade é relato adicional, não demonstrado nesta captura.
- Usuário relata que pela base a região laranja deixa pontas muito finas e pinos não funcionam; com profundidade, resultado e distribuição/geração dos pinos funcionam corretamente. Comparar isso de forma controlada, sem concluir que todos os casos de profundidade estão resolvidos.
- Usuário solicita opção de mudar a cor/material da base da peça extraída. Na imagem, base/faces internas aparecem claras e exterior laranja; não há controle de material de base visível no painel Loop.

### Investigação de direção

Separar quatro conceitos: normal geométrica da interface; direção de extração para dentro; lado que recebe pino/cavidade; deslocamento visual de explosão. A direção visual errada não comprova normais de faces invertidas. Comparar estado montado (explosão zero), Face Orientation, normais reais, identidade A/B e dados persistidos da interface. Inverter explosão não pode mudar geometria ou lado dos encaixes.

Testar DETACH, DETACH com base e EXTRUDE sobre mesmo contorno e face, com ordem de captura invertida, rotação/escala do alvo, Remove Preview e ciclos de atualização. Garantir orientação semântica estável pela região escolhida e ocupação do sólido, não somente winding arbitrário do contorno. Se a superfície de interface mudar com profundidade, recalcular sua origem, domínio e direção corretamente.

### Espessura e escolha de comportamento

Para este relevo com pontas finas, a extração com profundidade/base é preferência explícita do usuário. Reforça REQ-01: preservar relevo inteiro e adquirir espessura do receptor. Não eliminar DETACH para saliências que já são sólidas e adequadas; AUTO deve considerar risco de película/espessura local e necessidade de base, com profundidade exibida e editável. Se diagnóstico for inconclusivo, explicar em vez de prometer imprimibilidade.

Analisar opção “Add base for fitting” existente: resultado com checkbox ligado/desligado, contrato de profundidade, apoio e atualização. Unificar experiência sem aumentar categorias; não atribuir falha apenas a normal quando o volume de base também difere.

### REQ-05 — material/cor da base e das novas faces

Adicionar controle explícito de material das superfícies novas da peça extraída, disponível em Loop e Material: usar material do relevo/peça, do corpo original ou material escolhido. Preservar todos os materiais externos existentes. A cor é atributo de faces: uma base unida ao relevo não exige objeto separado para receber material próprio. Definir material de laterais/fundo novos e, quando aplicável, dos pinos; material da cavidade do receptor é decisão separada, padrão do receptor. Não repintar região externa nem trocar materiais compartilhados globalmente. Integrar tratamento no export 3MF; STL não carrega materiais.

### Teste comparativo obrigatório

Mesma região laranja: DETACH/base off → DETACH/base on → EXTRUDE 5 mm; em cada caso sem pinos e depois com cilindro/cápsula/padrões válidos. Registrar espessura mínima, plano/interface, posição de cada pino, profundidade disponível, resultado booleano e materiais. Testar montado/explodido e inversão visual independentemente. Documentar separadamente falha de domínio, espessura insuficiente, degeneração booleana e orientação visual. Validar seleção de material da base sem alterar exterior/receptor, após atualizar, confirmar, desfazer e exportar.

**Aceitação:** direção estável, extração com base/profundidade sem películas espúrias, encaixes usando interface e espessura reais, cor de base configurável sem repintura indevida. Caso DETACH não tenha espessura para os pinos, explicar a necessidade de base/profundidade em vez de gerar malha inválida.

### Esclarecimento do usuário — 14/10/2026

O relato “O por profundidade ainda gera para modelos que não são planos” refere-se especificamente à **divisão por Material**, conforme confirmação explícita do usuário. Classificar BUG-12 em Material; não usar esse relato como evidência de falha do Loop. A comparação posterior por Loop (BUG-16) é outro caso: o usuário relata resultado correto com profundidade e problemas em Destacar Saliência/pela base. São observações distintas, com critérios próprios de reprodução. Manter o suporte desejado a relevo com apoio planar; investigar a validade da referência e do resultado em Material, sem proibir indiscriminadamente objetos não planos.

## 19. Caso de controle / BUG-17 — saliência verde por Loop, base espessa e triângulos brancos

**Data:** 14/10/2026. **Referências:** image(20261014-200011).png (libfile_fb38574844c08191b39ba3729beb9e14), 200157 (libfile_ec32e5928764819185ca1f1fc4f4c8a4), 200301 (libfile_21b80cfa27588191aae6adfc0b4f48e5). Blender 5.2.0 LTS; alvo Cube.002. Versão e parâmetros de profundidade não aparecem neste recorte.

**Relato do usuário:** corte Loop pela base funciona com 1/2/3 pinos nesta forma verde com relevo; 4 não funciona e o usuário considera essa rejeição esperada, não bug. Profundidade não funciona neste caso, mas usuário não exige extração arbitrária de superfícies não planas: propõe achar a referência da base e acrescentar espessura nela, removendo volume correspondente do receptor.

**Capturas:** 200011 mostra um pino e alojamento; 200157 mostra três pinos da prévia anterior com 4 Pinos selecionado e aviso de encaixe #1 fora do domínio/margem de 1 mm. Não registrar “4 gera apenas 3”: a UI conserva última prévia válida. 200301 mostra alvo após descartar a prévia, com saliência verde escalonada; há comando de edição To Sphere ativo, não inferir deformação aplicada ou estado final a partir disso. Confirmar no .blend se apoio/contorno são planares: superfície externa com relevo não prova que o plano de apoio seja não planar.

**Caso de controle:** preservar o sucesso em 1/2/3, inclusive materiais e cavidades, durante a correção dos bugs anteriores. Rejeição por containment em 4 é limite esperado deste cenário segundo usuário; manter diagnóstico e não reduzir quantidade silenciosamente. Não presumir impossibilidade absoluta de quatro em qualquer colocação manual sem medir.

### Base com espessura — refinamento de REQ-01

A profundidade deve partir da referência de apoio e acrescentar volume contínuo atrás de todo o relevo, mantendo forma exterior. Gerar cavidade complementar no corpo; pinos nas superfícies de contato resultantes; respeitar folgas. Não extrudar separadamente cada face externa pela sua normal, nem limitar o corte a uma camada medida desde os pontos altos do relevo.

Se apoio for planar válido, reutilizar extração com base. Se o apoio realmente for dobrado/não planar, seu espessamento requer estratégia própria: definir direção de inserção e espessura, verificar auto-interseções/undercuts e adequação da montagem. Não projetar para plano médio sem validação ou prometer suporte universal na primeira versão. Esta extensão de suporte é interessante, não exigência de extrair todo modelo não plano segundo o usuário.

### BUG-17 — novas faces inferiores recebem material branco incorreto

Na captura 200157 há triângulos claros/brancos intercalados com verde na parte inferior da saliência extraída. Usuário espera verde, material da peça. Investigar material_index das tampas/triângulos criados e remapeamento de slots após booleanos. Atribuir material aos elementos novos explicitamente; não depender do slot 0, ordem dos materiais ou de apenas algumas faces adjacentes. Confirmar se são realmente faces com outro material, sobreposição ou artefato de shading; a aparência é observada, causa ainda não comprovada.

**Padrão desejado neste caso:** todas as faces inferiores novas da peça recebem verde, incluindo tampa subdividida e junção dos pinos. Preservar materiais externos existentes e o material do receptor. Controle de cor/material de base de REQ-05 permite override, mas default precisa ser coerente. Região multicolor exige política explícita, não repintura global.

**Testes:** repetir 1/2/3 como controles positivos, 4 como rejeição esperada; inspecionar material de cada triângulo da tampa e interfaces dos pinos; reordenar slots de material; testar escolha explícita da base e cavidade independente; comparar DETACH e base com profundidade válida; origem/normal/interface e espessura medidas; confirmar/desfazer/exportar 3MF. A cor correta no viewport não basta: conferir material_index e exportação.

## 20. BUG-18 — guia de plano e overlay laranja ficam dessincronizados ao mover com G

**Data:** 14/10/2026. **Prioridade:** alta; usuário deseja resolver antes do trabalho na próxima versão. **Evidências:** image(20261014-200451).png (libfile_f1b3ac3c41e48191bca67527b47da4c3), image(20261014-200613).png (libfile_16162e9f797081919c189610767d13fc). Blender 5.2.0 LTS, objeto ativo CHEST_SPLITTER_PLANE_GUIDE; modo Plano, Mostrar Plano e Linha de Corte ativos, opacidade 15%, deslocamento 0 mm.

**Relato/observação:** ao mover o guia com G, o retângulo/linha laranja não acompanha o plano de referência do corte. Antes da prévia, guia selecionado aparece como linha laranja junto ao relevo superior enquanto overlay translúcido aparece atravessando o meio do cubo. A cor preta/laranja do wire depende da seleção Blender, não identifica dois motores de corte. Depois da geração, corte ocorre junto ao guia, conforme relato/captura. A segunda captura está explodida (37,6 mm); seu afastamento visual não deve ser usado para medir o plano físico do corte.

**Evidência estática da base 0.8.9, não garantia do código atual:** gpu_drawing.py::_draw_plane_overlay lê plane_origin/plane_normal persistidos em settings. operators.py::read_plane_geometry lê matrix_world do objeto guia e atualiza essas propriedades; geração do corte chama essa função. Logo existem caminhos que podem consumir estados distintos. Isso explica plausivelmente overlay antigo e corte no guia atualizado. Inspecionar código da versão efetivamente testada (contexto recente 0.8.10) antes de aplicar patch.

**Correção recomendada:** fonte única de geometria do plano, helper puro compartilhado entre render, corte, alinhamento, assinatura e invalidation. Ler matriz mundial atual do guia; retornar origem/normal e offset físico aplicado exatamente uma vez. Não importar operators em callback GPU se gerar dependência circular; isolar helper num módulo de geometria/estado adequado. Callback de desenho deve consultar estado atual sem criar coleções, alterar settings ou provocar depsgraph recursivo. Propriedades persistidas servem de fallback apenas quando guia não existe, com política clara.

Normal deve representar o plano transformado, inclusive escala não uniforme/parent; avaliar inversa transposta da normal local ou produto vetorial de tangentes transformadas, com tratamento de escala singular/espelhamento. Não duplicar um segundo objeto/parent como solução para um overlay GPU. Invalidate preview e solicitar redraw durante G/R, alinhamentos e offset; testar cancelamento de transformação e Ctrl-Z. Se for legítimo desenhar retângulo de tamanho diferente, ele ainda precisa ser coplanar; movimento no próprio plano pode manter overlay centrado no alvo por projeto, mas movimento normal/rotação obrigatoriamente acompanham o plano efetivo.

**Reprodução e aceitação:** G em direção normal, G tangencial, R, valores no painel N, alinhamento Face/Cursor/Eixos, offset zero/positivo/negativo, parent/escala; antes de gerar preview o overlay/linha de interseção já coincide com o corte efetivo. Gerar e conferir montado (explosão zero), alternar explodido, remover preview e repetir. Sem atualização atrasada que só se corrige ao gerar; sem offset aplicado duas vezes; sem handlers recursivos. Medir coplanaridade e comparar interseção exibida versus arestas da seção resultante. Preservar última prévia válida sem apresentá-la como atual.

**Pendência para correção imediata:** obter ZIP do código mais recente. Não entregar como corrigida uma 0.8.10 que não foi recebida/analisada; os anexos 0.8.5/0.8.6 e a base 0.8.9 disponível não substituem a versão testada.
