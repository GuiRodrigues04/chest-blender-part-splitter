# Modelos reais — comparação 0.9.7 / 0.9.8

Driver: `manual_real_models_098.py`. Baseline congelada em `scratch/baseline098`, commit `dc4977031c0679714a2217314a169795e5c7e7a9`. Fontes locais são abertas sem executar scripts e nenhum `.blend` é salvo.

## Onze cenários finais

- Placa de quatro testes: regiões verde e azul por Região inteira.
- Mesma placa: contorno das faces verdes capturado pelo operador de Loop, seguido de Destacar; e faces azuis por Loop / Região inteira.
- Pata laranja do gato: Material / Região inteira, contato 0, dois pinos de 8 × 12 mm e folga de 0,1 mm. Seleção real do slot 4, com 477 faces, sem depender dos objetos privados antigos de referência de patas.
- Chifre da Spot: arquivo `Vaquinha.blend` em fator uniforme 0,4, seção 13,86 × 11,17 mm, pino central de 1 × 8 mm e folga de 0,1 mm.
- Mesmo chifre: Sugerir dimensões e gerar a prévia, macho A e macho B.
- Pé da Spot: arquivo `Vaquinha pos cortes.blend`, pino de 6 × 8 mm, folga de 0,1 mm com macho A/B e 1 mm com macho A.

Os resultados exigem duas peças fechadas, volume positivo, nenhuma aresta não manifold, uma componente por peça e assinatura geométrica da origem preservada. O chifre conserva as UV originais.

## Resultados

**0.9.8: 11/11 cenários aprovados.** Na baseline, oito cenários passam, o teste novo de centralização reproduz o bug e duas sugestões dimensionais estão marcadas como `NOT_AVAILABLE`, pois o recurso ainda não existia.

O centro esperado é calculado independentemente a partir da área do contorno original, antes de preparar a interface dos pinos. Não se confunde com a média dos vértices (UV=0) nem com o centroide da faceta reduzida da 0.9.7. A posição atual ficou a aproximadamente **0,00423 mm** desse centroide original; a pequena diferença é compatível com a mudança do contorno físico após a folga. A tolerância do teste é 0,05 mm. Na baseline, o pino ficou 1,356 mm deslocado desse centroide e falhou na mesma verificação.

O ponto manual UV=0 é válido na 0.9.8. A sugestão escolheu **2 × 3 mm** no chifre pequeno, em ambos os lados, e as duas prévias passaram. Esse cálculo é geométrico; não constitui ensaio de resistência da impressão.

Dados completos: `baseline_final.json`, `current_final.json` e `summary_final.json`. Logs correspondentes permanecem locais e ignorados pelo Git. Comparações intermediárias com escala/seleção inadequadas foram substituídas pelos resultados finais acima.

## Recusa anterior encontrada numa exploração adicional

Capturar as faces azuis e pedir extração por profundidade de 1 mm gera dezesseis arestas nulas na Parte A. A operação é recusada tanto na baseline quanto na 0.9.8, sem publicar uma geometria inválida. Foi registrada separadamente em `known_blue_depth.json`; não é aprovação, não é regressão nova e não foi corrigida nesta versão. O driver permite reproduzir esse cenário chamando `region_loop_case(2, 'EXTRUDE')`.
