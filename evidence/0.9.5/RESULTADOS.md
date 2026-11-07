# Splitter 0.9.5 — 7 de novembro de 2026

## Resultado e escopo

Instalada no Blender 5.2 após comparação com a instalação 0.9.4. O fechamento direto por loop tenta uma grade com borda fixa e interior interpolado; a alternativa anterior continua disponível quando a grade não é segura. O aviso da triangulação usa mensagem de sucesso informativa, sem alerta vermelho, em português e inglês. Outros métodos mantêm seus algoritmos de fechamento.

Foi corrigido o exemplo central da Spot com 0,1 mm: 16 quads em cada tampa, duas malhas fechadas. As distâncias medidas nos centros dos triângulos de cópias das superfícies de contato ficaram entre 0,099755 e 0,100495 mm no destino Peça; Cavidade e Ambos também passaram. A validação de grades usa quatro amostras interiores por triângulo nos dois sentidos e tolerância de 0,003 mm. É uma amostragem, não uma prova matemática em todos os pontos da superfície.

Contornos curvos que não admitem uma solução uniforme continuam sendo recusados. A mensagem agora distingue a incompatibilidade de construção da hipótese de uma folga fisicamente grande demais. Pinos no contorno curvo da Spot com folga de 0,1 mm continuam sem contato adequado no teste efetuado e são recusados com segurança; a prévia anterior é mantida. Não foi validada impressão física.

## Comparação de nove cenários reais

O Luna, em esforço baixo conforme solicitado, auxiliou no inventário e numa bateria de sete cenários. A bateria final reproduzível `tests/manual_real_models_095.py` foi verificada pelo agente principal com nove cenários. Usa `geometry_region.slice_region` para Região inteira, preserva os arquivos originais e verifica a assinatura da malha de entrada após cada operação bem-sucedida.

| Cenário | 0.9.4 | 0.9.5 |
|---|---|---|
| Placa simples — Região inteira verde | Fechado; 2 contatos | Mesmo resultado e volumes |
| Placa simples — Região inteira azul | Fechado; 1 contato | Mesmo resultado e volumes |
| Placa simples — plano | Fechado | Mesmo resultado e volumes |
| Placa simples — material com profundidade | Fechado | Mesmo resultado e volumes |
| Placa simples — material pela base | Recusa: desvio de 1,60 mm | Mesma recusa; limitação anterior |
| Gato — material, slot 2, profundidade 5 mm | Fechado | Mesmo resultado e volumes |
| Gato — plano | Fechado | Mesmo resultado e volumes |
| Spot — loop sem folga | Fechado; tampa triangulada | Fechado; 16 quads por tampa |
| Spot — loop com 0,1 mm | Recusa da folga | Fechado; 16 quads por tampa |

Todos os resultados aceitos têm zero arestas não manifold. Não foi detectada regressão nesses cenários. Os JSON `verified_baseline.json` e `verified_current.json` registram parâmetros, volumes, número de faces e erros. Resultados esperados de recusa não são contabilizados como cortes aprovados.

## Verificações automatizadas pertinentes

48 métodos de teste passaram, sem falhas, nas suítes:

- `test_loop_quad_caps.py`: 4, incluindo conservação de volume/fonte, grade, recusa de folga coincidente e alternativa para borda ímpar.
- `test_inv_005_loop.py`: 5, fechamento, concavidade e entrada aberta.
- `test_clearance_uniformity.py`: 4 métodos, incluindo destinos da folga, folga de fundo independente, corte passante, plano e sólido.
- `test_manual_connectors_workflow.py`: 11, edição manual e prévias com encaixes.
- `test_interface_history.py`: 13, marcas de interfaces e cortes anteriores.
- `test_region_multicontact_091.py`: 9, região inteira, folga e múltiplos contatos.
- `test_release_package.py`: 2, pacote exato, idiomas, exportação, confirmação e reversão.

Também foram verificados o idioma real PT/EN, o aviso informativo da alternativa triangulada nos dois idiomas e o build/validação oficial de extensões do Blender. A instalação foi conferida byte a byte com o ZIP e carregada pelo namespace real `bl_ext.user_default.chest_part_splitter`; o corte da Spot com 0,1 mm foi executado novamente nessa instalação.

## Instalação

Pacote: `dist/chest_part_splitter-0.9.5.zip`.

SHA-256: `9f83ccbeca899f0f6a922316c24c654ba9450c372644108822c14cf8906cafc8`.

A instalação 0.9.4 foi copiada integralmente para `evidence/0.9.5/installed_before_0.9.4` antes da atualização. O backup local não é versionado. Nenhum arquivo de modelo original foi sobrescrito. Uma instância gráfica já aberta do Blender precisa ser reiniciada para carregar os módulos atualizados.
