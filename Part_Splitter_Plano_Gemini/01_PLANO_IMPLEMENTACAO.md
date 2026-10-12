# Plano de correção orientado por evidências

## 1. Base real e limites

Foram comparados os ZIPs 0.8.5 e 0.8.6 e lido o registro anterior com 15 capturas. As imagens foram inspecionadas visualmente. A 0.8.6 tem manifesto e código de entrada declarando essa versão; sua distribuição contém 20 arquivos e não inclui testes. A 0.8.5 inclui testes e documentos históricos.

O registro cita código 0.8.7 e modos presentes nas capturas que não existem na 0.8.6 anexada. Em particular, slice_mesh_by_material na 0.8.6 só separa componente fechado ou extrai superfície com prisma booleano. Não há caminho de destaque por base nesse módulo. INV-002 exige encontrar a implementação no checkout posterior ou criar um caminho equivalente, sem atribuir à 0.8.6 um traceback ausente.

Não existem cenas .blend originais neste pacote. Dimensões e índices das capturas são pistas, não geometria reconstruível com exatidão. O loop de 19 vértices não pode ser recriado somente por sua contagem. O exemplo de 32 vértices mostra a prévia removida; a película nesse caso é relato, não resultado visível comprovado.

## 2. Decisão de produto

**Preservar Extrair com Profundidade, restringindo seu uso aos casos geometricamente validados.** Não remover o algoritmo nem o caso positivo INV-003. Também não prometer suporte geral só por volume positivo e manifoldness.

| Tipo de entrada | Fluxo proposto |
|---|---|
| Componente fechado realmente válido | Separar diretamente, validando A e B. |
| Saliência com ligação/base inequívoca e fechamento suportado | Destacar pela base após estabilizar INV-002. |
| Patch capaz de gerar inserto sólido, incluindo relevo validado | Extrair com profundidade; mostrar o volume de extração e as limitações. |
| Patch dobrado, direção tangente, domínio ambíguo ou fechamento incompatível | Diagnóstico específico; operação experimental ou indisponível para esse caso. |
| Cunha fiel com zona fina | Mostrar risco e preservar corte nominal; ajustar somente por comando explícito. |

“Profundidade” é distância de construção/extrusão, não espessura mínima garantida. “Destacar” e “criar inserto” podem produzir volumes diferentes. Mostrar qual operação foi escolhida pelo AUTO e por quê.

No lançamento inicial, estabilizar destacar pela base e separação de componentes. Não ampliar agora para um offset geral de superfícies curvas. Ajuste de ponta, chanfro e espessamento localizado são evolução posterior; o diagnóstico e a proteção da entrada são escopo imediato.

## 3. Invariantes para todas as etapas

- Trabalhar com geometria em espaço de mundo e unidades físicas explícitas; manter a convenção já usada no projeto. Normais e áreas precisam corresponder ao mesmo espaço.
- Usar um snapshot consistente de malha, materiais, região, transformações e parâmetros. Sincronizar Edit Mode sem invalidar índices capturados. Modificadores não podem alterar a topologia do resultado sem remapeamento explícito.
- Publicar A/B e seus metadados apenas após validação final. Atualizar normal/origem do snapshot junto com o commit, nunca antes de uma possível falha.
- Falha conserva alvo, backup e prévia válida; limpa BMeshes, meshes avaliadas, objetos temporários e candidatos da tentativa.
- Separar incidência 1 (borda), 0 (aresta solta), >2 (ramificação) e orientação inválida. A contagem agregada não explica o defeito.
- Materiais das faces externas preservados conforme o modo escolhido; faces novas têm política documentada. Geometria não pode depender da cor exibida.
- Folga zero define o corte nominal. Folga positiva é operação adicional sobre a interface escolhida, com semântica clara. Não exigir conservação exata do volume quando há folga ou encaixes.
- Linha laranja do corte e seleção por região já úteis não devem regredir. Mudanças de UI acompanham a capacidade real do algoritmo.

## 4. Etapa 0 — identidade e reprodução

Execute scripts/identificar_fontes.py apontando ao addon real; registre SHA-256, versão manifestada, versão em execução, bpy.app.version_string e caminho __file__ do módulo. Não misture install de usuário com checkout.

Execute cada caso primeiro com encaixes desligados, folga zero, vista montada, original visível apenas quando necessário. Depois reintroduza visualização explodida, materiais e folga separadamente.

Salve a cena antes do corte. Para a cena real, registrar material, região, IDs das faces/vértices, coordenadas de contorno em mundo, seed, transformação, escala da cena, modificadores e configurações. Para imagens, manter vistas montada/explodida, wireframe e seção.

Saída da etapa: tabela de casos reproduzidos, casos aproximados sinteticamente e casos sem cena original. Não aguardar cena original para corrigir a inconsistência estática da explosão.

## 5. Etapa 1 — INV-004, explosão do Plano

**Achado confirmado na 0.8.6:** slice_mesh_by_plane mantém A no lado negativo da normal efetiva, usando clear_outer=True. CutInterface registra essa normal efetiva como A→B. compute_explosion_offsets move A para +normal e B para -normal, contrário ao afastamento nessa convenção. update_preview_positions usa settings.plane_normal atual e não invert_sides nem o snapshot da interface.

Correção:

1. Armazenar interface efetiva, modo de origem e matrizes montadas nos metadados da prévia validada. A prévia antiga não deve usar parâmetros novos de um corte ainda não regenerado.
2. Com N apontando de A para B, deslocar A=-N*d/2 e B=+N*d/2. d é afastamento relativo adicional, em mm. Validar convenção com pontos dos lados retidos, incluindo invert_sides e normal negada.
3. Adicionar “Inverter sentido da explosão” com fator s=+1/-1, independente de Inverter Lados e macho/fêmea. O automático deve afastar por padrão; o botão manual pode colocar as peças para dentro, por escolha visual.
4. Recalcular a posição sempre a partir das matrizes montadas: world_translation=M0.translation+offset. Não acumular offsets. Para objetos com parent, converter corretamente entre local e mundo.
5. Distância zero restaura matrizes exatas. A opção visual não integra a assinatura de geometria, não recorta novamente e não altera exportação.
6. Exportação, commit e overlays passam a usar o mesmo estado montado/snapshot. Auditar trechos que hoje zeram location: não generalizar essa suposição para objetos futuros com matriz montada diferente da identidade.

Aceite: sequência 0→39,3→0 mm, normal invertida e invert_sides; nenhum drift, métricas/materiais invariáveis, exportação montada. Afastamento incremental não garante liberar toda saliência para qualquer d; testar distância suficiente sem exigir que 1 mm revele uma peça profunda.

## 6. Etapa 2 — contrato e fechamento, INV-005

**Achado confirmado:** slice_mesh_by_loop coleta todas as arestas is_boundary e fecha A/B em chamadas independentes. Apesar do comentário, não filtra o contorno da operação. build_cut_interface recebe contorno, porém não recebe os triângulos efetivamente usados nas tampas. analyze_loop_region escolhe EXTRUDE/DETACH pela amplitude de altura (0,2 mm), sem provar a capacidade de fechamento.

O registro de 19 vértices, 14,76 mm de desvio e 19 arestas inválidas sugere ausência de tampa; identificar as arestas antes de afirmar a causa.

Implementação incremental:

1. Validar ciclo simples com graus 2, adjacência existente, índices válidos, seed e partição não vazia. Verificar snapshot/topologia novamente antes do corte.
2. Transportar identidade do perímetro para cópias A/B. Não localizar apenas por coordenada arredondada ou índice que muda após delete.
3. Construir uma única superfície de interface; usar a mesma triangulação e coordenadas para A/B, com orientações opostas. A planicidade é propriedade medida, não exigência universal de qualquer tampa.
4. Para contorno planar simples: triangulação restrita ao contorno, respeitando concavidades, segmentos subdivididos e buracos quando explicitamente suportados. Não convex hull. Preservar subdivisões da borda necessárias para incidência 2; remover ponto colinear sem remapear faces vizinhas cria T-junction.
5. Para não planar: primeira entrega pode recusar precocemente casos sem método validado, explicando como escolher contorno na ligação. Não prometer resolver qualquer loop torcido. Se implementar suporte, validar cobertura, orientabilidade e ausência de interseção com o exterior antes de publicar.
6. Preencher interface_triangles_world com a superfície real. UV pode continuar útil como referência, mas não substitui a geometria 3D no caso não planar. Encaixes nessa interface só podem ser habilitados com domínio real validado.
7. AUTO consulta capacidade do método: altura/relevo não bastam. Uma escolha incompatível deve aparecer no painel antes de “Gerar”.

Auditar cap_open_cut_boundaries do Plano: seu fallback também pode incluir bordas antigas fora do corte. Fazer a alteração somente com testes do Plano, sem usar essa etapa para reescrever o modo inteiro.

Aceite: loop real fechado e válido OU diagnóstico precoce específico; nenhum resultado aberto publicado. Caso sintético não planar suportado precisa de A/B complementares. Entrada com abertura fora do corte não pode ser reparada silenciosamente.

## 7. Etapa 3 — INV-002, tampa duplicada no destaque por Material

Na captura, Área 2 possui 13 faces e há erro faces.new(...): face already exists. Esse caminho não está implementado no geometry_material.py anexado. Localizar a função posterior pelo texto da mensagem e rastrear triangulação, domínio e mapa de vértices.

Reproduzir com folga zero antes dos 5 mm. Registrar cada triângulo proposto, sua chave de vértices, área, origem e face preexistente equivalente. Distinguir repetição topológica da sobreposição geométrica com vértices diferentes.

Uma face existente só pode ser reutilizada quando domínio, orientação e incidência são corretos. Inverter ordem dos mesmos vértices não evita duplicação. Capturar ValueError e continuar pode deixar o sólido sem tampa.

Se a região colorida contém saliência e extensão plana do corpo, definir explicitamente o domínio: não adicionar película só por igualdade de material. Mostrar faces conflitantes ou propor destaque somente do volume inequívoco. Não extrair arbitrariamente uma parte diferente da seleção sem mostrar essa decisão.

Reusar o contrato de interface compartilhada da Etapa 2. Criar somente o domínio aberto; validar cobertura sem lacunas, triângulos repetidos/degenerados e sobreposição. Cancelar se a região não possui base única suportada.

Aceite: destaque simples, base parcialmente triangulada, borda colinear, seleção mista e repetição após falha. A/B válidas; erro amigável para incompatibilidade; nenhum erro bruto de face duplicada.

## 8. Etapa 4 — INV-001 e INV-003, profundidade e materiais

### Geometria

**Achado confirmado na 0.8.6:** create_material_patch_prism_cutter duplica todas as faces do patch e move seus vértices em uma direção média única. Faces laterais quase paralelas a essa direção podem gerar volume local degenerado; patches dobrados podem auto-intersectar. Isso é uma fragilidade do método, não prova de causa exata nas capturas.

analyze_material_structure usa normal transformada pela inversa transposta, mas pesos f.calc_area() ainda locais. Sob escala não uniforme isso não equivale à média ponderada por área em mundo. Calcular normais e áreas após transformar um snapshot, ou usar áreas mundiais reais. Tratar reflexões e matrizes singulares explicitamente.

1. Validar o próprio cortador antes do booleano: volume com orientação, bordas, degeneração, duplicação, interseções e distribuição local da direção de extrusão.
2. Medir a projeção da direção nas normais das faces e destacar trechos tangentes ou dobrados. Não usar um único limiar angular para excluir o relevo positivo sem reproduzi-lo.
3. Preservar tesselação e concavidades úteis do patch. Não substituir pelo n-gon/convex hull do contorno, que pode ocupar áreas não selecionadas.
4. Para patches que não formam prisma simples: não reparar com offset generalizado. Recusar com explicação ou adotar método de inserto explicitamente validado para esse domínio.
5. Validar os booleanos A=S∩C e B=S\C no corte nominal, incluindo interseção entre A/B e cobertura do original. Soma de volumes igual não prova complementaridade; sobreposição e perda podem se cancelar.
6. Representar interface real, não marcar is_planar=True e desvio=0 por conveniência: na 0.8.6, o caminho Material faz isso mesmo para patches gerais.

### Materiais

O cortador da 0.8.6 cria faces sem atribuição explícita de material e sem slots. O booleano usa EXACT. Os resultados são carregados em BMesh e depois em candidate_mesh com slots do alvo. Esse caminho exige rastrear material_index e lista de slots no mesh avaliado, não apenas na entrada.

Registrar mapas índice→identidade de material em origem, cortador, meshes avaliadas e candidatos. Faces externas podem mudar índice por remapeamento sem mudar identidade; copiar índices cegamente é arriscado.

Classificar faces novas da interface e faces exteriores preservadas. Definir política de material da interface, mantendo exteriores de origem; se existir opção “Material da Peça Extraída”, documentar seu alcance. Testar também “Manter origem” para não esconder o problema.

Comparar wireframe, seção e polígonos reais dos quadrados. Se são faces coincidentes/z-fighting, tratar geometria; se apenas material_index incorreto, remapear corretamente. Mudança de cor sem mudança do mesh não confirma integridade.

### Preservar o caso positivo

INV-003: profundidade 10 mm, folga zero, 13 faces, resultado visual volumétrico e uma ilha em cada peça. Salvar fixture real assim que disponível. O segmento medido 0,01 m não é espessura mínima global. Diferença exibida 0,00% é arredondada. Não reduzir seu relevo a “região necessariamente plana”.

O caso deve continuar gerando inserto espesso correto. Se a construção deixa núcleo no corpo, informar isso como consequência do tipo de extração. Não prometer destacar toda a saliência nesse modo.

### Folga

Testar 0; 0,15; 0,30 mm e 5 mm quando viável. Não culpar a folga sem isolar a operação: INV-002 pode ocorrer antes dela. A 0.8.6 não implementa a mesma UI de folga das imagens.

Folga futura atua na interface conforme alvo selecionado; não escalar a peça inteira nem diminuir apenas a profundidade chamando isso de folga lateral. Medir diferença efetiva, limitar quando colapsa detalhes e revalidar receptor e inserto. Não exigir que 5 mm funcione em geometrias pequenas.

## 9. Etapa 5 — INV-006, espessura e cunhas

Reproduzir o loop planar de 32 vértices em DETACH e EXTRUDE; guardar resultados montados e seccionados. Identificar:

- Filme sem volume, duplicata, face interna ou resíduo do booleano: bloquear e corrigir.
- Parede volumétrica fina: avisar, medir nas zonas relevantes e conferir continuidade no fatiador.
- Cunha/ponta fiel ao corte: preservar nominal; sugerir contorno/base diferente ou ajuste explícito.

Não existe espessura mínima universal de impressão. Permitir limite definido pelo usuário/perfil. Uma ponta matemática vai a zero; reportar extensão/área afetada, posição e resolução da medida, sem marcar toda aresta externa como erro.

Diagnóstico por raios deve evitar autocontato imediato, testar múltiplas amostras e declarar pontos sem leitura. Uma amostra no centro do contorno não prova o mínimo global; centroides podem estar fora de regiões côncavas. Ausência de hit não significa 1000 mm de espessura disponível.

Mínimo amostrado deve ser chamado estimativa, com resolução. Medição exata de espessura e detecção robusta de auto-interseções podem exigir ferramenta própria; não simular sua existência só com BMesh.is_manifold.

UI imediata: destacar zona fina, mostrar superfície de corte e explicar o risco. Chanfro/recuo/espessamento só entra depois com preview e regeneração da interface complementar; não alterar silenciosamente encaixe ou silhueta.

## 10. Entrega e verificação

Executar regressões Plano/Loop/Material; editar em Object/Edit Mode; cena em scale_length 1 e 0,001; objetos rotacionados, transladados, escala não uniforme e refletida; índices e região mudando; mudanças de parâmetro com prévia antiga; erro injetado em cada estágio.

Exportar STL/3MF conforme suporte, reimportar e comparar dimensões, posições montadas e materiais onde o formato suporta. Conferir seção no fatiador sem tomar reparo automático como prova de correção. Não alegar encaixe físico validado sem impressão/montagem.

Preencher 03_TESTES_ACEITE.csv. Estados permitidos: NÃO EXECUTADO, PASSOU, FALHOU, BLOQUEADO SEM CENA, NÃO SUPORTADO COM DIAGNÓSTICO. Informar Blender, versão e evidência por teste.

Concluir somente com relatório por INV, testes realmente executados, ZIP instalável e limitações explícitas. Se a versão não puder suportar patches gerais/nonplanar, entregar suporte restrito honesto e conservar o código experimental sem o divulgar como capacidade garantida.
