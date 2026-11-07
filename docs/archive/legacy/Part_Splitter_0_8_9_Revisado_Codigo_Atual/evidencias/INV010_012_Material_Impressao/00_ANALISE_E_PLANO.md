# Part Splitter — INV-010 a INV-012, geometria e fluxo de impressão

Recebido em 12/10/2026, horário de São Paulo. Extensão mostrada no painel: 0.8.8. Os únicos códigos anexados continuam sendo 0.8.5 e 0.8.6.

## Comece aqui — instrução para Gemini / Antigravity

Investigue estes três casos no checkout da versão instalada. Abra cena/Testes_1.blend em processo de teste, sem executar scripts embutidos, e preserve esse original. Use as imagens e Evidencias_Malha.json. Reproduza folga zero antes de testar folga. As medições deste pacote foram feitas por leitura binária da malha salva, sem Blender; confirme-as pelo script conferir_faces_blender.py antes de implementar.

Não trate face fechada ou material uniforme como prova de imprimibilidade. Corrija a construção geométrica, mantenha a cavidade com material do receptor e implemente um fluxo explícito para continuar o corte no corpo remanescente. Não remapeie índices de faces da prévia para o alvo original por posição na lista.

Preserve as correções já presentes no checkout: as novas capturas mostram o botão Invert Explosion Direction; não afirmar que ele continua ausente nessa versão nem removê-lo ao portar referências antigas.

## Leitura do .blend e confiança

O arquivo foi descomprimido e suas estruturas SDNA, objetos, meshes, atributos e polígonos foram lidos sem executar Blender ou scripts da cena. Escala da cena: 1,0; atributos de posição são unidades Blender, convertidos aqui para mm por fator 1000.

A cena contém Cube, dois pares de prévias, uma guia planar, câmera, luz e dois snapshots. Não assumir que o estado salvo é exatamente cada captura, nem que os dois pares são objetos finais confirmados: os nomes salvos ainda são PREVIEW_A/B e PREVIEW_A/B.001.

Foram separados blocos de dados por proprietário e expandidos atributos constantes; contagens de faces/material devem corresponder aos tamanhos de cada mesh. Medidas de volume por leque de triângulos são aproximadas para polígonos não planares/côncavos, não substituem a tesselação nativa Blender. Não usar diferenças pequenas de volume como prova de perda/ganho geométrico.

| Mesh | Vértices | Faces | Faces material 0 / 1 | Faces sem área detectadas |
|---|---:|---:|---|---:|
| Cube | 1463 | 1423 | 1098 / 325 | 0 |
| Cube_part_a_preview | 76 | 86 | 0 / 86 | 0 |
| Cube_part_b_preview | 1505 | 1479 | 1098 / 381 | 0 |
| CHEST_SPLITTER_PREVIEW_B_part_a_preview | 110 | 128 | 0 / 128 | 0 |
| CHEST_SPLITTER_PREVIEW_B_part_b_preview | 1580 | 1572 | 1098 / 474 | 5 |

As cinco faces suspeitas do segundo receptor possuem todos os pontos com x=-0,07669300586 e y=0,08225734532 BU, variando apenas z. Portanto, são polígonos colineares, não apenas triângulos pequenos. Índices base zero: **66, 68, 69, 147, 150**. Há vértices com IDs diferentes e coordenadas iguais nesses polígonos. Coordenadas completas em Evidencias_Malha.json.

Nesse receptor, as 3142 arestas têm incidência 2. Isso não elimina faces degeneradas. Não foram verificadas auto-interseções, espessura global mínima, sobreposição espacial de faces ou trajetória contínua de montagem.

## INV-010 — artefatos e pontas persistem com folga zero

Imagens 01/02: Área 3 com 16 faces, profundidade 5 mm, folga zero, explosão 30 mm; Manter Origem versus Material da Peça Extraída. Resultado visual com reentrâncias, zonas triangulares e possíveis resíduos.

Não classificar cada triângulo desenhado como defeito: triangulação normal e pontas de espessura física são diferentes. Neste arquivo há prova independente de faces degeneradas em outro resultado salvo; ainda é necessário correlacionar cada artefato da captura com os objetos atuais.

Na 0.8.6, geometry_material.create_material_patch_prism_cutter translada as faces exatas do patch por um vetor único. Essa hipótese de construção continua relevante para regiões com relevo/dobras, mas o código 0.8.8 precisa ser lido.

### Investigar e corrigir

1. Conferir origem, região, índices estáveis e direção de extrusão; registrar cortador antes dos booleanos.
2. Medir degeneração antes/depois de cada etapa: patch, cortador, booleanos, materialização da interface, folga e publicação.
3. Inspecionar os cinco polígonos do receptor salvo: descobrir em qual etapa surgiram vértices coincidentes e polígonos colineares.
4. Acrescentar validação de área física, segmentos nulos, duplicação topológica/espacial e interseções quando houver método confiável. Separar tolerância numérica em mm de espessura mínima de impressão.
5. Não apenas apagar as cinco faces: isso pode abrir a malha. Reparar o domínio de construção ou retriangular/reestruturar a região com incidência e cobertura verificadas.
6. Não usar merge_by_distance global como correção automática. Qualquer união local precisa manter contorno, dimensões e interfaces; documentar tolerância.
7. Testar Manter Origem e Material da Peça Extraída com hashes/coordenadas/tesselação: a troca de política de cor deve manter o mesmo corte geométrico. Mudanças da malha exigem investigação, não são aceitas como efeito normal de recolorir.
8. Para pontas fiéis à extrusão em região dobrada, apresentar limitação e alternativa com cortador sólido, conforme INV-009; não modificar a silhueta exterior automaticamente.

### Aceites

- Cena salva: zero polígonos colineares/degenerados publicados no receptor ou inserto.
- Folga zero: resultado sem resíduos inesperados e materiais corretos.
- Receptor e inserto: seções e espessuras conferidas, não apenas volume/uma ilha.
- Política de material alternada: mesma geometria nominal.
- Erro de geometria: preserva original, snapshot e prévia válida.

## INV-011 — seleção de região após confirmar exige reselecionar alvo

Imagem 03: ativo/editado CHEST_SPLITTER_PREVIEW_B; painel ainda declara Alvo: Cube. Mensagem:

“Edit the target object to choose a region. Preview parts cannot define the selection.”

O bloqueio de faces da prévia é correto, pois índices do booleano não correspondem aos do alvo. A captura mostra uma prévia, não prova que o commit ocorreu naquele estado. O usuário relata essa dificuldade depois de confirmar; reproduzir a sequência completa.

Na 0.8.6, CHEST_OT_splitter_pick_material_region exige edit_object==target e um único objeto em Edit Mode. CHEST_OT_splitter_commit_parts renomeia/move A/B, mas não estabelece explicitamente próximo alvo/seleção para a etapa seguinte. São referências do fluxo antigo, não identificação final da causa no 0.8.8.

### Fluxo recomendado para impressão sequencial

Após confirmar, oferecer **Continuar no corpo remanescente**. Esse comando inicia nova sessão sobre B confirmado, ativa apenas esse objeto e permite selecionar a próxima região em Edit Mode.

Não retornar cegamente ao Cube original para um próximo corte cumulativo: isso pode gerar outra cópia completa e reintroduzir volumes já extraídos. “Editar original novamente” é uma ação distinta para refazer uma operação.

- Definir papéis sem depender do nome B ou da posição superior/inferior: inserto, receptor, sessão e origem.
- Conservar peças extraídas anteriores; transferir o papel de alvo para receptor confirmado em nova sessão.
- Criar snapshot do novo alvo para restauração local; manter cadeia de restauração com sessões anteriores.
- Recalcular regiões, materiais e topologia; não copiar IDs de faces/region_index da sessão anterior.
- Prévia: manter proteção e oferecer **Editar alvo** como ação visível.
- Commit: estabelecer objeto ativo e seleção coerentes; sair de multi-object Edit Mode de maneira controlada, sem descartar edições.
- Se auto-continuação for configurada, avisar claramente que o alvo passou ao corpo remanescente. Não trocar alvo implicitamente quando o usuário apenas clica numa face da prévia.

Aceite: extrair região 1 → confirmar → continuar no receptor → escolher região 2 → confirmar. Nenhuma necessidade de buscar manualmente o objeto correto; inserto 1 conservado; cavidade 1 não desaparece; restauração e exportação por sessão corretas.

## INV-012 — cavidade assume cor do inserto

Imagens 04/05: profundidade 5 mm, folga zero. Ao escolher Material da Peça Extraída, a cavidade do corpo fica roxa. Isso conflita com a finalidade declarada: imprimir insertos e bloco separadamente, evitando troca de filamento causada pela interface interna.

**Requisito:** faces novas da cavidade recebem material do corpo/receptor; faces novas do inserto recebem material do inserto. Essa regra vale também para paredes, fundo e interfaces criadas por folga.

Não obrigar ambos os operandos a compartilhar o mesmo material de interface. Não recolorir todo B para esconder a falha: outras regiões pintadas continuam sendo referências para futuras extrações.

### Política de materiais

| Faces | Regra |
|---|---|
| Exterior original preservado | Manter identidade de material de origem. |
| Interior novo do inserto | Material do inserto selecionado. |
| Fundo/paredes novos da cavidade | Material do receptor, branco neste exemplo. |
| Interfaces novas após folga | Regra da peça à qual pertencem. |
| Resultado final para impressão monocromática | Opção explícita por peça, independente da pintura de regiões ainda não extraídas. |

O material do receptor deve ser resolvido a partir do domínio exterior não extraído, ou de escolha explícita do usuário. Em regiões ambíguas/multimaterial, oferecer escolha em vez de assumir material 0, o slot ativo ou a maioria global.

“Manter Origem” pode preservar exteriores, mas a interface nova não existia antes: precisa de política definida. Preferir rótulos claros: **Material do inserto** e **Material da cavidade**. “Material da Peça Extraída” não deve pintar o receptor inteiro ou sua cavidade.

### Implementação

1. Rastrear identidade de materiais nos operandos, cortador e malha avaliada; remapear por identidade, não apenas índice.
2. Identificar faces novas versus superfícies exteriores preservadas de modo confiável. Não classificar faces somente pela cor.
3. Política independente em A/B. Aplicar depois do booleano e reaplicar somente nas superfícies novas de etapas posteriores.
4. Verificar o cortador, material_mode do Boolean e slots avaliados para evitar vazamento da cor de A para B.
5. Confirmar, exportar 3MF e reimportar: faces da cavidade com material receptor. STL não armazena material, mas peças/cavidades precisam ter geometria íntegra.
6. No fatiador, corpo final destinado a uma cor não deve conter solicitação adicional de filamento por material da cavidade. Outras regiões pintadas ainda não extraídas são um assunto separado; a UI deve deixar claro quando a preparação monocromática final está completa.

## Execução e entrega

Abra cópia da cena. Execute scripts/conferir_faces_blender.py e diagnosticar_selecao_blender.py. O segundo exige selecionar malhas e grava JSON ao lado do .blend; renomeie por estágio.

Corrija geometria primeiro; materiais e estado de seleção são tarefas separadas. Não substituir diagnóstico geométrico por pintura uniforme. Entregue causas por caso, scripts/testes executados, antes/depois e código/ZIP da versão corrigida.

Status: evidências visuais e leitura estática do arquivo; nenhuma geração de corte, simulação de montagem, exportação nativa ou impressão foi executada nesta análise.
