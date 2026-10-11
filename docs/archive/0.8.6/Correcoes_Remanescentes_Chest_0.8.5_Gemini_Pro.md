# Chest Part Splitter — correções remanescentes para Gemini Pro

## 1. Instrução para o Antigravity

Leia este documento inteiro e implemente as correções no repositório atual. O objetivo é resolver os problemas que permaneceram após a primeira implementação pelo Gemini Pro. Preserve as melhorias existentes; não volte ao código antigo e não acrescente funcionalidades novas.

**Base analisada:** `chest-blender-part-splitter(1).zip`, enviado após o pacote de correções da 0.8.5. O manifesto desse projeto ainda declara versão 0.8.5.

SHA-256 do arquivo analisado:

```text
f5ea7de3cda4b0fe14f2dcf948f6bb03ea11c4c3ae771e65f861106ec845fc70
```

Este documento complementa o plano anterior e prevalece para os problemas aqui descritos. Primeiro confronte as funções citadas com o código atual. As linhas servem para localização na base analisada; não aplique patches cegamente se o projeto mudou.

**Evidências disponíveis:** compilação sintática de 71 arquivos Python sem erros e testes isolados de funções reais com objetos simulados. Nesses testes, a verificação aceitou uma prévia com somente A, e a sequência “Refazer” manteve o ID antigo sem disparar a condição de renovação. Não houve execução do Blender nesta revisão. Não declare cortes, encaixes ou compatibilidade aprovados a partir dessas evidências.

## 2. Melhorias já implementadas que devem ser preservadas

- Prévia filtrada por sessão e papel compatíveis.
- Leitura integral de posições dos vértices e arestas pelo hash, eliminando a amostragem antiga do alvo.
- Índices de material por face do alvo incluídos na assinatura.
- Validação geométrica na confirmação e exportação, ainda com exceções a corrigir.
- Validação dos subobjetos no STL por material.
- Separação por material permitida somente depois de confirmar.
- Cópia de trabalho separada da coleção de prévias.
- Conversão física dos arquivos, escape XML, gravação atômica do 3MF e idioma da ajuda.

Não reescreva o motor geométrico inteiro. Corrija o ciclo de vida e os limites de validação, com testes específicos.

## 3. Mapa de referências

| Área | Referência da base atual |
|---|---|
| Limpeza | `src/operators.py`, `cleanup_collection_objects`, 83–149 |
| Assinatura de entrada | `src/operators.py`, `compute_session_input_signature`, 255–357 |
| Verificação da prévia | `src/operators.py`, `verify_preview_current`, 360–386 |
| Resolver das partes | `src/operators.py`, `get_current_session_parts`, 389–441 |
| Definir/limpar alvo | `src/operators.py`, classes a partir de 531 e 589 |
| Geração da prévia | `src/operators.py`, `CHEST_OT_splitter_generate_preview`, 853–1353 |
| Confirmação | `src/operators.py`, `CHEST_OT_splitter_commit_parts`, 1443–1539 |
| Restauração/refazer | `src/operators.py`, classes a partir de 1542 e 1589 |
| Separação por material | `src/operators.py`, classe a partir de 1696 |
| Exportação | `src/operators.py`, classe a partir de 1758 |
| Hash de topologia do loop | `src/geometry_loop.py`, `get_topology_signature`, 34–48 |
| STL por material | `src/io_export.py`, `export_objects_to_stl_by_material`, 250–350 |
| Nova suíte e executor | `tests/test_b01_b07.py`, `tests/run_all_tests.py` |

## 4. P01 — refazer um corte confirmado não inicia outra identidade

**Prioridade: alta.**

Na geração, o ID novo depende desta condição:

```python
if not settings.session_id or settings.session_id == "session_01" or settings.session_status == 'COMMITTED':
    settings.session_id = uuid.uuid4().hex[:12]
```

Porém, `CHEST_OT_splitter_redo_session.execute()` muda o status para `CONFIGURED` antes da próxima geração e mantém o ID. O caminho de interface “Refazer / Ajustar Sessão” portanto não atende à condição que deveria separar o corte novo do confirmado.

### Correção

Centralize início de novo corte, atualização da mesma prévia e reabertura de resultado confirmado. Escolha a política de menor risco: reabrir cria uma nova candidata com novo ID e preserva as peças confirmadas anteriores. Atualizar a mesma candidata mantém seu ID.

Não dependa de descobrir na geração qual era o status antes de um operador anterior modificá-lo. Pode zerar o ID no início do novo corte, gerar a identidade numa função central ou persistir uma transição explícita; o contrato precisa ser consistente em definir alvo, limpar, restaurar, refazer e gerar diretamente após COMMITTED.

### Reprodução e aceitação

Confirmar X → registrar ID X → clicar Refazer → gerar prévia → confirmar Y. Exigir ID Y diferente, exportar apenas Y, preservar X. Em seguida atualizar uma prévia três vezes e exigir ID estável. Cobrir o caminho real do botão, não apenas chamar a geração diretamente enquanto o estado ainda é COMMITTED.

## 5. P02 — trocar alvo com prévia pendente permite referências por nome erradas

**Prioridade: crítica para correção do resultado.**

Sequência identificada no código:

1. Definir outro alvo zera o ID.
2. Gerar nova prévia cria um novo ID e limpa apenas objetos desse ID.
3. Prévia anterior com ID diferente permanece na coleção com os nomes fixos A/B.
4. Blender pode atribuir nomes A/B com sufixo numérico aos objetos novos.
5. Confirmação continua buscando `preview_col.objects.get(PREVIEW_A_NAME)` e equivalente B.
6. A revalidação usa o resolver da sessão atual, mas os objetos renomeados e transferidos são os obtidos pelo nome fixo.

Isso separa o conjunto validado do conjunto efetivamente confirmado. `update_preview_positions()` também precisa usar as referências da prévia atual.

### Correção exigida

- Gere um conjunto autoritativo de resultados da candidata: referências aos objetos A/B, sessão e identidade de parte. Todos os operadores usam esse conjunto.
- Confirme exatamente os objetos validados, sem uma segunda busca por nome.
- Renomear um objeto não pode alterar a propriedade da sessão ou substituir outro resultado.
- Resolva a prévia anterior ao trocar alvo: descarte apenas os temporários comprovadamente pertencentes à candidata abandonada, ou mantenha-os como resultado inativo explicitamente excluído. Preserve cortes confirmados.
- Use os nomes como apresentação. Atualização de posições, inversões, confirmação e exportação precisam resolver as mesmas referências.
- Se houver múltiplos objetos representando A ou B sem uma relação válida de derivação, cancele por ambiguidade. Não selecione o primeiro da coleção.
- Não sobrescreva os metadados de objetos antigos para fazê-los parecer parte da candidata nova.

### Teste obrigatório

Criar X e Y distintos → prévia de X sem confirmar → trocar alvo para Y → gerar prévia → confirmar. Exigir que as geometrias confirmadas pertençam a Y. Verificar sessão, posição, dimensões e referências dos objetos. Repetir colocando objetos antigos com nomes reservados e renomeando os resultados novos. Não aceitar como prova apenas “o botão retornou FINISHED”.

## 6. P03 — proteção da cena deve preservar vínculo, não só datablock

**Prioridade: crítica para proteção do trabalho.**

A limpeza agora não apaga todo objeto pelo nome da coleção, mas mantém dois problemas:

- Objeto sem ID/papel com nome reservado A/B e na coleção de prévias ainda é classificado como descartável.
- Objeto não reconhecido é desvinculado da coleção de prévias. Se era seu único vínculo, deixa de aparecer na cena, embora continue em `bpy.data.objects`.

O teste existente só exige que o nome continue em `bpy.data.objects`. Essa assertiva não comprova que o trabalho continua acessível na cena.

### Correção

Exija propriedade comprovada, sessão e papel descartável para remover. Não classifique objetos legados como temporários somente pelo nome. Quando a identidade antiga for ambígua, preserve e avise; uma operação de migração conservadora pode pedir seleção explícita.

Para objetos do usuário não reconhecidos, preferencialmente mantenha o vínculo existente. Se a organização exigir movê-los para outra coleção, vincule à coleção de destino antes de desvincular, e preserve cena/visibilidade. Não remova seus vínculos silenciosamente.

Use a cena recebida pela operação, não somente `bpy.context.scene`. Distingua unlink local de remoção global com `do_unlink=True`. Papel de peça final ou igualdade de sessão não devem, isoladamente, autorizar exclusão.

### Aceitação

Testar malha pessoal com vínculo único à coleção de prévias; malha com dois vínculos; nomes reservados sem metadados; objeto renomeado; corte confirmado antigo; cópia de trabalho. Depois de gerar, atualizar, restaurar, limpar alvo e falhar encaixe, verificar identidade, geometria, vínculos e presença na cena. Checar também que temporários realmente descartáveis são removidos, sem órfãos novos.

## 7. P04 — validar conjunto completo, inclusive depois de confirmar

**Prioridade: alta.**

`verify_preview_current()` aceita qualquer lista não vazia da sessão. No teste isolado, uma candidata com somente A retornou `(True, '')`. A confirmação tem uma busca adicional por nome, mas a exportação não exige as duas partes; no estado COMMITTED, o resolver também pode retornar somente o que sobrou.

### Correção

Registre quais partes físicas são esperadas e quais objetos ativos as representam. Antes de confirmar, separar ou exportar, exigir o conjunto completo. Para prévia canônica de dois lados, exigir exatamente um A e um B da sessão. Depois de derivar partes por material, preservar origem A/B e completude através da relação de derivação, sem exigir rigidamente dois objetos quando existirem subpeças válidas.

Não crie essa regra por contagem total sem identidade: dois objetos A não substituem A+B. Não usar nomes para inferir completude. ID ativo vazio e assinatura ausente em dados que deveriam ter snapshot devem bloquear ou iniciar migração segura; não dispensar validação silenciosamente.

Fallback por prefixo do nome em `get_current_session_parts()` ainda pode selecionar objetos sem relação inequívoca. Restrinja migração ao que puder provar; caso contrário, solicite associação explícita.

### Aceitação

Excluir A, excluir B, duplicar A, introduzir objeto de outra sessão e testar confirmar/exportar em PREVIEW_VALID e COMMITTED. Exigir cancelamento claro antes de gravar arquivo. Testar também subpartes fechadas derivadas de A e B, que devem ser reconhecidas como um conjunto completo.

## 8. P05 — remover exceções que permitem confirmar/exportar sólidos abertos

**Prioridade: alta.**

Na confirmação:

```python
check_solid = settings.split_mode != 'MATERIAL'
```

Na exportação principal:

```python
check_solid = settings.export_format == 'STL_PARTS'
```

O modo Material com profundidade produz peças físicas e também deve exigir fechamento. O formato 3MF/OBJ, por si só, não autoriza malhas abertas num fluxo anunciado como exportação de sólidos. Uma peça gerada válida e depois aberta manualmente precisa ser revalidada.

### Correção

- Exigir geometria sólida fechada para os resultados físicos do corte, independentemente do modo que os criou.
- Revalidar a geometria efetivamente exportada, incluindo modificadores e transformações conforme a política suportada, não apenas `obj.data` se o exportador avalia outra malha.
- Coordenadas finitas, volume físico positivo e ausência de bordas não-manifold são critérios mínimos; não são certificação universal de imprimibilidade.
- Para 3MF colorido de uma malha canônica fechada, preservar cores sem separar superfícies artificialmente.
- Se separação por material gerar cascas abertas, não converter silenciosamente essas cascas em peças físicas nem permitir que a escolha de outro formato contorne a exigência. Preserve/oriente o uso do resultado fechado canônico ou corte Material com profundidade.
- Não adicionar um novo exportador técnico de superfícies para encerrar esta tarefa. Essa funcionalidade está fora do escopo.
- Toda validação deve ocorrer antes de efeitos externos do lote.

### Aceitação

Gerar corte Material válido → apagar uma face de uma parte → confirmar. Exigir cancelamento. Repetir com corte já confirmado e exportar STL por peça, STL por material, 3MF e OBJ. Verificar que nenhum caminho apresenta a casca como sólido válido. O caso de 3MF com cores sobre uma malha realmente fechada deve continuar passando.

## 9. P06 — assinatura ainda precisa representar faces, modificadores e loop

**Prioridade: alta para impedir confirmação de prévia antiga.**

A leitura integral de vértices/arestas corrigiu a antiga amostragem. Contudo, a assinatura das entradas não inclui a estrutura completa dos loops/polígonos nem os dados relevantes dos modificadores. `get_topology_signature()` do contorno ainda amostra arestas. A captura de loop precisa ser invalidada quando seus índices deixam de identificar a região pretendida.

### Correção

- Representar loops, vértices de cada face e orientação/conectividade relevante, além de posições e arestas.
- Representar a geometria avaliada ou os parâmetros/dependências efetivamente usados pelos modificadores conforme a política do corte. Não basta quantidades da malha base.
- Cobrir malha do cortador e suas faces; alterações de forma ou de pilha devem invalidar quando afetam o corte.
- Conferir atualização em Edit Mode e dependências de objeto pai/unidades.
- O handler ajuda na resposta visual, mas a validação final antes de confirmar/exportar continua obrigatória. Use cena/depsgraph recebidos em vez de contexto global como autoridade.
- Separar assinatura topológica da assinatura de posições. Alteração topológica invalida a captura; mudança apenas de posição exige regenerar, mas pode preservar a captura se ainda válida.
- Não calcular hashes integrais em todo redesenho da HUD. Cache e marcação de dados sujos devem preservar detecção completa.

### Aceitação

Alterar parâmetro de Solidify/Bevel/Mirror após gerar prévia; mudar estrutura/orientação de faces mantendo contagens e arestas quando possível; alterar região capturada de contorno; deformar cortador. Confirmar/exportar precisa invalidar resultados antigos. Alterar apenas vista explodida/contraste não deve invalidar o corte.

## 10. P07 — validação antes de qualquer gravação no lote

**Prioridade: alta para resultados de exportação coerentes.**

O STL por material valida as subpeças de cada objeto antes de exportar aquele objeto, mas continua iterando objeto por objeto. Se o primeiro passar e for gravado, e o segundo tiver casca aberta, a operação falha deixando parte do lote exportada. O retorno dos operadores STL nessa rotina ainda não é verificado.

### Correção

Pré-processar todos os resultados/subpeças → validar todos → planejar nomes/destinos → gravar. Se a validação de qualquer peça falhar, não criar nenhum arquivo novo do lote.

Verifique FINISHED/CANCELLED em todas as chamadas nativas. Não acrescente caminho à lista de sucesso apenas porque não houve exceção. Preserve seleção, modo, localização e temporários em `finally`.

Falha de IO durante a gravação é diferente de falha de validação. Use staging temporário quando viável e informe arquivos efetivamente concluídos quando não houver atomicidade total. Não apague arquivos anteriores para esconder uma falha de lote.

**Teste:** objeto 1 válido, objeto 2 com superfície aberta; STL por material deve cancelar antes de gravar o objeto 1. Simular CANCELLED do exportador e exigir ausência de falso sucesso.

## 11. P08 — executor de testes precisa detectar falha e incluir a suíte nova

`tests/test_b01_b07.py` tem quatro testes e termina assim:

```python
unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(TestCorrecoesB01B07)
)
```

O retorno do runner não é usado. O executor geral não inclui essa suíte e considera sucesso apenas o código de saída do subprocesso Blender. Corrija as duas partes.

### Implementação

Guardar o resultado de unittest e sinalizar falha ao processo, por exemplo:

```python
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise RuntimeError("A suíte apresentou falhas; consulte o log.")
```

No executor Blender, configurar código de saída para erro de Python, por exemplo:

```python
cmd = [BLENDER_BIN, "--background", "--factory-startup",
       "--python-exit-code", "1", "--python", test_path]
```

Confira o comportamento na versão usada. Inclua `test_b01_b07.py` ou a suíte sucessora no runner. Verifique existência do binário, dos scripts e diretório de execução. Capture e preserve stdout/stderr por suíte. Não contabilize “script abriu” como aprovação dos testes.

Um teste que espera qualquer RuntimeError pode passar por motivo errado, como poll indisponível ou falha de inicialização. Para integridade, valide preparo, retorno/erro esperado, mensagem e pós-condições. A exceção deve corresponder à causa testada.

**Aceitação do executor:** inserir temporariamente uma assertiva propositalmente falsa num teste descartável e executar pelo runner. Ele deve falhar, retornar não zero e não anunciar 100% aprovado. Remover o teste proposital e executar a suíte real. Entregar ambos os registros, identificando o teste de falha do executor.

## 12. Matriz obrigatória desta rodada

| ID | Sequência | Resultado |
|---|---|---|
| C01 | Confirmar → botão Refazer → gerar/confirmar | Novo ID; corte anterior intacto |
| C02 | Atualizar candidata três vezes | ID estável; conjunto único |
| C03 | Prévia X pendente → trocar para Y → confirmar | Geometria confirmada de Y, sem troca por nome |
| C04 | Objetos antigos com nomes A/B; novos renomeados | Resolver e confirmação usam referências atuais |
| C05 | Objeto pessoal com vínculo único em prévias | Continua visível e vinculado à cena |
| C06 | Objeto pessoal com nome reservado | Não é removido nem transformado em resultado |
| C07 | Objeto pessoal com dois vínculos | Vínculos externos preservados |
| C08 | Apagar A ou B antes de exportar | Cancelamento sem arquivo parcial |
| C09 | Apagar A ou B depois de confirmar | Conjunto incompleto bloqueado |
| C10 | Duplicar A mantendo sessão | Ambiguidade bloqueada |
| C11 | Subpartes fechadas derivadas de A/B | Conjunto completo reconhecido |
| C12 | Corte Material, face removida, confirmar | Sólido aberto bloqueado |
| C13 | Peça aberta, quatro formatos de exportação | Nenhum apresenta casca como sólido válido |
| C14 | 3MF colorido de malha canônica fechada | Cores e geometria preservadas |
| C15 | Modificador/topologia/cortador alterados | Prévia antiga invalidada |
| C16 | Apenas explosão/contraste alterados | Prévia não invalidada; exportação alinhada |
| C17 | Lote: primeiro objeto válido, segundo inválido | Validação cancela antes de gravar qualquer um |
| C18 | Exportador nativo retorna CANCELLED | Sem falso FINISHED ou contagem de arquivo |
| C19 | Teste intencionalmente falso pelo runner | Executor retorna falha corretamente |
| C20 | Undo/redo, salvar/reabrir e reinstalar | Referências, sessões e handlers coerentes |

Acrescente regressões do que já funcionava: unidades de cena 1/0.01/0.001, STL/3MF com dimensão conhecida, cilindro/cápsula, inversão macho/fêmea, cortes plano/loop/sólido/material e ajuda PT/EN. Não precisa repetir testes extras depois de passarem sem nova alteração que justifique.

## 13. Referências oficiais de apoio

- Operadores: https://docs.blender.org/api/5.0/bpy.types.Operator.html
- CLI e código de erro de Python: https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html
- Dependency graph: https://docs.blender.org/api/5.0/bpy.types.Depsgraph.html
- Handlers: https://docs.blender.org/api/5.0/bpy.app.handlers.html
- Exportação WM: https://docs.blender.org/api/5.0/bpy.ops.wm.html
- BMesh: https://docs.blender.org/api/current/bmesh.html
- Especificações 3MF: https://3mf.io/spec/

Consulte a versão correspondente ao Blender executado antes de escolher argumentos. As referências explicam APIs; não validam o código do Chest. As imagens do pacote anterior continuam úteis como esquemas de sessão, assinatura, superfície versus sólido e exportação montada. Não representam capturas de teste.

## 14. Entrega exigida e critério de encerramento

Entregue implementação, testes, logs, relatório P01–P08 e ZIP **de instalação** da candidata. O ZIP de código completo é útil para revisão, mas não substitui o pacote instalável validado. Escolha a próxima versão coerentemente com o repositório e atualize manifesto, `bl_info`, README e changelog.

No relatório, informe por problema: causa, solução, referências das funções alteradas, testes executados e resultado. Registre a versão exata do Blender. Não declare todas as versões 4.2+ compatíveis sem executar as versões necessárias à promessa de suporte.

Capturas úteis: X/Y com IDs e geometrias distintos; objeto pessoal sobrevivendo na cena; aviso de conjunto incompleto; casca do modo Material rejeitada; arquivo correto aberto no fatiador. Não fabricar evidência visual. Se não houver Blender, marque o teste como não executado e forneça o comando para reproduzir.

**Encerramento:** os oito pontos precisam estar corrigidos e testados, ou explicitamente pendentes por limitação real do ambiente. Uma correção que muda o filtro mas deixa a confirmação buscando nomes antigos não está completa. Testes devem acompanhar a sequência real dos botões e comprovar o resultado, não apenas o retorno do operador.
