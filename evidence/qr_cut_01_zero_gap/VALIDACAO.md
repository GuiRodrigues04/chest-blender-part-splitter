# Placa QR — profundidade de 0,10 mm e folga zero

Reprodução: importar o arquivo original em processo separado; aplicar o reparo seguro; Material 0 / região 0; Profundidade 0,10 mm; folgas zeradas; sem conectores.

A fonte reparada tem 1884 faces e é válida/manifold. O solver EXACT gerou a peça A com 9 arestas não manifold. O fallback MANIFOLD gerou a superfície fechada, mas a limpeza deixou uma aresta isolada de aproximadamente 0,100002 mm, ligada a zero faces. Esse resíduo sem superfície fazia a validação rejeitar o resultado.

Correção: remover somente arestas com zero faces e vértices isolados nas cópias resultantes da operação booleana, antes e depois do saneamento. Não altera faces, materiais, área de superfície ou volume. Arestas com uma face (buracos reais) não são removidas. A fonte não é modificada e a validação estrita continua ativa.

Resultado: peça A 998,978800114 mm³; peça B 218425,687378564 mm³. Fonte 219424,666260253 mm³; diferença total aproximada -0,000081575 mm³. Ambas válidas e fechadas. Confirmação conserva exatamente os volumes da prévia. A regressão verifica também que a limpeza não altera as faces/materiais/volume e não remove contornos abertos.

Isto resolve o bloqueio do corte sem folga mostrado na captura. A folga de 0,10 mm ainda pode colapsar microaberturas desta região; ela não foi reduzida nem aplicada silenciosamente.
