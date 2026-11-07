# Folga lateral afunila o encaixe

Diagnóstico confirmado no código local e reproduzido no Blender 5.2.0 LTS.
Esta análise não altera os módulos do add-on nem a instalação do Blender.

## Caminho responsável

1. `geometry_material.py`, ramo EXTRUDE com `_region_has_relief`, delega para `slice_mesh_by_loop_extrude`.
2. `geometry_loop.py`, `slice_mesh_by_loop_extrude`, detecta relevo e chama `slice_mesh_by_loop` com `detach_add_base=True`.
3. No ramo de base profunda de `slice_mesh_by_loop`, apenas `new_verts_a` e `new_verts_b` recebem o deslocamento lateral.
4. As faces laterais conectam esses novos vértices aos `loop_verts_a`/`loop_verts_b` originais, que continuam na posição nominal. A lateral é uma rampa entre contornos de tamanhos diferentes.

O comentário do próprio ramo descreve o fundo da base encolhido. O resultado implementa afunilamento, incompatível com uma folga lateral constante ao longo da inserção.

## Reprodução

`reproduce.py` cria uma placa estanque com relevo quadrado de 20 x 20 mm, altura de 3 mm e corte de 2 mm. Executa a API pública de corte por material em PART, CAVITY e BOTH com folgas 0, 0.1 e 1 mm. Não usa o arquivo privado das capturas.

Com PART:

| Folga mm | Largura na entrada (z=0) mm | Largura no fundo mm | Profundidade final mm |
|---|---|---|---|
| 0 | 20 | 20 | 2 |
| 0.1 | 20 | 19.8 | 1.9 |
| 1 | 20 | 18 | 1 |

Em CAVITY, a entrada permanece 20 mm e o fundo aumenta para 20.2/22 mm. Em BOTH, ambas as partes afunilam em sentidos opostos, mantendo a entrada nominal e sem folga lateral nessa altura. As nove execuções retornam peças manifold; esse critério não detecta a incorreção dimensional.

A folga de fundo não foi separada nesta reprodução: o comportamento padrão usa a folga lateral também no eixo de profundidade. Separar o fundo muda a profundidade, mas não corrige a aplicação lateral apenas nos vértices inferiores.

## Direção da correção

Construir a região de encaixe usando um contorno deslocado igualmente em todas as alturas relevantes, com paredes paralelas à direção de extração. O deslocamento axial do fundo deve ser independente. Se o relevo externo precisar manter a dimensão nominal, a transição deve ser um ombro na entrada, preservando o trecho de inserção com seção constante.

O ramo prismático já aplica deslocamento lateral aos dois níveis do cortador; entretanto, o roteamento de regiões com relevo toma o ramo topológico acima. Uma correção precisa preservar concavidades, saliências e regiões não planas que motivaram esse roteamento; simplesmente deslocar os vértices originais pode deformar o relevo.

Validar dimensões em seções de várias alturas nos três destinos de folga, além de estanqueidade e volume. Os resultados brutos estão em `measurements.json`.
