# 0.9.7 — fechamento natural e folga em contornos curvos — 2026-11-07

- Contornos orgânicos por loop tentam fechar diretamente sobre o contorno, com grade quando válida, antes de recorrer ao fechamento antigo com degraus. Contornos ortogonais em três direções preservam o solver de degraus, incluindo folgas e transformações que já funcionavam.
- O fechamento natural verifica contenção e coincidência das tesselações visíveis das duas peças; grades incompatíveis são repetidas com triangulação. Bases não planas com um contorno de material compartilham esse caminho, mantendo a orientação para usar profundidade quando o fechamento não cabe no sólido.
- Quando a folga escalar não pode ser construída por deslocamento da superfície natural, tenta uma lâmina local fechada, Solidify Complex e Boolean Exact, preservando o exterior fora da faixa cortada. A lâmina é validada por distâncias bidirecionais no contato comum e raios normais. Contornos não suportados continuam sendo recusados com a prévia anterior preservada.
- A prévia informa a faixa amostrada de folga no contato e a faixa incluindo bordas. A tolerância da nova lâmina é o maior entre 0,005 mm e 5% do valor solicitado; as bordas além da área de contato têm medição separada e não representam uma promessa de distância uniforme em toda a borda curva. A tolerância anterior de grades permanece inalterada.
- Encaixes em cortes curvos usam uma área plana comum da superfície efetivamente gerada, sem achatar o fechamento inteiro. A tentativa conservadora de grade após a folga continua compartilhada por Loop, Plano, Região inteira, Sólido e Material.
- Corrigida a versão mostrada no painel para acompanhar a versão do pacote.

# 0.9.6 — tentativa de grade em todos os métodos — 2026-11-07

- Prévia de Loop, Plano, Região inteira, Sólido e Material compartilha uma etapa de organização das superfícies criadas, após a folga e antes dos encaixes. Regiões planas compatíveis recebem quads; contornos ímpares, furos e grades incompatíveis preservam a alternativa segura com aviso informativo.
- A reorganização preserva bordas, materiais, marcas de contato, volume e superfície física, verificada por amostragem bidirecional da tesselação. Superfícies curvas do loop mantêm o tratamento da 0.9.5.
- Corrigido fechamento planar com contornos internos: os contornos são triangulados conjuntamente, preservando furos em vez de criar discos sobrepostos.
- Folga sem encaixes verificada nos cinco métodos com zero e 0,1 mm, incluindo distância em cinco pontos da interface e alternativa triangulada. Não altera os valores padrão das folgas.

# 0.9.5 — tampas editáveis por loop — 2026-11-07

- Fechamento direto por loop tenta uma grade de quadriláteros, mantendo o contorno e verificando fechamento, interseções e coincidência das superfícies. Quando a grade não é válida, tenta o fechamento anterior e informa a triangulação em PT/EN sem sinalizar erro vermelho.
- Interfaces e posicionamento de encaixes passam a usar a tesselação da superfície realmente gerada; marcas temporárias da grade não são arquivadas como contatos de cortes anteriores.
- Grades com folga igual nos dois eixos recebem uma verificação amostrada bidirecional de distância, com tolerância de 0,003 mm. Uma grade que falha nessa verificação não é publicada.
- Falhas de compatibilidade entre os planos do contorno informam que não foi possível construir folga uniforme, sem atribuir automaticamente o problema ao tamanho escolhido.
- Spot: o anel central testado fecha com 16 quads por tampa e aceita 0,1 mm. Outros anéis curvos continuam podendo ser recusados; esta versão não garante solução para todos os contornos nem valida montagem física.
- Os demais métodos mantêm seus algoritmos de fechamento. Contornos ímpares, grades muito densas ou geometrias sem grade válida continuam usando a alternativa anterior.

# 0.9.4 — revisão complementar dos avisos — 2026-11-02

- Erros do editor manual de pinos, alinhamento do cortador e exportação passam pela tradução na apresentação, inclusive causas inseridas em avisos bilíngues.
- Mantidos os algoritmos de corte, folga e encaixe.

# 0.9.3 — auditoria de português e inglês — 2026-11-02

- Catálogo ampliado para erros de geometria e estado, incluindo mensagens com medidas e causas internas. Aviso de reescolha de contato agora usa tradução explícita.
- Preferências e terminologia de prévia/contorno revisadas em português. Verificação cruzada de catálogos, parâmetros, ajuda e erros nos dois idiomas.
- Sem alteração dos algoritmos de corte e folga.

# 0.9.2 — conectores ao trocar alvo — 2026-11-02

- Região inteira desativa os conectores ao mudar de alvo, exigindo preparar o contato da nova peça. O botão permite desligar um estado ativo herdado, mesmo sem contato escolhido.
- Margem de borda padrão: 0,4 mm; valores já salvos são preservados.
- Geometria da folga mantida; deformação exterior parcial permanece em avaliação no registro GAP-003.

# 0.9.1 — Região inteira e folga em múltiplos contatos — 2026-11-02

- Reconstrução conservadora de regiões convexas com contatos unidos em direções diferentes, validada por contenção, superfície selecionada e conservação de volume. Operações locais preservam escala, rotação e espelhamento.
- Contornos com projeção ambígua não geram mais um fechamento silenciosamente diferente da região pretendida; são recusados quando a reconstrução não pode ser certificada.
- Folga aplicada simultaneamente às normais de todos os contatos, com interseção de restrições nos cantos. Transições estreitas usam corte validado e verificações de superfícies sem afastamento.
- Mantidos os modos por Base, Profundidade, Material e cortador sólido. Novas regressões medem folga em cada contato, incluem peças côncavas e transformadas e preservam a malha de entrada.
- A versão é destinada aos testes finais do usuário; geometria e encaixe físico ainda dependem da impressão. Casos que não admitem reconstrução segura continuam sendo recusados.
- Preservação dos materiais e das identidades dos contatos em cortes sucessivos; preparação de pinos corrigida para faces poligonais com triangulações diferentes.

# 0.8.35 — área comum dos pinos e offsets pequenos — 2026-11-02

- A área para posicionar pinos é reconstruída a partir das faces finais da superfície de corte, após o reparo de microarestas, preservando ilhas e furos. Não reutiliza referências de arestas do bisect invalidadas pelo reparo.
- Removido o fallback que interpretava extremos de arestas sem ordem como um polígono. Contornos inválidos agora geram erro explícito.
- Cortes por plano completo calculam a interseção das seções finais A e B, considerando folga e inversão. A superfície mais larga do pé não oferece posições sem contraparte na placa vertical. Furos e ilhas são preservados, com simplificação apenas abaixo de 0,0001 mm no domínio do contato.
- Remoção de lâminas usa coincidência numérica do plano, sem confundir proximidade de 0,05 mm com coplanaridade. Offsets de 0,03 mm deixam de remover a face vizinha do pé.
- Regressão da Placa Chest: pinos à esquerda, no centro e à direita aceitos; prévia com três pinos e ambas as peças fechadas. Testes adicionais de folga, inversão, furos, ilhas, transformação e fluxo manual.
- Validação focada: 41 testes aprovados, incluindo 48 combinações adicionais de offset/folga, inversão e destino da folga na placa real.

# 0.8.34 — recuperação de interfaces em modo de edição — 2026-10-30

- Corrigido IndexError ao gerar prévia em Edit Mode num restante que já possui atributos de interfaces anteriores. A leitura usa uma cópia da BMesh de edição, incluindo geometria e marcações consistentes, em vez de indexar arrays RNA vazios.
- A mesma leitura se aplica aos ancestrais em edição. Marcas já existentes, seleção, modo de edição e geometria são preservados; malhas temporárias são liberadas, inclusive no caminho de cache.
- Mantidas as restrições de procedência do histórico, de malhas compartilhadas em edição e de espessura real da parede.

# 0.8.33 — folga uniforme nas paredes do encaixe — 2026-10-30

- Corrigido o afunilamento da base profunda nos cortes por Contorno e Material. A folga remove uma faixa completa das paredes de inserção, com ombro junto ao relevo original preservado.
- Folgas lateral e de fundo independentes, incluindo fundo zero. Material na base passa a respeitar a folga de fundo separada; a profundidade não limita indevidamente a folga lateral dos cortes prismáticos.
- Validação de espessura da cavidade considera a profundidade adicional da folga. Preservadas as faces, materiais e UVs do relevo nas operações de remoção.
- Verificação dos quatro modos de corte, com 16 suítes aprovadas e 105 cenários dimensionais dedicados à folga, incluindo os três destinos e cortes passantes.

# 0.8.32 — interfaces preservadas em cortes sucessivos — 2026-10-30

- A triangulação de entrada remapeia os atributos de faces splitter_* para cada triângulo. Não perde as marcações de interfaces, inclusive em polígonos com mais de três vértices.
- Região inteira e regiões com aberturas acumulam os contatos anteriores em splitter_previous_interface antes de marcar o contato do novo corte. Não reutilizam esses contatos antigos como área atual para pinos.
- Ao gerar a prévia ou preparar encaixes, a extensão recupera marcações legadas somente por correspondência de superfície com alvos/snapshots da cadeia de operações do próprio objeto. Corrige o caso do bigode com espessura incorreta de 0,02 mm, sem mover vértices ou mudar materiais e seleção. Sem histórico elegível, não relaxa a checagem de parede.
- Recuperação respeita Edit Mode e separa dados quando a malha é compartilhada por outros objetos. Cache considera geometria, transformações e marcações dos ancestrais e é limpo ao carregar/desfazer.
- Mantidos os bloqueios para paredes realmente finas e fechamentos que cruzem a superfície. Nenhuma mudança no editor manual de pinos nesta versão.

# 0.8.31 — fechamento de Região inteira com triângulos herdados degenerados — 2026-10-29

- Corrigido o corte da pata de 405 faces: triângulos quase colineares gerados pela triangulação de um polígono do restante são saneados em uma cópia candidata, sem alterar o alvo nem a seleção.
- O reparo é aceito somente se preservar as tampas exatas, superfície, áreas por material, limites e volume dentro das tolerâncias físicas existentes. Tampas degeneradas continuam sendo recusadas. Mantidas as validações finais de fechamento, componentes, cruzamento e contenção.
- Reparos rejeitados descartam a cópia sem invalidar referências das faces originais. Falhas por degenerescência passam a ter mensagem própria em português e inglês, em vez de sugerir somente ajuste da seleção.

# 0.8.30 — cortes por material e histórico — 2026-10-29

- Profundidade não depende de uma tentativa de fechamento direto para analisar a região. Corrige o contorno do gato com desvio de 0,30 mm.
- Relevos com projeção saliente usam a união das projeções de todas as faces selecionadas. Preserva o bigode completo sem fechar sua concavidade com um casco convexo.
- Medição de espessura distingue interfaces de cortes anteriores da parede externa. Corrige os 0,04 mm encontrados ao cortar o bigode após separar o nariz. Mantidos os bloqueios de parede fina real, contornos inválidos e peças abertas.
- Alvos intermediários gerados pela extensão passam à coleção Histórico de cortes. Migração dos alvos antigos ocultos ao abrir a cena; não apaga objetos, não altera backups e mantém reversão. O olho volta a controlar a visibilidade desses intermediários.
- Nomes curtos numerados para novas peças e restantes; os nomes manuais viram a referência dos próximos resultados. Objetos antigos não são renomeados em massa.

# 0.8.29 — idiomas e seleção do cortador — 2026-10-25

- Seletor de cortador exclui backups internos; revisão de traduções e auditoria de catálogo.

# 0.8.28 — painel do Loop com sequência estável — 2026-10-24

- Seletor dos quatro tipos do Loop permanece no topo, na mesma ordem, incluindo Região inteira. Elimina a mudança de posição ao trocar de tipo.
- Painel organizado em escolha do tipo, seleção/captura e ajustes/prévia, com explicação curta de cada tipo e Editar Alvo disponível em todos. Mantém apenas controles pertinentes abaixo do seletor.
- Manual do Loop explica seleção por faces, contorno, face de referência, Região inteira, Pela Base, Profundidade, Automático e encaixes. Incluído no guia rápido distribuído.
- Sem mudanças nos cálculos de corte, geometria, materiais, encaixes ou folgas.

# 0.8.27 — material uniforme na região inteira — 2026-10-24

- Região inteira no corte por Material passa a mostrar a mesma opção Material da Interface dos modos Pela Base e Profundidade.
- Material da Peça Extraída colore toda a parte A com o material escolhido, incluindo fechamentos, apoio plano, transições, pinos e paredes dos furos. A atribuição é reaplicada após as booleanas dos encaixes.
- Manter Origem conserva a atribuição anterior; corte por faces/Edge Loop e materiais do corpo restante permanecem independentes. Sem alteração de coordenadas, topologia, dimensões ou folgas.

# 0.8.26 — regiões inteiras e contatos planos para montagem — 2026-10-24

- Região inteira passa a ser um tipo de corte em Material e Edge Loop. No Loop aceita faces selecionadas ou contorno fechado. Remove Fechar região da lista principal. Material continua separando a região pela cor sem exigir captura adicional.
- Para pinos, agrupa triângulos adjacentes em áreas amplas, avaliando o desvio contra um plano comum. Preparar área plana modifica somente a interface interna e cria superfícies complementares nas duas peças, com transição para o contorno original. Mantém a superfície exterior, sem escalar a pata.
- Todos os pinos compartilham a mesma direção de inserção, perpendicular à área preparada. Recusa contatos sem direção comum, travas locais e colisões encontradas em seis posições amostradas de retirada do corpo. A verificação é discreta, não uma prova contínua de montagem.
- Folga entre peças aplicada fisicamente na peça, cavidade ou ambas; mantém o apoio realmente plano e as folgas lateral/fundo dos pinos independentes. Tamanho, distribuição e lado macho continuam ajustáveis.
- Sólido mantém corte, diagnóstico e alinhamentos, sem pinos ou atalhos de geração de cascas no painel. O cortador não é sugerido em vermelho como novo alvo.
- Editar alvo oculta as prévias da operação e marca a prévia como desatualizada, evitando sobreposição com o original e confirmação de resultado antigo. Mantém as correções de seleção e descarte da 0.8.25.
- Migra arquivos com Fechar região da 0.8.24/0.8.25 para Edge Loop / Região inteira; exige preparar novamente o contato dos pinos.

# 0.8.25 — seleção e edição após descartar prévia — 2026-10-24

- Corrigido handler modal de alinhamento de vértices do cortador que podia continuar consumindo cliques e Tab depois de gerar/descartar uma prévia. A ferramenta agora é encerrada nas transições de sessão e entrega o primeiro evento seguinte ao Blender, sem reativar o objeto/modo anterior. Uma instância antiga não remove o cabeçalho de uma ferramenta nova.
- Descartar prévia e Editar alvo restauram seleção e visibilidade do alvo, uma rota de coleções da camada atual e a presença do alvo na vista local. Coleções sem relação com o alvo permanecem intactas. Erros de ativação deixam de ser tratados como sucesso silencioso.
- Reverter corte volta a definir o objeto original restaurado como alvo da sessão, evitando referência vazia após apagar a peça que era o alvo atual.
- Encerramento do alinhamento também acompanha troca de alvo, desfazer/refazer, carregamento e desativação da extensão. Limpeza tolera áreas/handlers já removidos.
- Sem alteração dos algoritmos geométricos de corte, fechamento, pinos ou folgas.

# 0.8.24 — fechar regiões inteiras e escolher o contato dos pinos — 2026-10-24

- Novo Fechar região: captura as faces do alvo e fecha cada contorno com os mesmos triângulos nas duas peças. Mantém a superfície exterior e os materiais; não amplia a região e não gera uma segunda parede. Atalho no modo Material: Separar região inteira (sem criar casca), usando a região de cor escolhida.
- Prévia de Região e Sólido permite escolher uma superfície plana real de contato para os pinos, pela lista de áreas ou por uma face selecionada na prévia. O contato escolhido aparece destacado em edição. Pinos automáticos e manuais usam essa interface; trocar a geometria exige reescolher o contato. Os outros contatos permanecem sem pinos.
- Triangulação explícita da superfície visível dos operandos sólidos antes das operações booleanas: evita diagonais diferentes nas duas metades de tampas não planares.
- Prévia bem-sucedida seleciona somente a operação nova. Editar alvo revela o objeto oculto e sai da edição anterior antes de trocar o alvo ativo.
- Validação do fechamento verifica orientação, volume, componentes, singularidades, degenerações, interseções dos fechamentos e amostras de contenção. Mantém a prévia anterior se a atualização falhar. Recusa seleção obsoleta, modificadores ativos e contornos acima de 128 vértices.
- Limite desta etapa: Fechar região e pinos escolhidos na prévia do Sólido requerem folga entre peças de 0 mm. Folgas lateral e de fundo dos pinos continuam configuráveis. Contatos curvos são divididos em facetas planas; não é uma reconstrução suave nem uma garantia de trajetória de montagem ou ajuste na impressora.

# 0.8.23 — inspeção manual de defeitos no cortador — 2026-10-24

- Painel do cortador ganha Localizar problemas, Próximo problema e Atualizar diagnóstico. A localização entra na edição do cortador, revela e enquadra os elementos defeituosos com raio X, sem alterar coordenadas, conexões ou o alvo principal.
- Diagnóstico do cortador distingue bordas abertas, arestas soltas, arestas com mais de duas faces, orientação incompatível, vértices não-manifold, degenerações e arestas de comprimento nulo. Não classifica mais toda aresta não-manifold como aberta. Cortador vazio ou sem volume não recebe status saudável.
- Atualização explícita reexamina edições e modificadores, preservando seleção e modo. Defeitos exclusivos dos modificadores são informados sem mapear índices inexistentes na malha base. Campos do alvo e do cortador permanecem independentes.
- Sem reparo automático, preenchimento de buracos ou alteração dos algoritmos de corte.

# 0.8.22 — criação e edição dos cortadores sólidos — 2026-10-22

- Criar/Focar restaura a visibilidade do cortador e do caminho das coleções, incluindo a vista local. Criar recupera cortador vazio após exclusão de todos os vértices, preserva cortadores editados não vazios e respeita o cortador configurado. Reiniciar atua no cortador atual, inclusive cópias, e restaura escala/orientação da primitiva.
- Painel separa geração a partir de faces/contorno, alinhamento do objeto inteiro e edição da malha. Expõe face do alvo, centro da seleção, cursor, eixos do alvo e X/Y/Z, com apoio e inversão explícitos. Centro da seleção preserva a orientação; referência vazia é recusada. Cursor respeita rotação por quaternion.
- Novo Ajustar só um vértice: dois cliques movem apenas o ponto do cortador até o vértice do alvo, em coordenadas globais, mantendo o cortador em edição. Mover cortador por vértices preserva o comportamento anterior de translação do objeto inteiro. Escape restaura o modo/objeto de origem, sem mover geometria. Malhas compartilhadas são copiadas somente ao confirmar edição de um ponto.
- Das faces selecionadas torna explícita a geração por extrusão já existente, abre parâmetros de profundidade/extensão e usa normais ponderadas por área. Começa pela edição do alvo e recusa seleção sem direção definida. Criação independente preserva o cortador anterior inclusive em falhas.
- Testes cobrem recuperação, foco, reinício, sete alinhamentos com dois apoios e inversão, edição de um vértice, cliques/cancelamento, malhas compartilhadas, desenho do painel e geração por faces. Validado também em pequena seleção da pata do Teste Gato. Esta versão não implementa pinos no Corte Sólido nem fechamento automático de interfaces curvas da pata.

# 0.8.21 — profundidade em regiões de contorno não planar — 2026-10-22

- Extração com profundidade por Loop ou Material passa pelo motor de base volumétrica, sem substituir a profundidade por um fechamento em degraus definido pela largura do contorno. O fechamento em degraus continua disponível no destaque direto sem base adicional.
- Reproduzido no nariz do Teste Gato: 5 e 20 mm agora deslocam o fundo de contato em 15 mm, com peças fechadas e conservação de volume. Interseções e regiões que não admitem projeção continuam sendo recusadas.
- Diagnóstico do gato: bigode com contorno bifurcado por uma face cinza isolada; pata curva com dois contornos incompatíveis com o apoio planar do motor de molduras. Não são reparados automaticamente nesta versão.

# 0.8.20 — localização de defeitos para correção manual — 2026-10-22

- Localizar problemas seleciona bordas abertas, arestas soltas, arestas com mais de duas faces, orientação incompatível entre faces, vértices singulares e faces degeneradas na malha editável.
- Próximo problema percorre regiões recalculadas em cada clique, entra no Modo de Edição, habilita visibilidade por raio X e enquadra a seleção numa vista 3D disponível.
- As ações alteram seleção/visibilidade, sem reparar, apagar ou mover geometria. A análise é atualizada para permitir nova conferência após correção manual. Falhas existentes apenas no resultado de modificadores não recebem índices falsos na malha base.

# 0.8.19 — área limitada no corte planar — 2026-10-22

- Plano completo mantém o comportamento existente. Área limitada usa o retângulo do guia como domínio real de seleção das seções a separar, com largura e altura ajustáveis em milímetros e por escala do guia.
- Somente contornos fechados totalmente contidos no retângulo são separados; regiões atravessadas pelo plano fora do retângulo permanecem unidas. Não são criadas paredes laterais de caixa.
- Área parcial ou insuficiente é recusada com orientação para ampliar ou reposicionar o guia; a prévia anterior é preservada em caso de falha.
- Desenho translúcido, linha de corte, superfície de conectores, assinaturas de entrada e invalidação de prévia usam o mesmo domínio. Rotação no plano e alteração da escala/tamanho do guia invalidam a prévia limitada.
- Testes: nove casos de área limitada, fluxo de conector/prévia/confirmação, pose de pé real e regressões de plano, conectores e recriação do guia.

# 0.8.18 — auditoria de placas, folgas e robustez numérica — 2026-10-21

- Corrigida troca de Loop para Material com captura antiga: a região capturada só é consultada no modo Loop.
- Volume de referência do saneamento calculado em precisão dupla, preservando a tolerância existente e evitando rejeição por erro numérico de triangulação.
- Saídas planares passam pelo saneamento validado antes das métricas finais. Cortes por sólido repetem a operação com o solver Manifold quando Exact produz saída inválida, mantendo validação de ambas as peças.
- Prismas de extração por material recebem o mesmo saneamento; saídas booleanas vazias acionam a tentativa alternativa já existente.
- Saídas vazias do Loop acionam a tentativa alternativa validada. Encaixes avaliam as duas peças em candidatos temporários e repetem com Manifold somente quando a saída Exact é inválida, sem alterar as folgas ou dimensões.
- Auditoria com nove BLENDs, nove GLBs e o arquivo de cubos: evidências e limitações em `evidence/commercial_20261021`. Um caso Arco/Base permanece bloqueado por fechamento inválido; nenhuma validação foi desativada.

- Corrigido o corte por material da placa QR reparada com profundidade de 0,10 mm e folga zero. Resíduos de arestas sem faces gerados na saída booleana são removidos antes da validação; arestas de superfície abertas não são removidas nem preenchidas. Prévia e confirmação geram dois sólidos fechados, conservando o volume dentro da tolerância.

- Reparo seguro também trata microfaces quase colineares em cópia, com validações de fechamento, volume, áreas por material e distância de superfície por cor em precisão dupla (0,0001 mm). Faces pequenas bem formadas são preservadas; diagnóstico e corte passam a usar o mesmo critério físico. Novos controles Tentar reparo seguro e Mostrar faces. Folga que colapsa microdetalhes recebe mensagem orientada, sem alteração automática de parâmetros.

- Corrigido agrupamento de regiões por material: a união por coincidência preserva conexões topológicas existentes, evitando falsas ilhas e bifurcações em microarestas da placa QR Inclinada. A validação de microfaces da fonte permanece ativa.

- Corrigida extração de molduras com contorno externo planar e contorno interno em alturas diferentes (placa Osso): usa o contorno externo como referência e projeta os contornos no apoio mais interno. Mantém validações de projeção, espessura, fechamento e volume. Regressões cobrem Material e Loop, com a placa real em profundidade de 2 mm e folga de 0,10 mm.

- Seletor único de folgas: Impressão FDM (peças 0,10 mm; pinos 0,15 mm radial e 0,20 mm axial), Sem folgas e Personalizado. Edição individual ativa Personalizado; dimensões e posições dos pinos são preservadas. Arquivos antigos não têm valores sobrescritos.
- Removidos os botões rápidos redundantes de folga dos pinos. A seção Slicer Export fica oculta; exportadores internos são preservados.
- Regressões verificam presets, edição, compatibilidade e persistência, além de prévia e criação final com conectores.

# 0.8.17 — molduras, aberturas e reparo seguro — 2026-10-20

- Material reconhece regiões conectadas com contornos interno e externo. Extrai molduras pela base ou por profundidade, preservando o centro receptor.
- Captura pelas faces do Loop registra todos os contornos e a região selecionada; o corte compartilha o motor de molduras com Material.
- Folgas consideram paredes internas e externas, com fundo independente. Pinos usam a superfície final de contato e respeitam aberturas.
- Reparo de malha opera em cópia com tolerância física conservadora, recusa resultados inválidos e retorna corretamente ao modo de edição. Malhas já fechadas não são modificadas.
- Contornos cruzados, ajustes que colapsam a moldura e regiões sem projeção/apoio válidos continuam bloqueados. Regressões incluem a placa Arco e regiões sintéticas com duas aberturas.

# 0.8.16 — correção de extração por profundidade — 2026-10-20

- Captura de Loop: reconhece microfaces omitidas que conectam a seleção sem deformar a malha. A recuperação de vértices separados é testada em uma cópia e só é aplicada após validar o contorno; falhas preservam a seleção e a geometria. A seleção visual final contém somente as arestas consecutivas do perímetro, sem diagonais internas.
- Encaixes após folga entre peças: o saneamento transacional pós-booleano também trata triângulos quase colineares, mesmo sem micro-arestas. Mantém a folga configurada e as validações de sólido fechado; verifica volume e limites antes de aceitar a limpeza. Regressão com a placa Mesa, pinos automáticos/central e inversão de macho; preservadas as alterações de captura de contornos.
- Material com relevo usa o mesmo motor de região e profundidade do Loop. Preserva a estrutura selecionada inteira, inclusive partes inclinadas que saem da projeção do contorno, e cria a base apenas na ligação com o corpo.
- O fallback booleano do Loop verifica a superfície selecionada antes de projetar o cortador. Se a projeção cortaria a estrutura, a operação é recusada em vez de gerar peças truncadas e fragmentos no corpo.
- Mantém a cor original das faces selecionadas e o material configurado nas interfaces novas A/B. Corrige o texto de ajuda de Profundidade em PT/EN.
- Regressões com a cena Cubo Teste 2 conferem preservação das faces da estrutura, componentes conectados, profundidade real, folgas e corte passante. Versão candidata para validação no Blender 5.2.

# 0.8.15 — candidata de validação — 2026-10-19

- Folga por Loop preserva os planos das faces externas nos casos de canto e degrau. Reconstrói cantos convexos quando o deslocamento exige novos vértices; trata laterais e fundo independentemente.
- Loop AUTO identifica quando o fechamento direto atravessaria a superfície existente e usa a profundidade configurada. Fechamentos diretos inválidos são recusados com diagnóstico; o valor escolhido de profundidade é preservado.
- Extração por profundidade de Loop e Material usa a mesma tesselação visível da fonte para as duas booleanas e remove degenerações numéricas conectadas sob limite físico. Mantém as validações de área e sólido fechado.
- Pinos usam a superfície final de contato, com referência de origem e orientação estáveis ao trocar o lado macho ou alterar a folga. Preserva furos no domínio de posicionamento.
- Exportação bloqueia prévias desatualizadas, inválidas ou incompletas. O painel e o operador compartilham a verificação; a execução confere novamente o estado completo.
- Falhas tardias na substituição da prévia recuperam os objetos, malhas, métricas, referências e visibilidade anteriores.
- Assinaturas avaliam modificadores pelo depsgraph correto. A ocultação visual do alvo mantém sua avaliação geométrica ativa.
- Caches de material e contorno acompanham as revisões da geometria; consultas repetidas evitam percorrer a malha inteira. A análise em Edit Mode lê o BMesh sem escrever nos datablocks durante o desenho.
- Mensagens prioritárias de geometria e diagnósticos são estruturados e localizados em PT/EN, inclusive após trocar o idioma. Botões de ajuda abrem o tópico correspondente.
- Guia rápido PT/EN e novas regressões com os casos recebidos. Consulte o relatório de validação para resultados, artefato e verificações manuais pendentes.

# 0.8.14 — 2026-10-19

- **COM-01 (Exportação após Confirmar)**: Criado resolvedor explícito de operações exportáveis (`resolve_exportable_operation_record` e `get_current_session_parts`), permitindo exportar peças A e B em qualquer modo de próximo alvo (`RECEIVER`, `EXTRACTED` ou `NONE`) e em cortes encadeados.
- **COM-02 (Invalidação por Modificadores do Cortador)**: Assinatura determinística de corte e sessão agora avaliam modificadores e deformações da malha do cortador sólido via depsgraph, rejeitando prévias obsoletas e invalidando cache quando parâmetros do cortador mudam.
- **COM-03 (Transação de Prévia com Recuperação Segura)**: Reestruturado o ciclo de vida da geração de prévia: caches e validações agora precedem o descarte da prévia anterior. Em caso de falha em qualquer etapa, a prévia anterior é preservada intacta na Viewport sem deixar órfãos nem ocultar o alvo indevidamente.
- **COM-04 (Validação Física e Orientação 3MF)**: Adicionada validação de finitude e determinante de matriz mundial antes da exportação, bloqueando peças com escala singular/zero. Exportador 3MF corrige automaticamente o winding de triângulos em malhas com escala negativa/espelhamento, garantindo volumes assinados positivos.
- **COM-05 (Preservação de Pinos ao Renomear)**: Identificador persistente em `target` e `cutter` impede que renomeações de objetos na cena limpem acidentalmente o posicionamento de pinos manuais.
- **COM-06 (Linha de Corte com Tesselação Real)**: Eliminação do leque ingênuo de triângulos em favor da triangulação real da malha (`calc_loop_triangles` e `tessellate_polygon`), impedindo traços espúrios sobre vazios em n-gons côncavos (ex: perfis em U e L).
- **COM-07 (Otimização e Cache de Redraw)**: Implementado cache de análise de material e de segmentos de corte do plano na Viewport, evitando recalcular malhas pesadas durante órbita de câmera e interações de interface.
- **Internacionalização (i18n)**: Auditoria bilíngue completa com 1.285 termos simétricos em Português e Inglês, eliminando vazamentos em tooltips e botões de enum.
- **Suíte de Testes**: 62 testes de regressão automatizados passando 100% no Blender 5.2.0 LTS.

# 0.8.13

- Marcadores vinculados à interface atual e ao deslocamento real da prévia; descartado o fallback que desenhava sobre uma origem antiga.
- Normais atualizadas após transformações, frame estável em superfícies simétricas e posições levantadas sobre tampas trianguladas não planas.
- Profundidade de Loop/Material com apoio projetado abaixo do contorno e amostras interiores de espessura.
- Cores determinísticas nas faces novas do Loop, com material da peça extraída em A e do corpo na cavidade.
- Busca de dois pinos em toda a área útil, com validação de perfil e separação.
- Cortador excluído da cena rejeitado mesmo quando seu datablock permanece referenciado.
- Modo Sólido: folga física por offset de faces, escolha/captura da face de encaixe, pinos manuais e alinhamento por vértices.
- Preservados os quatro modos, formatos de encaixe, prévias, confirmação, reversão e exportações.
- 49 regressões em bpy 4.2.23, 4.5.3 e 5.0.1; interface gráfica Windows/Blender 5.2 ainda requer validação manual.

# 0.8.12 — 2026-10-15

- Preserva o contorno ao remover prévia ou reabrir o editor: reatribuir o mesmo alvo não limpa a captura.
- Invalida captura/cache ao trocar realmente de alvo; valida índices vivos em Edit Mode sem atualizar datablocks no desenho.
- Encerra arrastes soltos fora do viewport e desativa instâncias modais antigas ao reabrir a edição.
- Cancela corretamente rascunhos vazios; não anuncia sucesso se a geração retornar CANCELLED.
- Prepara a superfície antes de remover a prévia; limita a remoção à operação atual.
- Reutiliza a referência geométrica determinística do corte, sem refletir eixos isoladamente dos contornos.
- Corrige a direção das rotações dos pinos quando o macho está na Parte B.
- Atualiza cache por geometria, transformação, guia vivo, unidades e parâmetros completos de base/folga.
- Usa a malha avaliada com modificadores na preparação do plano e a normal real do guia na explosão.
- Usa a direção própria do corte sólido na explosão, sem impor o eixo Z.
- Detecta furos internos completamente cobertos por um pino e colisões reais entre cápsulas.
- Mantém grade visual de 5 mm, movimento livre e nenhum controle novo; memoriza também grades vazias.
- Limpa caches e edição volátil ao carregar, desfazer/refazer e desativar a extensão.
- Corrige import de Vector ausente no redimensionamento de cortador ancorado.
- Mantém o referencial anterior de extração por material; se a booleana gera resultado não-manifold, tenta uma vez a normal acumulada em precisão dupla. Mantém o solver EXACT e todas as validações.
- Bloqueia extração com profundidade sem apoio planar; mantém o destaque de volume por contorno.
- Corrige o namespace das preferências na extensão instalada, permitindo resolver a seleção PT/EN.
- Corrige precedência de mensagens de status e centraliza rótulos do painel no idioma da extensão.
- Acrescenta regressões de integração e fixture geométrica do arquivo de teste do usuário. Corrige inicialização/seleção de duas suítes antigas e atualiza a identificação da versão.

# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.8.11] - 2026-10-14

### Implementado e Corrigido (Plano de Implementação 0.8.11: Gates A01 a A12)
- **A01 — Sincronização Geométrica do Plano (`plane_state.py`)**:
  - Extraído helper neutro e puro `resolve_plane_state(scene, settings)` como única fonte de verdade para origem, normal e tangentes do plano de corte.
  - Normal mundial calculada rigorosamente pela matriz inversa transposta da transformação do guia (`matrix_world.to_3x3().inverted().transposed()`), tratando escalas não-uniformes e rotações.
  - Sincronização perfeita entre overlay GPU, bisecção/corte booleano, linha de interseção e assinaturas de estado durante transformações interativas (G/R), alinhamentos rápidos e desfazimento.
- **A02 — Contrato do Cortador por Seleção de Material (`analyze_material_structure`)**:
  - Corrigida a chamada da API de análise em `operators.py` enviando os argumentos requeridos `target`, `material_index` e `region_index`.
  - Tratamento de regiões com múltiplas ilhas e validação de coplanaridade antes da geração do cortador prismático, eliminando exceções `TypeError`.
- **A03 — Contrato Físico de Base e Apoio em Loop e Material**:
  - **Loop com Base Adicional**: `CutInterface` agora referencia formalmente o fundo da base (origem, anel de contorno e triângulos de interface deslocados pela profundidade), garantindo que conectores sejam gerados na interface real de encaixe.
  - **Material com Apoio Planar**: Substituída a extrusão média de relevo por prisma perpendicular erguido a partir do footprint da base de apoio (`create_material_footprint_prism_cutter`). A profundidade conta a partir do apoio, preservando a geometria exterior nominal e escavando cavidade complementar no corpo receptor.
  - Análise física de espessura de parede por múltiplos raycasts distribuídos pelo domínio (incluindo concavidades e formas em U/L), prevenindo perfurações inadvertidas.
- **A04 — Folgas Físicas Independentes**:
  - Separação completa entre folga lateral (`part_clearance_mm`) e folga de fundo axial (`part_clearance_bottom_mm`) no modo Material.
  - No modo Loop com base, a folga é aplicada na peça extraída A encolhendo o fundo sem alargar a boca, eliminando cavidades inclinadas ou rebaixos invertidos (undercuts).
- **A05 & A07 — Padrões Editáveis, Posicionamento Manual e Contenção Exata**:
  - Implementado sistema de conectores manuais (`ChestManualConnector`) e modo de distribuição `MANUAL`.
  - Ferramenta interativa de posicionamento por clique no Viewport 3D (`CHEST_OT_splitter_manual_connector_click`) através de raycasting direto no plano/interface de corte.
  - Operador de conversão de padrões (`CHEST_OT_splitter_convert_pattern_to_manual`) que transforma posições calculadas (Padrões 1, 2, 3, 4 ou Auto) em pontos manuais editáveis individualmente em coordenadas U/V e rotação Yaw.
  - Overlay GPU no Viewport com círculos e cápsulas de conectores com anéis de folga, cruz central e identificação imediata de status: verde (válido), vermelho (fora do domínio ou margem violada) e amarelo (conector ativo).
  - Algoritmo de amostragem no domínio real (`sample_domain_valid_points`) para localização de posições válidas em geometrias complexas e côncavas (formas em U, L e S), rejeitando posições no vazio sem reduzir silenciosamente diâmetros ou quantidades.
- **A06 — Encaixes e Conectores no Modo Material**:
  - Habilitados encaixes (pinos e cápsulas) no modo Material, reutilizando o pipeline comum de layout, validação física e união/subtração booleana.
- **A08 — Saneamento Determinístico Pós-Booleanos (`sanitize_mesh_micro_degeneracies`)**:
  - Implementada rotina de soldagem de micro-arestas geradas pelo solver EXACT do Blender ao longo das costuras dos cilindros, com agrupamento Union-Find determinístico e rollback transacional caso a integridade do sólido sofra degradação.
  - Aplicação automática pós-booleano eliminando falhas de arestas quase nulas e garantindo sólidos 100% estanques (manifold).
- **A09 — Desacoplamento de Orientação Geométrica e Explosão Visual**:
  - Separação estrita entre a normal física da interface (`normal_a_to_b`), orientação das peças e direção de afastamento da visualização explodida.
  - Posições montadas imutáveis armazenadas em snapshot (`chest_assembled_loc`), garantindo zero deriva ou deslocamento físico ao alterar distâncias de explosão ou alternar entre montado e explodido.
- **A10 — Coerência de Materiais em Tampas, Bases e Conectores**:
  - Correção na atribuição de materiais nas tampas criadas no corte por loop, propagando os materiais das faces vizinhas para evitar triângulos brancos não mapeados.
  - Pinos recebem o material da superfície de contato onde estão ancorados, e as cavidades receptoras herdam o material do corpo hospedeiro.
- **A11 — Fidelidade Geométrica na Tesselação de Tampas (CDT)**:
  - Verificação de cobertura e conservação de área na Triangulação de Delaunay Construtiva (`mathutils.geometry.delaunay_2d_cdt`), com fallback automático para Ear Clipping robusto caso haja criação de pontos espúrios.
- **A12 — Preservação de Âncora Fixa e Localização PT_BR / EN_US**:
  - Preservação da posição do ponto de apoio/ancoragem em coordenadas mundiais durante o redimensionamento de cortadores sólidos (`solid_cutter_width_mm`, `height`, `depth`), impedindo deriva no alinhamento de quinas e faces.
  - Catálogo de tradução atualizado com suporte bidirecional completo em Português do Brasil e Inglês Americano.

## [0.8.10] - 2026-10-13

### Corrigido e Aprimorado (Plano de Correções 0.8.10: DEV-01 a DEV-10)
- **DEV-01 & DEV-06 — Triangulação Construtiva de Delaunay (CDT) e Extrusão em Regiões Planas**:
  - Implementado motor de triangulação 2D baseado em `mathutils.geometry.delaunay_2d_cdt` com restrição estrita ao domínio interior do contorno (`CDT_INSIDE`).
  - Eliminação definitiva de triângulos degenerados com área zero em contornos côncavos, entalhes ou vértices colineares.
  - Resolução das falhas de arestas nulas e arestas abertas não-manifold no fatiamento por loop extrude.
- **DEV-02 & DEV-04 — Cortador de Caixa de Quina (`create_corner_box_cutter`)**:
  - Exigência estrita de exatamente 3 faces ortogonais ($|\text{dot}| \le 0.15$) compartilhando um único vértice de quina real.
  - Orientação correta dos eixos de penetração $e_i = -N_i$ e garantia de referencial dextrógiro por permutação de eixos sem inversão do sentido de penetração.
  - Adição de 1,0 mm de extensão exterior nas faces externas para eliminar coplanaridade degenerada no solver EXACT do Blender (resolvendo o erro de 3 arestas nulas da quina E01 em `Teste_3.blend`).
- **DEV-03 — Correção de Assinaturas e Ownership em `create_cutter_from_selection`**:
  - Ajustada a chamada a `create_material_patch_prism_cutter` e `create_loop_prism_cutter` respeitando o retorno direto de `Object` já vinculado à coleção de guias.
  - Suporte completo ao parâmetro `invert_direction` e ativação imediata do modo `SOLID` com o cortador selecionado.
- **DEV-05 — Alinhamento Robusto de Cortadores Sólidos (`align_solid_cutter`)**:
  - Substituição da dependência de centro de bounding box mundial pela fórmula formal $t = ref\_pos - R @ (S @ a_{local})$, calculando o ponto de apoio $a_{local}$ na malha local sem escala.
  - Suporte completo aos modos de ancoragem `SUPPORT_FACE` e `CENTER` e preservação do ângulo de rolamento (roll) ao alinhar em faces ativas.
- **DEV-07 — Destaque de Saliência com Base e Cavidade Receptora (DETACH com Base)**:
  - Adicionadas propriedades `loop_detach_add_base`, `loop_detach_base_depth_mm` e `loop_detach_base_clearance_mm`.
  - Geração de base prismática contínua na saliência destacada e escavação de cavidade complementar no corpo receptor, preservando a superfície exterior nominal do modelo e conservando o volume exato.
  - Verificação rigorosa da espessura disponível de parede antes da criação da cavidade, impedindo perfuração inadvertida.
- **DEV-08 — Confirmação e Seleção Semântica Exclusiva (`commit_parts`)**:
  - Ao confirmar o corte, o add-on desmarca todos os objetos e seleciona exclusivamente a peça extraída (garantindo Object Mode e foco imediato para mover com `G`).
  - Detecção automática de Edição Proporcional (`use_proportional_edit_objects`) na cena, emitindo alerta claro ao usuário para desativar a tecla 'O' quando necessário, impedindo que o receptor seja arrastado inadvertidamente.
- **DEV-09 — Visualização em Overlay GPU Ciano para Cortador Sólido**:
  - Integração de desenho GPU no SpaceView3D desenhando as arestas reais do cortador ativo em ciano contrastante (`(0.0, 0.9, 1.0)`), mantendo visibilidade mesmo quando o Blender desenha a seleção laranja de contorno.
  - Exibição de vetor indicador de direção de penetração e profundidade.
- **DEV-10 — Unificação e Localização Completa da Interface (PT_BR / EN_US)**:
  - Tradução e padronização completa de todos os textos, labels, tooltips e mensagens de erro e diagnóstico da extensão.
  - Remoção de literais em inglês residuais no painel principal.

## [0.8.9] - 2026-10-12

### Adicionado (Plano Revisado 0.8.9: INV-008 a INV-014, SOL-01 a SOL-06, LANG-01)
- **INV-008 — Folga Lateral Calibrada no Corte por Material (`part_clearance_lateral_mm`)**:
  - Aplicação de alívio dimensional lateral por miter offset 2D nas paredes da cavidade (`CAVITY`), no inserto (`PART`) ou bilateralmente (`BOTH`), permitindo montagem precisa de peças plásticas pós-impressão.
- **INV-009 & SOL-06 — Cortador de Caixa de Quina (`create_corner_box_cutter`)**:
  - Criação rápida de caixa ortogonal ancorada em cantos/arestas do modelo alvo para chanfros e remoções regulares em milímetros físicos.
- **INV-010 — Diagnóstico Avançado de Malha no BMesh (`validate_bmesh_mesh_geometry`)**:
  - Detecção prévia de arestas de comprimento nulo, faces colineares ou com área zero e vértices coincidentes antes da resolução booleana, evitando falhas silenciosas do solver EXACT.
- **INV-011 — Fluxo de Continuação no Receptor (`continue_on_receiver`)**:
  - Operador `CHEST_OT_splitter_continue_on_receiver` que define automaticamente o corpo receptor (`Cube__B`) como novo alvo, vinculando `parent_operation_id` para permitir cortes sucessivos e recursivos sem perder rastreabilidade do ciclo de vida.
- **INV-012 — Isolamento Estrito de Materiais no Encaixe**:
  - No fatiamento por material (`slice_mesh_by_material`), as faces internas da cavidade recebem o material original do corpo principal e o inserto mantém seu material exclusivo, impedindo que faces externas do receptor sejam repintadas inadvertidamente.
- **INV-013 — Distribuição Automática de Encaixes e Busca Colinear Adaptativa**:
  - Adicionado modo `AUTO_SHAPE` para seleção automática do perfil de conector (Cilindro vs Cápsula) com base na razão de aspecto da interface.
  - Algoritmo adaptativo para `LINEAR_2` ao longo do eixo maior com redução automática de espaçamento quando a interface for estreita.
  - Exposição do controle `adjust_to_valid_area` no painel da interface N para acomodação em polígonos côncavos.
- **INV-014 — Limpeza e Validação de Captura de Loop**:
  - Operadores e funções de validação (`validate_capture`, `clear_capture`) garantindo reset do anel de arestas capturado, sincronização com o GPU overlay e integridade antes do fatiamento.
- **SOL-01 a SOL-05 — Suíte Completa de Cortador Sólido**:
  - **SOL-01**: Desacoplamento entre criar cortador, focar (`focus_solid_cutter`) e reiniciar geometria para primitiva padrão (`reset_solid_cutter`).
  - **SOL-02**: Alinhamento determinístico nos eixos principais e centro da face ativa (`align_solid_cutter`).
  - **SOL-03**: Propriedades dimensionais em milímetros físicos locais (`solid_cutter_width_mm`, `height`, `depth`), escalando a malha no espaço local sem alteração na rotação nem deriva de orientação.
  - **SOL-04**: Operadores para duplicar cortador (`duplicate_solid_cutter`) e transformar qualquer malha da cena em cortador sólido (`copy_selected_as_cutter`).
  - **SOL-05**: Criação de cortador prismático a partir de seleção de faces da malha (`create_cutter_from_selection`).
- **LANG-01 — Preferências de Idioma e Catálogo Unificado de Tradução**:
  - Adicionado seletor de idioma nas Preferências do Add-on (`AUTO`, `PT_BR`, `EN_US`).
  - Catálogo bilíngue completo via `MESSAGES` em `src/translations.py`, com funções auxiliares `tr()`, `set_localized_status()` e `get_localized_status()`.

### Corrigido (Resolução INV-001 a INV-006 — Plano Gemini Flash 3.8)
- **INV-004 (A01–A05) — Explosão do Plano, Inversão e Invariância**:
  - Implementação da propriedade `invert_explosion` desacoplada da normal geométrica do corte (`invert_sides`), permitindo inversão visual de afastamento sem alterar a identidade geométrica de A e B.
  - Snapshot de posições montadas (`chest_assembled_loc`) e normal congelada por prévia (`chest_explosion_normal_a_to_b`), eliminando deriva cumulativa (drift) em ciclos sucessivos de explosão e contração.
  - Garantia de exportação e confirmação (commit) nas coordenadas canônicas montadas, independentemente do estado do controle deslizante na viewport.
- **INV-005 (B01–B05) — Contrato e Fechamento de Loop**:
  - Validação precoce contra aberturas pré-existentes fora do loop de corte, recusando sólidos não-estanques de entrada sem mascaramento silencioso.
  - Construção de interface compartilhada única (`triangulate_polygon_2d`) garantindo topologia complementar exata entre Parte A e Parte B sem furos na interface.
  - Diagnóstico precoce em contornos não-planares incompatíveis no modo AUTO e fechamento restrito, impedindo a publicação de modelos não-manifold.
- **INV-002 (C01–C04) — Destaque de Saliência por Material e Tampa Duplicada (BASE)**:
  - Eliminação da exceção `faces.new(...): face already exists` no destaque por base: classificação automática de faces da região entre volumétricas (saliência útil) e coplanares da base, mantendo as faces planas no corpo receptor e prevenindo películas (fins) de espessura nula.
  - Verificação de incidência topológica antes da criação de novas faces, reutilizando triângulos válidos ou diagnosticando duplicidades conflitantes.
- **INV-001 & INV-003 (D01–D06) — Extração por Profundidade, Materiais e Folgas**:
  - Validação de estanqueidade e volume estritamente positivo do cortador prismático antes de qualquer booleano, rejeitando patches dobrados degenerados com aviso informativo.
  - Mapeamento explícito de slots de materiais no cortador e cópias de trabalho, respeitando a política de interface (`SOURCE` mantém material adjacente do corpo; `EXTRACTED` aplica a cor do inserto) e eliminando faces brancas/despadronizadas.
  - Preservação comprovada do caso positivo INV-003 (inserto espesso com 10 mm de profundidade e folga zero) e progressão volumétrica calibrada em folgas de 0, 0.15 e 0.30 mm.
- **INV-006 (E01–E03) — Diagnóstico de Espessura de Parede e Cunhas**:
  - Distinção rigorosa entre películas espúrias (volume nulo / não-manifold) e cunhas geométricas fiéis (volume > 0, manifold com aresta viva), preservando a geometria nominal de corte sem recuos silenciosos.
  - Diagnóstico por raycast com amostragem múltipla e estado explícito (`MEASURED` vs `INCONCLUSIVE`), evitando estimativas fictícias (ex: 1000 mm) em direções tangentes.
- **Validação e Regressão**:
  - 100% de aprovação em 29/29 suítes de testes automatizados no Blender 5.2.0 LTS.

## [0.8.8] - 2026-10-12

### Corrigido (Auditoria 0.8.7 e Plano 0.8.8)
- **C01, C02, C03 & V01-V04: Triangulação Ear Clipping 2D Robusta e Saliência por Base (BASE)**:
  - Eliminação de pontes e membranas em contornos côncavos (L/U) e polígonos colineares (4, 12, 20, 40 vértices) com preservação de todas as arestas de borda na triangulação.
  - No modo BASE ("Destacar saliência pela base"), remoção de lâminas coplanares e faces degeneradas: tanto a saliência destacada quanto o corpo receptor são gerados como sólidos 100% estanques (manifold) com tampas planas fechadas e conservação estrita de volume (\(\Sigma V_{\text{partes}} = V_{\text{original}}\)).
  - Rejeição e cancelamento controlado de polígonos de borda degenerados sem travamento do operador.
- **C04, C09, C10 & V06-V07: Vetores de Explosão Orientados e Invariância sem Deriva (Drift)**:
  - Sentido de explosão calculado estritamente para fora da interface em todos os modos (PLANE, LOOP, MATERIAL), garantindo afastamento mútuo das peças A e B em qualquer orientação espacial e rotação.
  - Cálculo de explosão baseado na matriz mundial montada original, eliminando realimentação cumulativa e deriva posicional (drift) mesmo após dezenas de ciclos alternados entre montado e explodido.
- **C05, C06, C07, C08 & V08-V12: Contrato e Calibração Fiel de Folga entre Peças**:
  - Folga axial na interface suportada exclusivamente nos modos PLANE e MATERIAL com validação contra espessura útil e volume remanescente (rejeição segura de folgas excessivas).
  - Em modos não suportados (LOOP, SOLID), os controles de folga são desabilitados com aviso informativo claro na interface de usuário.
  - Distinção exata entre aplicação unilateral (deslocamento $g$ na peça selecionada) e bilateral ($g/2$ em cada peça).
- **C11, C12, C13, C14, C15 & V13-V16: Fechamento de Corte e Linhas de Contorno**:
  - `cap_open_cut_boundaries` restrito às arestas geradas no plano de corte da operação atual, evitando fechamento indevido de orifícios pré-existentes do modelo original de entrada.
  - Deduplicação de segmentos coplanares e tangentes sem traçado de diagonais internas ou arestas nulas em faces côncavas.
  - Na visualização explodida, os contornos de corte são projetados sobre as coordenadas transformadas das peças associadas aos papéis `ROLE_PREVIEW_A` e `ROLE_PREVIEW_B`.
- **C16, C17, C18 & V17-V20: Encaixes, Grade OMBB e Herança Fiel de Materiais**:
  - Grade de pinos GRID_4 alinhada aos eixos principais da interface via Oriented Minimum Bounding Box (OMBB) com fator de escala seguro para retenção dos 4 conectores em domínios sólidos.
  - Pinos de encaixe herdam fielmente os materiais dos polígonos de contato por análise de área em World Space; em interfaces multimateriais, cada conector é avaliado individualmente.
  - Verificação de limites e footprint para conectores do tipo Cápsula evitando perfuração de cantos e paredes adjacentes.
- **C19, C20, C21, C22, C23, C24 & V21-V27: Atomicidade de Sessão, Ciclo de Vida e Assinatura**:
  - Resolução de ambiguidade com cancelamento estrito e sem fallback se objetos de sessões ou operações distintas forem selecionados simultaneamente.
  - Operador `splitter_restore_original` bloqueado em operações confirmadas (COMMITTED), exigindo o uso explícito de `splitter_revert_cut`.
  - Swap atômico de prévia: substituição e descarte da prévia anterior apenas após sucesso pleno de todos os cálculos geométricos e validações, restaurando estado íntegro em caso de exceção.
  - Assinatura de sessão completa cobrindo transformações, matrizes mundiais, materiais, modificadores e parâmetros de conectores (chanfro, folga axial e ajuste à área válida).
  - Avaliação fiel de modificadores em `compute_session_input_signature` preservando a visibilidade temporária do alvo oculto.
- **C25, C26, C27 & V28-V32: Exportação Atômica e Tratamento de Modificadores**:
  - Cancelamento explícito da exportação caso a avaliação de modificadores de qualquer peça falhe, prevenindo divergência entre a prévia e os arquivos finais em disco.
  - Publicação atômica em disco com diretório de staging, backup de arquivos existentes e rollback automático integral em caso de falha de I/O.
  - Exportação 3MF coleta recursos de cores e materiais da geometria avaliada com modificadores.
  - Exportação a partir de vista explodida restaura internamente as matrizes montadas de cada componente.
- **C28, C29, C30 & V33-V36: CLI, Testes de Estresse e Suíte 0.8.8**:
  - Tratamento unificado de argumentos CLI nos scripts `scripts/build.py` e `tests/run_all_tests.py` com e sem separador `--`.
  - Nova suíte oficial `tests/test_plan_088.py` com 36 testes cobrindo 100% da matriz de aceitação V01–V36.
  - Aprovação de 100% (23/23 suítes de testes) no Blender 5.2.0 LTS.

## [0.8.7] - 2026-10-11

### Corrigido (Pós-Testes 0.8.7)
- **C01 & C02: Modo BASE de Extração por Material e Conservação Estrita de Volume**:
  - Implementação do modo `BASE` ("Destacar saliência pela base") em `slice_mesh_by_material`: destaca o ressalto sólido íntegro com tampa plana fechada na base (ex: Z=100 mm), enquanto o corpo receptor mantém sua parede exterior plana restaurada com o material original adjacente, eliminando o núcleo interno oco e lâminas espúrias.
  - Conservação de volume total garantida (\(\Sigma V_{\text{partes}} = V_{\text{original}}\)) sem resíduos ou fragmentos desconexos na cena.
  - Modo `EXTRUDE` preservado para corte de cavidades e regiões planas (M03).
- **C03: Calibração de Folga entre Peças (part_clearance_mm) e Assinatura de Sessão**:
  - Alívio dimensional calibrado aplicado axialmente na interface de contato montada (`PART`, `CAVITY` ou `BOTH`), com validação prévia da espessura útil do sólido (rejeitando folgas \(\ge \text{espessura} - 0.1\text{ mm}\)).
  - Parâmetros `part_clearance_mm`, `part_clearance_apply_to`, `material_extraction_mode` e `material_interface_mat_mode` integrados à assinatura de sessão (`compute_session_input_signature`).
- **C04: Linhas de Corte Face a Face e Vista Explodida**:
  - Interseção calculada estritamente face a face via `_compute_cut_line_segments`, eliminando conexões espúrias ou diagonais que cruzavam o vazio entre ilhas desconexas.
  - Na visualização explodida (`EXPLODED`), o plano flutuante no vácuo é ocultado e os contornos de corte são desenhados diretamente sobre as interfaces deslocadas das peças A e B.
- **C05: Grade GRID_4 em Seções Rotacionadas (OMBB) e Escala Segura**:
  - Algoritmo de Oriented Minimum Bounding Box (OMBB) para alinhamento automático da grade de 4 pinos aos lados reais do quadrado/retângulo, mesmo com rotação de 45° ou eixos arbitrários no plano da interface (`Demonstracao_Grade_4.py`).
  - Busca determinística de escala segura (passos de 0.55 a 0.15) acomodando todos os 4 pinos com margem de segurança dentro do domínio sólido.
- **C06: Herança Fiel de Material nos Pinos por Área em World Space**:
  - Pinos machos herdam fielmente o material da peça dona (ex: peça amarela gera pinos amarelos). Em interfaces multicoloridas ou ambíguas, o material é selecionado pela maior soma de área de faces em World Space (não por contagem de polígonos).
- **C07: Resiliência em Falha de Atualização de Prévia e Bloqueio de Ações**:
  - Quando uma atualização de parâmetros falha e a prévia anterior é preservada, um aviso persistente em destaque de alerta é exibido no painel ("Aviso: A última atualização falhou..."), bloqueando as operações de confirmação (`commit_parts`) e exportação (`export_parts`) até que a configuração seja válida.

### Corrigido (Fase Inicial 0.8.7)
- **B11 & P02/P03: Eliminação de Lâmina Coplanar no Alinhamento por Face**:
  - Classificação física pré-corte de faces coplanares e remoção seletiva da película e faces degeneradas da outra metade na peça retida. Em alinhamentos pela face de apoio, a saliência é gerada com contorno fiel e tampa fechada de base (ex: 30x30x20 mm), sem duplicar a face exterior da base (100x100 mm) nem produzir película de espessura zero.
  - Operador `CHEST_OT_splitter_align_plane` com validação estrita de Edit Mode e face ativa única no alvo, emitindo cancelamento controlado sem falso sucesso.
- **B05 & L01/L02: Triangulação Ear Clipping 2D em Contornos Côncavos (U/L)**:
  - Algoritmo de triangulação por Ear Clipping 2D implementado para as tampas do prisma cortador de loop, garantindo que 100% dos triângulos permaneçam estritamente dentro do domínio sólido sem gerar pontes ou membranas que atravessavam o vazio.
  - Diagnóstico fiel de espessura (`thickness_determined`) sem recurso ao fallback arbitrário de 1000 mm quando a região aberta não encontra parede oposta.
- **B06 & D2: Encaixes em Domínios Côncavos e Ajuste à Área Válida**:
  - Implementada função de amostragem determinística da área sólida útil (polo de inacessibilidade) ativada por `adjust_to_valid_area`. Quando a distribuição `CENTER` cairia no vazio ou furos de formatos em U ou anéis, reposiciona o conector na região com maior margem física útil das bordas.
  - Correção na função `build_cut_interface` para aceitar explicitamente origem `Vector((0,0,0))` válida sem sobrescrever pelo centroide.
- **B03: Desalocação Estrita de Recursos e Limpeza de Memória**:
  - Blocos `finally` sistemáticos com `eval_obj.to_mesh_clear()` aplicados ao mesmo objeto avaliado gerador em todas as rotinas de corte por loop e material, evitando vazamento de malhas em depurações sucessivas.
- **B04 & T23: Rastreamento Completo de Cortador no Depsgraph**:
  - O manipulador `depsgraph_update_post` monitora transformações e topologia tanto do alvo quanto do cortador (`cutter.matrix_world`), marcando `PREVIEW_STALE` quando o cortador é movido individualmente.
- **B12, B13, B14 & B15: Atomicidade e Isolamento do Ciclo de Vida**:
  - `capture_target_snapshot`: Procedimento transacional criando um candidato validado antes de substituir snapshots legados.
  - `discard_target_snapshot`: Checagem rigorosa de propriedade (`chest_role` e `chest_operation_id`), rejeitando objetos do usuário com mesmo nome.
  - `resolve_operation`: Detecção de seleção ambígua quando objetos de operações distintas são selecionados simultaneamente, retornando `None`.
  - `check_child_operations`: Bloqueio de reversão de operação pai se houver operações filhas confirmadas OU prévias de filhas ativas.
  - `revert_committed_operation`: Restauração fiel de alvos deletados clonando o snapshot com modificadores preservados.

### Adicionado
- **Etapa E (E01) — Folga Física entre Peças**:
  - Propriedades `part_clearance_mm` e `part_clearance_apply_to` ('PART', 'CAVITY', 'BOTH') permitindo alívio dimensional calibrado entre as peças cortadas para montagem física justa pós-impressão 3D.
- **Etapa C (C01-C03) — Modos de Extração por Material**:
  - Propriedades `material_extraction_mode` ('EXTRUDE' vs 'BASE') e `material_interface_mat_mode` ('SOURCE' vs 'EXTRACTED') permitindo destacar a saliência inteira pela base ou extrair com profundidade nominal.
- **Etapa F (F01-F02) — Visualização GPU Aprimorada e Isolada**:
  - Prévia visual do corte planar com preenchimento translúcido e linha de corte contrastante no contorno do modelo alvo.
  - Salvamento e restauração estrita do estado gráfico do Blender (`gpu.state`) em bloco `finally`, prevenindo interferências no renderizador da viewport.
  - Separação estrita de visualizadores por modo (`LOOP` vs `PLANE`) com leitura de BMesh em tempo real no Modo de Edição.

## [0.8.6] - 2026-10-10

### Corrigido
- **B01: Seleção por Face Confiável no Objeto Correto**:
  - Restrição estrita do operador `pick_material_region` ao objeto alvo em Modo de Edição (`context.edit_object == target`), impedindo interferência de objetos de prévia ou outros elementos na cena.
  - Rejeição determinística e amigável quando múltiplos objetos estão em edição ou quando não há face ativa válida identificável.
  - Atualização automática dos slots e regiões de material diretamente a partir da topologia atual em edição.
- **B02: Estabilidade e Prevenção de Crash em Undo/Redo**:
  - Remoção de alocação de malhas avaliadas (`eval_obj.to_mesh()`) de dentro do handler `depsgraph_update_post`, eliminando a causa raiz de falhas de segmentação e referências mortas em operações de desfazer/refazer.
  - Handlers dedicados `on_undo_post` e `on_redo_post` registrados com verificação leve e proteção contra `ReferenceError`.
  - Guard global de execução `_is_generating_preview` prevenindo reentrâncias descontroladas durante o pipeline booleano.
- **B03: Geração de Prévia Segura e Transacional com Rollback**:
  - Criação de malhas e objetos em namespace isolado de candidatos (`_cand_{exec_id}_...`).
  - Em falhas intermediárias do corte, da topologia ou dos pinos, a prévia existente é preservada intacta (sinalizada como `PREVIEW_STALE`) e os candidatos transitórios são purgados sem deixar resíduos na cena.
  - Swap e limpeza da prévia anterior executados unicamente após 100% de sucesso.
- **B04 & B05: Reconstrução Ordenada do Contorno no Corte Planar e Múltiplos Encaixes**:
  - Função `reconstruct_boundary_loops` ordenando arestas de corte em loops cíclicos fechados orientados pela conectividade real do BMesh.
  - Classificação robusta em contornos externos e furos (`outer_contours_uv` e `hole_contours_uv`) via inclusão 2D ponto-em-polígono.
  - Eliminação de falsos negativos de encaixes: teste de footprint com amostragem perimétrica multiponto garantindo posicionamento exato de 2 ou mais pinos sem colisões espúrias.
- **B06: Eliminação Definitiva da Película na Extração por Material**:
  - Nova geração de cortador prismático `create_material_patch_prism_cutter` duplicando a topologia exata das faces da região para compor as tampas e extrudando paredes exclusivamente no perímetro de fronteira.
  - Eliminação total de n-gons planos que atravessavam concavidades abertas, preservando o rebaixo complementar na Parte B e gerando a Parte A como sólido estanque (0 arestas não-manifold).
- **Integridade e Confiabilidade de Exportação**:
  - Transação atômica em diretório de staging temporário para exportações STL por material e STL por peças: arquivos só são publicados na pasta de destino após validação de 100% dos itens gerados.
  - Função `sanitize_unique_filename` prevenindo sobrescrita silenciosa de arquivos quando nomes de peças geram nomes de arquivos idênticos.
  - Avaliação fiel de modificadores (`apply_modifiers=True`) durante a checagem prévia de solidez imprimível.

### Adicionado
- **F01: Destaque Persistente do Contorno no Viewport (GPU Overlay)**:
  - Módulo `src/gpu_drawing.py` renderizando o anel de arestas capturado em ciano dinâmico via callback de viewport do Blender (`SpaceView3D.draw_handler_add`).
  - Suporte completo a transformações e posições do objeto alvo na viewport.
  - Propriedade e controle na interface `show_loop_highlight` para alternar a exibição.
- **F02: Captura do Contorno Perimetral a partir de Seleção de Faces**:
  - Função `capture_face_boundary_loop` em `src/geometry_loop.py` e operador `chest.splitter_capture_face_boundary` ("Capturar das Faces").
  - Identificação de arestas de fronteira com incidência de exatamente uma face selecionada, validação de ciclo simples conexo e rejeição de ilhas, furos ou seleção total da malha.
  - Definição automática da semente para a Parte A a partir de face válida da seleção.
- **F03: Remoção de Prévia e Reversão Segura de Cortes**:
  - Operador `chest.splitter_remove_preview` ("Remover Prévia") permitindo descarte imediato da geometria de prévia sem perder a cópia de trabalho nem edições do usuário no alvo, com reativação e seleção do alvo na viewport.
  - Operador `chest.splitter_revert_cut` ("Reverter este corte") com diálogo nativo de confirmação exibindo o modelo alvo e a contagem de peças afetadas, desfazendo o corte confirmado, removendo as peças geradas/subpeças e restaurando o modelo alvo ao seu estado pré-corte.
  - Modelo persistente com `ChestOperationRecord` e `ChestObjectRef` vinculado a `Scene.chest_operations` e `active_operation_id` para rastreamento por UUID e estados de ciclo de vida (`PREVIEW`, `COMMITTED`, `REVERTED`, `BROKEN`).
  - Coleção interna oculta `CHEST_SPLITTER_BACKUPS` para snapshots intactos de malha base, permitindo restauração mesmo se o usuário tiver apagado acidentalmente o objeto alvo após a confirmação.
  - Bloqueio hierárquico determinístico (`check_child_operations`): proteção contra reversão de corte pai quando existem cortes filhos confirmados ativos, com mensagem explicativa ao usuário.
  - Proteção de duplicatas manuais feitas pelo usuário e rastreamento de peças renomeadas ou movidas para outras coleções.
- **Suíte de Testes Comercial & Reversão (20 Suítes / 100% OK)**:
  - Bateria completa de 20 suítes de testes automatizados cobrindo os 24 casos comerciais e os 12 casos do plano de reversão (`tests/test_reversion_086.py`), incluindo teste de estresse de 10 ciclos consecutivos com zero vazamento de malhas ou snapshots.

## [0.8.5] - 2026-10-09

### Corrigido
- **Isolamento e Preservação de Cópias de Trabalho (Seção 2 / R01-R02)**:
  - Criação da coleção dedicada `CHEST_SPLITTER_WORK` para cópias de trabalho e atribuição de metadados `chest_role="WORK_COPY"`.
  - Reformulação de `cleanup_collection_objects`: garantia de tolerância zero à remoção do objeto alvo, cópias de trabalho ou malhas do usuário durante atualizações sucessivas de prévia. Migração automática de cópias legadas.
  - Implementação de restauração segura em `CHEST_OT_splitter_restore_original` reativando a visibilidade do modelo base original (`hide_set(False)` e `hide_viewport=False`), reatribuindo `target_object` e limpando a cópia de trabalho sem deixar datablocks órfãos.
- **Contrato Físico em Milímetros & Retornos do Operador (Seção 3 / R03-R04)**:
  - Adição de retorno explícito `{'FINISHED'}` e caminhos determinísticos de cancelamento `{'CANCELLED'}` em `CHEST_OT_splitter_export_parts`.
  - Padronização física em milímetros para STL (`global_scale=unit_scale`, `use_scene_unit=False`, `apply_modifiers=True`), garantindo que modelos exportados mantenham dimensões idênticas ao 3MF em qualquer escala de cena (`scale_length = 1.0`, `0.01` ou `0.001`).
  - Padronização em milímetros para exportação Wavefront OBJ (`global_scale=unit_scale`, 1 unidade = 1 mm).
  - Remoção de diretórios Windows/OneDrive fixos; fallback inteligente para diretório da cena salva, Desktop do usuário ou pasta temporária do sistema.
  - Alinhamento canônico na exportação de prévias: objetos na visualização explodida são temporariamente exportados na posição original montada `(0, 0, 0)` com restauração transparente da visualização na viewport em bloco `finally:`.
  - Escaping XML com `html.escape` em `build_3mf_xml` para suporte total a nomes de objetos com aspas, e-comercial (`&`) e colchetes angulares (`<`, `>`).
  - Gravação atômica de arquivos 3MF via arquivo temporário `.tmp` e `os.replace` para evitar corrupção ou perda de arquivos pré-existentes em falhas de escrita.
- **Isolamento de Sessões & Invalidação de Prévias (Seções 4 e 5 / R05-R08)**:
  - Geração de identificadores únicos UUID para cada sessão de corte.
  - Assinatura determinística SHA-256 (`session_input_signature`) rastreando transformações, posições, rotações, escalas, contagens e amostras geométricas do alvo e cortadores, além de escala de cena e parâmetros de corte.
  - Invalidação automática (`PREVIEW_STALE`) e bloqueio preventivo de confirmação/exportação quando o alvo ou cortador forem movidos ou alterados na viewport.
  - Handler de depsgraph (`on_depsgraph_update_post`) monitorando alterações em tempo real sem loops de redesenho.
  - Independência da vista explodida e modos de cor em relação à assinatura geométrica do corte.
  - Função centralizada `get_current_session_parts` garantindo que exportações e separações por material processem exclusivamente peças da sessão ativa, preservando cortes anteriores na mesma cena.
- **Validação Geométrica e Tolerâncias de Encaixe (Seção 6 / R11-R12)**:
  - Auto-ajuste de comprimento de conectores cápsula (`adjusted_capsule_length_mm` e `max_safe_lateral_mm`) para interfaces estreitas sem falha prematura da operação.
  - Amostragem perimétrica multiponto em `check_receiving_wall_thickness` para detecção de perfurações em paredes inclinadas e diagnóstico de ausência de corpo receptor (`hit_loc is None`).
  - Verificação de malhas válidas e imprimíveis antes de confirmar ou exportar peças, bloqueando a exportação de cascas abertas como sólidos individuais.
- **Internacionalização & Correção de Localização (Seção 8 / R16)**:
  - Correção de `_get_current_locale()` para retornar `pt_BR` apenas quando o locale do Blender iniciar com `pt`, adotando `en_US` como padrão internacional nos demais casos.
  - Correção de caracteres UTF-8 no manifesto e `__init__.py`.

### Adicionado
- Nova suíte de testes de regressão automatizada cobrindo os 18 requisitos de aceite (`tests/test_final_plan_corrections.py`).

## [0.8.4] - 2026-10-09

### Corrigido
- **Corte por Material com várias áreas da mesma cor**: cada área separada (ilha) agora é uma região independente, com contorno e direção próprios. Antes, duas áreas da mesma cor eram misturadas num único contorno inválido, gerando peças deformadas.
- **Seleção da cor base**: escolher o material do corpo (que envolve as outras áreas) agora mostra um aviso claro em vez de gerar um corte quebrado.
- **Vista explodida no modo Material**: as peças se afastam na direção real da extração (peça sai, corpo recua), e a distância é ajustada automaticamente para a peça sair totalmente da cavidade.
- **Prisma de extração**: pontos colineares do contorno são removidos, corrigindo malhas não-manifold e volume errado em áreas com mais de uma face (afeta também o Loop com profundidade).

### Adicionado
- Lista de "Áreas" quando uma cor aparece em vários lugares e botão **Usar Face Selecionada (Edit Mode)**.

## [0.8.3] - 2026-10-08

### Adicionado
- **Corte por Material com Contrato Estrito de Sólidos Estanques (Etapa 6 / Seção 9)**:
  - Criação do módulo `src/geometry_material.py` com análise topológica estrutural (`analyze_material_structure`) e corte determinístico (`slice_mesh_by_material`).
  - Distinção automática entre **Componentes Fechados** (`CLOSED_COMPONENT`, ex: corpos desconexos com materiais dedicados) e **Regiões Superficiais** (`SURFACE_PATCH`, ex: decalques ou faces pintadas em superfície contínua).
  - Componentes isolados são separados diretamente preservando manifoldness estrita (0 arestas abertas).
  - Superfícies contínuas com materiais diferentes são extraídas através de projeção prismática com profundidade física ajustável (`material_extrude_depth_mm`), gerando uma peça sólida inserível e a cavidade receptora correspondente no corpo principal.
  - Preservação estrita de slots de materiais e índices de faces em ambas as partes (Critério M1).
- **Diagnóstico e Alerta contra Cascas Abertas em `separate_object_by_material`**:
  - Detecção e registro de `open_edges`, `is_manifold` e `is_solid_for_printing` em sub-peças geradas por simples separação de faces.
  - Aviso explicativo na interface e no operador indicando quando cascas abertas não-imprimíveis foram geradas, orientando o usuário a utilizar o corte por Material com Profundidade.
- **Identidade e Coexistência de Estado (Seção 8)**:
  - Adição do alias `scene.part_splitter` apontando diretamente para `scene.chest_splitter`, permitindo interoperabilidade com novas APIs e migração progressiva.
- **Bateria de Testes Automatizados (Etapa 6)**:
  - Adição da suíte `tests/test_acceptance_etapa6_material.py` cobrindo separação manifold de componentes fechados, extração volumétrica de superfícies contínuas com conservação de volume, Critério M1, detecção de cascas e alias de cena (14/14 suítes aprovadas com 100% de sucesso).

## [0.8.2] - 2026-10-08

### Adicionado
- **Reorganização Didática da Interface e Fluxo Linear (Etapa 5 / Seção 7.1)**:
  - Estruturação do painel em 6 seções lógicas: (1) Objeto Alvo, (2) Método de Corte, (3) Encaixes & Folgas, (4) Prévia do Corte, (5) Criar Peças e (6) Exportação.
  - A Seção 3 (Encaixes) foi posicionada antes do botão de geração da Prévia, respeitando o fluxo natural de que os encaixes alteram a geometria gerada.
  - Remoção de todos os jargões técnicos confusos (ex: "Fase 3A", "Modo D", "Face Semente: 19").
  - Adição de instruções claras no modo Contorno: *"Dica: Selecione apenas 1 face dentro da região desejada (o contorno delimita a seleção automaticamente)"*.
- **Sistema de Ajuda Contextual e Popups Didáticos (`src/translations.py` & `CHEST_OT_splitter_help`)**:
  - Implementação de botões de ajuda compactos com ícone `INFO` em cada seção e recurso principal.
  - Ao passar o mouse, exibe tooltips explicativos detalhados para iniciantes.
  - Ao clicar no botão `INFO`, abre um popup menu legível (`popup_menu`) detalhando o funcionamento, recomendações práticas e exemplos de uso em milímetros.
  - Catálogo nativo de tradução bilíngue (`pt_BR` e `en_US`) registrado via `bpy.app.translations`.
- **Proteção Transacional de Estado Desatualizado (`PREVIEW_STALE` / Critério U2)**:
  - Alterações em qualquer parâmetro de corte ou de encaixe após um preview válido marcam a sessão automaticamente como `PREVIEW_STALE`.
  - Exibição de aviso claro em destaque: *"Os ajustes mudaram. Atualize a prévia antes de criar as peças."*
  - Bloqueio preventivo do botão de confirmação (`commit_parts.poll() == False`) até que o usuário clique em "Gerar / Atualizar Preview", prevenindo inconsistências.
- **Auto-Ajuste Inteligente da Distância de Explosão para Pinos Longos**:
  - Ao gerar a prévia com encaixes ativados, a extensão calcula dinamicamente a distância mínima necessária para que o pino e a cavidade se desacoplem totalmente ($\text{Inserção} + \text{Folga de fundo} + 15\text{ mm}$).
  - Caso o slider de explosão esteja menor que essa medida, ele é elevado automaticamente para garantir visualização perfeita do pino 100% fora do furo na vista explodida.
- **Bateria de Testes U1/U2 (`tests/test_acceptance_etapa5_ui.py`)**:
  - Testes cobrindo integridade do catálogo de ajuda, execução do operador, transição de `PREVIEW_STALE` com bloqueio de commit, e auto-ajuste da visão explodida (13/13 testes aprovados).

## [0.8.1] - 2026-10-08

### Corrigido
- **Correção da Avaliação do Depsgraph Booleano em Atualização de Preview (`geometry_loop` & `geometry_solid`)**:
  - Correção de bug crítico onde `temp_obj_a`, `temp_obj_b`, `cutter_obj` e objetos de trabalho herdavam `hide_viewport = True` do objeto original ocultado após a primeira geração de preview.
  - No Blender 4.x/5.x, o Dependency Graph (`evaluated_depsgraph_get()`) ignora silenciosamente a avaliação de modificadores booleanos para economizar recursos caso o objeto esteja oculto na viewport (`hide_viewport = True`).
  - Como consequência, ao ajustar parâmetros (ex: profundidade do corte ou corte passante) e atualizar o preview, as operações booleanas retornavam a malha original inteira para ambas as partes (duplicando o bloco sem corte e causando Z-fighting).
  - Todos os objetos de trabalho temporários agora forçam explicitamente `hide_viewport = False` e `hide_render = False` antes da resolução booleana, garantindo corte perfeito e determinístico em qualquer reexecução de preview.
  - Adicionado teste de aceitação automatizado de regressão (`tests/test_verify_bug_and_fix.py`) integrado à suíte de testes.

## [0.8.0] - 2026-10-08

### Adicionado
- **Extração Plana com Profundidade (Modo Loop `EXTRUDE`)**:
  - Projeção prismática fechada e manifold do contorno capturado para dentro do modelo até a profundidade física $d$.
  - Preservação estrita de concavidades e relevos superficiais com extensão externa de segurança anti-coplanaridade.
  - Verificação automática de espessura de parede via `BVHTree.ray_cast` para prevenção de perfuração acidental.
  - Opção explícita de **Corte Passante** (`loop_through_cut`) para furos passantes limpos e contínuos.
- **Decisão Automática Inteligente (Modo Loop `AUTO`)**:
  - Análise geométrica em tempo real do relevo da região selecionada em relação ao plano médio.
  - Seleção automática entre **Destacar Saliência** (`DETACH`) e **Extrair com Profundidade** (`EXTRUDE`) acompanhada de justificativa didática em texto na interface.
- **Contrato Formal de Geometria (`CutInterface` & `SplitResult`)**:
  - Padronização em World Space de todas as operações de corte, eixos principais (U/V) via PCA, dimensões reais da interface e normais de contato.
  - Invariância topológica estrita à ordem dos vértices no contorno fechado.
- **Encaixes Transacionais Robustos e Tolerâncias Perfeitas**:
  - Perfil de cápsula com tangentes fechadas e folga perimetral estritamente uniforme em toda a periferia.
  - Validação de espessura de parede na peça receptora (`check_receiving_wall_thickness`) antes de qualquer alteração na malha.
  - Validação de inclusão em polígonos côncavos e detecção de furos internos para evitar encaixes no vazio.
  - Rollback atômico em caso de falha booleana, impedindo estados parciais e protegendo a integridade da cena.
  - Proteção de estado contra operações pós-confirmação (`COMMITTED`).
- **Bateria Completa de Testes de Aceitação Formal**:
  - 11 suítes de testes automatizados integradas cobrindo P1-P2, L1-L5, G1-G2, C1-C5 e E1-E3 com 100% de aprovação no Blender 5.2.0 LTS.

## [0.7.0] - 2026-09-28

### Adicionado
- **Controle de Comprimento Lateral de Encaixes Tipo Cápsula (`connector_capsule_length_mm`)**:
  - Nova opção na Seção 3 para expandir a largura lateral dos pinos oblongos/cápsula ao longo do plano de corte.
  - Folga física uniforme (offset radial) em toda a periferia do encaixe fêmea (tanto na espessura quanto no comprimento lateral alargado).
  - Chanfro perimetral proporcional com offset uniforme nas extremidades.
  - Alinhamento de orientação determinístico: o eixo maior da cápsula acompanha a direção longitudinal da interface de corte e a linha de pinos.
- **Sistema de Limites Coerentes Anti-Colisão (`compute_connector_layout` & `connector_max_safe_lateral_mm`)**:
  - Cálculo automático em tempo real da distância entre centros de encaixes vizinhos, deduzindo folgas e garantindo uma parede sólida mínima de segurança entre cavidades adjacentes.
  - Cálculo da margem segura em relação à borda externa da peça (`edge_margin_mm`).
  - Exibição do limite seguro máximo diretamente na interface do Blender.
  - Ajuste protetor automático (clamping) com aviso amigável quando o valor inserido ultrapassar o limite seguro, prevenindo erros booleanos ou contato indevido.
- **Nova Suíte de Testes Automatizados**:
  - Adicionado `tests/test_capsule_lateral_size.py` cobrindo geometria, folgas uniformes, limites matemáticos, detecção de colisão e corte completo (8/8 suítes aprovadas).

## [0.6.1] - 2026-09-28

### Corrigido & Aprimorado
- **Orientação e Inversão de Encaixes (Macho / Fêmea)**:
  - Corrigido cálculo do vetor normal dos encaixes quando `invert_sides` está ativo (`effective_normal_a`), evitando que pinos fossem gerados voltados para o interior do modelo.
  - Adicionada detecção geométrica automática de qual parte é Superior e qual é Inferior com base na coordenada Z de mundo.
  - Adicionado botão direto de inversão de encaixes na Seção 2 (`Inverter Pinos: Macho na Parte Superior / Inferior`).
  - Adicionado seletor visual e botão de inversão detalhado na Seção 3 com indicação textual imediata de status.

## [0.6.0] - 2026-09-28

### Adicionado
- **Suporte Completo a Modelos Multicores e Materiais**:
  - Preservação estrita de todos os slots de materiais e índices de faces originais durante cortes nos modos Plano (`PLANE`), Cortador Sólido (`SOLID`) e Loop Fechado (`LOOP`).
  - Atribuição inteligente de materiais nas tampas de interface de corte (capping faces), herdando automaticamente o material predominante das faces vizinhas imediatas.
  - Sincronização de materiais em pinos e cavidades de encaixe, prevenindo a criação de slots nulos (`None`) após operações booleanas.
- **Alternador de Modo de Exibição de Cores na Viewport (`preview_color_mode`)**:
  - Modo `Cores Originais (Materiais)`: exibe fielmente as cores, materiais e shaders originais do modelo.
  - Modo `Cores A / B (Contraste)`: destaca Parte A (Azul) e Parte B (Laranja) para inspeção geométrica rápida.
- **Operador "Separar Peças por Cores / Materiais" (`chest.splitter_separate_by_material`)**:
  - Divide qualquer peça multicolor em sub-objetos individuais por material/cor, mantendo o alinhamento espacial perfeito para impressão multicolor em sistemas tipo AMS / MMU.
- **Módulo de Exportação Direta para Fatiadores (`src/io_export.py` e `chest.splitter_export_parts`)**:
  - Exportação nativa em **3MF Multimaterial (.3mf)** com `<m:colorgroup>` compatível com Bambu Studio, OrcaSlicer e PrusaSlicer.
  - Exportação em **STLs por Material / Cor (.stl)** com coordenadas globais alinhadas para importação como objeto multipartes.
  - Exportação em **Wavefront OBJ (.obj + .mtl)**.
- **Correção de Interface**:
  - Botão de Gerar Preview, visualização e confirmação de divisão habilitados também para o Modo Loop Fechado (`LOOP`).
- **Suíte de Testes Automatizados**:
  - Adicionado `tests/test_multicolor_support.py` cobrindo cortes planares, sólidos, encaixes com materiais, separação por material e exportação para 3MF e STL. Total de 7 suítes com 100% de aprovação no Blender 5.2 LTS.

## [0.5.0] - 2026-09-08

### Adicionado
- **Fase 3A — Modo Loop Fechado de Arestas**:
  - Captura e validação de loop de arestas em Edit Mode (`capture_edge_loop`).
  - Separação direta da geometria (Caminho D1) por região e face-semente (`slice_mesh_by_loop`).
  - Fechamento manifold de tampas internas compartilhadas.

## [0.4.0] - 2026-09-06

### Adicionado
- **Fase 3 — Cortador Sólido Personalizado**:
  - Módulo de geometria volumétrica (`src/geometry_solid.py`) para corte tridimensional usando cortadores fechados e manifold.
  - Quatro primitivas paramétricas integradas: Caixa (`BOX`), Cilindro (`CYLINDER`), Esfera (`SPHERE`) e Cápsula (`CAPSULE`), geradas diretamente na coleção de guias (`CHEST_SPLITTER_GUIDES`).
  - Suporte a Cortador Existente da cena: selecione qualquer malha fechada para atuar como ferramenta de corte volumétrico.
  - Validação estrita e bloqueante do cortador (`validate_solid_cutter`):
    - Rejeição imediata com feedback amigável para malhas não-manifold (arestas abertas, normais invertidas).
    - Verificação de volume nulo ou degenerado.
    - Teste de colisão por bounding box com o modelo alvo antes de qualquer computação booleana pesada.
  - Fatiamento volumétrico com solver EXACT booleano no espaço de mundo (`slice_mesh_by_solid`):
    - Parte A = Interseção ($Alvo \cap Cortador$).
    - Parte B = Diferença ($Alvo \setminus Cortador$).
    - Suporte nativo à inversão rápida de papéis ($A \leftrightarrow B$) via `invert_sides`.
  - Visualização explodida volumétrica interativa calculada ao longo do vetor entre os baricentros (centróides) das Partes A e B.
  - Atualização completa da Seção 2 da interface na Sidebar N com alternador de modo (Plano / Sólido), seleção de fonte, parâmetros do cortador e métricas de diagnóstico em tempo real (manifold, triângulos, volume e dimensões).
  - Suíte de 55 testes automatizados na Fase 3 (`tests/test_smoke_phase3.py`), totalizando 144 testes no projeto com 100% de aprovação no Blender 5.2 LTS.

## [0.3.1] - 2026-09-06

### Corrigido
- **Correção Crítica de Escala e Topologia de Encaixes**:
  - Eliminado bug onde `base_offset` (0.5) e `tip_r` (0.2) em `create_pin_mesh_data` eram interpretados diretamente em Blender Units (metros), gerando pinos e cavidades gigantes de 400 mm a 500 mm em cenas milimétricas/métricas.
  - O cálculo de `base_offset` e raio de chanfro `tip_r` agora é estritamente proporcional e invariante à escala da geometria (`min(eff_length * 0.05, eff_radius * 0.1)`).
  - Corrigido o traçado paramétrico da chave cápsula (`create_capsule_2d_profile`), eliminando auto-interseções em formato bowtie e garantindo malhas 100% manifold com normais consistentes para o solver EXACT booleano.
  - Padronização de `get_scene_scale_to_mm(scene)` em todo o ciclo de vida dos operadores para suporte transparente tanto a cenas em metros quanto em milímetros.
  - Adicionado teste automatizado de regressão no cubo de 97,2 mm do usuário (`test_smoke_phase2.py` Teste 10), garantindo dimensões exatas de 97,2 x 97,2 x 58,6 mm (macho) e 97,2 x 97,2 x 48,6 mm (fêmea) com 0 arestas não-manifold.

## [0.3.0] - 2026-09-06

### Adicionado
- **Fase 2 — Encaixes em Cortes Planos**:
  - Módulo paramétrico de conectores (`src/geometry_connectors.py`) para pinos cilíndricos com chanfro de entrada e chaves cápsula anti-rotação.
  - Convenção rigorosa de folga física: dimensão nominal exata no macho, expansão radial por lado na cavidade fêmea ($D + 2c$) e folga de fundo ($L + c_{fundo}$).
  - Quatro presets de calibração FDM para PLA e bico 0,4 mm: Justo (0,10 mm), Normal (0,15 mm), Fácil (0,20 mm) e Solto (0,25 mm), além de valor livre.
  - Distribuições automáticas no plano de corte: 1 pino (Centro), 2 pinos (Linha), 3 pinos (Linha) e 4 pinos (Grade 2x2), com margem de segurança configurável da borda externa.
  - Validações bloqueantes contra sobreposição entre encaixes e violação de margem de borda (`ConnectorValidationError`).
  - Operações booleanas robustas com solver EXACT no BMesh (`UNION` do macho e `DIFFERENCE` da cavidade).
  - Operador de inversão rápida de macho/fêmea (`chest.splitter_invert_male_female`) e seleção de presets (`chest.splitter_apply_connector_preset`).
  - Atualização completa da Seção 3 da interface na Sidebar N (`Viewport 3D -> Chest -> Part Splitter`).
  - Suíte de 34 testes automatizados na Fase 2 (`tests/test_smoke_phase2.py`) cobrindo aferição micrométrica, validação de todos os 4 presets, múltiplos pinos, chave cápsula e conservação de integridade manifold.

## [0.2.0] - 2026-09-06


### Adicionado
- **Fase 1 — Corte por Plano**:
  - Módulo de geometria planar (`src/geometry_plane.py`) com bisect e fechamento manifold automático (*capping*) via `edgenet_fill` e `holes_fill`.
  - Objeto guia visual de plano na Viewport 3D (`CHEST_SPLITTER_PLANE_GUIDE`) redimensionado automaticamente ao tamanho do alvo.
  - Operador de alinhamento rápido do plano (`chest.splitter_align_plane`) por Vista 3D, Cursor 3D, Face selecionada e Eixos X/Y/Z.
  - Operador de geração de preview não destrutivo (`chest.splitter_generate_preview`) com cálculo instantâneo das Partes A e B.
  - Visualização Montada vs Explodida com controle interativo de distância de explosão em milímetros (`explosion_distance_mm`).
  - Alternador de inversão de lados (`chest.splitter_invert_sides`) para alternar papéis de A e B.
  - Diagnóstico em tempo real para as partes divididas (volumes, dimensões, verificação de manifold, número de componentes desconexos e conservação de volume).
  - Operador de confirmação (`chest.splitter_commit_parts`) que gera `<alvo>__A` e `<alvo>__B` na coleção `CHEST_SPLITTER_PARTS`.
  - Operador de restauração do original (`chest.splitter_restore_original`) e refazer sessão (`chest.splitter_redo_session`).
  - Suíte de 38 testes automatizados headless no Blender 5.2 (`tests/test_smoke_phase1.py`), incluindo cortes inclinados, alvo transformado, conservação de volume e prevenção de vazamento de memória em 20 ciclos de preview.

## [0.1.0] - 2026-09-06


### Adicionado
- **Fase 0 — Fundação da Extensão**:
  - Manifesto oficial de extensão para Blender 5.2+ (`blender_manifest.toml`).
  - Painel principal em `Viewport 3D -> Barra lateral (N) -> Chest -> Part Splitter`.
  - Operador para selecionar e registrar o objeto alvo (`chest.splitter_set_target`).
  - Diagnóstico em tempo real da malha: dimensões físicas em mm, contagem de triângulos e faces, volume.
  - Alertas automáticos para escala não aplicada, arestas não-manifold e faces degeneradas.
  - Operador seguro `Criar cópia de trabalho com transformações aplicadas` preservando 100% o modelo original.
  - Coleções dedicadas para isolamento: `CHEST_SPLITTER_GUIDES` e `CHEST_SPLITTER_PREVIEWS`.
  - Registro e ciclo de vida idempotentes.
  - Suíte de smoke tests automatizados em modo headless (`tests/test_smoke_phase0.py`).
