# Verificação geral e correção da folga

Validado no Blender 5.2.0 LTS em 30/10/2026. Pacote: `dist/chest_part_splitter-0.8.32-folga-uniforme.zip`.

## Resultado por caminho

| Caminho | Implementação verificada | Resultado |
|---|---|---|
| Plano completo | Deslocamento de cada plano de corte | Folga uniforme; medição dimensional nos três destinos |
| Plano limitado | Deslocamento do plano dentro da região delimitada | Regressões de localização, inversão, transformação e conectores aprovadas |
| Sólido | Deslocamento dos planos do cortador completo | Paredes paralelas; medição em três alturas e nos três destinos |
| Contorno, fechamento direto e degrau 3D | Deslocamento das superfícies de contato, com preservação dos planos externos | Regressões de planos de apoio, distâncias e geometria aprovadas |
| Contorno, profundidade com relevo | Banda fechada de material removida da região de inserção | Corrigido: paredes com seção constante e ombro junto ao relevo preservado |
| Material, profundidade com relevo | Compartilha o motor de contorno | Mesma correção e testes dimensionais |
| Material/contorno, região plana com profundidade | Prismas com ambos os níveis deslocados | Seção constante confirmada; removida limitação indevida da folga lateral pela profundidade |
| Material, na base | Separação axial pela interface plana | Corrigido o uso da folga de fundo separada; teste nos três destinos |
| Regiões com aberturas/molduras | Prismas com deslocamento dos contornos externo e internos | Regressões de furos, centro preservado, transformações, materiais e pinos aprovadas |
| Região inteira por faces/material | Remoção da faixa de contato espacial | Regressões de superfície, materiais, montagem e folga aprovadas |
| Componentes já fechados por material | Separação de componentes existentes | Não cria uma interface nova para aplicar folga |
| Conectores | Folgas radial e axial próprias dos alojamentos | Regressões de dimensões, posicionamento, materiais e resíduos aprovadas |

Em interfaces planas sem paredes laterais de inserção, a separação é axial. Em contatos espaciais sem eixo único de inserção, a faixa acompanha as superfícies de contato. Isso preserva a semântica geométrica de cada modo.

## Alterações

- `geometry_loop.py`: constrói primeiro a base nominal e depois aplica a remoção completa de material. Retira o deslocamento exclusivo do contorno inferior. Mantém o relevo selecionado, seu material, a ordem original dos polígonos e os UVs das faces restauradas.
- `geometry_clearance.py`: nova operação `trim_depth_contact`, com deslocamentos lateral e axial independentes. Intersecta os planos de contato, fecha a banda e a subtrai da peça. Restringe a banda à região de inserção abaixo do relevo e rejeita colapso/resultado aberto.
- `geometry_material.py`: respeita a folga de fundo separada no corte na base; a validação de profundidade passa a usar a componente axial efetivamente aplicada. A verificação de espessura da cavidade considera a profundidade ampliada pela folga.

A preservação de relevos curvos exigiu usar a tesselação visível original antes da subtração e restaurar os polígonos completos depois dela. Isso evita modificar as diagonais de faces não planas.

## Evidência dimensional

`tests/test_clearance_uniformity.py` cobre 105 subcasos em quatro métodos de teste:

- 90 combinações de caminho, destino da folga e valores lateral/fundo; medidas nas quatro direções laterais e em três alturas, mais profundidade final;
- 6 combinações de folga de fundo independente no material na base;
- 6 combinações de plano/sólido e destino;
- 3 destinos no corte passante, medidos perto da entrada, no meio e perto da saída.

Inclui folga lateral de 3 mm com profundidade de 2 mm e fundo zero, confirmando a independência dos parâmetros. O teste também verifica faces/arestas/vértices manifold, volume positivo e preservação das coordenadas do modelo fonte.

Para o quadrado nominal de 20 mm, profundidade 2 mm e folga 1 mm aplicada à peça: o encaixe mede 18 mm em todas as seções abaixo do ombro; a cavidade mede 20 mm. Com fundo ligado à mesma folga, a profundidade da peça é 1 mm. Com fundo separado em zero, continua 2 mm.

## Regressões e pacote

16 suítes distintas aprovadas: `test_release_geometry`, `test_plane_limited`, `test_frame_regions`, `test_clearance_profiles`, `test_planar_seats`, `test_whole_region_material`, `test_solid_edit_tools`, `test_connector_clearance_slivers`, `test_clearance_uniformity`, `test_release_depth_region`, `test_release_depth_guard`, `test_release_connector_frames`, `test_stepped_frame_support`, `test_region_release`, `test_release_interface`, `test_release_material_patch`.

Após os ajustes finais, as suítes diretamente afetadas foram repetidas; os resultados estão em `final_checks/summary.json`, `uniformity.log` e `horn_final.log`. Os demais resultados estão em `regressions/summary.json` e `final_regressions/summary.json`.

O pacote foi montado com a rotina de preparação do projeto, inspecionado quanto a conteúdo e integridade e aprovado pelo comando oficial de validação de extensões do Blender. A instalação usada pela interface aberta não foi substituída.
