# Part Splitter — plano de implementação para Antigravity

Destinatário: agente de desenvolvimento no Antigravity (modelo escolhido pelo usuário: Gemini Flash 3.8 High).
Base analisada: `chest-blender-part-splitter.zip`, manifesto 0.7.0, enviado em 07/10/2026.
Escopo: corrigir encaixes, completar corte por contorno, melhorar interface e ajuda, preparar inglês/português e identidade independente do Chest.

## 1. Instrução inicial para o agente

Leia este documento inteiro e o código real antes de editar. Este é um plano técnico com achados de análise estática; não é um relatório de testes executados no Blender. Nesta análise não havia executável Blender. Reproduza primeiro os casos abaixo em sua instalação e só declare uma correção validada depois de executar os testes.

Implemente em etapas pequenas, começando pelo pipeline de cortes e pelos encaixes. Preserve as funções úteis existentes e os materiais. Não substitua a solução por um simples plano infinito no modo Loop. Não esconda ou remova os encaixes para fazer os erros desaparecerem: o usuário quer que funcionem, inclusive na saliência das imagens.

Use Part Splitter como nome provisório e Splitter como aba lateral. Não altere a extensão de placas do Chest nem o site. O ZIP analisado já possui pacote e registro independentes; compartilhar a aba Chest não demonstra dependência entre extensões.

Antes de modificar, identifique a versão atual do checkout. Os números de linha aqui se referem ao ZIP original e são apenas localizadores; prefira nomes das funções quando o código mudar. Não execute os scripts antigos em `scratch/patch_ops_loop.py` ou `scratch/patch_ui.py`: são artefatos históricos, não instruções atuais.

Entregue código, testes, ZIP instalável, instruções de uso e resumo das validações realmente executadas. Se não houver Blender, entregue a implementação com a limitação explícita e não invente resultados.

## 2. O que as imagens demonstram

- `image.png`: um corpo semelhante a um cubo subdividido, com uma saliência elevada e uma parede inclinada. O contorno de quatro vértices está na base da saliência. O usuário quer destacar a saliência por esse contorno e conseguir criar pino/cavidade naquela interface.
- `image(1).png`: painel estreito com textos truncados; mostra “Configuração de Loop (Fase 3A)”, “Face Semente: 19” e uma instrução sobre posicionar o plano mesmo estando no método Loop.
- `image(2).png`: encaixe Cápsula, largura 6 mm, comprimento lateral 14 mm, inserção 8 mm, chanfro 0,8 mm, folga por lado 0,15 mm, folga de fundo 0,5 mm, distribuição central e margem 4 mm. A interface usa “Superior/Inferior”, que não define corretamente o sentido de montagem em cortes arbitrários.

As dimensões exibidas são aproximadamente 2000 mm e o volume é de bilhões de mm³. Não inferir apenas disso um bug de unidades: um cubo de 2 unidades Blender, com escala de cena 1, tem 2000 mm. Explicar escala e testar unidades. Não alterar automaticamente o tamanho do modelo.

Há dois casos distintos que precisam funcionar:

1. Saliência com volume existente: separar as faces da saliência e fechar a interface pela base do contorno, sem retirar o resto da face superior do cubo.
2. Quadrado plano numa face subdividida: extrair um bloco com profundidade escolhida e deixar uma cavidade correspondente. A separação de faces seguida de tampa não cria esse volume.

## 3. Mapa do código e defeitos localizados

| Local no ZIP | Achado | Correção requerida |
|---|---|---|
| `src/operators.py`, `generate_preview`, 639–672 | Loop exporta coordenadas locais e calcula origem/normal locais; previews novos têm transformação identidade. | Padronizar coordenadas de geometria e interface; transformar uma única vez para mundo. |
| `src/geometry_connectors.py`, `compute_connector_layout`, 142–160 | Faz bisect na malha inteira do alvo. | Receber a interface real do corte; em Loop não usar seção global. |
| Mesmo arquivo, 166–177 | Se não encontra seção, inventa pino na origem do plano com limites fictícios. | Gerar erro explicativo; nunca fabricar uma posição considerada segura. |
| Mesmo arquivo, 179–269 | Bounding box UV e fórmulas de vãos não verificam o polígono real, furos, ilhas, largura menor ou espessura interna. `max(diameter_mm, ...)` mascara falta de espaço. | Validar perfil inteiro e volume disponível; retornar inviabilidade quando não cabe. |
| Mesmo arquivo, `validate_connectors`, 306–326 | Verifica somente distâncias entre centros, com aproximação do comprimento. | Validar bordas, perfis orientados, profundidade e parede remanescente. |
| `src/operators.py`, 746–755 | Normal do macho deriva da normal do plano e da escolha A/B. No loop a normal deriva da ordem das arestas, sem orientação em relação à região. | Orientar pela interface e pelas partes, independente da ordem do loop. |
| `src/operators.py`, 741–811 | Modo SOLID informa que encaixes não são suportados, mas continua no `try` que usa variáveis não inicializadas. | Bloquear explicitamente o recurso sem executar layout/booleans ou implementar interface suportada. |
| `src/operators.py`, 804–859 | Erros e avisos de encaixe são seguidos por `PREVIEW_VALID` e mensagem de sucesso. | Estados e fluxo transacionais; falha obrigatória não pode virar sucesso. |
| `src/operators.py`, `update_preview_positions`, 192–222 | Explosão do loop usa `settings.plane_normal`, sem persistir a interface calculada do loop. | Usar eixo da interface resolvida. |
| `src/geometry_loop.py`, `capture_edge_loop`, 79–106 | Desvio em unidades locais é exibido como mm; tolerância fixa local. | Calcular no mundo e converter pela escala da cena. |
| `src/geometry_loop.py`, `get_topology_signature`, 9–14; captura em operators 1089 | Assinatura só conta V/E/F, é salva, mas não é comparada no corte. | Conferir objeto e conectividade; invalidar referências após mudanças. |
| `src/geometry_loop.py`, 188–209; `geometry_plane.py`, `cap_open_cut_boundaries`, 55–79 | Fecha todas as bordas abertas, inclusive possíveis buracos anteriores ao corte. | Fechar apenas interfaces geradas; preservar furos e demais bordas. |
| `src/operators.py`, inversão 880–899 | Também regenera preview no estado COMMITTED. | Não criar automaticamente outro preview sobre peças finais já confirmadas. |
| `src/ui.py`, 169–170; `io_export.py`, `separate_object_by_material` | Método Material é placeholder; função existente só filtra faces, sem garantir sólidos. | Separar superfícies e dividir volumes devem ter contratos e mensagens diferentes. |
| `src/diagnostic.py`, `analyze_target_mesh` | Diagnóstico usa malha avaliada; cortes recebem `target.data`. Volume diagnóstico não transforma o BMesh para mundo. | Diagnosticar e cortar o mesmo snapshot, com a mesma transformação e unidades. |
| `src/operators.py`, alinhamento FACE, 461 | Normal de face transformada pela matriz direta, inadequada sob escala não uniforme. | Usar inversa transposta para normais ou recalcular da geometria mundial. |
| Manifesto / raiz / README | Versões 0.7.0 / 0.4.0 / 0.6.0 divergentes. | Uma versão coerente e compatibilidade efetivamente testada. |

### 3.1 Diagnóstico principal dos encaixes na saliência

O posicionamento está sendo calculado no lugar conceitualmente errado. A seção inteira do modelo no plano da base da saliência pode incluir a superfície do corpo grande. Mesmo que um ponto central pareça correto, o limite lateral passa a ser o do corpo, e não o da interface pequena. Isso permite encaixes largos demais, fora da saliência ou sem espessura suficiente.

Há ainda mistura local/mundo e sentido da normal não garantido. Portanto, corrigir só um sinal, aumentar a margem ou chamar `view_layer.update()` não resolve o conjunto.

### 3.2 O que ainda precisa ser verificado por teste

O sentido no modo PLANE depende do lado efetivamente preservado pelo `bisect_plane`. O código comenta que A fica no lado oposto da normal, mas isso deve ser confirmado numericamente. Não inverter a normal globalmente por tentativa e erro: fixe um contrato e teste A, B e `invert_sides`.

`apply_connectors_boolean()` cria booleans em ambas as peças antes de consolidar as malhas; testar atualização do depsgraph e a troca de datablocks durante a avaliação. A API não garante avaliação nova só por chamar `evaluated_get()`. Isso é um risco a investigar, não a causa comprovada única do defeito.

`create_capsule_2d_profile()` amostra sem incluir os extremos finais de cada semicírculo. Revisar as ligações tangentes e medir o perfil real: evitar que o estádio nominal tenha segmentos diagonais indevidos ou folga não uniforme. Preservar a convenção dimensional descrita adiante.

## 4. Contrato de geometria: implemente antes do layout

Defina um resultado de corte explícito, por dataclass ou estrutura equivalente, contendo:

```python
SplitResult:
    part_a_mesh
    part_b_mesh
    interface:
        origin_world
        normal_a_to_b_world
        axis_u_world
        axis_v_world
        outer_contours_uv
        hole_contours_uv
        interface_triangles_world
        is_planar
        deviation_mm
        source_mode
    diagnostics_before_connectors
```

Este formato é uma proposta de contrato, não um símbolo existente para importar. Introduza-o de forma pequena e adapte os chamadores. Para interfaces complexas, use coleção de regiões em vez de misturar ilhas num único contorno.

Regras obrigatórias:

- Malhas resultantes e dados de interface trabalham em mundo; previews possuem matriz identidade. Alternativa local é aceitável somente se todo o pipeline adotar consistentemente o mesmo contrato; a preferência aqui é mundo por já ser usado em PLANE/SOLID.
- Transformar as malhas de Loop uma vez. Não aplicar `matrix_world` de novo após o snapshot já transformado.
- `mm_per_bu = scene.unit_settings.scale_length * 1000`; comprimento em BU = mm / `mm_per_bu`, área e volume usam potência 2 e 3.
- Recalcular normais após transformação, tratar escala negativa e rejeitar matriz singular. Não inverter normal pela aparência de “superior/inferior”.
- `normal_a_to_b_world` aponta para fora da parte A, entrando em B, na interface escolhida. Macho em A usa essa normal; macho em B usa a oposta.
- PLANE: estabelecer a normal a partir das faces da tampa/semiespaços resultantes e verificar ocupação nos dois lados. LOOP: usar a tampa da região escolhida, com orientação exterior consistente. Não usar apenas a ordem do contorno ou centroides de objetos complexos.
- Falhar de modo explícito se não for possível determinar uma interface plana compartilhada e válida. Não usar normal Z ou origem zero como fallback “bem-sucedido”.
- Para Loop, os índices devem corresponder ao snapshot original. Modificadores que alteram topologia exigem uma cópia de trabalho avaliada e nova captura, ou bloqueio explicado. Não aplicar índices da malha original à malha avaliada.
- Sincronizar Edit Mesh antes de obter o snapshot, atualizar índices e lookup tables. Operadores devem conferir modo e objeto ativo e explicar pré-requisitos. Não acessar `obj.data` desatualizado silenciosamente.

## 5. Correção dos encaixes

### 5.1 Interface certa

Alterar `compute_connector_layout()` para trabalhar com `SplitResult.interface`. Em modo Loop, usar exatamente a tampa do contorno. Em modo Plano, usar a seção compartilhada real, incluindo furos e componentes. O bisect global pode auxiliar a construção da interface do plano, mas não pode substituir a interface de um loop local.

Na extração com profundidade, a interface inclui fundo e paredes laterais. Para esta versão, os encaixes automáticos devem usar uma região plana explícita do fundo; não fingir que toda a interface é um único plano. A normal de inserção deve acompanhar essa região. Suporte a encaixes automáticos em interfaces curvas fica bloqueado com explicação, preservando o corte sem encaixes.

### 5.2 Perfil e domínio admissível

Projetar a interface em UV. Conservar contornos externos e furos. Encontrar posições para as distribuições CENTER, LINEAR_2, LINEAR_3 e GRID_4 considerando:

1. Perfil completo da cavidade, maior que o macho devido à folga.
2. Margem entre a borda externa da cavidade e a borda da interface.
3. Parede mínima entre cavidades e nas laterais/fundo das peças.
4. Profundidade necessária em cada direção de montagem.
5. Regiões desconectadas, concavidades e furos.

O centro da bounding box pode cair fora de uma região côncava. Usar busca determinística de candidatos no domínio admissível, por exemplo triângulos internos e distâncias às bordas. O ranking pode privilegiar distância às bordas e simetria. Testar a distribuição inteira antes de aceitar; não reduzir quatro encaixes a um silenciosamente.

Para região retangular, cilindro central com diâmetro D e folga por lado c precisa de largura e altura >= D + 2c + 2m, onde m é a margem até a borda da cavidade. Cápsula orientada precisa de comprimento disponível >= L + 2c + 2m e largura >= D + 2c + 2m. Em contorno arbitrário, essas desigualdades são necessárias, mas não suficientes: testar o perfil no polígono real.

Não usar `max(diameter_mm, limite)` para forçar um tamanho mínimo quando não cabe. Se o máximo admissível é menor que o solicitado, mostrar o limite real e bloquear, ou oferecer botão “Usar tamanho sugerido”. Não mudar o parâmetro durante geração sem avisar e sem validar novamente.

Não adicionar dependências externas sem necessidade. Usar geometria disponível em Blender/mathutils e algoritmos pequenos com testes. Se uma biblioteca for indispensável, justificar e empacotar corretamente antes de depender dela.

### 5.3 Espessura e direção

Macho deve sobrepor uma pequena região dentro da sua peça de origem e projetar-se para a receptora. Cavidade deve abrir na interface da receptora e avançar no mesmo sentido do pino, com folga de fundo.

Validar o volume de suporte do macho e todo o envelope de cavidade. Um único raio no centro não garante que a cápsula cabe: amostrar/avaliar toda a seção e verificar se a cavidade atravessa superfície externa, furo ou parede fina. Usar BVH/raios como pré-teste e validação geométrica final. Não anunciar um “limite seguro” só por estimativa de bounding box.

### 5.4 Dimensões que não podem mudar

| Parâmetro | Macho | Cavidade |
|---|---|---|
| Cilindro D=6 mm; c=0,15 mm | D=6 mm | D=6,30 mm |
| Cápsula D=6 mm; L=14 mm; c=0,15 mm | largura 6; comprimento total 14 | largura 6,30; comprimento total 14,30 |
| Inserção 8 mm; folga de fundo 0,5 mm | projeção útil 8 | profundidade útil 8,5 |
| Chanfro 0,8 mm | ponta com chanfro limitado pelo perfil | não aplicar o chanfro do macho à cavidade automaticamente |

A sobreposição interna na base é detalhe de construção do booleano, não extensão da medida de inserção mostrada ao usuário. Especificar claramente a medida útil.

Para cápsula, centros dos semicírculos ficam separados por L−D. Acrescentar c ao raio da cavidade mantendo essa separação gera offset uniforme nominal. Não acrescentar a folga duas vezes ao comprimento dos centros.

### 5.5 Booleanos e falhas

- Validar layout antes de modificar peças.
- Criar e avaliar cópias temporárias; só substituir ambas as peças quando os dois resultados forem válidos.
- Atualizar view layer/depsgraph após criar cortadores/modificadores, antes de avaliar. Copiar malhas avaliadas e liberar todas com `to_mesh_clear()` em `finally`.
- Remover apenas os modificadores e objetos temporários criados pelo splitter. Não usar `obj.modifiers.clear()` em objetos do usuário.
- Limpar objetos, meshes e BMeshes em todos os caminhos de erro. Um erro na segunda peça não pode deixar a primeira parcialmente alterada.
- Conferir que união acrescentou pino conectado, diferença realmente abriu cavidade, volume é positivo e malhas são fechadas. Conferir materiais e índices após booleans.
- Sem encaixes, comparar soma dos volumes ao original. Com folgas nos encaixes, perda de volume é esperada: comparar ao resultado previsto das operações, e não exigir conservação exata do original.
- Testar colisão entre peças na posição montada: interseção volumétrica deve ser desprezível, dentro da tolerância declarada. O macho deve ocupar o espaço da cavidade e manter as folgas.

### 5.6 Estado e regeneração

Não continuar após falha de encaixe obrigatório e não sobrescrever erro com sucesso. Preservar preview anterior válido quando possível e apresentar “Alterações não aplicadas”; bloquear confirmação se ele já não corresponde aos parâmetros atuais.

Introduzir assinatura/revisão dos parâmetros do preview e indicar estado desatualizado. Mudar método, contorno, profundidade, orientação ou encaixes invalida a confirmação até atualizar. Não gerar booleans dentro de `draw()` ou em cada movimento de slider.

Proposta de estados: CONFIGURED, PREVIEW_STALE, PREVIEW_VALID, PREVIEW_INVALID, COMMITTED. Se usar estrutura equivalente, manter as mesmas garantias. Usar botão explícito Atualizar prévia; se houver atualização automática, debounce seguro fora de draw e sem recursão de callbacks.

Após COMMITTED, inversão de macho/fêmea não deve chamar `generate_preview()` automaticamente. Oferecer “Novo corte” ou fluxo explícito de edição de sessão. Preservar as peças finais existentes.

## 6. Corte por contorno: três escolhas, dois motores

Mostrar “Por contorno (loop)”, com comportamento Automático / Destacar parte / Extrair com profundidade.

### 6.1 Destacar parte — caso da imagem

Manter seleção de ciclo simples fechado e região indicada por uma face. Percorrer faces sem cruzar as arestas capturadas. Verificar que separa duas regiões válidas; rejeitar loop não separador numa alça com explicação.

Construir uma tampa compartilhada para o contorno, com a mesma triangulação nas duas peças e orientação oposta. Não gerar duas triangulações diferentes para um contorno não plano e alegar que as peças encaixam. Para esta entrega, contorno planar ou quase planar dentro de tolerância física documentada; contorno fora da tolerância deve ser diagnosticado e bloqueado se não houver implementação consistente de superfície compartilhada.

Não fechar buracos preexistentes. A região do ressalto pode ter paredes inclinadas: isso não impede que a base do contorno seja plana. A região não precisa ser toda plana para destacar uma saliência.

### 6.2 Extrair com profundidade — quadrado plano

Para contorno planar simples:

1. Encontrar plano e direção para dentro do sólido.
2. Projetar e triangular perfil, preservando concavidade.
3. Construir prisma fechado da superfície até a profundidade d, com pequena extensão externa para evitar contato coplanar degenerado.
4. Interseção modelo/prisma gera extraído; diferença gera restante, reaproveitando `geometry_solid.py` após adequar contratos.
5. Validar fechamento, volume, alinhamento e materiais.

Não substituir o perfil pela caixa delimitadora: isso extrairia áreas fora do contorno. A profundidade física é d, independente da extensão externa de robustez.

Se houver saliência dentro do contorno e for escolhida extração, o volume cortador deve cobrir toda a superfície externa da região, além da profundidade para dentro. Não cortar a saliência pela metade usando um prisma que começa exatamente no plano da base.

Detectar se d atravessa o objeto. Por padrão, bloquear com explicação e sugestão do limite; corte passante só com opção explícita. Superfície curva e espessura por normais locais exigem um algoritmo separado de offset com detecção de autointerseção; não prometer esse comportamento na primeira implementação.

### 6.3 Automático

Planicidade do contorno não decide o modo. Analisar desvio da região delimitada ao plano, variação das normais, volume do fechamento candidato e validade topológica.

- Região plana sem volume ao fechar: sugerir extração e exigir profundidade.
- Saliência fechável com volume positivo: sugerir destacar.
- Caso ambíguo: mostrar motivo e pedir escolha manual.

Não decidir por valor absoluto arbitrário de “curvatura grande”. Usar tolerância em mm e medida relativa ao tamanho da região, com parâmetros documentados e testes. Uma saliência baixa também pode ser intencional. O automático não deve determinar intenção estética nem profundidade desejada.

## 7. Interface didática e ajuda ao passar o mouse

É possível usar tooltip nativo em propriedades e operadores. Não inventar parâmetro `tooltip=` de `layout.label()` ou `layout.operator()`: ele não existe nessas chamadas.

Usar `description=` nas propriedades RNA, `bl_description` nos operadores e `Operator.description(context, properties)` para ajuda dinâmica. Para a bolinha de informação, criar botão de operador com `icon='INFO'`, `text=''`, `emboss=False`, propriedade identificadora de tópico e descrição dinâmica. Um ícone desenhado só como label não fornece essa descrição dinâmica.

Exemplo estrutural (completar registro e traduções, conferir API na versão mínima):

```python
class PARTSPLITTER_OT_help(bpy.types.Operator):
    bl_idname = 'part_splitter.help'
    bl_label = 'Help'
    topic: bpy.props.StringProperty(options={'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        return translated_help_for_topic(properties.topic)

    def execute(self, context):
        # Exibir a mesma ajuda num popup legível ao clicar.
        # Não modificar malha, seleção ou sessão; não criar etapa de Undo.
        return {'FINISHED'}

help_button = row.operator('part_splitter.help', text='', icon='INFO', emboss=False)
help_button.topic = 'loop_capture'
```

`translated_help_for_topic` é função nova a implementar. Tooltips dependem da configuração global do Blender; não ativar preferências do usuário à força. Clicar no ícone deve abrir ajuda mesmo se tooltips estiverem desativados. Não prometer tooltip customizado com HTML ou caixa arbitrária ao hover.

### 7.1 Ordem proposta

| Seção | Sempre visível | Recolhido ou contextual |
|---|---|---|
| 1. Modelo | Usar selecionado, nome do alvo, dimensões X/Y/Z em linhas curtas | Diagnóstico detalhado, escala, reparos |
| 2. Corte | Método e orientação/instrução específica | Opções avançadas do método |
| 3. Encaixes | Ativar, formato, parte com pino, medidas essenciais | Folgas, margem, distribuição, chanfro, paredes mínimas |
| 4. Prévia | Gerar/Atualizar, montado/separado, realçar A/B | Diagnóstico por peça e balanço físico |
| 5. Criar peças | Criar peças, Cancelar/Restaurar conforme estado | Novo corte após confirmação |
| 6. Exportar | Formato e exportação quando há peças válidas | Opções avançadas |

Encaixes antes do botão de geração, pois mudam o resultado. Evitar grandes listas expandidas para todas as opções; método pode ser dropdown curto, enquanto escolhas de dois itens cabem em botões lado a lado. Usar nomes curtos nas propriedades, ajuda longa no tooltip e popup.

Não criar formulário vertical com todos os diagnósticos antes de o usuário poder cortar. Na largura estreita, quebrar instruções em labels curtos; implementar quebra de texto considerando largura do painel se necessário. `layout.label` não faz quebra automática de parágrafos. Testar 260, 320 e 420 pixels e escala de UI 1 e 1,5.

Trocar “Fase 3A”, “Modo D”, “Face Semente: 19” por instruções de uso. Pode manter os índices no diagnóstico avançado. Não usar “Superior/Inferior” como identificação principal; usar A/B com realce e, em Loop, “região escolhida”/“restante”.

Garantir que realce A/B funciona no shading escolhido; `obj.color` sozinho pode não ser exibido. Se alterar configurações da viewport, preservar e restaurar as anteriores. Realce não deve substituir materiais reais na exportação.

### 7.2 Textos-base para copiar e traduzir

| Item | Português brasileiro | English |
|---|---|---|
| Escolher modelo | Selecione a malha que deseja dividir e clique em Usar selecionado. | Select the mesh you want to split, then click Use selected. |
| Corte plano | Posicione o plano. Ele divide todo o modelo nos dois lados do plano. | Position the plane. It splits the entire model on either side of the plane. |
| Capturar contorno | No Modo de Edição, selecione um contorno fechado de arestas e clique em Capturar contorno. | In Edit Mode, select a closed edge boundary and click Capture boundary. |
| Escolher região | Selecione uma face da região desejada e clique em Escolher região. O contorno limita essa seleção. | Select a face in the desired region and click Choose region. The boundary limits this selection. |
| Destacar parte | Separa uma saliência ou parte existente e fecha a abertura compartilhada pelo contorno. | Detaches an existing protrusion or part and closes the shared boundary opening. |
| Profundidade | Distância para dentro do modelo. A região extraída vira uma peça e deixa uma cavidade no restante. | Distance into the model. The extracted region becomes a part and leaves a recess in the remainder. |
| Parte com pino | Escolhe qual peça recebe o pino saliente. A outra recebe a cavidade correspondente. | Chooses which part receives the protruding pin. The other receives the matching socket. |
| Comprimento lateral | Comprimento total da cápsula sobre a interface. Não é a profundidade de inserção. | Total capsule length along the interface. This is not the insertion depth. |
| Inserção | Quanto o pino entra na peça receptora, medido a partir da interface. | How far the pin enters the receiving part, measured from the interface. |
| Folga por lado | Espaço em cada lado do pino. Com pino de 6 mm e folga de 0,15 mm, a cavidade tem 6,30 mm. | Clearance on each side of the pin. A 6 mm pin with 0.15 mm clearance needs a 6.30 mm socket. |
| Folga de fundo | Espaço adicional após a ponta do pino para evitar que ele encoste no fundo da cavidade. | Extra space beyond the pin tip to prevent it from touching the bottom of the socket. |
| Margem da borda | Distância mínima entre a cavidade e a borda da interface. | Minimum distance between the socket and the interface boundary. |
| Chanfro | Inclinação na ponta do pino para facilitar a montagem. | Bevel at the pin tip to make assembly easier. |
| Desatualizado | Os ajustes mudaram. Atualize a prévia antes de criar as peças. | Settings have changed. Update the preview before creating parts. |
| Falta de espaço | O encaixe não cabe na interface com a margem escolhida. Reduza as medidas ou a quantidade. | The connector does not fit the interface with the selected margin. Reduce its size or count. |
| Parede fina | A cavidade atravessaria a peça. Reduza a inserção ou escolha outra posição. | The socket would break through the part. Reduce insertion depth or choose another position. |

Presets de folga são sugestões, não garantia para todas as impressoras e materiais. Explicar isso no tooltip de folgas, sem adicionar avisos invasivos a cada operação.

## 8. Tradução e identidade

Criar catálogo de strings em inglês e tradução `pt_BR`, registrado e removido por `bpy.app.translations.register/unregister`. Acompanhar idioma e opções de tradução do Blender. Não criar seletor próprio redundante por padrão.

Traduzir template antes de interpolar valores. Mensagens persistidas na cena devem preferencialmente armazenar código + argumentos para renderizar no idioma atual, em vez de guardar apenas frase já traduzida. Tooltips usam tradução de dicas; UI usa tradução de interface; evitar dupla tradução.

Branding provisório:

- Manifesto: `id = 'part_splitter'`, nome Part Splitter.
- Sidebar: Splitter.
- Operadores: `part_splitter.*` e classes com prefixo PARTSPLITTER.
- Estado novo: `Scene.part_splitter`, com migração documentada do antigo `chest_splitter` quando recuperável.
- Coleções e objetos auxiliares com identidade da sessão, sem colidir com outra sessão ou apagar trabalho alheio.
- Nome do produto não se traduz; descrições e instruções se traduzem.

Renomear ids pode fazer Blender reconhecer uma extensão diferente. Testar instalação lado a lado e migração. Não manter dois registros simultâneos da mesma classe. Não prometer recuperação de PropertyGroup antigo que não está registrado; avaliar dados existentes num `.blend` real antes de definir a migração.

Atualizar documentação e versão. Manifesto atual declara mínimo 4.2; testar nessa versão ou elevar mínimo conscientemente. Excluir `scratch/`, caches e artefatos de desenvolvimento do ZIP comercial. Manter licença e revisar o arquivo LICENSE, que hoje contém um marcador de texto incompleto; não inventar nova licença neste trabalho.

## 9. Material e cortador sólido

Preservar corte sólido como recurso avançado útil, sem torná-lo requisito para usar os três métodos principais. Não habilitar encaixes automáticos em interface sólida arbitrária sem determinar uma região suportada.

Completar Material em etapa própria. Hoje `separate_object_by_material()` apenas remove faces que não pertencem ao material; pode gerar cascas abertas. Não rotular isso como sólidos prontos para impressão.

Para componentes fechados já definidos por material, separar e validar. Para fronteira pintada numa superfície contínua, permitir definir extração por profundidade quando a região for suportada, usando motor de extração. Se não houver regra geométrica suficiente, explicar a limitação e manter o botão correspondente desabilitado. Nunca fechar cada região indiscriminadamente e preencher furos desejados.

## 10. Testes de aceitação obrigatórios

Não basta verificar `FINISHED`, PREVIEW_VALID ou manifold isoladamente: um pino dentro da própria peça pode manter esses indicadores. Medir posição, sentido, tamanho, conectividade e cavidade real.

Fixtures em milímetros, convertidos pela escala da cena. Declarar tolerâncias nos testes: sugestão inicial de 0,02 mm para dimensões e 0,5% para volume de cortes sem encaixes. Volume de colisão deve usar tolerância proporcional à escala/volume das peças, declarada e justificada. Não aumentar tolerância só para fazer passar.

| ID | Caso | Verificações |
|---|---|---|
| P1 | Bloco 60×40×30, plano central Z | Duas peças fechadas, volumes positivos e soma conservada. |
| P2 | P1 com macho A, B; normal invertida; `invert_sides` | Pino sai da peça escolhida e entra na cavidade receptora em todas as combinações. |
| L1 | Base 60×60×20, saliência 24×18×15 com parede inclinada e contorno na base | Só saliência é destacada; interface real 24×18, não 60×60; restante preservado. |
| L2 | L1 com cilindro/cápsula, ambos lados | Pino e cavidade na interface local, sem atravessar paredes; sucesso medido. |
| L3 | L1, inverter ordem das arestas do loop | Mesmo resultado físico e orientação. |
| L4 | Cubo 40³, região plana 10×10, profundidade 3 | Bloco 10×10×3, volume 300 mm³; restante 63700 mm³; alinhamento montado correto. |
| L5 | Mesmo caso com extração > espessura | Bloqueio explicado ou opção passante explicitamente selecionada; nunca clamp silencioso. |
| G1 | Translação, rotação arbitrária, escala não uniforme e escala negativa | Cortes e encaixes continuam alinhados, dimensões físicas corretas e normais coerentes. |
| G2 | Escalas de cena 1, 0,01 e 0,001 para mesmas dimensões físicas | Dimensões, tolerâncias e profundidades iguais em mm. |
| C1 | Interface estreita demais para D=6, c=0,15, margem 4 | Rejeição real. Largura inferior a 14,30 mm não cabe mesmo que o eixo maior seja longo. |
| C2 | Cápsula 6×14, c=0,15, inserção 8 e fundo 0,5 | Macho 6×14; cavidade 6,30×14,30; profundidade útil 8,5; perfil e montagem corretos. |
| C3 | Região côncava, anel com furo, ilhas separadas | Centros e perfis não caem no vazio nem ultrapassam domínio; furos preservados. |
| C4 | 2/3/4 encaixes sem espaço | Rejeitar distribuição inteira ou oferecer mudança explícita; não reduzir silenciosamente. |
| C5 | Peça receptora com 4 mm, inserção 8 | Rejeição por espessura; não atravessar exterior. |
| E1 | Induzir erro na segunda operação booleana | Preview anterior preservado ou limpo integralmente, sem parcial; erro visível; confirmação bloqueada. |
| E2 | SOLID + connector_enabled por script | Sem variável não inicializada nem falso sucesso; suporte explícito/bloqueio coerente. |
| E3 | 20 regenerações e uma falha | Sem crescimento de objetos/meshes temporários, sem duplicação das peças. |
| T1 | Mudar conectividade mantendo V/E/F | Recaptura exigida; assinatura de contagens não basta. |
| T2 | Mover vértices após captura, sem mudar conectividade | Recalcular geometria e invalidar preview; seleção continua se ainda válida. |
| T3 | Loop aberto, ramificado, degenerado e não separador | Mensagem específica e nenhuma peça final incorreta. |
| S1 | Confirmar, inverter pino, começar novo corte, restaurar | Estado coerente; não duplicar final, não apagar peças de outra sessão. |
| M1 | Materiais reais diferentes nas peças e nas tampas | Slots e faces preservados no corte, boolean e exportação. |
| U1 | UI estreita, inglês/pt_BR, escala UI 1/1,5 | Instruções legíveis, nomes curtos, ajuda com hover e clique, sem jargão de fases. |
| U2 | Trocar ajustes após preview | Estado desatualizado e Criar peças desabilitado até atualização válida. |

L1/L2 devem reproduzir a imagem por uma fixture manifold contínua. Não use apenas dois cubos sobrepostos como se fossem uma única superfície ligada ao contorno: construir malha única ou realizar união e preparar as arestas adequadas.

No teste de cápsula e folgas, medir seção longe do chanfro e distinguir profundidade útil da sobreposição de base. Incluir assert de que existe mudança de volume e superfície de pino/cavidade; só manifold não prova operação aplicada.

Adaptar `tests/run_all_tests.py`: hoje o caminho do Blender é fixo para Windows. Aceitar `--blender` ou variável específica `BLENDER_BIN`, com fallback de PATH; rodar a suíte original e os novos testes. Atualizar imports/ids de testes quando renomear.

Comandos de referência, ajustados à instalação real:

```bash
blender --background --factory-startup --python-exit-code 1 --python tests/test_loop_connectors.py
blender --command extension validate .
blender --command extension build
```

Os nomes dos testes novos são propostas, não arquivos existentes. Antes de executar, criá-los. UI requer inspeção manual no Blender; teste headless não valida truncamento, tooltip nem destaque visual.

## 11. Ordem de implementação e critérios de passagem

1. Reproduzir falhas e criar fixtures que falham pelas causas apontadas. Documentar versão do Blender e mensagens atuais.
2. Definir snapshot, unidades e interface compartilhada; corrigir loop/mundo e orientação. Passar P1, L1, L3, G1 e G2.
3. Corrigir layout, espessura, booleanos transacionais e estados dos encaixes. Passar P2, L2, C1–C5, E1–E3. Não avançar ocultando erro.
4. Implementar extração plana com profundidade e decisão automática explicada. Passar L4/L5 e validações de região/topologia.
5. Reorganizar UI, ajuda e traduções sem alterar regras geométricas. Passar U1/U2; revisar textos com usuário iniciante em mente.
6. Separar branding e registro, testar coexistência/migração e atualizar documentação. Implementar método Material com contrato de sólidos em etapa própria.
7. Rodar regressão completa, validar pacote, instalar ZIP gerado num perfil limpo e testar fluxo final.

Cada etapa deve informar arquivos alterados, comportamento, testes executados e limites restantes. Se um teste original afirmava apenas sucesso/manifold, fortalecê-lo em vez de removê-lo para encobrir defeito.

## 12. Referências oficiais e como utilizá-las

Referências de API servem para confirmar mecanismos do Blender; o diagnóstico do bug vem do código deste ZIP. Verificar sempre a versão mínima suportada antes de copiar API de documentação current.

- [Operator: descrição, tooltip e poll](https://docs.blender.org/api/4.0/bpy.types.Operator.html): `bl_description`, `description(context, properties)` e `poll_message_set`. Conferir também na versão instalada.
- [UILayout](https://docs.blender.org/api/5.0/bpy.types.UILayout.html): `operator`, `icon`, `emboss`, `prop`, contextos de tradução e layouts. Não inventar argumento tooltip.
- [ID.evaluated_get](https://docs.blender.org/api/4.2/bpy.types.ID.html): retorna a última avaliação; não garante atualização do dependency graph.
- [Depsgraph](https://docs.blender.org/api/4.5/bpy.types.Depsgraph.html): avaliação e acesso a dados avaliados.
- [Application Translations](https://docs.blender.org/api/5.2/bpy.app.translations.html): catálogo, registro/desregistro, tradução de UI e dicas.
- [Guia oficial de tradução](https://developer.blender.org/docs/handbook/translating/developer_guide/): contextos, opções globais de tradução e templates antes de formatação.
- [Criar extensões no Blender 4.2](https://docs.blender.org/manual/en/4.2/advanced/extensions/getting_started.html): manifesto, empacotamento e validação.
- [BMesh Operations](https://docs.blender.org/api/current/bmesh.ops.html): confirmar semântica real de bisect, triangulação e fechamento antes de definir lados A/B.
- [BVHTree](https://docs.blender.org/api/current/mathutils.bvhtree.html): consultas espaciais úteis à espessura; não substituir por um raio central a validação do perfil completo.

## 13. Checklist de entrega

- [x] Encaixes corrigidos em plano e na saliência cercada pelo loop.
- [x] Interface pequena do loop usada no layout; nenhum fallback fictício.
- [x] Orientação independente da ordem das arestas e da altura no Z global.
- [x] Extração plana com profundidade cria duas peças fechadas e correspondentes.
- [x] Nenhuma falha obrigatória é convertida em mensagem de sucesso.
- [x] Preview e confirmação correspondem à revisão atual dos ajustes.
- [x] Materiais, original e peças de outras sessões preservados.
- [x] Tooltips nativos e ajuda por clique funcionam em inglês e pt_BR.
- [x] UI testada na largura das capturas, sem instrução errada sobre plano no método Loop.
- [x] Nome provisório e instalação independente, sem alterar o Chest de placas.
- [x] Resultados reais de testes, ZIP instalado em perfil limpo e instruções de uso.
- [x] Limites não implementados descritos honestamente; nenhuma promessa de curva/offset/Material sem testes.

Fim do prompt. Execute a implementação conforme as etapas, sem interromper para confirmar decisões rotineiras já definidas neste documento.
