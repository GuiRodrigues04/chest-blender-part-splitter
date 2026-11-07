# Cortadores sólidos — 0.8.22

## Criar ou recuperar

Criar disponibiliza o cortador configurado sem destruir modelagem existente. Restaura ocultação do objeto, coleções e vista local. Se o objeto foi excluído, cria outro; se todos os vértices foram apagados em edição, regenera a primitiva no objeto vazio. Uma malha parcialmente editada não é reconstruída silenciosamente.

Focar revela e enquadra. Reiniciar é uma ação explícita que substitui a forma atual pela primitiva escolhida, centrada no alvo e com escala/orientação reiniciadas. Duplicar mantém uma malha independente.

## Criar pelas faces

1. Em Corte Sólido, clique em Editar Alvo ou Das faces selecionadas.
2. Selecione as faces que delimitam uma superfície a extrudar.
3. Clique em Das faces selecionadas; ajuste profundidade, extensão exterior e inversão na janela de parâmetros.
4. O novo cortador é selecionado em modo Objeto. Use Editar cortador para subdividir e moldar sua malha.

A fonte é preservada. O volume é construído transladando a superfície selecionada na direção média ponderada por área, fechando as bordas. A opção não reconstrói automaticamente uma pata inteira envolvendo interfaces perpendiculares. Superfícies que envolvem a peça ou não definem uma direção útil podem precisar de uma seleção menor ou de uma caixa moldada manualmente. Faces / Contorno preserva também o fluxo de contorno capturado.

## Alinhar o objeto inteiro

- Face do alvo: posição e orientação da face selecionada no alvo. Em edição, usa a face ativa selecionada; sem seleção válida, recusa.
- Centro da seleção: translada o centro geométrico do cortador até o centro dos vértices selecionados no alvo, preservando sua orientação. Em modo Objeto usa as origens dos objetos selecionados, excluindo o cortador.
- Cursor 3D: posição e orientação do cursor, inclusive rotação por quaternion.
- Eixos do alvo: posição da origem e orientação do alvo.
- X/Y/Z: eixo de profundidade do cortador alinhado ao eixo global escolhido, com referência de posição na origem do alvo.

Ponto de apoio escolhe o centro da caixa delimitadora local ou o centro da sua face local inferior (-Z). Uma malha moldada não precisa ter uma face poligonal coincidente com esse apoio. Centro da seleção sempre centra a malha. Inverter direção vale para os alinhamentos orientados; centrar a seleção é somente uma translação.

Mover cortador por vértices: clique em um vértice do cortador e depois em um vértice do alvo; a malha inteira é transladada sem deformação.

## Ajustar somente um vértice

1. Clique em Ajustar só um vértice. O cortador entra em edição.
2. Clique no vértice do cortador a mover.
3. Clique no vértice de destino no alvo.

Apenas o ponto escolhido muda. Origem, transformação do objeto, outros vértices e malha do alvo são preservados. O cálculo respeita as transformações dos dois objetos. Escape ou botão direito cancela sem mover geometria, restaurando o objeto/modo de origem. Se o cortador compartilha dados de malha com outra cópia, a edição confirmada usa uma cópia independente.

O ajuste manual pode deformar as faces; confira o sólido e a prévia antes de confirmar o corte. Pinos no Corte Sólido continuam fora do escopo desta versão.
