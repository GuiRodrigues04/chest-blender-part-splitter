# Agentes e uso de tokens nos projetos

Use o agente principal para entender o pedido, escolher a menor verificação útil e integrar o resultado. Se uma tarefa delimitada justificar delegação e estiver autorizada, use **um GPT-6 Luna em `low`**. Exemplos são reproduzir um bug com parâmetros conhecidos, editar um módulo ou rodar uma bateria já definida. Se Luna estiver indisponível, avise antes de substituir e proponha **GPT-6.1 Terra em `low`**. Enquanto espera, o agente principal pode adiantar o trabalho que consegue fazer diretamente. Nunca substitua Luna por um segundo Sol. Todo subagente usa `low`, inclusive se for encarregado de revisar.

## Como trabalhar

1. **Delimite antes de delegar.** Registre o objetivo, caminhos relevantes, entrada mínima, sintoma esperado e critério de conclusão. Prefira tarefas sequenciais com um executor quando todas dependem da mesma investigação. Em trabalho que possa ser dividido, cada agente recebe arquivos ou responsabilidades distintos e apenas o contexto necessário.
2. **Busque por etapas.** Comece pelo índice do projeto e por buscas de nomes e símbolos com `rg`. Leia os arquivos que participam do fluxo em questão. Abra relatórios, históricos, imagens e logs completos apenas se o trecho relevante não resolver a dúvida. Salve a saída extensa em arquivo e traga para a conversa os erros, as contagens e os caminhos.
3. **Reutilize um caso verificado.** Anote versão, entrada, parâmetros, comando, resultado e próximo passo. Ao retomar, aproveite essa ficha e os logs. Se uma hipótese falhar, registre o resultado antes de tentar outra para evitar reproduções duplicadas.
4. **Valide por impacto.** Primeiro reproduza o problema. Depois rode o teste mais próximo do código alterado e as regressões dos comportamentos compartilhados. Amplie a bateria quando a mudança atravessar módulos, houver resultados inconclusivos ou o trabalho for uma entrega que exige validação mais ampla. Teste o pacote exato quando publicar. Em documentação, revise links e diffs. O custo do processo local e o volume de logs enviados ao modelo são coisas diferentes.
5. **Conclua com evidência.** Informe o resultado, quais verificações passaram, as limitações e os modelos e esforços efetivamente usados. Para um trabalho interrompido, deixe um resumo curto com o que já foi feito e o primeiro passo pendente.

### Exemplo de tarefa delegada

> Use GPT-6 Luna em low. Parta do commit indicado. Reproduza o defeito descrito no arquivo indicado, revise apenas o módulo relacionado e execute a suíte indicada. Retorne o diagnóstico, os arquivos alterados, o resultado do teste e qualquer bloqueio. Salve logs longos localmente.

## O que aproveitar no Splitter

| Já existe | Como usar |
| --- | --- |
| [Mapa do repositório](ESTRUTURA_REPOSITORIO.md), código ativo em `src/` e [índice de evidências](../evidence/README.md) | Comece por eles. Abra somente a campanha ou o trecho que responde à pergunta. |
| `tests/run_all_tests.py` e testes isolados no Blender | Use `--suite` para escolher o teste ligado à alteração e `--report-dir` para guardar a saída. Reutilize o executor em vez de criar outra cópia por versão. |
| `scripts/build.py` e `tests/test_release_package.py` | Use a rotina de build do projeto antes do teste do pacote. Valide o ZIP final antes da publicação. |
| Scripts de auditoria em `scripts/audits/` e relatórios por versão | Reutilize casos com os mesmos dados e parâmetros. Separe resultados finais, tentativas e casos ignorados. |

Nas correções recentes da Spot, a reprodução no arquivo real distinguiu problemas que pareciam iguais pela imagem. Por exemplo, uma peça fechada ainda podia conter a película na borda. Preserve a medida que verificou o defeito, como a espessura da película ou a folga no contorno, e reutilize-a junto do teste sintético. Repetir a inspeção visual, reler o histórico inteiro ou criar vários agentes para investigar o mesmo trecho tende a adicionar trabalho. Isso é uma oportunidade de melhoria observada no fluxo, sem uma medição histórica de tokens por causa.

Nos tutoriais, transcreva localmente com FFmpeg e faster-whisper e reutilize a transcrição. Para revisão de vídeo, passe os trechos e timestamps pertinentes. Use um executor por vez quando houver alterações na mesma sequência.

## Como medir a economia

Compare duas execuções com o mesmo commit, insumos, critério de aceite e checagens. Registre modelos, esforço, quantidade de agentes, tempo, retrabalho e, quando disponíveis, tokens de entrada, cache, saída e raciocínio. Registre o que a ferramenta inclui no total antes de somar contagens. Se houver só um percentual de cota compartilhada, trate-o como sinal geral da conta. Evite atribuir a diferença a um agente ou a uma versão de modelo sem medição por execução.

Para levar a regra a outro projeto, copie a seção **Uso de agentes** para o `AGENTS.md` da raiz e aponte seu link para este guia ou para uma cópia no novo repositório. A documentação oficial explica como o Codex lê essas instruções, como subagentes ampliam o trabalho processado e como escolher um modelo para tarefas delimitadas. [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) · [Subagentes](https://developers.openai.com/codex/subagents) · [Seleção de modelos](https://developers.openai.com/api/docs/guides/model-selection)
