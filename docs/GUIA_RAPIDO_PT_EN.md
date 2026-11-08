## Novidade 0.9.8: pinos centralizados e dimensões sugeridas

Reabra o Blender e gere novamente a prévia. Nos cortes curvos compatíveis, **1 Pino (Centro)** considera o contato completo; o editor manual usa a mesma área. Bordas internas da grade não limitam o pino. Margens externas, furos e paredes finas continuam sendo verificados.

**Sugerir dimensões** escolhe diâmetro e profundidade iniciais pela área e pelo material disponível nas duas peças. A ativação interativa dos pinos aplica a sugestão somente a parâmetros iniciais ainda não personalizados. Arquivos existentes, scripts e ajustes manuais conservam seus valores. O botão solicita uma nova sugestão explicitamente, inclusive depois de mudar o lado macho. Se faltar espaço ou profundidade para o mínimo, a extensão informa isso sem substituir seus valores. Confira a nova prévia antes de confirmar as peças.

English: Reopen Blender and regenerate the preview. Compatible curved cuts use the complete shared contact footprint for Center and Manual placement. Internal grid edges are not pin boundaries. Suggest dimensions calculates initial diameter and insertion depth from the actual cut solids. The interactive enable toggle only proposes untouched defaults; saved values, scripts and manual adjustments are preserved. Use the button to request a new suggestion after changing the cut or male side. External margins, holes and actual thin walls remain checked.

## Correção 0.8.32: cortes sucessivos e espessura do bigode

As informações de interfaces anteriores passam a acompanhar as faces durante os próximos cortes. Ao **Gerar / Atualizar prévia**, a extensão também tenta recuperar marcações já perdidas usando o histórico de operações e os backups desse próprio modelo. A recuperação altera somente atributos internos da malha, preservando geometria, materiais e seleção. Se o histórico necessário foi apagado, ela não inventa uma interface nem ignora a parede fina.

Após instalar, salve o trabalho e reabra o Blender para carregar a versão nova. Gere novamente a prévia do corte por **Profundidade**. No arquivo do gato testado, Material e Loop funcionaram com 1 e 5 mm, folga zero e sem pinos. O status de erro antigo só muda depois de atualizar a prévia. Salve uma cópia da cena para persistir as marcações recuperadas.

O fechamento direto **Pela Base** ainda pode recusar contornos não planos que façam a tampa atravessar a peça; a correção de espessura não remove essa proteção.

English: Interface metadata now survives successive cuts. Generate / Update Preview also recovers legacy marks from matching surfaces in this object's recorded cut ancestry and restore snapshots, without changing geometry, materials or selection. Missing history cannot authorize recovery. Reopen Blender after installation and update the Depth preview; save a scene copy to persist recovered tags. Actual thin walls and intersecting direct closures remain rejected.

## Correção 0.8.31: Região inteira

O corte pode sanear triângulos quase colineares herdados da preparação interna da malha. Esse saneamento atua apenas nos resultados candidatos, preserva o alvo e não modifica as tampas do corte. Atualize a prévia após carregar a nova versão. Se o reparo seguro não for possível, a extensão informa a degenerescência e mantém o alvo; defeitos reais não são ignorados.

English: Whole region can safely clean inherited near-collinear triangles on candidate results. Source geometry and closing caps remain unchanged. Update the preview after loading the new version. Failed repairs leave the source intact and show a dedicated geometry error; real defects are not ignored.

## Novidade 0.8.30: cortes por material e organização

Profundidade preserva relevos curvos e considera interfaces de cortes anteriores ao medir a parede. Atualize a prévia para refazer um corte que falhava na versão anterior. Continua necessário conferir o resultado e a orientação de montagem no fatiador.

A coleção **Parts** contém os resultados atuais. **Histórico de cortes** guarda resultados intermediários substituídos por outro corte. Eles ficam ocultos, mas o olho do Outliner permite exibi-los para inspeção; oculte-os novamente para evitar sobreposição. **Backups** continua reservado à restauração interna. Reverter corte restaura o resultado anterior na coleção Parts. Nenhum histórico é apagado automaticamente.

Novas peças usam nomes como `Gato — Peça 001` e `Gato — Restante 001`. Renomeie cada peça para indicar sua função, como nariz ou olho preto. A numeração evita o acúmulo de sufixos; nomes existentes permanecem intactos. A migração da organização acontece em memória ao abrir a cena; salve uma cópia se quiser preservar essa organização no arquivo.

English: Depth extraction preserves curved reliefs and distinguishes prior cut interfaces from outer walls. Update the preview after upgrading. Parts holds current results; Histórico de cortes holds hidden intermediate results, still available for reversion. The Outliner eye can show these objects for inspection. Backups remains internal restore data. History is never deleted automatically. New results have short numbered names; rename them to describe their purpose. Existing names are preserved. Reopen Blender after installation to load the new code.

## Novidade 0.8.27: material da peça inteira

Em **Material → Região inteira**, use **Material da Interface → Material da Peça Extraída** para deixar toda a peça extraída com o material escolhido, incluindo as faces internas e os encaixes. É a opção padrão. **Manter Origem** preserva a atribuição anterior. Atualize a prévia depois de alterar a opção. As cores do corpo restante não são substituídas.

In **Material → Whole region**, choose **Interface Material → Extracted Part Material** to color the entire extracted piece, including internal faces and connectors, with the selected material. This is the default. Keep Source preserves the previous assignment. Update the preview after changing the option. Remaining-body materials are not replaced.

## Novidade 0.8.26: separar regiões inteiras e preparar encaixes

**Material:** escolha a cor/ilha da peça, selecione **Região inteira** em Tipo de corte e gere a prévia.

**Edge Loop, sem pintar:** escolha **Região inteira**, clique em **Editar alvo**, selecione as faces da peça em seleção de faces e clique em **Capturar seleção**. Gere a prévia. Também aceita um contorno fechado em seleção de arestas; se houver dúvida sobre o lado, selecione as faces.

Para pinos, clique em **Preparar área plana**. A extensão junta os triângulos do contato e prepara uma área plana real nas duas peças, preservando o exterior. Ative os encaixes, ajuste diâmetro, comprimento, distribuição e folgas e atualize a prévia. Os pinos usam uma única direção perpendicular ao apoio. Outros contatos ficam sem pinos. A folga entre peças é independente da folga lateral/fundo dos pinos.

Se não houver contato adequado ou a montagem colidir, escolha outra área ou divida a peça de outra forma. Há uma verificação de travas locais e posições amostradas da trajetória, não uma garantia contínua de montagem. Faça um teste físico de encaixe. O modo Sólido permanece disponível para cortes auxiliares, sem pinos ou criação de cascas no painel.

**English:** Material → Whole region separates the selected color island. Edge Loop → Whole region captures selected faces or a closed contour without recoloring. Generate the preview, prepare a planar contact, enable pins, adjust dimensions/clearances, and update. Both parts receive complementary flat seats; all pins share one insertion direction. Internal contact clearance is separate from pin clearance. Local undercut and sampled withdrawal checks may reject a contact, but are not a continuous-motion guarantee. Solid Cutter remains an auxiliary cut without pins.

# Part Splitter — guia rápido / quick start

## Português

### Localizar falhas para correção manual (0.8.20)

No painel do objeto alvo, clique **Localizar problemas** para selecionar as regiões suspeitas no Modo de Edição. **Próximo problema** percorre uma região por vez e aproxima a vista. O raio X é habilitado para mostrar elementos ocultos atrás da superfície; use **Alt+Z** para desligá-lo quando desejar. Corrija a geometria com as ferramentas do Blender e clique novamente em Localizar problemas para reavaliar. Nenhuma geometria é reparada ou removida por esses botões. Problemas gerados somente por modificadores exigem inspeção do resultado do modificador.

### Locate mesh defects (0.8.20)

Click **Locate problems** in the target panel to select suspect regions in Edit Mode. **Next problem** frames one region at a time. X-ray is enabled to reveal elements behind surfaces; **Alt+Z** toggles it off. Edit the geometry and scan again. These buttons do not repair or remove geometry. Modifier-only defects require inspection of the evaluated modifier output.

### Instalação e primeiro corte

1. Guarde uma cópia do seu `.blend` antes de testar a candidata.
2. No Blender, abra **Edit > Preferences > Add-ons**, use **Install from Disk...** no menu e selecione o ZIP da versão. Ative Part Splitter se necessário.
3. Selecione a malha, abra a Sidebar com **N**, entre na aba **Chest** e defina o objeto alvo.
4. Para o primeiro teste, escolha **Plano**, posicione o plano e desative os encaixes. Gere a prévia.
5. Confira as partes montadas e explodidas, as dimensões e os indicadores de integridade. Mudar parâmetros exige atualizar a prévia.
6. Confirme o corte. **Próximo Alvo** escolhe entre continuar no corpo, continuar na peça extraída ou encerrar a operação.
7. Exporte as peças pelos recursos do Blender para uma pasta escolhida (Slicer Export integrado está oculto). Abra a saída no seu fatiador e confira escala, posição montada e materiais antes de imprimir.
8. Use **Reverter último corte** para recuperar o estado anterior da operação.

### Plano com área limitada (0.8.19)

No modo Plano, escolha **Área limitada**. Use **Largura (mm)** e **Altura (mm)**, ou escale o guia, para enquadrar toda a seção do membro desejado. O preenchimento e a linha de corte obedecem ao retângulo do guia. Se outras regiões atravessarem o mesmo plano fora do retângulo, elas permanecem unidas.

O retângulo deve conter o contorno inteiro da seção. Se cobrir só parte da seção ou não conseguir separar uma peça, amplie ou reposicione o guia. O corte é recusado e a prévia anterior é preservada. Os pinos consideram somente as seções aceitas. **Plano completo** mantém o corte que atravessa todo o modelo.

### Limited-area plane (0.8.19)

In Plane mode, choose **Limited area**. Set **Width (mm)** and **Height (mm)**, or scale the guide, to enclose the complete section of the desired limb. The fill and intersection line follow the guide rectangle. Other sections outside the rectangle remain connected. Partial sections are rejected; enlarge or reposition the guide. Pins use only the accepted sections. **Full plane** keeps the existing full-model cut.

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

Escolha **Impressão FDM**, **Sem folgas** ou **Personalizado** em Padrão de Folgas. FDM usa 0,10 mm na interface e fundo das peças, 0,15 mm por lado do pino e 0,20 mm no fundo do furo. Sem folgas zera todos esses valores. Editar qualquer folga ativa Personalizado. Os pinos continuam com tamanho e posicionamento escolhidos pelo usuário.

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

# Como usar o corte por Loop — Splitter 0.8.28

O Loop separa uma região da malha sem precisar mudar sua cor. Você indica a superfície desejada pelas faces ou por um contorno fechado de arestas. O painel segue sempre a mesma ordem: **tipo de corte → seleção/captura → ajustes → prévia → encaixes → confirmação**.

## Qual tipo escolher?

| Tipo | Quando usar | O que precisa informar |
|---|---|---|
| Região inteira | Tirar uma pata ou outra peça completa, inclusive com contatos em direções diferentes | As faces da peça ou um contorno fechado |
| Pela Base | Destacar uma saliência pela ligação dela com o corpo | O contorno e uma face do lado desejado |
| Profundidade | Retirar uma região superficial com espessura controlada para dentro do modelo | O contorno, a região e a profundidade em milímetros |
| Automático | Deixar a extensão decidir entre Pela Base e Profundidade | O contorno e a região; confira a decisão antes de confirmar |

Automático não escolhe Região inteira. Para separar a pata inteira como no gato, comece explicitamente por **Região inteira**.

## Exemplo 1 — separar a pata inteira por faces

1. Defina o gato como alvo. Escolha **Edge Loop → Região inteira**.
2. Clique **Editar Alvo**. No modo de edição, ative a seleção de faces, não a de vértices ou arestas.
3. Selecione todas as faces externas da pata, incluindo a parte que fica escondida atrás. Gire a vista para conferir a seleção. Não selecione o gato inteiro.
4. Clique **Capturar seleção**. A extensão registra as faces, sai da edição e inicia a separação com folga entre peças de 0 mm.
5. Clique **Gerar / Atualizar prévia**, no painel de prévia mais abaixo. Confira as peças montadas e explodidas.
6. Se quiser pinos, clique **Preparar área plana** no painel de encaixes. A superfície de apoio aparece destacada.
7. Ative os encaixes, escolha diâmetro, comprimento, distribuição e folgas. Gere a prévia novamente.
8. Confira o resultado e clique **Confirmar corte**.

Esse modo fecha a região inteira. Não há profundidade para configurar. O apoio dos pinos é preparado nas faces internas; os pinos usam uma direção comum de montagem. Se o contato travar ou não permitir preparação, será necessário escolher outro contato ou outra divisão.

## Exemplo 2 — capturar apenas o contorno

Um contorno é uma linha fechada de arestas na própria malha, como um anel ao redor do braço. Não precisa ser um círculo e não é um objeto desenhado separado.

Em **Região inteira**, use Editar Alvo, ative seleção de arestas, selecione somente o contorno e clique Capturar seleção. O contorno precisa dividir a superfície em duas regiões; a extensão tenta escolher a menor quando não há referência anterior. Se houver ambiguidade, prefira selecionar diretamente todas as faces da peça, como no exemplo 1. Não misture várias linhas soltas ou bifurcações.

Nos modos **Pela Base, Profundidade e Automático**, o fluxo é:

1. Em Editar Alvo, selecione o contorno em seleção de arestas e clique **Capturar Contorno**. Se preferir selecionar faces, use **Capturar das Faces**, que registra o perímetro da seleção.
2. No alvo em edição, deixe selecionada somente **uma face dentro do lado que deseja retirar**, e clique **Escolher Região**. Essa face serve de referência; não significa que só ela será extraída.
3. Confira os ajustes do tipo escolhido e gere a prévia.

**Capturar seleção**, no modo Região inteira, e **Capturar Contorno / Capturar das Faces**, nos outros modos, registram entradas diferentes. Depois de trocar entre esses caminhos, refaça a captura correspondente.

## Exemplo 3 — retirar uma região com profundidade

Escolha **Profundidade**, capture o contorno e indique a região como no exemplo 2. Ajuste **Profundidade (mm)** para definir quanto a extração entra no corpo. Gere a prévia e veja a espessura real e a cavidade receptora.

**Corte Passante** permite atravessar a parede se a profundidade configurada a alcançar. A opção sozinha não aumenta a profundidade e não garante que o corte atravessará tudo.

Em **Pela Base**, o corte destaca a saliência pela base identificada. **Adicionar base para encaixe** acrescenta uma base retirada do corpo receptor; ative apenas quando quiser essa extensão interna e confira a profundidade da base na prévia.

Em **Automático**, confira a indicação Auto Detectado. Se ele usar Profundidade, o valor em milímetros continua relevante. Se a decisão não corresponder ao resultado desejado, escolha Pela Base ou Profundidade explicitamente.

## Se o resultado não for o esperado

- Separou o lado errado: nos modos de contorno, confira a face indicada em Escolher Região; em Região inteira, selecione diretamente as faces da peça.
- Captura recusada: confira se está editando o alvo correto, se está no tipo de seleção apropriado e se o contorno está fechado, sem bifurcações.
- A seleção mudou depois da captura: capture novamente. Depois de alterar a malha, não reutilize a captura antiga.
- Está vendo o original sobre a prévia: use os comandos da extensão. Editar Alvo oculta as prévias para permitir selecionar o original; depois, gere a prévia novamente.
- Cores diferentes nas faces internas: Loop preserva materiais e não identifica uma cor única para a peça. Para separar pela cor e uniformizar a peça, use Material → Região inteira → Material da Interface → Material da Peça Extraída.
- O apoio ou pino não cabe: escolha outro contato, reduza os pinos ou refaça a divisão. As folgas dos pinos e a folga entre as peças são controles independentes. Confira a montagem e faça um teste de impressão.

Na 0.8.28, os quatro tipos permanecem na mesma ordem e no mesmo lugar. Somente os controles necessários ao tipo escolhido mudam abaixo deles. Os algoritmos de corte, encaixes e folgas permanecem os mesmos da 0.8.27.
