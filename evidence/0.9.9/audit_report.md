# Auditoria de modelos reais — 0.9.9

Data da execução: 10 nov 2026. Blender 5.2 background, fonte 0.9.9 com o ajuste anti-coplanar, modelos abertos sem executar scripts; nenhum `.blend` foi salvo.

## Resultado dos 11 cenários

O driver `manual_real_models_098.py` foi repetido após o ajuste anti-coplanar e terminou com **11/11 casos OK** em `real_models_audit.json`. Cada par teve duas peças, uma componente por peça, nenhuma aresta não manifold e assinatura da malha de origem preservada.

| Caso | Resultado 0.9.8 publicado | Resultado 0.9.9 |
|---|---|---|
| Placa, região verde | OK | OK |
| Placa, região azul | OK | OK |
| Placa verde, Loop/Detach | OK | OK |
| Placa azul, Loop/Whole | OK | OK |
| Pata do gato, slot 4, conectores 8 × 12 mm, folga 0,1 mm | OK | OK |
| Chifre da Spot, pino central 1 × 8 mm, folga 0,1 mm | OK | OK |
| Sugestão no chifre, macho A | OK | OK |
| Sugestão no chifre, macho B | OK | OK |
| Pé da Spot, pino 6 × 8 mm, folga 0,1 mm, macho A | OK | OK |
| Pé da Spot, pino 6 × 8 mm, folga 0,1 mm, macho B | OK | OK |
| Pé da Spot, pino 6 × 8 mm, folga 1 mm, macho A | OK | OK |

O sumário comparativo legado em `evidence/0.9.8/summary_final.json` relata que a baseline anterior à 0.9.8 passava 8 casos, falhava o posicionamento do pino do chifre por 1,356 mm e não possuía as duas sugestões dimensionais. A versão 0.9.8 publicada passou os 11 cenários; 0.9.9 repetiu esses resultados.

## Olho da Spot — folga e preservação

O driver `reproduce_eye.py` abriu `Spot corte bugado.blend`, validou a captura de 26 vértices (face semente 2239), profundidade de 5 mm e pinos desligados. O operador passou com folgas 0, 0,1, 0,2 e 1 mm. Os dois resultados permaneceram manifold, conectados e válidos; as UVs canônicas (12.270 loops) e a assinatura da malha original permaneceram iguais.

Para 0,1 mm, a peça A ficou em 695,343 mm³; sem folga ficou em 732,651 mm³. O arquivo original manteve SHA256 `66f7213e14b5867b7f7bb453ee3d88b1fe7af6d43b6de99f6dda12c061d847de` antes e depois. Resultados completos em `real_results.json`.

Uma medição física adicional usa o corte de folga zero como referência, triângulos visíveis do Blender e quatro amostras interiores por triângulo. Classifica superfícies por normal relativa ao eixo de inserção, considera apenas pontos abaixo do ombro, exclui pontos a até 0,01 mm da borda e opera diretamente nos BMeshes, sem transformação de explosão.

| Superfície, folga solicitada 0,1 mm | Amostras | Mínimo | P10 | Mediana | P90 | Máximo |
|---|---:|---:|---:|---:|---:|---:|
| Fundo, alinhado ao eixo | 96 | 0,100001 mm | 0,100002 mm | 0,100003 mm | 0,100004 mm | 0,100005 mm |
| Paredes laterais | 208 | 0,099993 mm | 0,099998 mm | 0,100000 mm | 0,100003 mm | 0,100005 mm |

Antes do ajuste, 97 de 208 amostras laterais (46,6%) coincidiam com a peça oposta. A causa foi confirmada na casca externa da ferramenta temporária: ela coincidia exatamente com a face original, e o Boolean preservava essa face. A amostra de diagnóstico ficava 3,30 mm abaixo do ombro; a banda era uma componente fechada/manifold, continha o ponto e a restauração de faces não introduzia o contato. Deslocar apenas a casca externa em 0,001 mm pelas normais das faces de contato eliminou a coplanaridade. A casca interna e os valores de folga não mudaram.

Na repetição, não houve raios laterais de folga zero e os mínimos das 208 amostras laterais e 96 do fundo ficaram a aproximadamente 0,00001 mm de 0,1 mm. As duas peças permaneceram válidas e manifold. O arquivo original manteve o mesmo SHA256 antes e depois. A verificação de UVs executada no mesmo código final comparou os 12.270 loops: nenhuma diferença; assinatura e ponteiro da malha fonte inalterados.

Dados amostrais e hashes em `eye_wall_floor_measurements.json` e execução em `eye_wall_floor_measurements.log`.

## Regressão analítica da banda de contato

`tests/test_trim_depth_contact_band.py` passou **6/6 métodos** no Blender 5.2. A fixture é um corpo 20 × 20 mm com fundo a −0,4 mm e topo inclinado a 0 / 0,2 / 0,4 / 0,2 mm; o esperado para folga 0,1 / 0,1 mm é preservar o relevo e reduzir o volume de 240 para 197,612 mm³. Folga lateral zero/fundo 0,1 mm resultou em 200 mm³; lateral 0,1/fundo zero em 236,816 mm³. Um teste adicional amostra o mínimo nas quatro paredes e exige 0,095–0,105 mm para folga 0,1 mm. O teste também mantém `clearance_excessive` para colapso de contato e usa `clearance_unresolved` para cortador aberto ou Boolean sem remoção.

## Limites

Os 11 cenários cobrem modelos reais selecionados, não todos os arquivos do usuário. A análise física adicional foi feita no olho da Spot com folga 0,1 mm e profundidade de 5 mm; as amostras estão limitadas às superfícies laterais e de fundo abaixo do ombro e afastadas da borda. A medição não afirma distância uniforme nas regiões do ombro ou fora do contato.
