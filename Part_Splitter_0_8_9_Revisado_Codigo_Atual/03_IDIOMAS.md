# LANG-01 — revisão de idioma

## Achados específicos

Na base atual 0.8.9:

- ui.py e properties.py contêm muitos textos PT fixos.
- translations.TRANSLATIONS_DICT tem 25 entradas pt_BR e 26 en_US, incluindo entradas pt_BR idênticas às fontes e traduções en_US de fontes PT.
- HELP_TOPICS usa catálogo PT/EN próprio.
- _get_current_locale resolve pt quando bpy.app.translations.locale começa com pt; todo restante vira en_US.
- Mensagens de alguns operadores usam loc=='pt_BR'; outras são PT fixas.
- Exceptions geométricas são frases PT; operadores embrulham str(e) com prefixos PT/EN. Pode resultar envelope inglês e causa portuguesa.
- F-strings formatadas antes de tradução não têm msgid estável; catálogo parcial não cobre toda combinação dinâmica.
- Falhas de registro de tradução são capturadas silenciosamente; investigar registro/unregister em reload.

As capturas 0.8.8 exibem mistura: Enable Connectors, Cut Distribution, Nominal Dimensions, Assembly Clearances (FDM), Boundary Loop Cut, Highlight Loop in Viewport, Invert Explosion Direction e mensagens de erro em inglês entre controles portugueses.

O Blender das capturas também tem menus em inglês. Assim, não concluir que o idioma do sistema era PT: a mistura pode decorrer de locale en + fontes PT incompletamente catalogadas. A preferência explícita do addon resolve a expectativa sem exigir mudar toda a interface do Blender.

## Política recomendada

AddonPreferences.language: AUTO / PT_BR / EN_US; padrão AUTO. Preferência do addon, não configuração de cada cena. IDs internos e EnumIdentifiers permanecem estáveis e não são traduzidos.

Um único resolver resolve preferência explícita ou idioma Blender. Fallback EN_US documentado para idiomas não suportados. Alterar idioma deve redesenhar UI sem alterar geometria, sessão, captura ou validade da prévia.

Usar catálogo único com chaves de mensagem estáveis e placeholders nomeados. Todas as mensagens possuem PT/EN. Exemplos:

| Chave | PT | EN |
|---|---|---|
| connectors.enable | Ativar encaixes | Enable connectors |
| connectors.distribution | Distribuição dos encaixes | Connector distribution |
| connectors.suggest_positions | Sugerir posições | Suggest positions |
| connectors.suggest_count | Sugerir quantidade | Suggest count |
| connectors.outside_domain | O encaixe {index} está fora da região útil ou viola a margem de {margin_mm} mm. | Connector {index} is outside the usable region or violates the {margin_mm} mm margin. |
| preview.failed_preserved | A atualização falhou: {reason}. A prévia anterior foi mantida. | Update failed: {reason}. The previous preview was preserved. |
| loop.recapture_target_changed | O corpo mudou após o corte. Capture um novo contorno para continuar. | The body changed after the cut. Capture a new boundary to continue. |
| target.edit | Editar alvo | Edit target |
| target.continue_receiver | Continuar no corpo remanescente | Continue on the remaining body |
| explosion.reverse | Inverter sentido da explosão | Reverse explosion direction |
| cutter.focus | Focar cortador | Focus cutter |
| cutter.from_selection | Criar cortador desta seleção | Create cutter from selection |
| materials.receiver | Material da cavidade | Cavity material |
| materials.insert | Material do inserto | Insert material |

Preferir “Prévia” em PT, sem alternar Preview/Prévia. Manter nomes de marca Part Splitter e de objetos do usuário. “Contorno (Loop)” pode ser termo didático na primeira ocorrência; restante consistente.

## Estratégia de implementação sem tradução dupla

Para atender override do addon independente do Blender, escolher uma camada explícita de resolução de texto. Renderizar texto já resolvido com translate=False nas chamadas que suportam isso; não passar frase PT resolvida de novo pelo catálogo en do Blender.

Verificar a API UILayout da versão mínima. Propriedades e enums podem receber tratamento diferente de rótulos: cobrir nomes, descrição/tooltips e cada enum exibido. Usar callbacks estáveis ou botões explícitos quando necessário; não reinicializar propriedades RNA a cada troca de idioma nem renomear seus identifiers.

Caso opte por integração nativa bpy.app.translations para AUTO, não manter duas estratégias concorrentes por widget. Isolar adaptação para override e testar menus/enum popovers; versões diferentes podem interpretar translate/context de forma diferente. Escolher a solução mais simples que passe nos testes PT/EN e documentar.

Strings retornadas por callbacks de enum devem ter vida útil estável; manter catálogo em memória, evitando construir itens efêmeros sem referência retida. Não adicionar complexidade dinâmica se botões existentes resolvem o requisito.

Formato: primeiro resolver template, depois formatar parâmetros. Não usar f-string final como chave. Validar igualdade de placeholders PT/EN, incluindo índice, unidade, nomes e causa aninhada.

Relatórios persistem code+params+severity+stage. Ao desenhar/mostrar report, resolver idioma atual; mudar idioma depois de uma falha muda texto do diagnóstico sem perder dados.

Exceções de domínio retornam códigos tipados; logs técnicos podem conservar traceback original. Erro não previsto vira mensagem amigável localizada + identificador para log; não despejar inglês técnico como única explicação.

Não substituir globalmente palavras nos fontes: nomes de propriedades, imports, operadores e filenames não são textos de interface.

## Auditoria e migração

scripts/auditar_textos.py extrai candidatos de labels, descriptions, textos de layout, reports e exceções. referencias/Auditoria_Textos_Atual.csv foi produzido na base atual 0.8.9; é inventário de candidatos, não prova de ausência de chaves nem teste de execução.

Auditar checkout atual 0.8.9:

1. ui.py: rótulos fixos e dinâmicos, tooltips de ajuda, status, instruções.
2. properties.py: names/descriptions e enum display.
3. operators.py: bl_label, bl_description, reports, popup/menu e last_status.
4. geometry_* e io_export: erros/avisos convertidos em códigos.
5. translations/help: unificar catálogos e remover fallback PT acidental em EN.
6. Scripts auxiliares destinados ao usuário: linguagem clara; logs técnicos podem ser técnicos.

Corrigir promessas de ajuda como “100% pronto para impressão” e “cavidade perfeita”: fechamento topológico não prova espessura, material ou montagem.

## Testes obrigatórios

- Blender EN + addon PT: nenhum inglês de interface do addon, exceto marca/nome do usuário.
- Blender PT + addon EN: nenhum PT em interface/erros/ajuda.
- AUTO com Blender PT/EN: resultado consistente.
- Tradução de interface/tooltips Blender on/off: override do addon mantém política definida.
- Trocar idioma com prévia válida e com erro salvo: geometria e dados iguais, texto atualizado.
- Painel, enums, tooltip, erro de encaixe, erro de loop, falha com prévia preservada, confirmação, continuidade e exportação.
- Reload/register/unregister repetidos: catálogo e handlers sem duplicações.
- Placeholders e plural/singular: mensagens1/2/5 encaixes/faces; valores não desaparecem ou trocam significado.

Referências oficiais em referencias/Fontes_Oficiais.md. Testar no Blender instalado; catálogo estático sozinho não comprova idioma renderizado.
