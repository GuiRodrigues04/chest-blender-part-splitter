# Resultados da validação 0.9.11

## Suítes Blender

- Blender 5.2.0 LTS; fonte testada após congelamento da geometria; um processo Blender simultâneo.
- 16/16 suítes aprovadas, 122 verificações, 0 falhas, 0 erros e 1 skip por referência privada das patas do gato indisponível.
- Fluxo de release: 11/11; UV/material: 5/5; faixa de contato: 5/5; profundidade e região: 3/3; interface: aviso visível recolhido, métricas escondidas e ordem expandida aprovados.
- Relatório agregado: `current.json`. Logs individuais: `current_logs/`.

## Caso Spot reconstruído

Os parâmetros da operação original não estavam disponíveis. O caso medido foi reconstruído da malha de origem e das faces sem marcação do resultado salvo, com uma região de 10 faces e base de 5 mm inferidas; folga PART solicitada de 0,1 mm.

- 164 triângulos de parede por direção; distâncias de parede marcadas entre 0,0999968 e 0,101373 mm.
- Nenhum triângulo de contato zero sustentado nas paredes medidas.
- Pino manual CYLINDER 2 × 2 mm, chanfro 0,2 mm, folgas radial/fundo 0,1 mm: cavidade com 64 triângulos/256 amostras, intervalo 0,099514–0,099521 mm e mediana 0,099518 mm; verificação separada da parede externa com mediana 0,1 mm e zero contatos zero. O dimensionador automático recusou sugerir as dimensões mínimas de 1 × 2 mm para esse contorno.
- A medição usa pontos internos das faces de contato marcadas. Não demonstra folga em faces sem marcação nem garante montagem física.
- Evidência completa: `spot_contact_audit/reconstructed_5mm_gap_0.1.json` e `spot_contact_audit/README.md`.

## Pacote instalado

- ZIP `dist/chest_part_splitter-0.9.11.zip`, SHA-256 `D1772BFB8A1311B6B217AF111973BA19F114680D46EDC93F330035684CD3B858`; pacote 2/2 aprovado. ZIP comparado byte a byte com a instalação real em `user_default/chest_part_splitter`; versão instalada `(0, 9, 11)`.
- Namespace instalado: cinco rotas de corte; sizing 14/14; UV/material 5/5; faixa de contato 5/5; aviso recolhido e ordem expandida da UI aprovados. Logs em `package_tests.log` e `verify_installed.log`.

## Uso após atualização

Pré-visualizações e peças já confirmadas permanecem como salvas. Reabra o Blender, gere uma prévia nova e revise o resultado antes de confirmar novas peças. A validação não inclui impressão física.
