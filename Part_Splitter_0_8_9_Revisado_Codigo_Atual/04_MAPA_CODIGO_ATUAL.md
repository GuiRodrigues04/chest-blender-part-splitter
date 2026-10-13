# Mapa do código ATUAL recebido — manifesto 0.8.9

Não são linhas da 0.8.6. Fonte-base no pacote; snapshots numerados em referencias/codigo_atual_numerado. O arquivo-base não foi modificado.

## Pontos exatos para cada correção

| Requisito | Arquivo/função e trecho atual | Achado |
|---|---|---|
| INV-008 | geometry_material.py, slice_mesh_by_material; EXTRUDE662–684; BASE551–555/610–615 | Só profundidade/shift axial; mesmo contorno em A/B. |
| INV-012 | geometry_material.py303–339 e697–718/760–782 | target_iface_mat compartilhado; mesmo modo nos dois prismas. |
| INV-010 | operators.py168–201; geometry_material.py345–354 | Validação não mede calc_area/auto-interseção. |
| INV-014 | operators.py619–679 e1093–1112; gpu_drawing.py30–87 | Geração compara assinatura; troca/desenho não invalidam e draw filtra índices. |
| INV-011 | operators.py1595–1733; lifecycle.py | Commit ativaA;parent_op e reversão já existem. |
| INV-013 | geometry_connectors.py418–462/465–490; properties.py628–633 | CENTER25×25 opcional;LINEAR2/3 fixos; flagFalse. |
| INV-013/UI | ui.py378–383;operators.py1260–1288 | Flag passada ao domínio porém não desenhada na UI. |
| SOL-01 | operators.py503–544 e906–934 | Focar chama factory que recria noelse. |
| SOL/interface | geometry_solid.py270–382 | Retorna métricas sem CutInterface;materiais fallback0. |
| LANG | translations.py239–305; ui/properties/operators/lifecycle |25PT/26EN,locale-only e strings mistas. |

As faixas curtas identificam o bloco; use definição por função abaixo para localizar alterações após edições.

## Definições atuais

| Arquivo | Definição | Linhas |
|---|---|---|
| src/__init__.py | register | 10–15 |
| src/__init__.py | unregister | 18–23 |
| src/diagnostic.py | get_scene_scale_to_mm | 9–15 |
| src/diagnostic.py | analyze_target_mesh | 18–136 |
| src/geometry_connectors.py | ConnectorValidationError | 20–22 |
| src/geometry_connectors.py | point_in_polygon_2d | 25–38 |
| src/geometry_connectors.py | point_to_segment_dist_sq | 41–51 |
| src/geometry_connectors.py | min_distance_to_polygon_boundaries | 54–78 |
| src/geometry_connectors.py | find_optimal_grid_axes | 81–136 |
| src/geometry_connectors.py | create_capsule_2d_profile | 139–160 |
| src/geometry_connectors.py | create_pin_mesh_data | 163–249 |
| src/geometry_connectors.py | check_receiving_wall_thickness | 252–315 |
| src/geometry_connectors.py | compute_connector_layout | 319–651 |
| src/geometry_connectors.py | compute_connector_positions | 654–673 |
| src/geometry_connectors.py | validate_connectors | 676–725 |
| src/geometry_connectors.py | determine_connector_material | 729–794 |
| src/geometry_connectors.py | apply_connectors_boolean | 797–1017 |
| src/geometry_contract.py | CutInterface | 15–45 |
| src/geometry_contract.py | build_cut_interface | 48–191 |
| src/geometry_contract.py | SplitResult | 195–214 |
| src/geometry_loop.py | LoopSliceResult | 21–36 |
| src/geometry_loop.py | get_topology_signature | 42–66 |
| src/geometry_loop.py | capture_edge_loop | 69–153 |
| src/geometry_loop.py | capture_face_boundary_loop | 156–266 |
| src/geometry_loop.py | get_selected_seed_face | 269–283 |
| src/geometry_loop.py | slice_mesh_by_loop | 286–551 |
| src/geometry_loop.py | analyze_loop_region | 554–722 |
| src/geometry_loop.py | _get_orthonormal_basis | 725–733 |
| src/geometry_loop.py | triangulate_polygon_2d | 736–906 |
| src/geometry_loop.py | create_loop_prism_cutter | 909–967 |
| src/geometry_loop.py | slice_mesh_by_loop_extrude | 970–1135 |
| src/geometry_material.py | _get_orthonormal_basis | 22–30 |
| src/geometry_material.py | get_material_regions | 33–57 |
| src/geometry_material.py | _order_boundary_loops | 60–90 |
| src/geometry_material.py | list_material_regions | 93–101 |
| src/geometry_material.py | find_region_of_face | 104–116 |
| src/geometry_material.py | analyze_material_structure | 119–273 |
| src/geometry_material.py | create_material_patch_prism_cutter | 276–367 |
| src/geometry_material.py | slice_mesh_by_material | 370–837 |
| src/geometry_plane.py | PlaneSliceError | 13–15 |
| src/geometry_plane.py | NoIntersectionError | 18–20 |
| src/geometry_plane.py | count_mesh_islands | 23–43 |
| src/geometry_plane.py | cap_open_cut_boundaries | 46–128 |
| src/geometry_plane.py | evaluate_bmesh_metrics | 131–180 |
| src/geometry_plane.py | reconstruct_boundary_loops | 183–238 |
| src/geometry_plane.py | slice_mesh_by_plane | 241–406 |
| src/geometry_plane.py | compute_explosion_offsets | 409–428 |
| src/geometry_solid.py | SolidCutterValidationError | 22–24 |
| src/geometry_solid.py | SolidSliceError | 27–29 |
| src/geometry_solid.py | create_bmesh_capsule | 32–116 |
| src/geometry_solid.py | create_primitive_cutter_mesh | 119–182 |
| src/geometry_solid.py | validate_solid_cutter | 185–267 |
| src/geometry_solid.py | slice_mesh_by_solid | 270–381 |
| src/geometry_solid.py | compute_solid_explosion_offsets | 384–414 |
| src/gpu_drawing.py | _get_orthonormal_basis | 19–27 |
| src/gpu_drawing.py | _draw_loop_overlay | 30–132 |
| src/gpu_drawing.py | _compute_cut_line_segments | 135–236 |
| src/gpu_drawing.py | _draw_plane_overlay | 239–399 |
| src/gpu_drawing.py | _draw_overlay_callback | 402–415 |
| src/gpu_drawing.py | register_overlay | 418–430 |
| src/gpu_drawing.py | unregister_overlay | 433–441 |
| src/io_export.py | sanitize_unique_filename | 23–36 |
| src/io_export.py | get_material_rgba | 41–57 |
| src/io_export.py | rgba_to_hex | 60–66 |
| src/io_export.py | publish_staged_files_atomic | 69–117 |
| src/io_export.py | build_3mf_xml | 120–247 |
| src/io_export.py | export_objects_to_3mf | 250–286 |
| src/io_export.py | separate_object_by_material | 290–354 |
| src/io_export.py | export_objects_to_stl_by_material | 357–491 |
| src/lifecycle.py | get_or_create_collection | 27–34 |
| src/lifecycle.py | find_collection | 37–42 |
| src/lifecycle.py | ensure_backups_collection | 45–50 |
| src/lifecycle.py | find_operation_record | 57–64 |
| src/lifecycle.py | get_or_create_operation_record | 67–95 |
| src/lifecycle.py | record_created_object | 98–115 |
| src/lifecycle.py | record_unlinked_parent | 118–128 |
| src/lifecycle.py | capture_target_snapshot | 135–166 |
| src/lifecycle.py | discard_target_snapshot | 169–192 |
| src/lifecycle.py | resolve_operation_status | 199–245 |
| src/lifecycle.py | resolve_operation | 248–251 |
| src/lifecycle.py | check_child_operations | 254–281 |
| src/lifecycle.py | remove_preview | 288–410 |
| src/lifecycle.py | revert_committed_operation | 417–603 |
| src/operators.py | find_collection | 80–85 |
| src/operators.py | get_or_create_collection | 88–95 |
| src/operators.py | cleanup_collection_objects | 99–165 |
| src/operators.py | validate_printable_mesh | 168–200 |
| src/operators.py | get_target_bounds | 204–215 |
| src/operators.py | ensure_plane_guide | 218–254 |
| src/operators.py | read_plane_geometry | 257–270 |
| src/operators.py | compute_session_input_signature | 273–410 |
| src/operators.py | verify_preview_current | 413–445 |
| src/operators.py | get_current_session_parts | 448–500 |
| src/operators.py | ensure_solid_cutter | 503–544 |
| src/operators.py | update_preview_positions | 547–616 |
| src/operators.py | CHEST_OT_splitter_set_target | 619–678 |
| src/operators.py | CHEST_OT_splitter_clear_target | 681–716 |
| src/operators.py | CHEST_OT_splitter_create_work_copy | 719–774 |
| src/operators.py | CHEST_OT_splitter_create_or_focus_guide | 777–794 |
| src/operators.py | CHEST_OT_splitter_align_plane | 797–903 |
| src/operators.py | CHEST_OT_splitter_create_or_focus_solid_cutter | 906–934 |
| src/operators.py | CHEST_OT_splitter_select_existing_cutter | 937–964 |
| src/operators.py | CHEST_OT_splitter_generate_preview | 970–1505 |
| src/operators.py | CHEST_OT_splitter_invert_sides | 1510–1528 |
| src/operators.py | CHEST_OT_splitter_invert_male_female | 1531–1555 |
| src/operators.py | CHEST_OT_splitter_apply_connector_preset | 1558–1591 |
| src/operators.py | CHEST_OT_splitter_commit_parts | 1595–1733 |
| src/operators.py | CHEST_OT_splitter_remove_preview | 1736–1759 |
| src/operators.py | CHEST_OT_splitter_revert_cut | 1762–1827 |
| src/operators.py | CHEST_OT_splitter_restore_original | 1830–1871 |
| src/operators.py | CHEST_OT_splitter_redo_session | 1874–1899 |
| src/operators.py | CHEST_OT_splitter_capture_loop | 1902–1950 |
| src/operators.py | CHEST_OT_splitter_capture_face_boundary | 1953–2021 |
| src/operators.py | CHEST_OT_splitter_define_seed_face | 2024–2055 |
| src/operators.py | CHEST_OT_splitter_separate_by_material | 2058–2123 |
| src/operators.py | CHEST_OT_splitter_export_parts | 2126–2374 |
| src/operators.py | CHEST_OT_splitter_help | 2377–2411 |
| src/operators.py | CHEST_OT_splitter_select_split_material | 2412–2427 |
| src/operators.py | CHEST_OT_splitter_pick_material_region | 2430–2530 |
| src/operators.py | on_depsgraph_update_post | 2566–2634 |
| src/operators.py | on_undo_post | 2638–2652 |
| src/operators.py | on_redo_post | 2656–2669 |
| src/operators.py | register_handlers | 2672–2679 |
| src/operators.py | unregister_handlers | 2682–2689 |
| src/operators.py | register | 2692–2698 |
| src/operators.py | unregister | 2701–2707 |
| src/properties.py | _on_preview_transform_update | 24–31 |
| src/properties.py | _on_param_change_mark_stale | 34–39 |
| src/properties.py | _on_clearance_preset_update | 42–46 |
| src/properties.py | _poll_mesh_cutter | 49–51 |
| src/properties.py | _on_cutter_object_update | 54–81 |
| src/properties.py | _on_target_object_update | 84–86 |
| src/properties.py | ChestObjectRef | 89–93 |
| src/properties.py | ChestOperationRecord | 96–118 |
| src/properties.py | ChestSplitterSettings | 121–797 |
| src/properties.py | register | 807–816 |
| src/properties.py | unregister | 819–830 |
| src/translations.py | _get_current_locale | 297–305 |
| src/translations.py | get_help_tooltip | 308–315 |
| src/translations.py | get_help_popup_content | 318–327 |
| src/translations.py | register_translations | 333–341 |
| src/translations.py | unregister_translations | 344–352 |
| src/ui.py | draw_help_button | 7–11 |
| src/ui.py | VIEW3D_PT_chest_part_splitter | 14–534 |
| src/ui.py | register | 537–541 |
| src/ui.py | unregister | 544–548 |

## Testes com cobertura insuficiente

| Arquivo | Caso | Lacuna estática |
|---|---|---|
| tests/test_inv_001_003_material.py | test_d01_bent_patch_cutter_validation | Não exige lançamento; faces opostas desconectadas. |
| mesmo | test_d02_materials_slots_preservation | Fallback só verifica success; não cavidade/receptor. |
| mesmo | test_d03_clearance_progression | Sem fixture real não executa asserções;volume monotônico não prova folga lateral. |
| mesmo | test_d06_nominal_complementarity | Só verifica volumes positivos. |
| tests/run_all_tests.py | TESTS |28 suites listadas; novos requisitos exigem adições explícitas. |
