# Regiões curvas do Teste Gato — pendências verificadas

Investigação em 22/10/2026, fonte SHA-256 `25c3663e90f522fdfaf9e6695889c37909c613499163424d193ab8ff0d586330`.

A correção 0.8.21 resolve a profundidade ignorada do nariz. Os casos abaixo não estão resolvidos automaticamente.

## Bigode

Material.002, região 3, 239 faces: a face cinza 646 no interior da região branca gera um contorno com grau quatro no vértice 1191. A fonte é manifold; não se trata de um buraco topológico.

Em cópia, atribuir a face 646 ao material branco produz uma região de 240 faces, com um contorno de 16 vértices. Loop/Pela Base sem base adicional gera dois sólidos fechados e conserva o volume. Extrusão de 0,2, 1, 5 e 20 mm encontra interseções do fechamento com o corpo. O fallback por projeção também rejeita a saliência que excede a projeção. Não remover esses bloqueios.

Melhoria futura: localizar bifurcações de fronteiras de materiais, distinguindo-as de defeitos manifold. Sugerir faces de material discrepante com prévia e reversão, preservando a escolha explícita de cor do usuário.

## Pata laranja

Material.005, região 0, 477 faces: dois contornos, com 35 e 10 vértices. O motor de molduras requer apoio planar e não representa essas duas interfaces com orientações diferentes. Ignorar a tolerância de planicidade continua produzindo interseções na projeção.

Melhoria futura: modelar interfaces separadas para contornos que fecham volumes distintos, sem interpretá-los automaticamente como um anel planar. Definir claramente o significado de profundidade em uma região que envolve uma superfície curva. Exigir preservação das faces selecionadas, ausência de cruzamentos, dois sólidos válidos, conservação volumétrica sem folga e proteção de outras cores. Manter os testes de molduras planas e seus furos.

Até implementar e validar esse método, a extração exata da pata por cor permanece indisponível neste arquivo. Nenhum reparo destrutivo foi aplicado ao original.
