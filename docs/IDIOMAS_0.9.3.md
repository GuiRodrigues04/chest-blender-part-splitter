# Auditoria de idiomas 0.9.3
2026-11-02. Revisão estática de todos os módulos src, catálogo, ajuda e exceções; segunda verificação após correções e auditoria final após pacote.

Correções: erros literais de geometria/estado traduzidos nos dois sentidos; 38 mensagens dinâmicas migradas para modelos de catálogo com precisão numérica preservada; causas textuais de avisos traduzidas; aviso direto da reescolha de contato traduzido; terminologia portuguesa e preferências revisadas.

Verificações: zero rótulos estáticos ausentes no catálogo inglês na auditoria final; zero reports literais diretos; literais de exceções com frases têm entrada nos dois catálogos; não restam f-strings diretas em raise. Os 19 textos dinâmicos indicados pela auditoria de UI foram inspecionados: usam palavras localizadas, nomes do usuário, unidades/volume ou ramos já separados por idioma. Paridade das chaves e dos parâmetros de MESSAGES, ajuda nos dois idiomas e tradução aninhada verificadas em testes. Idioma real do Blender alternado entre pt_BR e en_US em processo descartável, sem salvar preferências. Testes adicionais: UI, estado, multicontatos, material e pacote aprovados.

Limites: revisão de código e testes não equivalem a inspeção visual de cada diálogo/modal. Nomes de objetos/materiais/arquivos fornecidos pelo usuário permanecem intactos. Falhas arbitrárias de bibliotecas externas podem conter detalhes técnicos não catalogados; não há tradução automática de qualquer texto desconhecido. Preferência Automático segue Blender; seleção manual de idioma permanece por compatibilidade. Não foram modificados algoritmos de corte/folga.

## Continuação 0.9.4
Revisão dos caminhos de exceção em avisos: connector_editor.py, solid_tools.py e operators.py. Mensagens diretas e causas interpoladas usam render_message. Teste impede report(str(exc)) em src e verifica exceção real PT/EN. Cinco testes de auditoria aprovados, locale Blender real aprovado, suítes de ferramentas sólidas e editor manual aprovadas, dois testes do pacote aprovados. Nova execução da auditoria estática: nenhum rótulo constante ausente e nenhum report literal direto. Não representa inspeção visual de todos os diálogos possíveis.
