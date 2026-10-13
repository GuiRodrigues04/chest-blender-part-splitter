# INV-013 — distribuir encaixes conforme a interface real

Complemento de 12/10/2026. Não substitui INV-014: antes de distribuir, validar origem e topologia do loop. Novas capturas mostram contorno côncavo semelhante a uma faixa em C com prolongamento.

## Evidência adicional

- Imagens 01/02: pino cilíndrico, diâmetro 6 mm, inserção 8 mm, folga lateral 0,15 mm, fundo 0,50 mm, margem 4 mm. Imagem 02 mostra dois pinos selecionados. Erro de margem/domínio no encaixe 1.
- Imagem 03: um pino central, diâmetro 3,62 mm, inserção 8,46 mm, chanfro 0,34 mm, folga lateral 0,15 mm, margem 1 mm. Mesmo tipo de erro.
- Reduzir diâmetro/margem não garante solução: se o centro está num vazio, pinos menores continuam inválidos. Esta é hipótese forte da configuração, não reprodução do candidato real na 0.8.8.

O centro de bounding box — e mesmo o centroide de área — pode ficar fora de um domínio côncavo. Na 0.8.6, compute_connector_layout usa centro da caixa UV no caso CENTER e posições simétricas predefinidas nos demais casos. Verificar a função atual.

## Recurso proposto para 0.8.9

**Sugerir posições**: manter quantidade, dimensões e tolerâncias escolhidas; procurar um arranjo suportado pela geometria.

**Sugerir quantidade**: ação distinta e opcional, propõe quantidade e justificativa para revisão. Não prometer resistência mecânica: forma, material, direção das cargas e processo de impressão não estão totalmente definidos.

Manter CENTER/LINEAR_2/LINEAR_3/GRID_4 como distribuições explícitas. Automático livre é um modo separado; não chamar de “2 Pinos (Linha)” dois pontos distribuídos sem colinearidade.

## Algoritmo incremental

1. Obter interface verdadeira e validada em posição montada: contornos externos, vazios e ilhas. Não usar somente bounding box ou pintar material como teste de domínio.
2. Construir domínio de centros seguros considerando o perfil fêmea e margem. Círculo: raio nominal + folga por lado + margem. Cápsula: perfil completo e orientação.
3. Gerar candidatos em malha 2D determinística/adaptativa e/ou pontos de máxima distância das bordas. Restringir à região útil; identificar vazios e trechos estreitos.
4. Um pino: escolher ponto com boa distância mínima às bordas, não o centro vazio da caixa. Equilibrar posição e suporte geométrico, sem afirmar resistência.
5. Dois ou mais: buscar separação e cobertura entre candidatos válidos, evitando concentração numa extremidade. Respeitar distância mínima entre cavidades, margem e espessura residual.
6. Para Linha: procurar linha/intervalos viáveis e pontos colineares. Se falhar, oferecer “Distribuição automática livre” ou edição manual, sem troca silenciosa.
7. Para Grid: preservar definição de grade; oferecer alternativa livre se a grade não cabe.
8. Validar geometria 3D para cada candidato: contato e união do macho, cavidade no receptor, profundidade + folga de fundo, espessura residual e colisões entre encaixes. A projeção 2D é filtro inicial.
9. Considerar chanfro/alargamento de entrada no envelope de verificação. Não verificar só o cilindro nominal se o processo cria geometria maior.
10. Exibir candidatos bons/rejeitados e domínio seguro antes do booleano. Distinguir falta de espaço, posição inadequada, parede insuficiente e busca inconclusiva.
11. Permitir mover pinos individualmente e fixar posições. Revalidar ajustes e manter os pinos fixos quando o usuário solicita nova sugestão dos restantes.
12. Após alterar alvo, loop, folga de interface ou dimensões, invalidar sugestão antiga. Não mover a proposta com base em uma prévia explodida.

Para interfaces não planares, não projetar tudo em UV como se a planificação fosse válida. Limitar o automático inicial a interfaces planares suportadas e mostrar limitação para o restante.

## UI

- Quantidade: escolhida pelo usuário; opção separada para pedir sugestão.
- Distribuição: Centro / Linha / Grade / Automática pela forma / Manual.
- Botão Sugerir posições.
- Indicação visual dos pinos e das zonas sem espaço.
- Explicação: “O centro do contorno cai numa área vazia; posição deslocada para uma faixa válida.”
- Se quantidade não couber: informar e oferecer sugestões de quantidade/diâmetro/profundidade para aceitar; não alterar parâmetros automaticamente.

“Margem da borda” deve informar sua referência: espaço entre perfil da cavidade e borda da interface, não apenas distância do centro do pino.

## Foco em impressão e montagem

Pinos e faces novas pertencem ao material da peça em que foram construídos. Receptor conserva material do corpo nas cavidades. Preferir poucos encaixes bem separados quando isso atende ao domínio geométrico, mas não generalizar “menos é sempre melhor”.

Mais pinos não significam automaticamente montagem melhor: aumentam exigência de alinhamento. Recomendações são geométricas, com revisão do usuário e teste físico, não cálculo universal de carga.

## Aceites

1. Faixa em C: centro fora do material identificado; Automático encontra posição válida quando existe suporte.
2. Caso 03, diâmetro 3,62 e margem 1: comparar candidato central antigo versus sugestão; comprovar causa com UV reais.
3. Dois pinos: solução com separação adequada sem invadir vazios; manter exatamente dois se solicitados e viáveis.
4. Interface retangular: distribuições antigas válidas não regridem.
5. Furos/ilhas/faixas estreitas: nenhuma cavidade corta uma região vazia ou colapsa parede.
6. Inserção 8/8,46 mm: profundidade e fundo validados em 3D, não aprovados apenas por largura visual.
7. Falta real de espaço: mensagem específica e sugestões; original/prévia anterior preservados.
8. Mover/fixar posição: regeneração determinística, folgas medidas e materiais corretos.
9. INV-014: dados antigos do loop nunca alimentam sugestão.

Estado: novas evidências visuais e proposta de desenvolvimento. Não há execução Blender ou código 0.8.8 disponível neste pacote. Para reproduzir na cena exata, capturar novamente esse contorno e salvar o estado pré-geração; Testes_2 anterior contém outro estado pós-commit e não prova identidade deste caso.
