# Auditoria do Splitter — 21/10/2026

Versão candidata: 0.8.18. Ambiente testado: Blender 5.2.0 LTS, Windows. Trabalho dividido entre três agentes Luna/medium e o agente principal. Os testes usaram processos isolados e cópias em memória. Os nove BLENDs, nove GLBs e `Padrão Testes.blend` originais não foram salvos; a comparação SHA-256 confirmou os 19 arquivos intactos.

## Cobertura e evidências

| Bateria | Cobertura | Resultado |
|---|---|---|
| Plano e sólido | 6 configurações × 19 arquivos | 114/114 passaram |
| Repetição final de pinos | Perfil FDM nos mesmos 19 arquivos após a correção dos conectores | 19/19 passaram, originais intactos |
| Material/Loop nos BLENDs | 9 arquivos, regiões significativas, profundidade 2 mm, folgas 0 e 0,1 mm, Base e conectores | Resultados completos por arquivo; rejeições e limitações discriminadas abaixo |
| Material/Loop nos GLBs | 46 tentativas na varredura, mais repetição direcionada Chest | 21 prévias válidas na varredura; Chest adicional: 3/3 configurações passaram na geometria e no fluxo completo |
| Cubos verdes | 46 verificações iniciais e 83 complementares, incluindo inventário e rejeições deliberadas | 43 + 11 verificações aprovadas; 3 + 72 rejeições esperadas; não equivalem a 129 cortes aprovados |
| Regressões | 22 suítes selecionadas e repetições direcionadas | 22/22 iniciais; 7/7 suítes afetadas após os ajustes; pacote exato e nova regressão de pinos 2/2 |

Plano/sólido cobrem corte central X sem folga, corte Z com folga e pinos, corte X com folga, plano diagonal sem folga e cortador sólido lateral com folga zero/0,1 mm. As prévias passaram por confirmação e reversão. Verificações incluem fechamento, volume positivo, materiais válidos, conservação de volume quando aplicável e preservação da origem. A folga planar foi medida geometricamente, tolerância de 0,002 mm.

As varreduras não testam toda posição de corte possível. Uma prévia válida numa região não significa que todas as regiões/espessuras da mesma placa sejam suportadas.

| Placa | Plano e sólido, BLEND e GLB | Material/Loop nas regiões testadas |
|---|---|---|
| Arco | Aprovados | Moldura principal com FDM/pinos aprovada; outra região Base tem defeito aberto |
| Cavalete | Aprovados | Detalhe com FDM/pinos aprovado; extração rasa do corpo tem limitações |
| Chest | Aprovados | Principais regiões a 2 mm aprovadas após correções; fluxo FDM/pinos aprovado no BLEND |
| Mesa | Aprovados | Detalhe com FDM/pinos aprovado; corpo tem espessura indeterminada no caminho tentado |
| Número | Aprovados | Material uniforme inteiro: não existe uma cor separável nestes arquivos |
| Osso | Aprovados | Moldura principal com FDM/pinos aprovada; outra região requer Base |
| Osso V2 | Aprovados | Região principal com FDM/pinos aprovada |
| QR Inclinada | Aprovados após reparo | Folga zero aprovada; 0,1 mm pode colapsar microaberturas |
| QR Inclinada V2 | Aprovados | Material uniforme inteiro: não existe uma cor separável nestes arquivos |

As referências a pinos nesta tabela usam os workers BLEND; os workers GLB de Material/Loop verificam importação, reparo e corte sem conectores. Ambos os formatos têm a bateria planar com pinos.

## Folgas e cubos

O material verde real é `Funciona`. Foram identificadas dez ilhas verdes no cubo principal e quatro no segundo cubo oculto, além de objetos de resultados anteriores. As regiões verdes com saliências que ultrapassam a projeção do contorno foram preservadas por extração Base; profundidades incompatíveis continuaram bloqueadas.

- Folga entre peças: 0,10 mm em 62 amostras de contorno, nos destinos peça/cavidade/ambos.
- Fundo personalizado: 0,20 mm medido.
- Pino nominal de 3 mm: folga radial medida de 0,149736 mm por lado, em 32 direções; fundo de 0,200003 mm.
- A pequena diferença radial decorre da aproximação poligonal do cilindro. Pino e furo continuam coerentes com os valores configurados.

## Importação GLB

Os nove GLBs importaram com bordas separadas. A opção `merge_vertices=True` do importador não fechou completamente nenhum deles. O reparo seguro da extensão fechou os nove, preservando dimensões e volume, antes dos cortes. Isso é uma etapa necessária nestes arquivos, não uma aprovação da malha bruta.

Número e QR Inclinada V2 têm um único material uniforme também nos BLENDs correspondentes. Não existe uma segunda cor armazenada para extrair nessas versões; selecionar o material inteiro é corretamente recusado. Seus cortes planares e por sólido passaram.

## Correções encontradas nesta auditoria

1. Captura antiga de Loop contaminava o modo Material. A captura agora só participa no modo Loop.
2. Cálculo de volume em precisão simples recusava saneamento válido após triangulação. O volume de referência agora usa soma em precisão dupla, com a mesma tolerância anterior.
3. Cortes planares podiam deixar microarestas ou triângulos colineares na interface. As saídas passam pelo saneamento validado antes das métricas.
4. O solver Exact podia retornar vazio em cortadores sólidos válidos na Chest. A operação tenta Manifold em candidatos isolados e aceita apenas resultados validados.
5. Extração por material tinha prismas numericamente degenerados e saídas vazias que não acionavam a tentativa alternativa. Prismas recebem saneamento e saídas vazias acionam a recuperação validada existente. Chest a 2 mm passou com folgas zero e 0,1 mm nos dois materiais principais, tanto no BLEND quanto no GLB reparado.
6. Saídas vazias do Loop agora acionam a tentativa Manifold existente. Chest passou com profundidade de 2 mm, perfil FDM e pinos automáticos, incluindo prévia, confirmação e reversão.
7. Encaixes Exact podiam gerar cinco faces degeneradas na Chest com folga FDM. As duas saídas são avaliadas e validadas em candidatos; quando Exact falha, Manifold reavalia as mesmas entradas. Duas execuções isoladas aprovaram a regressão, sem mudar dimensões nem folgas.

## Limitações para conferir manualmente

- QR Inclinada: reparada, profundidade de 0,1 mm e folga zero produz dois sólidos. Folga de 0,1 mm pode cruzar microaberturas reais da região; a operação deve continuar recusada, sem reduzir silenciosamente a folga.
- Arco: a região principal tem testes Material/Loop com FDM e pinos aprovados. Outra região, material 1/região 0, tem somente cerca de 1 mm de espessura e recusa profundidade de 2 mm. A tentativa Base dessa região revelou separadamente um defeito válido ainda não corrigido: aresta com quatro faces. Alternativas booleanas produziram fechamento, mas não foi comprovada a preservação completa das superfícies/materiais. A operação continua bloqueada; não foi introduzida uma correção arriscada.
- Cavalete e Mesa: extrair o material do corpo inteiro como região rasa gerou contornos abertos/espessura indeterminada em algumas configurações. As regiões de detalhe aprovadas e os cortes planares não cobrem esses casos. São limitações ainda abertas, não testes aprovados.
- Osso: uma região não admite a extração por profundidade tentada; Base funciona. Moldura principal e cortes de divisão passaram nas configurações registradas.
- Chest: falhas direcionadas de Loop e de conectores com folga foram corrigidas e retestadas após a varredura; usar `Placa_Chest_Inteira_retry.json`, `connector_solver_probe.json` e regressões finais, e não os erros anteriores dos JSON de baseline.

Não considero esta bateria uma garantia de prontidão comercial para qualquer malha. Ela fornece uma base reproduzível para os testes manuais de placas/cubos; personagens, superfícies curvas e outras estruturas continuam fora da cobertura atual.

## Arquivos para revisão

Na entrega, `Cenas/Plano e sólido` contém 19 cópias com prévias planares e pinos; `Cenas/Cubos verdes` contém seis cenários; as outras pastas contêm prévias aprovadas de Material/Loop. São cópias para inspeção e não substituem os modelos originais.

Abrir uma cópia, conferir o alvo e os valores salvos, observar as duas peças isoladamente e confirmar/reverter o corte. Para uma comparação limpa, reiniciar o Blender após instalar a nova versão. As dimensões ideais para uma impressora específica ainda precisam de calibração física.

Dados técnicos: `commercial_planar_solid_20261021/final`, `commercial_plates_blend_20261021/isolated`, `commercial_plates_glb_20261021`, `commercial_cube_20261021` e `commercial_20261021/regressions`. Baselines anteriores e tentativas rejeitadas foram preservados para comparação; contagens de repetição não devem ser somadas como casos inéditos.
