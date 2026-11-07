# Validação do Splitter 0.8.24 — 2026-10-24

234 testes em 25 suítes passaram, sem testes ignorados na execução final. Blender 5.2.0 LTS, processos separados, factory-startup, autoexec desabilitado. A suíte nova tem 29 testes; foi repetida usando o código extraído do ZIP exato. A instalação final também foi carregada em um processo independente e testada.

## Cobertura

- Gato original: pata laranja (477 faces) e pata do corte manual anterior (490 faces inferidas da superfície original), duas peças manifold de um componente cada, faces de fechamento idênticas em A/B e volume conservado antes dos pinos. Hash da fonte inalterado.
- Modelos sintéticos: esfera, cilindro com anel intermediário, cubo com cortador cúbico e esférico; escalas não uniformes, reflexão, rotação, translação e unidades físicas diferentes.
- Recusas: seleção vazia/total/fora dos índices, regiões desconectadas, abertura na fonte, seleção obsoleta, modificadores ativos, escala nula, contorno maior que 128 vértices, seleção plana sem volume e faixa toroidal com fechamento incompatível. Nenhuma substitui uma prévia válida por um resultado falho.
- Fluxo: captura no modo de edição e atalho de material, painel com comandos completos, destaque do contato, pino central e manual, macho A/B, alteração de folga dos pinos, salvar/reabrir, confirmar/reverter, reabrir alvo oculto, contatos determinísticos e rejeição de contatos obsoletos.
- Sólido: prévia reconhece as superfícies novas que possuem uma contraparte física com normal oposta, em vez de oferecer qualquer superfície exterior. A escolha dos pinos permanece em uma área plana.
- Instalação: carregar a cópia do gato, regenerar, gerar pinos A e B, exportar duas partes STL, 3MF em milímetros e OBJ, confirmar/reverter e localizar/reparar manualmente uma aresta solta de um cortador. Bytes instalados conferidos contra o ZIP e o código-fonte.
- Regressões: plano completo e limitado, profundidade, materiais, molduras, folgas existentes, conectores manuais, estado da sessão, seleção, exportação, reversão e diagnósticos.

## Resultado por suíte

| Suíte | Testes | Resultado |
|---|---:|---|
| test_regressions | 55 | passou |
| test_solid_edit_tools | 16 | passou |
| test_cutter_problem_selection | 9 | passou |
| test_problem_selection | 5 | passou |
| test_frame_regions | 10 | passou |
| test_release_depth_region | 3 | passou |
| test_release_depth_guard | 4 | passou |
| test_plane_limited | 9 | passou |
| test_manual_connectors_workflow | 11 | passou |
| test_acceptance_0810_suite | 8 | passou |
| test_acceptance_089_suite | 10 | passou |
| test_release_geometry | 6 | passou |
| test_release_interface | 9 | passou |
| test_release_state | 10 | passou |
| test_release_workflows | 9 | passou |
| test_release_material_patch | 1 | passou |
| test_clearance_profiles | 6 | passou |
| test_release_connector_frames | 4 | passou |
| test_safe_mesh_repair | 7 | passou |
| test_material_region_connectivity | 2 | passou |
| test_region_release | 29 | passou |
| test_release_package | 2 | passou |
| test_material_manual_connectors_bugfix | 4 | passou |
| test_commit_selection_bugfix | 2 | passou |
| test_reedit_after_preview_bugfix | 3 | passou |

## Artefatos

- `Gato_pata_regiao_0.8.24.blend`: cópia pronta, sem pinos, contato 1 escolhido, diâmetro 8 mm/comprimento 12 mm configurados.
- `Gato_pata_pino_0.8.24.blend`: cópia com um pino central para comparação.
- `pata_sem_pino.png` e `pata_com_pino.png`: renderizações efetivas do resultado, inspecionadas visualmente.
- `COMO_TESTAR.md`: instruções e limites de uso.
- `instalada-anterior-0.8.23`: backup completo da instalação anterior.

ZIP SHA256: `f2efdc1b1801d061e94ce93de201d005324e3acbef573d1ba97543c7a180b37c`.
Fonte Teste Gato.blend SHA256: `4ccb9897e82d561057906736afc09ee5319b5287ee4f7e038bc84589297cfd4e`.

## Limites práticos

O novo fechamento e os pinos escolhidos na prévia do Sólido começam com folga entre peças = 0 mm. Folgas lateral/de fundo dos pinos são independentes e foram testadas. O fechamento segue contornos discretos e pode ter várias facetas. Não há promessa de alisamento automático, trajetória de montagem livre de colisões ou ajuste físico para qualquer impressora. Mapas UV e atributos de pintura por vértice não são transferidos neste modo; os materiais e a superfície exterior são preservados. Ensaios manuais e impressão de um encaixe continuam sendo a próxima etapa.

O teste antigo de QR apontava para a pasta anterior do Desktop; foi localizado no diretório movido e executado novamente. A execução final não teve skips.
