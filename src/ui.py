"""Interface de usuário para o Chest Part Splitter (Sidebar N > Chest > Part Splitter)."""

import bpy
from .constants import PANEL_TITLE


def draw_help_button(layout, topic: str):
    """Desenha botão compacto com ícone INFO para exibir ajuda e popup dinâmico."""
    row = layout.row(align=True)
    op = row.operator("chest.splitter_help", text="", icon='INFO', emboss=False)
    op.topic = topic


class VIEW3D_PT_chest_part_splitter(bpy.types.Panel):
    """Painel principal do Chest Part Splitter na barra lateral da Viewport 3D"""
    bl_label = PANEL_TITLE
    bl_idname = "VIEW3D_PT_chest_part_splitter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Chest'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.chest_splitter
        obj = settings.target_object

        # --- SEÇÃO 1: OBJETO ALVO ---
        box_target = layout.box()
        row_target_head = box_target.row(align=True)
        row_target_head.label(text="1. Objeto Alvo", icon='OBJECT_DATA')
        draw_help_button(row_target_head, "target_model")

        row_set = box_target.row(align=True)
        row_set.operator("chest.splitter_set_target", text="Usar selecionado como alvo", icon='EYEDROPPER')

        if obj:
            row_target_info = box_target.row(align=True)
            row_target_info.label(text=f"Alvo: {obj.name}", icon='CHECKMARK')
            row_target_info.operator("chest.splitter_edit_target", text="Editar Alvo", icon='EDITMODE_HLT')
            row_target_info.operator("chest.splitter_clear_target", text="", icon='X')

            # Métricas físicas e topológicas
            col_metrics = box_target.column(align=True)
            dims = settings.diag_dims_mm
            col_metrics.label(
                text=f"Dimensões: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm",
                icon='CON_SIZELIMIT'
            )
            col_metrics.label(
                text=f"Malha: {settings.diag_triangles:,} triângulos ({settings.diag_faces:,} faces)",
                icon='MESH_DATA'
            )
            col_metrics.label(
                text=f"Volume: {settings.diag_volume_mm3:,.1f} mm³",
                icon='MOD_FLUIDSIM'
            )

            # Avisos preventivos
            if settings.diag_has_unapplied_scale:
                box_warn = box_target.box()
                box_warn.alert = True
                box_warn.label(text="Aviso: Escala não aplicada!", icon='ERROR')
                box_warn.label(text="Cortes e folgas podem ser distorcidos.")
                box_warn.operator(
                    "chest.splitter_create_work_copy",
                    text="Criar cópia com escala aplicada",
                    icon='DUPLICATE'
                )

            if not settings.diag_is_manifold:
                box_mani = box_target.box()
                box_mani.alert = True
                box_mani.label(
                    text=f"Aviso: {settings.diag_non_manifold_edges} aresta(s) abertas/não-manifold.",
                    icon='ERROR'
                )

            if settings.diag_degenerate_faces > 0:
                box_target.label(
                    text=f"{settings.diag_degenerate_faces} face(s) degeneradas detectadas.",
                    icon='INFO'
                )
        else:
            box_target.label(text="Nenhum alvo selecionado. Selecione um objeto malha.", icon='INFO')

        layout.separator()

        # --- SEÇÃO 2: MÉTODO DE CORTE ---
        box_split = layout.box()
        box_split.label(text="2. Método de Corte", icon='MOD_BOOLEAN')

        col_mode = box_split.column()
        col_mode.prop(settings, "split_mode", expand=True)

        if not obj:
            box_split.label(text="Defina um objeto alvo primeiro.", icon='INFO')
        elif settings.split_mode == 'PLANE':
            # --- Guia de Corte e Alinhamentos ---
            box_guide = box_split.box()
            row_guide_head = box_guide.row(align=True)
            row_guide_head.label(text="Posicionamento do Plano", icon='ORIENTATION_LOCAL')
            draw_help_button(row_guide_head, "split_plane")

            row_guide_btn = box_guide.row(align=True)
            row_guide_btn.operator("chest.splitter_create_or_focus_guide", text="Focar Guia 3D", icon='GIZMO')

            box_guide.label(text="Alinhamentos Rápidos:")
            row_align_view = box_guide.row(align=True)
            op_v = row_align_view.operator("chest.splitter_align_plane", text="Vista", icon='VIEW_CAMERA')
            op_v.align_mode = 'VIEW'
            op_c = row_align_view.operator("chest.splitter_align_plane", text="Cursor", icon='PIVOT_CURSOR')
            op_c.align_mode = 'CURSOR'
            op_f = row_align_view.operator("chest.splitter_align_plane", text="Face", icon='FACESEL')
            op_f.align_mode = 'FACE'

            row_align_axes = box_guide.row(align=True)
            op_x = row_align_axes.operator("chest.splitter_align_plane", text="Eixo X")
            op_x.align_mode = 'X'
            op_y = row_align_axes.operator("chest.splitter_align_plane", text="Eixo Y")
            op_y.align_mode = 'Y'
            op_z = row_align_axes.operator("chest.splitter_align_plane", text="Eixo Z")
            op_z.align_mode = 'Z'

            # Visualização do Plano (F02)
            col_plane_vis = box_guide.column(align=True)
            row_pvis = col_plane_vis.row(align=True)
            row_pvis.prop(settings, "show_plane_preview", text="Mostrar Plano")
            row_pvis.prop(settings, "show_plane_cut_line", text="Linha de Corte")
            if settings.show_plane_preview:
                col_plane_vis.prop(settings, "plane_preview_opacity", text="Opacidade (%)", slider=True)
            col_plane_vis.prop(settings, "plane_offset_mm", text="Deslocamento (mm)")

        elif settings.split_mode == 'LOOP':
            box_loop = box_split.box()
            row_loop_head = box_loop.row(align=True)
            row_loop_head.label(text="Corte por Contorno (Loop)", icon='MOD_EDGESPLIT')
            draw_help_button(row_loop_head, "split_loop")

            row_cap = box_loop.row(align=True)
            row_cap.scale_y = 1.2
            row_cap.operator("chest.splitter_capture_loop", text="Capturar Contorno", icon='VIEW_ORTHO')
            row_cap.operator("chest.splitter_capture_face_boundary", text="Capturar das Faces", icon='FACESEL')

            if settings.loop_is_captured:
                box_loop.label(text=f"Vértices no contorno: {settings.loop_vertex_count}", icon='VERTEXSEL')
                if settings.loop_is_planar:
                    box_loop.label(text=f"Status: Planar ({settings.loop_planarity_deviation_mm:.2f}mm desvio)", icon='CHECKMARK')
                else:
                    box_loop.label(text=f"Aviso: Não-planar ({settings.loop_planarity_deviation_mm:.2f}mm desvio)", icon='ERROR')
                
                box_loop.prop(
                    settings, 
                    "show_loop_highlight", 
                    text="Destacar Contorno no Viewport", 
                    icon='RESTRICT_VIEW_OFF' if settings.show_loop_highlight else 'RESTRICT_VIEW_ON'
                )

            row_seed = box_loop.row(align=True)
            row_seed.scale_y = 1.2
            row_seed.operator("chest.splitter_define_seed_face", text="Escolher Região", icon='FACESEL')
            draw_help_button(row_seed, "loop_region")

            col_seed_hint = box_loop.column()
            col_seed_hint.scale_y = 0.8
            col_seed_hint.label(text="Dica: Selecione apenas 1 face dentro da região desejada.", icon='INFO')

            if settings.loop_seed_face_index >= 0:
                box_loop.label(text=f"Região de Referência: Face #{settings.loop_seed_face_index}", icon='CHECKMARK')

            # Comportamento de corte por contorno
            box_behavior = box_loop.box()
            box_behavior.prop(settings, "loop_behavior", text="Comportamento")

            if settings.loop_behavior == 'AUTO' and settings.loop_auto_reason:
                box_dec = box_behavior.box()
                lbl_mode = "Destacar Saliência" if settings.loop_detected_mode == 'DETACH' else "Extrair com Profundidade"
                box_dec.label(text=f"Decisão: {lbl_mode}", icon='INFO')
                col_r = box_dec.column()
                col_r.scale_y = 0.8
                col_r.label(text=settings.loop_auto_reason)

            show_depth = (settings.loop_behavior == 'EXTRUDE') or (
                settings.loop_behavior == 'AUTO' and settings.loop_detected_mode == 'EXTRUDE'
            )
            if show_depth:
                box_depth = box_behavior.box()
                row_depth_head = box_depth.row(align=True)
                row_depth_head.label(text="Extração com Profundidade", icon='CON_SIZELIMIT')
                draw_help_button(row_depth_head, "loop_extrude")
                box_depth.prop(settings, "loop_extrude_depth_mm", text="Profundidade (mm)")
                box_depth.prop(settings, "loop_through_cut", text="Corte Passante")

            show_detach_base = (settings.loop_behavior == 'DETACH') or (
                settings.loop_behavior == 'AUTO' and settings.loop_detected_mode == 'DETACH'
            )
            if show_detach_base:
                box_base = box_behavior.box()
                box_base.prop(settings, "loop_detach_add_base", text="Adicionar base para encaixe")
                if settings.loop_detach_add_base:
                    box_base.prop(settings, "loop_detach_base_depth_mm", text="Profundidade da base (mm)")
                    box_base.prop(settings, "loop_detach_base_clearance_mm", text="Folga lateral (mm)")

            if settings.loop_is_captured and settings.loop_is_planar:
                row_solid_loop = box_loop.row(align=True)
                row_solid_loop.operator("chest.splitter_create_cutter_from_selection", text="Criar Cortador desta Seleção", icon='MOD_SOLIDIFY')


        elif settings.split_mode == 'SOLID':
            box_solid = box_split.box()
            box_solid.label(text="Configuração do Cortador Sólido", icon='MESH_UVSPHERE')

            col_src = box_solid.column(align=True)
            col_src.prop(settings, "solid_source", expand=True)

            if settings.solid_source == 'PRIMITIVE':
                col_prim = box_solid.column(align=True)
                col_prim.prop(settings, "solid_primitive_type", text="Formato")
                row_prim_btn = box_solid.row(align=True)
                row_prim_btn.scale_y = 1.1
                row_prim_btn.operator("chest.splitter_create_solid_cutter", text="Criar", icon='ADD')
                row_prim_btn.operator("chest.splitter_focus_solid_cutter", text="Focar", icon='VIEW_ZOOM')
                row_prim_btn.operator("chest.splitter_reset_solid_cutter", text="Reiniciar", icon='FILE_REFRESH')
            else:
                col_exist = box_solid.column(align=True)
                col_exist.prop(settings, "solid_cutter_object", text="Cortador")
                row_pick = box_solid.row(align=True)
                row_pick.operator("chest.splitter_select_existing_cutter", text="Usar Selecionado", icon='EYEDROPPER')
                row_pick.operator("chest.splitter_copy_selected_as_cutter", text="Copiar Selecionado", icon='DUPLICATE')

            # Ações e Alinhamento do Cortador
            cutter = settings.solid_cutter_object
            if cutter and cutter.name in bpy.data.objects:
                row_actions = box_solid.row(align=True)
                row_actions.operator("chest.splitter_duplicate_solid_cutter", text="Duplicar Cortador", icon='DUPLICATE')
                op_align = row_actions.operator("chest.splitter_align_solid_cutter", text="Alinhar à Face", icon='SNAP_FACE')
                op_align.align_mode = 'ACTIVE_FACE'
                op_align.anchor = 'SUPPORT_FACE'

                # Dimensões físicas locais (mm)
                box_dims = box_solid.box()
                box_dims.label(text="Dimensões Físicas Locais (mm):", icon='CON_SIZELIMIT')
                col_dims = box_dims.column(align=True)
                col_dims.prop(settings, "solid_cutter_width_mm")
                col_dims.prop(settings, "solid_cutter_height_mm")
                col_dims.prop(settings, "solid_cutter_depth_mm")

                # Diagnóstico do Cortador Selecionado
                box_cutter_diag = box_solid.box()
                box_cutter_diag.label(text=f"Cortador: '{cutter.name}'", icon='OUTLINER_OB_MESH')
                if settings.solid_cutter_is_manifold:
                    box_cutter_diag.label(text=f"Status: Fechado / 100% Manifold ({settings.solid_cutter_triangles:,} tris)", icon='CHECKMARK')
                    box_cutter_diag.label(text=f"Volume: {settings.solid_cutter_volume_mm3:,.1f} mm³")
                else:
                    box_cutter_warn = box_cutter_diag.box()
                    box_cutter_warn.alert = True
                    box_cutter_warn.label(text=f"Erro: {settings.solid_cutter_non_manifold_edges} aresta(s) abertas!", icon='ERROR')
                    box_cutter_warn.label(text="Cortador precisa ser um sólido 3D estanque.")


        elif settings.split_mode == 'MATERIAL':
            box_mat = box_split.box()
            row_mat_head = box_mat.row(align=True)
            row_mat_head.label(text="Divisão por Material (Fase 4)", icon='MATERIAL')
            draw_help_button(row_mat_head, "split_material")

            mats = obj.data.materials if (obj and obj.data) else []
            if not mats:
                box_mat.label(text="O modelo não possui materiais atribuídos.", icon='ERROR')
                box_mat.label(text="Adicione slots de materiais na aba Material.")
            else:
                col_mat_list = box_mat.column(align=True)
                col_mat_list.label(text="Escolha a cor/área a extrair (Parte A):")
                for idx, m in enumerate(mats):
                    mat_name = m.name if m else f"Material #{idx}"
                    is_active = (settings.material_split_index == idx)
                    icon_btn = 'CHECKBOX_HLT' if is_active else 'CHECKBOX_DEHLT'
                    row_m = col_mat_list.row(align=True)
                    op_sel = row_m.operator("chest.splitter_select_split_material", text=f"{idx}: {mat_name}", icon=icon_btn)
                    op_sel.material_index = idx
                    op_sel.region_index = 0

                # Atalho: escolher pela face selecionada no Modo de Edição
                row_pick = box_mat.row(align=True)
                row_pick.operator("chest.splitter_pick_material_region", text="Usar Face Selecionada (Edit Mode)", icon='RESTRICT_SELECT_OFF')

                # Diagnóstico dinâmico do material selecionado
                from .geometry_material import analyze_material_structure, list_material_regions
                mat_idx = min(settings.material_split_index, len(mats) - 1)

                regions = list_material_regions(obj, mat_idx)
                if len(regions) > 1:
                    box_reg = box_mat.box()
                    box_reg.label(text=f"Esta cor aparece em {len(regions)} áreas separadas:", icon='STICKY_UVS_DISABLE')
                    col_reg = box_reg.column(align=True)
                    for r in regions:
                        is_r = (settings.material_region_index == r["index"])
                        op_r = col_reg.operator(
                            "chest.splitter_select_split_material",
                            text=f"Área {r['index'] + 1} ({r['face_count']} faces)",
                            icon='RADIOBUT_ON' if is_r else 'RADIOBUT_OFF',
                        )
                        op_r.material_index = mat_idx
                        op_r.region_index = r["index"]

                analysis = analyze_material_structure(obj, mat_idx, settings.material_region_index)
                box_diag_mat = box_mat.box()
                if analysis.get("valid"):
                    mat_type = analysis.get("type")
                    if mat_type == "CLOSED_COMPONENT":
                        box_diag_mat.label(text="Tipo: Componente 3D Fechado (Sólido)", icon='CHECKMARK')
                        box_diag_mat.label(text=f"Faces: {analysis['face_count']:,} | Malha estanque para fatiador.")
                    else:
                        box_diag_mat.label(text="Tipo: Região Superficial (Com Profundidade)", icon='INFO')
                        box_diag_mat.label(text=f"Faces: {analysis['face_count']:,} | Fronteira contínua.")
                        box_mat_depth = box_mat.box()
                        box_mat_depth.label(text="Opções de Extração (C02/C03):", icon='PREFERENCES')
                        box_mat_depth.prop(settings, "material_extraction_mode", text="Modo")
                        if settings.material_extraction_mode == 'EXTRUDE':
                            box_mat_depth.prop(settings, "material_extrude_depth_mm", text="Profundidade (mm)")
                        box_mat_depth.prop(settings, "material_interface_mat_mode", text="Interface")
                else:
                    box_diag_mat.alert = True
                    box_diag_mat.label(text=f"Aviso: {analysis.get('error', 'Estrutura inválida')}", icon='ERROR')

                row_sol_tools = box_mat.row(align=True)
                row_sol_tools.operator("chest.splitter_create_cutter_from_selection", text="Criar Cortador Desta Seleção", icon='MOD_SOLIDIFY')
                row_sol_tools.operator("chest.splitter_create_corner_box_cutter", text="Caixa para Quina", icon='MESH_CUBE')


        layout.separator()

        # --- SEÇÃO 3: ENCAIXES E FOLGAS (Antes da Prévia!) ---
        box_conn = layout.box()
        row_conn_head = box_conn.row(align=True)
        row_conn_head.label(text="3. Encaixes & Folgas", icon='SNAP_VERTEX')
        draw_help_button(row_conn_head, "connectors")

        # Folga Física entre Peças (E01)
        box_part_clearance = box_conn.box()
        box_part_clearance.label(text="Folga da Interface entre Peças:", icon='DRIVER_DISTANCE')
        if settings.split_mode in ('PLANE', 'MATERIAL'):
            box_part_clearance.prop(settings, "part_clearance_mm", text="Folga (mm)", slider=True)
            if settings.part_clearance_mm > 0.0:
                box_part_clearance.prop(settings, "part_clearance_apply_to", text="Aplicar em")
            if settings.split_mode == 'MATERIAL':
                box_part_clearance.prop(settings, "part_clearance_bottom_enable", text="Folga de fundo separada")
                if settings.part_clearance_bottom_enable:
                    box_part_clearance.prop(settings, "part_clearance_bottom_mm", text="Folga de fundo (mm)")
        else:
            col_disabled = box_part_clearance.column()
            col_disabled.enabled = False
            col_disabled.prop(settings, "part_clearance_mm", text="Folga (mm)", slider=True)
            box_part_clearance.label(
                text="Folga de interface disponível apenas nos modos Plano e Material.", 
                icon='INFO'
            )

        if settings.split_mode == 'SOLID':
            box_conn.label(text="Encaixes de pinos não são suportados no modo Cortador Sólido.", icon='INFO')
        else:
            row_enable = box_conn.row(align=True)
            row_enable.prop(settings, "connector_enabled", text="Ativar Encaixes", toggle=True, icon='CHECKBOX_HLT' if settings.connector_enabled else 'CHECKBOX_DEHLT')

            if settings.connector_enabled:
                # Formato do Encaixe
                col_shape = box_conn.column(align=True)
                col_shape.label(text="Formato do Encaixe:")
                col_shape.prop(settings, "connector_type", expand=True)

                # Lado do Macho / Fêmea
                box_male = box_conn.box()
                box_male.label(text="Posição dos Pinos (Macho):", icon='SNAP_NORMAL')

                top_part = 'A' if settings.part_a_is_superior else 'B'
                is_top = (settings.connector_male_part == top_part)
                cur_desc = "Parte Superior" if is_top else "Parte Inferior"

                row_male_pick = box_male.row(align=True)
                row_male_pick.prop(settings, "connector_male_part", expand=True)

                row_male_btn = box_male.row(align=True)
                row_male_btn.scale_y = 1.2
                row_male_btn.operator(
                    "chest.splitter_invert_male_female",
                    text=f"Inverter: Pinos na {cur_desc}",
                    icon='ARROW_LEFTRIGHT'
                )

                # Dimensões Nominais do Macho
                box_dims = box_conn.box()
                box_dims.label(text="Dimensões Nominais:", icon='CON_SIZELIMIT')
                if settings.connector_type == 'CAPSULE':
                    box_dims.prop(settings, "connector_diameter_mm", text="Espessura / Diâmetro (mm)", slider=True)
                    box_dims.prop(settings, "connector_capsule_length_mm", text="Comprimento Lateral (mm)", slider=True)
                    if settings.connector_max_safe_lateral_mm > 0:
                        box_dims.label(
                            text=f"Limite Seguro Máx: {settings.connector_max_safe_lateral_mm:.1f} mm (anti-colisão)",
                            icon='INFO',
                        )
                else:
                    box_dims.prop(settings, "connector_diameter_mm", slider=True)
                box_dims.prop(settings, "connector_length_mm", text="Profundidade de Inserção (mm)", slider=True)
                box_dims.prop(settings, "connector_chamfer_mm", slider=True)

                # Folgas de Encaixe Físico
                box_clear = box_conn.box()
                row_clear_head = box_clear.row(align=True)
                row_clear_head.label(text="Folgas Físicas de Montagem (FDM):", icon='DRIVER')
                draw_help_button(row_clear_head, "clearance")

                # Botões rápidos de preset
                row_presets = box_clear.row(align=True)
                row_presets.label(text="Presets:")
                for p_code, p_lbl in [('TIGHT', "0.10"), ('NORMAL', "0.15"), ('EASY', "0.20"), ('LOOSE', "0.25")]:
                    op_p = row_presets.operator("chest.splitter_apply_connector_preset", text=p_lbl)
                    op_p.preset = p_code

                box_clear.prop(settings, "clearance_per_side_mm", slider=True)
                box_clear.label(text=f"Folga total no diâmetro: {settings.clearance_per_side_mm * 2:.2f} mm", icon='INFO')
                box_clear.prop(settings, "end_clearance_mm", slider=True)

                # Distribuição
                box_dist = box_conn.box()
                box_dist.label(text="Distribuição no Corte:", icon='PARTICLE_DATA')
                box_dist.prop(settings, "connector_distribution", expand=True)
                box_dist.prop(settings, "connector_edge_margin_mm", slider=True)
                box_dist.prop(settings, "adjust_to_valid_area")

                if settings.connector_distribution == 'MANUAL':
                    box_manual = box_conn.box()
                    row_man_head = box_manual.row(align=True)
                    row_man_head.label(text="Posicionamento Manual:", icon='RESTRICT_SELECT_OFF')

                    row_click = box_manual.row(align=True)
                    row_click.scale_y = 1.35
                    if settings.is_editing_connectors:
                        row_click.operator(
                            "chest.splitter_confirm_manual_connectors",
                            text="Confirmar Posições e Gerar Prévia",
                            icon='CHECKMARK'
                        )
                    else:
                        row_click.operator(
                            "chest.splitter_edit_manual_connectors",
                            text="Editar Posições dos Pinos",
                            icon='EDITMODE_HLT'
                        )

                    row_view = box_manual.row(align=True)
                    row_view.operator("chest.splitter_view_cut_face", text="Ver Face de Encaixe", icon='VIEW_CAMERA')

                    if settings.is_editing_connectors:
                        box_mode = box_manual.box()
                        row_mode_head = box_mode.row(align=True)
                        row_mode_head.label(text="Ação do Clique 3D no Modelo:", icon='CURSOR')
                        row_sub = box_mode.row(align=True)
                        row_sub.prop(settings, "manual_editor_submode", expand=True)

                    n_manual = len(settings.manual_connectors)
                    row_actions = box_manual.row(align=True)
                    row_actions.operator("chest.splitter_add_manual_connector", text="Adicionar", icon='ADD')
                    row_rem = row_actions.row(align=True)
                    row_rem.enabled = (n_manual > 0)
                    row_rem.operator("chest.splitter_remove_manual_connector", text="Remover", icon='REMOVE')
                    row_clr = row_actions.row(align=True)
                    row_clr.enabled = (n_manual > 0)
                    row_clr.operator("chest.splitter_clear_manual_connectors", text="Limpar", icon='TRASH')

                    if n_manual == 0:
                        box_manual.label(text="Nenhum pino posicionado. Clique em 'Editar Posições' para adicionar.", icon='INFO')
                    else:
                        box_manual.label(text=f"Total de Pinos: {n_manual}", icon='LAYER_ACTIVE')
                        box_edit = box_manual.box()
                        idx = settings.manual_connector_index
                        if 0 <= idx < n_manual:
                            active_conn = settings.manual_connectors[idx]
                            row_sel = box_edit.row(align=True)
                            row_sel.prop(settings, "manual_connector_index", text=f"Pino #{idx + 1}")
                            row_sel.operator("chest.splitter_remove_manual_connector", text="", icon='X')

                            row_coords = box_edit.row(align=True)
                            row_coords.prop(active_conn, "u_mm", text="U (mm)")
                            row_coords.prop(active_conn, "v_mm", text="V (mm)")
                            if settings.connector_type == 'CAPSULE':
                                box_edit.prop(active_conn, "yaw_deg", text="Rotação Yaw (°)", slider=True)

                            if not getattr(active_conn, "is_valid", True):
                                row_err = box_edit.row(align=True)
                                row_err.alert = True
                                reason = getattr(active_conn, "status_reason", "") or getattr(active_conn, "validation_msg", "") or "Posição fora do domínio / margem violada"
                                row_err.label(
                                    text=reason,
                                    icon='CANCEL'
                                )
                            else:
                                box_edit.label(text="Posição Válida", icon='CHECKMARK')
                        else:
                            box_edit.prop(settings, "manual_connector_index", text="Pino Ativo")
                else:
                    box_dist.operator(
                        "chest.splitter_convert_pattern_to_manual",
                        text="Converter Padrão para Manual",
                        icon='GREASEPENCIL'
                    )

        layout.separator()

        # --- SEÇÃO 4: PRÉVIA E VISUALIZAÇÃO ---
        if obj and settings.split_mode in ('PLANE', 'SOLID', 'LOOP', 'MATERIAL'):
            box_preview = layout.box()
            box_preview.label(text="4. Prévia do Corte", icon='RESTRICT_VIEW_OFF')

            # Alerta de preview desatualizado (Critério U2)
            if settings.session_status == 'PREVIEW_STALE':
                box_stale = box_preview.box()
                box_stale.alert = True
                box_stale.label(
                    text="Os ajustes mudaram. Atualize a prévia antes de criar as peças.",
                    icon='ERROR'
                )

            row_preview = box_preview.row(align=True)
            row_preview.scale_y = 1.3
            row_preview.operator("chest.splitter_generate_preview", text="Gerar / Atualizar Preview", icon='PLAY')
            row_preview.operator("chest.splitter_remove_preview", text="Remover Prévia", icon='X')

            if settings.connector_enabled and settings.connector_distribution == 'MANUAL':
                row_reedit = box_preview.row(align=True)
                row_reedit.operator(
                    "chest.splitter_edit_manual_connectors",
                    text="Editar Posições Novamente",
                    icon='EDITMODE_HLT'
                )

            if settings.split_mode in ('PLANE', 'SOLID'):
                row_inv = box_preview.row(align=True)
                if settings.split_mode == 'SOLID':
                    lbl_inv = "Inverter: A=Ext / B=Int" if settings.invert_sides else "Inverter: A=Int / B=Ext"
                else:
                    lbl_inv = "Inverter Lados (Ativo)" if settings.invert_sides else "Inverter Lados A / B"
                row_inv.operator("chest.splitter_invert_sides", text=lbl_inv, icon='ARROW_LEFTRIGHT')

            # Visualização Montada / Explodida e Cores
            if settings.session_status in ('PREVIEW_VALID', 'PREVIEW_STALE', 'COMMITTED'):
                box_view = box_preview.box()
                row_view_head = box_view.row(align=True)
                row_view_head.label(text="Visualização & Cores:", icon='VIEW3D')
                draw_help_button(row_view_head, "explosion")

                box_view.prop(settings, "view_mode", expand=True)

                if settings.view_mode == 'EXPLODED':
                    box_view.prop(settings, "explosion_distance_mm", slider=True)
                    box_view.prop(settings, "invert_explosion", toggle=True, icon='ARROW_LEFTRIGHT')

                box_view.prop(settings, "preview_color_mode", text="")

                # Diagnósticos de Partes A e B
                box_diag_parts = box_preview.box()
                box_diag_parts.label(text="Resultados do Corte", icon='CHECKMARK')

                lbl_tag_a = " (Superior)" if settings.part_a_is_superior else " (Inferior)"
                lbl_tag_b = " (Inferior)" if settings.part_a_is_superior else " (Superior)"

                col_a = box_diag_parts.box()
                col_a.label(text=f"Parte A{lbl_tag_a}", icon='MESH_CUBE')
                col_a.label(text=f"Volume: {settings.part_a_volume_mm3:,.1f} mm³")
                dims_a = settings.part_a_dims_mm
                col_a.label(text=f"Dimensões: {dims_a[0]:.1f} x {dims_a[1]:.1f} x {dims_a[2]:.1f} mm")
                col_a.label(text=f"Malha: {settings.part_a_triangles:,} tris | {settings.part_a_components} ilha(s)")
                if not settings.part_a_is_manifold:
                    col_a.label(text=f"Aviso: {settings.part_a_non_manifold_edges} aresta(s) abertas", icon='ERROR')

                col_b = box_diag_parts.box()
                col_b.label(text=f"Parte B{lbl_tag_b}", icon='MESH_CUBE')
                col_b.label(text=f"Volume: {settings.part_b_volume_mm3:,.1f} mm³")
                dims_b = settings.part_b_dims_mm
                col_b.label(text=f"Dimensões: {dims_b[0]:.1f} x {dims_b[1]:.1f} x {dims_b[2]:.1f} mm")
                col_b.label(text=f"Malha: {settings.part_b_triangles:,} tris | {settings.part_b_components} ilha(s)")
                if not settings.part_b_is_manifold:
                    col_b.label(text=f"Aviso: {settings.part_b_non_manifold_edges} aresta(s) abertas", icon='ERROR')

                # Balanço de Volume
                box_vol = box_diag_parts.box()
                vol_ok = settings.volume_diff_pct < 0.5
                icon_vol = 'CHECKMARK' if vol_ok else 'ERROR'
                box_vol.label(
                    text=f"Soma Volumes: {settings.part_sum_volume_mm3:,.1f} mm³ (dif: {settings.volume_diff_pct:.2f}%)",
                    icon=icon_vol
                )

                # Ação rápida de separação por material/cor
                row_sep = box_diag_parts.row()
                row_sep.operator("chest.splitter_separate_by_material", text="Separar por Cores / Materiais", icon='COLOR')

            layout.separator()

            # --- SEÇÃO 5: CRIAR PEÇAS (CONFIRMAÇÃO) ---
            box_commit = layout.box()
            box_commit.label(text="5. Criar Peças", icon='MOD_SOLIDIFY')

            if settings.session_status == 'PREVIEW_VALID':
                row_commit = box_commit.row()
                row_commit.scale_y = 1.4
                row_commit.operator("chest.splitter_commit_parts", text="Confirmar Divisão", icon='CHECKMARK')

                row_rest = box_commit.row()
                row_rest.operator("chest.splitter_remove_preview", text="Remover Prévia", icon='X')

            elif settings.session_status == 'PREVIEW_STALE':
                box_warn_commit = box_commit.box()
                box_warn_commit.label(text="Atualize a prévia antes de confirmar as peças.", icon='INFO')
                row_rest = box_commit.row()
                row_rest.operator("chest.splitter_remove_preview", text="Remover Prévia", icon='X')

            elif settings.session_status == 'COMMITTED':
                box_commit.label(text="Peças finais geradas na coleção CHEST_SPLITTER_PARTS.", icon='CHECKMARK')
                row_cont = box_commit.row()
                row_cont.scale_y = 1.3
                row_cont.operator("chest.splitter_continue_on_receiver", text="Continuar no corpo remanescente", icon='FORWARD')
                row_revert = box_commit.row()
                row_revert.scale_y = 1.1
                row_revert.operator("chest.splitter_revert_cut", text="Reverter este corte", icon='LOOP_BACK')
                box_commit.operator("chest.splitter_redo_session", text="Refazer / Novo Corte", icon='FILE_REFRESH')

            elif settings.session_status == 'CONFIGURED':
                hint_text = "Posicione o cortador e clique em 'Gerar / Atualizar Preview'." if settings.split_mode == 'SOLID' else "Posicione o plano ou contorno e clique em 'Gerar / Atualizar Preview'."
                box_commit.label(text=hint_text, icon='INFO')

        # --- SEÇÃO 6: EXPORTAÇÃO PARA IMPRESSÃO 3D ---
        if settings.session_status in ('PREVIEW_VALID', 'COMMITTED'):
            layout.separator()
            box_exp = layout.box()
            box_exp.label(text="6. Exportação para Fatiador (Bambu / Orca / Prusa)", icon='EXPORT')

            col_exp_cfg = box_exp.column(align=True)
            col_exp_cfg.prop(settings, "export_format")
            col_exp_cfg.prop(settings, "export_directory")

            row_exp_act = box_exp.row()
            row_exp_act.scale_y = 1.3
            row_exp_act.operator("chest.splitter_export_parts", text="Exportar Peças Selecionadas", icon='EXPORT')

        # --- FEEDBACK DE STATUS ---
        status_text = settings.get_localized_status() if hasattr(settings, "get_localized_status") else settings.last_status
        if status_text:
            layout.separator()
            box_status = layout.box()
            icon_status = 'INFO'
            if settings.last_status_level == 'SUCCESS':
                icon_status = 'CHECKMARK'
            elif settings.last_status_level == 'WARNING':
                icon_status = 'ERROR'
                box_status.alert = True
            elif settings.last_status_level == 'ERROR':
                icon_status = 'CANCEL'
                box_status.alert = True

            import textwrap
            paragraphs = status_text.split('\n')
            for p_idx, para in enumerate(paragraphs):
                lines = textwrap.wrap(para, width=44) or [para]
                for l_idx, line in enumerate(lines):
                    if p_idx == 0 and l_idx == 0:
                        box_status.label(text=line, icon=icon_status)
                    else:
                        box_status.label(text=line)



def register():
    try:
        bpy.utils.register_class(VIEW3D_PT_chest_part_splitter)
    except ValueError:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(VIEW3D_PT_chest_part_splitter)
    except RuntimeError:
        pass
