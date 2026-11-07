# Captura de Loop a partir das faces da placa Mesa

## Diferença entre Material e Loop

O modo Material obtém a região inteira associada ao material. A captura pelas faces do modo Loop analisa somente as faces atualmente selecionadas. Em uma malha com triângulos estreitos, é possível deixar uma microface de ligação fora da seleção: a área parece contínua, mas a seleção tem mais de uma ilha topológica.

A captura da região completa do material 0 da Mesa funciona: 84 faces, perímetro de 86 arestas. A reprodução problemática seleciona 80 dessas faces, omitindo quatro faces de área inferior a 0,01 mm². Uma delas é a ponte entre as duas ilhas selecionadas.

## Falha anterior

Ao detectar ilhas, o código tentava soldar toda a malha com tolerância de 0,05 mm. A operação era feita diretamente na malha em Edit Mode, antes de saber se resolveria o problema. No caso reproduzido, a tentativa reduziu a placa de 94 para 76 vértices e de 184 para 148 faces, e mesmo assim retornou erro. Além disso, a soldagem podia perder os marcadores das faces selecionadas.

## Correção

- A análise e qualquer tentativa de soldagem são feitas em uma cópia do BMesh. O resultado só é transferido ao objeto quando existe um contorno validado. Uma falha preserva geometria e seleção.
- A tolerância para recuperar vértices desmembrados foi reduzida para 0,0001 mm na escala local da cena, evitando a soldagem de detalhes próximos separados por 0,01–0,05 mm.
- Pequenas lacunas de seleção são completadas usando as faces existentes, sem mover vértices: a ponte precisa ter o mesmo material dos vizinhos, unir pelo menos duas ilhas selecionadas, ter área total de até 0,01 mm² e espessura efetiva de até 0,05 mm. As medidas da ponte consideram a transformação do objeto e as unidades da cena.
- Ilhas reais, omissões grandes, múltiplos ciclos e furos continuam sujeitos às verificações normais.
- A troca visual para o contorno limpa os marcadores anteriores, seleciona apenas pares consecutivos do perímetro e entra em seleção de arestas. Diagonais internas não permanecem selecionadas por acidente.
- A seleção original das faces é preservada ao recuperar uma importação com vértices desmembrados.

No caso de seleção incompleta reproduzido, a captura retorna 83 arestas e mantém os mesmos 94 vértices e 184 faces. A prévia por Loop, com extração de 5 mm, folga entre peças de 0,10 mm e pino central, resulta em duas partes fechadas. A importação padrão do GLB real também foi exercitada: 327 vértices importados são recuperados para os 94 vértices conectados, com 184 faces e zero bordas não-manifold.

## Validação e uso

As regressões estão em `tests/test_loop_capture_selection_gaps.py`: captura completa, microface omitida, importação desmembrada, unidades físicas, rejeição de ilhas verdadeiras sem deformação, preservação da fonte em falhas e fluxo completo com folga/pino. Os relatórios da suíte geral ficam em `evidence/loop_capture_fix/`.

Resultado no Blender 5.2.0 LTS: **57/57 suítes passaram**, incluindo sete novos testes de captura. O instalador foi reconstruído e validado. Foram atualizados apenas `geometry_loop.py` e `operators.py` na disposição ativa da extensão instalada; os arquivos anteriores estão em `evidence/loop_capture_fix/installed_before/`. Uma sessão separada carregou a instalação atualizada, abriu a placa original em disco (94 vértices, 184 faces), capturou a seleção parcial em 83 arestas e gerou as duas partes fechadas com folga de 0,10 mm e pino central.

A correção dos pinos feita anteriormente foi mantida. A cena aberta não é modificada pela atualização em disco. É necessário reiniciar o Blender para carregar o código novo. Caso a captura antiga tenha falhado e alterado a malha na sessão, refaça o teste a partir do arquivo original da placa; a atualização do código não desfaz alterações já feitas pela versão anterior.
