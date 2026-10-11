# Plano de implementação — Chest Part Splitter 0.8.7

Revisado em 11/10/2026 para Antigravity / Gemini Pro após recebimento do repositório completo. Base analisada: **0.8.6 com lifecycle e testes**. Esta revisão substitui o plano anterior baseado no pacote de distribuição reduzido. Este documento especifica trabalho futuro; não é um relatório de correções implementadas.

## 1. Objetivo e evidência

Entregar uma versão de estabilização que produza peças imprimíveis, explique os limites dos métodos e facilite posicionar cortes. Corrigir primeiro perdas de estado, temporários e geometria; depois acrescentar as melhorias discutidas. Não considerar uma mensagem de sucesso ou uma afirmação no changelog como prova de funcionamento.

Foram recebidos dois arquivos, 0.8.5 e 0.8.6. O manifesto do pacote mais recente identifica `version = "0.8.6"`, mínimo Blender 4.2.0. A próxima versão solicitada é **0.8.7**, incluindo funções novas e correções. Se existir uma compilação posterior da 0.8.6 fora destes anexos, comparar o código antes de aplicar este plano e registrar diferenças.

Identificação da base atual: `chest-blender-part-splitter-0.8.6.zip`, SHA-256 `fb6cdb60a7d83e7b460fe6e1c6a2273502aad200ddda320cb7b7a996397cd44b`. O ZIP contém 598 entradas, incluindo `.git`, documentos, scratch e ZIPs de versões anteriores. Manifesto e `bl_info` identificam 0.8.6. Foram analisados sintaticamente 44 arquivos Python: 16 módulos em `src`, 26 scripts em `tests`, entrada raiz e build. Todos passaram por `ast.parse`.

**Nesta base os testes existem**: há `test_plan_086_commercial.py`, `test_reversion_086.py` e um runner com 20 suítes explicitamente listadas. A ausência de testes constatada no plano anterior referia-se ao ZIP reduzido `chest_part_splitter-0.8.6.zip`, não a este repositório. Os módulos de geometria e GPU são byte a byte iguais aos daquele pacote; portanto, os diagnósticos geométricos continuam pertinentes. Mudaram `operators`, `properties`, `constants`, `translations`, `ui`, e foi acrescentado `lifecycle.py`.

Não havia executável Blender neste ambiente. Não foram executados booleanos, ensaios de impressão, medições de viewport nem reprodução de crashes. As conclusões abaixo distinguem observação no código, indício visual e hipótese a testar. As imagens são referências dos relatos do usuário; não comprovam sozinhas a versão instalada ou a causa de cada falha.

## 2. O que já existe e deve ser preservado

| Recurso da base | Tratamento na 0.8.7 |
|---|---|
| Captura de loop e captura do perímetro das faces | Corrigir validade e regressões, sem criar outro fluxo equivalente. |
| Destaque GPU do loop e opção de exibição | Corrigir visibilidade por modo, leitura em Edit Mode e estado GPU. |
| Encaixes em Plano e Loop | O Loop já possui encaixes; corrigir interface e posicionamento. |
| Contornos ordenados no corte por plano | Preservar e testar múltiplos encaixes, furos e ilhas. |
| Candidatos isolados para nova prévia | Preservar a prévia anterior em falhas e estender a transação aos temporários internos. |
| Seleção de região pela face no objeto alvo | Manter validações de contexto e atualizar a lista de regiões em Edit Mode. |
| Handlers de Undo/Redo e guard de geração | Auditar o comportamento real; sua presença não confirma que o crash foi resolvido. |
| Remover prévia, reverter corte e backups em `lifecycle.py` | Já implementados nesta base; corrigir isolamento e atomicidade, sem recriar o recurso. |

## 3. Diagnóstico priorizado

| ID | Evidência e diagnóstico | Prioridade |
|---|---|---|
| B01 | `gpu_drawing.py::_draw_loop_overlay_callback` não verifica `split_mode == 'LOOP'`. Explica a permanência do destaque ao mudar para Plano. | Alta |
| B02 | A captura grava `loop_topology_signature`, mas a geração no ramo LOOP não compara essa assinatura antes de usar índices. Índices existentes podem apontar para outra região depois de editar a topologia. | Crítica |
| B03 | `slice_mesh_by_loop_extrude` chama `to_mesh()` no objeto avaliado e `to_mesh_clear()` no original. A limpeza das cópias também não cobre todas as exceções intermediárias. É um defeito de gestão de recursos, sem prova de ser a causa do crash relatado. | Crítica |
| B04 | `on_depsgraph_update_post` detecta atualização do cortador, mas sua chave compara somente transformação local, número de vértices e número de modificadores do alvo. Mudança exclusiva do cortador, coordenadas com mesma contagem e parâmetros de modificadores podem escapar. | Crítica |
| B05 | `create_loop_prism_cutter` fecha um único contorno com n-gons e depois triangula. Os relatos mostram membranas, volume nulo e arestas não-manifold. A causa específica de cada caso precisa de reprodução; não atribuir toda falha à concavidade. | Crítica |
| B06 | `compute_connector_layout` usa centro e distribuições da caixa envolvente. Em uma região em U, o centro pode cair fora do domínio; a rejeição pode ser correta e o posicionamento automático inadequado. | Alta |
| B07 | O cortador por material desloca todas as faces selecionadas numa única direção média. Para uma saliência com faces de orientações diferentes, isso pode extrair uma camada, mantendo um núcleo no corpo. | Alta |
| B08 | A interface de Material é declarada planar com eixos X/Y fixos e contornos vazios. Esse contrato não serve para habilitar encaixes automaticamente em uma interface arbitrária. | Alta |
| B09 | O desenho restaura blend, mas não restaura o depth test e redefine a largura de linha para 1 em vez do valor anterior; a restauração não está em `finally`. | Alta |
| B10 | Lista de regiões é construída no painel com leitura da malha; conferir sincronização com BMesh vivo, atribuição de material e mudança de conectividade. A terceira imagem de Material não comprova seleção errada. | Alta |
| B11 | Plano alinhado com face produz lâmina branca junto à saliência nas novas imagens. O alinhamento usa centro/normal da face, mas o bisect não recebe tolerância física explícita e não há política explícita de atribuição das faces coplanares. O fechamento pode recorrer a todas as bordas abertas da malha. A causa exata exige reprodução. | Crítica |
| B12 | `lifecycle.remove_preview` inclui objetos pelo papel de prévia mesmo quando pertencem a outra operação. A remoção pode ultrapassar a sessão escolhida. | Crítica |
| B13 | `capture_target_snapshot` descarta o snapshot anterior antes de construir o novo. O operador chama essa função antes do `try` principal da geração. Uma falha pode perder o backup anterior ou deixar estado parcialmente alterado. | Crítica |
| B14 | `resolve_operation` escolhe a primeira operação entre selecionados; fallback de snapshot por nome não valida papel e operação. Nomes reutilizados ou seleção de sessões diferentes precisam de resolução inequívoca. | Alta |
| B15 | A recuperação de alvo apagado cria um objeto novo copiando malha e matriz, sem restaurar integralmente modificadores, vínculos e configuração do objeto copiado no snapshot. Definir e cumprir contrato de restauração. | Alta |

Também auditar `geometry_contract.py::build_cut_interface`: origem `(0,0,0)` não deve ser interpretada como ausência de origem. Hoje há um fallback ao centroide quando o comprimento da origem é pequeno; confirmar impacto em interfaces reais e remover essa ambiguidade.

## 4. Etapa A — estado, Undo/Redo e temporários

### A1. Invalidar a prévia com segurança

Separar **detecção leve de alteração** e **validação completa antes de operações**. O handler apenas identifica alterações relevantes e marca caches/prévia como desatualizados. Não executar booleanos, reconstruir objetos ou alocar malha avaliada dentro do handler.

Rastrear objetos originais e datablocks de malha, transformações mundiais, dependências/modificadores e cortador/guia. Quando o depsgraph informar mudança relevante, invalidar conservadoramente sem depender só das contagens. Alterar material e área deve invalidar o modo Material. Alterar parâmetros físicos deve invalidar os modos correspondentes. Alterações de cor da prévia, opacidade do overlay ou distância explodida não devem invalidar a geometria.

Antes de confirmar/exportar, manter a verificação completa da assinatura, executada fora do handler. Se a assinatura não puder ser calculada com segurança, bloquear a operação com instrução de atualizar a prévia. Assinaturas por amostragem são insuficientes como garantia absoluta de integridade geométrica.

### A2. Validade da captura

Verificar identidade do alvo e da malha, assinatura de conectividade, índices não negativos e limites, existência de cada aresta do ciclo, fechamento, grau 2 e validade da face-semente. Em Edit Mode, usar a topologia atual de forma consistente tanto na captura quanto na comparação; não misturar assinatura da malha desatualizada com seleção do BMesh vivo.

Mudança de topologia deve invalidar a captura e orientar “A malha mudou. Capture o contorno novamente”. Movimento de vértices pode preservar conectividade, mas exige recalcular planicidade, direção e profundidade útil. Mover o objeto deve atualizar o destaque e invalidar a prévia correspondente. Nunca substituir índices inválidos por uma região arbitrária.

### A3. Limpeza total

Guardar separadamente `eval_obj_a`, `eval_obj_b`, malhas avaliadas, cópias e cortador. Liberar `to_mesh()` pelo mesmo objeto que o criou em `finally`, antes de remover os objetos de origem. Inicializar referências antes do `try`; só liberar recursos efetivamente adquiridos. Aplicar também a Material, onde o `finally` pode referenciar cópias ainda não inicializadas após falha precoce.

Adotar registro dos recursos criados por uma execução, incluindo BMeshes. Remover apenas temporários pertencentes à execução, com checagem de usuários das malhas. A transação externa dos candidatos não resolve automaticamente vazamentos nos métodos geométricos internos. Testar falha após cada estágio e preservar alvo, original e prévia anterior.

### A4. Undo/Redo

Conferir argumentos reais dos handlers nas versões suportadas; não pressupor que todo argumento recebido seja uma cena válida. Reconciliar referências pelo contexto/cenas apropriados, invalidar caches e evitar referências RNA/BMesh antigas após Undo. Registrar/remover handlers sem duplicação e limpar overlays ao carregar arquivo ou desativar a extensão.

Reproduzir “gerar prévia → vários Ctrl+Z → atualizar prévia” em processos Blender reais. Coletar versão, sistema, passos, `.blend` mínimo e log/trace de crash quando disponível. Não concluir falha do computador nem anunciar causa raiz sem reprodução.

### A5. Reversão e backups existentes nesta base

Preservar os operadores Remover Prévia e Reverter Corte. Corrigir `remove_preview`: ID da operação é requisito de propriedade; papel PREVIEW_A/B/PART identifica o tipo do objeto, não autoriza excluir objetos de outra operação. Migração de legado só pode usar evidência inequívoca e nunca ser fallback universal por papel. Antes de excluir, conferir identidade atual e associação à operação também nos objetos registrados.

Construir novo snapshot como candidato; verificar criação e vínculo antes de promover. Manter snapshot anterior até a nova prévia e registro estarem válidos. Uma falha deve restaurar também o registro e backup anteriores, não apenas a malha da prévia. Abranger todas as alocações e mudanças persistentes no `try/finally` da execução. Não usar “transacional” no comentário se a função descarta o backup antes de construir o substituto.

Resolver operação explicitamente por identificador ou seleção não ambígua. Várias operações selecionadas exigem escolha clara; não escolher a primeira pela ordem da lista. Para fallback por nome, exigir `chest_operation_id` e papel esperado; nome idêntico não é propriedade. Um snapshot ausente/adulterado deve produzir cancelamento antes de apagar resultados.

Definir snapshot completo: malha independente, materiais, modificadores e referências suportadas, matriz, parenting/coleções, visibilidade e propriedades necessárias. Quando o alvo existe, preservar identidade e restaurar o estado previsto; quando foi apagado, recuperar a cópia de objeto adequadamente, sem perder silenciosamente seus modificadores. Registrar limitações de dependências externas. Observar que `revert_committed_operation` atribui valores de visibilidade salvos e depois força `hide_viewport=False`; decidir entre restaurar estado original e tornar alvo acessível de forma explícita.

Bloquear reversão do pai quando existirem operações filhas confirmadas e também tratar prévias filhas ativas. Validar status COMMITTED antes de reverter corte. Remover Prévia não deve descartar backup de uma operação confirmada selecionada acidentalmente. Atualizar esquema do registro se necessário, com migração para arquivos salvos da 0.8.6.

Testes existentes não provam todos os relatos: `test_t07_undo_redo_stability` apenas translada um cubo, tenta três Undo/Redo quando poll permite e verifica existência; não gera prévia nem repete sua atualização. `test_t15_export_and_reimport_concave_part` exporta uma caixa e verifica arquivo não vazio, sem reimportar. Fortalecer esses testes com o cenário anunciado e asserções geométricas reais.

## 5. Etapa B — cortes por Loop confiáveis

Reproduzir primeiro com encaixes desligados, identificando se o erro aparece na captura, flood fill, cortador, booleano ou fechamento. Somente depois testar encaixes. Registrar volumes A/B antes e depois dos encaixes, arestas abertas/não-manifold, faces degeneradas, componentes e direção adotada.

Para contorno planar, construir tampas com triangulação que preserve domínio e concavidade; não usar leque ou convex hull. Validar ciclo simples, interseções do contorno e triângulos degenerados antes do booleano. Uma concavidade válida não deve ser preenchida por uma ponte. O mecanismo de faces do modo Material pode inspirar a solução, mas não deve ser copiado sem considerar diferenças entre captura de loop e captura de região.

Para contorno não planar, não projetar silenciosamente. Reutilizar o comportamento de destaque/fechamento existente quando for geometricamente válido e informar limites. Se a extrusão não suportar aquela superfície, cancelar antes de alterar a cena. Suporte geral a furos e múltiplos loops fica para etapa posterior; uma seleção com furo deve ser rejeitada claramente na captura enquanto não houver suporte.

O flood fill precisa encontrar uma região própria, sem atravessar arestas ausentes. Se A ou B for vazio, não publicar. O fallback de espessura disponível de 1000 mm em `analyze_loop_region` deve ser substituído por diagnóstico “espessura não determinada” ou cálculo confiável. Pontos sobre a borda e centroide fora de uma região côncava não são amostras interiores confiáveis. Escalar epsilons para unidades físicas e usar pontos internos válidos. Não corrigir membranas com tolerâncias grandes que eliminem detalhes legítimos.

**Critério geométrico:** nas amostras sem folga e sem encaixes, volumes positivos, peças estanques, sem interseção volumétrica A/B e união equivalente ao volume original dentro de tolerância documentada. Testar também fidelidade da silhueta; uma malha manifold pode representar o sólido errado.

### B2. Plano alinhado à face: impedir lâmina coplanar

Referências adicionais [P02](imagens/P02_alinhar_face_antes.png) e [P03](imagens/P03_alinhar_face_pelicula.png). O usuário alinha à face do corpo na base de uma saliência amarela, buscando separar somente a saliência. A prévia explodida mostra uma superfície branca do tamanho do topo do corpo junto à peça superior. A imagem mostra o defeito visual; a espessura exata precisa ser medida na malha.

Reprodução mínima: cubo fechado com ressalto unido, faces do ressalto com outro material; selecionar uma face do topo do corpo ao lado do ressalto em Edit Mode, alinhar por Face, gerar prévia sem encaixes e explodir. Registrar origem/normal do plano e distâncias assinadas dos vértices das faces do topo; medir se há lâmina volumétrica fina, faces duplicadas de espessura zero ou ambas. O novo ZIP já contém botões de remoção/reversão e a coleção de backups mostrados nos screenshots; manter essas funções durante a correção.

No operador `CHEST_OT_splitter_align_plane`, validar que `context.edit_object` é o alvo e que existe face ativa válida (ou fallback não ambíguo de uma única face selecionada). Não retornar FINISHED com “Plano alinhado” quando nenhuma operação aconteceu. Se a face não for planar, avisar que uma orientação média não define uma base exata. Preservar a transformação correta da normal e conferir leitura da normal do guia sob escala/parent.

No corte, definir tolerância de coplanaridade em mm e converter para world-space Blender units antes de classificar vértices/faces e usar bisect. Tornar a decisão consistente nos dois lados. **Não duplicar automaticamente uma superfície exterior coplanar em A e B.** Classificar as faces no plano pelo lado sólido adjacente e pela superfície exterior original. No exemplo, o topo exterior do cubo deve ficar com o corpo; a peça amarela recebe uma tampa somente no seu perímetro de base, sem um quadrado branco externo a esse perímetro.

Restringir o fechamento às bordas realmente geradas pelo corte e ao domínio efetivo de contato. O fallback de `cap_open_cut_boundaries` não deve preencher aberturas pré-existentes ou criar tampas sobre faces coplanares já presentes. Detectar duplicatas e degenerações dentro da tolerância apropriada, sem apagar faces de base necessárias. Garantir orientação, materiais e conservação de volume/silhueta.

Não deslocar automaticamente todo plano por um epsilon arbitrário para esconder a lâmina: isso pode arrancar uma camada real do corpo ou cortar a saliência. Se oferecer “Deslocamento do plano (mm)”, começar em zero, mostrar o valor no painel e na linha de corte, e tratá-lo como decisão explícita do usuário. A implementação deve resolver o caso nominal de alinhamento exato sem exigir tentativa e erro.

Alinhar por Face define posição/orientação de um plano infinito; não seleciona apenas uma cor ou restringe o corte ao tamanho da face. Se houver várias saliências acima desse plano, o método pode separar todas. Para extrair exclusivamente uma região, indicar Loop/Material. Essa distinção não justifica a lâmina branca no exemplo: a superfície coplanar precisa de tratamento geométrico correto.

## 6. Etapa C — seleção e extração por Material

Cor identifica uma região; não determina sozinha o volume a destacar. Regiões desconexas do mesmo material continuam independentes. O modo Loop segue o contorno capturado e pode incluir faces brancas dentro dele: isso é esperado, não uma seleção por cor.

### C1. Seleção e atualização

Usar BMesh vivo em Edit Mode para face ativa, material e conectividade. Recalcular a lista após atribuir materiais, editar topologia ou trocar alvo; manter identificação da região pela face de referência quando possível, em vez de confiar no número anterior da lista. Mostrar quantidade de faces e destacar a área efetiva. Preservar rejeição de multiobjeto e seleção ambígua. Se não houver face ativa e existir uma única face selecionada, manter o fallback já disponível.

### C2. Comportamentos explícitos

Manter separação direta de componente fechado. Para regiões superficiais, acrescentar opções **Extrair com profundidade** e **Destacar saliência pela base**. Um AUTO pode sugerir comportamento, com explicação e possibilidade de escolha; não deve substituir a decisão sem mostrar o resultado.

Extrair com profundidade: inicialmente garantir regiões planares válidas, prismas fechados e profundidade fisicamente limitada. Superfícies dobradas não devem ser tratadas como uma superfície plana pela média de normais.

Destacar pela base: obter o perímetro da região de saliência, verificar base fechada e planar, separar o volume completo acima dessa base e fechar ambos os lados. Reaproveitar validação do Loop quando adequado, sem sobrescrever a captura manual do usuário. Bases abertas, superfícies ambíguas ou interfaces curvas sem suporte devem produzir instrução clara de usar Loop/Sólido.

### C3. Geometria versus material

Investigar a faixa branca da peça extraída: pode ser uma face de fechamento com material do corpo, uma camada geométrica incorreta ou ambos. Corrigir a geometria primeiro. Depois permitir material da interface (“Manter origem” ou “Material da peça extraída”), preservando as faces exteriores. Não pintar uma membrana para esconder o defeito.

## 7. Etapa D — encaixes e contrato da interface

### D1. Interface real, compartilhada pelos métodos

Gerar `CutInterface` a partir das superfícies efetivas de contato, em world space, com origem válida inclusive zero, normal A→B, base U/V ortonormal, contornos externos/furos, área, dimensões e planicidade medida. Para uma interface com várias regiões planas, identificar cada região e permitir escolher qual recebe encaixes. Não declarar uma interface curva planar por conveniência.

Material precisa abandonar eixos fixos e contornos vazios. Sólido precisa identificar as faces novas de contato, distinguindo-as do exterior original. **Não habilitar Sólido/Material apenas removendo os bloqueios da interface e do operador**: isso produziria encaixes com informações geométricas inadequadas.

### D2. Posição e validação

Manter as distribuições existentes e acrescentar “Ajustar posições à área válida” com resultado determinístico. Para região côncava, buscar ponto com distância útil das bordas; verificar o perfil inteiro da cavidade, furos, margem e colisões entre encaixes. O centro da caixa pode servir de tentativa inicial, nunca como prova de validade. Não reduzir silenciosamente a quantidade pedida.

No erro mostrar causa específica: posição fora da área, margem insuficiente, colisão ou profundidade acima da espessura receptora. Validar o lado fêmea e a parede real ao longo da direção de inserção; a profundidade de extração de 5 mm não limita automaticamente todos os encaixes de 13 mm, porque depende do lado receptor e da geometria.

### D3. Ampliação para Material e Sólido

Habilitar inicialmente encaixes em interfaces **planas, identificadas e validadas**. Material: base planar de saliência e extrações planares. Sólido: interface planar escolhida pelo usuário quando houver mais de uma. Para curva ou interface não determinada, exibir motivo e opção de corte sem encaixes. Encaixes gerais orientados sobre superfícies curvas ficam fora desta entrega.

Incluir propriedades novas nas assinaturas, presets quando aplicável, persistência e traduções. Validar espessura antes de fazer booleanos de pinos; garantir união real do macho e ausência de perfuração da fêmea.

## 8. Etapa E — folga entre peças em Material e Sólido

Separar a **folga da interface entre peças** da folga lateral e de fundo dos pinos. Controles em mm: “Folga entre peças” (zero por padrão) e “Aplicar em: Peça extraída / Cavidade / Ambos”. Para folga total g, deslocamento unilateral g ou bilateral g/2 por superfície; explicar que uma caixa terá redução total 2g na largura quando cada parede oposta for reduzida g.

Alterar exclusivamente superfícies de contato. Preservar exterior do modelo e detalhes fora da interface. Não escalar globalmente a peça ou o cortador: isso produz folga diferente em pontos diferentes e altera medidas não relacionadas ao encaixe. Folga zero deve reproduzir o corte nominal anterior.

Implementar primeiro casos com deslocamento controlado e verificável: extrações planares, prismas/caixas e cortadores com superfícies simples suportadas. Deslocar uma interface pode abrir junções com faces externas: reconstruir essas junções mantendo sólido fechado. Offset robusto de sólidos arbitrários e superfícies curvas exige tratamento próprio; não oferecer a opção como universal antes de validar.

Aplicar folga da interface antes dos encaixes e recalcular domínio/espessura após a alteração. Medir separação real em pontos de contato; não usar volume como prova de folga. Com folga, a conservação exata de volume deixa de ser requisito; registrar volume removido deliberadamente.

## 9. Etapa F — visualização do plano e do loop

### F1. Loop

Exibir somente no modo Loop, com opção “Mostrar contorno”. Ao mudar para outro modo, esconder automaticamente e conservar a captura válida; ao voltar, reexibir conforme a opção. Não destruir seleção original só para desenhar. Em Edit Mode, ler coordenadas atuais. Respeitar visibilidade do alvo e view layer; inválido/deletado significa não desenhar.

Salvar e restaurar blend, depth test, depth mask se alterado e largura de linha em `finally`. Usar getters disponíveis na versão mínima, sem presumir que redefinir largura para 1 restaura o estado. Escolher shader de linha apropriado às versões suportadas e validar DPI/backends.

### F2. Plano

Adicionar **Mostrar plano**, **Mostrar linha de corte** e **Opacidade do plano**. Proposta visual: preenchimento laranja, opacidade inicial 15%, linha de interseção contrastante; manter cores distinguíveis dos materiais da peça. O retângulo orienta visualmente um corte planar infinito, não limita a área cortada. Explicar essa distinção no tooltip.

A linha representa a interseção do alvo real com o mesmo plano usado pelo algoritmo, incluindo várias ilhas e furos. Para triângulos coplanares e tangências, definir tratamento explícito e deduplicar segmentos. Plano fora da peça deve mostrar “O plano não intersecta o objeto”. Não usar a linha do bounding box como se fosse o corte real.

Atualizar ao mover/rotacionar guia ou alterar alvo, antes de gerar a prévia. Compartilhar a leitura de origem/normal com `read_plane_geometry`; usar malha avaliada quando o corte também considerar modificadores. Considerar matriz mundial, escala não uniforme e normal correta. Em Edit Mode, usar estado vivo coerente com o corte.

O callback GPU apenas desenha dados de um cache. Marcar cache sujo nos eventos; recomputar fora de callbacks sensíveis com atualização limitada, inicialmente intervalo alvo de 100–150 ms, sujeito a medição. Não executar booleano por frame nem manter objetos avaliados entre ciclos do depsgraph. Guardar coordenadas independentes. Se houver atraso em malha pesada, indicar atualização em vez de mostrar uma linha antiga como válida.

Visibilidade por modo: Plano mostra suas indicações; Loop mostra seu contorno; Sólido e Material escondem ambos. Opções visuais não invalidam o corte. Overlays não entram em exportação, render ou geometria final e não criam entradas de Undo a cada movimento. Limpar caches/handlers em mudança de arquivo, Undo/Redo, exclusão e desativação.

## 10. Referências visuais do usuário

As imagens originais foram copiadas com nomes legíveis na pasta `imagens`. Use-as para reproduzir os casos; não copie geometrias erradas como objetivo visual.

| Imagem | Leitura e reprodução |
|---|---|
| [L01](imagens/L01_loop_membrana.png) / [L02](imagens/L02_loop_sem_encaixes.png) | Peça amarela côncava com área branca atravessando a abertura; reproduzir sem encaixes e inspecionar triângulos/booleano. |
| [L03](imagens/L03_loop_encaixe_fora.png) / [L04](imagens/L04_loop_profundidade.png) | Falha de posição/margem em região côncava; separar domínio inválido de espessura insuficiente. |
| [L05](imagens/L05_loop_volume_nulo.png) | Região verde e volume B nulo; registrar captura/seed/topologia e falha antes dos encaixes. |
| [L06](imagens/L06_loop_nao_manifold.png) | U vermelho com erro de arestas não-manifold; repetir sem conectores. |
| [L07](imagens/L07_loop_contorno_e_cores.png) | Contorno captura áreas brancas; distinguir seleção por loop e seleção por material. Um contorno externo simples não exclui o centro de um anel. |
| [L08](imagens/L08_loop_visivel_no_plano.png) | Destaque ciano permanece ao escolher Plano; deve desaparecer nesse modo. |
| [M01](imagens/M01_material_saliencia.png) / [M02](imagens/M02_material_camada.png) | Saliência amarela, extração superficial e núcleo branco remanescente; comparar extração por profundidade e destaque pela base. |
| [M03](imagens/M03_material_area_lateral.png) | Região lateral do mesmo material; verificar lista e seleção por face. Não prova seleção errada por si só. |
| [P01](imagens/P01_plano_guia.png) | Guia de plano só com borda; acrescentar preenchimento discreto e contorno exato da interseção. |
| [P02](imagens/P02_alinhar_face_antes.png) / [P03](imagens/P03_alinhar_face_pelicula.png) | Alinhamento à face na base da saliência; peça superior leva uma lâmina branca. Medir coplanaridade, classificação de faces e tampas. |

## 11. Ordem de implementação e escopo

1. **Estado e recursos:** B02–B04, A1–A4; diagnóstico reproduzível e regressão de preservar prévia.
2. **Cortes:** Plano alinhado à face sem lâmina coplanar, Loop simples/concavidades, Material planar e destaque de saliência; sem conectores para isolar falhas.
3. **Interfaces e conectores:** contrato real, posição em concavidade, validação de espessura e habilitação condicionada em Material/Sólido.
4. **Folga:** superfícies de contato suportadas, medição física e preservação exterior.
5. **Visualização:** visibilidade do loop, preenchimento e linha de interseção do plano, cache e desempenho.
6. **Integração:** traduções PT/EN, migração, exportação, teste em instalação limpa e pacote 0.8.7.

Não prometer que todo esse escopo cabe em dois dias. Se houver dificuldade, a 0.8.7 deve estabilizar os métodos e deixar recursos não validados desabilitados com motivo claro. Adiar offset universal, encaixes curvos, múltiplos contornos de Loop e novas articulações. Isso não dispensa investigar os bugs já relatados.

## 12. Testes de aceitação obrigatórios

Executar testes geométricos em Blender headless quando possível e testes de viewport/Undo em sessão interativa. Cobrir Blender 4.2 declarado mínimo e a versão usada pelo usuário; registrar número exato e backend. Cada teste deve exercitar comportamento e conferir resultado, não apenas localizar nomes de funções.

| Teste | Ação | Resultado esperado |
|---|---|---|
| T01 | Instalar pacote limpo | Manifesto e interface 0.8.7, sem erro de registro. |
| T02 | Selecionar 3×3 faces e capturar perímetro | Somente borda externa, face-semente correta. |
| T03 | Seleção de faces com furo/ilhas | Rejeição explicada enquanto não suportada. |
| T04 | Capturar e alterar conectividade com mesmas contagens | Captura invalidada antes do corte. |
| T05 | Mover vértices em Edit Mode | Overlay atualizado e análise recalculada. |
| T06 | Loop → Plano → Loop | Visibilidade correta, captura preservada se válida. |
| T07 | Extrair U/L sem conectores | Sem ponte/membrana, A/B sólidos e silhueta correta. |
| T08 | Loop inválido e seed inadequada | Cancelar sem substituir prévia válida. |
| T09 | Profundidade excede espessura ou espessura indeterminada | Diagnóstico específico; sem fallback permissivo. |
| T10 | Plano com 1/2/3/4 encaixes em área suficiente | Quantidade exata e sólidos válidos. |
| T11 | Plano com furo e várias ilhas | Nenhum encaixe fora do domínio/furos. |
| T12 | Encaixe automático em U | Posição válida quando viável; falha clara quando inviável. |
| T13 | Inverter macho A/B | Direção correta e espessura validada no receptor. |
| T14 | Extrair Material planar côncavo | Região correta, sem película. |
| T15 | Destacar saliência de Material | Volume inteiro destacado pela base; sem núcleo indevido. |
| T16 | Pintar outra ilha em Edit Mode e usar face | Lista e índice atualizados no alvo correto. |
| T17 | Múltiplos objetos em Edit Mode / objeto de prévia | Rejeição segura, sem selecionar região de outro objeto. |
| T18 | Encaixes em Material/Sólido planar | Interface real, furos/espessura corretos. |
| T19 | Interface curva sem suporte | Opção explicada/desabilitada; corte básico preservado. |
| T20 | Folga zero | Geometria nominal equivalente à base validada. |
| T21 | Folga unilateral e bilateral conhecida | Distância g medida, exterior preservado, sem faces abertas. |
| T22 | Folga + encaixes | Domínio atualizado, medidas dos pinos preservadas. |
| T23 | Mover apenas cortador / editar malha sem mudar contagens | Prévia desatualizada e confirmação/exportação bloqueadas. |
| T24 | 20 ciclos Undo/Redo e atualização | Sem crash, referências reconciliadas, original recuperável. |
| T25 | Injetar falha após aquisição de cada recurso | Sem temporários restantes; prévia anterior íntegra. |
| T26 | Gerar/atualizar 50 vezes | Sem crescimento contínuo de datablocks; observar memória. |
| T27 | Plano movido/inclinado, alvo com modificador | Linha coincide com corte efetivo. |
| T28 | Plano fora, tangente e coplanar | Indicação coerente, sem linhas falsas persistentes. |
| T29 | Desativar, reativar, trocar arquivo e viewport | Sem handlers duplicados nem estado GPU vazando. |
| T30 | Escalas de cena 1 / 0,01 / 0,001 e escala não uniforme | Mesmos valores físicos em mm. |
| T31 | Exportar STL/3MF após vista explodida | Montagem/dimensões corretas, nenhuma geometria de overlay. |
| T32 | Restaurar original e operações de recuperação disponíveis | Original/cópia de trabalho preservados, sessão coerente. |
| T33 | Prévia pesada e movimento contínuo do plano | Latência medida, cache coerente, sem booleanos por frame. |
| T34 | PT e EN, arquivo salvo da 0.8.6 | Migração e tooltips compreensíveis, sem perda de objetos. |
| T35 | Alinhar plano ao topo de cubo com saliência | Peça superior só com saliência e tampa da base, sem quadrado branco exterior. |
| T36 | Mesmo alinhamento com rotação/escala não uniforme e escala de cena variada | Resultado físico consistente, sem lâmina devido a arredondamento. |
| T37 | Alinhar por Face sem face válida ou no alvo errado | CANCELLED e mensagem específica, sem falso sucesso. |
| T38 | Topo coplanar com várias saliências e malha com abertura pré-existente | Plano mantém seu domínio global; não fecha arbitrariamente abertura original. Entrada não imprimível é diagnosticada. |
| T39 | Duas operações com prévias coexistentes; remover uma | Outra operação e objetos do usuário permanecem intactos. |
| T40 | Falha durante substituição de snapshot | Backup/registro/prévia anteriores preservados. |
| T41 | Selecionar resultados de duas operações | Resolução não ambígua ou cancelamento explicado. |
| T42 | Apagar snapshot e criar objeto com mesmo nome | Objeto substituto não é apagado nem usado como backup. |
| T43 | Apagar alvo com modificadores e reverter | Restauração cumpre contrato; sem perda silenciosa de configuração. |
| T44 | Pai com corte filho confirmado ou prévia filha | Reversão não deixa filho órfão nem apaga resultados indevidos. |
| T45 | Build sem Blender e a partir de outra pasta | Erro acionável sem caminho fixo; raiz resolvida pelo script. |
| T46 | Build validado e revisão do README | ZIP só de produção; versão coerente; README sem emojis e sem promessas não comprovadas. |

Medir volume em mm³, áreas e distâncias em unidades físicas; tolerâncias devem depender da escala física e da precisão numérica, com valores registrados. Conservação de volume só vale antes de folga/encaixes. Registrar falhas conhecidas e nunca marcar como aprovado um teste não executado.

## 13. Referências técnicas oficiais

As referências orientam a implementação; confirmar disponibilidade das APIs na versão mínima 4.2 e na versão de teste. Não usar documentação de desenvolvimento como justificativa para abandonar compatibilidade.

- [BMesh — leitura em Edit Mode e propriedade das malhas](https://docs.blender.org/api/5.0/bmesh.html): BMesh vivo, atualização e limpeza de BMesh criado pelo script. Não liberar o BMesh pertencente ao Blender.
- [Depsgraph — exemplos de malha avaliada](https://docs.blender.org/api/5.0/bpy.types.Depsgraph.html): criar e liberar malhas temporárias pelo objeto avaliado correspondente.
- [GPU State](https://docs.blender.org/api/current/gpu.state.html): consultar/restaurar estados de desenho, inclusive depth test e largura de linha.
- [Handlers](https://docs.blender.org/api/current/bpy.app.handlers.html): validar assinatura de callbacks, registro e cuidados com mudanças em dados.
- [SpaceView3D](https://docs.blender.org/api/current/bpy.types.SpaceView3D.html): ciclo de vida dos draw handlers.
- [Boolean Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/booleans.html): pressupostos e limites de operações booleanas.

As quatro primeiras rotas 4.2 consultadas diretamente não puderam ser recuperadas pelo serviço de pesquisa nesta revisão; por isso, nenhuma disponibilidade específica de versão é apresentada como testada. O implementador precisa validar no Blender mínimo.

## 14. Organização do repositório e alterações já preparadas

O pacote inclui `repositorio_organizado_0.8.6/`: uma cópia de trabalho organizada da base atual, **não uma implementação da 0.8.7**. Os 16 módulos de produção em `src/`, a entrada e o manifesto foram preservados byte a byte. Alteraram-se README, documentação e ferramentas de desenvolvimento. Use essa cópia ou aplique suas alterações equivalentes ao checkout real; não substitua a pasta `.git` do repositório existente.

| Local | Regra |
|---|---|
| Raiz | README, CHANGELOG, LICENSE, manifesto, entrada e .gitignore. |
| src/ | Módulos Python de produção; manter estrutura plana durante estabilização. |
| tests/ | Suítes atuais, runner e reproduções; scripts exploratórios não são automaticamente regressões aprovadas. |
| scripts/ | `build.py` e ferramentas de desenvolvimento. |
| docs/ | Arquitetura atual curta e guias vigentes. |
| docs/archive/0.8.6/ | Planos anteriores e arquivos de referência, preservados para consulta. |
| dist/ | Apenas saída local gerada, ignorada pelo Git. |

Nesta cópia, os ZIPs antigos da raiz, `.git` e `scratch` não foram incluídos. Os originais permanecem no arquivo recebido. No checkout real, preservar histórico Git, usar tags/releases para versões e guardar experimentos úteis antes de retirar resíduos. Não apagar arquivos rastreados sem entender a função. Não usar `git reset --hard`, reescrever histórico ou alterar remotos como parte desta limpeza.

README foi reescrito em aproximadamente uma página: objetivo, compatibilidade declarada, instalação, fluxo curto, comandos e limites. Sem emojis, linguagem promocional exagerada ou árvore extensa de arquivos. A versão informada é 0.8.6, coerente com o código; mudar para 0.8.7 apenas quando implementada. O README antigo está preservado como `.txt` no arquivo histórico. Na entrega final, garantir que todo arquivo cujo nome seja README tenha texto sem emojis. Explicações longas pertencem a docs, e não à página inicial.

O build antigo estava fixado no Blender 5.2 em Windows, removia `dist` inteiro, gravava ZIP na raiz e copiava automaticamente para Downloads. O novo `scripts/build.py` aceita `--blender`, `BLENDER_BIN` ou PATH, prepara staging isolado em `dist`, exige arquivos essenciais, chama build/validate oficiais e inspeciona conteúdo permitido. Só promove o arquivo novo depois da validação, sem apagar outros releases locais. Não usa `.blenderignore` como garantia de exclusão: o staging explícito define o conteúdo. Veja [comandos oficiais](https://docs.blender.org/manual/en/4.5/advanced/command_line/extension_arguments.html).

O runner permanece em `tests/run_all_tests.py`, conserva as mesmas 20 suítes selecionadas e aceita resolução portátil do executável. Resolve paths pela raiz do repositório e executa cada processo com cwd correto, mantendo falha no código de saída. Não acrescentar automaticamente testes exploratórios que foram feitos para reproduzir defeitos antigos; avaliá-los e convertê-los em regressões com comportamento esperado.

Foram conferidos sintaxe, igualdade dos módulos de produção, links internos das imagens, conteúdo do staging e sua allowlist. Build/validate oficial e as suítes continuam dependentes de Blender e não foram executados aqui. Não apresentar essa organização como prova de que os bugs estão corrigidos.

Depois de estabilizar, reduzir gradualmente `operators.py`: primeiro separar estado/assinatura da sessão e recursos temporários; depois operadores por área se isso melhorar manutenção. Manter nomes de operadores, propriedades serializadas e imports compatíveis ou adicionar migração. Evitar muitas subpastas de um arquivo ou refatoração geral junto ao primeiro conserto geométrico.

## 15. Instruções finais ao Gemini Pro

Leia este documento inteiro e a base incluída antes de editar. Compare a versão instalada se houver código posterior. Apresente diagnóstico por requisito, preserve recursos existentes e implemente por etapas com testes. Não reescreva a extensão inteira, não remova validações para fazer um caso passar e não mascare geometria defeituosa alterando materiais.

Não declare crash resolvido com base apenas em `try/except`: falha nativa pode encerrar o processo. Não declare sólidos válidos apenas pelo volume positivo. Não habilite recursos sem contrato geométrico e aceite correspondente. Registre qualquer limitação e explicação mostrada ao usuário.

Entregue ZIP instalável **0.8.7**, código fonte, changelog coerente, fixtures `.blend` mínimos, scripts de testes realmente incluídos e relatório de execução com versão do Blender, comandos, resultados e casos não executados. Atualize manifesto, metadados de versão existentes e README de forma consistente. O lançamento comercial depende de comprovar estabilidade e resultados nas geometrias suportadas, não do número da versão.
