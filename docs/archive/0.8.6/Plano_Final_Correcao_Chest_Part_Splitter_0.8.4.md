# Chest Part Splitter 0.8.4 — plano final de correção antes da venda

Documento de implementação para Antigravity • 9 de outubro de 2026

## Instrução principal para o agente implementador

Trabalhe no projeto Chest Part Splitter tomando o ZIP `chest_part_splitter-0.8.4.zip` como referência. Corrija os problemas abaixo, escreva testes de regressão focados nos fluxos afetados e entregue uma versão candidata verificável. Não acrescente funcionalidades novas neste trabalho. Preserve os cortes por plano, contorno, sólido e material, a folga física em milímetros e os modelos originais do usuário.

Antes de editar, leia as funções citadas e confirme se o código do repositório corresponde ao ZIP. Se o repositório já tiver correções, verifique-as com os testes descritos em vez de substituí-las. As linhas abaixo são referências da 0.8.4 e podem mudar; use os nomes das funções como referência principal.

Esta análise foi feita por leitura do código e compilação sintática dos arquivos Python. Não foi executada no Blender. Portanto, diferencie defeitos observáveis no código, consequências esperadas e resultados realmente reproduzidos. Não declare a extensão pronta para venda apenas porque a sintaxe passou ou porque o changelog menciona testes antigos.

## 1. Ordem de execução

| Ordem | Correção | Criticidade |
|---|---|---|
| 1 | Separar a cópia de trabalho dos objetos descartáveis de prévia | Crítica |
| 2 | Corrigir término do operador e conversão física dos arquivos exportados | Alta |
| 3 | Isolar sessões e exportar somente as peças do corte escolhido | Alta |
| 4 | Invalidar prévias quando a cena relevante mudar | Alta |
| 5 | Exigir resultados geométricos válidos antes de confirmar/exportar | Alta |
| 6 | Corrigir idioma da ajuda e documentação de entrega | Média |
| 7 | Executar regressões no Blender e conferir arquivos em um fatiador | Obrigatória |

Implemente por etapas pequenas. Não reescreva todo o motor geométrico para resolver um erro de organização de coleções ou de exportação.

## 2. Cópia de trabalho apagada pela limpeza da prévia

**Referências:** `src/operators.py`: `cleanup_collection_objects()` (71–79), `CHEST_OT_splitter_create_work_copy` (328–378), `CHEST_OT_splitter_generate_preview` (549–966).

### Evidência e reprodução

`create_work_copy.execute()` vincula `new_obj` à coleção `COLLECTION_PREVIEWS_NAME` e define esse objeto como `settings.target_object`. `generate_preview.execute()` armazena o alvo e imediatamente limpa todos os objetos dessa mesma coleção. A limpeza chama `bpy.data.objects.remove(..., do_unlink=True)`; portanto, remove a própria cópia usada como alvo. Uma referência Python não impede a remoção do datablock pelo Blender.

Reprodução mínima: selecionar uma malha → definir alvo → criar cópia de trabalho → gerar prévia. A operação deve cortar a cópia; atualmente o fluxo de limpeza a inclui entre os objetos apagados.

### Correção exigida

- Coloque cópias de trabalho em uma coleção própria, distinta de prévias e guias, ou implemente uma separação equivalente de propriedade e ciclo de vida.
- Identifique objetos temporários por metadados explícitos de proprietário, função e sessão. Não use somente nomes de objetos para decidir o que apagar.
- A limpeza da prévia deve remover apenas resultados temporários daquela sessão. Nunca remova o alvo, uma cópia de trabalho ou objetos do usuário.
- Trate cenas antigas da 0.8.4 nas quais a cópia já está na coleção de prévias: exclua o alvo da limpeza e migre seu vínculo com segurança.
- Restauração e troca de alvo devem manter acesso ao original. Preserve o estado anterior de visibilidade quando necessário, em vez de tornar todos os objetos visíveis indiscriminadamente.
- Se uma atualização de prévia falhar, deixe o alvo acessível e a sessão inválida; não deixe uma cena vazia ou referências removidas.

### Aceitação

Criar cópia e gerar/atualizar prévia três vezes sem perder alvo ou original; restaurar, desfazer e refazer sem referências inválidas. Repetir com uma cópia salva pela versão antiga na coleção de prévias. Objetos não pertencentes à sessão devem sobreviver às limpezas.

## 3. Exportação: retorno do operador, unidades e estado da cena

**Referências:** `src/operators.py`: `CHEST_OT_splitter_export_parts` (1328–1425); `src/io_export.py`: `export_objects_to_stl_by_material()` (237–303) e `build_3mf_xml()` (48–142); `src/diagnostic.py`: `get_scene_scale_to_mm()`.

### 3.1. Falta de retorno no sucesso

O método `execute()` do operador de exportação só tem retornos `{'CANCELLED'}`. Quando a gravação dá certo, chega ao fim retornando `None`, que não é um resultado válido de operador do Blender.

Adicione `return {'FINISHED'}` após uma exportação realmente bem-sucedida. Formato desconhecido, cancelamento ou falha devem ter caminhos explícitos. Verifique também o retorno dos operadores nativos de exportação: ausência de exceção não deve ser confundida automaticamente com sucesso se o operador retornar cancelamento.

### 3.2. Conversão física inconsistente entre STL e 3MF

O 3MF multiplica as coordenadas por `unit_scale`, convertido de `scene.unit_settings.scale_length * 1000`. Já o STL por material recebe esse fator, mas não o usa; chama o exportador com `global_scale=1.0`. O STL por peça também não passa a conversão física. O exportador nativo moderno tem `global_scale=1.0` e `use_scene_unit=False` por padrão.

Defina um contrato único: **coordenadas numéricas do STL em milímetros**, como o 3MF gerado pela extensão. Para o exportador moderno, a solução esperada é usar o fator em `global_scale` e manter `use_scene_unit=False`, após confirmar o comportamento na versão suportada. Não aplique a escala da cena duas vezes. Revise o fallback antigo conforme sua API.

Exemplo: com `scale_length=1`, uma peça de 0,04 unidade corresponde a 40 mm. O STL atual pode gravar 0,04, que um fatiador configurado em milímetros lê como 0,04 mm. Com `scale_length=0.001`, 40 unidades correspondem a 40 mm. Ambos os casos precisam exportar uma largura de 40 mm.

OBJ não declara uma unidade física universal: defina e documente a convenção de exportação da extensão, mantendo coerência com os demais formatos quando importado conforme essa convenção.

Não transforme permanentemente a malha do usuário para corrigir unidades. Use parâmetros do exportador ou snapshots temporários controlados.

### 3.3. Preservação de contexto e destino

As rotinas alteram seleção e objeto ativo. Preserve/restaure o contexto em `finally`, inclusive em falhas. Garanta o modo de operação adequado e mensagens claras quando o contexto não permitir exportar.

Remova o destino padrão específico de desenvolvimento `~\OneDrive\Desktop\Modelos 3D IA\Placas` e o fallback com caminho Windows literal. Para uma cena não salva e sem diretório escolhido, solicite um destino por seletor de arquivos ou mensagem orientativa. Cenas salvas podem usar seu diretório se essa convenção estiver clara.

Não sobrescreva arquivos existentes silenciosamente: use a confirmação do seletor ou uma regra explícita de substituição. Para o 3MF, prefira substituição atômica com `os.replace` após gravar o temporário, evitando remover o arquivo anterior antes de ter o novo pronto.

### 3.4. XML com nomes de objetos

`build_3mf_xml()` insere `obj.name` diretamente no atributo XML `name`. Nomes contendo `&`, aspas ou `<` podem invalidar o arquivo.

Use um construtor XML ou escape correto de atributos. Não resolva proibindo nomes comuns no Blender. Teste um objeto chamado `Peça "A" & B <teste>` e valide o XML com um parser.

### Aceitação

- Todos os formatos retornam `{'FINISHED'}` no sucesso e `{'CANCELLED'}` na falha.
- Peça conhecida de 40 × 30 × 20 mm mantém dimensões ao abrir STL e 3MF no fatiador.
- Repetir com `scale_length=1`, `0.01` e `0.001`, e com escala/rotação não aplicadas no objeto.
- STL por peça e por material seguem a mesma conversão, sem dupla escala.
- Erro de escrita não apaga arquivo anterior nem deixa objetos temporários; seleção é restaurada.
- 3MF com caracteres especiais no nome possui XML válido.

## 4. Sessões e seleção das peças exportadas

**Referências:** `src/operators.py`: `CHEST_OT_splitter_set_target`, `CHEST_OT_splitter_commit_parts` (1055–1119), `CHEST_OT_splitter_separate_by_material` (1262–1325) e `CHEST_OT_splitter_export_parts`; `src/properties.py`: `session_id`; `src/io_export.py`: `separate_object_by_material()`.

### Evidência

O exportador prefere todos os meshes da coleção de peças finais, mesmo quando a sessão atual está em prévia. A coleção é compartilhada entre cortes. O operador de separação por material também pode processar todos os meshes finais. Além disso, `session_id` tem valor padrão fixo `session_01`: apenas adicionar um filtro por esse valor não produz isolamento real.

### Correção exigida

- Crie identidade efetivamente única para cada novo corte, por exemplo UUID, com política clara para atualizar a mesma prévia e iniciar um novo corte.
- Atribua metadados de sessão e papel aos resultados desde sua criação. Ao separar por material, propague-os aos subobjetos e mantenha uma indicação de quais resultados substituem os anteriores.
- Em `PREVIEW_VALID`, exporte os resultados da prévia atual; em `COMMITTED`, exporte os resultados finais daquela sessão. Uma coleção antiga não deve ter prioridade sobre o estado atual.
- Centralize a resolução dos resultados atuais para exportação e separação por material. Coleção e nome são organização visual, não prova suficiente de propriedade.
- Preserve peças de outros cortes. Não limpe todas as peças finais para impedir exportações misturadas.
- Defina comportamento seguro para arquivos antigos com `session_01` ou sem metadados: migre apenas quando a associação for inequívoca; em caso ambíguo, peça seleção explícita em vez de adivinhar.
- Se houver subpeças derivadas da prévia, atualizar a prévia deve invalidá-las/removê-las de forma controlada; elas não podem continuar sendo exportadas como atuais.
- Ao exportar uma prévia, use a posição montada canônica em snapshots, sem incorporar o afastamento visual da vista explodida. O 3MF atual usa `matrix_world` diretamente. Não altere a vista do usuário permanentemente.

### Aceitação

Na mesma cena: confirmar corte X → criar prévia Y → exportar Y → confirmar Y → exportar Y. Os arquivos de Y contêm somente Y; X continua intacto. Repetir com separação por material, salvar/reabrir a cena e exportar nas vistas montada/explodida. A vista explodida não muda o alinhamento físico exportado.

## 5. Prévia desatualizada após mudanças no alvo ou cortador

**Referências:** `src/properties.py`: `_on_param_change_mark_stale()` (33–38), propriedades do alvo/plano/cortador; `src/operators.py`: `read_plane_geometry()`, geração, confirmação e exportação; `src/geometry_loop.py`: `get_topology_signature()`.

### Evidência

Vários parâmetros têm callbacks de invalidação, mas mover um objeto guia pela viewport ou editar a malha não é uma alteração dessas propriedades. O callback de troca do cortador atualiza diagnósticos, porém não marca a prévia como desatualizada. A assinatura topológica baseada somente em contagens V/E/F também não detecta alterações de conectividade com a mesma quantidade de elementos.

### Correção exigida

- Registre um snapshot ou assinatura dos dados relevantes usados para construir a prévia: alvo e transformação, geometria/conectividade, materiais quando influenciam o corte, guia/cortador e transformação, parâmetros, captura de contorno e escala física da cena.
- Invalide quando esses dados mudarem. Troca do alvo/cortador também precisa invalidar o resultado.
- Antes de confirmar, exportar ou separar resultados de prévia, faça uma validação final de atualidade. Não dependa exclusivamente de um handler ou de a interface já ter redesenhado.
- Um handler de depsgraph pode ajudar na resposta visual, mas filtre eventos relevantes e evite trabalho pesado em cada desenho da HUD. Não crie loops ao escrever propriedades derivadas como origem do plano.
- Mudanças apenas de vista explodida ou cores de contraste não alteram a geometria e não devem invalidar o corte.
- Ao detectar alteração topológica que torne índices do loop inseguros, descarte a captura e solicite nova seleção. Alteração apenas de posição dos vértices exige regeneração, sem necessariamente perder a captura.
- Registre/remova handlers corretamente ao ativar/desativar a extensão e trate carregamento de arquivos e undo/redo.

### Aceitação

Gerar prévia e depois: mover/rotacionar o plano; mover/trocar o cortador; mover o alvo; editar vértices; alterar conectividade mantendo contagens; trocar material relevante; alterar escala da cena. Cada caso deve impedir confirmar/exportar a prévia anterior e orientar sua atualização. Alterar apenas explosão/contraste deve continuar permitido.

## 6. Validação geométrica antes de sucesso, confirmação e exportação

**Referências:** `src/operators.py`: trecho final de `generate_preview.execute()` e `commit_parts.poll()`; `src/geometry_plane.py`: `evaluate_bmesh_metrics()` e `slice_mesh_by_plane()`; `src/geometry_material.py`: `slice_mesh_by_material()` (235–417); `src/geometry_connectors.py`: validação e booleanos dos encaixes.

### Evidência

A geração calcula `is_manifold`, volumes e diferenças, mas termina marcando `PREVIEW_VALID` sem uma condição geral que rejeite resultados inválidos. No modo material, há caminhos que constroem `SplitResult(success=True)` sem exigir peças fechadas, não vazias e com volume positivo. A classificação de componente isolado calcula `is_manifold`, mas o caminho de corte não o exige.

### Correção exigida

- Centralize a validação mínima de resultados imprimíveis: faces/volume positivos, coordenadas finitas e ausência de bordas abertas ou não-manifold. Registre a razão precisa para falhar. Esses critérios não equivalem a uma certificação completa de imprimibilidade e não detectam, sozinhos, toda auto-interseção.
- Aplique a validação após o corte e novamente após os encaixes. Não marque a sessão como válida só porque o booleano produziu faces.
- Verifique conservação de volume **antes dos encaixes** com tolerância documentada. Depois dos encaixes, pinos e folgas alteram o volume; não compare a soma final ao original como se precisasse ser exatamente igual.
- Não transforme uma simples separação de faces por material em promessa de sólido imprimível. Para cascas abertas, preserve o aviso existente e impeça sua exportação automática como STLs sólidos individuais. Se mantiver exportação técnica de superfícies, torne-a uma ação explícita e distinta.
- No modo material, rejeite resultado vazio, componente aberto e profundidade que produza saída incompatível com o contrato. Não declare sucesso por construção.
- Construa resultados temporários, valide e só então substitua os resultados atuais. Falha deve deixar estado inválido e limpar temporários sem alterar o original.
- Confirmação/exportação também devem verificar existência e integridade dos resultados: o usuário pode editar ou apagar uma peça após a prévia.

### Verificações adicionais dos encaixes

`check_receiving_wall_thickness()` verifica raios no centro dos encaixes e considera válido um raio sem interseção. Revise esse comportamento: um raio que deveria encontrar o corpo receptor e não encontra exige diagnóstico. A amostragem central não demonstra que toda a cavidade cabe numa parede inclinada ou fina. Verifique também o contorno da cavidade e a margem até bordas/furos, e não apenas a inclusão do centro no polígono.

O operador chama `compute_connector_layout()` sem informar `connector_type` e `capsule_length_mm`, apesar de a função aceitar esses parâmetros. Corrija a consistência entre perfil pedido, distribuição e limites. Se houver ajuste automático de cápsula, determine primeiro o limite, aplique o ajuste e valide o perfil final; não rejeite prematuramente um tamanho que a interface promete ajustar.

Não prometa encaixes automáticos nos modos SOLID/MATERIAL: a versão atual não os implementa. Mantenha o controle indisponível e mensagens coerentes nesses modos; revise também a mensagem de sucesso para não anunciar encaixes que foram ignorados.

### Aceitação

Testar cortes em malhas abertas, resultado vazio, parede receptora fina/inclinada, raio sem corpo receptor, interface côncava e interface com furo. Resultados inválidos devem cancelar de forma clara. Em malha válida, testar cilindro e cápsula, distribuições disponíveis, inversão macho/fêmea e folgas por lado. Confirmar que o encaixe permanece unido ao corpo e a cavidade não perfura indevidamente a peça.

## 7. Consistência da geometria com modificadores

**Referências:** `src/diagnostic.py`: `analyze_target_mesh()`; chamadas com `target.data` em `src/operators.py`; cópias de objetos no corte por extrusão/material.

O diagnóstico avalia o objeto com modificadores, mas alguns cortes usam a malha base `target.data`; outros copiam o objeto e conservam sua pilha. Isso exige uma política uniforme para evitar cortar uma geometria diferente daquela medida e exibida ao usuário.

Prefira um snapshot avaliado e determinístico compartilhado pelo diagnóstico e corte, sem aplicar destrutivamente os modificadores do original. Para contornos capturados em Edit Mode, não reutilize índices da malha base em uma malha avaliada de topologia diferente. Se não existir mapeamento seguro, bloqueie esse caso com orientação para criar uma cópia com os modificadores consolidados.

Teste pelo menos um modificador que altera geometria, como Solidify, e um que muda topologia, como Subdivision/Mirror. Resultado e dimensões devem corresponder à política declarada. Trate alvos ocultos na avaliação, incluindo atualizações sucessivas, conforme a correção já citada no changelog.

## 8. Inglês, português e documentação

**Referências:** `src/translations.py`: `_get_current_locale()` (282–290), catálogo e funções de ajuda; `src/ui.py`; `README.md`, `CHANGELOG.md`, `blender_manifest.toml` e `__init__.py`.

- `_get_current_locale()` atualmente retorna `pt_BR` tanto para idioma português quanto para todos os outros idiomas. Retorne `pt_BR` para português e `en_US` para inglês/fallback definido. Verifique tooltips e popups em execução real.
- Revise os textos novos e os avisos dinâmicos. Corrigir apenas o seletor de ajuda não assegura tradução de toda a interface.
- Atualize o README, que ainda anuncia 0.6.0, para o fluxo e a versão realmente entregues. Inclua instalação, cortes, folga por lado, exportação e limitações.
- Remova referências a documentos ausentes ou inclua-os. Corrija texto com encoding quebrado no `__init__.py`.
- Alinhe versão do manifesto, `bl_info`, README e changelog. Uma próxima candidata pode ser 0.8.5, após confirmar a versão atual do repositório.
- O manifesto declara Blender mínimo 4.2.0. Teste essa versão antes de manter a promessa. Registre exatamente as versões usadas e seus resultados; não afirme compatibilidade universal com 4.x/5.x.
- Não copie a declaração de aprovação total de testes do changelog para a nova entrega sem executar as suítes correspondentes.

## 9. Matriz mínima de regressão

| ID | Cenário | Resultado obrigatório |
|---|---|---|
| R01 | Original → cópia → prévia → atualizar 3 vezes | Alvo preservado; nenhum datablock removido indevidamente |
| R02 | Restaurar, undo/redo, salvar/reabrir | Sessão e objetos coerentes |
| R03 | Exportar cada formato | Retorno explícito e arquivo legível |
| R04 | Dimensões físicas em 3 escalas de cena | STL/3MF mantêm 40 × 30 × 20 mm |
| R05 | Cortes X e Y na mesma cena | Exportação e separação operam somente na sessão escolhida |
| R06 | Prévia montada e explodida | Arquivos mantêm alinhamento canônico |
| R07 | Mudar guia/alvo/cortador/geometria/unidades | Prévia antiga bloqueada |
| R08 | Mudar apenas explosão/contraste | Prévia continua atual |
| R09 | Peça apagada/editada depois da prévia | Confirmação/exportação revalidam |
| R10 | Malha aberta, corte vazio, profundidade inadequada | Falha clara sem resultado anunciado como imprimível |
| R11 | Encaixes em parede fina, concavidade e furo | Cavidade e pino respeitam corpo/margens |
| R12 | Cilindro/cápsula e inversão macho/fêmea | Peças fechadas, unidas e folga física correta |
| R13 | Material com duas áreas separadas | Região correta extraída; restante preservado |
| R14 | Contorno DETACH/EXTRUDE/AUTO | Regressão dos comportamentos existentes |
| R15 | XML com caracteres especiais e falha de escrita | XML válido; arquivo anterior preservado |
| R16 | Interface e ajuda em português/inglês | Idioma correto e instruções coerentes |
| R17 | Modificadores no alvo | Corte corresponde à geometria suportada/descrita |
| R18 | Instalação limpa e validação do ZIP | Extensão ativa sem erro nas versões declaradas |

Use testes headless no Blender para contratos geométricos e operadores quando possível. Testes de viewport, traduções, undo/redo, seletor de arquivos e importação no fatiador também precisam de verificação real. Inclua comandos de execução e resultados no relatório; se o ambiente não tiver Blender ou fatiador, marque esses itens como pendentes, sem inventar aprovação.

## 10. Entrega solicitada ao Antigravity

1. Código corrigido e ZIP candidato com versão coerente.
2. Testes de regressão incluídos no repositório, mesmo que não sejam empacotados no ZIP de instalação.
3. README e changelog atualizados somente com mudanças e verificações reais.
4. Relatório conciso por problema: causa, arquivos alterados, comportamento depois da correção e evidência do teste.
5. Lista explícita de verificações manuais ainda pendentes e limitações existentes.

**Critério para encerrar:** não deixar nenhum bloqueador acima sem correção ou decisão técnica documentada e verificável. Compilação sintática isolada não é aprovação de lançamento.

## 11. Validação do usuário antes de publicar os vídeos e iniciar a venda

Depois de receber a candidata, instale o ZIP em um perfil limpo, faça o tutorial completo e confirme as dimensões no fatiador. Imprima ao menos um conjunto macho/fêmea com folga nominal conhecida; verifique montagem, resistência do pino e integridade da parede receptora. Uma folga geometricamente correta ainda depende da impressora, material e orientação de impressão.

Grave os vídeos em português e inglês usando exatamente o ZIP validado. Mostre original → corte → encaixe → exportação → fatiamento → montagem física. Se um teste necessário continuar pendente, registre-o como pendente e não apresente esse recurso como validado.

## Referências oficiais para implementação

- Operadores e retorno: https://docs.blender.org/api/5.0/bpy.types.Operator.html
- Exportador STL e parâmetros: https://docs.blender.org/api/5.0/bpy.ops.wm.html
- Mesh/BMesh e avaliação: https://docs.blender.org/api/current/bmesh.html
- Dependency graph e geometria avaliada: https://docs.blender.org/api/current/bpy.types.Depsgraph.html

Consulte a documentação da versão efetivamente testada antes de escolher argumentos e callbacks. As referências não substituem os testes do ZIP entregue.
