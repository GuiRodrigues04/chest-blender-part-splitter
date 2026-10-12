# Mapa de código — base verificada 0.8.6

Linhas são da distribuição anexa; para checkout posterior buscar pelo nome da função. Fontes numeradas em referencias/codigo_086_numerado/. Originais permanecem intactos nos ZIPs.

| Arquivo | Função/classe | Linhas 0.8.6 |
|---|---|---|
| src/geometry_plane.py | cap_open_cut_boundaries | 46–101 |
| src/geometry_plane.py | evaluate_bmesh_metrics | 104–153 |
| src/geometry_plane.py | slice_mesh_by_plane | 214–307 |
| src/geometry_plane.py | compute_explosion_offsets | 310–324 |
| src/geometry_loop.py | LoopSliceResult | 21–28 |
| src/geometry_loop.py | slice_mesh_by_loop | 278–464 |
| src/geometry_loop.py | analyze_loop_region | 467–606 |
| src/geometry_loop.py | create_loop_prism_cutter | 609–659 |
| src/geometry_loop.py | slice_mesh_by_loop_extrude | 662–801 |
| src/geometry_material.py | analyze_material_structure | 108–232 |
| src/geometry_material.py | create_material_patch_prism_cutter | 235–303 |
| src/geometry_material.py | slice_mesh_by_material | 306–500 |
| src/geometry_contract.py | CutInterface | 15–45 |
| src/geometry_contract.py | build_cut_interface | 48–191 |
| src/operators.py | validate_printable_mesh | 153–185 |
| src/operators.py | compute_session_input_signature | 256–374 |
| src/operators.py | update_preview_positions | 511–552 |
| src/operators.py | CHEST_OT_splitter_generate_preview | 880–1349 |
| src/operators.py | CHEST_OT_splitter_commit_parts | 1439–1557 |
| src/operators.py | CHEST_OT_splitter_export_parts | 1853–2098 |

## Achados e confiança

| Caso | Verificado no código 0.8.6 | Ainda depende de reprodução |
|---|---|---|
| INV-001 | Cortador duplica patch por translação única; faces novas sem política explícita de materiais; interface Material marcada planar com contornos vazios. | Causa exata dos quadrados e da película; folga da versão instalada. |
| INV-002 | Destaque por base não existe nesse módulo Material. | Localizar código posterior, identificar duplicação/cobertura. |
| INV-003 | Método de prisma existe e pode produzir inserto. | Validade real da cena positiva, espessura e núcleo remanescente. |
| INV-004 | Sinal do helper contrário à convenção de A; preview usa normal atual sem invert_sides. | Resultado visual na cena real e versão instalada. |
| INV-005 | Fechamento coleta todas as bordas; A/B fechadas independentemente; AUTO por altura. | Quais são as 19 arestas inválidas. |
| INV-006 | Validação atual não mede espessura nem auto-interseções. | Película relatada versus cunha correta; imagem mostra prévia removida. |

## Compatibilidade entre versões

Mudança relevante de 0.8.5 para 0.8.6: geometry_material recebeu cortador preservando faces exatas do patch; geometry_plane e geometry_contract passaram a transportar loops; geometry_loop e operadores receberam alterações; gpu_drawing.py é novo. Não reaplicar uma correção antiga trocando o patch por um único n-gon ou hull. Diff integral em referencias/Diff_085_086.patch.

- src/__init__.py: alterado.
- src/constants.py: igual.
- src/diagnostic.py: igual.
- src/geometry_connectors.py: alterado.
- src/geometry_contract.py: alterado.
- src/geometry_loop.py: alterado.
- src/geometry_material.py: alterado.
- src/geometry_plane.py: alterado.
- src/geometry_solid.py: igual.
- src/gpu_drawing.py: novo.
- src/io_export.py: alterado.
- src/operators.py: alterado.
- src/properties.py: alterado.
- src/translations.py: alterado.
- src/ui.py: alterado.

## Outros pontos da 0.8.6

- analyze_material_structure: componente sem fronteira pode vir valid=True mesmo com is_manifold=False; rejeição final deve continuar efetiva.
- analyze_loop_region: fallback de 1000 mm sem hit não é medição da espessura; ray epsilon 1e-4 BU muda significado em cenas com outra escala.
- Material usa obj.data enquanto o caminho Plano recebe source_mesh_to_cut: rastrear coerência com Edit Mode e modificadores.
- finally de slice_mesh_by_material assume temporários criados: proteger falhas antes da atribuição para não mascarar o erro original.
- validate_printable_mesh só verifica contagem, coordenadas finitas, volume e manifoldness. Nome da função não comprova impressão válida.

Limites: nenhuma linha do registro histórico prova qual código 0.8.7 foi instalado. Não há Blender disponível aqui.
