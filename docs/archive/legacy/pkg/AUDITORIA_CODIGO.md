# Auditoria estática da base 0.8.10

Fonte: ZIP original incluído. Nenhum código foi corrigido. AST de 17 arquivos válido não prova comportamento Blender. Linhas são da base.

## Achados prioritários

1. A chamada analyze_material_structure(target, scene=...) é incompatível com assinatura que exige material_index e region_index e não recebe scene.

2. O overlay usa propriedades enquanto o corte lê o guia; falta fonte única ao transformar.

3. A assinatura LOOP visível não inclui loop_detach_add_base/depth/clearance nem loop_through_cut nesse ramo. Callbacks stale não substituem assinatura completa; confirmar tokens globais e todos os consumidores.

4. Material continua excluído da geração/assinatura de encaixes.

5. Tampas novas sem adjacência a faces antigas ficam sem material explícito; interface DETACH com base usa contorno/origem antigos.

6. Saneamento antes dos pinos não equivale a validação/saneamento depois. Não transformar hipótese de origem dos micro-defeitos em causa provada.

## Mapa de símbolos

### __init__.py

- `__init__.py:10–15` — `register`

- `__init__.py:18–23` — `unregister`

### constants.py

### diagnostic.py

- `diagnostic.py:11–17` — `get_scene_scale_to_mm`

- `diagnostic.py:20–138` — `analyze_target_mesh`

- `diagnostic.py:141–170` — `sanitize_mesh_micro_degeneracies`

- `diagnostic.py:173–218` — `validate_bmesh_mesh_geometry`

### geometry_connectors.py

- `geometry_connectors.py:20–22` — `ConnectorValidationError`

- `geometry_connectors.py:25–38` — `point_in_polygon_2d`

- `geometry_connectors.py:41–51` — `point_to_segment_dist_sq`

- `geometry_connectors.py:54–78` — `min_distance_to_polygon_boundaries`

- `geometry_connectors.py:81–136` — `find_optimal_grid_axes`

- `geometry_connectors.py:139–160` — `create_capsule_2d_profile`

- `geometry_connectors.py:163–249` — `create_pin_mesh_data`

- `geometry_connectors.py:252–315` — `check_receiving_wall_thickness`

- `geometry_connectors.py:319–717` — `compute_connector_layout`

- `geometry_connectors.py:720–739` — `compute_connector_positions`

- `geometry_connectors.py:742–791` — `validate_connectors`

- `geometry_connectors.py:795–860` — `determine_connector_material`

- `geometry_connectors.py:863–1083` — `apply_connectors_boolean`

### geometry_contract.py

- `geometry_contract.py:15–45` — `CutInterface`

- `geometry_contract.py:48–191` — `build_cut_interface`

- `geometry_contract.py:195–214` — `SplitResult`

### geometry_loop.py

- `geometry_loop.py:21–36` — `LoopSliceResult`

- `geometry_loop.py:42–66` — `get_topology_signature`

- `geometry_loop.py:69–79` — `clear_capture`

- `geometry_loop.py:82–138` — `validate_capture`

- `geometry_loop.py:141–225` — `capture_edge_loop`

- `geometry_loop.py:228–338` — `capture_face_boundary_loop`

- `geometry_loop.py:341–355` — `get_selected_seed_face`

- `geometry_loop.py:358–719` — `slice_mesh_by_loop`

- `geometry_loop.py:722–891` — `analyze_loop_region`

- `geometry_loop.py:894–902` — `_get_orthonormal_basis`

- `geometry_loop.py:905–1112` — `triangulate_polygon_2d`

- `geometry_loop.py:1115–1173` — `create_loop_prism_cutter`

- `geometry_loop.py:1176–1346` — `slice_mesh_by_loop_extrude`

### geometry_material.py

- `geometry_material.py:22–30` — `_get_orthonormal_basis`

- `geometry_material.py:33–101` — `offset_polygon_2d`

- `geometry_material.py:104–128` — `get_material_regions`

- `geometry_material.py:131–161` — `_order_boundary_loops`

- `geometry_material.py:164–172` — `list_material_regions`

- `geometry_material.py:175–187` — `find_region_of_face`

- `geometry_material.py:190–344` — `analyze_material_structure`

- `geometry_material.py:347–472` — `create_material_patch_prism_cutter`

- `geometry_material.py:475–950` — `slice_mesh_by_material`

### geometry_plane.py

- `geometry_plane.py:13–15` — `PlaneSliceError`

- `geometry_plane.py:18–20` — `NoIntersectionError`

- `geometry_plane.py:23–43` — `count_mesh_islands`

- `geometry_plane.py:46–128` — `cap_open_cut_boundaries`

- `geometry_plane.py:131–180` — `evaluate_bmesh_metrics`

- `geometry_plane.py:183–238` — `reconstruct_boundary_loops`

- `geometry_plane.py:241–406` — `slice_mesh_by_plane`

- `geometry_plane.py:409–428` — `compute_explosion_offsets`

### geometry_solid.py

- `geometry_solid.py:22–24` — `SolidCutterValidationError`

- `geometry_solid.py:27–29` — `SolidSliceError`

- `geometry_solid.py:32–116` — `create_bmesh_capsule`

- `geometry_solid.py:119–182` — `create_primitive_cutter_mesh`

- `geometry_solid.py:185–267` — `validate_solid_cutter`

- `geometry_solid.py:270–381` — `slice_mesh_by_solid`

- `geometry_solid.py:384–414` — `compute_solid_explosion_offsets`

### gpu_drawing.py

- `gpu_drawing.py:19–27` — `_get_orthonormal_basis`

- `gpu_drawing.py:30–135` — `_draw_loop_overlay`

- `gpu_drawing.py:138–239` — `_compute_cut_line_segments`

- `gpu_drawing.py:242–402` — `_draw_plane_overlay`

- `gpu_drawing.py:405–504` — `_draw_solid_overlay`

- `gpu_drawing.py:507–522` — `_draw_overlay_callback`

- `gpu_drawing.py:525–537` — `register_overlay`

- `gpu_drawing.py:540–548` — `unregister_overlay`

### io_export.py

- `io_export.py:23–36` — `sanitize_unique_filename`

- `io_export.py:41–57` — `get_material_rgba`

- `io_export.py:60–66` — `rgba_to_hex`

- `io_export.py:69–117` — `publish_staged_files_atomic`

- `io_export.py:120–247` — `build_3mf_xml`

- `io_export.py:250–286` — `export_objects_to_3mf`

- `io_export.py:290–354` — `separate_object_by_material`

- `io_export.py:357–491` — `export_objects_to_stl_by_material`

### lifecycle.py

- `lifecycle.py:27–34` — `get_or_create_collection`

- `lifecycle.py:37–42` — `find_collection`

- `lifecycle.py:45–50` — `ensure_backups_collection`

- `lifecycle.py:57–64` — `find_operation_record`

- `lifecycle.py:67–95` — `get_or_create_operation_record`

- `lifecycle.py:98–115` — `record_created_object`

- `lifecycle.py:118–127` — `record_unlinked_parent`

- `lifecycle.py:128–161` — `resolve_receiver_object`

- `lifecycle.py:169–200` — `capture_target_snapshot`

- `lifecycle.py:203–226` — `discard_target_snapshot`

- `lifecycle.py:233–279` — `resolve_operation_status`

- `lifecycle.py:282–285` — `resolve_operation`

- `lifecycle.py:288–315` — `check_child_operations`

- `lifecycle.py:322–444` — `remove_preview`

- `lifecycle.py:451–637` — `revert_committed_operation`

### operators.py

- `operators.py:80–85` — `find_collection`

- `operators.py:88–95` — `get_or_create_collection`

- `operators.py:99–165` — `cleanup_collection_objects`

- `operators.py:168–207` — `validate_printable_mesh`

- `operators.py:211–222` — `get_target_bounds`

- `operators.py:225–261` — `ensure_plane_guide`

- `operators.py:264–277` — `read_plane_geometry`

- `operators.py:280–417` — `compute_session_input_signature`

- `operators.py:420–452` — `verify_preview_current`

- `operators.py:455–507` — `get_current_session_parts`

- `operators.py:510–542` — `ensure_solid_cutter`

- `operators.py:546–582` — `reset_solid_cutter_mesh`

- `operators.py:586–655` — `update_preview_positions`

- `operators.py:658–717` — `CHEST_OT_splitter_set_target`

- `operators.py:720–755` — `CHEST_OT_splitter_clear_target`

- `operators.py:758–813` — `CHEST_OT_splitter_create_work_copy`

- `operators.py:816–833` — `CHEST_OT_splitter_create_or_focus_guide`

- `operators.py:836–942` — `CHEST_OT_splitter_align_plane`

- `operators.py:945–975` — `CHEST_OT_splitter_create_or_focus_solid_cutter`

- `operators.py:978–1005` — `CHEST_OT_splitter_select_existing_cutter`

- `operators.py:1008–1038` — `CHEST_OT_splitter_create_solid_cutter`

- `operators.py:1041–1071` — `CHEST_OT_splitter_focus_solid_cutter`

- `operators.py:1074–1094` — `CHEST_OT_splitter_reset_solid_cutter`

- `operators.py:1097–1127` — `CHEST_OT_splitter_duplicate_solid_cutter`

- `operators.py:1130–1178` — `CHEST_OT_splitter_copy_selected_as_cutter`

- `operators.py:1181–1350` — `CHEST_OT_splitter_align_solid_cutter`

- `operators.py:1354–1471` — `CHEST_OT_splitter_create_cutter_from_selection`

- `operators.py:1474–1577` — `CHEST_OT_splitter_create_corner_box_cutter`

- `operators.py:1584–2139` — `CHEST_OT_splitter_generate_preview`

- `operators.py:2144–2162` — `CHEST_OT_splitter_invert_sides`

- `operators.py:2165–2189` — `CHEST_OT_splitter_invert_male_female`

- `operators.py:2192–2225` — `CHEST_OT_splitter_apply_connector_preset`

- `operators.py:2229–2380` — `CHEST_OT_splitter_commit_parts`

- `operators.py:2383–2468` — `CHEST_OT_splitter_continue_on_receiver`

- `operators.py:2471–2495` — `CHEST_OT_splitter_edit_target`

- `operators.py:2498–2521` — `CHEST_OT_splitter_remove_preview`

- `operators.py:2524–2589` — `CHEST_OT_splitter_revert_cut`

- `operators.py:2592–2633` — `CHEST_OT_splitter_restore_original`

- `operators.py:2636–2661` — `CHEST_OT_splitter_redo_session`

- `operators.py:2664–2712` — `CHEST_OT_splitter_capture_loop`

- `operators.py:2715–2783` — `CHEST_OT_splitter_capture_face_boundary`

- `operators.py:2786–2817` — `CHEST_OT_splitter_define_seed_face`

- `operators.py:2820–2885` — `CHEST_OT_splitter_separate_by_material`

- `operators.py:2888–3136` — `CHEST_OT_splitter_export_parts`

- `operators.py:3139–3173` — `CHEST_OT_splitter_help`

- `operators.py:3174–3189` — `CHEST_OT_splitter_select_split_material`

- `operators.py:3192–3292` — `CHEST_OT_splitter_pick_material_region`

- `operators.py:3338–3406` — `on_depsgraph_update_post`

- `operators.py:3410–3424` — `on_undo_post`

- `operators.py:3428–3441` — `on_redo_post`

- `operators.py:3444–3451` — `register_handlers`

- `operators.py:3454–3461` — `unregister_handlers`

- `operators.py:3464–3470` — `register`

- `operators.py:3473–3479` — `unregister`

### properties.py

- `properties.py:24–31` — `_on_preview_transform_update`

- `properties.py:34–39` — `_on_param_change_mark_stale`

- `properties.py:42–46` — `_on_clearance_preset_update`

- `properties.py:49–51` — `_poll_mesh_cutter`

- `properties.py:57–92` — `_on_solid_dim_update`

- `properties.py:95–143` — `_on_cutter_object_update`

- `properties.py:147–151` — `_on_target_object_update`

- `properties.py:154–158` — `ChestObjectRef`

- `properties.py:161–183` — `ChestOperationRecord`

- `properties.py:186–952` — `ChestSplitterSettings`

- `properties.py:955–972` — `ChestSplitterAddonPreferences`

- `properties.py:984–993` — `register`

- `properties.py:996–1007` — `unregister`

### translations.py

- `translations.py:417–431` — `get_addon_preferences`

- `translations.py:434–451` — `get_addon_locale`

- `translations.py:454–458` — `_get_current_locale`

- `translations.py:461–475` — `tr`

- `translations.py:478–485` — `get_help_tooltip`

- `translations.py:488–499` — `get_help_popup_content`

- `translations.py:505–513` — `register_translations`

- `translations.py:516–524` — `unregister_translations`

### ui.py

- `ui.py:7–11` — `draw_help_button`

- `ui.py:14–579` — `VIEW3D_PT_chest_part_splitter`

- `ui.py:583–587` — `register`

- `ui.py:590–594` — `unregister`

## Overlay plano lê settings — src/gpu_drawing.py:242–268

```python

0242  def _draw_plane_overlay(context, settings):
0243      """Desenha o retângulo translúcido e a linha de corte do plano na Viewport 3D (F02)."""
0244      show_plane = getattr(settings, "show_plane_preview", True)
0245      show_cut_line = getattr(settings, "show_plane_cut_line", True)
0246  
0247      if not show_plane and not show_cut_line:
0248          return
0249  
0250      target = getattr(settings, "target_object", None)
0251      if not target or target.name not in bpy.data.objects or target.type != 'MESH':
0252          return
0253  
0254      # Normal e Origem em World Space
0255      norm = Vector(getattr(settings, "plane_normal", (0.0, 0.0, 1.0))).normalized()
0256      if norm.length < 1e-5:
0257          return
0258  
0259      # Lê origem atual do corte considerando deslocamento se houver
0260      origin = Vector(getattr(settings, "plane_origin", (0.0, 0.0, 0.0)))
0261      offset_mm = getattr(settings, "plane_offset_mm", 0.0)
0262      if abs(offset_mm) > 1e-6:
0263          from .diagnostic import get_scene_scale_to_mm
0264          scale_to_mm = get_scene_scale_to_mm(context.scene)
0265          origin = origin + (offset_mm / scale_to_mm) * norm
0266  
0267      mw = target.matrix_world
0268      # Centro e raio envolvente do alvo em World Space

```

## Reader plano lê objeto guia — src/operators.py:264–278

```python

0264  def read_plane_geometry(context: bpy.types.Context) -> (Vector, Vector):
0265      """Lê a origem e a normal do plano a partir do objeto guia ou das propriedades."""
0266      col = get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
0267      guide_obj = col.objects.get(PLANE_GUIDE_NAME)
0268      settings = context.scene.chest_splitter
0269  
0270      if guide_obj:
0271          origin = guide_obj.matrix_world.translation.copy()
0272          normal = (guide_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
0273          settings.plane_origin = origin
0274          settings.plane_normal = normal
0275          return origin, normal
0276      else:
0277          return Vector(settings.plane_origin), Vector(settings.plane_normal).normalized()
0278  

```

## Assinatura por modo; observar flags de base/passante — src/operators.py:386–418

```python

0386      elif settings.split_mode == 'LOOP':
0387          tokens.append(f"loop_indices:{settings.loop_vertex_indices}")
0388          tokens.append(f"loop_depth:{settings.loop_extrude_depth_mm:.4f}")
0389          tokens.append(f"loop_mode:{settings.loop_behavior}")
0390          tokens.append(f"loop_seed:{settings.loop_seed_face_index}")
0391  
0392      elif settings.split_mode == 'MATERIAL':
0393          tokens.append(f"mat_idx:{settings.material_split_index}")
0394          tokens.append(f"mat_region:{settings.material_region_index}")
0395          tokens.append(f"mat_depth:{settings.material_extrude_depth_mm:.4f}")
0396          tokens.append(f"mat_mode:{settings.material_extraction_mode}")
0397          tokens.append(f"mat_iface_mat:{settings.material_interface_mat_mode}")
0398          tokens.append(f"mat_clearance:{getattr(settings, 'part_clearance_mm', 0.0):.4f}")
0399          tokens.append(f"mat_clearance_app:{getattr(settings, 'part_clearance_apply_to', 'PART')}")
0400  
0401      # 3. Encaixes (apenas se ativos e suportados no modo)
0402      tokens.append(f"conn_enabled:{settings.connector_enabled}")
0403      if settings.connector_enabled and settings.split_mode not in ('SOLID', 'MATERIAL'):
0404          tokens.append(f"conn_type:{settings.connector_type}")
0405          tokens.append(f"conn_diam:{settings.connector_diameter_mm:.4f}")
0406          tokens.append(f"conn_len:{settings.connector_length_mm:.4f}")
0407          tokens.append(f"conn_cap_len:{settings.connector_capsule_length_mm:.4f}")
0408          tokens.append(f"conn_chamf:{getattr(settings, 'connector_chamfer_mm', 0.5):.4f}")
0409          tokens.append(f"conn_end_clear:{getattr(settings, 'end_clearance_mm', 0.5):.4f}")
0410          tokens.append(f"conn_adj_valid:{getattr(settings, 'adjust_to_valid_area', False)}")
0411          tokens.append(f"conn_dist:{settings.connector_distribution}")
0412          tokens.append(f"conn_margin:{settings.connector_edge_margin_mm:.4f}")
0413          tokens.append(f"conn_male:{settings.connector_male_part}")
0414  
0415      if tokens:
0416          h.update("|".join(tokens).encode("utf-8"))
0417      return h.hexdigest()[:16]
0418  

```

## Chamada incompatível de análise Material — src/operators.py:1389–1424

```python

1389          depth_bu = self.depth_mm / unit_scale
1390          outer_bu = self.outer_extension_mm / unit_scale
1391  
1392          col = get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
1393          prism_name = f"Prism_Cutter_{target.name}"
1394  
1395          if settings.split_mode == 'MATERIAL':
1396              from .geometry_material import create_material_patch_prism_cutter, analyze_material_structure
1397              mat_idx = settings.material_split_index
1398              reg_idx = settings.material_region_index
1399              try:
1400                  analysis = analyze_material_structure(target, scene=context.scene)
1401                  region_faces = analysis.get("region_face_indices", [])
1402                  if not region_faces:
1403                      self.report({'ERROR'}, "Nenhuma região válida identificada para o material selecionado.")
1404                      return {'CANCELLED'}
1405                  inward_dir = analysis.get("inward_dir_world", Vector((0.0, 0.0, -1.0)))
1406                  if self.invert_direction:
1407                      inward_dir = -inward_dir
1408                  body_mat = analysis.get("body_mat_index", 0)
1409                  prism_obj = create_material_patch_prism_cutter(
1410                      target,
1411                      region_faces,
1412                      inward_dir,
1413                      depth_bu=depth_bu,
1414                      outward_ext_bu=outer_bu,
1415                      name=prism_name,
1416                      material_index=mat_idx,
1417                      interface_mat_mode=settings.material_interface_mat_mode,
1418                      body_mat_index=body_mat,
1419                      lateral_offset_bu=0.0,
1420                  )
1421              except Exception as e:
1422                  self.report({'ERROR'}, f"Não foi possível gerar prisma de material: {str(e)}")
1423                  return {'CANCELLED'}
1424          else:

```

## Assinatura real e estado avaliado — src/geometry_material.py:190–212

```python

0190  def analyze_material_structure(obj: bpy.types.Object, material_index: int, region_index: int = 0) -> Dict[str, Any]:
0191      """Analisa a topologia de UMA região conectada (ilha) de faces de um material.
0192  
0193      Um mesmo material pode aparecer em várias áreas separadas do modelo (ex: dois quadrados
0194      rosa em lados diferentes). Cada área é tratada como uma região independente, com seu
0195      próprio contorno e direção de extração.
0196      """
0197      if not obj or obj.type != 'MESH':
0198          return {"valid": False, "error": "Objeto inválido."}
0199  
0200      bm = bmesh.new()
0201      bm.from_mesh(obj.data)
0202      bm.transform(obj.matrix_world)
0203      bm.verts.ensure_lookup_table()
0204      bm.edges.ensure_lookup_table()
0205      bm.faces.ensure_lookup_table()
0206  
0207      total_faces = len(bm.faces)
0208      regions = get_material_regions(bm, material_index)
0209  
0210      if not regions:
0211          bm.free()
0212          return {"valid": False, "error": f"Nenhuma face com o material #{material_index} encontrada.", "region_count": 0}

```

## EXTRUDE Material: depth e lateral offset — src/geometry_material.py:759–829

```python

0759                  "sum_volume_mm3": metrics_a["volume_mm3"] + metrics_b["volume_mm3"],
0760              },
0761              success=True,
0762          )
0763          return LoopSliceResult(bm_a, bm_b, split_res)
0764  
0765      else:
0766          # Extração superficial com profundidade (M03)
0767          if part_clearance_mm > 0.0:
0768              if part_clearance_mm >= depth_mm - 0.1:
0769                  raise ValueError(
0770                      f"A folga de material ({part_clearance_mm:.2f} mm) excede ou elimina a profundidade útil da peça "
0771                      f"({depth_mm:.2f} mm). Reduza a folga ou aumente a profundidade."
0772                  )
0773  
0774          inward_dir = analysis["inward_dir_world"]
0775          depth_bu = depth_mm / scale_to_mm
0776          outward_ext_bu = max(0.5 / scale_to_mm, 1.0 / scale_to_mm)
0777  
0778          clearance_bu = (part_clearance_mm / scale_to_mm) if part_clearance_mm > 0.0 else 0.0
0779          if part_clearance_apply_to == 'PART':
0780              depth_a_bu = max(0.05 / scale_to_mm, depth_bu - clearance_bu)
0781              depth_b_bu = depth_bu
0782              lat_off_a = clearance_bu
0783              lat_off_b = 0.0
0784          elif part_clearance_apply_to == 'CAVITY':
0785              depth_a_bu = depth_bu
0786              depth_b_bu = depth_bu + clearance_bu
0787              lat_off_a = 0.0
0788              lat_off_b = -clearance_bu
0789          elif part_clearance_apply_to == 'BOTH':
0790              depth_a_bu = max(0.05 / scale_to_mm, depth_bu - 0.5 * clearance_bu)
0791              depth_b_bu = depth_bu + 0.5 * clearance_bu
0792              lat_off_a = 0.5 * clearance_bu
0793              lat_off_b = -0.5 * clearance_bu
0794          else:
0795              depth_a_bu = depth_bu
0796              depth_b_bu = depth_bu
0797              lat_off_a = 0.0
0798              lat_off_b = 0.0
0799  
0800          temp_obj_a = None
0801          temp_obj_b = None
0802          prism_obj_a = None
0803          prism_obj_b = None
0804          eval_a = None
0805          eval_b = None
0806          mesh_a = None
0807          mesh_b = None
0808  
0809          try:
0810              body_mat_idx = analysis.get("body_mat_index", 0)
0811              prism_obj_a = create_material_patch_prism_cutter(
0812                  obj=obj,
0813                  region_face_indices=analysis["region_face_indices"],
0814                  inward_dir=inward_dir,
0815                  depth_bu=depth_a_bu,
0816                  outward_ext_bu=outward_ext_bu,
0817                  name=f"{obj.name}_mat_prism_a",
0818                  material_index=material_index,
0819                  interface_mat_mode=interface_mat_mode,
0820                  body_mat_index=body_mat_idx,
0821                  lateral_offset_bu=lat_off_a,
0822              )
0823              prism_obj_b = create_material_patch_prism_cutter(
0824                  obj=obj,
0825                  region_face_indices=analysis["region_face_indices"],
0826                  inward_dir=inward_dir,
0827                  depth_bu=depth_b_bu,
0828                  outward_ext_bu=outward_ext_bu,
0829                  name=f"{obj.name}_mat_prism_b",

```

## Base adicional já existe — src/geometry_loop.py:504–524

```python

0504          inward_dir = analysis["inward_dir_world"]
0505          max_avail_mm = analysis.get("max_avail_depth_mm", 0.0)
0506          if analysis.get("thickness_determined", False) and max_avail_mm > 0:
0507              if detach_base_depth_mm > (max_avail_mm + 1e-3):
0508                  bm_a.free()
0509                  bm_b.free()
0510                  raise ValueError(
0511                      f"A profundidade da base ({detach_base_depth_mm:.1f} mm) ultrapassa a espessura da parede "
0512                      f"({max_avail_mm:.1f} mm). Reduza a profundidade da base."
0513                  )
0514  
0515          depth_bu = detach_base_depth_mm / scale_to_mm
0516          new_verts_a = [bm_a.verts.new(v.co + inward_dir * depth_bu) for v in loop_verts_a]
0517          bm_a.verts.ensure_lookup_table()
0518          for i in range(n_loop):
0519              i_next = (i + 1) % n_loop
0520              try:
0521                  fa = bm_a.faces.new((loop_verts_a[i], new_verts_a[i], new_verts_a[i_next], loop_verts_a[i_next]))
0522                  created_faces_a.append(fa)
0523              except Exception:
0524                  try:

```

## Offset só nos vértices novos do receptor — src/geometry_loop.py:551–589

```python

0551                  d1 = (p_curr - p_prev).normalized() if (p_curr - p_prev).length > 1e-7 else Vector((1.0, 0.0))
0552                  d2 = (p_next - p_curr).normalized() if (p_next - p_curr).length > 1e-7 else Vector((1.0, 0.0))
0553                  n1 = Vector((d1.y, -d1.x)) if is_ccw else Vector((-d1.y, d1.x))
0554                  n2 = Vector((d2.y, -d2.x)) if is_ccw else Vector((-d2.y, d2.x))
0555                  n_sum = n1 + n2
0556                  n_avg = n_sum.normalized() if n_sum.length > 1e-6 else n1
0557                  cos_half = max(0.5, n_avg.dot(n1))
0558                  scale_fac = min(2.0, 1.0 / cos_half)
0559                  offset_3d = (n_avg.x * u_vec + n_avg.y * v_vec) * (clearance_bu * scale_fac)
0560                  vert_offsets_3d.append(offset_3d)
0561          else:
0562              vert_offsets_3d = [Vector((0.0, 0.0, 0.0)) for _ in range(n_loop)]
0563  
0564          new_verts_b = [bm_b.verts.new(v.co + inward_dir * depth_bu + vert_offsets_3d[i]) for i, v in enumerate(loop_verts_b)]
0565          bm_b.verts.ensure_lookup_table()
0566          for i in range(n_loop):
0567              i_next = (i + 1) % n_loop
0568              try:
0569                  fb = bm_b.faces.new((loop_verts_b[i], loop_verts_b[i_next], new_verts_b[i_next], new_verts_b[i]))
0570                  created_faces_b.append(fb)
0571              except Exception:
0572                  try:
0573                      fb = bm_b.faces.new((loop_verts_b[i], new_verts_b[i], new_verts_b[i_next], loop_verts_b[i_next]))
0574                      created_faces_b.append(fb)
0575                  except Exception:
0576                      pass
0577  
0578          for i, j, k in tri_indices:
0579              try:
0580                  fb = bm_b.faces.new((new_verts_b[i], new_verts_b[j], new_verts_b[k]))
0581                  created_faces_b.append(fb)
0582              except ValueError:
0583                  try:
0584                      fb = bm_b.faces.new((new_verts_b[i], new_verts_b[k], new_verts_b[j]))
0585                      created_faces_b.append(fb)
0586                  except Exception:
0587                      pass
0588      else:
0589          # Fechamento direto no plano do contorno

```

## Herança de materiais e interface da base — src/geometry_loop.py:650–704

```python

0650          )
0651  
0652      # Herança de materiais
0653      if created_faces_a:
0654          created_set_a = set(created_faces_a)
0655          for f in created_faces_a:
0656              adj = [lf.material_index for e in f.edges for lf in e.link_faces if lf not in created_set_a]
0657              if adj:
0658                  f.material_index = max(set(adj), key=adj.count)
0659  
0660      if created_faces_b:
0661          created_set_b = set(created_faces_b)
0662          for f in created_faces_b:
0663              adj = [lf.material_index for e in f.edges for lf in e.link_faces if lf not in created_set_b]
0664              if adj:
0665                  f.material_index = max(set(adj), key=adj.count)
0666  
0667      # Recalcula normais da Parte A e Parte B (garante orientação externa no sólido manifold)
0668      bmesh.ops.recalc_face_normals(bm_a, faces=bm_a.faces[:])
0669      bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces[:])
0670  
0671      # Determina a normal da interface que aponta DE A PARA B
0672      if detach_add_base and detach_base_depth_mm > 0.0:
0673          normal_a_to_b = inward_dir
0674      elif created_faces_a:
0675          valid_caps = [f for f in created_faces_a if f.is_valid]
0676          if valid_caps:
0677              avg_cap_norm = sum((f.normal for f in valid_caps), Vector()) / len(valid_caps)
0678              if avg_cap_norm.length > 1e-5:
0679                  normal_a_to_b = avg_cap_norm.normalized()
0680              else:
0681                  normal_a_to_b = n
0682          else:
0683              normal_a_to_b = n
0684      else:
0685          normal_a_to_b = n
0686  
0687      # Constrói CutInterface formal em World Space
0688      iface_tris = [
0689          (loop_coords_world[i], loop_coords_world[j], loop_coords_world[k])
0690          for i, j, k in tri_indices
0691      ] if tri_indices else None
0692  
0693      cut_interface = build_cut_interface(
0694          origin_world=centroid_world,
0695          normal_a_to_b=normal_a_to_b,
0696          boundary_points_world=loop_coords_world,
0697          interface_triangles=iface_tris,
0698          unit_scale=scale_to_mm,
0699          source_mode="LOOP",
0700      )
0701  
0702      metrics_a = evaluate_bmesh_metrics(bm_a, unit_scale=scale_to_mm)
0703      metrics_b = evaluate_bmesh_metrics(bm_b, unit_scale=scale_to_mm)
0704  

```

## Interface EXTRUDE deslocada — src/geometry_loop.py:1280–1304

```python

1280          bmesh.ops.recalc_face_normals(bm_a, faces=bm_a.faces[:])
1281          bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces[:])
1282  
1283          if through_cut:
1284              interface_origin = analysis["centroid_world"]
1285              interface_boundary = coords_world
1286          else:
1287              interface_origin = analysis["centroid_world"] + (depth_mm / scale_to_mm) * inward_dir
1288              interface_boundary = [p + (depth_mm / scale_to_mm) * inward_dir for p in coords_world]
1289          cut_interface = build_cut_interface(
1290              origin_world=interface_origin,
1291              normal_a_to_b=inward_dir,
1292              boundary_points_world=interface_boundary,
1293              unit_scale=scale_to_mm,
1294              source_mode="LOOP",
1295          )
1296  
1297          metrics_a = evaluate_bmesh_metrics(bm_a, unit_scale=scale_to_mm)
1298          metrics_b = evaluate_bmesh_metrics(bm_b, unit_scale=scale_to_mm)
1299  
1300          split_result = SplitResult(
1301              part_a_metrics=metrics_a,
1302              part_b_metrics=metrics_b,
1303              interface=cut_interface,
1304              diagnostics_before_connectors={

```

## CDT e mapas de origem — src/geometry_loop.py:933–968

```python

0933      # 2. Triangulação nativa restrita via mathutils.geometry.delaunay_2d_cdt (R1 / DEV-06)
0934      try:
0935          import mathutils
0936          edges = [(i, (i + 1) % n) for i in range(n)]
0937          face_poly = [list(range(n))] if is_ccw else [list(reversed(range(n)))]
0938          out_verts, out_edges, out_faces, orig_v, orig_e, orig_f = mathutils.geometry.delaunay_2d_cdt(
0939              pts_vec, edges, face_poly, 1, 1e-6
0940          )
0941          cdt_tris = []
0942          for f in out_faces:
0943              if len(f) != 3:
0944                  continue
0945              idx0 = orig_v[f[0]][0] if orig_v[f[0]] else f[0]
0946              idx1 = orig_v[f[1]][0] if orig_v[f[1]] else f[1]
0947              idx2 = orig_v[f[2]][0] if orig_v[f[2]] else f[2]
0948              if idx0 == idx1 or idx1 == idx2 or idx2 == idx0:
0949                  continue
0950              p0, p1, p2 = pts_vec[idx0], pts_vec[idx1], pts_vec[idx2]
0951              tri_signed = 0.5 * ((p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y))
0952              if abs(tri_signed) < 1e-12:
0953                  continue
0954              if is_ccw:
0955                  tri = (idx0, idx1, idx2) if tri_signed > 0 else (idx0, idx2, idx1)
0956              else:
0957                  tri = (idx0, idx2, idx1) if tri_signed > 0 else (idx0, idx1, idx2)
0958              cdt_tris.append(tri)
0959          if len(cdt_tris) >= (n - 2):
0960              return cdt_tris
0961      except Exception:
0962          pass
0963  
0964      # 3. Fallback: Ear Clipping com filtragem estrita de degenerações
0965      indices = list(range(n)) if is_ccw else list(reversed(range(n)))
0966      poly = [pts_vec[i] for i in indices]
0967  
0968      corners = []

```

## CENTER busca grid 25 — src/geometry_connectors.py:413–447

```python

0413  
0414      margin_bu = edge_margin_mm / unit_scale
0415      avail_major = max(0.0, (span_major / 2.0) - margin_bu)
0416      avail_minor = max(0.0, (span_minor / 2.0) - margin_bu)
0417  
0418      positions = []
0419  
0420      # Validação de distribuições múltiplas (Critério C4: sem redução silenciosa)
0421      if distribution == 'CENTER':
0422          cand_u, cand_v = center_u, center_v
0423          check_r = (diameter_mm / 2.0 + clearance_per_side_mm + edge_margin_mm) / unit_scale
0424          is_center_valid = False
0425          if outer_polys:
0426              in_outer = any(point_in_polygon_2d(cand_u, cand_v, poly) for poly in outer_polys)
0427              not_in_hole = not any(point_in_polygon_2d(cand_u, cand_v, h_poly) for h_poly in hole_polys)
0428              if in_outer and not_in_hole:
0429                  dist_to_edges = min_distance_to_polygon_boundaries(cand_u, cand_v, outer_polys, hole_polys)
0430                  if dist_to_edges >= check_r - 1e-6:
0431                      is_center_valid = True
0432  
0433          if not is_center_valid and outer_polys and adjust_to_valid_area:
0434              # Em regiões côncavas (como U ou L), o centro da bounding box cai no vazio (B06 / D2 / T12).
0435              # Busca determinística pelo ponto de maior distância útil das bordas (pólo de inacessibilidade)
0436              best_pt = None
0437              best_dist = -1.0
0438              steps = 25
0439              for si in range(1, steps):
0440                  gu = min_u + (span_u * si / steps)
0441                  for sj in range(1, steps):
0442                      gv = min_v + (span_v * sj / steps)
0443                      if any(point_in_polygon_2d(gu, gv, poly) for poly in outer_polys):
0444                          if not any(point_in_polygon_2d(gu, gv, h_poly) for h_poly in hole_polys):
0445                              d = min_distance_to_polygon_boundaries(gu, gv, outer_polys, hole_polys)
0446                              if d > best_dist:
0447                                  best_dist = d

```

## LINEAR_2 e LINEAR_3 — src/geometry_connectors.py:449–504

```python

0449  
0450              if best_pt is not None:
0451                  cand_u, cand_v = best_pt[0], best_pt[1]
0452  
0453          p = plane_origin + (u_axis * cand_u) + (v_axis * cand_v)
0454          positions.append(p)
0455  
0456      elif distribution == 'LINEAR_2':
0457          min_span_linear2 = 2.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 2.0
0458          if span_major_mm < min_span_linear2:
0459              raise ConnectorValidationError(
0460                  f"Falta de espaço: a distribuição LINEAR_2 requer vão de ao menos {min_span_linear2:.1f} mm "
0461                  f"(disponível: {span_major_mm:.1f} mm). Reduza a quantidade ou medidas dos encaixes."
0462              )
0463          d_major = avail_major * 0.6
0464          if outer_polys and adjust_to_valid_area:
0465              best_d = d_major
0466              best_min_dist = -1.0
0467              for factor in [0.6, 0.5, 0.45, 0.4, 0.35, 0.3, 0.7, 0.25]:
0468                  dt = avail_major * factor
0469                  test_p1 = plane_origin + (major_axis * (center_major - dt)) + (minor_axis * center_minor)
0470                  test_p2 = plane_origin + (major_axis * (center_major + dt)) + (minor_axis * center_minor)
0471                  rel1 = test_p1 - plane_origin
0472                  rel2 = test_p2 - plane_origin
0473                  u1, v1 = rel1.dot(u_axis), rel1.dot(v_axis)
0474                  u2, v2 = rel2.dot(u_axis), rel2.dot(v_axis)
0475                  if any(point_in_polygon_2d(u1, v1, poly) for poly in outer_polys) and not any(point_in_polygon_2d(u1, v1, h) for h in hole_polys):
0476                      if any(point_in_polygon_2d(u2, v2, poly) for poly in outer_polys) and not any(point_in_polygon_2d(u2, v2, h) for h in hole_polys):
0477                          dist1 = min_distance_to_polygon_boundaries(u1, v1, outer_polys, hole_polys)
0478                          dist2 = min_distance_to_polygon_boundaries(u2, v2, outer_polys, hole_polys)
0479                          min_d = min(dist1, dist2)
0480                          if min_d > best_min_dist:
0481                              best_min_dist = min_d
0482                              best_d = dt
0483              d_major = best_d
0484  
0485          p1 = plane_origin + (major_axis * (center_major - d_major)) + (minor_axis * center_minor)
0486          p2 = plane_origin + (major_axis * (center_major + d_major)) + (minor_axis * center_minor)
0487          positions.extend([p1, p2])
0488  
0489      elif distribution == 'LINEAR_3':
0490          min_span_linear3 = 3.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 4.0
0491          if span_major_mm < min_span_linear3:
0492              raise ConnectorValidationError(
0493                  f"Falta de espaço: a distribuição LINEAR_3 requer vão de ao menos {min_span_linear3:.1f} mm "
0494                  f"(disponível: {span_major_mm:.1f} mm). Reduza a quantidade ou medidas dos encaixes."
0495              )
0496          p_mid = plane_origin + (major_axis * center_major) + (minor_axis * center_minor)
0497          d_major = avail_major * 0.7
0498          p1 = plane_origin + (major_axis * (center_major - d_major)) + (minor_axis * center_minor)
0499          p2 = plane_origin + (major_axis * (center_major + d_major)) + (minor_axis * center_minor)
0500          positions.extend([p_mid, p1, p2])
0501  
0502      elif distribution == 'AUTO_SHAPE':
0503          min_span_auto2 = 2.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 2.0
0504          if span_major_mm >= min_span_auto2 and (span_major / max(span_minor, 1e-4)) >= 1.6:

```

## AUTO busca linha ou ponto — src/geometry_connectors.py:504–545

```python

0504          if span_major_mm >= min_span_auto2 and (span_major / max(span_minor, 1e-4)) >= 1.6:
0505              d_major = avail_major * 0.55
0506              if outer_polys:
0507                  best_d = d_major
0508                  best_min_dist = -1.0
0509                  for factor in [0.55, 0.45, 0.35, 0.65, 0.25]:
0510                      dt = avail_major * factor
0511                      test_p1 = plane_origin + (major_axis * (center_major - dt)) + (minor_axis * center_minor)
0512                      test_p2 = plane_origin + (major_axis * (center_major + dt)) + (minor_axis * center_minor)
0513                      rel1 = test_p1 - plane_origin
0514                      rel2 = test_p2 - plane_origin
0515                      u1, v1 = rel1.dot(u_axis), rel1.dot(v_axis)
0516                      u2, v2 = rel2.dot(u_axis), rel2.dot(v_axis)
0517                      if any(point_in_polygon_2d(u1, v1, poly) for poly in outer_polys) and not any(point_in_polygon_2d(u1, v1, h) for h in hole_polys):
0518                          if any(point_in_polygon_2d(u2, v2, poly) for poly in outer_polys) and not any(point_in_polygon_2d(u2, v2, h) for h in hole_polys):
0519                              dist1 = min_distance_to_polygon_boundaries(u1, v1, outer_polys, hole_polys)
0520                              dist2 = min_distance_to_polygon_boundaries(u2, v2, outer_polys, hole_polys)
0521                              min_d = min(dist1, dist2)
0522                              if min_d > best_min_dist:
0523                                  best_min_dist = min_d
0524                                  best_d = dt
0525                  d_major = best_d
0526              p1 = plane_origin + (major_axis * (center_major - d_major)) + (minor_axis * center_minor)
0527              p2 = plane_origin + (major_axis * (center_major + d_major)) + (minor_axis * center_minor)
0528              positions.extend([p1, p2])
0529          else:
0530              best_pt = (center_u, center_v)
0531              best_dist = -1.0
0532              if outer_polys:
0533                  steps = 25
0534                  for si in range(1, steps):
0535                      gu = min_u + (span_u * si / steps)
0536                      for sj in range(1, steps):
0537                          gv = min_v + (span_v * sj / steps)
0538                          if any(point_in_polygon_2d(gu, gv, poly) for poly in outer_polys):
0539                              if not any(point_in_polygon_2d(gu, gv, h_poly) for h_poly in hole_polys):
0540                                  d = min_distance_to_polygon_boundaries(gu, gv, outer_polys, hole_polys)
0541                                  if d > best_dist:
0542                                      best_dist = d
0543                                      best_pt = (gu, gv)
0544              p = plane_origin + (u_axis * best_pt[0]) + (v_axis * best_pt[1])
0545              positions.append(p)

```

## GRID_4 restringe grade — src/geometry_connectors.py:546–625

```python

0546  
0547      elif distribution == 'GRID_4':
0548          min_grid_major = 2.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 2.0
0549          min_grid_minor = 2.0 * cavity_diam_mm + 2.0 * edge_margin_mm + 2.0
0550  
0551          grid_u_axis = u_axis
0552          grid_v_axis = v_axis
0553          grid_span_u = span_u
0554          grid_span_v = span_v
0555          grid_center_u = center_u
0556          grid_center_v = center_v
0557  
0558          # Se houver contorno poligonal definido, calcula os eixos ótimos alinhados às arestas (OMBB - C05)
0559          if outer_polys:
0560              g_u, g_v, s_u, s_v, c_u, c_v = find_optimal_grid_axes(outer_polys[0], u_axis, v_axis)
0561              if s_u > 1e-4 and s_v > 1e-4:
0562                  grid_u_axis = g_u
0563                  grid_v_axis = g_v
0564                  grid_span_u = s_u
0565                  grid_span_v = s_v
0566                  grid_center_u = c_u
0567                  grid_center_v = c_v
0568  
0569          grid_span_u_mm = grid_span_u * unit_scale
0570          grid_span_v_mm = grid_span_v * unit_scale
0571  
0572          if grid_span_u_mm < min_grid_minor - 1e-3 or grid_span_v_mm < min_grid_minor - 1e-3:
0573              raise ConnectorValidationError(
0574                  f"Falta de espaço: a distribuição GRID_4 requer ao menos {min_grid_major:.1f}x{min_grid_minor:.1f} mm "
0575                  f"(disponível: {grid_span_u_mm:.1f}x{grid_span_v_mm:.1f} mm). Reduza a quantidade ou medidas dos encaixes."
0576              )
0577  
0578          avail_grid_u = max(0.0, (grid_span_u / 2.0) - margin_bu)
0579          avail_grid_v = max(0.0, (grid_span_v / 2.0) - margin_bu)
0580  
0581          check_r = (diameter_mm / 2.0 + clearance_per_side_mm + edge_margin_mm) / unit_scale
0582          min_pitch_mm = cavity_diam_mm + 2.0
0583  
0584          def _generate_4_cand(scale_f: float) -> List[Vector]:
0585              du = avail_grid_u * scale_f
0586              dv = avail_grid_v * scale_f
0587              pts = []
0588              for su, sv in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
0589                  p = plane_origin + (grid_u_axis * (grid_center_u + su * du)) + (grid_v_axis * (grid_center_v + sv * dv))
0590                  pts.append(p)
0591              return pts
0592  
0593          def _is_4_cand_valid(pts: List[Vector]) -> bool:
0594              if not outer_polys:
0595                  return True
0596              for pos in pts:
0597                  up = (pos - plane_origin).dot(u_axis)
0598                  vp = (pos - plane_origin).dot(v_axis)
0599                  if not any(point_in_polygon_2d(up, vp, p) for p in outer_polys):
0600                      return False
0601                  if any(point_in_polygon_2d(up, vp, hp) for hp in hole_polys):
0602                      return False
0603                  d = min_distance_to_polygon_boundaries(up, vp, outer_polys, hole_polys)
0604                  if d < check_r - 1e-6:
0605                      return False
0606              return True
0607  
0608          selected_cand = None
0609          for test_scale in (0.55, 0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15):
0610              cand = _generate_4_cand(test_scale)
0611              du_mm = 2.0 * avail_grid_u * test_scale * unit_scale
0612              dv_mm = 2.0 * avail_grid_v * test_scale * unit_scale
0613              if du_mm < min_pitch_mm or dv_mm < min_pitch_mm:
0614                  continue
0615              if _is_4_cand_valid(cand):
0616                  selected_cand = cand
0617                  break
0618  
0619          if selected_cand is not None:
0620              positions.extend(selected_cand)
0621          else:
0622              cand_nom = _generate_4_cand(0.55)
0623              positions.extend(cand_nom)
0624  
0625      # Cálculo dos limites laterais seguros para cápsula

```

## Footprint amostrado — src/geometry_connectors.py:662–710

```python

0662      # Validação rigorosa de inclusão do perfil completo no domínio sólido da interface (B04/B05)
0663      if outer_polys:
0664          check_r = (diameter_mm / 2.0 + clearance_per_side_mm + edge_margin_mm) / unit_scale
0665          u_proj = major_axis.dot(u_axis)
0666          v_proj = major_axis.dot(v_axis)
0667          rot_ang = math.atan2(v_proj, u_proj)
0668          cos_rot = math.cos(rot_ang)
0669          sin_rot = math.sin(rot_ang)
0670  
0671          for idx, pos in enumerate(positions):
0672              u_p = (pos - plane_origin).dot(u_axis)
0673              v_p = (pos - plane_origin).dot(v_axis)
0674  
0675              test_pts = [(u_p, v_p)]
0676              if connector_type == 'CAPSULE':
0677                  eff_cap = max(diameter_mm, adjusted_cap_len_mm) if adjusted_cap_len_mm > 0.0 else (diameter_mm * 2.4)
0678                  half_len = max(0.0, (eff_cap - diameter_mm) / 2.0) / unit_scale
0679                  prof = create_capsule_2d_profile(w=check_r, half_len=half_len, segments=24)
0680                  # No perfil da cápsula: Y (ly) é o eixo de alongamento (major_axis) e X (lx) é a largura (minor_axis)
0681                  # major_axis no plano UV é (cos_rot, sin_rot), minor_axis é (-sin_rot, cos_rot)
0682                  for lx, ly in prof:
0683                      test_pts.append((
0684                          u_p + ly * cos_rot - lx * sin_rot,
0685                          v_p + ly * sin_rot + lx * cos_rot,
0686                      ))
0687              else:
0688                  for ang_idx in range(16):
0689                      ang = 2.0 * math.pi * ang_idx / 16.0
0690                      test_pts.append((u_p + check_r * math.cos(ang), v_p + check_r * math.sin(ang)))
0691  
0692              for tp in test_pts:
0693                  in_any_outer = any(point_in_polygon_2d(tp[0], tp[1], poly) for poly in outer_polys)
0694                  if not in_any_outer:
0695                      raise ConnectorValidationError(
0696                          f"O encaixe #{idx+1} ultrapassa a margem de segurança de {edge_margin_mm:.1f} mm "
0697                          f"ou cai fora do domínio sólido da peça."
0698                      )
0699                  for hole_poly in hole_polys:
0700                      if point_in_polygon_2d(tp[0], tp[1], hole_poly):
0701                          raise ConnectorValidationError(
0702                              f"O encaixe #{idx+1} invade um furo/vazio interno da interface."
0703                          )
0704  
0705      return {
0706          "positions": positions,
0707          "major_axis": major_axis,
0708          "minor_axis": minor_axis,
0709          "span_major_mm": span_major_mm,
0710          "span_minor_mm": span_minor_mm,

```

## Espessura centro e quatro raios — src/geometry_connectors.py:252–318

```python

0252  def check_receiving_wall_thickness(
0253      obj_female: bpy.types.Object,
0254      positions: List[Vector],
0255      normal: Vector,
0256      required_depth_bu: float,
0257      min_wall_bu: float = 1e-4,
0258      cavity_radius_bu: float = 0.0,
0259  ) -> Tuple[bool, float]:
0260      """Verifica se a cavidade de inserção atravessaria a parede da peça receptora (Defeito C5).
0261      
0262      Amostra o centro e pontos perimétricos para detectar paredes inclinadas ou perfurações
0263      indesejadas em quinas e superfícies curvas.
0264      """
0265      depsgraph = bpy.context.evaluated_depsgraph_get()
0266      eval_obj = obj_female.evaluated_get(depsgraph)
0267      eval_mesh = eval_obj.to_mesh()
0268      try:
0269          bm = bmesh.new()
0270          bm.from_mesh(eval_mesh)
0271          bm.transform(obj_female.matrix_world)
0272          bvh = BVHTree.FromBMesh(bm)
0273          norm = normal.normalized()
0274  
0275          # Vetores perpendiculares no plano de corte para amostragem perimétrica
0276          ref = Vector((1.0, 0.0, 0.0))
0277          if abs(norm.dot(ref)) > 0.9:
0278              ref = Vector((0.0, 1.0, 0.0))
0279          u_dir = norm.cross(ref).normalized()
0280          v_dir = norm.cross(u_dir).normalized()
0281  
0282          sample_offsets = [Vector((0.0, 0.0, 0.0))]
0283          if cavity_radius_bu > 1e-5:
0284              r = cavity_radius_bu * 0.95
0285              sample_offsets.extend([
0286                  u_dir * r,
0287                  -u_dir * r,
0288                  v_dir * r,
0289                  -v_dir * r,
0290              ])
0291  
0292          min_found_depth = 1e9
0293  
0294          for pos in positions:
0295              for offset in sample_offsets:
0296                  sample_p = pos + offset
0297                  ray_start = sample_p + norm * 1e-4
0298                  hit_loc, hit_norm, hit_idx, hit_dist = bvh.ray_cast(ray_start, norm)
0299                  if hit_loc is None:
0300                      # Raio sem interseção: não há parede receptora na direção de inserção
0301                      bm.free()
0302                      return False, 0.0
0303  
0304                  avail_depth = (hit_loc - sample_p).length
0305                  if avail_depth < min_found_depth:
0306                      min_found_depth = avail_depth
0307  
0308                  if avail_depth < (required_depth_bu + min_wall_bu):
0309                      bm.free()
0310                      return False, avail_depth
0311  
0312          bm.free()
0313          return True, min_found_depth if min_found_depth < 1e8 else 0.0
0314      finally:
0315          eval_obj.to_mesh_clear()
0316  
0317  
0318  

```

## Offset/chamfer de união — src/geometry_connectors.py:180–202

```python

0180        profundidade útil length + clearance_end, sem chanfro automático.
0181      - Separação entre centros dos semicírculos da cápsula: exatamente L - D em macho e cavidade.
0182      """
0183      bm = bmesh.new()
0184  
0185      eff_radius = (diameter / 2.0) + (clearance_side if is_cavity else 0.0)
0186      eff_length = length + (clearance_end if is_cavity else 0.0)
0187      eff_chamfer = 0.0 if is_cavity else min(chamfer, eff_length * 0.4, eff_radius * 0.7)
0188  
0189      # Tolerância proporcional de sobreposição na base para garantir operação booleana não coplanar
0190      base_offset = min(eff_length * 0.05, eff_radius * 0.1)
0191      z_min = -base_offset
0192      z_max = eff_length
0193      z_shoulder = z_max - eff_chamfer
0194  
0195      base_verts = []
0196      shoulder_verts = []
0197      tip_verts = []
0198  
0199      if connector_type == 'CAPSULE':
0200          # Chave tipo cápsula / estádio
0201          w = eff_radius
0202          eff_cap_len = max(diameter, capsule_length) if capsule_length > 0.0 else (diameter * 2.4)

```

## Saneamento antes dos encaixes — src/operators.py:1854–1881

```python

1854  
1855              # Validação geométrica nos candidatos
1856              check_cand_manifold = getattr(settings, "diag_is_manifold", True)
1857              bm_a_chk = bmesh.new()
1858              bm_a_chk.from_mesh(candidate_mesh_a)
1859              ok_a, msg_a, _ = validate_printable_mesh(bm_a_chk, part_name="Parte A", unit_scale=unit_scale, check_manifold=check_cand_manifold)
1860              if not ok_a and "comprimento nulo" in msg_a:
1861                  from .diagnostic import sanitize_mesh_micro_degeneracies
1862                  if sanitize_mesh_micro_degeneracies(bm_a_chk, scale_to_mm=unit_scale):
1863                      ok_a, msg_a, _ = validate_printable_mesh(bm_a_chk, part_name="Parte A", unit_scale=unit_scale, check_manifold=check_cand_manifold)
1864                      if ok_a:
1865                          bm_a_chk.to_mesh(candidate_mesh_a)
1866              bm_a_chk.free()
1867  
1868              bm_b_chk = bmesh.new()
1869              bm_b_chk.from_mesh(candidate_mesh_b)
1870              ok_b, msg_b, _ = validate_printable_mesh(bm_b_chk, part_name="Parte B", unit_scale=unit_scale, check_manifold=check_cand_manifold)
1871              if not ok_b and "comprimento nulo" in msg_b:
1872                  from .diagnostic import sanitize_mesh_micro_degeneracies
1873                  if sanitize_mesh_micro_degeneracies(bm_b_chk, scale_to_mm=unit_scale):
1874                      ok_b, msg_b, _ = validate_printable_mesh(bm_b_chk, part_name="Parte B", unit_scale=unit_scale, check_manifold=check_cand_manifold)
1875                      if ok_b:
1876                          bm_b_chk.to_mesh(candidate_mesh_b)
1877              bm_b_chk.free()
1878  
1879              if not ok_a or not ok_b:
1880                  err_msg = msg_a if not ok_a else msg_b
1881                  raise RuntimeError(f"Validação da geometria cortada falhou: {err_msg}")

```

## Material excluído do pipeline encaixes — src/operators.py:1889–1928

```python

1889              # Aplica encaixes (macho e cavidade) se ativados na sessão
1890              if settings.connector_enabled:
1891                  if settings.split_mode in ('SOLID', 'MATERIAL'):
1892                      self.report({'INFO'}, "Encaixes automáticos não são suportados no modo Cortador Sólido / Material.")
1893                  else:
1894                      if settings.split_mode == 'LOOP':
1895                          norm_a = plane_normal
1896                      else:
1897                          norm_a = -plane_normal if settings.invert_sides else plane_normal
1898  
1899                      if settings.connector_male_part == 'A':
1900                          male_obj = candidate_obj_a
1901                          female_obj = candidate_obj_b
1902                          norm = norm_a
1903                      else:
1904                          male_obj = candidate_obj_b
1905                          female_obj = candidate_obj_a
1906                          norm = -norm_a
1907  
1908                      layout = compute_connector_layout(
1909                          target_mesh=target.data,
1910                          matrix_world=target.matrix_world,
1911                          plane_origin=plane_origin,
1912                          plane_normal=plane_normal,
1913                          distribution=settings.connector_distribution,
1914                          edge_margin_mm=settings.connector_edge_margin_mm,
1915                          unit_scale=unit_scale,
1916                          diameter_mm=settings.connector_diameter_mm,
1917                          clearance_per_side_mm=settings.clearance_per_side_mm,
1918                          interface=report.get("interface"),
1919                          connector_type=settings.connector_type,
1920                          capsule_length_mm=settings.connector_capsule_length_mm,
1921                          adjust_to_valid_area=getattr(settings, "adjust_to_valid_area", False),
1922                      )
1923                      positions = layout["positions"]
1924                      major_axis = layout["major_axis"]
1925                      max_safe_lateral_mm = layout["max_safe_lateral_mm"]
1926                      settings.connector_max_safe_lateral_mm = max_safe_lateral_mm
1927  
1928                      cap_len = layout.get("adjusted_capsule_length_mm", settings.connector_capsule_length_mm)

```

## Validação após encaixes — src/operators.py:1956–1971

```python

1956  
1957              # Re-avalia diagnósticos atualizados e validação final nos candidatos
1958              metrics_final = {}
1959              for side, p_obj in (("A", candidate_obj_a), ("B", candidate_obj_b)):
1960                  bm_res = bmesh.new()
1961                  bm_res.from_mesh(p_obj.data)
1962                  ok_res, msg_res, metrics = validate_printable_mesh(bm_res, part_name=f"Parte {side}", unit_scale=unit_scale, check_manifold=check_cand_manifold)
1963                  bm_res.free()
1964                  if not ok_res:
1965                      raise RuntimeError(f"Resultado inválido após encaixes ({msg_res}).")
1966                  metrics_final[side] = metrics
1967  
1968              # Pré-calcula métricas, limites e nova assinatura antes de alterar a cena (C22 / V23)
1969              sum_vol = metrics_final["A"]["volume_mm3"] + metrics_final["B"]["volume_mm3"]
1970              orig_vol = settings.diag_volume_mm3
1971              vol_diff = (abs(sum_vol - orig_vol) / orig_vol * 100.0) if orig_vol > 0 else 0.0

```

## Saneamento mutante sem cheque manifold interno — src/diagnostic.py:141–180

```python

0141  def sanitize_mesh_micro_degeneracies(bm: bmesh.types.BMesh, scale_to_mm: float = 1000.0) -> bool:
0142      """Saneamento restrito e transacional de micro-arestas causadas por arredondamento no solver booleano (DEV-01 / DEV-02).
0143      
0144      Solda vértices separados por distâncias sub-micrométricas (< 0.1 µm), preservando a integridade manifold.
0145      Retorna True se houve saneamento bem-sucedido e a malha permaneceu manifold.
0146      """
0147      eps_bu = 1e-4 / max(1e-6, scale_to_mm)
0148      bm.edges.ensure_lookup_table()
0149      micro_edges = [e for e in bm.edges if e.calc_length() < eps_bu]
0150      if not micro_edges:
0151          return False
0152      
0153      targetmap = {}
0154      for e in micro_edges:
0155          if e.is_valid and len(e.verts) == 2:
0156              v0, v1 = e.verts[0], e.verts[1]
0157              if v1 not in targetmap.values():
0158                  targetmap[v1] = v0
0159      
0160      if not targetmap:
0161          return False
0162      
0163      try:
0164          bmesh.ops.weld_verts(bm, targetmap=targetmap)
0165          bm.edges.ensure_lookup_table()
0166          bm.faces.ensure_lookup_table()
0167          bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
0168          return True
0169      except Exception:
0170          return False
0171  
0172  
0173  def validate_bmesh_mesh_geometry(bm: bmesh.types.BMesh, scale_to_mm: float = 1000.0) -> Dict[str, Any]:
0174      """Valida a geometria de um BMesh medindo integridade, áreas nulas e degenerações (INV-010 / DEV-01)."""
0175      bm.verts.ensure_lookup_table()
0176      bm.edges.ensure_lookup_table()
0177      bm.faces.ensure_lookup_table()
0178  
0179      # 1. Arestas de comprimento nulo calibradas pela escala física (< 0.1 µm)
0180      eps_length_bu = 1e-4 / max(1e-6, scale_to_mm)

```

## Tolerâncias agora em mm — src/diagnostic.py:181–202

```python

0181      null_edges = [e.index for e in bm.edges if e.calc_length() < eps_length_bu]
0182  
0183      # 2. Faces de área nula / colineares / com vértices coincidentes
0184      min_face_area_mm2 = 1e-6
0185      eps_dist_bu_sq = (eps_length_bu) ** 2
0186      degenerate_faces = []
0187      for f in bm.faces:
0188          area_mm2 = f.calc_area() * (scale_to_mm ** 2)
0189          if area_mm2 < min_face_area_mm2:
0190              degenerate_faces.append(f.index)
0191          else:
0192              coords = [v.co for v in f.verts]
0193              has_coincident = False
0194              for i in range(len(coords)):
0195                  for j in range(i + 1, len(coords)):
0196                      if (coords[i] - coords[j]).length_squared < eps_dist_bu_sq:
0197                          has_coincident = True
0198                          break
0199                  if has_coincident:
0200                      break
0201              if has_coincident:
0202                  degenerate_faces.append(f.index)

```

## Seleção exclusiva e aviso proporcional — src/operators.py:2342–2366

```python

2342          # Garante Object Mode para evitar estados de seleção mistos (DEV-08)
2343          try:
2344              if context.mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
2345                  bpy.ops.object.mode_set(mode='OBJECT')
2346          except Exception:
2347              pass
2348  
2349          # Seleciona EXCLUSIVAMENTE a peça extraída por papel semântico (DEV-08)
2350          extracted_obj = obj_b if getattr(settings, "invert_sides", False) else obj_a
2351          try:
2352              bpy.ops.object.select_all(action='DESELECT')
2353              extracted_obj.select_set(True)
2354              context.view_layer.objects.active = extracted_obj
2355          except Exception:
2356              pass
2357  
2358          # Informa e alerta se a edição proporcional estiver ativa (DEV-08)
2359          prop_warning = ""
2360          if getattr(context.scene.tool_settings, "use_proportional_edit_objects", False):
2361              prop_warning = " Aviso: A Edição Proporcional de Objetos está ativa. Desative-a (tecla 'O') para mover a peça sem arrastar o corpo remanescente."
2362              self.report({'WARNING'}, prop_warning.strip())
2363  
2364          settings.active_operation_id = settings.session_id
2365  
2366          # Oculta guias de corte

```