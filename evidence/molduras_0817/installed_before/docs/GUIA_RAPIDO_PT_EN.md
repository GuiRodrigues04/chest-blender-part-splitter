# Part Splitter — guia rápido / quick start

## Português

### Instalação e primeiro corte

1. Guarde uma cópia do seu `.blend` antes de testar a candidata.
2. No Blender, abra **Edit > Preferences > Add-ons**, use **Install from Disk...** no menu e selecione o ZIP da versão. Ative Part Splitter se necessário.
3. Selecione a malha, abra a Sidebar com **N**, entre na aba **Chest** e defina o objeto alvo.
4. Para o primeiro teste, escolha **Plano**, posicione o plano e desative os encaixes. Gere a prévia.
5. Confira as partes montadas e explodidas, as dimensões e os indicadores de integridade. Mudar parâmetros exige atualizar a prévia.
6. Confirme o corte. **Próximo Alvo** escolhe entre continuar no corpo, continuar na peça extraída ou encerrar a operação.
7. Exporte para uma pasta escolhida. Abra a saída no seu fatiador e confira escala, posição montada e materiais antes de imprimir.
8. Use **Reverter último corte** para recuperar o estado anterior da operação.

### Escolher o método

| Método | Entrada | Conferência principal |
|---|---|---|
| Plano | Posição e orientação do plano | Lado extraído e posição da seção |
| Sólido | Cortador fechado, paramétrico ou objeto existente | Volume de interseção e cavidade |
| Loop | Contorno fechado de arestas ou perímetro de faces, mais região de referência | Região extraída, superfície de fechamento e profundidade |
| Material | Material e ilha correspondente | Região correta, fechamento e profundidade |

Loop: em Edit Mode, selecione um contorno fechado ou uma região de faces e capture a borda. Indique uma face dentro da região desejada quando solicitado. Confira o modo automático; selecione base ou profundidade conforme o resultado pretendido.

Material: escolha o material e a ilha correta. Uma pintura sobre a superfície não define por si só a espessura da peça. Confira a prévia do fechamento ou configure profundidade quando necessário.

Em regiões com depressões ou contornos não planares, escolha **Profundidade** e ajuste o valor desejado. O Loop automático também pode selecionar esse método quando o fechamento direto atravessaria a malha; ele usa o valor configurado. O modo **Na Base** de Material exige uma base planar. Em uma região irregular convertida para extração com apoio planar, a profundidade é medida desse apoio até o fundo plano; a espessura até cada saliência ou depressão da superfície varia. Confira essa referência na prévia.

Em uma estrutura saliente ou inclinada, **Profundidade** preserva a região escolhida inteira e cria a base de encaixe para dentro do corpo. O contorno indica a ligação com o corpo; as pontas podem sair da projeção desse contorno. **Corte Passante** permite atravessar a parede quando o valor de profundidade a alcança; marcar a opção com uma profundidade rasa continua produzindo uma cavidade rasa.

### Folgas e encaixes

- Folga de interface: separa superfícies de contato. **Peça**, **Cavidade** e **Ambos** definem qual lado perde material.
- Folga de fundo separada: quando disponível, controla o fundo independentemente das laterais.
- Folga por lado do pino: aumenta o alojamento em cada lado; o aumento total do diâmetro é duas vezes esse valor.
- Comece sem encaixes. Depois escolha tipo, dimensões e distribuição. No posicionamento manual, confirme os pontos sobre a área válida da interface.
- Faça uma amostra pequena com sua impressora e material para escolher a folga. A prévia mede geometria; o processo de impressão também afeta o ajuste.

### Relatar um problema

Inclua versão e hash do ZIP, `.blend` antes da operação, objeto/região, passos, parâmetros, resultado esperado e captura do resultado. Para cortes sucessivos, indique a sequência. Não substitua o arquivo original por uma cena já corrigida.

## English

### Installation and first cut

1. Keep a copy of your `.blend` before testing the candidate.
2. In Blender, open **Edit > Preferences > Add-ons**, choose **Install from Disk...** from the menu and select the versioned ZIP. Enable Part Splitter if needed.
3. Select the mesh, open the Sidebar with **N**, go to **Chest**, and set the target object.
4. For the first test, choose **Plane**, position the plane and disable connectors. Generate the preview.
5. Check the assembled and exploded parts, dimensions and geometry indicators. Regenerate the preview after changing parameters.
6. Confirm the cut. **Next Target** chooses whether to continue on the receiver, continue on the extracted part, or finish the operation.
7. Export to a chosen folder. Open the output in your slicer and check scale, assembly position and materials before printing.
8. Use **Revert last cut** to restore the previous operation state.

### Choosing a method

| Method | Input | Main check |
|---|---|---|
| Plane | Plane position and orientation | Extracted side and section position |
| Solid | Closed primitive or existing cutter | Intersection volume and cavity |
| Loop | Closed edge boundary or face perimeter, plus reference region | Extracted region, closing surface and depth |
| Material | Material and connected region | Correct region, closing surface and depth |

Loop: in Edit Mode, select a closed boundary or face region and capture its boundary. Specify a face inside the desired region when prompted. Check automatic detection; choose base or depth according to the intended result.

Material: choose the material and correct connected region. Painted faces alone do not specify part thickness. Inspect the closing preview or set extraction depth where required.

For depressions or nonplanar boundaries, choose **Depth** and set the desired value. Automatic Loop detection can also select this method when direct closing would cross the mesh; it uses the configured depth. Material **At Base** requires a planar base. For an irregular region converted to a planar support extraction, depth is measured from that support to the flat bottom; thickness up to each surface bump or depression varies. Check this reference in the preview.

For a protruding or inclined structure, **Depth** preserves the complete selected region and adds a mating base into the receiver. The boundary identifies its connection to the receiver; tips may extend outside that boundary’s projection. **Through-cut** allows the depth to cross the wall when the chosen value reaches it; enabling it at a shallow depth still produces a shallow cavity.

### Clearances and connectors

- Interface clearance separates contact surfaces. **Part**, **Cavity** and **Both** choose where material is removed.
- Separate bottom clearance, where available, controls the bottom independently of the side walls.
- Connector clearance per side enlarges the socket on each side; total diameter clearance is twice this value.
- Start without connectors, then choose their type, dimensions and distribution. In manual placement, confirm positions over valid contact areas.
- Print a small fit sample using your printer and material. Preview measurements describe geometry; the printing process also affects fit.

### Reporting a problem

Include version and ZIP hash, the `.blend` before the operation, object/region, steps, parameters, expected result and a screenshot of the actual result. For chained cuts, include the sequence. Preserve the original problem scene.
