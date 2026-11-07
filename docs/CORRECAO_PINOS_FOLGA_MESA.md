# Correção dos pinos após folga entre peças — 2026-10-20

## Reprodução e causa

A placa `Placa_Mesa_Chest_Inteira.blend` entra fechada e passa pela validação estrita: não há bordas abertas, arestas nulas ou faces degeneradas. O corte por material também passa com profundidade de 5 mm e folga entre peças de 0,10 mm.

Ao acrescentar os pinos (diâmetro 5 mm, inserção 2 mm, chanfro 0,20 mm, folgas lateral/fundo de 0,10 mm), a operação booleana produz quatro faces degeneradas na borda da Parte A. As faces ficam longe dos pinos. A mesma falha ocorre com um pino central, sem chanfro e invertendo o lado macho. Zerar apenas a folga entre peças evita a falha.

O defeito está no tratamento numérico da geometria após as booleanas de encaixe, quando aplicado ao resultado já ajustado por folga. A triangulação fina da placa expõe a fragilidade, mas a fonte não contém as quatro faces inválidas. Esse problema é distinto dos vértices desconectados na importação padrão de GLB.

## Alteração

`sanitize_mesh_micro_degeneracies` já era usado após as booleanas. Antes, retornava imediatamente quando não encontrava uma aresta menor que 0,0001 mm. Um triângulo quase colinear pode ter área nula e arestas relativamente longas; por isso as quatro faces escapavam.

O saneamento agora também dissolve localmente faces reprovadas pela validação estrita cuja altura efetiva seja inferior a 0,0001 mm. Faz até quatro passagens porque uma dissolução pode revelar outra degeneração na mesma região. Não altera o limite de área da validação nem remove indiscriminadamente faces pequenas.

A limpeza é transacional: só é aceita se o resultado passar na validação estrita, não aumentar bordas não-manifold, mantiver os limites geométricos dentro de 0,0001 mm e respeitar o limite de mudança de volume `max(0,00001 mm³, volume × 10⁻⁸)`. Caso contrário, a malha anterior é recuperada e o erro continua sendo exibido.

As mudanças do Antigravity em captura de faces/arestas e interface foram preservadas. Nenhum arquivo de modelo original foi alterado.

## Regressões

`tests/test_connector_clearance_slivers.py` usa uma fixture portátil derivada da placa fornecida, com 94 vértices e 184 faces. Exercita o operador completo com folga de 0,10 mm e as configurações automática, central, macho invertido e sem chanfro. Verifica sólidos fechados, ausência de degenerações e preservação da fonte. Inclui um cubo inclinado como controle, preservação de faces pequenas válidas e rollback de uma limpeza insegura.

Os logs da suíte completa ficam em `evidence/connector_clearance_fix/`, com o resumo em `summary.json`. A instalação em disco requer reiniciar o Blender para que a sessão carregue o código atualizado; a cena aberta não é modificada pelo instalador desta correção.

Resultado: 56/56 suítes passaram no Blender 5.2.0 LTS, incluindo o novo teste de regressão. O pacote `dist/chest_part_splitter-0.8.16.zip` foi reconstruído e conferido pela suíte de pacote. A correção foi instalada somente em `diagnostic.py` nas duas disposições de módulos já existentes; as versões anteriores foram preservadas em `evidence/connector_clearance_fix/installed_before/`.
