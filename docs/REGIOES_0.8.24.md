# Testar o Splitter 0.8.24

Salve o trabalho e reinicie o Blender após atualizar a extensão. O painel deve mostrar 0.8.24.

## Pata laranja pelo material

1. Defina o gato original completo como alvo. No modo Material, escolha a cor laranja e a região da pata desejada.
2. Clique em **Separar região inteira (sem criar casca)**. A extensão passa para **Fechar região**, captura as faces e começa com folga entre peças de **0 mm**, sem pinos.
3. Clique em **Gerar / Atualizar Prévia**. Confira a pata destacada, a parte de trás e o corpo. Não é necessário duplicar, escalar 1.01 nem modelar uma casca.
4. Em **Contato para os pinos**, escolha um dos contatos da lista. A superfície fica selecionada em laranja na prévia em modo de edição. Para escolher outro contato que não aparece na lista, selecione uma face da superfície nova do corte e clique em **Usar face selecionada na prévia**. Faces exteriores não servem como contato.
5. Ative **Ativar Encaixes**, comece com **1 Pino (Centro)** e escolha **Macho A/B**. Para o gato deste teste foram usados diâmetro 8 mm e comprimento 12 mm. Gere a prévia novamente e confira macho/furo. Depois confirme o corte.

Também é possível usar **Fechar região → Editar alvo**, selecionar manualmente as faces exteriores da peça (inclusive laterais e fundo, se fizerem parte dela), e clicar em **Capturar faces para separar**. A captura se mantém ao trocar a seleção. Se editar a geometria ou os materiais do alvo, capture novamente.

## Cortador sólido

Mantenha seu cortador fechado, posicione-o e gere a prévia com folga entre peças = 0 mm. Escolha o contato após a prévia e ative os encaixes, como acima. Apenas a superfície escolhida recebe pinos. Os modos antigos continuam disponíveis, inclusive a geração de cortador por extrusão para quando o objetivo for uma casca.

## Ajustes e limites deste teste

- **Folga entre peças: 0 mm** no novo fechamento e no sólido com pinos escolhidos na prévia. A captura inicia explicitamente esse valor. Não confundir com **Folga por lado** e **Folga de fundo dos pinos**, que podem ser ajustadas e já alteram o encaixe. A folga geral de interfaces curvas será uma etapa posterior.
- Se mudar o corte depois de escolher o contato, use **Reescolher contato / prévia sem pinos**, gere a prévia e escolha novamente. Alterar apenas as medidas ou folgas dos pinos não exige reescolher o contato.
- Os contatos seguem a malha original. Uma borda curva pode produzir vários triângulos com inclinações diferentes; escolha uma área ampla que comporte o pino. Os fechamentos não são alisados automaticamente.
- O motor recusa seleções que não produzam duas peças únicas, fechadas e com volume. Contornos bifurcados, regiões com buracos incompatíveis, seleção inteira do objeto ou mais de 128 vértices em uma borda podem exigir ajuste manual/cortador modelado.
- Trabalhe próximo da origem e com dimensões físicas corretas. Modificadores ativos precisam ser aplicados em uma cópia antes da captura por faces. Este fluxo preserva a superfície e os slots de material; não transporta mapas UV/atributos de pintura por vértice da região.
- Testes geométricos não substituem avaliar a direção de inserção, colisões durante a montagem e uma impressão física. Comece com um encaixe e uma peça de teste.

O arquivo de exemplo é uma cópia independente. O Teste Gato.blend original permanece intacto.
