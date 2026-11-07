# Estudo do pé da Spot — 7/11/2026

## Conclusão

O arquivo fornecido permite reproduzir exatamente o corte do pé: loop de 16 vértices, semente 552 e desvio de 25,0353 mm. A versão 0.9.6 fecha sem folga, mas rejeita 0,1 e 1 mm. O fechamento automático em degraus produz a saliência interna vista nas imagens. A falha de folga é a incompatibilidade das restrições de deslocamento dos vértices; não demonstra que 0,1 ou 1 mm seja fisicamente excessivo para o pé.

Um protótipo separado, seguindo a ideia do usuário (superfície estendida, Solidify e Boolean), gerou o pé com 0,1 e 1 mm sem o degrau, em um componente fechado. Isso demonstra viabilidade neste caso. Ainda existe variação nas bordas e nos vincos; não é uma correção pronta para publicação nem validação dos encaixes.

Nenhum algoritmo de produção, pacote instalado ou número de versão foi alterado neste estudo. Os scripts, resultados e imagens estão versionados para a próxima etapa.

## Entrada e reprodução

O arquivo inicialmente estava em `C:/Users/guiro/OneDrive/Desktop/Vaquinha pos cortes.blend`. Ao final do estudo foi encontrado em `C:/Users/guiro/OneDrive/Desktop/Modelos 3D e testes extensao/02_Personagens_e_Criaturas/spot/spot/Vaquinha pos cortes.blend`, com o mesmo tamanho e data de modificação inicialmente observados: 329.672 bytes, 7/11/2026 às 14:28:02. Os scripts aceitam os dois locais. SHA-256 encontrado: `579981c6eec27d03504273c3f3b5c22ba7ed492295a67490f91fbb79e95e403a`.

A cena foi salva com folga zero e prévia válida; as imagens mostram a tentativa posterior com 0,1 mm e a mensagem de preservação da prévia anterior. O usuário também pediu investigar 1 mm: ambos os valores foram testados. Os objetos são métricos, com escala de objeto 1; o modelo tem aproximadamente 1,72 m em sua maior dimensão e o pé tem cerca de 0,40 m. Essas dimensões foram mantidas nos testes.

Loop: `0,764,197,771,11,1182,306,1188,9,743,190,748,15,821,213,812`. Semente: `552`. Encaixes desativados, sem base adicional, destino da folga: peça extraída.

## Diagnóstico do algoritmo atual

O destacamento tenta um fechamento em degraus quando o desvio absoluto ultrapassa 0,5 mm. Neste caso, ele gera 50 faces de interface, incluindo base/prateleiras e paredes internas. O formato estranho é gerado antes de qualquer pino. As alterações de topologia em quads não eliminam essa construção geométrica.

Na etapa de folga, `offset_contact_surface` e `_constrained_delta` exigem preservar planos das faces externas e afastar as faces da interface simultaneamente. A tentativa falha nas restrições para 0,1 e 1 mm. Apenas desativar os degraus não resolve: o fechamento direto reduz a tampa a 14 triângulos, com duas peças fechadas, mas o mesmo afastamento por vértices continua sendo recusado.

## Protótipo da lâmina

1. Usar o fechamento direto validado como superfície comum, sem degraus automáticos.
2. Extrair essa superfície e acrescentar um anel externo de 20 mm. A extensão altera somente a lâmina; não amplia o pé nem muda o contorno original da superfície de referência.
3. Aplicar Solidify, com escala 1, espessura igual à folga e offset -1 em direção ao interior do pé. Comparar Simple/Even com Complex/Constraints, sem clamp que reduza silenciosamente a espessura.
4. Remover essa lâmina do pé por Boolean Exact. O corpo permanece com a superfície comum original. Trabalhar nas partes já identificadas pelo loop evita cortar outra perna por acidente.
5. Refinar somente a lâmina, com três subdivisões por aresta, mantendo sua superfície de referência. Não subdividir nem remodelar a vaquinha inteira.

O protótipo refinado usa triangulação explícita da superfície visível da peça antes do Boolean. Isso evita comparar volumes calculados por tesselações diferentes de quads não planos; os primeiros resultados em `blade_results.json` não devem ser usados como referência de conservação de volume. A medição válida de remoção está em `refined_results.json`.

## Medições do protótipo refinado

| Pedido | Raios normais a partir do interior da interface do corpo | Distância mínima à superfície oposta, amostrada no pé, incluindo bordas/vincos |
|---|---|---|
| 0,1 mm | 0,099935–0,100019 mm | 0,098496–0,103767 mm |
| 1 mm | 0,999943–1,000026 mm | 0,985416–1,037575 mm |

As medidas centrais não devem ser anunciadas como distância uniforme em toda a interface. As amostras do pé revelam variação localizada que ainda exige decisão e validação. O Solidify em uma superfície pouco refinada foi pior: no caso de 1 mm, as medidas normais do corpo variaram de aproximadamente 0,9698 a 1,0256 mm. A documentação do Blender também informa que Complex/Constraints não garante espessura perfeita em toda geometria: https://docs.blender.org/manual/en/5.1/modeling/modifiers/generate/solidify.html .

Em 0,1 e 1 mm, o pé refinado tem um componente e zero arestas não manifold; nenhuma das 56 amostras normais no corpo perdeu a superfície oposta. A forma externa afastada da interface foi conferida em 160 pontos, com diferença máxima de aproximadamente 0,000076 mm. A remoção de volume foi de aproximadamente 8.598 mm³ para 0,1 mm e 85.924 mm³ para 1 mm, com a mesma tesselação explícita de referência.

Não foram validadas todas as auto-interseções possíveis, trajetória física de montagem, impressão, destinos Cavidade/Ambos, folga de fundo separada, nem conectores no novo protótipo. Não se recomenda liberar o protótipo apenas pela contagem de arestas fechadas.

## Recomendação de mudança pequena

- Alterar apenas o destacamento direto por loop nesta primeira etapa. Manter os algoritmos de Plano, Sólido, Material/Profundidade e Região inteira.
- Tentar primeiro uma superfície contínua, contida e sem cruzamentos. Um desvio absoluto grande deve ser uma informação, não um comando para inventar um degrau.
- Usar a mesma superfície de referência nos dois lados e obter a folga pela remoção de uma faixa de material, sem obrigar um único vértice a satisfazer todos os planos externos.
- Manter o caminho de folga zero como fechamento compartilhado; Solidify com espessura zero não é um volume cortador válido.
- Reservar degraus/base de encaixe para uma escolha explícita. Se não houver fechamento natural válido, explicar a limitação em vez de mudar silenciosamente a intenção do corte.
- Antes de integrar, medir bordas e vincos com amostras mais densas, preservar materiais/histórico e cobrir Peça/Cavidade/Ambos. Depois testar um encaixe local em uma área realmente compartilhada. Não exigir que toda a tampa curva seja plana para permitir um pino local.
- Fazer regressão moderada: este pé, um chifre, um loop planar, uma superfície com profundidade e os exemplos já conhecidos de placa/gato. Não reescrever todos os modos para resolver este caso.

## Arquivos

- `inspect_scene.py`, `settings.json`: parâmetros exatos da cena.
- `compare_initial.py`, `initial_results.json`: seis tentativas, com/sem degraus e folgas 0/0,1/1 mm.
- `prototype_blade.py`, `blade_results.json`: primeira comparação Solidify Simple/Complex.
- `prototype_refined.py`, `refined_results.json`: fonte tessellada de maneira consistente e lâmina refinada.
- `validate_prototype.py`, `prototype_validation.json`: componente, fechamento e exterior preservado.
- `atual_sem_folga.png`, `prototipo_folga_1mm.png`: comparação no mesmo enquadramento; laranja identifica a superfície criada.
- `prepare_review.py`: gera `C:/Users/guiro/OneDrive/Documentos/ChatGPT/Extensão Blender/estudo-pe-spot-2026-11-07/Estudo_Pe_Spot.blend`.

O arquivo de revisão abre na cena `Lamina - 1 mm - explodido`. A cena `Atual - sem folga - explodido` permite comparar; `Lamina - 1 mm - montado` mantém as peças na posição real para medir. O afastamento visual das cenas explodidas é de 203,1 mm, como na demonstração do usuário, e não representa a folga física de 1 mm. Os `.blend` de estudo são locais e não estão no Git; podem ser reconstruídos pelos scripts a partir da entrada fornecida.
