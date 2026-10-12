# Part Splitter — registro de investigações para a 0.8.8

Atualizado em 12/10/2026. Complementa a auditoria da 0.8.7 e o plano da 0.8.8. Novos exemplos devem ser acrescentados neste registro, preservando requisitos, evidências e casos já funcionais.

O código mais recente recebido é o ZIP 0.8.7 analisado anteriormente. As imagens atuais mostram mensagens/comportamentos que podem vir de uma compilação posterior. Confirmar versão, caminho do módulo instalado e hash antes de aplicar mudanças. Não houve reprodução em Blender nesta análise.

## INV-001 — extração por profundidade gera materiais trocados e paredes finas

Prioridade: alta. Status: sintomas visuais confirmados; causas geométricas e de material precisam ser isoladas.

Referências: [antes](imagens/INV001_170750.png), [detalhe inferior](imagens/INV001_170839.png), [faces/resíduos](imagens/INV001_170938.png).

Modo Material, extração com profundidade 20 mm, folga 5 mm na peça extraída e vista explodida 35 mm. Peça amarela apresenta quadrados brancos; corpo apresenta resíduos amarelos e geometria fina. Medir espessuras: imagem não prova valor físico ou manifoldness.

Hipóteses: deslocamento de patch dobrado numa direção média; faces coincidentes/degenéricas no cortador; material dos operandos/copas mapeado incorretamente; folga aplicada apenas à profundidade. Não pintar todo o resultado para esconder resíduos.

Decisão recomendada para discussão: retirar Extrair com Profundidade do fluxo comercial geral do modo Material, preservando implementação separada para revisão. O usuário ainda não confirmou a retirada. Pode voltar futuramente como inserto de região planar, com espessura útil medida. Preservar o requisito de extração verde planar dos testes anteriores quando esse suporte for validado. Destaque pela base também precisa de correções; não substituí-lo por um caminho ainda defeituoso.

Aceite: peça volumétrica correta, sem películas/resíduos, materiais exteriores preservados, cavidade complementar quando aplicável; erro explicado para patch não suportado. Testar com folga zero antes de introduzir folga.

## INV-002 — destaque pela base tenta criar uma face já existente

Prioridade: alta, bloqueia uma operação básica. Status: erro confirmado na captura; causa topológica exata pendente de reprodução.

Referências: [configuração](imagens/INV002_171258.png), [erro](imagens/INV002_171316.png).

### Observação

Objeto Cube em Edit Mode; material amarelo selecionado; Área 2 com 13 faces; modo **Destacar Saliência pela Base**; interface **Material da Peça Extraída**; folga **5 mm** aplicada à peça extraída. A primeira imagem mostra configuração e região selecionada; a segunda registra:

> Falha na criação de tampa da base para a Parte A: faces.new(...): face already exists

O erro indica tentativa de criar uma face que o BMesh já reconhece como existente. Não é a mensagem de base não planar, espessura insuficiente ou seleção ausente. Portanto, o bloqueio imediato está na construção da tampa. A imagem não demonstra mau uso; se a seleção incluir um caso incompatível, a extensão precisa diagnosticá-lo antes desse erro interno.

### Hipóteses a verificar

1. A região de material inclui faces coplanares no entorno da saliência. O destaque mantém essas faces em A e tenta criar a tampa sobre parte de uma face existente.
2. A triangulação retorna um triângulo repetido ou sobreposto, ou o mapeamento dos índices do contorno reutiliza vértices incorretamente.
3. O contorno tem vértices repetidos ou colineares tratados inadequadamente. A auditoria já demonstrou triângulos de área zero na triangulação original da 0.8.7; isso é evidência de fragilidade, não prova de ser a causa desta duplicação.
4. Uma criação parcial anterior da mesma tampa é repetida dentro da execução. Conferir recursos/estado de candidatos e índices, sem confundir com backups de operações anteriores.

A folga de 5 mm é outra variável a testar, mas a mensagem não prova que ela causa a duplicação. Na base 0.8.7 recebida, a tampa de A é criada antes do deslocamento da folga. A nova mensagem explicativa não aparece exatamente nesse ZIP: verificar a compilação instalada.

### Instrumentação exigida

- Registrar origem e normal da base, planicidade em mm, material e identificação estável da região.
- Registrar faces selecionadas coplanares e faces com relevo, contorno ordenado e mapa índice→vértice.
- Antes de criar cada triângulo, registrar seus três vértices e procurar face já existente com os mesmos vértices.
- Se houver colisão, identificar se a face veio da entrada, de uma tampa anterior ou de uma triangulação duplicada. Registrar área, orientação e faces incidentes em cada aresta.
- Medir área já coberta no plano da base e área ainda aberta, para evitar construir uma tampa completa sobre superfície parcialmente existente.
- Executar primeiro com folga zero, depois valores pequenos, e finalmente 5 mm quando viável.

### Correção proposta

Validar e classificar a região antes da separação. No destaque volumétrico, faces exteriores planas do corpo não devem virar lâminas sem volume em A apenas por terem o mesmo material da saliência. Definir qual é o domínio geométrico da base e mostrar a região efetivamente extraída.

Construir tampas somente sobre a área aberta que necessita fechamento. Preservar uma face existente somente quando ela pertence ao domínio correto, tem orientação compatível e não gera sobreposição ou incidência incorreta. Não considerar todos os erros face already exists como sucesso.

Deduplicar triângulos por identidade dos vértices, validar área e cobertura e preservar todos os segmentos do perímetro. Inverter a ordem dos mesmos três vértices não resolve a duplicação de uma face; não repetir faces.new como correção.

Se a seleção tiver região plana pintada junto a uma saliência e o algoritmo não suportar esse caso, exibir diagnóstico explícito e destacar faces conflitantes. Preferir suporte geométrico correto quando a ligação é inequívoca; não instruir o usuário a repintar a malha sem explicar a limitação.

Não usar convex hull, não preencher todos os buracos da malha e não remover faces arbitrariamente para passar na validação. Falha deve cancelar, limpar candidatos e preservar alvo/prévia/backup anteriores.

### Testes de aceitação adicionais

| Teste | Resultado |
|---|---|
| I01 | Região do exemplo de 13 faces com folga zero: destaque correto ou diagnóstico específico, sem erro bruto de duplicação. |
| I02 | Saliência cuja cor também pinta parte da superfície plana do corpo: domínio corretamente classificado, sem filme plano em A. |
| I03 | Base já parcialmente triangulada: nenhuma tampa duplicada; incidência de arestas válida. |
| I04 | Contorno com pontos colineares/subdivisão: sem triângulos degenerados ou repetidos. |
| I05 | Repetir a operação após falha: nenhum estado parcial da tampa é reaproveitado. |
| I06 | Folga 0/0,15/0,30 mm e 5 mm quando viável: resultados medidos e origem da falha separada do fechamento. |
| I07 | Material da peça extraída/Manter origem: mesma geometria válida, atribuição de materiais conforme a opção. |
| I08 | Entrada incompatível: aviso antes do pipeline, faces problemáticas identificadas e original intacto. |

## INV-003 — caso com profundidade 10 mm que deve ser preservado

Prioridade: alta como regressão. Status: resultado visual favorável e medidas relatadas; imprimibilidade ainda não verificada na malha/fatiador.

Este é um caso positivo, não um bug confirmado. Referências: [extração](imagens/INV003_171431.png), [medidas](imagens/INV003_171637.png), [vista frontal](imagens/INV003_171709.png), [perfil](imagens/INV003_171722.png), [conjunto](imagens/INV003_171732.png).

Região do mesmo exemplo anterior: Área 2, 13 faces; modo Extrair com Profundidade; profundidade 10 mm; folga zero; interface Material da Peça Extraída. Resultado confirmado pelo usuário no Blender, com inspeção visual da peça isolada.

O painel mostra A: 87.216,8 mm³, 40,7 × 93,4 × 93,4 mm, 90 triângulos, uma ilha; B: 15.762.396,0 mm³, uma ilha; diferença de volume exibida 0,00%. Ferramenta de medida mostra 0,01 m = 10 mm em um segmento, além de 0,022012 m e 0,09339 m. Não interpretar esse segmento como medição de espessura mínima em todos os pontos.

As vistas mostram uma peça com relevo e base de espessura perceptível, diferentemente da película anterior. Não é possível concluir só pela captura se toda a saliência foi retirada ou se permanece um núcleo no receptor. Inserto espesso e destaque inteiro são resultados diferentes e podem ambos ser úteis, desde que o modo explique qual produz.

Diferença de volume zero é arredondada e não comprova ausência de sobreposição, faces internas ou auto-interseção. Uma ilha é indício favorável de conectividade, mas não comprova manifoldness. Conferir material real nas faces: a visualização toda amarela após escolher Material da Peça Extraída não comprova que o problema geométrico anterior foi corrigido.

Revisão da recomendação INV-001: **não remover incondicionalmente o recurso de profundidade**. Preservar este caso e a extração verde planar como fixtures positivas. Preferir suporte condicionado por validação geométrica e espessura; casos sem validação suficiente podem permanecer experimentais ou desabilitados no fluxo comercial. Não limitar suporte apenas com base na aparência plana da região: este exemplo com relevo merece reprodução própria.

### Validação de impressão e testes

| Teste | Resultado |
|---|---|
| I09 | Salvar a cena positiva com 13 faces, 10 mm e folga zero; reprodução consistente sem regressão. |
| I10 | A/B com zero bordas abertas, não-manifold, faces de área zero, duplicatas e auto-interseções verificáveis. |
| I11 | Espessura mínima medida em base, cantos e relevo; nenhuma lâmina residual sem espessura útil. |
| I12 | Posição montada: ausência de sobreposição A/B, interface coerente e identificação de eventual núcleo remanescente. |
| I13 | Exportar e reimportar: mesma geometria e dimensões; fatiador sem reparo automático inesperado e com perímetros/camadas contínuos. |
| I14 | Orientação com a base plana apoiada, se de fato plana: verificar primeira camada e necessidade de suportes nas inclinações. |
| I15 | Testar pequena folga calibrada antes de montagem real; folga zero não garante montagem após impressão. |

## INV-004 — corte por plano gera prévia explodida para dentro do corpo

Prioridade: alta. Status: sobreposição aparente confirmada nas imagens; inconsistência de sinal confirmada na base 0.8.7 recebida. Validar a compilação instalada antes de associar a ocorrência ao mesmo trecho.

Referências: [plano/linha antes da geração](imagens/INV004_172046.png), [prévia após geração](imagens/INV004_172153.png), [explosão em zero](imagens/INV004_172421.png).

O usuário considera que a linha laranja está funcionando bem neste exemplo; registrar como comportamento a preservar. Corte Plano, deslocamento zero, folga zero, encaixes desativados. A segunda imagem mostra Explodido e distância 39,3 mm; a saliência não aparece afastada acima do corpo. O painel identifica A como superior: volume 294.679,1 mm³, dimensões 103,7 × 103,5 × 30,6 mm. B tem volume 15.554.934,0 mm³ e dimensões 279,8 × 249,0 × 249,0 mm. Esses dados sugerem que as partes foram geradas; o defeito visual não significa automaticamente que a geometria foi apagada.

A imagem adicional com Explodido=0,0 mm mostra a saliência novamente na posição montada e mantém os mesmos volumes/dimensões exibidos. Essa comparação reforça a origem visual/transformacional do desaparecimento, em vez de exclusão da malha. Não prova sozinha todas as propriedades da geometria do corte. Registrar como sequência mínima: geração → Explodido 39,3 mm (saliência encoberta) → 0,0 mm (saliência visível) → afastamento positivo corrigido (saliência livre do corpo).

### Relação com o código conhecido

`geometry_plane.slice_mesh_by_plane` usa clear_outer=True e retém A no lado negativo de sua normal efetiva. `compute_explosion_offsets` retorna A=+normal*d/2 e B=-normal*d/2, aproximando as partes em vez de afastá-las nessa convenção. `operators.update_preview_positions` passa a normal atual do plano e não considera invert_sides nesse caminho. Portanto, há dois pontos a corrigir: sinal da translação e associação da direção aos lados efetivamente gerados.

Uma normal de plano não precisa estar errada: inverter seu sinal descreve o mesmo plano geométrico, mas troca a convenção dos lados. A prévia precisa manter a relação entre essa convenção e A/B. Não recalcular a direção pela aparência da câmera ou pelo eixo global Z.

### Correção e controle solicitado

Guardar a normal/interface efetiva e as matrizes montadas na prévia validada. Calcular saída de A/B conforme o lado real de cada peça. Quando o parâmetro de corte muda e a prévia fica desatualizada, a exibição continua usando os dados da prévia antiga até regeneração bem-sucedida.

Adicionar controle visual **Inverter sentido da explosão**, independente de Inverter Lados do corte e de inverter macho/fêmea. Distância permanece positiva; um fator visual +1/-1 troca o sentido dos deslocamentos. Isso implementa a ideia do usuário de movimento positivo/negativo com uma interface mais clara. Um campo avançado de distância assinada pode ser oferecido, mas não precisa substituir o controle simples.

O controle manual complementa o automático e permite inspeção; não substitui a correção da convenção. Distância positiva no comportamento automático deve afastar, por padrão. Inverter somente a explosão não modifica geometria, materiais, folgas, encaixes, assinatura geométrica nem posições montadas de exportação. Atualizar overlays para acompanhar o deslocamento visual escolhido.

Nunca aplicar o deslocamento cumulativamente a uma peça já explodida. Determinar se a distância indicada significa deslocamento total relativo ou por peça e documentar: a implementação atual usa d/2 para cada lado. Verificar original/backups sobrepostos e distância suficiente para liberar toda a saliência antes de concluir desaparecimento.

### Testes de aceitação adicionais

| Teste | Resultado |
|---|---|
| I16 | Exemplo de plano sem folga/encaixes: distância positiva afasta as peças e deixa A visível fora do corpo. |
| I17 | Mesmo plano com normal oposta e invert_sides alternado: A/B seguem os lados reais, sem penetração automática. |
| I18 | Inverter sentido da explosão duas vezes: volta ao mesmo estado sem alterar o corte. |
| I19 | Distância 0/20/40/20 e Montado/Explodido repetidos: sem drift; Montado restaura matrizes exatas. |
| I20 | Corte desatualizado: exibição usa snapshot válido anterior; parâmetros novos não invertem a prévia antiga. |
| I21 | Exportação e overlays: exporta montado e mantém linha de corte corretamente associada ao estado visual. |
| I22 | Comparação 0,0/39,3/0,0 mm do relato: geometria e métricas invariáveis, distância zero idêntica ao estado Montado; sentido automático positivo libera a saliência. |

## INV-005 — Loop não planar aceito pelo AUTO falha no fechamento

Prioridade: alta. Status: erro e não planicidade confirmados no painel; causa específica da falha pendente de reprodução da cena instalada.

Referência: [loop de 19 vértices](imagens/INV005_172720.png).

Cube.002 em Edit Mode; Loop com 19 vértices; aviso de desvio não planar **14,76 mm**; face-semente 406; AUTO decide Destacar Saliência; encaixes desativados e folga de interface desabilitada. Mensagem: **Parte A possui 19 arestas não-manifold/abertas (não é um sólido fechado)**.

A seleção foi capturada e a geração foi tentada. Não há prova de mau uso. A coincidência entre 19 vértices do loop e 19 arestas inválidas sugere investigar se o perímetro inteiro ficou sem tampa, mas é hipótese: contar e identificar as arestas reais para confirmá-la. O painel não distingue bordas abertas de arestas com incidência maior que dois.

Um loop fechado na superfície não define uma superfície de corte interna única, especialmente quando não planar. É possível fechar certos loops não planares com superfície triangulada válida, mas essa superfície não deve atravessar a própria saliência/corpo nem produzir auto-interseção. Não projetar silenciosamente o contorno para um plano.

Na base 0.8.7, AUTO considera relevo e pode escolher DETACH sem validar antes se o fechamento é suportado. `slice_mesh_by_loop` separa faces por flood fill e tenta holes_fill/edgenet_fill nas bordas; não constrói um contrato explícito de superfície não planar compartilhada. Também coleta todas as bordas abertas do resultado, podendo misturar bordas anteriores com o corte. Confirmar o comportamento na compilação instalada, que já mostra mensagens novas.

### Correção/investigação

- Validar entrada e ciclo de corte, semente e separação das regiões antes de criar candidatos.
- Identificar somente as arestas do contorno da operação, sem preencher aberturas anteriores.
- Planejar uma única superfície de fechamento para A/B, com orientações opostas, contorno preservado e sem interseção com a geometria exterior. Não gerar tampas independentes incompatíveis.
- Para não planicidade, definir suporte explícito: casos validados recebem fechamento triangulado; caso não suportado cancela antes do pipeline, mostra o perímetro e explica como escolher outra base/contorno.
- AUTO precisa considerar validade do fechamento e capacidade do método, não apenas altura do relevo. Aviso no painel deve corresponder à escolha automática.
- Mostrar as arestas inválidas e estágio em que apareceram; preservar prévia anterior, alvo e backup em falhas.

Não eliminar validação manifold, não nivelar todos os vértices do contorno e não resolver aumentando a tolerância para absorver desvio de 14,76 mm.

## INV-006 — loop planar pode produzir lâmina ou extremidades pouco imprimíveis

Prioridade: alta para diagnóstico de impressão. Status: sintoma de película relatado pelo usuário; a imagem fornecida mostra configuração, não o resultado final dessa operação.

Referência: [loop planar de 32 vértices](imagens/INV006_173049.png).

Loop com 32 vértices, desvio 0,00 mm, seed 418; AUTO decide Destacar Saliência; encaixes desativados. O painel mostra Prévia removida, portanto não tomar a superfície da imagem como película comprovadamente produzida pelo corte. O usuário relata lâmina no destaque e ponta triangular muito fina ao usar profundidade.

Separar três possibilidades: (a) região selecionada é quase coplanar com a tampa e não possui volume útil; (b) o corte atravessa superfícies inclinadas e produz uma cunha/ponta fiel à geometria; (c) fechamento, projeção ou booleano gera face duplicada/resíduo que não deveria existir. Triângulos visíveis na malha não provam parede fina: medir espessura física e seccionar o resultado.

Plano da interface é planar, mas isso não garante espessura útil da região. Profundidade configurada também não garante espessura mínima em todos os cantos, sobretudo se a direção de extração for quase tangente a uma face. Um sólido pode ser topologicamente fechado e ainda ter detalhes que o fatiador omite ou que são frágeis.

### Opções de tratamento

1. Diagnóstico de espessura/volume antes de publicar: avisar sobre região sem volume, trechos de parede abaixo do limite escolhido e resíduos degenerados. Medir peça e receptor separadamente.
2. Mostrar a superfície de corte proposta e destacar zonas críticas, para o usuário escolher um contorno mais próximo da base ou outro método.
3. Quando a ponta fina é resultado fiel do corte, oferecer ajuste explícito: recuo do corte, remoção da ponta abaixo de limiar, chanfro ou espessamento localizado. Cada opção altera a peça e deve regenerar a interface complementar e a prévia.
4. Não aplicar offset/espessamento geral por padrão: pode alterar silhueta e encaixe. Preservar o corte nominal, com aviso, quando for válido e o usuário aceitar o detalhe fino.
5. Para filme de volume zero, bloquear como resultado inválido; não tratá-lo como peça imprimível só por ter faces.

Evitar um limiar universal de impressão: considerar perfil/limite escolhido pelo usuário e conferir no fatiador. Pontas matematicamente agudas terminam em espessura zero; o diagnóstico deve avaliar extensão do trecho fino e sua relevância, sem classificar qualquer aresta externa de um sólido como defeito.

### Testes de aceitação adicionais

| Teste | Resultado |
|---|---|
| I23 | Loop não planar do relato, 19 vértices: fechamento válido ou diagnóstico precoce; nenhuma peça aberta publicada. |
| I24 | Loop não planar simples suportado: A/B compartilham a mesma tampa, sem interseção com o exterior. |
| I25 | Entrada com abertura fora do loop: não fechar nem confundir com contorno da operação. |
| I26 | AUTO em região sem volume ou fechamento incompatível: explicação específica antes da geração. |
| I27 | Loop planar de 32 vértices: reproduzir destaque e profundidade, medir peça real e receptor. |
| I28 | Cunha fiel versus lâmina degenerada: identificar ambos com diagnóstico distinto. |
| I29 | Ajuste explícito de ponta/espessura: preservar complementaridade e mostrar diferença geométrica ao usuário. |
| I30 | Corte válido com ponta fina aceita pelo usuário: manter nominal e advertência, sem correção destrutiva automática. |

## Integração ao plano principal

INV-001 complementa os achados de extração, folga e materiais; a retirada do recurso é recomendação, não decisão já aprovada. INV-002 complementa C01/C02 da auditoria: além de degeneração, investigar duplicação e sobreposição das tampas.

INV-003 registra um resultado que deve continuar funcionando e refina a recomendação de escopo de INV-001. INV-004 amplia C04 da auditoria e adiciona um controle manual independente para a explosão. INV-005 investiga suporte a fechamento não planar; INV-006 distingue filme inválido de cunha fiel mas pouco imprimível. Os próximos exemplos recebidos devem ganhar identificador INV-007 em diante, com configuração, mensagem exata, versão instalada, hipóteses e aceite. Relatos semelhantes podem ampliar um caso existente, evitando duplicar tarefas com causas ainda desconhecidas.
