# Splitter 0.9.11 — notas de versão

## Folga de contato em extrações com profundidade

A faixa de folga agora acompanha todo o contato capturado. O corte não é mais truncado pelo plano de apoio; as bordas da ferramenta avançam além das faces retidas para evitar uma faixa coplanar.

Uma reconstrução do caso Spot usou uma seleção de 10 faces e profundidade de 5 mm inferidas da proveniência da malha, com folga PART solicitada de 0,1 mm. Nas paredes de contato marcadas, as medidas bidirecionais ficaram entre 0,0999968 e 0,101373 mm, sem triângulos com contato zero sustentado. Os parâmetros originais da operação não estavam disponíveis; o resultado descreve essa reconstrução, não uma reprodução exata da cena salva nem faces sem marcação.

Na mesma reconstrução, um pino cilíndrico com dimensões explícitas de 2 × 2 mm, chanfro de 0,2 mm e folgas radial/fundo de 0,1 mm mediu 0,099514–0,099521 mm no perfil da cavidade (mediana 0,099518 mm); a verificação separada da parede externa mediu mediana 0,1 mm e zero contatos zero. O dimensionador automático recusou sugerir um pino mínimo de 1 × 2 mm nesse contorno. Portanto, esse caso confirma somente a geometria manual testada, não uma sugestão automática nem a recuperação de parâmetros históricos.

## Avisos e diagnósticos

Na comparação dos 584 pontos da faixa antiga com ambas as peças reconstruídas após adicionar o pino, 572 ficaram a até 0,005 mm da folga nominal de 0,1 mm. Nas transições e cantos restantes, a menor distância ao olho foi de 0,0387 mm; portanto não se afirma uniformidade de 0,1 mm em todos os pontos. O teste não substitui uma impressão física.

Com a diferença de volume em 0,5% ou mais, o painel mantém um aviso visível mesmo quando os dados detalhados estão recolhidos. **Mostrar dados** expande volumes, dimensões, estatísticas da malha e o balanço completo.

## Validação

Blender 5.2.0 LTS: 16 suítes aprovadas, 122 verificações contabilizadas e uma verificação ignorada porque os objetos de referência privados não estavam disponíveis. A bateria inclui cobertura de folga, profundidade, UV/material, interface, geometria e fluxo de release. O relatório completo está em `current.json` e os logs em `current_logs/`.

Após instalar, reinicie o Blender e gere novas prévias. Peças confirmadas em arquivos existentes não são reescritas automaticamente. As reconstruções medidas não substituem a conferência da cena do usuário nem testes de impressão física.
