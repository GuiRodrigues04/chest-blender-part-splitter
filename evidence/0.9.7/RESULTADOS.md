# Splitter 0.9.7 — verificação

## Resultado funcional

- O loop salvo do pé da Spot fecha naturalmente, sem o degrau central automático. Tenta quads; no pé enviado, conserva a triangulação segura quando a grade não passa nas verificações.
- Nove cortes diretos: zero; 0,1 / 0,2 / 0,5 / 1 mm na peça; 0,1 / 1 mm na cavidade e em ambos. Todos geraram duas malhas fechadas, com superfícies locais compatíveis para encaixes.
- Dezesseis prévias com pino cilíndrico central de 2 × 2 mm: macho A/B, folgas 0 / 0,1 / 0,2 / 1 mm na peça e 0,1 / 1 mm na cavidade/ambos. Todas válidas, sem arestas não manifold e com volume positivo.
- Três prévias adicionais com pino de 6 × 8 mm: 0,1 mm com macho A/B e 1 mm com macho A. Todas válidas (`operator_foot_pins6mm_final_results.json`).
- O exterior foi amostrado nos 5.856 triângulos visíveis da origem, longe da interface, nos nove cortes diretos. Desvio máximo: 0,00014356 mm; percentil 95: 0,00006664 mm. Usa a tesselação visível do Blender tanto na origem quanto no resultado, evitando comparar diagonais alternativas de quads não planos.
- O arquivo original manteve SHA-256 `579981c6eec27d03504273c3f3b5c22ba7ed492295a67490f91fbb79e95e403a`.

## Folga e limites

Na Spot, pedido de 0,1 mm na peça: distância normal amostrada de aproximadamente
0,099965–0,100015 mm e distância mínima entre superfícies no interior comum de
0,098477–0,103632 mm. A faixa completa, incluindo bordas além do contato,
é maior. A prévia informa ambas as faixas. Isso não garante espessura uniforme
em cada ponto de uma borda curva nem valida a montagem física da impressão.

O solver novo da lâmina aceita tolerância max(0,005 mm, 5% da folga) no contato
comum. O solver convexo existente mantém sua validação por planos; distâncias
em quinas não são equivalentes às distâncias normais de uma lâmina suave.
Folgas lateral/fundo independentes, furos e bases adicionais mantêm seus
tratamentos anteriores. Grades que alterariam a superfície são recusadas.

## Regressão comparativa

| Execução | Suítes aprovadas | Métodos declarados | Pulados | Erros de subtest |
| --- | --- | --- | --- | --- |
| Baseline 0.9.6 congelada | 25 / 26 | 172 | 6 | 23 |
| Final 0.9.7 | 26 / 27 | 175 | 6 | 23 |

Os mesmos 23 erros estão em `test_release_workflows.py` nas duas versões:
extração com profundidade/automática em regiões privadas com folga de 0,15 mm
e um caso de encaixe manual. Não foram corrigidos nesta versão nem contados
como aprovação. As regressões intermediárias em degraus e cantos foram
corrigidas, e `test_release_geometry.py` passou na repetição final.

Os seis testes opcionais foram inicialmente pulados por caminhos antigos de
fixtures. O complemento `regression_fixtures.json` registra a repetição com os
arquivos reais movidos, sem substituir a comparação principal.

- Material regional no gato: 5 métodos aprovados em cada versão, sem skips.
- Regiões: 28 métodos aprovados em cada versão, com um skip porque a cena
  carregada não contém os objetos de referência de patas esperados.
- Contornos da Placa Chest: o mesmo erro e 24 falhas de subtest nas duas
  versões. As 24 asserções esperam o literal `GRID_4`, enquanto a mensagem
  localizada informa que a grade de quatro pinos exige 8,2 mm e o contato
  tem 6 mm: o layout é recusado corretamente. O caso de três pinos também
  encontra um `NoneType`. Esses resultados não são tratados como aprovação.
- QR: a fixture V2 disponível contém grupos `[982]`, enquanto o teste
  privado espera `[443, 2, 4]`. A mesma incompatibilidade aparece nas duas
  versões. O runner usa uma cópia temporária para apontar à fixture V2;
  não altera a malha nem as expectativas do teste original.

A repetição independente em modelos reais aprovou nove cenários: regiões
verde/azul da plaquinha, plano na plaquinha, extração por material com
profundidade e pela base, material/plano no gato, e loop na Spot com zero e
0,1 mm. A extração não plana pela base da plaquinha, recusada na 0.9.6,
agora fecha pelo caminho natural. Resultados em `real_final097.json` e
driver `manual_real_models_097.py`.

Relatórios principais: `regression_baseline.json`, `regression_final.json`,
`foot_results_final.json`, `foot_results_exterior_final.json` e
`operator_foot_connector_sweep_final_results.json`. Os testes portáveis incluem
os cinco modos com zero/0,1 mm, alternativa de contorno ímpar, furos, quads,
folgas nos três destinos, limpeza de temporários e preservação da origem.

## Pacote e instalação

Pacote validado pelo Blender: `dist/chest_part_splitter-0.9.7.zip`.
SHA-256: `9511bc9018902cad808d891410c3175d4a92d1694e1fca4bc9e2580688d87b6f`.
`test_release_package.py`: dois testes aprovados, incluindo importação pelo
namespace de extensão, comparação exata de bytes, exportação e reversão.

Instalação substituída no Blender 5.2 após backup local da 0.9.6.
`verify_installed.py` verificou bytes idênticos ao ZIP, versão real 0.9.7,
cinco modos de prévia e seis cortes reais do pé com folgas e encaixes
(`installed_foot_results.json`). Não alterou as preferências salvas nem o
arquivo original. Uma sessão do Blender que já estava aberta precisa ser
reiniciada para carregar o código novo.
