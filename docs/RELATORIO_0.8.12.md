# Part Splitter 0.8.12 — revisão, correções e testes

Data: 15/10/2026. Base: `chest-blender-part-splitter(3).zip`, versão interna 0.8.11. Esta entrega altera o código; não é apenas um plano para o Antigravity.

## Resultado

Foram mantidos os quatro métodos de corte, os padrões de pinos, o editor manual, os encaixes cilíndricos/cápsula, as folgas, o destaque com base, as prévias montada/explodida, a reversão e os formatos de exportação existentes. Não foram acrescentados controles à interface. A grade continua sendo uma referência visual fixa de 5 mm, sem snap, exibida durante a edição manual.

A alteração foi concentrada nos defeitos reproduzidos. Não houve reescrita integral do motor geométrico. A identidade da extensão e a licença original foram preservadas.

## Falhas corrigidas e evidência

| Área | Causa encontrada | Correção |
|---|---|---|
| Loop no editor manual | Remover prévia reatribuía o mesmo alvo, cujo callback apagava a captura | Callback idempotente com referência persistente; remoção não reatribui o mesmo alvo |
| Reedição | Limpeza defensiva apagava qualquer malha da coleção de prévias | Remoção limitada à sessão; preparação ocorre antes de descartar a prévia |
| Operações independentes | Fallback por papel removia prévias de outra operação | IDs de operação/sessão respeitados; fallback reservado a objetos antigos sem IDs |
| Cancelar edição | Lista vazia de entrada não era restaurada pelo botão | Snapshot vazio também é restaurado; cancelar fora de edição não reaplica snapshot antigo |
| Confirmação | Retorno CANCELLED podia ser seguido de mensagem de sucesso | Sucesso somente quando o operador de geração retorna FINISHED |
| Sessões modais | Instância antiga podia sobreviver ao fechamento por botão e reabertura | Identificador de geração aposenta o modal antigo sem encerrar o novo |
| Arraste | Soltar o mouse fora da região WINDOW deixava arraste ativo | Liberação do botão tratada antes do filtro de regiões; navegação com Alt passa ao Blender |
| Macho na Parte B | Rotações individuais continuavam orientadas A→B | Rotação recebe a normal real de inserção, incluindo macho B |
| Referência U/V | Eixos eram invertidos sem reprojetar os polígonos de validação | Usa a mesma base determinística produzida pela geometria, sem reflexões isoladas |
| Cache | Assinatura ignorava alterações de coordenadas, unidades, guia e opções de base | Hash em lote da geometria e configuração completa; guia resolvido pela matriz atual |
| Plano com modificadores | Preparação manual usava malha diferente da geração | Preparação usa a mesma malha avaliada e rotina de corte do preview |
| Explosão | Plano podia usar normal antiga; sólido recebia direção Z genérica | Snapshot usa normal real do guia ou direção própria da divisão sólida |
| Pino sobre furo pequeno | Amostras do perímetro não detectavam furo totalmente contido | Teste analítico de disco/cápsula contra segmentos de contorno e furos |
| Cápsulas paralelas | Distância mínima usava comprimento total em toda direção | Distância real entre segmentos centrais, com orientação individual |
| Extração não plana | Profundidade podia fabricar um prisma sem apoio confiável | Bloqueio explícito para contorno de apoio não planar; destaque de volume permanece |
| Material com base plana | Arredondamento acumulado da normal gerava pequena inclinação e falhas de booleana | Preserva o referencial anterior; em falha numérica, tenta uma vez a normal acumulada em precisão dupla |
| Cortador ancorado | Callback usava Vector sem importar; exceção era engolida | Import corrigido e teste verifica dimensão e preservação da âncora |
| Preferências instaladas | bl_idname apontava para o subpacote .src | Preferências registradas no namespace raiz; teste do ZIP confere seleção PT/EN |
| Status | Código de tradução antigo podia esconder um erro novo | Atribuição direta de status limpa o código anterior |
| Carregar/Undo/Redo | Cache e estado modal podiam sobreviver aos datablocks antigos | Invalidação explícita e encerramento da edição volátil |

A tentativa adicional por material mantém **EXACT**, não preenche buracos arbitrariamente, não aplica deslocamentos artificiais e não relaxa as validações. Se as duas tentativas falharem, a operação continua bloqueada. Os BMeshes das tentativas rejeitadas são liberados.

A captura de loop é verificada no BMesh vivo durante Edit Mode. A validação chamada pelo desenho não sincroniza nem escreve no Mesh datablock. A sincronização necessária para operações geométricas ocorre fora do desenho.

## Testes executados

| Ambiente real de geometria | Suítes executadas | Resultado |
|---|---:|---|
| bpy oficial 4.2.23 / Linux / Python 3.11 | 44 | 44 aprovadas |
| bpy oficial 4.5.3 LTS / Linux / Python 3.11 | 44 | 44 aprovadas |
| bpy oficial 5.0.1 / Linux / Python 3.11 | 44 | 44 aprovadas |

São **132 execuções de suítes**, não 132 cenários distintos. Foram acrescentados **34 métodos de teste**: 31 na suíte de regressões 0.8.12 e 3 na suíte da malha do usuário. Vários métodos percorrem subcasos, como padrões de pinos e regiões de material. A suíte de 29 regressões usada na comparação intermediária retornou 20 falhas contra a base original; esse número inclui subcasos e não representa 20 bugs independentes.

As verificações abrangem:

- Capturar loop, gerar prévia e entrar novamente na edição duas vezes, mantendo captura e pinos.
- Mesmo alvo versus troca real de alvo; leitura da captura em Edit Mode; invalidação após mudança topológica.
- Cancelamento de lista vazia e preenchida; preservação de IDs/posições.
- Macho A/B, padrões CENTER, LINEAR_2, LINEAR_3, GRID_4 e AUTO_SHAPE em peças compatíveis.
- Extração plana por loop, base adicional, folga e bloqueio de profundidade não plana.
- Cavidades, materiais, cápsulas orientadas, furos e colisões.
- Plano movido/rotacionado, modificadores, escala da cena, alterações que mantêm as contagens de vértices/faces.
- Reversão, confirmação, isolamento de operações, exportação, salvar/reabrir e integridade de pacotes, nas suítes existentes.
- Arraste liberado fora do viewport e aposentadoria de uma instância modal antiga, por eventos simulados.

O ZIP também foi extraído em um namespace `bl_ext.user_default.chest_part_splitter` isolado: registro, preferências PT/EN, corte, confirmação, reversão e desativação passaram. A suíte confere que os bytes testados correspondem ao código empacotado.

Verificações adicionais: compilação dos módulos Python; análise estática Ruff para nomes indefinidos, variáveis locais e erros de sintaxe; inspeção de membros e CRC do ZIP; validação do pacote pelo CLI oficial de extensões distribuído com o Blender. Todas passaram.

Dois problemas de infraestrutura dos testes antigos foram corrigidos: uma suíte não registrava a extensão quando executada isoladamente; outra mantinha seleção/visibilidade residual ao construir o caso de loop. As listas de versões aceitas foram atualizadas, e o runner passou a descobrir todas as suítes. O teste de distribuição passou a usar o pacote 0.8.12 efetivamente gerado. Asserções geométricas não foram removidas para conseguir aprovação.

## Uso do arquivo Padrão 1.blend

O arquivo enviado foi aberto para diagnóstico, sem sobrescrevê-lo. Ele registra Blender 5.2; versões anteriores avisam sobre a diferença de versão. Para executar a geometria nas três APIs sem depender do layout de uma versão posterior, foi extraída uma malha neutra em JSON, com coordenadas, faces, materiais e matriz de transformação.

A fixture `tests/fixtures/padrao1_mesh.json` conserva os dados da malha `Extração por material`. Os testes percorrem suas nove regiões do material `Funciona`, verificam o caso do material `Erro` que apresentava falha numérica e confirmam a rejeição da região não plana `Erro Critico`. O arquivo .blend original não faz parte do instalador.

## Limites desta validação

- Os testes usam os módulos oficiais bpy e as booleanas reais do Blender, em modo sem interface. Não houve operação do mouse nem inspeção visual do viewport em um Blender Windows.
- Blender 5.2 não estava disponível como runtime de teste. O mínimo declarado permanece 4.2; a aprovação das APIs 4.2, 4.5 e 5.0 não equivale a homologação do Blender 5.2.
- O desenho GPU, contraste, zoom, captura por clique, navegação e comportamento sob diferentes drivers ainda precisam de teste visual.
- O corte de contornos não planos foi preservado. A grade é omitida nesses casos, e a projeção/posição dos pinos em superfícies curvas precisa de validação adicional com seus modelos. Não foi criado um novo sistema de parametrização de superfícies curvas nesta versão.
- Foram centralizados rótulos do painel e acrescentadas traduções do editor; ainda existem diagnósticos e textos dinâmicos antigos que precisam de revisão PT/EN. A entrega não promete tradução integral revisada.
- Geometria de entrada com autointerseções, tangências e regiões muito finas ainda pode levar a rejeição segura. Nenhuma suíte finita comprova ausência total de bugs em malhas arbitrárias.
- Não houve impressão física nem teste no Bambu Studio nesta execução.

## Teste visual recomendado para esta versão

1. Instalar o ZIP 0.8.12 e conferir o número no painel.
2. Capturar um loop/perímetro, iniciar Manual, colocar quatro pinos fora de uma única linha e arrastá-los. Soltar um deles fora do viewport.
3. Cancelar, reabrir, posicionar e confirmar; gerar a prévia, reabrir o editor e confirmar novamente. Repetir para Plano e Material.
4. Trocar macho A/B e conferir a direção dos pinos e das cavidades.
5. Mover/rotacionar o guia, regenerar e conferir a linha laranja e o afastamento explodido. Conferir também um cortador sólido lateral.
6. Confirmar, reverter, salvar/reabrir e exportar. No fatiador, conferir medidas, cores, cavidades e posição montada.

Esses passos completam a validação visual que não pode ser substituída pelos testes sem interface.

## Referências e decisões de implementação

Foram consultados os exemplos oficiais efetivamente instalados no pacote Blender 4.5.3:

- `scripts/templates_py/operator_modal.py`: ciclo de eventos e cancelamento/restauração.
- `scripts/templates_py/operator_modal_draw.py`: draw handlers, região WINDOW, desenho e limpeza.
- `scripts/templates_py/operator_modal_view3d_raycast.py`: coordenadas de região, raycast, transformações e distinção entre objeto avaliado e original.
- `scripts/addons_core/bl_pkg/cli/blender_ext.py`: validação oficial de manifesto/pacote; executado nesta entrega.

Referências oficiais para manutenção:

- [BMesh API](https://docs.blender.org/api/current/bmesh.html)
- [Projeto BMesh no código do Blender](https://developer.blender.org/docs/features/objects/mesh/bmesh/)
- [SpaceView3D e draw handlers](https://docs.blender.org/api/4.5/bpy.types.SpaceView3D.html)
- [Exemplos oficiais de modal e desenho](https://github.com/blender/blender/blob/main/scripts/templates_py/operator_modal_draw.py)
- [Exemplo oficial de raycast](https://github.com/blender/blender/blob/main/scripts/templates_py/operator_modal_view3d_raycast.py)

A busca pública retornou documentação BMesh/SpaceView3D. Parte das páginas não pôde ser aberta integralmente pelo serviço de pesquisa; nesses pontos a verificação técnica usou o código oficial instalado, não conteúdo presumido de páginas inacessíveis. Não foi incorporado código de extensões comerciais de terceiros.

## Conteúdo entregue

- `chest_part_splitter-0.8.12.zip`: instalador com manifesto, código-fonte Python de execução, licença, README e changelog. Sem caches, .blend, capturas ou ZIPs antigos.
- `chest_part_splitter-0.8.12-dev.zip`: fonte de desenvolvimento, testes, fixture, logs das três versões, relatório, patch comparativo e scripts. Não é um instalador.

A pasta `evidence/` do pacote de desenvolvimento contém os logs e os resumos por versão. `docs/ALTERACOES_0.8.12.patch` permite revisar as diferenças de implementação sem os históricos e imagens do ZIP original.
