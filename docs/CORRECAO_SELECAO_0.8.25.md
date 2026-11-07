# Seleção do alvo após descartar a prévia — Splitter 0.8.25

Investigação e correção em 2026-10-24. Versão instalada: 0.8.25.

## Conclusão

Foi reproduzido um defeito real compatível com o relato: uma instância da ferramenta de alinhar vértices do cortador podia continuar ativa depois de gerar e descartar a prévia. O objeto alvo estava ativo, selecionado e constava entre os objetos selecionáveis, mas o handler antigo devolvia RUNNING_MODAL para os cliques normais e consumia Tab. O sintoma era de objeto bloqueado, embora os flags de seleção estivessem corretos.

A reprodução usou o método modal real com um evento controlado e uma sequência real de operadores de gerar/descartar no Blender. Não foi uma gravação do clique ocorrido na sua janela. Portanto, confirma a existência do bug e sua compatibilidade com o sintoma; não identifica com certeza o estado exato daquela sessão.

## Achados

1. **Alinhamento do cortador continuava recebendo eventos.** Antes, o modal só encerrava com Esc, botão direito, fim da escolha ou exclusão do objeto. Não verificava se outra operação havia encerrado a interação nem se o usuário havia trocado de objeto/modo. Foi adicionado encerramento explícito com geração de sessão; instâncias antigas liberam o primeiro evento para o Blender e não restauram o cortador antigo. Isso também acompanha gerar/descartar, Editar alvo, troca de alvo, desfazer/refazer, carregar e desativar a extensão. Tab encerra o seletor de vértices e é entregue ao Blender.
2. **Restauração de seleção incompleta.** Descartar só limpava a visibilidade do objeto. Flags de seleção do objeto/coleção e vista local podiam impedir o acesso. Agora o alvo é revelado, desbloqueado e ativado por uma rota de coleções da camada atual, incluindo sua presença nas vistas locais. Coleções sem relação com o alvo não são desbloqueadas. Falha de ativação gera aviso em vez de sucesso silencioso. Este cenário foi testado com bloqueios explícitos; não há evidência de que a extensão tenha criado esses bloqueios na sua sessão.
3. **Referência ao alvo perdida em Reverter corte.** Fluxo distinto do descarte: quando a peça B virava o próximo alvo e era apagada na reversão, a referência da sessão podia ficar vazia. O original reaparecia, mas Editar alvo ficava indisponível. A referência agora volta ao original restaurado.

## Evidência antes/depois

- Antes: `TARGET_ACTIVE=True`, `TARGET_SELECTED=True`, `TARGET_SELECTABLE=True`, evento do alinhamento antigo: `RUNNING_MODAL`. O teste de liberação do clique falhou, como esperado.
- Depois: mesma sequência retorna `FINISHED + PASS_THROUGH` para a instância antiga. O original fica ativo/selecionável e Editar alvo entra na edição dele.
- O teste foi repetido em alinhamento do objeto inteiro e de um único vértice, nas duas etapas da escolha. Coordenadas e transformações do alvo e cortador permaneceram iguais ao descartar.

Logs: `antes.log`, `depois.log`, `pacote.log`, `instalada.log` e `regressoes/*.log` nesta pasta.

## Validação

267 testes aprovados em 27 suítes, sem skips na execução final, Blender 5.2.0 LTS. A nova suíte tem 21 testes e foi repetida carregando o código do ZIP exato. A instalação real também foi carregada em processo independente para confirmar descarte, liberação do evento, desbloqueio e entrada em Edit Mode.

Foram testados: vista local, coleções aninhadas ocultas/excluídas/bloqueadas, objeto bloqueado, coleções alheias preservadas, troca de alvo/cortador, limpeza após remoção da área, modais concorrentes, remoção por API interna, pinos, cinco ciclos de gerar/descartar/editar sem mudar a geometria, descarte a partir da edição da prévia, confirmação/reversão e dois ciclos com o gato salvo. A instalação também regenerou o gato com pinos A/B e exportou STL, 3MF e OBJ.

| Suíte | Testes | Resultado |
|---|---:|---|
| test_regressions | 55 | passou |
| test_solid_edit_tools | 16 | passou |
| test_cutter_problem_selection | 9 | passou |
| test_problem_selection | 5 | passou |
| test_frame_regions | 10 | passou |
| test_release_depth_region | 3 | passou |
| test_release_depth_guard | 4 | passou |
| test_plane_limited | 9 | passou |
| test_manual_connectors_workflow | 11 | passou |
| test_acceptance_0810_suite | 8 | passou |
| test_acceptance_089_suite | 10 | passou |
| test_release_geometry | 6 | passou |
| test_release_interface | 9 | passou |
| test_release_state | 10 | passou |
| test_release_workflows | 9 | passou |
| test_release_material_patch | 1 | passou |
| test_clearance_profiles | 6 | passou |
| test_release_connector_frames | 4 | passou |
| test_safe_mesh_repair | 7 | passou |
| test_material_region_connectivity | 2 | passou |
| test_region_release | 29 | passou |
| test_release_package | 2 | passou |
| test_material_manual_connectors_bugfix | 4 | passou |
| test_commit_selection_bugfix | 2 | passou |
| test_reedit_after_preview_bugfix | 3 | passou |
| test_preview_selection_recovery | 21 | passou |
| test_reversion_086 | 12 | passou |

## Escopo e instalação

Arquivos de fonte modificados nesta correção: constants.py, lifecycle.py, operators.py, properties.py, scene_state.py, solid_tools.py, __init__.py. Além disso, identificadores de versão e changelog foram atualizados e a suíte de regressão adicionada.

Os módulos de geometria de plano, loop, material, sólido, região e conectores foram comparados byte a byte com o início da investigação e permanecem idênticos. A correção não altera profundidade, fechamento, pinos nem folgas.

Backup da instalação anterior: `C:\Users\guiro\OneDrive\Documentos\ChatGPT\Extensão Blender\bug-selecao-0.8.25\instalada-anterior-0.8.24`.
ZIP SHA256: `92bfdf694e482c4d34096cd045ab3fc8d467ab39af529cfa5b5bd3e441bd52af`. Bytes da instalação conferidos contra ZIP e fonte.
O arquivo Teste Gato.blend original e a cópia de teste anterior não foram sobrescritos.

## Como testar manualmente

1. Salve seu trabalho e reinicie o Blender. Confira a versão 0.8.25 no painel.
2. Gere uma prévia e clique em Remover/Descartar prévia.
3. Clique no gato e pressione Tab. Ele deve voltar a aceitar seleção e edição.
4. Repita depois de usar Ajustar só um vértice ou Mover cortador por vértices. Gere/descarte e confira que a ferramenta antiga não continua capturando cliques.
5. Se o cortador estiver na frente do gato, use Editar alvo no painel para ativar diretamente o corpo. O cortador continua existindo para poder ser ajustado.

A malha é preservada. Não é necessário remalhar nem refazer o gato para tratar este defeito.
