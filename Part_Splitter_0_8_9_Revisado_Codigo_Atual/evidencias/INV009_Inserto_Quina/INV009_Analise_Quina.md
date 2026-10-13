# INV-009 — seleção de Material envolvendo uma quina

12/10/2026. Complementa INV-001, INV-006 e INV-008. Trata de construção do volume interno e montagem; não comprova uma falha topológica.

## Evidências e limites

Cube.002, material Erro, Área 1 com 3 faces; a outra região tem 92 faces. Extração com Profundidade 20 mm, Manter Origem, folga 5 mm aplicada à peça extraída. As primeiras vistas mostram peça e receptor com terminações triangulares/abas em cunha. Na quarta vista explosão=0; painel mostra A com 25.177,4 mm³, dimensões 39,8³ mm e uma ilha, mas há outras peças/sessões visíveis. Identificar exatamente A/B da operação atual antes de medir; não tratar cada objeto visível como fragmento desse corte.

A quinta captura mostra três faces ortogonais pintadas ao redor de uma quina, tentativa de Destacar pela Base e aviso de desvio 8,99 mm > 0,15 mm. O painel informa que a prévia visível é a anterior válida: ela NÃO demonstra resultado do destaque recusado.

O bloqueio é coerente com a capacidade declarada de base estritamente planar. Um contorno não planar não é universalmente impossível de fechar: esse método é que não o suporta; não ampliar tolerância para forçar o caso.

Não há .blend original nem código da versão instalada posterior aos anexos 0.8.5/0.8.6. Não houve reprodução Blender.

## Por que profundidade não resolve sozinha

Na 0.8.6, create_material_patch_prism_cutter duplica as faces e translada seus vértices por um único inward_dir, calculado em analyze_material_structure a partir de normais médias.

Uma região planar tem direção de extrusão intuitiva. Três faces da quina têm normais diferentes; a direção média é aproximadamente diagonal se áreas forem iguais. A cópia diagonal da superfície e seu fechamento podem produzir cunhas nas extremidades. Esta é hipótese consistente com o método e as imagens; confirmar no cortador/resultado atuais.

Mesmo um resultado manifold pode ter espessura que afina até a ponta. Corrigir incidência ou folga não garante geometria fácil de imprimir ou encaixar. Porém, não declarar peça fisicamente impossível de montar apenas pela forma pontuda: verificar seu caminho.

## Decisão recomendada

Preservar extração atual para casos validados. Para quinas, oferecer outra construção explícita do inserto, em vez de engrossar automaticamente a mesma superfície.

| Abordagem | Uso | Limitação |
|---|---|---|
| Extração por vetor único | Patch simples ou caso já validado | Pode formar cunhas em patches dobrados. |
| Inserto em bloco por cortador sólido | Quina retangular simples como a seleção das imagens | Precisa validar o domínio externo escolhido e o volume adicional retirado. |
| Inserto como capa de espessura local | Usuário quer manter apenas uma casca na quina | Exige offset robusto e união/tratamento dos cantos; pode ser peça fina. |
| Dividir em insertos por face | Alternativa simples para superfícies diferentes | Mais peças, linhas de divisão e montagem diferente. |

Para primeira versão comercial, priorizar cortador sólido editável e diagnóstico da extração. Não criar agora um algoritmo geral de offset 3D para toda região curva.

## Como conceber o bloco de quina

A pintura define superfície externa desejada, mas não determina um volume interno único. Mostrar cortador/planos internos antes da geração.

1. Detectar caso simples: faces em poucos planos, aproximadamente ortogonais, domínio exterior regular e contorno coerente.
2. Propor um bloco/cortador alinhado aos planos da quina. O sólido extraído é A=S∩C, receptor B=S\C, antes da folga.
3. Validar que a interseção do cortador com a superfície externa respeita a seleção. Se invade faces não selecionadas ou omite parte do patch, ajustar proposta ou pedir delimitação; não repintar como correção.
4. Se o bloco mantém toda a área pintada, suas dimensões internas podem ser determinadas pela extensão da região e não pelo único valor “20 mm”. Não fingir que profundidade, espessura de capa e tamanho do bloco são a mesma coisa.
5. Permitir editar planos internos/dimensões e mostrar o volume retirado. Um bloco retira mais núcleo do que uma capa em certas geometrias; isso deve ser escolha consciente.
6. Gerar superfícies internas simples e suficientemente espessas. Não substituir pelo bounding box indiscriminado de uma região côncava.
7. Aplicar folga por lado apenas às interfaces de montagem, mantendo superfícies externas livres conforme requisito do INV-008.

Para uma quina regular com três patches quadrados compatíveis, um pequeno bloco pode ser uma boa proposta. Para quinas irregulares, o comportamento correto é diagnóstico e controle geométrico explícito, não promessa de solução automática.

## Cantos e pontas

Não usar chanfro/arredondamento global como remendo. Um chanfro nas superfícies internas, com raio/limite escolhido, pode melhorar robustez e entrada; precisa recalcular receptor e folga. Chanfrar só o inserto pode deixar espaço intencional e áreas sem apoio; mostrar isso.

Não mover vértices externos pintados para eliminar pontas sem autorização: altera aparência. Se a ponta é interna e faz parte da interface construída, uma proposta alternativa de interface pode eliminá-la mantendo a superfície externa. Validar a correspondência A/B e o volume perdido/adicionado.

Deslocar cada vértice pela normal média de seus vizinhos também não é solução geral: pode produzir colisões e auto-interseções. Offsets por face em cantos exigem interseção/união robusta e tratamento de singularidades.

## Verificação de montagem

Encaixar na posição final não comprova que a peça consegue chegar até ela. Definir direção de inserção/retirada e testar movimento.

- Na quina simples, a diagonal para fora é uma candidata, não garantia universal.
- Verificar colisão entre inserto e receptor ao longo do trajeto, com folga e posição montada reais.
- Se teste amostrado, informar passo/resolução e não chamá-lo prova contínua.
- Identificar undercuts/travas ou necessidade de rotação. Não confundir explosão visual com simulação de montagem.
- Se não há trajeto suportado, orientar direção diferente, corte alternativo ou divisão da peça.

## Plano Gemini / aceites

1. Reproduzir a seleção de três faces sem folga; depois 0,15/0,30 e 5 mm quando viável. Separar cunhas nominais de efeitos da folga.
2. Inspecionar cortador diagonal, A/B e seções. Medir extensão das zonas finas, não apenas volume e bounding box.
3. Preservar o bloqueio de destaque planar; melhorar texto: “A região envolve uma quina e não possui uma base planar suportada por este modo. Use um cortador sólido para definir o volume interno.”
4. Introduzir proposta de bloco somente para domínios simples validados, ou utilizar o modo Sólido existente com orientação e instruções melhores.
5. Comparar extrusão/capa/bloco: mesma superfície externa quando possível; mostrar diferenças internas e qualquer alteração na seleção.
6. Verificar sólidos, materiais, folga por lado, espessura estimada, caminho de montagem e exportação. Slicer/ensaio físico completam validação, não foram feitos aqui.
7. Testar quina ortogonal, quina oblíqua, patch irregular e faixa estreita. Recusar suporte automático em casos ambíguos.
8. Preservar a região verde planar e o caso positivo de 10 mm; não limitar todos os patches com relevo indiscriminadamente.

O INV-009 é estudo de melhoria do método e diagnóstico de fabricação/montagem. Não remover automaticamente o método atual nem declarar defeito de malha sem inspecioná-la.
