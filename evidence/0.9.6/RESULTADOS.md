# Splitter 0.9.6 — tentativa de grade em todos os cortes

Data: 7 de novembro de 2026. Blender 5.2.0. Instalação anterior: 0.9.5.

## Alteração

As prévias de Loop, Plano, Região inteira, Sólido e Material agora compartilham uma tentativa de reorganizar as superfícies de corte depois da folga e antes dos encaixes. Superfícies planas com contorno compatível recebem quads; a organização conserva a borda, os materiais e os atributos inteiros das faces, inclusive as identidades dos contatos. Patches curvos já quadriculados pelo loop são preservados. A alternativa triangulada continua disponível, com aviso informativo sem vermelho.

A tentativa usa uma cópia privada e verifica fechamento, volume e coincidência da superfície tessellada por amostragem nos dois sentidos, com tolerância de 0,0001 mm. Uma melhoria de topologia recusada não substitui o corte válido anterior. Não preenche furos nem une regiões de materiais ou marcas diferentes para forçar uma grade. Contornos ímpares, muito densos ou com grade inadequada podem continuar triangulados.

Plano e Sólido identificam as novas superfícies pela comparação com o modelo fonte, mesmo quando o alvo contém marcas de cortes anteriores; não confundem uma interface antiga com o corte atual. Um teste específico exercita esse caso.

## Folga padrão sem encaixes

Confirmados em uma cena nova: folga entre peças de 0,1 mm, encaixes desligados e folga de fundo separada desligada. Não houve alteração desses padrões.

Os cinco métodos foram executados pelo operador real de prévia, com folga zero e com 0,1 mm, usando a mesma peça cilíndrica de 16 lados para comparação. Foram medidos cinco pontos da interface por lançamento de raios na geometria final. Todas as peças aceitas ficaram fechadas e o original permaneceu intacto.

| Método | Folga pedida | Medida mínima | Medida máxima | Tampas em quads |
|---|---:|---:|---:|---|
| Loop | 0,1 mm | 0,0999989 mm | 0,1000008 mm | 16 em cada lado |
| Plano | 0,1 mm | 0,0999989 mm | 0,1000017 mm | 16 em cada lado |
| Região inteira | 0,1 mm | 0,0999989 mm | 0,0999998 mm | 16 em cada lado |
| Sólido | 0,1 mm | 0,0999989 mm | 0,1000008 mm | Um lado triangulado, outro com 16 quads |
| Material | 0,1 mm | 0,0999980 mm | 0,1000008 mm | 16 em cada lado |

Com folga zero, o maior resíduo medido foi de aproximadamente 0,000002 mm. O corte sólido com folga criou segmentos muito pequenos no contorno do Boolean: a tentativa de grade não foi adequada em um dos lados e a triangulação preservou a folga. Isso é alternativa válida, não promessa de quads em qualquer geometria. Os dados completos estão em `measurements.json`.

Também foram exercitados contornos ímpares nos cinco métodos, todos com prévia válida e aviso da triangulação. As medições são de modelos computacionais e pontos amostrados; não constituem garantia de ajuste físico ou de distância uniforme em qualquer superfície curva.

## Furos no corte por plano

Um teste adicional revelou que o fechamento anterior podia criar discos sobrepostos em um tubo, fechando a abertura central apesar de ter arestas manifold. A correção triangula conjuntamente os contornos aninhados com restrições nas bordas e classifica o domínio por paridade. Ilhas separadas mantêm o preenchimento anterior. Foram verificados um tubo circular e uma moldura quadrada com subdivisões colineares, antes e depois da tentativa de grade: o raio no centro atravessa a abertura sem encontrar tampa.

## Modelos reais e regressão

`tests/manual_real_models_096.py` compara a versão instalada 0.9.5 com a nova finalização de topologia. Os JSON `real_baseline.json` e `real_current.json` registram os resultados.

- Placa multicontatos, Região inteira verde: resultado fechado preservado; alternativa triangulada.
- Placa multicontatos, Região inteira azul: resultado fechado; 112 novos quads no total, com algumas superfícies trianguladas.
- Placa por Plano: resultado fechado; 169 novos quads, com alternativa em outros patches.
- Placa por Material/Profundidade: resultado fechado preservado; alternativa triangulada.
- Placa por Material/Base: mesma recusa anterior por desvio de 1,60 mm; não é contada como corte aprovado.
- Gato por Material/Profundidade: resultado fechado; 40 novos quads no total.
- Gato por Plano: resultado fechado preservado; alternativa triangulada.
- Spot por Loop, zero e 0,1 mm: resultados fechados da 0.9.5 preservados, com 16 quads em cada tampa.

Não foi detectada regressão funcional nos nove cenários comparados. As mudanças de volume decorrentes da reorganização ficaram dentro da verificação numérica de superfície/volume; os detalhes estão nos JSON. Os arquivos de modelos originais não foram salvos nem sobrescritos.

Foram executados 52 métodos de teste com sucesso, nas suítes de todos os métodos (5), grade de loop (4), contornos do plano (8), plano limitado (9), encaixes manuais (11), uniformidade da folga (4), região multicontato (9) e pacote/exportação/confirmação/reversão (2). Três testes opcionais de contorno do plano foram ignorados porque o parâmetro de fixture específico não foi fornecido; não são incluídos nos 52 aprovados. As suítes existentes foram complementadas pelos novos cenários de quads, alternativa, folga e preservação dos furos.

## Instalação e limites

Pacote `dist/chest_part_splitter-0.9.6.zip`, validado pelo comando oficial de extensões do Blender. SHA-256: `0979317eedc00471e63a704ff0b2e0e254dadf4c2158a59f01c1641cc2677688`.

A instalação anterior foi preservada em `installed_before_0.9.5` (backup local ignorado pelo Git). A instalação nova foi comparada byte a byte com o ZIP, carregada pelo namespace real da extensão e exercitada novamente nos cinco métodos, com folga e alternativa. A fixture de smoke registra o mesmo módulo instalado diretamente entre os resets de preferências de fábrica, sem salvar preferências do usuário.

O tratamento geral de superfícies curvas mantém as limitações documentadas na 0.9.5. Não houve liberação de contornos que não permitem construir uma folga segura nem mudança nas medidas dos encaixes. Uma instância gráfica já aberta do Blender precisa ser reiniciada para carregar os novos módulos.
