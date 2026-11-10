# Validação física dos previews repetidos — etapa 1

## Resultado

Em Blender 5.2.0 LTS, os dez subcasos de `test_loop_auto_uses_selected_depth` (dois corpos, folga configurada de 0,15 mm, profundidades de 1, 2, 5, 10 e 15 mm) passaram com comparação geométrica tolerante a reindexação. A suíte inteira `test_release_workflows.py` passou: **11 testes**, incluindo os nove métodos originais e dois testes dos helpers; o teste negativo isolado de reindexação também passou.

## Critérios físicos e semânticos

- Correspondência bijetiva de vértices dentro de 0,001 mm; ciclos de faces mantêm orientação, `material_index` e UVs de todas as camadas após o mapeamento.
- Distância bidirecional de vértices, arestas e centróides das triangulações visíveis, usando `calc_loop_triangles()` e `BVHTree.FromPolygons(..., all_triangles=True)`. Para o refinamento das distâncias, usa-se ponto-triângulo em precisão dupla, com busca exaustiva quando o resultado inicial do BVH excede 0,001 mm.
- Volume, caixa delimitadora, profundidade selecionada, materiais e snapshot da malha/transformação da fonte também foram verificados.

Máximos observados nos 20 pares de peças: distância superfície-superfície **0,0005192 mm**; distância vértice-vértice **0,0004197 mm**; diferença de caixa delimitadora **0 mm**; diferença de volume por peça **0,0002968 mm³**. A soma dos volumes repetidos ficou idêntica à primeira geração nos dez casos. Erro máximo da profundidade de referência: **0,0000086 mm**. Materiais e fonte permaneceram inalterados. A propriedade de folga foi `0,15000000596 mm`, aplicada a `PART`.

## Reindexação e UVs

A assinatura exata canonizada diferiu em **6 de 20** peças para vértices/faces e em **7 de 20** para triângulos visíveis. Os sete pares correspondentes passaram as verificações de bijeção, ciclos orientados, materiais/UVs, volume, caixa e distância física até 0,001 mm. O teste negativo confirma que mudança de winding, material, UV ou deslocamento acima da tolerância é rejeitada.

O fixture privado de origem não tem camadas UV (`0` casos com UV de origem). A comparação suporta UV por canto em todas as camadas quando presentes, mas esta rodada não pode provar preservação de UVs que não existem no fixture.

## Arquivos

- `replay_validation_099.json`: dez casos e métricas por peça, incluindo assinaturas exatas e tolerantes.
- `run_replay_validation_099.py`: driver reprodutível da medição.
- `driver_final.log`: log da execução do driver (10/10).
- `release_workflows_final.log`: log da suíte Blender (`Ran 11 tests ... OK`).
- `reindex_helper_final.log`: execução isolada dos negativos de winding/material/UV/tolerância.

Não houve alteração de módulos de produção, rebuild do ZIP ou criação de nova versão.
