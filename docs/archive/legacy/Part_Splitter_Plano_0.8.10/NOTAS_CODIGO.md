# Notas e trechos reais da base 0.8.9

Trechos próprios do projeto, extraídos automaticamente do ZIP anexado. Linhas são referências da base, não da futura implementação. Nenhum trecho abaixo é correção pronta.

## Índice de símbolos

- `src/operators.py:168–207` — `validate_printable_mesh`

- `src/operators.py:1181–1301` — `CHEST_OT_splitter_align_solid_cutter`

- `src/operators.py:1305–1394` — `CHEST_OT_splitter_create_cutter_from_selection`

- `src/operators.py:1397–1478` — `CHEST_OT_splitter_create_corner_box_cutter`

- `src/geometry_loop.py:358–623` — `slice_mesh_by_loop`

- `src/geometry_loop.py:626–794` — `analyze_loop_region`

- `src/geometry_loop.py:808–978` — `triangulate_polygon_2d`

- `src/geometry_loop.py:981–1039` — `create_loop_prism_cutter`

- `src/geometry_loop.py:1042–1207` — `slice_mesh_by_loop_extrude`

- `src/geometry_material.py:347–472` — `create_material_patch_prism_cutter`

- `src/properties.py:57–92` — `_on_solid_dim_update`

- `src/diagnostic.py:141–184` — `validate_bmesh_mesh_geometry`

## Validação: src/operators.py:168–207

```python

0168  def validate_printable_mesh(
0169      bm: bmesh.types.BMesh,
0170      part_name: str = "Peça",
0171      unit_scale: float = 1000.0,
0172      check_manifold: bool = True,
0173      min_volume_mm3: float = 1e-3,
0174  ) -> Tuple[bool, str, Dict[str, Any]]:
0175      """Valida se uma malha atende aos critérios mínimos de solidez para impressão 3D."""
0176      bm.verts.ensure_lookup_table()
0177      bm.edges.ensure_lookup_table()
0178      bm.faces.ensure_lookup_table()
0179  
0180      verts_count = len(bm.verts)
0181      faces_count = len(bm.faces)
0182  
0183      if verts_count < 4 or faces_count < 4:
0184          return False, f"{part_name}: contagem insuficiente de elementos ({faces_count} faces, {verts_count} vértices).", {}
0185  
0186      for v in bm.verts:
0187          if not (math.isfinite(v.co.x) and math.isfinite(v.co.y) and math.isfinite(v.co.z)):
0188              return False, f"{part_name}: contém coordenadas infinitas ou NaN.", {}
0189  
0190      from .diagnostic import validate_bmesh_mesh_geometry
0191      geom_check = validate_bmesh_mesh_geometry(bm, scale_to_mm=unit_scale)
0192  
0193      if geom_check["null_edges"]:
0194          return False, f"{part_name}: possui {len(geom_check['null_edges'])} aresta(s) com comprimento nulo (degeneração).", {}
0195  
0196      if geom_check["degenerate_faces"]:
0197          return False, f"{part_name}: possui {len(geom_check['degenerate_faces'])} face(s) com área nula ou vértices colineares/coincidentes.", {}
0198  
0199      vol_mm3 = abs(geom_check["volume_mm3"])
0200      if vol_mm3 < min_volume_mm3:
0201          return False, f"{part_name}: volume nulo ou desprezível ({vol_mm3:.4f} mm³).", {}
0202  
0203      if check_manifold and not geom_check["is_manifold"]:
0204          return False, f"{part_name}: possui {len(geom_check['non_manifold_edges'])} aresta(s) não-manifold/abertas (não é um sólido fechado).", {}
0205  
0206      metrics = evaluate_bmesh_metrics(bm, unit_scale=unit_scale)
0207      return True, "OK", metrics

```

## Alinhamento atual: src/operators.py:1183–1302

```python

1183      bl_idname = "chest.splitter_align_solid_cutter"
1184      bl_label = "Alinhar Cortador Sólido"
1185      bl_options = {'REGISTER', 'UNDO'}
1186  
1187      align_mode: bpy.props.EnumProperty(
1188          name="Alinhamento",
1189          items=[
1190              ('ACTIVE_FACE', "Face Ativa", "Alinha à normal e posição da face selecionada no alvo"),
1191              ('TARGET_AXES', "Eixos do Alvo", "Alinha à orientação ortonormal do objeto alvo"),
1192              ('CURSOR_3D', "Cursor 3D", "Alinha à posição e orientação do Cursor 3D"),
1193              ('AXIS_X', "Eixo X", "Alinha a profundidade ao eixo global X"),
1194              ('AXIS_Y', "Eixo Y", "Alinha a profundidade ao eixo global Y"),
1195              ('AXIS_Z', "Eixo Z", "Alinha a profundidade ao eixo global Z"),
1196              ('SELECTION_CENTER', "Centro da Seleção", "Move para o centro dos elementos selecionados"),
1197          ],
1198          default='ACTIVE_FACE',
1199      )
1200  
1201      anchor: bpy.props.EnumProperty(
1202          name="Ponto de Apoio",
1203          items=[
1204              ('CENTER', "Centro", "Posiciona o centro do cortador no ponto de referência"),
1205              ('SUPPORT_FACE', "Face de Apoio", "Encosta a face de apoio do cortador na superfície"),
1206          ],
1207          default='SUPPORT_FACE',
1208      )
1209  
1210      invert_direction: bpy.props.BoolProperty(
1211          name="Inverter Direção",
1212          description="Inverte o vetor de profundidade de penetração no alvo",
1213          default=False,
1214      )
1215  
1216      @classmethod
1217      def poll(cls, context):
1218          settings = context.scene.chest_splitter
1219          return (settings.solid_cutter_object is not None and
1220                  settings.solid_cutter_object.name in bpy.data.objects and
1221                  settings.target_object is not None)
1222  
1223      def execute(self, context):
1224          settings = context.scene.chest_splitter
1225          cutter = settings.solid_cutter_object
1226          target = settings.target_object
1227  
1228          # Preserva escala/dimensões locais existentes
1229          curr_scale = cutter.scale.copy()
1230          if curr_scale.x <= 0 or curr_scale.y <= 0 or curr_scale.z <= 0:
1231              curr_scale = Vector((abs(curr_scale.x) or 1.0, abs(curr_scale.y) or 1.0, abs(curr_scale.z) or 1.0))
1232  
1233          ref_pos = target.matrix_world.translation.copy()
1234          normal = Vector((0.0, 0.0, 1.0))
1235  
1236          if self.align_mode == 'ACTIVE_FACE':
1237              found = False
1238              if target.mode == 'EDIT':
1239                  bm = bmesh.from_edit_mesh(target.data)
1240                  f = bm.faces.active or next((f for f in bm.faces if f.select), None)
1241                  if f:
1242                      norm_mat = target.matrix_world.to_3x3().inverted().transposed()
1243                      normal = (norm_mat @ f.normal).normalized()
1244                      ref_pos = target.matrix_world @ f.calc_center_median()
1245                      found = True
1246              else:
1247                  bm = bmesh.new()
1248                  bm.from_mesh(target.data)
1249                  f = next((f for f in bm.faces if f.select), None) or (bm.faces[0] if len(bm.faces) > 0 else None)
1250                  if f:
1251                      norm_mat = target.matrix_world.to_3x3().inverted().transposed()
1252                      normal = (norm_mat @ f.normal).normalized()
1253                      ref_pos = target.matrix_world @ f.calc_center_median()
1254                      found = True
1255                  bm.free()
1256              if not found:
1257                  self.report({'WARNING'}, "Nenhuma face ativa ou selecionada encontrada no alvo.")
1258                  return {'CANCELLED'}
1259  
1260          elif self.align_mode == 'TARGET_AXES':
1261              ref_pos = target.matrix_world.translation.copy()
1262              t_rot = target.matrix_world.to_3x3().to_quaternion().to_matrix()
1263              normal = (t_rot @ Vector((0.0, 0.0, 1.0))).normalized()
1264  
1265          elif self.align_mode == 'CURSOR_3D':
1266              ref_pos = context.scene.cursor.location.copy()
1267              c_rot = context.scene.cursor.rotation_euler.to_matrix()
1268              normal = (c_rot @ Vector((0.0, 0.0, 1.0))).normalized()
1269  
1270          elif self.align_mode == 'AXIS_X':
1271              normal = Vector((1.0, 0.0, 0.0))
1272          elif self.align_mode == 'AXIS_Y':
1273              normal = Vector((0.0, 1.0, 0.0))
1274          elif self.align_mode == 'AXIS_Z':
1275              normal = Vector((0.0, 0.0, 1.0))
1276          elif self.align_mode == 'SELECTION_CENTER':
1277              if context.active_object and context.active_object != cutter:
1278                  ref_pos = context.active_object.matrix_world.translation.copy()
1279  
1280          if self.invert_direction:
1281              normal = -normal
1282  
1283          # Constrói base ortonormal determinística com Z acompanhando normal (profundidade)
1284          z_axis = normal.normalized()
1285          up = Vector((0.0, 1.0, 0.0)) if abs(z_axis.dot(Vector((0.0, 0.0, 1.0)))) > 0.9 else Vector((0.0, 0.0, 1.0))
1286          x_axis = up.cross(z_axis).normalized()
1287          y_axis = z_axis.cross(x_axis).normalized()
1288          rot_mat = Matrix((x_axis, y_axis, z_axis)).transposed()
1289  
1290          dz_half = (cutter.dimensions.z / 2.0)
1291          final_pos = ref_pos.copy()
1292          if self.anchor == 'SUPPORT_FACE':
1293              final_pos = ref_pos + (z_axis * dz_half)
1294  
1295          cutter.matrix_world = Matrix.LocRotScale(final_pos, rot_mat.to_quaternion(), curr_scale)
1296          context.view_layer.update()
1297  
1298          if settings.session_status == 'PREVIEW_VALID':
1299              settings.session_status = 'PREVIEW_STALE'
1300          self.report({'INFO'}, f"Cortador alinhado ({self.align_mode}, {self.anchor}).")
1301          return {'FINISHED'}
1302  

```

## Criar cortador da seleção: src/operators.py:1305–1394

```python

1305  class CHEST_OT_splitter_create_cutter_from_selection(bpy.types.Operator):
1306      """Cria um cortador sólido prismático a partir do loop capturado ou região de material planar (SOL-05)"""
1307      bl_idname = "chest.splitter_create_cutter_from_selection"
1308      bl_label = "Criar Cortador desta Seleção"
1309      bl_options = {'REGISTER', 'UNDO'}
1310  
1311      depth_mm: bpy.props.FloatProperty(
1312          name="Profundidade (mm)",
1313          default=20.0,
1314          min=0.1,
1315          precision=2,
1316      )
1317  
1318      outer_extension_mm: bpy.props.FloatProperty(
1319          name="Extensão Exterior (mm)",
1320          default=1.0,
1321          min=0.0,
1322          precision=2,
1323      )
1324  
1325      invert_direction: bpy.props.BoolProperty(
1326          name="Inverter Direção",
1327          default=False,
1328      )
1329  
1330      @classmethod
1331      def poll(cls, context):
1332          settings = context.scene.chest_splitter
1333          return (settings.target_object is not None and
1334                  (settings.loop_is_captured or settings.split_mode == 'MATERIAL'))
1335  
1336      def execute(self, context):
1337          settings = context.scene.chest_splitter
1338          target = settings.target_object
1339          unit_scale = get_scene_scale_to_mm(context.scene)
1340          depth_bu = self.depth_mm / unit_scale
1341          outer_bu = self.outer_extension_mm / unit_scale
1342  
1343          col = get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
1344          prism_name = f"Prism_Cutter_{target.name}"
1345  
1346          if settings.split_mode == 'MATERIAL':
1347              from .geometry_material import create_material_patch_prism_cutter
1348              mat_idx = settings.material_split_index
1349              reg_idx = settings.material_region_index
1350              try:
1351                  mesh_data = create_material_patch_prism_cutter(
1352                      target,
1353                      target.data,
1354                      mat_idx,
1355                      reg_idx,
1356                      depth_bu=depth_bu,
1357                      outer_extension_bu=outer_bu,
1358                      lateral_offset_bu=0.0,
1359                      unit_scale=unit_scale,
1360                  )
1361              except Exception as e:
1362                  self.report({'ERROR'}, f"Não foi possível gerar prisma de material: {str(e)}")
1363                  return {'CANCELLED'}
1364          else:
1365              if not settings.loop_is_planar:
1366                  self.report({'ERROR'}, "A seleção de contorno não é planar (desvio > 0.15 mm). Selecione um contorno planar.")
1367                  return {'CANCELLED'}
1368              from .geometry_loop import create_loop_prism_cutter
1369              try:
1370                  mesh_data = create_loop_prism_cutter(
1371                      target,
1372                      depth_bu=depth_bu,
1373                      outer_extension_bu=outer_bu,
1374                      unit_scale=unit_scale,
1375                  )
1376              except Exception as e:
1377                  self.report({'ERROR'}, f"Não foi possível gerar prisma de contorno: {str(e)}")
1378                  return {'CANCELLED'}
1379  
1380          prism_obj = bpy.data.objects.new(prism_name, mesh_data)
1381          prism_obj.matrix_world = target.matrix_world.copy()
1382          prism_obj.display_type = 'WIRE'
1383          prism_obj.show_in_front = True
1384          col.objects.link(prism_obj)
1385  
1386          settings.solid_source = 'EXISTING'
1387          settings.solid_cutter_object = prism_obj
1388          for o in context.selected_objects:
1389              o.select_set(False)
1390          prism_obj.select_set(True)
1391          context.view_layer.objects.active = prism_obj
1392  
1393          self.report({'INFO'}, f"Cortador prismático editável criado: '{prism_obj.name}'.")
1394          return {'FINISHED'}

```

## Caixa de quina: src/operators.py:1397–1478

```python

1397  class CHEST_OT_splitter_create_corner_box_cutter(bpy.types.Operator):
1398      """Propõe um cortador em caixa regular para quinas ortogonais (SOL-06 / INV-009)"""
1399      bl_idname = "chest.splitter_create_corner_box_cutter"
1400      bl_label = "Caixa para Quina Regular"
1401      bl_options = {'REGISTER', 'UNDO'}
1402  
1403      size_x_mm: bpy.props.FloatProperty(name="Largura (X mm)", default=20.0, min=1.0)
1404      size_y_mm: bpy.props.FloatProperty(name="Altura (Y mm)", default=20.0, min=1.0)
1405      size_z_mm: bpy.props.FloatProperty(name="Profundidade (Z mm)", default=20.0, min=1.0)
1406  
1407      @classmethod
1408      def poll(cls, context):
1409          settings = context.scene.chest_splitter
1410          return settings.target_object is not None
1411  
1412      def execute(self, context):
1413          settings = context.scene.chest_splitter
1414          target = settings.target_object
1415          unit_scale = get_scene_scale_to_mm(context.scene)
1416  
1417          bm = bmesh.new()
1418          if target.mode == 'EDIT':
1419              bm_edit = bmesh.from_edit_mesh(target.data)
1420              bm = bm_edit.copy()
1421          else:
1422              bm.from_mesh(target.data)
1423  
1424          sel_faces = [f for f in bm.faces if f.select]
1425          if len(sel_faces) != 3:
1426              bm.free()
1427              self.report({'WARNING'}, "Selecione exatamente 3 faces que formam a quina regular.")
1428              return {'CANCELLED'}
1429  
1430          norm_mat = target.matrix_world.to_3x3().inverted().transposed()
1431          world_normals = [(norm_mat @ f.normal).normalized() for f in sel_faces]
1432          for i in range(3):
1433              for j in range(i + 1, 3):
1434                  dot = abs(world_normals[i].dot(world_normals[j]))
1435                  if dot > 0.35:
1436                      bm.free()
1437                      self.report({'ERROR'}, "Quina não ortogonal detectada (ângulo fora de 90°). A geração requer 3 faces ortogonais.")
1438                      return {'CANCELLED'}
1439  
1440          shared_verts = set(sel_faces[0].verts).intersection(sel_faces[1].verts).intersection(sel_faces[2].verts)
1441          if not shared_verts:
1442              corner_pt = sum([target.matrix_world @ f.calc_center_median() for f in sel_faces], Vector()) / 3.0
1443          else:
1444              v_corner = next(iter(shared_verts))
1445              corner_pt = target.matrix_world @ v_corner.co
1446          bm.free()
1447  
1448          n1, n2, n3 = world_normals[0], world_normals[1], world_normals[2]
1449          if n1.cross(n2).dot(n3) < 0:
1450              n3 = -n3
1451          rot_mat = Matrix((n1, n2, n3)).transposed()
1452  
1453          dx = self.size_x_mm / unit_scale
1454          dy = self.size_y_mm / unit_scale
1455          dz = self.size_z_mm / unit_scale
1456  
1457          col = get_or_create_collection(context.scene, COLLECTION_GUIDES_NAME)
1458          mesh_data = create_primitive_cutter_mesh(
1459              name=f"{SOLID_CUTTER_NAME}_CornerBox_Mesh",
1460              primitive_type='BOX',
1461              dims=Vector((dx, dy, dz)),
1462          )
1463          box_obj = bpy.data.objects.new(f"{SOLID_CUTTER_NAME}_CornerBox", mesh_data)
1464          center_offset = rot_mat @ Vector((-dx / 2.0, -dy / 2.0, -dz / 2.0))
1465          box_obj.matrix_world = Matrix.LocRotScale(corner_pt + center_offset, rot_mat.to_quaternion(), Vector((1, 1, 1)))
1466          box_obj.display_type = 'WIRE'
1467          box_obj.show_in_front = True
1468          col.objects.link(box_obj)
1469  
1470          settings.solid_source = 'EXISTING'
1471          settings.solid_cutter_object = box_obj
1472          for o in context.selected_objects:
1473              o.select_set(False)
1474          box_obj.select_set(True)
1475          context.view_layer.objects.active = box_obj
1476  
1477          self.report({'INFO'}, f"Caixa para quina criada com sucesso ({self.size_x_mm:.1f}x{self.size_y_mm:.1f}x{self.size_z_mm:.1f} mm).")
1478          return {'FINISHED'}

```

## Escolha DETACH/EXTRUDE: src/operators.py:1610–1648

```python

1610                      slice_mesh_by_loop,
1611                      slice_mesh_by_loop_extrude,
1612                      analyze_loop_region,
1613                      get_topology_signature,
1614                      validate_capture,
1615                  )
1616                  is_valid, reason = validate_capture(target, settings, context)
1617                  if not is_valid:
1618                      raise RuntimeError(f"A malha mudou ou o contorno é inválido ({reason}). Capture o contorno novamente.")
1619                  if settings.loop_seed_face_index < 0:
1620                      raise RuntimeError("Nenhuma região definida.")
1621                  if target.data and settings.loop_seed_face_index >= len(target.data.polygons):
1622                      raise RuntimeError("A face semente não é mais válida para a topologia atual.")
1623  
1624                  indices = [int(i) for i in settings.loop_vertex_indices.split(',') if i.strip()]
1625  
1626                  behavior = settings.loop_behavior
1627                  if behavior == 'AUTO':
1628                      analysis = analyze_loop_region(target, indices, settings.loop_seed_face_index, context.scene)
1629                      effective_mode = analysis["detected_mode"]
1630                      settings.loop_detected_mode = effective_mode
1631                      settings.loop_auto_reason = analysis["reason"]
1632                  else:
1633                      effective_mode = behavior
1634  
1635                  if effective_mode == 'EXTRUDE':
1636                      loop_res = slice_mesh_by_loop_extrude(
1637                          target,
1638                          target.name,
1639                          indices,
1640                          settings.loop_seed_face_index,
1641                          depth_mm=settings.loop_extrude_depth_mm,
1642                          through_cut=settings.loop_through_cut,
1643                          scene=context.scene,
1644                      )
1645                  else:
1646                      loop_res = slice_mesh_by_loop(target, target.name, indices, settings.loop_seed_face_index, context.scene)
1647  
1648                  bm_a, bm_b = loop_res[0], loop_res[1]

```

## Validação dos candidatos: src/operators.py:1738–1765

```python

1738  
1739              # Limpa malha avaliada temporária
1740              if eval_mesh:
1741                  try:
1742                      eval_obj.to_mesh_clear()
1743                  except Exception:
1744                      pass
1745                  eval_mesh = None
1746  
1747              # Validação geométrica nos candidatos
1748              check_cand_manifold = getattr(settings, "diag_is_manifold", True)
1749              bm_a_chk = bmesh.new()
1750              bm_a_chk.from_mesh(candidate_mesh_a)
1751              ok_a, msg_a, _ = validate_printable_mesh(bm_a_chk, part_name="Parte A", unit_scale=unit_scale, check_manifold=check_cand_manifold)
1752              bm_a_chk.free()
1753  
1754              bm_b_chk = bmesh.new()
1755              bm_b_chk.from_mesh(candidate_mesh_b)
1756              ok_b, msg_b, _ = validate_printable_mesh(bm_b_chk, part_name="Parte B", unit_scale=unit_scale, check_manifold=check_cand_manifold)
1757              bm_b_chk.free()
1758  
1759              if not ok_a or not ok_b:
1760                  err_msg = msg_a if not ok_a else msg_b
1761                  raise RuntimeError(f"Validação da geometria cortada falhou: {err_msg}")
1762  
1763              # Cria objetos candidatos isolados na coleção de prévias para operações booleanas
1764              candidate_obj_a = bpy.data.objects.new(cand_obj_name_a, candidate_mesh_a)
1765              candidate_obj_b = bpy.data.objects.new(cand_obj_name_b, candidate_mesh_b)

```

## Confirmação e seleção: src/operators.py:2169–2232

```python

2169              # check_manifold exigido se o alvo original era manifold
2170              check_solid = getattr(settings, "diag_is_manifold", True)
2171              is_valid, msg, _ = validate_printable_mesh(bm_part, part_name=part_obj.name, unit_scale=unit_scale, check_manifold=check_solid)
2172              bm_part.free()
2173              if eval_mesh != part_obj.data:
2174                  eval_obj.to_mesh_clear()
2175                  
2176              if not is_valid:
2177                  settings.session_status = 'PREVIEW_STALE'
2178                  settings.last_status = f"Erro de integridade na peça gerada: {msg}"
2179                  settings.last_status_level = 'ERROR'
2180                  self.report({'ERROR'}, settings.last_status)
2181                  return {'CANCELLED'}
2182  
2183          base_name = target.name.replace(WORK_COPY_SUFFIX, "")
2184          final_name_a = f"{base_name}{PART_A_SUFFIX}"
2185          final_name_b = f"{base_name}{PART_B_SUFFIX}"
2186  
2187          # Reseta localizações para posição montada original (INV-004)
2188          obj_a.location = Vector(obj_a.get("chest_assembled_loc", (0.0, 0.0, 0.0)))
2189          obj_b.location = Vector(obj_b.get("chest_assembled_loc", (0.0, 0.0, 0.0)))
2190  
2191          # Renomeia objetos e malhas
2192          obj_a.name = final_name_a
2193          obj_a.data.name = f"{final_name_a}_Mesh"
2194          obj_b.name = final_name_b
2195          obj_b.data.name = f"{final_name_b}_Mesh"
2196  
2197          # Adiciona metadados rastreáveis e isolamento por sessão (Seção 4)
2198          obj_a["chest_session_id"] = settings.session_id
2199          obj_a["chest_operation_id"] = settings.session_id
2200          obj_a["chest_role"] = ROLE_COMMITTED_PART
2201          obj_a["chest_splitter_session_id"] = settings.session_id
2202          obj_a["chest_splitter_part"] = "A"
2203  
2204          obj_b["chest_session_id"] = settings.session_id
2205          obj_b["chest_operation_id"] = settings.session_id
2206          obj_b["chest_role"] = ROLE_COMMITTED_PART
2207          obj_b["chest_splitter_session_id"] = settings.session_id
2208          obj_b["chest_splitter_part"] = "B"
2209  
2210          op_rec = find_operation_record(context.scene, settings.session_id)
2211          if op_rec:
2212              op_rec.status = 'COMMITTED'
2213              record_created_object(op_rec, obj_a, ROLE_COMMITTED_PART)
2214              record_created_object(op_rec, obj_b, ROLE_COMMITTED_PART)
2215  
2216          # Transfere para a coleção de partes finais
2217          preview_col.objects.unlink(obj_a)
2218          preview_col.objects.unlink(obj_b)
2219          parts_col.objects.link(obj_a)
2220          parts_col.objects.link(obj_b)
2221  
2222          # Seleciona as peças finais criadas e ativa a peça gerada
2223          try:
2224              bpy.ops.object.select_all(action='DESELECT')
2225              obj_a.select_set(True)
2226              obj_b.select_set(True)
2227              context.view_layer.objects.active = obj_a
2228          except Exception:
2229              pass
2230  
2231          settings.active_operation_id = settings.session_id
2232  

```

## Tolerâncias: src/diagnostic.py:141–182

```python

0141  def validate_bmesh_mesh_geometry(bm: bmesh.types.BMesh, scale_to_mm: float = 1000.0) -> Dict[str, Any]:
0142      """Valida a geometria de um BMesh medindo integridade, áreas nulas e degenerações."""
0143      bm.verts.ensure_lookup_table()
0144      bm.edges.ensure_lookup_table()
0145      bm.faces.ensure_lookup_table()
0146  
0147      # 1. Arestas de comprimento nulo
0148      null_edges = [e.index for e in bm.edges if e.calc_length() < 1e-7]
0149  
0150      # 2. Faces de área nula / colineares / com vértices coincidentes
0151      min_face_area_mm2 = 1e-6
0152      degenerate_faces = []
0153      for f in bm.faces:
0154          area_mm2 = f.calc_area() * (scale_to_mm ** 2)
0155          if area_mm2 < min_face_area_mm2:
0156              degenerate_faces.append(f.index)
0157          else:
0158              coords = [v.co for v in f.verts]
0159              has_coincident = False
0160              for i in range(len(coords)):
0161                  for j in range(i + 1, len(coords)):
0162                      if (coords[i] - coords[j]).length_squared < 1e-12:
0163                          has_coincident = True
0164                          break
0165                  if has_coincident:
0166                      break
0167              if has_coincident:
0168                  degenerate_faces.append(f.index)
0169  
0170      # 3. Arestas não-manifold
0171      non_manifold_edges = [e.index for e in bm.edges if not e.is_manifold]
0172  
0173      # 4. Volume orientado
0174      vol_bu = bm.calc_volume(signed=True)
0175      vol_mm3 = vol_bu * (scale_to_mm ** 3)
0176  
0177      return {
0178          "is_valid": len(null_edges) == 0 and len(degenerate_faces) == 0,
0179          "null_edges": null_edges,
0180          "degenerate_faces": degenerate_faces,
0181          "non_manifold_edges": non_manifold_edges,
0182          "is_manifold": len(non_manifold_edges) == 0,

```

## Redimensionamento: src/properties.py:57–99

```python

0057  def _on_solid_dim_update(self, context):
0058      """Atualiza as dimensões físicas locais do cortador em mm sem deriva ou recursão (SOL-03)."""
0059      global _updating_solid_dims
0060      if _updating_solid_dims:
0061          return
0062      cutter = self.solid_cutter_object
0063      if not cutter or cutter.type != 'MESH' or not cutter.data:
0064          return
0065      try:
0066          from .diagnostic import get_scene_scale_to_mm
0067          import bmesh
0068          unit_scale = get_scene_scale_to_mm(context.scene if context else None)
0069          bm = bmesh.new()
0070          bm.from_mesh(cutter.data)
0071          xs = [v.co.x for v in bm.verts]
0072          ys = [v.co.y for v in bm.verts]
0073          zs = [v.co.z for v in bm.verts]
0074          bm.free()
0075  
0076          span_x = (max(xs) - min(xs)) if xs else 1.0
0077          span_y = (max(ys) - min(ys)) if ys else 1.0
0078          span_z = (max(zs) - min(zs)) if zs else 1.0
0079  
0080          desired_x_bu = max(1e-4, self.solid_cutter_width_mm / unit_scale)
0081          desired_y_bu = max(1e-4, self.solid_cutter_height_mm / unit_scale)
0082          desired_z_bu = max(1e-4, self.solid_cutter_depth_mm / unit_scale)
0083  
0084          _updating_solid_dims = True
0085          cutter.scale.x = desired_x_bu / max(1e-6, span_x)
0086          cutter.scale.y = desired_y_bu / max(1e-6, span_y)
0087          cutter.scale.z = desired_z_bu / max(1e-6, span_z)
0088      except Exception:
0089          pass
0090      finally:
0091          _updating_solid_dims = False
0092      _on_param_change_mark_stale(self, context)
0093  
0094  
0095  def _on_cutter_object_update(self, context):
0096      """Atualiza diagnósticos imediatos ao alterar o objeto cortador."""
0097      if self.solid_cutter_object and self.solid_cutter_object.type == 'MESH':
0098          try:
0099              from .diagnostic import get_scene_scale_to_mm

```

## Triangulação: src/geometry_loop.py:808–978

```python

0808  def triangulate_polygon_2d(pts_2d: List[Vector]) -> List[Tuple[int, int, int]]:
0809      """Triangulação estrita por Ear Clipping para polígono simples 2D (B05 / L01-L06 / C01 / V01).
0810      
0811      Garante que 100% dos triângulos fiquem dentro do domínio do polígono,
0812      inclusive em formas côncavas (L, U, etc.), eliminando triângulos degenerados (área zero)
0813      mesmo em contornos com vértices colineares intermediários (12, 20, 40+ vértices).
0814      """
0815      n = len(pts_2d)
0816      if n < 3:
0817          return []
0818      
0819      pts_vec = [Vector((p[0], p[1])) if not hasattr(p, 'x') else Vector((p.x, p.y)) for p in pts_2d]
0820  
0821      # 1. Área orientada via Shoelace
0822      area = 0.0
0823      for i in range(n):
0824          j = (i + 1) % n
0825          area += pts_vec[i].x * pts_vec[j].y - pts_vec[j].x * pts_vec[i].y
0826      area *= 0.5
0827  
0828      if abs(area) < 1e-12:
0829          return []
0830  
0831      if n == 3:
0832          return [(0, 1, 2)] if area > 0 else [(0, 2, 1)]
0833  
0834      is_ccw = (area > 0.0)
0835      indices = list(range(n)) if is_ccw else list(reversed(range(n)))
0836      poly = [pts_vec[i] for i in indices]
0837  
0838      # 2. Identifica cantos essenciais (elimina colineares na mesma reta para o Ear Clipping)
0839      corners = []
0840      m_len = len(poly)
0841      for i in range(m_len):
0842          p_prev = poly[(i - 1) % m_len]
0843          p_curr = poly[i]
0844          p_next = poly[(i + 1) % m_len]
0845  
0846          v1 = p_curr - p_prev
0847          v2 = p_next - p_curr
0848          l1 = v1.length
0849          l2 = v2.length
0850  
0851          is_collinear = False
0852          if l1 > 1e-9 and l2 > 1e-9:
0853              cp = v1.x * v2.y - v1.y * v2.x
0854              dp = v1.x * v2.x + v1.y * v2.y
0855              if abs(cp) / (l1 * l2) < 1e-5 and dp > 0:
0856                  is_collinear = True
0857  
0858          if not is_collinear:
0859              corners.append(i)
0860  
0861      if len(corners) < 3:
0862          raise ValueError("Polígono degenerado: todos os pontos são colineares.")
0863  
0864      # 3. Mapeia intermediários colineares pertencentes a cada aresta de canto
0865      edge_intermediates = {}
0866      num_corners = len(corners)
0867      for c_i in range(num_corners):
0868          c_curr = corners[c_i]
0869          c_next = corners[(c_i + 1) % num_corners]
0870  
0871          inter = []
0872          if c_next > c_curr:
0873              for k in range(c_curr + 1, c_next):
0874                  inter.append(indices[k])
0875          else:
0876              for k in range(c_curr + 1, m_len):
0877                  inter.append(indices[k])
0878              for k in range(0, c_next):
0879                  inter.append(indices[k])
0880          edge_intermediates[(indices[c_curr], indices[c_next])] = inter
0881  
0882      # 4. Ear clipping no polígono simplificado de cantos essenciais
0883      corner_indices = [indices[c] for c in corners]
0884  
0885      def is_point_in_tri(pt: Vector, a: Vector, b: Vector, c: Vector) -> bool:
0886          v0 = c - a
0887          v1 = b - a
0888          v2 = pt - a
0889          dot00 = v0.dot(v0)
0890          dot01 = v0.dot(v1)
0891          dot02 = v0.dot(v2)
0892          dot11 = v1.dot(v1)
0893          dot12 = v1.dot(v2)
0894          denom = dot00 * dot11 - dot01 * dot01
0895          if abs(denom) < 1e-12:
0896              return False
0897          inv_denom = 1.0 / denom
0898          u = (dot11 * dot02 - dot01 * dot12) * inv_denom
0899          v = (dot00 * dot12 - dot01 * dot02) * inv_denom
0900          return (u > 1e-5) and (v > 1e-5) and (u + v < 1.0 - 1e-5)
0901  
0902      def is_convex(p_prev: Vector, p_curr: Vector, p_next: Vector) -> bool:
0903          cp = (p_curr.x - p_prev.x) * (p_next.y - p_curr.y) - (p_curr.y - p_prev.y) * (p_next.x - p_curr.x)
0904          return cp > 1e-8
0905  
0906      cur_c_indices = list(corner_indices)
0907      corner_triangles = []
0908      it = 0
0909      max_it = len(cur_c_indices) * len(cur_c_indices) * 2
0910  
0911      while len(cur_c_indices) > 3 and it < max_it:
0912          it += 1
0913          ear_found = False
0914          cm = len(cur_c_indices)
0915          for i in range(cm):
0916              idx_prev = cur_c_indices[(i - 1) % cm]
0917              idx_curr = cur_c_indices[i]
0918              idx_next = cur_c_indices[(i + 1) % cm]
0919  
0920              p_prev = pts_vec[idx_prev]
0921              p_curr = pts_vec[idx_curr]
0922              p_next = pts_vec[idx_next]
0923  
0924              if not is_convex(p_prev, p_curr, p_next):
0925                  continue
0926  
0927              has_pt = False
0928              for k in range(cm):
0929                  if k in ((i - 1) % cm, i, (i + 1) % cm):
0930                      continue
0931                  pt = pts_vec[cur_c_indices[k]]
0932                  if is_point_in_tri(pt, p_prev, p_curr, p_next):
0933                      has_pt = True
0934                      break
0935  
0936              if not has_pt:
0937                  corner_triangles.append((idx_prev, idx_curr, idx_next))
0938                  cur_c_indices.pop(i)
0939                  ear_found = True
0940                  break
0941  
0942          if not ear_found:
0943              corner_triangles.append((cur_c_indices[0], cur_c_indices[1], cur_c_indices[2]))
0944              cur_c_indices.pop(1)
0945  
0946      if len(cur_c_indices) == 3:
0947          corner_triangles.append((cur_c_indices[0], cur_c_indices[1], cur_c_indices[2]))
0948  
0949      # 5. Subdivide as arestas de cantos que possuem intermediários colineares
0950      final_triangles = []
0951      for tri in corner_triangles:
0952          sub_tris = [tri]
0953          for e_pair, inter_pts in edge_intermediates.items():
0954              if not inter_pts:
0955                  continue
0956              v_start, v_end = e_pair
0957  
0958              new_sub_tris = []
0959              for st in sub_tris:
0960                  a, b, c = st
0961                  found_edge = False
0962                  for p1, p2, p_opp in ((a, b, c), (b, c, a), (c, a, b)):
0963                      if (p1 == v_start and p2 == v_end) or (p1 == v_end and p2 == v_start):
0964                          found_edge = True
0965                          chain = [p1] + (inter_pts if p1 == v_start else list(reversed(inter_pts))) + [p2]
0966                          for ch_i in range(len(chain) - 1):
0967                              new_sub_tris.append((chain[ch_i], chain[ch_i + 1], p_opp))
0968                          break
0969                  if not found_edge:
0970                      new_sub_tris.append(st)
0971              sub_tris = new_sub_tris
0972  
0973          final_triangles.extend(sub_tris)
0974  
0975      if not is_ccw:
0976          final_triangles = [(t[0], t[2], t[1]) for t in final_triangles]
0977  
0978      return final_triangles

```

## Contrato do prisma Loop: src/geometry_loop.py:981–1039

```python

0981  def create_loop_prism_cutter(
0982      coords_world: List[Vector],
0983      inward_dir: Vector,
0984      depth_bu: float,
0985      outward_ext_bu: float = 1e-3,
0986      name: str = "temp_loop_prism",
0987  ) -> bpy.types.Object:
0988      """Constrói um prisma 3D fechado e manifold a partir de um contorno de coordenadas mundiais (B05)."""
0989      bm = bmesh.new()
0990      in_norm = inward_dir.normalized()
0991  
0992      # Remove pontos colineares para evitar triângulos degenerados
0993      pts = list(coords_world)
0994      changed = True
0995      while changed and len(pts) > 3:
0996          changed = False
0997          for i in range(len(pts)):
0998              p_prev, p, p_next = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
0999              d1 = p - p_prev
1000              d2 = p_next - p
1001              if d1.length < 1e-9 or d2.length < 1e-9 or d1.normalized().cross(d2.normalized()).length < 1e-5:
1002                  pts.pop(i)
1003                  changed = True
1004                  break
1005      coords_world = pts
1006      n = len(coords_world)
1007  
1008      # Projeta contorno para base 2D ortogonal para triangulação Ear Clipping
1009      u_vec, v_vec = _get_orthonormal_basis(in_norm)
1010      pts_2d = [Vector((p.dot(u_vec), p.dot(v_vec))) for p in coords_world]
1011      triangles_2d = triangulate_polygon_2d(pts_2d)
1012  
1013      top_verts = [bm.verts.new(p - outward_ext_bu * in_norm) for p in coords_world]
1014      bot_verts = [bm.verts.new(p + depth_bu * in_norm) for p in coords_world]
1015      bm.verts.ensure_lookup_table()
1016  
1017      # Paredes laterais
1018      for i in range(n):
1019          i_next = (i + 1) % n
1020          bm.faces.new((top_verts[i], top_verts[i_next], bot_verts[i_next], bot_verts[i]))
1021  
1022      # Tampas superior e inferior trianguladas estritamente dentro do domínio côncavo (B05)
1023      for t in triangles_2d:
1024          # Tampa superior: normal para fora (contra inward_dir)
1025          bm.faces.new((top_verts[t[2]], top_verts[t[1]], top_verts[t[0]]))
1026          # Tampa inferior: normal para fora (a favor de inward_dir)
1027          bm.faces.new((bot_verts[t[0]], bot_verts[t[1]], bot_verts[t[2]]))
1028  
1029      bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
1030  
1031      mesh = bpy.data.meshes.new(f"{name}_Mesh")
1032      bm.to_mesh(mesh)
1033      bm.free()
1034  
1035      obj = bpy.data.objects.new(name, mesh)
1036      obj.hide_viewport = False
1037      obj.hide_render = False
1038      bpy.context.scene.collection.objects.link(obj)
1039      return obj

```

## Contrato do prisma Material: src/geometry_material.py:347–364

```python

0347  def create_material_patch_prism_cutter(
0348      obj: bpy.types.Object,
0349      region_face_indices: List[int],
0350      inward_dir: Vector,
0351      depth_bu: float,
0352      outward_ext_bu: float = 1e-3,
0353      name: str = "temp_mat_prism",
0354      material_index: int = 0,
0355      interface_mat_mode: str = 'SOURCE',
0356      body_mat_index: int = 0,
0357      lateral_offset_bu: float = 0.0,
0358  ) -> bpy.types.Object:
0359      """Constrói um prisma 3D estanque a partir das faces exatas da região de material (B06).
0360      
0361      Preserva a tesselação e concavidades reais da região (ex: silhuetas em U ou reentrâncias),
0362      evitando tampas em n-gons planos que cruzam aberturas e geram películas/membranas espúrias.
0363      Valida a estanqueidade e ausência de degeneração antes da publicação (D01).
0364      Aplica offset lateral determinístico por lado no domínio de contato (INV-008).

```

## Profundidade/passante: src/geometry_loop.py:1042–1084

```python

1042  def slice_mesh_by_loop_extrude(
1043      obj: bpy.types.Object,
1044      target_name: str,
1045      indices: List[int],
1046      seed_face_idx: int,
1047      depth_mm: float,
1048      through_cut: bool = False,
1049      scene: Optional[bpy.types.Scene] = None,
1050  ) -> LoopSliceResult:
1051      """Corta o modelo extraindo o volume delimitado pelo contorno até a profundidade especificada.
1052      
1053      Parte A = volume extraído (prisma ∩ target)
1054      Parte B = restante do modelo (target \\ prisma)
1055      """
1056      actual_scene = scene if scene else bpy.context.scene
1057      scale_to_mm = get_scene_scale_to_mm(actual_scene)
1058  
1059      analysis = analyze_loop_region(obj, indices, seed_face_idx, scene=actual_scene)
1060      max_avail_mm = analysis["max_avail_depth_mm"]
1061  
1062      # Validação de espessura (T09)
1063      if not analysis.get("thickness_determined", True) and not through_cut:
1064          raise ValueError(
1065              "Espessura da peça não pôde ser determinada no ponto selecionado. "
1066              "Defina a profundidade manualmente ou ative a opção 'Corte Passante'."
1067          )
1068  
1069      if depth_mm > (max_avail_mm + 1e-3) and not through_cut:
1070          raise ValueError(
1071              f"A profundidade de extração ({depth_mm:.1f} mm) ultrapassa a espessura da peça "
1072              f"({max_avail_mm:.1f} mm). Reduza a profundidade ou ative a opção 'Corte Passante'."
1073          )
1074  
1075      coords_world = analysis["coords_world"]
1076      inward_dir = analysis["inward_dir_world"]
1077      depth_bu = depth_mm / scale_to_mm
1078  
1079      protrusion_h_bu = analysis["protrusion_height_mm"] / scale_to_mm
1080      outward_ext_bu = max(0.5 / scale_to_mm, protrusion_h_bu + 0.5 / scale_to_mm)
1081  
1082      if through_cut and depth_mm >= max_avail_mm:
1083          depth_bu = max(depth_bu, (max_avail_mm / scale_to_mm) + (1.0 / scale_to_mm))
1084  

```

## Booleanos e interface: src/geometry_loop.py:1093–1157

```python

1093      try:
1094          prism_obj = create_loop_prism_cutter(
1095              coords_world=coords_world,
1096              inward_dir=inward_dir,
1097              depth_bu=depth_bu,
1098              outward_ext_bu=outward_ext_bu,
1099              name=f"{target_name}_loop_prism",
1100          )
1101  
1102          bpy.context.view_layer.update()
1103  
1104          temp_obj_a = obj.copy()
1105          temp_obj_a.data = obj.data.copy()
1106          temp_obj_a.hide_viewport = False
1107          temp_obj_a.hide_render = False
1108          actual_scene.collection.objects.link(temp_obj_a)
1109          mod_a = temp_obj_a.modifiers.new(name="Extrude_Intersect", type='BOOLEAN')
1110          mod_a.operation = 'INTERSECT'
1111          mod_a.solver = 'EXACT'
1112          mod_a.object = prism_obj
1113  
1114          temp_obj_b = obj.copy()
1115          temp_obj_b.data = obj.data.copy()
1116          temp_obj_b.hide_viewport = False
1117          temp_obj_b.hide_render = False
1118          actual_scene.collection.objects.link(temp_obj_b)
1119          mod_b = temp_obj_b.modifiers.new(name="Extrude_Difference", type='BOOLEAN')
1120          mod_b.operation = 'DIFFERENCE'
1121          mod_b.solver = 'EXACT'
1122          mod_b.object = prism_obj
1123  
1124          bpy.context.view_layer.update()
1125          dg = bpy.context.evaluated_depsgraph_get()
1126  
1127          eval_obj_a = temp_obj_a.evaluated_get(dg)
1128          eval_a = eval_obj_a.to_mesh()
1129  
1130          eval_obj_b = temp_obj_b.evaluated_get(dg)
1131          eval_b = eval_obj_b.to_mesh()
1132  
1133          bm_a = bmesh.new()
1134          bm_a.from_mesh(eval_a)
1135          bm_a.transform(temp_obj_a.matrix_world)
1136  
1137          bm_b = bmesh.new()
1138          bm_b.from_mesh(eval_b)
1139          bm_b.transform(temp_obj_b.matrix_world)
1140  
1141          if len(bm_a.verts) == 0 or len(bm_b.verts) == 0:
1142              bm_a.free()
1143              bm_b.free()
1144              raise RuntimeError("A extração com profundidade gerou malha vazia para uma das partes.")
1145  
1146          bmesh.ops.recalc_face_normals(bm_a, faces=bm_a.faces[:])
1147          bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces[:])
1148  
1149          interface_origin = analysis["centroid_world"] + (depth_mm / scale_to_mm) * inward_dir
1150          cut_interface = build_cut_interface(
1151              origin_world=interface_origin,
1152              normal_a_to_b=inward_dir,
1153              boundary_points_world=coords_world,
1154              unit_scale=scale_to_mm,
1155              source_mode="LOOP",
1156          )
1157  

```