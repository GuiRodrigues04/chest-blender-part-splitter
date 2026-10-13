# INV-008 — Folga de interface altera profundidade, mas não laterais

12/10/2026. Complemento do plano Gemini e do INV-007.

## Evidência

Cube.001, material Funciona, Área 2 com 23 faces, região superficial côncava, Extrair com Profundidade, profundidade 20 mm, Manter Origem. Prévia gerada com sucesso.

| Configuração | Largura indicada | Volume A | Volume B |
|---|---|---|---|
| Folga zero | 0,15565 m = 155,65 mm | 445.775 mm³ | 14.999.916 mm³ |
| Folga 5 mm; aplicar em Peça Extraída | 0,15565 m = 155,65 mm | 334.332 mm³ | 14.999.916 mm³ |

O contorno verde permanece visualmente igual. V5/V0≈0,7500, compatível com profundidade 20→15 mm e área transversal constante. Essa é inferência quantitativa, não medição direta da profundidade. Confirmar que a régua mede a prévia atual, e não a origem; capturar vértices e seções reais A/B.

As imagens também mostram que extração com profundidade funciona nessa região antes bloqueada em DETACH. Isso reforça INV-007 como conflito de modo; não prova imprimibilidade completa.

## Requisito confirmado pelo usuário

Folga em mm POR LADO, incluindo laterais da interface de contato. Não limitar à direção de profundidade.

Se g=0,30 mm e a cavidade permanece nominal:

- Cada lateral oposta do inserto recua 0,30 mm.
- Uma dimensão nominal W entre duas paredes opostas passa a W−0,60 mm.
- O espaço medido entre inserto e cavidade é 0,30 mm em cada lado.

Exemplo de teste retangular: W=40 mm, H=30 mm, D=20 mm. Com g=0,30 mm aplicado à peça extraída, inserto W=39,40 e H=29,40 mm. Se a folga de fundo for igualmente g e a frente externa ficar fixa, D=19,70 mm. Esse último comportamento precisa ser explícito na UI: superfície exterior livre não é interface de contato.

Na captura com g=5 mm, um par de paredes laterais opostas que define a largura nominal 155,65 mm deveria resultar em 145,65 mm no inserto, caso o offset seja viável e essas paredes realmente definam a largura medida. Para a forma côncava, medir cada parede além do bounding box.

## Aplicar em: semântica

| Alvo | Comportamento lateral |
|---|---|
| Peça extraída | Erodir domínio do inserto por g; receptor nominal preservado. |
| Corpo/receptor, se essa opção existir | Expandir cavidade por g; inserto nominal preservado. |
| Ambos, se existir | Dividir g entre os lados, por padrão g/2 em cada peça, para que o espaço final continue g. Se outra semântica for adotada, mostrar explicitamente o espaço final. |

“Por lado” significa espaço em cada parede de contato, não duplicar g em cada operando. Em faces oblíquas, medir na normal local da parede.

## Implementação proposta para regiões planares extrudidas

1. Cortar nominalmente A0 e B0 com g=0.
2. Extrair domínio 2D real no plano da região e ciclos ordenados, distinguindo contornos exteriores e interiores. Preservar concavidades e segmentos relevantes.
3. Para reduzir inserto, aplicar erosão geométrica do domínio por g: contorno exterior recua e bordas de vazios/reentrâncias avançam sobre o material. Não usar a mesma direção ingênua para todo ciclo.
4. Gerar volume offset para esse domínio na profundidade configurada; aplicar folga de fundo separadamente se prevista. Recortar somente faces de interface; preservar superfícies livres/silhueta externa conforme o contrato escolhido.
5. Para ampliar receptor, usar dilatação do domínio da cavidade e booleano no receptor nominal; não reduzir inserto como efeito colateral.
6. Decidir tratamento de cantos, limite de miter e arcos explicitamente. Um offset de parede não garante distância euclidiana mínima de g em toda esquina; validar e documentar a convenção. Cantos côncavos precisam de tratamento geométrico, não deslocamento radial pelo centro.
7. Usar algoritmo robusto de offset/interseção poligonal já disponível no projeto ou dependência distribuível com a extensão. Não pressupor que biblioteca Python instalada no Antigravity exista no Blender do cliente; validar licença e pacote.
8. Se g colapsa uma faixa, elimina uma ilha ou divide uma região, mostrar quais detalhes são afetados. Não remover fragmentos silenciosamente nem conectar componentes artificialmente.
9. Para patches curvos/dobrados e saliências gerais, esse offset 2D não é solução universal. Limitar o suporte e explicar; não projetar superfície inteira para um plano ocultamente.
10. Revalidar espessura, incidência, materiais e regiões após a folga. Conservação de volume exata não é aceite de operação com folga; a perda intencional deve corresponder ao espaço de montagem.

## Onde investigar no código

A 0.8.6 anexada não contém controle de folga de interface “Aplicar em” como mostrado nas capturas. Há clearance_per_side_mm, mas essa propriedade é de encaixes; não confundir com o novo recurso.

- src/geometry_material.py: slice_mesh_by_material recebe depth_mm, não folga de interface. create_material_patch_prism_cutter preserva faces do patch.
- src/operators.py: ramo Material em torno de 1041–1084 passa a profundidade. Clearance nas chamadas posteriores é de conectores.
- No checkout instalado posterior: buscar texto “Aplicar em”, propriedades de interface gap, funções que subtraem g de depth_mm, deslocam tampa pelo vetor inward ou movem somente a base.

A causa provável é offset axial isolado; sua implementação exata precisa ser lida na versão instalada. Não atribuir a erro confirmado de código não anexado.

## Testes de aceite para Gemini

1. Inserto retangular: g=0/0,15/0,30 mm; medir largura, altura, fundo e cada espaço lateral montado. Não usar vista explodida para medir folga.
2. Forma verde real: g=0 e 5 mm; verificar contorno externo, todas as reentrâncias e eventual colapso, com vértices/seções reais.
3. Forma em U e domínio com buraco suportado: contornos internos/exteriores seguem a semântica da erosão/dilatação; nenhuma área branca vira material extraído.
4. Corpo/receptor e peça extraída: medir efeito só no alvo escolhido; g final por lado corresponde à UI.
5. Escala não uniforme, rotação e scale_length 1/0,001: g é distância física em mm, nunca porcentagem do tamanho.
6. Folga excessiva: diagnóstico claro antes de publicar geometria degenerada; preservar original e prévia anterior.
7. Atualizar g e regenerar: assinatura invalida prévia antiga; métricas finais e exportação refletem o mesh novo.
8. Exportar/reimportar e seccionar no fatiador: mesma folga e contorno; materiais externos preservados.

Não corrigir usando scale global, deslocamento radial de vértices pelo centro, somente diminuição da profundidade ou eliminação arbitrária de triângulos.

Status: capturas e análise estática; testes Blender NÃO EXECUTADOS. Os ZIPs disponíveis são 0.8.5/0.8.6; o código mais recente exibido nas imagens não foi anexado.
