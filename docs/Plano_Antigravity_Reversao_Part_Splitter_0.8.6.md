# Part Splitter 0.8.6 — Remover prévias e reverter cortes

## Instrução ao Antigravity

Implemente somente a reversão de prévias e cortes descrita neste documento. O objetivo é permitir testes rápidos: gerar prévia → remover prévia → editar alvo → gerar novamente; confirmar corte → reverter corte → ajustar → repetir. Não implementar novas folgas, encaixes, métodos de corte, correções geométricas ou atualização de regiões por material.

Este plano deriva de inspeção estática do ZIP chest_part_splitter-0.8.6.zip, cujo blender_manifest.toml declara 0.8.6 e Blender mínimo 4.2.0. SHA-256: fc84bacee7ddc9c976cd18c38968a1308a0ce334dc1518d64dfee808d6d6c0a3. Não foi executado no Blender nesta análise. As linhas abaixo correspondem ao pacote analisado; localize também pelos símbolos, pois mudarão durante a implementação.

Antes de alterar, confirme que o checkout corresponde a esta base. Se houver diferenças, compare os pontos citados e adapte o plano sem sobrescrever mudanças recentes.

## 1. O que já existe e o que falta

| Local | Comportamento observado | Implicação |
| --- | --- | --- |
| src/operators.py:880, CHEST_OT_splitter_generate_preview | Produz candidatos, valida e substitui a prévia anterior; oculta target.hide_viewport após sucesso. Usa UUID de sessão. | Preservar a geração transacional. Capturar estado antes de ocultar, sem sobrescrever esse estado a cada atualização. |
| src/operators.py:1439, CHEST_OT_splitter_commit_parts | Promove A/B, altera nomes e papéis, move para PARTS e oculta os guias. Não remove nem corta a malha do alvo. | A reversão pode aproveitar o alvo preservado; não recalcular geometricamente o original. |
| src/operators.py:1560, CHEST_OT_splitter_restore_original | Limpa prévias; se houver chest_original_target resolvido por nome, remove a cópia de trabalho. Passa para CONFIGURED. | Não desfaz o corte confirmado. Pode descartar edições na cópia de trabalho. Separar as responsabilidades. |
| src/operators.py:1607, CHEST_OT_splitter_redo_session | Mostra alvo/guias, limpa session_id e assinatura, mas mantém peças finais. | Não usar como reversão. Preservar registros anteriores antes de iniciar nova sessão. |
| src/operators.py:84, cleanup_collection_objects | Protege alvo/work copy, mas admite papel de prévia com ID ausente e usa filtro condicionado à presença de IDs. | Não reutilizar como exclusão de cortes sem um coletor mais estrito. |
| src/operators.py:412, get_current_session_parts | Consulta coleções; possui fallback por prefixo de nome em resultados confirmados. | Pode continuar servindo à leitura legada, mas o fallback por nome não pode autorizar exclusão. |
| src/operators.py:1791, CHEST_OT_splitter_separate_by_material | Cria subpeças com ID/papel; pode apenas desvincular os pais de PARTS. | Registrar também pais desvinculados para não deixar objetos órfãos após reversão. |
| src/operators.py:651, CHEST_OT_splitter_create_work_copy | Copia objeto/malha, aplica rotação/escala e oculta o original. Vincula original por nome. | Remover prévia deve preservar a cópia e suas edições. Não voltar automaticamente ao objeto anterior à cópia. |
| src/ui.py:438–459 | “Restaurar Original” aparece em prévia válida/desatualizada e COMMITTED. | Substituir por ações com semântica distinta; cobrir PREVIEW_INVALID com prévia anterior preservada. |
| src/properties.py:88–132 | Uma configuração global por cena, com target_object, session_id e status. | É necessário registro persistente de operações, separado da sessão ativa. |
| src/operators.py:2349–2400 | Handlers de undo/redo conservadores; sem load_post registrado aqui. | Reconciliar vínculos após reabertura e undo/redo, sem exclusão automática. |

## 2. Contrato da interface

### Remover prévia

Adicionar “Remover prévia” junto a “Gerar / Atualizar Preview”. Descrição: “Descarta esta prévia e retorna ao objeto alvo. Alterações feitas na prévia serão descartadas.”

Disponível quando houver objetos de prévia comprovadamente vinculados à operação resolvida, inclusive nos estados PREVIEW_STALE e PREVIEW_INVALID. Não depender somente de PREVIEW_VALID.

Ao executar: sair de Edit Mode antes de excluir objetos; remover somente as prévias da operação; restaurar os estados de visibilidade alterados pela extensão; selecionar e ativar o alvo da sessão; preservar cópia de trabalho, malha, materiais, parâmetros, cortador e posicionamento do guia. Limpar assinatura/métricas de resultado e retornar a CONFIGURED, se o alvo for válido.

O alvo deve ficar acessível para editar. Se uma coleção excluída ou escondida pelo usuário impedir a seleção, informar a limitação e não mudar silenciosamente estados de coleções externas. Preservar hide_render se a extensão não o alterou.

### Reverter corte

Adicionar “Reverter este corte” na área de resultados. Mostrar o alvo e a operação resolvida. Descrição: “Remove os resultados deste corte e restaura seu estado anterior. Alterações nas peças geradas serão descartadas.”

Confirmar usando diálogo nativo curto, com quantidade de objetos afetados e identificação da operação. Aplicável também a peças renomeadas, movidas ou parcialmente removidas. Não exigir preview atual nem integridade geométrica dos resultados para reverter.

Se houver operação filha ativa, bloquear a reversão do pai e indicar que é necessário reverter primeiro o corte posterior. Sem reversão em cascata nesta entrega.

Ambas as ações são independentes de bpy.ops.ed.undo; manter bl_options com UNDO para que as próprias ações respeitem o histórico do Blender.

## 3. Modelo persistente mínimo

Criar PropertyGroups para registro de operações e referências de objetos, preferencialmente em properties.py, com CollectionProperty na cena e PointerProperty para objetos/coleções reais. Registrar classes dependentes antes de ChestSplitterSettings; desfazer registro na ordem inversa.

Cada operação precisa de:

- UUID completo e estado próprio: PREVIEW, COMMITTED, REVERTED ou BROKEN.
- Ponteiro para alvo efetivo e snapshot de restauração; nome apenas informativo.
- ID da operação pai quando o alvo foi gerado por outro corte.
- Lista de objetos gerados e papel de cada um, incluindo pais de separação por material.
- Estado de visibilidade do alvo/guia antes das alterações da extensão; hide_viewport, hide_set por view layer pertinente e hide_render quando relevante.
- Vínculos com coleções do alvo no momento da captura e transformação.
- Versão do registro para evolução/migração.

Reutilizar chest_session_id onde adequado e manter compatibilidade com chest_splitter_session_id. Adicionar vínculo de propriedade da operação aos novos resultados, sem confundir o papel anterior do alvo com seu papel como entrada. Não sobrescrever o ID de geração de uma peça só porque ela se torna alvo de um corte filho.

Ponteiros não são suficientes para excluir: duplicatas feitas pelo usuário podem copiar propriedades customizadas. Autorizar exclusão pela lista explícita de objetos gerados pelo operador e pelo vínculo de propriedade; se houver ambiguidade, cancelar e explicar. Nunca considerar nome, prefixo, cor ou pertencimento à coleção como prova exclusiva.

## 4. Snapshot e alvo preservado

A base atual não modifica a malha do alvo ao confirmar. Aproveitar isso para a identidade do objeto e relações existentes, mas criar snapshot independente antes da primeira geração bem-sucedida da operação, antes de ocultar o alvo. Isso protege também contra alvo editado ou apagado depois.

Capturar após sincronizar Edit Mode. Usar Object.copy + cópia independente da malha base; não usar a malha avaliada do depsgraph como único backup, pois ela pode incorporar modificadores. Guardar snapshot em coleção interna oculta para viewport/render, com papel protegido RESTORE_BACKUP. Não deixar backups sem vínculo persistente, nem fazê-los entrar em exportações.

Atualizações sucessivas da prévia devem manter um único snapshot válido. Se o alvo foi realmente editado antes de regenerar, atualizar o snapshot transacionalmente para refletir o alvo que alimentou a última prévia bem-sucedida, sem capturar a visibilidade já alterada pela extensão. Se a atualização falhar, conservar a prévia e o snapshot anteriores.

Remover prévia não deve trocar a malha do alvo pelo snapshot: as edições feitas no alvo devem permanecer. Após remover, descartar o snapshot dessa operação de prévia quando não houver outra dependência.

Reverter corte deve recuperar o estado de entrada da prévia confirmada. Se o alvo existe, preservar sua identidade e restaurar os campos necessários; não substituí-lo indiscriminadamente e quebrar filhos/constraints. Se o alvo não existe, preparar sua recuperação a partir do snapshot antes de remover resultados.

Snapshot de objeto/malha não congela automaticamente materiais, ações, objetos apontados por modificadores ou outros datablocks compartilhados. O contrato desta entrega é restaurar geometria base, índices/slots de materiais, transformação e configuração dos modificadores/objeto, preservando referências compartilhadas. Não prometer desfazer edições externas em shaders, animação ou objetos do usuário. Documentar e testar essa fronteira.

Se não for possível restaurar corretamente um alvo ligado a biblioteca, override ou relação complexa, abortar antes de excluir resultados e informar a limitação.

## 5. Integração no ciclo atual

1. Em generate_preview, preparar snapshot e registro candidatos. Só consolidar junto ao swap bem-sucedido. Falha não apaga registros anteriores.
2. Registrar A/B na criação/promoção. Regenerar atualiza a lista; não acumula referências mortas.
3. Em commit_parts, validar e preparar registro antes de mover objetos. Promover a mesma operação para COMMITTED. Registrar as visibilidades dos guias antes de ocultá-los.
4. Em separate_by_material, registrar subpeças e manter registro de pais desvinculados. Não alterar o algoritmo geométrico.
5. Em set_target, clear_target e redo_session, preservar histórico confirmado. Limpar sessão ativa não elimina registros recuperáveis. Não deixar prévias abandonadas ao trocar alvo: pedir remoção explícita ou resolver a transição com a mesma rotina segura.
6. Refatorar restore_original como alias de compatibilidade que despacha para a ação apropriada, sem manter a exclusão automática da work copy. Evitar duas implementações divergentes.
7. Atualizar classes de operators.py e UI; inserir textos/ajuda PT-BR e inglês em translations.py.

Resolver a operação pela seleção registrada quando inequívoca; depois pela sessão ativa quando ela for válida e não conflitar com a seleção. Se várias operações forem candidatas, mostrar escolha explícita; nunca reverter uma operação por “última criada” silenciosamente.

## 6. Exclusão segura e falhas

Criar helpers dedicados, em módulo pequeno de lifecycle se ajudar, evitando expandir algoritmos geométricos:

- resolve_operation(context)
- collect_owned_objects(scene, operation, roles)
- capture_restore_state / prepare_restoration
- remove_preview / revert_committed_operation
- reset_result_state / reconcile_operation_records

Os nomes são propostas, não funções existentes.

Antes de excluir: validar alvo ou snapshot, dependências, editabilidade, propriedade dos resultados e possibilidade de restaurar/selecionar. Fazer todas as validações possíveis primeiro. Não retornar CANCELLED depois de apagar parcialmente resultados sem tratar a recuperação.

Reverter deve preparar a restauração e garantir um ponto de recuperação até a conclusão. Retirar resultados da visualização/vínculos antes da fase final de destruição, quando necessário, mantendo informação suficiente para rollback. Só liberar backup após sucesso completo; em falha parcial, conservar registro e backup, comunicar o ocorrido e permitir recuperação.

Remover malhas somente quando forem criadas pela extensão e users == 0. Não fazer purge global. Não apagar materiais compartilhados, cortadores existentes, guias do usuário, peças de outros cortes, work copies ou backups de operações ativas.

Persistir o registro no .blend. Reconciliar em load_post e handlers existentes, sem gerar geometria, apagar dados ou acionar operadores pesados dentro de handlers. Registro incompleto vira BROKEN com aviso, sem limpeza automática.

Para cenas 0.8.6 sem snapshot/registro: permitir remoção de prévia apenas quando o vínculo legado for inequívoco. Reverter corte legado não deve prometer estado histórico exato. Se não houver prova suficiente de propriedade e restauração, desabilitar com explicação; nunca inventar backup anterior ao corte.

## 7. Estado e parâmetros

Ao remover/reverter, limpar session_input_signature, métricas part_a_*, part_b_*, part_sum_volume_mm3, volume_diff_pct e mensagens antigas de resultado. Recalcular diagnóstico do alvo restaurado.

Preservar parâmetros de corte/encaixe, materiais selecionados, profundidade, guia/cortador e preferências de exportação. Índices de loop/região capturados só permanecem se ainda forem válidos na topologia restaurada; caso contrário, invalidar a captura e pedir recaptura. Não introduzir a correção de cache de regiões neste trabalho.

Nova tentativa recebe novo ID de operação. Históricos confirmados anteriores não podem depender do valor atual de settings.session_id.

## 8. Validação obrigatória

Executar no Blender e registrar resultados; inspeção estática não comprova a feature.

| Caso | Resultado exigido |
| --- | --- |
| PLANE, SOLID, LOOP e MATERIAL | Gerar → remover → editar alvo → gerar; confirmar → reverter → repetir. |
| Prévia explodida, stale e invalid com prévia anterior | Remoção disponível; alvo acessível; sem objetos residuais. |
| Edit Mode na prévia ou resultado | Saída segura antes da exclusão; sem ReferenceError; alvo ativo em Object Mode. |
| Cópia de trabalho editada | Remover prévia preserva a cópia e as edições. |
| Alvo com transformação/modificadores/materiais | Reversão recupera estado de entrada, mantendo identidade quando possível. |
| Duas operações independentes | Reverter uma mantém a outra intacta. |
| Corte filho em peça A | Pai bloqueado enquanto filho ativo; reverter filho permite reverter pai. |
| Separação por cores após confirmação | Remover subpeças e pais registrados sem deixar órfãos. |
| Resultados renomeados/movidos/parcialmente apagados | Vínculos continuam resolvendo; não usar prefixos. |
| Duplicata de resultado pelo usuário | Não excluir a duplicata automaticamente. |
| Alvo apagado; backup existente | Recuperar alvo antes de remover resultados. |
| Backup ausente, operação ambígua ou restauração inviável | Cancelar antes de excluir e mostrar motivo. |
| Salvar/reabrir; Ctrl+Z/Ctrl+Shift+Z | Registros coerentes; sem exclusão automática pelos handlers. |
| Dez ciclos de teste | Sem crescimento de snapshots/malhas temporárias após reversões concluídas. |

Verificar seleção/visibilidade, contagem e coordenadas de vértices, índices de materiais, matriz e modificadores antes/depois; não usar apenas volume como equivalência. Cobrir uma cena com objetos não relacionados na coleção da extensão para garantir proteção.

## 9. Entrega esperada

Entregar código com os dois botões, documentação curta do comportamento, changelog e ZIP instalável. Seguir a convenção de versão do projeto; não modificar identidade/publicação. Listar arquivos alterados e testes realmente executados, com versões do Blender. Se algum teste não foi executado, declarar isso.

Prioridade: reversão confiável para testes. Não incluir histórico visual completo, restauração em cascata, novo sistema de geometria ou reorganização geral da extensão.

## Referências oficiais para conferir as APIs

- ID.copy, users e gerenciamento de datablocks: https://docs.blender.org/api/4.2/bpy.types.ID.html
- Propriedades persistentes e referências: https://docs.blender.org/api/current/bpy.props.html
- Handlers e persistent: https://docs.blender.org/api/current/bpy.app.handlers.html

Conferir compatibilidade com o mínimo declarado de 4.2 e testar também na versão usada pelo usuário. Não depender de recurso exclusivo do Blender mais recente.
