# Sólido: novos controles da versão 0.8.13

## Folga entre as peças

Escolha o cortador, posicione-o sobre o alvo e ajuste a folga na seção Encaixes & Folgas. O valor é em milímetros por interface. Aplicar em Peça encolhe A; Cavidade amplia a abertura em B; Ambos divide a folga entre os dois. Isso também respeita Inverter Lados. As dimensões e a malha do cortador original são preservadas: usam-se operandos temporários com offset das faces em espaço global, em vez de escalar o objeto em torno de sua origem.

Offsets que colapsariam um detalhe ou não conseguiriam preservar as faces são recusados com uma mensagem; uma folga arbitrária não é válida em toda malha possível. Use um cortador simples ou reduza a folga nesse caso.

## Pinos e grade de posicionamento

Ative Encaixes, escolha a distribuição Manual e clique em Editar Posições dos Pinos. A extensão procura a maior face plana que realmente participa do contato entre as partes. Essa escolha fica estável durante a edição; a grade acompanha a orientação e a posição do cortador. A grade é apenas referência, sem obrigar encaixe dos pontos à malha de 5 mm.

Para escolher outra face: selecione o cortador, entre no modo Editar, selecione somente uma face e clique em Capturar Face de Encaixe. Volte ao modo Objeto e abra o editor de pinos. Escolher Face Automaticamente solicita uma nova escolha da maior face na próxima preparação. A face precisa efetivamente cortar a peça; uma face externa sem contato não oferece área para um encaixe.

Clique para adicionar, arraste para mover, use R para girar uma cápsula, X/Delete para remover e Confirmar Posições e Gerar Prévia para ver os pinos/cavidades. Folga de encaixe e folga entre as peças são configurações diferentes. Uma interface curva inteira não recebe uma grade plana fictícia: a operação trabalha com uma face plana de contato. Em sólidos facetados, essa face pode ser pequena demais para o pino solicitado.

Ao trocar de região/face ou de alvo, posições de outra interface não são reutilizadas. Mover o mesmo cortador mantém os UVs da face selecionada e revalida a área disponível. Ao sair do editor, atualize a prévia após alterar o cortador.

## Alinhar por vértices

Clique em Alinhar por Vértices. Clique primeiro em um vértice do cortador e depois em um vértice do alvo. O vértice sob o ponteiro recebe um ponto laranja. A ferramenta translada o cortador até os pontos coincidirem, preservando rotação e escala, inclusive quando existe um objeto pai. Esc cancela antes da translação. O picking usa os vértices da malha original; modificadores que criam novos vértices não são aplicados por essa ferramenta.

## Profundidade em Loop e Material

Nos casos com relevo e um contorno projetável simples, a base de apoio é colocada abaixo de todo o contorno e a profundidade é acrescentada abaixo desse apoio. Isso evita medir a profundidade a partir de um vértice alto do relevo. O resultado mantém uma base plana para os encaixes e uma cavidade complementar. Auto continua podendo escolher Destacar: escolha explicitamente Extrair com Profundidade para testar a extração com espessura adicional.

A extensão continua recusando paredes insuficientes, regiões degeneradas e booleanas que não produzam sólidos fechados. Contornos cuja projeção cruza a si mesma, regiões com sobreposição ao longo da direção de extração e sólidos abertos não têm garantia de extração. Confirme a prévia montada e explodida antes de criar as peças.
