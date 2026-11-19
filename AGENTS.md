# Uso de agentes

- O agente principal resolve tarefas pequenas diretamente. Só delegue quando o usuário ou as instruções aplicáveis pedirem e houver uma tarefa delimitada.
- Use **GPT-6 Luna em `low`** para subagentes. Se Luna estiver indisponível, avise antes de delegar. **GPT-6.1 Terra em `low`** é a alternativa preferida, mediante confirmação do usuário. Sol pode coordenar como agente principal. Não abra subagentes Sol nem use esforço acima de `low`.
- Use um executor por vez como padrão. Passe só o objetivo, os arquivos relevantes, o teste e o critério de conclusão. Informe os modelos e esforços efetivamente usados.
- Siga o [guia de agentes e uso de tokens](docs/AGENTES_E_TOKENS.md) para selecionar contexto, testes e evidências.
