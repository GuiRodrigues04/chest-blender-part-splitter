# Part Splitter — correções após os testes da 0.8.7

Plano para Antigravity / Gemini Pro. Data: 11/10/2026. Objetivo: corrigir os problemas observados nos testes mais recentes, preservando a extração por profundidade que funciona para regiões planas.

## 1. Base e limites desta revisão

As imagens mostram recursos posteriores ao código 0.8.6 recebido: modo de extração de material, folga da interface, linha de corte e deslocamento do plano. O ZIP dessa implementação atual ainda não foi recebido. Portanto, **não atribuir às funções antigas a causa confirmada dos novos sintomas**.

A última fonte completa analisada foi `chest-blender-part-splitter-0.8.6.zip`, hash SHA-256 `fb6cdb60a7d83e7b460fe6e1c6a2273502aad200ddda320cb7b7a996397cd44b`. Os anexos recentes também repetem um pacote reduzido da 0.8.6 e a 0.8.5; eles não incluem as novas opções vistas na interface. A revisão está fundamentada nas imagens, nos requisitos do usuário e nas limitações identificadas na base anterior.

Este documento complementa o plano geral da 0.8.7, substituindo suas orientações nos pontos refinados aqui. O implementador deve abrir o checkout atualmente usado no Blender, conferir manifesto, hash do pacote instalado e nomes reais das funções. Usar a numeração vigente: se 0.8.7 ainda estiver em desenvolvimento, corrigir nessa versão; se já tiver sido lançada, registrar um novo patch conforme a política do projeto. Não mudar a versão com base apenas no título deste documento.

Não houve teste no Blender neste ambiente. Capturas não comprovam espessura, ausência de interseções ou imprimibilidade. A demonstração de grade incluída é matemática e isolada; não reproduz automaticamente a cena do usuário.

## 2. Resumo do trabalho

| ID | Problema | Resultado exigido |
|---|---|---|
| C01 | Material retira uma capa e deixa núcleo | Opção para destacar o volume completo da saliência, fechando sua base e deixando o corpo plano. |
| C02 | Fragmentos e divergência de volume | Corte válido sem resíduos indevidos; diagnosticar entrada e resultado. |
| C03 | Folga de Material sem efeito comprovado | Separação física medida entre interfaces; nunca confundir com vista explodida. |
| C04 | Linha fina, interrompida ou deslocada | Contorno correto, legível e coerente em vista montada/explodida. |
| C05 | Grade com quatro encaixes rejeitada | Distribuição dentro da interface real quando houver espaço; diagnóstico específico se não houver. |
| C06 | Pinos brancos numa peça amarela | Material da região de ligação, com fallback por área predominante da peça. |
| C07 | Prévia antiga confunde após falha | Preservar geometria anterior com aviso persistente e bloqueio das operações do estado inválido. |

## 3. C01 — dois comportamentos de extração por material

### Resultado solicitado

Nas imagens M01/M02, a peça amarela é uma saliência volumétrica unida ao cubo. Ao destacá-la, deve sair o ressalto inteiro, com interior sólido e uma tampa em sua base. O cubo deve voltar a ter a parede plana naquela região, com fechamento próprio. Não deve restar um núcleo branco com o formato do ressalto nem uma lâmina branca externa ao perímetro da sua base.

Na M03, a região verde é uma área plana da superfície. A opção Extrair por Profundidade deve continuar gerando uma peça sólida de profundidade definida e uma cavidade complementar no corpo.

### Interface e algoritmo

Manter opções explícitas: **Extrair por profundidade** e **Destacar saliência pela base**. AUTO, se existir, apenas sugere com explicação; o usuário pode substituir. O modo visível na M02 é Extrair por Profundidade, portanto a seleção desse modo não prova um defeito no modo de destaque. Ainda assim, fragmentos não devem ser aceitos como resultado válido de extração.

Para destacar pela base:

1. Obter a região conectada de faces do material selecionado a partir da malha atual.
2. Identificar as arestas que a ligam ao corpo e validar perímetro fechado, simples e base planar.
3. Identificar o lado volumétrico da saliência pela geometria/adjacência; não apenas pela normal da face-semente ou média das normais pintadas.
4. Separar o volume completo delimitado pela superfície da saliência e pela tampa da base.
5. Fechar o corpo somente no perímetro de base, preservando sua superfície exterior.
6. Validar A e B antes de publicar a prévia.

Não substituir a forma da saliência por um prisma vertical, bounding box ou convex hull. Não usar um plano global que corte outras saliências quando a intenção é extrair apenas a região selecionada. Cor nas faces não define material interno; a tampa torna explícito o fechamento volumétrico.

Se o usuário não pintou toda a superfície da saliência até sua ligação com o corpo, ou se a base é aberta/ambígua, cancelar com orientação ou pedir delimitação por Loop. Não adivinhar um volume silenciosamente.

Para extração por profundidade, preservar o fluxo planar válido da M03. Superfícies dobradas precisam de algoritmo próprio ou diagnóstico de incompatibilidade. Não deslocar várias faces inclinadas numa direção média e apresentar o resultado como uma extração volumétrica geral.

## 4. C02 — geometria defeituosa e invariantes

M01 mostra diferença de volume de 2,68%, folga exibida como zero e Parte B com quatro ilhas. M04 mostra três ilhas na Parte B. Esses números são sinais para investigação, não prova isolada de um erro: confirmar se existem componentes desconexos legítimos no alvo e se há encaixes ou modificadores alterando a comparação.

Registrar por estágio: volume original avaliado, A/B antes da folga e encaixes, faces degeneradas, arestas abertas/não-manifold, componentes, auto-interseções e sobreposição A/B. Identificar o estágio em que resíduos surgem. Malha fechada com volume positivo ainda pode conter a forma errada.

Antes de folga/encaixes, para uma entrada sólida: exigir A/B positivos, união equivalente ao original e ausência de sobreposição volumétrica, dentro de tolerância física registrada. Depois de folga/encaixes, comparar com o resultado previsto dessa alteração, em vez de exigir soma de volume idêntica.

Verificar orientação, faces coincidentes, recortes coplanares e domínio das tampas. Remover degenerações somente com tolerância física adequada, nunca apagar componentes pequenos indiscriminadamente: podem ser detalhes legítimos. Falha mantém alvo e prévia anterior intactos, limpa todos os temporários e informa a causa.

## 5. C03 — provar e corrigir folga por material

Na M04 estão configurados **5 mm**, aplicação na **Peça Extraída**, profundidade **5,39 mm** e vista explodida **24,5 mm**. O afastamento explodido não demonstra a folga. Tampouco se pode concluir pela captura que 5 mm foram aplicados corretamente.

Definir contrato em mm para a distância entre superfícies de contato. Unilateral: deslocar a interface escolhida g. Bilateral: g/2 em cada lado. Para paredes opostas, explicar a redução total da dimensão, evitando confundir folga por parede com redução de largura.

Separar folga dos pinos da folga entre as peças. Corrigir assinatura/persistência para mudar a prévia ao alterar folga ou lado de aplicação. Uma propriedade no painel sem efeito no pipeline não conta como implementação.

Aplicar somente na interface de contato, preservando superfícies exteriores. **Não escalar globalmente a peça ou o cortador.** Para extrair região planar com profundidade, tratar laterais e fundo conforme o contrato, reconstruindo junções estanques. Para destaque de saliência pela base, definir claramente a folga axial na base; não encolher toda a saliência por conveniência. Interfaces curvas exigem suporte declarado e validação própria.

Valores que eliminem espessura útil precisam de rejeição antes do booleano. Uma folga de 5 mm próxima de uma profundidade de 5,39 mm merece essa verificação, mas não é automaticamente inválida em todas as políticas de aplicação.

Criar fixture simples com medidas conhecidas. Gerar 0,00; 0,15; 0,30 e 5,00 mm separadamente, restaurar posição montada, medir distâncias assinadas/entre superfícies nos pontos definidos e verificar o exterior original. Usar 5 mm como teste de estresse e limite, não como recomendação para impressão. O relatório deve informar valor solicitado, aplicado e espessura remanescente; se houver ajuste automático autorizado, exibi-lo, nunca alterá-lo silenciosamente.

## 6. C04 — linhas de corte legíveis e corretas

P01 mostra traçado no espaço entre peças explodidas; P02 mostra linha fina e parcialmente encoberta. Não afirmar que todo trecho escondido é segmento ausente: o teste de profundidade pode ocultar corretamente a linha atrás da peça.

Verificar primeiro a geometria: interseção entre plano efetivo e alvo atual, incluindo deslocamento exibido de **0,030 mm**, transformações e modificadores considerados pelo corte. Não usar origem do plano antes do deslocamento para o overlay e outra origem para o corte. Não conectar pontos pela ordem de coleta dos triângulos, nem ligar o fim de uma ilha ao início de outra.

Deduplicar pontos/segmentos com tolerância física, tratar triângulos coplanares e reconstruir conectividade. O contorno deve seguir o corte real; diagonais internas da triangulação não devem aparecer como borda de corte. Guardar segmentos independentes se não existir ciclo fechado válido.

Política de apresentação:

- Antes da prévia: linha no alvo, espessura em pixels e contraste adequado.
- Vista montada: contorno da interface atual.
- Vista explodida: preferencialmente contorno nas superfícies de contato de A/B, usando os deslocamentos visuais de cada peça. Alternativa simples: esconder o contorno da referência original e explicar no painel.
- Trechos encobertos: opção explícita de raio-X/tracejado; manter padrão com oclusão para não confundir frente e verso.

Não deslocar a geometria de corte para resolver z-fighting. Usar solução visual pequena e controlada, com restauração do estado GPU em finally. Desenhar de cache; recalcular fora do draw callback e não executar booleanos por frame. Invalidar cache em alterações, Undo/Redo e troca de alvo. Opções visuais não alteram assinatura geométrica. Esconder overlays de modos inativos.

## 7. C05 — quatro encaixes e domínio real

E02 informa: encaixe nº 1 fora do domínio ou ultrapassando margem de **1 mm**. A tentativa usa diâmetro **10 mm**, folga lateral **0,10 mm**, inserção **8,97 mm**, folga de fundo **0,50 mm** e grade com quatro. O erro é de inclusão/margem; não comprova falha do booleano nem limite de três pinos.

Na 0.8.6, `compute_connector_layout` cria GRID_4 sobre a caixa envolvente dos contornos em U/V. Essa estratégia pode falhar em um quadrado se os eixos ficarem próximos de suas diagonais: os cantos da grade caem fora do quadrado, embora quatro pinos caibam quando a grade é orientada corretamente. **É uma hipótese a conferir no código instalado**, não a causa confirmada da captura.

O arquivo `Demonstracao_Grade_4.py` ilustra esse problema com uma seção quadrada de 103 mm em eixos girados 45 graus. Ele usa a fórmula antiga, demonstra posições externas e uma configuração interior possível. Não reproduz o Blender nem prova a orientação usada no screenshot.

Plano de correção:

1. Registrar contornos externos/furos ordenados, origem, eixos, dimensões e quatro candidatos em mm.
2. Conferir estabilidade dos eixos em interfaces simétricas: PCA quase degenerada não deve provocar rotação arbitrária da grade.
3. Para retângulos, buscar base alinhada às bordas ou retângulo orientado adequado. Para regiões gerais, buscar posições no domínio com distância suficiente das bordas/furos.
4. Considerar raio da cavidade, margem, distância entre pinos e espessura do receptor. Mostrar cada motivo de rejeição separadamente.
5. Se a distribuição nominal não couber mas existir uma grade viável, oferecer ajuste determinístico dentro do domínio; mostrar posições efetivas.
6. Se não houver solução, cancelar com explicação. Não reduzir quatro para três nem retirar a validação de segurança.

Desenhar candidatos antes da geração: válidos em uma cor, inválidos em outra, com índice. A posição de teste e a posição do booleano devem compartilhar os mesmos dados. Conferir normal e inversão macho/fêmea.

## 8. C06 — material dos pinos

O requisito é material real nas faces, não apenas cor de objeto no viewport. Na E03, pinos ligados à peça amarela aparecem brancos; devem ficar amarelos conforme a regra abaixo.

Regra aprovada pelo usuário: se a região de ligação tiver um único material, aplicar esse material ao **pino inteiro**. Se envolver materiais diferentes, usar o material predominante da peça que possui os pinos para o pino inteiro. Não produzir pinos listrados por amostragem ponto a ponto.

Calcular predominância pela soma das áreas das faces em world space, antes de adicionar pinos, sem contagem de polígonos. A triangulação deve preservar o total; escala não uniforme deve ser considerada. Excluir geometria temporária e decidir explicitamente se tampas recém-criadas entram na referência. Preferir superfície original da peça para não deixar uma tampa grande alterar artificialmente a predominância. Empate: critério estável por índice de material; material ausente: fallback documentado.

Na base 0.8.6, `apply_connectors_boolean` copia slots do macho para o pin_mesh, mas isso sozinho não escolhe o material adequado: as faces criadas precisam de `material_index` correto e os slots devem ser mapeados pela identidade do material. Auditar a implementação atual antes de alterar.

Obter material local na área real de ligação do pino. Se não for possível resolver a área sem ambiguidade, aplicar fallback por área predominante. Atribuir material em todas as faces do pino antes da união e conferir que o booleano preserva esse mapeamento. Não recolorir as demais faces da peça para esconder o defeito.

Manter material adequado também nas paredes das cavidades do receptor, sem usar necessariamente o material do macho. Preservar o resultado em 3MF; STL comum não carrega materiais. STL por material deve respeitar a atribuição, sem criar corpos extras apenas para simular cores.

## 9. C07 — prévia antiga e estado após erro

E02 mostra que a prévia anterior foi preservada. Os pinos visíveis não comprovam a tentativa nova com quatro. Manter essa proteção, mas adicionar aviso persistente: **“A atualização falhou. Você está vendo a prévia anterior.”** Mostrar motivo completo sem truncamento, por popup ou painel expansível.

Manter último conjunto validado e configuração efetivamente usada separados dos parâmetros atuais. Bloquear confirmação/exportação da configuração atual enquanto estiver inválida/desatualizada. Remover Prévia deve continuar disponível e operar apenas na sessão correta.

## 10. Imagens para reprodução

| Referência | Arquivo |
|---|---|
| M01 — capa superior, resíduos e volume | [M01](imagens/M01_capa_superior.png) |
| M02 — saliência lateral e modo de profundidade | [M02](imagens/M02_capa_lateral.png) |
| M03 — extração verde que deve ser preservada | [M03](imagens/M03_extracao_plana_valida.png) |
| P01 — linha em vista explodida | [P01](imagens/P01_linha_explodida.png) |
| P02 — linha em vista montada | [P02](imagens/P02_linha_montada.png) |
| E01 — prévia com pinos existente | [E01](imagens/E01_previa_anterior.png) |
| E02 — quatro encaixes e erro de margem | [E02](imagens/E02_grade_4_erro.png) |
| M04 — folga 5 mm por material | [M04](imagens/M04_folga_material.png) |
| E03 — material branco dos pinos | [E03](imagens/E03_material_pinos.png) |

## 11. Ordem de execução e aceitação

Começar identificando a base instalada e criando fixtures dos três tipos de região. Corrigir volumes e resíduos; depois folga, posicionamento dos pinos e materiais; por último a apresentação dos overlays e avisos. Não trocar todos os métodos por um algoritmo único.

| Teste | Aceitação |
|---|---|
| R01 | Saliência superior sai inteira, sem núcleo no corpo nem lâmina fora da base. |
| R02 | Saliência lateral sai inteira, corpo fechado com parede plana. |
| R03 | Região verde planar mantém extração com profundidade e cavidade complementar. |
| R04 | Entrada com região incompleta/base ambígua cancela sem volume adivinhado. |
| R05 | Corte sem folga/encaixes conserva volume/união e não gera resíduos inesperados. |
| R06 | Folgas 0/0,15/0,30 mm medidas em posição montada; exterior preservado. |
| R07 | Folga 5 mm valida espessura e rejeita caso inviável antes de modificar a cena. |
| R08 | Troca unilateral/bilateral modifica interfaces conforme contrato e atualiza assinatura. |
| R09 | Linha coincide com corte incluindo deslocamento 0,030 mm e modificadores. |
| R10 | Montado/explodido mostram contornos coerentes; nenhum segmento entre ilhas distintas. |
| R11 | Grade de quatro em quadrado/retângulo funciona com eixos diferentes e rotação do alvo. |
| R12 | Grade em concavidade/furo preserva validação e quantidade; falha explica o motivo. |
| R13 | Pinos numa região amarela ficam amarelos; região branca gera pinos brancos. |
| R14 | Ligação multicolor usa material predominante por área, independente da subdivisão. |
| R15 | Inversão macho A/B recalcula material; 3MF reimportado preserva atribuição. |
| R16 | Falha na grade mantém prévia anterior sinalizada e bloqueia operações inválidas. |
| R17 | Escalas de cena 1/0,01/0,001 e transformações não uniformes mantêm medidas em mm. |
| R18 | Undo/Redo, remover prévia e repetir geração não deixam temporários nem referências mortas. |

Testes geométricos no Blender real, testes de viewport interativos e inspeção no fatiador quando necessário. Não marcar como aprovado um teste apenas porque o operador retornou FINISHED ou porque o arquivo exportado existe. Para pinos, conferir união real, material e contagem; para folga, medir superfícies; para corte, conferir silhueta além de manifoldness.

## 12. Referências e entrega

- [BMesh](https://docs.blender.org/api/5.0/bmesh.html): estado em Edit Mode, conectividade e propriedade das malhas.
- [Depsgraph](https://docs.blender.org/api/5.0/bpy.types.Depsgraph.html): avaliação de modificadores e limpeza das malhas temporárias.
- [MeshPolygon](https://docs.blender.org/api/current/bpy.types.MeshPolygon.html): atribuição por material_index e dados das faces; calcular área mundial quando houver escala não uniforme.
- [GPU State](https://docs.blender.org/api/current/gpu.state.html): estados de desenho e restauração.
- [Boolean Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/booleans.html): pressupostos geométricos e materiais.

Consultar compatibilidade das APIs na versão mínima suportada; os links não substituem teste nessa versão.

Entregar pacote instalável com versão real coerente, código fonte, changelog curto, fixtures, scripts e relatório R01–R18 com versão exata do Blender e casos não executados. Preservar organização compacta do repositório e READMEs sem emojis. Não anunciar correções por tentativa: anexar evidências mensuráveis e limites conhecidos.
